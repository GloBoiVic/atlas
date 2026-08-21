# TASK-08 — Experiment runner

Status: IMPLEMENTED — REVIEW REQUIRED

## Changes

- Added `backend/experiments/runner.py`, composing immutable snapshot membership
  reads, M1→M15 aggregation, `SimulationClock`, verified
  `StrategyVersion` registry resolution, repositories, pure Risk, pure
  simulated execution, and atomic Fill application.
- Warm-up frames evaluate with exposure disabled; trading evaluation uses only
  completed M15 bars and post-decision BID/ASK opens. The runner stops after
  the first completed target Trade.
- Entry facts include the checkpoint model version and completed-M1 source
  identities. PRE_FLIGHT and PRE_SUBMISSION Risk facts, entry Order/Fill, target
  Order/Fill, Position, Trade, account, and terminal Experiment projections are
  persisted through existing boundaries.
- Added categorized, sanitized result failures and terminal failure handling;
  `PHASE3_TRADE_NOT_COMPLETED` is never returned as success.

## Validation receipts

- `ruff check backend/experiments/runner.py` — passed.
- `python -m compileall -q backend/experiments/runner.py` — passed.
- `pytest -q backend/tests/experiments/test_clock.py backend/tests/risk/test_service.py backend/tests/execution/test_simulated.py` — **17 passed**.
- No Git operations were performed.

## Scope exclusions

- No API, UI, CLI, runtime, OANDA, PAPER/LIVE, reconciliation, or Phase 4
  intrabar/gap realism was added. Stop closure remains unsupported rather than
  fabricated; target closure only uses the existing simulated adapter.
- No EMA implementation or persisted LONG/SHORT golden fixtures were added;
  those remain Task 9.
- No new tables, migrations, general infrastructure, or dependency was added.

## Conflicts and limitations

- The approved Task 2 schema has no persisted failure-category/detail columns.
  The runner therefore persists terminal `FAILED` status and discloses the
  sanitized categorized failure in `ExperimentRunResult`; adding failure
  columns would exceed this task and conflict with the existing schema scope.
- No controlled PostgreSQL runner integration fixture was added in this pass;
  the existing component tests passed, but the end-to-end runner receipt and
  Task 9 golden flows remain review gates.
- Existing uncommitted dispatch context and prior task files were preserved and
  not modified.

## Terminal status

Implementation complete, with the limitations above explicitly surfaced for
independent validation/review before Task 9.
