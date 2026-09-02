# PLAN — PAPER 01G OANDA Practice Risk Account-State Projection

## Workstream state

- **Workstream:** `paper-01g-oanda-practice-risk-account-state-projection`
- **Outcome:** Project one already-normalized OANDA Practice account summary into the existing provider-neutral Risk `AccountState`.
- **Classification:** `Feature`.
- **Base:** `main` at `77f2b26` (`Close PAPER Readiness 01 workstream`).
- **Base SHA:** `77f2b265a8833c9aed9f52664eab8efefe42e1f9`.
- **Branch:** `solo/paper-01g-oanda-practice-risk-account-state-projection`.
- **Phase:** `READY_FOR_USER`.
- **Approval:** explicit developer implementation approval granted; GIT START completed.
- **Architecture:** not required. Current inspection shows no architectural blocker and no need to change an existing contract.
- **Task state:** `T001` — `DONE`; VALIDATION `PASS`; REVIEW `PASS`; no Critical or Important findings.
- **Next action:** await explicit developer merge approval; do not merge before approval.
- **Concerns:** none currently identified. If implementation requires changing Risk, the OANDA account-summary contract, persistence, execution, runtime, or activation semantics, stop `BLOCKED` for re-scope.

## Objective

Implement one pure deterministic projection:

```text
OandaPracticeAccountSummarySnapshot
        ↓
AccountState
```

The complete mapping is:

```python
AccountState(
    base_currency=summary.identity.base_currency,
    equity=summary.nav,
)
```

No other source field contributes to the projected `AccountState`.

## Why this slice exists

PAPER 01B established an immutable normalized OANDA Practice account-summary observation.

PAPER Readiness 01 removed Experiment lifecycle knowledge from reusable Risk.

Atlas can therefore now translate the minimum account facts Risk needs without:

- pretending PAPER is an Experiment;
- introducing OANDA into Risk;
- performing another provider request;
- changing Risk policy;
- connecting broker state to execution or persistence.

This slice establishes only that translation.

## Current contracts

### OANDA source

The existing:

```python
OandaPracticeAccountSummarySnapshot
```

contains normalized provider facts including:

```text
identity
balance
nav
unrealized_pl
margin_used
margin_available
open_trade_count
open_position_count
pending_order_count
last_transaction_id
```

Its financial Decimal fields are already required to be finite.

The snapshot intentionally permits adverse provider observations, including zero or negative NAV.

### Risk target

The existing:

```python
AccountState
```

contains:

```python
base_currency: str
equity: Decimal | None
```

Risk remains responsible for deciding whether the supplied equity is financially usable.

The projection must not duplicate that decision.

## Frozen mapping

### Base currency

Map:

```python
summary.identity.base_currency
```

directly to:

```python
AccountState.base_currency
```

Do not hard-code `"USD"` even though the currently validated OANDA Practice capability is USD-only.

The projection should preserve the normalized source fact.

### Equity

Map:

```python
summary.nav
```

directly to:

```python
AccountState.equity
```

Do not use:

```text
balance
margin_available
margin_used
balance + unrealized_pl
```

as the equity source.

Do not recompute NAV from other fields.

The normalized provider NAV fact is authoritative for this projection.

## Adverse NAV behavior

The projection must preserve finite NAV exactly.

Examples:

```text
NAV = 10000
→ equity = 10000
```

```text
NAV = 0
→ equity = 0
```

```text
NAV = -25.50
→ equity = -25.50
```

Do not:

- reject zero NAV;
- reject negative NAV;
- clamp NAV;
- call `abs`;
- convert adverse NAV to `None`;
- substitute balance;
- substitute margin available.

The projection communicates observed account truth.

Risk remains responsible for rejecting unusable financial state when Risk is actually invoked.

## Dependency direction

The intended dependency remains:

```text
OANDA integration
        ↓
Risk contract
```

Risk must not import or understand OANDA.

Strong expected implementation location:

```text
backend/integrations/oanda/risk_projection.py
```

Strong expected function:

```python
def project_oanda_practice_account_state(
    summary: OandaPracticeAccountSummarySnapshot,
) -> AccountState:
    return AccountState(
        base_currency=summary.identity.base_currency,
        equity=summary.nav,
    )
```

A pure function is preferred over a class.

Minor naming adjustments are acceptable only if they better match current OANDA integration conventions without widening scope.

## Source provenance

The resulting `AccountState` is deliberately narrower than the OANDA summary.

It does not retain:

```text
provider
environment
provider account ID
alias
balance
unrealized P/L
margin
counts
last transaction ID
```

That is intentional.

`AccountState` is a Risk input, not a broker snapshot.

The original immutable OANDA summary remains the provider evidence from which the Risk input was projected.

Do not expand `AccountState` to preserve provider provenance in this workstream.

## No network behavior

The projection receives an already-created:

```python
OandaPracticeAccountSummarySnapshot
```

It must not:

- accept `Settings`;
- inspect credentials;
- construct an OANDA requester;
- import `httpx`;
- call `/summary`;
- call `read_oanda_practice_account_summary`;
- perform any I/O.

PAPER 01B already owns provider observation.

PAPER 01G owns only translation.

## No duplicate normalization

The projection must not re-parse or revalidate:

```text
NAV
currency
transaction IDs
account counts
other summary financial fields
```

The source object is already normalized.

Do not create a second OANDA account normalization layer.

