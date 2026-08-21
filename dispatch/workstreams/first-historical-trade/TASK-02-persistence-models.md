# TASK-02 — Phase 3 persistence models and protections

Status: DONE

## Changes

- Added `backend/persistence/migrations/versions/0004_phase_3_first_historical_trade.py`, chained after `0003_phase_2_market_data`.
- Extended the existing declarative base metadata in `backend/persistence/models.py` with exactly:
  `ExperimentModel`, `ExperimentAccountModel`, `TradeIntentModel`,
  `RiskDecisionModel`, `OrderModel`, `FillModel`, `PositionModel`, and
  `TradeModel`.
- Added only the eight approved Phase 3 tables: `experiments`,
  `experiment_accounts`, `trade_intents`, `risk_decisions`, `orders`, `fills`,
  `positions`, and `trades`.
- Added restrictive foreign keys to existing StrategyVersion, DatasetSnapshot,
  VenueInstrument, and Phase 3 records. No TradingAccount or other forbidden
  table was introduced.

## Model and constraint coverage

- PostgreSQL timezone-aware timestamps are used for persisted trading times and
  lifecycle times.
- Financial values use PostgreSQL NUMERIC and reject non-positive or NaN
  quantities/prices/capital where applicable.
- Experiment configuration is immutable; terminal Experiments cannot be
  changed. TradeIntent, RiskDecision, and Fill are append-only facts.
- Order facts are immutable while current status/submission timestamp remain
  mutable projections. Completed Trade rows are terminal and immutable.
- Position state/exposure consistency is enforced for the distinct financial
  Position model from TASK-01; one Position exists per Experiment and venue
  instrument.
- Unique protections cover the intent frontier, Risk phase per intent, Fill
  sequence per Order, Fill external execution identity, and Trade sequence per
  Experiment.
- Experiment status/completion consistency, valid actions/phases/outcomes/order
  states, and completed Trade fact requirements are database checks.

## Migration and test evidence

- `pytest -q backend/tests/integration/test_migrations.py` — **2 passed**.
  This proves the upgrade/downgrade/upgrade cycle, exact table set, and the
  intent-frontier, Risk-phase, Fill-sequence, and Position uniqueness indexes.
- `pytest -q` — **148 passed, 1 skipped**; one pre-existing FastAPI/httpx
  deprecation warning.
- `ruff check backend/persistence/models.py backend/persistence/migrations/versions/0004_phase_3_first_historical_trade.py backend/tests/integration/test_migrations.py` — **passed**.
- `pyright backend/persistence` — **0 errors, 0 warnings, 0 informations**.
- `python -m compileall -q backend/persistence backend/tests/integration/test_migrations.py` — **passed**.

## Compatibility conflict resolved

The repository's existing `test_migration_revision.py` requires Alembic
revision IDs to fit the default VARCHAR(32) version column. The approved
descriptive migration filename remains exactly
`0004_phase_3_first_historical_trade.py`; its bounded revision identifier is
`0004_phase_3_first_trade`, and the test's expected head was updated accordingly.

## Scope exclusions

No repositories, dataset reads, Risk service, execution adapter, clock, runner,
Strategy implementation/fixtures, API/UI, Phase 4 realism, or Git-changing
operations were performed. No `TradingAccount`, `Deployment`, `RiskProfile`,
`OrderEvent`, equity-history, or `SystemEvent` table was created.

## Conflicts or blockers

None remaining. Existing uncommitted dispatch context changes were preserved.
