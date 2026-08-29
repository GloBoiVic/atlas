# Foundation Freeze 04 — Experiment Engine Simplification Architecture

Status: `FROZEN ARCHITECTURE — IMPLEMENTATION FORBIDDEN UNTIL APPROVAL`

Role: `ARCHITECT`  
Workstream: `foundation-freeze-04-experiment-engine-simplification`  
Inspected source: `/Users/vike/Desktop/atlas`, branch `main`  
Authority: `PLAN.md`, Freeze 01/02/03 approved architecture, and the relevant
Atlas architecture and feature documents.

This is a source-cleanup contract, not authorization to implement. No application
code, tests, migrations, tasks, branch changes, or Git history changes are part of
this artifact.

## 1. Frozen outcome and single authority

Atlas has exactly one authoritative executable path for a new historical
Experiment:

```text
POST /api/v1/experiments/{id}/run
  -> backend.api.experiments.run
  -> ExperimentRunService.run
  -> ExperimentRunner.run
  -> ExperimentRunner._run_v2
  -> SimulationClock + Strategy.evaluate + Risk + SimulatedExecutionAdapter
  -> Fill application -> Position/Trade/account/equity
  -> V2 result finalization -> COMPLETED
```

`ExperimentRunService` remains the durable claim/transaction boundary. The API
application composition in `backend/api/app.py` remains the production constructor
of `ExperimentRunner`. `ExperimentRunner.run` remains the only application runner
entry point and accepts only a persisted
`ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2` snapshot. A missing, malformed, or
non-V2 snapshot fails closed as `UNSUPPORTED_EXPERIMENT_MODEL`; it never selects a
legacy runner.

`_run_v2` remains the only execution loop. It consumes persisted native M15 MID
analytical members and persisted sparse M1 BID/ASK snapshot members, constructs the
`SimulationClock`, evaluates EMA Sweep Confirmation Break v2 on completed M15
frontiers, and uses the existing canonical Risk, execution, Fill, accounting, and
result seams. No second runner, fallback, adapter, or compatibility dispatcher is
permitted.

### Reachability evidence from current main

The production call graph was inspected, not inferred from names:

* `backend/api/experiments.py:550` calls `ExperimentRunService.run`.
* `backend/experiments/lifecycle.py:152-205` claims the Experiment, calls
  `self._runner.run`, requires a terminal result, and commits it atomically.
* `backend/api/app.py:50-52,81-86` constructs the runner and lifecycle and wires
  result reads.
* `backend/experiments/runner.py:441-459` dispatches only to `_run_v2`; all other
  models call `_fail`.
* `backend/experiments/runner.py:1016-1230` (`_run_phase4`) has no production
  caller. Its only source-local execution machinery is its own loop and its
  `_open_and_close` helper. Its diagnostic/comparison seams are only referenced by
  the old runner diagnostics/e2e test plumbing.
* The current `_run_v2` does not call `aggregate_m1_to_m15`; the aggregation import,
  `M15_AGGREGATION` stage, and `AggregationError` handler are attributable to the
  superseded loop, not the V2 loop.

The post-cleanup source-graph acceptance test must prove that the runner entry point
has no `_run_phase4`, `_open_and_close`, or M1-to-M15 call/import, and that no
production caller can reach a second Experiment loop. A private method may remain
callable for unit testing in Python, but only `_run_v2` is an authoritative runner
implementation and all application reachability must pass through `run`.

## 2. Exact cleanup scope

### 2.1 Remove superseded Experiment execution code

In `backend/experiments/runner.py`, remove:

* `ExperimentRunner._run_phase4` in its entirety;
* `ExperimentRunner._open_and_close`;
* `_validate_phase4_config`;
* `Phase4RunnerComparisonDiagnostic`, `RunnerComparisonDiagnosticSink`,
  `_comparison_record`, `_emit_comparison`, `_emit_terminal_comparison`, and the
  comparison-only constructor plumbing;
* `Phase4ValueErrorDiagnostic`, `ValueErrorDiagnosticSink`,
  `_VALUE_ERROR_REASONS`, `_INCOMPLETE_M1_MESSAGE`, `_diagnostic_details`, and
  `_emit_value_error_diagnostic`, because they are emitted only by `_run_phase4`;
* `NOT_COMPLETED` and any imports made dead by these removals, including the
  runner's `aggregate_m1_to_m15`/`AggregationError` dependency and its old-only
  `snapshot_repository`/`_execution_supplied` state;
