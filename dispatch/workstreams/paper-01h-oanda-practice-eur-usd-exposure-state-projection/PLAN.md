# PLAN — PAPER 01H OANDA Practice EUR/USD Exposure-State Projection

## Workstream state

- **Workstream:** `paper-01h-oanda-practice-eur-usd-exposure-state-projection`
- **Outcome:** Project already-normalized OANDA Practice open-Trade and open-Position inventories into one provider-neutral EUR/USD `FinancialPositionState` when the two provider views support one unambiguous Atlas exposure state.
- **Classification:** `Feature`.
- **Base:** `main` at `64536b4` (`Close PAPER 01G workstream`).
- **Base SHA:** `64536b433dbd17b55976f0ad16137ca9b8a8e5de`.
- **Branch:** `solo/paper-01h-oanda-practice-eur-usd-exposure-state-projection`.
- **Phase:** `READY_FOR_USER`.
- **Approval:** developer implementation approval granted; GIT START complete.
- **Architecture:** not required. PAPER Readiness 01 already established that OANDA Position facts must not be cast directly into Atlas `Position`. Current contracts support a narrower state-only projection without changing Risk or the trading domain.
- **Task state:** `T001` is `DONE`.
- **Next action:** stop for explicit developer merge approval; do not merge without it.
- **Concerns:** `/openTrades` and `/openPositions` are independent provider observations rather than one atomic snapshot. This Feature proves only whether their retained exposure facts agree sufficiently to produce one state. It does not establish freshness, atomicity, reconciliation, or authority.

## Objective

Implement one pure deterministic projection:

```text
OandaPracticeOpenTradeInventory
                +
OandaPracticeOpenPositionInventory
                ↓
      cross-view consistency
                ↓
FinancialPositionState
```

Successful results are limited to:

```text
FLAT
LONG
SHORT
```

The projection must fail closed when valid provider observations cannot produce one supported Atlas state.

It must not construct a full Atlas `Position`.

## Why this slice exists

PAPER 01G established the account-side Risk projection:

```text
OANDA account summary
        ↓
AccountState
```

Risk pre-flight also needs financial exposure state.

Current `RiskService` already accepts:

```python
FinancialPositionState
```

directly.

Therefore the smallest next bridge is:

```text
OANDA Trade + Position observations
        ↓
FinancialPositionState
```

rather than:

```text
OANDA Position
        ↓
Atlas Position
```

A full Atlas `Position` requires:

```text
quantity
average_entry_price
opened_at
```

The current provider observations do not establish one approved canonical rule for all three:

- an OANDA Position may contain separate long and short sides;
- multiple OANDA Trades may contribute to one instrument Position;
- Position sides do not contain an opening timestamp;
- Trade opening times do not automatically define the opening time of aggregate exposure;
- no approved weighted-average or Trade-selection rule exists.

01H therefore projects state only.

## Verified current contracts

### Open Trade inventory

The existing:

```python
OandaPracticeOpenTradeInventory
```

contains:

```text
identity
trades
last_transaction_id
```

Each:

```python
OandaPracticeOpenTrade
```

retains:

```text
provider_trade_id
provider_instrument
open_time
open_price
current_units
state
unrealized_pl
```

Relevant invariants:

- Trade IDs are unique;
- `current_units` is a finite nonzero signed `Decimal`;
- positive units represent provider long exposure;
- negative units represent provider short exposure;
- state is `OPEN` or `CLOSE_WHEN_TRADEABLE`;
- multiple Trades may share one instrument;
- unsupported provider instruments are preserved rather than filtered.

### Open Position inventory

The existing:

```python
OandaPracticeOpenPositionInventory
```

contains:

```text
identity
positions
last_transaction_id
```

Each:

```python
OandaPracticeOpenPosition
```

contains:

```text
provider_instrument
unrealized_pl
long
short
```

with side facts:

```text
units
average_price
unrealized_pl
```

Relevant invariants:

```text
long.units  >= 0
short.units <= 0
```

