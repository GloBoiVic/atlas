# TASK-15 Exploration — Experiment workflow refactor extension

## Scope and inputs

- `dispatch/ACTIVE.md` was requested but is absent at the workstream path. The
  root `dispatch/ACTIVE.md` is referenced by prior receipts, but was not loaded
  here because this task owns only this artifact.
- Reviewed `dispatch/workstreams/experiment-correctness-load-ui-audit/PLAN.md`,
  `ARCHITECTURE.md`, prior relevant receipts TASK-03, TASK-06, TASK-07, TASK-08,
  TASK-10, TASK-12, and TASK-14, root `AGENTS.md`, and `context/index.md`.
- Reviewed `context/design/design.md`, `visual-guide.md`, `ui-tokens.md`, the
  three Experiment reference PNG paths named by the plan, and
  `frontend/app/globals.css`.

## Relevant files and current responsibilities

- `frontend/components/experiment-workflow.tsx:1-33` — one client module owns
  navigation hooks, React state/effects, icons, API client calls, time-zone
  context, date formatting, and chart-library loading.
- `frontend/components/experiment-workflow.tsx:35-205` — local untyped data
  model (`Json`, `Status`, `ParameterValues`, `ChartPoint`), timestamp
  normalization (`strictlyAscending`), defensive object/text conversion,
  StrategyVersion identity, status/date/input helpers, snapshot/diagnostic
  labels, metric formatting, price/money/ratio/percent formatting, API error
  messaging, scalar error extraction, and parameter defaults.
- `frontend/components/experiment-workflow.tsx:207-324` — shared result/error
  presentation (`StatusBadge`, `ErrorPanel`, `MetricCard`).
- `frontend/components/experiment-workflow.tsx:326-430` — generic line-chart
  wrapper for equity/drawdown. It dynamically imports Lightweight Charts,
  formats display-zone labels, filters values, sorts/deduplicates timestamps,
  installs `ResizeObserver`, and cleans up the chart.
- `frontend/components/experiment-workflow.tsx:432-518` — assumptions and
  provenance disclosure, including simulation/execution facts, financing,
  snapshot provenance, quality, and gap disclosures.
- `frontend/components/experiment-workflow.tsx:519-721` — completed-result
  orchestration: fetches equity and Trades, computes zero/ambiguous display
  state, renders seven metrics, equity/drawdown charts, progressive price
  analysis disclosure, Trades table, and assumptions disclosure.
- `frontend/components/experiment-workflow.tsx:723-1169` — progressive price
  analysis fetch plus candlestick/EMA/marker/level rendering. `PriceAnalysisCanvas`
  consumes persisted M15/EMA/trade/landmark facts; no EMA calculation is
  present (covered by `frontend/tests/price_analysis.test.tsx:198-221`).
- `frontend/components/experiment-workflow.tsx:1171-1381` — Experiment list:
  fetch/retry state, selection for comparison, header/actions, empty/loading/
  error states, status and metric cells, and table links.
- `frontend/components/experiment-workflow.tsx:1383-2593` — Experiment setup:
  configuration-options loading, StrategyVersion/Data selection, parameter
  validation, UTC period/presets, automatic coverage validation, historical
  load creation/attachment/status polling, durable progress display, completion
  refresh/validation, fail-closed submit checks, and the full form layout.
- `frontend/components/experiment-workflow.tsx:2595-2787` — Experiment status
  page: initial load, optional start command, timeout/error handling, status
  polling, failed/PENDING/RUNNING states, and completed-result handoff.
- `frontend/components/experiment-workflow.tsx:2789-2908` — Trade detail
  candlestick/EMA chart with price levels and chart lifecycle management.
- `frontend/components/experiment-workflow.tsx:2920-2977` — recursive
  `Lineage` renderer for rationale, Risk decisions, Orders/events, and Fills.
- `frontend/components/experiment-workflow.tsx:2979-3153` — Trade detail
  fetch/validation, summary metrics, setup/proposal evidence, bounded chart
  context, ambiguity and omitted-range disclosures, and lineage.

## Imports, callers, routes, and tests

- Imports are local `AppShell`, `Button`, and `UtcDateTimePicker`; API/error
  types and `atlasApi` from `frontend/lib/api-client.ts`; time format/parse
  functions from `frontend/lib/time.ts`; and `useDisplayTimeZone` from
  `frontend/app/providers.tsx`. External imports are Next navigation/link,
  React hooks/types, Lucide icons, Sonner, and dynamic Lightweight Charts.
