# Integration fixture remediation receipt

## Scope

Updated integration/golden fixtures and obsolete assertions only. No production
code, migrations, environment files, credentials, or database configuration was
changed.

## Changes

- Reworked the golden seed to persist the current V2 snapshot contract: native
  M15 MID analytical memberships and intentionally sparse M1 BID/ASK execution
  observations.
- Generated the V2 fingerprint from ordered analytical/execution memberships,
  used `PHASE5_HISTORICAL_EXECUTION_V2`, and retained
  `required_historical_context_bars` in the StrategyVersion fixture.
- Used the repository-returned snapshot identity when a duplicate fingerprint
  is encountered, allowing multiple lifecycle experiments in one isolated test.
- Removed the golden fixture's retired V1 M1 snapshot membership and obsolete
  source-ID/target-R assertions; updated API assertions to the current
  `requiredHistoricalContextBars` field and valid snapshot coverage.
- Removed the explicitly retired V1 runner failure persistence test.
- Kept per-test PostgreSQL truncation isolation as the duplicate-fingerprint
  protection; no production behavior was changed.

## Validation

- `python -m ruff check backend/tests/integration` — **PASS**.
- Explicit PostgreSQL command using
  `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/atlas_test`
  and `ATLAS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/atlas_test`:

  `python -m pytest -q backend/tests/integration/test_golden_flows.py backend/tests/integration/test_experiment_lifecycle.py backend/tests/integration/test_market_data_repositories.py backend/tests/integration/test_market_data_ingestion.py backend/tests/integration/test_api_experiments.py`

  — **PASS: 26 passed, 4 warnings in 155.24s (0:02:35)**.

Warnings were the pre-existing Starlette/httpx deprecation and unregistered
`price_analysis` mark; they did not affect test results.