* diagnostic enum members used only by the removed loop. Rename the remaining
  in-memory enum to `ExperimentDiagnosticStage` and retain only the stages used by
  `_run_v2`; this rename must not alter persisted facts.

Rename the misleading shared `_complete_phase4` to a V2-neutral
`_complete_result` (or equivalently narrow it to `_complete_v2_result`) and remove
its old optional stage callback. Keep its current canonical terminal-fact read,
metric calculation, semantic payload, result insert, and completion ordering. The
V2 call remains `_complete_v2 -> _complete_result`.

In `backend/api/app.py` and `backend/tests/e2e_app.py`, remove only the obsolete
runner-comparison sink parameter/import/wiring. Remove the `market_data=` injection
from `ExperimentResultReadService`; V1 read composition is owned by its private
snapshot-membership helper and V2 never needs a market-data service. Do not remove
lifecycle diagnostics.
In `backend/tests/experiments/test_runner_diagnostics.py`, delete/rewrite tests
whose subject is the removed Phase 4 diagnostic/comparison machinery; retain or
replace tests for V2 failure classification, result quality, sparse terminal
behavior, and source-graph exclusivity.

### 2.2 Make pending price-trigger state explicit without adding a domain entity

Replace the current `_run_v2` local tuple
`(intent_row, frame, decision)` with a private frozen, slotted structure in
`backend/experiments/runner.py`, for example:

```python
@dataclass(frozen=True, slots=True)
class _PendingPriceTrigger:
    intent: TradeIntentModel
    decision_frame: ClockFrame
    decision: StrategyDecision
```

The names may vary only if the same three immutable handoff facts are preserved.
This structure is a runner-local handoff, not persisted state and not a new Atlas
domain model. It must not own an expiry clock or a second watch counter.

The following remain authoritative and unchanged:

* `StrategyState.phase`, `watch_bars`, `trigger_price`, and
  `last_evaluated_bar_end` are the Strategy authority;
* the opening decision's `decision_time`/frontier is the lower execution boundary;
* only observations with `observation.start_time > decision_time` can trigger;
* W1–W5 are the five eligible post-confirmation execution windows;
* execution observations during W5 remain eligible; after the W5 analytical
  frontier, execution observations in the W6 window are not eligible;
* at the W6 analytical frontier, Strategy state transitions to `SEARCHING` and
  the pending proposal expires;
* missing execution observations do not consume an analytical slot, and the final
  no-trigger pending handoff is expired deterministically at the experiment end;
* raw M1 observation and source provenance are retained, and slippage is applied
  once by the existing adapter.

The authoritative V2 runner preserves the existing behavior for both supported
opening policies. `EntryPolicy.PRICE_TRIGGERED` uses the explicit pending-trigger
handoff with a direction-compatible trigger basis and positive `expiry_bars`;
`EntryPolicy.IMMEDIATE` retains its current V2 execution behavior and tests. This
cleanup does not remove or invalidate IMMEDIATE. Any future removal requires a
separate explicit contract decision and approval.

### 2.3 V1 and M1-to-M15 compatibility decision

#### Retain, but isolate, immutable V1 reads

Freeze 03 requires existing V1 snapshots and completed Experiments to remain
readable and immutable. Therefore the V1 branch in
`backend/experiments/results.py` is **not deleted**. It is isolated behind an
explicit snapshot-schema dispatch:

* `snapshot_schema == ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2` uses persisted
  native M15 analytical membership directly and never asks a market-data service
  to derive M15;
* `snapshot_schema == ATLAS_HISTORICAL_SNAPSHOT_V1` uses a named, read-only legacy
  M1-to-M15 reader against that snapshot's immutable membership;
* absent/unknown schema is `INCOMPLETE_RESULT`, never an implicit V1 fallback;
* the same explicit split applies to `price_analysis` and `_chart`.

The compatibility boundary is the private
`ExperimentResultReadService._legacy_v1_m15` helper in
`backend/experiments/results.py`. It reads the V1 snapshot's immutable membership
through `DatasetSnapshotRepository`, calls the existing
`aggregate_m1_to_m15` primitive for MID, and returns only the chart/price read
series. It may not write bars/snapshots, consult current mutable bars, create
Experiments, invoke Strategy/Risk/execution, or be called by `ExperimentRunner`,
`ExperimentConfigurationService`, or `HistoricalDataLoadCoordinator` for a new
Experiment. `price_analysis` and `_chart` are its only callers.

