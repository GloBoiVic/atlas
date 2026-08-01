# Task 5 Report — Circuit Breaker and Retry

## Status

Complete.

## Implementation

- Added `CircuitBreakerState` with `CLOSED`, `OPEN`, and `HALF_OPEN` states.
- Added fail-closed `CircuitBreaker` with configurable failure threshold and recovery timeout.
- Serialized state changes with an async lock and allowed exactly one concurrent half-open probe.
- Added optional EventBus publication with account, bot, mode, correlation, and event metadata context.
- Published `CircuitBreakerOpen` and `CircuitBreakerClosed` only for actual transitions.
- Added `CircuitBreakerOpenError` under `backend.core.errors` as an `AtlasError`.
- Added composable `retry_async` with explicit attempts, capped exponential backoff, configured exception types, and injectable async sleep.
- Circuit breaker records only the protected operation's ultimate outcome and re-raises its original exceptions.

## Tests

- Added transition, recovery, concurrent probe, event metadata, event deduplication, retry success, retry exhaustion, non-transient failure, and capped backoff coverage.
- Full suite: `66 passed`.
- Ruff: passed with `python -m ruff check .`.
- Mypy: passed with `python -m mypy backend/`.
- Diff validation: passed with `git diff --check`.

## Concerns

- Docker/Compose checks were not run because Docker is unavailable on the Mac host, consistent with the repository Codespaces guidance.
- Full project dependencies were installed only in a temporary virtual environment at `/tmp/atlas-task5-venv`; no environment files were added to the repository.

## Reviewer Fixes

### Findings Addressed

- CLOSED operations no longer mutate breaker state after a later state transition. Each admitted
  call captures a monotonically increasing generation under the state lock. Any transition
  advances the generation, and completion handlers ignore outcomes from an older generation.
  This keeps concurrent CLOSED external calls concurrent while preventing stale successes or
  failures from closing or reopening a later HALF_OPEN probe.
- HALF_OPEN ownership remains serialized by the existing state lock. The first eligible caller
  transitions to HALF_OPEN and owns the current generation; all other calls are rejected with
  `CircuitBreakerOpenError` until that probe completes.
- Transition event construction now always assigns `occurred_at` from the injected Clock,
  including `SimulationClock`. Existing event context filtering continues to preserve
  correlation, account, bot, and mode metadata.

### Regression Coverage

- Added stale CLOSED success coverage while a HALF_OPEN probe is in flight. The stale result
  cannot emit a premature CLOSED transition, and a second probe is rejected without an extra
  operation call.
- Added stale CLOSED failure coverage with the same ownership and no-premature-OPEN assertions.
- Added explicit HALF_OPEN-to-OPEN coverage for a failed recovery probe.
- Asserted OPEN and CLOSED transition timestamps equal the SimulationClock time.

### Verification

- Focused tests: `/tmp/atlas-task5-venv/bin/python -m pytest tests/test_circuit_breaker.py` — 10 passed.
- Full tests: `/tmp/atlas-task5-venv/bin/python -m pytest` — 69 passed.
- Ruff: `/tmp/atlas-task5-venv/bin/python -m ruff check .` — passed.
- Mypy: `/tmp/atlas-task5-venv/bin/python -m mypy backend/` — passed.
- Diff validation: `git diff --check` — passed.

## Fix Status

Complete. The reviewer findings are fixed and covered by regression tests. Docker/Compose
verification remains deferred to a Codespace because Docker is unavailable on this Mac host.
