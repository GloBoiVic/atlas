# TASK-01 Receipt — Requirement and V2 Foundation

## Status

Implemented the domain/market-data/persistence foundation for the approved V2
blueprint. No runner, API, or frontend code was changed.

## Changes

- Added the canonical `required_historical_context_bars` StrategyVersion and
  StrategyDefinition field, with a deprecated read-only `warm_up_bars` alias
  for older runtime callers.
- Updated StrategyVersion persistence, catalog synchronization, repository
  mapping, and migration `0012_required_historical_context` to use the
  canonical database column.
- Extended `StrategyMarketDataRequirement` with canonical context access and
  fixed sparse execution components (`BID`, `ASK`); `requirement_for_version`
  reads the new field and only falls back at the legacy boundary.
- Threaded the requirement through V2 historical-load planning and coverage
  configuration rather than reading the persisted warm-up field directly.
- Added focused requirement contract tests.

## Verification

- `ruff check ...` (all changed Python files): **passed**.
- `pytest -q backend/tests/domain/test_strategy_requirements.py backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/strategies/test_ema_sweep_engulfing_v2.py backend/tests/experiments/test_configuration.py`: **18 passed**.
- Integration tests were attempted but blocked because
  `ATLAS_TEST_DATABASE_URL` is not set; no environment files were read or
  modified.

## Files changed

- `backend/domain/strategy.py`
- `backend/domain/strategy_requirements.py`
- `backend/experiments/configuration.py`
- `backend/market_data/historical_load.py`
- `backend/persistence/models.py`
- `backend/persistence/strategy_catalog.py`
- `backend/persistence/strategy_repository.py`
- `backend/persistence/migrations/versions/0012_required_historical_context.py`
- `backend/strategies/contract.py`
- `backend/strategies/ema_sweep_engulfing.py`
- `backend/strategies/ema_sweep_engulfing_v2.py`
- `backend/tests/domain/test_strategy_requirements.py`

## Notes / handoff

The compatibility alias remains intentionally non-persistent so later V2
runner/API cleanup can remove legacy reads without translating stored V1 rows.
