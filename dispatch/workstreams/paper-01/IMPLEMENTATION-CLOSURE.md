# PAPER 01 Implementation Closure

**Status:** FROZEN FOR BUILD  
**Workstream:** paper-01  
**Purpose:** Close the remaining PAPER 01 implementation invariants discovered
after the T004 remediation cycle.

This document is an implementation-closure contract. It does not replace or
redesign the frozen PAPER 01 PLAN or ARCHITECTURE.

Authority order remains:

1. Atlas North Star
2. PAPER 01 PLAN
3. PAPER 01 ARCHITECTURE
4. T004 F-R1/F-R2 design reconciliation
5. this IMPLEMENTATION-CLOSURE.md

If implementation discovers a contradiction with a higher-authority artifact,
BUILD must stop rather than reinterpret the architecture.

No PAPER activation is authorized by this document.

---

## 1. Closure objective

Close the remaining known PAPER 01 implementation gaps as one coherent capital-
boundary correction instead of continuing finding-by-finding remediation.

The implementation boundary is:

```text
Strategy state / analytical data
→ pending methodology state
→ TradeIntent
→ PRE_FLIGHT
→ broker/account facts
→ PRE_SUBMISSION
→ persisted authorization
→ PENDING_SUBMISSION Order
→ OANDA execution normalization
→ authoritative Fill
→ Position / Trade
→ broker-hosted protection
→ transaction reconciliation
→ durable cursor
→ restart / resume
```

The Strategy remains pure and environment-independent throughout this flow.
Broker account state, exposure state, Risk authorization, execution permission,
and reconciliation state must never be injected into Strategy methodology.

---

# C001 — Analytical M15 input and frontier safety

**Closes:** F-C1 and the analytical portion of F-C5.

## Required implementation

There must be one validation boundary immediately before a live M15 bar is
allowed to reach Strategy evaluation.

A live analytical bar may enter `process_completed_bar` only when all of the
following are true:

- provider/source is the validated OANDA source;
- instrument is EUR/USD;
- timeframe is native M15;
- price basis is MID;
- the provider reports the candle complete;
- timestamps are valid timezone-aware UTC;
- the completed candle is not from the future relative to the observation/poll
  time;
- the candle belongs strictly after the Deployment's durable analytical
  frontier;
- chronological order is preserved.

A bar at or before the durable frontier is never evaluated again through the
live path.

An identical duplicate is a no-op.

A conflicting duplicate, incomplete candle, wrong source, wrong instrument,
wrong timeframe, wrong price basis, future candle, or out-of-order candle blocks
the analytical cycle before Strategy state changes.

## Warm-up exception

Historical warm-up bars are loaded through a separate seed/restore path.

Warm-up bars:

- may be at or before the durable analytical frontier;
- populate Strategy analytical context only;
- must satisfy the same native OANDA / EUR/USD / M15 / MID / completed
  provenance checks;
- must not run normal Strategy evaluation;
- must not emit TradeIntent;
- must not change capital state.

Do not weaken the live frontier check to support warm-up.

## Frontier persistence

After one new completed M15 bar is successfully evaluated:

1. produce the next StrategyStateEnvelope;
2. persist that state;
3. persist the corresponding analytical frontier;
4. commit them atomically.

The frontier may never advance independently of its corresponding persisted
Strategy state.

Persisted Strategy state must have a database-enforced unique identity for the
Deployment plus analytical frontier so replay cannot create a second state for
the same evaluated bar.

## Required tests

- incomplete M15 rejected before Strategy;
- wrong source/timeframe/price basis rejected;
- future completed candle rejected;
- bar equal to durable frontier does not reevaluate;
- bar older than frontier does not reevaluate;
- chronological next bar evaluates once;
- identical replay is idempotent;
- conflicting duplicate blocks;
- state and frontier commit together;
- warm-up seeding does not evaluate Strategy or emit capital facts.

---

# C002 — Account, Risk, handoff, and Order authorization fence

**Closes:** F-R3, F-R6, and F-C2.

## A. Deployment account binding

`PaperEntryAuthorizer` must receive the Deployment's explicit TradingAccount
identity as an immutable expected account.

Every broker/account read used during an authorization attempt must be validated
against that expected account before the facts are allowed into Risk.

This applies independently to:

- PRE_FLIGHT broker facts;
- the fresh PRE_SUBMISSION broker facts.

The following must agree:

- provider = OANDA;
- environment = Practice;
- external account ID = Deployment's selected account;
- account currency = USD;
- instrument facts apply to EUR/USD.

If either read belongs to another account, is missing account identity, or
contradicts the selected Deployment account, authorization fails before Order
submission.

