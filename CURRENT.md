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

- **Name:** chore/next16-upgrade
- **Created:** 2026-08-01

## What was built

### Lease / Worker-Ownership Removal (feature/02-lease-removal, commit 8b735ec)

The cross-worker lease protocol was removed from the entire stack. Atlas MVP now
explicitly supports one worker process. Specific changes:

- **ORM models:** `BotRun` model removed; `bot_runs` table dropped in migration `004`.
- **Repository protocols:** `LeaseRecord` dataclass and `LeaseRepository` protocol removed.
  `SupervisorRepositories` simplified to `BotRepository & ReconciliationRepository`.
- **SQLAlchemy repositories:** All lease/claim/renew/release methods removed. `persist_lifecycle`
  and `persist_error` are now unconditional writes (no owner-conditional gating).
- **In-memory repositories:** Same simplification — no lease tracking, unconditional writes.
- **BotSupervisor:** Heartbeat loop, `worker_id`, lease generations, ownership tracking
  (`_claimed`, `_ownership_lost`, `_lease_generations`), `_assert_owned()`, `_release_claim()`,
  `_ensure_heartbeat_task()`, and all lease-failure handling removed. Retained: in-process
  per-bot `asyncio.Lock` (via explicit `acquire()`/`release()`, no async generator), pipeline
  tracking, lifecycle persistence, startup restoration, reconciliation before execution,
  cancellation-safe cleanup.
- **Worker errors:** `LeaseOwnershipLost` removed; `BotPipelineError` retained.
- **Worker lifecycle:** `persist_error()` simplified (no `worker_id` param, no `if_owned` call).
- **Migrations:** `004_drop_bot_runs.py` created. Alembic history preserved; no migrations
  rewritten or deleted.
- **Alembic env.py:** `BotRun` import removed.
- **Tests:** All lease-specific tests removed; lease-adjacent tests simplified. 47/47 targeted
  tests passing, Ruff and mypy clean.

### Previous Feature 02 slices (committed)

- EventBus, Clock abstraction, configuration system, circuit breaker/retry error handling,
  structured logging, BotSupervisor implementation, worker-boundary integration.

## What comes next

- Health monitor and orphan-state handling remain deferred (pre-existing).
- Docker/Compose verification must run inside the Codespace when the branch is committed
  and pushed. **Do not run unbounded test suites or full Docker Compose builds from this
  session — previous unbounded runs hung indefinitely. Bounded targeted tests (32/32 pass)
  suffice for this review cycle.**

## Notes

- The single-worker deployment invariant is the explicit replacement for cross-worker mutual
  exclusion. This is safe only while Docker Compose runs one worker and Atlas does not support
  horizontal scaling or overlapping deployments.
- A crashed worker may leave a bot persisted as RUNNING/STARTING until Docker restart recovery
  or a future health monitor reconciles it. This consequence is accepted.
- BotSupervisor's `_bot_lock` was changed from an `@asynccontextmanager` async generator to
  explicit `acquire()`/`release()` to eliminate a cancellation deadlock.
- No run-history records were added. The `bot_runs` table was exclusively lease machinery; no
  product behavior consumed runtime-history records.

## Closeout — Lease-Removal Review Cycle

- **Docs (Task 7):** Complete — 6 canonical files updated.
- **Review (Task 8):** Complete — Tier 2 follow-up PASS; all 3 findings (fixture isolation,
  migration downgrade UC, stale docstring) fixed in Task 9. Bounded verification: 32/32
  migration + supervisor tests pass, Ruff clean.
- **Full-suite verification:** Intentionally not run. Previous unbounded suites hung
  indefinitely in this workspace. Bounded targeted tests are the agreed check for this cycle.
  Docker/Compose validation is deferred until the branch is committed and pushed.
- **State:** All 9 lease-removal tasks done. Changes committed as `8b735ec` on
  `chore/next16-upgrade`.
