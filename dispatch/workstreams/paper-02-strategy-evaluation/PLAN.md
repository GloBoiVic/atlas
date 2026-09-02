# PLAN — PAPER 02 Strategy Evaluation

## Workstream state

- **Workstream:** `paper-02-strategy-evaluation`
- **Outcome:** Evaluate one exact persisted Atlas `StrategyVersion` against one safe current completed OANDA EUR/USD M15 analytical frontier using explicit parameters, caller-held Strategy state when continuing an existing state chain, and explicit financial-to-Strategy position translation, then return the existing `StrategyEvaluation` without Risk or execution.
- **Classification:** `Feature`. This capability is capital-incapable. It produces only existing Strategy methodology output and state. It performs no Risk decision, pricing/quantity sizing, execution, broker mutation, accounting, activation, reconciliation authority, or durable PAPER resume.
- **Base:** `main` at `7001a91` (`Close PAPER 01H workstream`).
- **Base SHA:** `7001a91fef1bfc0302b8b579d782654720375520`.
- **Branch:** `solo/paper-02-strategy-evaluation`.
- **Phase:** `READY_FOR_USER`.
- **Approval:** explicit developer implementation approval granted.
- **Architecture:** not required. PAPER Readiness 01 already establishes that Strategy methodology/evaluation is reusable while `ExperimentRunner`, `SimulationClock`, historical execution, Experiment persistence, and PAPER activation remain separate concerns.
- **Task state:** `T001 DONE`; `T002 DONE`; focused validation PASS.
- **Next action:** explicit developer merge approval; then perform GIT END without pushing or otherwise widening the approved operation.
- **Concerns:** this is intentionally a one-shot/caller-held-state capability. No durable PAPER Strategy owner/state/frontier persistence exists yet. A restored `StrategyStateEnvelope` containing an unresolved `PendingEntryHandoff` also cannot safely advance in this Strategy-only workstream because current Experiment semantics require post-decision execution observations to determine whether that handoff was triggered, consumed, expired, or cleared.

## 1. Capability boundary

The smallest coherent PAPER Strategy capability is:

```text
exact persisted StrategyVersion UUID
        +
complete explicit parameter mapping
        +
optional caller-held StrategyStateEnvelope
        +
current FinancialPositionState
        +
current completed native OANDA M15/MID analytical history
        ↓
verified local Strategy implementation
        ↓
existing evaluate_strategy(...)
        ↓
StrategyEvaluation
```

The expected application seam belongs under a new PAPER application package, strongly:

```text
backend/paper/strategy_evaluation.py
```

A likely callable boundary is equivalent to:

```python
evaluate_current_paper_strategy(
    session,
    *,
    strategy_version_id: UUID,
    parameter_values: Mapping[str, object],
    state: StrategyStateEnvelope | None,
    financial_position_state: FinancialPositionState,
    now: datetime,
) -> StrategyEvaluation
```

The exact function/class spelling may follow existing application-service conventions.

Injected dependencies should provide:

```text
StrategyRepository
StrategyRegistry
native OANDA M15 analytical source
MarketSpecification
```

The caller supplies the requested persisted version ID, full parameter values, current financial exposure state, optional prior Strategy state, and an explicit UTC `now`.

`now` is **only an acquisition cutoff**.

It must never become the Strategy decision clock.

The Strategy clock remains:

```text
selected completed M15 bar.end_time
```

Therefore every Strategy context evaluated by this capability uses:

```python
StrategyContext.evaluation_time == current_bar.end_time
```

This preserves Experiment → PAPER methodology meaning, including:

```text
decision_time
state frontier
PendingEntryHandoff.decision_frontier
analytical-bar eligibility semantics
```

The returned value is the existing:

```python
StrategyEvaluation
```

containing:

```text
StrategyDecision
next StrategyStateEnvelope
```

No PAPER-specific StrategyDecision or alternative methodology language is introduced.

### One-frontier rule

Each invocation evaluates at most one newly available analytical decision frontier.

It must not:

- silently skip unseen frontiers;
- evaluate multiple new decision frontiers in one call;
- replay the current frontier;
- call the latest bar regardless of caller state;
- silently catch up a stale restored state.

A later runtime/coordinator may invoke this capability sequentially.

That runtime is not part of PAPER 02.

## 2. Classification and capital boundary

This remains a `Feature`.

Successful completion means only:

