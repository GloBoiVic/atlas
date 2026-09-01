# ARCHITECTURE — PAPER Readiness 01 Internal Trading Boundary Audit

**Workstream:** `paper-readiness-01-internal-trading-boundary-audit`
**Audit posture:** architecture/readiness only. No implementation, broker mutation, PAPER activation, LIVE activation, credential change, or Risk-policy change is authorized.

## 1. Current architecture map

### Observed architecture

Atlas currently has one completed capital-modeling execution path:

```text
OANDA historical market data
        ↓
canonical Bar / DatasetSnapshot
        ↓
ExperimentRunner + SimulationClock
        ↓
verified StrategyVersion + Strategy contract
        ↓
StrategyDecision
        ↓
RiskService
        ↓
historical execution Order
        ↓
SimulatedExecutionAdapter
        ↓
historical Fill
        ↓
apply_fill()
        ↓
Experiment-owned Position / Account / Trade
        ↓
equity / result evidence
```

The application currently composes historical ingestion and Experiment execution.

There is no equivalent PAPER mutation graph.

The completed PAPER 01A–01F work instead establishes read-only OANDA Practice observations:

```text
01A  Practice account identity
01B  Account summary
01C  open Trades
01D  open Positions
01E  pending Orders
01F  EUR/USD pricing
```

These observations deliberately stop before translating provider facts into Atlas financial authority.

### Architectural conclusion

Atlas does **not** currently contain a universal trading engine that merely needs an OANDA adapter.

It contains:

```text
reusable methodology/financial semantics
+
a mature historical Experiment implementation
+
a growing provider-native PAPER observation boundary
```

PAPER should therefore compose reusable semantics with new broker-backed mechanics rather than becoming another mode of the historical Experiment machinery.

---

## 2. Environment-independent semantics

### 2.1 StrategyVersion and methodology identity

Current Strategy versioning establishes immutable methodology identity through:

- strategy key;
- version number;
- source fingerprint;
- implementation key;
- parameter schema;
- state schema;
- exact source snapshot/manifest;
- analytical timeframe/context requirements.

The Strategy registry verifies implementation identity instead of selecting arbitrary current source.

### Decision

**REUSE AS-IS.**

The same immutable methodology identity should carry through:

```text
Experiment → PAPER → LIVE
```

Environment differences may change data source, execution mechanics, and lifecycle authority, but they must not silently change the StrategyVersion methodology.

---

### 2.2 Strategy evaluation

Current Strategy evaluation accepts explicit canonical context, parameters, and state and returns a typed evaluation/decision.

It does not:

- call OANDA;
- call Risk;
- submit Orders;
- read persistence directly;
- determine broker authority.

Current `StrategyContext` already receives `MarketSpecification` as a value rather than resolving provider capability internally.

### Decision

**REUSE AS-IS.**

PAPER must construct equivalent canonical completed analytical input and durable Strategy state rather than changing the Strategy contract to understand a broker.

---

### 2.3 Strategy decision semantics

`Direction`, `Action`, `TargetProposal`, `EntryPolicy`, `PendingEntryHandoff`, `StrategyDecision`, and rationale/evidence describe methodology output.

A Strategy decision does not create financial exposure.

### Decision

**REUSE AS-IS.**

Future environments translate the same methodology output through different mechanics.

---

### 2.4 Risk-local TradeIntent

The current Risk `TradeIntent` carries:

```text
action
direction
stop
target
```

Those are the financial proposal facts Risk presently requires.

Its current shape is not inherently Experiment-specific merely because Experiment is the existing caller.

It does not need to carry:

```text
provider ID
activation mode
reconciliation proof
frontier persistence
broker authority
```

to remain useful inside Risk.

### Decision

**REUSE AS-IS for current Risk responsibility.**

If future PAPER orchestration needs richer intent provenance, that should be represented in the orchestration/persistence layer rather than inflating Risk's financial input without evidence.

---

### 2.5 Atlas financial Position

Atlas distinguishes:

```text
Strategy PositionState
```

from:

```text
financial Position
```

The financial Position expresses:

- instrument;
- FLAT/LONG/SHORT;
- quantity;
- average entry price;
- opened-at time.

Its invariants are financial rather than historical-simulation-specific.

### Decision

**REUSE AS-IS as a domain value.**

This does not authorize direct OANDA Position → Atlas Position casting.

Projection policy remains separate.

---

## 3. Historical Experiment-specific mechanics

Several modules have generic-looking names but carry explicit historical assumptions.

They should remain historical rather than being generalized merely to satisfy PAPER.

### 3.1 SimulationClock

The Experiment clock establishes:

- completed historical analytical frontiers;
- strict no-lookahead;
- historical M1 execution availability;
- sparse observation semantics;
- exact chronological replay.

These are reproducibility mechanics.

### Decision

**KEEP EXPERIMENT-SPECIFIC.**

PAPER needs completed live analytical frontiers and restart continuity, but not a simulated historical clock.

---

### 3.2 Historical ExecutionObservation

Current `ExecutionObservation` contains historical M1 BID/ASK OHLC plus MarketBar provenance and intrabar metadata.

That shape is not an OANDA live pricing observation.

### Decision

**KEEP EXPERIMENT-SPECIFIC.**

Do not populate it from `/pricing`.

---

### 3.3 Current execution Order

Current execution `Order` supports the bounded simulated execution tuples used by historical Experiments.

It lacks broker-account identity, provider instrument identity, provider correlation, asynchronous outcome semantics, and other broker-facing concerns.

That absence is not necessarily a defect in the historical contract.

### Decision

**KEEP EXPERIMENT-SPECIFIC.**

Do not refactor it into a universal Order before mutation is needed.

A separate PAPER provider-neutral instruction contract should be earned immediately before broker mutation.

---

### 3.4 Current execution Fill

Current execution `Fill` requires historical sequence-one semantics and contains simulation-specific provenance such as MarketBar source and price-basis/slippage fields.

### Decision

**KEEP EXPERIMENT-SPECIFIC.**

A future broker-confirmed execution fact should receive a separate contract when OANDA mutation/confirmation is actually implemented.

---

### 3.5 SimulatedExecutionAdapter

The simulator models:

- historical open/close prices;
- fixed adverse slippage;
- intrabar stop/target touches;
- adverse-first ambiguity;
- deterministic fills.

These are intentional historical policies.

### Decision

**KEEP EXPERIMENT-SPECIFIC.**

PAPER must never imply that OANDA matching behaves like the simulator.

---

## 4. PAPER boundary requirements

PAPER should enter Atlas through explicit translations.

### 4.1 Provider observations remain provider-native

Current OANDA modules correctly retain bounded provider facts.

Examples:

```text
OANDA AccountSummarySnapshot
OANDA open Trade inventory
OANDA open Position inventory
OANDA pending Order inventory
OANDA EUR/USD pricing observation
```

None automatically becomes:

```text
AccountState
Position
Trade
Order
Fill
ExecutableQuote
RiskDecision
```

### Decision

Projection occurs only through explicitly approved translation seams.

---

### 4.2 Exact methodology identity

PAPER must use the exact persisted StrategyVersion and verified implementation.

It must not:

- use “latest Strategy” semantics;
- silently substitute source;
- alter parameters between Experiment and PAPER;
- change decision methodology because execution environment changed.

---

### 4.3 Completed analytical data and state continuity

Before the first actual PAPER Strategy evaluation, Atlas must establish:

- completed canonical analytical bars;
- durable decision frontier;
- state-schema continuity;
- no duplicate evaluation after restart;
- no future/incomplete analytical input.

This is a future PAPER capability slice.

It is **not** an internal mass-refactor prerequisite for account/Risk projection work.

---

### 4.4 Lifecycle authority sits outside Risk

Before PAPER invokes Risk for a capital-capable decision, orchestration must already know that the environment is allowed to proceed.