The second read may not inherit trust from the first read.

## B. Persisted PRE_SUBMISSION is authoritative

An ENTRY Order may be created only from the persisted PRE_SUBMISSION
RiskDecision.

`create_pending_order` must load the persisted RiskDecision inside the same
database transaction used to create or resolve the ENTRY Order.

The persisted row must prove:

- phase is PRE_SUBMISSION;
- outcome is APPROVED;
- it belongs to the same TradeIntent;
- that TradeIntent belongs to the same Deployment;
- approved quantity equals the quantity used for Order creation;
- approved stop equals the stop used for execution/protection;
- approved price bound equals the price bound used for submission;
- executable reference/quote facts equal the authorization used by the caller;
- PAPER target is NULL at PRE_SUBMISSION;
- the persisted authorization has not been superseded, rejected, or invalidated.

The in-memory RiskDecision is not authority.

It may be used only as a convenience representation of the already-matching
persisted approval.

Any mismatch between in-memory and persisted authorization blocks Order creation.

## C. One handoff → one TradeIntent → one ENTRY Order

The opening path must be database-idempotent.

The durable lifecycle must enforce:

```text
one pending methodology handoff
→ at most one TradeIntent
→ at most one PAPER ENTRY Order
```

Use database uniqueness, not process memory, as the final fence.

There must be a database-enforced uniqueness rule equivalent to one ENTRY Order
per TradeIntent.

A crash or concurrent call after Order persistence may not create another ENTRY
Order.

If the existing ENTRY Order is:

- PENDING_SUBMISSION;
- UNKNOWN;
- FULL_FILLED;
- otherwise already authoritative,

the runtime must resolve/reconcile that Order rather than create another.

PENDING_SUBMISSION must still be committed before any provider mutation.

UNKNOWN must never be blindly retried.

A provider-absent result may be retried only through the already-frozen
reconciliation rule and a new fresh PRE_SUBMISSION authorization.

## D. Methodology authority remains in Strategy state

`StrategyStateEnvelope.pending_entry` remains the sole methodology authority for:

- direction;
- trigger;
- decision frontier;
- watch count;
- Strategy stop methodology.

The runtime handoff row is lifecycle linkage only.

It may not create a second independent methodology representation.

## Required tests

- first broker read wrong account blocks;
- second broker read wrong account blocks;
- account missing identity blocks;
- persisted PRE_SUBMISSION REJECTED + in-memory APPROVED blocks;
- persisted quantity mismatch blocks;
- persisted stop mismatch blocks;
- persisted price-bound mismatch blocks;
- wrong TradeIntent/Deployment ownership blocks;
- concurrent ENTRY creation leaves one Order;
- crash/re-entry with existing PENDING_SUBMISSION creates no second Order;
- UNKNOWN creates no blind retry.

---

# C003 — Restart, Strategy continuity, and durable runtime health

**Closes:** F-R4, F-C5, and the incomplete durable frontier/health finding.

## A. Processor restoration order

A Deployment may not enter actual RUNNING after process restart until its
Strategy processor has been reconstructed from durable state.

The restoration order is:

1. acquire the Deployment advisory ownership lock;
2. perform broker reconciliation;
3. load the latest valid StrategyStateEnvelope;
4. validate StrategyVersion and state schema linkage;
5. load validated M15 warm-up context;
6. seed analytical history without Strategy evaluation;
7. restore `pending_entry` from the StrategyStateEnvelope;
8. restore the durable analytical frontier;
9. perform analytical catch-up after that frontier;
10. persist the caught-up Strategy state/frontier;
11. pass freshness/readiness gates;
12. only then allow actual RUNNING.

## B. Strategy state linkage

Every executable PAPER Strategy state must belong to:

- the current Deployment;
- the Deployment's immutable StrategyVersion;
- the expected Strategy state schema/version.

If the latest state cannot prove those links, the Deployment cannot RUN.

Do not deserialize an unknown or mismatching Strategy state and continue.

The database must enforce the StrategyVersion relationship where the schema
permits it; runtime validation remains mandatory even when a FK exists.

## C. Warm-up reconstruction

Before live evaluation, load the most recent 100 validated completed native OANDA
EUR/USD M15 MID bars required for the approved PAPER 01 warm-up.

They must be loaded chronologically.

They seed `StrategyBarProcessor.bars` without normal Strategy evaluation.

Warm-up is independent of the live durable frontier: already-processed bars may
be loaded as analytical context without becoming eligible for reevaluation.

Insufficient or invalid warm-up context blocks readiness rather than silently
starting with an empty processor.

