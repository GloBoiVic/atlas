# PAPER 06 — Runtime + Activation Architecture

**Role:** `ARCHITECT`
**Workstream:** `paper-06-runtime-activation`
**Classification:** `Critical`
**Status:** Architecture freeze candidate; pre-approval
**Branch:** `main` (pre-approval; no GIT START)
**Base:** `main` at `0960191344595cf059cd99cb5bfb5ac6ce930dcd`

This document freezes the narrowest trustworthy local-first OANDA Practice PAPER runtime.

It authorizes no implementation, branch creation, PAPER activation, broker mutation, credential change, Risk-policy change, or capital exposure.

The current runtime in `backend/runtime/main.py` is readiness-only: it checks the database and waits for process termination. Process existence does not imply trading authority.

## 1. Frozen outcome and boundary

The capability is exactly one explicitly activated local runtime for:

```text
OANDA Practice
one configured non-MT4 USD account
EUR_USD
provider-native completed M15 MID analytical bars
one immutable StrategyVersion
one exact validated parameter snapshot
one RiskConfig.risk_per_trade snapshot
PAPER 05 durable execution and bounded reconciliation
```

The runtime is a single local process, not a worker platform.

It has no:

```text
queue
distributed scheduler
leader-election platform
catch-up worker
multi-account manager
autonomous repair system
```

Starting `atlas-runtime` never creates activation authority.

Only an explicit local trader activation request creates one durable PAPER runtime session.

### 1.1 Strategy evaluation and entry are separate gates

The runtime processes Strategy state on each newly eligible completed M15 frontier when it can establish a coherent supported financial-position input.

Therefore:

```text
Strategy evaluation eligibility
≠
new-entry eligibility
```

A coherent attributable open PAPER Trade may produce:

```text
FinancialPositionState.LONG
or
FinancialPositionState.SHORT
```

and the Strategy may still be evaluated read-only so its durable frontier/state remains current.

No new entry is possible while exposure exists.

A new opening requires a separate fresh entry gate:

```text
FinancialPositionState.FLAT
open_trade_count = 0
open_position_count = 0
pending_order_count = 0
no unsafe outstanding PAPER attempt
fresh PAPER 05 preparation/Risk approval
```

This distinction is mandatory.

Freezing Strategy evaluation merely because a supported Trade is open would make state stale and violate the existing one-frontier-at-a-time Strategy contract.

### 1.2 Fail-closed categories

The runtime distinguishes two classes of inability to proceed.

**Transient pre-claim observation unavailability**

Examples:

```text
temporary Account Details timeout
temporary analytical source timeout
expected completed bar not yet visible from provider
bounded read-only transport failure
```

When no durable cycle/mutation claim has crossed a capital boundary, these conditions do not immediately terminally block activation.

The runtime:

```text
creates no mutation
does not invent a completed frontier
does not advance Strategy state
remains RUNNING
reports a bounded waiting operational phase/reason
may retry the same eligible frontier on the normal 15-second poll
```

If the runtime misses an entire required eligible frontier before it can evaluate it, normal frontier-continuity rules then block the same activation with `FRONTIER_GAP`.

**Semantic or post-claim uncertainty**

Examples:

```text
wrong account identity
unsupported account/currency/provider state
contradictory Trade/Position projection
unattributed exposure
invalid durable Strategy state
registry drift
UNKNOWN execution
unresolved/conflicted reconciliation
protection-incomplete Fill
owner loss
post-claim persistence uncertainty
```

These fail closed and prevent further capital exposure.

## 2. Existing authority that remains unchanged

PAPER 06 composes, but does not reinterpret:

```text
evaluate_current_paper_strategy_receipt(...)
    exact persisted StrategyVersion
    exact local registry provenance
    exact validated parameters
    caller-supplied Strategy state
    caller-supplied FinancialPositionState
    current completed native M15 frontier
    StrategyEvaluation(decision, next_state)

PaperDurableExecutionApplication
    fresh execution-account facts
    fresh executable pricing
    fresh Risk evaluation exactly once
    immutable PAPER attempt evidence
    permanent ENTRY / TAKE_PROFIT claims
    non-retrying entry POST
    non-retrying dependent Take Profit PUT
    normalized observations and outcome

PaperReconciliationCoordinator
    GET-only
    finite
    bounded recovery
    no POST
    no PUT
    no cancel
    no close
    no reduce
    no repair
```

`Strategy` proposes.

`RiskService` authorizes and sizes every new opening.

OANDA facts establish broker exposure.

Persistence records what Atlas has durably established.

Historical Experiment Order/Fill/Trade persistence is never PAPER runtime state or broker truth.

`StrategyEvaluation.next_state` remains evaluation evidence until committed through the runtime cycle boundary.

The existing local authority middleware remains mandatory for PAPER control/status routes.

Loopback peer and authority validation must remain based on actual request metadata. Forwarded headers or caller-claimed client identity do not authorize PAPER activation.

## 3. Activation authority

### 3.1 Activation is an explicit runtime session

Each activation is identified by caller-supplied:

```text
activationRequestId UUID
```

The UUID is the idempotency identity for the explicit trader request.

It is not:

```text
an execution attempt_id
an OANDA client ID
a broker correlation
```

The activation snapshot contains bounded non-secret configuration:

```text
activation_id
provider = OANDA
environment = PRACTICE
provider_account_id = configured ATLAS_OANDA_ACCOUNT_ID
base_currency = USD
instrument = EUR_USD

strategy_version_id
strategy_key
strategy_version_number
source_fingerprint
implementation_key
validated_parameter_snapshot
parameter_fingerprint

risk_per_trade

state_origin = FRESH_BOOTSTRAP
runtime_policy_version = ATLAS_PAPER_RUNTIME_V1
poll_interval_seconds = 15

approval_kind = EXPLICIT_LOCAL_TRADER
approval_code = ACTIVATE_PAPER
requested_at
```

No credential/token is persisted, returned, or logged.

The request does not permit the caller to select:

```text
provider
environment
account
currency
instrument
Strategy state
RiskDecision
StrategyDecision
attempt_id
broker payload
broker correlation IDs
```

The configured account is server-bound.

Changing the configured account after activation is an identity mismatch and blocks the activation; it never retargets the session.

The activation request validates locally:

```text
StrategyVersion exists
registry provenance matches
parameter object exactly matches immutable schema
Risk value is valid
token configuration is present
account configuration is syntactically present
no non-terminal activation already occupies the slot
no locally known unresolved/unsafe PAPER attempt makes a new session obviously unsafe
```

The activation request itself never calls OANDA.

Provider capability/account facts are proven by the runtime before `RUNNING`.

### 3.2 New activation versus process restart

A **new explicit activation** always starts:

```text
state_origin = FRESH_BOOTSTRAP
strategy_state = null
```

P06 does not automatically seed a new session from a terminal prior session.

No hidden cross-activation continuation exists.

This is deliberate.

A **process restart of the same non-terminal activation** may continue its exact durable Strategy state after:

```text
ownership reacquisition
configuration revalidation
bounded claim reconciliation
safe current account truth
frontier continuity validation
```

If the same activation missed an eligible analytical frontier, it becomes `BLOCKED`.

There is no automatic missed-bar catch-up.

The trader may later create a new explicitly approved activation, which begins a visibly fresh Strategy session once broker/local safety permits.

### 3.3 Activation lifecycle

```text
REQUESTED
STARTING
RUNNING
STOP_REQUESTED
STOPPED
BLOCKED
FAILED
```

Non-terminal:

```text
REQUESTED
STARTING
RUNNING
STOP_REQUESTED
```

Terminal:

```text
STOPPED
BLOCKED
FAILED
```

Terminal refers only to the runtime session.

It does not mean:

```text
account flat
Trade closed
broker mutation absent
reconciliation resolved
```

Broker/exposure truth remains separately projected in status.

### 3.4 API surface

Minimum local HTTP surface:

```text
GET  /api/v1/paper/capability
POST /api/v1/paper/activations
GET  /api/v1/paper/activations/active
GET  /api/v1/paper/activations/{activation_id}
POST /api/v1/paper/activations/{activation_id}/stop
POST /api/v1/paper/activations/{activation_id}/reconcile
```

Activation request:

```json
{
  "activationRequestId": "uuid",
  "strategyVersionId": "uuid",
  "parameters": { "...": "exact schema values" },
  "riskPerTrade": "0.01",
  "confirmation": "ACTIVATE_PAPER"
}
```

Same ID + exact same immutable request:

```text
return existing activation
```

Same ID + changed facts:

```text
409 ACTIVATION_IDENTITY_CONFLICT
```

Different ID while another non-terminal activation exists:

```text
409 PAPER_ACTIVATION_ALREADY_PRESENT
```

### 3.5 STOP route

STOP requires a bounded non-empty reason.

It is idempotent.

For `REQUESTED`, the STOP transaction may move directly to `STOPPED` under the activation row lock because no runtime cycle/claim has started.

For `STARTING` or `RUNNING`:

```text
STOP_REQUESTED
```

is persisted under the activation row lock.

The API does not infer runtime liveness from heartbeat age.

The runtime owner observes the durable STOP fence and drains only already-authorized work.

For a terminal activation, repeated STOP returns terminal evidence.

### 3.6 Reconcile route

The route performs at most one existing PAPER 05 bounded GET-only reconciliation pass for an outstanding attempt.

It:

```text
never submits
never repairs
never creates a claim
never retries a mutation
never converts absence into success
```

The route refuses concurrent reconciliation for a non-terminal activation whose runtime owns recovery.

For terminal `STOPPED`, `BLOCKED`, or `FAILED` sessions, explicit operator reconciliation may run through existing P05 projection/version guards.

No heartbeat inference authorizes concurrency.

## 4. Durable persistence shape

The next migration must descend from the actual implementation-time migration head.

At the approved base, PAPER 05 ends at:

```text
0022_paper_persistence
```

Three PAPER-runtime-specific tables are frozen:

```text
paper_runtime_activations
paper_runtime_cycles
paper_runtime_ownership
```

They remain separate from:

```text
paper_execution_attempts
paper_mutation_claims
paper_broker_observations
paper_reconciliation_runs
```

and from historical Experiment persistence.

### 4.1 `paper_runtime_activations`

Immutable activation/configuration plus guarded runtime projection:

```text
activation_id PK
strategy_version_id FK ON DELETE RESTRICT
strategy_key
strategy_version_number
source_fingerprint
implementation_key
validated_parameter_snapshot JSONB
parameter_fingerprint

provider = OANDA
environment = PRACTICE
provider_account_id
base_currency = USD
instrument = EUR_USD

risk_per_trade NUMERIC
state_origin = FRESH_BOOTSTRAP
runtime_policy_version
poll_interval_seconds
approval_kind
approval_code
requested_at

lifecycle_state
state_reason_code nullable
state_detail nullable bounded
state_changed_at

operational_phase
last_operational_reason_code nullable
last_operational_at nullable

strategy_state JSONB nullable
strategy_state_fingerprint nullable
last_frontier_end nullable
last_cycle_id nullable FK

control_version
updated_at
```

Immutable configuration cannot update or delete.

Runtime projection changes only through named guarded repository transitions.

`STOP_REQUESTED` may be written by the local control API under row lock.

JSON is:

```text
canonical
bounded
object-shaped
secret-free
```

Every non-null Strategy state must restore to an exact valid `StrategyStateEnvelope`.

Database constraints include:

```text
fixed OANDA/PRACTICE/USD/EUR_USD scope
valid lifecycle
valid state_origin
valid runtime policy
positive finite risk_per_trade < 1
bounded JSON
lowercase SHA-256 fingerprints
one partial unique non-terminal activation slot
```

### 4.2 `paper_runtime_cycles`

One row represents exactly one analytical-frontier evaluation reservation/evidence set.

It is not a generic event log.

```text
cycle_id PK
activation_id FK ON DELETE RESTRICT
cycle_sequence positive BIGINT

evaluation_key
strategy_version_id FK ON DELETE RESTRICT
parameter_fingerprint

frontier_start UTC
frontier_end UTC
prior_frontier_end nullable UTC

state_before JSONB nullable
state_before_fingerprint nullable
state_after JSONB nullable
state_after_fingerprint nullable

financial_position_state
account_transaction_id
account_observed_at UTC
account_open_trade_count
account_open_position_count
account_pending_order_count
account_gate_fingerprint

strategy_evaluation_snapshot JSONB nullable
decision_snapshot JSONB nullable

attempt_id nullable FK → paper_execution_attempts.attempt_id

cycle_status
cycle_reason_code nullable

claimed_at
evaluated_at nullable
completed_at nullable
updated_at
```

`financial_position_state` is mandatory for an evaluated cycle because it is an input to Strategy behavior.

Allowed values:

```text
FLAT
LONG
SHORT
```

The bounded account evidence is not Risk authority.

It proves only the normalized runtime input used for this Strategy cycle.

PAPER 05 performs a second fresh account/pricing/Risk observation before any entry claim.

`evaluation_key` canonically identifies:

```text
StrategyVersion
validated parameter snapshot
```

Global uniqueness:

```text
UNIQUE(evaluation_key, frontier_end)
```

prevents the same Strategy configuration from evaluating the same completed frontier twice across:

```text
duplicate loop ticks
process restart
new activation sessions
```

Also unique:

```text
(activation_id, cycle_sequence)
(activation_id, frontier_end)
```

Cycle statuses:

```text
CLAIMED
EVALUATING
NO_ACTION
REFUSED
ENTRY_CLAIMED
ENTRY_RESOLVED
TAKE_PROFIT_CLAIMED
COMPLETE
RECOVERY_REQUIRED
BLOCKED
```

A terminal cycle never returns to `EVALUATING`.

### 4.3 `paper_runtime_ownership`

Singleton:

```text
slot_key = ATLAS_PAPER_RUNTIME PK
owner_id UUID
activation_id FK nullable
owner_generation positive BIGINT
acquired_at
heartbeat_at
phase
```

The live authority is one PostgreSQL **session-level advisory lock** on a fixed documented key.

The runtime holds that lock through one dedicated pinned PostgreSQL connection for its lifetime.

The lock must not be acquired through a transient pooled Session that can return the connection while the process continues.

Acquisition:

```text
pg_try_advisory_lock
```

The durable row is written only after lock acquisition succeeds.

Heartbeat is audit evidence.

Heartbeat age is never takeover authority.

A successor can replace the durable owner only after obtaining the advisory lock, which PostgreSQL releases when the previous lock-holding connection dies.

Every owner-controlled transition includes:

```text
owner_id
owner_generation
```

A zero-row guarded update is ownership loss.

Ownership loss fences:

```text
new cycle reservation
new ENTRY claim
new dependent claim
post-claim network dispatch not already protected by a valid owner
```

Claims are never transferred, released, reacquired, or retried.

## 5. Frontier, account input, and Strategy-state contract

### 5.1 One completed native frontier

The runtime consumes the existing native current analytical frontier semantics:

```text
OANDA
EUR/USD
M15
MID
completed-only
```

No:

```text
M1 aggregation
interpolation
forward-fill
forming candle
future candle
stale invented bar
```

At time `now`:

```text
cutoff = beginning of current UTC M15 interval
candidate = immediately preceding eligible completed M15 window
decision frontier = candidate.end_time
```

At:

```text
12:15:00Z
```

candidate is:

```text
12:00–12:15
```

At:

```text
12:14:59Z
```

candidate ends:

```text
12:00
```

Session-policy closures are skipped and do not count as missing eligible bars.

### 5.2 Consume one immutable frontier

P06 must add/refactor a Strategy evaluation seam that can consume the already-validated immutable `CurrentAnalyticalFrontier`.