Examples of orchestration-level prerequisites may eventually include:

```text
PAPER mode explicitly activated
correct broker account bound
reconciliation current
required protection state understood
runtime permitted to create exposure
```

Risk must not receive these as a generic replacement for `experiment_status`.

The call relationship is:

```text
orchestration establishes lifecycle authority
             ↓
Risk evaluates financial risk
```

not:

```text
Risk decides whether PAPER is activated
```

---

### 4.5 Broker mutation receives approved instructions only

A future PAPER coordinator/provider mutation boundary will translate an approved Atlas instruction into an OANDA request.

Strategy and Risk must not directly call OANDA.

No mutation contract is designed in this audit.

---

### 4.6 Confirmed broker execution creates financial execution facts

An attempted or submitted Order is not automatically a Fill.

A timeout is not a Fill.

A pending Order observation is not a Fill.

Financial execution facts must come from explicit provider-confirmed evidence under the future approved broker-confirmation contract.

---

### 4.7 Reconciliation precedes safe resume

Eventually, broker-backed state must be reconciled before Atlas resumes creating exposure after restart or uncertainty.

The exact persistence/recovery algorithm is deferred.

The architecture rule is only:

> local optimistic state cannot overrule contradictory current broker state.

---

## 5. Risk findings

### 5.1 What Risk already does correctly

Current `RiskService`:

- receives facts explicitly;
- does not read persistence;
- does not call OANDA;
- does not submit Orders;
- separates pre-flight from pre-submission;
- applies financial eligibility and sizing rules;
- uses ask for LONG and bid for SHORT;
- calculates risk budget from account equity and policy;
- floors quantity to current supported whole-unit semantics;
- resolves target from actual selected entry/stop/direction.

These are strong boundaries.

---

### 5.2 Demonstrated historical leakage

The public Risk call currently requires:

```text
experiment_status
```

and may emit:

```text
EXPERIMENT_NOT_RUNNING
```

The existing caller passes Experiment lifecycle directly into reusable financial Risk logic.

That is genuine historical coupling.

A PAPER caller should not have to send:

```text
experiment_status="RUNNING"
```

and Risk should not be rewritten to accept:

```text
paper_active=True
authorized=True
reconciled=True
```

instead.

That merely renames the same responsibility leak.

### Decision

**REFACTOR BEFORE PAPER dependency.**

Remove Experiment lifecycle knowledge from reusable Risk.

ExperimentRunner must establish its own lifecycle validity before invoking Risk.

Future PAPER orchestration must do the same for PAPER.

---

### 5.3 AccountState

Current:

```text
AccountState
  base_currency
  equity
```

is a small financial input.

It does not contain provider or lifecycle authority.

That is desirable.

### Decision

**REUSE AS-IS.**

A later OANDA projection may map the already normalized provider account facts into this narrow input.

Provider provenance remains available in the source observation rather than being stuffed into Risk.

---

### 5.4 RiskConfig

The current trader-defined risk-per-trade input is environment-independent for the currently validated capability.

### Decision

**REUSE AS-IS.**

Do not broaden Risk policy in this audit.

---

### 5.5 ExecutableQuote

Current:

```text
ExecutableQuote
  bid
  ask
```

works in the deterministic historical path.

The historical runner can provide the bid/ask pair expected by the simulator.

OANDA PAPER pricing differs materially:

```text
ClientPrice
  tradeable
  time
  bids[price, liquidity...]
  asks[price, liquidity...]
```

The issue is not that Risk needs every provider field.

Those validation facts belong in an upstream pricing projection.

The unresolved issue is:

> Can Atlas establish the correct executable price for the Risk-sized quantity from OANDA's price/liquidity buckets without circular or unsafe assumptions?

Current Risk determines quantity from the selected entry price.

Provider liquidity may make the executable price quantity-dependent.

### Decision

**KEEP current ExecutableQuote Experiment-specific for now.**

Do not expand or replace it in the immediate Risk cleanup.

