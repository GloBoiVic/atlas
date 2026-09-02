# T002 — exact Strategy evaluation composition

## Assignment

- **Workstream:** `paper-02-strategy-evaluation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/paper-02-strategy-evaluation`
- **Base SHA:** `7001a91fef1bfc0302b8b579d782654720375520`
- **Depends on:** T001
- **Owned application area:** `backend/paper/strategy_evaluation.py` and focused composition tests
- **Owned artifact:** this task file; update it with the BUILD receipt when dispatched and complete

## Objective

Implement the approved PAPER application boundary, strongly under:

```text
backend/paper/strategy_evaluation.py
```

Compose T001's current analytical data with one exact persisted StrategyVersion, explicit parameters, caller-held Strategy state, and translated financial exposure. Return exactly the existing `StrategyEvaluation` through `evaluate_strategy(...)`.

Do not re-plan the approved capability and do not modify existing Strategy methodology.

## Exact version resolution

Use this exact path:

```text
StrategyRepository.get_version
→ version_to_domain
→ StrategyRegistry.implementation_for_version
```

Requirements:

- select by the caller's persisted `StrategyVersion` UUID;
- never select a latest version;
- never use catalog defaults;
- never execute persisted source snapshots;
- preserve registry strategy-key, implementation-key, and source-fingerprint verification;
- after provenance resolution, explicitly require agreement for `parameter_schema`, `primary_timeframe`, `required_historical_context_bars`, and `state_schema_version`;
- do not create a new `StrategyMarketDataRequirement` abstraction.

Missing versions, unavailable implementations, source/provenance mismatch, or persisted/local metadata mismatch fail closed before Strategy execution.

## Parameters

Require the caller's complete explicit parameter mapping and construct it with:

```python
ValidatedParameterPayload.from_mapping(...)
```

Do not call `ValidatedParameterPayload.with_defaults(...)` inside PAPER evaluation. Missing, extra, or invalid values fail closed before implementation execution. Do not source parameters from an Experiment or implicitly select defaults.

## Strategy clock invariant

`now` is acquisition cutoff only. For every Strategy call:

```text
StrategyContext.evaluation_time == evaluated_bar.end_time
```

This applies to every warm-up evaluation and the current decision evaluation. Never use wall-clock `now`, provider request time, HTTP completion time, or local processing time as Strategy evaluation time.

## Initial state

Allow `state=None` and initialize via:

```python
initial_strategy_state(implementation)
```

For initial bootstrap:

- require translated current financial exposure to be `PositionState.FLAT`;
- fail closed for current LONG or SHORT exposure;
- evaluate the required historical prefix chronologically;
- use `exposure_allowed=False` and `PositionState.FLAT` during every warm-up call;
- evaluate exactly the selected current frontier with `exposure_allowed=True`;
- return the final existing `StrategyEvaluation` and its returned `StrategyStateEnvelope`.

Do not invent historical Strategy state for an already-exposed account.

## Restored state

For caller-supplied state:

- validate it against the exact resolved implementation and state schema;
- require a prior `last_evaluated_bar_end`;
- require that frontier to be the immediately preceding eligible analytical frontier;
- if it equals the current frontier, preserve the existing `DuplicateBarEvaluationError` behavior;
- if it is older than the immediately preceding frontier, fail as not caught up;
- do not re-evaluate historical bars to advance restored state;
- still provide the Strategy's required analytical history in each current `StrategyContext.bars`.

If restored `state.pending_entry is not None`, fail closed before evaluating any next analytical frontier. PAPER 02 does not own execution observations and must not call `consumed_at()` blindly, advance consumed count, expire or clear the handoff, assume trigger success/failure, or use pricing to resolve it.

## Exposure translation

Implement and test an explicit total mapping:

```text
FinancialPositionState.FLAT  → PositionState.FLAT
FinancialPositionState.LONG  → PositionState.LONG
FinancialPositionState.SHORT → PositionState.SHORT
```

