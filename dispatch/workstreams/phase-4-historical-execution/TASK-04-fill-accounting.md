# Task 04 — Fill accounting receipt

## Changed paths

- `backend/execution/fill_application.py`
- `backend/persistence/trading_repository.py`
- `backend/tests/integration/test_fill_application.py`

## Implemented

- Extended the caller-owned savepoint transition so a Phase 4 Fill, order status,
  immutable `OrderEvent`, Position projection, Trade projection, and simulated
  account changes flush as one atomic unit.
- Added Phase 4 submission/filled event sequencing, Fill provenance details,
  commission accounting, net P&L, initial risk/R multiple, and
  `END_OF_EXPERIMENT` completion semantics while retaining legacy behavior.
- Allocated Trade sequence numbers per Experiment, allowing sequential Trades
  without changing the one-Position projection.
- When a protection Fill closes a Trade, terminally canceled protection siblings
  and appended cancellation events within the same transition. Ambiguity facts
  can be attached to the affected completed Trade.
- Repository-created Orders now receive their immutable `ORDER_CREATED` event.

## Atomic/state guarantees

The outer transaction remains caller-owned. `apply_fill` uses a nested savepoint,
locks the Order, Position, and account, and rolls back the Fill, events, lifecycle
status, sibling cancellation, projections, and costs together on validation or
state failure. Exposure changes originate only from a Fill; Order submission alone
does not update Position, Trade, or account state. Financing remains `NULL` and is
not fabricated.

## Validation

- `uv run pytest backend/tests/integration/test_fill_application.py` — **2 passed**
- `uv run pytest backend/tests/integration/test_golden_flows.py` — **2 passed**
- `uv run ruff check backend/execution/fill_application.py backend/persistence/trading_repository.py backend/tests/integration/test_fill_application.py` — **passed**
- `python -m compileall -q backend/execution backend/persistence` — **passed**

## Exclusions

No runner loop/results fingerprint, clock, pure execution behavior, API/UI/runtime,
broker, PAPER/LIVE, reconciliation, financing engine, equity sampling orchestration,
or general infrastructure was added. Existing unrelated workstream changes and

## Blockers

None.
