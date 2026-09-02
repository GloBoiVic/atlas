# PAPER 05 Persistence + Reconciliation Architecture

**Workstream:** `paper-05-persistence-reconciliation`
**Classification:** Critical
**Status:** Architecture freeze candidate; pre-approval
**Scope:** One OANDA Practice `EUR_USD` account, one immediate `OPEN_LONG` or `OPEN_SHORT` execution attempt

This document freezes the smallest durable PAPER slice. It authorizes no branch creation, implementation, PAPER activation, credentialed broker call, or capital exposure.

## 1. Architectural decisions

1. PAPER 05 adds a durable PAPER execution ledger around the existing PAPER 04 instruction/result semantics. It does not turn historical Experiment rows into broker truth.
2. `attempt_id` remains the identity of one logical PAPER execution attempt. It is allocated before mutation and is never replaced after restart, timeout, uncertain transport, or reconciliation. PAPER 04's deterministic client IDs remain aliases of that identity.
3. The durable capital-capable path must consume a Strategy evaluation receipt produced by the verified PAPER Strategy evaluation boundary. It must not accept an arbitrary `StrategyDecision` paired with independently supplied StrategyVersion/parameter metadata.
4. The same fresh PAPER Risk composition used for mutation must produce the durable Risk authority evidence. PAPER 05 does not call Risk twice and does not treat persisted Risk evidence as future mutation authority.
5. Strategy authority, Risk authority, broker facts, and Atlas conclusions remain separate:

   - Strategy proposes;
   - Risk authorizes/sizes;
   - OANDA-normalized broker facts establish actual broker events;
   - PAPER persistence records those facts and derives bounded conclusions.

6. Broker observations are append-only. Proven Fill facts are immutable. The five PAPER 04 outcomes are execution-resolution facts, not an ongoing Trade lifecycle state.
7. Reconciliation status is separate from execution outcome. A later closed Trade or changed protection state cannot retroactively erase the fact that Atlas previously proved a protected Fill.
8. There are two permanent possible-mutation barriers:

   - `ENTRY`
   - `TAKE_PROFIT`

   Each is committed before its corresponding broker mutation becomes possible.

9. A mutation claim does not prove the HTTP request was sent or received. It proves only that Atlas must conservatively treat that mutation as possibly dispatched and must never automatically submit it again.
10. Mutation claims have no lease, expiry, ownership transfer, or reacquisition. After a claim exists, restart recovery is read-only.
11. Reconciliation is finite and read-only. It may observe and classify; it may not resubmit, cancel, close, reduce, replace, or repair any broker object.
12. PAPER 05 adds only one missing OANDA recovery read capability beyond PAPER 04: a bounded numeric Transaction-ID range query anchored to the pre-entry account frontier. It does not add open-ended transaction synchronization or polling.
13. The implementation must expose explicit durable commit seams immediately before both broker mutations. It must not place database transaction ownership inside the generic OANDA HTTP requester and must not claim broker/database atomicity.

## 2. Repository-grounded facts

The current PAPER 04 implementation provides:

```text
PaperExecutionInstruction
PaperExecutionResult
PaperExecutionOutcome =
    FILLED_PROTECTED
    | FILLED_PROTECTION_INCOMPLETE
    | REJECTED
    | CANCELLED
    | UNKNOWN

ExecutionCorrelation
BrokerFillFacts
ProtectionConfirmation
TransactionProvenance
```

`PaperExecutionInstruction` contains:

```text
attempt_id
StrategyDecision
account identity
instrument/direction
requested quantity
approved Risk entry price
Strategy stop
decision/pricing times
PRE_FLIGHT RiskDecision
PRE_SUBMISSION RiskDecision
observation provenance
provider display/trade-unit precision
```

and deterministically exposes:

```text
atlas-p04-o-<attempt_hex>
atlas-p04-t-<attempt_hex>
atlas-p04-sl-<attempt_hex>
atlas-p04-tp-<attempt_hex>
```

PAPER 04's application currently performs:

```text
account properties
→ coherent full Account Details
→ execution instrument metadata
→ current pricing
→ evaluate_paper_risk(...) exactly once
→ PaperExecutionInstruction
→ pure OANDA entry translation validation
→ entry mutation
→ optional protection completion
```

`PaperExecutionApplication` has no persistence state.

The current PAPER Strategy path:

```text
evaluate_current_paper_strategy(...)
```

loads the exact persisted `StrategyVersion`, verifies local registry metadata, validates the supplied parameters, evaluates the current analytical frontier, and returns a `StrategyEvaluation`.

`StrategyEvaluation` contains:

```text
decision
next_state
```

but does not retain:

```text
StrategyVersion identity
source fingerprint
implementation key
validated parameter snapshot
```

`StrategyDecision` itself deliberately contains no version identity.

Therefore a separate provenance object supplied beside an arbitrary `StrategyDecision` is insufficient: it could be valid provenance for one methodology while the decision came from another evaluation.

The durable execution path must close that handoff structurally.

The current PAPER Risk result contains:

```text
strategy_decision
trade_intent
PRE_FLIGHT
PRE_SUBMISSION
observation provenance
pricing evidence
```

and its sizing depends on `RiskConfig.risk_per_trade`, account equity, flat financial exposure, stop geometry, and selected executable capacity.

`PaperExecutionInstruction` does not by itself retain every normalized Risk input needed to explain why the quantity was authorized.

