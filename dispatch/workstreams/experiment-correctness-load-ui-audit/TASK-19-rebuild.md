# TASK-19 Experiments frontend rebuild receipt

## Status

DONE

## Changed files

- Deleted `frontend/components/experiment-workflow-legacy.tsx`.
- Rebuilt the route entrypoint in `frontend/components/experiment-workflow.tsx`.
- Physically moved implementation bodies into named modules: list (233 lines), setup (1,249), load status (77), run status (216), results (298), metrics (65), equity charts (123), Trades (9), price charts (621), lineage (79), and trade detail (208), with shared helpers in `shared.ts`.
- Updated chart role support and retained formatter contracts.
- Updated one stale chart-count assertion to reflect the intended equity + drawdown + price-analysis result view.
- No backend, API client, route, Strategy, Risk, execution, or dependency changes.
- Added authoritative FastAPI `Experiment.identity` assembled from persisted
  StrategyVersion, DatasetSnapshot, VenueInstrument, Instrument, and Experiment
  period facts; added typed identity schemas and StrategyVersion market/methodology
  metadata; Trade detail consumes owning Experiment identity.
- Updated frontend generated contract/types, Strategy presentation, and stale UI
  assertions for the new API-backed information contract.

## Evidence

- `npm run test:web` — passed, 9 files / 23 tests.
- `npm run typecheck:web` — passed.
- `npm run lint:web` — passed.
- `npm run build:web` — passed.
- Targeted Prettier check for changed frontend modules — passed.
- `npm run format:check:web` — blocked only by five pre-existing unrelated warnings (`frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, `tests/e2e/.fixtures.json`).
- Source audit: no legacy imports, forbidden palette utility classes, or literal chart hex colors in `frontend/components/experiments/**`; legacy file is absent.
- Local Host: `/experiments/new`, `/experiments`, and `/experiments/not-found` rendered with the Atlas dark shell, semantic token styling, responsive layout, shadcn/native controls, persistent error state, and no console errors. The Technical details disclosure interaction was dispatched and verified by visible content; the list Run Experiment action was dispatched. API readiness and Experiment requests returned HTTP 500, so loaded setup, running, completed-results, chart, and Trade-detail browser flows remain blocked. No full visual acceptance is claimed.
- Backend integration: `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests/integration/test_api_experiments.py` — 9 passed.
- Strategy backend regression: same dedicated test database, `backend/tests/integration/test_strategy_persistence.py backend/tests/experiments/test_comparison.py` — 8 passed.
- Final frontend: `npm run test:web`, `npm run typecheck:web`, `npm run lint:web`, `npm run build:web` — passed.
- Local Host final identity check: Strategy, Experiment, and Trade pages render backend-provided identity; Strategy technical details are collapsed; no console errors or failed network requests.

## Concern

The former 3,162-line catch-all is gone and no responsibility module delegates to it. Responsibility modules own real implementations. The authoritative identity contract is now served by FastAPI and consumed by Next.js. The five unrelated format warnings remain outside this scope; all required tests, typecheck, lint, build, focused backend integration, and Local Host identity checks pass.
