# C003 — Restart, Strategy continuity, and durable runtime health

**State:** `DONE`
**Dependency:** C002 `DONE`
**Owner:** BUILD
**Authority:** `IMPLEMENTATION-CLOSURE.md` C003; preserve PLAN, ARCHITECTURE, and
the frozen T004 reconciliation without reinterpretation.

## Objective

Implement exactly the frozen C003 restart boundary: reconstruct the Strategy
processor from validated durable state and native M15 context before actual
RUNNING, preserve pending methodology state and frontier continuity, perform
capital-inert catch-up, and durably retain runtime health/safety facts.

## Required behavior

- Enforce the exact twelve-step processor restoration order frozen in C003.
- Validate Deployment, immutable StrategyVersion, and expected state schema links
  before deserialization/use; enforce the StrategyVersion relationship in the DB
  where the schema permits and retain mandatory runtime checks.
- Load the latest 100 validated completed native OANDA EUR/USD M15 MID bars in
  chronological order and seed processor context without evaluation, TradeIntent,
  or capital action. Insufficient/invalid context blocks readiness.
- Restore exact pending_entry methodology state and prove any handoff linkage
  resolves to it; mismatch blocks.
- Replay post-frontier catch-up chronologically as analysis-only, persisting
  caught-up state/frontier without stale capital action.
- Persist runtime state, owner heartbeat, reconciliation time, broker observation
  time, analytical frontier, and current block reason through the existing
  health/safety seam. Lock/heartbeat/DB/freshness/state/frontier failures block
  new exposure immediately.

## Required tests

Implement and run every test listed under frozen C003, including immediate
100-bar restart context, pending restoration/link agreement, no 100-new-bar wait,
warm-up no reevaluation, chronological capital-inert catch-up, invalid version/
schema/frontier blocking, and health/frontier survival across runtime instances.
PostgreSQL-backed persistence checks must use only the configured `_test` DB.

## Hard boundaries

Do not touch C004-C005, F-07/F-09, PAPER 02, credentials, Risk policy, activation,
or any mutating/capital-capable OANDA request. Stop and report any contradiction
with PLAN, ARCHITECTURE, or T004 rather than redesigning.

## Completion receipt

BUILD must record changed files, focused checks, PostgreSQL evidence or explicit
environment blocker, no-mutation/no-activation evidence, and concerns here before
marking the task `DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`.

## BUILD receipt

**Final state:** `DONE_WITH_CONCERNS`

### Changed files

- `backend/runtime/{coordinator,production,main,store}.py` — make restoration a
  required pre-RUNNING lifecycle step after reconciliation; rebuild the processor
  from durable inputs, seed exactly 100 validated native M15 MID context bars,
  replay post-frontier bars chronologically with entries disabled, retain durable
  broker/reconciliation/heartbeat/frontier health facts, and block on any restore
  failure.
- `backend/domain/strategy.py` and `backend/strategies/production.py` — retain
  pending-entry stop methodology with the envelope-owned methodology state and
  reject an ARMED restored state that cannot prove it.
- `backend/persistence/{models,paper_repository}.py` and
  `backend/persistence/migrations/versions/0025_restart_continuity.py` — enforce
  state-to-Deployment StrategyVersion linkage with a composite FK, validate state
  schema/version links and lifecycle handoff agreement at runtime, atomically
  expire a stale lifecycle handoff when analysis-only catch-up clears it, and
  expose durable runtime-health facts.
- `backend/tests/runtime/{test_analytical_frontier,test_coordinator,
  test_production_runtime}.py` — cover no-evaluation warm-up, exact pending
  restoration, immediate next-bar operation from 100 bars, startup ordering,
  restore failure blocking, and chronological capital-inert source catch-up.
- `backend/tests/integration/test_analytical_frontier_persistence.py` and
  `backend/tests/test_migration_revision.py` — add isolated PostgreSQL
  health/frontier survival evidence and advance the Alembic head assertion.

### Checks and evidence

- Focused C003 runtime/persistence/migration and state-document compatibility
  checks: **90 passed, 3 skipped** before the isolated database was available.
- Re-run against the explicit isolated `atlas_test` PostgreSQL URL:
  `backend/tests/integration/test_analytical_frontier_persistence.py`:
  **3 passed**. This proves atomic state/frontier persistence and rollback,
  PostgreSQL frontier uniqueness, and health/frontier survival through a new
  `SqlAlchemyRuntimeStore` instance.
- The fresh-schema migration cycle successfully upgraded through
  `0025_restart_continuity`; the database was restored to head afterward.
  `alembic check` passed (`No new upgrade operations detected`), and live
  PostgreSQL inspection verified
  `fk_strategy_states_deployment_strategy_version` is the expected composite
  `strategy_states(deployment_id, strategy_version_id)` →
  `deployments(id, strategy_version_id)` foreign key.
- The broad existing `test_migration_cycle` still fails its known unrelated
  table-list ordering assertion (it expects `alembic_version` before the
  alphabetically earlier `account_transaction_cursors`). It fails after the
  successful upgrade and before C003-specific schema assertions; no C003 code
  or migration failure was observed, and the assertion was not changed.
- Full non-capital backend suite: **480 passed, 4 skipped, 109 deselected**;
  four pre-existing warnings remain.
- Ruff and `git diff --check`: **passed**. Pyright on all changed implementation
  modules: **0 errors, 0 warnings**. `compileall` on changed implementation and
  migration modules: **passed**.

### Safety receipt and concerns

- All checks used unit fakes/recorded provider shapes and the isolated PostgreSQL
  test database only. No OANDA credentials were read or changed; no PAPER
  activation, Risk-policy change, Order submission, or OANDA
  POST/PUT/PATCH/DELETE/cancel/close/transfer/capital-capable request was invoked.
- C004-C005, F-07/F-09, PAPER 02, credentials, activation, and Risk policy remain
  untouched. No `READY_TO_ACTIVATE` claim is made.
- The isolated PostgreSQL C003 evidence is complete. The only remaining concern
  is the pre-existing, unrelated broad migration-cycle table-order assertion
  described above; it is outside the frozen C003 scope.

### Lead-requested concern remediation

Completed against explicit `ATLAS_TEST_DATABASE_URL` for `atlas_test`. No C003
failure required remediation; the isolated database is at migration head. Do not
begin C004.
