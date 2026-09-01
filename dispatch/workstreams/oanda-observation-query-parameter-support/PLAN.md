# PLAN — OANDA Observation Query Parameter Support

## Workstream state

- **Workstream:** `oanda-observation-query-parameter-support`
- **Outcome:** extend the existing read-only OANDA Practice observation requester with an optional narrow caller-owned query mapping while preserving PAPER 01A–01E request behavior and adding no provider capability.
- **Classification:** `Critical`. The implementation is small, but it changes shared request infrastructure used by the closed PAPER 01A–01E observation consumers. An incorrect request-construction change could alter every existing broker observation.
- **Base:** `main` at `190282f07246f7603cdfe14d297186c304afc24c`.
- **Branch:** `solo/oanda-observation-query-parameter-support` — fast-forward merged into `main` at `a8c627f21b9cdbdfde4a699d397e12300898780d`.
- **Task:** `T001` — `DONE`.
- **Phase:** `COMPLETED`.
- **Next action:** none; workstream closed after GIT END.
- **Approval:** terminal closure approved; feature branch committed and fast-forward merged into `main`.
- **Architecture:** required and frozen in `ARCHITECTURE.md`, including the snapshot-once invariant.
- **Concerns:** preserving exact query-less behavior for PAPER 01A–01E, retry identity, sanitization, client ownership, and timeout/error semantics while exposing only a narrow transport capability.

## Objective

Permit safe caller-owned query parameters on the existing OANDA read-only GET seam so a future bounded provider-domain observation can use an endpoint that requires query parameters.

The requester remains ignorant of:

- query meaning;
- provider domain;
- instrument semantics;
- pricing;
- endpoint schema.

This workstream does not call a new provider endpoint.

The frozen public/internal seam is:

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

`params` is:

- keyword-only;
- optional;
- `Mapping[str, str] | None`;
- backward-compatible with all existing consumers.

It is not:

- `Mapping[str, Any]`;
- a provider-specific model;
- a multi-value/query-sequence API;
- an endpoint registry;
- query validation.

HTTPX owns URL query serialization.

Application code must not manually append query strings to `path`.

## Current foundation and affected callers

The current shared requester is:

```text
backend/integrations/oanda/request.py
```

It already owns:

- fixed OANDA Practice routing;
- authenticated GET-only requests;
- bounded timeout construction;
- token validation;
- owned/injected client behavior;
- bounded retries;
- `Retry-After`;
- status classification;
- sanitized errors;
- JSON decoding.

The current product consumers are:

```text
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/orders.py
```

Their current endpoints are:

```text
/summary
/openTrades
/openPositions
/pendingOrders
```

They do not require query parameters.

They must remain semantically unchanged and should not be edited merely to pass:

```text
params=None
```

## Scope

### In scope

- add one optional narrow query-parameter argument to `OandaObservationRequester.get_json`;
- snapshot supplied query values once per `get_json()` call without mutating the caller mapping;
- pass the local snapshot through HTTPX `params=`;
- preserve exact query-less behavior when the argument is omitted or `None`;
- preserve the same query snapshot across all retry attempts;
- preserve existing path, headers, Practice host, GET method, timeouts, retries, errors, JSON behavior, and client ownership;
- add focused requester tests;
- rerun focused account/Trade/Position/pending-Order regression tests;
- use focused validation only.

### Explicitly out of scope

Do not implement:

- PAPER 01F;
- `/pricing`;
- `instruments=EUR_USD`;
- current pricing;
- bids;
- asks;
- liquidity;
- quotes;
- executable prices;
- streaming;
- polling;
- live market-data runtime;
- provider-specific query validation;
- list/multi-value query semantics;
- query-schema registry;
- endpoint registry;
- POST;
- PUT;
- PATCH;
- DELETE;
- arbitrary methods;
- alternate base URLs;
- OANDA environment switching;
- persistence;
- reconciliation;
- execution;
- Risk;
- runtime;
- API/UI;
- generalized broker architecture;
- LIVE.

