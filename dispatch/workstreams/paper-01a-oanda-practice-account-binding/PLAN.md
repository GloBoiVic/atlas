# PLAN — PAPER 01A OANDA Practice Account Binding

## Workstream state

- **Outcome:** explicit configured OANDA Practice account ID → read-only provider validation → normalized Atlas account identity → fail closed on invalid, missing, inaccessible, or uncertain state.
- **Classification:** `Feature`. This adds a bounded provider-facing capability, but it is read-only, non-capital, local to configuration and the OANDA integration, and introduces no persistence or runtime authority. `ARCHITECTURE.md` is not required.
- **Phase:** CLOSED; developer approved; merge approved.
- **Planned branch:** `solo/paper-01a-oanda-practice-account-binding`.
- **Base:** `main` at `fa2a8f5ca7a4d5da1fb7d56bd1ee69dde34a8ab2`.
- **GIT START:** complete on `solo/paper-01a-oanda-practice-account-binding` at base `fa2a8f5ca7a4d5da1fb7d56bd1ee69dde34a8ab2`.
- **GIT END:** implementation commit `bc69499f56518690660f1b7e49ce8c1504fd2260` fast-forward merged into `main`; closure recorded and active state cleared.
- **Task:** `T001` — `DONE`.
- **Next action:** none; terminal workstream closure is complete.
- **Known inherited state:** `.codegraph/` and `frontend/.env.local` were already untracked and were reconfirmed at GIT START; they remain untouched and will not be read, modified, staged, or removed by this workstream.

## Current implementation and gap

Atlas already has:

- `Settings.oanda_api_token` as `SecretStr`, bounded OANDA connect/read timeouts, and `.env` loading;
- a fixed OANDA Practice REST base URL;
- a synchronous `httpx` read-only historical source with environment proxy isolation, bounded retries, and sanitized provider failures;
- the existing `Provider.OANDA` identity;
- a current Risk boundary that supports EUR/USD with a USD-base account.

Atlas does not have:

- an explicit configured OANDA Practice account ID;
- an account-specific read-only validation request;
- a normalized Atlas account identity contract.

The historical OANDA source is instrument-scoped and must not be treated as account binding.

## Planned behavior

1. Add optional-at-application-level `ATLAS_OANDA_ACCOUNT_ID` configuration with no default.

   Historical research remains usable without it.

   Invoking account binding requires both:

   - a non-empty OANDA token;
   - an explicit account ID satisfying OANDA's documented AccountID shape.

   Missing or malformed account-binding configuration must fail before network access.

   Validation must not invent additional Atlas-specific prefix, numeric-range, account-number, or other provider-unsupported semantics.

2. Add one narrow OANDA Practice account-binding module.

   It will issue only:

   ```text
   GET /v3/accounts/{configuredAccountID}/summary
   ```

   against the fixed OANDA Practice REST base URL.

   It will not:

   - call `GET /v3/accounts`;
   - enumerate credential-visible accounts;
   - select the first available account;
   - infer an account from provider responses;
   - call any mutating endpoint.

3. Return one immutable `OandaPracticeAccountIdentity` containing only:

   - provider: existing `Provider.OANDA`;
   - environment: fixed `PRACTICE`;
   - provider account ID: required and exactly equal to the configured account ID;
   - alias: optional, for trader confirmation only;
   - base currency: required and currently `USD`.

4. Ignore all other account-summary fields.

   In particular, this slice does not consume or expose:

   - balance;
   - NAV/equity;
   - margin facts;
   - Orders;
   - Trades;
   - Positions;
   - transaction IDs;
   - transaction cursors.

   The provider response is not persisted.

5. Fail closed with sanitized errors when:

   - token is missing;
   - account ID is missing or malformed;
   - the selected account is inaccessible;
   - the provider deterministically rejects the request;
   - transient provider or transport failure remains unresolved after any bounded safe retry;
   - response JSON is invalid;
   - required response fields are malformed or absent;
   - returned provider account ID differs from configuration;
   - account base currency is not `USD`.

   No token or raw provider response body may enter an exception or log message.

6. Reuse existing OANDA timeout or retry machinery only where it is a clean dependency.

   Account binding must not depend on historical candle-loading implementation internals merely to reuse code.

   Any retry behavior must:

   - be bounded;
   - be appropriate for this read-only GET;
   - preserve sanitized failures;
   - never convert unresolved provider state into a successful identity.

The direct account-specific request makes multiple accessible accounts irrelevant: only the configured ID is requested and accepted. A credential with access to multiple accounts cannot cause implicit or first-account selection.

## Persistence decision

**Persistence is not required for PAPER 01A.**

Explicit configuration plus fresh read-only validation and the narrow immutable normalized account contract are sufficient to prove the required capability.

This slice has no:

- Deployment;
- activation lifecycle;
- runtime ownership;
- reconciliation cursor;
- broker-state lifecycle;
- capital state

that requires a durable Atlas account entity.

Adding a `TradingAccount` table now would create future-oriented lifecycle and migration semantics without a PAPER 01A requirement.

