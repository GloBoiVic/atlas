# PAPER 01 — Bounded OANDA Practice Architecture

**Status:** `FROZEN FOR DEVELOPER REVIEW`
**Workstream:** `paper-01`
**Baseline:** `main` at `e671190ae4a77282367f2cecfa27ef45a375add1`
**Authority:** `dispatch/workstreams/pre-paper-audit/AUDIT.md`, then the current
architecture and feature contracts named below.

This is a planning contract. It authorizes no implementation, BUILD task,
branch start, credential change, Risk-policy change, PAPER activation, or OANDA
mutation.

## 1. Decision and bounded outcome

PAPER 01 proves one narrow, real-broker lifecycle:

```text
explicit Practice account
  → one Deployment
  → completed native OANDA M15 MID bar
  → EMA Sweep Confirmation Break v2
  → TradeIntent
  → PRE_FLIGHT RiskDecision
  → post-decision BID/ASK observation
  → PRE_SUBMISSION RiskDecision
  → OANDA MARKET/FOK Order
  → authoritative OANDA Fill
  → canonical Position and Trade
  → broker-hosted stop and 1.7R target
  → reconciliation
```

The slice is fixed to OANDA Practice (`PAPER`), one explicitly selected USD
account, EUR/USD, one Deployment, at most one Position, and at most one pending
opening setup. It uses the existing immutable `EMA Sweep Confirmation Break v2`
StrategyVersion and the same Strategy/Risk/Order/Fill/Position/Trade meanings as
Experiments. It is not permission to run that lifecycle yet.

### Explicitly out of scope

- OANDA Live, another broker, another account, another Instrument, or a second
  Deployment for the selected account/instrument.
- IOC, limit entry, smart execution, pyramiding, instant reversal, trailing
  protection, partial exits, or manual exposure automation.
- General partial-fill, remaining-unit, reissue, prolonged-downtime,
  self-healing, or broad manual-drift machinery. Those are PAPER 02 concerns;
  PAPER 01 must fail closed when they occur.
- A PaperOrder, PaperTrade, PaperPosition, PaperStrategy, worker-per-Deployment,
  queue, broker plugin framework, Redis, distributed coordinator, or browser-owned
  runtime.
- Any change to the meaning of a completed Experiment, DatasetSnapshot,
  StrategyVersion, Strategy boundary, Risk ownership, native M15/M1 products,
  Fill authority, or broker authority.

## 2. Contract authority and ownership

| Concern                                   | Sole owner                                            | PAPER 01 rule                                                                                                                                      |
| ----------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strategy methodology and state transition | Existing Strategy implementation                      | Pure `StrategyContext`/state evaluation; no broker, account, database, clock, or environment I/O.                                                  |
| StrategyVersion identity                  | Strategy catalog/domain                               | Reuse the immutable v2 identity, source fingerprint, parameter schema, M15/MID requirements, warm-up, capabilities, and state schema.              |
| Market data and frontier                  | Runtime market-data composition                       | Normalize OANDA data before Strategy; emit only completed native M15 MID bars and post-frontier sparse BID/ASK execution observations.             |
| Account identity and broker facts         | OANDA integration + TradingAccount boundary           | Explicit account ID; normalize account, instrument, quote, margin, tradeability, capability, and session facts. No OANDA DTO crosses the boundary. |
| Entry authorization and quantity          | Central Risk service                                  | PRE_FLIGHT followed immediately by PRE_SUBMISSION. Only an approved PRE_SUBMISSION decision authorizes a new entry.                                |
| Order submission and broker responses     | OANDA execution adapter, called only by atlas-runtime | Translate canonical Orders to OANDA MARKET/FOK requests; normalize all responses and preserve external identities.                                 |
| Exposure accounting                       | Canonical Fill application                            | A confirmed Fill alone changes Position/Trade/account projections. Submission or an Order status never creates exposure.                           |
| Actual broker state                       | OANDA                                                 | In PAPER, broker Orders, Fills, Trades, Positions, protection, and account exposure win over local projections.                                    |
| Desired state and local control           | API + PostgreSQL                                      | API records explicit commands; loopback/local Atlas authority is retained. API does not submit Orders.                                             |
| Ongoing execution and lifecycle           | One owning atlas-runtime process                      | Runtime owns data, Strategy, Risk composition, execution, reconciliation, health, and shutdown behavior.                                           |

The existing Experiment runner remains a separate historical composition using
`SimulationClock`, `SimulatedExecutionAdapter`, and simulated account state. A
PAPER runtime may reuse domain contracts and pure services, but must not route an
Experiment through broker code or alter historical assumptions.

## 3. Immutable Experiment and Strategy contracts

PAPER must instantiate the same registered StrategyVersion and equivalent typed
parameter snapshot used by an Experiment. A PAPER Deployment is not an
Experiment and has no DatasetSnapshot. It records live provider and runtime
provenance separately.

The following Experiment contracts are exact and remain unchanged:

- An Experiment is an immutable historical simulation with
  StrategyVersion, Instrument, parameter snapshot, DatasetSnapshot, UTC date
  range, starting account state, immutable Risk snapshot, simulation
  configuration, engine/version provenance, and resulting canonical facts.
- Historical analysis is provider-native OANDA M15 MID. Sparse provider-native
  M1 BID/ASK is execution data only; M1 never substitutes for M15.
- `SimulationClock` exposes only information available at its frontier. The
  signal bar is not reused as post-decision execution data.
- Historical Strategy evaluation, Risk phases, canonical Order/Fill/Position/
  Trade chain, actual-entry target calculation, accounting, and deterministic
  replay remain as specified in `context/features/experiments.md`.
- Completed Experiments, their configuration, DatasetSnapshots, TradeIntents,
  RiskDecisions, Fills, and completed facts remain immutable. A correction or
  rerun creates new provenance; it does not rewrite an old Experiment.
- Existing historical tests and golden flows must continue to pass. A shared
  persistence extension must preserve all existing Experiment foreign-key,
  uniqueness, status, result, and deletion semantics.

PAPER uses the same v2 methodology: 100 completed M15 bars for warm-up; EMA
100, ATR 14, 0.5 ATR stop buffer, 1.7R target, same-bar sweep/confirmation,
and five received completed M15 watch bars. No live-specific Strategy branch,
timeframe, or sizing logic is permitted.

## 4. Account, Instrument, and Deployment boundary

### 4.1 Explicit TradingAccount

The account configuration must contain a human-readable label, broker `OANDA`,
environment `Practice`, explicit external OANDA account ID, mode `PAPER`, and
base currency `USD`. A token is server-side configuration only; it is never
stored in the database, sent by the client, returned by the API, or written to
logs/diagnostics. If the authorized account list contains multiple accounts,
Atlas must reject an absent or non-matching selected account. It must never pick
the first account.

Connection validation is read-only: authorized account identity, account
summary, EUR/USD VenueInstrument (`EUR_USD`), required capabilities, and current
state must all validate before START can succeed. Validation never submits an
Order. Cached account values are monitoring facts, not authority when OANDA is
unreachable. OANDA MT4-associated accounts are explicitly unsupported for PAPER
01: if the account facts report an MT4 association (including an
`mt4AccountID`), account validation and START reject the account because stable
`clientExtensions` correlation is required. There is no alternate correlation
contract and no fallback to an MT4-compatible submission mode.

### 4.2 Normalized broker facts

The OANDA integration owns provider models and maps them to small canonical
values:

- `AccountSnapshot`: selected account identity, USD base currency, balance/NAV,
  unrealized P/L, equity, margin available, margin used, timestamp, freshness,
  source, and normalized current pending Orders/open Trades/Position sides.
- `VenueInstrumentFacts`: EUR/USD mapping, price precision, trade-unit
  precision/increment, minimum and maximum order/position units, margin rate,
  supported LONG/SHORT/MARKET/STOP_LOSS/TAKE_PROFIT capabilities, and current
  availability.
- `ExecutableQuote`: complete positive BID and ASK, quote timestamp, source,
  tradeability, closeout metadata where needed, and provider provenance. BUY
  uses ASK; SELL uses BID. A missing side, stale quote, non-tradeable quote, or
  unknown timestamp is not an executable quote.

These facts are explicit inputs to Risk and runtime gates. Strategy receives none
of balance, equity, margin, tradeability, provider identity, or credentials.
The initial USD/EUR/USD economics may use the existing simple calculation, but
the boundary must retain currency/conversion fields rather than scattering a
USD assumption through generic code.

### 4.3 Deployment configuration and state

A Deployment stores exactly one StrategyVersion, one TradingAccount, EUR/USD,
typed parameter snapshot, immutable Risk snapshot, mode, and live execution
provenance. It is persistent configuration, not the runtime process. Before its
first trade it may be DRAFT-editable; after it has traded, changes to any
trading-relevant identity/configuration require a new or cloned Deployment.

The database enforces at most one active Deployment for the selected
TradingAccount + EUR/USD. The Deployment also owns at most one current Position
and one pending opening setup. These are transactional invariants, not UI rules.

Desired state is trader intent; actual state is runtime fact:

| Desired command/state   | Actual transition and meaning                                                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| DRAFT                   | No ownership and no trading.                                                                                                               |
| START                   | API durably records desired `RUNNING`; it does not report activation. Runtime enters `STARTING`.                                           |
| RUNNING                 | Allowed only after ownership, account/capability checks, session-policy gate, reconciliation, state restore, warm-up, and fresh data pass. |
| PAUSE                   | No new exposure; market data and safe risk-reducing management may continue; existing protection is untouched.                             |
| RESUME                  | Fresh broker reconciliation, state validation, and freshness checks are required before `RUNNING`.                                         |
| STOP                    | No new exposure. It reaches `STOPPED` only when flat; STOP with open exposure is blocked and requires safe management/reconciliation.      |
| FAILED                  | New exposure blocked, reason and safety facts persisted, broker protection preserved; no speculative automatic recovery.                   |
| RECONCILIATION_REQUIRED | Local state cannot be proven against broker truth; new exposure blocked until explicit reconciliation succeeds.                            |
| ARCHIVED                | Historical configuration only; cannot activate.                                                                                            |

