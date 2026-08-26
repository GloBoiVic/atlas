# TASK-17 Receipt — Experiment frontend decomposition

## Verdict

**IMPLEMENTED — frontend decomposition applied in the owned application scope.**
The route-facing `experiment-workflow.tsx` remains the compatibility entry point
and preserves `ExperimentsList`, `ExperimentForm`, `ExperimentStatusPage`,
`TradeDetailPage`, and `strictlyAscending` exports. Existing workflow behavior,
API calls, polling, routes, and client-side result semantics remain in the moved
implementation while cohesive feature boundaries now have independently named
modules.

## Changed application files

- `frontend/components/experiment-workflow.tsx` — thin public compatibility entry
  point and route export surface.
- `frontend/components/experiment-workflow-legacy.tsx` — behavior-preserving
  implementation moved from the public entry point; chart role references and
  shared formatter delegation applied.
- `frontend/components/experiments/experiment-list.tsx`
- `frontend/components/experiments/experiment-setup.tsx`
- `frontend/components/experiments/load-status.tsx`
- `frontend/components/experiments/experiment-status.tsx`
- `frontend/components/experiments/experiment-results.tsx`
- `frontend/components/experiments/metric-summary.tsx`
- `frontend/components/experiments/equity-charts.tsx`
- `frontend/components/experiments/trades-table.tsx`
- `frontend/components/experiments/trade-detail.tsx`
- `frontend/components/experiments/price-chart.tsx`
- `frontend/components/experiments/lineage.tsx`
- `frontend/components/experiments/chart-support.ts` — single Atlas CSS-variable
  chart role map and shared chart time adapters.
- `frontend/lib/experiment-formatters.ts` — typed percent, money, ratio,
  integer, price, metric-state, unavailable, and time formatter surface.

No backend, API contract, dependency, route file, strategy, Experiment
semantics, PAPER/LIVE, or Git state was changed by this task.

## Validation evidence

| Command | Result |
|---|---|
| `npm run test:web` | **23 passed** across 9 files |
| `npm run typecheck:web` | **Passed** |
| `npm run lint:web` | **Passed** |
| `npm run build:web` | **Passed**; all Experiment routes compiled |
| Focused Prettier on changed decomposition files | **Passed** |
| `npm run check:web` | **Blocked by pre-existing formatting warnings** in unrelated `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and `tests/e2e/.fixtures.json`; no unrelated files were modified |

Existing focused tests continued to pass, including result lifecycle, zero-Trade,
price-analysis cleanup/independent failure, list formatting, and chart timestamp
guards.

## Local Host evidence

`local-host_localhost_discover_tabs` reported **Local Host is not running**.
No visual equivalence, screenshot, console, failed-network, keyboard traversal,
or responsive overflow claim is made. The approved screenshots and design guides
were reviewed as references before implementation, but post-refactor browser
verification is blocked until the existing `npm run dev:web` environment is
available.

## Scope and recovery

The decomposition is a code-only reversible move. Restore the prior single-file
boundary if lifecycle or request behavior becomes uncertain; do not alter server
authority or compensate with duplicate requests/client-side facts. Pre-existing
modified files shown by Git status were not touched.
