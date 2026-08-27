# T007 — Live validation remediation

Status: `DONE_WITH_CONCERNS`

Resolve the fresh validation failure without broad scope:

- fix the V2 Experiment coverage `Bar` constructor argument ordering defect;
- add a regression for the corrected constructor/domain contract;
- rerun the environment-enabled full suite and real OANDA evidence, including a
  genuine repeat covered one-year path proving zero provider calls where durable local
  coverage is complete;
- reconcile the environment-sensitive configuration test so it does not assert absent
  credentials while intentionally loading the configured root `.env`.

Keep secrets out of output and artifacts. Update this receipt with exact checks and any
remaining gates.

## Implementation

- Corrected V2 execution coverage normalization to construct `Bar` with the canonical
  `instrument, timeframe, price_component, ...` contract; provider is now explicit.
- Added a focused regression covering the normalized execution-bar domain fields.
- Reconciled the settings test with the intentionally loaded root `.env`: it accepts a
  configured environment token while asserting `SecretStr` redaction, and still checks
  absent-token behavior when no environment token is present. No credential value was
  printed or persisted.

## Checks

- `ruff check` on all four changed Python files: **passed**.
- Focused configuration and OANDA source tests with root `.env` loaded: **28 passed**.
- Full backend suite with root `.env`: **349 passed, 1 skipped, 1 failed**.
  The remaining failure is the pre-existing API timestamp test's golden fixture: its
  sparse snapshot contains only selected M1 execution observations, while the test
  requests a full 60-minute execution range; the endpoint correctly returns
  `409 INCOMPLETE_EXECUTION_DATA` after the constructor defect is fixed.
- Fixture benchmark: fresh one-year **24 provider calls**, repeat covered one-year
  **0 provider calls**, **68,126 reused** bars. This is a bounded representative
  fixture, not genuine full-calendar-year provider-backed durable evidence.
- Opt-in credentialed OANDA smoke: **skipped** because the required explicit external
  smoke environment was not present. No credential values were exposed.

## Remaining gates

1. Repair or replace the API timestamp test fixture with a snapshot whose requested
   trading range has complete BID/ASK M1 membership, then rerun the full suite.
2. Establish a genuine durable local repeat over the credentialed full calendar-year
   OANDA snapshot and record zero provider calls; the available benchmark does not
   prove that gate.
