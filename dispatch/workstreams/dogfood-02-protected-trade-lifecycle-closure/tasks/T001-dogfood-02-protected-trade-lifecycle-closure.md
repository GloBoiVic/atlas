# T001 — Closure Evidence Contracts and OANDA Normalization

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Owned artifact:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/tasks/T001-dogfood-02-protected-trade-lifecycle-closure.md`
- **Specialist skills:** `none`

## Scope

Implement the approved T001 boundary from PLAN.md and ARCHITECTURE.md:

- provider-neutral immutable closure contract;
- bounded exit-cause enum and normalized-facts V2 vocabulary/schema;
- exact CLOSED Trade aggregate normalization;
- exact one-transaction GET-only close normalization;
- OANDA provider-reason mapping, multiple/unresolved semantics, and matching `TradeReduce.price` authority;
- deterministic, bounded, normalized evidence only.

Primary ownership:

- `backend/paper/persistence_contracts.py`
- `backend/integrations/oanda/reconciliation.py`
- `backend/tests/paper/test_persistence_contracts.py`
- `backend/tests/integrations/test_oanda_reconciliation.py`

## Constraints

- Do not alter runtime reconciliation eligibility; T002 owns that seam.
- Do not alter Risk, Strategy, execution, mutation, runtime orchestration, persistence models, or migrations.
- Do not persist raw OANDA payloads or introduce realized-R/net-P/L semantics.
- Use synthetic test identities and deterministic MockTransport evidence only.
- No runtime start, PAPER activation, real OANDA credentials, real reconciliation, or broker mutation.

## Completion evidence

Update this task with the implementation receipt only after the bounded implementation and task-level tests are complete. Record files changed, checks, and concerns. Do not edit completed evidence later.

## Worker Evidence

### Immutable Receipt

- **ROLE:** `BUILD`
- **STATUS:** `DONE`
- **ARTIFACT:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/tasks/T001-dogfood-02-protected-trade-lifecycle-closure.md`
- **FILES CHANGED:**
  - `backend/paper/persistence_contracts.py`
  - `backend/paper/reconciliation.py`
  - `backend/paper/__init__.py`
  - `backend/integrations/oanda/reconciliation.py`
  - `backend/tests/paper/test_persistence_contracts.py`
  - `backend/tests/integrations/test_oanda_reconciliation.py`
- **IMPLEMENTATION:** Added frozen `PaperTradeClosure` and exact close-transaction contracts, bounded `PaperTradeExitCause`, V2 normalized closure vocabulary/schema, and contract-only reconciliation read fields/protocol. OANDA now normalizes exact CLOSED aggregate facts using `initialUnits`, performs one account/trade/transaction-scoped GET-only close read, maps provider reasons, preserves multiple/unresolved semantics, and uses matching `TradeReduce.price` as exact close-price authority. Existing V1 defaults and entry transaction semantics remain unchanged.
- **CHECKS / EVIDENCE:**
  - `uv run pytest backend/tests/paper/test_persistence_contracts.py backend/tests/integrations/test_oanda_reconciliation.py`: `42 passed`
  - `uv run pytest -m "not integration and not external"`: `1252 passed, 4 skipped, 115 deselected`
  - Changed-surface `uv run ruff format --check ...`: passed
  - Changed-surface `uv run ruff check ...`: passed
  - Changed-surface `uv run pyright backend/paper/persistence_contracts.py backend/paper/reconciliation.py backend/integrations/oanda/reconciliation.py`: `0 errors`
  - `git diff --check`: passed
  - Deterministic `httpx.MockTransport` tests assert GET-only requests, exact synthetic identities, all reason mappings, aggregate Decimal/time facts, V2 evidence, multiple IDs without fan-out, mismatch rejection, and `TradeReduce.price` authority.
- **FINDINGS / CONCERNS:** No T001 implementation concerns. Repository-wide `ruff format --check backend`, `ruff check backend`, and `pyright backend` remain non-clean because of pre-existing unrelated baseline findings; no changed-surface finding was reported. No runtime, API, persistence model, migration, Risk, Strategy, execution, mutation, or orchestration files were changed. No credentials, activation, runtime start, real reconciliation, or broker mutation was used.
