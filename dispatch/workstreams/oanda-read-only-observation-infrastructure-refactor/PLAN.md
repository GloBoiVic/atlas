# PLAN — OANDA Read-only Observation Infrastructure Refactor

## Workstream state

- **Workstream:** `oanda-read-only-observation-infrastructure-refactor`
- **Outcome:** preserve PAPER 01A–01D behavior while extracting only the demonstrated common OANDA request and provider-primitive mechanics from the account, open-Trade, and open-Position observation modules.
- **Classification:** `Critical`. The change alters shared authentication, timeout, retry, transport-error, response, and primitive-normalization infrastructure used by three shipped broker-observation slices. It introduces no new capability or financial state, but an incorrect refactor could change provider authority observations or fail-closed behavior across all three slices.
- **Base:** `main` at `48ddd4e1397609d0a48d4166ce158902b7113c69`.
- **Branch:** `solo/oanda-read-only-observation-infrastructure-refactor`.
- **Task:** `T001` — `DONE`.
- **Phase:** `READY_FOR_USER`; architecture frozen and reconciled.
- **Next action:** explicit merge approval, then GIT END.
- **Approval:** developer approved; GIT START complete at base `48ddd4e1397609d0a48d4166ce158902b7113c69`.
- **Architecture:** required and frozen in `ARCHITECTURE.md`; its request/primitive contracts, invariants, boundary examples, and required tests are reconciled into this PLAN.
- **Concerns:** preserving useful domain-specific normalization errors, exact retry timing/status behavior, injected-client ownership, and the historical `source.py` boundary without creating generalized broker architecture.

## Objective and invariant

The completed workstream must establish:

```text
account.py
trades.py
positions.py
        ↓
small OANDA-local shared infrastructure
        ↓
same external behavior, provider contracts, failures, and tests
```

This is a behavior-preserving refactor only.

It does not add:

- a provider endpoint;
- a provider fact;
- Atlas financial state;
- persistence;
- runtime behavior;
- Risk behavior;
- execution behavior;
- Order behavior;
- PAPER 01E capability.

The durable boundary remains that provider account, Trade, and Position values are read-only OANDA observations.

Nothing in the shared seam may:

- construct Atlas Position, Trade, Order, or Fill state;
- net long and short Position sides;
- infer ownership;
- reconcile observations;
- infer account completeness;
- authorize exposure;
- mutate broker state.

## Current demonstrated duplication

The following exact duplication is present across the three current observation modules:

| Shared behavior                                                                                                            | Current modules                           | Refactor intent                                                    |
| -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------ |
| bounded connect/read timeout validation and identical `httpx.Timeout` construction                                         | `account.py`, `trades.py`, `positions.py` | centralize in the request seam                                     |
| bearer header plus `Accept-Datetime-Format: RFC3339`                                                                       | all three                                 | centralize header construction                                     |
| `SecretStr` presence/blank validation using the existing sanitized configuration error                                     | all three                                 | centralize token validation                                        |
| owned/injected `httpx.Client` distinction, Practice base URL, `trust_env=False`, per-read closure, and per-request timeout | all three                                 | centralize client ownership/request mechanics                      |
| account-specific relative endpoint path executed as an authenticated GET                                                   | all three                                 | centralize GET execution while endpoint construction remains local |
| three attempts, transport retry, `Retry-After` numeric/date parsing, 30-second cap, and `0.25/0.5` fallback backoff        | all three                                 | centralize the proven observation retry policy                     |
| 401/403 auth rejection; 400/404 deterministic rejection; 408/429/5xx retry; other non-2xx failure                          | all three                                 | centralize status classification with the existing error classes   |
| sanitized invalid-JSON handling with no provider body or secret in request errors                                          | all three                                 | centralize JSON decoding failure handling                          |

This duplication is harmful now because three independently proven PAPER slices can drift in:

- safety bounds;
- authentication headers;
- retry classification;
- `Retry-After` handling;
- sanitization;
- client ownership.

The common behavior is now sufficiently demonstrated to extract.

