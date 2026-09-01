# Atlas Pre-PAPER Readiness Audit

**Audit date:** 2026-08-30  
**Audited baseline:** `main` at `e671190ae4a77282367f2cecfa27ef45a375add1`  
**Foundation status:** Freeze 07 is closed; `dispatch/ACTIVE.md` reports no active workstream.  
**Mode:** Read-only audit. No application, schema, credential, Risk, broker, or
capital-exposure changes were made.

## Audit question and conclusion

The current historical lifecycle is a credible semantic foundation for PAPER:
the immutable StrategyVersion, canonical Strategy boundary, two-stage Risk
concept, Fill-authoritative accounting, native M15/M1 separation, and fail-closed
authority rules do not contradict the intended OANDA Practice lifecycle.

The repository is **not currently capable of running PAPER**. The missing
Deployment, TradingAccount, runtime, live-data, OANDA execution, and
reconciliation implementation is substantial, and several current historical
storage/execution assumptions must be extended before activation. Those are
PAPER work, not evidence that the meaning of the frozen contracts must change.

## Evidence basis

### Repository evidence

Reviewed the current architecture and feature contracts, Freeze 07 closure
artifacts, the Strategy/Risk/Experiment runner, execution and Fill application,
OANDA integration, persistence models/migrations, runtime entrypoint, and
historical market-data clock/ingestion. Relevant authority documents are:

- `context/architecture/domain-model.md`
- `context/architecture/strategy-contract.md`
- `context/architecture/accounting-model.md`
- `context/architecture/runtime-model.md`
- `context/architecture/safety-model.md`
- `context/architecture/market-data-model.md`
- `context/features/{experiments,risk-management,execution,reconciliation,deployment,historical-data,reference-strategy}.md`
- `dispatch/workstreams/foundation-freeze-07-experiment-lifecycle-local-authority/{ARCHITECTURE,VALIDATION,REVIEW}.md`
- `dispatch/workstreams/foundation-freeze-07-corrections/{VALIDATION,REVIEW}.md`

Freeze 07 validation and review are terminal `PASS` artifacts with no unresolved
Critical/Important findings. They explicitly excluded PAPER/LIVE and did not
claim a broker runtime.

### Provider truth

The external provider contract was checked against the current official OANDA
v20 documentation on 2026-08-30:

- Account endpoints and definitions: <https://developer.oanda.com/rest-live-v20/account-ep/> and <https://developer.oanda.com/rest-live-v20/account-df/>
- Order endpoints and definitions: <https://developer.oanda.com/rest-live-v20/order-ep/> and <https://developer.oanda.com/rest-live-v20/order-df/>
- Trade definitions: <https://developer.oanda.com/rest-live-v20/trade-df/>
- Position definitions: <https://developer.oanda.com/rest-live-v20/position-df/>
- Pricing endpoints/definitions: <https://developer.oanda.com/rest-live-v20/pricing-ep/> and <https://developer.oanda.com/rest-live-v20/pricing-df/>
- Transaction endpoints/definitions: <https://developer.oanda.com/rest-live-v20/transaction-ep/> and <https://developer.oanda.com/rest-live-v20/transaction-df/>
- OANDA account-state update guidance: <https://developer.oanda.com/rest-live-v20/best-practices/>

### Sanitized Practice probes

The configured token was used only for GET requests to the fixed Practice host
`https://api-fxpractice.oanda.com`. No order/trade mutation endpoint was called;
no POST, PUT, PATCH, DELETE, cancel, close, or transfer operation was performed.
Account IDs, prices, balances, transaction IDs, request IDs, and token material
are intentionally omitted.

Observed response shapes:

| Probe | Result | Sanitized evidence |
|---|---:|---|
| Authorized account list | 200 | Top-level `accounts`; four account-property objects with `id`, `mt4AccountID`, `tags`. |
| Account summary | 200 after following a provider 307 redirect | Top-level `account`, `lastTransactionID`; account includes currency, balance/NAV, unrealized P/L, margin fields, counts, pending `orders`, `trades`, and `positions`. |
| EUR/USD account instrument information | 200 | One instrument object; includes `pipLocation`, `displayPrecision`, `tradeUnitsPrecision`, min/max order/position constraints, `marginRate`, and guaranteed-stop capability. |
| EUR/USD pricing | 200 | Top-level `time`, `prices`, `homeConversions`; one price object includes `bids`, `asks`, `tradeable`, closeout bid/ask, instrument, and time. |
| Pending orders | 200 | `orders` array; zero rows for the first probed account. |
| Open trades | 200 | `trades` array; zero rows for the first probed account. |
| Positions | 200 | `positions` array; the first probed account returned two instrument-position objects even though open trades were zero. Position sides expose units, P/L, financing, commission/fee-related fields, and trade linkage fields. |

