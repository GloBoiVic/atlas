# PAPER 04 Broker Execution Architecture

**Workstream:** `paper-04-broker-execution`
**Classification:** Critical
**Status:** Architecture freeze, pre-approval
**Scope:** One OANDA Practice `EUR_USD` `IMMEDIATE` `OPEN_LONG` or `OPEN_SHORT`

This document freezes the smallest trustworthy first mutation boundary. It authorizes no real broker request, branch creation, BUILD task, PAPER activation, or capital exposure.

## 1. Decisions at a glance

1. PAPER 04 does not execute a caller-supplied PAPER 03 approval. It reads current broker facts and invokes `evaluate_paper_risk(...)` itself.

2. Pre-entry account state comes from one OANDA full Account Details response, not independently fetched summary/Trade/Position/Order inventories.

3. Client extensions are permitted only after a read-only AccountProperties check proves the configured account has no `mt4AccountID`.

4. Ordinary `stopLossOnFill` is supported only when Account Details proves the account does not require guaranteed Stop Loss Orders.

5. EUR/USD execution precision comes from the provider's instrument metadata. No Risk value is rounded to fit OANDA.

6. Entry is one `MARKET`, `FOK`, `OPEN_ONLY` Order with exact Risk quantity, exact Risk `priceBound`, and the exact Strategy Stop Loss attached on fill.

7. The entry request intentionally does **not** contain `takeProfitOnFill`.

8. Actual target is recomputed from `TradeOpen.price`, the frozen Strategy stop, and the immutable `TargetProposal`.

9. After a confirmed Fill and confirmed Stop Loss, Atlas may perform exactly one dependent Take Profit mutation using the actual-fill-derived target.

10. Entry mutation and Take Profit mutation use non-retrying write semantics.

11. Entry submission uncertainty never triggers a second exposure POST.

12. A confirmed Fill with incomplete Stop/Target protection is not `UNKNOWN`; Atlas knows exposure exists and returns `FILLED_PROTECTION_INCOMPLETE`.

13. Historical `Order`, `Fill`, Experiment execution, persistence, Risk semantics, runtime activation and LIVE remain untouched.

## 2. Facts and Atlas policy

### 2.1 Official OANDA facts

The architecture relies on these provider facts:

- `GET /v3/accounts` returns `AccountProperties`.
- `AccountProperties.mt4AccountID` is present only for an MT4-associated account.
- `GET /v3/accounts/{accountID}` returns full Account Details, including full pending Orders, open Trades and open Positions.
- Account Details includes `guaranteedStopLossOrderMode`.
- `GET /v3/accounts/{accountID}/instruments` returns instrument-specific `displayPrecision`, `tradeUnitsPrecision`, `minimumTradeSize`, and `maximumOrderUnits`.
- Market Orders use signed units and may use FOK or IOC.
- `priceBound` is the worst acceptable fill price.
- `OPEN_ONLY` permits only opening or extension rather than reduction.
- Market Order requests support `stopLossOnFill`, `takeProfitOnFill`, `clientExtensions`, and `tradeClientExtensions`.
- Client extensions must not be set for MT4-associated accounts.
- `OrderFillTransaction.tradeOpened` identifies the newly opened Trade.
- The individual Trade-open price is an official execution price; the generic top-level fill price is deprecated as execution authority.
- A Trade's dependent Orders can be created/replaced through `PUT /v3/accounts/{accountID}/trades/{tradeSpecifier}/orders`.
- Omitting `stopLoss` from that dependent-order request leaves an existing Stop Loss unchanged.
- FOK means immediately Filled Or Killed; IOC permits immediate partial fill.
- Full Account Details plus transaction updates is OANDA's documented coherent account-state model.

### 2.2 Atlas policy

The initial capability admits only:

```text
provider = OANDA
environment = PRACTICE
instrument = EUR_USD
base currency = USD
non-MT4 account
guaranteedStopLossOrderMode ∈ {DISABLED, ALLOWED}
EntryPolicy = IMMEDIATE
account state = FLAT
pending Orders = none
FOK
OPEN_ONLY
ordinary absolute-price Stop Loss
R_MULTIPLE Take Profit
```