The refactor does not seek maximum deduplication. It extracts only behavior that is already semantically identical across PAPER 01A–01D.

## Primitive duplication inventory

The following provider-format parsers have identical successful semantics but currently wrap failures in domain-specific errors:

| Primitive                                                        | Current evidence                     | Plan                                                                                                      |
| ---------------------------------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| numerical transaction-ID string (`[0-9]+`)                       | account, Trade, and Position modules | share an OANDA-only parser; each owner retains its current domain error and field/message context         |
| finite provider decimal string → `Decimal`                       | account, Trade, and Position modules | share only exact-string parsing and finite-value validation; positive/nonzero/sign semantics remain local |
| provider instrument with one non-empty underscore-separated pair | Trade and Position modules           | share the exact current provider-string shape parser; each owner retains its current normalization error  |

These are provider-format primitives only.

They must not produce:

- Atlas `Instrument`;
- Atlas `Direction`;
- Atlas Position;
- Atlas Trade;
- Atlas Order;
- Atlas Fill;
- any financial authority.

The following deliberately remain local:

- configured four-part account-ID validation;
- positive/nonzero Trade-ID semantics;
- Trade-ID deterministic ordering;
- strict Trade RFC3339 `openTime` validation;
- historical candle timestamp handling;
- account count validation;
- account USD support rule;
- Trade state validation;
- Trade `currentUnits != 0`;
- Position long/short sign rules;
- Position both-zero contradiction;
- Position exposed-side average-price rules;
- duplicate detection;
- inventory ordering;
- provider payload shape checks.

## Smallest shared request seam

Add the internal OANDA-local module:

```text
backend/integrations/oanda/request.py
```

The frozen responsibilities are limited to:

1. validate the existing bounded connect/read timeout values and construct the same `httpx.Timeout`;
2. validate a non-blank `SecretStr` token without exposing it;
3. preserve owned versus injected `httpx.Client` behavior;
4. construct the existing authenticated request headers;
5. perform one safe authenticated GET to a caller-constructed local OANDA Practice path;
6. apply the existing bounded observation retry policy;
7. preserve exact `Retry-After` parsing and fallback behavior;
8. preserve current request-level error classes, attempt/status metadata, and sanitized error wording;
9. decode successful JSON once and return the decoded provider value without understanding its domain.

Endpoint paths remain local:

```text
account.py   /v3/accounts/{account_id}/summary
trades.py    /v3/accounts/{account_id}/openTrades
positions.py /v3/accounts/{account_id}/openPositions
```

Account-ID quoting also remains local.

### Request error subject

The requester must not hardcode or enumerate the currently shipped observation domains.

Do not introduce a closed type such as:

```text
Literal["account", "open Trades", "open Positions"]
```

The owning module instead passes a static internal error subject:

```text
account.py   → "account"
trades.py    → "open Trades"
positions.py → "open Positions"
```

The requester uses that subject only to preserve existing safe error messages, for example:

```text
OANDA account request failed
OANDA open Trades request failed
OANDA open Positions request failed
```

The subject is a code-owned constant, not provider data, configuration, or user input.

The requester must never branch on the subject to decide:

- endpoint;
- provider semantics;
- response shape;
- retry behavior;
- account authority;
- capability.

This keeps the shared request seam independent of the current domain count without implementing any future endpoint.

## Practice URL and existing OANDA error family

The fixed:

```text
https://api-fxpractice.oanda.com
```

Practice URL remains intentional current capability.

For this bounded refactor:

- `OANDA_PRACTICE_BASE_URL` remains owned/exported by `source.py`;
- existing generic OANDA request/configuration/auth error identities remain unchanged;
- `request.py` may reuse those current definitions;
- no Practice/LIVE environment abstraction is introduced.

This retains the existing package/public surface and avoids broadening the refactor into provider-core file reorganization.

The historical `source.py` ownership of these existing provider-wide definitions is intentionally left unchanged in this workstream.

## Smallest shared primitive seam

Add the internal OANDA-local module:

```text
backend/integrations/oanda/primitives.py
```

It contains only the three proven provider-format primitives:

```text
transaction ID
finite decimal
provider instrument
```

Its parsing errors remain internal.

Account, Trade, and Position modules convert primitive failures into their existing domain-specific normalization errors.

The primitive layer does not know:

- provider payload field names;
- account semantics;
- Trade semantics;
- Position semantics;
- Atlas financial semantics.

The layering remains:

```text
provider representation
        ↓
shared primitive parser
        ↓
owning provider-domain semantic validation
```

For example:

```text
"-1000"
   ↓
finite Decimal
   ↓
Trade requires currentUnits != 0
```

and:

```text
"-1000"
   ↓
finite Decimal
   ↓
Position short side requires units <= 0
```

If exact implementation inspection shows that one proposed primitive does not actually have identical semantics across all current callers, leave that primitive local rather than forcing it into the shared module.

## Explicit source.py boundary

`backend/integrations/oanda/source.py` remains behaviorally untouched by this refactor.

Historical candle access has materially different behavior:

- request windows;
- multiple requests per fetch;
- query parameters;
- request diagnostics;
- candle/session filtering;
- M1/M15 semantics;
- different retry classification;
- different timestamp rules;
- separate historical market-data normalization.

In particular, the historical source's transient response behavior is not identical to the account-observation readers.

Therefore:

```text
source.py
```

must not begin using the new `OandaObservationRequester`.

Its existing historical request loop and provider-data normalization remain intact.

Existing provider-wide URL/error definitions already located there may continue to be imported by the new request seam, but historical candle execution itself remains outside the new request call path.

## Preservation contract

### PAPER 01A — account binding

Preserve exactly:

- explicit configured Practice account selection;
- `/v3/accounts/{accountID}/summary`;
- account-ID validation;
- account mismatch rejection;
- five-field immutable account identity;
- `Provider.OANDA`;
- `"PRACTICE"`;
- alias handling;
- USD base-currency requirement;
- sanitized request failures;
- `OandaAccountNormalizationError`.

Account identity validation must remain independent of PAPER 01B financial-summary validity.

### PAPER 01B — account summary

Preserve exactly:

- same summary snapshot fields;
- same one-response identity + summary normalization;
- same finite provider financial-fact acceptance;
- same nonnegative counts;
- same top-level/nested `lastTransactionID` consistency requirement;
- same provenance-only meaning;
- same separation from Risk, persistence, runtime, and reconciliation.

### PAPER 01C — open Trade inventory

Preserve exactly:

- `/v3/accounts/{accountID}/openTrades`;
- account binding before independent Trade observation;
- immutable provider Trade fields;
- signed nonzero `currentUnits`;
- `OPEN` and `CLOSE_WHEN_TRADEABLE`;
- strict Trade timestamp handling;
- unsupported provider instruments;
- exact duplicate Trade-ID rejection;
- deterministic numeric/raw-ID ordering;
- explicit empty inventory;
- transaction provenance.

Multiple distinct provider Trades may legitimately share the same provider instrument.

Therefore:

```text
Trade 101 → EUR_USD
Trade 105 → EUR_USD
```

is valid provider state.

Only exact duplicate provider Trade IDs are rejected.

Trade normalization errors remain:

```text
OandaOpenTradeNormalizationError
```

### PAPER 01D — open Position inventory

Preserve exactly:

- `/v3/accounts/{accountID}/openPositions`;
- account binding before independent Position observation;
- immutable provider Position and PositionSide fields;
- provider-native instrument visibility;
- long-side units `>= 0`;
- short-side units `<= 0`;
- zero-side representation;
- both nonzero sides remaining independently visible;
- both sides zero failing closed;
- active-side average-price requirement;
- zero-side optional average price;
- exact duplicate provider-instrument rejection;
- deterministic provider-instrument ordering;
- explicit empty inventory;
- transaction provenance.

Position normalization errors remain:

```text
OandaOpenPositionNormalizationError
```

## Common failure and injection behavior

Preserve:

- timeout bounds;
- timeout construction;
- missing/blank token behavior;
- token-before-network validation;
- account token/account-ID error precedence;
- injected-client behavior;
- injected transport behavior;
- owned-client closure;
- `trust_env=False` for owned clients;
- exact headers;
- GET-only observation behavior;
- no query parameters for the current three endpoints;
- exact retry counts;
- exact retry sleep values;
- exact `Retry-After` behavior;
- status-code classifications;
- exact `OandaRequestError.status_code`;
- exact `OandaRequestError.attempts`;
- safe request-level messages;
- no raw response body in errors;
- no API token in errors;
- no secret-bearing transport exception propagation.

An injected `httpx.Client` remains externally owned and must never be closed by the shared requester.

An internally created client remains closed on every success or failure path.

## Public surface and dependency boundaries

Existing package exports from:

```text
backend/integrations/oanda/__init__.py
```

remain unchanged.

The new:

```text
request.py
primitives.py
```

modules are internal implementation seams.

Do not export them as new provider capabilities.

Existing public exception identities remain unchanged.

No new OANDA capability appears in `__all__`.

The refactor must not introduce imports from:

```text
backend.domain.trading
backend.execution
backend.persistence
backend.risk
backend.runtime
backend.api
frontend
```

into the OANDA account-observation modules.

## Expected files

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

Existing account/Trade/Position tests should change only where the extraction changes an internal patch point or where regression evidence must be strengthened.

No change is planned to:

```text
backend/integrations/oanda/source.py
backend/integrations/oanda/__init__.py
backend/persistence/
backend/risk/
backend/runtime/
backend/domain/trading.py
backend/execution/
backend/api/
frontend/
```

If BUILD demonstrates that an implementation change outside the approved boundary is necessary, it must stop as `BLOCKED` and return for developer re-scoping.

## Persistence decision

No persistence is required or permitted.

This workstream changes implementation structure only.

Do not add:

- database models;
- migrations;
- caches;
- request persistence;
- provider snapshots;
- reconciliation state;
- transaction cursors;
- durable runtime state.

## Acceptance criteria

1. Shared request infrastructure removes only demonstrated duplicate mechanics from account, Trade, and Position readers.

2. Endpoint paths, account-ID quoting, response-shape validation, provider-domain normalization, ordering, and duplicate rules remain local.

3. The shared requester does not contain a closed registry/enumeration of account, Trade, or Position observation types. Domain labels are static caller-owned error subjects used only for safe message preservation.

4. Timeout bounds and exact `httpx.Timeout` construction remain semantically identical.

5. Token validation remains identical, including account validation's token-before-account-ID error precedence.

6. Owned and injected `httpx.Client` behavior remains identical:

   - one owned client per read;
   - owned client closed exactly once;
   - injected client never closed;
   - injected client causes separate `transport` to remain unused.

7. Current requests retain:

   - fixed OANDA Practice URL;
   - exact endpoint;
   - authenticated GET;
   - `Accept-Datetime-Format: RFC3339`;
   - no query parameters.

8. First-attempt success performs exactly one GET to the same endpoint.

9. Retry repeats only the same safe GET and preserves:

   - maximum three attempts;
   - `0.25/0.5` fallback sleeps;
   - numeric/HTTP-date `Retry-After`;
   - 30-second cap;
   - current status-code classification.

10. Existing request exception classes, status codes, attempt counts, and exact sanitized messages remain stable.

11. Invalid JSON remains a non-retried sanitized request failure with the current account/Trade/Position wording.

12. Non-object decoded provider responses remain domain-owned normalization failures rather than request-layer failures.

13. Shared transaction-ID parsing preserves exact current acceptance/rejection semantics.

14. Shared finite-decimal parsing preserves exact-string type strictness and finite-value semantics; positive, negative, zero, nonzero, and sign rules remain local.

15. Shared provider-instrument parsing preserves the current exact regex shape without converting to Atlas `Instrument`.

16. Account public contracts and normalization behavior remain unchanged.

17. Trade public contracts and normalization behavior remain unchanged, including:

- multiple distinct Trades sharing an instrument are valid;
- only exact duplicate provider Trade IDs fail.

