# ARCHITECTURE — Dogfood 02 Protected Trade Lifecycle Closure

ROLE: `ARCHITECT`
WORKSTREAM: `dogfood-02-protected-trade-lifecycle-closure`
BRANCH: `main` (pre-approval; no GIT START)
CWD: `/Users/vike/Desktop/atlas`
TASK: `NONE`
OWNED_ARTIFACT: `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/ARCHITECTURE.md`
SPECIALIST_SKILLS: `none`

## Status and authority

- **Classification:** `Critical`
- **Architecture status:** `DRAFT_FOR_INTAKE`
- **Base inspected:** `main` at `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Implementation authorization:** none
- **Capital authority:** none
- **Broker mutation authority:** none

This architecture freezes the smallest trustworthy lifecycle-closure seam exposed by Dogfood 02.

Dogfood 02 demonstrated:

```text
Atlas entry
→ FILLED_PROTECTED
→ runtime intentionally STOPPED after the one approved Trade
→ OANDA Stop and Take Profit remained authoritative at broker
→ Trade later closed naturally at OANDA
→ current open-Trade read returned zero Trades
→ explicit reconciliation returned:
   performed = false
   reconciliationStatus = NOT_RUN
   executionOutcome = FILLED_PROTECTED
```

The defect is not that Atlas lost the Fill or protection evidence.

The defect is that the current runtime reconciliation gate treats a healthy
`FILLED_PROTECTED + NOT_RUN` attempt as no longer requiring reconciliation, so the existing
provider-neutral coordinator is never allowed to observe its later broker lifecycle
transition from `OPEN` to `CLOSED`.

This workstream also closes the evidence gap exposed by that natural closure: Atlas must
preserve the broker-supported completed-Trade economics and, where the closing transaction
can be exactly attributed, explain which exit mechanism closed the Trade.

No implementation, task creation, branch creation, runtime start, PAPER activation, Risk
evaluation, or broker mutation is authorized until this architecture and the reconciled
`PLAN.md` pass repository intake and receive explicit developer approval.

## 1. Current-main behavior and directly affected seams

### 1.1 Runtime reconciliation gate

`backend/runtime/activation.py` currently implements:

```text
PaperRuntimeService.reconcile(activation_id)
→ reject if runtime lifecycle is active/busy
→ load latest attempt
→ if attempt is absent OR not outstanding:
     performed = false
→ otherwise:
     call PAPER reconciliation coordinator
```

`_attempt_is_outstanding()` delegates to the strict shared
`is_unsafe_paper_attempt()` predicate.

Therefore:

```text
execution_outcome = FILLED_PROTECTED
reconciliation_status = NOT_RUN
```

is considered non-outstanding and the reconciliation coordinator is skipped.

That is correct for the question:

> Is this historical attempt unsafe enough to block recovery/new-session safety?

It is incomplete for the different question:

> Has this already-filled broker Trade subsequently advanced from OPEN to CLOSED?

Those two questions must remain separate.

### 1.2 Strict safety predicate

`backend/persistence/runtime_repository.py` defines the existing strict attempt predicate.

Safe terminal execution outcomes currently include:

```text
REJECTED
CANCELLED
FILLED_PROTECTED
```

with safe reconciliation statuses including:

```text
NOT_RUN
CONSISTENT
LIFECYCLE_ADVANCED
```

The predicate is used by safety-sensitive runtime/recovery behavior.

It must not be broadened, weakened, or redefined for lifecycle observation.

### 1.3 Existing provider-neutral CLOSED semantics

`backend/paper/reconciliation.py` already handles a durable Fill by reading the exact
provider Trade.

For an attributable Trade whose durable identity matches the Fill/context:

```text
Trade state = CLOSED
→ finding = TRADE_LIFECYCLE_ADVANCED
→ reconciliation_status = LIFECYCLE_ADVANCED
→ execution_outcome remains unchanged
```

Therefore:

```text
FILLED_PROTECTED + LIFECYCLE_ADVANCED
```

means:

```text
the original execution was successfully filled and protected
AND
the exact attributable broker Trade later completed its broker lifecycle
```

It does not by itself mean:

```text
current account flat
why the Trade closed
what the realized P/L was
what realized R was
that no unrelated exposure exists
```

Those meanings remain separate.

### 1.4 Existing OANDA reconciliation reader

`backend/integrations/oanda/reconciliation.py` already:

- reads the exact Trade by account-scoped Trade ID;
- accepts the documented account-scoped response when top-level `accountID` is absent;
- rejects explicit identity mismatch;
- uses `initialUnits` for CLOSED Trade identity because `currentUnits` becomes zero;
- maps an exact provider `CLOSED` state to `PaperReconciliationReadState.CLOSED`;
- preserves normalized provider evidence through `PaperBrokerObservation`.

The reader currently does not normalize the provider's completed-Trade economics such as:

```text
closeTime
averageClosePrice
realizedPL
financing
dividendAdjustment
closingTransactionIDs
```

and does not currently interpret the closing OrderFill reason.

### 1.5 Existing durable evidence seam

PAPER 05 already provides:

```text
paper_execution_attempts
paper_mutation_claims
paper_broker_observations
paper_reconciliation_runs
```

`paper_broker_observations` is append-only normalized provider evidence.

Each observation already carries:

- attempt identity;
- reconciliation-run identity;
- provider/object/read identity;
- typed provider IDs;
- exact Decimal-capable values;
- normalized bounded facts;
- a normalized-facts fingerprint.

This is sufficient for the current closure slice.

No new table or attempt-row closure projection is required.

### 1.6 Existing API result

The runtime reconciliation HTTP result currently exposes only:

```text
activationId
attemptId
performed
reconciliationStatus
executionOutcome
stale
```

For successful lifecycle closure, the same response should be able to return a bounded
closure summary derived from the exact reconciliation result.

That response is evidence only.

It does not become trading authority.

## 2. Governing evidence and authority

### 2.1 Authority hierarchy

The following authorities remain distinct:

```text
Strategy methodology
    ↓
