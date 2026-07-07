"""Starter glossary. The docx ingestion script extends this from Chapter 23 when available."""

TERMS = [
    ("Model Drift", "Gradual change in model performance over time as real-world data diverges from training data."),
    ("Hallucination", "A generative model producing confident output that is factually wrong or fabricated."),
    ("Human-in-the-Loop", "A workflow design where a human reviews, approves, or overrides AI outputs before they take effect."),
    ("Precision", "Of all items the model flagged positive, the fraction that were actually positive."),
    ("Recall", "Of all actual positives, the fraction the model correctly identified."),
    ("F1 Score", "Harmonic mean of precision and recall; balances false positives against false negatives."),
    ("False Positive", "The model predicted positive when the true answer was negative."),
    ("False Negative", "The model predicted negative when the true answer was positive."),
    ("Calibration", "How well a model's confidence scores match real-world probabilities."),
    ("PHI", "Protected Health Information: patient data regulated under HIPAA."),
    ("RAG", "Retrieval-Augmented Generation: grounding an LLM's answers in retrieved documents."),
    ("PRD", "Product Requirements Document: the specification of what a product/feature must do."),
    ("RACI", "Responsibility matrix: Responsible, Accountable, Consulted, Informed."),
    ("AI Incident", "An event where an AI system causes or risks harm, requiring classification, response, and review."),
    ("Audit Trail", "A traceable record of decisions, model versions, and data used, supporting accountability and compliance."),
]


def seed(conn):
    for term, definition in TERMS:
        conn.execute(
            "INSERT INTO glossary(term, definition) VALUES (?, ?) "
            "ON CONFLICT(term) DO NOTHING",
            (term, definition),
        )
