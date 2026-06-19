import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(conn):
    with TestClient(app) as c:
        yield c


def test_pages_render(client):
    for path in ("/", "/projects", "/tasks", "/checklists", "/knowledge",
                 "/glossary", "/compliance", "/issues", "/intake", "/search?q=rollback"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"


def test_intake_flow_end_to_end(client, conn):
    # populate the knowledge base so chapter citations (bm25 aggregation) run for real
    conn.execute("INSERT OR IGNORE INTO kb_chapters(number, title, summary, word_count) "
                 "VALUES (16, 'Writing AI PRDs', 'PRD chapter', 100)")
    ch = conn.execute("SELECT id FROM kb_chapters WHERE number=16").fetchone()["id"]
    conn.execute("INSERT INTO kb_sections(chapter_id, heading, order_index, content) VALUES (?,?,?,?)",
                 (ch, "Problem statements", 0,
                  "A problem statement defines the target user, rollback plan, data requirements, "
                  "model requirements, success metrics, human review, and safety for AI products."))
    conn.commit()
    resp = client.post(
        "/api/intake",
        data={"name": "PreOp Quality", "description": "Reduce missing preoperative data",
              "phase": "discovery", "objective": "Reduce missing info to below 5%"},
        files={"file": ("prd.txt", b"Problem Statement\nNurses face missing data. "
                                   b"This pain point causes delays for the target user.", "text/plain")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    project_id = int(resp.headers["location"].rstrip("/").split("/")[-1].split("?")[0])

    # the orchestrator created a compliance report, tasks, and a roadmap
    report = conn.execute(
        "SELECT * FROM compliance_reports WHERE project_id=?", (project_id,)).fetchone()
    assert report is not None
    tasks = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE project_id=? AND source='compliance_gap'",
        (project_id,)).fetchone()[0]
    assert tasks > 0
    roadmap = conn.execute(
        "SELECT COUNT(*) FROM roadmap_items WHERE project_id=?", (project_id,)).fetchone()[0]
    assert roadmap == 9
    # result page renders
    assert client.get(f"/intake/result/{project_id}").status_code == 200


def test_checklist_idempotent(client, conn):
    client.get("/")  # generates today's checklists
    n1 = conn.execute(
        "SELECT COUNT(*) FROM checklist_instances WHERE period='daily'").fetchone()[0]
    client.get("/")
    n2 = conn.execute(
        "SELECT COUNT(*) FROM checklist_instances WHERE period='daily'").fetchone()[0]
    assert n1 == n2 == 1


def test_p1_issue_creates_blocker_and_task(client, conn):
    resp = client.post("/api/issues", data={
        "title": "Production outage in scoring service",
        "description": "Major customer cannot use the product",
        "severity": "", "affected_area": "production", "reported_by": "QA",
    }, follow_redirects=False)
    assert resp.status_code == 303
    issue = conn.execute("SELECT * FROM issues ORDER BY id DESC LIMIT 1").fetchone()
    assert issue["severity"] == "P1"
    assert conn.execute("SELECT COUNT(*) FROM blockers").fetchone()[0] >= 1
    assert conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE source='issue'").fetchone()[0] >= 1
    # closing is blocked until all closure criteria are done
    resp = client.post(f"/api/issues/{issue['id']}/status",
                       data={"status": "closed"}, follow_redirects=False)
    assert "blocked=1" in resp.headers["location"]


def test_lang_toggle(client):
    resp = client.post("/lang/fa", follow_redirects=False)
    assert resp.status_code == 303
    client.cookies.set("lang", "fa")
    page = client.get("/").text
    assert 'dir="rtl"' in page
