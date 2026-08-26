# TASK-18 Receipt — Real Experiment frontend extraction

## Verdict

**BLOCKED — not implemented.** The requested remediation is not satisfied by
TASK-17's wrapper modules. The responsibility-owning code remains in
`frontend/components/experiment-workflow-legacy.tsx`, which is a 3,133-line
catch-all implementation. This receipt records the evidence and the exact
remaining work; it does not claim completion or visual equivalence.

## Ownership audit

`frontend/components/experiment-workflow.tsx` is currently a 16-line public
re-export entry point, but almost every approved feature module is only a
wrapper back to the legacy file:

| Module | Lines | Current ownership | Required ownership |
|---|---:|---|---|
| `experiment-workflow-legacy.tsx` | 3,133 | All list/setup/status/results/charts/trades/detail/lineage implementation, including legacy classes | Delete, or reduce to a genuinely narrow compatibility shim |
| `experiment-workflow.tsx` | 16 | Public exports plus `strictlyAscending` compatibility export | Keep thin; route composition/public compatibility only |
| `experiments/experiment-list.tsx` | 3 | Re-exports `ExperimentsList` from legacy | List fetch, states, selection, comparison, table, cells |
| `experiments/experiment-setup.tsx` | 3 | Re-exports `ExperimentForm` from legacy | Setup state, validation, load attachment/polling, submit gate |
| `experiments/load-status.tsx` | 3 | Re-exports `StatusBadge` from legacy | Durable load status/progress and Technical details |
| `experiments/experiment-status.tsx` | 3 | Re-exports status page from legacy | Lifecycle start/poll/error and completed handoff |
| `experiments/experiment-results.tsx` | 3 | Re-exports `EquityResults` from legacy | Completed result hierarchy and data orchestration |
| `experiments/metric-summary.tsx` | 3 | Re-exports `MetricCard` from legacy | Seven metric cards and unavailable reasons |
| `experiments/equity-charts.tsx` | 3 | Re-exports `Chart` from legacy | Equity/drawdown series and section composition |
| `experiments/chart-support.ts` | 19 | Chart role/time support exists | Retain one CSS-variable role map/lifecycle support |
| `experiments/trades-table.tsx` | 3 | Re-exports `EquityResults` from legacy | Compact Trades table and zero-Trades state |
| `experiments/trade-detail.tsx` | 3 | Re-exports detail page from legacy | Independent Trade detail fetch/presentation |
| `experiments/price-chart.tsx` | 6 | Re-exports chart symbols from legacy | Candles, EMA, markers, levels, lifecycle |
| `experiments/lineage.tsx` | 3 | Re-exports `Lineage` from legacy | Rationale, Risk, Orders/events, Fills |
| `lib/experiment-formatters.ts` | 57 | Typed formatter surface exists | Shared formatter API used by real owners |

The current wrappers also create forbidden dependency direction: ten feature
modules import `../experiment-workflow-legacy`. The legacy file still contains
the implementation and extensive `slate-*`, `blue-*`, `red-*`, `emerald-*`, and
`amber-*` presentation classes. Therefore the requirement of no legacy palette
classes in implementation modules is not met in substance, even though the
thin entry point and wrapper directories scan cleanly.

## Required extraction (not performed)

Move the existing behavior-preserving code, without changing requests, props,
exports, routes, polling cadence, request-generation guards, chart lifecycle,
or semantics, into the approved owners. Keep shared defensive helpers and
formatters at a lower-level support boundary; keep API orchestration with the
owning feature state machine. Ensure the single `chart-support.ts` role map
resolves chart roles from `globals.css`, and migrate moved presentation classes
to Atlas classes without removing compatibility aliases. Then delete the
catch-all legacy file (or leave only a narrowly justified compatibility shim),
and rerun the complete validation matrix.

## Validation run against current tree

| Check | Result |
|---|---|
| `npm run test:web` | PASS — 23 tests in 9 files |
| `npm run typecheck:web` | PASS |
| `npm run lint:web` | PASS |
| `npm run build:web` | PASS — Experiment list, setup, result, trade-detail, and compare routes compiled |
| `npm run format:check:web` | BLOCKED by five pre-existing warnings: `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, `tests/e2e/.fixtures.json` |

Passing checks validate the wrapper state, not real module ownership, and do
not close TASK-18.

## Browser evidence

Local Host was eligible at viewport 1332×815. `/experiments/new` rendered the
Atlas shell and fail-closed API error state; `/experiments` rendered the list
error state; `/experiments/not-found/trades/1` rendered the API error state.
The API returned HTTP 500 for readiness, configuration options, historical
capability, and active-load requests. Console diagnostics were empty. No valid
completed Experiment or Trade was available, so completed-result hierarchy,
charts, Trade detail, keyboard traversal, focus visibility, responsive data
states, and visual equivalence remain unverified.

## Scope note

No application source, backend, API, dependency, Git state, or other dispatch
artifact was changed by this worker. This artifact is the only owned output.
The source-level extraction must be performed by an authorized frontend builder
with ownership of the listed application files before this workstream can be
closed.
