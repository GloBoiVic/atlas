# PLAN — PAPER 01E OANDA Practice Pending Order Identity Inventory

## Workstream state

- **Workstream:** `paper-01e-oanda-practice-pending-order-identity-inventory`
- **Outcome:** one explicitly configured and account-validated OANDA Practice account → one read-only `/pendingOrders` observation → immutable normalized provider pending-Order identity inventory.
- **Classification:** `Feature`. This is a bounded provider-observation capability with financial-domain adjacency, but it is read-only, non-persistent, non-capital-capable, and does not change shared request infrastructure, Risk, runtime, execution, accounting, reconciliation, or broker authority. `ARCHITECTURE.md` is not required; the contract is narrow and follows the closed 01A–01D provider-observation pattern.
- **Base:** `main` at `43356fd3706271d10be77e54bafce434da91c112`.
- **Branch:** `solo/paper-01e-oanda-practice-pending-order-identity-inventory`.
- **Base SHA:** `43356fd3706271d10be77e54bafce434da91c112`.
- **Task:** `T001` — `DONE`.
- **Phase:** `COMPLETED`.
- **Next action:** none; workstream closed after GIT END.
- **Approval:** terminal closure approved by developer; fast-forward merged into `main`.
- **Architecture:** not required for this Feature classification.
- **Concerns:** the result is provider Order identity/type/state only. It must not be confused with an Atlas execution Order or treated as exposure, ownership, intent, reconciliation, or permission to act.

## Existing foundation and exact gap

PAPER 01A–01D on current `main` provide:

- explicit `Settings.oanda_account_id` selection and validation through the configured account's read-only `/summary` response;
- immutable `OandaPracticeAccountIdentity` bound to the explicitly selected Practice account;
- account-summary facts including the provider-reported pending-order count, without making that count an inventory;
- immutable provider-specific open Trade inventory from `/openTrades`;
- immutable provider-specific open Position inventory from `/openPositions`;
- fixed OANDA Practice routing, bounded timeouts, authenticated GETs, bounded same-GET retries, `Retry-After`, client ownership, status classification, invalid-JSON handling, and sanitized request errors;
- shared OANDA provider primitive parsing for numerical transaction IDs, finite decimal strings, and provider instrument strings;
- deterministic provider inventory normalization and exact-identity duplicate rejection in the existing Trade and Position seams;
- no PAPER persistence, runtime authority, Risk integration, reconciliation, Atlas broker execution, or broker mutation.

The merged OANDA read-only observation infrastructure refactor now owns the demonstrated common mechanics in:

```text id="3w21cc"
backend/integrations/oanda/request.py
backend/integrations/oanda/primitives.py
```

`OandaObservationRequester` performs safe authenticated GET/JSON behavior without knowing the endpoint's domain.

The owning provider module remains responsible for:

- its local endpoint path;
- account-ID quoting;
- response shape;
- provider-domain normalization;
- duplicate handling;
- deterministic ordering;
- provider semantics.

The exact gap is that Atlas cannot independently observe which provider Orders OANDA currently reports as pending while preserving each provider Order's identity, pending-capable type, and pending state.

PAPER 01E closes only:

```text id="sulzz0"
validated Practice identity
    → GET /v3/accounts/{accountID}/pendingOrders
    → common provider pending-Order envelope only
    → immutable pending provider-Order identity inventory
```

It does not turn the observation into:

- an Atlas `backend.execution.contract.Order`;
- an Atlas Order request;
- Strategy intent;
- Fill;
- Position change;
- exposure;
- ownership;
- reconciliation state;
- entry/protection interpretation;
- cancellation;
- replacement;
- submission;
- other broker mutation.

## Classification and architecture decision

This is `Feature`, not `Critical`, because the approved slice adds one local read-only provider module and deterministic tests while reusing the already-frozen request and primitive seams.

It does not alter those shared seams or introduce:

- persistence;
- financial authority;
- broker mutation;
- runtime behavior;
- cross-cutting execution semantics.

