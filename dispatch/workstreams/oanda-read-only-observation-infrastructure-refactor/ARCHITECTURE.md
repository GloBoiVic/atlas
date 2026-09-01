# ARCHITECTURE — OANDA Read-only Observation Infrastructure Refactor

## Status

`FROZEN_PENDING_DEVELOPER_APPROVAL`

This artifact freezes the smallest OANDA-local request and provider-primitive seams.

It is reconciled into `PLAN.md`.

It is not implementation approval, branch approval, or permission to create capital-capable behavior.

Explicit developer approval is required before GIT START or BUILD.

## Architectural decision

Extract only mechanics that are semantically identical in the existing Practice account-summary, open-Trade, and open-Position readers:

```text
account.py ─┐
trades.py  ─┼─> request.py       authenticated GET / retry / JSON mechanics
positions.py┘

account.py ─┐
trades.py  ─┼─> primitives.py    provider-format parsing only
positions.py┘
```

The owning modules continue to own:

- endpoint paths;
- account-ID quoting;
- account binding;
- provider response-shape checks;
- domain-specific normalization errors;
- semantic validation;
- ordering;
- duplicate detection;
- immutable provider observations.

This is a behavior-preserving refactor.

It adds no:

- endpoint;
- provider state;
- persistence;
- Risk behavior;
- execution behavior;
- runtime behavior;
- API/UI behavior;
- PAPER capability;
- LIVE capability.

## Frozen request seam

Add the internal module:

```text
backend/integrations/oanda/request.py
```

It is not exported from:

```text
backend.integrations.oanda
```

### Exact internal contract

```python
from typing import Any

def validate_token(token: SecretStr | None) -> None: ...

class OandaObservationRequester:
    def __init__(
        self,
        token: SecretStr | None,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
    ) -> None: ...

    def get_json(
        self,
        path: str,
        *,
        error_subject: str,
    ) -> Any: ...
```

`error_subject` exists only to preserve the current sanitized request-level wording.

Current static caller-owned subjects are:

```text
account.py   → "account"
trades.py    → "open Trades"
positions.py → "open Positions"
```

Do not define:

```python
Literal["account", "open Trades", "open Positions"]
```

or any equivalent domain registry in the requester.

The requester must not inspect or branch on `error_subject` except to interpolate the existing safe error text.

The subject must be a module-owned static constant.

It must not originate from:

- provider payload;
- settings;
- API/UI;
- user input;
- broker response.

The requester does not know whether it is reading an Account, Trade, or Position.

It only knows how to perform the currently proven safe OANDA Practice GET mechanics.

### Configuration and timeout behavior

The constructor rejects a connect timeout unless:

```text
0 < connect_timeout_seconds <= 30
```

and a read timeout unless:

```text
0 < read_timeout_seconds <= 120
```

with exactly:

```text
OandaConfigurationError("OANDA timeouts are outside bounded limits")
```

The constructor builds one:

```python
httpx.Timeout(
    read=read_timeout_seconds,
    connect=connect_timeout_seconds,
    write=connect_timeout_seconds,
    pool=connect_timeout_seconds,
)
```

This preserves the current reader-construction behavior.

### Token validation

`validate_token` rejects:

```text
None
blank after .strip()
```

with exactly:

```text
OandaConfigurationError("OANDA API token is required")
```

It must not:

- log the token;
- include the token in an exception;
- normalize the token;
- mutate the token.

`get_json` performs token validation before:

- creating an owned client;
- performing network activity.

Account validation additionally calls the same shared `validate_token` before its local account-ID validation so the current error precedence remains:

```text
timeout validation
→ token validation
→ configured account-ID validation
→ network
```

Repeated invocation of the same pure token validator is acceptable where necessary to preserve this ordering.

### Client ownership

With no injected client, `get_json` creates exactly one client for the call:

```python
httpx.Client(
    transport=transport,
    timeout=self._timeout,
    base_url=OANDA_PRACTICE_BASE_URL,
    trust_env=False,
)
```

It closes that internally owned client exactly once on:

- success;
- normalization-independent request failure;
- transport exhaustion;
- provider rejection;
- invalid JSON.