No new OANDA endpoint may be called by application code in this workstream.

## Query contract

The requester accepts:

```python
Mapping[str, str] | None
```

This is an Atlas static typing contract.

The requester must not add runtime provider/query validation for unsupported Python values.

For example, these are outside the typed Atlas contract:

```python
params={"limit": 50}
params={"ids": ["one", "two"]}
params=[("cursor", "abc")]
```

They should be rejected by static typing in normal Atlas code, not converted into a new runtime validation subsystem.

Do not add:

- `isinstance` traversal of query keys/values;
- query-specific error classes;
- query-specific runtime normalization;
- coercion to strings;
- provider key validation.

The only runtime work required is making a stable local snapshot of a valid typed mapping.

## Query snapshot and ownership

At the beginning of `get_json()`, after normal argument entry and before request attempts, establish one local snapshot equivalent to:

```python
request_params = None if params is None else dict(params)
```

The exact local variable name is not important.

The required semantics are:

- caller mapping is not mutated;
- caller mapping is not stored on `self`;
- query values are captured once for this request operation;
- every retry uses the same captured key/value set;
- no query state remains after `get_json()` returns or raises.

This prevents a mutable caller-owned mapping from changing the request between retry attempts.

The requester does not assign meaning to any key or value.

## Request construction

Every attempt continues using the existing authenticated GET, with only:

```python
params=request_params
```

added:

```python
response = client.get(
    f"{OANDA_PRACTICE_BASE_URL}{path}",
    headers=headers,
    params=request_params,
    timeout=self._timeout,
)
```

Do not:

- manually append `?`;
- manually URL-encode keys or values;
- parse query strings from `path`;
- create a custom query serializer.

HTTPX owns query serialization.

Existing callers continue to call:

```python
get_json(path, error_subject=...)
```

with no `params` argument.

## Preservation invariants

The following behavior must remain unchanged.

### Request method and endpoint

Every observation remains:

```text
GET
```

to:

```text
OANDA_PRACTICE_BASE_URL + caller-owned local path
```

No method parameter or alternate host is introduced.

### Authentication

Preserve exact application headers:

```python
{
    "Authorization": f"Bearer {token.get_secret_value()}",
    "Accept-Datetime-Format": "RFC3339",
}
```

### Timeouts

Preserve existing:

- constructor bounds;
- `httpx.Timeout` construction;
- per-request timeout;
- owned-client timeout.

### Client ownership

Preserve:

- injected client precedence;
- injected client not closed;
- separately supplied transport ignored when client is injected;
- internally owned client uses current transport/base URL/`trust_env=False`;
- internally owned client closes exactly once.

### Retry behavior

Preserve:

- maximum three attempts;
- transport retry;
- `408`;
- `429`;
- `5xx`;
- fallback sleep `0.25`, then `0.5`;
- `Retry-After`;
- 30-second cap;
- status/attempt metadata.

Every retry must repeat the same:

- method;
- endpoint;
- path;
- headers;
- timeout;
- local query snapshot.

### Errors

Preserve exact current request-level messages:

```text
OANDA API token is required
OANDA authorization failed
OANDA {error_subject} request was rejected
OANDA {error_subject} request failed
OANDA {error_subject} request failed after retries
OANDA returned invalid {error_subject} JSON
```

Do not include:

- path;
- query keys;
- query values;
- provider response bodies;
- bearer token;
- transport exception text.

### JSON

Preserve:

- successful 2xx → return `response.json()` as-is;
- non-object JSON remains valid requester output for owning domain normalization;
- invalid JSON is not retried;
- no query-specific response behavior.

## Existing consumers

The following files are expected to remain unchanged:

```text
backend/integrations/oanda/account.py
backend/integrations/oanda/trades.py
backend/integrations/oanda/positions.py
backend/integrations/oanda/orders.py
```

Their focused tests must prove backward compatibility.

No caller should be changed merely to add:

```text
params=None
```

## Expected implementation boundary

Expected product/test changes are limited to:

```text
backend/integrations/oanda/request.py
backend/tests/integrations/test_oanda_request.py
```

plus workstream artifacts.

Expected unchanged files include:

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

If implementation requires an application change outside:

```text
request.py
```

for anything other than an unavoidable import/type correction, stop:

```text
BLOCKED
```

and return for developer re-scoping.

## Acceptance criteria

1. `OandaObservationRequester.get_json(...)` accepts:

   ```python
   params: Mapping[str, str] | None = None
   ```

   as an optional keyword-only argument.

2. Existing callers compile and run without modification.

3. Omitting `params` preserves existing query-less request behavior.

4. `params=None` preserves query-less behavior.

5. An empty mapping produces no caller-supplied query parameters.

6. A supplied valid typed mapping is snapshotted once locally without mutating the caller.

7. The local snapshot is passed through HTTPX's `params=` API.

8. Query strings are never manually concatenated to `path`.

9. A first-attempt successful request performs one authenticated GET with exactly the supplied caller query values.

10. Every retry uses the identical captured query key/value set.

11. The caller's mapping remains unchanged after success.

12. The caller's mapping remains unchanged after failure.

13. Query keys and values do not appear in request-level error messages.

14. Existing token, timeout, client ownership, retry, `Retry-After`, status, JSON, error-class, attempt-metadata, and sanitization behavior remains unchanged.

15. No runtime query-schema/provider validation is introduced.

16. PAPER 01A–01E focused regression tests remain green without semantic changes.

17. No new OANDA endpoint, pricing capability, financial state, persistence, reconciliation, execution, Risk/runtime behavior, API/UI, broker mutation, or LIVE capability is introduced.

## Required focused validation

Do **not** run the entire backend suite for this workstream.

The blast radius is the shared requester plus its four known observation consumers.

Run:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_request.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_orders.py
```

Then:

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
full backend pytest suite
test_oanda_source.py
database integration tests
Alembic
frontend tests
browser tests
credentialed external OANDA tests
```

`test_oanda_source.py` does not use `OandaObservationRequester`.

If VALIDATE discovers concrete evidence that an excluded area changed, it may stop and request re-scoping rather than silently broadening validation.

## Required focused test evidence

### Existing no-params behavior

Retain evidence that:

```python
get_json(path, error_subject=...)
```

produces:

- same Practice URL;
- same path;
- GET;
- no caller-supplied query;
- exact headers.

### Supplied query mapping

Use provider-neutral test values such as:

```python
params={"example": "value"}
```

Verify HTTPX produces the expected request query.

Requester tests must not mention pricing semantics.

### Multiple string query values

Because the frozen type naturally supports multiple distinct keys, test something like:

```python
params={
    "first": "one",
    "second": "two",
}
```

Do not test repeated-key/list semantics.

### Escaping

A string value requiring URL encoding may be tested to prove HTTPX owns serialization.

The assertion should inspect decoded query semantics where practical rather than duplicate HTTPX's internal encoding implementation.

### Retry identity

A transient response followed by success must prove all attempts received identical:

- method;
- path;
- query parameters;
- headers.

### Caller ownership

Use a mutable dictionary.

Take a snapshot before the request.

Verify the original dictionary remains equal to the snapshot after:

- success;
- failure.

### Sanitization

Use a distinctive query key/value marker and prove neither appears in deterministic request error text.

Do not require provider-specific query validation.

### Existing consumers

Focused account, Trade, Position, and pending-Order tests must remain green without product-call-site changes.

## Approval gate

This PLAN is reconciled with the frozen ARCHITECTURE, including the developer-approved requirement to snapshot a supplied mapping once per `get_json()` call and reuse that local snapshot for every retry.

Because the workstream is `Critical`, implementation required explicit developer approval. That approval was granted before GIT START.

After approval:

```text
GIT START
→ BUILD
→ focused VALIDATE
→ REVIEW
→ immutable remediation chain if required
→ merge approval
```

Do not BUILD before approval.
