# UI/UX Review & Fix Report — AI PM Command Center

**Date:** 2026-06-19
**Method:** Reviewed the site against the `ui-ux-pro-max` skill's priority checklist
(Accessibility → Touch/Interaction → Style → Layout → Typography/Color → Animation).
**Scope:** Visual design, consistency, accessibility, and polish — no behavior or
backend changes. Stack unchanged (vanilla CSS/Jinja2, no build step), bilingual
EN + Persian-RTL preserved.

---

## Starting point

The existing stylesheet was a clean, sensible foundation: CSS custom properties,
logical properties (`margin-inline-*`, `text-align: start`) so RTL mostly "just
works", and a semantic badge system. It was **functional but flat** — and it had
real accessibility gaps. The review focused on the highest-impact issues first.

---

## Issues found → fixes applied

### §1 Accessibility (CRITICAL)

| Issue | Fix |
|---|---|
| **No visible keyboard focus** on links, buttons, inputs, tabs, or nav — keyboard users couldn't see where they were. | Added a global `:focus-visible` ring (`--ring`), plus tuned focus styles for inputs (brand border + ring) and the dark topbar (light ring for contrast). |
| **No skip-link** — keyboard/screen-reader users had to tab through the whole nav on every page. | Added a visually-hidden `.skip-link` ("Skip to main content") that appears on focus and jumps to `#main`. Translated EN + FA (`a11y.skip`). |
| **Emoji `🧭` used as the brand icon** — font-dependent, inconsistent across platforms, not theme-able (`no-emoji-icons`). | Replaced with an inline SVG compass that inherits `currentColor`, marked `aria-hidden`. |
| **Borderline muted-text contrast** (`--muted: #69718a` ≈ 4.3:1). | Darkened to `#5b6175` (~5.4:1) to clear WCAG AA for the small 13px text it's used on. |
| No `prefers-reduced-motion` handling for the new transitions. | Added a `@media (prefers-reduced-motion: reduce)` block that neutralizes transitions/animation. |

### §2 / §7 Touch, Interaction & Animation

| Issue | Fix |
|---|---|
| **State changes snapped** (0ms) — buttons, tabs, nav, links had no transition. | Added a shared `--ease` (160ms) token; applied to hover/focus on links, buttons, tabs, nav, inputs, rows, and cards. |
| **Buttons had no hover/active feedback.** | Hover darkens to `--brand-ink`; `:active` nudges 1px; secondary/danger/disabled each get correct distinct states. |
| Nav link tap targets were a little small (6px padding). | Bumped padding for comfortable hit area; added `touch-action: manipulation` to buttons to kill the 300ms tap delay. |

### §4 / §6 Style & Typography polish

| Issue | Fix |
|---|---|
| **Flat cards** — no elevation, weak hierarchy against the gray page. | Added a two-step shadow scale (`--shadow-sm` on cards, `--shadow-md` on the topbar and on hover). |
| **Knowledge chapter cards** had only a border-color hover. | Added a subtle lift (shadow + `translateY(-2px)`) for a tactile, scannable library. |
| **Repeated raw `#eef0f7`** in 5 places (secondary button, tabs, progressbar, Gantt track, hover) — not tokenized. | Consolidated into `--fill` / `--fill-hover` semantic tokens (consistency + easier future theming). |
| Data columns used proportional figures (numbers jittered). | Added `font-variant-numeric: tabular-nums` to tables, scores, Gantt dates, and progress stats. |
| Table rows had no affordance. | Added a quiet row hover. |

---

## Files changed

| File | Change |
|---|---|
| `app/static/css/app.css` | Rewritten with focus rings, skip-link, shadow/elevation scale, motion tokens, button/tab/input states, tabular figures, reduced-motion query, and `--fill` tokenization. Every existing selector preserved. |
| `app/templates/base.html` | Added skip-link, replaced emoji brand with inline SVG, gave `<main>` an `id="main"` skip target. |
| `app/translations/en.json`, `fa.json` | Added `a11y.skip`. |

