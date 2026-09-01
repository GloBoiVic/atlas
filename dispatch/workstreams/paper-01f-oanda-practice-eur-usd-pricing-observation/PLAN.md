# PLAN — PAPER 01F OANDA Practice EUR/USD Pricing Observation

## Workstream state

- **Workstream:** `paper-01f-oanda-practice-eur-usd-pricing-observation`
- **Outcome:** one explicitly configured and account-validated OANDA Practice account → one independent read-only EUR/USD `/pricing` observation → immutable normalized provider pricing facts.
- **Classification:** `Feature`. This is one bounded provider-observation capability using the already-frozen query-capable OANDA requester. It introduces no persistence, Risk/runtime authority, execution behavior, reconciliation, broker mutation, API/UI behavior, or capital exposure.
- **Base:** `main` at `d2eac2f1b257c890e510c1b2dd303a8abc6d20a0`.
- **Branch:** `solo/paper-01f-oanda-practice-eur-usd-pricing-observation`.
- **Base SHA:** `d2eac2f1b257c890e510c1b2dd303a8abc6d20a0`.
- **Phase:** `GIT_END`.
- **Next action:** commit the approved feature branch, merge into `main`, push GitHub, and close dispatch state.
- **Approval:** implementation and merge approved by developer; GIT START complete; GIT END in progress.
- **Architecture:** not required for this Feature classification unless SoloFlow independently finds a Critical architectural concern.
- **Task state:** `T001` — `DONE`; VALIDATION `PASS`; REVIEW `PASS`.
- **Concerns:** provider bid/ask liquidity facts must remain provider observations. PAPER 01F must not prematurely convert them into an Atlas `ExecutableQuote` or imply executable quantity.

## Objective

PAPER 01F answers only:

> What current account-specific EUR/USD pricing facts does OANDA Practice report, including provider price time, tradeability, and ordered bid/ask liquidity buckets?

Conceptually:

```text
explicit validated Practice account
        ↓
GET /v3/accounts/{accountID}/pricing
    ?instruments=EUR_USD
        ↓
one EUR_USD ClientPrice
        ↓
immutable provider pricing observation
```

This workstream does not answer:

- which price Atlas should submit against;
- what quantity is executable;
- whether the price is fresh enough to trade;
- whether Risk should approve;
- how many liquidity buckets should be consumed;
- what spread or VWAP is;
- whether PAPER should activate.

## Existing foundation

Current `main` already provides:

```text
PAPER 01A — Practice account identity
PAPER 01B — Account summary
PAPER 01C — Open Trade inventory
PAPER 01D — Open Position inventory
PAPER 01E — Pending Order identity inventory
```

The shared OANDA read-only infrastructure provides:

```text
backend/integrations/oanda/request.py
backend/integrations/oanda/primitives.py
```

`OandaObservationRequester.get_json(...)` already supports:

```python
params: Mapping[str, str] | None = None
```

with:

- fixed OANDA Practice routing;
- authenticated GET only;
- bounded timeouts;
- owned/injected client behavior;
- bounded retry;
- `Retry-After`;
- sanitized errors;
- JSON decoding;
- stable query snapshot across retries.

That requester seam is frozen.

PAPER 01F must reuse it without modification.

## Exact provider endpoint

Use exactly:

```text
GET /v3/accounts/{accountID}/pricing
```

with exactly:

```text
instruments=EUR_USD
```

through:

```python
params={"instruments": "EUR_USD"}
```

Do not manually append query text to the path.

Do not use:

```text
/pricing/stream
/candles/latest
/instruments/{instrument}/candles
```

Do not supply:

```text
since
includeHomeConversions
includeUnitsAvailable
```

The settings-facing flow remains:

```text
/summary
→ validate explicitly configured Practice account

/pricing?instruments=EUR_USD
→ independently observe current provider pricing
```

These two requests are not atomic and may represent different provider transaction/time frontiers.

## Exact response cardinality

PAPER 01F requests exactly one instrument:

```text
EUR_USD
```

The normalized observation therefore requires exactly one `ClientPrice`.

Fail closed if:

```text
prices missing
prices not a list
prices == []
more than one Price item
Price item not an object
returned instrument != EUR_USD
```

Examples:

