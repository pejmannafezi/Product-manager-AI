import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.agents.compliance import ComplianceAgent
from app.agents.execution import ExecutionAgent
from app.agents.knowledge import KnowledgeAgent
from app.db import get_db
from app.services.ai import get_ai
from app.services.docparse import DocParseError, extract_text
from app.web import render

router = APIRouter()


@router.get("/compliance")
def compliance(request: Request, error: str = "", conn=Depends(get_db)):
    reports = conn.execute(
        "SELECT r.*, d.filename, p.name AS project_name FROM compliance_reports r "
        "LEFT JOIN documents d ON d.id=r.document_id "
        "LEFT JOIN projects p ON p.id=r.project_id "
        "ORDER BY r.created_at DESC LIMIT 50"
    ).fetchall()
    projects = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
    return render(request, "compliance.html", reports=reports, projects=projects, error=error)


@router.post("/api/compliance/review")
async def review(file: UploadFile = File(...), project_id: str = Form(""), conn=Depends(get_db)):
    data = await file.read()
    try:
        text = extract_text(file.filename, data)
    except DocParseError as exc:
        return RedirectResponse(f"/compliance?error={exc}", status_code=303)
    pid = int(project_id) if project_id else None
    cur = conn.execute(
        "INSERT INTO documents(project_id, filename, mime, text) VALUES (?,?,?,?)",
        (pid, file.filename, file.content_type, text))
    ai = get_ai()
    knowledge = KnowledgeAgent(conn, ai)
    agent = ComplianceAgent(conn, ai, knowledge=knowledge)
    report_id = agent.review_document(pid, cur.lastrowid)
    return RedirectResponse(f"/compliance/report/{report_id}", status_code=303)


@router.get("/compliance/report/{report_id}")
def report(request: Request, report_id: int, conn=Depends(get_db)):
    rep = conn.execute(
        "SELECT r.*, d.filename, p.name AS project_name FROM compliance_reports r "
        "LEFT JOIN documents d ON d.id=r.document_id "
        "LEFT JOIN projects p ON p.id=r.project_id WHERE r.id=?",
        (report_id,)).fetchone()
    if not rep:
        return RedirectResponse("/compliance", status_code=303)
    findings = conn.execute(
        "SELECT f.*, ru.name AS rule_name, ru.category FROM compliance_findings f "
        "JOIN compliance_rules ru ON ru.id=f.rule_id WHERE f.report_id=? "
        "ORDER BY CASE ru.category WHEN 'critical' THEN 0 WHEN 'important' THEN 1 ELSE 2 END, ru.id",
        (report_id,)).fetchall()
    chapter_titles = {c["id"]: c for c in conn.execute("SELECT * FROM kb_chapters").fetchall()}
    findings_view = []
    for f in findings:
        chs = [chapter_titles[c] for c in json.loads(f["kb_chapter_ids"] or "[]") if c in chapter_titles]
        findings_view.append({"f": f, "chapters": chs})
    return render(request, "compliance_report.html", report=rep, findings=findings_view)


@router.post("/api/compliance/report/{report_id}/create-tasks")
def create_tasks(report_id: int, conn=Depends(get_db)):
    agent = ExecutionAgent(conn, get_ai())
    agent.create_tasks_from_gaps(report_id)
    return RedirectResponse(f"/compliance/report/{report_id}", status_code=303)