The runtime must not:

```text
read frontier A
reserve cycle A
then let Strategy fetch frontier B
```

The evaluation receipt must refer to the exact reserved frontier.

### 5.3 Fresh bootstrap

For a newly approved activation:

```text
strategy_state = null
state_origin = FRESH_BOOTSTRAP
```

The existing warm-up semantics run with exposure disabled before one current decision.

Bootstrap requires a fresh coherent FLAT account because the current Strategy boundary does not permit state-null bootstrap with non-flat financial exposure.

### 5.4 Same-activation resume

For process restart of the same activation:

```text
strategy_state is exact StrategyStateEnvelope
schema matches exact StrategyVersion
state fingerprint matches durable row
state has prior frontier
candidate frontier > prior frontier
candidate.previous_frontier == state.last_evaluated_bar_end
```

If more than one eligible frontier has been missed:

```text
BLOCKED
FRONTIER_GAP
```

No automatic catch-up.

No historical opening is executed after downtime.

### 5.5 New terminal-session replacement

A later explicit activation never silently imports prior terminal Strategy state.

It starts fresh.

If its first candidate frontier was already globally consumed for the same `evaluation_key`, it waits for the next new frontier rather than evaluating that bar again.

This provides an explicit recovery path after:

```text
STOP
terminal BLOCK
fatal failure
frontier gap
```

without pretending stale Strategy state is current.

## 6. Evaluation gate versus entry gate

### 6.1 Evaluation gate

Before reserving a Strategy cycle, the runtime obtains one coherent full OANDA execution-account snapshot and records its bounded observation time/frontier.

The snapshot must prove:

```text
expected account identity
USD currency
coherent Trade/Position counts
coherent transaction frontier
supported normalization
```

It projects:

```text
FinancialPositionState.FLAT
FinancialPositionState.LONG
FinancialPositionState.SHORT
```

A non-flat state may be used for read-only Strategy evaluation only when it is attributable to durable supported PAPER execution truth for the configured account/runtime context.

Unexpected/unattributed exposure is not absorbed into Strategy state.

It blocks.

Expected current exposure does not itself block Strategy evaluation.

### 6.2 Open attributable Trade

When a durable P05 Fill exists and current account facts coherently show its supported direction/exposure:

```text
Strategy evaluates current frontier
with financial_position_state LONG or SHORT
```

No Risk evaluation runs merely to advance Strategy state.

No entry mutation path is reachable.

For the current immediate-entry candidate Strategy, non-flat evaluation is expected to produce `NO_ACTION` and advance the Strategy frontier.

If a Strategy emits a currently unsupported capital action such as:

```text
CLOSE_POSITION
UPDATE_PROTECTION
PRICE_TRIGGERED opening
```

the runtime must not silently reinterpret or ignore that required methodology action.

The cycle records the unsupported decision and the activation becomes `BLOCKED`.

### 6.3 Entry gate

Only after Strategy produces a supported IMMEDIATE opening from a FLAT financial state may the runtime enter the capital-capable branch.

It requires:

```text
the cycle's observed position = FLAT
no locally unsafe unresolved PAPER attempt
```

Then P05 performs fresh independent execution preparation:

```text
fresh Account Properties
fresh full Account Details
fresh instrument facts
fresh executable pricing
fresh Risk evaluation exactly once
```

The runtime cycle's earlier account observation is never reused as Risk authority.

P05 itself requires:

```text
open_trade_count = 0
open_position_count = 0
pending_order_count = 0
```

If fresh P05 preparation disagrees with the earlier Strategy input, no ENTRY claim exists and no mutation occurs.

### 6.4 Previously filled execution

`FILLED_PROTECTED` means historical execution-resolution proof.

It does not mean:

```text
Trade is still open
Trade is now closed
account is flat
protection remains unchanged forever
```

A later fresh coherent account observation governs current Strategy financial-position input.

A new entry is possible only when:

```text
fresh full Account Details proves FLAT
pending_order_count = 0
prior attempt is not UNKNOWN
prior attempt is not unresolved
prior attempt is not conflicted
prior attempt is not protection-incomplete
```

`LIFECYCLE_ADVANCED` alone never proves entry eligibility.

### 6.5 Unsafe execution states

These prevent further capital exposure:

```text
UNKNOWN
FILLED_PROTECTION_INCOMPLETE
reconciliation UNRESOLVED
reconciliation CONFLICT
unattributed exposure
post-claim persistence uncertainty
```

If these states also prevent Atlas from establishing a trustworthy Strategy financial-position input, the activation blocks and Strategy state stops.

That interruption is explicit.

A later new activation may fresh-bootstrap after operator resolution and safe broker truth.

## 7. Runtime cycle ordering and seams

The runtime owns:

```text
activation
ownership
cycle reservation
Strategy-state persistence ordering
orchestration
```

It does not own:

```text
Risk semantics
OANDA payload construction
broker mutation semantics
P05 claim meaning
P05 reconciliation conclusions
```

### 7.1 Startup

