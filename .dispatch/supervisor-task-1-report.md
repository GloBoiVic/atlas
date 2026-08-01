# Supervisor Task 1 Report

## Status

Complete.

## Implementation

- Added typed SQLAlchemy 2.0 models for `bots`, `bot_runs`, and `reconciliation_runs`.
- Added `desired_status` to `bots` and `worker_id` plus `locked_at` to `bot_runs`.
- Preserved string UUID primary/foreign-key conventions and timezone-aware timestamps.
- Added PostgreSQL `JSONB` snapshots and Decimal-compatible `NUMERIC(20, 8)` P&L storage.
- Added Alembic revision `002`, dependent on `001`, with upgrade and downgrade paths.
- Updated the canonical database documentation for the supervisor fields.
- Registered the new models with Alembic metadata discovery.
- Added focused model and migration structure tests.

## Verification

- Focused tests: `python3 -m pytest tests/test_models.py tests/test_migrations.py` -> 7 passed.
- Full tests: `python3 -m pytest` -> 75 passed.
- Ruff: `python3 -m ruff check .` -> passed.
- Mypy: `python3 -m mypy backend` -> passed.
- Diff check: `git diff --check` -> passed.

## Concerns

- The current `001` migration creates only `accounts`; the documented `strategies` and
  `strategy_versions` tables are not yet available to reference. The ORM models retain those
  documented foreign keys, while migration `002` creates the bot columns without those two
  constraints so the `001` -> `002` upgrade remains executable. A later migration should add
  the constraints after those reference tables exist.
- PostgreSQL execution of the Alembic migration was not available on the Mac host; structural
  migration coverage and all local Python checks passed.

## Commit

The task implementation and this report are included in the task commit.