> Atlas can execute the same verified Strategy methodology against one current completed analytical frontier.

It does **not** mean:

```text
PAPER is active
Risk approved the proposal
the account is authorized
the price is executable
quantity has been sized
an Order may be submitted
a pending trigger has executed
capital exposure may change
```

Do not call:

```text
RiskService.evaluate_pre_flight
RiskService.evaluate_pre_submission
```

Do not construct:

```text
TradeIntent
historical Order
historical Fill
Atlas financial Position
broker instruction
```

Do not mutate OANDA.

Do not add PAPER persistence or runtime activation.

If implementation requires durable PAPER lifecycle/resume authority, stop `BLOCKED` and reclassify/re-scope rather than expanding this Feature.

## 3. Verified current contracts

### 3.1 Strategy contract

Current:

```python
evaluate_strategy(
    implementation,
    context: StrategyContext,
    parameters: ValidatedParameterPayload | StrategyParameterSet,
    state: StrategyStateEnvelope,
) -> StrategyEvaluation
```

is already the shared checked Strategy entry point.

It validates:

- local Strategy registration;
- parameter shape;
- Strategy state schema;
- context instrument;
- analytical resolution;
- price component;
- completed-bar contract;
- required warm-up count when proposal exposure is allowed;
- restored state not being ahead of the evaluation clock;
- strict advancement beyond an existing state frontier;
- prohibition on opening proposals when `exposure_allowed=False`;
- prohibition on opening proposals when Strategy `PositionState` is non-flat;
- returned Strategy state type/schema;
- returned state advancing exactly to the current completed bar.

It already raises:

```python
DuplicateBarEvaluationError
```

when the current context does not advance beyond the supplied state frontier.

PAPER must use this public entry point.

Do not call:

```python
implementation.evaluate(...)
```

directly.

### 3.2 Current production methodologies

Current production definitions are:

```text
ema_sweep_confirmation_break.v2
  EUR/USD
  M15
  MID
  completed-only
  required_historical_context_bars = 100
  state_schema_version = 2
  PRICE_TRIGGERED opening methodology
```

and:

```text
candle_confirmation_break.v1
  EUR/USD
  M15
  MID
  completed-only
  required_historical_context_bars = 1
  state_schema_version = 1
  IMMEDIATE opening methodology
```

Both use the public:

```python
StrategyStateEnvelope
```

boundary.

PAPER must not expose or require the legacy EMA internal `StrategyState`.

The EMA compatibility adaptor remains responsible for translating its envelope into the frozen internal state implementation.

### 3.3 Exact persisted version selection

Current exact-version retrieval already exists:

```text
StrategyRepository.get_version(session, version_id)
        ↓
version_to_domain(...)
        ↓
StrategyVersion
```

`get_version` performs an exact ID lookup.

It is not:

```text
latest version
latest implementation
strategy catalog default
```

After loading the exact version, use:

```python
StrategyRegistry.implementation_for_version(version)
```

The registry already requires matching:

```text
strategy_key
implementation_key
source_fingerprint
```

and does not read arbitrary current source during evaluation.

Do not introduce:

- latest-version lookup;
- filesystem discovery;
- dynamic import discovery;
- fallback implementation selection;
- source-snapshot execution.

Persisted:

```text
exact_source_snapshot
source_manifest
```

remain provenance only.

They are not executable fallback code.

### 3.4 Persisted/local metadata agreement

There is no separate:

```text
StrategyMarketDataRequirement
requirement_for_version
```

contract on current `main`.

Do not invent one in this Feature.

The relevant existing sources are:

**Persisted `StrategyVersion`:**

```text
strategy_key
implementation_key
source_fingerprint
parameter_schema
primary_timeframe
required_historical_context_bars
state_schema_version
```

**Verified local `StrategyDefinition`:**

```text
strategy_key
implementation_key
parameter_schema
primary_timeframe
required_historical_context_bars
state_schema_version
required_instrument
required_resolution
required_price_component
completed_only
```

After registry provenance matching succeeds, PAPER must additionally fail closed if the persisted version metadata that participates in evaluation disagrees with the verified local definition:

```text
parameter_schema
primary_timeframe
required_historical_context_bars
state_schema_version
```

Do not silently use local defaults to override contradictory persisted metadata.

The current provider capability must also support the verified local analytical contract:

```text
Instrument.EUR_USD
Timeframe.M15
PriceComponent.MID
completed_only=True
```