`ExperimentResultReadService` remains the result owner. Persisted rationale,
Risk, Fill, Trade, equity, result, and provenance facts remain the source of truth;
the compatibility reader supplies only the old chart/price series. It must not
re-detect Strategy patterns or recalculate immutable financial facts.

`aggregate_m1_to_m15` in `backend/market_data/aggregation.py` is retained only
for the isolated V1 read boundary. It is not used by the V2 execution-coverage
validator: that validator streams native M1 membership and acquisition-window
events directly. Its presence is not evidence of an authoritative V2 analytical
path; a source-graph test must prove no runner or V2 snapshot call.

#### Remove obsolete V1 acquisition/write paths

The following `MarketDataService` methods have no application caller on current
main; their only callers are the old CLI and legacy tests. They are not required
to preserve immutable reads and must be removed, with their dead private helpers
and CLI commands removed or rewritten:

* `plan_missing`, `load_missing`, `refresh_range`, `create_snapshot`;
* the old `_ingest`, `_coverage`, and `inspect_coverage` path when no remaining
  V2/legacy-read caller needs them;
* `load_v2_incremental`, which Freeze 03 explicitly says is not an authoritative
  compatibility path. V2 warm-up extension remains canonical `load_v2` over the
  extended range;
* CLI `load-missing`, `refresh`, `snapshot`, the old shared-range `coverage`, and
  `derive-m15` commands. They are undeployed compatibility/operator surfaces, not
  required to preserve immutable V1 result reads, and must not remain as
  misleading aliases to V2.

Retain `load_v2`, `create_snapshot_v2`, `_coverage_product`, independent native
product planning, acquisition-window reuse, immutable membership insertion, and
the V2 historical-load coordinator. Remove `MarketDataService.derive_m15` and its
unreferenced `current_m15` planning helper; the result service's private V1 helper
is the sole remaining M1-to-M15 read seam. Remove the public aggregation alias
`derive_m15` as well. No V1 snapshot is created by the application or CLI after
cleanup. No existing V1 row is deleted, rewritten, upgraded, or backfilled.

### 2.4 Unregistered legacy Strategy code and phase policy

Remove the unregistered execution modules and their tests:

* `backend/strategies/ema_sweep_engulfing.py`;
* `backend/strategies/ema_sweep_engulfing_v2.py`;
* tests whose sole purpose is either module, notably
  `backend/tests/strategies/test_ema_sweep_engulfing.py` and
  `backend/tests/strategies/test_ema_sweep_engulfing_v2.py`.

Evidence: neither module is imported by
`backend/strategies/production.py`; production registers only
`EmaSweepConfirmationBreakStrategy` with implementation key
`ema_sweep_confirmation_break.v2`. The old modules are only test-referenced and
are not reachable from `StrategyRegistry.implementation_for_version` in the
production registry. Removing them does not alter the current Strategy or its
source fingerprint. A persisted old StrategyVersion is not made runnable by this
cleanup; registry unavailability remains a safe failure.

Do **not** redesign `backend/strategies/ema_sweep_confirmation_break.py`.
Because the inspected source does not contain a durable Strategy-state table and
the persistence/read corpus for old state payloads is incomplete, the following
shared compatibility fields are **isolated, not guessed away in this workstream**:

* `Phase.AWAITING_CONFIRMATION`;
* `StrategyState.window_bars` and schema-1 deserialization/validation;
* `EntryPolicy.IMMEDIATE`;
* `StrategyDecision.expiry_time`/`expiry_bars` and the corresponding immutable
  `TradeIntentModel` columns/read projection;
* the `warm_up_bars` compatibility properties and the narrow fallback in
  `strategy_requirements.requirement_for_version`.

The schema-1/old-phase fields must be marked as legacy/non-authoritative in source
and covered by a test that proves no production registration or new V2 Experiment
execution uses them. `EntryPolicy.IMMEDIATE` is different: the existing V2 path is
supported, preserved, and remains covered by its current tests. The V2 runner never
uses `expiry_time` for eligibility, but existing immutable intent fields remain
readable and unchanged; no migration or column removal is authorized. Removal of
IMMEDIATE or any of these fields requires a separate explicit contract decision and
approval. This is the required narrow isolation where removal evidence is
insufficient.

