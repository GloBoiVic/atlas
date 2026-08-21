# TASK-07 — SimulationClock ordering and no-lookahead

Status: DONE

## Changes

- Added `backend/experiments/clock.py` with a narrow, immutable-observation
  `SimulationClock` and `ClockFrame` contract.
- At each UTC M15 frontier `T`, frames expose the completed M1 interval ending
  at `T` first, exactly one completed MID M15 decision bar ending at `T`, and
  only BID/ASK M1 opens beginning at `T` for execution.
- Enforced EUR/USD/OANDA M1 and M15 MID inputs, UTC/M15-aligned ranges,
  duplicate-frontier rejection, strict ordering, and the half-open
  `[trading_start, trading_end)` trading interval.
- Added warmup ordering hooks: selected completed M15 bars ending at or before
  `trading_start` are emitted with exposure disabled; trading frames are only
  emitted when `trading_start < frontier < trading_end`.
- Added tests proving signal-bar M1 data cannot be reused as post-decision
  execution data, BID/ASK-only execution opens, warmup exposure suppression,
  and range-alignment validation.

## Validation receipts

- `uv run pytest -q backend/tests/experiments/test_clock.py` — **3 passed**.
- `uv run ruff check backend/experiments backend/tests/experiments` — **passed**.
- `uv run pyright backend/experiments backend/tests/experiments` — **0 errors,
  0 warnings, 0 informations**.

## Scope exclusions

- No runner orchestration, Strategy implementation or fixtures, Risk/execution
  behavior, snapshot repository changes, UI/API, persistence, broker behavior,
  Phase 4 execution realism, or Git operations were performed.
- The clock does not evaluate Strategies, create facts, submit Orders, apply
  Fills, or model intrabar sequence/stop-target execution.

## Conflicts or blockers

None. Task-03's immutable `SnapshotBar`/source identity and `read_frontier`
contracts were reused; no conflict with Tasks 1–6 was identified.