`OANDA_PRACTICE_BASE_URL` retains its existing owner/export in `source.py`.

`request.py` may import it but must not redefine it.

With an injected client:

- the injected client is used as-is;
- the injected client receives the existing per-request timeout;
- the requester never closes it;
- separately supplied `transport` does not replace or wrap it.

This preserves the current deterministic `httpx.MockTransport` seam.

### Request boundary

The owning module constructs the local provider path.

Examples:

```text
/v3/accounts/{account_id}/summary
/v3/accounts/{account_id}/openTrades
/v3/accounts/{account_id}/openPositions
```

The requester accepts that already-constructed path.

It must not accept separate caller-supplied:

- HTTP method;
- base URL;
- account ID;
- query parameters;
- provider environment;
- broker type.

Every current observation request performs an authenticated:

```text
GET
```

to:

```python
f"{OANDA_PRACTICE_BASE_URL}{path}"
```

using exactly these application headers:

```python
{
    "Authorization": f"Bearer {token.get_secret_value()}",
    "Accept-Datetime-Format": "RFC3339",
}
```

and no query parameters.

The requester does not infer or validate endpoint semantics.

The caller remains responsible for which already-approved path is used.

### Successful response behavior

For a successful 2xx response:

1. call `response.json()` exactly once;
2. return the decoded result as `Any`.

The requester deliberately does not require the decoded result to be an object.

Each owning module retains its current:

```text
isinstance(payload, dict)
```

check and domain-specific non-object normalization error.

This preserves the distinction:

```text
transport / HTTP / JSON failure
        ↓
request error

valid JSON but wrong provider domain shape
        ↓
domain normalization error
```

### Invalid JSON

`ValueError` from `response.json()` raises:

```text
OandaRequestError
```

on the current attempt.

Invalid JSON is not retried.

No raw provider body is retained or surfaced.

The exact message is generated from the static `error_subject`:

```text
"OANDA returned invalid {error_subject} JSON"
```

Therefore the current messages remain:

```text
OANDA returned invalid account JSON
OANDA returned invalid open Trades JSON
OANDA returned invalid open Positions JSON
```

## Frozen retry policy

The following constants live once in:

```text
request.py
```

and remain non-configurable:

```python
_MAX_ATTEMPTS = 3
_RETRY_AFTER_CAP_SECONDS = 30.0
_BACKOFF_SECONDS = (0.25, 0.5)
```

### Attempt accounting

Every:

```text
client.get(...)
```

counts as one attempt.

Attempt numbering starts at:

```text
1
```

and never exceeds:

```text
3
```

### Transport failures

For:

```text
httpx.RequestError
```

on attempts one and two:

```text
sleep 0.25
sleep 0.5
```

respectively, then retry the same GET.

On attempt three raise:

```python
OandaRequestError(
    None,
    3,
    f"OANDA {error_subject} request failed after retries",
)
```

The underlying exception text must not escape.

### Authentication rejection

For:

```text
401
403
```

raise immediately:

```python
OandaAuthError(
    status,
    attempt,
    "OANDA authorization failed",
)
```

No retry.

### Deterministic request rejection

For:

```text
400
404
```

raise immediately:

```python
OandaRequestError(
    status,
    attempt,
    f"OANDA {error_subject} request was rejected",
)
```

No retry.

### Transient provider responses

Retry:

```text
408
429
5xx
```

through the third attempt.

On final exhaustion raise:

```python
OandaRequestError(
    status,
    attempt,
    f"OANDA {error_subject} request failed after retries",
)
```

### Retry-After

For a retryable provider response, parse `Retry-After` exactly as the current account/Trade/Position readers do.

Accepted numeric value:

- parseable as float;
- finite;
- nonnegative.

Cap at:

```text
30 seconds
```

Otherwise attempt HTTP-date parsing.

An HTTP date is usable only when:

- timezone-aware;
- parseable;
- future/nonnegative relative to current UTC;
- finite.

Cap the derived delay at:

```text
30 seconds
```

Use fallback backoff for:

- missing header;
- malformed numeric/date value;
- naive date;
- past date;
- non-finite result;
- negative result;
- resulting delay `<= 0`.

