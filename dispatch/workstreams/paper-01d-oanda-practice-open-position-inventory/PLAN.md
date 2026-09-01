# PLAN — PAPER 01D OANDA Practice Open Position Inventory

## Workstream state

- **Workstream:** `paper-01d-oanda-practice-open-position-inventory`
- **Outcome:** one explicitly configured and account-validated OANDA Practice account → one read-only `/openPositions` observation → immutable normalized provider open-Position inventory.
- **Classification:** `Feature`. This is a bounded broker-observation capability carrying provider exposure facts, but it is read-only, non-persistent, non-capital-capable, and does not change Atlas Risk, runtime, execution, accounting, reconciliation, or broker authority. `ARCHITECTURE.md` is not required; the contract is narrow and follows the closed 01A–01C integration pattern.
- **Base:** `main` at `faaed2ee820fd28143f08a773922fb93521aefae`.
- **Branch:** `solo/paper-01d-oanda-practice-open-position-inventory`.
- **Base SHA:** `faaed2ee820fd28143f08a773922fb93521aefae`.
- **Task:** `T001` — `DONE`.
- **Phase:** `READY_FOR_USER`.
- **Next action:** obtain explicit merge approval, then perform GIT END.
- **Approval:** merge approval required; BUILD, VALIDATE, and REVIEW passed.
- **Concerns:** the result is provider aggregate state, not an Atlas financial Position; both provider sides must remain visible without netting.

## Existing foundation and exact gap

PAPER 01A–01C on current `main` provide:

- explicit `Settings.oanda_account_id` selection and validation;
- fixed OANDA Practice base URL, bearer authentication, bounded timeouts, `Retry-After`, bounded safe retries, sanitized provider errors, and injected `httpx` seams;
- immutable `OandaPracticeAccountIdentity` from the configured account's read-only `/summary` response;
- immutable account-summary facts (`OandaPracticeAccountSummarySnapshot`);
- immutable provider-specific open Trade facts and inventory from `/openTrades`;
- provider-native unsupported-instrument visibility;
- no persistence, runtime ownership, Risk integration, reconciliation, or capital-capable behavior.

The gap is the independently account-specific read and normalized result for the Positions OANDA currently reports as open.

PAPER 01D closes only:

```text
validated Practice identity
    → GET /v3/accounts/{accountID}/openPositions
    → provider Position and PositionSide facts
    → immutable OANDA open Position inventory
```

It does not turn that result into:

- Atlas `Position`;
- `FinancialPositionState`;
- Atlas Trade;
- Atlas Order;
- Atlas Fill;
- ownership;
- accounting state;
- reconciled exposure;
- actionable exposure.

## Provider contract and endpoint choice

The official OANDA REST v20 references consulted for this plan are:

- OANDA Position endpoints;
- OANDA Position and PositionSide definitions;
- OANDA primitive definitions.

The official `/openPositions` endpoint defines an open Position as a Position in the Account that currently has a Trade opened for it and returns:

- `positions: Array[Position]`;
- top-level `lastTransactionID`.

The broader:

```text
GET /v3/accounts/{accountID}/positions
```

endpoint returns Positions for every instrument that has had a Position during the lifetime of the Account, so it is deliberately not used.

The full-account endpoint is also not used.

The request is an authenticated, read-only `GET` to exactly:

```text
/v3/accounts/{validated provider_account_id}/openPositions
```

It sends the established:

```text
Authorization: Bearer ...
Accept-Datetime-Format: RFC3339
```

headers and no query parameters.

A first-attempt successful Position observation performs exactly one `/openPositions` GET.

Existing bounded safe retry behavior may repeat only that same GET after transient failure.

The settings-facing flow remains:

```text
/summary
→ establish explicit validated account identity

/openPositions
→ independently observe current provider Positions
```

These are separate read-only broker observations and may represent different transaction frontiers.

The `/openPositions` inventory itself is normalized only from the successful `/openPositions` response.

The official Position contract contains:

```text
instrument
unrealizedPL
long
short
```

plus lifetime/accounting fields outside this slice.

The PositionSide contract contains provider facts including:

```text
units
averagePrice
tradeIDs
unrealizedPL
```

plus lifetime/accounting fields.

OANDA's official `/openPositions` example shows `averagePrice` and `tradeIDs` on exposed sides while omitting them from zero-unit sides. PAPER 01D uses that observed provider response shape when defining inactive-side normalization; it does not claim the formal PositionSide schema independently marks those fields as optional.

