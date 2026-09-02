# ARCHITECTURE — PAPER 03 Risk + Executable Pricing

**Status:** Critical architecture freeze, pre-approval. This artifact defines a read-only Risk/pricing composition boundary only. It authorizes no broker I/O, mutation, execution, persistence, or durable state transition.

## 1. Shared Risk boundary

Keep the existing historical contract unchanged:

```python
@dataclass(frozen=True, slots=True)
class ExecutableQuote:
    bid: Decimal
    ask: Decimal
```

and preserve:

```python
RiskService.evaluate_pre_submission(
    ...,
    quote: ExecutableQuote,
) -> RiskDecision
```

with its current semantics.

Add one provider-neutral quantity-capacity fact:

```python
@dataclass(frozen=True, slots=True)
class ExecutablePrice:
    price: Decimal
    max_quantity: Decimal
```

Add a separate Risk entry point equivalent to:

```python
RiskService.evaluate_pre_submission_at_executable_price(
    intent,
    *,
    position,
    account,
    config,
    instrument,
    executable_price: ExecutablePrice,
) -> RiskDecision
```

Exact naming may vary slightly, but do not replace the historical quote API with a union merely for convenience.

Both PRE_SUBMISSION paths must delegate to one shared internal financial-sizing calculation so the methodology remains:

```text
validate financial preconditions
        ↓
validate entry/stop geometry
        ↓
risk_budget = equity × risk_per_trade
        ↓
loss_per_unit = abs(entry − stop)
        ↓
quantity = floor(risk_budget / loss_per_unit)
        ↓
actual_risk = quantity × loss_per_unit
        ↓
target = methodology.resolve(entry, stop, direction)
```

The new quantity-aware path additionally requires:

```text
quantity <= max_quantity
```

`ExecutablePrice` means:

> a direction-appropriate entry price with a finite observed maximum quantity supplied by the caller.

It does not mean:

```text
OANDA
PriceBucket
Order
Fill
authorization
```

Risk must never import OANDA or interpret bucket arrays.

Add only:

```text
INVALID_EXECUTABLE_PRICE
INVALID_EXECUTABLE_CAPACITY
INSUFFICIENT_EXECUTABLE_CAPACITY
```

to the generic Risk rejection vocabulary.

Semantics:

- non-positive/non-finite price → `INVALID_EXECUTABLE_PRICE`;
- negative/non-finite capacity → `INVALID_EXECUTABLE_CAPACITY`;
- valid capacity smaller than the computed whole-unit Risk quantity → `INSUFFICIENT_EXECUTABLE_CAPACITY`.

Zero capacity is valid-but-insufficient.

A rejected capacity-aware decision contains no approved quantity or target.

The existing `RiskDecision` shape remains unchanged.

Historical `ExecutableQuote` behavior and rejection semantics remain unchanged.

## 2. OANDA finite pricing projection

Keep:

```python
OandaPracticeEurUsdPricingObservation
OandaPracticePriceBucket
```

unchanged as normalized provider facts.

Add a pure OANDA pricing-projection seam, strongly:

```text
backend/integrations/oanda/pricing_projection.py
```

It accepts:

```text
OandaPracticeEurUsdPricingObservation
+
Direction
```

and performs no request.

### Required side

```text
LONG  → asks
SHORT → bids
```

The opposite side is irrelevant to this opening-price calculation.

### Provider validity

```text
tradeable=False
→ no executable candidates

required side empty
→ no executable candidates

required side has no positive-liquidity bucket
→ no executable candidates
```

Zero-liquidity buckets remain evidence.

### Candidate fact

Every positive-liquidity required-side bucket becomes one finite candidate:

```text
price
available_quantity
```

The integration boundary does **not**:

```text
select the first bucket
select the final Risk price
aggregate liquidity
compute Risk quantity
compute weighted price
assume array order
```

The projection retains enough information to explain every normalized required-side source bucket and its candidate/non-candidate disposition.

Do not use:

```text
closeoutBid
closeoutAsk
midpoint
opposite side
historical bars
```

as opening-price fallback.

### Official semantic boundary

The architecture relies only on OANDA's documented facts:

- `ClientPrice.time` is the Price creation time;
- `tradeable` states whether the Price is tradeable;
- bid and ask arrays contain side-specific prices/liquidity and may independently be empty;
- each PriceBucket carries one price and one amount of liquidity;
- closeout prices are not opening prices;
- Market Orders support a requested quantity, FOK/IOC time-in-force, and a worst acceptable `priceBound`.

