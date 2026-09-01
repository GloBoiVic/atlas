# PAPER 01D — Validation

## Status

`PASS`

Independent validation completed on `solo/paper-01d-oanda-practice-open-position-inventory`.

## Acceptance evidence

- The settings helper validates the explicitly configured account through `/summary`, then performs the independent account-specific `GET /v3/accounts/{accountID}/openPositions` with the established bearer and RFC3339 headers and no query parameters.
- The reader preserves immutable, frozen/slotted identity, inventory, Position, and PositionSide contracts; sorts by exact provider instrument; rejects exact duplicates; and permits an explicit empty tuple.
- Long and short sides remain independent, including zero sides and both-nonzero exposure. Long units are nonnegative, short units are nonpositive, exposed sides require finite positive `averagePrice`, and inactive omissions normalize to `None`.
- Provider-native instruments and finite negative/zero/positive P/L are retained without Atlas Position, Direction, Trade, Fill, Risk, accounting, reconciliation, or persistence behavior.
- Invalid response shape, fields, side signs, contradictory zero exposure, provenance, provider status, transport, and exhausted retry cases fail closed with sanitized errors. `tradeIDs` and lifetime/accounting fields remain unexposed.
- Source inspection confirms no full-account/lifetime Position, Order, Trade, transaction-history, Account Changes, or mutating endpoint is retrieved.

## Checks / evidence

| Check | Result |
| --- | --- |
| Focused OANDA regression and Position tests | `169 passed` (`test_oanda_positions.py`, account, trades, source) |
| Non-integration/non-external suite | `556 passed, 4 skipped, 88 deselected`; four existing warnings |
| Targeted Ruff format | Passed; all three changed implementation/test files already formatted |
| Targeted Ruff lint | Passed |
| Targeted Pyright | `0 errors, 0 warnings, 0 informations` |
| `git diff --check` | Passed |

## Findings / concerns

No approved-scope product, regression, or safety defect was found. No browser, database, or credentialed external-OANDA validation is applicable to this read-only, non-persistent slice.

Repository-wide Ruff and Pyright remain non-zero on unrelated baseline files (`28` Ruff findings and `2891` Pyright findings); the changed module and tests pass their targeted checks. This does not block PAPER 01D validation.
