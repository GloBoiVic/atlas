# R001 — Reuse the Existing Transaction Observation Kind

- **Remediation ID:** `R001`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Origin finding:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/VALIDATION.md`, Blocking Finding
- **Finding severity:** `IMPORTANT`
- **Finding classification:** `PRODUCT / DEFECT`
- **Related original tasks:** T001, T002

## Approved Requirement or Invariant Violated

Closure evidence must be durably stored through the existing append-only broker-observation ledger, existing V1 observations must remain valid, and no database migration may be introduced. The current closure reader emits `PaperObservationReadKind.TRADE_CLOSE_TRANSACTION`, which is rejected by the existing database CHECK constraint in `models.py` and migration `0022`.

## Exact Remediation Outcome

Make the exact closing-transaction observation use the existing `PaperObservationReadKind.TRANSACTION_DETAIL` value while retaining the narrow `read_trade_close_transaction()` provider method, V2 normalized closure facts, exact Trade attribution, and all closure semantics. The existing database model and migrations must remain untouched. Durable closure reconciliation must no longer emit a read-kind value outside the current database CHECK constraint.

## Affected Implementation Seams

- `backend/paper/persistence_contracts.py`
- `backend/integrations/oanda/reconciliation.py`
- `backend/tests/paper/test_persistence_contracts.py` if contract coverage needs adjustment
- `backend/tests/integrations/test_oanda_reconciliation.py`
- directly affected T002 reconciliation tests only if required to update the read-kind expectation

## Explicit Out Of Scope

- Any change to `backend/persistence/models.py` or `backend/persistence/migrations/**`.
- Any new migration or schema change.
- Any change to runtime eligibility, reconciliation composition, API projection, Risk, Strategy, execution, mutation, orchestration, or UI.
- Any new provider abstraction, polling, activation, runtime start, real OANDA read, Dogfood reconciliation, or broker mutation.
- Any change to closure economics, exit-cause mapping, or V1/V2 semantics beyond the read-kind correction.

## Regression Evidence Required

- Existing focused T001/T002 tests pass with the corrected observation kind.
- Close-transaction normalization remains GET-only, exact, V2, attributable, and uses `TradeReduce.price`.
- Durable observation vocabulary is accepted by the current model/migration contract; no migration is generated.
- Safe backend and relevant formatting/lint/type checks remain clean on the changed surface.
- `uv run alembic check` reports no new operations.

## Worker Evidence

### Immutable Receipt

- **ROLE:** `BUILD`
- **STATUS:** `DONE`
- **ARTIFACT:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R001-dogfood-02-protected-trade-lifecycle-closure/BUILD.md`
- **FILES CHANGED:**
  - `backend/paper/persistence_contracts.py`
  - `backend/integrations/oanda/reconciliation.py`
  - `backend/tests/paper/test_reconciliation.py`
  - `backend/tests/integrations/test_oanda_reconciliation.py`
- **IMPLEMENTATION:** Removed the unsupported `TRADE_CLOSE_TRANSACTION` observation kind and used the existing `PaperObservationReadKind.TRANSACTION_DETAIL` for both exact close-transaction observation paths. The narrow `read_trade_close_transaction()` method, V2 closure facts, exact attribution, `TradeReduce.price` authority, and lifecycle/cause semantics remain unchanged.
- **CHECKS / EVIDENCE:**
  - Focused T001/T002 regression tests: `200 passed, 1 warning`.
  - Broad safe backend suite `uv run pytest -q -m "not integration and not external"`: `1265 passed, 4 skipped, 115 deselected, 4 warnings`.
  - Changed-surface `uv run ruff format --check`: `4 files already formatted`.
  - Changed-surface `uv run ruff check`: `All checks passed`.
  - Changed production-source `uv run pyright backend/paper/persistence_contracts.py backend/integrations/oanda/reconciliation.py`: `0 errors, 0 warnings, 0 informations`.
  - `git diff --check`: passed.
  - `uv run alembic check`: no new upgrade operations detected.
  - Deterministic OANDA tests continue to assert GET-only exact close reads, V2 normalized facts, exact attribution, and `TradeReduce.price`; the close observation now asserts `TRANSACTION_DETAIL`.
- **FINDINGS / CONCERNS:** No R001 concerns. `backend/persistence/models.py` and `backend/persistence/migrations/**` were not changed; no migration, credential, runtime, activation, real reconciliation, or broker mutation was used.