`STARTING` is the bounded runtime transitional state, not a second trader
command. Actual `RUNNING` is never inferred from a process being alive or from
desired state alone. Idempotent START does not create a second ownership claim,
runtime, or Order.

## 5. Strategy continuity and live data frontier

### 5.1 Native products and completed-bar scheduling

The runtime uses the existing OANDA normalization seam, extended for bounded
live polling (REST initially, not a streaming platform):

1. Request native EUR/USD M15 MID and determine completion from the provider and
   elapsed UTC half-open interval `[start, end)`.
2. Normalize only UTC, quarter-hour-aligned, complete bars to canonical `Bar`.
3. Persist/deduplicate bars and advance a durable completed-M15 frontier only
   after the bar is valid and committed.
4. Evaluate v2 once for each new completed M15 frontier, in chronological order.

Sparse native M1 BID/ASK observations are an execution observation source, not
an analytical source. Execution eligibility is strict: an M1 observation is
eligible only when `observation.start_time > decision_time`; an observation whose
start equals the decision frontier is ineligible. The exact Experiment trigger
predicate is reused, not a current-tick substitute: LONG is
`ASK open > trigger OR ASK high >= trigger`; SHORT is
`BID open < trigger OR BID low <= trigger`. Neither the decision bar's prices
nor a retrospective signal-close fill is eligible. No forward-fill,
interpolation, aggregation of M1 into authoritative M15, or fabricated
execution price is allowed. Both BID and ASK are required for an executable
observation; a missing minute remains unavailable.

The runtime persists freshness/heartbeat and distinguishes healthy, stale,
disconnected, expected session closure, and unexpected missing data. Stale,
disconnected, malformed, duplicate-conflicting, or out-of-order data blocks new
exposure. Expected closure does not fabricate bars.

### 5.2 Warm-up and state

Before exposure is allowed, the runtime loads the required 100 completed native
M15 MID bars and validates the v2 state schema. Warm-up may initialize state but
cannot create a TradeIntent or exposure. If state is missing, corrupt, or not
compatible with the immutable StrategyVersion, the Deployment fails closed; it
must not silently reset to SEARCHING.

Persist a small versioned state envelope linked to Deployment + StrategyVersion:
phase, direction, reference high/low/time, sweep/confirmation time, trigger,
received-bar watch count, and `last_evaluated_bar_end`. Do not persist indicator
objects, DataFrames, broker clients, or runtime references.

### 5.3 Pending-entry handoff

At a v2 price-triggered OPEN decision, one short local transaction must persist:

- the new Strategy state/frontier;
- the immutable canonical TradeIntent containing decision frontier, action,
  direction, proposed stop, target methodology/multiple, trigger and BID/ASK
  basis, rationale, setup facts, and evidence; and
- a durable pending-entry handoff identifying that intent and its `PENDING`
  lifecycle.

The idempotency key is Deployment + decision frontier. A restart therefore cannot
create a second intent for the same completed bar. M1 observations inspect the
handoff; they do not call Strategy. The handoff is eligible only when
`observation.start_time > decision_time` (frontier equality is ineligible). For
long, the exact Experiment predicate is `ASK open > trigger OR ASK high >=
trigger`; for short it is `BID open < trigger OR BID low <= trigger`. The first
observation satisfying the applicable predicate is considered.

`StrategyStateEnvelope.pending_entry` is the sole methodology authority for the
trigger, decision frontier, direction, and received-bar watch count. A runtime
pending-entry row, if used, is only a lifecycle/status/link row to the canonical
TradeIntent and envelope; it must not carry an independent trigger, frontier, or
watch-count truth. A missing, stale, or inconsistent row/envelope linkage blocks
entry and requires state repair or reconciliation rather than choosing one value.

The handoff is terminal when filled, rejected by Risk, expired at the v2 W6
frontier, or blocked by a safety condition. The same stale intent is never
retried blindly. W1–W5 count received completed analytical bars, W5 remains
execution-eligible, and expiry is observed at W6. Catch-up reconstructs state
chronologically but does not execute stale opportunities.

If exposure becomes disallowed or Position is non-FLAT, the Strategy contract
requires NO_ACTION, cleared pending setup, SEARCHING, and frontier-only advance.
This rule is not bypassed by the handoff.

## 6. Risk contract

Risk remains centralized, pure, and external to Strategy and execution. The
PAPER composition adapts the current Experiment-named eligibility seam to
explicit Deployment/account facts; it does not change the meaning of
`risk_per_trade` or create a PAPER Risk implementation.

### 6.1 Sole authorization sequence

For every opening TradeIntent, the runtime must execute exactly:

1. Persist an immutable `PRE_FLIGHT` RiskDecision. It checks active Deployment
   eligibility, Strategy/parameter compatibility, flat Position, account
   identity/mode/base currency, known fresh account state, Risk snapshot,
   instrument capabilities, stop direction/positivity, and relevant limits.
2. If approved, obtain a fresh post-decision executable BID/ASK observation and
   current normalized venue/account facts.
3. Immediately persist an immutable `PRE_SUBMISSION` RiskDecision. It selects
   ASK for long or BID for short, validates stop geometry, tradeability,
   precision/min/max rules, available margin, maximum position, current flat
   exposure, and all safety gates, then determines final quantity. For PAPER,
   `target_price` on this RiskDecision is explicitly `NULL`/not final. The
   decision preserves the approved stop, the immutable Strategy target
   methodology/multiple from the TradeIntent, and immutable quote/executable
   evidence; it never stores a quote-derived final target.
4. Only an approved PRE_SUBMISSION decision may create or submit an ENTRY Order.

No Strategy decision, pending handoff, API command, adapter convenience method,
or cached approval is an alternative authorization. PRE_FLIGHT approval is not
permission to submit. Any unknown account, Position, margin, venue capability,
quote, tradeability, ownership, reconciliation, or safety state is rejected or
blocked and recorded.

### 6.2 Conservative sizing and price bound

Risk budget remains `current broker-authoritative equity × risk_per_trade`.
Quantity is calculated from the executable side and stop distance, then rounded
down to provider-valid units/precision. The result must satisfy minimums,
maximums, maximum position, available-margin requirements, and
`actual_risk <= budget`; a quantity below the provider minimum is rejected.
Decimal arithmetic is authoritative. Rounding may reduce exposure, never
increase it.

The MARKET/FOK request must carry a provider-valid worst-executable constraint:
for this initial slice the conservative default is the current normalized
executable side after provider precision (`BUY priceBound = ASK`, `SELL
priceBound = BID`), with no invented slippage allowance. If a future approved
configuration permits a wider bound, quantity must instead be sized against the
adverse edge of that bound and the bound must be an immutable, auditable
Deployment/Risk fact. If a safe bound cannot be represented, PRE_SUBMISSION is
rejected. FOK plus the bound means movement outside the approved geometry is a
rejection, not an excuse to increase quantity or retry.

The actual Fill remains authoritative even when it is within the bound. Target
calculation uses that Fill, not the quote, trigger, or confirmation close. For
PAPER the final 1.7R target does not exist as a RiskDecision target before the
entry Fill; it is calculated only after that authoritative Fill. Existing
Experiment PRE_SUBMISSION target behavior remains exactly unchanged.

## 7. Canonical OANDA execution

### 7.1 One adapter and canonical nouns

Extend the existing narrow execution boundary with one OANDA adapter. Provider
request/response models remain inside `backend/integrations/oanda`; the rest of
Atlas sees canonical Order, OrderEvent, Fill, Position, and Trade facts. Existing
Experiment rows retain their Experiment ownership. Shared canonical tables gain
an explicit ownership seam with the following exact rule: each `TradeIntent`,
`Order`, `Position`, and `Trade` is directly owned by exactly one root,
`Experiment` or `Deployment`, never both and never neither. A PAPER row is
directly owned by its Deployment and never receives a fabricated `experiment_id`.

`RiskDecision` is owned transitively by its TradeIntent, and `Fill` is owned
transitively by its Order. Every cross-link must resolve to the same root owner:
an Order's TradeIntent and RiskDecision, a Fill's Order, a Trade's intent and
entry/exit Orders, and all Position/Trade projections must not cross from an
Experiment to a Deployment or between Deployments. The database must enforce
this with mutually exclusive non-null root ownership, foreign keys/constraints
and transactional validation of cross-links (a trigger or equivalent guarded
write is acceptable). Repository code must not be able to create a rootless or
dual-owned fact. Existing Experiment foreign keys and constraints remain valid.

An entry Order is `MARKET`, purpose `ENTRY`, signed according to OANDA's unit
convention, and `FOK`. IOC is unsupported and must be rejected before any
provider request. Limit-entry and other order types are out of this slice.
The Atlas Order ID remains local. A stable correlation/client-extension value
is tied to it and is reused for reconciliation; it is never regenerated after a
timeout.

### 7.2 Submission and response rules

Before network submission, commit `PENDING_SUBMISSION` Order, its correlation,
TradeIntent, approved PRE_SUBMISSION RiskDecision, null/not-final PAPER target,
approved stop, target methodology/multiple, immutable quote/executable evidence,
priceBound, and request provenance. Do not hold a database transaction open
during the network call.

Normalize OANDA create responses that may contain create, fill, cancel, reject,
reissue, and related transactions. Preserve, where supplied:

- external OANDA Order ID;
- OANDA Trade ID(s), signed initial/current units and open/close references;
- Fill execution ID, units, price, time, fees, and transaction ID;
- create/fill/cancel/reject/reissue/related transaction IDs;
- provider request ID and sanitized status diagnostics; and
- account-scoped `lastTransactionID` cursor evidence.