No `ARCHITECTURE.md` is required.

The contract, invariants, invalid examples, and required tests are frozen in this PLAN and will be implemented only after developer approval.

## Provider contract and endpoint choice

The official OANDA REST v20 contracts used for this plan define:

- `GET /v3/accounts/{accountID}/pendingOrders` as the endpoint that lists pending Orders in an Account;
- response fields `orders: Array[Order]` and top-level `lastTransactionID`;
- the polymorphic OANDA Order definitions;
- provider `OrderID`;
- general `OrderType`;
- `CancellableOrderType`;
- `OrderState`.

The selected endpoint is exactly:

```text id="mgcabd"
GET /v3/accounts/{accountID}/pendingOrders
```

It returns:

```text id="4ze8sm"
orders: Array[Order]
lastTransactionID
```

Do not use:

```text id="t9gl0b"
GET /v3/accounts/{accountID}/orders
GET /v3/accounts/{accountID}/orders/{orderSpecifier}
```

Do not use the full-account endpoint.

Do not use:

- transaction history;
- Account Changes;
- single-Order lookup;
- a mutating endpoint.

The settings-facing flow remains two independent observations:

```text id="uythpw"
/summary
→ establish explicitly validated Practice account identity

/pendingOrders
→ independently observe pending provider Orders
```

The reads are not atomic and may represent different broker transaction frontiers.

The pending-Order inventory is normalized only from the successful `/pendingOrders` response.

It does not consume or compare:

- PAPER 01B pending-order count;
- PAPER 01C Trades;
- PAPER 01D Positions;
- any prior transaction ID.

The request uses the already-proven authenticated OANDA Practice GET behavior with no query parameters.

On a first-attempt successful read:

```text id="fviuiw"
exactly one /pendingOrders GET
```

occurs.

Existing bounded retry behavior may repeat only that same GET after transient failure.

The owning module supplies the static requester error subject:

```text id="ulwzqy"
"pending Orders"
```

solely to preserve sanitized request wording.

`request.py` is not modified into an Order registry or endpoint registry.

## Smallest immutable normalized contract

Add the adjacent provider-specific module:

```text id="6kwz9q"
backend/integrations/oanda/orders.py
```

with frozen, slotted values:

```text id="q8u7ak"
OandaPracticePendingOrder
  provider_order_id: str
  provider_order_type: Literal[
    "LIMIT",
    "STOP",
    "MARKET_IF_TOUCHED",
    "TAKE_PROFIT",
    "STOP_LOSS",
    "GUARANTEED_STOP_LOSS",
    "TRAILING_STOP_LOSS",
  ]
  state: Literal["PENDING"]

OandaPracticePendingOrderInventory
  identity: OandaPracticeAccountIdentity
  orders: tuple[OandaPracticePendingOrder, ...]
  last_transaction_id: str
```

The expected reader and settings-facing helper are:

```text id="qbn0bv"
OandaPracticePendingOrderReader
read_oanda_practice_pending_order_inventory(...)
```

The provider-specific names are intentional.

An observed OANDA Order is not the Atlas execution `Order` contract despite sharing the word “Order.”

The module must not import:

```text id="82khae"
backend.execution.contract.Order
```

or any Atlas execution type.

Retain exactly these facts:

| Fact                  | Why PAPER 01E needs it now                                                                                      |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| `identity`            | Attaches the observation to the explicitly configured and server-validated Practice account.                    |
| `provider_order_id`   | Preserves which OANDA-assigned provider Order was reported and supplies exact identity for duplicate detection. |
| `provider_order_type` | Preserves the documented pending-capable provider type label without interpreting what the Order will do.       |
| `state`               | Preserves and verifies the endpoint's pending-state observation; it must be exactly `PENDING`.                  |
| `last_transaction_id` | Preserves provenance for this `/pendingOrders` response only.                                                   |

`createTime` is explicitly excluded.

Chronology is not required to answer:

> Which provider Orders are currently pending and what pending-capable provider type does each report?

