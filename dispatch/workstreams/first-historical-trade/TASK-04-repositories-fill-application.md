# TASK-04 — Repositories and atomic Fill application

Status: DONE

## Changes

- Added focused, caller-owned-`Session` `ExperimentRepository` for Experiment
  creation/read, simulated-account and initial FLAT Position projections, and
  terminal completion.
- Added focused `TradingRepository` for immutable TradeIntent/RiskDecision
  facts, Order creation/read, and Fill reads. Order creation is flush-only and
  cannot modify financial exposure.
- Added `apply_fill` in `backend/execution/fill_application.py` as the sole
  Fill-driven state boundary. A savepoint atomically persists the Fill and
  updates Order, Position, Trade, and SimulatedAccount projections; failures
  roll back the whole boundary while leaving the caller-owned Session usable.
- Enforced Phase 3 full sequence-one Fills, exact Decimal financial inputs,
  zero fees, direction/exposure consistency, and long/short Decimal P&L.
  Entry Fills open Position/Trade state; supported exit Fills close them and
  realize account P&L.
- Added PostgreSQL integration tests proving entry exposure changes only after
  Fill application and failed Fill application rolls back Fill and Order
  projection changes.

## Validation receipts

- `pytest -q backend/tests/integration/test_fill_application.py` — **2 passed**
  against the configured PostgreSQL test database.
- `ruff check backend/persistence/experiment_repository.py backend/persistence/trading_repository.py backend/execution/fill_application.py backend/tests/integration/test_fill_application.py` — **passed**.
- `pyright backend/persistence/experiment_repository.py backend/persistence/trading_repository.py backend/execution/fill_application.py backend/tests/integration/test_fill_application.py` — **0 errors, 0 warnings, 0 informations**.

## Scope exclusions

No Risk policy or sizing, simulated execution adapter, clock, runner, fixtures,
API/UI, real broker behavior, Phase 4 execution realism, additional tables, or
forbidden tables were added. No Git-changing commands were run. Existing
dispatch artifacts were not modified.

## Conflicts or blockers

None. The existing Phase 3 schema requires the caller to seed an Experiment
account and one Position before applying Fills; the repository provides that
projection initialization explicitly. The boundary is flush-only by design;
the caller remains responsible for the outer commit/rollback.