Known rejection/cancellation becomes a canonical rejected/canceled Order with a
reason and immutable OrderEvent. A timeout, malformed/incomplete response, or
inability to establish whether the Order exists becomes `UNKNOWN`; it is not a
rejection and never triggers an immediate retry. The runtime enters a safety
blocked/reconciliation-required path and queries broker truth using correlation,
external IDs, account snapshots, and transaction history.

PAPER 01 is full-fill-only operationally. A response that is partial, reissued,
or otherwise ambiguous is never promoted to a full Fill or full Position. It is
persisted as an explicit broker fact/event as far as the canonical schema allows,
new exposure is blocked, protection is preserved/verified, and the Deployment
becomes `FAILED` or `RECONCILIATION_REQUIRED`. PAPER 01 does not complete,
reissue, or manage remaining units. General `PARTIALLY_FILLED` accounting and
recovery across multiple Fills is PAPER 02, but PAPER 01 must not lie about the
executed quantity while waiting for it.

### 7.3 Fill authority and protection

For a confirmed full entry Fill, apply the Fill transactionally to Order,
Position, Trade, and any local account projection. The resulting Position
quantity is executed quantity; no submission assumption creates exposure.

The entry request must use OANDA-hosted stop-loss-on-fill protection with the
approved stop whenever the required capability is advertised. If the capability
is absent, the Deployment cannot pass START; it must not submit an unprotected
entry. The stop is the primary immediate protection and must be visible in the
authoritative response/reconciliation.

Only after the authoritative Fill is known does execution calculate the final
target; no quote-derived target is represented as final in the PAPER
PRE_SUBMISSION RiskDecision:

```text
long:  target = fill_price + 1.7 × (fill_price - approved_stop)
short: target = fill_price - 1.7 × (approved_stop - fill_price)
```

The target is a broker-hosted TAKE_PROFIT instruction attached to the linked OANDA Trade at the actual-Fill-derived target price, covering that Trade’s remaining exposure and preserving Atlas correlation lineage. Atlas must confirm
both stop and target in broker state before actual `RUNNING` or normal new-entry
operation. A missing stop, missing target, wrong quantity/price, orphan
protection, failed follow-up, or ambiguous protection state is a critical safety
condition: persist a SystemEvent, block new exposure, and enter FAILED or
RECONCILIATION_REQUIRED. Do not treat a local Order row as broker protection.
Shutdown, PAUSE, and runtime failure must not cancel valid broker-hosted
protection.

Protective stop/target Fills use the same canonical Fill application. A stop Fill
closes the Trade with `STOP_LOSS`; a target Fill closes it with `TAKE_PROFIT`.
PAPER 01 has no normal partial exit. No conflicting sibling protection may
remain capable of creating unintended exposure after a closing Fill.

## 8. Reconciliation and broker authority

### 8.1 Required triggers and outcomes

The owning runtime reconciles at startup, START, RESUME, broker reconnect,
uncertain submission, detected mismatch, and explicit local reconcile command.
Every attempt has a durable trigger, start/end times, outcome, summary, and
linked canonical repair facts. Outcomes are:

- `MATCHED`: local and broker facts agree sufficiently and all safety gates pass.
- `REPAIRED`: broker truth was clear; missing Fills or projections were rebuilt
  transactionally and auditably, then verified.
- `RECONCILIATION_REQUIRED`: identity, quantity, direction, protection, history,
  account, or broker availability is ambiguous. New exposure remains blocked;
  there is no automatic resume.

### 8.2 Startup/reconnect ordering

The runtime must not set actual `RUNNING` until this ordered sequence succeeds:

1. Load desired Deployments and acquire the single-runtime/PostgreSQL ownership
   lock for the selected Deployment.
2. Mark actual `STARTING`, persist heartbeat/health, and block exposure.
3. Validate explicit Practice account binding, capabilities, pinned session
   policy, and broker connectivity.
4. Fetch account summary, pending Orders, open Trades, Positions, protection,
   and transaction pages/details. A non-empty OANDA instrument Position row is
   not exposure by itself; inspect long/short units and open Trades.
5. Reconcile local Orders/Fills/Position/Trade and pending handoff. Recover a
   missed unambiguous Fill through the same Fill application; deduplicate by
   external execution/transaction identity.
6. Restore and validate Strategy state and frontier, load required warm-up, and
   catch up completed M15 bars chronologically. Catch-up may reconstruct state;
   it never executes a stale entry.
7. Validate current data freshness, tradeability, flat/open Position rules, and
   required protection. Only then set actual `RUNNING` (or retain PAUSED when
   desired state is PAUSED).

Reconnect repeats broker retrieval and reconciliation. Reconnect alone never
resumes trading. Broker unavailable, incomplete transaction history, stale data,
unknown owner, unknown Order, manual EUR/USD activity, local/broker mismatch,
or missing protection leaves new exposure blocked.

### 8.3 Unknown and mismatch matrix

