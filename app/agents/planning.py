"""Planning Agent: turns project info + knowledge into a realistic plan.

Produces milestones, a dated deliverables schedule, resource recommendations,
a risk assessment, and a prioritized project task list with dependencies and a
critical path. Every AI step has a rule-based fallback so the app works with no
ANTHROPIC_API_KEY (app invariant)."""
import json

from app.agents.base import BaseAgent
from app.services import schedule

# ----------------------------- rule-based fallbacks (governed healthcare AI) ---
MILESTONE_FALLBACK = [
    ("Discovery & requirements sign-off", "Confirm problem, target users, scope, success metrics, and constraints."),
    ("Data readiness & AI PRD", "Assess data sources/quality/consent; finalize the AI PRD and human-review rules."),
    ("Model evaluation plan approved", "Define evaluation dataset, acceptance thresholds, and bias checks."),
    ("Pilot build & human-review workflow", "Build the pilot with monitoring, audit logging, and a rollback path."),
    ("Pilot review & go/no-go", "Compare pilot metrics against targets; document the go/no-go decision."),
    ("Launch & monitoring", "Staged rollout with governance reviews and a retraining cadence."),
]

DELIVERABLE_FALLBACK = [
    ("AI PRD", "Problem statement, users, data/model requirements, safety & human-review rules.", "Product"),
    ("Data readiness report", "Sources, quality, consent/privacy classification, representativeness.", "Data"),
    ("Model evaluation report", "Metrics vs thresholds, bias checks, error analysis.", "ML"),
    ("Pilot plan", "Scope, users, human-review rules, rollback procedure, success criteria.", "Product"),
    ("Go/No-Go decision memo", "Evidence-based recommendation with risks and conditions.", "PM"),
    ("Monitoring & governance plan", "Dashboards, alerts, audit logging, and review cadence.", "Ops"),
]

RESOURCING_FALLBACK = (
    "Recommended core team: Product Manager (owner), ML/Data Scientist, Data Engineer, "
    "Backend Engineer, Designer (part-time), Compliance/Privacy reviewer, and a Clinical/Domain "
    "SME for governed healthcare AI. Add QA and an MLOps engineer before the pilot."
)

RISK_FALLBACK = [
    ("Training data not representative of the target population", "data", 3, 4,
     "Define the target population; audit data coverage; add representative samples; document gaps."),
    ("Model performance degrades in production (drift)", "model", 3, 4,
     "Monitor metrics; set drift alerts; schedule retraining; keep human review on high-risk outputs."),
    ("Insufficient human oversight on high-risk outputs", "operational", 2, 5,
     "Define human-review thresholds and override logging; train reviewers; audit overrides."),
    ("Regulatory/compliance gaps before launch", "regulatory", 3, 4,
     "Run the compliance review early; close critical gaps; maintain a decision log and audit trail."),
    ("Privacy / consent issues with sensitive data", "privacy", 2, 5,
     "Classify data; verify the consent basis; minimize PII; apply access controls and retention limits."),
]