PAPER 05 therefore retains a bounded snapshot of the same fresh Risk evaluation and its inputs before mutation.

Relevant existing OANDA seams are:

```text
OandaObservationRequester
    GET-only
    safely retrying

OandaPracticeEntryMutation
    one non-retrying entry POST
    bounded uncertain-entry readback

OandaPracticeProtectionCompletion
    Stop confirmation
    actual-Fill target resolution
    one non-retrying Take Profit PUT
    final Trade readback

OandaPracticeEntryReadbackReader
    exact Order by client ID
    exact Transaction
    exact Trade

OandaProtectionReadbackReader
    exact Trade

OandaPracticeExecutionAccountReader
    coherent full Account Details
```

OANDA additionally exposes:

```text
GET /v3/accounts/{accountID}/transactions/idrange
```

with explicit `from` and `to` Transaction IDs.

That capability is required only for bounded lost-response recovery where an entry rejection or other transaction may exist but no Order resource can be found.

The historical persistence graph:

```text
Experiment
TradeIntent
RiskDecision
Order
Fill
Position
Trade
OrderEvent
...
```

remains deterministic historical simulation evidence.

PAPER 05 does not import, update, adapt, or link those historical trading rows as PAPER broker truth.

The current Alembic head is revision:

```text
0021_experiment_deletion
```

from `0021_experiment_deletion_lifecycle.py`.

PAPER 05's migration must be a child of the actual current head at implementation time.

## 3. Strategy evaluation receipt and durable identity

### 3.1 Strategy evaluation receipt

Add a provider-neutral immutable receipt at the PAPER Strategy boundary, for example:

```text
PaperStrategyEvaluationReceipt
```

Exact naming may vary.

It contains at minimum:

```text
strategy_version_id
strategy_key
version_number
source_fingerprint
implementation_key
validated_parameter_snapshot
StrategyEvaluation
```

The receipt must be produced by the same validated operation that loads the exact persisted StrategyVersion, validates the parameters, and evaluates the Strategy.

The implementation may refactor the current PAPER Strategy evaluation internally so that:

```text
evaluate_current_paper_strategy(...)
```

retains its existing public behavior, while a companion execution-oriented seam returns the richer receipt.

The receipt's executable decision is always:

```text
receipt.evaluation.decision
```

PAPER 05 must not expose a capital-capable coordinator that accepts both:

```text
receipt
+
independent StrategyDecision
```

The repository reloads `strategy_version_id` and verifies:

```text
strategy_key
version_number
source_fingerprint
implementation_key
parameter contract
validated parameter snapshot
```

before the entry mutation claim is committed.

The durable evidence may retain `StrategyEvaluation.to_json()`, including `next_state`.

That persisted next state is evidence of the evaluation only.

It is not PAPER runtime state authority, activation state, or restart/resumption policy.

### 3.2 Attempt identity

`attempt_id` is the UUID primary identity of one logical execution attempt.

The deterministic client aliases remain exactly:

```text
atlas-p04-o-<attempt_hex>
atlas-p04-t-<attempt_hex>
atlas-p04-sl-<attempt_hex>
atlas-p04-tp-<attempt_hex>
```

The aliases are unique durable fields.

Reusing an existing `attempt_id` is allowed only to:

```text
load the existing durable attempt
return its durable result
request read-only reconciliation
```

A call that presents the same `attempt_id` with different immutable Strategy, Risk, instruction, account, quantity, Stop, correlation, or precision facts is an identity conflict and cannot mutate the broker.

A new independently authorized logical attempt requires a new UUID.

The supported identity remains fixed to:

```text
provider = OANDA
environment = PRACTICE
provider_account_id = configured USD account
instrument = EUR_USD
entry_policy = IMMEDIATE
action = OPEN_LONG or OPEN_SHORT
```

## 4. Durable Risk authority

Add a bounded provider-neutral immutable value, for example:

```text
PaperRiskAuthoritySnapshot
```

Exact naming may vary.

It is produced from the same already-computed fresh `PaperRiskEvaluation` that creates the PAPER 04 instruction.

It contains enough canonical normalized facts to explain the decision, at minimum:

```text
RiskConfig
    risk_per_trade

Risk input account facts
    base_currency
    equity

financial exposure state used by Risk
    FLAT for this supported entry slice

Strategy Risk geometry
    direction
    stop
    TargetProposal identity/value

PRE_FLIGHT RiskDecision
PRE_SUBMISSION RiskDecision

executable-pricing evidence
    required side
    normalized candidate price/capacity evidence
    selected candidate
    per-candidate Risk disposition required to explain selection

observation provenance
    account identity
    account transaction frontier
    pricing time
    execution instrument transaction frontier
```

The exact serializer must:

```text
use canonical Atlas values
exclude raw OANDA payloads
exclude credentials
exclude unbounded provider error text
have an explicit schema version
have bounded keys/collection sizes/serialized size
```

If the exact fresh Risk evidence cannot be represented by the durable contract, execution refuses before an `ENTRY` mutation claim exists.

The serializer must not change candidate selection or call Risk again.

The persisted Risk decisions remain evidence of the original authoritative decisions.

They are never replayed as authority for a later broker mutation.

## 5. PAPER-specific durable shape

Use a PAPER-specific persistence module and a separate:

```text
PaperExecutionRepository
```

Exact module filenames may vary.

The smallest durable slice uses four conceptual tables:

```text
paper_execution_attempts
paper_mutation_claims
paper_broker_observations
paper_reconciliation_runs
```