Therefore:

```text
Retry-After: 0
```

uses the current fallback rather than creating an immediate zero-delay retry.

The patchable sleep point moves to:

```text
backend.integrations.oanda.request.sleep
```

for deterministic tests.

No test may wait for actual provider backoff.

### Other non-2xx responses

Every other non-2xx response raises immediately:

```python
OandaRequestError(
    status,
    attempt,
    f"OANDA {error_subject} request failed",
)
```

No response body is included.

### Exact message preservation

The generic formatting above must reproduce these existing messages exactly:

| outcome                    | account                                      | open Trades                                      | open Positions                                      |
| -------------------------- | -------------------------------------------- | ------------------------------------------------ | --------------------------------------------------- |
| invalid JSON               | `OANDA returned invalid account JSON`        | `OANDA returned invalid open Trades JSON`        | `OANDA returned invalid open Positions JSON`        |
| 400/404                    | `OANDA account request was rejected`         | `OANDA open Trades request was rejected`         | `OANDA open Positions request was rejected`         |
| retry/transport exhaustion | `OANDA account request failed after retries` | `OANDA open Trades request failed after retries` | `OANDA open Positions request failed after retries` |
| other non-2xx              | `OANDA account request failed`               | `OANDA open Trades request failed`               | `OANDA open Positions request failed`               |

`OandaRequestError.status_code` and:

```text
attempts
```

retain their current meanings and values.

## Required call-site extraction

Each current observation reader constructs one:

```text
OandaObservationRequester
```

using its existing:

- token;
- injected client;
- injected transport;
- connect timeout;
- read timeout.

Endpoint construction remains in the owner:

```text
account.py
  /v3/accounts/{quoted account_id}/summary

trades.py
  /v3/accounts/{quoted provider_account_id}/openTrades

positions.py
  /v3/accounts/{quoted provider_account_id}/openPositions
```

Static error subjects remain in the owner:

```text
account
open Trades
open Positions
```

After `get_json(...)`, each owner retains:

- current non-object response check;
- exact domain-specific non-object message;
- `Mapping[str, Any]` cast;
- provider payload normalization.

No domain payload normalization moves into:

```text
request.py
```

### Account binding sequencing

The Trade and Position settings helpers continue:

```text
configured settings
    ↓
/summary
    ↓
validated OandaPracticeAccountIdentity
    ↓
independent provider observation
```

The refactor must not:

- remove `/summary` account validation;
- cache identity;
- combine responses;
- claim atomicity;
- compare transaction IDs;
- reconcile responses.

## Frozen provider-primitive seam

Add the internal module:

```text
backend/integrations/oanda/primitives.py
```

It is not exported by the package.

### Exact internal contract

```python
class OandaPrimitiveError(ValueError):
    ...

def parse_transaction_id(value: Any) -> str:
    ...

def parse_decimal(value: Any) -> Decimal:
    ...

def parse_instrument(value: Any) -> str:
    ...
```

The primitive parser:

- has no provider payload context;
- does not know field names;
- does not include the rejected input value in its error;
- raises only internal `OandaPrimitiveError` for invalid primitive representation.

The public reader paths must not leak `OandaPrimitiveError`.

Each owning module catches it and raises its existing domain-specific normalization error with the current domain wording.

## Transaction-ID primitive

`parse_transaction_id` accepts only an exact:

```text
str
```

matching:

```regex
[0-9]+
```

using full-match semantics.

Valid boundaries include:

```text
"0"
"000"
"1"
"001"
"999999"
```

Leading zeroes remain accepted.

Reject:

```text
None
42
""
"-1"
"+1"
"1.0"
" 1"
"1 "
```

This primitive does not determine whether a particular domain imposes additional semantics.

## Decimal primitive

`parse_decimal` accepts only an exact:

```text
str
```

that converts to a finite:

```text
Decimal
```

Valid examples include:

```text
"-100"
"0"
"0.0"
"1.25"
"1000000"
```

Reject:

```text
None
1
1.25
Decimal("1")
""
"abc"
"NaN"
"sNaN"
"Infinity"
"-Infinity"
```

