# AI PM Command Center

A local web application that turns a 23-chapter AI Product Manager guide into a
**working operating system** for managing governed (healthcare) AI products —
not a static document.

Three cooperating agents share one SQLite database and help each other make decisions:

| Agent | Like | What it does |
|---|---|---|
| **Execution Agent** | ClickUp | Projects, tasks, sprints, roadmap (now/next/later), risks, decisions, blockers, daily/weekly/monthly checklists, and a P0–P3 Problem-Solving Assistant with enforced closure criteria. |
| **Knowledge Agent** | Notion | The 23-chapter guide as a browsable, deep-searchable library (SQLite FTS5 full-text search with ranked, highlighted snippets) plus a glossary. |
| **Compliance Agent** | — | Reads an uploaded project document (docx/pdf/txt/md) and checks it against the AI PRD/governance framework **before a project starts**: score, grade, gap report, and recommendations that cite your own guide chapters. |

An **Orchestrator** wires them together: the *New Project Intake* flow runs a
compliance review, attaches a reading list from the knowledge base, converts
compliance gaps into prioritized tasks with due dates, generates a now/next/later
roadmap, daily/weekly/monthly checklists, and a strategy outline. Every
cross-agent action is recorded in an auditable activity feed.

## Quick start

```bash
pip install -r requirements.txt
python run.py
# open http://127.0.0.1:8000
```

### Load your guide into the knowledge base

```bash
python scripts/ingest_docx.py data/ai-pm-guide.docx --replace
```

The script splits the document on `Chapter N:` headings, indexes every section
for full-text search, and harvests glossary terms from the glossary chapter.

## Hybrid AI (optional)

The system is fully functional offline using rule-based logic. To make the
agents smarter, set an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run.py
```

With a key, Claude enhances four spots (each falls back to rule-based output on
any failure, and the UI shows an "AI-enhanced" badge when used):

1. **Compliance reports** — executive summary, false-positive/negative review, top actions.
2. **Intake strategy outline** — project-specific vision, pillars, first-90-days plan.
3. **Issue analysis** — root-cause hypotheses, missing evidence, investigation plan.
4. **Deep search** — query expansion with related AI PM terminology.

## Bilingual UI

English by default; click **فارسی** in the top bar for a Persian RTL interface.
Knowledge-base content stays English (rendered LTR inside the RTL layout).

## Sharing with your team

- **Office network:** `python run.py --host 0.0.0.0`, then colleagues open
  `http://<your-ip>:8000`.
- **Internet (Render):** the repo ships a `render.yaml` blueprint. On
  [render.com](https://render.com): *New + → Blueprint → connect this repo →
  Apply*. Set the `PMAI_PASSWORD` environment variable — when it is set, every
  page requires that password (when unset, e.g. locally, there is no login).
  After deploying, open *Knowledge → Import guide* and upload the guide docx
  through the browser to populate the library.

Do not put real patient or confidential data on a shared demo deployment.

## Docker

```bash
docker build -t pm-center .
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" pm-center
```

## Tests

```bash
pytest
```

Covers: docx chapter splitting and FTS indexing, the compliance scoring rubric
(a complete PRD scores *Ready*, a weak document scores *Not Ready* with the
right gaps), gap→task generation with priorities and idempotency, the full
intake pipeline end-to-end, checklist idempotency, P0/P1 auto-escalation, and
the closure-criteria guard.

## Layout

```
run.py                  # python run.py → http://127.0.0.1:8000
scripts/ingest_docx.py  # guide.docx → knowledge base + FTS index
app/
  schema.sql            # all tables incl. FTS5 + triggers
  agents/               # execution, knowledge, compliance, orchestrator
  services/             # ai (optional Claude), docparse, search
  routers/              # pages + JSON/form APIs
  seed/                 # checklist templates, compliance rules, glossary
  templates/ static/    # Jinja2 + vanilla JS, no build step
data/                   # app.db (created at startup), your guide docx
```