If any required provider capability is unavailable or contradictory:

```text
refuse before POST
```

No fallback or inference is allowed.

### 2.3 Why target is not attached on entry

Atlas currently defines:

```python
TargetProposal.resolve(entry, stop, direction)
```

as:

```text
LONG:
entry + multiple × abs(entry - stop)

SHORT:
entry - multiple × abs(entry - stop)
```

Therefore the correct target depends on the actual entry.

PAPER 03 resolves a pre-submission target using the Risk reference entry.

That value is useful Risk evidence.

It is **not** the immutable final broker target when actual Fill differs.

Historical Experiment execution already re-resolves target from its actual Fill.

To preserve methodology:

```text
pre-submission target
≠ automatically broker target

actual Fill
→ TargetProposal.resolve(...)
→ broker target
```

## 3. Current contracts that remain authoritative

Reuse without semantic change:

```text
StrategyDecision
TargetProposal
Action
Direction
EntryPolicy

RiskConfig
RiskDecision
RiskService

evaluate_paper_risk
PaperRiskEvaluation

OandaPracticeAccountIdentity
OandaPracticeAccountSummarySnapshot
OandaPracticeOpenTradeInventory
OandaPracticeOpenPositionInventory
OandaPracticePendingOrderInventory
OandaPracticeEurUsdPricingObservation

project_oanda_practice_account_state
project_oanda_practice_eur_usd_exposure_state

OandaObservationRequester
```

The GET requester remains:

```text
GET-only
safe-retrying
read-only
```

It receives no POST/PUT method.

Keep Experiment-specific:

```text
backend/execution/contract.Order
backend/execution/contract.Fill
ExecutionObservation
SimulatedExecutionAdapter
apply_fill()
ExperimentRunner
TradingRepository
Experiment accounting/persistence
```

## 4. Read-only execution eligibility contracts

### 4.1 Account properties

Add an immutable normalized value equivalent to:

```python
@dataclass(frozen=True, slots=True)
class OandaPracticeAccountProperties:
    provider_account_id: str
    mt4_account_id: int | None
```

A reader for:

```text
GET /v3/accounts
```

must locate the configured account exactly once.

Execution eligibility requires:

```text
provider_account_id == configured account
mt4_account_id is None
```

Absent configured account, duplicate account identity, malformed properties, or an MT4 ID fails closed.

### 4.2 Coherent execution account snapshot

Add an immutable read-only contract equivalent to:

```python
@dataclass(frozen=True, slots=True)
class OandaPracticeExecutionAccountSnapshot:
    summary: OandaPracticeAccountSummarySnapshot
    trades: OandaPracticeOpenTradeInventory
    positions: OandaPracticeOpenPositionInventory
    pending_orders: OandaPracticePendingOrderInventory
    guaranteed_stop_loss_order_mode: str
    hedging_enabled: bool
    last_transaction_id: str
```

The exact shape may vary modestly if cleaner, but these semantics are frozen.

It is produced from one:

```text
GET /v3/accounts/{accountID}
```

response.

All nested normalized observations must carry:

```text
same financial identity
same response lastTransactionID
```

The full snapshot must require:

```text
summary.open_trade_count == len(trades.trades)
summary.open_position_count == len(positions.positions)
summary.pending_order_count == len(pending_orders.orders)
```

The execution slice requires all three to be zero.

Use existing Trade/Position/Order normalization semantics rather than inventing new interpretations.

### 4.3 Stop-loss account capability

Require:

```text
guaranteedStopLossOrderMode == DISABLED
or
guaranteedStopLossOrderMode == ALLOWED
```

If:

```text
REQUIRED
```

return unsupported execution capability before mutation.

Do not use guaranteed Stop Loss in this slice because:

```text
premium/cost semantics
guaranteed execution economics
```

are not represented in current Risk methodology.

### 4.4 Instrument execution capability

Add an immutable EUR/USD execution capability observation equivalent to:

