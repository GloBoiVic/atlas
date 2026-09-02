# T001 — Read-only execution account/instrument capability

- **Status:** DONE
- **Role:** BUILD
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Depends on:** none

## Assignment

Implement the frozen read-only prerequisites for PAPER 04: exact configured-account
AccountProperties lookup with non-MT4 proof, one coherent full Account Details
execution snapshot, ordinary-stop capability validation, and exact EUR/USD
execution metadata/precision validation. Reuse existing 01B–01E normalization
semantics without changing their meaning. Add deterministic focused tests using
fixtures/fakes only; do not perform broker mutation.

## Acceptance

- Account properties are located exactly once and MT4/absent/duplicate/malformed cases fail closed.
- Summary, Trades, Positions, pending Orders and GSLO mode come from one Account Details response with coherent counts/frontier.
- Only `DISABLED` and `ALLOWED` GSLO modes pass; `REQUIRED` is rejected before mutation.
- Exactly EUR/USD instrument capability is observed and exact price/unit representability and quantity bounds are validated without rounding.
- No persistence, runtime, historical execution, Strategy, or Risk semantic changes.

## Worker evidence

Implemented the read-only PAPER 04 prerequisites without changing Strategy, Risk,
historical execution, persistence, runtime, API/UI, or mutation behavior:

- Added exact configured-account `GET /v3/accounts` AccountProperties lookup with
  fail-closed missing, duplicate, malformed, and MT4-associated account handling.
- Added one full Account Details `GET /v3/accounts/{accountID}` normalizer that
  reuses the existing summary/Trade/Position/pending-Order semantics, verifies the
  shared transaction frontier and counts, retains GSLO/hedging facts, and exposes
  an explicit flat/pending-order gate.
- Added EUR/USD instrument capability read through the filtered instruments endpoint,
  enforcing observed `displayPrecision == 5`, `tradeUnitsPrecision == 0`, positive
  bounds, and exact non-rounding price/quantity serialization.
- Added deterministic `httpx.MockTransport` focused tests; all requests are GET-only.

## Checks

- `uv run pytest backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_orders.py backend/tests/integrations/test_oanda_trades.py` — **225 passed**.
- Focused `ruff format --check`, `ruff check`, `pyright`, and `git diff --check` — **passed**.
- No real OANDA requests, credentials, or broker mutations performed.

## Concerns

- The broader non-integration suite exceeded the available 5-minute command window;
  the focused T001 regression suite and changed-file static checks pass.
- Repository-wide existing `ruff check backend`/`pyright backend` output contains
  unrelated baseline findings outside T001.
