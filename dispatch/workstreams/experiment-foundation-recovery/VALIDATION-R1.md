# Validation R1 — Experiment Foundation Recovery

## Verdict

**NOT READY / BLOCKED.** The targeted recovery regression tests, V2-focused
tests, backend compile/Ruff checks, and frontend tests/typecheck/lint/build pass.
The full backend suite still has 15 integration setup errors because
`ATLAS_TEST_DATABASE_URL` is unset, `pyright` reports the existing strict typing
baseline, and frontend formatting still fails. Alembic graph inspection passes,
but `alembic check` is blocked by the unavailable/out-of-date database.

No application code or other dispatch artifact was modified. No environment
files or credentials were read. No Git commands were run.

## Commands and results

### Targeted recovery and V2 validation

- `python -m pytest -q backend/tests/test_historical_data_load.py backend/tests/test_migration_revision.py backend/tests/experiments/test_runner_diagnostics.py`
  - **PASS:** 19 passed, 1 skipped in 5.44s.
- `python -m pytest -q backend/tests/experiments backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/market_data/test_task3.py backend/tests/strategies/test_ema_sweep_engulfing_v2.py backend/tests/experiments/test_price_analysis_results.py backend/tests/experiments/test_results.py`
  - **PASS:** 64 passed in 3m38s.
- `python -m pytest -q backend/tests/experiments/test_clock.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/market_data/test_task3.py backend/tests/strategies/test_ema_sweep_engulfing_v2.py backend/tests/experiments/test_price_analysis_results.py backend/tests/experiments/test_results.py`
  - **PASS:** 76 passed in 2m06s.
- `python -m compileall -q backend`
  - **PASS.**
- `python -m ruff check backend`
  - **PASS:** all checks passed.

### Full backend suite

- `python -m pytest -q`
  - **FAIL/BLOCKED:** 259 passed, 37 skipped, 15 errors, 4 warnings in
    3m51s. All errors are integration setup failures requiring the absent
    `ATLAS_TEST_DATABASE_URL`; no deterministic implementation failure was
    reproduced in this run.
- `python -m pyright`
  - **FAIL:** 2036 errors, 0 warnings, 0 information. Errors are predominantly
    the existing strict typing/test-double baseline, including SQLAlchemy test
    fixture typing and unknown pytest fixture parameters.

### Migration graph and revision checks

- `alembic heads && alembic history --verbose`
  - **PASS (graph):** one linear head, `0012_required_historical_context`,
    parent `0011_fix_v2_snapshot_trigger`.
- `python -m pytest -q backend/tests/integration/test_migrations.py backend/tests/test_migration_revision.py`
  - **PASS/BLOCKED:** 1 passed, 2 skipped; migration integration tests skipped
    without the dedicated database.
- `alembic check`
  - **BLOCKED/FAIL:** `Target database is not up to date`. No migration upgrade,
    downgrade, reset, or other database mutation was attempted.

### Frontend checks

- `npm run test:web -- --run`
  - **PASS:** 9 files, 23 tests.
- `npm run typecheck:web`
  - **PASS.**
- `npm run lint:web`
  - **PASS.**
- `npm run build:web`
  - **PASS:** Next.js production build completed and routes generated.
- `npm run format:check:web`
  - **FAIL:** Prettier reports formatting issues in 14 files, including
    `frontend/components/experiment-workflow.tsx`,
    `frontend/components/strategy-history.tsx`, and generated API code.
    Formatting was not changed under this validation role.

## Remaining V1 / warm-up references

The current experiment path has no matches for `warm_up_bars`, `load_missing`,
or the old Phase 4 model in `backend/api`. Relevant remaining matches are:

- `backend/experiments/runner.py`: `PHASE4_MODEL_VERSION`, `version.warm_up_bars`
  compatibility reads, `run_path="PHASE4"`, and warm-up propagation in internal
  construction/provenance.
- `backend/experiments/configuration.py`: `MODEL_VERSION =
  "PHASE4_HISTORICAL_EXECUTION_V1"`.
- `backend/experiments/results.py`: a `getattr(version, "warm_up_bars", 0)`
  compatibility fallback.
- `backend/experiments/clock.py`: a stale “derived M15” comment.
- `backend/market_data/cli.py` and `backend/market_data/ingestion.py`: retained
  `load_missing` CLI/service methods and warm-up CLI arguments.
- Historical migrations retain V1 schema/model compatibility identifiers by
  design; these are immutable migration history, not evidence of a new request
  routing through V1. Current persistence models still expose a synonym for the
  renamed context column.

These references remain a scope/design concern against the approved literal
V1-removal boundary, although the targeted tests confirm the public runner
fallback was removed and the V2 path is exercised.

## Integration and real OANDA acceptance

Integration tests were attempted in the existing safe environment and are
blocked by the missing `ATLAS_TEST_DATABASE_URL` (the project requires a
dedicated URL ending in `_test`). The required real OANDA Practice UI flow is
**not executable**: no test database and no confirmed credentialed OANDA
Practice session are available. It was not attempted; no run ID, load status,
result, or broker evidence was fabricated.

## Required follow-up

1. Provide a dedicated `_test` PostgreSQL URL, run migrations from the current
   `0012` head, and rerun the full integration/golden lifecycle and migration
   checks.
2. Resolve or explicitly baseline the 2036 `pyright` errors.
3. Resolve the 14 frontend Prettier failures.
4. Complete the real OANDA Practice UI acceptance flow with approved
   credentials, recording durable load/run status, result quality/gaps, and
   provenance.
5. Have the orchestrator/reviewer perform the prohibited Git diff scope review.
