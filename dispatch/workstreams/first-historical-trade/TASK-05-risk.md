# TASK-05 — Central Risk and sizing

Status: DONE

## Changes

- Added the explicit-input `RiskService` in `backend/risk/service.py` with
  `PRE_FLIGHT` and `PRE_SUBMISSION` decisions.
- PRE_FLIGHT fail-closed checks require a RUNNING Experiment, actionable
  opening direction, known FLAT Position, known positive USD account equity,
  supported EUR/USD economics, and valid stop/target/configuration.
- PRE_SUBMISSION uses executable ASK for long and BID for short, validates stop
  geometry, derives the target from actual entry, calculates
  `equity × risk_per_trade`, floors Decimal sizing to whole EUR units, and
  proves actual risk does not exceed budget.
- Added focused long/short sizing, actual-entry target, market-movement, and
  required-rejection unit tests. Risk does not access persistence, broker
  adapters, or submit Orders; Strategy receives no account or sizing inputs.

## Validation receipts

- `uv run pytest -q backend/tests/risk/test_service.py` — **7 passed**.
- `uv run ruff check backend/risk backend/tests/risk` — **passed**.
- `uv run pyright backend/risk backend/tests/risk` — **0 errors, 0 warnings, 0 informations**.

## Required rejection coverage

`POSITION_ALREADY_OPEN`, `INVALID_STOP`, `INVALID_QUANTITY`,
`ACCOUNT_STATE_UNKNOWN`, `EXPERIMENT_NOT_RUNNING`, and
`UNSUPPORTED_INSTRUMENT_ECONOMICS` are represented as typed rejection codes
and exercised by focused tests where applicable.

## Scope exclusions

No execution adapter, clock, runner, fixtures, additional schema or
migrations, API/UI, PAPER/LIVE behavior, broker integration, or Phase 4
execution realism was added. No Git operations were performed.

## Conflicts or blockers

None. The current persistence models already provide RiskDecision storage for
later caller-owned persistence; this task keeps the calculation boundary pure
and does not add a schema or persistence side effect.
