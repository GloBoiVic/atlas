# VALIDATION - R002 Preserve Closure Conflicts and Attribution Uncertainty

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Remediation ID:** `R002`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Validated:** `2026-09-09`
- **Origin:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R001-dogfood-02-protected-trade-lifecycle-closure/REVIEW.md`, Findings / Concerns

## Immutable Receipt

### ROLE

`VALIDATE`

### STATUS

`PASS`

### ARTIFACT

`dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R002-dogfood-02-protected-trade-lifecycle-closure/VALIDATION.md`

### FILES CHANGED

- R002 implementation: `backend/paper/persistence_contracts.py`
- R002 implementation: `backend/paper/reconciliation.py`
- R002 implementation: `backend/paper/__init__.py`
- R002 implementation: `backend/persistence/paper_execution_repository.py`
- R002 implementation: `backend/integrations/oanda/reconciliation.py`
- R002 regression tests: `backend/tests/paper/test_persistence_contracts.py`
- R002 regression tests: `backend/tests/paper/test_reconciliation.py`
- R002 regression tests: `backend/tests/integrations/test_oanda_reconciliation.py`
- This validation receipt only: this artifact

### CHECKS / EVIDENCE

- Reviewed the frozen `PLAN.md`/`ARCHITECTURE.md`, immutable root validation failure, immutable R001 review/build/validation evidence, R002 BUILD receipt, and the complete base-to-worktree diff. The tracked resulting diff contains only the approved T001/T002/R002 seams, tests, workstream bookkeeping, and the inherited generated client; no forbidden product surface was changed.
- Exact replay: `test_identical_closed_trade_replay_is_idempotent_and_not_conflict` runs two deterministic coordinator reconciliations, retains two observations rather than duplicating them, returns `LIFECYCLE_ADVANCED` both times, and records no `CONFLICT` finding (`backend/tests/paper/test_reconciliation.py:1063-1085`). The real repository preserves this through fingerprint deduplication at `backend/persistence/paper_execution_repository.py:347-365`; the apply-boundary comparison is at `:434-512`.
- Changed aggregate economics: `test_changed_aggregate_closure_economics_is_conflict_and_append_only` changes `realized_pl`, retains the new observation append-only, returns run/reconciliation `CONFLICT`, records the existing conflict finding, suppresses `trade_closure`, and leaves three observations (`backend/tests/paper/test_reconciliation.py:1088-1115`).
- Changed exact-close economics and identity: `test_changed_exact_close_evidence_is_conflict_and_append_only` covers both changed `close_price` and changed exact transaction ID with the same append-only plus `CONFLICT`/finding/`trade_closure is None` assertions (`backend/tests/paper/test_reconciliation.py:1118-1151`). The production signature compares immutable aggregate and exact-close identity/economics at `backend/persistence/paper_execution_repository.py:1312-1354` before `apply_reconciliation_run`.
- Missing provider reason: deterministic OANDA normalization returns an attributable exact close with `provider_reason is None` and `UNRESOLVED`, while coordinator composition retains `LIFECYCLE_ADVANCED` and does not add a false conflict (`backend/tests/integrations/test_oanda_reconciliation.py:436-446`; `backend/tests/paper/test_reconciliation.py:1218-1243`).
- Oversized exact-close IDs: a 65-character request ID causes no MockTransport request, and a 65-character response-body ID raises `OandaReconciliationNormalizationError` before an observation can be constructed (`backend/tests/integrations/test_oanda_reconciliation.py:448-466`; bound enforcement at `backend/integrations/oanda/reconciliation.py:214-258,1122-1128`). The contract also bounds `PaperTradeCloseTransaction.transaction_id` to the existing 64-character persistence limit (`backend/paper/persistence_contracts.py:678-717`).
- Existing read-kind contract: an AST/model/migration probe passed for every emitted kind: `ACCOUNT_DETAILS`, `ENTRY_MUTATION_RESPONSE`, `ORDER_DETAIL`, `TAKE_PROFIT_MUTATION_RESPONSE`, `TRADE_DETAIL`, `TRANSACTION_DETAIL`, and `TRANSACTION_RANGE`. The model CHECK remains unchanged at `backend/persistence/models.py:1017-1020`; migration `0022` remains unchanged at `backend/persistence/migrations/versions/0022_paper_persistence_foundation.py:214-216`. No executable or test source contains `TRADE_CLOSE_TRANSACTION`.
- Model/migration scope: `git diff --quiet c0079e7b3f4f8bfbd00754060d37f7fdb925d649 -- backend/persistence/models.py backend/persistence/migrations` passed; no migration file is modified or newly present. `uv run alembic current` reported `0023_paper_runtime_activation (head)`, and `uv run alembic check` reported no new upgrade operations.
- Focused T001/T002/API/cross-seam tests: `uv run pytest backend/tests/paper/test_persistence_contracts.py backend/tests/integrations/test_oanda_reconciliation.py backend/tests/paper/test_reconciliation.py backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_completion_cross_seam.py backend/tests/test_api_paper.py` -> `207 passed, 1 warning`.
- Broad safe backend suite: `uv run pytest -q -m "not integration and not external"` -> `1272 passed, 4 skipped, 115 deselected, 4 warnings`.
- Changed-surface Ruff: `uv run ruff format --check` over all affected backend files -> `12 files already formatted`; `uv run ruff check` over the same surface -> `All checks passed`.
- Changed production plus R002 regression/API Pyright -> `0 errors, 0 warnings, 0 informations`. The repository-wide baseline remains non-clean: format `68 files would be reformatted`, lint `28` unrelated errors, and Pyright `3011` errors; the inherited untyped runtime test helpers are the only selected changed-test baseline issue and are outside R002.
- `git diff --check c0079e7b3f4f8bfbd00754060d37f7fdb925d649` passed. The generated OpenAPI client freshness comparison from current `create_app().openapi()` through `openapi-typescript 7.13.0` and repository Prettier was byte-identical. `npm run check:web` passed: formatting, typecheck, 18 frontend test files/91 tests, and production build; ESLint reported 242 pre-existing warnings and 0 errors. R002 made no frontend/generated-client change.
- Reconciliation remains GET-only: deterministic `httpx.MockTransport` tests assert exact close reads and GET methods; the reconciliation provider exposes reads only, and no mutation/Risk/activation/runtime-start path was invoked.
- Dedicated PostgreSQL integration was attempted with `env -u ATLAS_TEST_DATABASE_URL uv run pytest -q -m integration`: `1 passed, 97 skipped, 1277 deselected, 4 warnings, 16 setup errors`, all due missing `ATLAS_TEST_DATABASE_URL`. No database-backed append/apply execution was performed.
- No real credentials, runtime start, activation creation, real Dogfood reconciliation, Risk evaluation, or broker mutation was used.

### FINDINGS / CONCERNS

- **PRODUCT / DEFECT:** None found. R002 preserves identical replay idempotence, surfaces changed closure evidence as append-only `CONFLICT` with a conflict finding and no contradictory `tradeClosure`, preserves unresolved optional attribution without downgrading lifecycle, and fails oversized exact-close IDs before persistence-boundary observation construction.
- **REGRESSION / DEFECT:** None found. The existing V1/V2, lifecycle, execution-outcome, exact `TradeReduce.price`, read-kind, runtime safety, mutation-fence, API, and generated-contract checks remain passing.
- **TOOLING / NEW SCOPE:** Dedicated PostgreSQL integration is unavailable because `ATLAS_TEST_DATABASE_URL` is not configured. The integration result is recorded as a validation limitation, not as a product pass; the actual PostgreSQL query and append/apply transaction remain unexercised.
- **TOOLING / NEW SCOPE:** Repository-wide Ruff/Pyright baseline debt remains as reported above. No affected production or R002 regression source introduced a changed-surface static finding.