The architecture does **not** assume OANDA documents:

```text
bucket array ordering
cumulative bucket capacity
multi-bucket client matching order
weighted-average execution
future preservation of observed liquidity
```

## 3. PAPER composition and provider-neutral results

Add:

```text
backend/paper/risk_evaluation.py
```

with the pure application operation:

```python
evaluate_paper_risk(
    strategy_decision: StrategyDecision,
    *,
    summary: OandaPracticeAccountSummarySnapshot,
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
    pricing: OandaPracticeEurUsdPricingObservation,
    config: RiskConfig,
    risk_service: RiskService | None = None,
) -> PaperRiskEvaluation
```

No:

```text
Settings
reader
HTTP client
database Session
repository
broker mutation
```

is accepted by this operation.

### Outcome contract

Freeze:

```python
class PaperRiskOutcome(StrEnum):
    APPROVED = "APPROVED"
    NO_ACTION = "NO_ACTION"
    DEFERRED_ENTRY_POLICY = "DEFERRED_ENTRY_POLICY"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    OBSERVATION_MISMATCH = "OBSERVATION_MISMATCH"
    ENTRY_STATE_BLOCKED = "ENTRY_STATE_BLOCKED"
    PRICING_REJECTED = "PRICING_REJECTED"
    PRE_FLIGHT_REJECTED = "PRE_FLIGHT_REJECTED"
    PRE_SUBMISSION_REJECTED = "PRE_SUBMISSION_REJECTED"
```

Expected immutable result:

```python
@dataclass(frozen=True, slots=True)
class PaperRiskEvaluation:
    outcome: PaperRiskOutcome
    strategy_decision: StrategyDecision
    trade_intent: TradeIntent | None
    pre_flight: RiskDecision | None
    pre_submission: RiskDecision | None
    provenance: PaperObservationProvenance | None
    pricing_evidence: PaperPricingEvidence | None
```

Evidence helper type names may vary, but the information/invariants below are frozen.

### Strategy action ordering

#### NO_ACTION

Return:

```text
NO_ACTION
```

without:

```text
TradeIntent
financial observation validation
Risk
pricing
```

#### CLOSE_POSITION / UPDATE_PROTECTION

Return:

```text
UNSUPPORTED_ACTION
```

without converting them into opening attempts.

#### PRICE_TRIGGERED opening

Return:

```text
DEFERRED_ENTRY_POLICY
```

without:

```text
TradeIntent
Risk
pricing selection
PendingEntryHandoff mutation
```

The initial PAPER vertical slice is IMMEDIATE-only.

#### IMMEDIATE opening

Map exactly:

```python
TradeIntent(
    action=decision.action,
    direction=decision.direction,
    stop=decision.stop.price,
    target=decision.target,
)
```

### Identity and observation coherence

Before projections or Risk require exact identity equality on:

```text
provider
environment
provider_account_id
base_currency
```

across all four observations.

Ignore alias.

Mismatch:

```text
IDENTITY_MISMATCH
```

Then require:

```text
summary.open_trade_count == len(trades.trades)
summary.open_position_count == len(positions.positions)
```

Failure:

```text
OBSERVATION_MISMATCH
```

This is a fail-closed coherence rule.

Matching counts do not establish atomicity.

Then require:

```text
summary.pending_order_count == 0
```

Otherwise:

```text
ENTRY_STATE_BLOCKED
```

No pending Order is cancelled or interpreted here.

### Existing projections

On coherent observations reuse exactly:

```python
project_oanda_practice_account_state(summary)
```

and:

```python
project_oanda_practice_eur_usd_exposure_state(
    trades,
    positions,
)
```

Do not reproduce either projection.

### PRE_FLIGHT

Construct the existing `TradeIntent`.

Invoke PRE_FLIGHT exactly once.

If rejected:

```text
PRE_FLIGHT_REJECTED
```

and stop before candidate PRE_SUBMISSION evaluations.

### Pricing checks

For PRE_FLIGHT-approved IMMEDIATE proposals require:

```text
pricing.price_time >= strategy_decision.decision_time
```

Then apply the OANDA pricing projection.

A non-tradeable, temporally invalid, empty-required-side, or no-positive-capacity pricing observation produces:

```text
PRICING_REJECTED
```

### Candidate PRE_SUBMISSION

For every positive-liquidity required-side candidate construct:

```python
ExecutablePrice(
    price=candidate.price,
    max_quantity=candidate.available_quantity,
)
```

Invoke the new quantity-aware Risk PRE_SUBMISSION method.

Do not calculate quantity outside Risk.

Retain candidate outcome evidence.

### Final candidate selection

Approved candidates satisfy Risk, including capacity.

Select:

```text
LONG  → highest approved ask
SHORT → lowest approved bid
```

independent of source order.

For equal prices select the smallest capacity.

If exact price/capacity candidates are duplicated, they are semantically equivalent.

No bucket aggregation is allowed.

### APPROVED invariant

Only:

```text
APPROVED
```

contains an approved top-level PRE_SUBMISSION decision.

Require:

```text
pre_submission.quantity is positive and integral

pre_submission.actual_risk
    <= pre_submission.risk_budget

pre_submission.entry_price
    == selected candidate price

pre_submission.quantity
    <= selected candidate available_quantity
```

The pre-submission entry and target are observation-time Risk references.

They are not confirmed Fill values.

### Failure with candidates but no survivor

If all valid candidates fail only capacity:

```text
PRICING_REJECTED
```

with candidate evidence showing insufficient single-bucket capacity.

If any candidate fails for a non-capacity generic Risk reason and no candidate is approved:

```text
PRE_SUBMISSION_REJECTED
```

Retain a deterministic representative generic RiskDecision plus the candidate evidence.

Use the most adverse non-capacity-rejected candidate; for equal price use smallest capacity.

Do not let source order choose the failure.

## 4. Identity, provenance, and observation limits

For an identity- and coherence-checked composition retain provider-neutral provenance containing at minimum:

```text
provider
environment
provider_account_id
base_currency
pricing price_time
summary last_transaction_id
Trades last_transaction_id
Positions last_transaction_id
```

Transaction IDs are evidence labels only.

They are not:

```text
compared
ordered
merged
treated as one transaction cursor
used to prove atomicity
used to prove freshness
```

`price_time` is the OANDA ClientPrice creation timestamp.

Require:

```text
price_time >= StrategyDecision.decision_time
```

but do not invent a maximum-age policy.

Current account/Trade/Position observation contracts do not expose comparable capture timestamps.

Therefore PAPER 03 explicitly does not prove:

```text
whole-account freshness
same-cycle acquisition
atomic broker state
reconciliation
restart safety
durable execution authority
```

### Count coherence

Summary counts provide an additional fail-closed consistency test:

```text
open_trade_count
open_position_count
```

must match the normalized inventory lengths.

A mismatch demonstrates temporal/observation disagreement.

Matching counts remain only consistency evidence, not atomicity proof.

### Pending orders

For the initial IMMEDIATE entry path:

```text
pending_order_count > 0
```

blocks the composition.

Detailed pending Order identity/type/reconciliation remains future work.

## 5. Examples and boundaries

Assume:

```text
NAV = 10000 USD
risk_per_trade = 0.01
LONG stop = 1.0950
risk budget = 100 USD
```

| Observation                                                                              | Required result                                                                                  |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| asks `(1.1000, 25000)`, `(1.1002, 20000)`                                                | Risk sizes 20,000 and 19,230 respectively; both fit; choose adverse `1.1002`, quantity `19,230`. |
| ask `(1.1002, 19230)`                                                                    | Exact capacity boundary; approve.                                                                |
| ask `(1.1002, 19229)`                                                                    | Candidate fails capacity; with no survivor, pricing rejected.                                    |
| asks `(1.1002, 19000)`, `(1.1000, 20000)`                                                | Adverse candidate fails capacity; supported `1.1000` survives and is selected.                   |
| asks `(1.1002, 10000)`, `(1.1003, 10000)` with Risk quantity above 10,000 at both prices | Reject; never sum buckets.                                                                       |
| LONG with asks populated and bids empty                                                  | Allowed to evaluate asks; opposite side is irrelevant.                                           |
| LONG with empty asks                                                                     | Pricing rejected.                                                                                |
| `tradeable=False`                                                                        | Pricing rejected.                                                                                |
| pricing `price_time < decision_time`                                                     | Pricing rejected.                                                                                |
| summary Trade count differs from Trade inventory length                                  | Observation mismatch; no Risk.                                                                   |
| summary Position count differs from Position inventory length                            | Observation mismatch; no Risk.                                                                   |
| summary pending-order count > 0                                                          | Entry state blocked; no Risk.                                                                    |
| same financial identity but different aliases                                            | Identity match.                                                                                  |
| different provider/environment/account/currency                                          | Identity mismatch.                                                                               |
| `NO_ACTION`                                                                              | Typed no-op; no observations/Risk.                                                               |
| `PRICE_TRIGGERED`                                                                        | Deferred entry policy; no pricing/Risk.                                                          |
| `CLOSE_POSITION` / `UPDATE_PROTECTION`                                                   | Unsupported action; no opening attempt.                                                          |

