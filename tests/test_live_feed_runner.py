import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import CandleClosed, DataFeedError, EventBus, EventHandler, TickReceived
from backend.data.binance_usdm import BINANCE_USDM_PROVIDER
from backend.data.interfaces import LiveDataProvider
from backend.data.live_feed_runner import LiveFeedRunner, LiveFeedSession
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
