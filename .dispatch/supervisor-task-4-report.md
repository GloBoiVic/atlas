# Supervisor Task 4 Report

## Status

Complete.

## Implementation

- Added `BotSupervisor` with one generated UUID worker ID and one `asyncio.Lock` per bot.
- Claim leases before pipeline construction, persist lifecycle transitions, and publish
  `BotStatusChanged` after each persisted transition.
- Start and restore with execution disabled, record reconciliation, and enable execution only
  after `MATCHED`; mismatches, failures, and pipeline errors persist `ERROR` fail-closed.
- Preserve paused pipelines for explicit resume while excluding `PAUSED` and `ERROR` bots from
  automatic restore.
- Added injected-clock heartbeat renewal at 10 seconds, ownership-loss fail-closed handling,
  graceful stop/shutdown, lease release, and structured transition logging.
- Added in-memory/fake coverage for concurrency, isolation, claim ordering, restore filtering,
  execution gating, reconciliation and pipeline failures, heartbeat ownership, lifecycle events,
  pause/resume, and shutdown.

## Verification

- Focused tests: `python3 -m pytest tests/test_supervisor.py` -> 10 passed.
- Full tests: `python3 -m pytest` -> 110 passed.
- Ruff: `python3 -m ruff check .` -> passed.
- Mypy: `python3 -m mypy backend` -> passed.
- Diff check: `git diff --check` -> passed.

## Critical Finding Follow-up

- Lease renewal exceptions now use the same fail-closed path as a lost lease: execution is
  disabled immediately, the bot persists `ERROR` with the exception message, the pipeline stops,
  and the lease is released safely.
- Exception logs retain structured `worker_id`, `bot_id`, `error`, and `error_type` context while
  the per-bot heartbeat failure remains isolated from other bots.
- Expanded `test_heartbeat_renewal_failure_isolated_to_one_bot` to verify the failed bot is stopped,
  execution-disabled, persisted as `ERROR`, and released while another bot remains `RUNNING` and
  executable.

## Critical Finding Verification

- Focused tests: `python3 -m pytest tests/test_supervisor.py -q` -> 17 passed.
- Full tests: `python3 -m pytest -q` -> 117 passed.
- Ruff: `python3 -m ruff check .` -> passed.
- Mypy: `python3 -m mypy backend` -> passed.
- Diff check: `git diff --check` -> passed.

## Concerns

- Live PostgreSQL lease concurrency remains a Codespace/Compose verification concern inherited
  from Task 2; the supervisor tests use the repository's deterministic in-memory implementation.
- Worker entrypoint wiring remains Task 5 scope.

## Review Fixes

The follow-up review identified lifecycle races and cleanup gaps in the original implementation.
The current branch fixes them as follows:

- Lease ownership is tracked separately from installed pipelines. A background heartbeat renews
  every claimed lease, including during factory construction, pipeline startup, reconciliation,
  and final lifecycle persistence. Startup performs explicit ownership checks after each awaited
  phase and fails closed before enabling execution or completing RUNNING persistence when ownership
  is lost.
- Shutdown sets its gate before waiting for in-flight operations, so new starts are rejected and
  a start already in progress cannot complete into an executable RUNNING pipeline. Shutdown keeps
  heartbeat renewal alive while those operations drain, then serializes per-bot cleanup and makes
  a final release pass over every still-claimed lease.
- Start cancellation and failure disable execution, stop any created pipeline, persist ERROR when
  possible, and release the claimed lease in shielded cleanup while preserving cancellation.
  Stop cleanup likewise disables and stops the pipeline before release even when persistence fails.
- Heartbeat renewal is isolated per bot with independent exception handling. Ownership loss marks
  only that bot failed closed and persists ERROR without terminating the global heartbeat loop.
- Pause now returns immediately for an already-paused bot regardless of whether its pipeline is
  present, preventing duplicate lifecycle transitions and events.
- Added regression tests for long startup renewal, startup ownership loss, shutdown/start races,
  cancellation cleanup, persistence failure cleanup, per-bot heartbeat isolation, and idempotent
  pause without an in-memory pipeline.

## Review Verification

- Focused tests: `python3 -m pytest tests/test_supervisor.py -q` -> 17 passed.
- Full tests: `python3 -m pytest -q` -> 117 passed.
- Ruff: `python3 -m ruff check .` -> passed.
- Mypy: `python3 -m mypy backend` -> passed.
- Diff check: `git diff --check` -> passed.

## Remaining Race Fix

- `_handle_lease_failure()` now holds the affected bot's task-aware per-bot lock across
  execution disablement, `ERROR` persistence, pipeline stop/removal, and lease release.
- Start cleanup uses the same lock boundary, and the lock wrapper permits reentrant use by the
  owning task so failure handling cannot deadlock when called from an already locked operation.
- Stop preserves an existing or claimed lease-failure `ERROR` state instead of writing `STOPPED`.
- Added deterministic failure-versus-start and failure-versus-stop regression tests. Different bot
  locks remain independent.

## Remaining Race Verification

- Focused tests: `python3 -m pytest tests/test_supervisor.py -q` -> 19 passed.
- Full tests: `python3 -m pytest -q` -> 119 passed.
- Ruff: `python3 -m ruff check .` -> passed.
- Mypy: `python3 -m mypy backend` -> passed.
- Diff check: `git diff --check` -> passed.

## Remaining Race Concerns

- Live PostgreSQL lease concurrency remains a Codespace/Compose verification concern inherited
  from Task 2; the regression tests use the deterministic in-memory repository.
- Worker entrypoint wiring remains Task 5 scope.
