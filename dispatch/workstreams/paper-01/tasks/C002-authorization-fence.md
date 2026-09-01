# C002 — Account, Risk, handoff, and Order authorization fence

**State:** `DONE`
**Dependency:** C001 `DONE`
**Owner:** BUILD
**Authority:** `IMPLEMENTATION-CLOSURE.md` C002; preserve PLAN, ARCHITECTURE, and
the frozen T004 reconciliation without reinterpretation.

## Objective

Implement exactly the frozen C002 authorization boundary: bind both broker reads
to the Deployment's immutable selected TradingAccount, make persisted
PRE_SUBMISSION approval the sole ENTRY Order authority, and enforce one pending
methodology handoff to at most one TradeIntent and at most one PAPER ENTRY Order.

## Required behavior

- Validate provider OANDA, Practice environment, explicit external account ID,
  USD currency, and EUR/USD instrument facts independently on PRE_FLIGHT and
  fresh PRE_SUBMISSION reads before Risk consumes them.
- Inside the Order-creation transaction, load and validate the persisted
  PRE_SUBMISSION APPROVED RiskDecision and every ownership, quantity, stop,
  price-bound, executable-evidence, null PAPER target, and non-superseded fact
  frozen in C002. In-memory approval is never authority and any mismatch blocks.
- Add the database uniqueness and transactional resolution needed for one
  handoff → at most one TradeIntent → at most one ENTRY Order. Existing
  PENDING_SUBMISSION, UNKNOWN, FULL_FILLED, or otherwise authoritative Orders are
  resolved/reconciled, never duplicated or blindly retried.
- Keep StrategyStateEnvelope.pending_entry as sole methodology authority; any
  runtime handoff remains lifecycle linkage only.

## Required tests

Implement and run every test listed under frozen C002, including first/second
wrong account, missing identity, persisted rejection/in-memory approval,
quantity/stop/price-bound/ownership mismatch, concurrent ENTRY creation,
PENDING_SUBMISSION crash re-entry, and UNKNOWN no-blind-retry. Concurrency and DB
uniqueness checks must use only the isolated configured `_test` database.

## Hard boundaries

Do not touch C003-C005, F-07/F-09, PAPER 02, credentials, Risk policy, activation,
or any mutating/capital-capable OANDA request. Stop and report any contradiction
with PLAN, ARCHITECTURE, or T004 rather than redesigning.

## Completion receipt

BUILD must record changed files, focused checks, PostgreSQL evidence or explicit
environment blocker, no-mutation/no-activation evidence, and concerns here before
marking the task `DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`.

## BUILD receipt

**Final state:** `DONE`

### Changed files

- `backend/domain/broker.py` and `backend/runtime/coordinator.py` — retain an
  immutable OANDA/Practice/USD selected TradingAccount identity on each runtime
  Deployment.
- `backend/runtime/production.py` and `backend/runtime/__init__.py` — validate
  both broker reads independently before Risk, pass the exact persisted
  PRE_SUBMISSION decision identity into Order creation, and stop when any ENTRY
  Order already exists instead of resubmitting it.
- `backend/runtime/store.py` — validate the persisted Deployment/account,
  TradeIntent/handoff/current Strategy methodology, exact approved Risk facts,
  non-supersession, and existing Order inside transactional fences; serialize
  concurrent creation and resolve existing PENDING_SUBMISSION/UNKNOWN/terminal
  Orders without duplication.
- `backend/persistence/models.py` and
  `backend/persistence/migrations/versions/0024_authorization_fence.py` — add one
  PAPER ENTRY Order per TradeIntent uniqueness, immutable per-time RiskDecision
  identity for fresh post-reconciliation authorization, a database
  PRE_SUBMISSION Order guard, and the table-dispatched ownership-trigger repair
  required for PostgreSQL RiskDecision persistence.
- `backend/tests/runtime/test_paper_account_authorization.py`,
  `backend/tests/runtime/test_production_runtime.py`, and
  `backend/tests/integration/test_authorization_fence.py` — cover both wrong-read
  positions, missing identity, persisted rejection and all frozen mismatches,
  ownership, supersession, Strategy-state authority, crash re-entry, UNKNOWN,
  concurrency, and direct database uniqueness.
- `backend/tests/integration/test_migrations.py` and
  `backend/tests/test_migration_revision.py` — advance and assert the C002
  migration head and authorization constraints.

### Checks and evidence

- Focused C002, production-runtime, PAPER Risk/persistence, migration-head, and
  PostgreSQL checks: **36 passed**.
- Dedicated PostgreSQL C002 suite against configured `atlas_test`: **13 passed**,
  including concurrent creation and direct uniqueness rejection.
- Exact C002 Alembic cycle `0024 -> 0023 -> 0024`: **passed**; database restored
  to `0024_authorization_fence`. Live inspection confirmed the unique ENTRY
  index, RiskDecision identity constraint, and authorization trigger.
- Full non-capital/non-integration backend suite: **476 passed, 4 skipped, 108
  deselected**; four pre-existing warnings remain.
- Ruff on all C002 implementation/test modules: **passed**. Pyright on changed
  implementation modules: **0 errors, 0 warnings**. `git diff --check`: **passed**.

### Safety receipt and concerns

- Tests used normalized recorded facts, injected fakes, and isolated PostgreSQL
  only. No OANDA request, credential change, PAPER activation, Risk-policy
  change, Order submission, or POST/PUT/PATCH/DELETE/cancel/close/transfer/
  capital-capable action was invoked.
- The broad pre-existing migration-cycle test still stops at its known unrelated
  table-list ordering assertion (`sorted(...)` compared with a list beginning
  with `alembic_version`). C002's own migration cycle, schema objects, trigger,
  transaction, concurrency, and uniqueness evidence all executed successfully;
  the unrelated assertion was not changed.
- C003-C005, F-07/F-09, PAPER 02, activation, credentials, and Risk policy remain
  untouched. No `READY_TO_ACTIVATE` claim is made.