| Condition                                      | PAPER 01 action                                                                                                 |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Submission timeout                             | Order `UNKNOWN`; persist uncertainty; reconcile; no blind retry.                                                |
| Unknown Order found with full unambiguous Fill | Ingest/deduplicate Fill, verify protection, repair projections, then resume only if all gates pass.             |
| Unknown Order proven absent                    | Do not reuse stale approval; rerun PRE_SUBMISSION with fresh facts before any separately approved retry.        |
| Unknown Order ambiguous                        | `RECONCILIATION_REQUIRED`; no retry.                                                                            |
| Local FLAT, broker exposed                     | Attribute only with clear canonical correlation/history; otherwise do not claim it and require reconciliation.  |
| Local exposed, broker FLAT                     | Search authoritative transactions for the exit; repair only when unambiguous, otherwise require reconciliation. |
| Direction or quantity mismatch                 | Broker wins; repair only from unambiguous transactions; never auto-reverse or fabricate quantity.               |
| Manual/conflicting EUR/USD activity            | Treat as relevant account drift; block new exposure and surface the mismatch.                                   |
| Missing/wrong/orphan protection                | Critical safety event; preserve valid protection, block exposure, require repair/reconciliation.                |
| Partial/reissue response                       | Fail closed; no full-fill assertion or automated continuation; PAPER 02 owns general handling.                  |

The account `lastTransactionID` cursor advances only after all corresponding
transactions have been normalized, deduplicated, and durably applied. A cursor
must never advance past unapplied or ambiguous evidence. Repeated reconciliation
against unchanged broker state is idempotent and does not duplicate Fills,
Trades, Position changes, or submissions.

These hold decisions are also failure decisions, not merely data-shape
preferences:

| Failure fact                                                                       | Required result                                                                                                                                   |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `observation.start_time == decision_time`, even when the trigger predicate is true | Observation is ineligible; no Risk evaluation or Order is created from it.                                                                        |
| PAPER `PRE_SUBMISSION.target_price` is non-NULL or was derived from a quote        | Invalid PAPER Risk persistence; no entry authorization or Order. Final target may be created only from an authoritative Fill.                     |
| A canonical fact is rootless, dual-owned, or cross-linked to another root          | Reject the local transaction, persist the integrity/safety failure, and block new exposure; never repair ownership by inventing an Experiment ID. |
| `StrategyStateEnvelope.pending_entry` disagrees with a lifecycle/link row          | Treat methodology state as invalid/uncertain; block the handoff and require state repair/reconciliation.                                          |
| Deployment advisory-lock session or database connectivity is lost                  | Block new exposure immediately; do not finish or restart an in-flight authorization. Reacquisition requires reconciliation before RUNNING.        |
| Account is MT4-associated or the association cannot be safely established          | Reject account validation/START; do not submit and do not fall back to another correlation scheme.                                                |

## 9. Session-policy provenance gate

The current source and audit contain a material documentation contradiction that
must remain visible:

- `backend/market_data/session_policy.py` executes `OANDA_FX_NY_V2` with
  America/New_York rollover rules and dated exceptions.
- `backend/market_data/oanda_session_policy_provenance.md` identifies V1 and
  still contains `OANDA_DOC_PENDING` for the official URL, title, effective
  interval, and notice metadata.
- The audit records the implementation as V2 but explicitly requires the
  current official source and effective-date policy to be pinned before PAPER
  activation.

This architecture does not silently choose V1 or V2 and does not treat the
existing comments/holiday table as documentary proof. Before `READY_TO_ACTIVATE`
and before actual PAPER activation, the versioned policy provenance must contain
the official OANDA session/trading-hours source URL, exact title, retrieval date,
effective interval, timezone, and each applicable notice/exception identifier.
The live gate uses the pinned version and provider `tradeable`/response state;
an expected closure never fabricates a bar. Existing historical snapshots keep
their recorded policy/version semantics. Until this gate is satisfied, START
cannot reach actual `RUNNING`.

## 10. Persistence, locking, and idempotency

PostgreSQL remains the sole durable state and coordination store; all timestamps
are timezone-aware UTC and financial values are NUMERIC/Decimal. No database
transaction remains open during a broker or data network request.

The minimum PAPER extension is logically:

- `trading_accounts` with explicit external identity, mode, non-secret config,
  capabilities, MT4-association result, and connection status. MT4-associated
  Practice accounts are rejected before START;
- `deployments` with immutable trading configuration/Risk snapshot, desired and
  actual state, safety reason, and first-trade/provenance timestamps;
- versioned `strategy_states` and a durable completed-M15/data freshness frontier;
- a pending-entry handoff linked to the canonical TradeIntent;
- current normalized account/instrument/quote facts and their source timestamps;
- shared canonical Order/RiskDecision/Fill/Position/Trade ownership and broker
  identity fields, with exact direct/transitive root ownership and cross-link
  invariants, without Experiment ID fabrication. The PAPER RiskDecision
  persistence shape keeps `target_price` nullable and NULL/not-final at
  PRE_SUBMISSION while retaining approved stop, target methodology/multiple,
  and immutable quote/executable evidence. Existing Experiment RiskDecision
  target persistence is not changed;
