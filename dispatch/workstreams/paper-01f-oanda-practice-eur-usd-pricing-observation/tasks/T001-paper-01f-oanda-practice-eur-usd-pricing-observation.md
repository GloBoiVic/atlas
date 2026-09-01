# T001 — PAPER 01F OANDA Practice EUR/USD Pricing Observation

## Task state

- **Task:** `T001`
- **Status:** `DONE`
- **Workstream:** `paper-01f-oanda-practice-eur-usd-pricing-observation`
- **Role:** `BUILD`
- **Approval:** approved by developer; GIT START complete

## Assignment

Implement only the approved PAPER 01F plan. Add the bounded provider-specific OANDA Practice EUR/USD pricing reader and immutable normalized pricing observation. Bind the explicitly configured Practice account through the existing `/summary` flow first, then perform exactly one independent `/v3/accounts/{accountID}/pricing` GET through the frozen requester seam with `params={"instruments": "EUR_USD"}`. Require exactly one `EUR_USD` ClientPrice and retain only the validated account identity, provider instrument, UTC price timestamp, exact tradeable bool, and ordered immutable bid/ask price-liquidity buckets.

## Owned files

- `backend/integrations/oanda/pricing.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_pricing.py`
- this task receipt

## Required evidence

- exact `/summary` then `/pricing` settings-helper sequence and exact query parameters;
- reuse of the frozen requester and existing string `Decimal` primitive without shared-seam changes;
- frozen/slotted provider-only contracts with validated account identity;
- exact one-item EUR/USD cardinality and fail-closed malformed response behavior;
- UTC timestamp normalization, exact bool tradeability, valid empty sides, local finite nonnegative JSON-numeric liquidity normalization rejecting bool, positive finite bucket prices, and exact provider bucket order preservation;
- ignored malformed top-level/unretained fields and closeout prices do not invalidate a valid retained observation;
- no `ExecutableQuote`, top-of-book/spread/mid/VWAP/depth interpretation, persistence, polling, streaming, Risk/runtime/execution/reconciliation/API/UI, broker mutation, PAPER activation, or PAPER 01G/later work;
- approved focused tests and targeted quality checks.

## Explicit boundaries

Do not modify `backend/integrations/oanda/request.py`, `primitives.py`, `account.py`, `trades.py`, `positions.py`, `orders.py`, or `source.py`; persistence, historical market-data conversion, Risk, runtime, execution, reconciliation, API/UI, broker mutation, PAPER activation, and generalized broker infrastructure are out of scope. If the frozen requester/primitives or any out-of-scope area must change, mark this task `BLOCKED` and return the concrete reason for re-scoping.

## Worker Evidence

- Implemented the provider-specific immutable pricing contract and reader in
  `backend/integrations/oanda/pricing.py`.
- Exported the pricing contract, reader, normalization error, and settings-facing
  helper from `backend/integrations/oanda/__init__.py`.
- Added focused pricing tests covering request order/query, cardinality, retained
  field normalization, ignored fields, and fail-closed malformed responses.
- Focused tests: `199 passed` across pricing, account, requester, and primitive
  integration tests.
- Quality checks passed: targeted Ruff format/check, targeted Pyright, and
  `git diff --check`.
