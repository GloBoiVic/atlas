# Foundation Freeze 07 Correction Validation

Status: `PASS — targeted C1/C2 validation complete`

Role: `VALIDATE`
Workstream: `foundation-freeze-07-corrections`
Branch: `solo/foundation-freeze-07-corrections`
CWD/repository root: `/Users/vike/Desktop/atlas`
Artifact: `dispatch/workstreams/foundation-freeze-07-corrections/VALIDATION.md`

Only the authorized DELETE lock-order and exact 0021 downgrade corrections were
validated. No application, test, fixture, harness, migration, plan, architecture,
active, review, or other role artifact was edited by VALIDATE.

## Environment and targeted evidence

- PostgreSQL URL used exclusively for validation:
  `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test`.
- Migration tests reset only this validation database's `public` schema. Final
  state is `0021_experiment_deletion (head)`; `alembic check` reports no pending
  operations.
- Focused backend command covering deletion, lifecycle lock interactions, and
  migrations: **51 passed** (one existing Starlette/httpx deprecation warning).

### C1 — DELETE lock order and semantics: PASS

- `test_http_delete_locks_snapshot_before_experiment_once` proves exactly one
  non-lock Experiment read, then one `DatasetSnapshot FOR UPDATE`, then one
  `Experiment FOR UPDATE`; no contradictory second lock path was observed.
- The API uses one caller-owned `db.begin()` transaction, passes the already
  locked root to the service, and projects confirmation facts from that locked
  snapshot. Direct repository/service deletion retains the same canonical lock
  boundary.
- Focused deletion tests passed for exact confirmation facts and case-sensitive
  `DELETE`, locked `RUNNING` precedence, stale deletable-status mismatch,
  `NOT_FOUND` repeat behavior, PENDING/FAILED/COMPLETED and partial graph
  deletion, child-first semantics, snapshot orphan/shared/active-load retention,
  receipt durability, rollback, ownership conflicts, and surviving reads.
- Lifecycle lock tests passed for the bounded snapshot-first/no-deadlock and
  activation/deletion race proofs. No architecture, Strategy, accounting,
  native-data, pre-PAPER, PAPER, or LIVE semantics were changed or exercised.

### C2 — exact 0021 downgrade restoration: PASS

- `test_migration_cycle` and
  `test_downgrade_to_0020_restores_guarded_trigger_dependencies` passed the
  head → `0020_fix_snapshot_guard` → head cycle.
- At 0020, the restored `snapshot_v2_append_only_guard()` definition was
  compared exactly (normalized SQL) to the revision-0020 contract: INSERT is
  rejected with “insert validation must use the statement trigger,” and all
  other operations are rejected as immutable.
- All three membership tables were compared for the exact trigger contract:
  row `BEFORE UPDATE OR DELETE` append-only guard plus statement `AFTER INSERT
  ... REFERENCING NEW TABLE ... FOR EACH STATEMENT` `snapshot_v2_insert_guard`.
  Guarded INSERT, UPDATE, and DELETE DML behavior passed, including rejection
  of legacy-snapshot membership inserts and preservation of V2 membership
  validation.

## Static checks and residual findings

- Targeted Ruff: **PASS**.
- Targeted Python `compileall`: **PASS**.
- Targeted strict Pyright for changed persistence/migration implementation:
  **0 errors, 0 warnings, 0 informations**.
- `git diff --check`: **PASS**.
- The broader strict Pyright invocation over the affected API/test surface
  reports **55 legacy/partially typed diagnostics** (mostly existing API
  `Any`/unknown typing and untyped test helpers). This is a pre-existing
  repository typing baseline; no correction-specific persistence/migration
  implementation diagnostic remains. It is recorded as non-blocking and was not
  repaired because VALIDATE is diagnose-only.
- Current tracked diff is limited to the two correction implementations, their
  focused tests, `dispatch/ACTIVE.md` bookkeeping, and this workstream's
  artifacts. The frozen architecture is unchanged; no Strategy or
  pre-PAPER/PAPER/LIVE work appears in the correction diff. Pre-existing
  `.codegraph/` and `frontend/.env.local` remain unowned/unmodified.

## Receipt

ROLE: `VALIDATE`
STATUS: `PASS`
FILES CHANGED: `dispatch/workstreams/foundation-freeze-07-corrections/VALIDATION.md` only
CHECKS/EVIDENCE: 51 focused PostgreSQL tests; exact lock-order and confirmation
proof; head→0020→head exact function/trigger and guarded-DML proof; Alembic
current/check; targeted Ruff, Pyright, compileall, and diff checks.
FINDINGS/CONCERNS: Non-blocking repository strict-Pyright baseline (55
diagnostics); no unresolved Critical/Important C1 or C2 finding. Merge approval
and targeted rereview remain external.
