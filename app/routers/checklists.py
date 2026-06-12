from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.agents.execution import ExecutionAgent
from app.db import get_db
from app.routers.dashboard import _checklist_for
from app.services.ai import get_ai
from app.web import render

router = APIRouter()


@router.get("/checklists")
def checklists(request: Request, period: str = "daily", conn=Depends(get_db)):
    if period not in ("daily", "weekly", "monthly"):
        period = "daily"
    agent = ExecutionAgent(conn, get_ai())
    checklist = _checklist_for(conn, agent, period)
    return render(request, "checklists.html", period=period, checklist=checklist)


@router.post("/api/checklist-items/{item_id}/toggle")
def toggle_item(item_id: int, conn=Depends(get_db)):
    row = conn.execute("SELECT done FROM checklist_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return {"ok": False}
    new = 0 if row["done"] else 1
    conn.execute(
        "UPDATE checklist_items SET done=?, done_at=? WHERE id=?",
        (new, datetime.now().isoformat(timespec="seconds") if new else None, item_id),
    )
    return {"ok": True, "done": new}


@router.post("/api/checklists/generate")
def generate(period: str = "daily", conn=Depends(get_db)):
    agent = ExecutionAgent(conn, get_ai())
    instance_id = agent.ensure_checklist(period)
    return RedirectResponse(f"/checklists?period={period}", status_code=303)
