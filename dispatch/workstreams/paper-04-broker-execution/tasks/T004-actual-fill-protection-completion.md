# T004 — Actual-Fill protection completion

- **Status:** DONE
- **Role:** BUILD
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Depends on:** T003

## Assignment

Complete the frozen post-Fill protection flow: full Trade-detail Stop Loss
confirmation, actual-Fill `TargetProposal.resolve`, exact target precision
validation, one dependent Take Profit PUT containing only `takeProfit`, and
final protection confirmation. Preserve validated Fill facts and distinguish
`FILLED_PROTECTED` from `FILLED_PROTECTION_INCOMPLETE`; never repair Stops or
retry uncertain target mutations. Add deterministic tests for better Fill,
target differences, precision refusal, PUT semantics, and all protection states.

## Acceptance

- Stop is confirmed before target derivation/mutation and mismatch leaves target unattempted.
- Target is derived from actual `tradeOpened.price`, not the PAPER 03 target, and is never rounded.
- Take Profit PUT is at most once, exact, GTC, client-correlated, and leaves Stop unchanged.
- Final readback proves both protections before `FILLED_PROTECTED`; all definite Fill protection failures are incomplete.
- No persistence, runtime, historical execution, Strategy, or Risk semantic changes.

## Worker evidence

Implemented the T004 post-Fill protection slice without changing Strategy/Risk
semantics, persistence, runtime, API/UI, or historical execution:

- Added full Trade-detail validation for the opened Trade and exact ordinary
  pending Stop Loss; all missing, mismatched, non-open, failed, and terminal
  Stop states remain `FILLED_PROTECTION_INCOMPLETE` with no Stop repair and no
  target attempt.
- Added actual-Fill `TargetProposal.resolve`, provider-precision exactness
  refusal with `TARGET_PRECISION_UNREPRESENTABLE`, and no rounding.
- Added the non-retrying Practice Trade dependent-order PUT with exactly one
  `takeProfit` payload, deterministic client correlation, final Trade-detail
  confirmation of unchanged Stop plus pending Take Profit, and explicit
  protected/incomplete/rejected/uncertain outcomes.
- Strengthened protection/result contracts so confirmed protection is backed by
  an order and `FILLED_PROTECTED` cannot omit either protection.
- Added deterministic fixed-UUID `httpx.MockTransport` and fake-reader tests
  covering better Fill target differences, Stop gating, precision refusal,
  exact PUT semantics, target rejection/transport uncertainty, final
  confirmation, and no retry.

## Checks

- `uv run pytest backend/tests/integrations backend/tests/paper backend/tests/risk/test_service.py backend/tests/execution -q` — **547 passed, 1 skipped**.
- `uv run pytest -m "not integration and not external" -q` — **912 passed, 4 skipped, 88 deselected**; existing warnings only.
- Focused `ruff format --check`, `ruff check`, `pyright`, and `git diff --check` — **passed** for the T004 implementation/test files.
- No real OANDA requests, credentials, broker mutations, persistence, runtime activation, or Git history changes performed.

## Concerns

- Inherited T001–T003 working-tree changes and SoloFlow operational changes
  were preserved and not edited by T004.
- T005 remains responsible for the complete capital-capable PAPER composition;
  this task adds no public activation path.