The current Strategy remains exactly the registered v2 implementation with
`REFERENCE_IDENTIFIED -> ARMED`, immediate same-bar sweep/confirmation, native
M15 MID input, `PRICE_TRIGGERED` ASK/BID behavior, W1-W5 received-bar counting,
W6 expiry, and existing evidence/rationale serialization.

## 3. Ownership and non-change contract

The cleanup does not move or redesign ownership:

| Boundary | Frozen owner | Explicitly unchanged |
|---|---|---|
| Strategy methodology/state | `Strategy.evaluate`, `ema_sweep_confirmation_break.py` | EMA/ATR logic, reference/sweep/confirmation semantics, state authority, rationale/evidence |
| Risk | `backend/risk/service.py`, `_attempt_entry` | PRE_FLIGHT, PRE_SUBMISSION, sizing, stop/target validation, rejection facts |
| Execution | `SimulatedExecutionAdapter`, `_attempt_entry`/protection helpers | BID/ASK side selection, slippage, gap-through, adverse-first ambiguity, no double application |
| Accounting | `apply_fill`, Position/Trade projections, `_sample_equity` | Fill authority, P&L, executable liquidation valuation, equity sequence, end close |
| Market data | `MarketDataService` V2 path, `SimulationClock` | native M15 MID, sparse M1 BID/ASK, completion, UTC half-open ranges, no fabrication |
| Snapshot | `create_snapshot_v2`, snapshot repositories/models | immutable identity/membership, fingerprints, acquisition-window provenance, V1 rows |
| Result | `_complete_result`, `ExperimentResultReadService` | result schema, metric methodology/state, semantic fingerprint, read-only facts, V1 read boundary |
| Persistence/lifecycle | repositories, SQLAlchemy models, `ExperimentRunService` | atomic claim/commit/fallback, immutable terminal facts, no migrations |

Explicitly not changed: API lifecycle semantics, Experiment configuration schema,
Risk/simulation configuration values, OANDA adapter, PAPER/LIVE runtime, broker
behavior, deployment state, database tables/constraints/migrations, Snapshot
identity, DatasetSnapshot fingerprints, result metric formulas, UI/API result
shapes except removal of obsolete diagnostic plumbing, performance architecture,
or any new Experiment capability.

This workstream does not turn the runner into a generic engine, add a worker/queue,
introduce a second persistence model, or generalize beyond EUR/USD OANDA native
M15 MID plus sparse M1 BID/ASK.

## 4. Frozen invariants

1. **Single execution authority:** every new Experiment run reaches
   `ExperimentRunner.run -> _run_v2`; no V1 runner, M1-derived analytical runner,
   direct CLI runner, or result-reader execution path exists.
2. **Immutable inputs/results:** StrategyVersion, DatasetSnapshot, completed
   Experiment configuration, completed result, TradeIntent, RiskDecision,
   OrderEvent, Fill, completed Trade facts, and equity history are not rewritten.
   Rerun means a new Experiment.
3. **Native products:** analytical bars are provider-native OANDA M15 MID;
   execution observations are provider-native sparse M1 BID/ASK. M1 never fills a
   missing analytical M15 bar. Fully absent acquired M1 is unavailable, not a
   fabricated price; one-sided BID/ASK is invalid.
4. **Completed/no-lookahead:** Strategy sees only completed bars with
   `bar.end_time <= frontier`. A decision at 10:15 for `[10:00,10:15)` cannot use
   an M1 observation at or before 10:15 as entry data. The same analytical frontier
   is evaluated once.
5. **Strategy authority:** the current Strategy owns setup, direction, proposed
   stop, trigger, target methodology, rationale, and evidence. It does not know
   account, Risk, broker, database, or execution.
6. **Pending trigger:** the runner handoff is explicit but non-authoritative;
   Strategy state owns W1-W5 and W6. Trigger side is ASK for LONG and BID for
   SHORT. Trigger equality is eligible, gap-through open is eligible, and no
   pre-decision observation is eligible.
7. **Risk/execution/accounting:** Risk sizes from the actual adverse-slipped
   executable quote; Fill creates exposure; target is resolved from actual Fill;
   protection is applied before later equity samples; LONG liquidation uses BID and
   SHORT liquidation uses ASK.