Provider `InstrumentName` remains a provider string, and provider decimal values are represented as strings.

## Smallest immutable normalized contract

Add a provider-specific adjacent module:

```text
backend/integrations/oanda/positions.py
```

with these frozen, slotted values:

```text
OandaPracticePositionSide
  units: Decimal
  average_price: Decimal | None
  unrealized_pl: Decimal

OandaPracticeOpenPosition
  provider_instrument: str
  unrealized_pl: Decimal
  long: OandaPracticePositionSide
  short: OandaPracticePositionSide

OandaPracticeOpenPositionInventory
  identity: OandaPracticeAccountIdentity
  positions: tuple[OandaPracticeOpenPosition, ...]
  last_transaction_id: str
```

The reader and settings-facing helper are:

```text
OandaPracticeOpenPositionReader
read_oanda_practice_open_position_inventory(...)
```

Retain exactly these facts:

| Fact                    | Why PAPER 01D needs it                                                                                                      |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `identity`              | Attaches the observation to the explicitly configured and server-validated Practice account.                                |
| `provider_instrument`   | Identifies the provider Position, preserves unsupported instruments, and provides the exact duplicate/order key.            |
| overall `unrealized_pl` | Preserves OANDA's current instrument-level unrealized P/L observation without using it for Risk or accounting.              |
| `long` / `short`        | Preserves OANDA's two independent Position sides and prevents accidental netting into an Atlas direction.                   |
| side `units`            | Preserves finite signed provider units as `Decimal`.                                                                        |
| side `average_price`    | Preserves the provider's average open price when reported for that side while allowing the observed inactive-side omission. |
| side `unrealized_pl`    | Preserves current provider-side unrealized P/L without treating it as a safety or accounting decision.                      |
| `last_transaction_id`   | Preserves provenance for this `/openPositions` response only.                                                               |

Ignore Position-level lifetime/accounting facts including:

- `pl`;
- `resettablePL`;
- `marginUsed`;
- `financing`;
- `commission`;
- `dividendAdjustment`;
- `guaranteedExecutionFees`.

Ignore corresponding PositionSide lifetime/accounting facts.

`tradeIDs` are explicitly excluded.

They are not required to answer which instrument-level Positions OANDA currently reports as open, and retaining them in 01D would introduce an unnecessary seam toward PAPER 01C Trade correlation.

If present in the provider payload, `tradeIDs`:

- remain ignored;
- are not exposed;
- are not validated for 01D;
- are not compared with PAPER 01C provider Trade IDs.

No extra provider fields are copied into normalized values.

## Side semantics and validation

The normalizer preserves both provider side objects independently.

### Units

Long-side units must be provider decimal strings that normalize to finite `Decimal` values:

```text
>= 0
```

Short-side units must normalize to finite `Decimal` values:

```text
<= 0
```

This follows the provider's documented sign semantics:

- positive units indicate long exposure;
- negative units indicate short exposure.

Zero units are valid for an individual side and represent no current provider exposure on that side.

A nonzero long side remains provider long-side exposure.

A nonzero short side remains provider short-side exposure.

Both sides may be nonzero and must remain independently observable.

PAPER 01D does not:

- net the sides;
- assume only one side may be exposed;
- reject both-sided exposure merely because Atlas may not later permit it;
- infer account hedging policy;
- create Atlas `Direction`;
- create `FinancialPositionState`;
- create Atlas quantity.

Both sides being zero in an object returned by `/openPositions` is contradictory to the endpoint's documented meaning that an open Position currently has an open Trade contributing to it.

Such an object fails closed.

### Average price

For a side with nonzero units:

- `averagePrice` must be present;
- it must be a provider string;
- it must parse to a finite `Decimal`;
- it must be strictly positive.

Missing, null, malformed, non-finite, zero, or negative `averagePrice` for an exposed side fails closed.

For a zero-unit side:

- omission of `averagePrice` is accepted and normalizes to `None`, matching the provider response shape demonstrated by the official `/openPositions` examples;
- if `averagePrice` is supplied anyway, it must be a valid finite positive provider price before being retained;
- Atlas does not fabricate or derive a value.

No average price is reconstructed from PAPER 01C Trades.

### Unrealized P/L

Both:

```text
Position.unrealizedPL
```

and retained:

```text
PositionSide.unrealizedPL
```

