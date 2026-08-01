# Current Feature

Last updated: 2026-08-01

## Status

- [ ] Not started
- [x] In progress
- [ ] Complete

## Feature

- **Number:** 02
- **Name:** Core Infrastructure
- **File:** context/features/02-core-infrastructure.md

## Branch

- **Name:** feature/02-bot-supervisor
- **Created:** 2026-08-01

## What was built

- Task 6 structured logging implementation is complete and verified.
- Task 6 reviewer fix is complete: CircuitBreaker logs now filter arbitrary context keys.
- Five requested Feature 02 slices are complete and verified: EventBus, Clock abstraction,
  configuration, retry/circuit breaker error handling, and structured logging.
- BotSupervisor slice is complete on `feature/02-bot-supervisor`.
- Supervisor Task 3 runtime protocols and contract tests are complete.
- Error handling remains partial because the health monitor is deferred.
- Task 2 reviewer fixes complete: UTC event validation, callback typing, stats contract cleanup,
  expanded EventBus coverage, and the lifecycle event re-review fix.
- Supervisor Task 3 runtime protocol slice, BotSupervisor implementation, and worker-boundary
  integration are complete.
- Supervisor Task 4 BotSupervisor implementation and runtime tests are complete.
- Supervisor Task 4 review fixes are complete: lease renewal, shutdown gating, cancellation-safe
  cleanup, heartbeat isolation, pause idempotency, and race/failure regression coverage.
- Supervisor Task 4 critical follow-up is complete: renewal exceptions now fail closed, persist
  exception context as ERROR, stop the affected pipeline, and release its lease without affecting
  other bots.
- Supervisor Task 4 remaining race fix is complete: lease-failure cleanup now holds a task-aware
  per-bot lock through ERROR persistence, pipeline cleanup, and lease release; deterministic
  failure-versus-start and failure-versus-stop tests pass.
- Supervisor Task 4 final review fixes are complete: explicit stop/shutdown now converge ordinary
  ERROR bots to STOPPED, false lease releases clear local ownership, and cancellation cleanup is
  covered by regression tests.
- Supervisor Task 4 remaining heartbeat race is complete: lease generations and ownership/status
  checks now ignore stale delayed failures, with deterministic stop/reclaim coverage verified.
- Supervisor Task 4 cross-worker ownership race is complete: heartbeat ERROR persistence is now
  atomic and owner-conditional in both repositories, and stale cleanup cannot release a reclaimed
  worker's lease.
- Supervisor Task 4 final critical lifecycle fix is complete: pause/stop persistence is now
  owner-conditional, and heartbeat cleanup handles externally persisted PAUSED/STOPPED state.
- Supervisor Task 5 worker integration is complete: `run_worker()` accepts an injected
  `BotSupervisor`, restores active bots, and owns supervisor shutdown without constructing
  unavailable runtime dependencies.
- Task 1 ORM models and migration are complete and verified.
- Task 1 review fixes are complete: strategy reference tables now resolve ORM metadata and
  migration constraints, and bot P&L nullability/default matches the canonical schema.
- Task 1 follow-up fix is complete: Strategy timestamp nullability now matches the canonical
  schema and migration.
- Supervisor Task 2 repository slice is complete: model-free protocols, SQLAlchemy and
  in-memory bot, lease, lifecycle, and reconciliation repositories are implemented and tested.
- Supervisor Task 2 review fixes are complete: database-enforced one-run-per-bot, atomic first
  lease claims, concurrent-safe reconciliation idempotency, and SQL dialect coverage.
- Supervisor Task 2 follow-up review fixes are complete: the unique constraint has a safe `003`
  migration path, SQL repositories have executable async SQLite coverage, and verification counts
  and environment-gap documentation are current.
- Final Task 4 verification: focused supervisor/repository tests pass (39), full pytest passes
  (127), Ruff, mypy, and `git diff --check` pass.
- Final important supervisor findings are fixed: cancellation-safe stop finalization waits for
  pipeline cleanup before STOPPED/release, failed stops persist ERROR and retain ownership, and
  shutdown reports unresolved cleanup failures. Focused supervisor tests pass (29) and full pytest
  passes (138).
- Remaining cancellation findings are fixed: the entire stop transaction is shielded through
  lifecycle events and lease release, lease-loss cleanup uses the same boundary, and unresolved
  shutdown diagnostics include affected bot IDs.
- Final follow-up verification: focused supervisor tests pass (33), full pytest passes (142),
  Ruff, mypy, offline migration SQL generation, and `git diff --check` pass.
- Remaining start-abort cleanup finding is complete: failed pipeline stops during start failure or
  cancellation now persist owner-conditional ERROR/unresolved state, retain the live disabled
  pipeline and lease, and block duplicate starts until cleanup succeeds.
- Final start-abort verification: focused supervisor tests pass (35), full pytest passes (144),
  Ruff, mypy, offline migration SQL generation, and `git diff --check` pass.
- Final whole-branch review fixes are complete and verified: full pytest passes (150), focused
  supervisor/repository tests pass (57), Ruff, mypy, offline migrations, and diff check pass.

## What comes next

Do not claim Feature 02 complete. Health monitor and any remaining Feature 02 criteria remain
deferred; BotSupervisor implementation, worker-boundary integration, and its acceptance criterion
are complete.

## Notes

Branch from `main` because no `develop` branch exists. Run the full test suite immediately
after moving `AccountMode`, then again after all Feature 02 slices. Docker/Compose verification
must run inside the Codespace because Docker is unavailable on the Mac host.
Live Alembic checks and PostgreSQL lease concurrency remain Codespace checks; offline migration
upgrade/downgrade SQL generation passes locally.
