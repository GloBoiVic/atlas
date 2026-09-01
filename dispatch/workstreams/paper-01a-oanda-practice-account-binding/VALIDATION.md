# VALIDATION — PAPER 01A OANDA Practice Account Binding

- **Status:** `PASS`
- **Workstream:** `paper-01a-oanda-practice-account-binding`
- **Task under validation:** `T001`
- **Role:** VALIDATE

## Assignment

Independently verify the approved PAPER 01A plan, T001 receipt, exact OANDA Practice request shape, configuration and sanitization behavior, deterministic tests and checks, and the absence of persistence, runtime, API/UI, Risk, execution, reconciliation, Orders, live market data, activation, or other out-of-scope changes.

## Evidence

### Independent environment and scope check

- CWD verified as `/Users/vike/Desktop/atlas`.
- Repository root verified as `/Users/vike/Desktop/atlas`.
- Branch verified as `solo/paper-01a-oanda-practice-account-binding`.
- The implementation diff is limited to the approved configuration, OANDA
  integration, tests, `.env.example`, and workstream state/evidence files.
- No schema, migration, persistence, API/UI, runtime, Risk, execution, or
  capital-capable changes are present.
- Pre-existing untracked `.codegraph/` and `frontend/.env.local` were observed
  and left untouched, as recorded in the PLAN.

### Acceptance verification

- `ATLAS_OANDA_ACCOUNT_ID` defaults to `None`; account binding independently
  requires a non-blank token and a four-part path-safe account ID before any
  network call. Missing and malformed configuration tests assert zero handler
  calls.
- The deterministic request test observed exactly one authenticated `GET` to
  `https://api-fxpractice.oanda.com/v3/accounts/001-011-5838423-001/summary`
  with `Accept-Datetime-Format: RFC3339`. No account-list or mutating endpoint
  exists in the binding path.
- A valid response produces the frozen, slotted five-field identity: provider,
  environment, provider account ID, optional alias, and base currency. The
  returned ID must equal the configured ID; missing alias becomes `None` and
  account balance, NAV, margin, Orders, Trades, Positions, and transaction
  fields are not exposed.
- Deterministic authorization/rejection failures are not retried. Transport,
  408, 429, and 5xx failures are bounded to three attempts; `Retry-After` is
  capped at 30 seconds. Invalid JSON, malformed required/optional fields,
  mismatched IDs, and non-USD currency fail closed.
- Test assertions confirm provider bodies and the token do not enter raised
  error text. Historical OANDA behavior without an account ID remains covered
  by the passing historical-source tests.

### Checks

- Targeted tests: `uv run pytest backend/tests/test_config.py
  backend/tests/integrations/test_oanda_account.py
  backend/tests/integrations/test_oanda_source.py` — **57 passed**.
- Full non-integration/non-external suite: `uv run pytest -m "not integration and
  not external"` — **432 passed, 4 skipped, 88 deselected**; four existing
  warnings only.
- Targeted Ruff format check — **passed**.
- Targeted Ruff lint check — **passed**.
- Targeted Pyright for changed implementation modules — **0 errors**.
- `git diff --check` — **passed**.
- No external OANDA request or credentialed check was required.

### Baseline concerns

Repository-wide Ruff format/check and Pyright remain non-clean on unrelated
pre-existing files (70 files requiring format changes, 28 Ruff findings, and
2,892 Pyright errors). The changed files pass their targeted gates; no fix was
made because VALIDATE may not alter unrelated implementation or tooling state.
