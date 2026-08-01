# Supervisor Task 2 Report

## Status

Complete.

## Implementation

- Added model-free repository protocols and immutable supervisor-facing records for bots,
  lifecycle updates, leases, and reconciliation results.
- Added `SqlAlchemySupervisorRepositories`, which accepts an async session factory and owns
  session and transaction boundaries for every operation.
- Added atomic row-locked lease claiming with the required 30-second expiry window, same-worker
  reclaim behavior, and ownership-checked renewal and release.
- Added `InMemorySupervisorRepositories` with equivalent lease semantics and an async lock so
  concurrent claims have one winner.
- Added idempotent lifecycle persistence and reconciliation recording.
- Added tests for restore filtering, lifecycle idempotency, ownership and expiry, renewal and
  release, concurrent claims, and reconciliation idempotency.

## Verification

- Full tests: `python3 -m pytest` -> 87 passed.
- Ruff: `python3 -m ruff check .` -> passed.
- Mypy: `python3 -m mypy backend` -> passed.
- Diff check: `git diff --check` -> passed.

## Concerns

- Live PostgreSQL concurrency was not available on the Mac host. The SQL implementation uses
  `SELECT ... FOR UPDATE` for existing runs; a future migration should add a unique constraint
  on `bot_runs.bot_id` if the schema is intended to guarantee one run row per bot at the database
  level when no run exists yet.
- SQL repository integration tests against PostgreSQL remain a Codespace/Compose concern because
  the host does not provide the PostgreSQL service.

## Review Fixes

- Added the `uq_bot_runs_bot_id` unique constraint to the ORM and migration; downgrade explicitly
  removes the constraint before dropping `bot_runs`.
- Replaced the missing-row `SELECT FOR UPDATE` lease path with a PostgreSQL atomic upsert. The
  conflict update is conditional on an unclaimed row, the same worker, or a lease at least 30
  seconds old, so concurrent first claims have one winner and stale leases remain reclaimable.
- Made reconciliation recording use database conflict handling before reading the winning row,
  which is idempotent under concurrent duplicate calls.
- Added PostgreSQL dialect statement tests for the lease upsert and reconciliation conflict path,
  plus ORM and migration constraint assertions. Live PostgreSQL concurrency and `alembic check`
  remain unavailable on the Mac host because PostgreSQL is not running; the existing migration
  rendering tests and full test suite pass.