Excluding creation time avoids introducing timestamp and lifecycle semantics that 01E does not need.

## Polymorphic Order boundary and pending-capable type policy

OANDA's `Order` is polymorphic.

The general OANDA `OrderType` set currently includes:

```text id="lru6vc"
MARKET
LIMIT
STOP
MARKET_IF_TOUCHED
TAKE_PROFIT
STOP_LOSS
GUARANTEED_STOP_LOSS
TRAILING_STOP_LOSS
FIXED_PRICE
```

However PAPER 01E is not reading general Order history.

It is reading:

```text id="imjztl"
/pendingOrders
```

OANDA separately defines the pending/cancellable Order-type family as:

```text id="fdptvw"
LIMIT
STOP
MARKET_IF_TOUCHED
TAKE_PROFIT
STOP_LOSS
GUARANTEED_STOP_LOSS
TRAILING_STOP_LOSS
```

`MARKET` and `FIXED_PRICE` Orders are documented as immediate-fill Order forms and are not part of `CancellableOrderType`.

Therefore the PAPER 01E common envelope accepts exactly the seven documented pending-capable provider types above.

A `/pendingOrders` item reporting:

```text id="zfk5ko"
MARKET
FIXED_PRICE
```

fails closed as contradictory provider state for this endpoint.

This is an endpoint-level consistency rule only.

It does not interpret:

- entry semantics;
- protection semantics;
- trigger semantics;
- price semantics;
- Trade linkage;
- Position effects.

### Unknown future types

A syntactically valid but unknown future provider type fails the entire observation closed.

It is never:

- silently dropped;
- mapped to a known type;
- treated as operationally supported;
- returned as if Atlas understands its semantics.

This preserves uncertainty explicitly.

Recognizing one of the seven documented labels is also **not operational support**.

It does not authorize Atlas to:

- create;
- cancel;
- replace;
- interpret;
- correlate;
- own;
- execute

an Order of that type.

## No type-specific normalization

PAPER 01E does not construct a union of concrete OANDA Order models.

It does not create type-specific classes.

Ignore all concrete/type-specific Order facts, including as applicable:

```text id="8uj3oc"
instrument
units
price
priceBound
timeInForce
gtdTime
positionFill
triggerCondition
tradeID
clientTradeID
distance
takeProfitOnFill
stopLossOnFill
guaranteedStopLossOnFill
trailingStopLossOnFill
tradeClientExtensions
clientExtensions
fillingTransactionID
filledTime
tradeOpenedID
tradeReducedID
tradeClosedIDs
cancellingTransactionID
cancelledTime
replacesOrderID
replacedByOrderID
createTime
```

This list does not authorize validation of those fields.

If unretained fields are present:

- ignore them;
- do not expose them;
- do not correlate them;
- do not validate them merely for PAPER 01E.

Malformed ignored fields do not make a response invalid merely because 01E does not interpret them.

Missing type-specific fields also do not make the common-envelope observation invalid.

Only the approved retained common facts are normalized.

## Order-ID normalization and deterministic ordering

`provider_order_id` preserves the exact provider-assigned raw string.

OANDA documents `OrderID` as the string representation of a positive integer derived from the Transaction that created the Order.

The local PAPER 01E validation is:

1. exact `str`;
2. decimal digits only;
3. numeric meaning must be positive/nonzero;
4. raw provider representation is preserved.

Do not store the identity as a Python `int`.

Do not replace it with:

- `ClientOrderID`;
- `OrderSpecifier`;
- Atlas UUID;
- Atlas Order ID.

All-zero values fail:

```text id="lnyq62"
"0"
"00"
"000"
```

Positive leading-zero representations such as:

```text id="owdyj4"
"0007"
```

remain accepted unless current provider evidence explicitly proves they are impossible.

The raw string remains unchanged.

### Duplicate semantics

Exact duplicate raw Order IDs fail closed whether the remaining provider payloads are:

- identical;
- conflicting.

Do not:

- merge;
- deduplicate;
- first-win;
- last-win.

