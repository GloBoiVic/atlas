# TASK-13 — V2 phase timings

## Scope and method

One complete successful `MarketDataService.load_v2` was measured against the
disposable `atlas_test` PostgreSQL database. The deterministic fixture was the
same V2 shape used by TASK-11: EUR/USD, UTC half-open 30-day range, 2,880
completed native M15 MID bars, and 86,400 completed M1 BID/ASK observations
(89,280 total bars/observations).

No OANDA call, Strategy/PAPER/UI/schema compatibility change, or source-file
instrumentation change was made. The diagnostic run used test-process-only
monotonic wrappers around the two fake provider methods, M1 application,
coverage, V2 fingerprinting, and SQL execution; the existing V2 phase boundaries
were then accounted for. This was a single local observation, not a benchmark.

## Post-fix phase timings

Wall-clock `time.monotonic()` measurements, in seconds:

| Requested phase | Post-fix |
|---|---:|
| Planning | 0.000 |
| Native M15 fetch | 0.126 |
| M1 BID/ASK fetch | 3.733 |
| M15 persistence | 0.438 |
| M1 persistence | 68.418 |
| Immutable union/membership work | 31.926 |
| Fingerprint/snapshot creation | 1.561 |
| Coverage validation | 8.725 |
| **Total** | **114.926** |

The planning value is the measured synchronous validation/dispatch portion and
rounded below 1 ms. Immutable union/membership includes the execution-membership
insert (17.044 s) plus the remaining V2 membership/transaction work (14.882 s).
M15 persistence is the native analytical membership insert/SQL portion. The
phase values reconcile to total within rounding (114.927 s versus 114.926 s).

## Before/after context

TASK-11's pre-fix and post-fix captures did not split every requested phase. Its
recorded values were:

| Phase | Before | After |
|---|---:|---:|
| M1 persistence | 68.276 s | 46.527 s |
| Combined post-persistence phase | 52.972 s | 28.120 s |
| Total | 123.240 s | 76.376 s |

Those captures used the same 2,880/86,400 fixture, but are separate runs from
the phase-complete diagnostic above; they must not be combined as a time-series
comparison. The pre-fix run failed at V2 membership insertion with:
`psycopg.errors.RaiseException: V2 membership requires a V2 snapshot`.

## Regression and validation

The exact TASK-11 runtime failure remains covered by and prevented in the two
focused PostgreSQL regressions:

```text
2 passed
backend/tests/integration/test_market_data_ingestion.py::test_v2_snapshot_creation_returns_without_nested_mapping_lock
backend/tests/integration/test_market_data_repositories.py::test_v2_bulk_memberships_persist_representative_large_batch
```

Focused checks also passed:

```text
ruff check backend/persistence/market_data_repository.py
python -m compileall -q backend/persistence backend/market_data
```

No performance claim is made beyond these measurements. They are local,
single-run observations with database, Python, and machine variance; the
timings are evidence of a successful post-fix load and phase accounting only.
