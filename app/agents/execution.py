"""Execution Agent: the ClickUp-like task/project manager and Problem-Solving Assistant."""
import json
from datetime import date, datetime, timedelta

from app.agents.base import BaseAgent

P0_KEYWORDS = ("patient safety", "patient harm", "clinical harm", "data breach",
               "privacy breach", "security breach", "harmful output", "unsafe output")
P1_KEYWORDS = ("production", "outage", "down", "cannot use", "major customer",
               "false negative", "compliance failure")

CLOSURE_CRITERIA = [
    "Root cause confirmed.",
    "Corrective action completed.",
    "Acceptance criteria passed.",
    "Metrics returned to acceptable thresholds.",
    "Affected users or customers informed.",
    "Documentation updated.",
    "Risk register updated.",
    "Monitoring added.",
    "Decision log completed.",
    "Product owner approved closure.",
]

ROADMAP_TEMPLATE = {
    "now": [
        ("Close critical compliance gaps", "Resolve every critical gap from the compliance report before build starts."),
        ("Finalize the AI PRD", "Complete problem statement, target user, data/model requirements, human-review and safety rules."),
        ("Stakeholder alignment review", "Confirm owners, approvers (RACI), and decision authority for launch and risk acceptance."),
    ],
    "next": [
        ("Data readiness assessment", "Verify data sources, quality, consent/privacy classification, and representativeness."),
        ("Model evaluation plan", "Define evaluation dataset, acceptance thresholds (precision/recall/latency), and bias checks."),
        ("Pilot design with human-review workflow", "Design the pilot: scope, users, human-review rules, and rollback procedure."),
    ],
    "later": [
        ("Pilot launch", "Run the pilot with monitoring, audit logging, and weekly review of overrides and failures."),
        ("Metrics review and go/no-go", "Compare pilot metrics against targets; document the go/no-go decision with evidence."),
        ("Scale and rollout plan", "Plan staged rollout, support model, retraining cadence, and ongoing governance reviews."),
    ],
}


def period_key(period: str, day: date | None = None) -> str:
    day = day or date.today()
    if period == "daily":
        return day.isoformat()
    if period == "weekly":
        return f"{day.isocalendar().year}-W{day.isocalendar().week:02d}"
    return day.strftime("%Y-%m")


