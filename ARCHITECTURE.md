# AI PM Command Center — Architecture Report

A part-by-part description of the system: what each module is and what it does.
This is the "how it actually works" companion to the user-facing `README.md`.

---

## 1. What the system is

A local-first **FastAPI** web app that turns a 23-chapter "AI Product Manager"
guide into a working operating system for managing **governed (healthcare) AI
products**. It is built around cooperating **agents** that share one **SQLite**
database, coordinated by an **Orchestrator** that runs an automated
project-intake pipeline.

**Core invariant:** the app is fully functional with no API key. Every AI step
calls Claude *optionally* and falls back to rule-based logic on any failure, so
nothing breaks offline.

**Stack:** FastAPI · SQLite (FTS5 full-text search, WAL) · Jinja2 templates +
vanilla JS (no build step) · optional Anthropic Claude · bilingual EN / Persian-RTL.

---

## 2. Request lifecycle (how a click flows through the code)

```
Browser → auth_middleware → router (Depends(get_db)) → Agent/Service → SQLite
                                                     ↘ web.render() → Jinja2 → HTML
```

1. `app/main.py` builds the FastAPI app, runs startup (DB init, seeds, i18n,
   auto-ingest), and mounts all routers.
2. `app/auth.py` middleware optionally gates every request behind a password.
3. A **router** handles the route, getting a per-request SQLite connection via
   the `get_db` dependency.
4. The router calls an **agent** (business logic) and/or a **service** (helper).
5. Pages render through `app/web.py:render()`, which injects language/direction
   and the translation function; JSON endpoints return dicts directly.

---

## 3. Infrastructure & configuration

| File | What it does |
|---|---|
| `run.py` | Entry script. Parses `--host/--port/--reload` and launches `uvicorn` on `app.main:app`. |
| `app/main.py` | Builds the FastAPI app. **Lifespan startup:** `init_db()` → run seeds → load translations → `_auto_ingest()` (ingests a guide `.docx` from `data/` if the knowledge base is empty, so a fresh deploy comes up populated). Mounts `/static` and includes all 10 routers. |
| `app/config.py` | Central paths (data dir, DB, schema, templates, static, translations) and env config: `ANTHROPIC_API_KEY`, `PMAI_AI_MODEL` (default `claude-sonnet-4-6`), `PMAI_DATA_DIR`, `SEED_VERSION`. |
| `app/db.py` | SQLite access. `connect()` sets `WAL` + `foreign_keys=ON` per connection. `get_db()`/`db_session()` give per-request/contextual connections that auto-commit. **`_ensure_columns()`** is a lightweight migration system — since SQLite lacks `ADD COLUMN IF NOT EXISTS`, it idempotently adds newer columns (`projects.requirements/stakeholders/resourcing`, `tasks.depends_on/is_critical/milestone_id`, `checklist_items.carried_over`) that aren't in the base `schema.sql`. |
| `app/auth.py` | Optional password gate. If `PMAI_PASSWORD` is set, every page requires login (SHA-256 cookie token); if unset (local use), it's a no-op. `/static/` and `/login` are exempt. |
| `app/i18n.py` | Loads `translations/{en,fa}.json`; `web.render()` picks locale and sets text direction (RTL for Persian). |
| `app/web.py` | `render()` helper — wraps `Jinja2Templates.TemplateResponse` with `lang`, `dir`, and the `t` translator in context. |
| `app/schema.sql` | All tables, FTS5 virtual tables, and sync triggers (see §8). |

---

## 4. The agents (`app/agents/`) — the brains

All extend `BaseAgent`, which provides three shared capabilities:
`reference_context()` (pulls in-scope Reference Library material for a prompt),
`_with_context()` (prepends that material to an LLM user message), and
`log_event()` (writes to the auditable `agent_events` feed).

### `base.py` — `BaseAgent`
Holds the DB connection + `AIClient`. Reference-library injection and event
logging live here so every agent gets them for free.

### `execution.py` — `ExecutionAgent` (the "ClickUp")
The task/project manager and problem-solving assistant. Responsibilities:
- **Checklists:** `ensure_checklist()` creates a daily/weekly/monthly instance
  (idempotent per `period`+`period_key`+scope) from active templates.
  `_carry_forward()` rolls **unfinished ad-hoc items** (template_id NULL) from
  the previous period into the new one, flagged `carried_over`; recurring
  template items regenerate fresh.
- **Gaps → tasks:** `create_tasks_from_gaps()` turns compliance findings
  (`missing`/`partial`) into prioritized, due-dated tasks (critical-missing =
  high/3 days, etc.), attaching guide-chapter references, and links each finding
  to its task (idempotent via `task_id`).
- **Roadmap:** `generate_roadmap()` builds a now/next/later roadmap from a
  template, AI-personalized when a key is present.