8. **Failure safety:** invalid model/data/state, missing final executable quote,
   incomplete protection, unsupported StrategyVersion, Risk failure, or persistence
   failure cannot become a trustworthy result. No new exposure is inferred from
   unknown state.
9. **Legacy boundary:** V1 M1-to-M15 code can only read explicitly identified V1
   immutable membership. It cannot create snapshots, alter rows, run Strategies,
   or participate in V2 Experiment creation/result execution.

## 5. Valid, invalid, and boundary examples

### Valid

* A V2 Experiment has native M15 MID analytical members, sparse but complete BID+ASK
  pairs where observations exist, and successful acquisition-window records for
  fully absent open-session M1 minutes. It runs through `_run_v2` and produces the
  same canonical facts.
* A LONG confirmation at 10:15 produces a PRICE_TRIGGERED intent on ASK. The first
  post-10:15 M1 ASK equal to or above the trigger fills; raw BID/ASK source IDs and
  one adapter slippage application remain intact.
* A W5 observation reaches the trigger before W5 closes and fills. A W6 analytical
  frontier with no fill expires the proposal and cannot create an Order.
* A completed V1 Experiment is opened through the explicit V1 read boundary; its
  M1 membership is derived for chart context without any current-bar query or
  mutation.
* A zero-Trade V2 Experiment completes with its persisted equity/result projection;
  trade-dependent metrics remain their canonical unavailable states.

### Invalid

* A new Experiment points at a V1 snapshot, unknown snapshot schema, or old model:
  the runner fails closed; it does not call a legacy runner or aggregate M1 to M15.
* A production run attempts to call `_run_phase4`, `load_v2_incremental`, old
  `load_missing`, or `create_snapshot`; those executable surfaces are absent.
* A BID-only M1 minute, incomplete provider observation, unexpected closure
  observation, unacquired open-session absence, or missing terminal quote is not
  repaired or priced silently.
* A V2 result reader calls `derive_m15`, current mutable bars, or the V1 reader;
  it reads persisted native analytical membership directly.
* A result reader recomputes reference/sweep/confirmation facts from candles or
  uses current Strategy defaults/RiskProfile/DatasetSnapshot corrections.

### Boundaries

* `[10:00,10:15)` includes the native M15 bar ending at 10:15 and excludes the
  10:15-start bar. The decision frontier is 10:15; an M1 observation starting
  exactly at 10:15 is not eligible, and the first eligible minute-aligned
  observation starts strictly after 10:15 (10:16 in this example).
* Trigger exactly at the executable price is reached. A gap-through executable open
  is filled at the existing adapter-defined economic price, with no favorable
  improvement.
* W1–W5 are the five eligible post-confirmation execution windows, and execution
  observations during W5 remain eligible. After the W5 analytical frontier,
  execution observations in the W6 window are not eligible; Strategy performs its
  `SEARCHING`/reset transition at the W6 analytical frontier. A weekend or sparse
  gap does not consume a watch slot or cause wall-clock expiry.
* A V1 immutable snapshot may be read; a V1 snapshot may not be newly created.
  A V2 snapshot may be read directly; its M15 series is never rebuilt from M1.

## 6. Source cleanup versus behavior changes

### Source-only cleanup (must be behavior-neutral for valid V2 inputs)

Removing the unreachable `_run_phase4` loop and `_open_and_close`, old comparison
and value diagnostics, old runner imports/stages, dead V1 acquisition methods and
CLI commands, `load_v2_incremental`, unregistered Strategy modules/tests, and
renaming `_complete_phase4` are source/reachability cleanup. Replacing the tuple
with `_PendingPriceTrigger` is a representation cleanup. These changes must not
alter canonical valid V2 facts, result fingerprints, or failure-without-result
behavior.

### Deliberate boundary behavior

The only deliberate behavior tightening is that old V1 creation/acquisition and
unqualified M1-to-M15 execution are no longer available. Existing IMMEDIATE
behavior remains available and unchanged. V1 immutable reads remain available.
Unknown schema is rejected rather than inferred.
These changes affect obsolete/invalid paths only and must be proven with explicit
tests; they are not a Strategy, Risk, execution, accounting, market-data, snapshot,
result, or persistence redesign.

## 7. Acceptance criteria

Implementation is acceptable only when all are true:

1. The source/call graph proves one authoritative path:
   lifecycle/application entry -> `ExperimentRunner.run` -> `_run_v2`; no second
   executable Experiment loop or M1-derived V2 analytical path remains.
