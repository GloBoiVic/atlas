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
- Error handling remains partial because the health monitor is deferred.
- Task 2 reviewer fixes complete: UTC event validation, callback typing, stats contract cleanup,
  expanded EventBus coverage, and the lifecycle event re-review fix.
- Task 1 ORM models and migration are complete and verified.
- Task 1 review fixes are complete: strategy reference tables now resolve ORM metadata and
  migration constraints, and bot P&L nullability/default matches the canonical schema.
- Task 1 follow-up fix is complete: Strategy timestamp nullability now matches the canonical
  schema and migration.
- Supervisor Task 2 repository slice is complete: model-free protocols, SQLAlchemy and
  in-memory bot, lease, lifecycle, and reconciliation repositories are implemented and tested.

## What comes next

Do not claim Feature 02 complete. Health monitor, BotSupervisor runtime integration, and the
remaining Feature 02 acceptance criteria are still deferred to later slices.

## Notes

Branch from `main` because no `develop` branch exists. Run the full test suite immediately
after moving `AccountMode`, then again after all Feature 02 slices. Docker/Compose verification
must run inside the Codespace because Docker is unavailable on the Mac host.
