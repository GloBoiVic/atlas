# Task 03 — Simulated execution receipt

## Changed paths

- `backend/execution/contract.py`
- `backend/execution/simulated.py`
- `backend/tests/execution/test_simulated.py`

## Implemented semantics

- Extended the pure immutable execution contracts for complete M1 BID/ASK
  observations, optional close prices, source MarketBar IDs, and Fill price
  provenance.
- Added fixed adverse tick slippage. Long entries use ASK and short entries use
  BID; liquidation uses the adverse BID/ASK side. Target limits fill at the
  requested price without slippage or improvement.
- Added market `EXIT` support for deterministic `END_CLOSE` fills.
- Simulated stop fills, target fills, gap-through stops, intrabar price basis,
  and non-positive post-slippage rejection.
- Added a pure protection-pair decision method. When one OHLC observation
  touches both protection levels, STOP_LOSS wins and the result records
  `STOP_LOSS_ADVERSE_FIRST_V1` ambiguity policy.
- Fill provenance includes source bar ID, raw executable reference price,
  price basis, slippage per unit, and analytic slippage cost. No spread is
  charged separately and no persistence or exposure state is mutated.

## Validation

- `uv run pytest backend/tests/execution/test_simulated.py` — **9 passed**
- `uv run pytest backend/tests/integration/test_golden_flows.py backend/tests/integration/test_fill_application.py` — **4 passed**
- `uv run ruff check backend/execution/contract.py backend/execution/simulated.py backend/tests/execution/test_simulated.py` — **passed**
- `python -m compileall -q backend/execution` — **passed**

## Exclusions

No Session, I/O, Strategy, Risk, persistence transition, runner orchestration,
API/UI/runtime, broker, PAPER/LIVE, session-calendar, financing, commission,
or speculative execution abstraction was added. Existing clock and runner
changes were preserved and not expanded under this task.

## Blockers and integration note

No Task 03 blocker. The existing Phase 3 runner still owns its legacy narrow
observation construction and orchestration; Task 05 must supply the Task 02
full chronological observations and invoke the new protection/end-close
contracts without moving that responsibility into this pure adapter.

No Git-changing command was performed. Pre-existing changes and `.codegraph/`
were preserved.