```python
@dataclass(frozen=True, slots=True)
class OandaPracticeExecutionInstrument:
    provider_instrument: Literal["EUR_USD"]
    display_precision: int
    trade_units_precision: int
    minimum_trade_size: Decimal
    maximum_order_units: Decimal
    last_transaction_id: str
```

For current validated scope require:

```text
EUR_USD exactly
display_precision == 5
trade_units_precision == 0
minimum_trade_size > 0
maximum_order_units > 0
```

The Risk quantity must satisfy the provider unit capability.

No hardcoded rounding is permitted.

## 5. Provider-neutral execution contracts

### 5.1 Account/provenance

```python
@dataclass(frozen=True, slots=True)
class ExecutionAccountIdentity:
    provider: Provider
    environment: str
    account_id: str
    base_currency: str
```

```python
@dataclass(frozen=True, slots=True)
class ExecutionObservationProvenance:
    identity: ExecutionAccountIdentity
    account_transaction_id: str
    pricing_time: datetime
    instrument_transaction_id: str
```

The account transaction ID is the single Account Details frontier.

It is stronger evidence than unrelated independent account reads, but it is still not a durable reconciliation cursor.

### 5.2 Instruction

```python
@dataclass(frozen=True, slots=True)
class PaperExecutionInstruction:
    attempt_id: UUID
    strategy_decision: StrategyDecision
    account: ExecutionAccountIdentity
    instrument: Instrument
    direction: Direction
    requested_quantity: Decimal
    approved_entry_price: Decimal
    stop_price: Decimal
    decision_time: datetime
    pricing_time: datetime
    pre_flight: RiskDecision
    pre_submission: RiskDecision
    observation_provenance: ExecutionObservationProvenance
    display_precision: int
    trade_units_precision: int
```

Instruction invariants:

```text
Strategy action = matching OPEN_LONG / OPEN_SHORT
EntryPolicy = IMMEDIATE
instrument = EUR_USD
account = OANDA / PRACTICE / USD

PRE_FLIGHT approved
PRE_SUBMISSION approved

requested_quantity
    == pre_submission.quantity

approved_entry_price
    == pre_submission.entry_price

stop_price
    == pre_submission.stop_price

pricing_time >= decision_time
```

The instruction intentionally does not contain:

```text
target_price as a broker instruction
signed units
MARKET
FOK
OPEN_ONLY
raw OANDA JSON
broker IDs
credentials
```

The Strategy's `TargetProposal` remains available through `strategy_decision.target`.

### 5.3 Preparation refusal

Use a separate immutable refusal:

```python
class PaperExecutionRefusalCode(StrEnum):
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    ACCOUNT_UNSUPPORTED = "ACCOUNT_UNSUPPORTED"
    INSTRUMENT_UNSUPPORTED = "INSTRUMENT_UNSUPPORTED"
    OBSERVATION_INVALID = "OBSERVATION_INVALID"
    ENTRY_STATE_BLOCKED = "ENTRY_STATE_BLOCKED"
    RISK_REJECTED = "RISK_REJECTED"
    LOCAL_SERIALIZATION_REJECTED = "LOCAL_SERIALIZATION_REJECTED"
```

```python
@dataclass(frozen=True, slots=True)
class PaperExecutionRefusal:
    attempt_id: UUID
    code: PaperExecutionRefusalCode
    detail_code: str
    submitted: Literal[False] = False
```

No free-form raw broker response text belongs here.

## 6. Fresh read and Risk sequence

One invocation executes serially:

```text
1. allocate attempt_id

2. validate StrategyDecision
   IMMEDIATE OPEN_LONG/OPEN_SHORT only

3. GET /v3/accounts
   prove configured account
   prove non-MT4

4. GET /v3/accounts/{accountID}
   normalize coherent execution account snapshot

5. enforce:
   supported GSLO mode
   flat account
   zero pending orders
   exact count coherence

6. GET /v3/accounts/{accountID}/instruments?instruments=EUR_USD
   prove execution precision/capability

7. GET current EUR/USD pricing

8. invoke evaluate_paper_risk(...) exactly once
   using summary/trades/positions from coherent snapshot
   plus current pricing

9. require PaperRiskOutcome.APPROVED

10. validate exact provider serialization
    of quantity, priceBound, and stop

11. construct PaperExecutionInstruction

12. translate and submit entry exactly once
```

