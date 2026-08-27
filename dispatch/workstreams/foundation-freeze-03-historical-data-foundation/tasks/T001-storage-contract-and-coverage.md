# T001 — Storage contract and coverage

Status: `DONE_WITH_CONCERNS`

Implement only the canonical V2 persistence and independent analytical/execution
coverage planning described in PLAN.md and ARCHITECTURE.md. Preserve durable data,
use provider/instrument/resolution/component identity, support native M15 MID and M1
BID/ASK, idempotent duplicates, conflicting-observation rejection, completed-bar-count
analytical warm-up ranges,
expected closures, and bounded bulk operations. Add focused tests. Do not implement
coordinator lifecycle, snapshot authority, or unrelated cleanup.

## Receipt

Implemented the T001 storage and coverage slice only.

### Files changed

- `backend/persistence/models.py` — canonical `market_bars` now accepts native
  M1/M15 resolutions with resolution-specific interval/alignment constraints.
- `backend/persistence/market_data_repository.py` — resolution-aware reads,
  missing-range planning, native M1/M15 persistence, provider/instrument/
  resolution/component identity, bounded set-based lookup, and fail-closed
  conflicting duplicates within one provider batch.
- `backend/persistence/migrations/versions/0015_native_market_bar_resolutions.py`
  — migrates the PostgreSQL checks without deleting historical data.
- `backend/market_data/coverage.py` — independent native product plans,
  closure-aware expected starts, deterministic coalesced missing ranges, and
  completed-native-M15 warm-up counting.
- `backend/tests/market_data/test_storage_coverage_v2.py` — deterministic tests
  for completed-bar warm-up, independent products, missing-only planning, and
  closure handling.

### Checks and evidence

- `pytest -q backend/tests/market_data backend/tests/test_historical_data_load.py`
  — **18 passed, 1 skipped** (the skip is the existing environment-dependent
  CLI/database case).
- `python -m compileall -q backend/persistence backend/market_data ...` — passed.
- `ruff check` on all changed Python modules — passed.
- `git diff --check` — passed.

### Concerns / boundaries

- PostgreSQL migration/integration execution was not available in this
  environment, so migration upgrade/downgrade and database trigger behavior
  remain for validation. Existing correction behavior remains versioned and
  snapshot-safe; only conflicting duplicates within a single batch are rejected
  here. Coordinator lifecycle, provider adapter, and snapshot authority were
  intentionally not changed.