No generic strategy-requirement abstraction is required.

### 3.5 Parameters

`StrategyVersion` stores the schema, not a selected PAPER parameter snapshot.

PAPER 02 therefore requires a **complete explicit parameter mapping** from the caller.

Construct:

```python
ValidatedParameterPayload.from_mapping(
    version.parameter_schema,
    parameter_values,
)
```

Do not use:

```python
ValidatedParameterPayload.with_defaults(...)
```

inside this evaluator.

Do not silently fill omitted PAPER parameters from schema defaults.

The caller may explicitly construct a full mapping from defaults before invoking the capability, but the evaluator itself requires all exact keys.

Missing keys, extra keys, invalid primitive types, invalid values, or schema disagreement fail before Strategy execution.

The resulting `ValidatedParameterPayload` then passes through the existing `evaluate_strategy` validation and Strategy-specific parser.

## 4. Current analytical data seam

### 4.1 Source to reuse

Current:

```python
OandaHistoricalBarSource.fetch_native_m15(start, end)
```

already performs the required OANDA normalization for:

```text
EUR_USD
M15
MID
smooth=false
provider complete candles only
```

It returns canonical:

```python
Bar
```

values and separately retains provider incomplete observations.

Despite the class name containing `Historical`, the native M15 method is a bounded read of provider-native completed analytical candles and is suitable for this current read-only capability.

Reuse its provider normalization.

Do not route current PAPER Strategy data through:

```text
MarketDataService.load_v2
DatasetSnapshot
DatasetSnapshotRepository
SimulationClock
M1 aggregation
historical ExecutionObservation
```

PAPER must not fabricate historical snapshot identity.

### 4.2 UTC acquisition cutoff

Require `now` to be timezone-aware UTC.

Derive:

```text
cutoff = now floored to the current UTC 15-minute boundary
```

Examples:

```text
10:17 UTC → cutoff 10:15
10:29 UTC → cutoff 10:15
10:30 UTC → cutoff 10:30
```

The candidate current analytical window is:

```text
[cutoff - 15 minutes, cutoff)
```

The currently forming candle beginning at `cutoff` is never requested.

### 4.3 Current-frontier eligibility

The candidate window must be eligible under the existing versioned EUR/USD session policy.

Use existing:

```python
eligible_m15_windows(...)
required_warmup_range(...)
```

rather than creating a new calendar implementation.

If the immediately preceding calendar M15 window contains no expected provider session data under the existing policy, there is **no current decision frontier** for this invocation.

Fail with a narrow PAPER application error/outcome.

Do not search backward through the weekend or closure and present an old Friday bar as a new Saturday decision.

This distinction is important:

```text
latest historical bar
≠
current analytical frontier
```

### 4.4 Fetch range

Fetch enough provider-native history to include:

1. the current candidate bar;
2. the persisted StrategyVersion's required historical context;
3. at least the immediately preceding eligible analytical frontier when needed to validate restored-state continuity.

Use:

```python
required_warmup_range(...)
```

to calculate eligible historical context across weekly/daily session closures.

Do not subtract:

```text
N × 15 calendar minutes
```

and assume those are N eligible bars.

### 4.5 Exact analytical set

For the requested range:

- derive the expected eligible M15 windows from the existing session policy;
- require canonical returned bars to correspond to the expected eligible windows used by the Strategy context;
- reject duplicate/conflicting frontiers;
- reject provider incomplete observations for required windows;
- reject bars outside the requested/cutoff range;
- reject unsupported instrument/provider/timeframe/component facts;
- reject insufficient required context.

Do not:

- fabricate missing bars;
- forward-fill;
- interpolate;
- substitute M1 aggregation;
- substitute a later bar;
- use a provider-incomplete candle.

The existing canonical `Bar` invariants remain authoritative.

### 4.6 Strategy clock

For every Strategy invocation:

```python
context.evaluation_time = bar.end_time
```

Never use:

```text
now
HTTP response completion time
provider request time
local processing time
```

as Strategy `evaluation_time`.

`now` determines what information may be acquired.

The completed bar frontier determines what the Strategy believes “now” means.

This is required for methodology invariance with historical Experiment evaluation.

## 5. Strategy state and frontier semantics

### 5.1 Initial invocation

The application input may use:

```python
state=None
```

to mean:

> initialize this exact verified implementation using its existing `initial_strategy_state()` contract.