The last observation is material: OANDA's positions list is instrument-level
position information, and a non-empty response is not by itself an assertion
that every returned instrument currently has open exposure. Reconciliation must
inspect side units and open trades, not equate a non-empty positions array with
an open Atlas Position.

## Findings

Severity is consequence if the finding is left unresolved for PAPER. A PAPER
disposition means the current contract can be preserved while implementing the
missing seam. `Foundation contradiction` is reserved for a meaning change to a
frozen contract; none was found.

### 1. Strategy continuity

#### S-01 — Strategy semantics are environment-independent; no foundational contradiction

**Severity:** MINOR (positive assessment)  
**Area:** Strategy continuity  
**Current truth:** `StrategyContext` supplies UTC evaluation time, canonical
completed bars, Position state, immutable market facts, and exposure permission.
`EmaSweepConfirmationBreakStrategy` consumes M15 MID bars, persisted state, and
typed parameters only. `StrategyVersion` retains version number, source
fingerprint, implementation key, parameter schema, timeframe, warm-up, and state
schema. The Strategy does not branch on Experiment/PAPER/LIVE, call a broker, or
read account state.  
**Code/provider evidence:** `backend/strategies/contract.py:78-89,241-335`;
`backend/strategies/ema_sweep_confirmation_break.py:30-89,113-305`;
`backend/domain/strategy.py:604-647,726-835,1447-1538`;
`context/architecture/strategy-contract.md:5-9,21-29,63-93`. Freeze 07's
provider-neutral `MarketSpecification` composition is validated in
`dispatch/workstreams/foundation-freeze-07-experiment-lifecycle-local-authority/VALIDATION.md:58-63`.  
**Why it matters:** The same methodology can receive live canonical inputs
without a PAPER-specific Strategy implementation.  
**Required action:** Preserve this boundary. Put provider clocks, live data
normalization, account facts, and execution behavior outside Strategy.  
**Disposition:** Deferred

#### S-02 — PAPER Strategy state is not yet durable or restart-recoverable

**Severity:** IMPORTANT  
**Area:** Strategy continuity  
**Current truth:** The Experiment runner creates initial state in memory and
advances it while replaying a snapshot. The current persistence model has no
Deployment/Strategy-state record, and the runtime does not restore a Strategy
state or a last processed bar frontier.  
**Code/provider evidence:** `backend/experiments/runner.py:431-458,555-660` keeps
`state` local to one run; `backend/persistence/models.py` contains StrategyVersion
and Experiment rows but no Deployment or Strategy-state model; `backend/runtime/main.py:17-39`
only checks the database and waits. The required restart behavior is stated in
`context/architecture/strategy-contract.md:51-57` and
`context/architecture/runtime-model.md:39-57`.  
**Why it matters:** Restarting after a reference, confirmation, or pending
trigger could otherwise duplicate evaluation, lose setup state, or create an
incorrect new decision.  
**Required action:** PAPER 01 must persist the version-compatible state envelope,
last evaluated completed M15 frontier, and pending-entry handoff; restore and
validate them before exposure. Invalid state must fail closed, not reset silently.  
**Disposition:** PAPER 01

#### S-03 — Entry, stop, target, evidence, and timing carry semantically

**Severity:** MINOR (positive assessment)  
**Area:** Strategy continuity  
**Current truth:** V2 emits a price-triggered OPEN decision at completed M15
confirmation, with ASK/BID trigger basis, proposed stop, target methodology,
rationale, setup facts, and evidence. The runner persists decision frontier,
trigger, stop, target multiple, and evidence in the canonical TradeIntent
record. Target resolution is deliberately deferred until executable entry.  
**Code/provider evidence:** `backend/strategies/ema_sweep_confirmation_break.py:226-305`;
`backend/experiments/runner.py:916-971`; `backend/persistence/models.py:489-524`;
`context/features/reference-strategy.md:26-43,63-68`.  
**Why it matters:** The same immutable StrategyVersion can create the same
methodology-driven TradeIntent in PAPER; only the market observation and
execution adapter change.  
**Required action:** Keep the exact decision frontier and evidence provenance;
do not make live Strategy code calculate quantity or query OANDA.  
**Disposition:** Deferred

### 2. Risk continuity

#### R-01 — The current Risk seam is Experiment-named and has no PAPER caller