For SHORT, use bid-side candidates and select the lowest approved bid.

The architecture does not model:

```text
multi-bucket fill
weighted average fill
slippage after observation
broker latency
```

PAPER 04 must address the broker-side consequence of a price moving beyond the Risk-approved reference before/during mutation.

## 6. Historical compatibility and focused tests

Historical Experiment semantics remain unchanged.

`ExperimentRunner` continues to:

```text
derive slipped BID/ASK historical quote
        ↓
ExecutableQuote
        ↓
existing evaluate_pre_submission(...)
        ↓
SimulatedExecutionAdapter
        ↓
assert simulated Fill price == Risk entry price
```

No OANDA pricing buckets enter Experiment.

No Experiment contract becomes a PAPER contract.

Expected product-code changes are limited to:

```text
backend/risk/service.py
backend/risk/__init__.py

backend/integrations/oanda/pricing_projection.py
backend/integrations/oanda/__init__.py

backend/paper/risk_evaluation.py
backend/paper/__init__.py
```

plus focused tests.

`backend/experiments/runner.py` is expected to remain unchanged.

Required focused evidence:

### Risk

Preserve every legacy `ExecutableQuote` test.

Add:

```text
valid ExecutablePrice long/short
invalid price
invalid capacity
zero capacity
exact capacity
insufficient capacity
whole-unit quantity
actual_risk <= budget
target resolution
no approved quantity on rejection
```

### OANDA pricing projection

Cover:

```text
LONG asks only
SHORT bids only
empty opposite side
empty required side
tradeable false
zero-liquidity retention
positive candidate construction
source-order invariance
duplicate/equal-price capacities
no aggregation
closeout fields not consumed
```

### PAPER composition

Cover:

```text
NO_ACTION
unsupported actions
PRICE_TRIGGERED defer
exact opening TradeIntent mapping
identity mismatch
alias ignored
summary/inventory count mismatch
pending-order block
01G AccountState reuse
01H exposure-state reuse
PRE_FLIGHT rejection ordering
price_time before decision rejection
LONG candidate selection
SHORT candidate selection
capacity failures
generic PRE_SUBMISSION failures
provenance transaction IDs
approved invariant
no I/O/mutation
```

### Historical compatibility

Run existing Risk/Experiment evidence proving:

```text
historical quote path unchanged
simulated entry-price equality unchanged
candidate vertical flow unchanged when integration environment is available
```

## 7. Explicit deferrals

Deferred:

```text
same-cycle broker re-observation
MarketOrder instruction
priceBound policy
FOK versus IOC policy
OANDA mutation
broker Fill confirmation
post-fill Risk comparison
protective stop/take-profit instructions
PAPER persistence/accounting
pending Order ownership
reconciliation
restart-safe resume
runtime activation
scheduler
API/UI
LIVE
```

Also deferred from the initial end-to-end PAPER capability:

```text
PRICE_TRIGGERED Strategy execution
```

until Atlas separately proves:

```text
trigger ownership
pending Strategy state continuity
broker Order ownership
expiry semantics
reconciliation
```

The sole PAPER 03 invariant exported to later work is:

```text
At the supplied OANDA ClientPrice observation, the approved whole-unit
Risk quantity is no greater than one selected required-side PriceBucket's
stated liquidity, and Risk used that exact bucket price as its entry-price
reference.
```

This invariant is:

```text
observation-scoped
read-only
non-durable
```

It is not:

```text
a Fill prediction
a weighted-average execution model
a broker liquidity guarantee
an Order instruction
capital authorization
```

Any future broker mutation must re-establish safe state immediately before submission and ensure the broker instruction cannot silently exceed the Risk-approved price/risk boundary.

## Official OANDA sources consulted

- OANDA v20 Pricing Definitions
- OANDA v20 Pricing Common Definitions
- OANDA v20 Order Definitions
- OANDA v20 Pricing Endpoint documentation

These establish the provider facts used above and do not establish bucket ordering or a multi-bucket client fill algorithm.