Do not require callers to know implementation-specific state codecs merely to begin a state chain.

When `state is None`:

```python
initial_strategy_state(implementation)
```

is authoritative.

The initial state is then warmed through the required prior completed analytical bars in chronological order using:

```text
exposure_allowed=False
Strategy PositionState.FLAT
evaluation_time=warmup_bar.end_time
```

This mirrors the existing Experiment methodology preparation without reusing `ExperimentRunner` or `SimulationClock`.

After warm-up, evaluate exactly the selected current bar with:

```text
exposure_allowed=True
position=<translated current financial position>
evaluation_time=current_bar.end_time
```

### 5.2 Initial bootstrap with existing financial exposure

If:

```text
state is None
```

and the current financial exposure is:

```text
LONG
SHORT
```

fail closed.

Do not bootstrap historical Strategy state while pretending that current external exposure was historically FLAT or historically present.

A non-flat PAPER account requires a caller-held Strategy state chain or later reconciliation/state-adoption semantics.

Those semantics are not invented here.

Initial bootstrap is therefore permitted only when:

```text
FinancialPositionState.FLAT
```

### 5.3 Restored state

When the caller supplies a `StrategyStateEnvelope`:

- it must pass the existing state-schema validation for the exact implementation;
- `last_evaluated_bar_end` must be present;
- it must identify the immediately preceding **eligible analytical frontier** before the selected current frontier;
- it must not be older than that frontier;
- it must not equal or exceed the current frontier.

If the state is exactly at the current frontier, preserve the existing typed duplicate behavior.

If the state is behind by more than one eligible frontier, fail as not caught up.

Do not silently replay missing frontiers.

Do not silently jump over them.

A future coordinator may repeatedly invoke the evaluator one frontier at a time.

### 5.4 Historical bars for restored evaluation

Even when state is restored, the current Strategy implementation may require analytical history to recompute indicators for the current bar.

Therefore construct the current `StrategyContext.bars` from:

```text
required eligible historical context
+
selected current completed bar
```

The presence of caller-held state does not eliminate the Strategy's declared market-history requirement.

Only the selected current bar is newly evaluated.

Prior bars provide analytical context and must not advance the state again.

### 5.5 State returned by PAPER

Return the existing:

```python
StrategyEvaluation
```

with its existing:

```python
next_state
```

The next state's:

```text
last_evaluated_bar_end
```

must equal the selected current bar's `end_time`, as already enforced by `evaluate_strategy`.

Do not create a parallel PAPER state object.

## 6. Pending-entry boundary

### 6.1 Strategy may create a handoff

The EMA methodology may return a:

```python
PendingEntryHandoff
```

inside:

```python
StrategyEvaluation.next_state
```

for a `PRICE_TRIGGERED` opening proposal.

PAPER 02 must preserve that returned Strategy state exactly.

The existence of a pending handoff does **not** mean an Order was submitted or triggered.

### 6.2 PAPER 02 may not advance an unresolved handoff

Current Experiment orchestration does more than call `evaluate_strategy`.

Between analytical decision frontiers it uses M1 execution observations to determine whether a price-triggered setup:

```text
triggered
remained pending
consumed another eligibility bar
expired
was cleared after execution
```

and it advances/clears `PendingEntryHandoff` accordingly.

Those facts are not available inside PAPER 02.

Therefore, if a caller supplies a restored:

```python
StrategyStateEnvelope
```

whose:

```python
pending_entry is not None
```

PAPER 02 must fail closed before evaluating another analytical frontier.

Do not:

- call `PendingEntryHandoff.consumed_at()` blindly;
- increment `consumed_count` based only on a new M15 bar;
- assume the trigger was not reached;
- assume the trigger was reached;
- expire it;
- clear it;
- use current pricing to resolve it in this workstream.

That behavior belongs to the later PAPER pricing/execution capability.

This Feature may **produce** a pending handoff.

It may not independently **resolve or advance** one.

## 7. Exposure translation and `exposure_allowed`

### 7.1 Explicit position translation

PAPER 01H returns:

```python
FinancialPositionState
```

Strategy requires the distinct:

```python
PositionState
```

Use an explicit total mapping:

```text
FinancialPositionState.FLAT  → PositionState.FLAT
FinancialPositionState.LONG  → PositionState.LONG
FinancialPositionState.SHORT → PositionState.SHORT
```

Do not use:

```python
PositionState(financial_state.value)
```

