# PLAN — PAPER 06 Runtime + Activation

## Workstream state

- **Workstream:** `paper-06-runtime-activation`
- **Outcome:** Establish the smallest trustworthy local-first OANDA Practice PAPER runtime and explicit activation boundary that can repeatedly process the supported completed EUR/USD M15 analytical frontier, preserve Strategy state and durable execution identity across process restart, continue read-only Strategy state advancement while attributable supported exposure is open, route every new capital-capable opening through the frozen PAPER 05 execution/reconciliation authority, and fail closed on stop, uncertainty, stale state, ownership loss, semantic conflict, or fatal error.
- **Classification:** `Critical`. This workstream may authorize repeated capital-capable PAPER execution and crosses activation, restart, ownership, scheduling, Strategy-state, and runtime safety boundaries.
- **Base:** `main` at `0960191344595cf059cd99cb5bfb5ac6ce930dcd` (`Close PAPER 05 workstream`)
- **Base SHA:** `0960191344595cf059cd99cb5bfb5ac6ce930dcd`
- **Branch:** `solo/paper-06-runtime-activation`
- **Phase:** `READY_FOR_USER`
- **Approval:** `IMPLEMENTATION APPROVED` received; GIT START completed on the approved base
- **Architecture:** `FROZEN` for approval review once this replacement and its matching ARCHITECTURE are installed together
- **Task state:** T001 DONE; T002 DONE; T003 DONE; T004 DONE; T005 DONE; T006 DONE; T007 DONE; T008 DONE in the bounded implementation decomposition
- **Next action:** developer independently inspect the pushed feature HEAD and provide merge approval; do not merge or perform GIT END
- **Remediation state:** Original validation and the subsequent workstream review returned findings; R001–R003 passed their immutable chains, and the explicitly authorized post-cap R004–R006 closure batch now has independent validation/review PASS receipts. The immutable first R004 validation records its unavailable-environment/tooling limitation; later serial dedicated-PostgreSQL validation and complete review close the product findings. No R007 or additional remediation is authorized.
- **Post-cap findings:** R004 terminal P05 outcome safety, R005 non-MT4 startup capability proof, and R006 exact `risk_per_trade` persistence are closed by their independent BUILD/VALIDATE/REVIEW chains. No unresolved CRITICAL, IMPORTANT, or MINOR product finding remains.
- **Concerns:** This is the first repeated capital-capable PAPER boundary. Activation must be explicit and local-authority constrained; Strategy evaluation eligibility must remain distinct from new-entry eligibility; runtime state must not be inferred from process liveness; Strategy/Risk/execution/reconciliation authority must not be bypassed; a durable claim remains a possible mutation rather than proof; STOP and restart semantics must preserve already-authorized dependent protection without allowing new exposure or resubmission; transient pre-claim observation failure must not be converted into false terminal corruption. No real OANDA mutation, PAPER activation, LIVE operation, credential change, or Risk-policy change is authorized during BUILD, VALIDATE, or REVIEW.

## 1. Repository-grounded starting point

The requested slice follows the closed PAPER 05 capability on the required base. The current implementation provides:

```text
validated PAPER Strategy evaluation
fresh completed native analytical frontier
Strategy evaluation using caller-supplied FinancialPositionState
fresh PAPER Risk composition
durable PAPER execution attempts and permanent mutation claims
durable normalized broker observations and execution outcomes
bounded read-only reconciliation
```

The repository also establishes two important current semantics that PAPER 06 must preserve:

```text
evaluate_current_paper_strategy_receipt(...)
accepts FLAT / LONG / SHORT FinancialPositionState for restored Strategy state

Candle Confirmation Break
returns NO_ACTION while financial exposure is non-FLAT
and advances StrategyStateEnvelope to the current completed frontier
```

Therefore:

```text
Strategy evaluation eligibility
≠
new-entry eligibility
```