If the exact source type is accepted by the function signature, that is sufficient unless implementation reveals a concrete type-safety issue.

## No Risk evaluation

Do not call:

```text
RiskService.evaluate_pre_flight
RiskService.evaluate_pre_submission
```

This slice does not determine whether the account may trade.

It only produces the financial account input Risk may later consume.

Do not add:

```text
approved
eligible
authorized
paper_active
reconciled
```

or any lifecycle concept to the projection.

## Fields intentionally ignored

The following source facts do not affect the projected `AccountState`:

```text
provider
environment
provider_account_id
alias
balance
unrealized_pl
margin_used
margin_available
open_trade_count
open_position_count
pending_order_count
last_transaction_id
```

Varying those values while holding:

```text
identity.base_currency
nav
```

constant must not change the result.

## Other PAPER observations remain separate

Do not consume or correlate:

```text
EUR/USD pricing
open Trades
open Positions
pending Orders
transaction IDs across observations
```

Do not construct:

```text
ExecutableQuote
Position
Trade
Order
Fill
```

Do not perform reconciliation.

Each later provider-to-Atlas translation is earned separately.

## Expected implementation scope

Expected product files:

```text
backend/integrations/oanda/risk_projection.py
backend/integrations/oanda/__init__.py
```

Expected focused test file:

```text
backend/tests/integrations/test_oanda_risk_projection.py
```

`backend/integrations/oanda/__init__.py` should change only if package export conventions require exporting the projection function.

Expected unchanged:

```text
backend/risk/service.py
backend/integrations/oanda/account.py
backend/integrations/oanda/request.py
backend/integrations/oanda/primitives.py
backend/integrations/oanda/pricing.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/orders.py
backend/domain/
backend/execution/
backend/persistence/
backend/runtime/
backend/strategies/
frontend/
migrations/
```

If implementation requires changing one of those contracts to make the projection work, stop `BLOCKED` rather than widening scope.

## Acceptance criteria

1. A valid `OandaPracticeAccountSummarySnapshot` projects into the existing `AccountState`.

2. Projection is deterministic.

3. Projection performs no I/O.

4. `AccountState.base_currency` comes exactly from:

   ```python
   summary.identity.base_currency
   ```

5. `AccountState.equity` comes exactly from:

   ```python
   summary.nav
   ```

6. Balance is never used as the equity source.

7. Margin available is never used as the equity source.

8. NAV is not recomputed from balance and unrealized P/L.

9. Positive NAV is preserved exactly.

10. Zero NAV is preserved exactly.

11. Negative NAV is preserved exactly.

12. Adverse NAV is not rejected, clamped, replaced, or converted to `None`.

13. Irrelevant source fields do not affect the projected result.

14. The source summary is not mutated.

15. `AccountState` is not expanded.

16. `OandaPracticeAccountSummarySnapshot` is not expanded.

17. No Risk evaluation occurs.

18. No Experiment/PAPER/LIVE lifecycle concept is introduced.

19. No OANDA request occurs.

20. No pricing, Position, Trade, Order, Fill, or reconciliation input is consumed.

21. No persistence, execution, runtime, API/UI, PAPER activation, LIVE behavior, or broker mutation is added.

## Focused test requirements

### Exact NAV mapping

Construct a valid source summary where:

```text
balance != nav
margin_available != nav
```

Assert:

```python
result.equity == summary.nav
```

This proves the projection does not accidentally use another account financial field.

### Exact currency mapping

Assert:

```python
result.base_currency == summary.identity.base_currency
```

### Positive NAV

Verify a positive NAV is preserved exactly.

### Zero NAV

Verify:

```text
NAV = 0
```

projects to:

```text
equity = 0
```

without rejection or substitution.

### Negative NAV

Verify a negative finite NAV is preserved exactly.

### Irrelevant fields

Create summaries with the same:

```text
identity.base_currency
nav
```

but different:

```text
balance
unrealized_pl
margin_used
margin_available
open_trade_count
open_position_count
pending_order_count
last_transaction_id
```

Assert the resulting `AccountState` values are equal.

### Source immutability

Verify projection does not mutate the immutable source summary.

## Validation

Use focused validation only.

Run:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_risk_projection.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/risk/test_service.py
```

Then targeted quality checks:

```bash
uv run ruff format --check \
  backend/integrations/oanda/risk_projection.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_risk_projection.py

uv run ruff check \
  backend/integrations/oanda/risk_projection.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_risk_projection.py

uv run pyright \
  backend/integrations/oanda/risk_projection.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_risk_projection.py

git diff --check
```

Do not run by default:

```text
full backend pytest suite
credentialed OANDA checks
database integration
migrations
frontend tests
browser tests
```

Broaden validation only if the actual implementation diff demonstrates broader blast radius.

## Explicitly out of scope

Do not implement:

- another OANDA account read;
- Risk evaluation;
- Risk-policy changes;
- PAPER lifecycle or activation;
- OANDA pricing projection;
- liquidity-aware pricing;
- `ExecutableQuote` changes;
- provider Position projection;
- Trade reconciliation;
- pending Order reconciliation;
- broker instructions;
- broker Order mutation;
- broker Fill confirmation;
- PAPER persistence;
- PAPER accounting;
- runtime orchestration;
- PAPER 01H or later work;
- LIVE.

## Lifecycle gate

This PLAN is the complete pre-approval workstream artifact.

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