or another implicit enum cast.

The two values have different domain meanings despite currently sharing labels.

Do not construct Atlas financial `Position`.

### 7.2 Current decision context

For the selected current frontier:

```text
exposure_allowed=True
```

means only:

> Strategy methodology is permitted to emit an opening proposal if its other Strategy-level conditions allow one.

It does not mean:

```text
PAPER activated
Risk approved
account reconciled
broker mutation authorized
capital exposure allowed
```

The existing Strategy contract still prevents opening decisions when translated Strategy position is non-flat.

### 7.3 Warm-up context

During initial historical state preparation:

```text
exposure_allowed=False
position=PositionState.FLAT
```

This mirrors the current Experiment Strategy preparation behavior.

It is not a statement about historical broker exposure.

That is why initial bootstrap is prohibited when current financial exposure is already non-flat.

## 8. Reuse versus exclusion

### Reuse

Reuse current:

```text
StrategyRepository.get_version
version_to_domain
StrategyVersion
StrategyRegistry.implementation_for_version
StrategyDefinition
ValidatedParameterPayload.from_mapping
initial_strategy_state
StrategyStateEnvelope
evaluate_strategy
StrategyEvaluation
StrategyDecision
PendingEntryHandoff as returned Strategy state
OandaHistoricalBarSource.fetch_native_m15
canonical Bar
eligible_m15_windows
required_warmup_range
OANDA_CAPABILITY.market_specification(EUR_USD)
FinancialPositionState
Strategy PositionState
```

### Keep Experiment-specific

Do not reuse:

```text
ExperimentRunner
Experiment lifecycle
SimulationClock
ClockFrame
DatasetSnapshot
DatasetSnapshot membership
historical ExecutionObservation
historical M1 execution mechanics
SimulatedExecutionAdapter
historical Order
historical Fill
apply_fill()
Experiment trading persistence
Experiment parameter snapshots as PAPER ownership
Experiment result finalization
```

### Explicitly out of scope

Do not add:

```text
Risk PRE_FLIGHT
Risk PRE_SUBMISSION
OANDA current pricing selection
price/liquidity interpretation
quantity sizing
pending trigger resolution
TradeIntent
Order creation
broker instruction
OANDA mutation
broker confirmation
PAPER accounting
PAPER trading persistence
durable PAPER Strategy state persistence
reconciliation
PAPER activation
runtime scheduler/daemon
API/UI
LIVE
```

Do not add a generic broker or generic strategy-requirement framework.

## 9. Likely post-approval task decomposition

These are proposed BUILD tasks only.

Do not create task files before approval.

### T001 — PAPER current analytical frontier

Implement the narrow current analytical read and validation seam.

Expected responsibility:

```text
UTC now
↓
current completed eligible M15 frontier
↓
required eligible historical context
↓
validated canonical EUR/USD M15 MID bars
```

Include:

- UTC cutoff;
- immediate candidate M15 window;
- session eligibility;
- warm-up range;
- native M15 read;
- complete/missing/duplicate/unexpected bar checks;
- no-lookahead;
- no stale weekend/closure frontier substitution;
- deterministic test source injection.

Do not include Strategy evaluation, Risk, persistence, or execution.

### T002 — exact Strategy evaluation composition

Implement the PAPER application operation around the T001 analytical result.

Include:

- exact persisted version ID lookup;
- domain version mapping;
- registry implementation/fingerprint verification;
- persisted/local evaluation-metadata agreement;
- exact complete parameter payload;
- `state=None` initialization;
- initial warm-up;
- restored one-frontier continuity;
- explicit financial → Strategy position mapping;
- unresolved pending-entry fail-closed rule;
- existing `evaluate_strategy`;
- existing `StrategyEvaluation` return.

Prove behavior with both current production Strategies.

If implementation evidence shows T001 and T002 are cleaner as one task, they may be combined without changing the approved capability boundary.

Do not create a third task merely to separate tests from implementation.

## 10. Acceptance criteria

1. The capability selects a persisted `StrategyVersion` by exact supplied UUID.

2. Missing exact version fails closed.

3. No latest-version or catalog-default selection is used.

4. Registry resolution requires the existing exact strategy key, implementation key, and source fingerprint match.

5. Persisted parameter schema, primary timeframe, required historical-context count, and state schema version agree with the verified local definition before evaluation.

6. No nonexistent or new `StrategyMarketDataRequirement` abstraction is introduced.

