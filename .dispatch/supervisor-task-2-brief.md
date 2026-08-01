# Supervisor Task 2 — Repository Boundaries

Build repository protocols first, then SQLAlchemy implementations, then an in-memory
repository with equivalent behavior. Read `context/database.md`, the Task 1 models,
and `context/coding-standards.md`.

Repositories must own sessions and transactions. Expose atomic operations for loading
restore candidates, claiming a lease, renewing/releasing a lease, persisting lifecycle
status, and recording reconciliation results. Lease claim must accept an unclaimed row
or a row whose `locked_at` is older than the configured 30-second timeout, and must
prevent another worker from claiming a current lease. The in-memory implementation must
match these semantics for deterministic tests.

Use repository protocols so BotSupervisor never imports SQLAlchemy sessions/models.
Add tests for state persistence, idempotency, lease ownership/expiry, renewal/release,
and reconciliation records. Run pytest, Ruff, mypy, and diff checks. Commit and report
to `.dispatch/supervisor-task-2-report.md`.