A supported open PAPER Trade must prevent a second entry, but it must not automatically freeze analytical Strategy-state progression.

The current implementation does not provide:

```text
durable PAPER activation authority
runtime ownership or a single active runtime guard
repeated frontier cadence
durable runtime Strategy-state authority
cycle/frontier idempotency
explicit trader start/stop controls
restart recovery orchestration
runtime status/health evidence
```

The existing runtime is readiness-only. The existing API is locally authorized, but has no PAPER activation contract. PAPER 05 deliberately retained Strategy `next_state` as evaluation evidence rather than runtime authority and explicitly excluded runtime, activation, scheduling, and automatic resumption.

The current supported capital-capable boundary remains exactly:

```text
OANDA Practice
one configured non-MT4 USD account
EUR_USD
IMMEDIATE OPEN_LONG / OPEN_SHORT
fresh Strategy evaluation
fresh Risk evaluation
durable PAPER execution attempt
bounded read-only reconciliation
```

## 2. Capability hypothesis

The smallest complete vertical slice is:

```text
explicit local trader activation
        ↓
durable exact activation/configuration snapshot
        ↓
one owned local runtime process
        ↓
wait for one new completed native EUR/USD M15 frontier
        ↓
obtain one coherent current account/exposure observation
        ↓
evaluate the exact configured StrategyVersion
with persisted Strategy state + observed FinancialPositionState
        ↓
persist cycle evidence + Strategy state
        ↓
if NO_ACTION / read-only state progression:
    no Risk and no mutation
        ↓
if IMMEDIATE opening while fresh account is entry-eligible:
    fresh PAPER 05 preparation/Risk
    → durable attempt + ENTRY claim
    → existing bounded mutation/protection flow
        ↓
bounded reconciliation on interrupted claimed work only
        ↓
durable inspectable runtime status
```

A known attributable open Trade therefore permits read-only Strategy evaluation while forbidding a second opening.

Only the entry branch requires:

```text
FLAT exposure
zero pending Orders
no unresolved/unsafe PAPER attempt
fresh P05 Risk/execution eligibility
```

The architecture must not introduce generic worker infrastructure merely to obtain this loop.

## 3. Scope boundary

In scope:

```text
one local Atlas runtime process
one explicitly configured OANDA Practice USD account
EUR_USD native completed M15 frontier
one exact persisted StrategyVersion and validated parameter snapshot
one exact RiskConfig.risk_per_trade activation snapshot

durable activation intent/approval and lifecycle state
one live runtime owner
durable cycle/frontier identity
durable Strategy state for same-activation process restart
bounded account/exposure input evidence for each evaluated frontier

monotonic no-lookahead frontier processing
read-only Strategy evaluation while an attributable supported Trade is open
strict separation between Strategy evaluation and entry eligibility

reuse of PAPER 05 durable execution and bounded reconciliation
narrow P05 caller-owned transaction seam for runtime atomicity
explicit STOP with deterministic claim/mutation linearization
restart-safe read-only recovery
durable runtime status and bounded operational-phase evidence

local-only API control seam
deterministic unit tests
PostgreSQL migration/concurrency/restart tests
```

Explicitly out of scope:

```text
LIVE or non-Practice operation
broker credential management or credential persistence
automatic activation
automatic entry resubmission
automatic cancellation, closing, reduction, or protection repair
mutation on restart after an existing claim

multiple runtime owners
multiple accounts
multiple instruments
multiple concurrently configured Strategies
queues, distributed scheduling, workers, leader-election platforms

cross-activation automatic Strategy-state continuation
automatic missed-frontier catch-up
historical-signal execution after downtime

changing Strategy methodology
general Strategy SDK work
Risk-policy administration
historical Experiment semantic changes

PAPER PnL
closed-Trade accounting
general portfolio management

WebSockets
streaming market data
unbounded transaction synchronization

capital-capable testing against a real broker
```

## 4. Architecture questions resolved

`ARCHITECTURE.md` resolves:

- explicit activation as a durable trader-approved session;
- exact immutable activation configuration and Risk snapshot;
- one PostgreSQL advisory-lock runtime owner plus guarded durable ownership evidence;
- one cycle per exact Strategy configuration and completed frontier;
- same-activation Strategy-state persistence and restart recovery;
- fresh bootstrap for every newly approved activation session;
- no automatic state seeding from a terminal prior activation;
- no automatic analytical catch-up after a missed eligible frontier;
- distinct evaluation and entry gates;
- Strategy evaluation with exact `FinancialPositionState`;
- durable cycle evidence binding the financial-position input and bounded account observation provenance;
- transient pre-claim observation unavailability as a retryable operational wait within the same frontier;
- malformed, contradictory, identity-changing, unattributed, or post-claim uncertainty as fail-closed state;
- exact P05 preparation/Risk/claim authority for all openings;
- one-shot STOP/claim ordering;
- completion of already-authorized same-process dependent protection after a pre-STOP ENTRY claim;
- no dependent mutation on process restart;
- deterministic recovery of committed claims through PAPER 05 read-only reconciliation only;
- explicit status projections that separate runtime lifecycle from broker/exposure truth.

## 5. Acceptance direction

Implementation must prove at minimum:

1. No runtime becomes capital-capable without explicit trader activation for the exact supported account, StrategyVersion, parameters, Risk configuration, and runtime policy.

2. Activation and runtime ownership are durable, auditable, idempotent, and single-owner under concurrent starts and process restart.

3. Only a newly observed completed analytical frontier can create a Strategy cycle. Duplicate, future, forming, or already-consumed frontiers never evaluate twice.

4. A coherent supported `LONG` or `SHORT` financial position does not automatically prevent read-only Strategy evaluation. Strategy state continues to advance across eligible frontiers while new entry exposure remains forbidden.

5. A new entry is possible only when a fresh coherent account snapshot proves the current supported entry state is FLAT with zero pending Orders and no outstanding unsafe PAPER truth.

6. Unattributed exposure, contradictory account views, malformed provider facts, unsafe pending state, or inability to establish a valid financial position fails closed.

7. Temporary read-only provider/data unavailability before a durable cycle/claim does not immediately terminally block activation. The runtime may retry the same frontier within bounded normal polling. If the frontier is ultimately missed, the same activation blocks with an explicit frontier-gap reason.

8. Strategy state is advanced only at a durable named boundary and cannot be paired with another StrategyVersion, parameter snapshot, financial-position input, frontier, or cycle identity.

9. A new explicit activation starts from a fresh bootstrap. Process restart of the same non-terminal activation resumes only its exact durable Strategy state. No terminal activation automatically donates Strategy state to a new session.

10. Every executable opening uses the exact validated Strategy receipt, fresh PAPER Risk authority, and PAPER 05 durable attempt/claim/mutation/reconciliation path. Runtime never calls an OANDA mutation seam directly.

11. A cycle/process crash cannot create a second ENTRY or TAKE_PROFIT mutation. Any committed claim encountered after restart is read-only reconciliation authority only.

12. STOP linearizes against the activation row and new ENTRY claim. If STOP wins first, no new entry claim is possible. If the ENTRY claim wins first, that already-authorized same-process execution may complete at most once, including its dependent protection chain if Fill occurs, while no later cycle may start.

13. STOP never implies that an already-authorized broker mutation was cancelled, reversed, or absent.

14. `UNKNOWN`, unresolved reconciliation, conflict, unattributed exposure, protection-incomplete execution, owner loss, invalid durable state, and fatal errors cannot permit new exposure.

15. `FILLED_PROTECTED` remains historical execution-resolution truth, not proof that the current Trade remains open or closed. `LIFECYCLE_ADVANCED` never proves flatness.

16. A current attributable open Trade may support read-only Strategy-state progression, but another entry still requires a later fresh full Account Details snapshot proving FLAT and zero pending Orders.