7. Caller parameter values must exactly match the persisted schema keys.

8. The evaluator does not silently materialize missing parameter defaults.

9. Persisted source snapshots remain provenance only.

10. Current analytical data comes from native OANDA EUR/USD M15 MID provider normalization.

11. No M1 → M15 aggregation is used.

12. No DatasetSnapshot or SimulationClock is used.

13. `now` must be explicit UTC and determines only the acquisition cutoff.

14. The candidate current bar is the immediately preceding eligible M15 window ending at the cutoff.

15. A closed-session candidate window produces no current frontier rather than selecting an older historical bar.

16. The currently forming M15 candle is excluded.

17. Required historical context is calculated through the existing eligible-session policy rather than calendar subtraction.

18. Missing, incomplete, duplicate, conflicting, insufficient, or out-of-contract analytical data fails closed.

19. No synthetic or forward-filled analytical bar is created.

20. Every Strategy invocation uses:

    ```python
    evaluation_time == evaluated_bar.end_time
    ```

21. `state=None` initializes through `initial_strategy_state`.

22. Initial bootstrap evaluates required prior bars chronologically with:

    ```text
    exposure_allowed=False
    PositionState.FLAT
    ```

23. Initial bootstrap is rejected when current `FinancialPositionState` is LONG or SHORT.

24. Current frontier evaluation uses the explicit translated Strategy `PositionState`.

25. Current frontier evaluation uses `exposure_allowed=True` only as a Strategy proposal guard.

26. A supplied restored state must contain a prior frontier.

27. A restored state at the current frontier preserves the existing duplicate-frontier rejection behavior.

28. A restored state older than the immediately previous eligible analytical frontier fails as not caught up.

29. PAPER 02 never silently skips unseen frontiers.

30. Required historical context remains present when evaluating a restored state.

31. `FinancialPositionState` is translated explicitly to Strategy `PositionState`; no implicit enum cast is used.

32. No Atlas financial `Position` is constructed.

33. PAPER 02 may return a Strategy state containing `PendingEntryHandoff`.

34. PAPER 02 rejects a restored state with unresolved `pending_entry` rather than guessing trigger/expiry/consumption behavior.

35. No M1 execution or pricing observation is used to resolve a pending handoff in this Feature.

36. The returned value is exactly the existing `StrategyEvaluation`.

37. The returned `next_state.last_evaluated_bar_end` equals the selected completed frontier.

38. Strategy-owned decision and handoff semantics remain unchanged.

39. Both current production Strategies are exercised by focused tests.

40. No Risk evaluation, pricing/quantity sizing, broker mutation, persistence write, runtime activation, API/UI, or LIVE capability is introduced.

## 11. Focused validation

Expected focused behavioral tests:

```bash
uv run pytest \
  backend/tests/paper/test_strategy_evaluation.py \
  backend/tests/strategies/test_contract.py \
  backend/tests/strategies/test_provenance.py \
  backend/tests/strategies/test_ema_sweep_confirmation_break.py \
  backend/tests/strategies/test_candle_confirmation_break.py \
  backend/tests/integrations/test_oanda_source.py \
  backend/tests/market_data/test_session_calendar.py
```

Use the actual existing session-calendar test filename if current repo naming differs.

Run the existing Strategy persistence integration test **only if implementation changes the persistence read seam or evidence shows it is necessary to validate the actual diff**.

Do not add a new PAPER database integration test by default.

No migration or persistence write is expected.

Run targeted changed-file gates:

```bash
uv run ruff format --check <changed backend files>
uv run ruff check <changed backend files>
uv run pyright <changed backend files>
git diff --check
```

Do not run by default:

```text
full backend suite
full database suite
credentialed external OANDA checks
frontend
browser
runtime
migrations
```

Broaden validation only if the actual diff demonstrates broader blast radius.

## 12. Approval gate

This is the complete pre-approval Feature artifact.

Current lifecycle:

```text
PLAN
→ PLAN_PENDING_APPROVAL
```

Before explicit developer approval, do not:

```text
GIT START
create tasks/
create T001
dispatch BUILD
modify application code
modify tests
add persistence
add migrations
```

After explicit approval:

```text
GIT START
→ verify solo/paper-02-strategy-evaluation
→ create approved task files
→ BUILD
→ focused VALIDATE
→ independent REVIEW
→ remediation if required
→ merge approval
```
