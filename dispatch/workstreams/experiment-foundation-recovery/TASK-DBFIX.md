# Integration-test remediation receipt

## Scope

Updated only integration-test fixtures/tests. No production code, migrations,
environment files, credentials, or database state were changed.

## Changes

- Replaced `warm_up_bars` StrategyVersion constructor/SQL references with
  `required_historical_context_bars` in persistence and fill/failure fixtures.
- Removed the explicitly retired Phase4/V1 integration coverage:
  `test_phase5_valid_run.py`, `_run_validation_real_data.py`, and the obsolete
  V1 configuration-gating test module.
- Removed Phase4 branches and assertions from the reusable golden/API fixtures;
  retained the long/short golden lifecycle and API/lifecycle coverage under the
  current model-version path.
- Updated lifecycle fixture setup to seed through the current golden fixture,
  avoiding the retired configuration fixture dependency.

## Validation

- `python -m ruff check backend/tests/integration` — **PASS**.
- `python -m compileall -q backend/tests/integration` — **PASS**.
- Focused integration/golden pytest collection ran, but PostgreSQL execution was
  **BLOCKED**: `ATLAS_TEST_DATABASE_URL` is not set in this environment.
  Exact observed outcomes were environment setup errors (`KeyError` or the
  fixture's required-variable failure), not production failures; golden tests
  that skip when the URL is absent were skipped.
- The requested explicit shell invocation was attempted and stopped before
  pytest because `ATLAS_TEST_DATABASE_URL` was unset. No database URL was
  fabricated or read from files.

## Remaining gate

Run the focused integration/golden suite with an existing dedicated
`ATLAS_TEST_DATABASE_URL` ending in `_test`. Database-backed production defects
remain unclassified until that run is available.