Before PAPER pre-submission sizing is wired, create a separate Critical pricing/quantity semantics workstream.

That workstream decides whether a new PAPER pricing contract or adjusted Risk interface is required.

---

### 5.6 Risk sizing logic

The underlying financial laws remain valuable:

```text
risk budget = equity × risk_per_trade
loss per unit = |entry - stop|
quantity = floor(risk budget / loss per unit)
```

But the current pre-submission implementation receives a historical simple bid/ask quote.

### Decision

**REFACTOR BEFORE PAPER pre-submission dependency, but not now.**

Preserve historical Risk behavior.

The immediate prerequisite is lifecycle decoupling only.

Pricing/quantity semantics are addressed just before PAPER begins actual pre-submission sizing.

---

## 6. Position findings

Atlas currently has at least three distinct meanings.

### 6.1 Strategy PositionState

This is methodology/evaluation state.

It is not a financial broker position.

### 6.2 Atlas financial Position

This is one normalized financial-position value.

It has one instrument and one economic state.

### 6.3 OANDA provider Position aggregate

OANDA preserves separate provider long and short sides for an instrument.

Both sides may exist.

That provider structure cannot be safely cast directly into the current Atlas financial Position.

OANDA open Trades provide an additional provider view and may include multiple Trade IDs and instruments.

### Decision

- Strategy `PositionState`: **REUSE AS-IS**
- Atlas financial `Position`: **REUSE AS-IS**
- direct OANDA Position → Atlas Position cast: **not authorized**

A future projection slice must define supported netting/hedging/inventory consistency semantics before constructing an Atlas broker-backed Position.

---

## 7. Execution findings

### Reusable semantic law

Across environments:

> exposure must arise from confirmed execution facts, not from Strategy intent or local Order submission.

This principle is reusable.

The existing concrete historical execution contracts are not.

### Environment split

```text
Experiment:
Strategy/Risk
   ↓
historical Order
   ↓
SimulatedExecutionAdapter
   ↓
historical Fill
```

Future PAPER:

```text
Strategy/Risk
   ↓
provider-neutral approved instruction
   ↓
OANDA mutation translation
   ↓
provider outcome
   ↓
broker-confirmed execution fact
```

The PAPER side does not yet exist.

### Decision

Do not refactor current historical Order/Fill/simulator to serve both paths.

Design the PAPER instruction/confirmation seam immediately before first broker mutation.

---

## 8. Persistence findings

### Observed ownership

Current trading persistence is structurally Experiment-owned.

Examples include:

```text
TradeIntentModel.experiment_id
OrderModel.experiment_id
PositionModel.experiment_id
TradeModel.experiment_id
ExperimentAccountModel
```

RiskDecision and Fill ownership is transitively tied to that graph.

The repository APIs likewise assume Experiment ownership.

### Decision

Current:

```text
TradingRepository
TradeIntent persistence
RiskDecision persistence
Order persistence
Fill persistence
Trade persistence
```

are all **KEEP EXPERIMENT-SPECIFIC**.

This does not imply duplicating every table later.

It means Atlas does not yet possess evidence that the historical ownership graph is the correct PAPER ownership graph.

Future shared persistence semantics may be extracted only if the concrete PAPER design demonstrates them.

### Prohibited shortcut

Do not create:

```text
fake experiment_id
```

for PAPER.

Do not preemptively create generic nullable ownership columns.

---

## 9. Fill/accounting findings

Current `apply_fill()` correctly owns historical financial transition.

It:

- validates the Fill;
- locks historical Order/Position/Account state;
- rejects invalid transitions;
- persists Fill/order events;
- opens/closes Experiment Trades;
- calculates historical P/L;
- updates Experiment financial projections;
- handles historical protection sibling behavior;
- runs atomically within the caller-owned transaction.

These are valuable proven historical invariants.

But the function also depends on:

```text
Experiment account
Experiment Position
Experiment Trade
Experiment model version
historical full-fill behavior
historical exit-reason vocabulary
MarketBar provenance
historical protection behavior
```