must originate from provider decimal strings and parse to finite `Decimal` values.

Finite:

- negative;
- zero;
- positive

values are all valid broker facts.

A losing Position is not a normalization failure.

PAPER 01D does not require:

```text
Position.unrealizedPL
==
long.unrealizedPL + short.unrealizedPL
```

or perform any other locally derived arithmetic consistency test between the provider-reported Position and side P/L facts.

Those values are preserved as independently broker-reported observations.

No P/L value is sent to Risk or interpreted as Atlas accounting state in this slice.

## Provider instrument semantics

`provider_instrument` remains an exact provider-bound `str`.

Validate only the minimum provider shape needed to reject malformed values:

```text
non-empty base segment
_
non-empty quote segment
```

Do not require membership in:

```text
backend.domain.market_data.Instrument
```

Do not:

- case-fold;
- rewrite;
- translate;
- silently filter;
- map unsupported values to a supported Atlas instrument.

For example:

```text
USD_CAD
```

must remain observable if OANDA reports it.

This does not expand Atlas's supported trading capability.

Observability does not imply operability.

## Duplicate instrument handling

An OANDA Position is instrument-level provider state.

If the `/openPositions` response contains multiple Position objects with the same exact `provider_instrument`, normalization fails closed.

This applies whether the duplicate objects contain:

- identical facts;
- conflicting facts.

The normalizer must not:

- merge;
- net;
- deduplicate;
- first-win;
- last-win.

Differently represented provider strings are not silently rewritten into equality unless the provider contract itself requires such normalization.

PAPER 01D preserves the supplied provider identifier.

## Inventory ordering and provenance

Provider array order is not adopted as an Atlas semantic contract.

After duplicate detection, normalize the immutable Position tuple in ascending lexicographic order of the exact:

```text
provider_instrument
```

string.

This ordering exists only to make:

- normalized equality;
- tests;
- future observation comparison

deterministic.

It does not imply:

- Position priority;
- chronology;
- exposure magnitude;
- ownership;
- reconciliation order.

`last_transaction_id` must be a valid numerical-string transaction identifier using the same narrow representation already established by the OANDA account and Trade seams.

It belongs only to this `/openPositions` observation.

It is not:

- a reconciliation cursor;
- an Account Changes cursor;
- replay state;
- durable recovery state;
- proof of a shared transaction frontier;
- authority to mutate broker state.

It is not persisted or advanced.

## No cross-read reconciliation

PAPER 01D does not enforce relationships such as:

```text
PAPER 01B open_position_count
==
len(PAPER 01D positions)
```

or:

```text
aggregate(PAPER 01C trades)
==
PAPER 01D positions
```

or:

```text
PAPER 01C last_transaction_id
==
PAPER 01D last_transaction_id
```

or:

```text
PAPER 01B last_transaction_id
==
PAPER 01D last_transaction_id
```

The account summary, open Trade inventory, and open Position inventory are independent broker observations that may represent different transaction frontiers.

PAPER 01D does not:

- aggregate PAPER 01C Trades;
- compare PAPER 01C Trade IDs with provider Position `tradeIDs`;
- establish completeness;
- establish ownership;
- reconcile broker state.

Trade ↔ Position consistency and account-wide reconciliation remain deferred.

## Empty inventory

A valid response containing:

```text
positions: []
```

with valid transaction provenance succeeds with:

```text
positions == ()
```

It means only:

> OANDA reported no open Positions in this `/openPositions` observation.

It does not prove:

- PAPER 01C reported no open Trades at another transaction frontier;
- PAPER 01B's open Position count was zero at the same frontier;
- no pending Orders exist;
- the account is reconciled;
- PAPER is safe to activate.

## Failure behavior

Fail closed with sanitized OANDA errors on:

- missing or blank token;
- invalid timeout configuration;
- invalid reader identity;
- invalid JSON;
- non-object response;
- missing or non-list `positions`;
- non-object Position items;
- malformed provider instrument;
- exact duplicate provider instrument;
- missing or malformed retained Position fields;
- missing or malformed `long` / `short` objects;
- malformed or non-finite side units;
- long-side negative units;
- short-side positive units;
- both sides zero;
- missing or invalid exposed-side average price;
- malformed supplied inactive-side average price;
- malformed Position-level unrealized P/L;
- malformed side-level unrealized P/L;
- malformed top-level transaction provenance;
- deterministic provider rejection;
- transport failure;
- exhausted bounded retries.

