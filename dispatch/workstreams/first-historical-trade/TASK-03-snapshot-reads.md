# TASK-03 — Snapshot-bounded M1 reads

Status: DONE

## Changes

- Extended `DatasetSnapshotRepository` with ordered, half-open membership reads
  bounded by the immutable snapshot coverage and requested MID/BID/ASK
  components.
- Added `SnapshotBarSourceIdentity` and `SnapshotBar` so each returned M1 bar
  carries its immutable `market_bar_id`, content fingerprint, source request
  identity, and retrieval timestamp.
- Added `read_frontier`, which exposes the completed M1 interval ending at `T`
  separately from BID/ASK executable opens beginning at `T`, matching the
  Phase 3 frontier contract without implementing a clock or runner.
- Snapshot queries join `dataset_snapshot_bars` directly and deliberately do
  not filter `market_bars.is_current`; corrections to mutable current heads
  therefore cannot enter a run or alter captured snapshot membership.
- Existing `members` now uses the same ordered immutable read path.

## Validation receipts

- `pytest -q backend/tests/integration/test_market_data_repositories.py` — **3 passed**.
- `ruff check backend/persistence/market_data_repository.py backend/tests/integration/test_market_data_repositories.py` — **passed**.
- `pyright backend/persistence/market_data_repository.py backend/tests/integration/test_market_data_repositories.py` — **0 errors, 0 warnings, 0 informations**.
- Focused integration coverage proves ordering, source request identities,
  correction provenance, and that a snapshot reread remains equal to the
  originally captured bars after the mutable current projection changes.

## Scope exclusions

- No migrations or models were added or changed.
- No clock, runner, M15 aggregation, Phase 4 intrabar realism, Risk,
  execution, API/UI, general data API, or other repository work was added.
- No Git operations were performed.

## Conflicts or blockers

None. The existing immutable association-table protections and Task-02
models were sufficient; no conflict with Task-01 or Task-02 was identified.