18. Position public contracts and normalization behavior remain unchanged.

19. Settings-facing Trade and Position helpers still perform `/summary` account validation before their independent provider observation.

20. No cross-read atomicity, reconciliation, ownership, completeness, or financial-state claim is introduced.

21. `source.py` historical request behavior remains outside the shared observation requester and unchanged.

22. Existing package exports remain unchanged.

23. No new endpoint, Order behavior, full-account retrieval, persistence, transaction history, Account Changes, reconciliation, Risk, runtime, execution, Strategy, API/UI, broker mutation, PAPER activation, PAPER 01E, or LIVE behavior is introduced.

24. Focused OANDA regression tests and the non-integration/non-external suite pass, with targeted formatting, lint, typing, and diff checks clean.

## Validation strategy

BUILD and VALIDATE use deterministic injected HTTP seams only.

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

Independent VALIDATE must inspect both implementation and tests and verify:

- exact pre/post request equivalence;
- exact provider URLs;
- exact headers;
- no query parameters;
- first-attempt request count;
- transport/client ownership;
- retry counts and sleep values;
- `Retry-After` boundaries;
- status/attempt metadata;
- sanitized error messages;
- primitive type strictness;
- domain-specific error wrapping;
- account semantics;
- Trade semantics, including valid repeated instruments across distinct IDs;
- Position semantics;
- account-binding sequencing;
- unchanged `source.py`;
- unchanged package exports;
- absence of forbidden provider/Atlas capability expansion.

No database, browser, API/UI, or credentialed external OANDA validation is applicable.

## Intentionally remaining duplication

This workstream intentionally leaves the following repetition in place:

- historical candle request mechanics in `source.py`;
- historical retry constants in `source.py`;
- historical diagnostics;
- historical timestamp/decimal normalization;
- local endpoint constants;
- local account-ID quoting;
- domain-specific normalization error messages;
- account-ID validation;
- account identity/USD/count rules;
- Trade-ID semantics;
- Trade timestamp rules;
- Trade state/unit rules;
- Trade ordering and duplicate-ID detection;
- Position side/sign rules;
- Position average-price rules;
- Position both-zero contradiction;
- Position ordering and duplicate-instrument detection;
- provider response-shape validation;
- immutable contract construction.

This is intentional semantic duplication or domain ownership, not infrastructure drift.

The workstream does not optimize for line count.

## Hardcoded constants

The following observation retry constants move once into `request.py`:

```text
_MAX_ATTEMPTS = 3
_RETRY_AFTER_CAP_SECONDS = 30.0
_BACKOFF_SECONDS = (0.25, 0.5)
```

They remain hardcoded safety bounds.

They do not become Settings.

The historical source retains its own same-valued constants because its request behavior is a separate proven contract.

The following also remain intentionally fixed:

```text
OANDA Practice base URL
/summary
/openTrades
/openPositions
```

The Practice URL represents current validated provider environment scope.

Endpoint paths represent explicit OANDA contracts.

Hardcoded explicit capability boundaries are acceptable; duplicating identical infrastructure policy across modules is what this refactor removes.

## No capability expansion proof

The approved implementation boundary contains:

- no new provider URL path;
- no new HTTP method;
- no provider mutation;
- no new provider response field;
- no new public package capability;
- no persistence;
- no financial-state construction;
- no runtime activation.

`request.py` merely executes already-existing safe GETs.

`primitives.py` merely parses provider values already accepted by current readers.

The shared request seam does not enumerate or register provider capabilities; caller-owned endpoint paths remain the authority over which existing reads occur.

`source.py` remains outside the new request path.

Therefore PAPER 01E, Orders, LIVE, reconciliation, accounting, and capital-capable behavior cannot be introduced without violating this PLAN.

## Approval gate

Architecture is frozen and reconciled into this PLAN.

This remains a `Critical` workstream, so implementation requires explicit developer approval.

After approval:

```text
GIT START
→ BUILD T001
→ VALIDATE
→ REVIEW
→ immutable remediation chain if required
→ merge approval
```

Do not BUILD before approval.
