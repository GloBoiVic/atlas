# ARCHITECTURE — OANDA Observation Query Parameter Support

## Status

`FROZEN_APPROVED`

This artifact freezes the narrow query-parameter extension to the existing read-only OANDA observation requester.

It is reconciled into `PLAN.md`.

It is not:

- implementation approval;
- branch approval;
- provider-endpoint approval;
- pricing approval;
- permission to create capital-capable behavior.

Explicit developer approval was granted on 2026-09-01 before GIT START or BUILD.

## Architectural decision

Extend only:

```text
OandaObservationRequester.get_json(...)
```

with a narrow optional query mapping.

No provider-domain behavior moves into the requester.

The frozen seam is:

```python
from collections.abc import Mapping
from typing import Any

def get_json(
    self,
    path: str,
    *,
    error_subject: str,
    params: Mapping[str, str] | None = None,
) -> Any:
    ...
```

`Mapping` comes from:

```text
collections.abc
```

The query contract is intentionally:

```text
Mapping[str, str] | None
```

It is not:

- `dict[str, str]` only;
- `Mapping[str, Any]`;
- an HTTPX-wide query type;
- a list/tuple multi-value API;
- a provider query object;
- an endpoint-specific schema.

This is a narrow Atlas transport contract.

## Static typing boundary

`Mapping[str, str]` is enforced primarily through Atlas's static typing discipline.

The requester must not add runtime validation or coercion merely to police Python callers that violate the type annotation.

These are outside the approved typed contract:

```python
params={"limit": 50}
params={"ids": ["one", "two"]}
params=[("cursor", "abc")]
```

The workstream must not respond by introducing:

- runtime key/value traversal;
- string coercion;
- query validation errors;
- provider query rules;
- query schema objects.

If incorrectly typed values are forced into the function at runtime, resulting behavior is outside this frozen contract.

Tests should exercise the supported typed surface rather than build a second runtime type system.

## Stable local query snapshot

A supplied valid query mapping is caller-owned.

The requester must not:

- mutate it;
- store it on `self`;
- change entries;
- remove entries;
- append entries.

To guarantee deterministic retry identity, snapshot it exactly once into local request state:

```python
request_params = None if params is None else dict(params)
```

Equivalent implementation is permitted if it preserves the same semantics.

The snapshot:

- exists only for the current `get_json()` call;
- captures the caller's key/value set once;
- is reused for every attempt;
- is discarded when the call returns or raises.

This guarantees retry behavior does not depend on later mutation of the caller-owned mapping.

No provider meaning is assigned during the copy.

## Request construction

Every attempt uses the existing GET construction with only the new HTTPX parameter argument added:

```python
response = client.get(
    f"{OANDA_PRACTICE_BASE_URL}{path}",
    headers=headers,
    params=request_params,
    timeout=self._timeout,
)
```

The requester must not:

- append `?` to the path;
- concatenate query fragments;
- manually percent-encode query values;
- parse query strings;
- modify endpoint paths based on query contents.

HTTPX owns query serialization.

## Path boundary

`path` remains a caller-owned local OANDA path.

Correct Atlas callers must use the new `params` argument for query values rather than embedding a query string in `path`.

This workstream does **not** add runtime path-query rejection.

It does not inspect:

```text
?
&
=
```

inside `path`.

Adding such validation would be a separate behavioral change and is out of scope.

## Query omission behavior

Existing calls:

```python
requester.get_json(
    "/v3/accounts/example/summary",
    error_subject="account",
)
```

continue to behave as before.

Internally:

```text
params omitted
→ params == None
→ request_params == None
```

and the requester passes:

```text
params=None
```

to HTTPX.

No current consumer is changed merely to spell the default explicitly.

An empty mapping:

```python
{}
```

is also a valid typed input.

It produces no caller-supplied query entries.

The requester adds no special case beyond normal local snapshotting and HTTPX serialization.

## Valid transport examples

These examples define transport mechanics only.

They do not authorize new provider endpoints.

### No query

```python
requester.get_json(
    "/v3/accounts/example/summary",
    error_subject="account",
)
```

### One query value

```python
requester.get_json(
    "/v3/accounts/example/summary",
    error_subject="account",
    params={"example": "value"},
)
```

### Multiple distinct keys

```python
params = {
    "first": "one",
    "second": "two",
}

requester.get_json(
    "/v3/accounts/example/summary",
    error_subject="account",
    params=params,
)
```

### Empty string value

```python
params={"cursor": ""}
```

remains within the static `Mapping[str, str]` contract.

Whether a provider endpoint accepts a particular key or empty value belongs to that provider-domain caller, not this requester.

## Invariants that remain unchanged

### Fixed provider environment

Every request remains on:

```text
https://api-fxpractice.oanda.com
```

No environment selection or LIVE URL is added.

### GET only

No method parameter is added.

Every request remains:

```text
GET
```

### Authentication

Preserve:

```python
{
    "Authorization": f"Bearer {token.get_secret_value()}",
    "Accept-Datetime-Format": "RFC3339",
}
```

Token validation remains before owned-client creation/network activity.

### Timeout behavior

Preserve:

- connect bounds;
- read bounds;
- `httpx.Timeout`;
- per-request timeout;
- owned-client timeout.

### Client ownership

Preserve:

- injected client precedence;
- injected client not closed;
- injected client uses the existing per-request timeout;
- separately supplied transport does not override the injected client;
- internally owned client uses current transport;
- internally owned client uses fixed Practice base URL;
- internally owned client uses `trust_env=False`;
- internally owned client closes exactly once.

### Retry policy

Preserve:

```text
maximum attempts = 3
fallback sleeps = 0.25, 0.5
Retry-After cap = 30 seconds
```

Preserve current classifications:

```text
httpx.RequestError → retry
401/403             → immediate auth failure
400/404             → immediate deterministic rejection
408                  → retry
429                  → retry
5xx                  → retry
other non-2xx        → immediate request failure
```

Every retry uses the same local:

```text
request_params
```

snapshot.

### Retry identity

For one `get_json()` operation, every attempt must be identical with respect to:

- method;
- Practice host;
- path;
- headers;
- timeout;
- query key/value set.

Only provider response and attempt number may differ.

### JSON

Preserve:

- successful 2xx → `response.json()`;
- decoded value returned as-is;
- non-object JSON remains the owning domain's concern;
- invalid JSON is not retried.

### Status metadata

Preserve:

```text
OandaRequestError.status_code
OandaRequestError.attempts
```

semantics exactly.

## Sanitization

Existing request-level messages remain byte-equivalent:

```text
OANDA API token is required
OANDA authorization failed
OANDA {error_subject} request was rejected
OANDA {error_subject} request failed
OANDA {error_subject} request failed after retries
OANDA returned invalid {error_subject} JSON
```

Request errors must not include:

- path;
- query key;
- query value;
- provider body;
- bearer token;
- transport exception text.

No query-specific error class or message is added.

## Existing consumer boundary

Current consumer modules remain unchanged:

```text
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/orders.py
```

They continue to omit the new argument.

Their current semantics remain:

```text
account    → /summary
trades     → /openTrades
positions  → /openPositions
orders     → /pendingOrders
```

No consumer gains query semantics in this workstream.

## Expected implementation boundary

Expected application/test edits:

```text
backend/integrations/oanda/request.py
backend/tests/integrations/test_oanda_request.py
```

Expected unchanged:

```text
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/orders.py
backend/integrations/oanda/primitives.py
backend/integrations/oanda/source.py
backend/integrations/oanda/__init__.py
backend/risk/
backend/runtime/
backend/execution/
backend/persistence/
backend/api/
frontend/
```

Any required behavioral edit outside the frozen requester/test seam is:

```text
BLOCKED
```

pending developer re-scoping.

## Required focused test evidence

### 1. Existing no-query request

Retain the existing requester test proving:

- fixed Practice URL;
- GET;
- current path;
- no caller query;
- exact authentication headers.

### 2. One supplied query

Supply:

```python
params={"example": "value"}
```

and verify the mock transport receives that query through the request URL.

Do not introduce provider semantics.

### 3. Multiple distinct string keys

Supply:

```python
{
    "first": "one",
    "second": "two",
}
```

and verify both arrive.

Do not test repeated-key/list-value behavior.

### 4. HTTPX escaping delegation

Supply a string value that requires URL escaping.

Verify the resulting request decodes to the supplied semantic value.

Do not reproduce or custom-test HTTPX's encoding algorithm beyond proving delegation.

### 5. Caller mapping unchanged after success

Use a mutable dictionary.

Capture a copy before the request.

Assert equality after completion.

### 6. Caller mapping unchanged after failure

Repeat using a deterministic provider/request failure.

Assert equality after failure.

### 7. Retry query identity

Cause:

```text
transient failure
→ success
```

and record each request.

Assert identical across attempts:

- method;
- path;
- query parameters;
- headers.

Existing retry sleep assertions remain unchanged.

### 8. Snapshot stability

Use a test seam that mutates the original caller dictionary after the first request reaches the mock transport.

The second retry must still contain the original captured query values.

This proves the requester uses one local snapshot rather than re-reading mutable caller state.

### 9. Sanitization

Use distinctive query key/value markers.

For representative deterministic failure paths, assert neither marker appears in the raised error text.

Existing provider body/token/transport sanitization tests remain green.

### 10. Typed surface only

Do not add runtime tests expecting the requester to reject:

```text
int values
list values
sequence params
```

Those are outside the statically typed Atlas contract.

Targeted Pyright is the relevant guard for supported Atlas call sites.

## Focused validation boundary

Required tests:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_request.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_orders.py
```

Required quality checks:

```bash
uv run ruff format --check \
  backend/integrations/oanda/request.py \
  backend/tests/integrations/test_oanda_request.py

uv run ruff check \
  backend/integrations/oanda/request.py \
  backend/tests/integrations/test_oanda_request.py

uv run pyright \
  backend/integrations/oanda/request.py \
  backend/tests/integrations/test_oanda_request.py

git diff --check
```

Do not run by default:

```text
full backend test suite
test_oanda_source.py
database tests
Alembic
frontend tests
browser validation
credentialed external OANDA requests
```

The excluded areas are outside this workstream's demonstrated blast radius.

If independent VALIDATE finds evidence of an unexpected cross-boundary change, the workstream should stop for re-scoping rather than automatically expanding validation.

## Safety boundary

This architecture adds transport capability only.

It does not add:

```text
new OANDA endpoint
pricing
instrument selection
market data
broker mutation
execution
Risk
runtime
persistence
reconciliation
PAPER activation
LIVE
```

The requester remains a read-only OANDA Practice GET transport seam.

## Approval gate

This architecture is frozen and reconciled into `PLAN.md`.

Implementation is authorized on the approved workstream branch only.

After explicit developer approval:

```text
GIT START
→ BUILD
→ focused VALIDATE
→ REVIEW
→ immutable remediation chain if required
→ merge approval
```

If BUILD requires capability or behavior outside this frozen boundary, stop:

```text
BLOCKED
```

and return the concrete reason.