Do not add a generic event-sourcing framework or separate findings subsystem unless implementation proves a concrete requirement that cannot be represented by the bounded reconciliation-run contract below.

### 5.1 `paper_execution_attempts`

One row owns the immutable execution evidence plus the guarded current execution-resolution/reconciliation projection.

#### Immutable Strategy/Risk/instruction evidence

At minimum:

```text
attempt_id PK

strategy_version_id FK → strategy_versions.id ON DELETE RESTRICT
strategy_key
strategy_version_number
source_fingerprint
implementation_key
validated_parameter_snapshot
strategy_evaluation_snapshot

risk_authority_snapshot

strategy_decision
pre_flight_risk_decision
pre_submission_risk_decision

provider
environment
provider_account_id
base_currency
instrument
direction

requested_quantity
approved_entry_price
stop_price
decision_time
pricing_time

account_transaction_id
instrument_transaction_id

display_precision
trade_units_precision

client_order_id
client_trade_id
client_stop_loss_order_id
client_take_profit_order_id

created_at
```

The typed duplicate fields are intentional where they support constraints, indexing, exact comparison, and reconciliation.

Canonical JSON snapshots are bounded/versioned evidence, not arbitrary payload storage.

#### Proven Fill facts

```text
fill_broker_order_id
fill_transaction_id
fill_trade_id
fill_signed_units
fill_price
fill_executed_at
fill_actual_initial_risk
```

Fill is all-or-none.

Once any Fill exists, the complete Fill set is immutable.

No later conclusion may null, replace, or rewrite it.

#### Protection/execution resolution facts

```text
actual_target_price

stop_loss_status
stop_loss_broker_order_id
stop_loss_client_order_id
stop_loss_price
stop_loss_provider_state

take_profit_status
take_profit_broker_order_id
take_profit_client_order_id
take_profit_price
take_profit_provider_state

execution_outcome
rejection_code
rejection_broker_order_id
rejection_transaction_id
uncertainty_code
```

`execution_outcome` is nullable only before the original mutation result has been durably resolved/recorded.

When non-null it is one of:

```text
FILLED_PROTECTED
FILLED_PROTECTION_INCOMPLETE
REJECTED
CANCELLED
UNKNOWN
```

#### Reconciliation projection

Keep reconciliation truth separate:

```text
reconciliation_status
    NOT_RUN
    CONSISTENT
    UNRESOLVED
    CONFLICT
    LIFECYCLE_ADVANCED

reconciliation_block_code
last_reconciliation_run_id
last_reconciled_at
last_applied_transaction_id
projection_version
updated_at
```

`reconciliation_status` does not authorize trading.

`LIFECYCLE_ADVANCED` means the broker Trade has progressed outside the narrow open-entry/protection state PAPER 05 models—for example a previously protected Trade is now closed.

It does not mean Atlas has modeled the close, realized PnL, or current flatness.

#### Database safety

Required constraints/guards include:

```text
fixed OANDA / PRACTICE / USD / EUR_USD scope

positive finite financial values

unique four client correlation IDs

all-or-none Fill facts

FILLED_PROTECTED
    => Fill exists
    and Stop CONFIRMED
    and Take Profit CONFIRMED
    and actual target exists

FILLED_PROTECTION_INCOMPLETE
    => Fill exists

REJECTED
    => no Fill at the moment that outcome is first established

CANCELLED
    => no Fill at the moment that outcome is first established

UNKNOWN
    => no Fill

filled execution outcome
    can never transition to UNKNOWN / REJECTED / CANCELLED

Fill columns
    can never be deleted or changed

immutable Strategy/Risk/instruction facts
    can never be updated
```

A later extraordinary provider contradiction that proves an attributable Fill after an earlier rejection/cancellation must preserve the old reject/cancel observation, append the new Fill observation, advance the execution outcome to a filled outcome, and mark reconciliation `CONFLICT`.

Broker exposure truth takes precedence over preserving a mistaken no-Fill projection.

The database trigger/guard is the final safety net.

Provider interpretation remains in typed application/provider code.

### 5.2 `paper_mutation_claims`

This append-only table is the permanent possible-mutation barrier.

Fields:

```text
claim_id PK
attempt_id FK
phase = ENTRY | TAKE_PROFIT
claimed_at
provider_endpoint_key
normalized_request_fingerprint
```

Hard constraint:

```text
UNIQUE(attempt_id, phase)
```

A claim is inserted and committed before its mutation becomes possible.

The row is never:

```text
updated
deleted
expired
transferred
reacquired
```

Do not call this row proof that a mutation was submitted.

Its semantic meaning is:

> Atlas has crossed the durable point after which this mutation must be treated as possibly dispatched.

Provider request IDs and broker results belong to broker observations.

No `claim_token`, lease owner, expiry timestamp, or ownership-transfer abstraction is required for this slice.

### 5.3 `paper_broker_observations`

Every retained provider fact is append-only and normalized.

It is not an Atlas conclusion.

Use finite current-slice observation/read kinds rather than inventing a general future broker event platform.

Each row contains at minimum:

```text
observation_id PK
attempt_id FK
mutation_claim_id nullable FK
reconciliation_run_id nullable FK

observation_sequence

read_kind
    ENTRY_MUTATION_RESPONSE
    TAKE_PROFIT_MUTATION_RESPONSE
    ORDER_DETAIL
    TRANSACTION_DETAIL
    TRANSACTION_RANGE
    TRADE_DETAIL
    ACCOUNT_DETAILS

object_kind
    ORDER
    TRANSACTION
    TRADE
    ACCOUNT
    MUTATION_RESULT

provider
environment
provider_account_id
instrument nullable

provider_order_id nullable
provider_transaction_id nullable
provider_trade_id nullable

client_order_id nullable
client_trade_id nullable
client_protection_order_id nullable

provider_type nullable
provider_state nullable
signed_units nullable
price nullable
executed_at nullable

request_id nullable
batch_id nullable
related_transaction_ids
last_transaction_id nullable

provider_observed_at nullable
atlas_observed_at

normalized_schema_version
normalized_facts
normalized_facts_fingerprint
```

The normalized facts envelope:

```text
has a finite key set per object/read kind
is versioned
is size-bounded
contains only whitelisted normalized provider facts
contains no credentials
contains no raw HTTP body
contains no arbitrary provider error text
```

Facts used to change execution resolution must also be represented in typed validated values before the projection changes.

A replay of the same normalized provider fact must be idempotent.

A later changed provider state creates a new observation instead of overwriting history.

### 5.4 `paper_reconciliation_runs`

One append-only row summarizes one explicit bounded reconciliation request.

It contains:

```text
run_id PK
attempt_id FK
run_sequence

requested_at
read_started_at
completed_at

status
    PROVEN
    UNRESOLVED
    CONFLICT
    LIFECYCLE_ADVANCED
    FAILED

projection_version_observed
projection_version_applied nullable

read_count
read_budget

frontier_before
frontier_observed
frontier_applied nullable

non_atomic_read_set

prior_execution_outcome
resulting_execution_outcome

finding_codes
diagnostic_summary

created_at
```

`finding_codes` is a bounded finite canonical set/array.

Required codes include, as applicable:

```text
ENTRY_FILLED
ENTRY_REJECTED
ENTRY_CANCELLED
PROTECTION_CONFIRMED
PROTECTION_INCOMPLETE
ENTRY_READBACK_NOT_FOUND
TRANSACTION_RANGE_TRUNCATED
UNRESOLVED
CONFLICT
UNATTRIBUTED_EXPOSURE
TRADE_LIFECYCLE_ADVANCED
PROTECTION_DRIFT
STALE_RECONCILIATION
```

No separate generic findings table is required for the smallest slice.

Provider observations linked to the run contain the detailed evidence.

A reconciliation run performs network GETs before its final short application transaction.

When applying a run, the repository:

1. locks the attempt row;
2. verifies that `projection_version` still equals the version observed when the run began;
3. appends/associates the validated observations;
4. applies only a valid execution-resolution/reconciliation transition;
5. advances the projection version and applicable transaction frontier;
6. commits.

If the projection changed meanwhile, the run becomes stale and cannot overwrite newer truth.

A new explicit reconciliation request may read again.

No broker mutation is permitted.

## 6. Commit boundaries and mutation protocol

The network and database are deliberately not one transaction.

### 6.1 Preparation seam

PAPER 05 requires a narrow refactor of the existing one-shot P04 composition so the durable coordinator can obtain the complete pre-entry facts **before** mutation.

The preparation result contains at least:

```text
Strategy evaluation receipt
fresh PaperRiskEvaluation
PaperRiskAuthoritySnapshot
PaperExecutionInstruction
execution instrument metadata
pure validated OANDA entry request representation/fingerprint
```

The current public PAPER 04 behavior may remain as a compatibility composition over the narrower internal seams.

The refactor must not change:

```text
Strategy semantics
fresh-read sequence
exactly-one Risk evaluation
Risk candidate selection
entry priceBound
requested quantity
Stop
MARKET / FOK / OPEN_ONLY
precision rules
OANDA client correlation
Fill truth
mutation retry behavior
```

### 6.2 Entry

1. Obtain one validated Strategy evaluation receipt.
2. Perform the existing fresh P04 account/instrument/pricing reads.
3. Run `evaluate_paper_risk(...)` exactly once.
4. Build the exact `PaperExecutionInstruction`.
5. Purely validate/translate the OANDA entry payload.
6. Build the canonical Strategy receipt snapshot and Risk authority snapshot.
7. Verify all durable evidence is exactly representable.
8. In one local database transaction:

   - insert the immutable attempt;
   - insert the permanent `ENTRY` mutation claim with the exact normalized request fingerprint;
   - commit.

9. If that commit fails, no broker mutation is permitted.
10. Outside the database transaction, invoke the existing non-retrying OANDA entry mutation exactly once.
11. In a new database transaction:

- append all normalized mutation/readback observations first;
- if a Fill is proven, persist the complete immutable Fill first;
- apply the bounded execution outcome;
- commit.

If the process dies after step 8, Atlas cannot prove whether step 10 occurred.

Therefore:

```text
no second entry POST
no claim reacquisition
no new attempt identity as automatic recovery
read-only reconciliation only
```

The claim is conservative by design.

### 6.3 Post-Fill protection preparation

A broker-confirmed Fill must be durably committed before PAPER 05 allows any dependent Take Profit mutation.

After Fill persistence, preserve PAPER 04's sequence:

```text
GET Trade
→ prove Trade OPEN
→ prove exact ordinary Stop Loss PENDING
→ resolve actual-fill target
→ validate exact target precision
```

PAPER 05 requires a narrow seam between:

```text
target successfully prepared
```

and:

```text
Take Profit PUT
```

The preparation result contains at minimum:

```text
Fill identity
confirmed Stop facts
actual_target
pure validated OANDA Take Profit request fingerprint
```

This may be implemented by splitting the current protection completion internally into preparation and mutation/final-readback stages, while preserving the current public composition.

The database must not be called from the generic OANDA HTTP requester.

### 6.4 Dependent Take Profit

Before the PUT, in one database transaction:

```text
verify immutable Fill
persist the confirmed Stop observation/projection
persist exact actual_target
insert permanent TAKE_PROFIT mutation claim
    with exact request fingerprint
commit
```

Only after that commit may the one non-retrying Take Profit PUT occur.

Then in another transaction:

```text
append normalized mutation result
append final Trade readback
apply bounded execution outcome
commit
```

If the process dies after the TAKE_PROFIT claim but before/after the PUT:

```text
never issue a second PUT
reconcile by reading the original Trade
```

If later readback proves the exact expected Take Profit with the deterministic client ID and actual-fill-derived target, the original execution may advance from:

```text
FILLED_PROTECTION_INCOMPLETE
```

to:

```text
FILLED_PROTECTED
```

without another mutation.

If the target remains absent/rejected/wrong/unproven, the original execution remains protection-incomplete and reconciliation records the current status.

No repair is permitted.

## 7. Execution outcome and reconciliation state machines

### 7.1 Execution outcome

The five PAPER 04 outcomes describe the original entry/protection attempt.

Allowed proof-driven advancements:

| Current execution outcome      | Valid next execution outcome                                                   | Required proof                                                     |
| ------------------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `NULL` / claimed               | `UNKNOWN`                                                                      | Mutation may have occurred but terminal broker truth is not proven |
| `NULL` / claimed               | `REJECTED`                                                                     | Attributable broker reject and no Fill                             |
| `NULL` / claimed               | `CANCELLED`                                                                    | Attributable FOK cancellation and no Fill                          |
| `NULL` / claimed               | `FILLED_PROTECTION_INCOMPLETE`                                                 | Attributable valid Fill; full protection not yet proven            |
| `NULL` / claimed               | `FILLED_PROTECTED`                                                             | Attributable valid Fill plus exact confirmed Stop and Take Profit  |
| `UNKNOWN`                      | same, `REJECTED`, `CANCELLED`, or either filled outcome                        | New bounded provider proof                                         |
| `REJECTED`                     | same, or filled outcome only under later contradictory attributable Fill proof | Preserve reject observation; mark reconciliation conflict          |
| `CANCELLED`                    | same, or filled outcome only under later contradictory attributable Fill proof | Preserve cancel observation; mark reconciliation conflict          |
| `FILLED_PROTECTION_INCOMPLETE` | same or `FILLED_PROTECTED`                                                     | Fill never erased; promotion requires exact protection proof       |
| `FILLED_PROTECTED`             | `FILLED_PROTECTED` only                                                        | Historical proof is never retroactively downgraded                 |

Never permit:

```text
filled outcome → UNKNOWN
filled outcome → REJECTED
filled outcome → CANCELLED
FILLED_PROTECTED → FILLED_PROTECTION_INCOMPLETE
```

A later broker lifecycle change belongs to reconciliation status.

### 7.2 Reconciliation status

Separate status:

```text
NOT_RUN
CONSISTENT
UNRESOLVED
CONFLICT
LIFECYCLE_ADVANCED
```

Examples:

```text
FILLED_PROTECTED + same open Trade + exact pending protections
    → CONSISTENT

FILLED_PROTECTED + Trade now CLOSED
    → LIFECYCLE_ADVANCED
    execution_outcome remains FILLED_PROTECTED

FILLED_PROTECTED + Trade still OPEN but expected Stop unexpectedly missing
    → CONFLICT
    execution_outcome remains FILLED_PROTECTED

FILLED_PROTECTION_INCOMPLETE + Trade OPEN + exact expected target now proven
    → execution_outcome advances to FILLED_PROTECTED
    reconciliation_status = CONSISTENT

UNKNOWN + no attributable terminal found within bounded reads
    → execution_outcome remains UNKNOWN
    reconciliation_status = UNRESOLVED
```

`LIFECYCLE_ADVANCED` does not claim:

```text
which protection fired
realized PnL
current accounting truth
flatness
```

Those are outside PAPER 05.

## 8. Bounded read-only reconciliation

All provider reads are GET-only.

GET retries remain bounded inside the existing safe observation requester.

A reconciliation request has an explicit finite read budget.

No open-ended polling is introduced.

Separate GETs are retained as separate observations with separate frontiers.

### 8.1 `UNKNOWN` / entry-claim reconciliation

Use the original deterministic client Order ID.

#### Primary exact path

```text
1. GET exact Order by @client_order_id

2. If the matching terminal Order references:
      fillingTransactionID
      cancellingTransactionID
   GET that exact Transaction

3. If an attributable Fill is proven:
      persist Fill first
      GET exact Trade detail
```

An exact Order 404/not-found proves only that this read did not return the Order.

It does not prove rejection, cancellation, flatness, or that the request never reached OANDA.

#### Safety/account frontier path

When no attributable Fill/terminal has yet been established:

```text
4. GET one full Account Details snapshot
```

Use it to retain:

```text
current account transaction frontier
current Trades
current Positions
current pending Orders
```

and detect account state that cannot be attributed to the attempt.

