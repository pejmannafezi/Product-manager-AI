import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.agents.orchestrator import Orchestrator
from app.db import get_db
from app.services.ai import get_ai
from app.web import render

router = APIRouter()


@router.get("/intake")
def intake_form(request: Request, conn=Depends(get_db)):
    return render(request, "intake.html", ai_on=get_ai().available)


@router.post("/api/intake")
async def run_intake(name: str = Form(...), description: str = Form(""),
                     phase: str = Form("discovery"), target_date: str = Form(""),
                     owner: str = Form(""), customer: str = Form(""), objective: str = Form(""),
                     file: UploadFile | None = File(None), conn=Depends(get_db)):
    data = await file.read() if file and file.filename else b""
    orch = Orchestrator(conn, get_ai())
    result = orch.run_intake(name=name, description=description, phase=phase,
                             target_date=target_date, owner=owner, customer=customer,
                             objective=objective,
                             filename=file.filename if file else "", file_bytes=data)
    url = f"/intake/result/{result['project_id']}"
    if result.get("doc_error"):
        url += f"?doc_error={result['doc_error']}"
    return RedirectResponse(url, status_code=303)


@router.get("/intake/result/{project_id}")
def intake_result(request: Request, project_id: int, doc_error: str = "", conn=Depends(get_db)):
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        return RedirectResponse("/intake", status_code=303)
    report = conn.execute(
        "SELECT * FROM compliance_reports WHERE project_id=? ORDER BY id DESC LIMIT 1",
        (project_id,)).fetchone()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE project_id=? ORDER BY "
        "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date",
        (project_id,)).fetchall()
    items = conn.execute(
        "SELECT * FROM roadmap_items WHERE project_id=? ORDER BY order_index", (project_id,)).fetchall()
    roadmap = {h: [i for i in items if i["horizon"] == h] for h in ("now", "next", "later")}
    strategy = conn.execute(
        "SELECT text FROM documents WHERE project_id=? AND filename='strategy-outline.md' "
        "ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
    reading_event = conn.execute(
        "SELECT payload FROM agent_events WHERE action='reading_list' AND entity_id=? "
        "ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
    reading = json.loads(reading_event["payload"])["chapters"] if reading_event and reading_event["payload"] else []
    events = conn.execute(
        "SELECT * FROM agent_events WHERE entity_type='project' AND entity_id=? "
        "OR entity_type='compliance_report' AND entity_id=? ORDER BY id",
        (project_id, report["id"] if report else 0)).fetchall()
    return render(request, "intake_result.html", project=project, report=report,
                  tasks=tasks, roadmap=roadmap,
                  strategy=strategy["text"] if strategy else "",
                  reading=reading, events=events, doc_error=doc_error)
