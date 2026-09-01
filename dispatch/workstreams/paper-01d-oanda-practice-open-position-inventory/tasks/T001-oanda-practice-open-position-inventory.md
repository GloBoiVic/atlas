# T001 — OANDA Practice Open Position Inventory

## Task state

- **Task:** `T001`
- **Status:** `DONE`
- **Workstream:** `paper-01d-oanda-practice-open-position-inventory`
- **Role:** `BUILD`
- **Approval:** developer approved; GIT START complete

## Assignment

Implement only the approved PAPER 01D plan. Add the narrow provider-specific OANDA `/openPositions` reader and immutable normalized open Position inventory, with independent long/short side preservation, provider-native instrument visibility, exact duplicate rejection, deterministic instrument ordering, active-side average-price validation, finite signed Decimal units, finite P/L observation, transaction provenance, bounded sanitized retries, and deterministic injected-HTTP tests.

## Owned files

- `backend/integrations/oanda/positions.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_positions.py`
- this task receipt

## Required evidence

- exact `/summary` then `/openPositions` settings-helper request sequence;
- one successful `/openPositions` GET and same-GET-only retry behavior;
- immutable contract field sets and no Atlas Position/Direction/Fill construction;
- both sides, zero-side and both-nonzero semantics;
- active/inactive `averagePrice` behavior;
- unsupported instruments, duplicate instruments, deterministic ordering, empty inventory;
- malformed/uncertain response failure and sanitized errors;
- focused OANDA tests and targeted quality checks.

## Explicit boundaries

Do not modify existing 01A–01C semantics, persistence, Risk, runtime, domain trading Position, execution, API/UI, reconciliation, ownership, accounting, activation, broker mutation, or generalized broker infrastructure.  If a boundary is required, mark this task `BLOCKED` and return for re-scoping.

## Worker Evidence

Implemented the narrow OANDA Practice open-Position observation slice:

- Added frozen/slotted provider-specific PositionSide, Position, and inventory contracts.
- Added validated-identity `/v3/accounts/{accountID}/openPositions` reader with exact GET/header/no-query behavior, bounded transient retries, `Retry-After` capping, and sanitized failures.
- Preserved independent long/short signed Decimal units, conditional average prices, finite provider P/L, unsupported instruments, exact duplicate rejection, deterministic instrument ordering, empty inventories, and observation-local transaction provenance.
- Added the settings-facing `/summary` then independent `/openPositions` helper.
- Exported only the new Position contracts, reader, normalization error, and helper from the OANDA package boundary.
- Added deterministic injected-HTTP tests covering request flow, contract fields, ignored provider facts, side semantics, average-price rules, malformed state, duplicates, ordering, empty inventory, provenance, sanitization, retries, and configuration.

### Implementation files

- `backend/integrations/oanda/positions.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_positions.py`

### Checks

- `uv run pytest backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_trades.py backend/tests/integrations/test_oanda_source.py` — **169 passed**.
- `uv run pytest -m "not integration and not external"` — **556 passed, 4 skipped, 88 deselected**; existing warnings only.
- Targeted `uv run ruff format --check ...` — **passed**.
- Targeted `uv run ruff check ...` — **passed**.
- `uv run pyright backend/integrations/oanda/positions.py backend/tests/integrations/test_oanda_positions.py` — **0 errors**.
- `git diff --check` — **passed**.

### Concerns

The inventory intentionally remains provider aggregate observation state. It does not construct or reconcile an Atlas Position, Trade, Order, Fill, Risk state, ownership state, or accounting state, and it is not persisted or capital-capable.

Repository-wide `uv run ruff check backend` and `uv run pyright backend` still report pre-existing unrelated baseline findings; the changed module and tests pass their targeted Ruff and Pyright checks.
