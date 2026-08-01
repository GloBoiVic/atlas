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