### Decision

**KEEP EXPERIMENT-SPECIFIC.**

Do not refactor `apply_fill()` into a universal Fill application function before PAPER mutation exists.

Immediately before durable broker-confirmed PAPER fills are introduced, design an explicit PAPER accounting/projection boundary.

That future work may reuse financial laws where proven, but it must not silently change historical Experiment accounting.

---

## 10. Runtime findings

Current `runtime/main.py`:

- loads settings;
- initializes logging;
- checks database readiness;
- logs readiness;
- waits for shutdown;
- disposes resources.

It does not:

- select PAPER/LIVE;
- evaluate Strategy;
- activate a trading mode;
- reconcile OANDA;
- submit broker mutations.

This is currently safe.

### Decision

**DEFER UNTIL BROKER MUTATION.**

Do not redesign runtime before there is a real mutation-capable lifecycle to orchestrate.

Future runtime architecture must ensure:

```text
process startup != trading activation
```

Explicit trader approval remains mandatory before PAPER or LIVE activation.

---

## 11. Dependency-direction decision

### 11.1 Which modules may know OANDA?

Allowed:

```text
backend/integrations/oanda/
future PAPER provider translation/coordinator boundary
```

Not allowed:

```text
Strategy methodology
Strategy implementations
RiskService
historical simulation core
generic financial domain values
```

---

### 11.2 Which modules may know Experiment lifecycle?

Allowed:

```text
ExperimentRunner
Experiment application/configuration/persistence
historical orchestration
```

Reusable Risk must not.

PAPER must not.

---

### 11.3 Which modules may know PAPER/LIVE activation?

A future application/runtime activation boundary.

Not:

```text
Strategy
Risk
OANDA normalizers
historical simulator
financial value objects
```

---

### 11.4 Where are provider facts translated?

At explicit provider-to-Atlas projection boundaries.

Examples may include later:

```text
OANDA AccountSummary → AccountState
OANDA pricing → validated PAPER pricing input
OANDA inventory → reconciled broker-backed financial state
```

Each translation is independently earned.

---

### 11.5 Where does Risk authority live?

Risk owns:

```text
individual financial RiskDecision
under the active trader-approved Risk policy
```

Risk does not own:

```text
PAPER activation
LIVE activation
broker credential authority
reconciliation completion
process startup permission
```

---

### 11.6 Where will broker mutation live?

In a future PAPER provider-mutation boundary called only after:

```text
orchestration prerequisites
+
Strategy proposal
+
Risk approval
```

Exact API is deferred.

---

### 11.7 Where will reconciliation live?

In a future PAPER application/provider authority boundary that compares broker-confirmed state with Atlas-local state before resume/new exposure.

Exact schema/algorithm is deferred.

---

### 11.8 Which contracts should retain identical meaning across environments?

Strong reusable semantics:

```text
StrategyVersion methodology identity
Strategy evaluation
StrategyDecision
Direction / Action
TargetProposal
EntryPolicy / PendingEntryHandoff
MarketSpecification
Strategy PositionState
Atlas financial Position value
Risk AccountState
RiskConfig
Risk financial decision semantics
```

subject to later explicit pricing/sizing work.

---

### 11.9 Which mechanics should intentionally differ?

Experiment-specific:

```text
SimulationClock
DatasetSnapshot execution observations
historical ExecutionObservation
SimulatedExecutionAdapter
historical Order
historical Fill
Experiment financial projections
Experiment trading persistence
ExperimentRunner
historical apply_fill()
```

Future PAPER-specific:

```text
provider pricing projection
broker instruction translation
provider outcome/confirmation
reconciliation
broker-backed accounting projection
activation/resume orchestration
```

---

### 11.10 Where does capital authorization occur?

Trader approval governs mode activation and capital exposure.

Atlas Risk remains authoritative for individual RiskDecision outcomes under the approved policy.

A Risk approval alone is not permission for PAPER/LIVE activation.

