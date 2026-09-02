# T003 — PAPER Risk composition

- **Status:** `COMPLETE`
- **Role:** `BUILD`
- **Workstream:** `paper-03-risk-executable-pricing`
- **Branch:** `solo/paper-03-risk-executable-pricing`
- **Dependency:** T001 and T002

## Objective

Implement the pure/read-only PAPER application seam, strongly in
`backend/paper/risk_evaluation.py`, plus public exports and focused tests as needed.

## Required behavior

Implement the approved `evaluate_paper_risk(...) -> PaperRiskEvaluation` composition:

- NO_ACTION is a typed no-op with no observation validation, Risk, or pricing.
- CLOSE_POSITION/UPDATE_PROTECTION return UNSUPPORTED_ACTION.
- PRICE_TRIGGERED openings return DEFERRED_ENTRY_POLICY without intent, Risk, pricing,
  or pending-state mutation.
- IMMEDIATE openings compare exact financial identity across all four observations,
  enforce summary/inventory counts, then `pending_order_count == 0` before reusing the
  existing account and EUR/USD exposure projections.
- Map openings to the existing provider-neutral TradeIntent and invoke PRE_FLIGHT once.
- Require pricing time at or after the Strategy decision; project required-side OANDA
  candidates and evaluate every positive-liquidity candidate through quantity-aware Risk
  at its own price/capacity.
- Select highest approved ask for LONG or lowest approved bid for SHORT; equal price
  selects smallest capacity, independently of source order.
- Return the frozen outcome vocabulary and retain deterministic candidate/provenance
  evidence, including transaction IDs as labels only.
- APPROVED alone carries approved PRE_SUBMISSION and proves positive integral quantity,
  budget-safe actual risk, exact selected entry price, and quantity no greater than
  selected capacity. Capacity-only failure is PRICING_REJECTED; generic failure is
  PRE_SUBMISSION_REJECTED with the approved adverse representative.

## Boundaries and evidence

No Settings, HTTP, database Session/repository, broker mutation, persistence,
accounting, runtime, API/UI, order/fill/protection, trigger polling, or generic broker
framework. Do not construct Atlas financial Position or duplicate 01G/01H projection
semantics.

## Completion receipt

Implemented the pure/read-only PAPER Risk composition for supported IMMEDIATE
openings. The composition now preserves the no-op/deferred/unsupported action
boundaries, checks identity/count/pending-order eligibility, reuses the existing
account and exposure projections, invokes PRE_FLIGHT once, evaluates every finite
required-side candidate through quantity-aware Risk, and selects the conservative
capacity-supported candidate with immutable provenance and candidate evidence.

### Changed files

- `backend/paper/risk_evaluation.py`
- `backend/paper/__init__.py`
- `backend/tests/paper/test_risk_evaluation.py`

### Checks

- `uv run pytest backend/tests/risk/test_service.py backend/tests/integrations/test_oanda_pricing.py backend/tests/integrations/test_oanda_risk_projection.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/integrations/test_oanda_pricing_projection.py backend/tests/paper/test_strategy_evaluation.py backend/tests/paper/test_risk_evaluation.py backend/tests/experiments/test_runner_diagnostics.py` — 173 passed
- `uv run pytest -m "not integration and not external"` — 860 passed, 4 skipped
- `uv run ruff format --check backend/paper/risk_evaluation.py backend/paper/__init__.py backend/tests/paper/test_risk_evaluation.py` — passed
- `uv run ruff check backend/paper/risk_evaluation.py backend/paper/__init__.py backend/tests/paper/test_risk_evaluation.py` — passed
- `uv run pyright backend/paper/risk_evaluation.py backend/paper/__init__.py backend/tests/paper/test_risk_evaluation.py` — passed
- `git diff --check` — passed

### Concerns

- None. The composition performs no provider I/O, broker mutation, persistence,
  accounting, runtime activation, or trigger polling.
