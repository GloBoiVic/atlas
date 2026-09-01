# PLAN — PAPER 01C OANDA Practice Open Trade Inventory

## Workstream state

- **Workstream:** `paper-01c-oanda-practice-open-trade-inventory`
- **Outcome:** one explicitly configured and account-validated OANDA Practice account → one read-only open-Trades observation → immutable normalized provider open-Trade inventory.
- **Classification:** `Feature`. This is a bounded provider-facing capability carrying broker exposure facts, but it is read-only, non-persistent, non-capital-capable, and does not change Risk, runtime, execution, or broker authority. `ARCHITECTURE.md` is not required.
- **Phase:** `READY_FOR_USER`; developer approval received, GIT START and BUILD complete; R001 addresses the validation finding.
- **Base:** `main` at `d3a546f` (`d3a546f487601e9a8abffc28f203a2b131899ad8`).
- **Branch:** `solo/paper-01c-oanda-practice-open-trade-inventory`.
- **Task:** `T001` — `DONE_WITH_CONCERNS`; targeted BUILD checks pass; repository-wide unrelated findings remain.
- **Current remediation:** `R001` — `PASS`; leading-zero ordering tie-breaker and regression coverage completed.
- **Validation chain:** root validation found IMPORTANT V-001; R001 validation `PASS` and review `PASS`.
- **Next action:** explicit developer merge approval.
- **Approval:** developer approved in the current request.
- **Concerns:** the provider reports broker Trades, not Atlas financial Trades; the account may contain instruments outside Atlas's supported `Instrument` enum.

## Current foundation and exact gap

PAPER 01A/01B on current `main` already provide:

- explicit `Settings.oanda_account_id` selection, `SecretStr` token handling, fixed OANDA Practice base URL, bounded timeouts, and sanitized bounded retry behavior;
- `bind_oanda_practice_account(...)` and `OandaPracticeAccountValidator.validate()` returning an immutable, validated `OandaPracticeAccountIdentity` from the configured account's read-only `/summary` response;
- `read_oanda_practice_account_summary(...)` and immutable normalized account-summary facts;
- deterministic injected `httpx.Client` / `MockTransport` seams;
- fail-closed configuration, identity, JSON, provider, and normalization behavior.

The gap is that Atlas cannot yet make the account-specific:

```text
GET /v3/accounts/{accountID}/openTrades
```

request or expose the provider-reported open Trade facts.

The PAPER 01C result remains a separate provider observation. It must not become:

- an Atlas `Trade`;
- an Atlas `Position`;
- an Atlas `Order`;
- an Atlas `Fill`;
- proof that Atlas created the exposure;
- proof that Atlas owns the exposure;
- reconciliation state;
- permission to act.

## Provider contract and request

The current OANDA REST v20 contract establishes:

- `GET /v3/accounts/{accountID}/openTrades` as the narrow endpoint for an account's open Trades;
- the explicitly selected AccountID as the path parameter;
- authenticated `GET` access with `Authorization: Bearer ...`;
- `Accept-Datetime-Format: RFC3339`;
- no query parameters required for the open-Trades endpoint;
- a response object containing:

  - `trades: Array<Trade>`;
  - top-level `lastTransactionID`.

The endpoint is distinct from:

- full-account retrieval;
- account enumeration;
- Position retrieval;
- Order retrieval;
- transaction history;
- Account Changes;
- broker mutation.

Relevant OANDA Trade facts include:

- `id`: OANDA TradeID, unique within the account and represented as a positive-integer string;
- `instrument`: provider InstrumentName;
- `price`: execution price;
- `openTime`: Trade opening DateTime;
- `state`: current TradeState;
- `currentUnits`: current signed provider units;
- `unrealizedPL`: current unrealized P/L.

OANDA documents positive Trade units as long, negative units as short, and current units reducing toward zero as a Trade closes.

The settings-facing PAPER 01C helper will:

1. use existing `bind_oanda_practice_account(...)` to obtain the validated account identity;
2. issue the narrow account-specific open-Trades read using that validated identity.