Different raw positive identifiers remain distinct observations.

No partial inventory may be returned if a later item fails.

### Deterministic ordering

Provider array order is not an Atlas ordering contract.

After duplicate detection, normalize the immutable tuple using a total raw-preserving numeric ordering equivalent to:

```text id="uuw68h"
numeric magnitude
→ significant digits
→ raw provider Order ID
```

Implement this without storing the ID as an integer.

A safe string key is:

```text id="cfff18"
significant = provider_order_id.lstrip("0")

(
  len(significant),
  significant,
  provider_order_id,
)
```

Because all-zero IDs are invalid, `significant` is nonempty for accepted identities.

Thus:

```text id="7n7wxe"
"01"
"1"
```

remain distinct but sort deterministically independent of provider response order.

The raw tie-breaker prevents the permutation defect previously found during PAPER 01C.

This ordering exists only for:

- deterministic equality;
- deterministic tests;
- future observation comparison.

It does not imply:

- chronology;
- broker priority;
- execution priority;
- ownership;
- reconciliation order.

## Pending-state normalization

OANDA `OrderState` includes:

```text id="aikhl0"
PENDING
FILLED
TRIGGERED
CANCELLED
```

The selected endpoint is specifically:

```text id="6brknq"
/pendingOrders
```

Therefore every returned item must report exactly:

```text id="rqt3xh"
state == "PENDING"
```

Accept only an exact string:

```text id="2dozd2"
PENDING
```

Fail closed on:

```text id="c6gwip"
missing state
non-string state
unknown state
FILLED
TRIGGERED
CANCELLED
```

A contradictory non-pending item must not be:

- silently filtered;
- moved into history;
- normalized as valid;
- resolved by another provider request.

The retained state remains a provider observation only.

It is not:

- Atlas execution lifecycle state;
- Fill result;
- Position change;
- permission to act.

## Response normalization and failure behavior

A successful decoded provider result must be a JSON object containing:

```text id="7atbcy"
orders
lastTransactionID
```

`orders` must be a list.

Each item must be an object.

Each retained Order envelope must provide valid:

```text id="8fzwgl"
id
type
state
```

Top-level:

```text id="aawt1y"
lastTransactionID
```

uses the existing shared OANDA transaction-ID primitive.

The owning module wraps provider-domain normalization failures in:

```text id="ysvx47"
OandaPendingOrderNormalizationError
```

or an equivalently narrow pending-Order-specific normalization error name if current package naming convention requires it.

Fail closed on:

- missing/blank token through the shared request seam;
- invalid timeout configuration;
- invalid reader identity;
- invalid JSON;
- non-object top-level JSON;
- missing/non-list `orders`;
- non-object Order items;
- missing/non-string/non-digit/all-zero Order ID;
- exact duplicate raw Order ID;
- missing/non-string provider Order type;
- `MARKET` or `FIXED_PRICE` in `/pendingOrders`;
- unknown future provider type;
- missing/non-string/non-`PENDING` state;
- malformed top-level transaction provenance;
- authorization/provider rejection;
- transport failure;
- exhausted bounded retries.

No partial inventory is returned if any item fails.

Errors remain sanitized:

- no API token;
- no provider response body;
- no secret-bearing transport exception.

Request failures reuse the existing:

```text id="6sfn4u"
OandaObservationRequester
```

and current OANDA request error family.

## Empty inventory and provenance

A valid response containing:

```text id="43d6vp"
orders: []
```

with valid transaction provenance succeeds with:

```text id="k5s72m"
orders == ()
```

This means only:

> OANDA reported no pending Orders in this `/pendingOrders` observation.

It does not prove:

- PAPER 01B `pending_order_count` was zero at the same frontier;
- no Trade protection exists at another observation time;
- no exposure exists;
- the account is reconciled;
- PAPER is safe to activate.

`last_transaction_id` is provider transaction provenance for this response only.

It is not:

- a reconciliation cursor;
- transaction replay state;
- Account Changes cursor;
- persistence key;
- restart state;
- proof of shared frontier;
- mutation authority.

