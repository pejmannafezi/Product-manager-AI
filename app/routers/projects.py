import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.db import get_db
from app.web import render

router = APIRouter()


@router.get("/projects")
def projects(request: Request, conn=Depends(get_db)):
    rows = conn.execute(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id AND t.status!='done') AS open_tasks,
                  (SELECT MAX(score) FROM compliance_reports r WHERE r.project_id=p.id) AS last_score
           FROM projects p ORDER BY p.created_at DESC"""
    ).fetchall()
    return render(request, "projects.html", projects=rows)


@router.post("/api/projects")
def create_project(name: str = Form(...), description: str = Form(""), phase: str = Form("discovery"),
                   owner: str = Form(""), customer: str = Form(""), target_date: str = Form(""),
                   conn=Depends(get_db)):
    cur = conn.execute(
        "INSERT INTO projects(name, description, status, phase, owner, customer, target_date) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, description, "active", phase, owner, customer, target_date or None),
    )
    return RedirectResponse(f"/projects/{cur.lastrowid}", status_code=303)


@router.post("/api/projects/{project_id}/status")
def set_status(project_id: int, status: str = Form(...), phase: str = Form(""), conn=Depends(get_db)):
    conn.execute("UPDATE projects SET status=?, phase=COALESCE(NULLIF(?, ''), phase), "
                 "updated_at=datetime('now') WHERE id=?", (status, phase, project_id))
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@router.get("/projects/{project_id}")
def project_detail(request: Request, project_id: int, tab: str = "tasks", conn=Depends(get_db)):
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        return RedirectResponse("/projects", status_code=303)
    ctx = {"project": project, "tab": tab}
    if tab == "tasks":
        ctx["tasks"] = conn.execute(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY status='done', "
            "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date",
            (project_id,)).fetchall()
    elif tab == "roadmap":
        items = conn.execute(
            "SELECT * FROM roadmap_items WHERE project_id=? ORDER BY order_index", (project_id,)).fetchall()
        ctx["roadmap"] = {h: [i for i in items if i["horizon"] == h] for h in ("now", "next", "later")}
    elif tab == "risks":
        ctx["risks"] = conn.execute(
            "SELECT * FROM risks WHERE project_id=? ORDER BY score DESC", (project_id,)).fetchall()
    elif tab == "decisions":
        ctx["decisions"] = conn.execute(
            "SELECT * FROM decisions WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()
    elif tab == "blockers":
        ctx["blockers"] = conn.execute(
            "SELECT * FROM blockers WHERE project_id=? ORDER BY status, raised_at DESC", (project_id,)).fetchall()
    elif tab == "compliance":
        ctx["reports"] = conn.execute(
            "SELECT r.*, d.filename FROM compliance_reports r "
            "LEFT JOIN documents d ON d.id=r.document_id "
            "WHERE r.project_id=? ORDER BY r.created_at DESC", (project_id,)).fetchall()
    elif tab == "documents":
        ctx["documents"] = conn.execute(
            "SELECT id, filename, mime, uploaded_at, length(text) AS size FROM documents "
            "WHERE project_id=? ORDER BY uploaded_at DESC", (project_id,)).fetchall()
    elif tab == "activity":
        ctx["events"] = conn.execute(
            "SELECT * FROM agent_events WHERE (entity_type='project' AND entity_id=?) "
            "OR id IN (SELECT e.id FROM agent_events e WHERE e.payload LIKE ?) "
            "ORDER BY id DESC LIMIT 100",
            (project_id, f'%"project_id": {project_id}%')).fetchall()
    return render(request, "project_detail.html", **ctx)


@router.get("/documents/{doc_id}")
def view_document(request: Request, doc_id: int, conn=Depends(get_db)):
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        return RedirectResponse("/projects", status_code=303)
    return render(request, "document.html", doc=doc)


# ---- risks / decisions / blockers quick-create ----

@router.post("/api/risks")
def create_risk(project_id: int = Form(...), title: str = Form(...), category: str = Form("other"),
                likelihood: int = Form(3), impact: int = Form(3), mitigation: str = Form(""),
                owner: str = Form(""), conn=Depends(get_db)):
    conn.execute(
        "INSERT INTO risks(project_id, title, category, likelihood, impact, mitigation, owner) "
        "VALUES (?,?,?,?,?,?,?)",
        (project_id, title, category, likelihood, impact, mitigation, owner))
    return RedirectResponse(f"/projects/{project_id}?tab=risks", status_code=303)


@router.post("/api/decisions")
def create_decision(project_id: int = Form(...), title: str = Form(...), context: str = Form(""),
                    options_considered: str = Form(""), conn=Depends(get_db)):
    conn.execute(
        "INSERT INTO decisions(project_id, title, context, options_considered) VALUES (?,?,?,?)",
        (project_id, title, context, options_considered))
    return RedirectResponse(f"/projects/{project_id}?tab=decisions", status_code=303)


@router.post("/api/decisions/{decision_id}/decide")
def decide(decision_id: int, decision: str = Form(...), rationale: str = Form(""), conn=Depends(get_db)):
    row = conn.execute("SELECT project_id FROM decisions WHERE id=?", (decision_id,)).fetchone()
    conn.execute(
        "UPDATE decisions SET decision=?, rationale=?, status='decided', decided_at=datetime('now') WHERE id=?",
        (decision, rationale, decision_id))
    return RedirectResponse(f"/projects/{row['project_id']}?tab=decisions" if row and row["project_id"] else "/",
                            status_code=303)


@router.post("/api/blockers")
def create_blocker(project_id: int = Form(...), title: str = Form(...), description: str = Form(""),
                   severity: str = Form("medium"), conn=Depends(get_db)):
    conn.execute(
        "INSERT INTO blockers(project_id, title, description, severity) VALUES (?,?,?,?)",
        (project_id, title, description, severity))
    return RedirectResponse(f"/projects/{project_id}?tab=blockers", status_code=303)


@router.post("/api/blockers/{blocker_id}/resolve")
def resolve_blocker(blocker_id: int, resolution: str = Form(""), conn=Depends(get_db)):
    row = conn.execute("SELECT project_id FROM blockers WHERE id=?", (blocker_id,)).fetchone()
    conn.execute(
        "UPDATE blockers SET status='resolved', resolved_at=datetime('now'), resolution=? WHERE id=?",
        (resolution, blocker_id))
    return RedirectResponse(f"/projects/{row['project_id']}?tab=blockers" if row and row["project_id"] else "/",
                            status_code=303)
