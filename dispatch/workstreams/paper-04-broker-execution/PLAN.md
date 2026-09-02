# PLAN — PAPER 04 Broker Execution

## Workstream state

- **Workstream:** `paper-04-broker-execution`
- **Outcome:** Define and, after explicit approval, implement the smallest fail-closed OANDA Practice broker-mutation slice that obtains one coherent current account snapshot, re-runs PAPER Risk against current executable pricing, submits one bounded FOK EUR/USD Market Order with immediate stop-loss protection, derives actual execution only from broker-confirmed Fill facts, then establishes the Strategy's exact R-multiple target from the actual Fill through one bounded dependent-order mutation.
- **Classification:** `Critical`. This workstream crosses the first broker-mutation and capital-capable boundary. It establishes execution semantics future PAPER runtime and reconciliation will depend upon.
- **Base:** `main` at `53c6b22` (`Close PAPER 03 workstream`).
- **Base SHA:** `53c6b229d6d5081e7853163d7e70952d14c33d61`.
- **Branch:** `solo/paper-04-broker-execution`.
- **Phase:** `READY_FOR_USER`.
- **Approval:** developer implementation approval granted for the frozen PLAN and ARCHITECTURE; GIT START completed.
- **Architecture:** `FROZEN`; `ARCHITECTURE.md` is canonical with this PLAN.
- **Task state:** T001–T005 DONE; R001 DONE; latest validation and review chains PASS.
- **Next action:** stop for explicit developer merge approval; do not merge or perform broker mutation before approval.
- **Concerns:** No HTTP response alone proves exposure. Entry mutation uncertainty must never trigger blind resubmission. The exact Strategy target depends on the actual Fill price and therefore cannot be frozen safely in the entry request. Required ordinary Stop Loss support, non-MT4 client-extension eligibility, and EUR/USD execution precision must be established read-only before mutation. No credentialed mutation, PAPER activation, or LIVE behavior is authorized by this plan. Durable reconciliation remains PAPER 05 scope.

## 1. Capability boundary

The initial capability is deliberately narrow:

```text
PAPER 02 StrategyDecision
        ↓
read-only execution capability checks
  account properties
  EUR/USD instrument metadata
        ↓
one OANDA full Account Details snapshot
  account state
  open Trades
  open Positions
  pending Orders
  account protection mode
        +
one current EUR/USD pricing observation
        ↓
existing PAPER 03 Risk composition
        ↓
provider-neutral PaperExecutionInstruction
        ↓
one MARKET / FOK / OPEN_ONLY entry POST
  exact Risk priceBound
  exact Strategy stopLossOnFill
        ↓
broker proves FILL / CANCEL / REJECT
or submission remains UNKNOWN
        ↓
if filled:
  confirm Trade + Stop Loss
  derive target from ACTUAL Fill
        ↓
one dependent Take Profit mutation
        ↓
PaperExecutionResult
```

The supported scope is exactly:

```text
OANDA Practice
one configured USD account
EUR_USD
IMMEDIATE entry only
OPEN_LONG / OPEN_SHORT
flat account
zero existing pending Orders
whole-unit quantity
ordinary Stop Loss supported
non-MT4 account
FOK entry
OPEN_ONLY position fill
```

PAPER 04 does not accept a stale `PaperRiskEvaluation` as authority.

The public capital-capable application seam accepts the immutable Strategy proposal and explicit Risk configuration, then performs its own fresh reads and PAPER 03 evaluation.

Do not expose a public path that allows:

```text
old PaperRiskEvaluation
→ raw broker POST
```

## 2. Explicit exclusions

Do not add:

```text
LIVE
PAPER activation
scheduler/runtime loop
API/UI
durable PAPER Order/Trade/Fill persistence
accounting
restart-safe reconciliation
automatic retry/resubmission
partial-fill accounting
IOC
PRICE_TRIGGERED entries
closing
position reduction
manual protection edits
multiple simultaneous execution attempts
multiple instruments/brokers
generic broker framework
Risk-policy administration
historical Experiment contract changes
```

The workstream may perform at most:

```text
one entry Market Order POST

and, only after a broker-confirmed Fill with confirmed Stop Loss,

one dependent Take Profit mutation
```

Neither mutation may be automatically retried after uncertain transport outcome.

## 3. Non-negotiable safety invariants

### 3.1 PAPER 03 approval is never durable authority

PAPER 03 `APPROVED` remains:

```text
observation-scoped
read-only
non-durable
```

PAPER 04 must acquire its own current observations and invoke the existing:

```python
evaluate_paper_risk(...)
```

exactly once before constructing an entry instruction.

Do not copy PAPER 03 logic into execution.

Do not call Risk separately around it.

The fresh PAPER 03 result is authoritative for:

```text
PRE_FLIGHT
PRE_SUBMISSION
entry reference
quantity
stop
risk budget
target methodology evidence
```

### 3.2 Use one coherent account snapshot

Do not use five independent account-state GETs as the primary mutation gate.

Add a narrow read-only OANDA execution snapshot based on:

```text
GET /v3/accounts/{accountID}
```

OANDA's full Account Details response contains:

```text
account financial state
full open Trades
full open Positions
full pending Orders
one lastTransactionID
guaranteedStopLossOrderMode
```

Normalize the required subset into one immutable:

```text
OandaPracticeExecutionAccountSnapshot
```

or equivalent.

The snapshot should provide existing PAPER 03-compatible values:

```text
OandaPracticeAccountSummarySnapshot
OandaPracticeOpenTradeInventory
OandaPracticeOpenPositionInventory
OandaPracticePendingOrderInventory
```

all derived from the same provider response and transaction frontier.

Do not modify 01B/01C/01D/01E meanings merely to support this reader.

Prefer reusable pure normalization helpers where needed.

### 3.3 Account capability must be proven before mutation

Before constructing any client-extension-bearing order, use:

```text
GET /v3/accounts
```

and require the configured account's `AccountProperties` to be present exactly once.

The account is supported only if:

```text
mt4AccountID is absent
```

Do not discover MT4 incompatibility by attempting an Order.

From the coherent full Account Details snapshot also require:

```text
guaranteedStopLossOrderMode != REQUIRED
```

The initial Atlas Risk methodology does not model guaranteed-stop premiums or guaranteed-stop execution economics.

Therefore an account requiring guaranteed Stop Loss Orders is unsupported by this slice and must fail before POST.

Do not silently substitute:

```text
guaranteedStopLossOnFill
```

for ordinary `stopLossOnFill`.

### 3.4 Execution precision must be provider-validated

Before mutation read:

```text
GET /v3/accounts/{accountID}/instruments?instruments=EUR_USD
```

and require exactly one EUR/USD instrument capability.

Retain at minimum:

```text
displayPrecision
tradeUnitsPrecision
minimumTradeSize
maximumOrderUnits
```

The initial validated capability is expected to prove:

```text
displayPrecision == 5
tradeUnitsPrecision == 0
```

but do not hardcode those values without checking the provider observation.

No broker-bound Decimal may be rounded.

If:

```text
entry bound
stop
actual target
```

cannot be represented exactly at the observed display precision, that value cannot be submitted.

The entry/stop precision gate occurs before exposure creation.

The actual target precision gate necessarily occurs after Fill because its value depends on actual Fill.

### 3.5 Flatness and pending-order gate

From the coherent Account Details snapshot require:

```text
summary.open_trade_count == len(trades.trades) == 0
summary.open_position_count == len(positions.positions) == 0
summary.pending_order_count == len(pending_orders.orders) == 0
```

and:

```text
project_oanda_practice_eur_usd_exposure_state(
    trades,
    positions,
) == FLAT
```

Do not infer flatness only from counts.

Do not cancel or reinterpret existing pending Orders.

### 3.6 Provider-neutral instruction is not an Order

The PAPER application boundary constructs a provider-neutral immutable instruction only after fresh Risk approval.

It contains:

```text
attempt identity
account identity
Strategy decision
direction
positive Risk quantity
approved Risk entry reference
Strategy stop
fresh Risk decisions
observation provenance
execution capability provenance
```