The Account Details read is safety evidence.

It is not proof that the entry was rejected.

#### Bounded transaction-range recovery

When the exact Order path does not prove a terminal result, PAPER 05 may inspect one finite Transaction-ID range.

Anchor:

```text
from = numeric(pre_entry_account_transaction_id) + 1
```

Upper observation frontier:

```text
current_frontier = numeric(Account Details lastTransactionID)
```

Freeze a small implementation constant such as:

```text
MAX_ENTRY_RECONCILIATION_TRANSACTIONS
```

The exact value is an implementation constant covered by tests, not a runtime tuning or scheduler setting.

Read at most:

```text
to = min(
    current_frontier,
    pre_entry_frontier + MAX_ENTRY_RECONCILIATION_TRANSACTIONS,
)
```

through:

```text
GET /v3/accounts/{accountID}/transactions/idrange
```

Do not use an unbounded `sinceid` query.

If:

```text
current_frontier > pre_entry_frontier + MAX_ENTRY_RECONCILIATION_TRANSACTIONS
```

record:

```text
TRANSACTION_RANGE_TRUNCATED
```

and remain unresolved unless an attributable terminal is already proven.

Within the bounded range, inspect only the finite OANDA transaction types required by this slice:

```text
MARKET_ORDER
MARKET_ORDER_REJECT
ORDER_FILL
ORDER_CANCEL
```

and directly related supported transaction lineage.

Strict attribution requires all applicable available facts to match the original attempt:

```text
account
EUR_USD
deterministic client Order/Trade IDs
signed requested units
MARKET
FOK
OPEN_ONLY
exact priceBound
expected Stop-on-Fill identity/price where present
batch/order/fill/cancel relationships
```

A matching `MARKET_ORDER_REJECT` can prove `REJECTED` even when no Order resource exists.

A matching create/fill chain can prove Fill.

A matching create/cancel chain can prove `CANCELLED`.

Absence from the bounded range proves nothing.

Unrecognized or contradictory transactions remain unresolved/conflicted.

#### Account exposure

After all observations are normalized, determine whether current account exposure/pending Orders can be attributed to the known attempt.

If additional or unexplained exposure remains:

```text
UNATTRIBUTED_EXPOSURE
reconciliation_status = CONFLICT
```

If an attributable Fill is discovered, persist it before any protection interpretation.

Never erase the Fill afterward.

### 8.2 Known Fill / protection-incomplete reconciliation

Use the durable broker Trade ID for one bounded Trade-detail GET.

For an OPEN Trade, require exact attempt attribution:

```text
account
EUR_USD
Trade ID
client Trade ID
signed units consistent with the proven Fill/current supported slice
actual entry price
```

Classify the expected ordinary Stop and Take Profit independently by:

```text
Trade ID
deterministic client Order ID
order type
exact price
GTC
provider state
```

For an initially protection-incomplete attempt:

```text
both exact expected legs PENDING
and expected target was previously prepared/claimed
    → may advance execution outcome to FILLED_PROTECTED
```

A target appearing without Atlas's durable `TAKE_PROFIT` claim is not silently adopted as Atlas's intended protection.

Treat it as conflict/unattributed broker state.

Missing/rejected/wrong/unproven protection leaves the execution outcome protection-incomplete and records the reconciliation result.

No repair request is created.

### 8.3 Previously `FILLED_PROTECTED`

Read the known Trade.

If the Trade remains OPEN and exact protections remain pending:

```text
CONSISTENT
```

If the Trade is now CLOSED or otherwise clearly progressed beyond this slice:

```text
LIFECYCLE_ADVANCED
```

Keep:

```text
execution_outcome = FILLED_PROTECTED
Fill facts unchanged
original protection proof unchanged
```

PAPER 05 does not infer which exit occurred unless a future approved capability models that lifecycle.

If the Trade is still OPEN but exact expected protection is unexpectedly absent/changed:

```text
CONFLICT
```

Again, keep the original execution outcome and append the new broker observation.

Do not repair.

### 8.4 Missing/changed known Trade

A missing Trade, unexpected units, unexpected identity, malformed object, or provider state that cannot be safely classified must not be translated into `UNKNOWN` entry truth.

The Fill remains proven.

Record:

```text
CONFLICT
```

or:

```text
LIFECYCLE_ADVANCED
```

only when the provider facts actually support that distinction.

Otherwise remain blocked/unresolved.

No read may claim flatness solely because one object is absent.

## 9. Provenance and transaction frontiers

For every mutation response and logical GET, retain only bounded normalized provenance:

```text
provider HTTP RequestID when supplied
provider transaction IDs
batchID
relatedTransactionIDs
lastTransactionID / read frontier when supplied
provider Order/Trade IDs
Atlas observation timestamp
provider transaction/object timestamp when supplied
read kind
provider endpoint key
```

OANDA exposes `RequestID` headers on relevant read endpoints.

The current GET requester does not expose all response metadata to callers, so PAPER 05 may add a narrowly typed read-response envelope that retains:

```text
payload
request_id nullable
```

plus the payload's normalized transaction frontier.

Do not invent a missing RequestID.

This extension must preserve GET-only behavior and safe retry semantics.

A retried GET remains one logical read for reconciliation accounting.

POST/PUT remain separate and non-retrying.

Transaction IDs must be parsed and compared numerically.

`last_applied_transaction_id` is per-attempt evidence only.

It is not:

```text
a global OANDA synchronization cursor
a runtime loop cursor
activation state
```

