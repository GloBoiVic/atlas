import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.clock import Clock
from backend.core.events import (
    CandleClosed,
    DataFeedError,
    EventBus,
    EventHandler,
    MarketContextUpdated,
    TickReceived,
)
from backend.data.binance_usdm import (
    BINANCE_USDM_PROVIDER,
    BookTicker,
    MarkPriceUpdate,
)
from backend.data.interfaces import LiveDataProvider
from backend.data.live_feed_runner import (
    LiveFeedRunner,
    LiveFeedSession,
    LiveMarketContextProvider,
)
from backend.data.market_context import MarketContextAggregator
from backend.data.models import Candle, Instrument, Tick


class FiniteProvider(LiveDataProvider):
    def __init__(self, candle: Candle, tick: Tick) -> None:
        self.candle = candle
        self.tick = tick

    async def subscribe_candles(
        self, instrument: Instrument, timeframe: str
    ) -> AsyncGenerator[Candle, None]:
        yield self.candle

    async def subscribe_ticks(self, instrument: Instrument) -> AsyncGenerator[Tick, None]:
        yield self.tick


class FailingProvider(LiveDataProvider):
    async def subscribe_candles(
        self, instrument: Instrument, timeframe: str
    ) -> AsyncGenerator[Candle, None]:
        raise RuntimeError("candle transport failed")
        yield  # pragma: no cover

    async def subscribe_ticks(self, instrument: Instrument) -> AsyncGenerator[Tick, None]:
        while True:
            await asyncio.sleep(3600)
            yield Tick(instrument.id, datetime.now(UTC), Decimal("1"))


class DuplicateCandleProvider(LiveDataProvider):
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self.candles = candles

    async def subscribe_candles(
        self, instrument: Instrument, timeframe: str
    ) -> AsyncGenerator[Candle, None]:
        for candle in self.candles:
            yield candle

    async def subscribe_ticks(self, instrument: Instrument) -> AsyncGenerator[Tick, None]:
        if False:
            yield Tick(instrument.id, datetime.now(UTC), Decimal("1"))


class FixedClock(Clock):
    def __init__(self, timestamp: datetime) -> None:
        self.timestamp = timestamp

    def now(self) -> datetime:
        return self.timestamp


class ContextProvider(FiniteProvider, LiveMarketContextProvider):
    def __init__(
        self,
        candle: Candle,
        tick: Tick,
        book: BookTicker,
        mark: MarkPriceUpdate,
        *,
        fail_book: bool = False,
        hold_mark: asyncio.Event | None = None,
        mark_closed: asyncio.Event | None = None,
    ) -> None:
        super().__init__(candle, tick)
        self.book = book
        self.mark = mark
        self.fail_book = fail_book
        self.hold_mark = hold_mark
        self.mark_closed = mark_closed

    async def subscribe_book_tickers(
        self, instrument: Instrument
    ) -> AsyncGenerator[BookTicker, None]:
        if self.fail_book:
            raise RuntimeError("book transport failed")
        yield self.book

    async def subscribe_mark_prices(
        self, instrument: Instrument
    ) -> AsyncGenerator[MarkPriceUpdate, None]:
        try:
            if self.hold_mark is not None:
                await self.hold_mark.wait()
            else:
                yield self.mark
        finally:
            if self.mark_closed is not None:
                self.mark_closed.set()


def _context_updates(
    instrument_id: UUID, timestamp: datetime
) -> tuple[BookTicker, MarkPriceUpdate]:
    return (
        BookTicker(instrument_id, timestamp, Decimal("100"), Decimal("101")),
        MarkPriceUpdate(
            instrument_id,
            timestamp,
            Decimal("100.5"),
            Decimal("100.25"),
            Decimal("-0.0001"),
            timestamp + timedelta(hours=8),
        ),
    )


def _data(instrument_id: UUID) -> tuple[Candle, Tick]:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(
        instrument_id=instrument_id,
        provider=BINANCE_USDM_PROVIDER,
        timeframe="1m",
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=1),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        base_volume=Decimal("1"),
    )
    return candle, Tick(instrument_id, timestamp, Decimal("100.5"))


@pytest.mark.asyncio
async def test_session_publishes_typed_events_with_scope_metadata() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    candle, tick = _data(instrument.id)
    bus = EventBus()
    received: list[object] = []
    account_id, bot_id, correlation_id = uuid4(), uuid4(), uuid4()

    async def record(event: object) -> None:
        received.append(event)

    bus.subscribe(CandleClosed, record)
    bus.subscribe(TickReceived, record)
    session = LiveFeedSession(
        bus,
        FiniteProvider(candle, tick),
        instrument,
        "1m",
        account_id=account_id,
        bot_id=bot_id,
        mode=AccountMode.PAPER,
        correlation_id=correlation_id,
    )

    assert session._context_provider() is None
    await session.run()

    assert isinstance(received[0], CandleClosed)
    assert isinstance(received[1], TickReceived)
    assert received[0].account_id == account_id
    assert received[1].bot_id == bot_id
    assert received[0].correlation_id == correlation_id
    assert received[0].occurred_at == candle.close_time
    assert not session.tasks