It contains no:

```text
signed OANDA units
MARKET
FOK
OPEN_ONLY
JSON
client ID wire fields
credentials
historical Order
historical Fill
```

OANDA translation owns those provider details.

### 3.7 Risk's entry boundary cannot be widened

The OANDA Market Order must use:

```text
priceBound = fresh PRE_SUBMISSION entry_price
```

exactly.

For LONG this is the maximum acceptable entry.

For SHORT this is the minimum acceptable entry.

Do not add:

```text
slippage allowance
pip tolerance
percentage tolerance
```

after Risk.

A better Fill is allowed.

A worse Fill beyond the approved bound is an execution invariant violation.

### 3.8 FOK only

Use:

```text
timeInForce = FOK
```

not IOC.

PAPER 03 approves one whole-unit quantity and Atlas does not yet own partial-fill accounting.

A successful supported Fill must therefore correspond to the full requested quantity.

Any partial/reissue path is unsupported and fails closed.

### 3.9 Stop immediately; target after actual Fill

The initial Market Order must attach:

```text
stopLossOnFill
```

using the exact Strategy/Risk stop.

Do **not** attach:

```text
takeProfitOnFill
```

using PAPER 03's pre-submission `target_price`.

Atlas `TargetProposal` is an `R_MULTIPLE` resolved from entry and stop.

The existing Experiment methodology re-resolves target geometry from actual Fill.

Therefore:

```text
actual target
=
StrategyDecision.target.resolve(
    actual broker Fill price,
    frozen Strategy stop,
    direction,
)
```

A better Fill changes the correct target.

Sending the PAPER 03 target before the actual Fill would silently change Strategy methodology.

After a broker-confirmed Fill:

```text
confirm opened Trade
confirm attached Stop Loss
derive actual target from actual Fill
validate exact provider precision
submit Take Profit through Trade dependent-order endpoint
```

The dependent-order request must specify only:

```text
takeProfit
```

so the existing Stop Loss remains unchanged.

### 3.10 No rounding of actual target

If the exact actual-Fill R-multiple target cannot be represented at the provider's observed display precision:

```text
do not round
do not move the target
do not approximate R
```

The Trade remains a broker-confirmed Fill with its Stop Loss.

Return:

```text
FILLED_PROTECTION_INCOMPLETE
```

with an explicit target-precision diagnostic.

Do not falsely report a fully protected methodology-preserving success.

### 3.11 Mutation uncertainty is first-class

The entry requester and dependent-protection requester are separate from the safe-retrying GET requester.

Neither write operation may automatically retry.

A timeout or connection reset may mean:

```text
broker acted
client did not receive proof
```

Therefore:

```text
uncertain entry POST
→ UNKNOWN

uncertain target mutation after proven Fill
→ FILLED_PROTECTION_INCOMPLETE
```

Do not translate either case into rejection.

Do not resubmit automatically.

### 3.12 Actual execution comes only from broker facts

Actual exposure is proven only from normalized broker transactions.

Do not infer a Fill from:

```text
requested quantity
HTTP 201
Order creation alone
summary count changes
missing pending order
Risk approval
```

A supported entry Fill requires a matching:

```text
OrderFillTransaction
tradeOpened
```

with exact account/instrument/order/correlation/direction/full-quantity agreement.

Use:

```text
TradeOpen.price
```

as actual execution price.

Do not use the deprecated top-level `OrderFillTransaction.price` as authority.

## 4. Official OANDA contract constraints

The implementation must rely only on official v20 semantics.

### Account capability

```text
GET /v3/accounts
→ AccountProperties[]
```

`AccountProperties.mt4AccountID` is present only for MT4-associated accounts.

### Coherent account snapshot

```text
GET /v3/accounts/{accountID}
```

returns full Account Details including open Trades, Positions and pending Orders.

The Account contract also exposes:

```text
guaranteedStopLossOrderMode
```

### Instrument capability

```text
GET /v3/accounts/{accountID}/instruments?instruments=EUR_USD
```

provides instrument-specific:

```text
displayPrecision
tradeUnitsPrecision
minimumTradeSize
maximumOrderUnits
```

### Market Order

```text
POST /v3/accounts/{accountID}/orders
```

with:

```text
type = MARKET
positive units = LONG
negative units = SHORT
timeInForce = FOK
priceBound = worst acceptable price
positionFill = OPEN_ONLY
```

Client Order and Trade extensions may be used only after the non-MT4 precondition is proven.

### Protection

Market Order request supports:

```text
stopLossOnFill
```

with absolute price and client extensions.

The Trade dependent-order endpoint:

```text
PUT /v3/accounts/{accountID}/trades/{tradeSpecifier}/orders
```

can create a Take Profit independently.

If `stopLoss` is omitted from that request, the existing Stop Loss is not modified.

### Fill

`OrderFillTransaction` carries:

```text
orderID
clientOrderID
instrument
units
time
tradeOpened
```

and the embedded `TradeOpen` carries:

```text
tradeID
units
price
```

The individual TradeOpen price is the execution authority for the opened Trade.

### Market Order outcomes

Create-order responses may include:

```text
orderCreateTransaction
orderFillTransaction
orderCancelTransaction
orderReissueTransaction
orderReissueRejectTransaction
relatedTransactionIDs
lastTransactionID
```

HTTP 201 alone is not Fill proof.

## 5. Reuse and boundary inventory

### Reuse

```text
StrategyDecision
TargetProposal
EntryPolicy
Action
Direction

RiskConfig
RiskDecision
RiskService

evaluate_paper_risk
PaperRiskEvaluation

OANDA Practice account identity
existing summary/trade/position/pending-order normalized contracts
existing account/exposure projections
OANDA pricing observation/projection
OandaObservationRequester for GET only
OANDA Practice base URL
existing primitive parsers
```

### New bounded capabilities

Expected:

```text
read-only AccountProperties / execution-account eligibility
read-only coherent execution Account Details snapshot
read-only EUR/USD execution instrument metadata

provider-neutral PaperExecutionInstruction
PaperExecutionRefusal
PaperExecutionResult

non-retrying OANDA mutation requester
OANDA Market Order translation
OANDA entry response normalization
OANDA Trade-detail protection confirmation
dependent Take Profit mutation/normalization
bounded readback after write uncertainty
```

### Must remain unchanged in meaning

```text
backend/execution/contract.py
backend/execution/simulated.py
backend/experiments/runner.py
historical Order/Fill/persistence
PAPER 03 Risk semantics
Risk sizing semantics
runtime/main.py
```

## 6. Acceptance criteria for implementation

1. No real broker mutation occurs during BUILD, VALIDATE, or REVIEW.

2. Only OANDA Practice EUR/USD IMMEDIATE OPEN_LONG/OPEN_SHORT is executable.

3. PAPER 04 does not accept an old PAPER 03 approval as execution authority.

4. A non-MT4 account is proven read-only through AccountProperties before client extensions are used.

5. Accounts requiring guaranteed Stop Loss Orders are rejected before POST.

6. Provider EUR/USD execution precision and unit precision are observed and validated before POST.

7. No broker-bound price or quantity is rounded.

8. The primary account state gate comes from one full Account Details response.

9. The full snapshot's summary, Trades, Positions and pending Orders describe one provider transaction frontier.

10. The account must be flat with zero pending Orders.

11. Current pricing is acquired after the account-state snapshot and PAPER 03 is run exactly once over current normalized facts.

12. Only fresh PAPER 03 `APPROVED` may produce an instruction.

13. Risk quantity is copied exactly.

14. Risk entry reference becomes exact `priceBound`.

15. Entry uses MARKET/FOK/OPEN_ONLY.

16. LONG units are positive and SHORT units negative only in OANDA translation.

17. Entry POST contains exact `stopLossOnFill`.

18. Entry POST does not contain `takeProfitOnFill`.

19. Entry POST is attempted at most once.

20. Transport uncertainty never triggers another POST.

21. HTTP success alone cannot prove Fill.

22. A supported Fill must prove the complete FOK quantity and one newly opened Trade.

