# TASK-05 — Missing-only warm-up union

## Receipt

- **Role:** Backend remediation builder
- **Scope:** V2 historical-load persistence and coordinator seam only.
- **Status:** Implemented and focused-validated.
- **Git:** No Git operations were run.

## Implementation

- Added immutable `DatasetSnapshotRepository.v2_analytical_members`, which reads
  the exact native M15 MID rows captured by an existing V2 snapshot.
- Added `MarketDataService.load_v2_incremental`. It fetches native OANDA M15
  only for the newly required prefix, independently plans execution BID/ASK
  missing ranges from canonical persisted M1 rows, applies only those ranges,
  unions the prior native membership with the fetched prefix, and creates a
  new V2 snapshot. Existing snapshots and memberships are never updated.
- Updated `HistoricalDataLoadCoordinator.run` to use the incremental seam for a
  warm-up extension when available; the initial acquisition remains `load_v2`.
- Added a deterministic coordinator regression test proving an extension emits
  one initial acquisition plus one prefix acquisition and completes from the
  extended snapshot.

## Exact application files changed

- `backend/market_data/ingestion.py`
- `backend/market_data/historical_load.py`
- `backend/persistence/market_data_repository.py`
- `backend/tests/test_historical_data_load.py`

## Evidence

- `pytest -q backend/tests/test_historical_data_load.py` — **15 passed, 1
  skipped** (the existing PostgreSQL-dependent case).
- `pytest -q backend/tests/test_historical_data_load.py
  backend/tests/integrations/test_oanda_source.py` — **37 passed, 1 skipped**.
- `ruff check` on all changed application/test files — **passed**.
- `python -m compileall -q backend/market_data backend/persistence` —
  **passed**.

The coordinator regression asserts the deterministic request/acquisition shape
for the warm-up extension: `full=1`, `prefix=1`, with no second full-range
acquisition. Execution range planning is independent of native M15 membership;
native M15 is never derived from M1.

## Limitations

- PostgreSQL integration coverage was not run because the test URL is not
  exported in the pytest process; TASK-04 records that the dedicated
  `atlas_test` database is reachable through dotenv and must be explicitly
  injected by the operator.
- The new persistence path requires the existing V2 repository and source
  seams; pre-V2 test doubles continue to exercise the prior initial-load path.
- No real OANDA request or timing benchmark was run by this task; no provider
  latency or performance claim is made.