Strategy evaluation

Risk policy
    ↓
RiskDecision

PAPER mutation authority
    ↓
P05 claim + execution boundary

Broker lifecycle truth
    ↓
provider-specific GET normalization

Atlas reconciliation conclusion
    ↓
provider-neutral reconciliation coordinator

Trader-facing completed-Trade interpretation
    ↓
safe projection from durable evidence
```

No lower layer may manufacture facts owned by a higher or external authority.

### 2.2 OANDA Trade authority

For the supported OANDA Practice Trade contract, a Trade in state:

```text
CLOSED
```

is fully closed.

For a closed/reduced Trade, OANDA provides aggregate Trade facts including:

```text
averageClosePrice
realizedPL
financing
dividendAdjustment
closingTransactionIDs
closeTime
```

The Trade GET is authoritative for the aggregate lifecycle facts of that exact
account-scoped Trade.

### 2.3 OANDA closing-transaction authority

An exact closing transaction may provide:

```text
type = ORDER_FILL
reason
tradesClosed[]
tradeReduced
```

The exact TradeReduce entry supplies the official close price and realized P/L for the
specific Trade reduction/closure.

The top-level `OrderFillTransaction.price` is deprecated and must not become Atlas close
price authority.

Where Atlas needs an exact closing price from a closing OrderFill, use the matching
`TradeReduce.price`.

### 2.4 Exit-cause authority

Atlas may derive a provider-neutral exit cause only from an exact attributable closing
transaction.

The OANDA provider adapter owns the mapping from provider reason to the product-level
closure cause.

The minimum supported product-level causes are:

```text
TAKE_PROFIT
STOP_LOSS
MARKET_CLOSE
MARGIN_CLOSEOUT
OTHER
MULTIPLE
UNRESOLVED
```

The exact provider reason must also remain preserved as evidence when one exact closing
transaction is available.

Examples:

```text
OANDA TAKE_PROFIT_ORDER
→ TAKE_PROFIT

OANDA STOP_LOSS_ORDER
→ STOP_LOSS

OANDA GUARANTEED_STOP_LOSS_ORDER
→ STOP_LOSS

OANDA TRAILING_STOP_LOSS_ORDER
→ STOP_LOSS

OANDA MARKET_ORDER_TRADE_CLOSE
→ MARKET_CLOSE

OANDA MARKET_ORDER_MARGIN_CLOSEOUT
→ MARGIN_CLOSEOUT
```

A provider reason Atlas does not explicitly map becomes:

```text
OTHER
```

not a guessed known cause.

### 2.5 Multiple closing transactions

`closingTransactionIDs` may contain more than one transaction.

A multi-transaction Trade does not have one safely inferable single exit cause merely
because it is now CLOSED.

For this workstream:

```text
len(closing_transaction_ids) == 1
→ Atlas may attempt exact closing-transaction attribution