No partial inventory is returned if any Position fails normalization.

Errors may expose only safe provider failure metadata already supported by the current OANDA error family.

They must never expose:

- API token;
- raw provider response body;
- secret-bearing transport exception text.

Ignored `tradeIDs` and ignored lifetime/accounting fields do not become required PAPER 01D facts.

Valid but financially or operationally concerning provider facts remain observable.

Examples include:

- unsupported instruments;
- large exposure;
- negative unrealized P/L;
- both long and short sides carrying exposure.

PAPER 01D represents broker truth; it does not judge whether that truth is safe for future trading.

## Request-code reuse decision

Do not refactor:

```text
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/source.py
```

for this slice.

Their request behavior is already proven by PAPER 01A–01C and should remain unchanged.

`positions.py` should narrowly reuse current public/current seams where appropriate:

- `OANDA_PRACTICE_BASE_URL`;
- existing sanitized OANDA error types;
- `OandaPracticeAccountIdentity`;
- `bind_oanda_practice_account(...)`;
- Settings timeout values;
- established request/header/retry behavior.

The `/openPositions` request and Position normalization remain locally cohesive in the new Position module.

Do not extract:

- generalized OANDA HTTP client;
- generic broker reader;
- generic broker Position hierarchy;
- future LIVE adapter.

Some local repetition is preferable to expanding this bounded provider-observation slice into a cross-cutting integration refactor.

If BUILD demonstrates that sharing request machinery is genuinely unavoidable, it must stop for re-scoping rather than opportunistically refactor 01A–01C.

## Implementation seams and task

Expected changes are limited to:

| File                                                 | Planned change                                                                                                                                                                                                                                                                                                                                                                |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/integrations/oanda/positions.py`            | Add provider-specific immutable PositionSide/Position/inventory contracts, `/openPositions` reader, side validation, deterministic ordering, duplicate rejection, transaction provenance, and bounded sanitized request behavior.                                                                                                                                             |
| `backend/integrations/oanda/__init__.py`             | Export only the new Position contracts, reader, narrowly required normalization error, and settings-facing helper.                                                                                                                                                                                                                                                            |
| `backend/tests/integrations/test_oanda_positions.py` | Add deterministic injected-HTTP coverage for validated-account flow, exact `/openPositions` request, contract fields, side semantics, conditional average-price behavior, unsupported instruments, both-sided exposure, deterministic ordering, empty inventory, duplicate instruments, malformed/contradictory state, provenance, retries, sanitization, and ignored fields. |
| existing focused OANDA tests                         | No product changes; rerun PAPER 01A–01C focused tests as regression evidence.                                                                                                                                                                                                                                                                                                 |

No change is planned to:

```text
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/source.py
backend/persistence/
backend/risk/
backend/runtime/
backend/domain/trading.py
backend/execution/
backend/api/
frontend/
```

No migration is expected.

If BUILD finds one of those boundaries necessary, it must stop as `BLOCKED` for re-scoping rather than expand the slice.

## Persistence decision

**No durable Atlas persistence is required.**

A fresh immutable in-memory provider observation tied to a validated account identity satisfies PAPER 01D.

Persistence is not added for:

- restart recovery;
- audit history;
- future reconciliation;
- runtime ownership;
- broker account state;
- Deployment.

The identity, Position facts, and transaction provenance must not be written to:

- database;
- cache;
- file;
- durable runtime state.

If BUILD discovers a concrete persistence requirement, it must stop as `BLOCKED` and return for developer re-scoping approval.

## Acceptance criteria

1. The settings-facing helper validates the explicitly configured Practice account through the existing `/summary` binding and then independently performs the account-specific read-only:

   ```text
   GET /v3/accounts/{accountID}/openPositions
   ```

   observation.

   A first-attempt successful Position read performs exactly one `/openPositions` GET. Bounded safe retries may repeat only that same GET after transient failure.

2. A valid response returns a frozen, slotted `OandaPracticeOpenPositionInventory` containing:

   - validated account identity;
   - deterministic immutable Position tuple;
   - top-level transaction provenance.

3. Each Position exposes exactly:

   - provider instrument;
   - overall unrealized P/L;
   - independent normalized long side;
   - independent normalized short side.

4. Each Position side exposes exactly:

   - signed provider units;
   - optional normalized average price according to exposed/inactive-side rules;
   - side unrealized P/L.

5. Long-side units are finite and nonnegative. Short-side units are finite and nonpositive. Zero sides remain explicitly represented.

6. Both nonzero sides are accepted and preserved independently. No net exposure, Atlas direction, hedging interpretation, or financial Position is constructed.

7. A Position returned by `/openPositions` with both sides zero fails closed as contradictory provider state.

8. An exposed side requires a finite positive provider average price. A zero side may omit average price and normalize it to `None`. No average price is fabricated or derived from PAPER 01C.

9. Negative, zero, and positive finite Position-level and side-level unrealized P/L values remain valid observations. No arithmetic consistency between overall and side P/L is locally required or derived.

10. Provider-native unsupported instruments remain visible without expanding Atlas's supported `Instrument` enum.

11. Exact duplicate provider instruments fail closed without merge, netting, or deduplication.

12. Provider response ordering cannot affect normalized equality because Positions are sorted by the exact provider instrument identifier.

13. A valid empty Position list returns an explicit immutable empty inventory.

14. Malformed response, Position, side, instrument, unit, sign, average-price, P/L, provenance, JSON, provider, or retry state fails closed without partial output and with sanitized errors.

15. `tradeIDs`, lifetime/accounting fields, and other unretained provider facts are not exposed or used.

16. PAPER 01D never retrieves:

    - full-account Position data;
    - lifetime `/positions`;
    - pending Orders;
    - protection Orders;
    - additional Trade data;
    - transaction history;
    - Account Changes;
    - any mutating endpoint.

17. PAPER 01A–01C behavior remains unchanged.

18. PAPER 01B and 01C counts, inventories, Trade IDs, and transaction provenance are never reconciled with PAPER 01D.

19. No Atlas Position/Trade/Order/Fill state, ownership, accounting, persistence, API/UI, runtime, Risk, execution, reconciliation, activation, Deployment, generalized broker architecture, or capital-capable behavior is introduced.

## Validation strategy

BUILD will first run:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_source.py
```

