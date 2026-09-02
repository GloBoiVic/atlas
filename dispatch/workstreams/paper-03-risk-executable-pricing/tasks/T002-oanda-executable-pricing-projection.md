# T002 — OANDA executable-pricing projection

- **Status:** `COMPLETE`
- **Role:** `BUILD`
- **Workstream:** `paper-03-risk-executable-pricing`
- **Branch:** `solo/paper-03-risk-executable-pricing`
- **Dependency:** T001 may be complete before composition consumes the new Risk seam; projection itself must remain independent of Risk.

## Objective

Implement the pure provider-specific executable-pricing projection, strongly in
`backend/integrations/oanda/pricing_projection.py`, plus public exports and focused
tests as needed.

## Required behavior

- Accept normalized `OandaPracticeEurUsdPricingObservation` and `Direction`; perform
  no I/O.
- LONG inspects asks only; SHORT inspects bids only.
- `tradeable == False`, empty required side, or no positive-liquidity required-side
  bucket yields no executable candidates.
- Preserve all relevant required-side bucket facts as evidence; retain zero-liquidity
  buckets as evidence but exclude them from executable candidates.
- Produce deterministic candidate facts of `price` and `available_quantity` without
  aggregation, Risk sizing, final entry selection, array-order assumptions, midpoint,
  opposite-side, closeout, or historical-candle fallback.

## Completion receipt

Implemented the pure OANDA required-side executable-pricing projection with immutable
candidate and per-bucket evidence contracts. The projection retains every required-side
bucket, excludes zero-liquidity and non-tradeable buckets from candidates, makes no
liquidity aggregation or final-price selection, and canonicalizes candidate/evidence
ordering independently of provider array order.

### Changed files

- `backend/integrations/oanda/pricing_projection.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_pricing_projection.py`

### Checks

- `uv run pytest backend/tests/integrations/test_oanda_pricing_projection.py backend/tests/integrations/test_oanda_pricing.py` — 76 passed
- `uv run pytest backend/tests/integrations/test_oanda_pricing_projection.py backend/tests/integrations/test_oanda_pricing.py backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — 113 passed
- `uv run ruff format --check backend/integrations/oanda/pricing_projection.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_pricing_projection.py` — passed
- `uv run ruff check backend/integrations/oanda/pricing_projection.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_pricing_projection.py` — passed
- `uv run pyright backend/integrations/oanda/pricing_projection.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_pricing_projection.py` — passed
- `git diff --check` — passed

### Concerns

- None. No Risk sizing, I/O, broker mutation, persistence, or historical Experiment
  methodology was changed.