2. `_run_v2` retains native M15 MID and sparse M1 BID/ASK semantics and the named
   pending-trigger handoff; current valid outputs are deterministic before/after,
   excluding only generated UUIDs, operational timestamps, and removed diagnostics.
3. EMA Sweep Confirmation Break v2 golden long/short behavior is unchanged:
   reference frontier, immediate same-bar confirmation, setup facts/rationale,
   post-decision trigger, ASK/BID basis, W1-W5, W6 expiry, stop/target geometry,
   ambiguity, and end close.
4. Risk, Order, Fill, Position, Trade, accounting/equity, and result projections
   remain Fill-driven, immutable at completion, and equivalent for canonical inputs.
5. No-lookahead, completed-bar, signal-bar, sparse-observation, one-sided absence,
   and terminal-quote failure paths are proven.
6. V1 snapshots/Experiments remain read-only and immutable; no new V1 snapshot or
   Experiment is created, and V2 reads never choose the compatibility reader.
7. No database migration, schema deletion, Strategy redesign, or ownership move is
   included.

## 8. Required validation matrix

| Concern | Required evidence |
|---|---|
| One runner | AST/source graph and import scan: lifecycle/API reach only `run -> _run_v2`; `_run_phase4`, `_open_and_close`, `load_v2_incremental`, and runner aggregation are absent; direct V2 loop has one call site from `run`. |
| Before/after determinism | Replay fixed canonical V2 fixtures twice and compare ordered intents, RiskDecisions, Orders, Fills, Trades, equity points, result metrics, quality, and output fingerprint; normalize only UUID/operational timestamps and removed diagnostic records. |
| EMA v2 golden behavior | Public `Strategy.evaluate` and integration golden tests for LONG/SHORT reference, immediate same-bar sweep/confirmation, evidence, stop proposal, trigger max/min, and current registered source fingerprint. |
| Pending W1-W6 | Trigger in W1 and W5; no trigger; W5 sparse observation; W6-window observations are ineligible after the W5 frontier; Strategy reset at W6; duplicate frontier; restart-equivalent state; exact trigger and gap-through boundaries; strict `observation.start_time > decision_time`; prove no `expiry_time` or runner slot clock is consulted. |
| No lookahead | M15 end/frontier tests, M1 exactly-at-frontier rejection, first strictly-post-frontier observation, incomplete/duplicate/out-of-order bar rejection, and one evaluation per analytical frontier. |
| Native market data | V2 snapshot membership tests prove analytical rows are native M15 MID and execution rows are sparse M1 BID/ASK; no `aggregate_m1_to_m15` call from runner; missing M15 is never filled from M1. |
| Sparse execution | Fully absent acquired minute remains unavailable/non-fabricated; unacquired absence blocks; one-sided BID/ASK blocks; exact source IDs and executable sides remain in fills/equity. |
| Risk and accounting | PRE_FLIGHT then PRE_SUBMISSION, adverse slippage once, actual-fill target, stop geometry, Fill-driven Position/Trade/account updates, LONG BID and SHORT ASK valuation, costs, ambiguity, and end close match before/after. |
| Result immutability | Completed result reads use persisted result/metric states and facts; no current defaults, mutable data, or read-time writes; completed/failed rows and V1 read fixtures remain byte-stable. |
| Failure safety | Unsupported model/schema, unavailable StrategyVersion, invalid market data, missing protection/final quote, Risk rejection, and persistence failure produce sanitized failure and no trustworthy result/new exposure; existing IMMEDIATE behavior remains covered by its current tests. |
| V1 compatibility isolation | Read old immutable V1 chart/price fixtures through the explicit boundary; prove no mutation/current-bar query; prove V1 creation/write commands are unavailable and V2 never dispatches there. |
| Legacy Strategy isolation | Production registry contains only `ema_sweep_confirmation_break.v2`; old modules are absent; schema-1/old-phase compatibility, if retained, is not executable by a new V2 run, while existing IMMEDIATE behavior remains covered and unchanged. |
| Ownership regression | Existing repository, snapshot, Risk, execution, accounting, result, API lifecycle, and Freeze 03 acquisition/recovery tests pass without migrations or changes to their contracts. |

The ARCHITECT did not create or dispatch BUILD work. The reconciled PLAN contains
prepared task assignments, but explicit developer approval and GIT START are still
required before any BUILD task is opened or implementation begins.
