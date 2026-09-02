# PLAN — PAPER 03 Risk + Executable Pricing

## Workstream state

- **Workstream:** `paper-03-risk-executable-pricing`
- **Outcome:** Evaluate one supported current Strategy opening proposal against one identity- and observation-consistent set of normalized OANDA Practice account, exposure, and EUR/USD pricing facts through PRE_FLIGHT and quantity-aware PRE_SUBMISSION Risk, without broker mutation or durable execution authority.
- **Classification:** `Critical`. PAPER 03 establishes a new shared quantity-capacity invariant that later broker execution will depend upon. The existing two-sided historical `ExecutableQuote` cannot express one-sided provider liquidity or prove that a Risk-sized quantity is covered by the selected price.
- **Base:** `main` at `4f25a9e` (`Close PAPER 02 workstream`).
- **Base SHA:** `4f25a9e65c30eae14a78f22701addd9e2e2e9614`.
- **Branch:** `solo/paper-03-risk-executable-pricing`.
- **Phase:** `READY_FOR_USER`.
- **Approval:** explicit developer implementation approval granted; PLAN and ARCHITECTURE are canonical and frozen.
- **Architecture:** `FROZEN_PRE_APPROVAL`; `ARCHITECTURE.md` is canonical with this PLAN.
- **Task state:** T001, T002, and T003 are complete with BUILD receipts.
- **Next action:** stop for explicit developer merge approval; do not merge before approval.
- **Concerns:** OANDA documents price/liquidity buckets but does not document bucket array ordering or a client-visible multi-bucket aggregation/fill algorithm. PAPER 03 therefore uses a deliberately conservative single-bucket capacity rule. The resulting Risk approval is valid only for the supplied pricing observation and is not a broker Fill promise or durable mutation authority.

## 1. Capability boundary

The smallest coherent PAPER 03 operation is:

```text
supported StrategyDecision from PAPER 02
        +
normalized OANDA Practice account summary
        +
normalized OANDA open-Trade inventory
        +
normalized OANDA open-Position inventory
        +
normalized OANDA EUR/USD pricing observation
        +
explicit caller-supplied RiskConfig
        ↓
observation identity/coherence checks
        ↓
existing account + exposure projections
        ↓
provider-neutral TradeIntent
        ↓
Risk PRE_FLIGHT
        ↓
OANDA required-side price/liquidity candidates
        ↓
quantity-aware Risk PRE_SUBMISSION
        ↓
capital-incapable PaperRiskEvaluation
```

Strong expected application seam:

```text
backend/paper/risk_evaluation.py
```

Strong expected public operation:

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

The operation:

- accepts already-normalized immutable observations;
- performs no Settings/credential lookup;
- performs no HTTP;
- performs no database read/write;
- reuses the existing pure 01G and 01H projections;
- maps only supported opening Strategy proposals into Risk;
- returns a one-shot explanatory result;
- creates no Order or broker instruction.

An approved result means only:

> At the supplied OANDA pricing observation, one conservative required-side price bucket supported the quantity approved by Risk at that same price.

It does **not** mean:

```text
broker mutation is authorized
the observation is still current
the account state is atomic
the broker will fill at that price
the broker will preserve that liquidity
PAPER is activated
```

PAPER 04 must reacquire/revalidate the facts required for any future mutation.

## 2. Classification and capital boundary

This workstream is `Critical` because it changes the shared Risk capability surface in a way that future capital-capable PAPER execution will rely upon.

Current Risk knows only:

```python
ExecutableQuote(
    bid: Decimal,
    ask: Decimal,
)
```

That is sufficient for deterministic historical execution, where Experiment owns one known simulated executable price.

It is insufficient for current OANDA pricing because:

```text
LONG needs ask-side evidence only
SHORT needs bid-side evidence only

and

each OANDA price carries finite observed liquidity
```

The new shared semantic must prove:

```text
Risk-approved quantity <= observed capacity at the Risk entry price
```

without making Risk understand OANDA.

This Critical workstream still performs no broker mutation and creates no durable execution authority.

Explicitly prohibited:

```text
POST/PUT/DELETE OANDA order requests
market/stop/limit broker instructions
broker Fill confirmation
PAPER persistence
PAPER accounting
reconciliation/resume authority
runtime activation
API/UI
LIVE
```

## 3. Verified current contracts

### 3.1 Reusable Risk

Current `backend/risk/service.py` provides:

```python
RiskConfig(risk_per_trade)
AccountState(base_currency, equity)
ExecutableQuote(bid, ask)
TradeIntent(action, direction, stop, target)
RiskDecision(...)
RiskService.evaluate_pre_flight(...)
RiskService.evaluate_pre_submission(..., quote=ExecutableQuote)
```

PRE_FLIGHT already owns the existing financial checks for:

```text
supported EUR/USD/USD economics
known flat financial exposure
positive account equity
valid opening action/direction
valid stop/target
valid risk_per_trade
```

PRE_SUBMISSION currently:

```text
selects ask for LONG / bid for SHORT
        ↓
budget = equity × risk_per_trade
        ↓
loss_per_unit = abs(entry − stop)
        ↓
quantity = floor(budget / loss_per_unit)
        ↓
actual_risk = quantity × loss_per_unit
        ↓
target resolved from entry + stop
```

These calculations remain authoritative.

PAPER 03 must not duplicate them in the OANDA integration or PAPER application layer.

### 3.2 Shared Risk extension

Do **not** broaden the existing historical method into:

```python
evaluate_pre_submission(
    ...,
    quote: ExecutableQuote | ExecutablePrice,
)
```

unless implementation proves a separate method impossible.

Preferred frozen boundary:

```python
@dataclass(frozen=True, slots=True)
class ExecutablePrice:
    price: Decimal
    max_quantity: Decimal
```

and a new quantity-aware Risk entry point equivalent to:

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

The exact method spelling may be adjusted slightly during BUILD, but its semantics are frozen:

- the existing `evaluate_pre_submission(... quote=ExecutableQuote)` remains externally and semantically unchanged;
- both paths reuse one internal financial sizing implementation;
- `ExecutablePrice.price` is already the required-side entry-price fact;
- `max_quantity` is provider-neutral observed capacity;
- Risk verifies the resulting quantity does not exceed that capacity;
- Risk still owns budget, stop geometry, whole-unit quantity, actual risk, and target calculations.

Add only the generic rejection vocabulary required for this path:

```text
INVALID_EXECUTABLE_PRICE
INVALID_EXECUTABLE_CAPACITY
INSUFFICIENT_EXECUTABLE_CAPACITY
```

Semantics:

```text
invalid/non-positive/non-finite price
→ INVALID_EXECUTABLE_PRICE

negative/non-finite capacity
→ INVALID_EXECUTABLE_CAPACITY

valid capacity smaller than Risk-sized quantity
→ INSUFFICIENT_EXECUTABLE_CAPACITY
```

Zero capacity is a valid statement of no available capacity and therefore behaves as insufficient, not malformed.

Historical `ExecutableQuote` rejection behavior remains unchanged.

### 3.3 Strategy proposal → TradeIntent

Current opening `StrategyDecision` already contains:

```text
action
direction
decision_time
stop
target
entry_policy
```

For supported immediate openings:

```text
OPEN_LONG
→ TradeIntent(
    action=OPEN_LONG,
    direction=LONG,
    stop=decision.stop.price,
    target=decision.target,
)

OPEN_SHORT
→ TradeIntent(
    action=OPEN_SHORT,
    direction=SHORT,
    stop=decision.stop.price,
    target=decision.target,
)
```

Do not use historical `TradeIntentModel`.

Do not create a new PAPER TradeIntent contract.

For:

```text
NO_ACTION
```

return a typed no-op with no TradeIntent and no Risk calls.

For:

```text
CLOSE_POSITION
UPDATE_PROTECTION
```

return an explicit unsupported-action outcome.

### 3.4 PAPER entry-policy boundary

PAPER 02 can return:

```text
IMMEDIATE
PRICE_TRIGGERED
```

PAPER 03 supports only:

```text
IMMEDIATE
```

for the initial PAPER execution vertical slice.

A `PRICE_TRIGGERED` opening returns an explicit deferred-policy result and performs:

```text
no TradeIntent
no PRE_FLIGHT
no pricing selection
no PRE_SUBMISSION
no pending-state mutation
```

Do not poll point pricing to guess whether a Strategy trigger fired.

Do not advance:

```text
PendingEntryHandoff.consumed_count
```

Do not expire or clear a handoff.

Do not commit PAPER 04 to a specific STOP-order implementation yet.

PRICE_TRIGGERED PAPER support requires a separately approved trigger/order/state-continuity design and remains outside the initial IMMEDIATE PAPER capability.

### 3.5 Existing OANDA observations and projections

Reuse exactly:

```text
OandaPracticeAccountSummarySnapshot
OandaPracticeOpenTradeInventory
OandaPracticeOpenPositionInventory
OandaPracticeEurUsdPricingObservation
```

Reuse exactly:

```python
project_oanda_practice_account_state(summary)
```

which remains:

```text
base_currency = summary.identity.base_currency
equity = summary.nav
```

Do not switch to:

```text
balance
margin_available
recomputed NAV
```

Reuse exactly:

```python
project_oanda_practice_eur_usd_exposure_state(
    trades,
    positions,
)
```

Do not:

```text
construct Atlas Position
net opposing exposure
derive average entry
derive opened_at
```

## 4. Account identity and observation truth

### 4.1 Financial identity

For an IMMEDIATE opening, all supplied financial/provider observations must refer to the same validated account.

Compare exactly:

```text
provider
environment
provider_account_id
base_currency
```

across:

```text
summary.identity
trades.identity
positions.identity
pricing.identity
```

Alias is descriptive and ignored.

Identity mismatch fails closed before projections or Risk.

### 4.2 Cross-observation count coherence

The account summary already carries:

```text
open_trade_count
open_position_count
pending_order_count
```

Before projecting exposure, require:

```text
summary.open_trade_count == len(trades.trades)
summary.open_position_count == len(positions.positions)
```

A mismatch does **not** prove which observation is wrong.

It proves only that the independently acquired observations do not describe one sufficiently coherent state for this Risk calculation.

Return an explicit observation-mismatch outcome.

Do not attempt to repair or prefer one observation.

Matching counts do not prove atomicity.

### 4.3 Pending-order entry gate

For the first supported IMMEDIATE opening capability require:

```text
summary.pending_order_count == 0
```

If the summary reports any pending broker Order, return an explicit entry-state-blocked outcome before Risk.

Do not assume the Order is harmless.

Do not inspect or cancel it here.

Detailed pending-order ownership/reconciliation remains deferred.

This is orchestration eligibility, not a new generic Risk policy.

### 4.4 Transaction IDs

Retain:

```text
summary.last_transaction_id
trades.last_transaction_id
positions.last_transaction_id
```

as evidence only.

Do not:

```text
require equality
order them
treat them as one atomic cursor
claim reconciliation
claim same-snapshot semantics
```

### 4.5 Pricing temporal ordering

For an IMMEDIATE opening, require:

```text
pricing.price_time >= strategy_decision.decision_time
```

A pricing observation older than the Strategy decision cannot be used as that decision's executable-price evidence.

Reject it as pricing-unusable.

Do not invent a maximum-age threshold in PAPER 03.

Current contracts do not provide comparable observation timestamps for the summary, Trade inventory, or Position inventory.

Therefore PAPER 03 still does **not** claim whole-account freshness.

PAPER 04 must reacquire/revalidate before mutation.

## 5. Official OANDA semantics relied upon

The approved design relies only on these documented provider facts.

### ClientPrice

OANDA documents:

```text
time
→ date/time the Price was created

tradeable
→ whether the Price is tradeable

bids
→ prices and liquidity available on the bid side

asks
→ prices and liquidity available on the ask side
```

Bid and ask arrays may independently be empty.

Therefore:

```text
LONG requires ask-side evidence
SHORT requires bid-side evidence
```

An empty opposite side does not by itself invalidate the required side.

### PriceBucket

OANDA defines a PriceBucket as:

```text
one price
+
one amount of liquidity available at that price
```

PAPER 03 may therefore treat each individual bucket as one finite candidate price/capacity fact.

