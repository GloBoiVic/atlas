# T007 — API and status projection

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T002, T006
- **Owned artifact:** this file

## Objective

Expose the approved local HTTP capability, activation, active/detail status, STOP, and reconcile routes with separate runtime and broker/exposure projections.

## Required boundaries

- Use the existing FastAPI/local-authority patterns and exact approved route/request/response semantics.
- Do not expose credentials, tokens, raw provider payloads, unbounded exception text, or caller-selected forbidden authority.
- Status must distinguish lifecycle, operational phase, current financial position, execution outcome, reconciliation status, and the fact that terminal runtime state does not prove flatness.
- No frontend work unless explicitly required by the existing API seam.

## Evidence required

- FastAPI contract/authorization/status tests, secret-redaction checks, and no-provider-call activation route evidence.

## Completion receipt

Implemented the local FastAPI PAPER capability and control surface over the
T002 service boundary.  The six approved routes now expose strict activation
input, capability, active/detail status, idempotent STOP, and bounded
GET-only reconciliation projections.  Local authority remains enforced by the
existing actual-peer middleware, runtime lifecycle and broker/exposure status
remain separate, and route/validation failures are bounded without echoing
provider payloads or credential material.

### Files changed

- `backend/api/app.py`
- `backend/api/paper.py`
- `backend/api/schemas.py`
- `backend/tests/test_api_paper.py`

### Checks and evidence

- Focused API/activation tests: `14 passed`.
- Full non-integration/non-external backend suite: `1025 passed, 4 skipped, 104 deselected`.
- Changed-slice Ruff format/check: passed.
- Changed API route/schema Pyright (`--threads 1`): `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: passed.
- Tests cover exact camel-case request/response projections, decimal-wire and
  unknown-field rejection, local-peer enforcement, active/detail not-found
  contracts, STOP/reconcile forwarding, separate status projections, and
  service/unexpected error redaction.
- No OANDA calls, PAPER activation, credentials, or broker mutation were used.

### Concerns / handoff

- `backend/api/app.py` retains pre-existing strict-Pyright diagnostics from its
  broad `Any`-typed app-factory seams; the changed route/schema slice is clean.
- PostgreSQL migration/concurrency and cross-seam completion remain T008 scope.
