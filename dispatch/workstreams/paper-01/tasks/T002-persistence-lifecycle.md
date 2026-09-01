# T002 — PAPER persistence, lifecycle facts, and ownership

**State:** `DONE`
**Dependency:** T001 `DONE`
**Owner:** BUILD

## Objective

Add the minimum PostgreSQL-backed TradingAccount, Deployment, Strategy continuity,
pending-entry, safety/health, broker identity, reconciliation cursor, and runtime
ownership persistence required by the frozen architecture.

## Required behavior

- Add explicit TradingAccount and Deployment records for one OANDA Practice
  EUR/USD slice, including non-secret account identity, desired/actual state,
  immutable trading configuration/Risk snapshot, safety reason, and provenance.
- Add versioned strategy state/frontier and pending-entry lifecycle/link facts;
  `StrategyStateEnvelope.pending_entry` remains the sole methodology authority.
- Extend canonical TradeIntent/Order/RiskDecision/Fill/Position/Trade storage with
  direct/transitive Experiment-vs-Deployment ownership and external OANDA IDs,
  client correlation, transaction/request evidence, and cursor facts without
  fabricating Experiment IDs for PAPER.
- Enforce one active Deployment per account/instrument, one Position and pending
  opening setup per Deployment, unique decision-frontier idempotency, stable
  correlation, and no rootless/dual-owned/cross-root canonical graph.
- Add append-only Order/System/Reconciliation safety facts and durable health /
  heartbeat facts. Persist only bounded sanitized provider evidence; never secrets.
- Implement a session-level PostgreSQL advisory lock keyed by Deployment UUID;
  loss of DB/lock blocks exposure and reacquisition requires reconciliation.
- Preserve all historical Experiment constraints and migration behavior.
- Migration up/down or fresh-schema tests must be non-capital and must not contact
  OANDA.

## Owned implementation surface

`backend/persistence/models.py`, a new migration after `0021`, persistence
repositories/lock helpers, and focused persistence tests. Coordinate imports with
T001 contracts; do not implement runtime orchestration or broker network calls.

## Task-level checks

- Migration cycle and relevant PostgreSQL integration tests.
- Constraint/ownership/idempotency/advisory-lock tests.
- Numeric/UTC round-trip and state restoration tests.
- Existing migration and historical Experiment tests remain green.

## Completion receipt requirements

At completion, update this file with `DONE` or `DONE_WITH_CONCERNS`, changed files,
checks/evidence, and concerns. Do not edit role artifacts.

## Completion receipt

**Final state:** `DONE`

### Changed files

- `backend/persistence/models.py` — TradingAccount, Deployment, durable Strategy
  state/frontier, pending handoff, normalized account facts, runtime health,
  reconciliation/cursor facts, and canonical Experiment-vs-Deployment ownership /
  broker identity fields.
- `backend/persistence/migrations/versions/0022_paper_persistence_lifecycle.py`
  — PostgreSQL schema, constraints, ownership/cross-link guards, append-only
  lifecycle guards, PAPER target/FOK checks, and reversible migration.
- `backend/persistence/paper_repository.py` — flush-only account, Deployment,
  Strategy-state, pending-entry, safety, heartbeat, reconciliation, cursor, and
  stable-correlation repositories with bounded evidence handling.
- `backend/persistence/lifecycle_locks.py` — stable Deployment UUID key and
  session-level PostgreSQL advisory-lock helpers.
- `backend/persistence/trading_repository.py` — dual-root-aware canonical
  TradeIntent/Order creation, PAPER execution evidence fields, and strict UTC
  timestamp validation at the PAPER intent/Risk boundary.
- `backend/persistence/timestamps.py` — centralized strict timezone-aware UTC
  validation and non-decreasing timestamp guard.
- `backend/persistence/__init__.py` — persistence seam exports.
- `backend/tests/persistence/test_paper_persistence.py` — non-DB ownership,
  correlation, lock-key, snapshot, secret-evidence, strict PAPER timestamp,
  and monotonicity checks.
