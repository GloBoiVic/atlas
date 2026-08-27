# T008 — Live evidence completion

Status: `BLOCKED`

Resolve the remaining T007 validation gates:

- repair the API timestamp test fixture so its requested execution range has complete
  M1 BID/ASK membership and the full backend suite is green;
- run a genuine durable full-calendar-year OANDA-backed acquisition followed by a
  repeat covered request, proving zero provider calls and recording the required
  metrics without exposing credentials.

Do not weaken V2 coverage validation or fabricate provider data. Update this receipt
with exact evidence and any environment limitation.

## Completion receipt

### Fixture repair

- Updated `backend/tests/integration/test_api_experiments.py` so the timestamp
  contract fixture uses complete execution membership for its requested
  `2026-01-06T01:00:00Z`–`2026-01-06T02:00:00Z` range.
- Added the opt-in `complete_execution` fixture mode in
  `backend/tests/integration/test_golden_flows.py`; it persists both native M1
  `BID` and `ASK` observations for each requested minute without changing the
  sparse execution-behavior fixture.
- `pytest -q -m 'not integration'`: **307 passed, 5 skipped, 39 deselected**.
- `ruff check` on both changed integration fixtures: **passed**.
- An environment-enabled `pytest -q backend/tests` run collected successfully
  but exceeded the 120-second execution limit after reaching 41% (the
  non-integration result above is the complete suite result available locally).

### Durable OANDA evidence attempt

- Environment was available from the existing local configuration; credentials
  were not printed or persisted.
- Requested range: `2025-01-01T00:00:00Z`–`2026-01-01T00:00:00Z` (full calendar
  year), using `MarketDataService.load_v2` with PostgreSQL and the real
  `OandaHistoricalBarSource`.
- Alembic was upgraded to head before the attempt.
- The first real M15 provider window returned data, but durable persistence
  failed before commit with PostgreSQL check constraint
  `ck_market_bars_exact_one_minute`: the row was native M15
  (`2025-01-01T22:15:00Z`–`2025-01-01T22:30:00Z`) while the database still
  enforced a one-minute interval.
- Safe metrics: **1 M15 provider call observed, 0 committed windows, repeat
  request not run**. No valid first-run or zero-provider-call repeat evidence
  can be claimed.

### Remaining gate

The durable run is blocked by the existing PostgreSQL schema constraint. The
`0015_native_market_bar_resolutions` migration attempts to drop constraints by
the legacy names `exact_one_minute`/`m1_only`, while the live database reports
the naming-convention form `ck_market_bars_exact_one_minute`. The migration/schema
must be reconciled by the owning database task, then this exact year request and
an unchanged repeat request must be rerun and metrics recorded. No V2 validation
was weakened and no provider data was fabricated.
