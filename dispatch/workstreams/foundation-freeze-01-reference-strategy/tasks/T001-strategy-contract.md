# T001 — Correct Strategy contract

## Status

`DONE`

## Ownership

BUILD owns this task.

## Scope

Implement the approved immediate-confirmation, ARMED W1–W5 state machine,
ATR14-at-confirmation stop methodology, trigger behavior, typed/persisted
Strategy evidence, and public `Strategy.evaluate` regression tests.

## Acceptance

- Confirmation is immediate-only, directional, and strictly swept.
- A valid confirmation arms with zero consumed watch bars.
- W1–W5 are consumed exactly once; W5 is eligible and W6 is not.
- Restart, duplicate, gap, competing-setup, and reset behavior is deterministic.
- Proposed stop uses ATR14 including the confirmation candle.
- Tests exercise the public seam, not private helpers.

## Required receipt

Record files changed, checks run, and concerns here when complete.

## Completion receipt

- Files changed: `backend/strategies/ema_sweep_confirmation_break.py`,
  `backend/domain/strategy.py`, `backend/tests/strategies/test_ema_sweep_confirmation_break.py`,
  and relevant registration tests.
- Checks: `pytest -q backend/tests/strategies/test_ema_sweep_confirmation_break.py
  backend/tests/strategies/test_contract.py backend/tests/strategies/test_provenance.py`
  backend/tests/experiments/test_configuration.py` (29 passed); compileall,
  Ruff, and diff checks passed.
- Evidence: public `evaluate_strategy` tests cover immediate strict
  confirmation, PRICE_TRIGGERED evidence, numeric EMA/ATR and stop inputs,
  zero-watch ARMED state, W1-W5, W6 expiry, and production registration.
- Findings: Strategy owns the analytical frontier and emits SetupFacts,
  proposed stop, ASK/BID trigger, and target methodology without sizing or
  execution concerns.
- Findings: legacy `ema_sweep_engulfing.py` and its tests remain unchanged;
  pre-freeze undeployed registration now uses immutable
  `ema_sweep_confirmation_break.v2` with state schema 2 and evidence version
  `REFERENCE_STRATEGY_EVIDENCE_V2`; corrected decisions omit wall-clock expiry,
  and typed evidence marks the same-candle sweep/confirmation explicitly.

## Corrective receipt — 2026-08-26

- Files changed: `backend/domain/strategy.py`,
  `backend/strategies/contract.py`,
  `backend/strategies/ema_sweep_confirmation_break.py`,
  `backend/strategies/ema_sweep_engulfing.py`,
  `backend/strategies/ema_sweep_engulfing_v2.py`,
  `backend/tests/domain/test_primitives.py`,
  `backend/tests/strategies/test_ema_sweep_confirmation_break.py`,
  `backend/tests/strategies/test_ema_sweep_engulfing.py`,
  `backend/tests/integration/test_golden_flows.py`,
  `backend/tests/test_historical_data_load.py`,
  `backend/tests/integration/test_strategy_persistence.py`,
  `backend/tests/integration/test_fill_application.py`.
- Checks: targeted Strategy/domain/runner/configuration pytest (`84 passed`),
  Ruff, compileall, and `git diff --check` passed.
- Evidence: `StrategyState` is schema 2 only and serializes no `window_bars`;
  public evaluation assertions cover candle identity, EMA/ATR, stop inputs,
  trigger basis, W1-W5 evidence, and same-candle representation.

## Final corrective receipt — 2026-08-26

- Files changed: `backend/domain/strategy.py`,
  `backend/strategies/contract.py`,
  `backend/strategies/ema_sweep_confirmation_break.py`, and
  `backend/tests/strategies/test_ema_sweep_confirmation_break.py`.
- Compatibility: generic `StrategyDefinition` and untouched legacy
  `ema_sweep_engulfing.py` / `ema_sweep_engulfing_v2.py` retain schema 1 and
  their original state machine; only the authoritative confirmation-break
  registration advertises schema 2. Public evaluation rejects schema-1 state
  for that registration.
- Checks: targeted pytest (95 passed), `python -m compileall -q backend`,
  targeted Ruff, and `git diff --check` passed. Full `ruff check backend`
  remains blocked by pre-existing findings outside this task.
