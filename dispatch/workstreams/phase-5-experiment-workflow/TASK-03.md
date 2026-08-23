# TASK-03 — Coverage and configuration workflow

- **Task:** Implement approved blueprint task 3 only: focused StrategyVersion and DatasetSnapshot reads, immutable-membership coverage validation, fixed configuration derivation, atomic PENDING graph creation, and explicit production EMA Sweep Engulfing registration.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/experiments/configuration.py`
- `backend/persistence/strategy_repository.py`
- `backend/persistence/market_data_repository.py`
- `backend/strategies/production.py`
- `backend/tests/experiments/test_configuration.py`

## Outcome

Added `ExperimentConfigurationService` for UTC/M15-aligned coverage checks over exact DatasetSnapshot membership, including warm-up M15 derivation, session-closure handling, component gaps, snapshot venue compatibility, and registered StrategyVersion provenance availability. Invalid coverage is represented with actionable blocking reasons and create revalidates it before persistence.

Creation derives the fixed Phase 4 Risk and simulation snapshots, validates bounded financial/cost inputs and persisted Strategy parameters, then flushes exactly one PENDING Experiment, USD simulated account, and flat Position in the caller-owned transaction. Added focused option reads without mutable `is_current` membership predicates. Added explicit production registration for EMA Sweep Engulfing; filesystem access is confined to registration-time source archiving, not evaluation.

No HTTP routes, run lifecycle, result reads, frontend, worker, or Phase 4 simulation changes were added.

## Exact validation receipts

- `pytest -q backend/tests/experiments/test_configuration.py backend/tests/market_data/test_task3.py` → **12 passed**.
- `pytest -q backend/tests/strategies/test_provenance.py backend/tests/strategies/test_contract.py backend/tests/strategies/test_ema_sweep_engulfing.py` → **29 passed**.
- `ruff check backend/experiments/configuration.py backend/strategies/production.py backend/persistence/strategy_repository.py backend/persistence/market_data_repository.py backend/tests/experiments/test_configuration.py` → **All checks passed**.
- `python -m py_compile backend/experiments/configuration.py backend/strategies/production.py` → **passed**.

## Evidence scope

Receipts cover fixed configuration assumptions and bounds, explicit production registration/provenance, coverage session policy and gap behavior, aggregation warm-up behavior, and existing Strategy contract/evaluation/provenance regression tests. Database-backed create orchestration was implemented against the existing caller-owned SQLAlchemy transaction boundary; no API or lifecycle receipt was claimed because those are later tasks.

## Blocker/conflict

None. No Git mutations were performed. Existing dispatch artifacts and preceding task changes remain untouched.

## R1 remediation

Added `backend/tests/integration/test_experiment_configuration.py` with PostgreSQL-backed service coverage. The fixture seeds an immutable StrategyVersion, registered EMA implementation, complete DatasetSnapshot membership, and the caller-owned SQLAlchemy session.

- Invalid create uses an out-of-snapshot period, asserts `ConfigurationError` with `RANGE_OUTSIDE_SNAPSHOT`, and verifies no Experiment graph was persisted.
- Valid create commits through the caller-owned session and asserts exactly one `PENDING` Experiment, one USD account at the configured capital, and one flat Position.
- The two documented Minor findings were not changed; neither was required to repair the Important validation gap.

### Exact remediation validation receipts

- `pytest -q backend/tests/integration/test_experiment_configuration.py` → **2 passed** (PostgreSQL-backed invalid/valid orchestration coverage).
- `pytest -q backend/tests/integration/test_experiment_configuration.py backend/tests/experiments/test_configuration.py` → **5 passed**.
- `ruff check backend/tests/integration/test_experiment_configuration.py backend/experiments/configuration.py backend/strategies/production.py backend/persistence/strategy_repository.py backend/persistence/market_data_repository.py` → **All checks passed**.
- `python -m py_compile backend/experiments/configuration.py backend/tests/integration/test_experiment_configuration.py` → **passed**.