It is not persisted or advanced.

## No cross-read reconciliation

PAPER 01E does not enforce:

```text id="3tx1ki"
01B pending_order_count == len(01E orders)
```

It does not compare:

```text id="t6ezab"
01B lastTransactionID
01C lastTransactionID
01D lastTransactionID
01E lastTransactionID
```

It does not correlate:

```text id="kucq0k"
01E tradeID
↔
01C provider Trade IDs
```

or:

```text id="68um3b"
01E instrument
↔
01D provider Positions
```

PAPER 01E deliberately does not retain:

```text id="c7ub7g"
tradeID
instrument
```

for those purposes.

Account summary, Trade, Position, and pending Order reads may occur at different provider transaction frontiers.

Reconciliation remains deferred.

## Atlas execution boundary

Current Atlas:

```text id="aoc63f"
backend.execution.contract.Order
```

has Atlas execution semantics and is not the same object as an observed OANDA Order.

The PAPER 01E result must therefore:

- remain in `backend.integrations.oanda.orders`;
- preserve provider Order identity as a provider string;
- preserve only the approved pending-capable provider type label;
- preserve `PENDING` provider state;
- never import or instantiate Atlas execution `Order`;
- never construct a Fill;
- never construct an Atlas Position;
- never construct an Atlas Trade;
- never derive direction;
- never derive quantity;
- never derive requested price;
- never infer Strategy intent;
- never infer ownership;
- never infer safety;
- never infer protection role;
- never infer trigger behavior;
- never infer operational support.

The shared word “Order” creates no semantic authority between the provider and Atlas contracts.

## Request-code reuse decision

`orders.py` must reuse without modification:

```text id="djhmby"
OandaObservationRequester
```

for:

- token validation;
- timeout construction;
- request headers;
- fixed Practice URL;
- client ownership;
- retry policy;
- `Retry-After`;
- status classification;
- invalid-JSON handling.

Reuse:

```text id="n87x7b"
parse_transaction_id
```

for top-level response provenance.

Reuse:

```text id="m2hfz2"
bind_oanda_practice_account
```

for explicit Practice-account validation.

Reuse existing:

- Settings token;
- Settings timeout values;
- sanitized OANDA request errors.

The positive Order-ID rule remains local because it is Order-specific.

Do not modify:

```text id="opngyk"
request.py
primitives.py
source.py
account.py
trades.py
positions.py
```

for this slice.

If BUILD discovers that the recently frozen shared request/primitive seams must change, stop:

```text id="n18bop"
BLOCKED
```

and return for developer re-scoping.

Endpoint construction remains local to `orders.py`:

```text id="u6pfhc"
/v3/accounts/{validated provider_account_id}/pendingOrders
```

Account-ID quoting remains local.

No query parameters are added.

No endpoint registry is introduced.

## Persistence decision

**No durable Atlas persistence is required.**

An immutable in-memory provider observation tied to a validated Practice identity fully satisfies PAPER 01E.

Do not persist pending Orders for:

- reconciliation;
- ownership;
- restart recovery;
- audit;
- runtime supervision;
- cancellation;
- replacement;
- PAPER activation.

No:

- database;
- cache;
- file;
- repository;
- migration;
- durable runtime state;
- API;
- UI

is required.

If BUILD discovers a concrete persistence requirement, stop as `BLOCKED` for developer re-scoping.

## Implementation seams and task

Expected product/test changes are limited to:

| File                                                                                                                                                     | Planned change                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/integrations/oanda/orders.py`                                                                                                                   | Add provider-specific frozen/slotted pending-Order and inventory contracts, seven-type pending-capable common-envelope normalization, exact raw Order-ID validation, total deterministic ordering, strict `PENDING` enforcement, `/pendingOrders` reader, transaction provenance, and settings-facing helper.                                                                                                                |
| `backend/integrations/oanda/__init__.py`                                                                                                                 | Export only the new pending-Order normalization error, provider contracts, reader, and settings-facing helper.                                                                                                                                                                                                                                                                                                               |
| `backend/tests/integrations/test_oanda_orders.py`                                                                                                        | Add deterministic injected-HTTP tests for account binding, exact endpoint/request behavior, retained field set, ignored type-specific fields, seven valid pending-capable types, contradictory `MARKET`/`FIXED_PRICE`, unknown future types, Order-ID validation, leading-zero total ordering, duplicates, pending-state contradiction, empty inventory, provenance, retries, sanitization, immutability, and configuration. |
| `dispatch/workstreams/paper-01e-oanda-practice-pending-order-identity-inventory/tasks/T001-paper-01e-oanda-practice-pending-order-identity-inventory.md` | Preserve the BUILD assignment and completion receipt.                                                                                                                                                                                                                                                                                                                                                                        |

Existing OANDA account, Trade, Position, request, primitive, and source modules have no planned product changes.

Existing focused OANDA tests are regression evidence only.

No changes are planned to:

```text id="0vhl8q"
backend/integrations/oanda/request.py
backend/integrations/oanda/primitives.py
backend/integrations/oanda/source.py
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/execution/
backend/domain/trading.py
backend/persistence/
backend/risk/
backend/runtime/
backend/api/
frontend/
```

No migration is expected.

## Acceptance criteria

1. The settings-facing helper first validates the explicitly configured Practice account through the existing `/summary` binding, then independently performs exactly one account-specific read-only:

   ```text
   GET /v3/accounts/{accountID}/pendingOrders
   ```

   on first-attempt success.

2. The request is an authenticated GET to the fixed Practice host using the established headers and no query parameters. Bounded retries repeat only the same GET after transient failure. No request infrastructure is reimplemented.

3. A valid response becomes a frozen, slotted `OandaPracticePendingOrderInventory` containing:

   - validated account identity;
   - deterministic immutable Order tuple;
   - response-local `last_transaction_id`.

4. Each normalized pending Order exposes exactly:

   - `provider_order_id`;
   - `provider_order_type`;
   - `state`.

   No `createTime` or type-specific field is retained.

5. Provider Order IDs are exact digit-only strings whose numeric meaning is positive/nonzero. Raw representation is preserved and never stored as Python integer identity.

6. All-zero, malformed, missing, or non-string Order IDs fail closed.

7. Exact duplicate raw provider Order IDs fail closed without merge, deduplication, first-win, last-win, or partial output.

8. Provider array order cannot affect normalized inventory equality. Order tuples use total deterministic numeric-magnitude/significant-digit/raw-ID ordering, including leading-zero tie-breaking.

9. `provider_order_type` accepts exactly:

   ```text
   LIMIT
   STOP
   MARKET_IF_TOUCHED
   TAKE_PROFIT
   STOP_LOSS
   GUARANTEED_STOP_LOSS
   TRAILING_STOP_LOSS
   ```

10. `/pendingOrders` items reporting `MARKET` or `FIXED_PRICE` fail closed as contradictory to the current documented pending-capable Order-type contract.

11. Unknown future provider types fail the entire observation closed and are never silently hidden, remapped, or treated as understood.

12. Recognized provider type labels remain observational labels only and do not authorize any type-specific operation.

13. Every returned item must report exact state:

```text
PENDING
```

Missing, malformed, unknown, `FILLED`, `TRIGGERED`, or `CANCELLED` state fails closed.

14. Type-specific and other unretained fields are ignored, not exposed, and not validated. Malformed ignored fields or missing type-specific fields do not invalidate the approved common envelope.

15. A valid empty list returns an explicit immutable:

```text
orders == ()
```

inventory.

16. A valid top-level numerical-string `lastTransactionID` is preserved as response-local provenance. Malformed provenance fails closed.

17. PAPER 01B/01C/01D counts, inventories, provider IDs, and transaction IDs are never reconciled with PAPER 01E.

18. Missing/blank token, invalid timeout, invalid reader identity, malformed JSON, malformed response/list/item/common field, provider rejection, transport failure, and exhausted retries fail closed with sanitized errors and no partial inventory.

19. The result remains separate from `backend.execution.contract.Order`. No Atlas Order, Strategy intent, Fill, Position, Trade, ownership, exposure, accounting, Risk, runtime authority, persistence, reconciliation, or broker mutation is introduced.

20. PAPER 01A–01D behavior remains unchanged.

21. No product change is made to the frozen shared request/primitive seams or existing provider account/Trade/Position/source modules.

## Validation strategy

BUILD will first run the new focused tests with current OANDA regression tests:

```bash id="ofm568"
uv run pytest \
  backend/tests/integrations/test_oanda_orders.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_request.py \
  backend/tests/integrations/test_oanda_primitives.py \
  backend/tests/integrations/test_oanda_source.py
