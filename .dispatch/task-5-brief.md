# Task 5 — Circuit Breaker and Retry

Implement `backend/health/circuit_breaker.py`. Add CircuitBreakerState CLOSED,
OPEN, HALF_OPEN; CircuitBreaker with failure_threshold, recovery_timeout, optional
EventBus/context, single HALF_OPEN probe guarded by an async lock, and fail-closed
behavior. Publish CircuitBreakerOpen/Closed only on actual transitions. Add
CircuitBreakerOpenError under `backend/core/errors.py` as an AtlasError.

Implement separate composable `retry_async()` with max_attempts, backoff_base,
backoff_max, retry_on tuple, and injectable sleep. Retry only configured exception
types and use capped exponential backoff. CircuitBreaker.call() counts only the
ultimate outcome and re-raises operation errors.

Write tests for all state transitions, concurrent probes, event publication, retry
success/exhaustion/non-transient errors, and capped timing. Commit and report to
`.dispatch/task-5-report.md`.