- **Dashboards:** `daily_focus()` aggregates top-3 tasks, overdue, open blockers,
  high-score risks (≥15), pending decisions, open issues.
- **Problem-Solving Assistant:** `classify_severity()` (P0/P1 keyword rules),
  `triage_issue()` (auto-creates blocker + same/next-day task for P0/P1, seeds
  the 10-point closure criteria), `analyze_issue()` (AI root-cause analysis),
  and `can_close_issue()` (the **closure guard** — can't close until every
  criterion is checked).

### `planning.py` — `PlanningAgent` (the planning engine) *(new)*
Turns project info + knowledge into a realistic, dated plan. Logs under the
`execution` agent name.
- `generate_plan()` — creates **milestones**, a dated **deliverables** schedule,
  a **resourcing** paragraph, and a **risk assessment**. Idempotent per artifact
  (skips a section that already has rows); schedules undated user deliverables
  across the project window. Uses `_ai_plan()` (Claude → JSON) with healthcare-AI
  rule-based fallbacks.
- `generate_project_tasks()` — builds a **dependency-linked task backbone** (one
  chained task per milestone), optional AI sub-tasks, then marks the
  **critical path** via `schedule.critical_path()`.
- `regenerate()` — clears AI-planning artifacts (milestones, deliverables, plan
  tasks) and rebuilds, leaving manually-entered items untouched.

### `knowledge.py` — `KnowledgeAgent` (the "Notion")
Library over the guide.
- `search()` — FTS5 search with bm25 ranking + highlighted snippets; `deep=True`
  uses Claude to expand the query with related terms, then merges result sets.
- `relevant_chapters()` — bm25-aggregated chapter ranking for a topic (used by
  intake reading lists and compliance chapter citations).
- `chapters()` / `chapter()` / `glossary()` — browse + glossary lookup.

### `compliance.py` — `ComplianceAgent`
Scores an uploaded project document against the AI PRD/governance framework
**before** a project starts.
- `review_document()` — checks each seeded rule (`_check_rule()` uses
  heading-regex + keyword-proximity within a 600-char window → present/partial/
  missing), computes a weighted score → grade (Ready/Conditional/Needs Work/Not
  Ready), writes a report + findings, cites relevant guide chapters for gaps.
- `review_missing_document()` — when no doc is uploaded, produces an all-missing
  report so the gap→task machinery still generates a full PRD-building checklist.
- `_ai_enhance()` — optional Claude exec-summary, false-positive/negative review,
  and top-3 actions appended to the report (sets `ai_enhanced=1`).

### `orchestrator.py` — `Orchestrator`
Coordinates all four agents in **New Project Intake** (`run_intake()`):
1. Create the project; seed any user-entered deliverables.
2. **Compliance** review (uploaded doc, or all-missing report).
3. **Knowledge** reading list (relevant chapters).
4. **Execution:** tasks from gaps + roadmap + recurring checklists.
5. **Planning:** milestones, scheduled deliverables, resourcing, risks, then a
   critical-path task backbone.
6. **Strategy outline** (AI-personalized or templated).
Every step is logged to the activity feed.

---

## 5. The services (`app/services/`) — reusable helpers

| File | What it does |
|---|---|
| `ai.py` | Optional Claude layer. `AIClient.complete(system, user, max_tokens)` returns model text or **`None` on any failure** (the fallback contract). `available` is False when no key/SDK. `get_ai()` is a cached singleton. |
| `search.py` | FTS5 helpers: `fts_query()` (safe OR-joined MATCH expr), `keywords()` (stopword-filtered frequency terms), `search_sections()` (bm25 + `snippet()` highlights), `relevant_chapters()` (per-chapter bm25 aggregation in Python). |
| `docparse.py` | Extracts plain text from uploaded `docx`/`pdf`/`txt`/`md` (raises `DocParseError` on unsupported/corrupt files). |
| `schedule.py` *(new)* | Pure date/graph math: `project_window()` + `spread_dates()` (evenly schedule milestones/deliverables), `previous_period_key()` (checklist rollover), `critical_path()` (longest dependency chain, cycle-guarded, memoized), `project_stats()` (completion %, overdue, breakdown), `timeline_bars()` (positioned bars for the Gantt). |
| `refs.py` *(new)* | **Reference Library** — user material the agents consult at **global** (all projects) or **project** scope. `add_reference()` stores + chunks + FTS-indexes. `gather_context()` does **hybrid retrieval**: short refs injected whole, long refs contribute only the chunks relevant to the current action's query (RAG), all capped to a token budget. Returns a ready-to-prepend prompt block. |

---

## 6. The routers (`app/routers/`) — HTTP endpoints