Do not cast by string or enum value. Do not construct Atlas financial `Position`. Consume the already projected `FinancialPositionState`; do not invoke 01H provider readers in this task.

## Strategy execution and scope

Use only:

```python
evaluate_strategy(...)
```

Do not call an implementation's `.evaluate()` directly. Return exactly the existing `StrategyEvaluation`, preserving `StrategyDecision`, `StrategyStateEnvelope`, `PendingEntryHandoff`, and `EntryPolicy` semantics without PAPER reinterpretation.

Do not add or call Risk, pricing, liquidity, sizing, TradeIntent, Order, Fill, broker instruction/mutation, persistence, reconciliation, runtime activation, API/UI, or LIVE behavior. Do not add a migration or durable Strategy/PAPER state owner.

## Focused tests

Add focused tests in the existing PAPER test area (normally `backend/tests/paper/test_strategy_evaluation.py`) covering at least:

- exact UUID resolution and no latest-version fallback;
- source fingerprint and all four persisted/local metadata mismatch failures;
- complete explicit parameters and rejection of missing/extra/invalid values;
- StrategyContext evaluation time equal to each evaluated bar's `end_time` during warm-up and current evaluation;
- initial FLAT bootstrap and initial LONG/SHORT fail-closed behavior;
- restored exact-prior state success without historical replay;
- same-frontier duplicate failure;
- stale/not-caught-up restored state failure;
- restored unresolved `PendingEntryHandoff` failure before Strategy execution;
- explicit FLAT/LONG/SHORT financial-to-Strategy mapping;
- both production Strategies and preservation of returned pending-entry/entry-policy semantics;
- no Risk/execution/persistence/runtime/broker side effects.

Use deterministic fake source/repository/registry dependencies and existing Strategy fixtures. Do not require OANDA credentials or a database integration test unless the implementation actually changes the persistence read seam.

## Validation

After T001 is complete, run the focused composition and existing contract/provenance/production Strategy tests plus format, lint, type, and diff checks over changed files. The approved PLAN supplies the final focused suite.

## Completion receipt

When dispatched, change **Status** to `READY`. On completion, update this file with:

- **Status:** `DONE` or `BLOCKED`;
- changed files;
- concise implementation summary;
- focused validation commands and results;
- remaining concerns, if any.

If the required behavior would need changing Strategy meaning, Risk, historical execution, persistence ownership, runtime authority, or broker mutation, stop `BLOCKED` and report the exact re-scope instead of widening the task.

## BUILD receipt

- **Status:** `DONE`
- **Changed files:**
  - `backend/paper/strategy_evaluation.py`
  - `backend/paper/__init__.py`
  - `backend/tests/paper/test_strategy_evaluation.py`
- **Implementation:** Added the read-only PAPER Strategy composition operation. It resolves the exact persisted version, requires registry provenance and persisted/local metadata agreement, validates complete explicit parameters, translates financial exposure explicitly, performs initial chronological warm-up or one-frontier restored-state evaluation, rejects stale/future/unresolved-pending state safely, and delegates every Strategy call through `evaluate_strategy`. It returns the existing `StrategyEvaluation` unchanged and exercises both production Strategies.
- **Focused validation:**
  - `uv run pytest backend/tests/paper/test_strategy_evaluation.py backend/tests/strategies/test_contract.py backend/tests/strategies/test_provenance.py backend/tests/strategies/test_ema_sweep_confirmation_break.py backend/tests/strategies/test_candle_confirmation_break.py backend/tests/integrations/test_oanda_source.py backend/tests/market_data/test_task3.py` — **105 passed**.
  - `uv run ruff format --check backend/paper backend/tests/paper` — passed.
  - `uv run ruff check backend/paper backend/tests/paper` — passed.
  - `uv run pyright backend/paper backend/tests/paper` — **0 errors, 0 warnings, 0 informations**.
  - `git diff --check` — passed.
- **Concerns:** None within T002. The operation remains one-shot and caller-state-held; no PAPER persistence, coordinator, Risk, pricing, execution, broker mutation, runtime, API, or UI behavior was added.
