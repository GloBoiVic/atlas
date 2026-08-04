import asyncio
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import (
    ApiError,
    BotStatusChanged,
    CandleClosed,
    CircuitBreakerClosed,
    CircuitBreakerOpen,
    ConnectionLost,
    ConnectionRestored,
    DataFeedError,
    DomainEvent,
    EventBus,
    EventFailure,
    HealthStatusChanged,
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
    TickReceived,
    TradeClosed,
)
from backend.data.models import Candle, Tick
from backend.execution.models import Fill, Order, OrderSide, Position, PositionSide, Trade
from backend.strategy.contracts import Signal, SignalDirection

# CandleClosed and TickReceived now require keyword-only payload fields.
# Construct a minimal valid payload for tests.
_FIXTURE_INSTRUMENT_ID = uuid4()
_FIXTURE_CANDLE = Candle(
    instrument_id=_FIXTURE_INSTRUMENT_ID,
    provider="binance",
    timeframe="1m",
    open_time=datetime(2026, 1, 1, tzinfo=UTC),
    open=Decimal("100"),
    high=Decimal("110"),
    low=Decimal("90"),
    close=Decimal("105"),
    base_volume=Decimal("1000"),
)
_FIXTURE_TICK = Tick(
    instrument_id=_FIXTURE_INSTRUMENT_ID,
    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    price=Decimal("100.5"),
)
_FIXTURE_SIGNAL = Signal(
    instrument_id=_FIXTURE_INSTRUMENT_ID,
    direction=SignalDirection.BUY,
    strength=Decimal("1"),
    metadata={},
    candle_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    strategy_version_id=uuid4(),
    strategy_name="test",
    strategy_commit_sha="abc123",
)


def _make_candle_closed(**kwargs: object) -> CandleClosed:
    extra: dict[str, object] = {}
    if "candle" not in kwargs:
        extra["candle"] = _FIXTURE_CANDLE
    return CandleClosed(**{**extra, **kwargs})  # type: ignore[arg-type]


def _make_tick_received(**kwargs: object) -> TickReceived:
    extra: dict[str, object] = {}
    if "tick" not in kwargs:
        extra["tick"] = _FIXTURE_TICK
    return TickReceived(**{**extra, **kwargs})  # type: ignore[arg-type]


# Event types that remain metadata-only (their payloads belong to later slices).
EVENT_TYPES: tuple[type[DomainEvent], ...] = (
    ApiError,
    DataFeedError,
    ConnectionLost,
    ConnectionRestored,
    CircuitBreakerOpen,
    CircuitBreakerClosed,
    BotStatusChanged,
    HealthStatusChanged,
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

    event = _make_candle_closed()
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
    publish_task = asyncio.create_task(bus.publish(_make_candle_closed()))
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
    await bus.publish(_make_candle_closed())

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
    await bus.publish(_make_candle_closed())

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
    await bus.publish(_make_candle_closed())

    assert len(received) == 1


@pytest.mark.asyncio
async def test_publishing_same_event_twice_does_not_deduplicate() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe(CandleClosed, handler)
    event = _make_candle_closed()
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
    event = _make_candle_closed(bot_id=bot_id)
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
    event = _make_candle_closed(bot_id=uuid4())

    await bus.publish(event)

    assert received == [event]


def test_domain_event_metadata_defaults_and_account_mode() -> None:
    account_id = uuid4()
    bot_id = uuid4()
    event = _make_candle_closed(account_id=account_id, bot_id=bot_id, mode=AccountMode.PAPER)

    assert event.event_id is not None
    assert event.correlation_id is not None
    assert event.occurred_at.tzinfo is UTC
    assert event.account_id == account_id
    assert event.bot_id == bot_id
    assert event.mode is AccountMode.PAPER
    assert event.candle is _FIXTURE_CANDLE


def test_domain_event_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValueError, match="UTC"):
        _make_candle_closed(occurred_at=datetime(2026, 1, 1))


def test_domain_event_rejects_non_utc_occurred_at() -> None:
    with pytest.raises(ValueError, match="UTC"):
        _make_candle_closed(
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))
        )


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


