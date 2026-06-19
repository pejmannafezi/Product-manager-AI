# Changelog

All notable changes to the **AI PM Command Center** are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/); this project
does not yet use formal version numbers.

## [Unreleased] — branch `feature/planning-platform` (PR #2)

A planning platform, a reference library, and a full UI overhaul. Backend
behavior stays backwards-compatible; the app remains fully functional with no API
key (every AI step keeps a rule-based fallback). Test suite: **21 passing**.

### Added

**Planning platform**
- New **Planning Agent** that turns project info + knowledge into a realistic
  plan: milestones, a dated deliverables schedule, resourcing recommendations, a
  risk assessment, and a prioritized, dependency-linked task backbone with a
  marked **critical path**.
- **Schedule service** — date-window math, even date-spreading, period rollover,
  critical-path detection (cycle-guarded), progress stats, and Gantt timeline
  positioning.
- Wired into **New Project Intake**: the orchestrator now also generates the plan
  and a critical-path task backbone, and the project page gains **Plan** and
  **Timeline (Gantt)** tabs plus a "regenerate plan" action.

**Reference Library**
- User-provided reference material the agents consult, at **global** (all
  projects) or **project** scope, managed under **References**.
- **Hybrid retrieval**: short references are injected in full; long ones are
  chunked and FTS-indexed so only the chunks relevant to the current action are
  pulled in (RAG), all capped to a token budget. Injected into every agent prompt
  via `BaseAgent.reference_context()`.

**UI / UX overhaul**
- **Accessibility**: visible `:focus-visible` rings everywhere, a translated
  skip-to-main-content link, WCAG-AA muted-text contrast, and a
  `prefers-reduced-motion` guard.
- **Dark mode** driven by `prefers-color-scheme`, built on the token system.
- **Responsive mobile nav** — a CSS-only ☰ disclosure under 760px.
- **Active-nav highlighting** via a `navlink()` macro (`aria-current="page"`).
- **SVG icon system** (`templates/_icons.html`) replacing all emoji icons.
- **Richer empty states** (icon + message + optional CTA) on first-run surfaces.
- **Submit/loading feedback** — spinner + disable on POST form submit.
- **Favicon + theme-color** and descriptive **per-page `<title>`s**.
- **Bilingual** keys added for all new strings (EN + FA).

**Docs**
- `ARCHITECTURE.md` — part-by-part description of the system.
- `UI-REVIEW.md` — the UI review, fixes, verification, and next steps.
- `CHANGELOG.md` — this file.
- `README.md` rewritten to match the current code.

### Changed
- Refactored the app entry point to `app/main.py` (run via `run.py`), with new
  `projects` / `checklists` / `intake` / `refs` routers.
- Idempotent column migrations in `app/db.py` for the new
  `projects` / `tasks` / `checklist_items` columns.
- Grid columns clamped with `minmax(min(…px, 100%), 1fr)` to prevent mobile
  horizontal overflow.

### Added — data model
- `milestones`, `deliverables` (planning artifacts).
- `reference_docs`, `reference_chunks`, `ref_fts` (reference library + FTS).
- New columns: `projects.{requirements, stakeholders, resourcing}`,
  `tasks.{depends_on, is_critical, milestone_id}`, `checklist_items.carried_over`.

### Tests
- New `tests/test_planning.py`: schedule/window math, critical-path detection,
  rule-based plan generation, checklist carry-forward, and progress stats — all
  in the no-API-key path.

### Notes
- Locally-installed Claude skills under `.claude/skills/` are gitignored (personal
  tooling, not project code).

## [Prior] — `main`
- Initial release: Execution, Knowledge, and Compliance agents over a shared
  SQLite database; New Project Intake orchestration; FTS5 knowledge search;
  compliance scoring; bilingual EN / Persian-RTL UI; optional Claude enhancement;
  team-sharing (password gate, Render blueprint, browser guide import).
