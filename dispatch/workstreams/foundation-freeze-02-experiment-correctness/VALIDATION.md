# Foundation Freeze 02 — Validation

Status: `PASS`

## Receipt

- **ROLE:** VALIDATE
- **WORKSTREAM:** foundation-freeze-02-experiment-correctness
- **BRANCH:** `solo/foundation-freeze-02-experiment-correctness`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Validated:** complete branch after T009 continuation

All database-backed commands below used the exact command-scoped variables
`ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
and `ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`;
no credentials were persisted. Validation changed only this artifact.

## Commands and complete results

Executed sequentially where tests reset the shared PostgreSQL schema:

1. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests/integration/test_migrations.py`
   — **PASS:** `2 passed in 3.37s` (PostgreSQL upgrade → downgrade → upgrade).
2. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests/integration`
   — **PASS:** `37 passed, 4 warnings in 78.25s (0:01:18)`.
3. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest -q backend/tests -m 'not integration'`
   — **PASS:** `291 passed, 1 skipped, 39 deselected, 4 warnings in 74.89s (0:01:14)`.
4. `pytest -q backend/tests/experiments/test_metrics.py backend/tests/experiments/test_runner_diagnostics.py`
   — **PASS:** `24 passed in 0.81s`.
5. `pytest -q backend/tests/experiments`
   — **PASS:** `81 passed in 70.36s (0:01:10)`.
6. `pytest -q backend/tests/test_migration_revision.py`
   — **PASS:** `1 passed in 0.75s`.
7. `python -m compileall -q backend`
   — **PASS:** no output/errors.
8. `git diff --check`
   — **PASS:** no output/errors.
9. `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' alembic heads`
   — **PASS:** `0014_result_metric_state_details (head)`; exactly one head.

## T009 contract and diff verification

- Actual application/test diff is limited to `backend/experiments/metrics.py`,
  `backend/experiments/runner.py`, `backend/tests/experiments/test_metrics.py`,
  and `backend/tests/experiments/test_runner_diagnostics.py` (plus workstream
  coordination artifacts). Drawdown amount and percentage are independent
  maxima over `tuple(equity_points)` in canonical persisted order; no timestamp
  sorting was introduced.
- Typed seam ownership is explicit: Strategy, Market Data, Risk, Execution,
  Validation/Accounting, and Persistence retain narrow categories. SQLAlchemy
  failures map to `PERSISTENCE`; accounting fill `ValueError` is wrapped as
  `VALIDATION` / `ACCOUNTING_INVARIANT`; unexpected non-database failures map to
  `VALIDATION` / `UNEXPECTED_ENGINE_FAILURE`. Classification does not inspect
  exception wording.
- The new regression directly invokes `ExperimentRunner._run_v2` with a typed
  strategy repository whose `get_version` raises `RuntimeError`. It asserts the
  returned failure is `status == FAILED`, category `FailureCategory.VALIDATION`,
  code `UNEXPECTED_ENGINE_FAILURE`, and that durable `mark_failed` receives
  `VALIDATION` and `UNEXPECTED_ENGINE_FAILURE`; it therefore proves the failure
  is not classified as `PERSISTENCE`.
- Focused regressions cover independent drawdown maxima, wording-independent
  classification, typed category owners, SQLAlchemy/Persistence, Strategy, Risk
  rejection, Execution, accounting invariant, and the direct unexpected-engine
  fallback. All focused, experiment, integration, and non-integration suites
  pass.

## Warnings and limitations

Tests emitted four existing warnings: one Starlette/httpx deprecation warning
and three `PytestUnknownMarkWarning` warnings for the existing `price_analysis`
mark. They did not fail tests and are not validation blockers. One
non-integration test was skipped; 39 integration-marked tests were deselected
by the requested selector. PostgreSQL was available. The working tree also
contains unowned/pre-existing changes and untracked `.codegraph/`,
`frontend/.env.local`, and the T009 task receipt; none were modified or
included in this validation artifact.

## Disposition

`PASS` — T009 implementation and required direct `_run_v2` unexpected-engine
regression are verified, all requested checks pass, and only `VALIDATION.md`
was modified by VALIDATE.