Additionally:

- at least one Position side is exposed;
- both long and short sides may be nonzero;
- exposed sides require an average price;
- duplicate instrument Positions are rejected;
- unsupported provider instruments are retained.

### Atlas target

Current:

```python
FinancialPositionState
```

contains:

```text
FLAT
LONG
SHORT
```

Risk already accepts this enum directly.

No Risk or trading-domain contract change is required.

## Frozen projection contract

Strong expected module:

```text
backend/integrations/oanda/exposure_projection.py
```

Strong expected function:

```python
def project_oanda_practice_eur_usd_exposure_state(
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
) -> FinancialPositionState:
    ...
```

The function:

- accepts already-normalized immutable observations;
- performs no I/O;
- performs no Risk evaluation;
- performs no second normalization pass;
- performs no persistence;
- performs no provider request;
- performs no reconciliation beyond the explicit cross-view consistency rules below.

## Projection failure contract

Add one narrow integration-local exception:

```python
class OandaExposureProjectionError(OandaError):
    """Valid OANDA observations cannot produce one supported Atlas exposure state."""
```

Use it when the source observations are individually valid but cannot safely produce one supported Atlas state.

Examples include:

- account mismatch;
- unsupported instrument exposure;
- missing counterpart exposure;
- opposing Trade directions;
- dual-sided Position exposure;
- Trade/Position direction mismatch;
- exact unit mismatch.

Do not raise:

```text
OandaOpenTradeNormalizationError
OandaOpenPositionNormalizationError
```

for these cases.

Those errors belong to provider-response normalization.

Projection-error messages must remain sanitized and must not include raw provider payloads, credentials, or secrets.

Export the function and exception through `backend.integrations.oanda` according to current package convention.

## Account identity rule

The two observations must represent the same validated Practice account.

Compare the financial identity fields:

```text
provider
environment
provider_account_id
base_currency
```

These must match exactly.

Do **not** require aliases to match.

`alias` is provider account metadata and may change independently; it is not account ownership, financial state, transaction-frontier, or reconciliation authority.

Therefore do not use whole-dataclass equality if that would make alias differences fail the projection.

If any financial identity field differs, fail closed.

## Supported instrument rule

Current validated financial scope remains:

```text
EUR_USD
```

Every retained Trade and Position must therefore use:

```text
provider_instrument == "EUR_USD"
```

If either inventory contains any other exposed provider instrument, fail closed.

Examples:

```text
USD_CAD Trade
→ projection error
```

```text
XAU_USD Position
→ projection error
```

Do not silently remove unsupported exposure and continue projecting EUR/USD.

An account containing unsupported open exposure is outside Atlas's currently validated financial-state scope.

## FLAT semantics

Return:

```python
FinancialPositionState.FLAT
```

only when both inventories are empty:

```text
trades.trades == ()
positions.positions == ()
```

Examples:

```text
no Trades
no Positions
→ FLAT
```

```text
EUR_USD Trade exists
no Position
→ projection error
```

```text
no Trades
EUR_USD Position exists
→ projection error
```

Do not trust one provider view over the other.

## LONG semantics

Return:

```python
FinancialPositionState.LONG
```

only when all of these are true:

1. account financial identity matches;

2. all exposure is EUR/USD;

3. at least one EUR/USD Trade exists;

4. every Trade has:

   ```text
   current_units > 0
   ```

5. exactly one EUR/USD Position exists;

6. that Position has:

   ```text
   long.units > 0
   short.units == 0
   ```

7. the exact signed sum of Trade `current_units` equals `position.long.units`.

Example:

```text
Trades:
  +60
  +40

Position:
  long.units  = +100
  short.units = 0

→ LONG
```

Use exact `Decimal` equality.

Do not round or apply tolerance.

## SHORT semantics

Return:

```python
FinancialPositionState.SHORT
```

only when all of these are true:

1. account financial identity matches;

2. all exposure is EUR/USD;

3. at least one EUR/USD Trade exists;