No M1 data may be used to synthesize this M15 context.

## D. Pending-entry restoration

If the latest StrategyStateEnvelope contains a pending entry, the processor must
restore that exact pending methodology state.

It may not initialize `pending_entry = None` merely because the process restarted.

The restored pending state must preserve:

- direction;
- trigger;
- confirmation/decision frontier;
- watch count;
- approved Strategy stop methodology/state.

Any durable runtime handoff linked to that pending entry must resolve to the same
methodology state.

A mismatch blocks reconciliation/readiness.

## E. Catch-up semantics

Completed native M15 bars after the durable analytical frontier are replayed
chronologically to reconstruct current Strategy state.

Catch-up is analysis-only.

Catch-up may:

- update indicators;
- advance Strategy state;
- expire/reset stale pending methodology state according to Strategy rules;
- advance the durable analytical frontier.

Catch-up may not create capital exposure from a stale historical opportunity.

Only observations arriving after the runtime has completed reconciliation,
catch-up, freshness checks, and actual RUNNING may authorize new capital action.

## F. Durable runtime health

The runtime must durably retain, using the existing runtime health/safety
persistence seam:

- current Deployment runtime state;
- owner heartbeat timestamp;
- last successful broker reconciliation timestamp;
- latest authoritative broker-account observation time;
- latest durable analytical M15 frontier;
- current safety/block reason when blocked.

A successful cycle updates the applicable health facts.

Loss of the advisory lock, failed heartbeat persistence, database connectivity
loss, stale broker facts, invalid Strategy state, or inconsistent frontier blocks
new exposure immediately.

These facts may not exist only in process memory.

## Required tests

- restart restores 100-bar context immediately;
- restart restores pending_entry;
- restart with pending handoff resolves same methodology state;
- restart does not require 100 new M15 bars before Strategy works;
- warm-up bars do not reevaluate;
- post-frontier catch-up evaluates chronologically;
- catch-up produces no stale capital action;
- invalid StrategyVersion linkage blocks;
- invalid state schema blocks;
- state/frontier mismatch blocks;
- durable health/frontier survive a new runtime instance.

---

# C004 — Protection truth and OANDA transaction-cursor authority

**Closes:** F-R2, F-R5, and F-C4.

## A. Protection identity

A broker protection state is valid only when:

- exactly one STOP_LOSS provider Order is linked to the matching OANDA Trade;
- exactly one TAKE_PROFIT provider Order is linked to the matching OANDA Trade;
- both provider Order IDs are non-empty;
- STOP_LOSS Order ID != TAKE_PROFIT Order ID;
- both link to the exact same expected OANDA Trade ID;
- stop price equals the approved PAPER stop;
- target price equals the actual-Fill-derived target;
- the current Trade is OPEN;
- current Trade direction matches the Fill;
- absolute current Trade units equal the authoritative full Fill quantity;
- the broker observation is fresh.

OANDA protection Orders remain Trade-scoped.

Do not invent stop-order or target-order quantity fields.

Protection quantity is proven by the exact Trade linkage plus the authoritative
Trade current units and matching Position side.

Duplicate, foreign, missing, or contradictory protection identities are
ambiguous and fail closed.

## B. Immediate Fill versus protection failure

An authoritative broker Fill is financial truth and must not be erased merely
because protection confirmation fails afterward.

For the immediate submission path:

1. persist/deduplicate the authoritative Fill;
2. derive/update canonical Position/Trade facts;
3. confirm broker-hosted stop/target protection;
4. only report the entry lifecycle healthy when protection confirmation passes.

If the authoritative Fill is known but protection is missing, duplicated,
incorrect, stale, or ambiguous:

- preserve the authoritative Fill and resulting local exposure truth;
- do not pretend the entry never happened;
- set/block the Deployment as FAILED or RECONCILIATION_REQUIRED according to the
  existing safety state contract;
- block all new exposure;
- do not report protected success.

For missed-Fill reconciliation, retain the stricter frozen F-R2 rule: current
broker Trade/Position/protection proof must pass before Atlas reconstructs the
missing local Fill.

## C. OANDA cursor authority

For PAPER 01, the durable OANDA transaction cursor is advanced only through the
OANDA Account Changes reconciliation path.

The canonical read is the read-only provider operation equivalent to:

```text
GET Account Changes since durable lastTransactionID
```

The execution/order-submission response's `lastTransactionID` is observation
evidence only.

A submission response must never directly advance the durable reconciliation
cursor.

This removes the possibility of jumping the cursor past compound-response
transactions that Atlas has not processed.

## D. Account Changes reconciliation

Given durable cursor `C`:

1. call OANDA Account Changes using `sinceTransactionID=C`;
2. require the read to belong to the Deployment's explicit account;
3. normalize every returned transaction without applying a provider type filter;
4. reconcile returned Order/Trade/Position changes;
5. classify and durably receipt every returned transaction;
6. apply/deduplicate every transaction that maps to canonical Atlas financial
   state;
7. reject any unresolved exposure-relevant or conflicting transaction;
8. only after the complete response is durably handled may Atlas advance the
   cursor to the response's `lastTransactionID`.

The Account Changes response is the cursor fence for that poll.

Do not manually infer transaction completeness by requiring every integer between
two IDs to exist.

Provider transaction IDs remain numeric-string identities, but completeness for
this flow comes from the successful unfiltered Account Changes response.

## E. Minimal transaction receipt

Add the smallest durable provider receipt needed to prove a transaction was
observed and classified.

Use an account-scoped OANDA transaction receipt with semantics equivalent to:

```text
OandaTransactionReceipt
- id
- trading_account_id
- external_transaction_id
- transaction_type
- occurred_at
- instrument nullable
- external_order_id nullable
- external_trade_id nullable
- normalized_digest
- disposition
- canonical_order_id nullable
- canonical_fill_id nullable
- observed_at
```

Database requirements:

```text
UNIQUE (trading_account_id, external_transaction_id)
```

Allowed disposition meanings:

```text
APPLIED
IDEMPOTENT
OBSERVED_NO_PROJECTION
IGNORED_OTHER_INSTRUMENT
```

`normalized_digest` is a deterministic digest of the normalized immutable
provider facts used to detect conflicting replay.

Do not persist secrets, authorization headers, or raw provider payloads in this
receipt.

Replay of the same account + transaction ID with the same immutable digest is
idempotent.

Replay with a different immutable digest is a CRITICAL provider identity
conflict and blocks the Deployment.

## F. Transaction classification

Every transaction in one Account Changes response must reach exactly one durable
classification.

`APPLIED`

- transaction changed canonical Atlas Order/Fill/Position/Trade state and the
  corresponding change was durably applied.

`IDEMPOTENT`

- the same authoritative canonical fact was already durably applied and exact
  replay agreement was proven.

`OBSERVED_NO_PROJECTION`

- the transaction type is explicitly understood and does not require a canonical
  PAPER 01 Order/Fill/Position/Trade mutation.

`IGNORED_OTHER_INSTRUMENT`

- the transaction is for an instrument outside the selected EUR/USD Deployment
  and does not conflict with account-level safety.

An unknown provider transaction type is never silently ignored.

An unattributed or conflicting EUR/USD execution/order/trade transaction blocks
reconciliation.

A provider transaction whose effect on selected-account exposure cannot be
proven harmless blocks reconciliation.

## G. Cursor transactionality

All of the following belong to one database transaction:

- transaction-receipt insert/deduplication;
- canonical projection application required by those receipts;
- reconciliation evidence;
- final durable cursor update.

If any transaction fails classification/application:

- roll back the whole reconciliation application;
- leave the old durable cursor unchanged;
- persist the safety failure using the existing clean safety-transaction path;
- enter/remain RECONCILIATION_REQUIRED;
- block new exposure.

Cursor advancement is the last write in the successful reconciliation
transaction.

## H. Initial cursor baseline

For a brand-new PAPER Deployment with no durable broker cursor and no existing
broker-linked execution facts, Atlas does not import the account's entire history.

It may establish an initial cursor baseline only after a current authoritative
account reconciliation proves:

- correct selected Practice account;
- EUR/USD has no open Trade;
- EUR/USD has no non-zero Position side;
- there is no pending EUR/USD opening Order attributable to or conflicting with
  Atlas;
- no unresolved local broker-linked execution fact exists.

After that flat baseline is durably recorded, the current provider
`lastTransactionID` becomes the initial durable cursor.

If local execution facts already exist, or current EUR/USD broker state is not
provably flat/clean, cursor baselining is forbidden and reconciliation blocks.

## I. Startup / resume cursor gate

START, RESUME, reconnect, ownership reacquisition, and UNKNOWN recovery must not
allow new exposure until Account Changes reconciliation has caught the durable
cursor up to a current successful provider fence.

If the provider has observed newer transactions than Atlas's durable cursor,
new exposure remains blocked until those changes are reconciled.

## Required tests

Protection:

- same provider ID for stop and target rejected;
- foreign Trade linkage rejected;
- missing stop/target rejected;
- wrong price rejected;
- wrong current Trade quantity rejected;
- stale Trade state rejected;
- authoritative Fill persists even when protection confirmation fails;
- failed protection blocks new exposure.