- Thin route callers are:
  - `frontend/app/experiments/page.tsx:1-5` → `ExperimentsList`.
  - `frontend/app/experiments/new/page.tsx:1-5` → `ExperimentForm`.
  - `frontend/app/experiments/[experimentId]/page.tsx:1-5` →
    `ExperimentStatusPage`.
  - `frontend/app/experiments/[experimentId]/trades/[sequenceNumber]/page.tsx:1-5`
    → `TradeDetailPage`.
- `ExperimentStatusPage` and `strictlyAscending` are directly exercised by
  `frontend/tests/experiment_results.test.tsx` and
  `frontend/tests/price_analysis.test.tsx`. `ExperimentsList` is exercised by
  `frontend/tests/experiment_list.test.tsx`. The result test suite also covers
  zero-Trades, unavailable/infinite metrics, failed/running states, disclosures,
  trade facts, chart cleanup, and detail rendering.
- `frontend/components/experiment-comparison.tsx` is a separate result-adjacent
  caller of `AppShell`, with its own `show`, `metric`, and `field` helpers;
  `frontend/components/strategy-history.tsx` also uses `AppShell` and has a
  separate `date` helper. `AppShell` is shared by six component consumers per
  CodeGraph, so changes to shared presentation have broader blast radius.

## Candidate boundaries and shared formatter opportunities

These are meaningful decomposition seams, not implementation decisions:

- **Workflow shared primitives:** move `StatusBadge`, `ErrorPanel`, metric
  state/formatting, defensive payload helpers, Strategy identity, snapshot
  labels, and date/price labels together only if their input/output contracts
  are kept stable. The same metric-state presentation is currently duplicated
  in `experiment-comparison.tsx:12-27`; comparison currently renders raw values
  rather than the list/detail percent/money/ratio conventions.
- **Chart primitives:** line equity/drawdown, price analysis canvas, and Trade
  chart share dynamic import, theme options, timezone formatters, resize
  handling, cleanup, and timestamp normalization, but differ materially in
  series and marker data. A small chart-options/lifecycle helper is a plausible
  seam; avoid merging domain-specific series preparation into a generic chart.
- **Completed result sections:** `EquityResults` already separates result
  orchestration from `StateDisclosure` and chart components. Further seams are
  metrics summary, equity/drawdown, Trades table, and progressive technical/
  provenance disclosures. Preserve independent price-analysis failure handling.
- **Setup workflow:** configuration initialization, coverage validation, load
  polling/progress, and form submission are distinct state machines inside
  `ExperimentForm`. The explicit coverage `validate` path has no request
  generation guard, while automatic inventory validation uses a local `current`
  guard (`:1560-1590`); this is a correctness/test risk during decomposition.
- **Status/detail shell:** `ExperimentStatusPage` owns lifecycle polling and
  delegates completed rendering. `TradeDetailPage` is independently routable
  and should not acquire Experiment-result state merely for visual reuse.
- `frontend/lib/time.ts` already owns instant/chart/tick formatting and UTC
  parsing. New date/time formatting should use it rather than local formatter
  copies. `formatInstant` is wrapped as `dateLabel` locally to accept unknown
  values.

## Theme and chart color dependencies

- `frontend/app/globals.css:3-55` defines Atlas semantic variables and Tailwind
  aliases for background, surfaces, borders, foregrounds, primary, positive,
  negative, warning, focus, muted states, and chart-local sweep violet.
- Chart code in `experiment-workflow.tsx:350-380`, `:889-927`, `:1000-1047`,
  `:1110-1125`, and `:2805-2837` uses CSS variable strings for canvas, axes,
  grid, equity/drawdown, candles, EMA, markers, and levels. Lightweight Charts
  receives these strings at runtime; preserving these role mappings is
  important because chart-local colors are not ordinary Tailwind classes.
- The approved guide maps equity/EMA/entry to primary, drawdown/stop/down
  candles to negative, up candles/target/exit to positive, grid to border, axes
  to muted foreground, confirmation to warning, and Sweep to chart-local violet.
- TASK-14 records that direct chart hex values were already replaced, but
  `experiment-workflow.tsx` still contains many legacy Tailwind utility names.
  The compatibility layer currently maps those names to Atlas variables; it is
  a migration dependency and should not be removed as part of decomposition
  until all consumers are migrated.