```text
[]
→ fail

[EUR_USD]
→ valid if retained fields normalize

[USD_CAD]
→ fail

[EUR_USD, EUR_USD]
→ fail

[EUR_USD, USD_CAD]
→ fail
```

Do not:

- silently choose the first;
- filter unexpected instruments;
- deduplicate;
- issue another provider request;
- return a partial observation.

Unexpected provider cardinality remains visible.

## Smallest immutable provider contract

The expected provider-specific contract is:

```text
OandaPracticePriceBucket
  price: Decimal
  liquidity: Decimal

OandaPracticeEurUsdPricingObservation
  identity: OandaPracticeAccountIdentity
  provider_instrument: Literal["EUR_USD"]
  price_time: datetime
  tradeable: bool
  bids: tuple[OandaPracticePriceBucket, ...]
  asks: tuple[OandaPracticePriceBucket, ...]
```

Use frozen/slotted immutable dataclasses following the current OANDA observation pattern.

Retain only the facts necessary for this slice.

## Validated account identity

`identity` must be the existing:

```text
OandaPracticeAccountIdentity
```

produced through:

```python
bind_oanda_practice_account(...)
```

The pricing reader must not construct account identity independently.

The settings-facing helper must bind the account first and then perform the pricing read.

## Instrument boundary

PAPER 01F supports only:

```text
EUR_USD
```

for this capability.

Require the provider `ClientPrice.instrument` to be exactly:

```text
EUR_USD
```

Do not broaden this workstream into arbitrary instruments.

This is a current validated capability boundary, not a permanent Atlas product limitation.

## Provider Price timestamp

Retain:

```text
ClientPrice.time
```

as:

```text
price_time: datetime
```

Normalize to timezone-aware UTC.

Use the existing OANDA Trade timestamp behavior as a nearby semantic pattern, but keep pricing timestamp normalization local unless an already-shared primitive exists with exactly the same semantics.

Do not modify `trades.py` or shared primitives merely to remove a small amount of timestamp parsing duplication.

Fail closed on:

- missing timestamp;
- non-string timestamp;
- malformed RFC3339 timestamp;
- timestamp without timezone.

Do not:

- substitute current system time;
- use account-summary time;
- strip timezone;
- create a staleness policy;
- decide whether the observation is fresh enough for trading.

PAPER 01F observes provider time only.

## Top-level pricing response time

The endpoint response also contains a top-level:

```text
time
```

PAPER 01F explicitly does **not retain or interpret this field**.

Do not:

- persist it;
- use it as a `since` cursor;
- create polling state;
- compare it with `ClientPrice.time`;
- validate it merely because it is present.

Malformed top-level `time` does not invalidate an otherwise valid retained observation.

Polling and cursor semantics are deferred.

## Tradeability

Retain exact provider:

```text
tradeable
```

as:

```python
bool
```

Require exact Python `bool`.

Both are valid observations:

```text
tradeable=True
tradeable=False
```

`False` is not a provider read failure.

It is an adverse but valid provider fact.

Do not infer tradeability from:

- bid presence;
- ask presence;
- liquidity;
- spread;
- deprecated provider `status`.

Do not convert `tradeable=False` into:

- Risk rejection;
- request error;
- PAPER deactivation.

Those semantics belong later.

## Bid and ask liquidity buckets

Retain:

```text
bids
asks
```

as immutable tuples of:

```text
OandaPracticePriceBucket
```

Each provider PriceBucket retains only:

```text
price
liquidity
```

Do not retain other provider fields.

### Price

Provider bucket price must normalize to:

```python
Decimal
```

Use the existing OANDA string decimal primitive where appropriate.

Require:

```text
finite
> 0
```

Fail closed on:

- missing;
- non-string;
- malformed decimal string;
- zero;
- negative;
- NaN;
- infinity.

Do not interpret a bucket price as:

- top-of-book;
- executable entry price;
- average fill price;
- spread boundary.

It is only the provider price attached to that bucket.

### Liquidity

Provider bucket liquidity is a JSON numeric value rather than the provider string-decimal representation used elsewhere.

Normalize liquidity locally in `pricing.py`.

The frozen rule is:

- reject `bool`;

- accept exact JSON integer values;

- accept finite JSON floating-point values;

- convert using a decimal-preserving representation equivalent to:

  ```python
  Decimal(str(value))
  ```

- require:

  ```text
  finite
  >= 0
  ```

- retain as `Decimal`.

