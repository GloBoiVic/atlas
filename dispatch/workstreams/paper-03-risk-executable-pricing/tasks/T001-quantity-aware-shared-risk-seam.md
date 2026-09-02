# T001 — Quantity-aware shared Risk seam

- **Status:** `COMPLETE`
- **Role:** `BUILD`
- **Workstream:** `paper-03-risk-executable-pricing`
- **Branch:** `solo/paper-03-risk-executable-pricing`

## Objective

Implement only the approved provider-neutral quantity-aware Risk extension in
`backend/risk/service.py` and its public exports/tests. Preserve the existing
`ExecutableQuote(bid, ask)` and `evaluate_pre_submission(..., quote=...)`
historical API and semantics.

## Required behavior

- Add an immutable `ExecutablePrice(price, max_quantity)` contract.
- Add a separate quantity-aware PRE_SUBMISSION entry point.
- Route both PRE_SUBMISSION paths through one shared financial-sizing implementation:
  common financial preconditions, entry/stop geometry, risk budget, loss per unit,
  floor whole-unit quantity, actual risk, and target resolution.
- Add only `INVALID_EXECUTABLE_PRICE`, `INVALID_EXECUTABLE_CAPACITY`, and
  `INSUFFICIENT_EXECUTABLE_CAPACITY` with the approved finite/non-positive/negative/
  zero-capacity semantics.
- Capacity rejection contains no approved quantity or target.
- Keep Risk provider-neutral: no OANDA, PriceBucket, tradeable, bid/ask arrays, or
  price timestamps.

## Boundaries and evidence

Do not change Experiment methodology, historical execution contracts, persistence,
migrations, runtime, API, or UI. Preserve existing Risk and Experiment tests and add
focused coverage for valid long/short sizing, invalid price/capacity, zero and exact
capacity, insufficient capacity, whole-unit quantity, actual-risk budget, target,
and rejection fields.

## Completion receipt

Implemented the provider-neutral quantity-aware PRE_SUBMISSION seam while preserving
the historical `ExecutableQuote` API and sizing behavior.

### Changed files

- `backend/risk/service.py`
- `backend/risk/__init__.py`
- `backend/tests/risk/test_service.py`

### Checks

- `uv run pytest backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — 37 passed
- `uv run ruff format --check backend/risk/service.py backend/risk/__init__.py backend/tests/risk/test_service.py` — passed
- `uv run ruff check backend/risk/service.py backend/risk/__init__.py backend/tests/risk/test_service.py` — passed
- `uv run pyright backend/risk/service.py backend/risk/__init__.py backend/tests/risk/test_service.py` — passed
- `git diff --check` — passed

### Concerns

- None. No provider integration, I/O, persistence, broker mutation, or historical
  Experiment methodology was changed.