## Other frontend files with legacy color utilities

- `experiment-workflow.tsx` is the dominant remaining legacy consumer: status,
  errors, panels, table states, links, progress, and semantic notices use
  `slate-*`, `blue-*`, `red-*`, `emerald-*`, and `amber-*` utility names (for
  example `:216`, `:241`, `:439`, `:595`, `:1200-1376`, `:1830-2577`, and
  `:2659-3150`). These currently work through `globals.css:258-331`.
- `strategy-history.tsx:49-287` and `experiment-comparison.tsx:57-267` are
  already mostly migrated to `atlas-*` classes and provide nearby patterns for
  semantic panels, tables, links, and status treatment.
- `app-shell.tsx:30-85`, `api-status.tsx:30-55`, and `ui/button.tsx:15-22` use
  shared Atlas component classes/aliases rather than the legacy palette.
- A source scan found no hard-coded hex/rgb/hsl values in frontend TSX/TS; the
  only source color literals are the intentional Atlas variables in
  `frontend/app/globals.css:4-27`.

## Visual route comparison

- The approved references are `atlas-experiment-run-page.png`,
  `atlas-experiments-detail-page.png`, and `atlas-experiments-page.png`, with
  written guidance requiring a shallow horizontal shell, generous gutters,
  focused page header, selective panels, and dark-first surfaces.
- Current source positioning follows that structure: `AppShell` supplies the
  horizontal header and `max-w-[1440px]` main region (`app-shell.tsx:30-87`);
  list uses a header/action row and full-width table (`experiment-workflow.tsx:
  1195-1377`); setup uses a narrow `max-w-4xl` form and stacked fieldsets
  (`:1804-2589`); result uses centered `max-w-5xl` detail content (`:2677-2784`).
- A live Local Host browser comparison could not be performed in this session:
  the localhost browser tools reported “Local Host is not running”. An attempt
  to start the web app found an existing Next process on port 3000 and a second
  process on 3002, but the browser tool still did not classify either route as
  available. Prior receipts TASK-10, TASK-12, and TASK-14 provide the latest
  available route evidence: `/experiments/new`, `/experiments`, and
  `/strategies` rendered dark-first with no console diagnostics; TASK-14
  reported no positioning/layout change required. No new screenshot match or
  mismatch is claimed here.

## Risks and focused test impact

- Splitting the 3,153-line module can accidentally alter client boundaries,
  effect dependency behavior, dynamic chart cleanup, or route-level exports.
  Retain focused tests for each exported route component and chart unmount.
- Preserve fail-closed result states: FAILED must not render result hierarchy;
  RUNNING/PENDING must not expose partial result facts; zero-Trades must retain
  valid metrics and unavailable reasons.
- Preserve independent API failure behavior: equity/Trades remain visible when
  price analysis fails, and price analysis must never fabricate EMA or candles.
- Preserve UTC request semantics versus display-zone labels. Add/retain tests
  around shared formatter extraction for percentage, money, ratio, integer,
  unavailable, infinite, full timestamp, and table/list consistency.
- If setup logic is split, test automatic coverage stale-response guards,
  explicit validation generation/cancellation behavior, load-status polling,
  completion refresh without duplicate commands, unknown/terminal progress,
  and creation remaining disabled until validated completion.
- Preserve keyboard semantics and accessible names for details, tables, charts,
  loading/error states, non-color state cues, and focus rings. Existing tests
  cover key result text but do not constitute full visual or accessibility
  regression coverage.
- Run focused `experiment_results.test.tsx`, `price_analysis.test.tsx`, and
  `experiment_list.test.tsx`, then the complete frontend test/type/lint/build
  checks after any implementation; browser screenshot and console checks remain
  necessary when Local Host is available.

## Receipt summary

- **Artifact:** `dispatch/workstreams/experiment-correctness-load-ui-audit/TASK-15-ui-refactor-exploration.md`
- **Status:** Read-only exploration complete; no application code, Git state, or
  other dispatch artifact was modified.
- **Mapped:** module responsibilities, local helpers/types, imports, route
  callers, tests, formatter seams, chart/theme dependencies, legacy color
  consumers, visual-layout evidence, risks, and focused test impact.
- **Open evidence gap:** live Local Host route/screenshot comparison was not
  executable because the browser tool reported no eligible Local Host; prior
  receipts are cited without extending their claims.