```

Then targeted checks:

```bash id="9sllzd"
uv run ruff format --check \
  backend/integrations/oanda/orders.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_orders.py

uv run ruff check \
  backend/integrations/oanda/orders.py \
  backend/integrations/oanda/__init__.py \
  backend/tests/integrations/test_oanda_orders.py

uv run pyright \
  backend/integrations/oanda/orders.py \
  backend/tests/integrations/test_oanda_orders.py

uv run pytest -m "not integration and not external"

git diff --check
```

Independent VALIDATE will inspect and rerun evidence for:

- exact `/summary` then `/pendingOrders` sequencing;
- explicit account binding;
- exact Practice endpoint;
- GET method;
- headers;
- no-query behavior;
- first-attempt request count;
- bounded same-GET retries;
- reuse of shared requester;
- frozen/slotted field sets;
- provider/Atlas semantic separation;
- all seven accepted pending-capable provider types;
- `MARKET` and `FIXED_PRICE` contradiction failures;
- unknown future-type failure;
- ignored malformed type-specific fields;
- absent type-specific fields;
- exact positive raw Order-ID validation;
- duplicate rejection;
- leading-zero permutation-invariant ordering;
- strict `PENDING` enforcement;
- contradictory-state failure;
- empty inventory;
- response-local transaction provenance;
- malformed response/no-partial-output behavior;
- sanitization;
- absence of cross-read reconciliation;
- absence of persistence;
- absence of mutation;
- absence of execution;
- absence of Risk/runtime/API/UI behavior.

VALIDATE will rerun:

- focused OANDA suite;
- targeted quality checks;
- non-integration/non-external suite;
- `git diff --check`.

No Alembic/database, browser, or credentialed external OANDA check is required because this slice is:

- non-persistent;
- non-UI;
- deterministically testable through injected HTTP.

## Explicitly out of scope

This workstream does not implement or authorize:

- Order creation;
- Order cancellation;
- Order replacement;
- Order lookup by ID;
- full/history Order retrieval;
- `/orders` retrieval;
- any provider endpoint other than `/pendingOrders` after account binding;
- entry-Order interpretation;
- protection-Order interpretation;
- instrument interpretation;
- units or direction;
- price semantics;
- price bounds;
- time-in-force;
- GTD expiry;
- trigger conditions;
- position-fill semantics;
- Trade linkage;
- Trade ↔ Order correlation;
- Position ↔ Order correlation;
- Order ownership;
- Atlas Order construction;
- Atlas execution integration;
- Fill construction;
- Position changes;
- accounting;
- exposure inference;
- transaction history;
- Account Changes;
- transaction replay;
- transaction cursors;
- shared-frontier claims;
- persistence;
- audit;
- restart recovery;
- runtime supervision;
- Risk;
- runtime;
- Deployment;
- PAPER activation;
- Strategy evaluation;
- sizing;
- protection;
- live pricing;
- quotes;
- market data;
- API/UI;
- generalized broker architecture;
- future provider-type abstraction;
- PAPER 01F or later work;
- LIVE.

If any deferred capability appears necessary during BUILD, stop and surface the concrete blocker for developer re-scoping approval rather than expanding this workstream.
