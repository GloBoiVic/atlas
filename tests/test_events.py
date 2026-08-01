from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import (
    ApiError,
    CandleClosed,
    DomainEvent,
    EventBus,
    InMemoryFailureRecorder,
    TickReceived,
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
    results: list[str] = []

    async def first(event: DomainEvent) -> None:
        results.append("first-start")
        results.append("first-end")

    async def second(event: DomainEvent) -> None:
        results.append("second")

    bus.subscribe(CandleClosed, first)
    bus.subscribe(CandleClosed, second)
    await bus.publish(CandleClosed())

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
    assert bus.stats == {"queue_size": 0, "subscribed_events": 0}


@pytest.mark.asyncio
async def test_handler_failure_is_recorded_pauses_bot_and_later_handlers_run() -> None:
    recorder = InMemoryFailureRecorder()
    paused: list = []
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
    paused: list = []
    bus = EventBus(pause_bot=paused.append)

    async def bad_handler(event: DomainEvent) -> None:
        raise RuntimeError("failure")

    bus.subscribe(ApiError, bad_handler)
    await bus.publish(ApiError())

    assert paused == []


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
    with pytest.raises(ValueError, match="timezone-aware"):
        CandleClosed(occurred_at=datetime(2026, 1, 1))


def test_event_classes_have_metadata_only() -> None:
    event = TickReceived()

    assert set(event.__dataclass_fields__) == {
        "event_id",
        "occurred_at",
        "correlation_id",
        "account_id",
        "bot_id",
        "mode",
    }
