# Foundation Freeze 02 — Validation

Status: `PASS`

## Receipt

- **ROLE:** VALIDATE
- **WORKSTREAM:** foundation-freeze-02-experiment-correctness
- **BRANCH:** `solo/foundation-freeze-02-experiment-correctness`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Validated:** complete branch after T008

All database-backed commands below used command-scoped variables; no credentials
were persisted.

## Commands and complete results

Executed sequentially where tests reset the shared PostgreSQL schema:

1. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests/integration/test_migrations.py`
   — **PASS:** `2 passed in 4.37s`.
   This exercises the PostgreSQL upgrade → downgrade → upgrade cycle.
2. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests/integration`
   — **PASS:** `37 passed, 4 warnings in 77.72s (0:01:17)`.
3. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests -m 'not integration'`
   — **PASS:** `288 passed, 1 skipped, 39 deselected, 4 warnings in 76.92s (0:01:16)`.
4. `pytest -q backend/tests/test_migration_revision.py` — **PASS:** `1 passed in 0.52s`.
5. `python -m compileall -q backend` — **PASS:** no output/errors.
6. `git diff --check` — **PASS:** no output/errors.
7. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' alembic heads` — **PASS:** `0014_result_metric_state_details (head)`; exactly one head.

## T008 and frozen-contract verification

- Migration integration passes and its inspector assertions confirm the physical
  PostgreSQL names `ck_experiment_results_result_metric_state_keys` and
  `ck_experiment_results_result_metric_state_consistency`.
- T008's completed lifecycle fixtures call `create_result` before
  `mark_completed`; the full integration suite passes, including API and
  lifecycle completion behavior. Completion therefore remains result-backed,
  rather than being weakened to permit completed Experiments without an
  `ExperimentResult`.
- The migration revision test confirms the new revision is the sole Alembic
  head. Upgrade/downgrade/upgrade success confirms both directions address the
  physical constraint names correctly.
- Full integration and non-integration suites pass, so existing application
  behavior and failure-path coverage remain green after T008.

## Warnings and limitations

Tests emitted four warnings: one Starlette/httpx deprecation warning and three
`PytestUnknownMarkWarning` warnings for the existing `price_analysis` mark.
These did not fail tests and are not validation blockers. One non-integration
test was skipped; 39 integration-marked tests were deselected by the requested
selector. No environment limitation occurred: PostgreSQL was available.

## Disposition

`PASS` — all requested validation commands completed successfully. VALIDATE
modified only this `VALIDATION.md` artifact.