Reject:

- bool;
- negative values;
- NaN;
- infinity;
- strings;
- null;
- objects;
- arrays.

Do not modify the existing shared string-only decimal primitive merely to accommodate pricing liquidity.

Liquidity normalization belongs locally to the pricing provider module.

PAPER 01F does not claim that provider liquidity equals executable Atlas quantity.

## Empty liquidity sides are valid

OANDA pricing may report no currently available liquidity on one or both sides.

Therefore all of these are valid:

```text
bids == ()
asks populated
```

```text
bids populated
asks == ()
```

```text
bids == ()
asks == ()
```

Do not fail merely because a side is empty.

Do not substitute another provider field.

Do not synthesize a price.

Do not use historical data as fallback.

## Bucket order

Preserve provider array order exactly.

Do not:

- sort;
- reverse;
- merge;
- aggregate;
- deduplicate;
- calculate cumulative liquidity.

Do not introduce undocumented assumptions such as:

```text
bids descending
asks ascending
```

Even if provider examples appear ordered, PAPER 01F does not require that semantic.

Provider array order remains provider-observed order only.

## No cross-bucket interpretation

PAPER 01F does not derive:

```text
best_bid
best_ask
spread
mid
VWAP
depth
available_quantity
```

Do not enforce:

```text
bid < ask
best bid < best ask
positive spread
non-crossed market
```

because 01F does not yet select a “best” bucket or interpret market execution.

## Closeout prices

Ignore:

```text
closeoutBid
closeoutAsk
```

Do not:

- expose them;
- validate them;
- substitute them for empty bids/asks;
- interpret them as opening prices;
- use them to create an executable quote.

Malformed closeout fields do not invalidate an otherwise valid retained observation.

## Deprecated and unretained ClientPrice fields

Ignore and do not expose:

```text
status
quoteHomeConversionFactors
unitsAvailable
closeoutBid
closeoutAsk
type
```

Also ignore top-level:

```text
time
homeConversions
```

Do not validate ignored fields merely because they are present.

If an ignored field is malformed, the retained PAPER 01F observation remains valid.

The rule is:

> Validate only the provider facts this bounded capability claims to understand.

## Atlas Risk semantic boundary

Current:

```text
backend/risk/service.py
```

contains:

```python
ExecutableQuote(
    bid: Decimal,
    ask: Decimal,
)
```

PAPER 01F must not construct or import that type.

Do not implement:

```text
bids[0] + asks[0]
→ ExecutableQuote
```

That future conversion requires explicit semantics for:

- price ordering;
- trade side;
- requested quantity;
- provider liquidity;
- missing sides;
- tradeability;
- freshness/staleness;
- depth consumption.

Those semantics are intentionally deferred.

PAPER 01F produces:

```text
provider pricing observation
```

not:

```text
Atlas executable quote
```

## Historical market-data boundary

Do not convert the pricing observation into:

```text
MarketBar
M1 BID/ASK historical observation
analytical Strategy data
historical candle
```

Current account-specific pricing is a different provider fact from historical candle data.

Do not persist 01F pricing into historical market-data storage.

## Request behavior

Expected module:

```text
backend/integrations/oanda/pricing.py
```

Expected reader:

```text
OandaPracticeEurUsdPricingReader
```

Expected settings-facing helper:

```text
read_oanda_practice_eur_usd_pricing(...)
```

PLAN naming may be adjusted slightly during implementation only if current OANDA package naming makes another provider-specific name clearly more cohesive.

The reader must:

1. receive an already validated `OandaPracticeAccountIdentity`;

2. validate its own configuration through existing mechanisms;

3. construct:

   ```text
   /v3/accounts/{quotedAccountID}/pricing
   ```

4. call the existing requester with:

   ```python
   params={"instruments": "EUR_USD"}
   ```

5. normalize exactly one EUR/USD `ClientPrice`.

The settings-facing helper must:

```text
bind_oanda_practice_account(...)
→ construct pricing reader
→ read pricing observation
```

No other endpoint is introduced.

## Error behavior

Add one narrow pricing normalization error following existing OANDA naming conventions, for example:

```text
OandaPricingNormalizationError
```

or a slightly more EUR/USD-specific equivalent if current package naming favors it.

Fail closed on at least:

- invalid reader identity;
- missing/blank token;
- invalid timeout configuration;
- invalid JSON;
- non-object top-level payload;
- missing/non-list `prices`;
- empty prices;
- multiple Price items;
- non-object Price item;
- wrong provider instrument;
- malformed/missing Price timestamp;
- malformed/missing/non-bool tradeable;
- missing/non-list bids;
- missing/non-list asks;
- non-object bucket;
- invalid bucket price;
- invalid bucket liquidity;
- provider rejection;
- transport failure;
- exhausted bounded retries.

No partial pricing observation may be returned.

If one bucket is malformed, the entire observation fails.

Existing request-level errors remain sanitized through the shared requester.

## No persistence

PAPER 01F does not require durable persistence.

The result is an ephemeral provider observation.

Do not add:

- database model;
- migration;
- repository;
- cache;
- price table;
- durable cursor;
- audit persistence;
- recovery state.

If BUILD discovers a genuine persistence requirement, stop:

```text
BLOCKED
```

and return for re-scoping.

## No polling or streaming

One helper invocation performs one explicit observation.

Do not implement:

```text
loop
timer
scheduler
background worker
poll every N seconds
since cursor
stream
heartbeat
WebSocket
pricing cache
```

Do not design the next polling slice here.

## No broker mutation

PAPER 01F remains read-only.

Do not:

- submit;
- cancel;
- replace;
- modify;
- close;
- open

any broker Order, Trade, or Position.

## Expected implementation seams

Expected product/test changes:

```text
backend/integrations/oanda/pricing.py
backend/integrations/oanda/__init__.py
backend/tests/integrations/test_oanda_pricing.py
```

plus canonical workstream artifacts created according to SoloFlow lifecycle.

Before developer approval there must be no BUILD task artifact.

After approval and GIT START, Solo may create:

```text
tasks/T001-paper-01f-oanda-practice-eur-usd-pricing-observation.md
```

Expected unchanged application files:

```text
backend/integrations/oanda/request.py
backend/integrations/oanda/primitives.py
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/orders.py
backend/integrations/oanda/source.py

backend/risk/
backend/runtime/
backend/execution/
backend/persistence/
backend/api/
frontend/
```

If BUILD requires a product change to the frozen requester or other shared OANDA modules, stop:

```text
BLOCKED
```

for re-scoping.

A local timestamp or liquidity parser is preferable to another shared infrastructure refactor.

## Acceptance criteria

1. The settings-facing helper validates the explicitly configured Practice account through the existing `/summary` account-binding flow before pricing.

2. It independently performs:

   ```text
   GET /v3/accounts/{accountID}/pricing
   ```

   with exactly:

   ```text
   instruments=EUR_USD
   ```

3. Query parameters use the frozen `params=` requester seam.

4. No query string is manually concatenated.

5. No `since`, home-conversion, units-available, streaming, or other pricing option is supplied.

6. Exactly one Price object is required.

7. The one Price object's instrument must be exactly `EUR_USD`.

8. Empty, duplicate, extra, or wrong-instrument Price arrays fail closed.

9. The normalized result is frozen/slotted.

10. The observation retains only:

    ```text
    identity
    provider_instrument
    price_time
    tradeable
    bids
    asks
    ```

11. `ClientPrice.time` normalizes to timezone-aware UTC.

12. Top-level response `time` is ignored.

13. `tradeable` must be an exact bool.

14. Both `True` and `False` are valid observations.

15. `bids` and `asks` are required arrays.

16. Either side or both sides may be empty.

17. Bucket price is a positive finite `Decimal`.

18. Bucket liquidity is a locally normalized finite nonnegative `Decimal`.

19. Bool liquidity is rejected.

20. Shared `parse_decimal` is not broadened for JSON numeric liquidity.

21. Provider bucket order is preserved exactly.

22. No sorting, aggregation, deduplication, spread, mid, top-of-book, VWAP, or executable-depth interpretation occurs.

23. Closeout prices are ignored.

24. Deprecated and otherwise unretained ClientPrice fields are ignored.

25. Malformed ignored fields do not invalidate an otherwise valid observation.

26. Malformed retained fields fail closed with no partial result.

27. The provider observation is not converted into:

    ```text
    ExecutableQuote
    Atlas Order
    Fill
    Position
    Trade
    historical MarketBar
    ```