**Severity:** BLOCKER  
**Area:** Risk continuity  
**Current truth:** `RiskService` is pure and centralized, but its public inputs
and rejection vocabulary still say `experiment_status` and
`EXPERIMENT_NOT_RUNNING`. The only current caller is `ExperimentRunner`; no
Deployment/PAPER path exists. There is therefore no current path that could
bypass Risk, but also no proof that a PAPER entry must pass both Risk phases.  
**Code/provider evidence:** `backend/risk/service.py:72-184` and
`backend/experiments/runner.py:995-1090`; `backend/tests/risk/test_service.py` and
historical golden-flow evidence in
`dispatch/workstreams/first-historical-trade/VALIDATION.md:44-63`.  
**Why it matters:** A PAPER implementation that submits directly from a
Strategy decision, or merely reuses a stale Experiment status argument, could
create exposure outside Atlas Risk.  
**Required action:** PAPER 01 must compose the same Risk rules behind the
Deployment eligibility/state seam, with explicit account/exposure/venue inputs,
PRE_FLIGHT followed immediately by PRE_SUBMISSION. The only entry authorization
must be an approved PRE_SUBMISSION RiskDecision; retain immutable RiskDecision
facts and reject unknown state. This is an API/composition adaptation, not a
change to Risk meaning.  
**Disposition:** PAPER 01

#### R-02 — Broker account and venue constraints are not current Risk inputs

**Severity:** BLOCKER  
**Area:** Risk continuity  
**Current truth:** Current sizing is `equity × risk_per_trade / stop distance`,
floored to whole units. It checks USD/EUR/USD, positive equity, stop geometry,
and flat exposure, but it does not consume OANDA margin available/used, margin
rate, trade-unit precision, minimum/maximum order units, maximum position size,
tradeability, or home-currency conversion facts.  
**Code/provider evidence:** `backend/risk/service.py:114-148,150-184`;
`context/features/risk-management.md:23-29,35-54`; Practice instrument probe
returned the documented constraint fields (`tradeUnitsPrecision`, minimum and
maximum sizes, `marginRate`), while account summary returned balance/NAV and
margin fields. Official OANDA account/instrument/pricing definitions above are
the provider authority.  
**Why it matters:** A numerically valid historical quantity may be invalid,
unsubmittable, or unsafe against actual OANDA margin and precision rules.
Historical USD/EUR/USD economics remain valid for the initial slice, but the
broker account state must be known before PAPER exposure.  
**Required action:** Normalize the selected OANDA account and instrument facts
at the adapter boundary and supply them explicitly to the same Risk calculation.
Risk must conservatively round to provider rules, check available margin and
tradeability, and reject unavailable/unknown facts. Do not move sizing into
Strategy or execution.  
**Disposition:** PAPER 01

#### R-03 — Actual OANDA fill price and protection prices need an explicit bridge

**Severity:** IMPORTANT  
**Area:** Risk continuity  
**Current truth:** Historical PRE_SUBMISSION sizes from the simulated adapter's
predicted executable price, then asserts the simulated Fill equals that price.
OANDA market execution can return a different actual fill price, while the
Strategy target is defined as 1.7R from actual entry and the stop/target must be
broker-hosted.  
**Code/provider evidence:** `backend/experiments/runner.py:1047-1138` performs
the simulated equality assertion and resolves target after the simulated Fill;
`backend/execution/simulated.py:153-207` applies deterministic slippage.
OANDA's official MarketOrder definition includes market units, time-in-force,
price bound, and position-fill semantics; the create response can include create,
fill, cancel, reissue, and related transactions (`order-ep`).  
**Why it matters:** Blindly attaching a target calculated from a pre-submit quote
could violate actual-entry target semantics; delaying all protection after an
entry can leave real exposure unprotected.  
**Required action:** PAPER 01 must define the exact order/protection sequence:
bound or otherwise constrain entry where appropriate, consume the authoritative
fill, verify post-fill geometry, calculate the target from that Fill, and confirm
broker-hosted stop/target state. Any interval or failed protection must enter the
frozen fail-closed state rather than silently continuing.  
**Disposition:** PAPER 01

### 3. Execution continuity

#### E-01 — Canonical chain exists, but execution is currently simulation-only

