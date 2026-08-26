# TASK-11 — Deterministic V2 load timing and runtime remediation

## Scope and safety

Implemented and verified the post-persistence V2 snapshot remediation. The
benchmark used a deterministic fake provider and the disposable `atlas_test`
PostgreSQL database only: EUR/USD, UTC half-open 30-day range, native M15 MID,
and independent M1 BID/ASK. No OANDA credentials or network were used. Native
M15 semantics, independent BID/ASK execution, missing-only warm-up, immutable
snapshots, and fail-closed validation were retained. No Strategy, PAPER, UI, or
schema migration change was made. No Git operation was run.

## Reproduction and exact root cause

The V2 path reached `DatasetSnapshotRepository.create_v2_validated` after M1
rows had committed, then failed while inserting membership rows. The focused
PostgreSQL reproduction raised:

```text
psycopg.errors.RaiseException: V2 membership requires a V2 snapshot
SQL: INSERT INTO dataset_snapshot_execution_observations DEFAULT VALUES
```

Root cause was the bulk insert call being made through an ORM-mapped class with
an empty parameter collection. SQLAlchemy emitted `DEFAULT VALUES`, so the
append-only trigger saw no V2 snapshot identity. The same issue applied to an
empty gaps collection. The fix uses explicit table inserts with mapping rows and
skips each insert when its collection is empty. This preserves database checks,
triggers, membership identity, and snapshot immutability while avoiding the
large ORM object materialization cost in the post-persistence phase.

The existing focused integration regressions
`test_v2_snapshot_creation_returns_without_nested_mapping_lock` and
`test_v2_bulk_memberships_persist_representative_large_batch` failed with the
exact exception above during the first implementation attempt and pass after
the table/empty-input correction.

## Timing evidence

The fixture generated 2,880 native M15 bars and 86,400 execution observations.
Instrumentation used `time.monotonic()` around provider fetches, mapping
planning, M1 persistence, coverage, and snapshot construction. The first
pre-change capture separately measured M1 persistence and the combined
post-persistence phase; it did not separately time native fetch or planning.

| Phase | Before (s) | After (s) |
|---|---:|---:|
| Planning/mapping | not separately captured | 0.060 |
| Native M15 fetch | not separately captured | 0.031 |
| M1 BID/ASK fetch | not separately captured | 1.626 |
| Native M15 persistence | included in snapshot phase | included in snapshot phase |
| M1 persistence | 68.276 | 46.527 |
| Immutable union/membership, fingerprint, snapshot, coverage | 52.972 combined | 28.120 snapshot/fingerprint/coverage |
| Coverage validation (within snapshot phase) | not separately captured | 5.544 |
| Total | 123.240 | 76.376 |

The measurements are wall-clock observations on the local disposable database,
not a duration promise. Run-to-run variance is material (a later after-fix run
measured 149.114s), so no performance reduction claim is made from this sample.
The evidence does show that the corrected path completes snapshot creation for
the deterministic 30-day load instead of leaving a post-persistence no-snapshot
failure.

## Validation

| Command | Result |
|---|---|
| Focused V2 integration regressions | **2 passed** |
| Historical-load + OANDA source tests | **38 passed, 1 skipped** |
| Relevant ingestion/repository integration tests | **49 passed** |
| Full backend suite with injected disposable test URL | **320 passed, 1 skipped, 4 warnings** |
| `ruff check backend/persistence/market_data_repository.py` | **Passed** |
| `python -m compileall -q backend/persistence backend/market_data` | **Passed** |

The skip is the pre-existing PostgreSQL-conditional test behavior when its
individual invocation lacks the test URL; the full run was executed with the
approved local dotenv-derived test URL injected only into the child process.
No real OANDA load was retried.

## Remaining uncertainty

The preserved real OANDA attempt had no traceback, so this deterministic fixture
proves and fixes the reproduced post-persistence membership failure but cannot
retroactively prove that its exact production exception was identical. The real
request remains terminal FAILED and must not be retried without explicit
authorization. Native M15 persistence remains included in the atomic snapshot
phase rather than separately timed; no further optimization is proposed without
new evidence.