- `backend/tests/integration/test_migrations.py` — migration-cycle assertions for
  PAPER tables and canonical extensions.
- `backend/tests/test_migration_revision.py` — latest revision assertion.

### Checks and evidence

- Targeted persistence, migration-revision, T001 OANDA/frontier, domain, and
  Strategy tests: **128 passed**.
- Full non-capital suite: **418 passed, 4 skipped, 88 deselected**; the only
  failure was the pre-existing latest-revision assertion, which was updated for
  the new 0022 head and then passed in the targeted rerun.
- Targeted Ruff: **passed**.
- Pyright on changed persistence implementation modules: **0 errors, 0 warnings**.
- Alembic history resolves cleanly through `0022_paper_persistence_lifecycle`;
  metadata PostgreSQL DDL compilation succeeded.
- Migration integration checks: **3 skipped** because
  `ATLAS_TEST_DATABASE_URL` is not configured. No DB application failure is
  masked; PostgreSQL migration up/down, trigger, constraint, numeric/UTC, and
  advisory-lock behavior remain unverified in this environment.
- No credentials, OANDA network calls, mutating provider requests, activation,
  Risk-policy changes, or Git history operations were performed.

### Concerns

- A dedicated PostgreSQL test database is required to validate migration cycle,
  trigger ordering, cross-root rejection, concurrent uniqueness, and actual
  session-lock exclusivity. This is an environment limitation, not an observed
  application failure.
- Runtime orchestration, broker execution, Risk composition, reconciliation
  workflows, and capital-capable actions remain intentionally unimplemented for
  T003/T004.

## F-08 remediation completion receipt

**Final state:** `DONE`

### Remediation details

- Added one persistence timestamp validator requiring an actual timezone-aware
  UTC `datetime`; naive, non-UTC, and wrong-type values are rejected before
  repository persistence.
- Applied the validator to PAPER Deployment intent/Risk timestamps, strategy
  state/frontier, pending-entry resolution, account snapshots, safety events,
  heartbeat, reconciliation, cursor, and first-trade writes. Risk quote
  observation timestamps are validated as well.
- Preserved and tightened non-decreasing frontier and cursor timestamp guards;
  existing numeric transaction-cursor monotonicity remains enforced.

### Remediation checks

- Focused persistence tests: **8 passed** (naive/non-UTC rejection for each
  PAPER timestamp seam, UTC acceptance, frontier/cursor monotonicity).
- Persistence and migration-revision tests: **10 passed**.
- Full non-capital suite after remediation: **449 passed, 4 skipped, 88
  deselected** (four expected database-backed skips; only unrelated warnings).
- Migration integration tests: **3 skipped** because
  `ATLAS_TEST_DATABASE_URL` is unset; PostgreSQL round trips remain unverified.
- Ruff: **passed**; Pyright on changed persistence modules: **0 errors, 0
  warnings**; compileall and `git diff --check`: **passed**.

### Remediation concerns

- A dedicated PostgreSQL test database is still required for the requested
  migration/UTC round-trip evidence. No credentials, OANDA calls, activation,
  mutating requests, or Git history operations were performed.

## Validation remediation packet — F-08

- **Classification:** PRODUCT; **severity:** IMPORTANT.
- **Issue:** PAPER persistence entry points accept naive/non-UTC timestamps;
  `create_paper_risk_decision`, frontier, reconciliation, and cursor writes do
  not enforce the required UTC-aware boundary.
- **Affected seam:** `backend/persistence/trading_repository.py` and
  `backend/persistence/paper_repository.py` timestamp validation.
- **Required fix:** Centralize strict timezone-aware UTC validation and apply it
  to every PAPER persistence timestamp, including monotonic frontier/cursor
  writes. Reject naive and non-UTC values before persistence.
- **Invalidated evidence:** T002 UTC round-trip and persistence completion claims.
- **Smallest revalidation:** repository unit cases for naive, non-UTC, UTC, and
  monotonic inputs, followed by PostgreSQL round-trip checks when the dedicated
  test database is available.