**Severity:** BLOCKER  
**Area:** Execution continuity  
**Current truth:** The historical path is explicit:
`Strategy → TradeIntent → PRE_FLIGHT RiskDecision → executable context →
PRE_SUBMISSION RiskDecision → Order → simulated execution → Fill → Position /
Trade`. `Fill` is the only exposure transition. The reusable concepts are the
Strategy decision/state/evidence, TradeIntent, RiskDecision shape, canonical
Order/Fill/Position/Trade vocabulary, parent protection relationship, and
transactional Fill application. The current adapter and runner are not broker
adapters.  
**Code/provider evidence:** `backend/experiments/runner.py:323-412,995-1179`;
`backend/execution/contract.py:1-75,117-156`;
`backend/execution/fill_application.py:74-243`;
`backend/execution/simulated.py:42-207`; `backend/execution/contract.py:1`
explicitly describes historical simulated execution.  
**Why it matters:** No PAPER order can be safely submitted today, and a parallel
fake PaperOrder/PaperTrade model would break the canonical lifecycle.  
**Required action:** Implement one OANDA adapter behind the existing canonical
Order/Fill boundary and one PAPER runtime composition. Do not create parallel
PAPER domain nouns.  
**Disposition:** PAPER 01

#### E-02 — Current persistence/application does not yet tolerate broker partial fills

**Severity:** BLOCKER  
**Area:** Execution continuity  
**Current truth:** The architecture says an Order may have multiple Fills and
`PARTIALLY_FILLED` status, but the current database status constraint omits
`PARTIALLY_FILLED`; `apply_fill` requires sequence one and Fill quantity equal
to requested Order quantity. The historical simulator intentionally assumes
full fills.  
**Code/provider evidence:** `context/architecture/domain-model.md:82-96,150-159`;
`context/features/execution.md:29-33,79-85`; `backend/persistence/models.py:567-618`
(`valid_status`, one-fill uniqueness); `backend/execution/fill_application.py:113-139`.
OANDA's order-create response documents immediate fill, cancel, and reissue
transactions, and OANDA Trade exposes current versus initial units.  
**Why it matters:** Treating a partial broker execution as full exposure, or
rejecting a later fill, would make local Position, Trade, and risk state false.
This is a required implementation of an already-defined canonical capability,
not a reason to redefine Position or Trade.  
**Required action:** Harden the existing Order/Fill application for executed
quantity, multiple fills, remaining units, partial status, and idempotent external
execution identifiers. Reconcile the migration/model constraints before PAPER
activation and test partial entry/exit behavior conservatively.  
**Disposition:** PAPER 02

#### E-03 — Historical protection is local simulation, not broker-hosted protection

**Severity:** BLOCKER  
**Area:** Execution continuity  
**Current truth:** The historical runner applies stop/target behavior by asking
`SimulatedExecutionAdapter` to inspect later M1 observations. It creates the
historical entry Fill before creating and submitting local protection Orders.
There is no broker confirmation path.  
**Code/provider evidence:** `backend/experiments/runner.py:1129-1258`;
`backend/execution/simulated.py:113-151`; `backend/persistence/models.py:590-592`
has only a local parent order link. The required PAPER rule is
`context/features/execution.md:43-49` and `context/architecture/safety-model.md:39-45`.  
**Why it matters:** Atlas uptime cannot be the only protection for an open
Practice Position. An entry followed by an unconfirmed or failed protective
instruction is a critical safety condition.  
**Required action:** PAPER 01 must use OANDA-native stop-loss/take-profit order
semantics where supported, retain the parent/correlation relationship, confirm
the broker state, and fail/block new exposure if protection is missing or
ambiguous. Shutdown must not cancel valid broker-hosted protection.  
**Disposition:** PAPER 01

### 4. OANDA broker and reconciliation contract

#### O-01 — Existing OANDA integration is a historical candle source only

**Severity:** BLOCKER  
**Area:** OANDA broker/reconciliation contract  
**Current truth:** The OANDA package exposes only a synchronous read-only
historical candle source. It supports native M15 MID and sparse M1 BID/ASK
fetches, normalized canonical Bars, bounded retries, and sanitized diagnostics.
It has no account, pricing, order, trade, position, transaction, or reconciliation
client.  
**Code/provider evidence:** `backend/integrations/oanda/source.py:1-5,196-260,263-431`;
`backend/integrations/oanda/__init__.py:1-33`; repository search found no
`OandaExecutionAdapter`, account client, or reconciliation service. The probes
confirmed the provider endpoints exist and return the shapes listed above.  
**Why it matters:** The current source cannot establish broker truth or submit
an Atlas Order.  
**Required action:** Add the narrow Practice account/pricing/order/transaction
adapter required by the canonical lifecycle; keep provider payloads inside the
integration layer and normalize them to Atlas values.  
**Disposition:** PAPER 01

#### O-02 — External identity and transaction cursor storage is incomplete

