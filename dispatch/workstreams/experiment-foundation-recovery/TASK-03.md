# TASK-03 Receipt — V2 API and Frontend Contract

## Status

Implemented the V2-only API/frontend contract and acceptance-flow disclosures.
Core domain, market-data persistence, clock, and runner behavior were not changed.

## Changes

- Configuration options now expose only `.v2` StrategyVersions and V2 DatasetSnapshots;
  removed V1 warm-up fields from public experiment/strategy schemas.
- Added V2 architecture, native M15 MID, sparse M1 BID/ASK, required historical
  context, bounded one-minute entry policy, result schema, quality, and gap-count
  provenance to API payloads.
- Result price-analysis diagnostics now use the canonical required-context field;
  read composition includes immutable model/result/metric provenance and quality.
- Frontend proof, coverage, assumptions, and result views now use native M15 MID +
  sparse M1 BID/ASK language, show the bounded post-frontier bucket, and disclose
  execution gaps and result quality.
- Preserved durable historical-load attachment, create/run status polling, completed
  result gating, explicit zero-trade rendering, failed-state fail-closed rendering,
  and non-UUID normal labels.
- Updated focused frontend result coverage to assert V2 provenance disclosures.

## Files changed

- `backend/api/experiments.py`
- `backend/api/schemas.py`
- `backend/api/strategies.py`
- `backend/experiments/results.py`
- `frontend/components/experiment-workflow.tsx`
- `frontend/components/strategy-history.tsx`
- `frontend/lib/api.generated.ts`
- `frontend/tests/experiment_results.test.tsx`

## Verification

- `python -m ruff check backend/api/experiments.py backend/api/schemas.py backend/api/strategies.py backend/experiments/results.py` — **passed**.
- `python -m pytest -q backend/tests/experiments/test_price_analysis_results.py backend/tests/experiments/test_results.py` — **36 passed**.
- `npm run test:web -- --run frontend/tests/experiment_results.test.tsx frontend/tests/experiment_list.test.tsx` — **6 passed**.
- `npm run typecheck:web` — **passed**.
- `npm run lint:web` — **passed**.
- `npm run build:web` — **passed**.
- `python -m pytest -q backend/tests/integration/test_api_experiments.py` — **blocked**: `ATLAS_TEST_DATABASE_URL` is not set (1 passed, 8 setup errors). No environment files were read or modified.
- Real OANDA UI acceptance — **blocked/not attempted** because the required credentialed environment and test database are unavailable; no credentials were exposed.

## Notes

The existing runner/configuration still carries internal historical model labels for
the previously implemented execution path; changing those would cross the explicit
TASK-03 prohibition on runner/core changes. Public API and UI choices/copy are V2-only.
