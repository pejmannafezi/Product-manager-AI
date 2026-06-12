from app.agents.compliance import ComplianceAgent
from app.agents.execution import ExecutionAgent
from app.services.ai import AIClient

FULL_PRD = """
AI PRD: PreOp Missing Information Detector

Problem Statement
For preoperative nurses, the problem is that 18% of patient records arrive with
missing information, causing surgical delays. This pain point affects scheduling daily.

Target User
The intended user is the preoperative clinician (nurse persona) reviewing records.

Human Review
All high-risk outputs require human review by a clinician before any action.
Every override is recorded with a human-in-the-loop workflow.

Safety
Patient safety analysis: potential harm includes a missed allergy. Adverse event
reporting is mandatory and unsafe output triggers escalation.

Rollback Plan
A kill switch disables the feature instantly; the fallback is the manual checklist
workflow. Rollback restores the previous release.

Data Requirements
Training data comes from the EHR data source; the dataset contains PHI and data
quality thresholds are defined.

Model Requirements
Model performance targets: precision >= 0.90, recall >= 0.85, latency < 2s.

Success Metrics
KPI: reduce missing preoperative information from 18% to below 5%. Success criteria
include adoption by 80% of nurses.

Regulatory Considerations
HIPAA applies; FDA classification reviewed; compliance evidence is archived.

Risk Assessment
Risk register maintained with mitigation owners and residual risk review.

Stakeholders
RACI: product owner is accountable; clinical lead responsible.

Timeline
Milestone plan with target date for pilot launch on the roadmap.

Scope
Out of scope: medication dosing recommendations. Non-goals listed.

Monitoring
Model monitoring with drift detection and alerting thresholds.

Evaluation
Evaluation against a held-out validation set; acceptance criteria documented;
clinical validation before release.
"""

WEAK_DOC = """
Project idea

We want to improve the AI for our hospital. The problem is that things are slow.
"""


def _review(conn, text):
    ai = AIClient()
    agent = ComplianceAgent(conn, ai)
    cur = conn.execute(
        "INSERT INTO documents(filename, text) VALUES (?,?)", ("test.txt", text))
    report_id = agent.review_document(None, cur.lastrowid)
    return conn.execute("SELECT * FROM compliance_reports WHERE id=?", (report_id,)).fetchone()


def test_full_prd_scores_ready(conn):
    report = _review(conn, FULL_PRD)
    assert report["score"] >= 85, f"expected Ready, got {report['score']}"
    assert report["grade"] == "Ready"


def test_weak_doc_scores_not_ready(conn):
    report = _review(conn, WEAK_DOC)
    assert report["score"] < 50, f"expected Not Ready, got {report['score']}"
    rollback = conn.execute(
        """SELECT f.status FROM compliance_findings f
           JOIN compliance_rules r ON r.id=f.rule_id
           WHERE f.report_id=? AND r.artifact_key='rollback_plan'""",
        (report["id"],)).fetchone()
    assert rollback["status"] == "missing"


def test_gaps_become_prioritized_tasks(conn):
    report = _review(conn, WEAK_DOC)
    execution = ExecutionAgent(conn, AIClient())
    task_ids = execution.create_tasks_from_gaps(report["id"])
    assert task_ids
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE source='compliance_gap'").fetchall()
    assert all(t["due_date"] for t in tasks)
    # critical+missing artifacts must produce high-priority tasks
    high = [t for t in tasks if t["priority"] == "high"]
    assert any("Rollback" in t["title"] for t in high)
    # rerun is idempotent: findings already linked to tasks are skipped
    assert execution.create_tasks_from_gaps(report["id"]) == []