**Severity:** BLOCKER  
**Area:** OANDA broker/reconciliation contract  
**Current truth:** Atlas has an Atlas Order ID, unique local
`client_correlation_id`, and nullable `Fill.external_execution_id`, but no
persisted external OANDA Order ID, Trade ID, transaction ID, request ID, or
account transaction cursor. Order events have only local event sequence/details.  
**Code/provider evidence:** `backend/persistence/models.py:567-618,677-690`;
`backend/persistence/trading_repository.py:70-118`. OANDA documentation defines
account-scoped Order/Trade IDs, transaction IDs, `lastTransactionID`, related
transaction IDs, request IDs, and `clientExtensions`; account details and
account-update polling are specifically designed to use the last transaction ID
(`best-practices`, `account-ep`, `transaction-df`).  
**Why it matters:** After a timeout or restart Atlas cannot reliably associate a
provider result with one canonical Order or advance a durable reconciliation
cursor. Duplicate exposure becomes possible.  
**Required action:** Persist stable Atlas correlation in OANDA client extensions
where permitted, external Order/Trade/Fill/Transaction identifiers, provider
request diagnostics, and the account `lastTransactionID` cursor. Make every
normalization and replay operation idempotent.  
**Disposition:** PAPER 01

#### O-03 — Unknown submission, rejection, cancellation, drift, and restart paths are absent

**Severity:** BLOCKER  
**Area:** OANDA broker/reconciliation contract  
**Current truth:** The canonical documentation defines UNKNOWN, rejection,
cancellation, broker authority, and reconciliation-required states, but current
code has no broker submission or query path, no transaction-history recovery,
no startup reconciliation, no protection verification, and no broker-drift
handler. Current runtime startup is only a database readiness check.  
**Code/provider evidence:** `context/architecture/safety-model.md:15-37`;
`context/features/reconciliation.md:15-61,71-81`;
`context/features/execution.md:19-29,55-69`; `backend/runtime/main.py:17-39`.
OANDA official documentation provides account snapshots, pending orders, open
trades, positions, and transaction pages/details, but none of those endpoints
are currently called by Atlas.  
**Why it matters:** A network timeout cannot be converted into a rejection or a
blind retry. Manual OANDA activity, missed fills, unexpected positions, orphan
protection, or a runtime restart must block new exposure until broker truth is
established.  
**Required action:** PAPER 01 must implement startup/reconnect/unknown-order
reconciliation before RUNNING, with explicit found/absent/ambiguous outcomes,
transaction-based Fill recovery, duplicate prevention, rejection/cancel mapping,
and persistent safety state. PAPER 02 should harden repeated polling, partial
fills, manual drift, and broader recovery matrices.  
**Disposition:** PAPER 01

#### O-04 — Provider shapes require explicit normalization, not direct field reuse

**Severity:** IMPORTANT  
**Area:** OANDA broker/reconciliation contract  
**Current truth:** OANDA's account summary is a self-consistent snapshot with
embedded pending orders, trades, and positions plus `lastTransactionID`. Pricing
has bid/ask arrays, tradeability, closeout prices, and optional home conversions.
Positions are instrument aggregates with separate long/short sides. A market
order create response may contain create, fill, cancel, reissue, rejection, and
related transactions. A direct OANDA object cannot be treated as one Atlas
Order/Fill/Position fact.  
**Code/provider evidence:** Sanitized probes above; official OANDA account,
pricing, order, trade, position, and transaction definition URLs above. The
first direct account-summary GET returned a 307 and was successfully read only
with redirect-following, which is also a transport behavior the adapter must
handle deliberately.  
**Why it matters:** Incorrectly mapping aggregate Position rows, signed OANDA
units, closeout prices, or compound transaction responses can invent exposure or
lose a real Fill.  
**Required action:** Define provider-neutral normalization for the following
mapping before submitting any Order:

| OANDA concept | Atlas boundary |
|---|---|
| Account ID/alias/currency | `TradingAccount` identity and USD account-state inputs; account ID must be explicit, not inferred from a token with multiple accounts. |
| balance, NAV, unrealizedPL, marginAvailable, marginUsed | normalized broker account snapshot used by Risk; broker values remain authoritative. |
| `ClientPrice` bids/asks/tradeable/closeout prices/home conversions | `ExecutableQuote` plus explicit provider pricing metadata; BUY uses ASK and SELL uses BID. |
| OANDA Order ID and `clientExtensions` | Atlas Order external identity and stable correlation; never replace Atlas Order ID. |
| create/fill/reject/cancel/reissue transactions | immutable OrderEvents and canonical Fill facts, with all related transaction IDs retained. |
| OrderFillTransaction units/price/time/fees and trade-open/close references | one or more canonical Fills with external execution/transaction identity. |
| OANDA Trade ID, signed initial/current units, open/close state | Atlas Trade/exposure episode projection, reconciled from broker facts. |
| OANDA Position long/short units, average price, trade IDs | Atlas Position projection for the one Deployment/instrument rule; any conflicting side/external trade is drift. |
| `lastTransactionID` and transaction pages/details | durable reconciliation cursor and recovery evidence; never advance it without applying the corresponding facts. |