This means a settings-facing PAPER 01C call may contain two distinct read-only provider observations:

```text
/summary
→ establish explicit validated account identity

/openTrades
→ observe current open Trades
```

These reads may occur at different broker transaction frontiers.

PAPER 01C must not imply they form one atomic broker snapshot.

The open-Trade inventory itself is normalized only from the successful `/openTrades` response.

A first-attempt successful open-Trade read performs exactly one `/openTrades` GET. Existing bounded safe retries may repeat that same GET after transient failure.

PAPER 01C does not call `read_oanda_practice_account_summary(...)`, consume PAPER 01B financial/count facts, or compare `open_trade_count` with the returned Trade inventory.

## Smallest immutable normalized contract

Add a provider-specific `backend/integrations/oanda/trades.py` seam with two frozen, slotted values:

```text
OandaPracticeOpenTrade
  provider_trade_id: str
  provider_instrument: str
  open_time: datetime
  open_price: Decimal
  current_units: Decimal
  state: "OPEN" | "CLOSE_WHEN_TRADEABLE"
  unrealized_pl: Decimal

OandaPracticeOpenTradeInventory
  identity: OandaPracticeAccountIdentity
  trades: tuple[OandaPracticeOpenTrade, ...]
  last_transaction_id: str
```

`open_time` is normalized to timezone-aware UTC.

The public settings helper will be:

```text
read_oanda_practice_open_trade_inventory(...)
```

The narrow reader will be:

```text
OandaPracticeOpenTradeReader
```

These contracts remain explicitly OANDA-specific so they cannot be mistaken for Atlas financial-domain Trade contracts.

Retain exactly these facts:

| Retained fact         | Why PAPER 01C needs it now                                                                                                                    |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `identity`            | Keeps the observed inventory attached to the explicitly configured, server-validated Practice account.                                        |
| `provider_trade_id`   | Identifies exactly which provider Trade OANDA reported and provides the provider key for duplicate detection.                                 |
| `provider_instrument` | Preserves provider-native instrument identity, including unsupported instruments, without expanding Atlas's canonical `Instrument` enum.      |
| `open_time`           | Preserves the provider's reported Trade opening time without turning it into Atlas lifecycle history.                                         |
| `open_price`          | Preserves the provider's reported Trade execution price without converting it into an Atlas Fill or accounting fact.                          |
| `current_units`       | Preserves current signed provider exposure and therefore the observable provider-side long/short fact without constructing an Atlas Position. |
| `state`               | Preserves the provider Trade state relevant to an open inventory.                                                                             |
| `unrealized_pl`       | Preserves provider-reported current unrealized P/L without applying Risk or accounting policy.                                                |
| `last_transaction_id` | Preserves transaction provenance attached to this open-Trades response only. It is not durable state or a reconciliation cursor.              |

Do not retain or expose:

- `initialUnits`;
- `initialMarginRequired`;
- `realizedPL`;
- `financing`;
- `dividendAdjustment`;
- `marginUsed`;
- `averageClosePrice`;
- `closingTransactionIDs`;
- `closeTime`;
- client extensions;
- dependent Take Profit Orders;
- dependent Stop Loss Orders;
- dependent Trailing Stop Loss Orders;
- other protection details.

Those facts are not required to prove the current open-Trade inventory and would introduce future accounting, protection, correlation, or reconciliation semantics.

## Provider-native instrument and unit semantics

### Provider instrument

`provider_instrument` remains a provider-bound `str`.

OANDA documents `InstrumentName` as a string containing base and quote identifiers separated by `_`.

PAPER 01C validates only the minimum documented provider shape needed to reject malformed values:

```text
non-empty base segment
_
non-empty quote segment
```

It does not require membership in:

```text
backend.domain.market_data.Instrument
```

A valid provider instrument outside Atlas's current supported trading boundary remains visible in the inventory.

For example:

```text
USD_CAD
```

must not be:

- filtered;
- dropped;
- converted to EUR/USD;
- treated as malformed solely because Atlas cannot trade it;
- added to Atlas's canonical instrument support merely to normalize the provider fact.