```text
1. Load Settings.
2. Create database engine.
3. Check database readiness.
4. Acquire dedicated singleton advisory-lock connection.
5. Lock/update durable ownership row and owner_generation.
6. Find the sole relevant non-terminal activation.
7. If none exists:
       remain idle
       no OANDA call
8. Verify activation immutable configuration.
9. Verify configured account ID/token presence and Strategy registry identity.
10. Transition REQUESTED/RUNNING-interrupted activation to STARTING as appropriate.
11. Inspect interrupted cycles and outstanding P05 attempts.
12. For committed mutation claims without definite durable resolution:
       run one bounded P05 GET-only reconciliation pass
       never POST/PUT
13. If activation is STOP_REQUESTED:
       perform only necessary read-only recovery
       never enter RUNNING
       finalize STOPPED after owner-side drain/recovery bookkeeping
14. For a fresh REQUESTED activation:
       require safe FLAT bootstrap account truth.
15. For interrupted same-session RUNNING:
       require valid durable Strategy state and frontier continuity.
16. Transition to RUNNING only when all required safety facts are durable.
```

### 7.2 Normal tick

```text
RUNNING
    ↓
observe STOP/control version
    ↓
read one current native completed M15 frontier
```

If no new frontier:

```text
WAITING_FRONTIER
sleep 15 seconds
```

If the read temporarily fails before cycle reservation:

```text
WAITING_DATA / WAITING_PROVIDER
no state advancement
no claim
retry normal cadence
```

For one new eligible frontier:

```text
read one coherent current execution-account snapshot
project FinancialPositionState
validate attribution/supported runtime context
```

Temporary read failure before cycle claim:

```text
wait/retry same frontier
```

Semantic conflict:

```text
BLOCKED
```

When inputs are valid:

```text
owner-guarded transaction
    reserve unique cycle
    bind frontier
    bind state_before
    bind financial_position_state
    bind account observation provenance
commit
```

Then:

```text
evaluate exact StrategyVersion
against exact reserved frontier
exact state_before
exact financial_position_state
```

Validate:

```text
receipt identity
next_state type/schema
next_state frontier == cycle.frontier_end
decision vocabulary
```

### 7.3 NO_ACTION

One local transaction:

```text
lock activation/cycle
verify owner generation
verify no STOP invalidates new cycle completion semantics
persist Strategy evaluation
persist decision
persist state_after
advance activation.strategy_state
advance activation.last_frontier_end
cycle → NO_ACTION
commit
```

No Risk.

No P05 attempt.

No broker mutation.

### 7.4 Unsupported decision

If Strategy returns a methodology action outside current runtime capability:

```text
PRICE_TRIGGERED opening
CLOSE_POSITION
UPDATE_PROTECTION
malformed opening
```

persist evaluation evidence without broker mutation.

The activation becomes:

```text
BLOCKED
UNSUPPORTED_STRATEGY_ACTION
```

Do not silently convert it into `NO_ACTION`.

### 7.5 Supported opening

For:

```text
OPEN_LONG / OPEN_SHORT
EntryPolicy.IMMEDIATE
cycle financial_position_state = FLAT
```

P05 performs its fresh preparation.

Expected Risk/account/provider refusal before a mutation claim:

```text
persist evaluation + state_after
cycle → REFUSED
no mutation
continue future frontier when refusal semantics are safe
```

Identity contradiction/invariant failure:

```text
BLOCKED
```

Successful preparation produces:

```text
exact PaperStrategyEvaluationReceipt
PaperRiskAuthoritySnapshot
PaperExecutionAttempt
entry request fingerprint
```

Then one caller-owned local transaction atomically commits:

```text
activation owner/control guard
cycle evaluation evidence
state_after
activation Strategy state/frontier
P05 immutable execution attempt
permanent ENTRY claim
cycle → ENTRY_CLAIMED
```

No broker POST is permitted unless this transaction commits.

P06 may introduce a narrow P05 caller-owned transaction seam.

It must reuse P05 attempt/claim contracts.

It must not duplicate P05 Risk or execution semantics in the runtime layer.

### 7.6 Post-claim entry dispatch

After ENTRY claim commit:

```text
verify the same process still holds valid runtime ownership
```

If ownership is lost:

```text
do not POST
claim remains possible dispatch
recovery is read-only
```

If ownership remains valid:

```text
one existing non-retrying entry POST
```

A STOP that linearized **after** the ENTRY claim does not retroactively erase that already-authorized operation.

The one claimed operation may complete at most once.

### 7.7 Result and protection

P05 persists the entry result.

If:

```text
REJECTED
CANCELLED
```

cycle can resolve without Fill.

If Fill:

```text
persist Fill first
confirm Stop
derive actual target from actual Fill
```

If the same process still owns the already-authorized execution chain, dependent protection belongs to that already-authorized operation.

Therefore a STOP that arrived after the ENTRY claim does **not** deliberately prevent necessary same-process dependent protection.

The same-process chain may:

```text
commit Stop/actual-target evidence
commit permanent TAKE_PROFIT claim
cycle → TAKE_PROFIT_CLAIMED
perform one non-retrying dependent PUT
persist final observations/result
```

This exception does not authorize:

```text
a new entry
a repair
a retry
a restart-time TP mutation
```

If the process crashes before the TP claim:

```text
restart is read-only
no missing TP claim is automatically created
```

If it crashes after TP claim:

```text
restart is read-only
no second PUT
```

## 8. Lifecycle and cycle transition matrices

### 8.1 Activation lifecycle

