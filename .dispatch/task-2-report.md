# Task 2 Report: Typed EventBus

## Status

Complete.

## Implementation

- Replaced the string-keyed queue/drain API with immediate asynchronous publishing.
- Added immutable metadata-only domain event classes for all Feature 02 trading, error,
  and lifecycle events.
- Added generated `event_id` and `correlation_id`, UTC-aware `occurred_at`, optional
  account and bot IDs, and shared `AccountMode` metadata.
- Added exact event-class subscriptions with deterministic sequential handler delivery.
- Added `Subscription` unsubscribe handles.
- Added `EventFailure`, `FailureRecorder`, and `InMemoryFailureRecorder`.
- Added injected failure recording and bot pause callbacks with failure isolation.
- Switched EventBus logging to `structlog.get_logger()` and included structured context.
- Updated focused tests for metadata, exact matching, order, unsubscribe, failure
  continuation, recording, and bot pausing.

## Verification

- `python3 -m compileall -q backend/core/events.py tests/test_events.py`: passed.
- Direct async smoke test for failure recording, pause callback, and later-handler
  delivery: passed.
- `git diff --check`: passed.
- Focused pytest, Ruff, and mypy were unavailable on the Mac host because `pytest`,
  `ruff`, and `mypy` are not installed. Full test suite was therefore not runnable.

## Concerns

- The repository requires the Codespace/Compose development environment for the full
  dependency and test toolchain; verification should be rerun there.

## Reviewer Fix Report

### Files

- `backend/core/events.py`: require UTC-offset `occurred_at` values, type synchronous and
  asynchronous failure recorder and bot pause callbacks, and remove the stale `queue_size`
  stats field.
- `tests/test_events.py`: cover every required event class, sequential awaiting with a blocked
  handler, duplicate publishing, duplicate-registration unsubscribe, UTC rejection, and callback
  failure isolation.
- `.dispatch/task-2-report.md`: record this reviewer fix and verification.

### Re-review Fix

- `backend/core/events.py`: added the architecture-defined metadata-only `BotStatusChanged`
  and `HealthStatusChanged` event classes.
- `tests/test_events.py`: included both lifecycle event classes in the metadata-only event-class
  coverage.
- EventBus dispatch and existing behavior were not changed.

### Verification

- `python3 -m pytest tests/test_events.py`: passed, 34 tests.
- `python3 -m pytest`: passed, 45 tests.
- `python3 -m ruff check .`: passed.
- `python3 -m mypy backend/core/events.py tests/test_events.py`: passed.
- `python3 -m mypy backend tests`: blocked by three pre-existing `AccountMode` versus string
  comparison errors in `tests/test_models.py`.
- `git diff --check`: passed.

### Concerns

- Full strict mypy remains non-green because of unrelated existing model tests; no event-related
  mypy errors remain.
