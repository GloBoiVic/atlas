# Task 02 — Clock receipt

## Changed paths

- `backend/experiments/clock.py`
- `backend/tests/experiments/test_clock.py`

Added the simulation frontier contract without changing runner orchestration or
execution behavior. `SimulationClock` now exposes complete chronological M1
BID/ASK/MID observations through a half-open range, validates one-minute UTC
bars, and attaches the complete post-decision M1 observation to a decision
frame when available. Existing `completed_m1` and `executable_opens` fields
remain compatible for the next sequential task.

## Frontier guarantees

- Trading range remains UTC and M15-aligned and is `[trading_start,
  trading_end)`.
- M15 bars ending at `trading_start` are warm-up-only; zero warm-up emits no
  historical frame, and warm-up frames never allow exposure.
- Decision frontiers satisfy `trading_start < T < trading_end`; a bar ending
  exactly at `trading_end` is not evaluated.
- M1 observations are chronological, complete, non-fabricated, and half-open;
  scheduled session closures are skipped and incomplete open-session minutes
  fail rather than being synthesized.
- Signal-bar completion and post-decision execution data remain separate; the
  first eligible execution interval begins at the frontier.
- M15 derivation remains the existing `aggregate_m1_to_m15` boundary; no
  second aggregator was introduced.

## Focused checks

- `uv run pytest backend/tests/experiments/test_clock.py backend/tests/market_data/test_task3.py` — **14 passed**
- `uv run ruff check backend/experiments/clock.py backend/tests/experiments/test_clock.py` — **passed**
- `python -m compileall -q backend/experiments` — **passed**

## Scope exclusions

No execution pricing/slippage or lifecycle, Fill application, runner
orchestration/results, API/UI/runtime, broker, PAPER/LIVE, or general
infrastructure was implemented. No dispatch artifact other than this receipt
was modified, and no Git-changing command was performed.

## Blockers

None.
