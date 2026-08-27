# Foundation Freeze 02 — Validation

Status: `PASS`

## Receipt

- **ROLE:** VALIDATE
- **WORKSTREAM:** foundation-freeze-02-experiment-correctness
- **BRANCH:** `solo/foundation-freeze-02-experiment-correctness`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Validated:** fresh independent validation of the approved final T009 correction

All database-backed commands used the exact command-scoped variables
`ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
and `ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`.
No credentials were persisted. Only this artifact was modified by VALIDATE.

## Checks and complete results

Executed sequentially because the PostgreSQL tests reset the shared schema:

1. Migration cycle: `pytest -q backend/tests/integration/test_migrations.py` — **PASS**, `2 passed in 4.13s` (upgrade → downgrade → upgrade).
2. PostgreSQL integration suite: `pytest -q backend/tests/integration` — **PASS**, `37 passed, 4 warnings in 78.46s`.
3. Non-integration suite: `pytest -q backend/tests -m 'not integration'` — **PASS**, `294 passed, 1 skipped, 39 deselected, 4 warnings in 74.88s`.
4. Focused diagnostics/metrics: `pytest -q backend/tests/experiments/test_metrics.py backend/tests/experiments/test_runner_diagnostics.py` — **PASS**, `27 passed in 0.63s`.
5. Full experiments suite: `pytest -q backend/tests/experiments` — **PASS**, `84 passed in 66.87s`.
6. Migration revision: `pytest -q backend/tests/test_migration_revision.py` — **PASS**, `1 passed in 0.42s`.
7. Compile: `python -m compileall -q backend` — **PASS**, no output/errors.
8. Formatting: `git diff --check` — **PASS**, no output/errors.
9. Alembic heads: `alembic heads` with the exact scoped variables — **PASS**, `0014_result_metric_state_details (head)`; exactly one head.

## T009 contract verification

- Actual diff confirms `_run_v2` catches only `StrategyVersionUnavailableError` around `implementation_for_version`; unrelated `KeyError` and `IndexError` reach `UNEXPECTED_ENGINE_FAILURE`, not `STRATEGY_VERSION_UNAVAILABLE`.
- Stage ownership advances through Strategy lookup/evaluation, snapshot and clock Market Data, entry/protection/accounting/equity, and result/metrics/completion seams. Typed accounting failures remain Validation-owned; SQLAlchemy remains Persistence-owned; classification does not inspect exception wording.
- Drawdown correction remains unchanged: amount and percentage are independently maximized over canonical persisted equity sequence order, with no timestamp sorting.
- Direct regressions exercise both registry unavailability and unrelated lookup errors through `_run_v2`, durable unexpected-engine failure handling, independent drawdown maxima, wording-independent classification, seam owners, Risk rejection, Execution, accounting invariant, SQLAlchemy/Persistence, and result/completion behavior. Normal Risk rejection remains a persisted `RiskDecision`, not a terminal experiment failure.

## Warnings and concerns

Four existing warnings appeared (Starlette/httpx deprecation and three unknown `price_analysis` marks); none failed validation. One non-integration test was skipped and 39 integration-marked tests were deselected by the requested selector. Pre-existing/unowned changes remain in the worktree (`PLAN.md`, `.codegraph/`, `frontend/.env.local`, and T009 receipt); they were not modified.

## Disposition

`PASS` — required T009 behavior and regressions are verified; every requested diagnostic, experiment, PostgreSQL, migration, compile, head, and diff check passed.