No additional Risk call is made.

No pricing read may occur after Risk without invalidating the instruction.

If another pricing read is required:

```text
discard instruction
rerun full fresh composition
```

Do not widen a stale bound.

## 7. Entry Market Order translation

The entry payload is exactly:

```json
{
  "order": {
    "type": "MARKET",
    "instrument": "EUR_USD",
    "units": "<signed exact whole units>",
    "timeInForce": "FOK",
    "priceBound": "<fresh Risk entry price>",
    "positionFill": "OPEN_ONLY",
    "clientExtensions": {
      "id": "<client_order_id>",
      "tag": "atlas-paper-04"
    },
    "tradeClientExtensions": {
      "id": "<client_trade_id>"
    },
    "stopLossOnFill": {
      "price": "<exact Strategy stop>",
      "timeInForce": "GTC",
      "clientExtensions": {
        "id": "<client_stop_loss_order_id>"
      }
    }
  }
}
```

There is no:

```text
takeProfitOnFill
IOC
GTD
guaranteedStopLossOnFill
trailingStopLossOnFill
distance-based stop
triggerCondition override
slippage widening
```

### Signed units

Risk quantity is positive.

OANDA translation is:

```text
LONG  → +quantity
SHORT → -quantity
```

Generic Risk remains unsigned/provider-neutral.

### Price serialization

Use the provider-observed:

```text
displayPrecision
```

as the exact representability boundary.

A Decimal is valid only if serializing it at the observed scale does not alter its mathematical value.

Do not round.

### Unit serialization

Use:

```text
tradeUnitsPrecision
minimumTradeSize
maximumOrderUnits
```

to validate the requested quantity.

For current EUR/USD capability the expected unit precision is zero.

## 8. Correlation

Allocate one UUID:

```text
attempt_id
```

per independent logical execution attempt.

Derive stable bounded IDs:

```text
client_order_id
  = atlas-p04-o-<attempt_hex>

client_trade_id
  = atlas-p04-t-<attempt_hex>

client_stop_loss_order_id
  = atlas-p04-sl-<attempt_hex>

client_take_profit_order_id
  = atlas-p04-tp-<attempt_hex>
```

The same IDs survive:

```text
translation
entry POST
readback
Trade confirmation
target creation
```

Never generate replacement IDs after uncertainty.

A genuinely new operator-authorized attempt gets a new UUID.

Duplicate-client-ID broker rejection is:

```text
REJECTED
```

not a retry signal.

Client extensions are used only after the AccountProperties non-MT4 proof succeeds.

## 9. Write requester

Create a separate write requester, for example:

```text
OandaPracticeMutationRequester
```

It owns:

```text
POST
PUT
```

for the exact approved execution endpoints only.

It must:

```text
use Practice base URL
validate token
apply bounded timeouts
send authenticated JSON
sanitize diagnostics
perform exactly one request per mutation call
```

It must not:

```text
retry POST
retry PUT
backoff and resend mutation
switch environment
log credentials
return raw response body as application evidence
```

The GET requester remains unchanged.

## 10. Entry response normalization

Normalize only provider facts required to establish this attempt.

### 10.1 Supported definite Fill

Require:

```text
orderCreateTransaction.type == MARKET_ORDER
orderFillTransaction.type == ORDER_FILL
```

and exact agreement on:

```text
account
instrument
provider Order ID
client Order ID
signed quantity
FOK
OPEN_ONLY
priceBound
Trade client ID
```

Fill requires:

```text
tradeOpened exists
no tradeReduced
no tradesClosed
abs(fill units) == requested quantity
tradeOpened units == fill units
tradeOpened Trade ID valid
tradeOpened price positive
```

Use:

```text
tradeOpened.price
```

as actual Fill price.

Do not use requested price as actual execution.

### 10.2 Bound invariant

Require:

```text
LONG:
actual_fill_price <= approved_entry_price

SHORT:
actual_fill_price >= approved_entry_price
```

A provider-confirmed violation is an execution invariant failure requiring reconciliation.

### 10.3 Actual initial Risk

After a valid Fill calculate for explanation:

```text
actual_loss_per_unit
    = abs(actual_fill_price - stop_price)

actual_initial_risk
    = actual_filled_quantity × actual_loss_per_unit
```

Require correct geometry:

```text
LONG  → stop < actual fill
SHORT → stop > actual fill
```

and:

```text
actual_initial_risk
<= pre_submission.risk_budget
```

Do not replace or mutate the original RiskDecision.

Retain both:

```text
pre-submission Risk evidence
actual broker execution comparison
```

### 10.4 Definite cancellation

A matching:

```text
orderCreateTransaction
+
orderCancelTransaction
```

with no Fill is:

```text
CANCELLED
```

This is the supported FOK kill path.

### 10.5 Definite rejection

A complete matching:

```text
orderRejectTransaction
```

is:

```text
REJECTED
```

Risk approval and broker rejection remain distinct truths.

### 10.6 Unsupported/uncertain response

These are not clean terminal success:

```text
create only
reissue path
partial Fill
fill + cancel
fill + reject
wrong account
wrong instrument
wrong units
wrong client IDs
wrong order type
wrong positionFill
wrong priceBound
malformed transaction
ambiguous duplicate terminal facts
invalid JSON after possible submission
transport uncertainty
```

Use bounded readback where permitted.

Otherwise return:

```text
UNKNOWN
```

for entry-state uncertainty.

## 11. Bounded entry readback

After uncertain entry mutation, never submit again.

Use the original client Order ID.

Logical readback budget:

```text
1. GET exact Order by @client_order_id

2. if Order proves FILLED:
     GET its fillingTransactionID

3. if Order proves CANCELLED:
     GET its cancellingTransactionID

4. if Fill proves Trade:
     GET full Trade detail
```

Existing safe GET retry behavior may apply within one logical GET.

Do not extend the logical readback sequence indefinitely.

These remain unknown:

```text
Order not found
PENDING Market Order
unrecognized state
malformed correlation
readback transport failure
contradictory transaction
```

Not-found never proves rejection.

No cancellation/recovery mutation is allowed.

## 12. Stop-loss confirmation

A valid entry Fill proves exposure but not yet clean protection.

Perform one full Trade-detail GET using the confirmed broker Trade ID.

Require:

```text
matching account
matching Trade ID
matching client Trade ID
EUR_USD
OPEN state
matching signed initial/current units
matching broker open price
```

Require exactly one expected ordinary Stop Loss dependent Order with:

```text
type = STOP_LOSS
state = PENDING
matching Trade ID
matching client_stop_loss_order_id
price == instruction.stop_price
timeInForce = GTC
```

If the Trade is filled but Stop Loss cannot be proven:

```text
FILLED_PROTECTION_INCOMPLETE
```

Do not attempt Take Profit.

Do not submit a repair Stop in this workstream.

This is exposure that requires operator/reconciliation handling.

## 13. Actual-fill target derivation

Only after:

```text
entry Fill proven
+
Trade proven OPEN
+
Stop Loss proven PENDING
```

derive:

```python
actual_target = strategy_decision.target.resolve(
    fill.price,
    instruction.stop_price,
    instruction.direction,
)
```

Require:

```text
LONG:
actual_target > fill.price > stop

SHORT:
actual_target < fill.price < stop
```

The result must be exactly representable at observed EUR/USD `displayPrecision`.

If not:

```text
do not round
do not submit target
return FILLED_PROTECTION_INCOMPLETE
detail = TARGET_PRECISION_UNREPRESENTABLE
```

The PAPER 03 `pre_submission.target_price` remains retained Risk evidence and may differ from `actual_target`.

That difference is expected when the Fill improves.

## 14. Take Profit mutation

After exact target derivation, perform at most one:

```text
PUT /v3/accounts/{accountID}/trades/{tradeID}/orders
```

