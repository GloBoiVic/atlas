# TASK-DBFIX4 — PostgreSQL current market-bar projection ordering

## Result

Implemented the minimal persistence fix in `MarketDataRepository.apply_bar_batch`.
When a previously corrected variant is reactivated, the repository now defers
setting that variant current until after SQLAlchemy flushes the old current row
as non-current. This preserves the append-only variant history and serialized
current projection while satisfying PostgreSQL's partial unique constraint
`uq_market_bars_current`. The existing venue-row `FOR UPDATE` lock remains the
concurrency serialization point.

Updated the focused regression in
`backend/tests/integration/test_market_data_repositories.py` to flush the
corrected replacement before reactivation, explicitly exercising the persisted
ordering boundary.

## Verification

All commands used the explicit isolated test database URL:

```text
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'
ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'
```

- `backend/tests/integration/test_market_data_repositories.py` and
  `backend/tests/integration/test_golden_flows.py`: **7 passed** in **50.78s**.
- `backend/tests/integration/test_market_data_ingestion.py`: **5 passed** in
  **4.08s**.

No migrations, environment files, credentials, or databases were changed.
