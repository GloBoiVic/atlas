# C001 — Analytical M15 input and frontier safety

**State:** `DONE`
**Dependency:** T004 `DONE`
**Owner:** BUILD
**Authority:** `IMPLEMENTATION-CLOSURE.md` C001; preserve PLAN, ARCHITECTURE, and
the frozen T004 reconciliation without reinterpretation.

## Objective

Implement exactly the frozen C001 analytical boundary: validate live native
OANDA EUR/USD M15 MID completed bars before Strategy evaluation; keep historical
warm-up on a separate seed/restore path; and persist each successfully evaluated
Strategy state with its analytical frontier atomically and uniquely.

## Required behavior

- Enforce every C001 live provenance, completion, UTC, future-time, durable
  frontier, chronological-order, duplicate, and conflict rule before
  `process_completed_bar` or any Strategy state change.
- Treat identical replay as a no-op and conflicting/incomplete/wrong/future/
  out-of-order input as a blocked analytical cycle.
- Seed validated historical warm-up context without normal Strategy evaluation,
  TradeIntent emission, frontier weakening, or capital-state change.
- Commit the next StrategyStateEnvelope and matching analytical frontier in one
  database transaction. Enforce unique Deployment + analytical-frontier state
  identity in PostgreSQL.

## Required tests

Implement and run every test listed under frozen C001, including invalid input
before Strategy, equal/older frontier no reevaluation, next-bar exactly once,
idempotent/conflicting replay, atomic state/frontier persistence, and capital-
inert warm-up seeding. PostgreSQL-specific constraints/transactionality must use
only the isolated configured database whose name ends in `_test`.

## Hard boundaries

Do not touch C002-C005, F-07/F-09, PAPER 02, credentials, Risk policy, activation,
or any mutating/capital-capable OANDA request. Stop and report any contradiction
with PLAN, ARCHITECTURE, or T004 rather than redesigning.

## Completion receipt

BUILD must record changed files, focused checks, PostgreSQL evidence or explicit
environment blocker, no-mutation/no-activation evidence, and concerns here before
marking the task `DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`.

### BUILD receipt

**Final state:** `DONE`

### Changed files

- `backend/market_data/live.py`
- `backend/runtime/coordinator.py`
- `backend/runtime/production.py`
- `backend/runtime/store.py`
- `backend/persistence/models.py`
- `backend/persistence/paper_repository.py`
- `backend/persistence/migrations/versions/0023_analytical_frontier.py`
- `backend/tests/market_data/test_live_frontier.py`
- `backend/tests/runtime/test_analytical_frontier.py`
- `backend/tests/runtime/test_coordinator.py`
- `backend/tests/runtime/test_production_runtime.py`
- `backend/tests/persistence/test_paper_persistence.py`
- `backend/tests/integration/test_analytical_frontier_persistence.py`
- `backend/tests/integration/test_migrations.py`
- `backend/tests/test_migration_revision.py`

### Implementation receipt

- The live boundary now validates canonical OANDA EUR/USD native M15 MID
  provenance, completed/elapsed UTC intervals, observation time, chronological
  advancement, durable-frontier equality/age, and immutable bar fingerprints
  before Strategy evaluation. Identical replay is inert; conflicting equality,
  gaps, future input, and out-of-order input block before Strategy mutation.
- OANDA polling uses an elapsed quarter-hour request boundary and surfaces any
  provider-incomplete analytical candle as a blocked cycle. Historical context
  is split into a dedicated validated warm-up seed path that neither evaluates
  Strategy nor invokes state/evaluation/capital callbacks.
- Successful evaluation persists the next StrategyStateEnvelope, analytical bar
  fingerprint, and Deployment frontier in one SQLAlchemy transaction before
  in-memory Strategy state advances. PostgreSQL adds unique Deployment +
  analytical-frontier state identity, fingerprint constraints, and a frontier
  trigger requiring the matching persisted Strategy state.

### Checks and evidence

- Focused C001/runtime/persistence/migration tests: **43 passed**.
- Full non-capital backend suite: **473 passed, 4 skipped, 95 deselected**; four
  pre-existing warnings remain.
- The initial PostgreSQL C001 integration attempt collected **2 skipped** before
  the isolated test URL was exported. The lead-requested remediation below
  replaces that environment-limited evidence with executed PostgreSQL proof.
- Ruff on all changed implementation/test modules: **passed**.
- Pyright on changed implementation modules: **0 errors, 0 warnings**.
- `python -m compileall -q backend` and `git diff --check`: **passed**.

### Safety receipt and concerns

- No credential was changed or used outside isolated PostgreSQL validation. No
  PAPER activation, Risk-policy change, OANDA request, order submission, or
  POST/PUT/PATCH/DELETE/cancel/close/transfer/capital-capable action was invoked.
- PostgreSQL transaction, trigger, uniqueness, and exact migration-cycle proof
  now passes against the configured isolated `atlas_test` database.
- C002-C005, F-07/F-09, PAPER 02, activation, credentials, and Risk policy were
  not implemented or reinterpreted.

### Lead-requested concern remediation

The isolated PostgreSQL database is available at the repository's configured
`ATLAS_TEST_DATABASE_URL` and its name is `atlas_test`. Re-run the C001
PostgreSQL integration/migration checks with that variable exported, remediate
only C001 failures if any, and update this receipt. Do not begin C002.

#### Remediation result

- Verified the configured URL resolves to the exact database name `atlas_test`
  before any database command. No production database was addressed.
- C001 PostgreSQL atomicity/constraint tests plus migration-head revision tests:
  **4 passed**. This executed atomic state/frontier commit and rollback, unique
  Deployment + analytical-frontier enforcement, and the trigger rejecting
  frontier-only advancement.
- Exact C001 Alembic cycle `0023 → 0022 → 0023`: **passed** against
  `atlas_test`; the final database revision is restored to head.
- A broader shared migration-suite attempt produced **5 passed, 2 failed** for
  pre-existing, non-C001 test-isolation assertions: an unsorted expected table
  list and an unscoped trigger query observing other schemas in the same test
  database. No C001 assertion failed, and those unrelated tests were not changed
  under the instruction to remediate only C001 failures.
- No C001 implementation change was required during concern remediation. The
  first broad migration failure traceback displayed SQLAlchemy's configured
  local test URL; it was not copied into this artifact or changed. No OANDA
  request or capital-capable action was invoked, and C002 was not started.
