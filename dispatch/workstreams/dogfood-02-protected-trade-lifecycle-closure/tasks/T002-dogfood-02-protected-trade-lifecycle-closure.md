# T002 — Lifecycle Reconciliation Composition and Public Result

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Owned artifact:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/tasks/T002-dogfood-02-protected-trade-lifecycle-closure.md`
- **Specialist skills:** `none`
- **Dependency:** T001 must be `DONE` before this task becomes `READY`.

## Scope

Implement the approved T002 boundary from PLAN.md and ARCHITECTURE.md:

- separate explicit manual-reconciliation eligibility from `is_unsafe_paper_attempt()`;
- healthy `FILLED_PROTECTED` lifecycle checks and bounded no-op for lifecycle-complete attempts;
- OPEN → `CONSISTENT` and CLOSED → `LIFECYCLE_ADVANCED` composition;
- optional one-read closing-transaction enrichment and uncertainty behavior;
- durable linked observations through the existing append/apply transaction;
- bounded `tradeClosure` result and HTTP response, including generated client only if required.

Primary ownership:

- `backend/paper/reconciliation.py`
- `backend/runtime/activation.py`
- `backend/api/schemas.py`
- `backend/api/paper.py` only if projection requires it
- `frontend/lib/api.generated.ts` generated only if the HTTP schema changes
- `backend/tests/paper/test_reconciliation.py`
- `backend/tests/runtime/test_runtime_activation.py`
- existing PAPER API tests owning the reconcile route

## Constraints

- Depends on T001 contracts; do not duplicate or redefine them.
- Leave `is_unsafe_paper_attempt()` and new-session/recovery semantics unchanged.
- Preserve the active-runtime busy fence.
- Do not alter Risk, Strategy, execution, mutation, runtime orchestration, persistence models, or migrations.
- Do not persist raw OANDA payloads or introduce realized-R/net-P/L semantics.
- Use synthetic test identities and deterministic Mock/spy evidence only.
- No runtime start, PAPER activation, real OANDA credentials, real reconciliation, or broker mutation.

## Completion evidence

Update this task with the implementation receipt only after the bounded implementation and task-level tests are complete. Record files changed, checks, and concerns. Do not edit completed evidence later.

## Worker Evidence

### Immutable Receipt

- **ROLE:** `BUILD`
- **STATUS:** `DONE`
- **ARTIFACT:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/tasks/T002-dogfood-02-protected-trade-lifecycle-closure.md`
- **FILES CHANGED:**
  - `backend/paper/reconciliation.py`
  - `backend/runtime/activation.py`
  - `backend/api/schemas.py`
  - `backend/tests/paper/test_reconciliation.py`
  - `backend/tests/runtime/test_runtime_activation.py`
  - `backend/tests/test_api_paper.py`
  - `frontend/lib/api.generated.ts`
  - `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/tasks/T002-dogfood-02-protected-trade-lifecycle-closure.md`
- **IMPLEMENTATION:** Added a separate manual lifecycle-reconciliation eligibility check requiring a coherent durable Fill for healthy `FILLED_PROTECTED + NOT_RUN/CONSISTENT` attempts, with an explicit no-op for lifecycle-complete attempts. The coordinator now preserves OPEN as `CONSISTENT`, composes CLOSED aggregate closure with at most one exact close-transaction read, keeps `LIFECYCLE_ADVANCED` when enrichment is unavailable or unresolved, preserves `MULTIPLE` semantics, and links successful observations to the same run. Added bounded runtime/API `tradeClosure` projection with exact string financial values and regenerated the OpenAPI client through the existing workflow. `is_unsafe_paper_attempt()`, active-runtime fencing, recovery/new-session behavior, Risk, Strategy, execution, mutation, orchestration, persistence models, and migrations were not changed.
- **CHECKS / EVIDENCE:**
  - `uv run pytest backend/tests/paper/test_reconciliation.py backend/tests/runtime/test_runtime_activation.py backend/tests/test_api_paper.py`: `145 passed`
  - `uv run pytest -m "not integration and not external"`: `1265 passed, 4 skipped, 115 deselected`
  - Changed-surface `uv run ruff format --check ...`: passed
  - Changed-surface `uv run ruff check ...`: passed
  - Changed-surface `uv run pyright backend/paper/reconciliation.py backend/runtime/activation.py backend/api/schemas.py`: `0 errors`
  - `npm run typecheck:web`: passed
  - OpenAPI regeneration via `create_app().openapi()` -> `openapi-typescript 7.13.0` -> Prettier; `cmp` against `frontend/lib/api.generated.ts`: passed
  - `uv run alembic current`: `0023_paper_runtime_activation (head)`; `uv run alembic check`: no new operations
  - `git diff --check`: passed
- **FINDINGS / CONCERNS:** No T002 implementation concerns. Repository-wide `ruff format --check backend`, `ruff check backend`, and `pyright backend` remain non-clean because of pre-existing unrelated baseline findings; the changed-surface checks are clean. No migration, credential, runtime start, activation, real reconciliation, or broker mutation was used.
