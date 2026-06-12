from fastapi import APIRouter, Depends, Request

from app.agents.execution import ExecutionAgent, period_key
from app.db import get_db
from app.services.ai import get_ai
from app.web import render

router = APIRouter()


def _checklist_for(conn, agent: ExecutionAgent, period: str):
    instance_id = agent.ensure_checklist(period)
    items = conn.execute(
        "SELECT * FROM checklist_items WHERE instance_id=? ORDER BY order_index", (instance_id,)
    ).fetchall()
    sections: dict[str, list] = {}
    for item in items:
        sections.setdefault(item["section"], []).append(item)
    done = sum(1 for i in items if i["done"])
    return {"instance_id": instance_id, "sections": sections,
            "done": done, "total": len(items), "key": period_key(period)}


@router.get("/")
def dashboard(request: Request, period: str = "daily", conn=Depends(get_db)):
    if period not in ("daily", "weekly", "monthly"):
        period = "daily"
    agent = ExecutionAgent(conn, get_ai())
    focus = agent.daily_focus()
    checklist = _checklist_for(conn, agent, period)
    events = conn.execute(
        "SELECT * FROM agent_events ORDER BY id DESC LIMIT 30"
    ).fetchall()
    return render(request, "dashboard.html", period=period, focus=focus,
                  checklist=checklist, events=events, ai_on=get_ai().available)


@router.get("/api/agent-events")
def agent_events(limit: int = 50, conn=Depends(get_db)):
    rows = conn.execute("SELECT * FROM agent_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