If BUILD discovers a concrete requirement for persistence, it must stop as `BLOCKED` and return for scope/architecture approval rather than adding persistence opportunistically.

## Implementation seams

| File                                               | Planned change                                                                                                                                                                                                                                                                              |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/config.py`                                | Add the explicit optional OANDA account-ID setting and validate only the provider-documented AccountID shape needed for safe request construction, without inventing additional Atlas account-ID semantics or changing token handling.                                                      |
| `.env.example`                                     | Document the non-secret placeholder and that it selects one explicit Practice account. Commit no real account identifier.                                                                                                                                                                   |
| `backend/integrations/oanda/account.py`            | Add the narrow OANDA-only normalized identity and read-only account validator using the fixed Practice endpoint, bounded timeout/failure handling, clean reuse of existing OANDA transport/retry utilities only where appropriate, and sanitized failures. No generalized broker framework. |
| `backend/integrations/oanda/__init__.py`           | Export only the new public account-binding contract required by this slice.                                                                                                                                                                                                                 |
| `backend/tests/test_config.py`                     | Prove account-ID default, valid configuration, malformed/missing behavior, and safe representation as applicable.                                                                                                                                                                           |
| `backend/tests/integrations/test_oanda_account.py` | Deterministic `httpx.MockTransport` coverage for request shape, normalization, explicit account selection, provider uncertainty, malformed responses, mismatch handling, USD boundary, and sanitization.                                                                                    |

No schema, migration, persistence model, FastAPI route, frontend, Risk, execution, historical-source behavior, or runtime process is expected to change.

If implementation demonstrates that one of those is necessary, BUILD must stop as `BLOCKED` rather than expand scope.

## Acceptance criteria

1. Account binding cannot start without:

   - the existing OANDA token;
   - an explicit configured Practice account ID satisfying OANDA's documented AccountID shape.

   Missing or malformed values fail before network access.

   Atlas introduces no stricter account-ID semantics than required by the provider contract.

2. The only successful provider request is an authenticated HTTP `GET` to:

   ```text
   /v3/accounts/{configuredAccountID}/summary
   ```

   on the fixed OANDA Practice endpoint.

   No account-list or mutating endpoint is called.

3. A valid USD Practice response returns exactly these normalized identity facts:

   - provider;
   - environment;
   - provider account ID;
   - optional alias;
   - base currency.

   Returned provider account ID must exactly match configuration.

   Missing alias normalizes to `None`.

4. A credential with access to multiple accounts cannot influence account selection because:

   - no account-list response is consumed;
   - no fallback selection exists;
   - only the configured account ID is requested.

5. Invalid, inaccessible, or mismatched selection; deterministic provider rejection; unresolved transient provider or transport failure after any bounded safe retry; invalid JSON; malformed required fields; and non-USD base currency all produce:

   - no normalized identity;
   - sanitized actionable failure.

6. Provider bodies, credentials, balance/equity, margin, Orders, Trades, Positions, and transaction cursors are neither retained nor exposed by the account-binding contract.

7. Existing historical OANDA behavior remains compatible when no account ID is configured.

8. No persistence or capital-capable provider request is introduced.

9. Account binding does not introduce generalized broker/account/runtime architecture for later PAPER work.

## Validation strategy

BUILD will run the smallest relevant checks first:

```bash
uv run pytest \
  backend/tests/test_config.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_source.py
```

```bash
uv run ruff format --check \
  backend/config.py \
  backend/integrations/oanda \
  backend/tests/test_config.py \
  backend/tests/integrations
```

```bash
uv run ruff check \
  backend/config.py \
  backend/integrations/oanda \
  backend/tests/test_config.py \
  backend/tests/integrations
```

```bash
uv run pyright backend
```

Independent VALIDATE will inspect:

- the exact diff;
- provider request method/path;
- configuration handling;
- sanitization;
- absence of persistence/runtime/capital-capable changes.

Then run:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration and not external"
```

No database gate is required because persistence is unchanged.

No external OANDA request is required for acceptance.

Any later opt-in credentialed check must:

- use only the same Practice `GET /summary` request;
- remain read-only;
- not alter credentials;
- not alter broker account state;
- not invoke any capital-capable endpoint.

## Explicitly out of scope

The following are not authorized in PAPER 01A:

- `TradingAccount` persistence;
- Deployment;
- PAPER activation;
- runtime coordination;
- runtime ownership or advisory locks;
- market-data streaming or live analytical frontiers;
- Strategy evaluation;
- Strategy-state persistence;
- Risk changes;
- balance/equity sizing;
- instrument entitlement discovery;
- executable quotes;
- Order creation;
- Order submission;
- Fill handling;
- Position synchronization;
- broker Trade synchronization;
- transaction history;
- transaction cursors;
- reconciliation;
- broker-hosted stop or target protection;
- START/STOP trading controls;
- frontend or API expansion;
- generalized broker abstractions;
- generalized account abstractions;
- generalized runtime infrastructure;
- PAPER 01B or later PAPER work;
- LIVE.

If any of these appears necessary during BUILD, stop and surface the requirement rather than expanding the workstream.
