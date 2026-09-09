# VALIDATION - Dogfood 02 Protected Trade Lifecycle Closure

- **Status:** `FAIL`
- **Role:** `VALIDATE`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Validated:** 2026-09-09
- **Scope:** independent validation of T001 and T002 against the frozen PLAN.md and ARCHITECTURE.md

## Result

`FAIL`. The focused deterministic implementation tests pass, but a required durable CLOSED reconciliation path cannot persist its new observation kind under the current database contract.

## Worker Evidence Reviewed

- T001 immutable receipt: `DONE`; closure contracts and OANDA normalization implemented.
- T002 immutable receipt: `DONE`; manual lifecycle eligibility, reconciliation composition, API projection, and generated client implemented.
- `PLAN.md` still reports T002 as `READY`, although its immutable task receipt reports `DONE`.

## Checks and Evidence

- `uv run pytest backend/tests/paper/test_persistence_contracts.py backend/tests/integrations/test_oanda_reconciliation.py`: `42 passed`.
- `uv run pytest backend/tests/paper/test_reconciliation.py backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_completion_cross_seam.py backend/tests/test_api_paper.py`: `158 passed`.
- `uv run pytest -q -m "not integration and not external"`: `1265 passed, 4 skipped, 115 deselected, 4 warnings`.
- Changed-surface `uv run ruff format --check` over the 11 affected backend files: `11 files already formatted`.
- Changed-surface `uv run ruff check` over the affected backend files: `All checks passed`.
- Changed production-source `uv run pyright backend/paper/persistence_contracts.py backend/paper/reconciliation.py backend/integrations/oanda/reconciliation.py backend/runtime/activation.py backend/api/schemas.py`: `0 errors, 0 warnings, 0 informations`.
- `npm run check:web`: passed; frontend tests `18 files`, `91 tests`, and production build completed. ESLint emitted `242 warnings` and `0 errors` in existing experiment components.
- `uv run alembic current`: `0023_paper_runtime_activation (head)`.
- `uv run alembic check`: no new operations detected.
- OpenAPI was regenerated from the current FastAPI app and compared with `frontend/lib/api.generated.ts`: freshness comparison passed.
- `git diff --check`: passed.
- Scope audit against the forbidden production surfaces: clean. No migration files changed; `git diff --name-only` reported 13 implementation files, none under the forbidden paths.
- `env -u ATLAS_TEST_DATABASE_URL uv run pytest -q -m integration`: unavailable dedicated PostgreSQL environment; `1 passed, 16 errors, 97 skipped, 1270 deselected`. The errors are missing `ATLAS_TEST_DATABASE_URL`; no database-backed validation was performed.
- Repository-wide `uv run ruff format --check backend`: non-clean baseline; `68 files would be reformatted`, `145 files already formatted`. No affected file was included in the changed-surface failure.
- Repository-wide `uv run ruff check backend --output-format concise`: non-clean baseline, `28 errors`, including unrelated migration/repository/test files.
- Repository-wide `uv run pyright backend --level error`: non-clean baseline, `3011 errors`; output includes untyped helpers in the changed `backend/tests/runtime/test_runtime_activation.py` at lines 778-826, while changed production-source Pyright is clean.

## Blocking Finding

**Classification:** `PRODUCT / DEFECT`

The new closure flow emits `PaperObservationReadKind.TRADE_CLOSE_TRANSACTION` from `backend/integrations/oanda/reconciliation.py:242`, but the append-only persistence contract rejects it:

- `backend/persistence/models.py:1017-1020` defines `paper_observation_read_kind` without `TRADE_CLOSE_TRANSACTION`.
- `backend/persistence/migrations/versions/0022_paper_persistence_foundation.py:214-216` creates the same incomplete CHECK constraint.
- `backend/persistence/paper_execution_repository.py:390-400` persists `observation.read_kind.value` into that constrained column.

Therefore an attributable CLOSED Trade can be normalized in memory and reach the existing append/apply boundary, but the linked closure observation will violate the database CHECK constraint. The transaction must fail closed instead of producing the required durable `LIFECYCLE_ADVANCED` plus `tradeClosure` result. This blocks acceptance criteria 30-32 and the end-to-end durable closure objective.

The defect is a material conflict with the frozen architecture's “no migration expected” decision. No migration or application fix was introduced during validation; return for architecture/product resolution.

## Authorization and Safety Audit

- No runtime was started.
- No PAPER activation was created.
- No real OANDA credentials, Dogfood identifiers, or live provider reads were used.
- No broker mutation path was invoked.
- No Risk, Strategy, execution, runtime orchestration, persistence model, or migration file was changed by validation.
- Only this validation artifact was updated, once.
