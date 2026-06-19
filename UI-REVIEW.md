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

## Deliberately left out (recommended next steps)

These are worthwhile but bigger than a styling pass and need visual testing:

1. **Full dark mode.** The variable system makes it feasible, but the topbar,
   badges, and several light fills need paired light/dark tokens and per-page
   contrast checks — best done as its own change with screenshots.
2. **Active-nav highlighting.** The nav doesn't mark the current page; passing an
   `active` flag from the routers + an `aria-current="page"` style would aid
   orientation (`nav-state-active`).
3. **Empty/loading states.** A few lists rely on plain italic "empty" text;
   richer empty states with a suggested action would help first-run users.
4. **Mobile nav.** At very narrow widths the 10-item nav wraps to several rows; a
   collapsible menu under ~640px would tidy this up.
