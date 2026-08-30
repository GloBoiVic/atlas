# T001 — Experiment deletion lifecycle

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
- Depends on: none
- Owns: the persistence/domain deletion boundary and its deterministic tests

## Frozen requirements

Implement the explicit Experiment-owned deletion service/repository boundary from
`ARCHITECTURE.md` §§2–3.4. Keep existing `RESTRICT` foreign keys; do not use ORM
cascades or introduce generic destructive-resource infrastructure.

The implementation must:

1. hard-delete only PENDING, FAILED, and COMPLETED Experiments; reject RUNNING and
   invalid states before mutation;
2. lock and re-read the Experiment and candidate snapshot as specified, preflight
   the complete order-parent graph (including cycles, dangling/external parents,
   and finite descendant depth), and reject every unclassified inbound
   cross-owner edge before the first mutation with `DELETE_OWNERSHIP_CONFLICT`;
3. delete the complete graph in the exact child-first order in §3.2, including both
   Trade order edges, order events, fills, self-referential orders, projections,
   results, gaps, and root;
4. serialize the orphan decision with the dedicated PostgreSQL transaction-scoped
   historical-load lifecycle lock, preserve snapshots for every remaining
   Experiment/load/active-load predicate, and otherwise delete only snapshot-owned
   membership/gap rows and the snapshot (never canonical bars or acquisition
   history);
5. insert exactly one minimal append-only deletion receipt in the same transaction,
   with no foreign keys to deleted rows and no tombstone/restore behavior; and
6. roll back the entire transaction on injected stage/receipt/database failure.

Do not implement the API or UI in this task. Preserve existing read semantics.

## Required proof

Add focused deterministic tests covering all status classes, partial FAILED graphs,
exact deletion ordering, graph/inbound preflight, snapshot shared/terminal/active
load retention, receipt contents and uniqueness, canonical data survival, repeated
failure rollback, and lifecycle-lock interaction seams that this task owns. Use
existing repository/test conventions and document any unavoidable integration test
boundary in the receipt.

## Completion receipt

- Status: `DONE`
- Application paths:
  - `backend/persistence/experiment_deletion.py`
  - `backend/persistence/models.py`
- Migration path:
  - `backend/persistence/migrations/versions/0021_experiment_deletion_lifecycle.py`
- Test paths:
  - `backend/tests/integration/test_experiment_deletion.py`
  - `backend/tests/integration/test_migrations.py`
  - `backend/tests/test_migration_revision.py`
  - `backend/tests/test_foundation_freeze_guards.py`
- Implementation evidence:
  - Added explicit caller-transaction deletion repository/service with locked
    status/snapshot preflight, complete graph and order-parent validation, exact
    child-first deletion, lifecycle advisory-lock seam, conditional snapshot
    cleanup, and atomic identity-only receipt insertion.
  - Added the receipt table and transaction-local guarded-delete migration while
    preserving `RESTRICT` foreign keys and append-only behavior outside this
    reviewed operation.
- Added deterministic PostgreSQL integration coverage for clean deletion,
  canonical-bar retention, RUNNING rejection, receipt content, stage ordering,
  rollback after an injected stage failure, and malformed direct diagnostic/Trade
  ownership edges that fail closed without mutation.
- F-001 remediation: `0021` downgrade now restores the exact eight pre-0021
  guarded trigger bodies before dropping `atlas_deletion_context_matches(UUID)`;
  the downgrade smoke asserts all trigger functions exist, the helper is absent,
  representative guarded UPDATE/DELETE operations still reject, and head can be
  upgraded again.
- F-002 remediation: deletion preflight now selects every direct diagnostic and
  Trade for the target Experiment in addition to inbound target edges, and
  rejects any intent/risk/order edge outside the collected target sets before
  mutation.
- R-001 remediation: migration `0021` now reconciles the legacy Phase 3
  `prevent_fact_mutation`, `prevent_order_fact_mutation`, and
  `prevent_completed_trade_mutation` triggers with the reviewed deletion
  context. Ordinary UPDATE/DELETE remains immutable without that context, and
  downgrade restores their exact pre-0021 bodies before dropping the helper.
- R-004 remediation: added populated PENDING/FAILED/COMPLETED graph proof,
  representative partial FAILED graphs, self/multi-node and external-parent
  preflight proof, receipt-insertion rollback, rollback after every explicit
  deletion stage, direct immutable-DML proof, and a PostgreSQL inbound-FK
  inventory guard for every FK into `trade_intents`, `risk_decisions`, and
  `orders`; parent-depth traversal is iterative so finite valid chains are not
  constrained by Python recursion depth.
- Checks / evidence:
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' pytest -q backend/tests/integration/test_migrations.py` — 3 passed, including head→0020→head downgrade and guarded-DML smoke.
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' pytest -q backend/tests/integration/test_experiment_deletion.py` — 36 passed; 1 existing deprecation warning.
- Combined migration/deletion proof — 39 passed; 1 existing Starlette/httpx TestClient deprecation warning.
- Final T001 focused persistence/migration/guard proof — 46 passed; 1 existing
  Starlette/httpx TestClient deprecation warning.
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' pytest -q backend/tests/integration/test_experiment_lifecycle.py` — 5 passed.
  - `ruff check` on all changed application, migration, and test paths — passed.
  - `git diff --check` and Python compilation of changed application/migration/test modules — passed.
  - Alembic script graph inspection — head `0021_experiment_deletion`.
  - `pytest -q backend/tests/test_foundation_freeze_guards.py backend/tests/test_migration_revision.py backend/tests/experiments/test_result_state.py` — 7 passed.
- `pyright backend/persistence/experiment_deletion.py backend/persistence/models.py` — 0 errors.
- Concerns:
   - None for the T001 remediation. The populated deletion and downgrade cycle
     pass against the dedicated PostgreSQL database; the one warning is the
     existing Starlette/httpx TestClient deprecation warning.
   - Completed survivor API/read equivalence remains the T005-owned read seam;
     T001 covers persisted receipt provenance, canonical-data survival, and
     deletion of the selected populated graph only.
  - Historical-load activation and API/UI implementation remain owned by T002/T005.

Do not edit `PLAN.md`, `ARCHITECTURE.md`, `ACTIVE.md`, or another task artifact.

## Approved review remediation — R-001 and R-004

- R-001: reconcile legacy immutable triggers with the reviewed deletion context;
  ordinary immutable UPDATE/DELETE remains fail-closed; preserve exact downgrade
  behavior. Add genuinely populated graph proof for PENDING/FAILED/COMPLETED,
  including Trade/order/fill/risk/intent/diagnostic/projection/result/gap facts,
  migration upgrade/downgrade, receipt failure, and stage rollback.
- R-004 portions owned here: add only minimum deterministic coverage for
  representative partial FAILED graphs, order self/multi-node cycles and
  malformed depths, receipt insertion rollback, one parameterized rollback matrix
  across every explicit deletion stage, the inbound-FK inventory guard, and
  populated deletion/read proof needed by the frozen architecture.

Use the dedicated `*_test` database. Preserve all frozen contracts and do not
edit role artifacts or other task artifacts. Update this receipt with remediation
paths, checks, and final status.
