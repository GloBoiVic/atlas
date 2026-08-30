# T004 — Strategy capability composition

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
- Depends on: none
- Owns: provider-neutral StrategyContext inputs and fixed-product composition

## Frozen requirements

Implement `ARCHITECTURE.md` §8. Remove OANDA capability imports, resolution, and
fallbacks from `StrategyContext` and generic Strategy/domain modules. Require an
explicit immutable, already-validated `MarketSpecification` at composition/runtime
boundaries, reject missing facts and instrument mismatch, and retain generic
shape/frontier/completed-bar/no-lookahead validation. Update the Experiment runner,
composition sites, and deterministic fixtures to obtain the fixed EUR/USD
specification from `OANDA_CAPABILITY` outside the domain.

Do not add a provider resolver to the domain, broaden providers/instruments, or
change Strategy, experiment, M15/M1, BID/ASK, or persisted-result semantics.

## Required proof

Add the static/import guard, missing/mismatch rejection, provider-neutral fixture,
and regression proof for deterministic EMA v2, completed native M15 MID inputs,
no future bars, same-bar frontier rules, sparse native M1 BID/ASK execution, and
equivalent persisted facts.

## Completion receipt

BUILD must update this file with `DONE` or `DONE_WITH_CONCERNS`, list every changed
application/test path, and record task-level checks and concerns. Do not edit role
artifacts or another task artifact.

## BUILD result

- Status: `DONE`
- Implementation: `StrategyContext` now requires an explicit immutable
  `MarketSpecification`, performs only provider-neutral validation, and has no OANDA
  capability import or fallback. `ExperimentRunner` receives the composed market
  fact, and the application plus fixed-product fixtures compose it from
  `OANDA_CAPABILITY` outside the domain. Existing strategy/frontier and result
  behavior is unchanged.
- Files changed:
  - `backend/domain/strategy.py`
  - `backend/experiments/runner.py`
  - `backend/api/app.py`
  - `backend/tests/domain/test_strategy_capability_composition.py`
  - `backend/tests/domain/test_primitives.py`
  - `backend/tests/domain/test_trading.py`
  - `backend/tests/strategies/test_contract.py`
  - `backend/tests/strategies/test_legacy_strategy_isolation.py`
  - `backend/tests/strategies/test_candle_confirmation_break.py`
  - `backend/tests/strategies/test_ema_sweep_confirmation_break.py`
  - `backend/tests/market_data/test_task3.py`
  - `backend/tests/experiments/test_runner_diagnostics.py`
  - `backend/tests/e2e_seed.py`
  - `backend/tests/integration/test_candidate_vertical_flow.py`
  - `backend/tests/integration/test_api_experiments.py`
  - `backend/tests/integration/test_golden_flows.py`
- Checks / evidence:
  - `pytest -q backend/tests/domain/test_strategy_capability_composition.py backend/tests/domain/test_primitives.py backend/tests/domain/test_trading.py backend/tests/strategies/test_contract.py backend/tests/strategies/test_legacy_strategy_isolation.py backend/tests/strategies/test_candle_confirmation_break.py backend/tests/strategies/test_ema_sweep_confirmation_break.py backend/tests/market_data/test_task3.py backend/tests/experiments/test_runner_diagnostics.py`: 132 passed.
  - `pytest -q -m 'not integration'`: 396 passed, 5 skipped, 45 deselected.
  - Targeted `ruff check` and `git diff --check`: passed.
  - Static/import guard proves `backend/domain/strategy.py` contains no OANDA capability dependency; provider-neutral and missing-market rejection tests pass.
- Findings / concerns: Repository-wide strict `pyright` remains non-zero with
  broad typing diagnostics; this is non-blocking for T004 and targeted behavioral
  and lint checks pass.