**Disposition:** PAPER 01

### 5. Operational authority

#### A-01 — Freeze 07 local authority is suitable for local control, but PAPER activation is not implemented

**Severity:** IMPORTANT  
**Area:** Operational authority  
**Current truth:** Freeze 07 admits only a loopback socket peer plus local
Host/`:authority`, with proxy-header rewriting disabled in the supported Uvicorn
entrypoint. The runtime does not start trading; it checks the database and waits.
There is no Deployment, desired/actual PAPER state, START approval, or activation
record today.  
**Code/provider evidence:** `backend/api/app.py:36-101`;
`dispatch/workstreams/foundation-freeze-07-experiment-lifecycle-local-authority/ARCHITECTURE.md:517-600`;
`README.md:108-127`; `backend/runtime/main.py:17-39`. Freeze 07's validation
confirmed loopback, local authority, spoofed-header, and `--no-proxy-headers`
behavior.  
**Why it matters:** The local boundary is appropriate for a single-user local
control plane, but PAPER must not become active merely because the process or API
starts.  
**Required action:** PAPER 01 must make account selection, credential
configuration, Risk configuration, Deployment creation, explicit trader START,
and actual runtime activation distinct durable steps. START should record desired
state; runtime should reach actual RUNNING only after ownership, reconciliation,
warm-up, data freshness, and protection prerequisites pass.  
**Disposition:** PAPER 01

#### A-02 — The token authorizes multiple accounts; no explicit Practice account binding exists

**Severity:** IMPORTANT  
**Area:** Operational authority  
**Current truth:** Settings supports one optional OANDA token but no OANDA account
ID. The read-only account-list probe returned four authorized account properties.
The token therefore does not identify the trader's intended PAPER account.  
**Code/provider evidence:** `backend/config.py:23-35`; `.env.example:7-10`;
sanitized `account_list` probe above returned four accounts; the official OANDA
account endpoint documents account-scoped access and account identifiers.  
**Why it matters:** PAPER could operate against the wrong account, and account
selection would not remain an explicit trader-controlled decision.  
**Required action:** Require a selected account identity in the TradingAccount /
Deployment configuration, validate it through the authorized account list and
summary, and keep credentials server-side. Do not silently choose the first
account returned by OANDA.  
**Disposition:** PAPER 01

#### A-03 — Loopback-only unauthenticated API remains a deployment boundary

**Severity:** MINOR  
**Area:** Operational authority  
**Current truth:** The API has local peer and authority protection but no user
authentication/authorization. `CURRENT.md` records this as acceptable only for
the documented loopback-only posture and a required deployment-time gate before
network exposure.  
**Code/provider evidence:** `backend/api/app.py:82-100` and Freeze 07 authority
artifacts; `CURRENT.md:31-34`; `README.md:114-117`.  
**Why it matters:** A remote or proxy-exposed API would not have a sufficient
trader approval boundary. The current local posture is not itself a contradiction
for the requested single-user local PAPER slice.  
**Required action:** Keep the supported server loopback-only and do not expose
PAPER control remotely until authentication/authorization and trusted deployment
boundary work is explicitly approved.  
**Disposition:** Deferred

### 6. Data and runtime continuity

#### D-01 — Historical native-product semantics are proven, but no live OANDA data frontier exists

**Severity:** BLOCKER  
**Area:** Data/runtime continuity  
**Current truth:** Historical ingestion fetches native OANDA M15 MID and sparse
M1 BID/ASK, rejects incomplete/malformed data, stores immutable provenance, and
the SimulationClock separates the completed signal-bar frontier from post-decision
execution observations. There is no live M15 finalizer, quote/M1 execution
observation source, stream/poll loop, or reconnect recovery.  
**Code/provider evidence:** `backend/integrations/oanda/source.py:222-260,326-350`;
`backend/experiments/clock.py:87-286`;
`backend/market_data/ingestion.py:580-610,908-1129`;
`context/architecture/market-data-model.md:23-57,75-81`; `backend/runtime/main.py:31-38`.  
**Why it matters:** PAPER must not feed an incomplete M15 candle to Strategy,
reuse signal-bar observations for entry, fabricate missing M1 prices, or silently
change the native product.  
**Required action:** PAPER 01 must normalize incoming OANDA data into canonical
completed M15 MID bars and post-frontier executable BID/ASK observations, with a
durable frontier. Choose the provider polling/streaming boundary explicitly and
prove that it preserves the current half-open UTC and no-lookahead semantics.  
**Disposition:** PAPER 01