The primitive does not impose:

- positivity;
- negativity;
- nonzero;
- price semantics;
- quantity semantics.

Those remain local.

Examples:

```text
Trade currentUnits
  parse_decimal
  then require != 0
```

```text
Position long.units
  parse_decimal
  then require >= 0
```

```text
Position averagePrice
  parse_decimal
  then require > 0
```

## Instrument primitive

`parse_instrument` accepts only an exact:

```text
str
```

matching the current regex:

```regex
[^\s_]+_[^\s_]+
```

using `fullmatch`.

Valid:

```text
EUR_USD
USD_CAD
XAU_USD
```

Reject:

```text
""
"EUR"
"_USD"
"EUR_"
"EUR_USD_EXTRA"
"EUR USD"
" EUR_USD"
"EUR_USD "
```

The provider string remains unchanged.

The primitive must not:

- case-fold;
- split into Atlas instrument enums;
- validate current Atlas support;
- filter unsupported instruments.

## Deliberately local primitives and semantics

Do not move into `primitives.py`:

- configured account-ID parser;
- positive Trade-ID parser;
- Trade-ID ordering;
- Trade RFC3339 timestamp parser;
- historical candle timestamp parser;
- account counts;
- account currency;
- positive prices;
- Trade states;
- Trade `currentUnits != 0`;
- Position side signs;
- Position exposed-side average-price rules;
- Position both-zero contradiction;
- duplicate detection;
- inventory ordering.

## Domain invariants

### Account

The explicit configured account remains the only account selected.

Account-specific normalization continues to own:

- account payload shape;
- returned account-ID equality;
- alias;
- USD currency;
- summary field selection;
- counts;
- top-level/nested transaction-ID consistency.

`OandaAccountNormalizationError` remains the public normalization failure.

### Trade

Trade normalization continues to own:

- positive/nonzero provider Trade ID;
- provider instrument;
- strict timezone-aware `openTime`;
- positive open price;
- signed nonzero `currentUnits`;
- accepted Trade state;
- unrealized P/L;
- duplicate provider Trade-ID rejection;
- deterministic Trade-ID ordering.

Multiple distinct Trades may have the same provider instrument.

For example:

```text
id="101" instrument="EUR_USD"
id="105" instrument="EUR_USD"
```

is valid.

The refactor must never introduce duplicate-instrument rejection for Trade inventories.

`OandaOpenTradeNormalizationError` remains the public normalization failure.

### Position

Position normalization continues to own:

- provider instrument;
- Position-level unrealized P/L;
- independent `long`;
- independent `short`;
- long units `>= 0`;
- short units `<= 0`;
- active-side average-price requirement;
- zero-side optional average price;
- both nonzero sides remaining valid;
- both sides zero failing closed;
- duplicate exact provider-instrument rejection;
- deterministic instrument ordering.

`OandaOpenPositionNormalizationError` remains the public normalization failure.

## Historical source boundary

`backend/integrations/oanda/source.py` remains outside the new observation request executor.

Historical candle behavior includes:

- windowed requests;
- query parameters;
- M1/M15 granularity;
- MID/BID/ASK selection;
- request diagnostics;
- session filtering;
- incomplete observations;
- historical timestamp rules;
- different transient response classification.

Its request loop must not be replaced by:

```text
OandaObservationRequester
```

during this workstream.

Its current:

```text
OANDA_PRACTICE_BASE_URL
OandaError
OandaConfigurationError
OandaNormalizationError
OandaRequestError
OandaAuthError
```

definitions/public behavior remain unchanged and may continue to be reused by the observation modules/request seam.

This existing provider-core ownership is intentionally not reorganized in this bounded refactor.

## Package/public-surface invariants

Existing exports from:

```text
backend/integrations/oanda/__init__.py
```

remain unchanged.

Do not export:

```text
OandaObservationRequester
validate_token
OandaPrimitiveError
parse_transaction_id
parse_decimal
parse_instrument
```

as provider capabilities.

No new public OANDA capability is introduced.

## Safety invariants

1. The explicit configured account ID remains the only selected account.

2. Every returned fact remains a read-only OANDA observation.

