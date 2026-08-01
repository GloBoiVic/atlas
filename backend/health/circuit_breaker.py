import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import structlog

from backend.core.clock import Clock, LiveClock
from backend.core.errors import CircuitBreakerOpenError
from backend.core.events import CircuitBreakerClosed, CircuitBreakerOpen, EventBus

type AsyncOperation[T] = Callable[..., Awaitable[T]]
AsyncSleep = Callable[[float], Awaitable[None]]
EventContext = Mapping[str, object]

logger = structlog.get_logger(__name__)


class CircuitBreakerState(StrEnum):
    """States in the circuit breaker's lifecycle."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Protect an asynchronous dependency with a fail-closed circuit."""

    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout: float,
        event_bus: EventBus | None = None,
        context: EventContext | None = None,
        *,
        metadata: EventContext | None = None,
        clock: Clock | Callable[[], datetime] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must not be negative")
        if context is not None and metadata is not None:
            raise ValueError("provide context or metadata, not both")

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.event_bus = event_bus
        self.context = dict(context if context is not None else metadata or {})
        self._clock = clock or LiveClock()
        self._lock = asyncio.Lock()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_at: datetime | None = None
        self._generation = 0

    @property
    def state(self) -> CircuitBreakerState:
        """Return the current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Return the number of consecutive failures in the closed state."""
        return self._failure_count

    @property
    def last_failure_time(self) -> datetime | None:
        """Return when the circuit most recently recorded an operation failure."""
        return self._last_failure_at

    async def call[T](self, operation: AsyncOperation[T], *args: Any, **kwargs: Any) -> T:
        """Call ``operation`` unless the circuit is open.

        Args:
            operation: Asynchronous operation to protect.
            *args: Positional arguments passed to ``operation``.
            **kwargs: Keyword arguments passed to ``operation``.

        Returns:
            The operation's result.

        Raises:
            CircuitBreakerOpenError: If the circuit rejects the call.
            Exception: The operation's original exception after recording failure.
        """
        transition: CircuitBreakerOpen | CircuitBreakerClosed | None = None
        async with self._lock:
            if self._state is CircuitBreakerState.OPEN:
                if not self._recovery_elapsed():
                    logger.bind(**self.context).warning("circuit_breaker_call_rejected")
                    raise CircuitBreakerOpenError("circuit breaker is open")
                self._state = CircuitBreakerState.HALF_OPEN
                self._generation += 1
            elif self._state is CircuitBreakerState.HALF_OPEN:
                logger.bind(**self.context).warning("circuit_breaker_probe_rejected")
                raise CircuitBreakerOpenError("circuit breaker probe is in progress")
            generation = self._generation

        await self._publish(transition)

        try:
            result = await operation(*args, **kwargs)
        except Exception:
            transition = await self._record_failure(generation)
            logger.bind(**self.context).exception(
                "circuit_breaker_operation_failed",
                state=self._state.value,
                failure_count=self._failure_count,
                operation=getattr(operation, "__qualname__", repr(operation)),
            )
            await self._publish(transition)
            raise
        else:
            transition = await self._record_success(generation)
            await self._publish(transition)
            return result

    def _recovery_elapsed(self) -> bool:
        if self._last_failure_at is None:
            return True
        return self._now() - self._last_failure_at >= timedelta(seconds=self.recovery_timeout)

    async def _record_failure(self, generation: int) -> CircuitBreakerOpen | None:
        async with self._lock:
            if generation != self._generation:
                return None
            self._last_failure_at = self._now()
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
                self._generation += 1
                return cast("CircuitBreakerOpen", self._event(CircuitBreakerOpen))
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                self._generation += 1
                return cast("CircuitBreakerOpen", self._event(CircuitBreakerOpen))
        return None

    async def _record_success(self, generation: int) -> CircuitBreakerClosed | None:
        async with self._lock:
            if generation != self._generation:
                return None
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._last_failure_at = None
                self._generation += 1
                return cast("CircuitBreakerClosed", self._event(CircuitBreakerClosed))
            self._failure_count = 0
        return None

    def _event(
        self,
        event_type: type[CircuitBreakerOpen] | type[CircuitBreakerClosed],
    ) -> CircuitBreakerOpen | CircuitBreakerClosed:
        allowed = {"event_id", "occurred_at", "correlation_id", "account_id", "bot_id", "mode"}
        event_context = {key: value for key, value in self.context.items() if key in allowed}
        event_context["occurred_at"] = self._now()
        return event_type(**cast("dict[str, Any]", event_context))

    async def _publish(self, event: CircuitBreakerOpen | CircuitBreakerClosed | None) -> None:
        if event is not None and self.event_bus is not None:
            await self.event_bus.publish(event)

    def _now(self) -> datetime:
        value = self._clock() if callable(self._clock) else self._clock.now()
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("clock must return a UTC timestamp")
        return value.astimezone(UTC)


async def retry_async[T](
    operation: AsyncOperation[T],
    *args: Any,
    max_attempts: int,
    backoff_base: float,
    backoff_max: float,
    retry_on: tuple[type[BaseException], ...],
    sleep: AsyncSleep = asyncio.sleep,
    **kwargs: Any,
) -> T:
    """Retry an asynchronous operation with capped exponential backoff.

    Args:
        operation: Asynchronous operation to retry.
        *args: Positional arguments passed to ``operation``.
        max_attempts: Total number of operation attempts, including the first.
        backoff_base: Delay before the second attempt, in seconds.
        backoff_max: Maximum delay between attempts, in seconds.
        retry_on: Exception types that are safe to retry.
        sleep: Injectable asynchronous delay function.
        **kwargs: Keyword arguments passed to ``operation``.

    Returns:
        The first successful operation result.

    Raises:
        ValueError: If retry configuration is invalid.
        Exception: The final or non-retryable operation exception.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if backoff_base < 0 or backoff_max < 0:
        raise ValueError("backoff values must not be negative")
    if backoff_base > backoff_max:
        raise ValueError("backoff_base must not exceed backoff_max")

    for attempt in range(max_attempts):
        try:
            return await operation(*args, **kwargs)
        except retry_on as error:
            if attempt == max_attempts - 1:
                logger.exception(
                    "operation_retry_exhausted",
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    operation=getattr(operation, "__qualname__", repr(operation)),
                )
                raise
            delay = min(backoff_base * (2**attempt), backoff_max)
            logger.warning(
                "operation_retrying",
                error=str(error),
                attempt=attempt + 1,
                max_attempts=max_attempts,
                delay=delay,
                operation=getattr(operation, "__qualname__", repr(operation)),
            )
            await sleep(delay)

    raise RuntimeError("retry loop completed without a result")