---

## Verification

- **All pages render** (`/`, `/projects`, `/checklists`, `/intake`, `/references`) → HTTP 200 via the FastAPI test client.
- **CSS serves** with the new rules present (`:focus-visible`, shadow tokens).
- **Markup confirmed**: skip-link present, SVG brand present, emoji removed.
- **JSON valid** for both translation files.
- **Full test suite: 21 passed** — no regressions.

> Note: changes are pure CSS/markup and verified to render, but a final **visual
> pass in a browser** (especially the Persian RTL view and dark-OS contrast) is
> recommended before sharing externally.

---

## Follow-up: emoji → SVG icons (done)

The dashboard, intake-result, and login pages used emoji as section icons
(⭐ ⏰ 🚧 ⚠️ 🧩 🔥 ✅ 🤖 📚 🗺️ 🧭 🔒), which the `no-emoji-icons` rule flags as
font-dependent and non-theme-able. Added a reusable Jinja macro
(`app/templates/_icons.html`) that renders a single, consistent Lucide-style SVG
set inheriting `currentColor`, and replaced every emoji with `{{ icon('…') }}`.
Header icons are tinted with the brand color via `h1 .icon, h2 .icon`. Verified
in-browser; no emoji remain in any template; full suite still 21 passed.

## Follow-up v2: dark mode, active nav, mobile nav (done)

All verified in-browser with headless-Chrome screenshots (light + dark, desktop +
mobile); full suite still 21 passed.

1. **Dark mode** — added a `@media (prefers-color-scheme: dark)` block driven by
   the existing token system. Tokenized the last hardcoded fills (`--input-bg`)
   and split link/accent text into a `--link` token so card-surface text and
   icons lighten correctly on dark; `mark` and agent-feed colors get dark-mode
   overrides; shadows/focus-ring re-tuned. The always-dark topbar now reads as
   intentional in both themes.
2. **Active-nav highlighting** — a `navlink()` macro in `base.html` marks the
   current page with `.active` + `aria-current="page"` (no router changes; uses
   `request.url.path`).
3. **Mobile nav** — a CSS-only disclosure (hidden checkbox + ☰ label) collapses
   the 10-item nav under 760px into a toggle that stacks nav, search, and the
   language switch full-width. Also fixed a latent horizontal-overflow bug by
   clamping the grid columns with `minmax(min(340px, 100%), 1fr)`.

Added translation keys `a11y.skip` and `a11y.menu` (EN + FA).

## Follow-up v3: empty states + loading feedback (done)

- **Richer empty states** — an `emptystate()` macro (soft icon + message + optional
  CTA) replaces plain italic text on the first-run surfaces: Projects (with a "New
  Project Intake" CTA), Knowledge, and the global/project Reference lists. Added
  `projects.empty` / `kb.empty` keys (EN + FA).
- **Submit/loading feedback** — a small global enhancement in `app.js` shows a
  spinner on the submit button and disables it when a POST form is submitted
  (covers the slow agent-driven flows: intake, compliance upload, AI analyze,
  plan generation). Skips cancelled `confirm()` submits and `data-noloading`
  forms; honors reduced-motion. Verified in-browser; suite 21 passed.

## Follow-up v4: professional finish (done)

- **Favicon + theme-color** — added an SVG app icon (`static/favicon.svg`, the
  brand compass on an indigo tile) and a `theme-color` meta; browsers previously
  showed a blank default icon.
- **Per-page `<title>`** — every page now sets a descriptive title
  ("Projects · AI PM Command Center", project/issue/chapter names on detail
  pages) instead of all tabs reading the same app name. Verified across 11+ routes;
  suite 21 passed.

## Still recommended (next steps)

- Convert remaining in-content emoji if any new ones surface (dashboard, intake,
  and login sets are already done).
- Consider skeleton placeholders if any view later loads data asynchronously
  (the app is currently server-rendered, so this isn't needed yet).