Observability does not imply operability.

### Current units

`current_units` is a finite `Decimal` parsed from the provider string and remains signed.

Positive and negative values preserve OANDA's provider-side long/short fact.

PAPER 01C does not create:

- absolute Atlas quantity;
- Atlas `Direction`;
- `FinancialPositionState`;
- Atlas `Position`;
- Atlas `TradeModel`;
- Atlas Fill-derived exposure.

A zero `currentUnits` value in an item returned by `/openTrades` is contradictory to the open-Trade observation and fails closed rather than being converted into a closed or flat Atlas state.

### Trade state

The provider defines:

```text
OPEN
CLOSED
CLOSE_WHEN_TRADEABLE
```

For the `/openTrades` inventory, PAPER 01C accepts:

```text
OPEN
CLOSE_WHEN_TRADEABLE
```

`CLOSE_WHEN_TRADEABLE` remains visible because it represents broker exposure that has not yet become fully closed.

A returned `CLOSED` Trade is contradictory to this endpoint's open-Trade observation and fails closed.

Unknown or malformed Trade states also fail closed.

No state is silently filtered from the provider response.

## Normalization and failure behavior

The open-Trades response must be a JSON object containing:

- a list-valued `trades`;
- a valid top-level numerical-string `lastTransactionID`.

Each Trade must be an object containing all retained PAPER 01C fields.

Extra provider fields are ignored and never copied into the normalized contracts.

### Trade ID

`provider_trade_id` must:

- be a string;
- represent a positive integer;
- preserve the provider-assigned value as a string.

Duplicate Trade IDs fail closed.

This applies to:

- identical duplicate Trade objects;
- conflicting duplicate Trade objects.

The normalizer must not:

- deduplicate;
- overwrite;
- merge;
- use first-wins or last-wins behavior.

TradeID is unique within the account, so duplicate provider IDs represent invalid or contradictory observation data for this slice.

### Instrument

Reject malformed provider InstrumentName values.

Accept valid provider-native instruments regardless of Atlas support.

Do not convert them into Atlas `Instrument`.

### Open price

`open_price` must:

- originate from a provider string;
- parse to a finite `Decimal`;
- be greater than zero.

Reject:

- missing price;
- non-string price;
- invalid decimal text;
- `NaN`;
- infinity;
- zero;
- negative values.

### Current units

`current_units` must:

- originate from a provider string;
- parse to a finite `Decimal`;
- be nonzero.

Positive and negative values are valid.

Zero fails closed for an object returned as currently open.

### Open time

`openTime` must:

- be a provider string;
- satisfy the RFC3339 response contract established by the request header;
- contain timezone information;
- normalize to UTC.

Malformed or timezone-naive values fail closed.

PAPER 01C does not derive business chronology, ownership, or reconciliation state from `open_time`.

### Unrealized P/L

`unrealized_pl` must:

- originate from a provider string;
- parse to a finite `Decimal`.

Finite:

- negative;
- zero;
- positive

values are all valid provider facts.

No Risk or profitability interpretation occurs.

### Transaction provenance

`lastTransactionID` must:

- be a string;
- represent the documented numerical transaction identifier form;
- be non-empty and valid.

Malformed transaction provenance fails closed.

### Request/provider failures

Fail closed on:

- invalid JSON;
- malformed response objects;
- deterministic provider rejection;
- authorization failure;
- transport failure;
- exhausted bounded safe retry.

Errors reuse the existing sanitized OANDA error family where appropriate.

No credential or raw provider response body may enter:

- normalized values;
- exceptions;
- logs.

No partial inventory is returned after any normalization failure.

## Empty inventory

A valid response such as:

```text
trades: []
```

with valid transaction provenance succeeds.

The result is:

```text
trades == ()
```

An empty provider inventory means:

> OANDA reported no open Trades in this observation.

It does not mean:

- account state is unknown;
- PAPER is safe to activate;
- Atlas has reconciled the account;
- no Position or Order exists;
- the PAPER 01B summary count is proven equal to zero at the same frontier.

