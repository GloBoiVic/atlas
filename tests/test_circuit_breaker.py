import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.clock import SimulationClock
from backend.core.errors import CircuitBreakerOpenError
from backend.core.events import CircuitBreakerClosed, CircuitBreakerOpen, EventBus
from backend.health.circuit_breaker import CircuitBreaker, CircuitBreakerState, retry_async


@pytest.mark.asyncio
async def test_breaker_opens_at_failure_threshold_and_rejects_calls() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

    async def fail() -> None:
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        await breaker.call(fail)
    with pytest.raises(ConnectionError):
        await breaker.call(fail)

    assert breaker.state is CircuitBreakerState.OPEN
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(fail)


@pytest.mark.asyncio
async def test_breaker_half_open_success_closes_and_resets_failures() -> None:
    clock = SimulationClock(datetime(2026, 8, 1, tzinfo=UTC))
    breaker = CircuitBreaker(1, 10, clock=clock)

    async def fail() -> None:
        raise TimeoutError

    with pytest.raises(TimeoutError):
        await breaker.call(fail)
    clock.advance(clock.now() + timedelta(seconds=10))

    assert await breaker.call(lambda: _value("ok")) == "ok"
    assert breaker.state is CircuitBreakerState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_half_open_allows_only_one_concurrent_probe() -> None:
    clock = SimulationClock(datetime(2026, 8, 1, tzinfo=UTC))
    breaker = CircuitBreaker(1, 1, clock=clock)
    started = asyncio.Event()
    release = asyncio.Event()

    async def fail() -> None:
        raise RuntimeError

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    clock.advance(clock.now() + timedelta(seconds=1))

    async def probe() -> str:
        started.set()
        await release.wait()
        return "ok"

    first = asyncio.create_task(breaker.call(probe))
    await started.wait()
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(probe)
    release.set()
    assert await first == "ok"


@pytest.mark.asyncio
async def test_stale_closed_success_cannot_close_later_half_open_probe() -> None:
    clock = SimulationClock(datetime(2026, 8, 1, tzinfo=UTC))
    events: list[object] = []
    bus = EventBus()
    bus.subscribe(CircuitBreakerOpen, events.append)
    bus.subscribe(CircuitBreakerClosed, events.append)
    breaker = CircuitBreaker(1, 1, bus, clock=clock)
    stale_started = asyncio.Event()
    stale_release = asyncio.Event()
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()
    calls = 0

    async def stale_operation() -> str:
        nonlocal calls
        calls += 1
        stale_started.set()
        await stale_release.wait()
        return "stale"

    stale = asyncio.create_task(breaker.call(stale_operation))
    await stale_started.wait()

    async def fail() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    clock.advance(clock.now() + timedelta(seconds=1))

    async def probe() -> str:
        nonlocal calls
        calls += 1
        probe_started.set()
        await probe_release.wait()
        return "probe"

    probe_task = asyncio.create_task(breaker.call(probe))
    await probe_started.wait()
    stale_release.set()
    assert await stale == "stale"

    assert breaker.state is CircuitBreakerState.HALF_OPEN
    assert len(events) == 1
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(probe)
    assert calls == 3

    probe_release.set()
    assert await probe_task == "probe"


@pytest.mark.asyncio
async def test_stale_closed_failure_cannot_open_later_half_open_probe() -> None:
    clock = SimulationClock(datetime(2026, 8, 1, tzinfo=UTC))
    events: list[object] = []
    bus = EventBus()
    bus.subscribe(CircuitBreakerOpen, events.append)
    bus.subscribe(CircuitBreakerClosed, events.append)
    breaker = CircuitBreaker(1, 1, bus, clock=clock)
    stale_started = asyncio.Event()
    stale_release = asyncio.Event()
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()
    calls = 0

    async def stale_operation() -> None:
        nonlocal calls
        calls += 1
        stale_started.set()
        await stale_release.wait()
        raise TimeoutError

    stale = asyncio.create_task(breaker.call(stale_operation))
    await stale_started.wait()

    async def fail() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    clock.advance(clock.now() + timedelta(seconds=1))

    async def probe() -> str:
        nonlocal calls
        calls += 1
        probe_started.set()
        await probe_release.wait()
        return "probe"

    probe_task = asyncio.create_task(breaker.call(probe))
    await probe_started.wait()
    stale_release.set()
    with pytest.raises(TimeoutError):
        await stale

    assert breaker.state is CircuitBreakerState.HALF_OPEN
    assert len(events) == 1
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(probe)
    assert calls == 3

    probe_release.set()
    assert await probe_task == "probe"


