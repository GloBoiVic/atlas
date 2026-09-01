# T001 — PAPER 01E OANDA Practice Pending Order Identity Inventory

## Task state

- **Task:** `T001`
- **Status:** `DONE`
- **Workstream:** `paper-01e-oanda-practice-pending-order-identity-inventory`
- **Role:** `BUILD`
- **Approval:** approved by developer; GIT START complete

## Assignment

Implement only the approved PAPER 01E plan. Add the narrow provider-specific OANDA `/pendingOrders` reader and immutable normalized pending-Order identity inventory. Retain only the raw positive provider Order ID, recognized documented provider Order type, exact `PENDING` state, validated Practice identity, and response-local transaction provenance. Reuse the merged shared requester and transaction-ID primitive without modifying them.

## Owned files

- `backend/integrations/oanda/orders.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_orders.py`
- this task receipt

## Required evidence

- exact `/summary` then `/pendingOrders` settings-helper sequence;
- one successful `/pendingOrders` GET and same-GET-only retry behavior;
- frozen/slotted provider-only field sets and no Atlas execution `Order` construction;
- all documented recognized types, unknown-type fail-closed behavior, and ignored malformed type-specific fields;
- exact raw Order-ID validation, leading-zero total ordering, duplicate rejection, empty inventory, strict `PENDING` state, and provenance;
- malformed/uncertain response failure, sanitized errors, focused OANDA regression tests, and targeted quality checks.

## Explicit boundaries

Do not modify `request.py`, `primitives.py`, `source.py`, `account.py`, `trades.py`, or `positions.py`; persistence, Risk, runtime, domain trading, execution, API/UI, reconciliation, ownership, accounting, activation, broker mutation, Order interpretation, or generalized broker infrastructure. If a frozen boundary is required, mark this task `BLOCKED` and return for re-scoping.

## Worker Evidence

- Added `backend/integrations/oanda/orders.py` with the provider-only frozen/slotted
  pending-Order contracts, strict common-envelope normalization, positive raw Order-ID
  validation, duplicate rejection, deterministic raw-preserving numeric ordering,
  strict `PENDING` state, response provenance, and the `/pendingOrders` reader/helper.
- Exported only the new pending-Order error, contracts, reader, and settings-facing
  helper from `backend.integrations.oanda`.
- Added deterministic injected-HTTP coverage for account binding and request shape,
  all seven pending-capable types, ignored malformed type-specific fields, malformed
  and uncertain responses, identity/order-ID/state rules, duplicate and ordering
  behavior, empty inventory, provenance, retries, sanitization, immutability, and
  configuration.
- Checks passed:
  - `uv run pytest backend/tests/integrations/test_oanda_orders.py backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_trades.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_request.py backend/tests/integrations/test_oanda_primitives.py backend/tests/integrations/test_oanda_source.py` — 309 passed.
  - `uv run ruff format --check backend/integrations/oanda/orders.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_orders.py` — passed.
  - `uv run ruff check backend/integrations/oanda/orders.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_orders.py` — passed.
  - `uv run pyright backend/integrations/oanda/orders.py backend/tests/integrations/test_oanda_orders.py` — 0 errors.
  - `uv run pytest -m "not integration and not external"` — 696 passed, 4 skipped, 88 deselected.
  - `git diff --check` — passed.
- No frozen shared OANDA seam, execution type, persistence, Risk, runtime, API/UI,
  reconciliation, or broker mutation was changed. No known concerns.
