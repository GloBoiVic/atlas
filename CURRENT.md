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
- BotSupervisor slice is now in progress on `feature/02-bot-supervisor`.
- Supervisor Task 3 runtime protocols and contract tests are complete.
- Error handling remains partial because the health monitor is deferred.
- Task 2 reviewer fixes complete: UTC event validation, callback typing, stats contract cleanup,
  expanded EventBus coverage, and the lifecycle event re-review fix.
- Supervisor Task 3 runtime protocol slice is complete; BotSupervisor implementation remains next.
- Supervisor Task 4 BotSupervisor implementation and runtime tests are complete.
- Supervisor Task 4 review fixes are complete: lease renewal, shutdown gating, cancellation-safe
  cleanup, heartbeat isolation, pause idempotency, and race/failure regression coverage.
- Supervisor Task 4 critical follow-up is complete: renewal exceptions now fail closed, persist
  exception context as ERROR, stop the affected pipeline, and release its lease without affecting
  other bots.
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

## What comes next

Do not claim Feature 02 complete. Health monitor, BotSupervisor runtime integration, and the
remaining Feature 02 acceptance criteria are still deferred to later slices.

## Notes

Branch from `main` because no `develop` branch exists. Run the full test suite immediately
after moving `AccountMode`, then again after all Feature 02 slices. Docker/Compose verification
must run inside the Codespace because Docker is unavailable on the Mac host.