23. Actual Fill price comes from `TradeOpen.price`.

24. A better Fill is accepted if stop geometry remains valid and actual initial risk does not exceed the approved budget.

25. A worse-than-bound Fill is an invariant violation.

26. A confirmed Fill must have its attached ordinary Stop Loss confirmed before Atlas attempts target creation.

27. Actual target is resolved from the actual Fill using the immutable Strategy `TargetProposal`.

28. PAPER 03's pre-submission target is evidence only and is never blindly sent as the broker target.

29. Actual target must be exactly representable at provider precision.

30. Unrepresentable target is not rounded; result is a confirmed Fill with incomplete protection.

31. At most one dependent Take Profit mutation is attempted.

32. The dependent target mutation omits Stop Loss so the confirmed Stop is not replaced.

33. Target mutation uncertainty is never automatically retried.

34. Clean `FILLED_PROTECTED` requires a broker-confirmed entry, confirmed Stop Loss, and confirmed pending Take Profit at the actual-fill-derived price.

35. A definite Fill with any incomplete protection remains visibly distinct from entry uncertainty.

36. Definite broker reject, FOK cancel/kill, uncertain entry, fully protected Fill, and protection-incomplete Fill are distinct outcomes.

37. Client correlation IDs are deterministic within one attempt and never regenerated during recovery.

38. Duplicate client-ID broker rejection is not a retry trigger.

39. No raw payload, credential, or unbounded provider text enters result diagnostics.

40. No historical Experiment Order/Fill, persistence, runtime, API/UI, activation, or LIVE behavior changes.

## 7. Architecture freeze checklist

`ARCHITECTURE.md` freezes:

```text
read-only non-MT4 account proof
coherent Account Details snapshot
ordinary-stop account capability
EUR/USD execution precision observation

public capital-capable application boundary
fresh PAPER 03 composition
provider-neutral instruction

MARKET/FOK/OPEN_ONLY entry
exact priceBound
stopLossOnFill only
client correlation

non-retrying write transport
entry response normalization
bounded uncertain-entry readback

Trade + Stop confirmation
actual-Fill target derivation
exact target precision rule
one dependent Take Profit mutation
target confirmation/uncertainty

PaperExecutionResult outcomes
residual race/reconciliation boundary
historical contract isolation
```

## 8. Lifecycle gate

Current Critical lifecycle:

```text
PLAN
→ ARCHITECTURE
→ reconcile PLAN + ARCHITECTURE
→ DEVELOPER_APPROVAL
```

Before explicit developer implementation approval, do not:

```text
GIT START
create feature branch
create tasks/
BUILD
VALIDATE
REVIEW
modify code/tests
add credentials
perform OANDA mutation
```

Implementation approval authorizes mocked implementation and deterministic testing only.

It does not authorize:

```text
Practice exposure
PAPER activation
LIVE exposure
```

## 9. Reconciled architecture freeze

The canonical architecture is:

```text
AccountProperties eligibility
        +
one coherent Account Details snapshot
        +
EUR/USD execution metadata
        +
current pricing
        ↓
fresh PAPER 03 Risk
        ↓
PaperExecutionInstruction
        ↓
one MARKET / FOK / OPEN_ONLY POST
  exact Risk priceBound
  exact stopLossOnFill
        ↓
Fill proven?
  no → REJECTED / CANCELLED / UNKNOWN
  yes
        ↓
confirm Trade + Stop
        ↓
derive exact TargetProposal from ACTUAL Fill
        ↓
one Take Profit mutation
        ↓
FILLED_PROTECTED
or
FILLED_PROTECTION_INCOMPLETE
```

The initial Market Order deliberately does **not** attach the pre-submission target.

That is required to preserve:

```text
Experiment → PAPER
TargetProposal R_MULTIPLE methodology
```

when real broker Fill differs from the Risk reference.

The remaining unavoidable race between account snapshot/pricing and broker mutation is explicit. PAPER 04 contains no durable execution lease, transaction cursor, or restart ownership. PAPER 05 must establish persistence and reconciliation before PAPER 06 may activate repeated autonomous trading.