Then it will run:

- targeted Ruff formatting;
- targeted Ruff lint;
- targeted Pyright for the changed OANDA module/tests;
- the non-integration/non-external suite;
- `git diff --check`.

Independent VALIDATE will inspect:

- exact `/openPositions` endpoint, method, headers, and query behavior;
- validated-account `/summary` → independent `/openPositions` flow;
- first-attempt `/openPositions` request count;
- bounded retry behavior;
- immutable contract field sets;
- provider-side preservation;
- long/short sign semantics;
- zero-side behavior;
- both-sided exposure behavior;
- exposed/inactive-side average-price handling;
- provider-native unsupported instruments;
- duplicate rejection;
- deterministic ordering;
- explicit empty inventory;
- Position and side P/L preservation without arithmetic inference;
- provenance-only handling;
- sanitization;
- ignored `tradeIDs` and lifetime fields;
- all forbidden-scope boundaries.

VALIDATE will rerun:

- focused OANDA tests;
- targeted quality checks;
- the non-integration/non-external suite;
- `git diff --check`.

No Alembic/database, browser, API/UI, or credentialed external-OANDA check is required because this slice is non-persistent, non-UI, and has a deterministic injected HTTP seam.

## Explicitly out of scope

This workstream does not implement or authorize:

- full-account retrieval;
- lifetime `/positions` retrieval;
- single-instrument Position retrieval;
- pending Orders;
- protection Orders;
- new Trade retrieval;
- Atlas Position construction;
- Atlas Trade construction;
- Atlas Order construction;
- Atlas Fill construction;
- net Atlas exposure;
- Trade ↔ Position aggregation;
- Trade ↔ Position reconciliation;
- summary ↔ Position reconciliation;
- provider Trade-ID correlation;
- ownership inference;
- Strategy correlation;
- accounting;
- Position P/L derivation;
- transaction history;
- Account Changes;
- transaction replay;
- reconciliation cursors;
- persistence;
- `TradingAccount`;
- Deployment;
- runtime ownership;
- runtime coordinator;
- Risk integration;
- broker-equity wiring into Risk;
- live market data;
- Strategy evaluation;
- executable quotes;
- order sizing;
- Order submission;
- broker mutation;
- broker protection;
- PAPER activation;
- START/STOP controls;
- API/UI work;
- generalized broker abstractions;
- PAPER 01E or later behavior;
- LIVE.

If any deferred capability appears necessary during BUILD, stop and surface the concrete blocker for developer re-scoping approval.