with:

```json
{
  "takeProfit": {
    "price": "<actual_target>",
    "timeInForce": "GTC",
    "clientExtensions": {
      "id": "<client_take_profit_order_id>"
    }
  }
}
```

Do not send:

```text
stopLoss
stopLoss=null
guaranteedStopLoss
trailingStopLoss
```

Omitting Stop Loss is deliberate so the existing confirmed Stop is not modified.

The mutation is not retried.

### Definite target confirmation

A successful target mutation must prove a matching:

```text
TakeProfitOrderTransaction
```

with:

```text
Trade ID
client Trade ID where present
client Take Profit Order ID
exact actual_target
GTC
```

Then perform one final Trade-detail GET and require:

```text
Trade remains OPEN
same confirmed Stop Loss remains PENDING
Take Profit exists
Take Profit state = PENDING
Take Profit price = actual_target
matching target client ID
```

Only then is the final result:

```text
FILLED_PROTECTED
```

### Target mutation uncertainty/rejection

If target PUT:

```text
times out
connection resets
returns malformed result
returns reject
creates then immediately cancels/fills
or final Trade readback cannot confirm expected open protected state
```

do not retry automatically.

Return:

```text
FILLED_PROTECTION_INCOMPLETE
```

with:

```text
entry Fill facts retained
confirmed Stop facts retained when proven
target state/rejection/uncertainty retained
```

Atlas knows exposure was created.

Do not downgrade this to generic entry `UNKNOWN`.

## 15. Result contracts

### Entry-level outcomes

```python
class PaperExecutionOutcome(StrEnum):
    FILLED_PROTECTED = "FILLED_PROTECTED"
    FILLED_PROTECTION_INCOMPLETE = "FILLED_PROTECTION_INCOMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"
```

`UNKNOWN` means the entry exposure itself could not be established definitively.

`FILLED_PROTECTION_INCOMPLETE` means exposure **is** proven but intended protection is not fully established.

### Correlation

```python
@dataclass(frozen=True, slots=True)
class ExecutionCorrelation:
    attempt_id: UUID
    client_order_id: str
    client_trade_id: str
    client_stop_loss_order_id: str
    client_take_profit_order_id: str
```

### Fill facts

```python
@dataclass(frozen=True, slots=True)
class BrokerFillFacts:
    broker_order_id: str
    broker_fill_transaction_id: str
    broker_trade_id: str
    signed_units: Decimal
    price: Decimal
    executed_at: datetime
    actual_initial_risk: Decimal
```

Every value comes from validated broker facts except the derived `actual_initial_risk`.

### Protection

Represent Stop and Take Profit independently.

Strong expected shape:

```python
class ProtectionLegStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
```

```python
@dataclass(frozen=True, slots=True)
class BrokerProtectionOrder:
    broker_order_id: str
    client_order_id: str
    price: Decimal
    state: str
```

```python
@dataclass(frozen=True, slots=True)
class ProtectionConfirmation:
    stop_loss_status: ProtectionLegStatus
    stop_loss: BrokerProtectionOrder | None
    take_profit_status: ProtectionLegStatus
    take_profit: BrokerProtectionOrder | None
    actual_target_price: Decimal | None
```

### Final result

```python
@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    outcome: PaperExecutionOutcome
    instruction: PaperExecutionInstruction
    correlation: ExecutionCorrelation
    fill: BrokerFillFacts | None
    protection: ProtectionConfirmation
    rejection: BrokerRejection | None
    uncertainty: BrokerUncertainty | None
    transaction_provenance: TransactionProvenance
    diagnostic_codes: tuple[str, ...]
```

Result invariants:

### FILLED_PROTECTED

```text
Fill proven
full requested FOK quantity
actual Risk <= approved budget
Stop confirmed PENDING
actual target derived from actual Fill
target exactly representable
Take Profit confirmed PENDING
no unresolved mutation uncertainty
```

### FILLED_PROTECTION_INCOMPLETE

```text
Fill proven
+
required fully protected state not proven
```

Fill facts must remain visible.

### REJECTED