---

## 12. Reuse/refactor classification matrix

| Seam                                   | Current responsibility                       | Historical coupling                                 | PAPER requirement                                       | Primary classification          | Decision / next action                                    |
| -------------------------------------- | -------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------- | ------------------------------- | --------------------------------------------------------- |
| StrategyVersion / methodology identity | Immutable methodology/version identity       | Existing Experiment selection                       | Exact same methodology                                  | **REUSE AS-IS**                 | Preserve verified version/fingerprint semantics           |
| Strategy evaluation contract           | Pure validated evaluation                    | Historical caller supplies bars/frontier            | Completed canonical PAPER inputs                        | **REUSE AS-IS**                 | PAPER builds context; Strategy remains unchanged          |
| StrategyContext                        | Completed analytical context/state           | Historical data currently comes from snapshots      | Equivalent completed PAPER context                      | **REUSE AS-IS**                 | Preserve no-lookahead/frontier rules                      |
| Direction / Action                     | Typed methodology vocabulary                 | Persisted historically as strings                   | Same meaning                                            | **REUSE AS-IS**                 | Keep provider-neutral                                     |
| TargetProposal                         | Deterministic target methodology             | Historical runner resolves it                       | Same methodology from actual accepted entry semantics   | **REUSE AS-IS**                 | Preserve                                                  |
| EntryPolicy / PendingEntryHandoff      | Strategy-owned trigger/window semantics      | Historical runner consumes via replay               | PAPER consumes via completed frontiers                  | **REUSE AS-IS**                 | Preserve methodology meaning                              |
| StrategyDecision                       | Immutable proposal/evidence                  | Persisted by Experiment                             | Same decision semantics                                 | **REUSE AS-IS**                 | Translate downstream; never treat as exposure             |
| Risk-local TradeIntent                 | Action/direction/stop/target input           | Existing caller is Experiment                       | Same financial proposal facts                           | **REUSE AS-IS**                 | Do not inflate with lifecycle/provider metadata           |
| Atlas financial Position               | Normalized financial state                   | ORM projection is separate                          | Broker-backed projection later                          | **REUSE AS-IS**                 | Reuse value only after explicit projection policy         |
| Risk AccountState                      | Base currency + equity                       | Experiment currently supplies simulation equity     | Provider-projected financial facts                      | **REUSE AS-IS**                 | PAPER 01G may project OANDA summary into it               |
| RiskConfig                             | Risk-per-trade policy input                  | Stored with Experiment today                        | Same approved policy input                              | **REUSE AS-IS**                 | No broad policy redesign                                  |
| RiskDecision                           | Financial decision output                    | Currently persisted in Experiment graph             | Same decision meaning                                   | **REUSE AS-IS**                 | Persistence ownership remains environment-specific        |
| Risk lifecycle gating                  | Requires `experiment_status == RUNNING`      | Direct historical lifecycle dependency              | No environment lifecycle inside reusable Risk           | **REFACTOR BEFORE PAPER**       | Immediate prerequisite: remove lifecycle coupling         |
| Risk sizing arithmetic                 | Equity/risk-rate/stop-distance quantity      | Uses historical simple quote                        | Same financial law but PAPER price semantics unresolved | **REFACTOR BEFORE PAPER**       | Preserve now; revisit only at PAPER pricing/quantity seam |
| ExecutableQuote                        | Historical bid/ask input                     | Runner can produce deterministic simple quote       | Quantity-aware broker pricing not yet proven            | **KEEP EXPERIMENT-SPECIFIC**    | Do not broaden now; separate PAPER pricing seam later     |
| Historical ExecutionObservation        | M1 BID/ASK OHLC + bar provenance             | Entirely historical                                 | Not a live-price contract                               | **KEEP EXPERIMENT-SPECIFIC**    | Leave unchanged                                           |
| execution Order                        | Small simulated instruction                  | Historical order tuples                             | Future broker-neutral instruction                       | **KEEP EXPERIMENT-SPECIFIC**    | Create separate PAPER instruction later                   |
| execution Fill                         | Sequence-one historical execution fact       | Simulation price basis/slippage/bar provenance      | Future broker-confirmed execution                       | **KEEP EXPERIMENT-SPECIFIC**    | Separate PAPER confirmation contract later                |
| SimulatedExecutionAdapter              | Deterministic replay execution               | Fully historical                                    | Must not model OANDA matching                           | **KEEP EXPERIMENT-SPECIFIC**    | Preserve reproducibility                                  |
| `apply_fill()`                         | Historical financial transition              | Experiment Account/Position/Trade/model assumptions | PAPER broker-backed accounting later                    | **KEEP EXPERIMENT-SPECIFIC**    | Separate PAPER accounting boundary when earned            |
| TradingRepository                      | Historical trading-row persistence           | Experiment ownership required                       | PAPER ownership later                                   | **KEEP EXPERIMENT-SPECIFIC**    | Do not generalize                                         |
| TradeIntent persistence                | Append-only historical intent                | Non-null Experiment ownership                       | PAPER durable intent later                              | **KEEP EXPERIMENT-SPECIFIC**    | Design separate ownership only when needed                |
| RiskDecision persistence               | Historical Risk receipt                      | Transitively Experiment-owned                       | PAPER receipt later                                     | **KEEP EXPERIMENT-SPECIFIC**    | Preserve existing graph                                   |
| Order persistence                      | Historical Order/event state                 | Experiment ownership/status model                   | Broker-backed order state later                         | **KEEP EXPERIMENT-SPECIFIC**    | Defer new PAPER design                                    |
| Fill persistence                       | Historical Fill storage                      | Historical fields/ownership                         | Provider-confirmed execution later                      | **KEEP EXPERIMENT-SPECIFIC**    | Do not generalize before confirmation semantics           |
| Trade persistence                      | Historical result projection                 | Experiment ownership/exit vocabulary                | Broker-backed local projection later                    | **KEEP EXPERIMENT-SPECIFIC**    | Separate later                                            |
| Experiment account projection          | Simulated financial account                  | Explicitly Experiment-owned                         | Never broker account truth                              | **KEEP EXPERIMENT-SPECIFIC**    | Leave unchanged                                           |
| Experiment Position projection         | Historical financial projection              | Experiment + Fill application                       | Never direct broker projection                          | **KEEP EXPERIMENT-SPECIFIC**    | Leave unchanged                                           |
| ExperimentRunner                       | Historical orchestration/result finalization | Clock/snapshot/simulation/terminal close            | PAPER requires separate coordinator                     | **KEEP EXPERIMENT-SPECIFIC**    | No PAPER mode flag                                        |
| OANDA read-only observations           | Provider-native validated facts              | Provider-specific by design                         | Inputs to later projection seams                        | **REUSE AS-IS**                 | Keep provider-specific/read-only                          |
| `runtime/main.py`                      | Safe readiness/shutdown process              | No trading lifecycle yet                            | Activation/reconcile/resume before mutation             | **DEFER UNTIL BROKER MUTATION** | Keep inert until required                                 |

