"""Compliance Agent: checks a project document against the AI PRD/governance framework."""
import json
import re

from app.agents.base import BaseAgent

GRADES = [(85, "Ready"), (70, "Conditional"), (50, "Needs Work"), (0, "Not Ready")]
WINDOW = 600  # chars: two distinct keywords inside one window count as "present"


def detect_headings(text: str) -> list[str]:
    headings = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or len(s) >= 80:
            continue
        next_blank = i + 1 >= len(lines) or not lines[i + 1].strip()
        if (re.match(r"^#{1,4}\s+", s)
                or (s.isupper() and len(s) > 3)
                or s.endswith(":")
                or (next_blank and len(s.split()) <= 8 and s == s.title())):
            headings.append(s.lstrip("#").strip().rstrip(":"))
    return headings


def grade_for(score: int) -> str:
    for threshold, grade in GRADES:
        if score >= threshold:
            return grade
    return "Not Ready"


class ComplianceAgent(BaseAgent):
    name = "compliance"

    def __init__(self, conn, ai, knowledge=None):
        super().__init__(conn, ai)
        self.knowledge = knowledge

    def review_document(self, project_id: int | None, document_id: int) -> int:
        doc = self.db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        text = doc["text"] or ""
        lower = text.lower()
        headings = [h.lower() for h in detect_headings(text)]
        rules = self.db.execute("SELECT * FROM compliance_rules ORDER BY weight DESC, id").fetchall()

        findings, earned, total = [], 0.0, 0
        for rule in rules:
            total += rule["weight"]
            status, evidence = self._check_rule(rule, text, lower, headings)
            if status == "present":
                earned += rule["weight"]
            elif status == "partial":
                earned += rule["weight"] / 2
            chapter_ids = []
            if status != "present" and self.knowledge:
                chapter_ids = [r["id"] for r in self.knowledge.relevant_chapters(rule["kb_query"], 2)]
            findings.append(dict(rule_id=rule["id"], status=status, evidence=evidence,
                                 recommendation=rule["recommendation"],
                                 kb_chapter_ids=json.dumps(chapter_ids)))

        score = round(100 * earned / total) if total else 0
        grade = grade_for(score)
        missing = sum(1 for f in findings if f["status"] == "missing")
        partial = sum(1 for f in findings if f["status"] == "partial")
        summary = (f"Rule-based review: {len(findings) - missing - partial} artifacts present, "
                   f"{partial} partial, {missing} missing. Grade: {grade} ({score}/100).")

        cur = self.db.execute(
            "INSERT INTO compliance_reports(project_id, document_id, score, max_score, grade, summary) "
            "VALUES (?,?,?,?,?,?)",
            (project_id, document_id, score, 100, grade, summary),
        )
        report_id = cur.lastrowid
        for f in findings:
            self.db.execute(
                "INSERT INTO compliance_findings(report_id, rule_id, status, evidence_snippet, "
                "recommendation, kb_chapter_ids) VALUES (?,?,?,?,?,?)",
                (report_id, f["rule_id"], f["status"], f["evidence"],
                 f["recommendation"], f["kb_chapter_ids"]),
            )
        self.log_event("document_reviewed", "compliance_report", report_id,
                       f"Reviewed '{doc['filename']}': {grade} ({score}/100), "
                       f"{missing} missing, {partial} partial",
                       payload={"score": score, "grade": grade})
        self._ai_enhance(report_id, text, findings, score, grade)
        return report_id

    def review_missing_document(self, project_id: int) -> int:
        """No document supplied at intake: produce an all-missing report so the
        gap-to-task machinery still generates a complete PRD-building to-do list."""
        cur = self.db.execute(
            "INSERT INTO documents(project_id, filename, mime, text) VALUES (?,?,?,?)",
            (project_id, "(no document provided)", "text/plain", ""),
        )
        doc_id = cur.lastrowid
        rules = self.db.execute("SELECT * FROM compliance_rules").fetchall()
        cur = self.db.execute(
            "INSERT INTO compliance_reports(project_id, document_id, score, max_score, grade, summary) "
            "VALUES (?,?,?,?,?,?)",
            (project_id, doc_id, 0, 100, "Not Ready",
             "No project document was provided. Every required artifact is treated as missing; "
             "the generated tasks form a complete PRD-building checklist."),
        )
        report_id = cur.lastrowid
        for rule in rules:
            chapter_ids = []
            if self.knowledge:
                chapter_ids = [r["id"] for r in self.knowledge.relevant_chapters(rule["kb_query"], 2)]
            self.db.execute(
                "INSERT INTO compliance_findings(report_id, rule_id, status, recommendation, kb_chapter_ids) "
                "VALUES (?,?,?,?,?)",
                (report_id, rule["id"], "missing", rule["recommendation"], json.dumps(chapter_ids)),
            )
        self.log_event("document_reviewed", "compliance_report", report_id,
                       "No document provided: generated full artifact gap list (Not Ready, 0/100)")
        return report_id

    def _check_rule(self, rule, text, lower, headings):
        keywords = [k.lower() for k in json.loads(rule["keywords"])]
        if rule["heading_regex"]:
            pattern = re.compile(rule["heading_regex"], re.I)
            for h in headings:
                if pattern.search(h):
                    return "present", self._snippet_around(text, lower, keywords) or h
        positions = []
        for kw in keywords:
            idx = lower.find(kw)
            if idx >= 0:
                positions.append((idx, kw))
        if len(positions) >= 2:
            positions.sort()
            for i in range(len(positions) - 1):
                if positions[i + 1][0] - positions[i][0] <= WINDOW:
                    return "present", self._snippet_around(text, lower, keywords)
        if positions:
            return "partial", self._snippet_around(text, lower, keywords)
        return "missing", None

    @staticmethod
    def _snippet_around(text, lower, keywords):
        for kw in keywords:
            idx = lower.find(kw)
            if idx >= 0:
                start = max(0, idx - 100)
                return ("…" if start else "") + text[start:idx + 140].replace("\n", " ").strip() + "…"
        return None

    def _ai_enhance(self, report_id, text, findings, score, grade):
        if not self.ai.available or not text:
            return
        rules_by_id = {r["id"]: r for r in self.db.execute("SELECT * FROM compliance_rules").fetchall()}
        finding_lines = "\n".join(
            f"- {rules_by_id[f['rule_id']]['name']}: {f['status']}" for f in findings)
        report = self.db.execute(
            "SELECT project_id FROM compliance_reports WHERE id=?", (report_id,)).fetchone()
        context = self.reference_context(
            f"{finding_lines}\n{text[:1000]}", report["project_id"] if report else None)
        result = self.ai.complete(
            "You are a compliance reviewer for governed healthcare AI products. Given a rule-based "
            "artifact checklist result and a document excerpt, write: (1) a one-paragraph executive "
            "summary of the document's readiness; (2) any findings that look like false positives or "
            "false negatives, with the evidence; (3) the 3 most important project-specific actions. "
            "Concise markdown, no preamble.",
            self._with_context(
                context,
                f"Rule-based result: grade {grade}, score {score}/100.\nFindings:\n{finding_lines}\n\n"
                f"Document excerpt (first 8000 chars):\n{text[:8000]}",
            ),
            max_tokens=1500,
        )
        if result:
            self.db.execute(
                "UPDATE compliance_reports SET summary = summary || ? , ai_enhanced=1 WHERE id=?",
                ("\n\n---\n\n" + result, report_id),
            )
            self.log_event("ai_review", "compliance_report", report_id,
                           "AI-enhanced compliance summary added")
