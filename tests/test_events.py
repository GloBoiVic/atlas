import asyncio
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import (
    ApiError,
    CandleClosed,
    CircuitBreakerClosed,
    CircuitBreakerOpen,
    ConnectionLost,
    ConnectionRestored,
    DataFeedError,
    DomainEvent,
    EventBus,
    EventFailure,
    InMemoryFailureRecorder,
    OrderFailed,
    OrderFilled,
    OrderRejected,
    OrderSubmitted,
    PositionClosed,
    PositionOpened,
    PositionUpdated,
    RiskApproved,
    RiskRejected,
    SignalGenerated,
    StrategyError,
    TickReceived,
    TradeClosed,
)

EVENT_TYPES: tuple[type[DomainEvent], ...] = (
    CandleClosed,
    TickReceived,
    SignalGenerated,
    RiskApproved,
    RiskRejected,
    OrderSubmitted,
    OrderFilled,
    PositionOpened,
    PositionUpdated,
    PositionClosed,
    TradeClosed,
    ApiError,
    DataFeedError,
    OrderRejected,
    OrderFailed,
    StrategyError,
    ConnectionLost,
    ConnectionRestored,
    CircuitBreakerOpen,
    CircuitBreakerClosed,
)


@pytest.mark.asyncio
async def test_publish_delivers_matching_event_to_handlers_in_registration_order() -> None:
    bus = EventBus()
    results: list[str] = []

    async def first(event: DomainEvent) -> None:
        results.append("first")

    async def second(event: DomainEvent) -> None:
        results.append("second")

    bus.subscribe(CandleClosed, first)
    bus.subscribe(CandleClosed, second)

    event = CandleClosed()
    await bus.publish(event)

    assert results == ["first", "second"]


@pytest.mark.asyncio
async def test_publish_awaits_each_handler_before_starting_next() -> None:
    bus = EventBus()
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    results: list[str] = []

    async def first(event: DomainEvent) -> None:
        results.append("first-start")
        first_started.set()
        await release_first.wait()
        results.append("first-end")

    async def second(event: DomainEvent) -> None:
        results.append("second")

    bus.subscribe(CandleClosed, first)
    bus.subscribe(CandleClosed, second)
    publish_task = asyncio.create_task(bus.publish(CandleClosed()))
    await first_started.wait()
    await asyncio.sleep(0)
    assert results == ["first-start"]

    release_first.set()
    await publish_task

    assert results == ["first-start", "first-end", "second"]


@pytest.mark.asyncio
async def test_subscriptions_match_exact_event_class_only() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(DomainEvent, handler)
    await bus.publish(CandleClosed())

    assert received == []


@pytest.mark.asyncio
async def test_subscription_handle_unsubscribes_one_handler() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    subscription = bus.subscribe(CandleClosed, handler)
    subscription.unsubscribe()
    subscription.unsubscribe()
    await bus.publish(CandleClosed())

    assert received == []
    assert bus.stats == {"subscribed_events": 0}


@pytest.mark.asyncio
async def test_unsubscribe_removes_only_one_duplicate_registration() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    first = bus.subscribe(CandleClosed, handler)
    bus.subscribe(CandleClosed, handler)
    first.unsubscribe()
    await bus.publish(CandleClosed())

    assert len(received) == 1


@pytest.mark.asyncio
async def test_publishing_same_event_twice_does_not_deduplicate() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(CandleClosed, handler)
    event = CandleClosed()
    await bus.publish(event)
    await bus.publish(event)

    assert received == [event, event]


@pytest.mark.asyncio
async def test_handler_failure_is_recorded_pauses_bot_and_later_handlers_run() -> None:
    recorder = InMemoryFailureRecorder()
    paused: list[UUID] = []
    bus = EventBus(failure_recorder=recorder, pause_bot=paused.append)
    received: list[DomainEvent] = []
    bot_id = uuid4()

    async def bad_handler(event: DomainEvent) -> None:
        raise ValueError("oops")

    async def good_handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(CandleClosed, bad_handler)
    bus.subscribe(CandleClosed, good_handler)
    event = CandleClosed(bot_id=bot_id)
    await bus.publish(event)

    assert received == [event]
    assert len(recorder.failures) == 1
    assert recorder.failures[0].event is event
    assert isinstance(recorder.failures[0].exception, ValueError)
    assert paused == [bot_id]


@pytest.mark.asyncio
async def test_failure_without_bot_does_not_pause() -> None:
    paused: list[UUID] = []
    bus = EventBus(pause_bot=paused.append)

    async def bad_handler(event: DomainEvent) -> None:
        raise RuntimeError("failure")

    bus.subscribe(ApiError, bad_handler)
    await bus.publish(ApiError())

    assert paused == []


@pytest.mark.asyncio
async def test_failure_callback_errors_are_isolated_from_later_handlers() -> None:
    class FailingRecorder:
        def record(self, failure: EventFailure) -> None:
            raise RuntimeError("recording failed")

    def failing_pause(bot_id: UUID) -> None:
        raise RuntimeError("pause failed")

    bus = EventBus(failure_recorder=FailingRecorder(), pause_bot=failing_pause)
    received: list[DomainEvent] = []

    async def bad_handler(event: DomainEvent) -> None:
        raise ValueError("handler failed")

    async def good_handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(CandleClosed, bad_handler)
    bus.subscribe(CandleClosed, good_handler)
    event = CandleClosed(bot_id=uuid4())

    await bus.publish(event)

    assert received == [event]


def test_domain_event_metadata_defaults_and_account_mode() -> None:
    account_id = uuid4()
    bot_id = uuid4()
    event = CandleClosed(account_id=account_id, bot_id=bot_id, mode=AccountMode.PAPER)

    assert event.event_id is not None
    assert event.correlation_id is not None
    assert event.occurred_at.tzinfo is UTC
    assert event.account_id == account_id
    assert event.bot_id == bot_id
    assert event.mode is AccountMode.PAPER


def test_domain_event_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValueError, match="UTC"):
        CandleClosed(occurred_at=datetime(2026, 1, 1))


def test_domain_event_rejects_non_utc_occurred_at() -> None:
    with pytest.raises(ValueError, match="UTC"):
        CandleClosed(occurred_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2))))


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_all_required_event_classes_are_metadata_only(
    event_type: type[DomainEvent],
) -> None:
    event = event_type()

    assert set(event.__dataclass_fields__) == {
        "event_id",
        "occurred_at",
        "correlation_id",
        "account_id",
        "bot_id",
        "mode",
    }
