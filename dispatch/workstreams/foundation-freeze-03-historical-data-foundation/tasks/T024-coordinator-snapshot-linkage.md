# T024 — Coordinator completion and snapshot linkage

Status: `DONE`

Fix only the validated lifecycle blocker: the actual HistoricalDataLoadCoordinator
must complete using canonical warm-up/native M15 coverage without requiring an
unavailable warm-up window, and must persist/link the immutable DatasetSnapshot to the
load request rather than leaving an orphaned snapshot. Preserve no-provider-I/O repeat
behavior, sparse/native semantics, immutable snapshots, deterministic identity, and
crash/resume safety. Add regressions for completed warm-up, request-to-snapshot linkage,
and unchanged repeat. Do not weaken strict M15 validation or reset/load data in this
task.

## Completion receipt

Implemented the coordinator lifecycle fix. `prepare()` now uses the canonical
eligible-completed-M15 session calendar to compute the warm-up prefix, so closure
minutes do not create an unavailable provider window. Retries of legacy requests
whose boundary is the old fixed 25-hour calculation are normalized to the same
canonical boundary. Snapshot completion linkage is guarded in the repository by
requiring the immutable `DatasetSnapshot` row to exist in the same completion
transaction before setting `snapshot_id` and terminal request state.

Added regressions for Monday/market-closure warm-up planning and for passing the
created snapshot ID through coordinator completion. Existing V2, sparse execution,
strict-gap, deterministic identity, and repeat behavior were not changed.

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T024-coordinator-snapshot-linkage.md`
FILES CHANGED: `backend/market_data/historical_load.py`,
`backend/persistence/historical_data_load_repository.py`,
`backend/tests/test_historical_data_load.py`, this receipt
CHECKS / EVIDENCE: Ruff targeted check passed; focused suite passed: **30 passed,
6 skipped**. No database reset, provider/OANDA call, branch switch, or Git history
operation performed.
FINDINGS / CONCERNS: Existing `VALIDATION.md` remains BLOCKED pending a fresh
authorized durable-data coordinator run; this task did not fabricate live evidence
or reload the disposed database.