- append-only OrderEvents/SystemEvents and reconciliation records;
- external OANDA Order/Trade/Fill/Transaction/request IDs, client correlation,
  related transaction evidence, and account transaction cursor; and
- runtime ownership/heartbeat/health and persistent safety state.

Exact table/column names are an implementation concern, but constraints must
enforce: one active Deployment per account/instrument; one Position per
Deployment; one pending opening setup; unique decision-frontier idempotency;
unique stable client correlation; unique external execution identity where
provider-guaranteed; and no duplicate canonical Fill on replay. Existing
Experiment constraints and rows remain readable and semantically unchanged.

Runtime ownership uses one concrete session-level PostgreSQL advisory lock per
Deployment: a dedicated database session acquires `pg_advisory_lock` on the
stable 64-bit key derived from that Deployment UUID and holds it for the runtime
ownership session. This is deliberately a session-level lock, not a
transaction-local lock, row lease, or interchangeable ownership scheme. The
same owner persists durable heartbeat and health facts (including lock/DB
connectivity state). A second runtime cannot acquire the Deployment lock.

If the lock session is lost, lock ownership cannot be proven, or database
connectivity is lost, new exposure is blocked immediately and the runtime does
not submit or continue an in-flight authorization. Reacquiring the lock always
requires the full broker reconciliation, Strategy-state validation, frontier
recovery, freshness, and protection gates before actual `RUNNING`; lock
reacquisition alone never resumes trading. Short row transactions still
serialize the Deployment frontier, handoff, Position, and submission-state
transitions. Persist PENDING_SUBMISSION, commit, perform the external request,
then persist normalized results.

Provider payloads may be retained only as bounded, sanitized technical evidence
where required for reconciliation. Never persist tokens, authorization headers,
raw secret-bearing payloads, or unsanitized provider exception text.

## 11. Runtime ownership, restart, and shutdown

`atlas-runtime` is one long-running process with ordinary in-process modules for
market data, Strategy, Risk, execution, and reconciliation. It is not a
microservice collection. The browser cannot keep trading alive.

On normal shutdown, the runtime stops new exposure, persists Strategy state,
frontier, pending handoff, health, and ownership facts, avoids new submissions,
and leaves valid broker-hosted protection untouched. STOP remains subject to the
flat-position rule. On unexpected death, in-memory state is untrusted; the next
startup follows the full ownership → broker reconciliation → state restore →
data catch-up sequence before any resume. A process being restarted, a database
being reachable, or a connection being re-established is never sufficient.

## 12. Required non-capital tests

The implementation phase must add deterministic, mocked, or recorded-shape
tests without calling a mutating OANDA endpoint. Credential-dependent tests must
be a separate suite and must remain gated. At minimum:

### Contracts and Experiment parity

- Existing Experiment migrations, golden flows, deterministic replay, result
  fingerprints, immutable configuration, DatasetSnapshot semantics, and all
  existing Strategy conformance tests remain green.
- The same v2 StrategyVersion, parameters, completed M15 MID inputs, state
  serialization, warm-up, state restoration, no-lookahead, duplicate frontier,
  W1–W5/W6 handoff, long/short stop, rationale/evidence, and actual-entry 1.7R
  behavior work identically in the live composition.
- Invalid/corrupt/incompatible state blocks exposure and never silently resets;
  Position non-FLAT and exposure disallowed follow the exact Strategy contract.

### Account, data, and provenance

- Explicit account selection rejects absent, unauthorized, wrong, or first-list
  inference; Practice→PAPER and USD normalization are correct and secrets are
  absent from API/log/diagnostic output.
- MT4-associated Practice accounts are rejected at account validation and START;
  clientExtensions is required for correlation and no alternate identity scheme
  is accepted.
- Account summary, margin, instrument precision/min/max, capabilities,
  tradeability, BID/ASK, redirects, malformed payloads, provider errors,
  timeouts, rate limits, and sanitized diagnostics normalize correctly.
- Native completed M15 finalization, UTC half-open boundaries, sparse BID/ASK,
  post-decision eligibility, no signal-bar reuse, duplicates, out-of-order
  observations, stale/disconnected data, expected closure, unexpected gaps,
  chronological catch-up, and no fabricated bars are tested.
- Session-policy provenance fields and the unresolved V1/V2 placeholder gate
  prevent actual RUNNING until official provenance is pinned.

### Deployment, Risk, and runtime

- Valid/invalid Deployment creation, configuration immutability after trading,
  account/instrument uniqueness, one Position/pending setup, desired versus
  actual state, idempotent START, PAUSE/RESUME/STOP rules, ownership conflict,
  heartbeat, and browser-independent runtime behavior.
- PRE_FLIGHT and immediate PRE_SUBMISSION ordering; rejection for unknown
  account/Position/margin, stale quote, unavailable/tradeability, invalid stop,
  margin, min/max/precision, and market movement; deterministic conservative
  quantity and budget; `PRE_SUBMISSION.target_price IS NULL` for PAPER while
  stop/methodology/multiple/quote evidence remain immutable; priceBound at the
  adverse-safe edge; no alternate entry authorization.
