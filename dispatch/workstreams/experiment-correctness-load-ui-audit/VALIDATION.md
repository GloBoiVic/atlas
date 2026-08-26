# Validation — Experiment frontend decomposition

## Verdict

**BLOCKED — keep the workstream open; do not create a closure/review artifact.**
The decomposed frontend passes automated validation and source audits. Live
verification reached the running Local Host, but the API returned HTTP 500, so
no completed Experiment or Trade data was available for result/chart inspection.
Prior real-load and benchmark blockers also remain.

## Required inputs and scope

Reviewed `dispatch/ACTIVE.md`, `PLAN.md`, `ARCHITECTURE.md`,
`TASK-15-ui-refactor-exploration.md`, `TASK-17-frontend-decomposition.md`,
`TASK-14-atlas-theme-ui.md`, the prior `VALIDATION.md`, all current changed
frontend source/tests, `context/design/design.md`, `visual-guide.md`,
`ui-tokens.md`, the approved Experiment screenshots, and
`frontend/app/globals.css`. Root `dispatch/ACTIVE.md` is the active receipt;
there is no workstream-local ACTIVE file.

Validation only inspected application code and the browser. No application code,
other dispatch artifact, or Git state was changed. `frontend/.env.local` was not
opened.

## Automated evidence

| Check | Result |
|---|---|
| `npm run test:web` | **PASS** — 23 tests, 9 files |
| Focused list/result/price tests | **PASS** — included in the 23-test run; result 5, price 7, list 1 |
| `npm run typecheck:web` | **PASS** |
| `npm run lint:web` | **PASS** |
| `npm run build:web` | **PASS** — Experiment list, setup, result, trade-detail, and compare routes compiled |
| Prettier on every changed frontend source/test file, including `frontend/next-env.d.ts` | **PASS** — all matched files use Prettier style |

The build emitted `/experiments`, `/experiments/new`,
`/experiments/[experimentId]`, `/experiments/[experimentId]/trades/[sequenceNumber]`,
and `/experiments/compare`.

## Boundary, exports, and request audit

- `frontend/components/experiment-workflow.tsx` remains the `'use client'`
  compatibility entry point and preserves `ExperimentsList`, `ExperimentForm`,
  `ExperimentStatusPage`, `TradeDetailPage`, and `strictlyAscending` exports.
- The four route callers still import those public workflow exports; route paths
  and links are unchanged.
- API calls remain in the existing moved workflow implementation. No generic
  loader, API adapter, duplicate result coordinator, or changed request payload
  was found. Focused tests cover result/equity/trades, price-analysis failure
  independence, list behavior, polling/lifecycle semantics, and chart cleanup.
- `chart-support.ts` contains the single Atlas CSS-variable chart role map;
  formatter time behavior delegates to `frontend/lib/time.ts`.

## Theme and presentation source audit

- No hard-coded hex, RGB, HSL, or HSLA values were found in the decomposed
  Experiment TS/TSX modules. Chart colors resolve through `chart-support.ts` and
  the variables in `globals.css`.
- No legacy palette utility names were found in
  `frontend/components/experiments/*` or the thin compatibility entry point.
- Legacy names remain extensively in
  `frontend/components/experiment-workflow-legacy.tsx` (notably `slate`,
  `blue`, `red`, `emerald`, and `amber`). This is the intentional compatibility
  legacy file named by TASK-17; its classes resolve through the existing
  `globals.css` compatibility layer. It prevents a clean repository-wide legacy
  class claim and must not be removed without an authorized migration.
- `globals.css` retains the approved deep blue-black canvas, navy surfaces,
  semantic colors, focus ring, reduced-motion rule, and compatibility aliases.

## Local Host evidence (viewport 1332×815)

Local Host was eligible and running. Screenshots were captured at the same live
browser viewport for comparison with the approved Experiment references.

### `/experiments/new`

- **PASS for available state:** Atlas horizontal shell, active Experiments
  navigation, dark-first canvas, spacious gutters, bordered form fieldsets,
  UTC/display-zone context, persistent API status, and fail-closed form wording
  rendered consistently with the approved run-page direction.
- The page text exposed the expected setup hierarchy: Strategy/Data, requested
  period, technical details, historical coverage, strategy settings, and
  coverage validation. Screenshot showed no horizontal overflow at this width.
- API options remained loading (`Loading StrategyVersions…`), so no data-backed
  setup submission or load-status progression could be exercised.
- The date click was dispatched, but no immediate focus/value/navigation effect
  was observable. Structured accessibility snapshot returned only a minimal
  shell, so a complete keyboard traversal/focus-ring claim is **blocked**, not
  passed.

### `/experiments`

- **PASS for failure presentation:** the list header/action placement and Atlas
  shell rendered; persistent `API unavailable` / `Request needs attention`
  treatment included the actionable Retry link and visible text cue, not color
  alone.
- The list request displayed `Atlas API returned 500`. No experiment rows,
  completed result, chart, responsive table overflow, selection, or comparison
  behavior was available to inspect.
- Browser console diagnostics: **0 entries**. Failed-request diagnostics:
  **0 entries reported by the browser tool** (the rendered API 500 remains the
  observed application blocker).

### Completed result and Trade detail routes

No completed Experiment ID was discoverable because `/experiments` returned the
API 500. A non-data probe at
`/experiments/not-found/trades/1` rendered the same persistent API-500 error
state; it is not evidence of a valid Trade detail route. Consequently result
hierarchy, seven metrics, equity/drawdown chart behavior, chart text
alternatives, Trades table, price analysis, lineage, trade inspection, and
completed-route keyboard/focus behavior are **not validated**. No claim of
visual equivalence is made for those states.

The approved `atlas-experiments-page.png`, `atlas-experiments-detail-page.png`,
and `atlas-experiment-run-page.png` were inspected as visual references. The
available setup/list error shell matches the documented dark-first, horizontal,
restrained Atlas direction; reference inspection does not substitute for
data-backed post-refactor verification.

## Retained blockers and next action

- API-backed golden-flow/browser evidence is blocked by the observed HTTP 500.
- Completed result and Trade detail screenshot, chart, accessibility, and
  responsive checks must be rerun with safe seeded data at a consistent viewport.
- Full keyboard traversal/focus visibility and chart text-alternative verification
  remain unproven; the browser snapshot/click did not expose reliable focus
  evidence.
- The authorized real OANDA Practice load remains terminally failed and was not
  retried. The complete three-case fake benchmark with detailed telemetry is
  still absent. These prior blockers prevent R1 closure.

Start with a healthy API and safe test data, then rerun all four route checks,
including console/network diagnostics, responsive overflow, keyboard/focus,
charts, and Trade inspection. Keep compatibility aliases and the workstream
open; do not retry the real OANDA load without explicit authorization.