class PlanningAgent(BaseAgent):
    name = "execution"  # logged under the execution agent (ClickUp-like surface)

    # ----------------------------------------------------------- whole plan ---
    def generate_plan(self, project) -> dict:
        """Create milestones + deliverables schedule + resourcing + risk assessment.
        Idempotent per artifact: skips a section that already has rows."""
        pid = project["id"]
        start, end = schedule.project_window(project["start_date"], project["target_date"])
        ms_titles, dl_items, resourcing, risks = self._ai_plan(project) if self.ai.available else (None, None, None, None)
        ms_titles = ms_titles or MILESTONE_FALLBACK
        dl_items = dl_items or DELIVERABLE_FALLBACK
        resourcing = resourcing or RESOURCING_FALLBACK
        risks = risks or RISK_FALLBACK

        created = {"milestones": 0, "deliverables": 0, "risks": 0}

        if not self._has_rows("milestones", pid):
            dates = schedule.spread_dates(start, end, len(ms_titles))
            for i, ((title, desc), due) in enumerate(zip(ms_titles, dates)):
                self.db.execute(
                    "INSERT INTO milestones(project_id, title, description, due_date, order_index) "
                    "VALUES (?,?,?,?,?)", (pid, title, desc, due.isoformat(), i))
                created["milestones"] += 1

        if not self._has_rows("deliverables", pid):
            dates = schedule.spread_dates(start, end, len(dl_items))
            for i, (item, due) in enumerate(zip(dl_items, dates)):
                title, desc, owner = (tuple(item) + ("", ""))[:3]
                self.db.execute(
                    "INSERT INTO deliverables(project_id, title, description, owner, due_date, order_index) "
                    "VALUES (?,?,?,?,?,?)", (pid, title, desc, owner, due.isoformat(), i))
                created["deliverables"] += 1
        else:
            # user-seeded deliverables without dates -> schedule them across the window
            undated = self.db.execute(
                "SELECT id FROM deliverables WHERE project_id=? AND (due_date IS NULL OR due_date='') "
                "ORDER BY order_index", (pid,)).fetchall()
            dates = schedule.spread_dates(start, end, len(undated))
            for row, due in zip(undated, dates):
                self.db.execute("UPDATE deliverables SET due_date=? WHERE id=?", (due.isoformat(), row["id"]))

        if resourcing and not project["resourcing"]:
            self.db.execute("UPDATE projects SET resourcing=? WHERE id=?", (resourcing, pid))

        if not self._has_rows("risks", pid):
            for title, category, likelihood, impact, mitigation in risks:
                self.db.execute(
                    "INSERT INTO risks(project_id, title, category, likelihood, impact, mitigation) "
                    "VALUES (?,?,?,?,?,?)", (pid, title, category, likelihood, impact, mitigation))
                created["risks"] += 1

        self.log_event("plan_generated", "project", pid,
                       f"Generated {created['milestones']} milestones, {created['deliverables']} "
                       f"deliverables, and {created['risks']} risks",
                       payload={"project_id": pid, **created})
        return created

    def _ai_plan(self, project):
        context = self.reference_context(
            f"{project['name']} {project['description'] or ''} {project['objective'] or ''} "
            f"{project['requirements'] or ''}", project["id"])
        raw = self.ai.complete(
            "You plan governed healthcare AI products. From the project info, produce a realistic plan. "
            "Reply ONLY with JSON: {\"milestones\":[[\"title\",\"description\"],... 5-7 in order], "
            "\"deliverables\":[[\"title\",\"description\",\"owner\"],...], "
            "\"resourcing\":\"one paragraph of recommended roles/team\", "
            "\"risks\":[[\"title\",\"category\",likelihood_1to5,impact_1to5,\"mitigation\"],... 4-6]} "
            "where category is one of data|model|regulatory|privacy|security|operational|vendor|clinical|other. "
            "Prioritize safety, traceability, human review, auditability, and compliance.",
            self._with_context(
                context,
                f"Project: {project['name']}\nDescription: {project['description'] or ''}\n"
                f"Objective: {project['objective'] or ''}\nRequirements: {project['requirements'] or ''}\n"
                f"Stakeholders: {project['stakeholders'] or ''}\nPhase: {project['phase'] or ''}"),
            max_tokens=2500,
        )
        if not raw:
            return None, None, None, None
        try:
            parsed = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
            ms = [(m[0], m[1]) for m in parsed.get("milestones", []) if len(m) >= 2] or None
            dl = [(d[0], d[1], d[2] if len(d) > 2 else "") for d in parsed.get("deliverables", []) if len(d) >= 2] or None
            res = parsed.get("resourcing") or None
            risks = [(r[0], r[1], int(r[2]), int(r[3]), r[4])
                     for r in parsed.get("risks", []) if len(r) >= 5] or None
            return ms, dl, res, risks
        except (ValueError, KeyError, IndexError, TypeError):
            return None, None, None, None

    # --------------------------------------------------- project task list ----
    def generate_project_tasks(self, project) -> list[int]:
        """Create a prioritized, dependency-linked task backbone from milestones
        (one task per milestone, chained), plus optional AI sub-tasks. Marks the
        critical path. Skips if plan tasks already exist."""
        pid = project["id"]
        if self.db.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id=? AND source='plan'", (pid,)).fetchone()[0]:
            return []
        milestones = self.db.execute(
            "SELECT * FROM milestones WHERE project_id=? ORDER BY order_index", (pid,)).fetchall()
        if not milestones:
            return []

        sub_by_ms = self._ai_subtasks(project, milestones) if self.ai.available else {}
        created: list[int] = []
        prev_backbone: int | None = None
        n = len(milestones)
        for idx, m in enumerate(milestones):
            priority = "high" if idx < max(2, n // 3) else ("medium" if idx < (2 * n) // 3 else "low")
            depends = json.dumps([prev_backbone]) if prev_backbone else None
            cur = self.db.execute(
                "INSERT INTO tasks(project_id, milestone_id, title, description, priority, due_date, "
                "depends_on, source, source_ref) VALUES (?,?,?,?,?,?,?,?,?)",
                (pid, m["id"], f"Deliver: {m['title']}", m["description"], priority, m["due_date"],
                 depends, "plan", f"milestone:{m['id']}"))
            backbone_id = cur.lastrowid
            created.append(backbone_id)
            # optional AI sub-tasks for this milestone — can start after the previous milestone
            for sub in sub_by_ms.get(idx, [])[:3]:
                sdep = json.dumps([prev_backbone]) if prev_backbone else None
                scur = self.db.execute(
                    "INSERT INTO tasks(project_id, milestone_id, title, description, priority, due_date, "
                    "depends_on, source, source_ref) VALUES (?,?,?,?,?,?,?,?,?)",
                    (pid, m["id"], sub, "", priority, m["due_date"], sdep, "plan", f"milestone:{m['id']}"))
                created.append(scur.lastrowid)
            prev_backbone = backbone_id

        self._recompute_critical_path(pid)
        self.log_event("tasks_generated", "project", pid,
                       f"Generated {len(created)} planning tasks across {n} milestones",
                       payload={"project_id": pid, "task_ids": created})
        return created

    def _ai_subtasks(self, project, milestones) -> dict[int, list[str]]:
        context = self.reference_context(
            f"{project['name']} {project['description'] or ''}", project["id"])
        ms_lines = "\n".join(f"{i}. {m['title']}" for i, m in enumerate(milestones))
        raw = self.ai.complete(
            "You break product milestones into concrete next-action tasks for an AI PM. "
            "Reply ONLY with JSON mapping each milestone index to 2-3 short task titles: "
            "{\"0\":[\"...\"],\"1\":[\"...\"],...}. Imperative, specific, no numbering.",
            self._with_context(context, f"Milestones:\n{ms_lines}"),
            max_tokens=1200,
        )
        if not raw:
            return {}
        try:
            parsed = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
            return {int(k): [str(x) for x in v] for k, v in parsed.items() if isinstance(v, list)}
        except (ValueError, KeyError, IndexError, TypeError):
            return {}

    def _recompute_critical_path(self, pid: int):
        tasks = [dict(r) for r in self.db.execute(
            "SELECT id, depends_on, due_date FROM tasks WHERE project_id=?", (pid,)).fetchall()]
        crit = schedule.critical_path(tasks)
        self.db.execute("UPDATE tasks SET is_critical=0 WHERE project_id=?", (pid,))
        for tid in crit:
            self.db.execute("UPDATE tasks SET is_critical=1 WHERE id=?", (tid,))

    # ------------------------------------------------------------- helpers ----
    def _has_rows(self, table: str, pid: int) -> bool:
        return bool(self.db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE project_id=?", (pid,)).fetchone()[0])

    def regenerate(self, project) -> dict:
        """Clear AI-planning artifacts (milestones, deliverables, plan tasks) and
        rebuild. Leaves manually-entered risks/decisions/tasks untouched."""
        pid = project["id"]
        self.db.execute("DELETE FROM tasks WHERE project_id=? AND source='plan'", (pid,))
        self.db.execute("DELETE FROM milestones WHERE project_id=?", (pid,))
        self.db.execute("DELETE FROM deliverables WHERE project_id=?", (pid,))
        counts = self.generate_plan(project)
        fresh = self.db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        task_ids = self.generate_project_tasks(fresh)
        counts["tasks"] = len(task_ids)
        return counts
