# TASK-02 Receipt — V2 Experiment Clock and Execution

## Status

Implemented the V2-only historical clock/runner execution semantics. TASK-01
foundation was compatible; no material conflict was found.

## Changes

- Added exact bounded sparse entry lookup at `start_time == frontier` and made
  incomplete sparse buckets explicit unavailable data rather than fabricated or
  delayed execution.
- Reworked V2 replay to evaluate every eligible native M15 frontier exactly
  once, independently of sparse M1 observations, while preserving chronological
  protection and same-observation entry-before-protection ordering.
- Added explicit `EXECUTION_DATA_UNAVAILABLE` gap decisions for actionable
  frontiers without a complete BID+ASK bucket; later quotes cannot satisfy an
  earlier frontier.
- Added fail-closed terminal handling when an open Position has no executable
  observation establishing its terminal outcome, and propagated result quality
  as `DETERMINED_WITH_GAPS` when gap facts exist.
- Disabled the public runner fallback into legacy V1/aggregation dispatch.
- Added focused clock tests for exact entry selection, later-quote rejection,
  and incomplete sparse buckets.

## Files changed

- `backend/experiments/clock.py`
- `backend/experiments/runner.py`
- `backend/tests/experiments/test_clock.py`

## Verification

- `python -m pytest -q backend/tests/experiments/test_clock.py backend/tests/experiments/test_runner_diagnostics.py`: **12 passed**.
- `ruff check backend/experiments/clock.py backend/experiments/runner.py backend/tests/experiments/test_clock.py`: **passed**.
- `python -m compileall -q backend/experiments backend/tests/experiments`: **passed**.
- Integration attempt (`test_phase5_valid_run.py`, `test_golden_flows.py`): **blocked** because `ATLAS_TEST_DATABASE_URL` is not set; 8 skipped and 2 setup errors. No environment files were read or modified.