@pytest.mark.asyncio
async def test_session_suppresses_incomplete_and_duplicate_candles() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    candle, _tick = _data(instrument.id)
    incomplete = replace(candle, is_complete=False)
    bus = EventBus()
    received: list[CandleClosed] = []

    async def record(event: CandleClosed) -> None:
        received.append(event)

    bus.subscribe(CandleClosed, cast("EventHandler", record))
    session = LiveFeedSession(
        bus,
        DuplicateCandleProvider((incomplete, candle, candle)),
        instrument,
        "1m",
    )

    await session.run()

    assert [event.candle for event in received] == [candle]


@pytest.mark.asyncio
async def test_context_capability_drains_publish_wrapped_context_metadata() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    candle, tick = _data(instrument.id)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    book, mark = _context_updates(instrument.id, timestamp)
    provider: LiveMarketContextProvider = ContextProvider(candle, tick, book, mark)
    bus = EventBus()
    received: list[MarketContextUpdated] = []
    account_id, bot_id, correlation_id = uuid4(), uuid4(), uuid4()

    async def record(event: MarketContextUpdated) -> None:
        received.append(event)

    bus.subscribe(MarketContextUpdated, cast("EventHandler", record))
    session = LiveFeedSession(
        bus,
        cast("LiveDataProvider", provider),
        instrument,
        "1m",
        account_id=account_id,
        bot_id=bot_id,
        mode=AccountMode.PAPER,
        correlation_id=correlation_id,
        aggregator=MarketContextAggregator("binance_usdm", clock=FixedClock(timestamp)),
    )

    assert session._context_provider() is provider
    await session.run()

    assert len(received) == 1
    assert received[0].context.bid == Decimal("100")
    assert received[0].occurred_at == timestamp
    assert received[0].account_id == account_id
    assert received[0].bot_id == bot_id
    assert received[0].mode is AccountMode.PAPER
    assert received[0].correlation_id == correlation_id


@pytest.mark.asyncio
async def test_context_drain_failure_isolated_and_cleaned_up() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    candle, tick = _data(instrument.id)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    book, mark = _context_updates(instrument.id, timestamp)
    provider = ContextProvider(candle, tick, book, mark, fail_book=True)
    bus = EventBus()
    errors: list[DataFeedError] = []

    async def record(event: DataFeedError) -> None:
        errors.append(event)

    bus.subscribe(DataFeedError, cast("EventHandler", record))
    session = LiveFeedSession(
        bus,
        provider,
        instrument,
        "1m",
        aggregator=MarketContextAggregator("binance_usdm", clock=FixedClock(timestamp)),
    )

    await session.run()

    assert len(errors) == 1
    assert errors[0].error == "book transport failed"
    assert not session.tasks


@pytest.mark.asyncio
async def test_context_drain_cancellation_closes_provider_generator() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    candle, tick = _data(instrument.id)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    book, mark = _context_updates(instrument.id, timestamp)
    release_mark = asyncio.Event()
    mark_closed = asyncio.Event()
    provider = ContextProvider(
        candle,
        tick,
        book,
        mark,
        hold_mark=release_mark,
        mark_closed=mark_closed,
    )
    session = LiveFeedSession(
        EventBus(),
        provider,
        instrument,
        "1m",
        aggregator=MarketContextAggregator("binance_usdm", clock=FixedClock(timestamp)),
    )

    await session.start()
    await asyncio.sleep(0)
    await session.stop()

    assert mark_closed.is_set()
    assert not session.tasks


@pytest.mark.asyncio
async def test_session_failure_isolated_and_published_once() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    bus = EventBus()
    errors: list[DataFeedError] = []

    async def record(event: DataFeedError) -> None:
        errors.append(event)

    bus.subscribe(DataFeedError, cast("EventHandler", record))
    session = LiveFeedSession(bus, FailingProvider(), instrument, "1m")
    await session.start()
    await asyncio.sleep(0)

    assert len(errors) == 1
    assert errors[0].instrument_id == instrument.id
    assert session.tasks
    await session.stop()
    assert not session.tasks
    assert all(task.done() for task in session.tasks)


@pytest.mark.asyncio
async def test_runner_cancellation_awaits_all_child_tasks() -> None:
    instrument = Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")
    candle, tick = _data(instrument.id)
    bus = EventBus()
    runner = LiveFeedRunner(bus)
    session = runner.create_session(FiniteProvider(candle, tick), instrument, "1m")
    await runner.start()
    await runner.stop()

    assert not session.tasks
    assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
