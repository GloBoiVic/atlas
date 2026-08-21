# TASK-06 — Pure simulated execution adapter

Status: DONE

## Changes

- Added immutable canonical `Order`, reduced `ExecutionObservation`, and full
  in-memory `Fill` contracts in `backend/execution/contract.py`.
- Added pure `SimulatedExecutionAdapter` in
  `backend/execution/simulated.py`. MARKET/ENTRY uses ASK for LONG and BID for
  SHORT. LIMIT/TAKE_PROFIT and STOP/STOP_LOSS use the matching liquidation
  quote, fill target-at-open and exact stop-at-open, and reject unsupported
  stop gaps or intrabar triggers with typed codes.
- Added focused tests for sides, supported fills, fail-closed behavior, and
  absence of mutation/exposure application.

## Validation receipts

- `uv run pytest -q backend/tests/execution/test_simulated.py` — **7 passed**.
- `uv run ruff check backend/execution/contract.py
  backend/execution/simulated.py backend/tests/execution/test_simulated.py` —
  **passed**.
- `uv run pyright backend/execution/contract.py backend/execution/simulated.py
  backend/tests/execution/test_simulated.py` — **0 errors, 0 warnings, 0
  informations**.

## Exclusions

No persistence, repositories, Fill application, clock, runner, Risk, schema,
API/UI, broker behavior, or Phase 4 execution realism was added. Creating an
Order and producing a pure Fill do not apply exposure.

## Conflicts or blockers

None observed. Existing persistence `OrderModel`/`FillModel` remain separate;
the adapter returns a pure domain Fill for a later caller-owned application.
