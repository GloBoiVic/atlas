# R002 — Preserve Closure Conflicts and Attribution Uncertainty

- **Remediation ID:** `R002`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Origin finding:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R001-dogfood-02-protected-trade-lifecycle-closure/REVIEW.md`, Findings / Concerns
- **Finding severity:** `IMPORTANT` primary; related `MINOR` findings included
- **Finding classification:** `PRODUCT / DEFECT`
- **Related original tasks:** T001, T002
- **Related remediation:** R001

## Approved Requirement or Invariant Violated

Frozen ARCHITECTURE.md 3.2.8 and acceptance criterion 31 require contradictory closure evidence to remain append-only and not be silently overwritten or selected as successful latest truth. Frozen closure failure behavior also requires a proven CLOSED lifecycle to survive optional attribution uncertainty, while unresolved provider identity/evidence must not be manufactured as conflict. Provider IDs must remain within the existing bounded persistence contract.

## Exact Remediation Outcome

- Detect incompatible aggregate CLOSED-Trade facts and incompatible exact closing-transaction facts against prior normalized closure observations for the same attempt/exact Trade/close evidence before treating the new result as successful.
- Preserve append-only observations, but return bounded `CONFLICT` with a conflict finding and no successful closure projection when incompatible closure economics or exact-close identity are observed.
- Treat an exactly attributable closing transaction with a missing optional provider reason as `UNRESOLVED` attribution while retaining `LIFECYCLE_ADVANCED` and aggregate closure evidence.
- Reject exact closing transaction IDs that exceed the existing 64-character `provider_transaction_id` persistence bound.
- Keep exact replay idempotent, all existing V1/V2 semantics intact, and all current lifecycle/Risk/mutation boundaries unchanged.

## Affected Implementation Seams

- `backend/paper/persistence_contracts.py`
- `backend/paper/reconciliation.py`
- `backend/persistence/paper_execution_repository.py` only as required to read/compare existing append-only normalized closure observations at the current apply boundary
- `backend/integrations/oanda/reconciliation.py`
- directly affected existing tests in `backend/tests/paper/test_persistence_contracts.py`, `backend/tests/paper/test_reconciliation.py`, and `backend/tests/integrations/test_oanda_reconciliation.py`

## Explicit Out Of Scope

- Any change to `backend/persistence/models.py` or `backend/persistence/migrations/**`.
- Any new migration, closure projection/table, API schema, generated client, or UI change.
- Any change to runtime eligibility, active-runtime fencing, Risk, Strategy, execution, mutation, orchestration, or provider scope.
- Any polling, activation, runtime start, real OANDA read, Dogfood reconciliation, or broker mutation.
- Any new financial metric, net P/L, realized-R, or broad provider abstraction.

## Regression Evidence Required

- Repeated identical closure evidence remains idempotent and does not become conflict.
- Changed aggregate economics or exact-close economics/identity are append-only and surface `CONFLICT` without returning the changed closure as successful.
- Missing provider reason remains lifecycle advanced with `UNRESOLVED` exit cause and no false conflict.
- Oversized exact close transaction IDs fail closed before persistence-boundary failure.
- Existing focused T001/T002 tests, safe backend tests, changed-surface format/lint/type checks, `git diff --check`, and Alembic current/check pass.
- Models and migrations are unchanged and no migration is generated.

## Worker Evidence

### Immutable Receipt

- **ROLE:** `BUILD`
- **STATUS:** `DONE`
- **ARTIFACT:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R002-dogfood-02-protected-trade-lifecycle-closure/BUILD.md`
- **FILES CHANGED:**
  - `backend/paper/persistence_contracts.py`
  - `backend/paper/reconciliation.py`
  - `backend/paper/__init__.py`
  - `backend/persistence/paper_execution_repository.py`
  - `backend/integrations/oanda/reconciliation.py`
  - `backend/tests/paper/test_persistence_contracts.py`
  - `backend/tests/paper/test_reconciliation.py`
  - `backend/tests/integrations/test_oanda_reconciliation.py`
- **IMPLEMENTATION:** Added a bounded apply-boundary query over prior V2 closure observations. Changed aggregate or exact-close economics/identity remains append-only but changes the current run to `CONFLICT`, records the existing conflict finding, and suppresses the contradictory `tradeClosure`. Exact replay remains idempotent. Missing close reasons now preserve exact attribution with `UNRESOLVED`; exact close-read transaction IDs are limited to the existing 64-character persistence bound before evidence construction. V1/V2, `TradeReduce.price`, GET-only, and all lifecycle/safety boundaries remain intact; models and migrations were not changed.
- **CHECKS / EVIDENCE:**
  - Focused R002 regressions: `uv run pytest backend/tests/paper/test_reconciliation.py backend/tests/integrations/test_oanda_reconciliation.py backend/tests/paper/test_persistence_contracts.py` -> `81 passed`.
  - Broad safe backend suite: `uv run pytest -m "not integration and not external"` -> `1272 passed, 4 skipped, 115 deselected, 4 warnings`.
  - Changed-surface Ruff format/check -> passed; changed-surface Pyright over production and regression files -> `0 errors`.
  - `uv run alembic current` -> `0023_paper_runtime_activation (head)`; `uv run alembic check` -> no new upgrade operations.
  - `git diff --check` -> passed.
  - Deterministic tests cover identical replay, changed aggregate economics, changed exact-close economics and identity, missing reason, oversized request/body IDs, append-only evidence, and no false conflict.
  - Full repository Ruff checks retain known unrelated baseline debt: `68 files would be reformatted`, `28 lint errors`; no changed-surface file is included.
- **FINDINGS / CONCERNS:** No R002 product or scope concerns. Dedicated PostgreSQL integration was attempted with `env -u ATLAS_TEST_DATABASE_URL uv run pytest -q -m integration` but is unavailable in this workspace (`1 passed, 97 skipped, 16 setup errors` due the missing dedicated test URL); no database-backed R002 execution was performed. No credentials, runtime start, activation, real reconciliation, Risk evaluation, or broker mutation was used. No model or migration file changed.
