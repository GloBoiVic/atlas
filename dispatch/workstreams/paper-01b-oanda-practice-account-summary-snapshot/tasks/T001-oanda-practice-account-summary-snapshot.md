# T001 — Implement the OANDA Practice account summary snapshot

- **Status:** `DONE`
- **Workstream:** `paper-01b-oanda-practice-account-summary-snapshot`
- **Depends on:** GIT START on `solo/paper-01b-oanda-practice-account-summary-snapshot` (developer approved)

## Assignment

Implement only the approved `PLAN.md` slice: evolve the existing OANDA Practice account validator so `read_summary()` and `read_oanda_practice_account_summary(...)` perform one authenticated `/summary` request and return an immutable normalized snapshot containing the existing identity, balance, NAV, unrealized P/L, margin used/available, open Trade/Position/pending Order counts, and top-level last transaction ID.

## Required constraints

- Preserve the 01A identity-returning `validate()` and `bind_oanda_practice_account()` behavior while sharing one response-normalization path; do not add a redundant provider read.
- Parse provider financial strings as finite `Decimal` values without rejecting valid negative/zero broker facts for financial-policy reasons.
- Require exact non-negative integer counts and a valid numerical-string transaction ID; fail closed on malformed or uncertain fields.
- Keep provider payloads, detailed broker entities, nested duplicate transaction ID, credentials, and raw bodies out of the normalized contract and errors.
- Do not add persistence, API/UI, runtime, Risk, execution, reconciliation, full-account/detailed broker requests, generalized broker architecture, or capital-capable behavior.
- Stop as `BLOCKED` if the approved outcome requires a boundary outside the listed integration and test seams.

## Required evidence

- One-request success with exact Practice method/path/auth and all retained facts normalized from the same response.
- 01A identity compatibility and no duplicate `/summary` request.
- Missing/invalid/non-finite financial values, malformed/negative counts, malformed transaction ID, invalid JSON, identity mismatch, provider failure, and sanitization coverage.
- Valid adverse values and nonzero counts accepted as broker facts without Risk interpretation.
- Extra provider fields and detailed collections not exposed; no persistence or forbidden endpoint/code changes.
- Focused tests, Ruff, Pyright, preserved historical OANDA tests, and the non-integration/non-external backend suite recorded in Worker Evidence.

## Worker Evidence

### Implementation

- Added the frozen, slotted `OandaPracticeAccountSummarySnapshot` containing the
  existing identity plus the five finite financial values, three exact non-negative
  counts, and canonical top-level transaction ID.
- Added `OandaPracticeAccountValidator.read_summary()` and
  `read_oanda_practice_account_summary(...)` using the shared single authenticated
  `/v3/accounts/{configured_account_id}/summary` request seam.
- Kept `validate()` and `bind_oanda_practice_account()` identity-only and independent
  of 01B-only fields through separate identity and summary normalization paths.
- Enforced finite `Decimal` financial values, exact non-negative integer counts,
  numerical transaction IDs, nested/top-level transaction-ID agreement, and
  sanitized fail-closed normalization without exposing provider collections or raw
  payloads.
- Added deterministic MockTransport coverage for one-request success, auth/path,
  retries, adverse facts, malformed fields, provenance consistency, sanitization,
  ignored provider details, snapshot immutability, and 01A compatibility.

### Files changed

- `backend/integrations/oanda/account.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_account.py`
- This task receipt.

### Checks

- `uv run pytest backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_source.py` — **72 passed**.
- `uv run pytest -m "not integration and not external"` — **459 passed, 4 skipped, 88 deselected**.
- Targeted `ruff format --check` — **passed**.
- Targeted `ruff check` — **passed**.
- Targeted `pyright` for changed OANDA modules/tests — **0 errors, 0 warnings, 0 informations**.
- `git diff --check` — **passed** before receipt update; final receipt-only edit is whitespace-clean.

### Scope and concerns

- No persistence, API/UI, runtime, Risk, execution, reconciliation, detailed broker
  endpoint, or capital-capable behavior was added.
- No blockers or unresolved concerns.