len(closing_transaction_ids) > 1
→ exit_cause = MULTIPLE
→ preserve all transaction IDs
→ do not manufacture a single SL/TP/manual cause
```

Do not fan out into an unbounded historical reconstruction in this slice.

### 2.6 Current account state remains separate

A CLOSED attributable Trade proves that Trade's lifecycle ended.

It does not prove:

```text
zero unrelated Trades
zero Positions
zero pending Orders
account flatness
future entry eligibility
```

Current broker/account state continues to come from the existing fresh account/inventory
read contracts.

## 3. Frozen architecture decisions

### 3.1 Contracts

#### 3.1.1 Separate manual-reconciliation eligibility

Do not modify:

```text
is_unsafe_paper_attempt()
```

Introduce a separate narrowly named decision for whether an explicit terminal-runtime
reconciliation request should invoke the coordinator.

Conceptually:

```text
manual reconciliation eligible
=
existing unsafe/outstanding attempt
OR
healthy filled-protected lifecycle candidate
```

The additional healthy lifecycle candidate is:

```text
execution_outcome = FILLED_PROTECTED
reconciliation_status ∈ {NOT_RUN, CONSISTENT}
durable Fill identity is complete
```

`FILLED_PROTECTED + LIFECYCLE_ADVANCED` is already lifecycle-complete and should return a
bounded no-op rather than repeatedly append identical lifecycle runs.

`REJECTED` and `CANCELLED` with safe reconciliation statuses remain no-op because there is
no filled Trade lifecycle to advance.

Existing unsafe states continue to use the existing reconciliation behavior.

This new eligibility rule is for the explicit reconciliation operation only.

It is not:

```text
same-attempt recovery safety
new-session safety
new-entry safety
flatness proof
```

#### 3.1.2 Runtime busy fence remains unchanged

An activation in:

```text
REQUESTED
STARTING
RUNNING
STOP_REQUESTED
```

continues to reject explicit manual reconciliation with the existing busy conflict.

The runtime owns recovery while active.

A stopped/blocked/failed terminal activation may use the explicit bounded reconciliation
path when its latest attempt is eligible.

#### 3.1.3 Provider-neutral closure contract

Add one immutable provider-neutral closure value, conceptually:

```text
PaperTradeClosure
```

It contains at minimum:

```text
trade_id
closed_at
average_close_price
realized_pl
financing
dividend_adjustment
closing_transaction_ids
exit_cause
provider_reason
closing_transaction_id
exact_close_price
```

Rules:

- financial values use finite `Decimal`;
- `average_close_price` is positive;
- `exact_close_price`, when present, is positive;
- `closed_at` is timezone-aware;
- transaction IDs are bounded, non-empty, deterministic, and unique;
- CLOSED closure evidence requires at least one closing transaction ID;
- `closing_transaction_id` is populated only for a single exactly attributed closing
  transaction;
- `provider_reason` is evidence, not a product enum;
- `exact_close_price` comes from the matching close `TradeReduce`, not deprecated top-level
  OrderFill price.

For a multi-transaction close:

```text
exit_cause = MULTIPLE
closing_transaction_id = null
exact_close_price = null
provider_reason = null
```

while aggregate Trade facts remain authoritative and preserved.

For a single close whose cause enrichment cannot be proven:

```text
exit_cause = UNRESOLVED
```

The proven CLOSED lifecycle must not be erased merely because optional cause attribution is
unavailable.

#### 3.1.4 Reconciliation read contract

`PaperReconciliationRead` may carry closure evidence for an exact CLOSED Trade.

The provider protocol gains a narrow GET-only closing-transaction read seam rather than
reusing entry-Fill semantics ambiguously.

Conceptually:

```text
read_trade_close_transaction(
    context,
    transaction_id,
    trade_id,
)
```

or a semantically equivalent narrowly named method.

It must be:

- GET-only;
- account-scoped;
- exact transaction-ID scoped;
- exact Trade-ID attributable;
- bounded;
- provider-normalized before crossing into the coordinator.

Do not reinterpret the entry `read_transaction()` contract in a way that weakens existing
entry recovery attribution.

#### 3.1.5 Normalized evidence schema

The existing append-only `PaperBrokerObservation` ledger remains the durable evidence
store.

Extend the normalized broker-fact vocabulary for closure evidence and introduce a new
normalized broker-facts schema version for observations containing the new close facts.

Conceptually:

```text
ATLAS_PAPER_BROKER_FACTS_V2
```

Existing V1 observations remain valid and immutable.

V2 closure Trade evidence may include normalized bounded facts such as:

```text
close_time
average_close_price
realized_pl
financing
dividend_adjustment
closing_transaction_ids
```

A closing-transaction observation may include bounded facts such as:

```text
provider_reason
closed_trade_id
closed_units
close_price
close_realized_pl
close_financing
```

Do not store raw OANDA payloads.

Do not mutate an old observation into V2.

#### 3.1.6 Reconciliation result

`PaperReconciliationResult` and the bounded runtime/HTTP reconciliation response may carry:

```text
tradeClosure: null | {
    tradeId
    closedAt
    averageClosePrice
    realizedPl
    financing
    dividendAdjustment
    closingTransactionIds
    exitCause
    providerReason
    closingTransactionId
    exactClosePrice
}
```

Decimal values remain exact strings on the HTTP wire.

This is a result of the current reconciliation request.

The status endpoint does not need to become a completed-Trade history API in this
workstream.

#### 3.1.7 No first-class closure database projection yet

Do not add:

```text
close_price columns
realized_pl columns
exit_reason columns
new completed_trades table
new trade_results table
```

in this slice.

The append-only normalized broker observations plus reconciliation run already provide
durable reproducible evidence.

A later Understand/UI slice may add a read model if repeated completed-Trade querying proves
it necessary.

If implementation demonstrates that the current observation ledger cannot durably preserve
the frozen closure contract without ambiguity, stop for architecture re-approval rather
than quietly adding schema.

### 3.2 Domain invariants

#### 3.2.1 Execution outcome is historical entry/protection truth

Natural Trade closure must not rewrite:

```text
FILLED_PROTECTED
```

into a new execution outcome.

Execution outcome answers:

> What happened during Atlas entry and protection establishment?

Reconciliation status answers:

> What did later broker observation prove about that execution lifecycle?

Therefore the expected Dogfood transition is:

```text
FILLED_PROTECTED + NOT_RUN
→ explicit GET-only reconciliation
→ FILLED_PROTECTED + LIFECYCLE_ADVANCED
```

not:

```text
FILLED_PROTECTED
→ CLOSED
```

as an execution-outcome mutation.

#### 3.2.2 Fill is immutable

Existing Fill identity remains write-once:

```text
broker order ID
fill transaction ID
Trade ID
signed units
entry price
fill time
actual initial risk
```

Closure cannot erase or rewrite entry facts.

#### 3.2.3 Closure is attributable to the exact durable Trade

`CLOSED` is accepted only when the provider Trade:

- is the requested exact Trade;
- belongs to the configured account-scoped read;
- matches the persisted provider Trade ID;
- matches client Trade identity;
- matches instrument;
- uses the documented CLOSED-unit identity rule;
- matches the durable Fill price/initial units according to the current reconciliation
  contract.

Missing or contradictory identity remains unresolved/conflicted as today.

#### 3.2.4 Aggregate close facts are provider facts, not Atlas calculations

Atlas must preserve separately:

```text
realized_pl
financing
dividend_adjustment
```

Do not call their sum or any one value:

```text
net P/L
total return
account return
```

without a separately defined metric contract.

#### 3.2.5 No realized R in this workstream

Do not persist or expose a new `realizedR` field in this slice.

Although Atlas has durable initial-risk evidence, a product-level realized-R definition
needs an explicit metric contract covering:

- which realized P/L basis is used;
- financing;
- commissions/fees;
- partial/multiple closes;
- account-currency treatment;
- zero/edge cases.

This workstream preserves the underlying exact evidence needed for that later calculation.

#### 3.2.6 Exit cause never comes from price comparison

Do not infer:

```text
hit target because close price ~= target
hit stop because close price ~= stop
```

The exit cause comes from exact provider transaction semantics.

Price comparison may be used only as a consistency check, never as authority for exit
cause.

#### 3.2.7 Lifecycle closure survives optional cause uncertainty

If the exact Trade GET coherently proves:

```text
Trade CLOSED
```

then lifecycle advancement is proven.

If a secondary closing-transaction read:

- times out;
- is unavailable;
- has an unsupported reason;
- cannot establish one single cause;

Atlas must preserve:

```text
LIFECYCLE_ADVANCED
```

and make the exit attribution explicitly:

```text
UNRESOLVED
MULTIPLE
OTHER
```

as appropriate.

Do not downgrade a proven closed Trade back to OPEN or erase the lifecycle finding because
an enrichment read failed.

#### 3.2.8 Contradictory closure evidence is never overwritten

If Atlas already has one durable close observation and a later read presents incompatible
identity/economic facts for the same exact close evidence:

```text
do not overwrite
do not silently choose newest
do not average
```

Preserve append-only evidence and surface the contradiction through the existing conflict
or an explicit closure-attribution conflict path.

Exact replay remains idempotent.

#### 3.2.9 Closure is not flatness

Even after:

```text
FILLED_PROTECTED + LIFECYCLE_ADVANCED
```

the terminal runtime state still does not prove current account flatness.

Existing fresh broker/account reads remain authoritative for future activation/startup and
entry.

### 3.3 Failure behavior

#### Trade read failure

If the primary exact Trade GET fails or cannot be normalized:

```text
reconciliation = UNRESOLVED/FAILED under existing semantics
closure = absent
```

No lifecycle advancement is created.

#### Trade identity conflict

If exact Trade evidence contradicts durable identity:

```text
reconciliation = CONFLICT
closure = absent
```

No lifecycle advancement is created.

#### Trade remains OPEN

If exact Trade remains OPEN and protection matches:

```text
FILLED_PROTECTED
reconciliation = CONSISTENT
closure = null
```

The attempt remains eligible for a later explicit lifecycle reconciliation.

No polling is introduced.

#### CLOSED aggregate malformed

If OANDA reports `CLOSED` but required closure aggregate facts are malformed or internally
invalid:

```text
do not manufacture closure economics
do not report successful completed-Trade detail
fail closed through normalized provider/reconciliation semantics
```

#### Single closing-transaction read unavailable

If CLOSED aggregate identity is valid but the one optional closing transaction cannot be
read:

```text
reconciliation = LIFECYCLE_ADVANCED
closure aggregate = preserved
exit_cause = UNRESOLVED
```

The failure/uncertainty must remain visible in finding/evidence.

#### Single closing-transaction attribution conflict

If the returned transaction does not close/reduce the exact expected Trade:

```text
lifecycle remains LIFECYCLE_ADVANCED from Trade authority
exit_cause = UNRESOLVED
record explicit exit-attribution conflict evidence
```

Do not reinterpret another Trade's transaction.

#### Multiple closing transactions

```text
reconciliation = LIFECYCLE_ADVANCED
exit_cause = MULTIPLE
aggregate closure facts preserved
no single exact_close_price claim
```

No unbounded transaction fan-out.

#### Persistence failure

If closure/reconciliation evidence cannot be committed atomically through the current
PAPER reconciliation apply boundary:

```text
do not return durable success
do not partially update the attempt projection
surface bounded reconciliation failure
```

Broker state is not mutated.

## 4. Valid, invalid, and boundary examples

### Example A — protected Trade still open

```text
attempt:
  outcome = FILLED_PROTECTED
  reconciliation = NOT_RUN

