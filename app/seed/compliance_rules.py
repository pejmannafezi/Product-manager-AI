"""Compliance rules derived from the user's AI PRD template and governance framework.

Each rule checks whether a project document contains a required artifact before the
project starts. Categories: critical (weight 3), important (weight 2), standard (weight 1).
"""
import json

RULES = [
    # --- critical (weight 3) ---
    dict(
        artifact_key="problem_statement", name="Problem Statement", category="critical", weight=3,
        keywords=["problem statement", "the problem", "pain point", "customer problem", "user problem"],
        heading_regex=r"problem",
        recommendation="Add a clear problem statement: who is affected, what happens today, and the measurable impact.",
        kb_query="problem statement define AI problem",
    ),
    dict(
        artifact_key="target_user", name="Target User", category="critical", weight=3,
        keywords=["target user", "persona", "intended user", "end user", "clinician", "target users"],
        heading_regex=r"target user|users?|persona",
        recommendation="Define the target user and their workflow: role, environment, and how they will interact with the AI output.",
        kb_query="target user persona user research workflow",
    ),
    dict(
        artifact_key="human_review", name="Human Review / Oversight", category="critical", weight=3,
        keywords=["human in the loop", "human review", "human oversight", "clinician review", "override", "human-in-the-loop"],
        heading_regex=r"human[- ]?(review|oversight|in[- ]the[- ]loop)",
        recommendation="Specify human-review requirements: which outputs require review, who reviews them, and how overrides are recorded.",
        kb_query="human in the loop review oversight design patterns",
    ),
    dict(
        artifact_key="safety", name="Safety Requirements", category="critical", weight=3,
        keywords=["patient safety", "safety requirement", "safety plan", "harm", "adverse event", "unsafe output"],
        heading_regex=r"safety",
        recommendation="Document safety requirements: potential harms, unacceptable failure modes, and safeguards (especially for clinical use).",
        kb_query="safety harmful output risk patient",
    ),
    dict(
        artifact_key="rollback_plan", name="Rollback / Fallback Plan", category="critical", weight=3,
        keywords=["rollback", "roll back", "kill switch", "fallback", "degradation plan", "disable the feature"],
        heading_regex=r"rollback|fallback",
        recommendation="Add a rollback plan: how the AI feature is disabled or reverted, and what the manual fallback workflow is.",
        kb_query="rollback fallback incident response failure",
    ),
    # --- important (weight 2) ---
    dict(
        artifact_key="data_requirements", name="Data Requirements", category="important", weight=2,
        keywords=["data requirement", "training data", "data source", "dataset", "PHI", "data quality"],
        heading_regex=r"data (requirements?|strategy|sources?)",
        recommendation="Document data requirements: sources, quality, consent/privacy classification (PHI), representativeness, and known bias.",
        kb_query="data strategy quality training data requirements",
    ),
    dict(
        artifact_key="model_requirements", name="Model Requirements", category="important", weight=2,
        keywords=["model requirement", "accuracy", "precision", "recall", "latency", "performance target", "model performance"],
        heading_regex=r"model (requirements?|performance)",
        recommendation="Define model requirements: performance targets (precision/recall/latency), acceptance thresholds, and known limitations.",
        kb_query="model performance precision recall evaluation metrics",
    ),
    dict(
        artifact_key="success_metrics", name="Success Metrics", category="important", weight=2,
        keywords=["success metric", "KPI", "north star", "adoption", "key performance indicator", "success criteria"],
        heading_regex=r"metrics?|kpis?|success criteria",
        recommendation="Define success metrics with formulas, targets, and warning thresholds, tied to a business decision.",
        kb_query="metrics KPIs evaluation success measurement",
    ),
    dict(
        artifact_key="regulatory", name="Regulatory Considerations", category="important", weight=2,
        keywords=["FDA", "HIPAA", "regulatory", "compliance", "510(k)", "GDPR", "regulation"],
        heading_regex=r"regulat|compliance",
        recommendation="Document regulatory considerations: jurisdiction, product classification, applicable regulations, and required approvals.",
        kb_query="regulatory compliance FDA HIPAA healthcare",
    ),
    dict(
        artifact_key="risk_assessment", name="Risk Assessment", category="important", weight=2,
        keywords=["risk register", "risk assessment", "mitigation", "risk analysis", "residual risk"],
        heading_regex=r"risks?",
        recommendation="Add a risk assessment: risk description, probability, impact, mitigation, owner, and approval requirements.",
        kb_query="risk management register mitigation",
    ),
    # --- standard (weight 1) ---
    dict(
        artifact_key="stakeholders", name="Stakeholders & Ownership", category="standard", weight=1,
        keywords=["stakeholder", "RACI", "responsible", "accountable", "product owner"],
        heading_regex=r"stakeholders?|raci|ownership",
        recommendation="List stakeholders and ownership (RACI): who approves requirements, model changes, launch, and incident decisions.",
        kb_query="stakeholder management RACI responsibility",
    ),
    dict(
        artifact_key="timeline_milestones", name="Timeline & Milestones", category="standard", weight=1,
        keywords=["timeline", "milestone", "target date", "launch date", "roadmap"],
        heading_regex=r"timeline|milestones?|roadmap",
        recommendation="Add a timeline with milestones: start date, target completion, dependencies, and the next milestone.",
        kb_query="roadmap milestones planning",
    ),
    dict(
        artifact_key="scope_boundaries", name="Scope Boundaries", category="standard", weight=1,
        keywords=["out of scope", "non-goals", "scope", "not included", "boundaries"],
        heading_regex=r"scope|non[- ]goals",
        recommendation="State scope boundaries explicitly: what the product does NOT do (non-goals / out of scope).",
        kb_query="requirements scope PRD",
    ),
    dict(
        artifact_key="monitoring_plan", name="Monitoring Plan", category="standard", weight=1,
        keywords=["model monitoring", "drift", "alerting", "monitoring plan", "post-launch monitoring"],
        heading_regex=r"monitoring",
        recommendation="Add a monitoring plan: drift detection, alert thresholds, review frequency, and who responds to alerts.",
        kb_query="monitoring drift alerts post launch",
    ),
    dict(
        artifact_key="evaluation_plan", name="Evaluation Plan", category="standard", weight=1,
        keywords=["evaluation", "validation set", "clinical validation", "test plan", "acceptance criteria"],
        heading_regex=r"evaluation|validation|acceptance",
        recommendation="Define the evaluation plan: evaluation dataset, acceptance criteria, and validation steps before release.",
        kb_query="evaluation framework validation acceptance criteria",
    ),
]


def seed(conn):
    if conn.execute("SELECT COUNT(*) FROM compliance_rules").fetchone()[0]:
        return
    for r in RULES:
        conn.execute(
            "INSERT INTO compliance_rules(artifact_key, name, category, weight, keywords, "
            "heading_regex, recommendation, kb_query) VALUES (?,?,?,?,?,?,?,?)",
            (r["artifact_key"], r["name"], r["category"], r["weight"],
             json.dumps(r["keywords"]), r["heading_regex"], r["recommendation"], r["kb_query"]),
        )
