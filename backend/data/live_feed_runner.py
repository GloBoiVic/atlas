"""EventBus ownership for live market-data provider streams."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode
from backend.core.events import (
    CandleClosed,
    DataFeedError,
    DomainEvent,
    EventBus,
    MarketContextUpdated,
    TickReceived,
)
from backend.data.binance_usdm import BookTicker, MarkPriceUpdate
from backend.data.interfaces import LiveDataProvider
from backend.data.market_context import MarketContextAggregator
from backend.data.models import Candle, Instrument


class LiveMarketContextProvider(Protocol):
    """Optional capability implemented by providers with book/mark streams."""

    def subscribe_book_tickers(
        self, instrument: Instrument
    ) -> AsyncGenerator[BookTicker, None]: ...

    def subscribe_mark_prices(
        self, instrument: Instrument
    ) -> AsyncGenerator[MarkPriceUpdate, None]: ...


class LiveFeedSession:
    """Own and publish one isolated instrument's live feed tasks."""

    def __init__(
        self,
        event_bus: EventBus,
        provider: LiveDataProvider,
        instrument: Instrument,
        timeframe: str,
        *,
        account_id: UUID | None = None,
        bot_id: UUID | None = None,
        mode: AccountMode | None = None,
        correlation_id: UUID | None = None,
        aggregator: MarketContextAggregator | None = None,
    ) -> None:
        if not timeframe:
            raise ValueError("timeframe must not be empty")
        self._event_bus = event_bus
        self._provider = provider
        self._instrument = instrument
        self._timeframe = timeframe
        self._account_id = account_id
        self._bot_id = bot_id
        self._mode = mode
        self._correlation_id = correlation_id
        self._aggregator = aggregator or MarketContextAggregator(instrument.provider)
        self._tasks: set[asyncio.Task[None]] = set()
        self._seen_candles: set[tuple[UUID, str, str, datetime, str]] = set()
        self._started = False
        self._stopped = False

    @property
    def tasks(self) -> tuple[asyncio.Task[None], ...]:
        """Return the session's currently owned tasks."""
        return tuple(self._tasks)

    @property
    def started(self) -> bool:
        """Whether the session has been started."""
        return self._started and not self._stopped

    async def start(self) -> None:
        """Start all supported provider drains without creating orphan tasks."""
        if self._started:
            return
        self._started = True
        self._stopped = False
        drains: list[Callable[[], Coroutine[Any, Any, None]]] = [
            self._drain_candles,
            self._drain_ticks,
        ]
        context_provider = self._context_provider()
        if context_provider is not None:
            drains.extend((
                lambda: self._drain_book(context_provider),
                lambda: self._drain_mark(context_provider),
            ))
        self._tasks = {asyncio.create_task(drain()) for drain in drains}

    async def run(self) -> None:
        """Run until every feed ends, isolating failures to individual feeds."""
        await self.start()
        if not self._tasks:
            return
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            await self.stop()
            raise
        finally:
            self._tasks.clear()
            self._stopped = True

    async def stop(self) -> None:
        """Cancel and await every child task owned by this session."""
        self._stopped = True
        tasks = tuple(self._tasks)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _drain_candles(self) -> None:
        try:
            async for candle in self._provider.subscribe_candles(
                self._instrument, self._timeframe
            ):
                if not candle.is_complete:
                    continue
                key = (
                    candle.instrument_id,
                    candle.provider,
                    candle.timeframe,
                    candle.open_time,
                    candle.price_basis,
                )
                if key in self._seen_candles:
                    continue
                self._seen_candles.add(key)
                await self._publish(
                    CandleClosed(
                        candle=candle,
                        occurred_at=_candle_time(candle),
                        account_id=self._account_id,
                        bot_id=self._bot_id,
                        mode=self._mode,
                        correlation_id=self._correlation_id or uuid4(),
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._publish_error(error)

    async def _drain_ticks(self) -> None:
        try:
            async for tick in self._provider.subscribe_ticks(self._instrument):
                await self._publish(
                    TickReceived(
                        tick=tick,
                        occurred_at=_utc(tick.timestamp),
                        account_id=self._account_id,
                        bot_id=self._bot_id,
                        mode=self._mode,
                        correlation_id=self._correlation_id or uuid4(),
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._publish_error(error)

    async def _drain_book(self, provider: LiveMarketContextProvider) -> None:
        try:
            async for update in provider.subscribe_book_tickers(self._instrument):
                event = self._aggregator.update_book_ticker(update)
                if event is not None:
                    await self._publish(self._with_metadata(event))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._publish_error(error)

    async def _drain_mark(self, provider: LiveMarketContextProvider) -> None:
        try:
            async for update in provider.subscribe_mark_prices(self._instrument):
                event = self._aggregator.update_mark_price(update)
                if event is not None:
                    await self._publish(self._with_metadata(event))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._publish_error(error)

    def _context_provider(self) -> LiveMarketContextProvider | None:
        if not hasattr(self._provider, "subscribe_book_tickers") or not hasattr(
            self._provider, "subscribe_mark_prices"
        ):
            return None
        return cast("LiveMarketContextProvider", self._provider)

    def _with_metadata(self, event: MarketContextUpdated) -> MarketContextUpdated:
        return MarketContextUpdated(
            context=event.context,
            occurred_at=_utc(event.occurred_at),
            account_id=self._account_id,
            bot_id=self._bot_id,
            mode=self._mode,
            correlation_id=self._correlation_id or uuid4(),
        )

    async def _publish(self, event: DomainEvent) -> None:
        await self._event_bus.publish(event)

    async def _publish_error(self, error: Exception) -> None:
        feed_error = getattr(error, "data_feed_error", None)
        source = error if isinstance(error, DataFeedError) else feed_error
        detail = source.error if isinstance(source, DataFeedError) else str(error)
        occurred_at = source.occurred_at if isinstance(source, DataFeedError) else datetime.now(UTC)
        instrument_id = (
            source.instrument_id if isinstance(source, DataFeedError) else self._instrument.id
        )
        await self._publish(
            DataFeedError(
                instrument_id=instrument_id,
                error=detail,
                occurred_at=_utc(occurred_at),
                account_id=self._account_id,
                bot_id=self._bot_id,
                mode=self._mode,
                correlation_id=self._correlation_id or uuid4(),
            )
        )


class LiveFeedRunner:
    """Manage isolated live-feed sessions and their complete task lifecycles."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._sessions: set[LiveFeedSession] = set()

    def create_session(
        self,
        provider: LiveDataProvider,
        instrument: Instrument,
        timeframe: str,
        account_id: UUID | None = None,
        bot_id: UUID | None = None,
        mode: AccountMode | None = None,
        correlation_id: UUID | None = None,
        aggregator: MarketContextAggregator | None = None,
    ) -> LiveFeedSession:
        """Create and register an isolated feed session."""
        session = LiveFeedSession(
            self._event_bus,
            provider,
            instrument,
            timeframe,
            account_id=account_id,
            bot_id=bot_id,
            mode=mode,
            correlation_id=correlation_id,
            aggregator=aggregator,
        )
        self._sessions.add(session)
        return session

    async def start(self) -> None:
        """Start every registered session."""
        await asyncio.gather(*(session.start() for session in tuple(self._sessions)))

    async def run(self) -> None:
        """Start all sessions and await their owned feed tasks."""
        await asyncio.gather(*(session.run() for session in tuple(self._sessions)))

    async def stop(self) -> None:
        """Stop and await every registered session."""
        await asyncio.gather(*(session.stop() for session in tuple(self._sessions)))

    async def close(self) -> None:
        """Stop sessions and release the runner's registry."""
        await self.stop()
        self._sessions.clear()


def _candle_time(candle: Candle) -> datetime:
    return _utc(candle.close_time or candle.open_time)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("live feed event timestamps must be UTC")
    return value.astimezone(UTC)


__all__ = ["LiveFeedRunner", "LiveFeedSession", "LiveMarketContextProvider"]