- Warm-up, durable state/frontier, same-bar duplicate prevention, crash between
  state/intent persistence boundaries, pending handoff recovery, stale trigger
  expiry, stale catch-up non-execution, strict `observation.start_time >
decision_time` equality rejection, and the exact LONG/SHORT Experiment
  trigger predicates.

### Execution, protection, reconciliation, and persistence

- Canonical MARKET/FOK mapping, IOC rejection before network, stable correlation,
  PENDING_SUBMISSION commit ordering, successful/rejected/canceled responses,
  compound response normalization, timeout→UNKNOWN, no blind retry, found/absent/
  ambiguous recovery, and external-ID deduplication.
- Full-fill Fill authority and atomic Order→Fill→Position→Trade updates; actual
  Fill target at 1.7R; stop-on-fill request; target attach; broker confirmation;
  missing/wrong/orphan protection; protection preservation through pause,
  shutdown, restart, and broker disconnect.
- Unexpected partial/reissue/ambiguous state fails closed without claiming a
  full Fill; tests explicitly show that PAPER 02 handling is not present.
- Clean/repeated startup reconciliation, missed Fill repair, local/broker flat,
  open, direction, quantity, manual-drift, pending-Order, protection, broker
  unavailable, cursor-gap, cursor replay, and reconnect cases; ambiguous cases
  remain `RECONCILIATION_REQUIRED`.
- Migration up/down or fresh-schema cycle as supported by the repository,
  NUMERIC/Decimal and UTC round trips, foreign-key ownership, unique locks,
  direct/transitive Experiment-vs-Deployment ownership, cross-root-link rejection,
  rootless/dual-owned fact rejection, pending-row/envelope mismatch blocking,
  concurrent duplicate submission prevention, idempotent Fill/reconciliation
  replay, durable safety visibility, session-level Deployment advisory-lock
  exclusivity, lost-lock/DB blocking, reconciliation-required reacquisition,
  and no transaction held over network I/O.

All tests that exercise the OANDA adapter use mocked HTTP/recorded provider
shapes and assert that no POST/PUT/PATCH/DELETE/cancel/close/transfer endpoint
is called. A later capital-capable test is a separate approval-gated activity,
not part of architecture validation.

## 13. PAPER 01 / PAPER 02 boundary

**PAPER 01 owns:** the single explicit Practice account and Deployment; v2
Strategy continuity; native completed M15 MID and post-frontier BID/ASK;
durable state/frontier/pending handoff; normalized account/instrument/margin/
tradeability facts; PRE_FLIGHT then PRE_SUBMISSION; conservative full-fill
quantity and FOK/priceBound entry; canonical broker identities/cursor;
immediate broker-hosted stop; actual-Fill 1.7R target attach/confirm; explicit
START and desired/actual lifecycle; one runtime owner; startup/reconnect/
uncertain-submission reconciliation; fail-closed safety; and pinned official
session-policy provenance before activation. Execution eligibility is strictly
`observation.start_time > decision_time` with the exact Experiment LONG/SHORT
trigger predicates. PAPER PRE_SUBMISSION target is null/not-final until the
authoritative Fill. Direct/transitive root ownership, envelope-owned pending
methodology state, the Deployment session advisory lock, and MT4 rejection are
also mandatory.

**PAPER 02 owns:** general multiple-Fill and remaining-unit/reissue accounting;
broader partial entry/exit handling; repeated polling and recovery matrices;
manual drift/orphan-protection repair hardening; prolonged downtime and stale or
out-of-order catch-up recovery; and operational hardening not required to prove
this bounded first slice. PAPER 02 cannot weaken PAPER 01's no-blind-retry,
broker-authority, protection, or fail-closed rules.

## 14. Approval boundary

This artifact is complete only as an architecture gate. The next phase requires
explicit developer approval for implementation/BUILD, followed by non-capital
validation and independent review. After implementation, all gates must visibly
confirm the selected Practice account ID, immutable Deployment/Risk/Strategy
configuration, pinned session-policy provenance, broker connectivity, ownership,
reconciliation, freshness, and protection behavior.

Only after those checks pass with no unresolved Critical or Important finding may
the developer/trader give a **separate explicit approval for the first action
capable of creating OANDA Practice exposure**. Until that approval, Atlas must
not activate PAPER or invoke any POST/PUT/PATCH/DELETE, cancel, close, transfer,
or Order-submission request. `READY_TO_ACTIVATE` would mean that this separate
approval is still required; it does not mean activation occurred.

## 15. Frozen developer-review status

`ARCHITECTURE.md` remains **FROZEN FOR DEVELOPER REVIEW**. The five hold
decisions are incorporated without changing Experiment semantics or broadening
PAPER 01. No BUILD tasks, implementation, Git operation, credential change,
Risk-policy change, PAPER activation, or mutating OANDA request is authorized.