3. The shared seams never infer:

   - ownership;
   - reconciliation;
   - completeness;
   - Atlas financial exposure;
   - trading authorization.

4. Account identity/summary, Trade inventory, and Position inventory retain their existing immutable contracts.

5. Unknown, malformed, contradictory, partial, failed, or non-object provider data remains failure-closed according to the same owning layer as before.

6. Existing request failure sanitization remains unchanged.

7. No provider response body enters errors.

8. No API token enters errors.

9. No secret-bearing transport exception text enters errors.

10. No new endpoint is introduced.

11. No non-GET method is introduced.

12. No persistence is introduced.

13. No Order behavior is introduced.

14. No Risk, runtime, execution, Strategy, API/UI, activation, PAPER 01E, or LIVE behavior is introduced.

## Required valid, invalid, and boundary evidence

### Request seam

Valid/boundary evidence must include:

- one successful 2xx GET for each current endpoint;
- exact fixed Practice URL;
- exact application headers;
- no query parameters;
- exact static error subject wording;
- decoded JSON returned without domain classification;
- decoded non-object returned to owner for domain rejection;
- injected client remains open;
- internally owned client closes exactly once;
- transport ignored when client injected.

Failure evidence must include:

- missing token;
- blank token;
- connect timeout `<= 0`;
- connect timeout `> 30`;
- read timeout `<= 0`;
- read timeout `> 120`;
- 401;
- 403;
- 400;
- 404;
- 408 exhaustion;
- 429 exhaustion;
- 5xx exhaustion;
- transport exhaustion;
- other non-2xx;
- invalid JSON.

### Retry seam

Valid/boundary evidence must include:

- transient failure then success repeats the same GET;
- attempt count increments only for actual GETs;
- fallback sleeps `0.25`, then `0.5`;
- positive numeric `Retry-After`;
- numeric value above 30 capped at 30;
- future timezone-aware HTTP date;
- HTTP-date delay above 30 capped at 30.

Fallback evidence must include:

- missing `Retry-After`;
- malformed header;
- zero;
- negative numeric;
- non-finite numeric;
- naive HTTP date;
- past HTTP date.

No retry may exceed three GET attempts.

### Primitive seam

Transaction IDs:

Valid:

```text
"0"
"000"
"1"
"001"
```

Invalid:

```text
None
1
""
"-1"
"1.0"
whitespace-bearing values
```

Decimals:

Valid:

```text
"-1"
"0"
"1"
"1.25"
```

Invalid:

```text
non-string objects
malformed text
NaN
sNaN
Infinity
-Infinity
```

Instruments:

Valid:

```text
EUR_USD
USD_CAD
XAU_USD
```

Invalid:

```text
EURUSD
EUR
_USD
EUR_
EUR_USD_EXTRA
whitespace-bearing values
```

### Account regression evidence

Preserve evidence that:

- malformed PAPER 01B-only fields do not break identity-only PAPER 01A validation;
- matching configured/returned account ID succeeds;
- mismatched account ID fails;
- non-USD fails;
- valid finite adverse summary facts remain observable;
- counts remain nonnegative integers;
- mismatched top/nested transaction IDs fail;
- non-object JSON result fails with `OandaAccountNormalizationError`.

### Trade regression evidence

Preserve evidence that:

- empty inventory succeeds;
- unsupported provider instruments remain visible;
- distinct Trade IDs may share the same instrument;
- signed positive and negative nonzero units remain valid;
- `OPEN` remains valid;
- `CLOSE_WHEN_TRADEABLE` remains valid;
- deterministic leading-zero Trade-ID ordering remains permutation invariant;
- exact duplicate Trade IDs fail;
- zero Trade ID fails;
- zero current units fail;
- unsupported state fails;
- malformed timestamp fails;
- malformed retained fields fail;
- non-object JSON result fails with `OandaOpenTradeNormalizationError`.

### Position regression evidence

Preserve evidence that:

- empty inventory succeeds;
- unsupported provider instruments remain visible;
- long/short signed sides remain independent;
- both nonzero sides remain valid;
- zero side remains explicit;
- zero side may omit average price;
- exposed side requires average price;
- both sides zero fail;
- exact duplicate provider instruments fail;
- deterministic instrument ordering remains stable;
- malformed retained side/Position fields fail;
- non-object JSON result fails with `OandaOpenPositionNormalizationError`.

