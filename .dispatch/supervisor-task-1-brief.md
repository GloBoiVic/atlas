# Supervisor Task 1 — ORM Models and Migration

Read `context/database.md` lines 250-319 before writing persistence code. The schema is
the source of truth. Translate the documented `bots`, `bot_runs`, and
`reconciliation_runs` tables mechanically into SQLAlchemy 2.0 typed ORM models.

The supervisor requirements correct the older schema documentation: `bots` must include
`desired_status`; `bot_runs` must include `worker_id` and `locked_at` in addition to
runtime status, heartbeat, and error data. Update `context/database.md` to match the
intended schema without redesigning unrelated tables.

Add a new Alembic migration after `001` with upgrade and downgrade paths. Do not rewrite
the existing migration. Preserve UUID/string conventions used by this repository and
timezone-aware timestamps. Add model tests and migration structure tests where practical.

Run pytest, Ruff, mypy, and diff checks. Commit the task and write the full report to
`.dispatch/supervisor-task-1-report.md`. Return only status, commits, tests, and concerns.
