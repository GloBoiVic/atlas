import pytest

from backend.core.events import DomainEvent, EventBus


@pytest.mark.asyncio
async def test_publish_and_drain():
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("test_event", handler)
    event = DomainEvent(name="test_event", bot_id=None)
    await bus.publish(event)
    await bus.drain()

    assert len(received) == 1
    assert received[0].id == event.id
    assert received[0].name == "test_event"


@pytest.mark.asyncio
async def test_multiple_handlers():
    bus = EventBus()
    results: list[str] = []

    async def handler_a(event: DomainEvent) -> None:
        results.append("a")

    async def handler_b(event: DomainEvent) -> None:
        results.append("b")

    bus.subscribe("test_event", handler_a)
    bus.subscribe("test_event", handler_b)

    event = DomainEvent(name="test_event")
    await bus.publish(event)
    await bus.drain()

    assert len(results) == 2
    assert "a" in results
    assert "b" in results


@pytest.mark.asyncio
async def test_handler_exception_does_not_break_drain():
    bus = EventBus()
    received: list[DomainEvent] = []

    async def bad_handler(event: DomainEvent) -> None:
        raise ValueError("oops")

    async def good_handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("test_event", bad_handler)
    bus.subscribe("test_event", good_handler)

    event = DomainEvent(name="test_event")
    await bus.publish(event)
    await bus.drain()

    assert len(received) == 1


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("test_event", handler)
    bus.unsubscribe("test_event", handler)

    event = DomainEvent(name="test_event")
    await bus.publish(event)
    await bus.drain()

    assert len(received) == 0


@pytest.mark.asyncio
async def test_stats():
    bus = EventBus()

    async def handler(event: DomainEvent) -> None:
        pass

    bus.subscribe("test_event", handler)

    stats = bus.stats
    assert stats["queue_size"] == 0
    assert stats["subscribed_events"] == 1


def test_domain_event_requires_name():
    with pytest.raises(ValueError):
        DomainEvent(name="")


def test_domain_event_has_timestamp():
    event = DomainEvent(name="test")
    assert event.timestamp is not None


def test_domain_event_has_id():
    event = DomainEvent(name="test")
    assert event.id is not None
