# T001 — Implement read-only OANDA Practice account binding

- **Status:** `DONE`
- **Workstream:** `paper-01a-oanda-practice-account-binding`
- **Depends on:** developer approval and GIT START on `solo/paper-01a-oanda-practice-account-binding`

## Assignment

Implement the complete bounded slice defined in `../PLAN.md`: explicit account-ID configuration, one direct read-only OANDA Practice account-summary validation, the five-field immutable normalized identity, fail-closed sanitized handling, and deterministic mocked tests.

## Required implementation constraints

- Use the existing configured OANDA token and timeout values.
- Request only the explicitly configured account; never enumerate or choose credential-visible accounts.
- Permit only an HTTP `GET` to the fixed Practice account-summary endpoint.
- Accept only an exact response-ID match and USD base currency.
- Ignore and do not retain balance, NAV/equity, margin, Order, Trade, Position, and transaction fields.
- Do not add persistence, API/UI/runtime wiring, Risk/execution behavior, generalized broker abstractions, or external credential requirements.
- Stop `BLOCKED` if a schema, migration, mutating request, activation concept, or later PAPER behavior appears necessary.

## Expected seams

- `.env.example`
- `backend/config.py`
- `backend/integrations/oanda/account.py` (new)
- `backend/integrations/oanda/__init__.py`
- `backend/tests/test_config.py`
- `backend/tests/integrations/test_oanda_account.py` (new)

## Required evidence

- Exact request method, Practice URL, and configured account path.
- No-network failures for missing/malformed token/account selection.
- Success with exact normalized provider/environment/account ID/optional alias/USD currency.
- No list-based or first-account selection.
- Sanitized 4xx and exhausted transient/timeout failures.
- Fail-closed malformed JSON/schema, mismatched ID, and unsupported currency.
- Targeted tests, Ruff, and Pyright results recorded below.

## Worker Evidence

Implemented the bounded OANDA Practice account-binding slice.

- Added optional `ATLAS_OANDA_ACCOUNT_ID` configuration with four-part,
  path-safe OANDA AccountID validation and no numeric/prefix assumptions.
- Added immutable `OandaPracticeAccountIdentity` with exactly provider,
  environment, provider account ID, alias, and base currency facts.
- Added `OandaPracticeAccountValidator` and settings factory using only the
  configured token/account and the existing configured OANDA timeouts.
- The validator performs only authenticated `GET
  /v3/accounts/{configuredAccountID}/summary` against the fixed Practice base
  URL. It never lists accounts or performs mutating requests.
- Added bounded retries for transport/408/429/5xx failures and sanitized
  deterministic, transient, malformed-JSON, schema, ID-mismatch, and
  non-USD failures. Provider bodies and credentials are not retained or
  included in errors.
- Added deterministic `httpx.MockTransport` tests for request shape,
  explicit selection, no-network configuration failures, normalization,
  alias absence, list-selection absence, retry behavior, sanitization, and
  fail-closed response boundaries.

Checks:

- `uv run pytest backend/tests/test_config.py backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_source.py` — **57 passed**.
- `uv run pytest -m "not integration and not external"` — **432 passed, 4 skipped, 88 deselected**.
- Targeted Ruff format/check for the changed config, OANDA integration, and
  tests — **passed**.
- Targeted Pyright for `backend/config.py` and
  `backend/integrations/oanda/account.py` — **0 errors**.

Concerns:

- Repository-wide Ruff format/check and Pyright remain non-clean from
  pre-existing findings outside this task; no unrelated files were changed
  to address them.
- No external OANDA request, credential, persistence, API/UI, runtime, Risk,
  or execution behavior was introduced.