---

## 13. Required pre-PAPER sequence

The audit does **not** authorize a multi-stage mass refactor.

Only one demonstrated internal prerequisite blocks the next planned PAPER projection.

### Immediate prerequisite

## PAPER Readiness 02 — Risk Lifecycle Boundary Cleanup

**Likely class:** Critical.

### Why now

Current reusable Risk requires:

```text
experiment_status
```

PAPER has no Experiment lifecycle and must not fabricate one.

### Exact seam

Primarily:

```text
backend/risk/service.py
historical ExperimentRunner Risk call sites
focused Risk/Experiment tests
```

### Required architectural result

Before:

```text
Experiment status
      ↓
Risk
```

After:

```text
ExperimentRunner proves lifecycle eligibility
      ↓
Risk financial decision
```

Future PAPER:

```text
PAPER coordinator proves lifecycle/reconciliation eligibility
      ↓
Risk financial decision
```

### Preserve

- Risk sizing mathematics;
- RiskConfig;
- AccountState;
- TradeIntent;
- RiskDecision semantics;
- historical Experiment methodology/results;
- current EUR/USD/USD capability;
- whole-unit sizing unless separately changed later.

### Do not add

```text
authorized=True
eligible=True
paper_active=True
reconciled=True
runtime_ready=True
```

