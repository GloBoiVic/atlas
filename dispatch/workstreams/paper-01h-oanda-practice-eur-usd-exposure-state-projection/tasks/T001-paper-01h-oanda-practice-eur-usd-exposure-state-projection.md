# T001 — PAPER 01H OANDA Practice EUR/USD Exposure-State Projection

- **Workstream:** `paper-01h-oanda-practice-eur-usd-exposure-state-projection`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/paper-01h-oanda-practice-eur-usd-exposure-state-projection`

## Objective

Implement only the approved pure exposure-state projection:

```text
OandaPracticeOpenTradeInventory
                +
OandaPracticeOpenPositionInventory
                ↓
      cross-view consistency
                ↓
FinancialPositionState
```

Use the approved PLAN as the canonical contract. The strong expected implementation is:

```text
backend/integrations/oanda/exposure_projection.py
```

with:

```python
project_oanda_practice_eur_usd_exposure_state(
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
) -> FinancialPositionState
```

Add and export `OandaExposureProjectionError(OandaError)`, and export the projection
function through `backend.integrations.oanda` following existing package conventions.

## Required behavior

- Require equality only for `provider`, `environment`, `provider_account_id`, and
  `base_currency`; ignore alias differences.
- Retain only the validated Atlas instrument `EUR_USD`; any unsupported Trade or Position
  exposure fails closed with `OandaExposureProjectionError`.
- Return `FLAT` only when both inventories are empty.
- Return `LONG` only for all-positive EUR/USD Trade units whose exact signed sum equals a
  positive Position `long.units`, with `short.units == 0`.
- Return `SHORT` only for all-negative EUR/USD Trade units whose exact signed sum equals a
  negative Position `short.units`, with `long.units == 0`.
- Fail closed for missing counterpart views, opposing Trades, dual-sided Positions,
  direction mismatches, and exact unit mismatches.
- Treat `CLOSE_WHEN_TRADEABLE` as current exposure like `OPEN`.
- Ignore transaction IDs and irrelevant IDs, timestamps, prices, P/L, and average prices.
- Do not construct Atlas `Position`, derive position fields, call Risk, perform I/O, consume
  pending orders, or duplicate normalization.

## Scope

Expected changes are limited to:

```text
backend/integrations/oanda/exposure_projection.py
backend/integrations/oanda/__init__.py
backend/tests/integrations/test_oanda_exposure_projection.py
```

If implementation requires changing `FinancialPositionState`, `Position`, Risk, OANDA
normalization, persistence, execution, runtime, or any other out-of-scope seam, mark this
task `BLOCKED` rather than widening scope.

Add the required narrow projection tests from the approved PLAN, including determinism,
source immutability, ignored fields, identity rules, unsupported instruments, and the
projection-specific error type.

## Task checks

Run the focused projection tests and the required focused validation commands from the
approved PLAN/request. Complete this file with a BUILD receipt and set status to `DONE`
only when implementation and task-level checks are complete.

## Worker Evidence

Implemented the pure normalized OANDA Trade/Position cross-view projection and exported
`OandaExposureProjectionError` plus
`project_oanda_practice_eur_usd_exposure_state` through `backend.integrations.oanda`.
The focused public-interface tests cover FLAT, LONG, SHORT, counterpart and direction
fail-closed behavior, exact Decimal unit agreement, unsupported instruments, identity and
alias rules, ignored fields, transaction cursors, determinism, immutability, and the
projection-specific error type.

Checks passed:

- `uv run pytest backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/integrations/test_oanda_trades.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_risk_projection.py backend/tests/domain/test_trading.py backend/tests/risk/test_service.py` — 140 passed.
- Targeted `ruff format --check` — passed.
- Targeted `ruff check` — passed.
- Targeted `pyright` — 0 errors, 0 warnings, 0 informations.
- `git diff --check` — passed.
