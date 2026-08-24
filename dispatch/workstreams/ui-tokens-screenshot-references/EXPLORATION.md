# Exploration: UI Token + Visual Guide Extraction (R1)

- **Classification:** Architecture (R1)
- **Workstream:** `ui-tokens-screenshot-references`
- **Phase:** Explore (Step 1 of PLAN.md)
- **Owner artifact:** `EXPLORATION.md`
- **Status:** **BLOCKED** (partial) — see Blockers.

## 1. Required Inputs (per PLAN.md / task brief)

| Input | Path | Status |
| --- | --- | --- |
| User brief | this conversation | read |
| Selected `PLAN.md` | `dispatch/workstreams/ui-tokens-screenshot-references/PLAN.md` | read |
| Root `AGENTS.md` | `/Users/vike/Desktop/atlas/AGENTS.md` | read |
| `context/index.md` | `/Users/vike/Desktop/atlas/context/index.md` | read |
| `context/design/design.md` | `/Users/vike/Desktop/atlas/context/design/design.md` | read |
| Approved mockups (`atlas-*-page.png`) | `context/design/` (10 files) | **NOT VISUALLY INSPECTED** — model cannot read images |
| Frontend style/config files (identified) | `frontend/app/globals.css`, `frontend/components/app-shell.tsx`, `frontend/components/ui/button.tsx`, `frontend/app/layout.tsx`, `frontend/package.json` | read |

## 2. Scope Boundary

This is design-context only. No application code, context docs, mockups, PLAN.md, or
dispatch artifacts were edited. No dispatch paths outside the selected workstream were read.
No implementation blueprint is produced.

## 3. Mockup Inventory

All ten approved mockups are PNG image files under `context/design/`:
`atlas-overview-page`, `atlas-strategies-page`, `atlas-strategies-details-page`,
`atlas-experiments-page`, `atlas-experiments-detail-page`, `atlas-experiment-run-page`,
`atlas-compare-experiments-page`, `atlas-deployments-page`, `atlas-journal-page`,
`atlas-journal-detail-page`.

There are no textual/alternative descriptions of these images in the repo. The written
`design.md` is the only design-context prose; it does not enumerate concrete token values.

## 4. Observed Facts (verified from written sources — evidence-backed)

### 4.1 Design intent (from `design.md`)
- Visual direction: clean, modern, restrained, technical, calm, precise. **Light/restrained
  neutral theme preferred.** Explicitly avoid: dark institutional terminal, excessive
  green/red, dense walls, oversized KPI dashboards, gradients, shadows, decorative animations,
  generic fintech visuals.
- Navigation: horizontal top nav (NO sidebar). Active section via restrained emphasis (text
  weight, subtle background, underline/border). No large tabs or excessive color.
- Layout: desktop-first workstation, `max-width` container feel; page = title + short
  supporting context + primary action; no breadcrumbs on top-level pages.
- Cards: selective (account summary, current Position, active Deployment, Experiment metrics,
  focused config groups). No nested card grids or dashboard tile walls. Tables for lists.
- Color-for-meaning: green (positive/healthy/long), red (negative/critical/short),
  blue (selection/primary action/info). Neutral text stays neutral. PAPER/LIVE unmistakable.
- Charts: TradingView Lightweight Charts (candles, trade viz, equity curves, drawdown).
  EMA Sweep Engulfing annotations subtle, not overwhelming.
- Feedback: Sonner for transient feedback only; persistent safety conditions in persistent UI.
- Scope restraint: 1 OANDA account, EUR/USD, small number of StrategyVersions/Deployments.
  USD base currency example `$52,840.50`.
- Success criteria: simple, focused, modern, trader-oriented, easy to scan.

### 4.2 Current frontend implementation conventions (verified from source)
- **Styling engine:** Tailwind CSS **v4** (`@import 'tailwindcss'`; `@theme` block). PostCSS
  via `@tailwindcss/postcss`. No `tailwind.config.js` — v4 CSS-first config.
- **Design tokens defined today (minimal):** in `frontend/app/globals.css`
  - `--atlas-background: oklch(0.985 0.004 250)` (very light, near-white neutral).
  - `--atlas-ink: oklch(0.22 0.025 255)` (dark blue-tinted neutral text).
  - `--color-atlas-blue: oklch(0.52 0.18 255)` (saturated mid-blue).
- **Base font:** Arial, Helvetica, sans-serif (default; no custom font family configured).
- **Conventions in `globals.css`:** `.nav-link` (slate-600, rounded-md, min-h-10, text-sm,
  hover:bg-slate-100 hover:text-slate-950, focus ring blue-600); `.nav-link-active`
  (bg-slate-100, font-medium, slate-950); `.status`/`.status-muted` (slate-500)/
  `.status-success` (emerald-700)/`.status-danger` (red-50 bg, red-800 text);
  `.form-control` (border slate-300, bg-white, focus blue-600 ring); reduced-motion media query.
- **Palette in use (Tailwind utilities, from `app-shell.tsx` / `button.tsx` / `globals.css`):**
  neutrals via `slate` (`slate-100/200/300/500/600/900/950`, `white`); semantic
  `emerald-700` (success/positive), `red-50/red-800` (danger), `blue-600` (focus/primary ring).