to Risk as replacement lifecycle inputs.

### Enabled outcome

PAPER 01G may safely project OANDA account facts into provider-neutral `AccountState` without passing fake Experiment lifecycle information downstream.

---

### Next bounded PAPER slice

After Risk cleanup closes:

## PAPER 01G — OANDA Practice Account Summary → Risk AccountState

Pure deterministic projection:

```text
OandaPracticeAccountSummarySnapshot
        ↓
AccountState
```

No broker mutation.

No runtime.

No persistence.

No Risk-policy change.

---

### Later just-in-time gates

These are capability gates, not an up-front refactor roadmap.

#### A. PAPER analytical frontier/state continuity

Required immediately before the first PAPER Strategy evaluation.

Must establish:

- completed analytical input;
- exact StrategyVersion;
- durable state;
- no duplicate/replayed frontier.

#### B. PAPER pricing / quantity semantics

Required immediately before actual PAPER pre-submission sizing.

Must resolve the interaction between:

```text
provider price/liquidity buckets
```

and:

```text
Risk-sized quantity
```

without assuming `bids[0]` or `asks[0]` prices arbitrary quantity.

#### C. PAPER instruction / broker-confirmation boundary

Required immediately before first OANDA mutation.

Must distinguish:

```text
approved instruction
request attempted
broker rejected
outcome unknown
broker confirmed
confirmed execution
```

#### D. PAPER ownership / reconciliation / accounting

Required before durable mutation-capable state is relied upon.

Must avoid synthetic Experiment ownership and ensure contradictory broker state blocks further exposure.

#### E. PAPER runtime activation / resume gate

Required immediately before Atlas can actually mutate OANDA.

Must require explicit trader approval and fail closed when identity/reconciliation/protection/authority is uncertain.

Each gate receives its own approved vertical workstream when earned.

---

## 14. Explicitly deferred architecture

This audit deliberately does not design:

- final PAPER database tables;
- generalized Experiment/PAPER/LIVE ownership;
- generic broker abstractions;
- multi-broker architecture;
- multi-account portfolio architecture;
- final OANDA Order payloads;
- cancellation/amendment policy;
- partial-fill support;
- provider transaction recovery schema;
- reconciliation scheduler;
- broker Position netting/hedging policy;
- PAPER Strategy state persistence implementation;
- pricing depth/VWAP algorithm;
- quote freshness thresholds;
- generic execution engine;
- generic accounting engine;
- LIVE architecture;
- service decomposition;
- event bus;
- CQRS;
- event sourcing;
- WebSockets;
- daemon framework;
- frontend PAPER controls;
- additional instruments/currencies;
- broader Risk policy.

Future capability may shape today's seams.

It does not authorize speculative implementation today.

---

## 15. Safety / capital boundary

This audit changes architecture understanding only.

It does not authorize:

- OANDA mutation;
- Order submission;
- Order cancellation;
- broker Trade/Position modification;
- PAPER activation;
- LIVE activation;
- credential changes;
- Risk-policy changes;
- capital allocation changes;
- local state overriding broker facts.

Current OANDA PAPER modules remain read-only.

Current runtime remains non-trading.

Current Experiment execution remains historical simulation.

The immediate next implementation, if separately approved, is only:

```text
PAPER Readiness 02
Risk Lifecycle Boundary Cleanup
```

That workstream must remain capital-incapable and preserve historical Experiment behavior.

After it closes, Atlas resumes the smallest trustworthy PAPER vertical slices rather than beginning a broad internal refactor.
