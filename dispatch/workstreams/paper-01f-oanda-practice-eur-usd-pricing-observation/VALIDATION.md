# VALIDATION — PAPER 01F OANDA Practice EUR/USD Pricing Observation

## Result

- **Role:** `VALIDATE`
- **Workstream:** `paper-01f-oanda-practice-eur-usd-pricing-observation`
- **Task:** `T001`
- **Status:** `PASS`
- **Branch:** `solo/paper-01f-oanda-practice-eur-usd-pricing-observation`

## Checks and evidence

- Focused OANDA suite passed: `199 passed` in `2.23s` across pricing, account,
  requester, and primitive tests.
- Targeted Ruff format check passed for all three changed implementation/test
  paths.
- Targeted Ruff lint check passed for all three changed implementation/test
  paths.
- Targeted Pyright passed with `0 errors, 0 warnings, 0 informations`.
- `git diff --check` passed.

## Acceptance verification

- The settings helper binds the configured Practice account through `/summary`
  before issuing an independent `/pricing` request with exactly
  `params={"instruments": "EUR_USD"}`.
- The reader requires exactly one `EUR_USD` price, fails closed for malformed
  retained fields, normalizes timestamps to UTC, requires an exact boolean
  `tradeable`, accepts empty sides, preserves bucket order, and normalizes
  finite nonnegative numeric liquidity locally.
- The provider contracts are frozen/slotted and retain only the approved
  identity, instrument, timestamp, tradeability, and bid/ask bucket facts.
- Malformed top-level and ignored provider fields, including closeout prices,
  are not interpreted or retained.
- Inspection confirms no `ExecutableQuote` import/construction, persistence,
  polling, streaming, Risk/runtime/execution integration, broker mutation, or
  historical-data conversion was introduced. Frozen requester/primitives and
  prior OANDA observation modules are unchanged.

## Concerns

None found within the approved T001 scope. No credentialed external OANDA
request, database, frontend, browser, or full-backend-suite check was run, as
directed by the plan.
