# TASK-01 — PositionState and financial Position domain

Status: DONE

## Changes

- Renamed the Strategy-boundary `Position` enum to `PositionState`.
- Updated StrategyContext validation/defaults, EMA Sweep Engulfing imports and
  suppression logic, public domain exports, and affected tests.
- Added `backend/domain/trading.py` with the separate immutable financial
  `Position` contract and `FinancialPositionState` enum.
- Added strict financial validation: FLAT positions cannot carry exposure
  facts; LONG/SHORT positions require finite positive Decimal quantity and
  entry price plus UTC `opened_at`; serialization preserves Decimal strings.
- Added tests proving Strategy `PositionState` and financial `Position` are
  distinct and that invalid financial contracts fail closed.

## Contracts and affected paths

- Strategy state: `backend/domain/strategy.py`,
  `backend/domain/__init__.py`, `backend/strategies/ema_sweep_engulfing.py`.
- Financial exposure foundation: `backend/domain/trading.py` and public
  exports in `backend/domain/__init__.py`.
- Tests: `backend/tests/domain/test_trading.py` and
  `backend/tests/strategies/test_ema_sweep_engulfing.py`.

## Validation receipts

- `pytest -q backend/tests/domain/test_primitives.py backend/tests/domain/test_trading.py backend/tests/strategies/test_contract.py backend/tests/strategies/test_ema_sweep_engulfing.py`
  — **67 passed**.
- `pytest -q` — **148 passed, 1 skipped**; one pre-existing FastAPI/httpx
  deprecation warning.
- `ruff check` on all changed application/test paths — **passed**.
- `pyright backend/domain backend/strategies backend/tests/domain backend/tests/strategies`
  — **0 errors, 0 warnings**.

## Scope exclusions

No persistence, migrations, repositories, Risk, execution, SimulationClock,
runner, fixtures, UI/API, Phase 4 realism, or generalized infrastructure was
added. No Git operations were performed.

## Conflicts or blockers

None. Existing uncommitted dispatch context changes were preserved and not
modified.
