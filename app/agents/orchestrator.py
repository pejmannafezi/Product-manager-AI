"""Orchestrator: runs New Project Intake by coordinating all three agents."""
import json

from app.agents.base import BaseAgent
from app.agents.compliance import ComplianceAgent
from app.agents.execution import ExecutionAgent
from app.agents.knowledge import KnowledgeAgent
from app.agents.planning import PlanningAgent
from app.services.ai import AIClient
from app.services.docparse import extract_text

STRATEGY_FALLBACK = """# Strategy Outline: {name}

## Vision
Deliver "{name}" as a governed AI capability that is safe, traceable, auditable,
and embedded in the user's real workflow.

## Strategic Pillars
1. **Safety and human oversight** — every high-risk output gets defined human review,
   override recording, and a rollback path.
2. **Evidence-driven delivery** — measurable success metrics with targets and thresholds;
   no roadmap item ships without acceptance criteria.
3. **Regulatory readiness** — documentation, decision log, and audit trail maintained
   from day one, not reconstructed before an audit.

## First 90 Days
- **Days 1–30:** close critical compliance gaps; finalize the AI PRD; confirm RACI and
  decision authority.
- **Days 31–60:** data readiness assessment; model evaluation plan with thresholds;
  pilot design including human-review workflow.
- **Days 61–90:** controlled pilot with monitoring and audit logging; metrics review;
  documented go/no-go decision.

## Recommended Reading (from your guide)
{reading_list}
"""


class Orchestrator(BaseAgent):
    name = "orchestrator"

    def __init__(self, conn, ai: AIClient):
        super().__init__(conn, ai)
        self.knowledge = KnowledgeAgent(conn, ai)
        self.execution = ExecutionAgent(conn, ai)
        self.compliance = ComplianceAgent(conn, ai, knowledge=self.knowledge)
        self.planning = PlanningAgent(conn, ai)

    def run_intake(self, name: str, description: str = "", phase: str = "discovery",
                   target_date: str = "", owner: str = "", customer: str = "",
                   objective: str = "", requirements: str = "", stakeholders: str = "",
                   start_date: str = "", deliverables: str = "",
                   filename: str = "", file_bytes: bytes = b"") -> dict:
        cur = self.db.execute(
            "INSERT INTO projects(name, description, status, phase, owner, customer, objective, "
            "start_date, target_date, requirements, stakeholders) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (name, description, "intake", phase, owner, customer, objective,
             start_date or None, target_date or None, requirements or None, stakeholders or None),
        )
        project_id = cur.lastrowid
        # user-entered deliverables (one per line) become scheduled rows later
        self._seed_deliverables(project_id, deliverables)
        self.log_event("intake_started", "project", project_id, f"New project intake: {name}")

        # 1. Compliance review (uploaded document, or all-missing report without one)
        doc_error = None
        if file_bytes:
            try:
                text = extract_text(filename, file_bytes)
                cur = self.db.execute(
                    "INSERT INTO documents(project_id, filename, text) VALUES (?,?,?)",
                    (project_id, filename, text),
                )
                report_id = self.compliance.review_document(project_id, cur.lastrowid)
            except Exception as exc:
                doc_error = str(exc)
                report_id = self.compliance.review_missing_document(project_id)
        else:
            report_id = self.compliance.review_missing_document(project_id)

        # 2. Reading list from the knowledge base
        reading = self.knowledge.relevant_chapters(f"{name} {description} {objective}", 4)
        self.log_event("reading_list", "project", project_id,
                       f"Attached {len(reading)} relevant guide chapters",
                       payload={"chapters": [dict(r) for r in reading]})

        # 3. Tasks from gaps, roadmap, recurring checklists
        task_ids = self.execution.create_tasks_from_gaps(report_id)
        self.execution.generate_roadmap(project_id, name, description)
        for period in ("daily", "weekly", "monthly"):
            self.execution.ensure_checklist(period)

        # 4. Planning engine: milestones, deliverables schedule, resourcing, risks,
        #    then a prioritized task backbone with dependencies + critical path.
        project = self.db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        plan = self.planning.generate_plan(project)
        project = self.db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        plan_task_ids = self.planning.generate_project_tasks(project)

        # 5. Strategy outline (AI-personalized when available, templated otherwise)
        strategy = self._strategy_outline(name, description, objective, reading, project_id)
        self.db.execute(
            "INSERT INTO documents(project_id, filename, mime, text) VALUES (?,?,?,?)",
            (project_id, "strategy-outline.md", "text/markdown", strategy),
        )
        self.log_event("intake_completed", "project", project_id,
                       f"Intake complete: compliance report, {len(task_ids) + len(plan_task_ids)} tasks, "
                       f"{plan['milestones']} milestones, {plan['deliverables']} deliverables, "
                       "roadmap, checklists, risks, and strategy outline generated")

        return {"project_id": project_id, "report_id": report_id,
                "task_ids": task_ids, "plan": plan, "reading": reading,
                "strategy": strategy, "doc_error": doc_error}

    def _seed_deliverables(self, project_id: int, deliverables: str):
        """Store user-entered deliverables (one per line); the planning engine
        schedules their due-dates across the project window."""
        for i, line in enumerate(l.strip() for l in (deliverables or "").splitlines()):
            if line:
                self.db.execute(
                    "INSERT INTO deliverables(project_id, title, order_index) VALUES (?,?,?)",
                    (project_id, line, i))

    def _strategy_outline(self, name, description, objective, reading, project_id=None) -> str:
        reading_list = "\n".join(
            f"- Chapter {r['number']}: {r['title']}" for r in reading) or "- (knowledge base not ingested yet)"
        if self.ai.available:
            context = self.reference_context(f"{name} {description} {objective}", project_id)
            result = self.ai.complete(
                "You write product strategy outlines for an AI PM managing governed healthcare AI. "
                "Prioritize safety, traceability, human review, auditability, and regulatory compliance. "
                "Produce concise markdown with: Vision, 3 Strategic Pillars, First 90 Days plan "
                "(3 phases), and key assumptions to validate. No preamble.",
                self._with_context(
                    context,
                    f"Project: {name}\nDescription: {description}\nObjective: {objective}\n"
                    f"Relevant guide chapters:\n{reading_list}",
                ),
                max_tokens=2000,
            )
            if result:
                return result + f"\n\n## Recommended Reading (from your guide)\n{reading_list}\n"
        return STRATEGY_FALLBACK.format(name=name, reading_list=reading_list)