#### D-02 — Stale, delayed, duplicate, disconnect, reconnect, and restart behavior is not implemented

**Severity:** IMPORTANT  
**Area:** Data/runtime continuity  
**Current truth:** Historical repositories have duplicate/content-fingerprint
guards and the SimulationClock rejects duplicate M15 frontiers, but those are
snapshot/replay protections. No live runtime owns a data frontier, stores
heartbeat/freshness, handles out-of-order or delayed observations, catches up
chronologically, or blocks stale entry opportunities after restart.  
**Code/provider evidence:** `backend/market_data/ingestion.py:908-1129` is a
bounded historical loader; `backend/experiments/clock.py:171-245` is a replay
index; no live runtime modules exist beyond `backend/runtime/main.py`. Required
behavior is `context/architecture/runtime-model.md:39-57,83-85` and
`context/architecture/safety-model.md:15-29,47-57`.  
**Why it matters:** A delayed signal must not become a fresh entry, and a
disconnect must not be interpreted as absence of broker orders or exposure.
Duplicate/delayed data can duplicate Strategy decisions unless the frontier is
durable and idempotent.  
**Required action:** Implement freshness thresholds, expected session-closure
classification, duplicate/out-of-order handling, chronological catch-up,
disconnect/reconnect state, and startup reconciliation before resume. Existing
broker protection must remain untouched during runtime loss.  
**Disposition:** PAPER 02

#### D-03 — The session policy has not pinned its official source metadata

**Severity:** IMPORTANT  
**Area:** Data/runtime continuity  
**Current truth:** The implementation uses `OANDA_FX_NY_V2`, America/New_York
rollover rules, and a finite holiday exception table. Its module documentation
still says the OANDA source URL/title/effective interval are `OANDA_DOC_PENDING`,
despite comments referencing a 2025 holiday notice.  
**Code/provider evidence:** `backend/market_data/session_policy.py:1-14,103-140`;
`backend/market_data/oanda_session_policy_provenance.md`; official OANDA account,
pricing, instrument, and current provider documentation are the external source
of truth, not the pending placeholder.  
**Why it matters:** A live closure, rollover, holiday, or tradeability change
must not be classified as an expected gap by an unverified historical policy, nor
should a provider correction silently alter old snapshot semantics.  
**Required action:** Before PAPER 01 activation, pin the current official source
and effective-date policy, retain versioned historical policy semantics for old
snapshots, and use provider `tradeable`/response state as an explicit live
precondition rather than fabricating bars.  
**Disposition:** PAPER 01

#### D-04 — Runtime ownership, durable health, and actual-state transitions are absent

**Severity:** BLOCKER  
**Area:** Data/runtime continuity  
**Current truth:** The documented target requires one runtime owner, PostgreSQL
coordination, heartbeat/health, desired versus actual Deployment state, startup
reconciliation, warm-up, and safe shutdown. Current `atlas-runtime` performs a
database check and blocks on an event; it does not discover Deployments, acquire
ownership, receive bars, evaluate Strategy, call Risk, submit Orders, or persist
health.  
**Code/provider evidence:** `backend/runtime/main.py:17-39`; no Deployment or
TradingAccount models in `backend/persistence/models.py`; target contract in
`context/architecture/runtime-model.md:5-29,31-77` and
`context/features/deployment.md:19-41`.  
**Why it matters:** Starting Atlas must not activate PAPER, and a second runtime
or restart must not create duplicate decisions/orders or resume before broker
truth is known.  
**Required action:** PAPER 01 must add the narrow single-runtime coordinator,
desired/actual state, ownership lock, durable health/safety state, and startup
sequence. The process must remain inert until an explicitly activated PAPER
Deployment passes all gates.  
**Disposition:** PAPER 01

## Overall reusable lifecycle assessment

The current historical path proves the following reusable semantics:

- Immutable StrategyVersion provenance, typed parameter snapshot, deterministic
  Strategy evaluation, completed-bar/no-lookahead enforcement, M15 MID analysis,
  and sparse M1 BID/ASK separation.
- Strategy-owned direction/stop/target methodology, trigger policy, rationale,
  setup facts, and decision timing, with Risk kept outside Strategy.
- Two-stage Risk shape: structural PRE_FLIGHT, then executable-price
  PRE_SUBMISSION; long entry at ASK, short entry at BID; actual-entry target
  methodology; conservative Decimal sizing for the initial EUR/USD/USD slice.