## Required tests

Add:

```text
backend/tests/integrations/test_oanda_request.py
```

covering:

- constructor timeout boundaries;
- token validation;
- exact GET construction;
- fixed Practice URL;
- exact headers;
- no params;
- static error-subject message preservation;
- successful JSON return;
- non-object JSON return;
- invalid JSON;
- status classes;
- attempt/status metadata;
- transport failures;
- retry timing;
- `Retry-After`;
- owned/injected client behavior;
- sanitization.

Add:

```text
backend/tests/integrations/test_oanda_primitives.py
```

covering:

- exact type strictness;
- transaction-ID regex boundaries;
- leading-zero transaction IDs;
- finite decimal parsing;
- non-finite decimal rejection;
- instrument regex boundaries;
- internal primitive-error sanitization.

Update existing:

```text
test_oanda_account.py
test_oanda_trades.py
test_oanda_positions.py
```

only where needed to:

- use the new patch point;
- prove the shared seam is exercised;
- preserve existing public contracts;
- strengthen explicit regression evidence.

Do not weaken existing assertions merely because request code moved.

`test_oanda_trades.py` must retain or add explicit evidence that:

> repeated provider instruments across distinct Trade IDs are valid.

Keep:

```text
test_oanda_source.py
```

passing without changing historical source execution to use the new request seam.

## Completion checks

Run:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_request.py \
  backend/tests/integrations/test_oanda_primitives.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_source.py
```

Then:

```bash
uv run pytest -m "not integration and not external"
```

Then targeted:

```text
Ruff format check
Ruff lint
Pyright
git diff --check
```

No database, Alembic, browser, API/UI, or credentialed external OANDA validation is required.

Independent VALIDATE must additionally verify:

- implementation diff is structurally smaller and behavior preserving;
- no closed observation registry exists in `request.py`;
- request labels affect only safe message text;
- source historical request execution remains outside requester;
- package exports remain unchanged;
- only the three existing observation endpoint paths are exercised;
- no provider mutation exists;
- no forbidden Atlas financial/runtime boundary is imported;
- current Trade repeated-instrument semantics remain valid.

## Expected implementation boundary

Expected tracked implementation/test changes are limited to:

```text
backend/integrations/oanda/request.py
backend/integrations/oanda/primitives.py
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/tests/integrations/test_oanda_request.py
backend/tests/integrations/test_oanda_primitives.py
backend/tests/integrations/test_oanda_account.py
backend/tests/integrations/test_oanda_trades.py
backend/tests/integrations/test_oanda_positions.py
```

No change is planned to:

```text
backend/integrations/oanda/source.py
backend/integrations/oanda/__init__.py
backend/persistence/
backend/migrations/
backend/risk/
backend/runtime/
backend/execution/
backend/api/
frontend/
```

If implementation demonstrates that a necessary change falls outside this boundary, BUILD must stop as:

```text
BLOCKED
```

and return the concrete reason for developer re-scoping.

## Intentionally retained structure

The following remain intentionally explicit rather than generalized:

```text
OANDA Practice environment
fixed Practice URL
account / Trade / Position endpoint constants
account binding before dependent observation
provider-specific account contract
provider-specific Trade contract
provider-specific Position contract
provider-specific normalization errors
```

Do not introduce:

```text
BrokerAdapter
BrokerClient
TradingGateway
ProviderFactory
GenericAccount
GenericTrade
GenericPosition
GenericObservation
provider plugin system
environment registry
```

The shared request seam is infrastructure reuse, not broker architecture.

## Approval gate

This architecture is frozen and reconciled into `PLAN.md`.

Implementation is not yet authorized.

After explicit developer approval:

```text
GIT START
→ BUILD T001
→ VALIDATE
→ REVIEW
→ immutable remediation chain if required
→ merge approval
```

If BUILD discovers a required behavior or file outside the frozen boundary, it must stop `BLOCKED` rather than expand the architecture.