@pytest.mark.asyncio
async def test_half_open_failure_reopens_breaker() -> None:
    clock = SimulationClock(datetime(2026, 8, 1, tzinfo=UTC))
    breaker = CircuitBreaker(1, 1, clock=clock)

    async def fail() -> None:
        raise ConnectionError

    with pytest.raises(ConnectionError):
        await breaker.call(fail)
    clock.advance(clock.now() + timedelta(seconds=1))

    with pytest.raises(ConnectionError):
        await breaker.call(fail)

    assert breaker.state is CircuitBreakerState.OPEN
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(fail)


@pytest.mark.asyncio
async def test_breaker_publishes_only_open_and_closed_transitions_with_context() -> None:
    bus = EventBus()
    events: list[object] = []
    clock = SimulationClock(datetime(2026, 8, 1, tzinfo=UTC))

    async def record_open(event: CircuitBreakerOpen) -> None:
        events.append(event)

    async def record_closed(event: CircuitBreakerClosed) -> None:
        events.append(event)

    bus.subscribe(CircuitBreakerOpen, record_open)
    bus.subscribe(CircuitBreakerClosed, record_closed)
    context = {"account_id": uuid4(), "bot_id": uuid4(), "mode": AccountMode.PAPER}
    breaker = CircuitBreaker(1, 1, bus, context=context, clock=clock)

    async def fail() -> None:
        raise ValueError

    with pytest.raises(ValueError):
        await breaker.call(fail)
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(fail)
    assert len(events) == 1
    assert isinstance(events[0], CircuitBreakerOpen)
    assert events[0].bot_id == context["bot_id"]
    assert events[0].occurred_at == clock.now()
    clock.advance(clock.now() + timedelta(seconds=1))
    assert await breaker.call(lambda: _value(1)) == 1
    assert len(events) == 2
    assert isinstance(events[1], CircuitBreakerClosed)
    assert events[1].occurred_at == clock.now()


@pytest.mark.asyncio
async def test_retry_retries_configured_failures_and_returns_success() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError
        return "success"

    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    result = await retry_async(
        operation,
        max_attempts=3,
        backoff_base=0.1,
        backoff_max=1,
        retry_on=(ConnectionError,),
        sleep=sleep,
    )

    assert result == "success"
    assert sleeps == [0.1, 0.2]


@pytest.mark.asyncio
async def test_retry_reraises_exhausted_and_non_transient_failures() -> None:
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ConnectionError

    with pytest.raises(ConnectionError):
        await retry_async(
            operation,
            max_attempts=3,
            backoff_base=0,
            backoff_max=0,
            retry_on=(ConnectionError,),
        )
    assert attempts == 3

    async def non_transient() -> None:
        raise ValueError

    with pytest.raises(ValueError):
        await retry_async(
            non_transient,
            max_attempts=3,
            backoff_base=1,
            backoff_max=2,
            retry_on=(ConnectionError,),
        )


@pytest.mark.asyncio
async def test_retry_caps_exponential_backoff() -> None:
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    async def operation() -> None:
        raise ConnectionError

    with pytest.raises(ConnectionError):
        await retry_async(
            operation,
            max_attempts=5,
            backoff_base=2,
            backoff_max=3,
            retry_on=(ConnectionError,),
            sleep=sleep,
        )

    assert sleeps == [2, 3, 3, 3]


async def _value(value: object) -> object:
    return value
