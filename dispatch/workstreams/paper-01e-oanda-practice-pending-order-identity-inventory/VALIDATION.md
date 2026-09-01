# VALIDATION — PAPER 01E OANDA Practice Pending Order Identity Inventory

## Status

- **Status:** `PASS`
- **Workstream:** `paper-01e-oanda-practice-pending-order-identity-inventory`
- **Task:** `T001`
- **Role:** `VALIDATE`

## Scope

Independently verify the approved PAPER 01E plan, the completed T001 receipt, the
implementation/test diff, focused OANDA regression evidence, and the targeted quality
checks. No application or test files may be changed by VALIDATE.

## Required checks

- pending `/summary` account binding followed by independent `/pendingOrders` observation;
- exact Practice endpoint, authenticated GET, no query parameters, and same-GET-only retries;
- provider-only frozen/slotted contracts and approved retained fields;
- seven accepted types, contradictory/unknown types, ignored type-specific fields;
- exact raw positive Order-ID handling, duplicate failure, deterministic leading-zero ordering;
- exact `PENDING` state, empty inventory, response-local transaction provenance;
- fail-closed malformed responses, no partial output, and sanitized errors;
- no frozen seam, persistence, reconciliation, execution, Risk/runtime/API/UI, or mutation changes;
- focused OANDA tests, targeted quality checks, non-integration suite, and diff hygiene.

## Worker Evidence

Independent validation completed on the requested branch and repository root.

## Acceptance Evidence

- `read_oanda_practice_pending_order_inventory` calls the existing account binding
  first, then performs the independent `/v3/accounts/{accountID}/pendingOrders`
  GET. Tests verify exact `/summary` → `/pendingOrders` sequencing, Practice
  account identity, bearer/RFC3339 headers, GET method, and no query parameters.
- `orders.py` reuses `OandaObservationRequester` and `parse_transaction_id`; no
  changes were made to the shared request/primitive seams. Retry coverage verifies
  bounded same-GET retries and `Retry-After` capping.
- Provider contracts are frozen and slotted. The normalized Order exposes only
  `provider_order_id`, `provider_order_type`, and `state`; the inventory exposes
  only validated `identity`, immutable `orders`, and response-local
  `last_transaction_id`. No Atlas execution `Order` or other execution/domain
  object is imported or constructed.
- Tests cover all seven accepted pending-capable provider types, fail-closed
  `MARKET`, `FIXED_PRICE`, and unknown types, ignored malformed/missing
  type-specific fields, exact positive raw IDs, all-zero/malformed IDs, duplicate
  IDs, leading-zero numeric ordering with raw tie-breaking, strict `PENDING`
  state, empty inventories, provenance, malformed responses, no partial output,
  sanitization, token/configuration failures, and immutability.
- Working-tree inspection shows only the planned OANDA export, new
  `orders.py`, new focused tests, and the expected dispatch workstream/ACTIVE
  artifacts. No persistence, reconciliation, Risk, runtime, API/UI, execution,
  or broker-mutation files changed.

## Checks

- Focused OANDA suite (orders, account, trades, positions, request, primitives,
  source): **309 passed**.
- Non-integration/non-external suite: **696 passed, 4 skipped, 88 deselected**.
- Targeted Ruff format: **passed**.
- Targeted Ruff lint: **passed**.
- Targeted Pyright: **0 errors, 0 warnings, 0 informations**.
- `git diff --check` plus explicit checks for the two new untracked files:
  **passed**.

## Result

**PASS.** T001 satisfies the approved bounded read-only observation contract.
No credentialed external OANDA request was performed. The four non-blocking
pytest warnings in the broad suite are pre-existing dependency/unknown-mark
warnings and do not affect this slice.
