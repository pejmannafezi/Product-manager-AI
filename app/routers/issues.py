import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.agents.execution import ExecutionAgent
from app.db import get_db
from app.services.ai import get_ai
from app.web import render

router = APIRouter()


@router.get("/issues")
def issues(request: Request, conn=Depends(get_db)):
    rows = conn.execute(
        "SELECT i.*, p.name AS project_name FROM issues i "
        "LEFT JOIN projects p ON p.id=i.project_id "
        "ORDER BY i.status IN ('resolved','closed'), i.severity, i.detected_at DESC"
    ).fetchall()
    projects = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
    return render(request, "issues.html", issues=rows, projects=projects)


@router.post("/api/issues")
def create_issue(title: str = Form(...), description: str = Form(""), severity: str = Form(""),
                 affected_area: str = Form(""), reported_by: str = Form(""),
                 project_id: str = Form(""), conn=Depends(get_db)):
    agent = ExecutionAgent(conn, get_ai())
    sev = severity if severity in ("P0", "P1", "P2", "P3") else \
        agent.classify_severity(title, description, affected_area)
    cur = conn.execute(
        "INSERT INTO issues(project_id, title, description, severity, affected_area, reported_by) "
        "VALUES (?,?,?,?,?,?)",
        (int(project_id) if project_id else None, title, description, sev, affected_area, reported_by))
    agent.triage_issue(cur.lastrowid)
    return RedirectResponse(f"/issues/{cur.lastrowid}", status_code=303)


@router.get("/issues/{issue_id}")
def issue_detail(request: Request, issue_id: int, conn=Depends(get_db)):
    issue = conn.execute(
        "SELECT i.*, p.name AS project_name FROM issues i "
        "LEFT JOIN projects p ON p.id=i.project_id WHERE i.id=?", (issue_id,)).fetchone()
    if not issue:
        return RedirectResponse("/issues", status_code=303)
    criteria = json.loads(issue["closure_criteria"] or "[]")
    agent = ExecutionAgent(conn, get_ai())
    return render(request, "issue_detail.html", issue=issue, criteria=criteria,
                  can_close=agent.can_close_issue(issue_id), ai_on=get_ai().available)


@router.post("/api/issues/{issue_id}/analyze")
def analyze(issue_id: int, conn=Depends(get_db)):
    agent = ExecutionAgent(conn, get_ai())
    agent.analyze_issue(issue_id)
    return RedirectResponse(f"/issues/{issue_id}", status_code=303)


@router.post("/api/issues/{issue_id}/criteria/{index}/toggle")
def toggle_criterion(issue_id: int, index: int, conn=Depends(get_db)):
    issue = conn.execute("SELECT closure_criteria FROM issues WHERE id=?", (issue_id,)).fetchone()
    criteria = json.loads(issue["closure_criteria"] or "[]")
    if 0 <= index < len(criteria):
        criteria[index]["done"] = 0 if criteria[index].get("done") else 1
        conn.execute("UPDATE issues SET closure_criteria=? WHERE id=?",
                     (json.dumps(criteria), issue_id))
    return {"ok": True}


@router.post("/api/issues/{issue_id}/status")
def set_status(issue_id: int, status: str = Form(...),
               root_cause_category: str = Form(""), root_cause_detail: str = Form(""),
               mitigation: str = Form(""), resolution: str = Form(""), conn=Depends(get_db)):
    agent = ExecutionAgent(conn, get_ai())
    if status == "closed" and not agent.can_close_issue(issue_id):
        return RedirectResponse(f"/issues/{issue_id}?blocked=1", status_code=303)
    conn.execute(
        "UPDATE issues SET status=?, "
        "root_cause_category=COALESCE(NULLIF(?, ''), root_cause_category), "
        "root_cause_detail=COALESCE(NULLIF(?, ''), root_cause_detail), "
        "mitigation=COALESCE(NULLIF(?, ''), mitigation), "
        "resolution=COALESCE(NULLIF(?, ''), resolution), "
        "closed_at=CASE WHEN ?='closed' THEN datetime('now') ELSE closed_at END "
        "WHERE id=?",
        (status, root_cause_category, root_cause_detail, mitigation, resolution, status, issue_id))
    return RedirectResponse(f"/issues/{issue_id}", status_code=303)
