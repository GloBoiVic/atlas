# TASK-04 Receipt — Bounded Recovery Fix Pass 1

## Status

Implemented the reported deterministic validation blockers without changing
production safety semantics.

## Changes

- Made historical loading V2-only: removed the unreachable legacy `load_missing`
  path while retaining bounded V2 warm-up and fail-closed completion behavior.
- Removed the unreachable V1 runner creation/run dispatch block; unsupported
  models now return an explicit validation failure instead of entering dead
  code.
- Removed the persistence status branch that encoded the retired V1 model.
- Updated historical-load test doubles to implement the actual repository and
  StrategyVersion contracts, and added V2 regression coverage for successful
  loading and warm-up extension.
- Updated the migration-head assertion to the intentional current head,
  `0012_required_historical_context`.
- Fixed backend Ruff findings, including the required real-data validation
  helper; `python -m ruff check backend` passes.

## Verification

- `python -m pytest -q backend/tests/test_historical_data_load.py backend/tests/test_migration_revision.py backend/tests/experiments/test_runner_diagnostics.py` — **19 passed, 1 skipped**.
- `python -m ruff check backend` — **passed**.
- Full `python -m pytest -q` was attempted; it exceeded the 120-second
  execution limit after progressing through the suite. No database credentials
  were available, so integration validation remains blocked by the existing
  `ATLAS_TEST_DATABASE_URL` prerequisite.

## Files changed

- `backend/market_data/historical_load.py`
- `backend/experiments/runner.py`
- `backend/persistence/experiment_repository.py`
- `backend/tests/test_historical_data_load.py`
- `backend/tests/test_migration_revision.py`
- `backend/tests/integration/_run_validation_real_data.py`