- Canonical TradeIntent, RiskDecision, Order, Fill, Position, and Trade nouns;
  Fill—not Order submission—changes exposure; PostgreSQL is the durable local
  authority for historical facts.
- Freeze 07 local authority, immutable Experiment/result provenance, explicit
  failure persistence, and fail-closed safety language.

These are sufficient to begin a PAPER 01 planning/implementation workstream, but
not to activate a PAPER Deployment. The required work must extend the existing
contracts rather than introduce PaperTrade, PaperOrder, PaperPosition, a second
Strategy implementation, or a Risk bypass.

## PAPER boundary map

### Already proven/reusable

- StrategyVersion and EMA Sweep Confirmation Break v2 methodology.
- StrategyContext purity, deterministic state transition contract, parameters,
  evidence/rationale, stop proposal, target methodology, trigger semantics.
- Native historical OANDA M15 MID and sparse M1 BID/ASK normalization contracts.
- UTC half-open intervals, completed-bar/no-lookahead frontier, BID/ASK side
  rules, and historical gap/no-fabrication policy as currently versioned.
- Canonical Strategy → TradeIntent → RiskDecision → Order → Fill → Position →
  Trade meaning and Fill-driven accounting boundary.
- Historical two-stage Risk semantics for the initial EUR/USD/USD slice.
- Freeze 07 loopback/local Host authority and explicit destructive-operation
  discipline.
- Secret-safe OANDA token handling and sanitized historical provider failures.

### Must implement in PAPER 01

- Explicit TradingAccount with selected OANDA Practice account ID, capabilities,
  account snapshot, and broker-state normalization.
- Deployment configuration and immutability, desired/actual activation state,
  explicit trader-controlled START boundary, and one-runtime ownership.
- Live completed M15 data and post-decision executable BID/ASK observation
  boundary, clock/frontier persistence, freshness, warm-up, and no duplicate
  evaluation.
- Durable Strategy state/frontier restoration and stale catch-up policy.
- OANDA account, instrument, pricing, order, transaction, and response
  normalization adapters.
- External OANDA Order/Trade/Fill/Transaction IDs, client-extension correlation,
  request diagnostics, and transaction cursor persistence.
- Canonical broker-backed Order submission with PENDING_SUBMISSION → submitted,
  rejected, or UNKNOWN handling; no timeout blind retry.
- PRE_FLIGHT and PRE_SUBMISSION Risk as the sole new-entry authorization using
  normalized broker account/venue facts.
- Broker-hosted stop/target submission/confirmation and protection-failure
  fail-closed behavior.
- Startup/reconnect reconciliation before actual RUNNING, including account,
  pending orders, open trades, positions, protection, and transaction history.

### Must harden in PAPER 02

- Partial fills and remaining-unit/reissue handling across Order, Fill, Position,
  Trade, and reconciliation.
- Repeated reconciliation idempotency, manual broker drift, orphan protection,
  delayed/missed transactions, and broader restart/disconnect matrices.
- Live stale/out-of-order/duplicate observation recovery and chronological
  catch-up under prolonged downtime.
- Provider/session-policy source pinning and effective-date correction handling
  if not completed as a PAPER 01 gate.
- Operational hardening of persistent safety visibility and runtime health.

### Deferred

- LIVE activation and promotion; it remains prohibited until PAPER lifecycle
  proof is complete.
- Remote API exposure, authentication/authorization, and deployment-time network
  boundary work.
- Additional brokers, instruments, timeframes, partial Strategy exits,
  pyramiding, trailing stops, and generalized infrastructure.
- Any change to the meaning of StrategyVersion, Risk ownership, Fill authority,
  broker authority, native M15/M1 products, or no-lookahead semantics.

## Foundational contradictions

**None identified.**

In particular, the current Experiment-only persistence and runtime plumbing,
simulation adapter, missing broker IDs, absent reconciliation, and absent
Deployment are gaps to implement within the already-written PAPER boundary. They
do not require changing what StrategyVersion, TradeIntent, RiskDecision, Order,
Fill, Position, Trade, completed M15 data, or broker authority mean. The current
partial-fill implementation gap is a serious PAPER hardening requirement, but
the frozen domain already defines the required multiple-Fill/partial-Order
meaning; it is not a justification for a parallel model.

## Overall verdict

**READY FOR PAPER 01**

This verdict means ready to plan and implement the bounded PAPER 01 workstream,
not authorized to activate PAPER, submit broker orders, or change credentials,
Risk policy, or capital exposure. No PAPER 01 plan or architecture was created by
this audit.