Advance it only in the same local transaction that has already validated and persisted the observations supporting the advancement.

When separate reads expose different transaction frontiers:

```text
non_atomic_read_set = true
```

Do not manufacture a common frontier or claim atomic provider state.

## 10. Conflict and fail-closed rules

The broker is authoritative for actual broker events/exposure.

Atlas Risk is authoritative for whether Atlas approved the original financial RiskDecision.

Atlas persistence is authoritative for what evidence Atlas has durably established.

Always fail closed for:

```text
Strategy receipt/version/parameter mismatch
Risk evidence that cannot be exactly serialized
same attempt_id with changed immutable facts
duplicate mutation claim
durable Fill versus contradictory later broker identity
Fill plus incompatible reject/cancel evidence
wrong account
wrong instrument
wrong units
wrong client correlation
wrong priceBound
wrong Trade identity
unexpected provider object
unexpected account exposure
unattributed target
stale reconciliation projection
transaction range exceeding the bounded recovery window
malformed/partial/transport-uncertain provider facts
database pre-mutation commit failure
```

When a valid Fill is proven:

```text
never delete it
never null it
never convert it to UNKNOWN
never claim flatness from missing later data
```

When later broker lifecycle has progressed beyond PAPER 05:

```text
record LIFECYCLE_ADVANCED
preserve original execution proof
perform no mutation
```

When a still-open Trade disagrees with Atlas's intended/proven protection:

```text
record CONFLICT
preserve original execution proof
perform no repair
```

## 11. Examples and boundaries

### Valid

- A long Fill exactly equal to `approved_entry_price` is valid because the long invariant is:

```text
actual_fill_price <= approved_entry_price
```

- A short Fill exactly equal to `approved_entry_price` is valid because:

```text
actual_fill_price >= approved_entry_price
```

- An entry timeout leaves a permanent `ENTRY` claim. Exact Order lookup later fails, but a bounded transaction-range read finds an attributable `MARKET_ORDER_REJECT` with the original client identity and exact request facts. Atlas may resolve the execution outcome to `REJECTED` without a second POST.

- An entry timeout leaves an `ENTRY` claim. A later bounded read proves the original Fill. Atlas persists the Fill first and resolves the execution to at least `FILLED_PROTECTION_INCOMPLETE`; it never sends a second POST.

- A target timeout leaves a `TAKE_PROFIT` claim. A later Trade read proves the exact deterministic pending Take Profit at the actual-fill-derived target and the unchanged exact pending Stop. Atlas may advance the original execution outcome to `FILLED_PROTECTED` without another PUT.

- A previously `FILLED_PROTECTED` Trade later shows `CLOSED`. PAPER 05 records `LIFECYCLE_ADVANCED` while preserving `FILLED_PROTECTED` as the original execution outcome.

### Invalid

- A valid StrategyVersion provenance object beside a StrategyDecision produced by a different Strategy evaluation is not an acceptable durable handoff.

- Same `attempt_id` with altered quantity, Stop, Strategy receipt, Risk snapshot, account, or client correlation cannot mutate.

- Missing `RiskConfig.risk_per_trade` from durable authority evidence is not acceptable because Atlas could no longer explain the assumption used to compute the Risk budget.

- Order not-found does not prove rejection/cancellation.

- A flat Account Details snapshot does not prove that an uncertain entry was never sent.

- A transaction-range scan wider than the frozen bounded limit is not automatically expanded.

- A Fill plus contradictory cancel/reject evidence is not hidden. The Fill remains visible and reconciliation is conflicted.

- A missing Stop or uncertain target is never repaired by PAPER 05.

- A target that appears at the broker without Atlas's durable TAKE_PROFIT claim is not silently adopted as Atlas-authored protection.

- A later closed Trade does not downgrade historical `FILLED_PROTECTED` to `FILLED_PROTECTION_INCOMPLETE`.

### Boundary

- Actual target remains:

```python
strategy_decision.target.resolve(
    actual_fill_price,
    frozen_stop,
    direction,
)
```

It is not the pre-submission target when the actual Fill improves.

- `FILLED_PROTECTION_INCOMPLETE` means a Fill is proven.

- `UNKNOWN` means entry truth is not yet definitely established and no Fill is proven.

- `LIFECYCLE_ADVANCED` is reconciliation status, not a new execution outcome.

- A durable mutation claim means possible dispatch, not proven dispatch.

- Separate provider GETs remain non-atomic observations even when they occur in one reconciliation run.

## 12. Ownership and implementation decomposition

After explicit developer approval, decompose the workstream into meaningful tasks approximately as follows:

1. **Strategy + Risk durable authority contracts**

   - Add the bound PAPER Strategy evaluation receipt.
   - Add strict canonical serializers for Strategy/Risk/instruction evidence.
   - Add the five-outcome execution transition validator and separate reconciliation status contract.
   - Preserve existing StrategyDecision and RiskDecision semantics.

2. **PAPER persistence schema + repository**

   - Add the four PAPER tables.
   - Add constraints/guards/indexes.
   - Add reversible migration from the actual current Alembic head.
   - Implement exact attempt identity, immutable facts, Fill non-erasure, unique mutation claims, row locking, and stale projection protection.

3. **Durable entry boundary**

   - Refactor the existing P04 composition only enough to expose the fresh pre-entry preparation.
   - Commit immutable attempt + ENTRY claim before the non-retrying POST.
   - Persist normalized entry observations and Fill/result afterward.
   - Preserve all frozen P04 entry semantics.

