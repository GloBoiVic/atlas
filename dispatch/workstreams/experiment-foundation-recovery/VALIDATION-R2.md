# Validation R2 — Experiment Foundation Recovery

## Verdict

**NOT READY / BLOCKED.** The deterministic V2-focused backend suite, backend
Ruff, backend compileall, and all frontend tests/typecheck/lint/build checks
pass. The full backend suite completes with 259 passed, 37 skipped, and 15
integration setup errors because `ATLAS_TEST_DATABASE_URL` is unset. `pyright`
still reports 2,036 strict-typing errors, and frontend Prettier check still
fails in 14 files. The migration graph is a single linear head at `0012`, but
`alembic check` is blocked because the configured target database is not up to
date. The required real OANDA Practice UI acceptance run is blocked by the
missing dedicated test database and unavailable confirmed credentialed OANDA
Practice session.

No application code, environment files, credentials, or other dispatch
artifacts were modified. No Git commands were run.

## Commands and exact results

### Backend full and targeted validation

- `python -m pytest -q`
  - **FAIL/BLOCKED:** 259 passed, 37 skipped, 15 errors, 4 warnings in
    326.33s (5m26s). All 15 errors are integration setup failures requiring
    the absent `ATLAS_TEST_DATABASE_URL`; no deterministic implementation
    failure was reproduced.
- `python -m pytest -q backend/tests/experiments backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/market_data/test_task3.py backend/tests/strategies/test_ema_sweep_engulfing_v2.py backend/tests/experiments/test_price_analysis_results.py backend/tests/experiments/test_results.py backend/tests/test_historical_data_load.py backend/tests/test_migration_revision.py`
  - **PASS:** 94 passed, 1 skipped in 315.32s (5m15s).
- `python -m ruff check backend`
  - **PASS:** all checks passed.
- `python -m compileall -q backend`
  - **PASS:** no output/errors.
- `python -m pyright`
  - **FAIL:** 2,036 errors, 0 warnings, 0 informations. The output is
    predominantly the existing strict typing/test-double baseline, including
    SQLAlchemy fixture typing and unknown pytest fixture parameters.

### Migration graph and database validation

- `alembic heads && alembic history --verbose`
  - **PASS (graph):** one linear head, `0012_required_historical_context`,
    parent `0011_fix_v2_snapshot_trigger`; history continues through
    `0010_experiment_gap_decisions`, `0009_historical_snapshot_v2`, and the
    earlier linear revisions.
- `alembic check`
  - **BLOCKED/FAIL:** `Target database is not up to date`.
  - No upgrade, downgrade, reset, or other database mutation was attempted.
- The full-suite integration errors identify the database blocker precisely:
  the required dedicated `ATLAS_TEST_DATABASE_URL` is not set. No database
  credentials or environment files were read.

### Frontend validation

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
    `frontend/components/strategy-history.tsx`, generated API code, and
    frontend tests. Formatting was not changed under this validation role.

## V2-only current-path inspection

- CodeGraph inspection and source search found no `PHASE4_MODEL_VERSION`,
  `warm_up_bars`, or `warmup_m15_bars` references under
  `backend/experiments`; no such legacy model labels were found under
  `backend/api`.
- The current runner dispatch is schema-first and accepts only
  `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2`; unsupported models fail with
  `UNSUPPORTED_EXPERIMENT_MODEL` rather than entering a V1 runner fallback.
- Current V2 provenance uses `PHASE5_HISTORICAL_EXECUTION_V2` and result
  schema `PHASE5_EXPERIMENT_RESULT_V2`, with canonical
  `required_historical_context_bars` usage in the current experiment path.
- The retained `load_missing` service/CLI methods in
  `backend/market_data/ingestion.py` and `backend/market_data/cli.py` are
  legacy acquisition surfaces and are still covered by legacy tests. They are
  not current V2 Experiment routing, but remain a literal V1-removal scope
  concern.
- Migration history retains earlier Phase 4/legacy identifiers by design;
  this is immutable history, not evidence that new V2 requests route through
  V1. The graph is linear and the required V2 foundation head is `0012`.

## Integration and real OANDA acceptance

- Integration execution was attempted only through the existing test suite.
  It is **blocked** before database setup because `ATLAS_TEST_DATABASE_URL`
  is unavailable; the project requires a dedicated URL ending in `_test`.
- The required browser UI flow (load missing historical data, durable
  `COMPLETED`, V2 coverage, create/run, completed result, quality/gaps,
  lineage, and provenance) was **not attempted**. There is no available
  dedicated test database and no confirmed credentialed OANDA Practice
  session. No run identifier, load status, result, or broker evidence was
  fabricated.
- Real OANDA UI/database acceptance therefore remains an external blocker,
  separate from the passing deterministic checks.

## Acceptance blockers and required follow-up

1. Provide a dedicated `_test` PostgreSQL URL, migrate/reset only that safe
   database to `0012`, and rerun integration, golden lifecycle, and migration
   checks; do not mutate a shared or credentialed database.
2. Complete the real OANDA Practice UI acceptance flow with approved
   credentials and record durable load/run status, result quality/gaps, and
   provenance.
3. Resolve or explicitly baseline the 2,036 `pyright` errors.
4. Resolve the 14 frontend Prettier failures.
5. Have the orchestrator/reviewer perform the prohibited Git diff scope review.

Until the database-backed golden flow and real OANDA Practice UI gate are
completed (or explicitly accepted as blocked by the approving human), the
workstream is not acceptance-ready.