Trade GET:
  exact attributable Trade
  state = OPEN
  Stop = exact
  Take Profit = exact
```

Result:

```text
performed = true
outcome = FILLED_PROTECTED
reconciliation = CONSISTENT
tradeClosure = null
```

A later explicit reconciliation remains allowed.

### Example B — Take Profit closes Trade

```text
attempt:
  FILLED_PROTECTED + NOT_RUN

Trade GET:
  state = CLOSED
  one closingTransactionID
  closeTime valid
  averageClosePrice valid
  realizedPL valid

closing transaction:
  type = ORDER_FILL
  matching TradeReduce
  reason = TAKE_PROFIT_ORDER
```

Result:

```text
performed = true
executionOutcome = FILLED_PROTECTED
reconciliationStatus = LIFECYCLE_ADVANCED
exitCause = TAKE_PROFIT
```

Aggregate and exact closing evidence are durably appended.

### Example C — Stop Loss closes Trade

Same as B except:

```text
reason = STOP_LOSS_ORDER
```

Result:

```text
exitCause = STOP_LOSS
```

### Example D — manual market close

Exact single closing transaction reports the provider's market Trade-close reason.

Result:

```text
exitCause = MARKET_CLOSE
```

Do not say Atlas closed the Trade.

### Example E — multiple reductions then final close

Trade:

```text
state = CLOSED
closingTransactionIDs = [x, y]
```

Result:

```text
LIFECYCLE_ADVANCED
exitCause = MULTIPLE
averageClosePrice = provider aggregate
realizedPl = provider aggregate
exactClosePrice = null
```

Do not pick the final transaction and label the entire Trade as SL/TP.

### Example F — CLOSED Trade but cause read times out

Result:

```text
LIFECYCLE_ADVANCED
exitCause = UNRESOLVED
```

The lifecycle truth survives; the causal uncertainty remains visible.

### Example G — unrelated transaction returned

Trade closure is proven, but the queried transaction does not contain the expected Trade.

Result:

```text
LIFECYCLE_ADVANCED
exitCause = UNRESOLVED
exit-attribution conflict evidence retained
```

No unrelated Trade economics are accepted.

### Example H — already lifecycle-advanced protected attempt

```text
FILLED_PROTECTED + LIFECYCLE_ADVANCED
```

Explicit reconcile:

```text
performed = false
```

No repeated run is required merely to reproduce the same terminal lifecycle conclusion.

### Example I — rejected attempt

```text
REJECTED + NOT_RUN
```

There is no filled Trade lifecycle.

Explicit reconcile remains a bounded no-op under the existing safe-terminal behavior.

### Example J — existing UNKNOWN / incomplete recovery state

Existing unsafe reconciliation behavior remains unchanged.

This workstream does not weaken recovery in order to support healthy lifecycle closure.

## 5. Implementation boundaries

### Expected domain/PAPER files

```text
backend/paper/persistence_contracts.py
backend/paper/reconciliation.py
```

### Expected OANDA file

```text
backend/integrations/oanda/reconciliation.py
```

### Expected runtime/API files

```text
backend/runtime/activation.py
backend/api/schemas.py
```

`backend/api/paper.py` should require little or no semantic change because it already
delegates the reconciliation request to the service.

### Expected tests

```text
backend/tests/paper/test_persistence_contracts.py
backend/tests/paper/test_reconciliation.py
backend/tests/integrations/test_oanda_reconciliation.py
backend/tests/runtime/test_runtime_activation.py
```

Existing API PAPER tests should be updated if the bounded response contract changes.

### Generated client

If the HTTP response schema changes, regenerate:

```text
frontend/lib/api.generated.ts
```

through the repository's existing OpenAPI generation workflow.

This generated contract update does not authorize a frontend UI change.

### No migration expected

No change is expected in:

```text
backend/persistence/models.py
backend/persistence/migrations/**
```

The existing observation ledger is the durable close-evidence boundary for this slice.

If a database schema change becomes necessary to meet the frozen semantics, stop for
architecture re-approval.

### No changes expected in capital-capable execution

Do not change:

```text
backend/paper/execution.py
backend/paper/risk_evaluation.py
backend/risk/**
backend/integrations/oanda/execution.py
backend/integrations/oanda/mutation_request.py
```

unless repository intake demonstrates an unavoidable compile-only contract import. Any
semantic change there requires architecture re-approval.

## 6. Required validation evidence and tests

Validation must prove all of the following.

### Reconciliation eligibility

- strict `is_unsafe_paper_attempt()` truth table is unchanged;
- `FILLED_PROTECTED + NOT_RUN` with coherent Fill is manually reconcilable;
- `FILLED_PROTECTED + CONSISTENT` with coherent Fill is manually reconcilable;
- `FILLED_PROTECTED + LIFECYCLE_ADVANCED` is no-op;
- REJECTED/CANCELLED safe-terminal cases remain no-op;
- existing UNKNOWN/incomplete/unresolved/conflicted recovery cases retain current behavior;
- active-runtime lifecycle states retain the busy fence.

### OPEN protected Trade

- exact OPEN Trade + exact protection returns `CONSISTENT`;
- execution outcome remains `FILLED_PROTECTED`;
- no closure is emitted;
- no mutation occurs.

### CLOSED Trade normalization

Test exact OANDA normalization for:

- CLOSED state;
- `initialUnits` identity;
- `closeTime`;
- `averageClosePrice`;
- `realizedPL`;
- `financing`;
- `dividendAdjustment`;
- one closing transaction ID;
- multiple closing transaction IDs;
- malformed/missing required close facts;
- explicit account mismatch;
- Trade/client/instrument mismatch.

### Closing transaction

Test:

```text
TAKE_PROFIT_ORDER -> TAKE_PROFIT
STOP_LOSS_ORDER -> STOP_LOSS
GUARANTEED_STOP_LOSS_ORDER -> STOP_LOSS
TRAILING_STOP_LOSS_ORDER -> STOP_LOSS
MARKET_ORDER_TRADE_CLOSE -> MARKET_CLOSE
MARKET_ORDER_MARGIN_CLOSEOUT -> MARGIN_CLOSEOUT
unsupported recognized provider reason -> OTHER
```

Also prove:

- transaction must be exact requested transaction ID;
- transaction must affect the exact expected Trade;
- official `TradeReduce.price` is used;
- deprecated top-level OrderFill price is not close-price authority;
- unrelated TradeReduce is rejected for attribution.

### Multiple close transactions

Prove:

```text
MULTIPLE
```

without transaction fan-out or a fabricated single close price/cause.

### Optional cause read failure

Prove:

- primary exact CLOSED Trade still becomes `LIFECYCLE_ADVANCED`;
- aggregate closure is retained;
- exit cause becomes `UNRESOLVED`;
- uncertainty is durably visible;
- no false `CONFLICT`/OPEN/flat result is manufactured merely because enrichment failed.

### Durable evidence

Prove:

- closure observations are append-only;
- exact replay is idempotent;
- V1 observations remain valid;
- closure observations use the new normalized facts schema;
- raw provider payload is not persisted;
- no credentials/account secrets leak into API response;
- conflicting exact-close evidence is not overwritten.

### HTTP result

Prove exact Decimal-string serialization and bounded closure output.

The response must preserve:

```text
performed
reconciliationStatus
executionOutcome
stale
tradeClosure
```

with `tradeClosure = null` when no closure was proven.

### Mutation fence

Spy/mock provider mutation seams.

A closure reconciliation must perform no:

```text
POST entry
PUT Take Profit
Trade close
Order cancel
Order replace
position close
Risk evaluation
activation
runtime start
```

## 7. Explicit non-authorizations

This workstream does not authorize:

- starting `atlas-runtime`;
- creating a PAPER activation;
- submitting another Trade;
- changing the existing Dogfood Strategy;
- changing Dogfood risk;
- changing Risk policy;
- closing/reducing/modifying a broker Trade;
- modifying broker Stop Loss or Take Profit;
- broker repair;
- automatic reconciliation polling;
- retrying broker mutations;
- automatic follow-on PAPER entry;
- LIVE behavior;
- UI work;
- completed-Trade history UI;
- new scheduler/daemon/background worker;
- new provider abstraction layer;
- new completed-Trade table;
- first-class realized-R metric;
- a net-P/L claim;
- hardcoding the Dogfood activation, attempt, Trade, account, transaction, price, or quantity
  into production logic.

The actual Dogfood 02 identifiers are operational evidence only.

Tests use synthetic identities.

## 8. Approval gate

Before implementation approval:

```text
do not GIT START
do not create tasks
do not create/switch feature branch
do not modify application code
do not modify tests
do not run real broker reconciliation
do not use broker credentials for validation
```

Required sequence:

```text
ARCHITECTURE + PLAN pasted
→ Solo PLAN/ARCHITECTURE intake
→ correct repo inaccuracies or cross-document contradictions
→ explicit developer approval
→ GIT START
→ task creation
→ BUILD
→ VALIDATE
→ REVIEW
→ remediation if required
→ explicit merge approval
→ GIT END
```

After the implementation is validated, reviewed, merged, and explicitly accepted for
operational use, Dogfood 02 may receive one explicit GET-only lifecycle reconciliation
through the normal Atlas API.

That operational acceptance:

- may read OANDA;
- may append Atlas reconciliation/observation evidence;
- may not start runtime;
- may not mutate the broker;
- may not create new capital exposure.

Expected successful Dogfood closure shape:

```text
performed = true
executionOutcome = FILLED_PROTECTED
reconciliationStatus = LIFECYCLE_ADVANCED
tradeClosure = present
```

The actual provider evidence determines the exit cause and economics.

No expected SL/TP result may be hardcoded in advance.
