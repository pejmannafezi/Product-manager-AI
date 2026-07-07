from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.db import get_db
from app.web import render

router = APIRouter()


@router.get("/tasks")
def tasks(request: Request, status: str = "", project_id: int = 0, conn=Depends(get_db)):
    sql = ("SELECT t.*, p.name AS project_name FROM tasks t "
           "LEFT JOIN projects p ON p.id=t.project_id WHERE 1=1")
    params: list = []
    if status:
        sql += " AND t.status=?"
        params.append(status)
    if project_id:
        sql += " AND t.project_id=?"
        params.append(project_id)
    sql += (" ORDER BY t.status='done', "
            "CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
            "t.due_date IS NULL, t.due_date")
    rows = conn.execute(sql, params).fetchall()
    projects = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
    return render(request, "tasks.html", tasks=rows, projects=projects,
                  status=status, project_id=project_id)


@router.post("/api/tasks")
def create_task(request: Request, title: str = Form(...), description: str = Form(""),
                project_id: str = Form(""), priority: str = Form("medium"),
                due_date: str = Form(""), conn=Depends(get_db)):
    conn.execute(
        "INSERT INTO tasks(project_id, title, description, priority, due_date) VALUES (?,?,?,?,?)",
        (int(project_id) if project_id else None, title, description, priority, due_date or None))
    back = request.headers.get("referer") or "/tasks"
    return RedirectResponse(back, status_code=303)


@router.post("/api/tasks/{task_id}/status")
def set_task_status(request: Request, task_id: int, status: str = Form(...), conn=Depends(get_db)):
    conn.execute(
        "UPDATE tasks SET status=?, completed_at=CASE WHEN ?='done' THEN datetime('now') ELSE NULL END "
        "WHERE id=?", (status, status, task_id))
    back = request.headers.get("referer") or "/tasks"
    return RedirectResponse(back, status_code=303)


@router.post("/api/tasks/{task_id}/toggle")
def toggle_task(task_id: int, conn=Depends(get_db)):
    row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return {"ok": False}
    new = "todo" if row["status"] == "done" else "done"
    conn.execute(
        "UPDATE tasks SET status=?, completed_at=CASE WHEN ?='done' THEN datetime('now') ELSE NULL END "
        "WHERE id=?", (new, new, task_id))
    return {"ok": True, "status": new}
