# Foundation Freeze 07 Validation

Status: `PASS — targeted R-001–R-005 revalidation`

Role: `VALIDATE`
Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
Branch: `solo/foundation-freeze-07-experiment-lifecycle-local-authority`

## Scope and environment

Fresh validation was limited to the changed areas from REVIEW R-001–R-005.
Prior passing evidence is preserved by reference; unrelated broad suites were
not rerun. No pre-PAPER audit, PAPER, or LIVE work was performed.

PostgreSQL checks used only:

`ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test`

The validation database was at Alembic `0021_experiment_deletion (head)` before
and after validation. `alembic check` reported no pending operations. Migration
tests exercised the head → 0020 → head cycle; no reset of a non-validation
database was performed.

## Fresh targeted evidence

### R-001 — populated deletion and legacy guards

**PASS.**

- `backend/tests/integration/test_experiment_deletion.py`: **37 passed**.
  This covers populated PENDING/FAILED/COMPLETED graphs, representative partial
  FAILED shapes, exact child-first ordering, both Trade order edges, fills,
  events, protections, projections, result/gap rows, receipt content and
  receipt-failure rollback, rollback after every explicit stage, cycles,
  malformed/external parents, inbound-FK inventory, repeated delete, and
  surviving completed-read equivalence.
- `backend/tests/integration/test_migrations.py`,
  `backend/tests/test_migration_revision.py`, and
  `backend/tests/test_foundation_freeze_guards.py`: **10 passed**. This includes
  upgrade/downgrade restoration and guarded UPDATE/DELETE DML at 0020; ordinary
  immutable DML remains fail-closed while the reviewed deletion context permits
  only the deletion operation.
- Migration state was rechecked with `alembic current` and `alembic check`:
  head/current clean.

### R-004 — deletion, snapshot retention, and lock proof

**PASS.**

- `backend/tests/integration/test_snapshot_lifecycle_locks.py` and
  `backend/tests/integration/test_experiment_lifecycle.py`: **15 passed**.
  Shared, terminal-load, active-load-without-attachment retention, both
  lifecycle activation race directions for new PENDING and FAILED → RUNNING,
  deletion-first ordering, and bounded snapshot-first/lifecycle no-deadlock
  proof all passed.
- `backend/tests/test_historical_data_load.py`: **29 passed**, including the
  snapshot-first attachment paths and insufficient-warm-up preservation.
- Strategy composition regression selection:
  `backend/tests/domain/test_strategy_capability_composition.py`,
  `backend/tests/strategies/test_contract.py`, and
  `backend/tests/strategies/test_legacy_strategy_isolation.py`: **19 passed**.
  Prior broader provider-neutral behavior evidence remains preserved by the T004
  receipt.

### R-002 — scoped IPv6 and local authority

**PASS.**

- `backend/tests/test_local_authority.py`, `backend/tests/test_api_health.py`,
  and `backend/tests/integration/test_api_experiments.py`: **58 passed**.
  Raw/bracketed/encoded/decoded scoped IPv6 peer and Host/`:authority` forms are
  denied before routing; valid IPv4/IPv6/mapped loopback and `localhost` pass.
  Spoofed forwarding headers, non-loopback peers, authority disagreement,
  resolver isolation, pre-routing denial, and lifespan are covered.
- The local API was run with the supported
  `uvicorn backend.api.app:create_app --factory --host 127.0.0.1 --port 8000
  --no-proxy-headers` command. A health request after restart returned ready with
  database `ok`.

### R-003 — accessible modal failure handling

**PASS.**

- Focused Vitest run for
  `frontend/tests/experiment_delete.test.tsx` and
  `frontend/tests/api_client.test.ts`: **10 passed**. Assertions cover visible
  dialog-contained errors for `EXPERIMENT_DELETE_FAILED`,
  `LOCAL_PEER_REQUIRED`, unavailable/transport timeout, retained typed
  `DELETE`, no deletion retry, disabled pending controls, and one request.
- Fresh Local Host failure workflow: after opening the real dialog and typing
  exact `DELETE`, the local API was stopped and the action was submitted once.
  The active dialog visibly retained the typed value and displayed
  `Atlas API returned 500` with no navigation; the accessibility snapshot
  exposed the dialog and its controls, and console diagnostics were empty. The
  unrelated completed-result `Retry` control remained outside the deletion
  dialog; no deletion retry control was present in the dialog.

### R-005 — canonical artifact consistency

**PASS.**

- `ARCHITECTURE.md` is `FROZEN — implementation authorized` and its final gate
  records approval; it contains no stale pre-authorization gate.
- `PLAN.md` records targeted validation, all five tasks `DONE`, and targeted
  rereview as the next action. `ACTIVE.md` records the VALIDATE phase, the
  expected branch, and the same workstream/base SHA.
- All five task headers and completion receipts are `DONE`. The old approval
  language remains only as quoted historical evidence in the initial `REVIEW.md`
  and does not contradict the active PLAN/ARCHITECTURE lifecycle.

## Static and workflow checks

- Focused Pyright for the remediation-specific deletion, authority, and lifecycle
  lock modules: **0 errors**.
- Frontend TypeScript: **passed**. Targeted ESLint: **passed**. Targeted
  Prettier check: **passed**. Targeted Ruff: **passed**. Python compilation of
  affected backend modules: **passed**. `git diff --check`: **passed**.
- The broader strict Pyright surface still reports legacy/partially typed code
  diagnostics (275 in `historical_data_load_repository.py` and 50 in the
  separately checked API app/experiments/schemas set), matching the non-blocking
  repository typing concern recorded by T004. This does not invalidate the
  focused remediation-module typecheck or behavioral evidence, but a clean
  repository-wide strict Pyright result is not claimed.
- Existing warnings only: Starlette/httpx TestClient deprecation and the
  pre-existing unregistered `price_analysis` mark warning.

## Decision, residual findings, and invalidated scope

- **R-001: PASS — remediation freshly verified.**
- **R-002: PASS — remediation freshly verified.**
- **R-003: PASS — remediation freshly verified.**
- **R-004: PASS — required targeted proof freshly verified.**
- **R-005: PASS — artifact consistency freshly verified without technical
  contract changes.**

The initial broad REVIEW R-001–R-005 failure is invalidated for the targeted
remediation scope. The historical `REVIEW.md` remains unchanged and still
records the initial FAIL pending targeted rereview. Full frontend coverage and
unrelated broad validation remain out of scope. This PASS does not authorize
pre-PAPER or PAPER work; targeted rereview and merge approval remain required.