def test_candle_closed_carries_candle_payload() -> None:
    candle = Candle(
        instrument_id=uuid4(),
        provider="binance",
        timeframe="1h",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("50000"),
        high=Decimal("51000"),
        low=Decimal("49000"),
        close=Decimal("50500"),
        base_volume=Decimal("100"),
    )
    event = CandleClosed(candle=candle)
    assert event.candle is candle
    assert event.candle.instrument_id == candle.instrument_id
    assert "candle" in event.__dataclass_fields__
    # candle is kw_only to avoid inheritance ordering issues
    assert event.__dataclass_fields__["candle"].kw_only is True


def test_tick_received_carries_tick_payload() -> None:
    tick = Tick(
        instrument_id=uuid4(),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        price=Decimal("100.5"),
    )
    event = TickReceived(tick=tick)
    assert event.tick is tick
    assert "tick" in event.__dataclass_fields__
    assert event.__dataclass_fields__["tick"].kw_only is True


def test_risk_events_carry_frozen_keyword_only_payloads_and_metadata() -> None:
    event = RiskApproved(
        signal=_FIXTURE_SIGNAL,
        position_size=Decimal("1"),
        stop_loss=Decimal("99"),
        take_profit=Decimal("0"),
        account_id=uuid4(),
        bot_id=uuid4(),
        mode=AccountMode.PAPER,
    )
    assert event.signal is _FIXTURE_SIGNAL
    assert event.__dataclass_fields__["signal"].kw_only is True
    with pytest.raises((AttributeError, TypeError)):
        event.position_size = Decimal("2")  # type: ignore[misc]


def test_risk_rejection_carries_typed_signal_payload() -> None:
    event = RiskRejected(signal=_FIXTURE_SIGNAL, reason="invalid_stop: bad geometry")
    assert event.signal is _FIXTURE_SIGNAL
    assert event.reason.startswith("invalid_stop")


def _execution_fixtures() -> tuple[Order, Fill, Position, Trade]:
    account_id = uuid4()
    instrument_id = uuid4()
    order = Order(
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        client_order_id="atlas-test-order",
        bot_id=uuid4(),
        mode=AccountMode.PAPER,
    )
    fill = Fill(
        order_id=order.id,
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("100"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    position = Position(
        account_id=account_id,
        instrument_id=instrument_id,
        side=PositionSide.LONG,
        quantity=Decimal("1"),
        entry_price=Decimal("100"),
        mode=AccountMode.PAPER,
    )
    trade = Trade(
        account_id=account_id,
        instrument_id=instrument_id,
        position_id=position.id,
        direction=PositionSide.LONG,
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        total_fees=Decimal("0.1"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return order, fill, position, trade


def test_execution_events_have_frozen_keyword_only_payloads() -> None:
    order, fill, position, trade = _execution_fixtures()
    events = (
        OrderSubmitted(order=order, broker_order_id="broker-1"),
        OrderFilled(order=order, fill=fill),
        PositionOpened(position=position),
        PositionUpdated(position=position),
        PositionClosed(position=position),
        TradeClosed(trade=trade),
        OrderRejected(order_id=order.id, reason="insufficient_margin: test"),
        OrderFailed(order_id=order.id, error="timeout"),
    )

    for event in events:
        payloads = set(event.__dataclass_fields__) - set(DomainEvent.__dataclass_fields__)
        assert payloads
        assert all(event.__dataclass_fields__[name].kw_only for name in payloads)

    with pytest.raises((AttributeError, TypeError)):
        events[0].broker_order_id = "changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_candle_closed_passed_to_eventbus_delivers_payload() -> None:
    """EventBus delivery preserves the candle payload through the handler."""
    bus = EventBus()
    candle = Candle(
        instrument_id=uuid4(),
        provider="binance",
        timeframe="1m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        base_volume=Decimal("1000"),
    )
    received: list[Candle] = []

    async def handler(event: DomainEvent) -> None:
        assert isinstance(event, CandleClosed)
        received.append(event.candle)

    bus.subscribe(CandleClosed, handler)

    await bus.publish(CandleClosed(candle=candle))
    assert received == [candle]