4. every Trade has:

   ```text
   current_units < 0
   ```

5. exactly one EUR/USD Position exists;

6. that Position has:

   ```text
   long.units == 0
   short.units < 0
   ```

7. the exact signed sum of Trade `current_units` equals `position.short.units`.

Example:

```text
Trades:
  -60
  -40

Position:
  long.units  = 0
  short.units = -100

→ SHORT
```

Keep the comparison signed.

Do not convert to absolute values.

## Multiple same-direction Trades

Multiple EUR/USD Trades may contribute to one Position.

Same-direction Trade units may therefore be summed exactly.

Allowed:

```text
+60
+40
→ compare +100 with Position long.units
```

and:

```text
-60
-40
→ compare -100 with Position short.units
```

This aggregation is used only to prove exposure-state agreement.

It does not create:

```text
Atlas quantity
weighted average entry
opened_at
Trade ownership
```

## Opposing Trade directions

If the Trade inventory contains both:

```text
current_units > 0
```

and:

```text
current_units < 0
```

fail closed.

Do not net opposing Trades.

Example:

```text
+100
-40
```

must not become:

```text
LONG
```

simply because the arithmetic net is positive.

The current Atlas state model does not represent simultaneous opposing Trade exposure.

## Dual-sided Position exposure

If an EUR/USD Position has:

```text
long.units > 0
AND
short.units < 0
```

fail closed.

Do not:

- net the sides;
- choose the larger side;
- return LONG;
- return SHORT.

Example:

```text
long.units  = +100
short.units = -40
```

must not become:

```text
LONG 60
```

or:

```text
LONG
```

The provider observation is valid, but it cannot be represented by the current Atlas `FinancialPositionState`.

## Trade / Position disagreement

Any disagreement between the two views fails closed.

Examples:

```text
Trade exists / Position missing
Position exists / Trade missing
positive Trades / short-only Position
negative Trades / long-only Position
Trade-unit total != corresponding Position-side units
```

Do not:

- repair;
- net;
- prefer one view;
- infer missing exposure;
- return a partial state.

## `CLOSE_WHEN_TRADEABLE`

A Trade with:

```text
state == "CLOSE_WHEN_TRADEABLE"
```

still has nonzero current units and therefore still represents current exposure.

It participates in direction and unit agreement exactly like:

```text
OPEN
```

Do not treat it as:

```text
FLAT
closed
pending Order
```

Changing a Trade between the two supported open states while keeping its current units unchanged must not change the resulting exposure state.

## Transaction IDs

Both inventories independently retain:

```text
last_transaction_id
```

01H does not use them to decide exposure state.

Do not require:

```text
trades.last_transaction_id == positions.last_transaction_id
```

Different IDs may still accompany matching retained exposure facts.

Equal IDs also do not prove:

```text
atomicity
freshness
reconciliation
authorization
```

Transaction cursors remain provenance facts.

Temporal reconciliation and recovery belong to a later workstream.

## Fields intentionally ignored

The exposure result depends only on:

```text
account financial identity
provider instrument
Trade current_units
Position long.units
Position short.units
```

The following do not determine `FLAT | LONG | SHORT`:

### Trade

```text
provider_trade_id
open_time
open_price
unrealized_pl
last_transaction_id
```

Supported `state` values both count as exposure.

### Position

```text
average_price
unrealized_pl
last_transaction_id
```

Do not:

- compare Trade open price with Position average price;
- calculate weighted average entry;
- compare P/L;
- derive an opening time;
- derive reconciliation from cursor equality.

## No Atlas Position construction

Do not construct:

```python
Position
```

Do not project or invent:

```text
quantity
average_entry_price
opened_at
```

The only output is:

```python
FinancialPositionState
```

A broker-backed full Position projection remains deferred.

## No Risk evaluation

Do not call:

```text
RiskService.evaluate_pre_flight
RiskService.evaluate_pre_submission
```

This Feature produces one provider-neutral financial fact that Risk can consume later.