### Closeout prices

OANDA explicitly documents that:

```text
closeoutBid
closeoutAsk
```

are used for closing when ordinary side liquidity is unavailable and are never used to open a new position.

PAPER 03 must never use them as entry-price fallbacks.

### Market Order facts

OANDA documents Market Orders as immediate current-market orders and exposes:

```text
units
timeInForce = FOK or IOC
priceBound = worst price client accepts
```

Those facts inform the future broker boundary.

They do **not** authorize any Order construction in PAPER 03.

### Not documented

The official docs do not establish for Atlas:

```text
bucket array order is best-to-worst
bucket array order is worst-to-best
multiple buckets are cumulatively available
the exact matching order between buckets
a client-side weighted-average fill formula
a later market order will preserve the observed buckets
```

Do not infer any of these.

## 6. Quantity-aware executable-pricing decision

### 6.1 Provider-specific candidate projection

Add a pure OANDA pricing projection seam, strongly:

```text
backend/integrations/oanda/pricing_projection.py
```

It accepts:

```text
normalized OANDA pricing observation
+
Direction
```

and performs no network I/O.

For:

```text
LONG
```

inspect only asks.

For:

```text
SHORT
```

inspect only bids.

The projection must preserve the normalized provider facts needed for evidence and produce a finite set of required-side candidate facts:

```text
price
available_quantity
```

Do not choose a final candidate in the provider projection.

Risk quantity must participate in final selection.

### 6.2 Provider-pricing rejection

Before candidate evaluation:

```text
tradeable == False
→ pricing rejected

required side empty
→ pricing rejected

required side contains no positive-liquidity bucket
→ pricing rejected
```

Zero-liquidity buckets remain evidence but are not executable candidates.

Do not use:

```text
opposite side
closeout price
midpoint
historical candle
first bucket
array order
```

as fallback.

### 6.3 Single-bucket capacity rule

No buckets are aggregated.

Each candidate means only:

> This source bucket reported this price with this amount of liquidity.

For each positive-liquidity candidate, PAPER constructs:

```python
ExecutablePrice(
    price=candidate.price,
    max_quantity=candidate.available_quantity,
)
```

and asks Risk to size at that candidate's price.

A candidate survives only if Risk approves and:

```text
Risk quantity <= candidate available_quantity
```

Because capacity enforcement belongs to the new generic Risk path, PAPER must not independently recalculate Risk quantity.

### 6.4 Circular price/quantity dependency

Resolve:

```text
entry price affects quantity
quantity must fit observed liquidity
```

using the finite candidate set.

Algorithm:

```text
for each required-side positive-liquidity bucket:
    evaluate PRE_SUBMISSION through Risk
    at that bucket's own price/capacity

retain approved candidates

if approved candidates exist:
    choose the most adverse approved candidate
```

For LONG:

```text
highest approved ask
```

For SHORT:

```text
lowest approved bid
```

This selection is independent of source array order.

If equal prices survive, choose the candidate with the smallest available quantity as the conservative deterministic tie-breaker.

Exact duplicate:

```text
price + capacity
```

candidates are semantically equivalent.

No unbounded iteration or fixed-point approximation is permitted.

### 6.5 Why adverse supported selection

The selected entry-price reference should not assume the most favorable observed price will remain executable.

Among individually capacity-supported candidates, Atlas uses the price producing the more adverse opening geometry:

```text
higher ask for LONG
lower bid for SHORT
```

This is a conservative Risk reference.

It is still **not** a predicted Fill price.

### 6.6 No supported candidate

If no candidate produces an approved capacity-covered Risk decision:

- if candidates fail only because their observed capacity is insufficient, return a provider-pricing/capacity rejection;
- if one or more candidates fail for another generic PRE_SUBMISSION Risk reason, preserve a deterministic representative Risk rejection and classify the result as PRE_SUBMISSION rejected;
- retain per-candidate evidence so the final explanation does not hide why other candidates failed.

Do not invent an executable quote.

## 7. PRE_FLIGHT and PRE_SUBMISSION result

Freeze a small immutable PAPER composition result.

Expected outcome vocabulary:

```text
APPROVED
NO_ACTION
DEFERRED_ENTRY_POLICY
UNSUPPORTED_ACTION
IDENTITY_MISMATCH
OBSERVATION_MISMATCH
ENTRY_STATE_BLOCKED
PRICING_REJECTED
PRE_FLIGHT_REJECTED
PRE_SUBMISSION_REJECTED
```

Strong expected result shape:

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

Exact evidence helper names may vary slightly.

### Result rules

#### NO_ACTION

```text
no TradeIntent
no financial-observation validation
no Risk calls
no pricing
```

#### DEFERRED_ENTRY_POLICY

For opening `PRICE_TRIGGERED`:

```text
no TradeIntent
no Risk calls
no pricing resolution
no pending-state mutation
```

#### UNSUPPORTED_ACTION

For:

```text
CLOSE_POSITION
UPDATE_PROTECTION
```

do not manufacture an opening attempt.

#### IMMEDIATE opening

Order:

```text
validate financial identity
        ↓
validate summary/inventory count coherence
        ↓
require pending_order_count == 0
        ↓
reuse 01G AccountState projection
        ↓
reuse 01H FinancialPositionState projection
        ↓
create TradeIntent
        ↓
PRE_FLIGHT once
        ↓
if approved, validate pricing temporal/provider facts
        ↓
evaluate finite executable candidates through Risk
        ↓
select adverse approved candidate
        ↓
APPROVED or explicit rejection
```

### APPROVED invariant

Only an `APPROVED` result contains an approved PRE_SUBMISSION RiskDecision.

It must satisfy:

```text
quantity is positive whole-unit Decimal
actual_risk <= risk_budget

selected price
    == pre_submission.entry_price

pre_submission.quantity
    <= selected observed bucket capacity
```

The resulting:

```text
entry_price
target_price
```

are observation-time pre-submission references.

They are not confirmed broker execution prices.

## 8. RiskConfig ownership

The caller supplies:

```python
RiskConfig(risk_per_trade=...)
```

PAPER 03 does not add:

```text
Risk policy persistence
default policy selection
settings UI
runtime policy mutation
account-specific policy administration
```

Changing Risk policy remains trader-controlled.

Current Risk uses:

```text
AccountState.equity = OANDA summary NAV
```

PAPER 03 does not reopen that decision.

## 9. Shared Risk and Experiment compatibility

Historical Experiment behavior must remain unchanged.

Current Experiment:

```text
historical M1 BID/ASK observation
        ↓
simulated adverse slippage
        ↓
ExecutableQuote
        ↓
Risk evaluate_pre_submission(...)
        ↓
SimulatedExecutionAdapter
        ↓
fill.execution_price == Risk entry_price
```

Preserve this path exactly in meaning.

Preferred implementation:

```text
existing evaluate_pre_submission(... ExecutableQuote ...)
→ unchanged public historical path

new evaluate_pre_submission_at_executable_price(...)
→ PAPER quantity-capacity path

both
→ shared private financial sizing implementation
```

Experiment must not consume:

```text
OANDA PriceBucket
tradeable
price_time
capacity-bearing current pricing
```

Do not modify:

```text
historical ExecutionObservation
historical Order
historical Fill
SimulatedExecutionAdapter
SimulationClock
```

to make PAPER work.

`ExperimentRunner` is expected to require **no product-code change**.

If implementing PAPER 03 requires changing historical Experiment methodology rather than merely sharing internal Risk calculation code, stop `BLOCKED`.

## 10. Reuse versus exclusion

### Reuse

```text
StrategyDecision
Action
Direction
EntryPolicy
RiskConfig
AccountState
TradeIntent
RiskDecision
RiskService
ExecutableQuote historical path
OandaPracticeAccountSummarySnapshot
OandaPracticeOpenTradeInventory
OandaPracticeOpenPositionInventory
OandaPracticeEurUsdPricingObservation
OandaPracticePriceBucket
project_oanda_practice_account_state(...)
project_oanda_practice_eur_usd_exposure_state(...)
FinancialPositionState
```

### New bounded contracts

Expected:

```text
ExecutablePrice
quantity-aware Risk PRE_SUBMISSION entry point
OANDA executable-pricing projection/candidate facts
PaperRiskEvaluation
PaperRiskOutcome
small provenance/pricing evidence values
```

### Keep out of PAPER 03

```text
Settings/readers/HTTP inside PAPER composition
Atlas financial Position construction
ExperimentRunner changes in methodology
SimulationClock
historical execution contracts
SimulatedExecutionAdapter
PAPER persistence
broker instruction/payload
broker Fill
protection orders
reconciliation/resume
runtime activation
API/UI
LIVE
```

## 11. Expected task decomposition after approval

Do not create task files before explicit Critical approval.

Expected chain:

### T001 — quantity-aware shared Risk seam

Implement:

```text
ExecutablePrice
new quantity-capacity PRE_SUBMISSION method
shared internal sizing calculation
new generic rejection vocabulary
legacy ExecutableQuote compatibility
```

Prove existing Risk and historical Experiment semantics remain unchanged.

### T002 — OANDA executable-pricing projection

Implement the pure OANDA required-side candidate projection and evidence.

Cover:

```text
tradeable
independently empty sides
zero liquidity
all buckets retained as evidence
no aggregation
no array-order assumption
```

No Risk calculation in the integration module.

### T003 — PAPER Risk composition

Implement:

```text
StrategyDecision
→ eligibility/observation checks
→ 01G + 01H projections
→ TradeIntent
→ PRE_FLIGHT
→ candidate Risk evaluations
→ conservative selected PRE_SUBMISSION
→ PaperRiskEvaluation
```

No broker mutation.

Do not split tests into a separate task.

If implementation proves T001/T002 can safely be combined without losing ownership clarity, that is allowed.

## 12. Acceptance criteria

1. PAPER 03 performs no I/O or broker mutation.

2. `NO_ACTION` returns a typed no-op without consuming financial observations or invoking Risk.

3. `CLOSE_POSITION` and `UPDATE_PROTECTION` are explicitly unsupported by this opening-only capability.

4. `PRICE_TRIGGERED` opening proposals are explicitly deferred and do not invoke Risk or pricing.

5. Only `IMMEDIATE` `OPEN_LONG` / `OPEN_SHORT` proposals enter the Risk path.

6. Supported Strategy opening decisions map exactly into existing provider-neutral `TradeIntent`.

7. All four OANDA observations must match on provider, environment, provider account ID, and base currency.

8. Alias differences alone do not fail identity.

9. Identity mismatch fails before projections or Risk.

10. `summary.open_trade_count` must exactly equal `len(trades.trades)`.

11. `summary.open_position_count` must exactly equal `len(positions.positions)`.

12. Count mismatch fails closed as observation inconsistency and does not claim which observation is authoritative.

13. Matching counts do not claim atomicity.

14. `summary.pending_order_count` must be zero for this initial IMMEDIATE entry capability.

15. Existing pending Orders block entry composition before Risk without being cancelled or reinterpreted.

16. Transaction IDs are retained as evidence but never compared as an atomic cursor.

17. Existing 01G account projection is reused exactly; NAV remains Risk equity.

18. Existing 01H exposure projection is reused exactly.

19. No Atlas financial `Position` is constructed.

20. PRE_FLIGHT remains Risk-authoritative and is called exactly once for an eligible IMMEDIATE opening.

21. PRE_FLIGHT rejection stops before executable-pricing candidate evaluation.

22. `pricing.price_time` must not precede the Strategy decision time.

23. `tradeable=False` cannot produce executable-price approval.

24. LONG uses asks only; SHORT uses bids only.

25. Empty opposite-side liquidity does not invalidate a populated required side.

26. Empty required side fails closed.

27. No closeout price, midpoint, historical candle, opposite side, first bucket, or source-order assumption is used.

28. Every required-side source bucket is preserved in evidence.

29. Zero-liquidity buckets are retained as evidence but are not executable candidates.

30. Buckets are never aggregated.

31. Each candidate is evaluated at its own observed price and own observed capacity.

32. Risk remains authoritative for stop geometry, risk budget, whole-unit quantity, actual risk, and target.

