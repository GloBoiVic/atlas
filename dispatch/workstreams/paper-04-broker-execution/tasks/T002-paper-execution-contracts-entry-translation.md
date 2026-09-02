# T002 — PAPER execution contracts + entry translation

- **Status:** DONE
- **Role:** BUILD
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Depends on:** T001

## Assignment

Implement the frozen provider-neutral PAPER execution instruction/refusal/result
contracts needed for entry and the OANDA Market Order translation. Preserve one
attempt identity and deterministic correlation IDs. Translate only to EUR/USD
MARKET/FOK/OPEN_ONLY with exact signed quantity, exact Risk `priceBound`, and
exact ordinary `stopLossOnFill` GTC; never attach `takeProfitOnFill`, round, or
reuse historical Order/Fill contracts. Add deterministic payload/contract tests.

## Acceptance

- Instruction contains approved Atlas facts only and enforces exact fresh PRE_SUBMISSION handoff invariants.
- Signed units are positive for LONG and negative for SHORT only at provider translation.
- Payload contains the exact frozen entry fields and no forbidden fields.
- Correlation IDs derive once from the attempt and remain stable.
- No persistence, runtime, historical execution, Strategy, or Risk semantic changes.

## Worker evidence

Implemented the frozen T002 slice without changing Strategy, Risk, historical
execution, persistence, runtime, API/UI, or broker mutation behavior:

- Added immutable provider-neutral PAPER execution identity, provenance,
  instruction, refusal, correlation, outcome, result, Fill, protection, and
  bounded transaction-evidence contracts.
- Enforced exact approved PRE_FLIGHT/PRE_SUBMISSION handoff facts, immediate
  EUR/USD opening scope, timezone/provenance coherence, and stable UUID-derived
  client IDs.
- Added a pure OANDA Practice entry translator for MARKET/FOK/OPEN_ONLY with
  exact signed whole-unit quantity, exact `priceBound`, exact ordinary GTC
  `stopLossOnFill`, client correlation, and no `takeProfitOnFill`.
- Provider precision/bounds are delegated to the observed T001 execution
  instrument; no broker-bound value is rounded and translation performs no I/O.
- Added deterministic public-seam tests for contract immutability/handoff,
  refusal bounds, LONG/SHORT payloads, stable correlation, forbidden target
  omission, and exactness rejection.

## Checks

- `uv run pytest backend/tests/paper backend/tests/risk/test_service.py backend/tests/execution backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_execution_translation.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/integrations/test_oanda_orders.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_primitives.py backend/tests/integrations/test_oanda_pricing.py backend/tests/integrations/test_oanda_pricing_projection.py backend/tests/integrations/test_oanda_request.py backend/tests/integrations/test_oanda_source.py backend/tests/integrations/test_oanda_trades.py` — **517 passed**.
- Focused `ruff format --check`, `ruff check`, `pyright`, and `git diff --check` — **passed**.
- No real OANDA requests, credentials, mutations, persistence, or runtime activation performed.

## Concerns

- Existing T001 working-tree changes and SoloFlow operational changes were
  preserved and not edited by this task.
- T003 remains responsible for non-retrying mutation transport and entry
  response normalization; T004/T005 remain responsible for protection and
  composition.