It does not decide whether new exposure may be created.

Do not add lifecycle or authority flags such as:

```text
authorized
eligible
paper_active
reconciled
runtime_ready
```

## No network behavior

The function accepts already-created normalized inventories.

Do not:

- accept `Settings`;
- read credentials;
- construct OANDA readers;
- call `/openTrades`;
- call `/openPositions`;
- call `/summary`;
- perform any HTTP request;
- perform filesystem or other I/O.

PAPER 01C and 01D own provider observation.

01H owns only projection.

## No duplicate normalization

Do not re-parse or re-normalize:

```text
Trade IDs
provider instruments
timestamps
prices
units
Position sides
transaction IDs
```

The source dataclasses already own those invariants.

01H validates only:

```text
supported Atlas scope
+
cross-view consistency
```

## Pending Orders remain separate

Do not consume:

```python
OandaPracticePendingOrderInventory
```

Pending Orders are not current financial exposure.

They may later affect activation, reconciliation, or duplicate-entry prevention, but they do not determine `FinancialPositionState` in this slice.

## Expected implementation scope

Expected product files:

```text
backend/integrations/oanda/exposure_projection.py
backend/integrations/oanda/__init__.py
```

Expected focused test file:

```text
backend/tests/integrations/test_oanda_exposure_projection.py
```

Expected unchanged:

```text
backend/domain/trading.py
backend/risk/service.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/risk_projection.py
backend/integrations/oanda/orders.py
backend/integrations/oanda/pricing.py
backend/integrations/oanda/account.py
backend/execution/
backend/persistence/
backend/runtime/
backend/strategies/
frontend/
migrations/
```

If implementation requires changing:

```text
FinancialPositionState
Position
RiskService
OANDA Trade normalization
OANDA Position normalization
persistence
execution
runtime
```

stop `BLOCKED` for re-scope rather than widening the Feature.

## Acceptance criteria

1. The projection accepts one normalized Trade inventory and one normalized Position inventory.

2. The projection returns exactly `FinancialPositionState`.

3. Matching empty inventories return `FLAT`.

4. Trade exposure with no Position fails closed.

5. Position exposure with no Trade fails closed.

6. Matching positive EUR/USD exposure returns `LONG`.

7. Matching negative EUR/USD exposure returns `SHORT`.

8. Multiple same-direction Trades may be summed exactly for cross-view comparison.

9. Trade current-unit totals must exactly equal the corresponding Position-side units.

10. Opposing Trade directions fail closed without netting.

11. Dual-sided Position exposure fails closed without netting.

12. Positive Trades paired with a short Position fail closed.

13. Negative Trades paired with a long Position fail closed.

14. Any unsupported-instrument Trade fails closed.

15. Any unsupported-instrument Position fails closed.

16. `OPEN` and `CLOSE_WHEN_TRADEABLE` Trades both count as current exposure.

17. Different account financial identities fail closed.

18. Alias differences alone do not cause account mismatch.

19. `last_transaction_id` equality is not required.

20. `last_transaction_id` equality is not treated as reconciliation, freshness, or authority.

21. Price, time, P/L, average-price, Trade-ID, alias, and transaction-ID changes do not affect the result when financial identity and exposure units remain equivalent.

22. Exact `Decimal` values are used without tolerance, rounding, or absolute-value conversion.

23. Source inventories are not mutated.

24. Repeated projection from the same inputs is deterministic.

25. No Atlas `Position` is constructed.

26. No average entry price or opened-at time is derived.

27. No Risk evaluation occurs.

28. No pending Order input is consumed.

29. No OANDA request or other I/O occurs.

30. No persistence, execution, runtime, API/UI, PAPER activation, LIVE behavior, or broker mutation is added.

## Focused tests

Add:

```text
backend/tests/integrations/test_oanda_exposure_projection.py
```

Use the existing frozen provider dataclasses directly.

Cover at minimum:

### FLAT

```text
trades = ()
positions = ()
→ FLAT
```