- **Buttons (`ui/button.tsx`):** primary = `bg-slate-900` text-white rounded-md min-h-10
  text-sm font-medium, hover:bg-slate-700, focus ring blue-600.
- **Shell (`app-shell.tsx`):** header `border-b border-slate-200 bg-white`; content container
  `max-w-[1440px] px-6 py-12 lg:px-10`; header `min-h-16`; Atlas wordmark `text-lg font-semibold
  tracking-tight`. Right side: `ApiStatus` + Settings icon button.
- **Dependencies (from `package.json`):** `lightweight-charts` ^5.2.1 (charting),
  `lucide-react` (icons), `next` 16, `react` 19, `sonner` ^2.0.8 (toasts), Tailwind v4.
  shadcn/ui conventions appear partially adopted (kebab `ui/` component folder with a hand-rolled
  `Button`), but **no shadcn CLI/setup present** — `ui/button.tsx` is a bespoke component, not a
  generated shadcn component.
- **Accessibility/state helpers:** focus-visible rings (blue-600), `aria-disabled` nav links,
  `disabled` opacity states, `prefers-reduced-motion` support.

## 5. Inference (clearly labeled — NOT verified by mockup inspection)

> The following are reasonable inferences from written context and existing code only. They
> must be validated against the mockups by a model that can read images before any architect
> treats them as evidence.

- Semantic token mapping would likely consolidate current ad-hoc utilities (slate neutrals,
  emerald success, red danger, blue primary/focus) into named `@theme` tokens mirroring the
  documented color-for-meaning rule.
- Type scale would likely stay compact (text-xs metadata, text-sm body/controls, text-lg/2xl
  headings), consistent with `globals.css` and `app-shell.tsx` usage.
- Spacing/radii would likely reuse Tailwind defaults actually in use: `rounded-md` (~6px),
  `min-h-10` (~40px) control height, `px-3/4`, `gap-1.5/2/6/8`, `max-w-[1440px]` container.
- Chart treatment likely maps to Lightweight Charts defaults with subtle EMA/entry/stop/target
  annotations per `design.md` §Charts, but exact theme (colors, gridlines, crosshair) is unknown.
- The `--atlas-background`/`--atlas-ink` pair suggests the theme is **light-first**, consistent
  with design.md's "Light/restrained neutral theme preferred," even though the task brief mentions
  "dark-first" — **conflict to resolve** (see Gaps).

## 6. Gaps / Risks for the Architect

1. **Mockup visual evidence is missing (PRIMARY BLOCKER).** The entire purpose of this
   exploration — extracting *evidence-backed recurring* colors, type, spacing, shapes, components,
   and chart treatment from the ten `atlas-*-page.png` mockups — could not be performed: the
   assigned model (`opencode/deepseek-v4-flash`) does not support image input. No visual token
   values, spacing, or chart treatment were extracted. **Do not proceed to `ARCHITECTURE.md`
   (PLAN step 2) on the current evidence.** Re-run this exploration with an image-capable model,
   or provide a written/structured token description of each mockup.
2. **No alternative mockup description exists.** `context/index.md` lists `design/` as optional;
   `design.md` is prose intent, not per-screen token specs. There is no machine-readable
   description of the PNGs to fall back on.
3. **Light vs dark conflict.** `design.md` §Visual Character says "Light/restrained neutral theme
   preferred" and existing tokens are near-white (`oklch(0.985 …)`), while the PLAN.md constraint
   says "calm, **dark-first** Atlas V2 visual direction." This is a real contradiction an architect
   must resolve with the requester before defining the palette.
4. **shadcn/ui not actually scaffolded.** PLAN and AGENTS.md refer to shadcn/ui, but only a
   hand-rolled `ui/button.tsx` exists; no shadcn components/theme (`components.json`, HSL/CSS vars
   convention) are present. Token naming (CSS-variable style vs Tailwind `@theme`) is an open
   decision affecting the ARCHITECTURE step.
5. **Minimal existing token surface.** Only three CSS vars and one `@theme` color exist. The
   extractable semantic vocabulary is small; the risk is over-deriving tokens from the brief
   screens (violating the "no speculative screen-specific tokens" constraint).
6. **PAPER/LIVE state tokens** (green/red) and connection state styling are specified only in
   prose; concrete values are unverified against mockups.
7. **Accessibility tokens** (focus rings, reduced motion) are present in code but not captured as
   named tokens; worth codifying to avoid drift.

## 7. Recommendation / Next Step

Re-open this workstream with a vision-capable model (or a text-based per-mockup token manifest
provided by the designer) to complete the visual evidence pass, resolve the light/dark conflict,
and only then proceed to PLAN step 2 (`ARCHITECTURE.md`).

## Blockers

- **BLOCKER-1 (hard):** Model `opencode/deepseek-v4-flash` cannot read image input
  (`ERROR: Cannot read image` for every mockup). All ten `context/design/atlas-*-page.png` files
  remain uninspected. Visual evidence extraction is impossible in this session.