## Determinism and provenance

The open-Trades endpoint does not establish provider array ordering as an Atlas semantic contract.

PAPER 01C therefore normalizes the immutable Trade tuple in deterministic ascending numeric `provider_trade_id` order.

This ordering exists only to make:

- equality;
- tests;
- future observation comparison

deterministic.

It does not imply:

- Trade priority;
- opening chronology;
- ownership;
- reconciliation sequence;
- execution order.

Duplicate IDs are rejected before deterministic ordering can hide them.

`last_transaction_id` belongs only to the `/openTrades` response being normalized.

It is not:

- compared with PAPER 01B's summary transaction ID;
- persisted;
- advanced;
- replayed;
- supplied to Account Changes;
- treated as an Atlas cursor;
- treated as proof of ownership;
- treated as authority to mutate broker state.

## No cross-read reconciliation

PAPER 01C does not enforce relationships such as:

```text
PAPER 01B open_trade_count == len(PAPER 01C trades)
```

or:

```text
PAPER 01B last_transaction_id == PAPER 01C last_transaction_id
```

The `/summary` and `/openTrades` reads are independent broker observations and may represent different transaction frontiers.

Cross-read consistency and reconciliation are explicitly deferred.

## Persistence decision

**Persistence is not required.**

The required outcome is a fresh immutable in-memory provider observation tied to an already validated account.

PAPER 01C requires no:

- restart recovery;
- audit-history persistence;
- durable cursor;
- reconciliation;
- `TradingAccount`;
- runtime ownership;
- broker-state lifecycle.

The identity, inventory, and transaction provenance must not be written to:

- the database;
- a cache;
- a file;
- durable runtime state.

If BUILD discovers a concrete persistence requirement, it must stop as `BLOCKED` and return for re-scoping rather than add persistence opportunistically.

## Implementation seams

Expected changes are limited to:

| File                                              | Planned change                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/integrations/oanda/trades.py`            | Add the OANDA-specific `/openTrades` read, immutable provider Trade/inventory contracts, provider-bound normalization, deterministic ordering, duplicate rejection, transaction provenance handling, and bounded sanitized request behavior. It may reuse existing OANDA errors/account identity seams but must not create a generalized broker adapter. |
| `backend/integrations/oanda/__init__.py`          | Export only the new OANDA open-Trade contracts, reader, any narrowly required normalization error, and settings-facing helper.                                                                                                                                                                                                                           |
| `backend/tests/integrations/test_oanda_trades.py` | Add deterministic `httpx.MockTransport` coverage for account binding plus exact `/openTrades` request behavior, successful normalization, unsupported instruments, signed units, accepted states, deterministic ordering, empty inventory, malformed fields, duplicate IDs, transaction provenance, retries, sanitization, and ignored provider details. |

`backend/integrations/oanda/account.py` is not expected to change.

Existing PAPER 01A/01B account identity and summary ownership remains cohesive there, and the new Trade seam consumes the already validated identity.

No changes are expected to:

```text
backend/persistence/
backend/risk/
backend/runtime/
backend/domain/trading.py
backend/execution/
backend/api/
frontend/
```

No migration is expected.

If implementation requires one of those boundaries or requires changing PAPER 01A/01B semantics, BUILD must stop as `BLOCKED` and return for re-scoping.

## Acceptance criteria

1. A settings-facing PAPER 01C read first validates the explicitly configured Practice account through the existing account-binding seam, then performs the account-specific read-only:

   ```text
   GET /v3/accounts/{configuredAccountID}/openTrades
   ```

   observation.

   A first-attempt successful open-Trade read performs exactly one `/openTrades` GET. Bounded safe retries may repeat only that same GET after transient failure.

2. A valid response returns an immutable, slotted `OandaPracticeOpenTradeInventory` containing:

   - the validated account identity;
   - deterministic tuple of normalized provider open Trades;
   - top-level transaction provenance.

3. Each normalized provider Trade exposes exactly:

   - provider Trade ID;
   - provider instrument;
   - open time;
   - open price;
   - signed current units;
   - accepted provider Trade state;
   - unrealized P/L.

4. Provider-native unsupported instruments remain visible as provider strings. No unsupported Trade is filtered and no Atlas instrument capability is expanded.

5. Signed current units remain signed provider `Decimal` facts. No Atlas `Direction`, `Position`, `TradeModel`, `Order`, `Fill`, ownership, or accounting state is constructed.

6. `OPEN` and `CLOSE_WHEN_TRADEABLE` remain observable open-inventory states. `CLOSED` and unknown/malformed states fail closed rather than being silently filtered.

7. Duplicate provider Trade IDs fail closed, whether their remaining facts are identical or conflicting. No deduplication or merge occurs.

8. Provider array ordering cannot affect normalized equality because the tuple is sorted in ascending numeric provider Trade-ID order.

9. A valid empty provider list returns a successful explicit empty inventory.

10. Malformed Trade lists, Trade objects, retained fields, transaction provenance, JSON, or provider/request outcomes produce no partial inventory and fail with sanitized errors.

11. Extra detailed Trade fields and dependent/protection Orders are ignored and not exposed.

12. PAPER 01C never calls:

    - full-account retrieval;
    - Positions;
    - pending Orders;
    - Trade history;
    - transaction history;
    - Account Changes;
    - mutating endpoints.

13. PAPER 01A identity binding and PAPER 01B summary behavior remain unchanged.

14. PAPER 01C does not reconcile PAPER 01B summary counts or transaction provenance against the independent `/openTrades` observation.

15. No persistence, API/UI, runtime, Risk, execution, reconciliation, activation, Deployment, or capital-capable behavior is introduced.

## Validation strategy

BUILD will run the focused OANDA integration tests first:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_source.py
```