33. No candidate can be approved when:

    ```text
    Risk quantity > candidate capacity
    ```

34. The new quantity-aware Risk path does not import or interpret OANDA.

35. The existing historical `ExecutableQuote` method remains semantically unchanged.

36. If multiple candidates are approved, selection is independent of source array order.

37. LONG selects the highest approved ask.

38. SHORT selects the lowest approved bid.

39. Equal-price approved candidates use smallest capacity as deterministic conservative tie-breaker.

40. No unbounded fixed-point or iterative approximation is introduced.

41. Only `APPROVED` contains an approved PRE_SUBMISSION RiskDecision and selected candidate.

42. Approved quantity is positive/integral and satisfies:

    ```text
    actual_risk <= risk_budget
    quantity <= selected capacity
    ```

43. Selected candidate price exactly equals PRE_SUBMISSION `entry_price`.

44. PRE_SUBMISSION price/target are explicitly observation-time references, not Fill facts.

45. PAPER result retains account/pricing provenance without claiming freshness, reconciliation, atomicity, or durable execution authority.

46. Existing historical Experiment execution still uses `ExecutableQuote` and deterministic simulated Fill equality.

47. No Risk policy administration, persistence, accounting, runtime, API/UI, LIVE, or broker instruction is introduced.

## 13. Focused validation

Expected focused suite:

```bash
uv run pytest \
  backend/tests/risk/test_service.py \
  backend/tests/integrations/test_oanda_pricing.py \
  backend/tests/integrations/test_oanda_risk_projection.py \
  backend/tests/integrations/test_oanda_exposure_projection.py \
  backend/tests/paper/test_strategy_evaluation.py \
  backend/tests/paper/test_risk_evaluation.py \
  backend/tests/experiments/test_runner_diagnostics.py
```

If the existing candidate vertical-flow integration environment is available and the shared Risk implementation changed:

```bash
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> \
uv run pytest -m integration \
  backend/tests/integration/test_candidate_vertical_flow.py
```

Do not make a DB integration test mandatory merely because PAPER 03 exists.

Include it when needed to prove the actual shared Risk diff did not change the historical persisted vertical flow.

Targeted quality gates:

```bash
uv run ruff format --check <changed backend files>
uv run ruff check <changed backend files>
uv run pyright <changed backend files>
git diff --check
```

No credentialed OANDA or broker mutation check is required.

Do not run by default:

```text
full backend matrix
full database matrix
frontend
browser
runtime
migrations
```

Broaden only if the actual diff demonstrates wider blast radius.

## 14. Explicit deferrals

Deferred to PAPER 04 or later:

```text
same-cycle broker re-observation
broker instruction contract
OANDA MarketOrder payload
priceBound policy
FOK versus IOC choice
broker mutation
broker Fill confirmation
actual-fill risk/protection reconciliation
stop-loss/take-profit broker protection
PAPER persistence/accounting
pending-order ownership/reconciliation
restart-safe state
runtime activation
scheduler
API/UI
LIVE
```

PRICE_TRIGGERED Strategy execution is also deferred from the initial IMMEDIATE PAPER vertical slice until Atlas explicitly proves:

```text
trigger semantics
pending state continuity
broker/order ownership
expiry behavior
reconciliation
```

The sole PAPER 03 quantity-aware invariant is:

```text
At the supplied pricing observation, the Risk-approved quantity is no
greater than one explicitly selected required-side PriceBucket's stated
liquidity at the exact price used by Risk.
```

This is not:

```text
a weighted-average execution model
a fill promise
a broker-liquidity guarantee
a durable Order authorization
```

## 15. Critical approval gate

Current lifecycle:

```text
PLAN
→ ARCHITECTURE
→ reconcile PLAN + ARCHITECTURE
→ DEVELOPER_APPROVAL
```

Before explicit developer implementation approval, do not:

```text
GIT START
create branch
create tasks/
create T001/T002/T003
BUILD
VALIDATE
REVIEW
modify application code
modify tests
add persistence/migrations/runtime/API/UI
perform OANDA mutation
```

The current state is:

```text
Phase: DEVELOPER_APPROVAL
Approval: waiting for explicit developer implementation approval
```
