# Task 01 — Strategy v2

## Status

**COMPLETE** — implemented the approved v2 Strategy source without changing v1,
database schema, APIs, Risk, execution, or Phase 5 behavior.

## Changes

- Added `backend/strategies/ema_sweep_engulfing_v2.py` with implementation key
  `ema_sweep_engulfing.v2`, warm-up 200, fixed `expiry_window=5`, and the four
  approved bounded runtime parameters.
- Added `backend/strategies/indicators_v2.py` with deterministic explicit-period
  EMA and Wilder ATR calculations.
- Added focused v2 schema, bounds, and indicator tests at
  `backend/tests/strategies/test_ema_sweep_engulfing_v2.py`.
- Preserved the existing v1 source files byte-for-byte. Explicit registry/catalog
  integration is intentionally left to ordered Task 02.

## Validation receipts

- `ruff check` on all Task 01 source/tests: **passed**.
- `python -m compileall` on v2 source: **passed**.
- Focused pytest (`test_ema_sweep_engulfing_v2.py` plus existing v1 suite): **26 passed**.
- v1 worktree diff for `ema_sweep_engulfing.py` and `indicators.py`: **clean**.
- Source archive fingerprints:
  - v1: `20c2bf0f1d0bba0574487e39d03f9ea0d9cc06c03ad17147d7a00abd94c8e3a3`
  - v2: `56b236e6dc6094e9940775a1b38ae10148556448cf55151a82ea368ec4497354`

## Blockers

None within Task 01 scope. Registry/catalog synchronization remains the approved
Task 02 boundary.