Cursor:

- compound submission response does not advance durable cursor;
- Account Changes with multiple transactions receipts every transaction before
  cursor advancement;
- matching Fill replay is idempotent;
- unrelated non-EUR/USD transaction is durably classified and does not stall the
  account cursor;
- unattributed EUR/USD transaction blocks;
- unknown exposure-relevant transaction blocks;
- receipt replay with changed immutable facts blocks;
- transaction application failure rolls back receipts/projections/cursor;
- cursor advances only as final successful transaction step;
- restart from old cursor replays through Account Changes safely;
- new Deployment flat baseline initializes cursor;
- baseline with existing EUR/USD exposure blocks.

---

# C005 — Closure gates, not application redesign

C005 begins only after C001-C004 pass validation and independent review.

## F-07 — session-policy provenance

The PAPER runtime may not reach actual RUNNING until the official OANDA
Corporation session-policy provenance is pinned.

For EUR/USD PAPER 01, the pinned standard policy must represent the currently
validated OANDA Corporation US FX schedule:

- timezone authority: New York / America/New_York;
- standard FX opening: Sunday 17:05 New York time;
- standard FX weekly close: Friday 16:59 New York time;
- daily maintenance break: 16:59 through 17:05 New York time;
- holiday/exception schedule is separate provider provenance and overrides the
  standard schedule where applicable;
- provider live `tradeable` remains an independent immediate execution gate.

The provenance file must record:

- official source title;
- official source URL;
- retrieval date;
- policy identifier/version;
- timezone;
- standard effective schedule;
- official holiday/exception source title and URL;
- applicable published exceptions for the activation period.

Do not silently infer future holiday hours.

If the official exception source does not cover the intended activation date,
activation remains blocked.

## F-09 — PostgreSQL proof

Before READY_TO_ACTIVATE, provide a dedicated isolated PostgreSQL database whose
database name ends in `_test`.

Run, against PostgreSQL rather than SQLite/fakes:

- full migration upgrade through the PAPER migrations;
- `alembic check`;
- root ownership constraints;
- Strategy state/frontier uniqueness and transactionality;
- one-ENTRY-Order-per-TradeIntent concurrency;
- Fill identity uniqueness and collision rollback/re-read;
- OANDA transaction-receipt uniqueness and conflicting replay;
- reconciliation receipt/projection/cursor rollback;
- cursor-last-write ordering;
- protection persistence constraints;
- numeric and UTC round trips;
- Deployment advisory-lock exclusivity;
- heartbeat/ownership loss behavior.

No application behavior may be weakened to make a PostgreSQL test pass.

Environment setup is not authorization to activate PAPER.

---

# Validation sequence

After C001-C004 implementation:

```text
BUILD
→ targeted tests for C001-C004
→ full non-capital backend suite
→ PostgreSQL tests where available
→ independent implementation-closure review
```

The independent review must review the complete capital boundary once, not only
the files changed by the last finding.

The reviewer must map every row of the previously produced invariant closure
matrix to PASS / FAIL / UNVERIFIED.

No known PRODUCT, CRITICAL, or IMPORTANT PAPER safety finding may remain hidden
behind a passing unit suite.

If C001-C004 pass but F-07 or F-09 remains open:

```text
STOP — NOT READY_TO_ACTIVATE
```

After F-07 and F-09 pass:

```text
final independent PAPER 01 review
→ READY_TO_ACTIVATE
```

`READY_TO_ACTIVATE` is not activation.

Actual OANDA Practice activation remains a separate explicit trader approval.

---

# Hard scope boundaries

This closure does not authorize:

- PAPER 02;
- general multi-Fill/partial-Fill recovery;
- closed-Trade lifecycle reconstruction;
- multiple active Deployments per account/instrument;
- another broker;
- LIVE;
- Strategy Studio;
- arbitrary provider transaction-ledger expansion beyond the minimal receipt
  required above;
- credentials changes;
- Risk-policy changes;
- mutating OANDA calls during implementation or non-capital validation.

The normal production builder must remain capital-inert by default.

No test may require a real mutating OANDA request.

---

# Completion condition

PAPER 01 implementation closure is complete only when:

1. C001 passes;
2. C002 passes;
3. C003 passes;
4. C004 passes;
5. the complete invariant matrix is independently rereviewed;
6. F-07 is pinned and validated;
7. F-09 PostgreSQL evidence passes;
8. no unresolved Critical/Important PRODUCT safety finding remains.

Only then may the workstream claim:

`READY_TO_ACTIVATE`

and stop for separate trader activation approval.