| Current          | Event / guard                                 | Next                   | Capital behavior                             |
| ---------------- | --------------------------------------------- | ---------------------- | -------------------------------------------- |
| absent           | valid explicit activation                     | `REQUESTED`            | none                                         |
| `REQUESTED`      | STOP wins row lock before runtime start       | `STOPPED`              | none                                         |
| `REQUESTED`      | runtime owns singleton and starts validation  | `STARTING`             | none                                         |
| `STARTING`       | safe bootstrap/recovery complete              | `RUNNING`              | only future claimed cycle                    |
| `STARTING`       | STOP                                          | `STOP_REQUESTED`       | no new ENTRY claim                           |
| `STARTING`       | semantic mismatch/unsafe recovery             | `BLOCKED`              | none                                         |
| `STARTING`       | fatal local error durably recordable          | `FAILED`               | none                                         |
| `RUNNING`        | no new frontier                               | `RUNNING`              | none                                         |
| `RUNNING`        | transient pre-cycle read unavailable          | `RUNNING`              | none                                         |
| `RUNNING`        | valid new frontier                            | `RUNNING`              | one cycle                                    |
| `RUNNING`        | attributable open Trade                       | `RUNNING`              | read-only Strategy cycles; no entry          |
| `RUNNING`        | STOP before next ENTRY claim                  | `STOP_REQUESTED`       | no new entry                                 |
| `RUNNING`        | semantic provider/account/state conflict      | `BLOCKED`              | none                                         |
| `RUNNING`        | owner loss                                    | `BLOCKED` when durable | none                                         |
| `RUNNING`        | fatal local error                             | `FAILED`               | no new operation                             |
| `STOP_REQUESTED` | already-claimed same-process execution drains | `STOP_REQUESTED`       | only already-authorized operation/protection |
| `STOP_REQUESTED` | drain/recovery bookkeeping complete           | `STOPPED`              | none                                         |
| `STOPPED`        | no automatic transition                       | `STOPPED`              | none                                         |
| `BLOCKED`        | no automatic transition                       | `BLOCKED`              | none                                         |
| `FAILED`         | no automatic transition                       | `FAILED`               | none                                         |

### 8.2 Cycle matrix

| Current               | Event                                                               | Next                  | Rule                               |
| --------------------- | ------------------------------------------------------------------- | --------------------- | ---------------------------------- |
| none                  | unique valid frontier/input reservation                             | `CLAIMED`             | owner + continuity + account input |
| `CLAIMED`             | evaluation begins                                                   | `EVALUATING`          | same frontier/state/input          |
| `EVALUATING`          | `NO_ACTION`                                                         | `NO_ACTION`           | state_after atomic                 |
| `EVALUATING`          | safe expected pre-claim refusal                                     | `REFUSED`             | state_after atomic; no mutation    |
| `EVALUATING`          | unsupported methodology action                                      | `BLOCKED`             | do not reinterpret                 |
| `EVALUATING`          | P05 preparation + atomic attempt/claim/state commit                 | `ENTRY_CLAIMED`       | exact receipt/Risk evidence        |
| `EVALUATING`          | fatal/invalid durable input                                         | `BLOCKED`             | no mutation                        |
| `ENTRY_CLAIMED`       | same-process result persists                                        | `ENTRY_RESOLVED`      | observations precede conclusion    |
| `ENTRY_CLAIMED`       | owner loss/process crash                                            | `RECOVERY_REQUIRED`   | never second POST                  |
| `ENTRY_RESOLVED`      | REJECTED/CANCELLED                                                  | `COMPLETE`            | exact no-Fill proof                |
| `ENTRY_RESOLVED`      | Fill + same-process dependent protection claim                      | `TAKE_PROFIT_CLAIMED` | Fill first                         |
| `ENTRY_RESOLVED`      | Fill cannot safely proceed to dependent chain                       | `BLOCKED`             | no repair                          |
| `TAKE_PROFIT_CLAIMED` | same-process PUT/result durable                                     | `COMPLETE`            | P05 outcome                        |
| `TAKE_PROFIT_CLAIMED` | owner loss/process crash                                            | `RECOVERY_REQUIRED`   | never second PUT                   |
| `RECOVERY_REQUIRED`   | bounded reconciliation proves definite safe terminal execution fact | `COMPLETE`            | GET-only                           |
| `RECOVERY_REQUIRED`   | unresolved/conflict/truncated/uncertain                             | `BLOCKED`             | original claim retained            |
| terminal cycle        | replay                                                              | unchanged             | no evaluation/mutation             |

A completed opening cycle does not prevent later analytical `NO_ACTION` cycles while the resulting known Trade remains open.

## 9. Ownership, STOP, restart, and error boundaries

### 9.1 Ownership

Two runtime processes may start.

Only one advisory-lock owner may operate.

Loser:

```text
no cycle
no broker read required
no mutation
RUNTIME_OWNER_PRESENT
```

Concurrent cycle reservation relies on:

```text
activation row guard
owner_generation
unique evaluation/frontier constraints
```

A uniqueness race returns existing durable evidence.

### 9.2 STOP/claim linearization

The activation row lock is the ENTRY STOP linearization boundary.

If STOP commits first:

```text
no new ENTRY claim
no new entry POST
```

If ENTRY claim commits first:

```text
the one already-authorized same-process execution may complete at most once
```

including dependent protection for any resulting Fill.