class ExecutionAgent(BaseAgent):
    name = "execution"

    # ---------- checklists ----------
    def ensure_checklist(self, period: str, day: date | None = None, project_id=None):
        key = period_key(period, day)
        row = self.db.execute(
            "SELECT id FROM checklist_instances WHERE period=? AND period_key=? AND project_id IS ?",
            (period, key, project_id),
        ).fetchone()
        if row:
            return row["id"]
        cur = self.db.execute(
            "INSERT INTO checklist_instances(period, period_key, project_id) VALUES (?,?,?)",
            (period, key, project_id),
        )
        instance_id = cur.lastrowid
        templates = self.db.execute(
            "SELECT * FROM checklist_templates WHERE period=? AND active=1 ORDER BY order_index",
            (period,),
        ).fetchall()
        for t in templates:
            self.db.execute(
                "INSERT INTO checklist_items(instance_id, template_id, section, text, order_index) "
                "VALUES (?,?,?,?,?)",
                (instance_id, t["id"], t["section"], t["item_text"], t["order_index"]),
            )
        self.log_event("checklist_generated", "checklist_instance", instance_id,
                       f"Generated {period} checklist ({key})")
        return instance_id

    # ---------- tasks from compliance gaps ----------
    def create_tasks_from_gaps(self, report_id: int) -> list[int]:
        findings = self.db.execute(
            """SELECT f.*, r.name AS rule_name, r.category, r.recommendation AS rule_rec
               FROM compliance_findings f JOIN compliance_rules r ON r.id = f.rule_id
               WHERE f.report_id=? AND f.status IN ('missing','partial') AND f.task_id IS NULL""",
            (report_id,),
        ).fetchall()
        report = self.db.execute("SELECT * FROM compliance_reports WHERE id=?", (report_id,)).fetchone()
        today = date.today()
        created = []
        for f in findings:
            if f["category"] == "critical" and f["status"] == "missing":
                priority, days = "high", 3
            elif f["category"] == "critical" or (f["category"] == "important" and f["status"] == "missing"):
                priority, days = "medium", 7
            else:
                priority, days = "low", 14
            chapters = json.loads(f["kb_chapter_ids"] or "[]")
            refs = ""
            if chapters:
                titles = self.db.execute(
                    f"SELECT number, title FROM kb_chapters WHERE id IN ({','.join('?' * len(chapters))})",
                    chapters,
                ).fetchall()
                refs = "\n\nGuide references: " + "; ".join(
                    f"Chapter {t['number']}: {t['title']}" for t in titles)
            cur = self.db.execute(
                "INSERT INTO tasks(project_id, title, description, priority, due_date, source, source_ref) "
                "VALUES (?,?,?,?,?,?,?)",
                (report["project_id"],
                 f"[Compliance] Add {f['rule_name']}",
                 (f["recommendation"] or f["rule_rec"] or "") + refs,
                 priority, (today + timedelta(days=days)).isoformat(),
                 "compliance_gap", f"finding:{f['id']}"),
            )
            self.db.execute("UPDATE compliance_findings SET task_id=? WHERE id=?", (cur.lastrowid, f["id"]))
            created.append(cur.lastrowid)
        if created:
            self.log_event("created_tasks_from_gaps", "compliance_report", report_id,
                           f"Created {len(created)} tasks from compliance gaps",
                           payload={"task_ids": created})
        return created

    # ---------- roadmap ----------
    def generate_roadmap(self, project_id: int, project_name: str, description: str = "") -> list[int]:
        existing = self.db.execute(
            "SELECT COUNT(*) FROM roadmap_items WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        if existing:
            return []
        items = ROADMAP_TEMPLATE
        if self.ai.available:
            raw = self.ai.complete(
                "You generate AI product roadmaps for a healthcare AI product manager who prioritizes "
                "safety, traceability, human review, and regulatory compliance. Reply ONLY with JSON: "
                '{"now": [["title","description"],...], "next": [...], "later": [...]} '
                "with exactly 3 items per horizon.",
                f"Project: {project_name}\nDescription: {description}\n"
                f"Base template to personalize: {json.dumps(items)}",
                max_tokens=1500,
            )
            if raw:
                try:
                    start, end = raw.index("{"), raw.rindex("}") + 1
                    parsed = json.loads(raw[start:end])
                    if all(h in parsed for h in ("now", "next", "later")):
                        items = {h: [(i[0], i[1]) for i in parsed[h]] for h in ("now", "next", "later")}
                except (ValueError, KeyError, IndexError, TypeError):
                    pass
        created = []
        for horizon, entries in items.items():
            for idx, (title, desc) in enumerate(entries):
                cur = self.db.execute(
                    "INSERT INTO roadmap_items(project_id, title, description, horizon, order_index) "
                    "VALUES (?,?,?,?,?)",
                    (project_id, title, desc, horizon, idx),
                )
                created.append(cur.lastrowid)
        self.log_event("roadmap_generated", "project", project_id,
                       f"Generated {len(created)}-item roadmap for {project_name}")
        return created

    # ---------- dashboards ----------
    def daily_focus(self):
        today = date.today().isoformat()
        top3 = self.db.execute(
            """SELECT t.*, p.name AS project_name FROM tasks t
               LEFT JOIN projects p ON p.id = t.project_id
               WHERE t.status != 'done'
               ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                        t.due_date IS NULL, t.due_date, t.created_at
               LIMIT 3"""
        ).fetchall()
        overdue = self.db.execute(
            """SELECT t.*, p.name AS project_name FROM tasks t
               LEFT JOIN projects p ON p.id = t.project_id
               WHERE t.status != 'done' AND t.due_date IS NOT NULL AND t.due_date < ?
               ORDER BY t.due_date""",
            (today,),
        ).fetchall()
        blockers = self.db.execute(
            "SELECT b.*, p.name AS project_name FROM blockers b "
            "LEFT JOIN projects p ON p.id = b.project_id WHERE b.status='open' ORDER BY b.raised_at DESC"
        ).fetchall()
        risks = self.db.execute(
            "SELECT r.*, p.name AS project_name FROM risks r "
            "LEFT JOIN projects p ON p.id = r.project_id "
            "WHERE r.status='open' AND r.score >= 15 ORDER BY r.score DESC"
        ).fetchall()
        decisions = self.db.execute(
            "SELECT d.*, p.name AS project_name FROM decisions d "
            "LEFT JOIN projects p ON p.id = d.project_id WHERE d.status='pending' ORDER BY d.created_at"
        ).fetchall()
        issues = self.db.execute(
            "SELECT i.*, p.name AS project_name FROM issues i "
            "LEFT JOIN projects p ON p.id = i.project_id "
            "WHERE i.status NOT IN ('resolved','closed') ORDER BY i.severity, i.detected_at DESC"
        ).fetchall()
        return {"top3": top3, "overdue": overdue, "blockers": blockers,
                "risks": risks, "decisions": decisions, "issues": issues}

    # ---------- problem-solving assistant ----------
    def classify_severity(self, title: str, description: str, affected_area: str) -> str:
        text = f"{title} {description} {affected_area}".lower()
        if any(k in text for k in P0_KEYWORDS):
            return "P0"
        if any(k in text for k in P1_KEYWORDS):
            return "P1"
        return "P2"

    def triage_issue(self, issue_id: int):
        issue = self.db.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        if not issue:
            return
        if not issue["closure_criteria"]:
            criteria = json.dumps([{"text": c, "done": 0} for c in CLOSURE_CRITERIA])
            self.db.execute("UPDATE issues SET closure_criteria=? WHERE id=?", (criteria, issue_id))
        if issue["severity"] in ("P0", "P1"):
            due = date.today() if issue["severity"] == "P0" else date.today() + timedelta(days=1)
            self.db.execute(
                "INSERT INTO blockers(project_id, title, description, severity) VALUES (?,?,?,?)",
                (issue["project_id"], f"[{issue['severity']}] {issue['title']}",
                 issue["description"], "high"),
            )
            self.db.execute(
                "INSERT INTO tasks(project_id, title, description, priority, due_date, source, source_ref) "
                "VALUES (?,?,?,?,?,?,?)",
                (issue["project_id"], f"[{issue['severity']}] Contain and investigate: {issue['title']}",
                 "Immediate containment, evidence preservation, and root-cause investigation.",
                 "high", due.isoformat(), "issue", f"issue:{issue_id}"),
            )
            self.log_event("issue_escalated", "issue", issue_id,
                           f"{issue['severity']} issue escalated: blocker and same/next-day task created")
        else:
            self.log_event("issue_triaged", "issue", issue_id,
                           f"{issue['severity']} issue added to backlog workflow")

    def analyze_issue(self, issue_id: int) -> str | None:
        """AI hook: root-cause hypotheses across the standard categories."""
        issue = self.db.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        if not issue or not self.ai.available:
            return None
        result = self.ai.complete(
            "You are an AI PM problem-solving assistant for governed healthcare AI products. "
            "Given an issue, produce: (1) a clear problem statement in the format "
            "'For [affected user], the product is producing [actual] instead of [expected], causing [impact]'; "
            "(2) ranked root-cause hypotheses across these categories: data, model, prompt/retrieval, "
            "integration/software, workflow/requirements, process/people, vendor, compliance — each with "
            "evidence needed to test it; (3) what data/evidence is missing; (4) recommended immediate "
            "containment, investigation steps, corrective and preventive actions with suggested owners "
            "and verification methods. Never invent facts; mark missing information explicitly. "
            "Use concise markdown.",
            f"Issue title: {issue['title']}\nSeverity: {issue['severity']}\n"
            f"Affected area: {issue['affected_area'] or 'unknown'}\n"
            f"Description: {issue['description'] or '(none provided)'}",
            max_tokens=2500,
        )
        if result:
            self.db.execute("UPDATE issues SET ai_recommendation=? WHERE id=?", (result, issue_id))
            self.log_event("issue_analyzed", "issue", issue_id, "AI root-cause analysis generated")
        return result

    def can_close_issue(self, issue_id: int) -> bool:
        issue = self.db.execute("SELECT closure_criteria FROM issues WHERE id=?", (issue_id,)).fetchone()
        if not issue or not issue["closure_criteria"]:
            return False
        criteria = json.loads(issue["closure_criteria"])
        return all(c.get("done") for c in criteria)
