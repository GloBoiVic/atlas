# Fill application integration defect receipt

## Scope

Fixed the V2 fill-application lifecycle defect and added focused PostgreSQL
regression coverage. No Experiment architecture, migrations, environment files,
credentials, or database configuration was changed.

## Changes

- When a pending order receives its first full fill, `apply_fill` now persists
  `ORDER_SUBMITTED` and `ORDER_FILLED` in canonical sequence for all supported
  historical execution versions, including `PHASE5_HISTORICAL_EXECUTION_V2`.
- Preserved the existing savepoint transaction, duplicate-sequence protection,
  and terminal-order idempotency behavior.
- Removed the obsolete Phase4-only guard around the submission transition.
- Extended the focused integration regression to assert `submitted_at` is
  persisted alongside the ordered lifecycle events.

## Validation

- `python -m ruff check backend/execution/fill_application.py backend/tests/integration/test_fill_application.py` — **PASS**.
- Explicit PostgreSQL command using
  `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/atlas_test`
  and `ATLAS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/atlas_test`:

  `python -m pytest -q backend/tests/integration/test_fill_application.py backend/tests/integration/test_golden_flows.py backend/tests/integration/test_api_experiments.py`

  — **PASS: 13 passed, 4 warnings in 36.91s**.
- `python -m pytest -q backend/tests/execution backend/tests/integration/test_experiment_lifecycle.py` — **PASS: 9 passed, 5 skipped in 0.65s**.

Warnings were the pre-existing Starlette/httpx deprecation and unregistered
`price_analysis` mark; they did not affect test results.