STOP never permits another cycle.

STOP never means:

```text
cancelled
closed
reversed
unsent
unfilled
```

### 9.3 Restart

| Durable state at process loss                             | Same-activation recovery                                                   |
| --------------------------------------------------------- | -------------------------------------------------------------------------- |
| no activation                                             | idle; no broker call                                                       |
| `REQUESTED`                                               | acquire owner and run startup checks                                       |
| `STARTING` with no claim                                  | revalidate exact session                                                   |
| `RUNNING` idle                                            | exact state/frontier recovery                                              |
| frontier read but no cycle claim                          | may reread                                                                 |
| `CLAIMED` / `EVALUATING` with no durable result           | `RECOVERY_REQUIRED`; never evaluate that claimed frontier again            |
| ENTRY claim committed                                     | reconcile original correlation read-only; never POST                       |
| entry Fill persisted before TP claim                      | preserve Fill; read-only; never create missing TP claim                    |
| TP claim committed                                        | read original Trade/protection only; never PUT                             |
| post-mutation persistence uncertain                       | read-only reconciliation                                                   |
| `UNKNOWN` / conflict / unresolved / protection incomplete | `BLOCKED`                                                                  |
| `STOP_REQUESTED`                                          | no RUNNING transition; read-only recovery/drain bookkeeping then `STOPPED` |
| `BLOCKED` / `FAILED` / `STOPPED`                          | no automatic resume                                                        |

If a same-session restart discovers:

```text
current eligible frontier
>
immediately next frontier after strategy_state
```

the activation blocks with `FRONTIER_GAP`.

A later explicit activation fresh-bootstraps.

### 9.4 Fatal error

Unexpected:

```text
invalid durable state
registry drift
database invariant failure
post-claim local persistence failure
unhandled normalization contradiction
owner loss
```

stops new cycle/ENTRY authority.

When durable writing remains possible:

```text
FAILED
bounded failure code/type
```

Existing P05 claims/outcomes remain unchanged.

No raw body, token, credential, or unbounded exception text is persisted.

Failure to persist `FAILED` is uncertainty, never success.

## 10. Valid, invalid, and boundary examples

### Valid

- Starting runtime with no activation waits locally and never calls OANDA.
- Exact activation retry returns the same durable activation.
- Runtime evaluates a new M15 frontier while account is FLAT and Strategy returns `NO_ACTION`; state advances once.
- Runtime has a known attributable LONG PAPER Trade; next M15 frontier is evaluated with `FinancialPositionState.LONG`; Strategy returns `NO_ACTION`; state advances; no Risk or mutation runs.
- Trade later closes at broker; a fresh coherent Account Details snapshot proves FLAT and zero pending Orders; current Strategy state is still contiguous because read-only cycles continued during the Trade.
- A later supported opening then enters fresh P05 Risk/execution.
- A delayed OANDA candle causes `WAITING_DATA`; no cycle is claimed; if the candle becomes available before the next frontier, it is processed once.
- An exact ENTRY claim commits, then STOP arrives; the already-authorized operation fills and same-process target protection completes once; runtime then stops.
- Restart after a claim performs only bounded P05 reconciliation.

### Invalid

- Non-flat account automatically freezes Strategy evaluation despite known attributable exposure.
- Starting runtime creates activation authority.
- Caller supplies account, Strategy state, RiskDecision, StrategyDecision, attempt ID, or broker payload.
- Same Strategy configuration/frontier evaluates twice.
- Temporary read failure is treated as successful NO_ACTION.
- Wrong account or contradictory exposure is treated as transient.
- Unattributed manual exposure is silently fed into Strategy state.
- `UNKNOWN` permits another entry.
- Permanent claim is interpreted as broker receipt.
- STOP is described as cancellation.
- Runtime restart sends an ENTRY because an ENTRY claim exists.
- Runtime restart creates a missing TAKE_PROFIT claim after Fill.
- `FILLED_PROTECTED` is treated as proof account is flat.
- New activation silently reuses Strategy state from a terminal previous activation.

### Boundary

- One transient read failure within the same M15 frontier is retryable.
- Missing the frontier entirely is not retryable state continuation; the same activation blocks.
- New explicit activation after that block starts fresh rather than silently catching up.
- OPEN Trade with known current exposure permits Strategy evaluation but never new entry.
- ENTRY claim before STOP authorizes at most that one same-process execution chain.
- STOP before ENTRY claim prevents entry.
- Process crash converts every committed mutation claim into read-only recovery authority.
- Separate account/frontier reads are not claimed to be atomic.
- P05's later fresh execution account read may invalidate an earlier Strategy-cycle FLAT observation; the later P05 gate wins for mutation authority.

## 11. Exclusions

PAPER 06 does not add:

```text
LIVE
non-Practice operation
automatic activation

broker credential persistence
credential editing

multiple accounts
multiple instruments
multiple active Strategies

distributed workers
queues
generic scheduler infrastructure
leader-election service

automatic historical catch-up
historical missed-signal execution
automatic cross-session state continuation

entry retry
Take Profit retry after restart
cancel
close
reduce
protection repair

partial-fill accounting
multi-fill accounting
PAPER PnL
closed-Trade accounting
portfolio management

WebSockets
streaming runtime
global transaction cursor
unbounded synchronization

Strategy SDK
general Strategy-authoring redesign

real broker mutation testing
```

