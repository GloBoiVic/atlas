# TASK-01 — Contract and Strategy Builder

- **Task:** Implement the approved generic Strategy proposal/evidence contract and EMA Sweep Confirmation Break strategy.
- **Agent:** Contract and Strategy builder
- **Model:** `opencode/gpt-5.6-luna`
- **Outcome:** COMPLETE

## Changed files

- `backend/domain/strategy.py` — added immutable `EntryPolicy`, structured `CandleFacts`/`SetupFacts`, proposal trigger/expiry/basis fields and validation, plus serializable armed-watch state.
- `backend/domain/__init__.py` — exported the new domain values.
- `backend/strategies/contract.py` — added generic analytical requirement metadata (instrument, resolution, price component, completed-only) and metadata-driven validation.
- `backend/strategies/ema_sweep_confirmation_break.py` — added the pure LONG/SHORT implementation with immediate-next-candle strict confirmation, exact mirrored trigger levels, ATR stop methodology, 1.7R target methodology, evidence, and five subsequent-bar armed state.
- `backend/strategies/production.py` — explicitly registered the new implementation.

## Validation receipts

- `python -m pytest backend/tests/strategies backend/tests/domain -q`
- Result: **95 passed**

## Concerns

- Runner and persistence were intentionally not changed; generic proposal watching and durable proposal persistence remain assigned to the subsequent builder.
- Legacy EMA implementations remain in source for their historical unit coverage, but are no longer production-registered or exposed as Experiment options.

## Validation blocker follow-up — attempt 1

- **Task:** Make EMA Sweep Confirmation Break the sole current production Experiment Strategy option.
- **Outcome:** COMPLETE
- **Changed:** `backend/strategies/production.py` now registers only `EmaSweepConfirmationBreakStrategy`; obsolete EMA Sweep Engulfing v1/v2 production catalog exposure was removed. Added `backend/tests/strategies/test_ema_sweep_confirmation_break.py` asserting the sole entry and clear display identity.
- **Validation receipt:** `python -m pytest backend/tests/strategies backend/tests/domain -q` → **96 passed**.
- **Note:** Legacy EMA implementations remain source-level historical coverage only; no compatibility production registration was added.

## Validation blocker follow-up — attempt 1 of 2

- **Task:** Update the obsolete production-registration expectation to the approved clean registry.
- **Outcome:** DONE
- **Changed:** `backend/tests/experiments/test_configuration.py` now requires the sole `ema_sweep_confirmation_break.v1` registration, verifies its provenance fingerprint, catalog exclusivity, and display identity.
- **Validation receipt:** `python -m pytest backend/tests/strategies backend/tests/domain backend/tests/experiments/test_configuration.py -q` → **99 passed**.

## R1 remediation — attempt 1 of 2

- **Finding addressed:** Generic `StrategyContext` no longer rejects provider, timeframe, or price component; analytical compatibility is validated against active `StrategyDefinition` metadata at the Strategy contract boundary.
- **Tests:** Updated the domain expectation to permit dimensions for contract-level validation and added a non-EMA declared-metadata contract test.
- **Validation receipt:** `python -m pytest backend/tests/strategies backend/tests/domain backend/tests/experiments/test_configuration.py -q` → **100 passed**.
- **Outcome:** DONE