4. **Durable protection boundary**

   - Expose the pre-PUT protection preparation seam.
   - Commit Fill/Stop/actual target + TAKE_PROFIT claim before the non-retrying PUT.
   - Persist mutation/final-readback observations afterward.
   - Preserve actual-fill target methodology and no-repair behavior.

5. **Bounded read-only reconciliation**

   - Add read metadata support and bounded OANDA Transaction-ID-range reader.
   - Implement UNKNOWN, known-Fill, protection-incomplete, and lifecycle-advanced reconciliation.
   - No POST/PUT/cancel/repair path exists in this coordinator.

6. **Critical validation**

   - Deterministic provider-shape/unit tests.
   - PostgreSQL migration/constraint/trigger/concurrency/restart/commit-boundary tests.
   - Focused PAPER 02–05, Risk, OANDA execution regression tests.
   - Broad safe non-external backend regression suite.

Exact T00x grouping may combine adjacent implementation units cleanly.

Do not create a separate test-only task.

No task may introduce PAPER 06.

## 13. Required validation evidence

Deterministic tests must cover:

```text
Strategy receipt cannot be mismatched with executed decision

exact StrategyVersion / parameter / StrategyEvaluation snapshot

exact RiskConfig and Risk authority snapshot

no second Risk evaluation for persistence evidence

same-ID durable load versus same-ID immutable conflict

one ENTRY claim under duplicate/concurrent/restart calls

one TAKE_PROFIT claim under duplicate/concurrent/restart calls

claim means possible dispatch, not proven broker receipt

database commit failure prevents broker mutation

process-crash simulations around both mutation claims

all five initial execution outcomes

UNKNOWN proof-driven resolution

Fill non-erasure

independent Stop and Take Profit facts

FILLED_PROTECTION_INCOMPLETE → FILLED_PROTECTED promotion

FILLED_PROTECTED never downgraded by later lifecycle movement

separate CONSISTENT / UNRESOLVED / CONFLICT / LIFECYCLE_ADVANCED status

exact Order readback

exact Transaction readback

bounded Transaction-ID-range recovery

lost reject response with no Order resource

transaction-range truncation remains unresolved

strict reject/cancel/fill attribution

known-Fill Trade reconciliation

closed Trade classified as lifecycle advancement

unexpected protection drift classified as conflict

no resubmit
no cancel
no close
no reduce
no repair

RequestID / transaction / batch / related IDs / frontiers / timestamps

raw provider body, credentials, and unbounded text exclusion

non-atomic read-set handling

stale reconciliation cannot overwrite newer projection
```

With a dedicated PostgreSQL database whose name ends in `_test`, include:

```text
alembic upgrade head
alembic current/check as applicable

upgrade
→ downgrade to prior head
→ upgrade

schema/table/column/index/check/foreign-key inspection

append-only mutation-claim guard
append-only broker-observation guard
append-only reconciliation-run guard

immutable Strategy/Risk/instruction evidence guard
Fill all-or-none and Fill non-erasure guard
execution-outcome transition guard
unique client correlation constraints
unique (attempt_id, phase) mutation claim

two-session concurrent ENTRY claim:
    exactly one durable claim succeeds

two-session concurrent TAKE_PROFIT claim:
    exactly one durable claim succeeds

row-lock / projection-version stale reconciliation behavior

rollback/commit proof:
    no broker call before successful pre-mutation commit
```

Then run:

```text
changed-file formatting/lint/type checks
focused PAPER execution/reconciliation tests
Risk regressions
historical Experiment regressions
broad non-integration/non-external backend suite appropriate to a Critical
persistence/execution boundary
git diff --check
```

No validation uses a real OANDA mutation or capital-capable credential.

## 14. PAPER 06 exclusions

PAPER 06 is explicitly not authorized here:

```text
runtime loop
scheduler
background worker
automatic Strategy cadence

PAPER activation
activation UI/API
start/stop controls
resumption policy
supervision policy

automatic recovery mutation
entry resubmission
Take Profit retry
Stop repair
Take Profit repair
cancel
close
reduce

LIVE
non-Practice operation

general broker/provider abstraction
multi-broker
multi-account
multi-instrument

partial-fill accounting
multi-fill accounting
closed-Trade accounting
realized PAPER PnL

credential-management redesign
credential persistence/logging

Risk-policy administration

historical Experiment Order/Fill/Trade semantic changes

global transaction synchronization
unbounded `sinceid`
reconciliation daemon
autonomous account repair
```

PAPER 05 establishes durable, explainable execution truth and bounded reconciliation only.

## 15. Decisions requiring developer approval

The domain and safety contract is resolved.

Before BUILD, the developer must explicitly approve the current PLAN and this architecture.

Implementation may choose narrow names and module boundaries consistent with the repository, but it may not reinterpret these frozen semantics.

In particular BUILD must not guess that:

```text
Strategy provenance may be paired independently with a decision

persisted RiskDecision alone is enough to explain the applied Risk policy

a mutation claim proves the HTTP request was sent

Order not-found means rejection

flat Account Details means the uncertain mutation did not happen

reconciliation may scan transactions without a finite bound

FILLED_PROTECTED is a mutable current-Trade status

a closed Trade means original protection was incomplete

a missing protection may be repaired

database commit and broker mutation are atomic
```

No implementation task or GIT START occurs until explicit developer approval.