## 12. Required validation evidence

### 12.1 Deterministic runtime/service tests

Required coverage includes:

```text
strict activation schema
confirmation requirement
exact parameter validation
Risk decimal validation
same-ID idempotency
same-ID identity conflict
single non-terminal activation

no activation → no OANDA action
local authority enforcement
no token/raw-provider leakage

fresh bootstrap only for new activation
same-activation restart exact state restoration
no automatic cross-activation state import

M15 cutoff semantics
duplicate frontier
future/forming frontier
session closure handling
frontier continuity
missed-frontier block

temporary pre-cycle provider failure waits/retries same frontier
semantic malformed/identity contradiction blocks
provider delay that resolves before next frontier evaluates once

FLAT Strategy evaluation
known attributable LONG Strategy evaluation
known attributable SHORT Strategy evaluation
state frontier advances while Trade is open
open exposure prevents entry
unattributed exposure blocks
flat + unsafe account state prevents entry

cycle evidence includes exact FinancialPositionState
cycle account input provenance is bounded and immutable

same evaluation key/frontier never evaluates twice
NO_ACTION state/cycle atomicity

unsupported PRICE_TRIGGERED/CLOSE/UPDATE action blocks without mutation

P05 fresh Risk exactly once
runtime does not reuse earlier account gate as Risk authority

pre-claim expected refusal
pre-claim local commit failure → zero broker mutation

atomic cycle/state/P05 attempt/ENTRY claim
rollback leaves no partial authority

STOP before ENTRY claim
ENTRY claim before STOP
STOP during entry network call
STOP after Fill before dependent target composition
already-authorized protection may complete same-process
no new cycle after STOP

owner-generation loss before claim
owner loss after claim before network
owner loss before dependent mutation

crash before/after:
cycle claim
Strategy evaluation persistence
ENTRY claim
POST
entry result
Fill
TP claim
PUT
final persistence

restart never POSTs
restart never PUTs
restart never creates missing TP claim

P05 five execution outcomes
P05 reconciliation statuses
Fill non-erasure
historical FILLED_PROTECTED preservation
LIFECYCLE_ADVANCED not flat proof

status projection separates:
runtime lifecycle
operational phase
current financial position
execution outcome
reconciliation status
```

### 12.2 PostgreSQL integration tests

Dedicated `*_test` database:

```text
upgrade head
downgrade prior head
upgrade head
alembic current
alembic check

runtime table constraints
immutable activation configuration
bounded JSON
finite risk
valid fingerprints
single non-terminal activation

two concurrent activation requests
same-ID replay conflict

dedicated advisory lock connection
two runtime sessions → exactly one owner
stale heartbeat cannot steal live lock
lock release after connection death permits one successor

owner_generation guarded updates
owner-loss zero-row transition

cycle immutable identity
unique evaluation_key/frontier
concurrent cycle reservation
monotonic cycle sequence

financial-position/account-input evidence constraints

NO_ACTION state/cycle transaction rollback

ENTRY transaction atomicity:
cycle
state_after
P05 attempt
ENTRY claim

rollback proves no partial P05/cycle authority

STOP/ENTRY claim row-lock race

P05 existing:
claim uniqueness
append-only observations
Fill non-erasure
stale reconciliation protection

restart fixture rows for every in-flight status
```

### 12.3 Safe completion gates

Run:

```text
focused PAPER 06 runtime tests
focused Strategy/PAPER/Risk/OANDA regressions
PostgreSQL migration/concurrency suite
broad backend:
pytest -m 'not integration and not external'
changed-slice Ruff
changed-slice Pyright
Alembic current/check on dedicated test database
git diff --check
```

Frontend gates only if frontend code is explicitly approved in later task scope.

No validation gate authorizes:

```text
actual PAPER activation
real OANDA mutation
capital-capable credentials
LIVE
```

## 13. Freeze decisions

These are architectural invariants:

```text
explicit local activation is durable and exact

process liveness never creates activation authority

one dedicated PostgreSQL advisory-lock owner
plus guarded durable ownership projection

new activation = fresh Strategy bootstrap

same non-terminal activation restart = exact durable state resume

no automatic cross-session state seeding

no automatic missed-frontier catch-up

one unique cycle per exact Strategy configuration/frontier

Strategy evaluation gate is separate from entry gate

known attributable open exposure may continue read-only Strategy state advancement

new entry requires fresh FLAT + zero-pending P05 authority

financial_position_state is durable Strategy-cycle input evidence

transient pre-claim observation unavailability may wait/retry the same frontier

semantic contradiction and post-claim uncertainty fail closed

Strategy state advances only with durable cycle evidence

PAPER 05 is the only capital-capable execution authority

permanent claims mean possible dispatch, not broker receipt

restart after a mutation claim is read-only

STOP fences new cycles and new ENTRY claims

an ENTRY operation that linearized before STOP may complete its same-process
dependent protection chain at most once

STOP is not broker cancellation

owner loss removes mutation authority

UNKNOWN / conflict / unresolved / protection incomplete never permit new entry

FILLED_PROTECTED remains historical execution truth

LIFECYCLE_ADVANCED never proves flatness

status reports runtime truth and broker truth separately
```

No BUILD task or implementation is authorized until this architecture and the canonical PLAN are explicitly approved together.