Then run targeted formatting/linting and Pyright for the changed OANDA module and tests.

Then run:

```bash
uv run pytest -m "not integration and not external"
git diff --check
```

Independent VALIDATE will inspect:

- exact `/openTrades` request path, method, and headers;
- account-validation-to-openTrades flow;
- distinction between the identity `/summary` observation and the open-Trades observation;
- first-attempt `/openTrades` request count;
- bounded retry behavior;
- immutable field sets;
- provider-native instrument preservation;
- signed-unit semantics;
- accepted and rejected Trade states;
- duplicate rejection;
- deterministic numeric Trade-ID ordering;
- explicit empty inventory;
- transaction provenance-only handling;
- sanitization;
- ignored provider/protection fields;
- all forbidden-scope boundaries.

VALIDATE will rerun:

- focused OANDA integration tests;
- targeted quality checks;
- the non-integration/non-external suite;
- `git diff --check`.

No database/Alembic, API/UI, browser, or credentialed external-OANDA validation is required because this slice is non-persistent, non-UI, and has a deterministic injected HTTP seam.

## Explicitly deferred / out of scope

This workstream does not implement or authorize:

- full-account retrieval;
- open Position retrieval;
- pending Order retrieval;
- dependent/protection Order handling;
- closed Trade history;
- transaction history;
- Account Changes;
- transaction replay;
- transaction cursors;
- Atlas Trade creation;
- Atlas Position reconstruction;
- Atlas Order correlation;
- Trade/Position aggregation;
- Trade/Strategy correlation;
- ownership inference;
- Fill application;
- accounting;
- reconciliation;
- PAPER 01B summary-count reconciliation;
- PAPER 01B transaction-frontier reconciliation;
- persistence;
- `TradingAccount`;
- audit-history persistence;
- restart recovery;
- runtime coordinator;
- runtime ownership;
- Deployment;
- PAPER activation;
- START/STOP controls;
- Risk changes;
- broker equity wiring into Risk;
- Strategy evaluation;
- live market data;
- executable quotes;
- order sizing;
- Order submission;
- broker mutation;
- broker protection;
- API/UI work;
- generalized broker/account hierarchies;
- plugin infrastructure;
- PAPER 01D or later behavior;
- LIVE.

If any deferred capability appears necessary during BUILD, stop and surface the concrete boundary instead of expanding this workstream.