### Missing counterpart

```text
Trade exists / Position empty
→ error
```

```text
Position exists / Trade empty
→ error
```

### LONG

```text
Trade +100
Position long +100 / short 0
→ LONG
```

and:

```text
Trades +60, +40
Position long +100 / short 0
→ LONG
```

### SHORT

```text
Trade -100
Position long 0 / short -100
→ SHORT
```

and:

```text
Trades -60, -40
Position long 0 / short -100
→ SHORT
```

### `CLOSE_WHEN_TRADEABLE`

A matching Trade in this state still projects LONG or SHORT according to its current units.

### Mixed Trade directions

Opposing positive and negative Trades fail even when their arithmetic net could match a Position.

### Dual-sided Position

```text
long.units > 0
short.units < 0
→ error
```

### Unit disagreement

```text
Trade total +100
Position long +99
→ error
```

and:

```text
Trade total -100
Position short -99
→ error
```

### Direction disagreement

Positive Trades against short-only Position fail.

Negative Trades against long-only Position fail.

### Unsupported exposure

Test non-EUR/USD exposure independently in:

```text
Trade inventory
Position inventory
```

Both fail.

### Account identity

Test:

- different provider account IDs fail;
- alias-only difference succeeds when all financial identity fields and exposure facts agree.

### Transaction IDs

Use matching exposure with different `last_transaction_id` values and prove projection still succeeds.

Do not add a test requiring cursor equality.

### Irrelevant fields

Vary while preserving financial identity and exposure units:

```text
alias
Trade ID
Trade open_time
Trade open_price
Trade unrealized P/L
OPEN vs CLOSE_WHEN_TRADEABLE
Position average_price
Position unrealized P/L
last_transaction_id
```

The projected state must remain the same.

### Determinism and immutability

Repeated projection produces the same enum value and leaves both source inventories unchanged.

### Projection-specific failure

Verify cross-view incompatibilities raise:

```text
OandaExposureProjectionError
```

rather than source normalization errors.

## Validation

Use focused validation only.

Run:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_exposure_projection.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_risk_projection.py \
  backend/tests/domain/test_trading.py \
  backend/tests/risk/test_service.py
```

Then targeted quality checks:

```bash
uv run ruff format --check \
  backend/integrations/oanda/exposure_projection.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_exposure_projection.py

uv run ruff check \
  backend/integrations/oanda/exposure_projection.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_exposure_projection.py

uv run pyright \
  backend/integrations/oanda/exposure_projection.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_exposure_projection.py

git diff --check
```

Do not run by default:

```text
full backend suite
credentialed OANDA tests
database integration
migrations
frontend
browser
runtime
```

Broaden validation only if the implementation diff demonstrates broader blast radius.

## Explicitly out of scope

Do not implement:

- OANDA Position → Atlas `Position`;
- Atlas financial quantity projection;
- average-entry calculation;
- opened-at derivation;
- P/L reconciliation;
- weighted-average calculations;
- provider snapshot atomicity;
- transaction-cursor reconciliation;
- freshness policy;
- Account Changes;
- pending Order eligibility;
- Risk evaluation;
- Risk-policy changes;
- Strategy PAPER evaluation;
- pricing/liquidity handling;
- `ExecutableQuote` changes;
- broker instructions;
- broker mutation;
- broker Fill confirmation;
- PAPER persistence;
- PAPER accounting;
- runtime activation;
- generalized broker abstractions;
- LIVE.

## Lifecycle gate

This PLAN is the complete pre-approval Feature artifact.

Current state:

```text
PLAN_PENDING_APPROVAL
```

Before explicit developer approval, do not:

```text
GIT START
create tasks/
create T001
BUILD
VALIDATE
REVIEW
modify application code
modify tests
```

After explicit approval:

```text
GIT START
→ create tasks/
→ create T001 from this approved PLAN
→ BUILD
→ focused VALIDATE
→ independent REVIEW
→ remediation if required
→ merge approval
```
