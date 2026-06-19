"""Checklist templates: the user's exact Daily / Weekly / Monthly AI PM checklist items."""

DAILY = {
    "Morning Review": [
        "Review today's product priorities.",
        "Review overdue tasks.",
        "Review critical dependencies.",
        "Check production incidents.",
        "Check model-performance alerts.",
        "Check data-quality alerts.",
        "Check customer escalations.",
        "Review important meetings.",
        "Identify decisions needed today.",
        "Select the three most important outcomes for the day.",
    ],
    "Product and Delivery": [
        "Review active sprint items.",
        "Identify blocked engineering tasks.",
        "Confirm every blocker has an owner.",
        "Confirm every important task has a deadline.",
        "Review changes to scope or requirements.",
        "Review new technical dependencies.",
        "Update acceptance criteria when necessary.",
        "Escalate critical delivery risks.",
    ],
    "AI and Data": [
        "Check for model-performance changes.",
        "Review unusual false positives or false negatives.",
        "Check missing or delayed data.",
        "Review new model, prompt, or data changes.",
        "Confirm high-risk outputs received required human review.",
        "Record model or prompt versions used in testing.",
        "Investigate serious user overrides.",
    ],
    "Stakeholders and Users": [
        "Respond to priority stakeholder questions.",
        "Record important customer feedback.",
        "Confirm stakeholder expectations are aligned.",
        "Document new decisions.",
        "Identify unresolved disagreements.",
        "Assign follow-up actions.",
    ],
    "End-of-Day Review": [
        "Update task statuses.",
        "Update the decision log.",
        "Record new risks.",
        "Record unresolved blockers.",
        "Confirm owners and deadlines.",
        "Prepare tomorrow's top three priorities.",
        "Generate a short daily summary.",
    ],
}

WEEKLY = {
    "Product Strategy and Roadmap": [
        "Review progress against weekly objectives.",
        "Review roadmap changes.",
        "Confirm priorities still support product goals.",
        "Review scope additions.",
        "Identify initiatives that should be delayed or removed.",
        "Review major product assumptions.",
        "Confirm upcoming milestones.",
    ],
    "Engineering and Delivery": [
        "Review completed and incomplete sprint work.",
        "Review blockers and dependencies.",
        "Review technical debt.",
        "Review quality and testing results.",
        "Confirm API and UI alignment.",
        "Review deployment readiness.",
        "Confirm engineering capacity.",
    ],
    "AI Model and Data": [
        "Review model metrics by user segment.",
        "Review false positives and false negatives.",
        "Review human overrides.",
        "Review prompt or model changes.",
        "Review data-quality trends.",
        "Check for model drift.",
        "Review evaluation failures.",
        "Confirm model documentation is current.",
    ],
    "Users and Customers": [
        "Review customer feedback.",
        "Review support tickets.",
        "Review feature adoption.",
        "Review usability problems.",
        "Identify new research questions.",
        "Confirm customer commitments.",
        "Track pilot or implementation status.",
    ],
    "Risk, Ethics and Compliance": [
        "Review new high-severity risks.",
        "Review privacy or security concerns.",
        "Review fairness and bias findings.",
        "Review audit-log completeness.",
        "Review unresolved compliance items.",
        "Confirm human-review rules are operating properly.",
        "Escalate risks requiring executive approval.",
    ],
    "Stakeholder Management": [
        "Prepare weekly stakeholder update.",
        "Confirm decisions and owners.",
        "Identify unresolved conflicts.",
        "Review RACI responsibilities.",
        "Confirm executive decisions needed.",
        "Review promises made to customers or employees.",
    ],
}

MONTHLY = {
    "Strategy": [
        "Review product vision and strategic goals.",
        "Review progress against quarterly objectives.",
        "Evaluate whether roadmap priorities remain correct.",
        "Review competitive or market changes.",
        "Review business-model assumptions.",
        "Reassess major product risks.",
    ],
    "Product Performance": [
        "Review monthly adoption.",
        "Review activation and retention.",
        "Review usage by customer and user segment.",
        "Review customer satisfaction.",
        "Review feature performance.",
        "Identify underused features.",
        "Identify features creating the most value.",
    ],
    "AI Performance": [
        "Compare model performance with previous months.",
        "Review drift.",
        "Review hallucinations and unsafe outputs.",
        "Review human-review and override rates.",
        "Review performance across demographic groups.",
        "Review model cost and latency.",
        "Decide whether retraining or reevaluation is needed.",
    ],
    "Data Strategy": [
        "Review dataset quality.",
        "Review data coverage.",
        "Review missing-data trends.",
        "Review access permissions.",
        "Review new data needs.",
        "Review privacy and retention requirements.",
        "Confirm dataset documentation is current.",
    ],
    "Compliance and Governance": [
        "Review the complete risk register.",
        "Review regulatory changes affecting the product.",
        "Review security and privacy incidents.",
        "Review compliance exceptions.",
        "Review audit readiness.",
        "Review model and data approvals.",
        "Confirm documentation is complete.",
    ],
    "Business and Go-to-Market": [
        "Review pipeline and customer progress.",
        "Review implementation capacity.",
        "Review revenue and cost metrics.",
        "Review product positioning.",
        "Review sales objections.",
        "Review pilot-to-contract conversion.",
        "Review customer expansion opportunities.",
    ],
    "Team and Operations": [
        "Review team capacity.",
        "Review responsibility gaps.",
        "Review recurring blockers.",
        "Review vendor performance.",
        "Review process efficiency.",
        "Update templates and playbooks.",
        "Identify work that can be automated.",
    ],
    "Career and Professional Development": [
        "Record major accomplishments.",
        "Update your AI PM portfolio.",
        "Document one difficult decision you managed.",
        "Document measurable product outcomes.",
        "Review one AI PM interview topic.",
        "Learn one new technical or regulatory concept.",
        "Update your glossary.",
        "Identify one skill to improve next month.",
    ],
}


def seed(conn):
    if conn.execute("SELECT COUNT(*) FROM checklist_templates").fetchone()[0]:
        return
    order = 0
    for period, sections in (("daily", DAILY), ("weekly", WEEKLY), ("monthly", MONTHLY)):
        for section, items in sections.items():
            for text in items:
                order += 1
                conn.execute(
                    "INSERT INTO checklist_templates(period, section, item_text, order_index) "
                    "VALUES (?, ?, ?, ?)",
                    (period, section, text, order),
                )