28. No persistence, polling, streaming, Risk/runtime, API/UI, execution, reconciliation, broker mutation, PAPER activation, or LIVE behavior is introduced.

29. PAPER 01A–01E behavior and the shared query-capable requester remain unchanged.

## Focused validation

Do **not** run the full backend suite.

Required focused tests:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_pricing.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_request.py \
  backend/tests/integrations/test_oanda_primitives.py
```

These cover:

- the new provider-domain pricing behavior;
- account binding;
- the already-frozen query transport;
- the reused decimal/transaction primitives.

Do not rerun Trade, Position, pending Order, historical source, database, frontend, or runtime tests unless implementation unexpectedly changes those areas.

Run targeted quality checks:

```bash
uv run ruff format --check \
  backend/integrations/oanda/pricing.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_pricing.py

uv run ruff check \
  backend/integrations/oanda/pricing.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_pricing.py

uv run pyright \
  backend/integrations/oanda/pricing.py \
  backend/tests/integrations/test_oanda_pricing.py

git diff --check
```

Do not run by default:

```text
full backend pytest suite
database integration tests
Alembic
frontend tests
browser tests
credentialed external OANDA requests
```

If independent VALIDATE discovers evidence of an unexpected cross-boundary change, stop for re-scoping rather than automatically broadening the validation workload.

## Required focused test evidence

The new pricing tests must prove at least:

### Request sequence

```text
/summary
→ /pricing
```

with exactly:

```python
params={"instruments": "EUR_USD"}
```

### Cardinality

Test:

```text
[]
[EUR_USD]
[USD_CAD]
[EUR_USD, EUR_USD]
[EUR_USD, USD_CAD]
```

Only one exact EUR/USD item succeeds.

### Timestamp

Test:

- valid UTC `Z`;
- valid offset timestamp normalized to UTC;
- malformed timestamp;
- timezone-less timestamp.

### Tradeability

Accept:

```text
true
false
```

Reject:

```text
missing
0
1
"true"
"false"
null
```

### Empty sides

Prove valid:

```text
bids empty, asks populated
bids populated, asks empty
both empty
```

### Bucket price

Accept valid positive finite provider price strings.

Reject:

```text
malformed
zero
negative
NaN
Infinity
non-string
```

### Bucket liquidity

Accept:

```text
0
positive integer
positive finite JSON float
```

Reject:

```text
bool
negative
NaN
Infinity
string
null
```

### Order preservation

Supply multiple buckets in intentionally non-monotonic order.

Assert output preserves the provider array order exactly.

Do not sort the expectation.

### Ignored fields

Supply malformed values for unretained fields such as:

```text
top-level time
status
closeoutBid
closeoutAsk
quoteHomeConversionFactors
unitsAvailable
```

and prove they do not invalidate a valid retained observation.

### Semantic boundary

Verify by test or inspection that the pricing module does not import or construct:

```text
backend.risk.service.ExecutableQuote
```

### Request failures

Do not duplicate the complete shared requester status/retry suite.

Pricing tests need only enough evidence to prove:

- correct endpoint;
- correct query;
- account binding;
- propagation of safe requester failures.

## Explicitly out of scope

Do not implement:

- executable quote construction;
- top-of-book selection;
- LONG/SHORT quote selection;
- price-depth consumption;
- requested-quantity pricing;
- cumulative liquidity;
- VWAP;
- spread;
- mid;
- closeout fallback;
- price freshness/staleness policy;
- market-hours policy;
- `since`;
- polling;
- streaming;
- heartbeat handling;
- current-price cache;
- persistence;
- historical data conversion;
- Risk integration;
- runtime integration;
- Order submission;
- Order cancellation;
- Position modification;
- reconciliation;
- Account Changes;
- Strategy evaluation;
- sizing;
- protection logic;
- PAPER activation;
- PAPER 01G or later work;
- LIVE;
- generalized broker architecture.

If any deferred capability appears necessary during BUILD, stop and return the concrete blocker rather than expanding the workstream.

## Approval gate

This workstream is currently planning-only.

The required lifecycle is:

```text
PLAN
→ developer feedback
→ PLAN reconciliation
→ explicit developer approval
→ GIT START
→ create tasks/
→ create T001
→ BUILD
→ focused VALIDATE
→ REVIEW
→ merge approval
```

Do not create or dispatch a BUILD task before explicit approval.