17. Historical Experiment semantics, Strategy methodology, Risk semantics, PAPER 05 execution/reconciliation, OANDA mutation semantics, and LIVE boundaries remain unchanged.

18. PostgreSQL migration, constraint, ownership, cycle-uniqueness, STOP race, restart, state, and transaction-boundary tests provide evidence appropriate to this Critical boundary.

19. All BUILD/VALIDATE/REVIEW execution evidence uses deterministic fakes, fixtures, and `httpx.MockTransport`. No real OANDA mutation, PAPER activation, or capital-capable credential use occurs.

## 6. Lifecycle gate

```text
PLAN
→ ARCHITECTURE
→ reconcile PLAN + ARCHITECTURE
→ DEVELOPER_APPROVAL
```

Before explicit developer implementation approval, do not:

```text
GIT START
create a feature branch
create tasks/
modify application or test code
start the PAPER runtime
activate PAPER
use credentialed broker mutation
```

The architecture worker owns only `ARCHITECTURE.md`. After reconciliation, the developer explicitly approved both complete canonical artifacts with `IMPLEMENTATION APPROVED`.

## 7. Reconciled architecture

The canonical architecture freezes:

```text
explicit local activation request
with exact Strategy + parameter + Risk configuration
        ↓
durable REQUESTED
        ↓
one PostgreSQL advisory-lock runtime owner
        ↓
STARTING
        ↓
safe startup / exact same-activation recovery
        ↓
RUNNING
        ↓
one eligible completed M15 frontier
        ↓
one coherent account/exposure observation
        ↓
one unique Strategy cycle
        ↓
Strategy evaluation using:
    exact StrategyVersion
    exact validated parameters
    exact state_before
    exact financial_position_state
    exact frontier
        ↓
state_after + cycle evidence durable
        ↓
NO_ACTION / read-only progression
or
PAPER 05 opening path if fresh entry gate is FLAT
```

Three PAPER-runtime-specific durable tables are selected:

```text
paper_runtime_activations
paper_runtime_cycles
paper_runtime_ownership
```

Activation is a durable explicit trader session, not process liveness.

A new explicit activation uses `FRESH_BOOTSTRAP`. It does not automatically resume Strategy state from a terminal prior activation. Process restart while the same activation remains non-terminal may resume its exact durable state after bounded read-only recovery and only if frontier continuity still holds.

Runtime uses one fixed 15-second polling cadence and processes at most one completed frontier per tick. It does not perform automatic missed-frontier catch-up.

Before cycle reservation, transient provider/data unavailability may leave the runtime `RUNNING` in a bounded waiting operational phase and retry the same frontier. Semantic contradiction, identity mismatch, or a missed eligible frontier blocks the session.

Every evaluated cycle durably binds:

```text
Strategy identity
parameter identity
frontier
state_before
financial_position_state
bounded account observation provenance
Strategy evaluation
state_after
```

A coherent attributable open PAPER position may continue read-only Strategy evaluation. Existing exposure, expected protection Orders, or a prior Fill do not authorize another entry.

Only a fresh FLAT/no-pending entry gate can enter PAPER 05 preparation/Risk.

For an opening cycle, the runtime-owned transaction commits:

```text
cycle evidence
state_after
PAPER 05 immutable attempt
permanent ENTRY claim
```

before one entry POST is possible.

The P05 implementation may gain a narrow caller-owned transaction seam to support this atomic boundary. Risk, durable attempt construction, claim semantics, broker translation, mutation, Fill, protection, observations, and reconciliation remain PAPER 05 authority.

STOP fences new cycles and new ENTRY claims. If an ENTRY claim committed before STOP, that already-authorized same-process execution may finish its one entry submission and dependent protection chain at most once while ownership remains valid. Restart after any claim is always read-only.

No BUILD task is authorized until this replacement PLAN and its matching ARCHITECTURE are explicitly approved.
