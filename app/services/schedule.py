"""Scheduling helpers: date-window math for plans, period rollover for the
carry-forward logic, and critical-path detection over task dependencies.

Pure functions where possible so they are easy to unit-test and work the same
whether the plan came from the AI or the rule-based fallback.
"""
import json
from datetime import date, datetime, timedelta


# ----------------------------------------------------------------- dates ------
def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def project_window(start, target, default_days: int = 90) -> tuple[date, date]:
    """Resolve a usable (start, end) window from possibly-missing project dates."""
    start_d = parse_date(start) or date.today()
    end_d = parse_date(target)
    if not end_d or end_d <= start_d:
        end_d = start_d + timedelta(days=default_days)
    return start_d, end_d


def spread_dates(start: date, end: date, count: int) -> list[date]:
    """`count` due-dates spaced evenly through (start, end], last one at end.

    Used to schedule milestones/deliverables realistically across the window."""
    if count <= 0:
        return []
    if count == 1:
        return [end]
    span = (end - start).days
    step = span / count  # leave the start clear, land the final item on `end`
    return [start + timedelta(days=round(step * (i + 1))) for i in range(count)]


def pct_offset(d: date, start: date, end: date) -> float:
    """Position of `d` within the window as a 0–100 percentage (for the Gantt)."""
    span = (end - start).days or 1
    return max(0.0, min(100.0, (d - start).days / span * 100.0))


# --------------------------------------------------------- period rollover ----
def previous_period_key(period: str, day: date | None = None) -> str:
    """The period_key of the period immediately before the one containing `day`.

    Mirrors ExecutionAgent.period_key formats: daily=YYYY-MM-DD, weekly=YYYY-Www,
    monthly=YYYY-MM."""
    day = day or date.today()
    if period == "daily":
        return (day - timedelta(days=1)).isoformat()
    if period == "weekly":
        prev = day - timedelta(weeks=1)
        iso = prev.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    # monthly
    first = day.replace(day=1)
    prev_month_last = first - timedelta(days=1)
    return prev_month_last.strftime("%Y-%m")


# ----------------------------------------------------------- critical path ----
def critical_path(tasks: list[dict]) -> set[int]:
    """Return the set of task ids on the longest dependency chain.

    Each task: {id, depends_on (list[int] | json str | None), due_date}. The chain
    weight is its length; ties broken by latest due_date. Cycles are ignored."""
    by_id: dict[int, dict] = {t["id"]: t for t in tasks}

    def deps(t) -> list[int]:
        raw = t.get("depends_on")
        if not raw:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return []
        return [d for d in raw if d in by_id]

    memo: dict[int, list[int]] = {}

    def longest(tid: int, seen: frozenset[int]) -> list[int]:
        if tid in seen:                 # cycle guard
            return []
        if tid in memo:
            return memo[tid]
        best: list[int] = []
        for d in deps(by_id[tid]):
            chain = longest(d, seen | {tid})
            if len(chain) > len(best):
                best = chain
        result = [tid] + best
        memo[tid] = result
        return result

    overall: list[int] = []
    for tid in by_id:
        chain = longest(tid, frozenset())
        if len(chain) > len(overall):
            overall = chain
    return set(overall)


# ---------------------------------------------------- progress & timeline -----
def project_stats(conn, pid: int) -> dict:
    """Completion %, overdue count, status breakdown, and milestone progress."""
    today = date.today().isoformat()
    tasks = conn.execute(
        "SELECT status, due_date FROM tasks WHERE project_id=?", (pid,)).fetchall()
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "done")
    overdue = sum(1 for t in tasks
                  if t["status"] != "done" and t["due_date"] and t["due_date"] < today)
    status_counts: dict[str, int] = {}
    for t in tasks:
        status_counts[t["status"]] = status_counts.get(t["status"], 0) + 1
    ms = conn.execute("SELECT status FROM milestones WHERE project_id=?", (pid,)).fetchall()
    return {
        "tasks_total": total, "tasks_done": done,
        "completion_pct": round(done / total * 100) if total else 0,
        "overdue": overdue, "status_counts": status_counts,
        "milestones_total": len(ms), "milestones_done": sum(1 for m in ms if m["status"] == "done"),
    }


def _point_bars(rows, start: date, end: date) -> list[dict]:
    """Sequential bars (milestones/deliverables): each spans from the previous
    item's date to its own due date."""
    bars, cursor = [], start
    for r in rows:
        due = parse_date(r["due_date"]) or end
        left = pct_offset(cursor, start, end)
        right = pct_offset(due, start, end)
        bars.append({"title": r["title"], "due": r["due_date"], "status": r["status"],
                     "left": round(left, 1), "width": round(max(2.0, right - left), 1)})
        cursor = max(cursor, due)
    return bars


def timeline_bars(conn, project) -> dict:
    """Everything the Gantt template needs: window, today marker, and positioned
    bars for milestones, deliverables, and tasks (tasks start after their deps)."""
    start, end = project_window(project["start_date"], project["target_date"])
    pid = project["id"]
    ms = conn.execute("SELECT * FROM milestones WHERE project_id=? ORDER BY order_index",
                      (pid,)).fetchall()
    dl = conn.execute("SELECT * FROM deliverables WHERE project_id=? ORDER BY due_date, order_index",
                      (pid,)).fetchall()
    tasks = conn.execute(
        "SELECT id, title, due_date, depends_on, is_critical, status FROM tasks "
        "WHERE project_id=? AND due_date IS NOT NULL ORDER BY due_date", (pid,)).fetchall()
    by_id = {t["id"]: t for t in tasks}
    task_bars = []
    for t in tasks:
        due = parse_date(t["due_date"]) or end
        s = start
        if t["depends_on"]:
            try:
                for d in json.loads(t["depends_on"]):
                    dd = parse_date(by_id[d]["due_date"]) if d in by_id else None
                    if dd and dd > s:
                        s = dd
            except (ValueError, TypeError, KeyError):
                pass
        left = pct_offset(s, start, end)
        right = pct_offset(due, start, end)
        task_bars.append({"title": t["title"], "due": t["due_date"], "status": t["status"],
                          "critical": bool(t["is_critical"]),
                          "left": round(left, 1), "width": round(max(2.0, right - left), 1)})
    today = date.today()
    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "today_pct": round(pct_offset(today, start, end), 1) if start <= today <= end else None,
        "milestones": _point_bars(ms, start, end),
        "deliverables": _point_bars(dl, start, end),
        "tasks": task_bars,
    }