| Router | Routes (selected) | Purpose |
|---|---|---|
| `dashboard.py` | `GET /`, `GET /api/agent-events` | Home: daily focus, current checklist, recent activity. Hosts the shared `_checklist_for()` helper. |
| `projects.py` | `GET /projects`, `GET /projects/{id}` (tabbed: tasks/plan/timeline/roadmap/risks/decisions/blockers/compliance/documents/activity), `POST /api/projects`, `…/status`, `…/regenerate-plan`, plus risks/decisions/blockers create/resolve, `GET /documents/{id}` | Project list + the tabbed project workspace, including the **plan** and **Gantt timeline** tabs. |
| `tasks.py` | task CRUD / status | The task board surface. |
| `checklists.py` | `GET /checklists`, toggle/generate/add-item | Daily/weekly/monthly checklists; ad-hoc items (the ones that carry forward). |
| `knowledge.py` | search, chapter, glossary pages | The knowledge library UI. |
| `refs.py` *(new)* | `GET /references`, `POST /api/references` (+ toggle/delete) | Reference Library UI + API (file upload or pasted text, scoped global/project). |
| `compliance.py` | upload + report views | Standalone compliance review surface. |
| `issues.py` | issue list/detail, triage, analyze, close | Problem-Solving Assistant UI with the closure guard. |
| `intake.py` | `GET /intake`, `POST /api/intake`, `GET /intake/result/{id}` | New Project Intake form → runs the Orchestrator → results page. |
| `pages.py` | misc/static pages | Remaining simple pages. |

---

## 7. Seeds, templates, scripts

- **`app/seed/`** — `run_seeds()` populates `checklist_templates` (daily/weekly/
  monthly), `compliance_rules` (the PRD/governance rubric: keywords, heading
  regex, weight, recommendation, KB query), and the `glossary`. Guarded by
  `SEED_VERSION`.
- **`app/translations/`** — `en.json` / `fa.json` string catalogs.
- **`app/templates/` + `app/static/`** — Jinja2 pages (incl. `references.html`,
  `project_detail.html`, `checklists.html`, `intake.html`) and vanilla JS/CSS
  (`app.css`, `rtl.css`). No build step.
- **`scripts/ingest_docx.py`** — splits the guide `.docx` on `Chapter N:`
  headings into `kb_chapters`/`kb_sections`, FTS-indexes every section, and
  harvests glossary terms. Run manually or auto-run at startup.

---

## 8. Data model (`app/schema.sql`)

- **Projects & execution:** `projects`, `sprints`, `tasks`, `roadmap_items`,
  `blockers`, `decisions`, `risks` (with a generated `score = likelihood*impact`).
- **Checklists:** `checklist_templates`, `checklist_instances`
  (unique per period+key+project), `checklist_items`.
- **Issues:** `issues` (P0–P3, closure criteria JSON, AI recommendation).
- **Knowledge:** `kb_chapters`, `kb_sections`, `kb_fts` (FTS5, contentless over
  sections), `glossary`.
- **Documents & compliance:** `documents`, `compliance_rules`,
  `compliance_reports`, `compliance_findings`.
- **Reference Library:** `reference_docs`, `reference_chunks`, `ref_fts` (FTS5).
- **Planning:** `milestones`, `deliverables`.
- **Audit:** `agent_events` (every cross-agent action).

Two FTS5 virtual tables (`kb_fts`, `ref_fts`) stay in sync with their content
tables via AFTER INSERT/DELETE/UPDATE triggers. Cascade deletes
(`reference_docs`→`reference_chunks`, project→planning artifacts) rely on the
per-connection `foreign_keys=ON` pragma.

---

## 9. AI integration points

With `ANTHROPIC_API_KEY` set, Claude enhances five spots — each with a rule-based
fallback and an "AI-enhanced" badge when used:

1. **Compliance reports** — exec summary, false-positive/negative review, top actions.
2. **Intake strategy outline** — vision, pillars, first-90-days.
3. **Project planning** — milestones, deliverables, resourcing, risks, sub-tasks.
4. **Issue analysis** — root-cause hypotheses, missing evidence, investigation plan.
5. **Deep search** — query expansion with related AI PM terminology.

In-scope **Reference Library** material is injected as authoritative context into
all of these prompts via `BaseAgent.reference_context()`.

---

## 10. Tests (`tests/`)

`pytest` covers: docx chapter splitting + FTS indexing, the compliance scoring
rubric (complete PRD → *Ready*, weak doc → *Not Ready* with the right gaps),
gap→task generation (priorities + idempotency), the full intake pipeline,
checklist idempotency, P0/P1 auto-escalation, the closure-criteria guard, and the
planning platform (schedule/window math, critical-path detection, rule-based plan
generation, carry-forward, progress stats) — all in the no-API-key path.

**Status: 21 passed** (last run).
