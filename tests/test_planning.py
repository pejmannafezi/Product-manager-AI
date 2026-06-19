"""Tests for the AI planning platform: schedule math, plan generation (rule-based
fallback), carry-forward, and progress — all in the no-API-key path."""
import json
from datetime import date

from app import db as dbmod
from app.agents.execution import ExecutionAgent
from app.agents.planning import PlanningAgent
from app.services.ai import AIClient
from app.services import schedule


def _project(conn, **over):
    fields = {"name": "P", "description": "d", "objective": "o", "requirements": "r",
              "stakeholders": "s", "start_date": "2026-07-01", "target_date": "2026-10-01"}
    fields.update(over)
    cols = ", ".join(fields)
    cur = conn.execute(f"INSERT INTO projects({cols}) VALUES ({','.join('?' * len(fields))})",
                       tuple(fields.values()))
    return conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone()


# ------------------------------------------------------------- schedule math --
def test_spread_dates_within_window_and_ordered():
    s, e = date(2026, 7, 1), date(2026, 10, 1)
    ds = schedule.spread_dates(s, e, 6)
    assert len(ds) == 6
    assert ds == sorted(ds)
    assert all(s < d <= e for d in ds)
    assert ds[-1] == e


def test_project_window_defaults_when_target_missing():
    s, e = schedule.project_window("2026-07-01", "")
    assert (e - s).days == 90


def test_previous_period_key():
    assert schedule.previous_period_key("daily", date(2026, 7, 2)) == "2026-07-01"
    assert schedule.previous_period_key("monthly", date(2026, 7, 15)) == "2026-06"
    assert schedule.previous_period_key("weekly", date(2026, 7, 8)).startswith("2026-W")


def test_critical_path_picks_longest_chain():
    tasks = [
        {"id": 1, "depends_on": None, "due_date": "2026-07-10"},
        {"id": 2, "depends_on": json.dumps([1]), "due_date": "2026-07-20"},
        {"id": 3, "depends_on": json.dumps([2]), "due_date": "2026-07-30"},
        {"id": 4, "depends_on": None, "due_date": "2026-07-15"},  # off the chain
    ]
    assert schedule.critical_path(tasks) == {1, 2, 3}


# ------------------------------------------------------------- migration -------
def test_column_migration_idempotent():
    dbmod.init_db()
    dbmod.init_db()  # second call must not raise
    c = dbmod.connect()
    cols = {r["name"] for r in c.execute("PRAGMA table_info(tasks)")}
    assert {"depends_on", "is_critical", "milestone_id"} <= cols
    c.close()


# ------------------------------------------------------- plan generation -------
def test_generate_plan_and_tasks_offline(conn):
    planner = PlanningAgent(conn, AIClient())  # no key -> rule-based
    p = _project(conn)
    counts = planner.generate_plan(p)
    assert counts["milestones"] >= 5 and counts["risks"] >= 4

    ms = conn.execute("SELECT due_date FROM milestones WHERE project_id=? ORDER BY order_index",
                      (p["id"],)).fetchall()
    assert all("2026-07-01" <= m["due_date"] <= "2026-10-01" for m in ms)

    p = conn.execute("SELECT * FROM projects WHERE id=?", (p["id"],)).fetchone()
    task_ids = planner.generate_project_tasks(p)
    assert len(task_ids) >= len(ms)
    backbone = conn.execute(
        "SELECT * FROM tasks WHERE project_id=? AND title LIKE 'Deliver:%'", (p["id"],)).fetchall()
    assert backbone and all(t["is_critical"] for t in backbone)

    # idempotent
    assert planner.generate_plan(p)["milestones"] == 0
    assert planner.generate_project_tasks(p) == []


# ------------------------------------------------------------- carry-forward ---
def test_checklist_carry_forward(conn):
    agent = ExecutionAgent(conn, AIClient())
    i1 = agent.ensure_checklist("daily", day=date(2026, 7, 1))
    conn.execute("INSERT INTO checklist_items(instance_id, template_id, section, text, order_index) "
                 "VALUES (?,?,?,?,?)", (i1, None, "My Tasks", "Carry me", 99))
    conn.execute("INSERT INTO checklist_items(instance_id, template_id, section, text, done, order_index) "
                 "VALUES (?,?,?,?,1,?)", (i1, None, "My Tasks", "Done one", 100))

    i2 = agent.ensure_checklist("daily", day=date(2026, 7, 2))
    rows = conn.execute("SELECT text, carried_over FROM checklist_items WHERE instance_id=?", (i2,)).fetchall()
    texts = [r["text"] for r in rows]
    assert "Carry me" in texts and "Done one" not in texts
    assert any(r["text"] == "Carry me" and r["carried_over"] for r in rows)


# ------------------------------------------------------------- progress --------
def test_project_stats_completion(conn):
    p = _project(conn)
    for st in ("done", "done", "todo"):
        conn.execute("INSERT INTO tasks(project_id, title, status) VALUES (?,?,?)", (p["id"], "t", st))
    stats = schedule.project_stats(conn, p["id"])
    assert stats["tasks_total"] == 3 and stats["tasks_done"] == 2
    assert stats["completion_pct"] == 67