```text
provider rejection proven
no Fill
```

### CANCELLED

```text
FOK cancellation proven
no Fill
```

### UNKNOWN

```text
entry outcome cannot be established
```

Do not claim flatness or Fill.

## 16. Transaction provenance

Retain bounded provider evidence:

```text
HTTP RequestID
provider transaction IDs
batch IDs
relatedTransactionIDs
lastTransactionID
entry Order ID
Fill transaction ID
Trade ID
Stop transaction/order IDs
Take Profit transaction/order IDs
readback RequestIDs
```

Do not retain:

```text
credentials
raw HTTP bodies
unbounded errorMessage text
arbitrary provider JSON
```

Provider rejection reasons may be normalized into bounded string/code vocabularies.

## 17. Residual race and PAPER 05 boundary

The coherent Account Details snapshot is stronger than multiple independent account-state reads.

It still does not create a conditional broker transaction.

The unavoidable sequence remains:

```text
Account Details snapshot
→ pricing
→ Risk
→ POST
```

Another actor could modify the account between those steps.

Likewise, Atlas currently has no:

```text
durable execution lease
multi-process lock
restart-safe attempt ownership
transaction cursor
persistent UNKNOWN recovery
```

Do not hide this.

PAPER 05 must introduce durable:

```text
attempt ownership
broker transaction lineage
PAPER Order/Fill/Trade state
reconciliation
unknown-outcome recovery
protection-state recovery
restart safety
```

PAPER 06 must not activate repeated autonomous execution until PAPER 05 can prove safe resume.

## 18. Historical Experiment boundary

Do not modify in meaning:

```text
historical Order
historical Fill
historical ExecutionObservation
SimulatedExecutionAdapter
ExperimentRunner
Experiment persistence
Experiment accounting
```

Real broker behavior is explicitly different:

```text
Risk reference price
≠ necessarily actual broker Fill price
```

Historical deterministic equality remains historical methodology only.

## 19. Expected implementation ownership

Strong expected new/changed areas:

```text
backend/paper/execution.py
backend/paper/__init__.py

backend/integrations/oanda/execution_account.py
backend/integrations/oanda/execution_instrument.py
backend/integrations/oanda/mutation_request.py
backend/integrations/oanda/execution.py
backend/integrations/oanda/__init__.py

focused tests
```

Exact filenames may vary if the ownership remains equivalent.

Narrow normalization-helper extraction from existing OANDA observation modules is allowed if required to reuse the exact 01B–01E semantics.

Expected unchanged in meaning:

```text
backend/risk/service.py
backend/execution/
backend/experiments/
backend/persistence/
backend/runtime/main.py
backend/strategies/
frontend/
migrations/
```

If implementation requires changing shared Risk semantics or Strategy methodology, stop `BLOCKED`.

## 20. Expected task decomposition

Do not create tasks before approval.

Strong expected post-approval tasks:

```text
T001 — read-only execution account/instrument capability
T002 — PAPER execution contracts + entry translation
T003 — non-retrying OANDA entry mutation + normalization/readback
T004 — actual-Fill protection completion
T005 — capital-capable PAPER execution composition
```

T004/T005 may be combined if the implementation remains understandable.

Do not split one helper per task.

Do not create PAPER 04A/04B micro-workstreams.

## 21. Focused deterministic test matrix

All mutation tests use:

```text
httpx.MockTransport
fake readers
fixed UUIDs
normalized fixtures
```

Never real credentials.

### Capability/read gates

Test:

```text
non-MT4 account accepted
MT4 account rejected
configured account absent/duplicated
GSLO DISABLED accepted
GSLO ALLOWED accepted
GSLO REQUIRED rejected
EUR_USD instrument exactly present
display precision mismatch
unit precision mismatch
minimum/maximum quantity violation
```

### Coherent account snapshot

Test:

```text
single Account Details response
summary/trade/position/order same transaction frontier
count mismatch
flat
non-flat
pending order
unsupported instrument
normalization contradiction
```

### PAPER Risk handoff

Test:

```text
fresh evaluate_paper_risk called exactly once
no stale evaluation authority
NO_ACTION
PRICE_TRIGGERED
Risk rejection
pricing rejection
selected quantity/entry copied exactly
```

### Entry payload

Test:

```text
LONG positive units
SHORT negative units
MARKET
FOK
OPEN_ONLY
exact priceBound
exact stopLossOnFill
GTC
no takeProfitOnFill
deterministic client IDs
no rounding
precision rejection
```

### Entry write semantics

Test:

```text
one POST only
no retry after timeout
no retry after 429/5xx
sanitized auth/error handling
Practice endpoint only
```

### Entry outcomes

Test:

```text
valid full Fill
valid FOK cancel
valid broker reject
create-only uncertainty
timeout uncertainty
malformed response
reissue
partial Fill
wrong account/instrument/units/client ID
Fill+cancel contradiction
```

### Fill invariants

Test:

```text
TradeOpen.price authority
better LONG Fill
better SHORT Fill
worse-than-bound violation
wrong-side stop geometry
actual initial risk <= budget
full requested quantity required
```

### Stop confirmation

Test:

```text
matching pending Stop
missing Stop
wrong client ID
wrong price
wrong Trade
cancelled/filled Stop
Trade not OPEN
readback failure
```

### Actual target

Test:

```text
LONG target from actual Fill
SHORT target from actual Fill
actual target differs from PAPER 03 target after better Fill
exact precision accepted
unrepresentable exact target not rounded
```

### Take Profit mutation

Test:

```text
one PUT only
only takeProfit field present
Stop not modified
exact actual target
GTC
deterministic target client ID
target reject
target timeout
target malformed response
```

### Final protection

Test:

```text
both protections confirmed → FILLED_PROTECTED
Fill + Stop only → FILLED_PROTECTION_INCOMPLETE
Fill + target uncertainty → FILLED_PROTECTION_INCOMPLETE
entry uncertainty → UNKNOWN
no automatic recovery mutation
```

### Isolation

Test:

```text
Experiment contracts unchanged
Risk tests unchanged
PAPER 03 tests unchanged
no persistence/runtime/API/UI side effects
```

## 22. Validation expectations

Expected focused suite includes:

```text
PAPER 03 Risk
new PAPER execution
OANDA account
OANDA orders
OANDA pricing/projection
new execution account/instrument capability
new mutation adapter
Risk regression
historical Experiment regression
```

Run changed-file:

```text
ruff format --check
ruff check
pyright
git diff --check
```

A broad non-integration/non-external backend suite is justified for this Critical broker boundary if focused tests pass.

Do not perform:

```text
credentialed Practice mutation
external broker test
frontend/browser
migration
runtime activation
```

## 23. Forbidden side effects

The implementation must never:

```text
retry an uncertain entry POST
retry an uncertain target PUT
create a second exposure attempt after UNKNOWN
cancel or close exposure automatically
repair an unconfirmed Stop automatically
round broker-bound Risk/Strategy prices
send the pre-submission target as the actual target
omit the Stop from the entry request
use client extensions without proving non-MT4
use ordinary Stop when GSLO is REQUIRED
reuse historical Order/Fill contracts
persist broker financial state
activate PAPER
touch LIVE
```

## 24. Summary

The frozen PAPER 04 vertical slice is:

```text
read-only broker capability proof
        ↓
coherent full account snapshot
        ↓
current pricing
        ↓
fresh PAPER 03 Risk
        ↓
exact FOK entry with priceBound + Stop
        ↓
broker-confirmed actual Fill
        ↓
confirm Stop
        ↓
re-resolve R-multiple Target from actual Fill
        ↓
one exact Take Profit mutation
        ↓
FILLED_PROTECTED
```

Anything less certain remains explicit:

```text
REJECTED
CANCELLED
UNKNOWN
FILLED_PROTECTION_INCOMPLETE
```

This slice establishes the first truthful capital-capable mutation contract.

It does not establish persistence, reconciliation, restart safety, repeated execution, PAPER activation, or LIVE authority.

Those remain later lifecycle boundaries.
