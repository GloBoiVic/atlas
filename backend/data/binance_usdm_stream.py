"""Async Binance USDⓈ-M public-stream subscriptions."""

import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Protocol, TypedDict, cast
from uuid import UUID

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from backend.core.events import DataFeedError
from backend.data.binance_usdm import (
    BINANCE_USDM_PROVIDER,
    BinanceUsdMStreamingConfig,
    BookTicker,
    MarkPriceUpdate,
    parse_binance_usdm_agg_trade,
    parse_binance_usdm_book_ticker,
    parse_binance_usdm_kline,
    parse_binance_usdm_mark_price,
)
from backend.data.interfaces import LiveDataProvider
from backend.data.models import Candle, Instrument, Tick


class _WebSocket(Protocol):
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

    async def __anext__(self) -> str | bytes: ...


type Sleeper = Callable[[float], Awaitable[None]]
type ErrorPublisher = Callable[[DataFeedError], Awaitable[None] | None]
type CandleKey = tuple[UUID, str, str, datetime, str]


class ConnectionSettings(TypedDict):
    """Transport settings passed to an injected WebSocket connection factory."""

    ping_interval: float
    ping_timeout: float
    close_timeout: float


class ConnectionFactory(Protocol):
    """Create one typed async WebSocket context for a stream URL."""

    def __call__(
        self,
        url: str,
        *,
        ping_interval: float,
        ping_timeout: float,
        close_timeout: float,
    ) -> AbstractAsyncContextManager[_WebSocket]: ...


class BinanceUsdMStreamingProvider(LiveDataProvider):
    """Stream normalized public USDⓈ-M market data from Binance fstream."""

    def __init__(
        self,
        config: BinanceUsdMStreamingConfig | None = None,
        connection_factory: ConnectionFactory | None = None,
        sleeper: Sleeper | None = None,
        max_reconnect_attempts: int | None = None,
        error_publisher: ErrorPublisher | None = None,
    ) -> None:
        self._config = config or BinanceUsdMStreamingConfig()
        configured_attempts = (
            self._config.max_reconnect_attempts
            if max_reconnect_attempts is None
            else max_reconnect_attempts
        )
        if configured_attempts < 0:
            raise ValueError("max_reconnect_attempts must not be negative")
        self._connection_factory: ConnectionFactory = (
            connection_factory or _default_connection_factory
        )
        self._sleeper = sleeper or asyncio.sleep
        self._max_reconnect_attempts = configured_attempts
        self._error_publisher = error_publisher
        self._active_subscriptions: set[tuple[str, UUID, str | None]] = set()
        self._emitted_candles: set[CandleKey] = set()
        self._last_candle_open: dict[tuple[UUID, str], datetime] = {}

    async def subscribe_candles(
        self, instrument: Instrument, timeframe: str
    ) -> AsyncGenerator[Candle, None]:
        """Yield only completed, duplicate-free klines."""
        self._validate_instrument(instrument)
        if not timeframe:
            raise ValueError("timeframe must not be empty")
        key = self._claim("candle", instrument.id, timeframe)
        try:
            try:
                messages = self._messages(self._stream(instrument, f"kline_{timeframe}"))
                async for payload in messages:
                    try:
                        candle = parse_binance_usdm_kline(payload, instrument, timeframe)
                    except (TypeError, ValueError) as error:
                        await self._publish_error(instrument.id, f"invalid_message: {error}")
                        continue
                    if not candle.is_complete:
                        continue
                    candle_key: CandleKey = (
                        candle.instrument_id,
                        candle.provider,
                        candle.timeframe,
                        candle.open_time,
                        candle.price_basis,
                    )
                    if candle_key in self._emitted_candles:
                        continue
                    previous = self._last_candle_open.get((instrument.id, timeframe))
                    if previous is not None:
                        interval = _timeframe_interval(timeframe)
                        if candle.open_time - previous > interval:
                            await self._publish_error(
                                instrument.id,
                                "gap_detected: missing completed candles before "
                                f"{candle.open_time.isoformat()}",
                            )
                    self._last_candle_open[(instrument.id, timeframe)] = max(
                        candle.open_time, previous or candle.open_time
                    )
                    self._emitted_candles.add(candle_key)
                    yield candle
            except StreamRetryExhaustedError as error:
                await self._publish_error(instrument.id, f"retry_exhausted: {error.detail}")
                raise
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                await self._publish_error(instrument.id, f"protocol_error: {error}")
                raise
        finally:
            self._active_subscriptions.remove(key)

    async def subscribe_ticks(self, instrument: Instrument) -> AsyncGenerator[Tick, None]:
        """Yield normalized aggregate trades."""
        async for value in self._subscribe_parsed(
            "agg_trade", instrument, parse_binance_usdm_agg_trade
        ):
            yield cast("Tick", value)

    async def subscribe_book_tickers(
        self, instrument: Instrument
    ) -> AsyncGenerator[BookTicker, None]:
        """Yield normalized best bid/ask updates."""
        async for value in self._subscribe_parsed(
            "book_ticker", instrument, parse_binance_usdm_book_ticker
        ):
            yield cast("BookTicker", value)

    async def subscribe_mark_prices(
        self, instrument: Instrument
    ) -> AsyncGenerator[MarkPriceUpdate, None]:
        """Yield normalized mark/index/funding updates."""
        async for value in self._subscribe_parsed(
            "mark_price", instrument, parse_binance_usdm_mark_price
        ):
            yield cast("MarkPriceUpdate", value)

    async def _subscribe_parsed(
        self,
        stream_kind: str,
        instrument: Instrument,
        parser: Callable[[Mapping[str, object], Instrument], object],
    ) -> AsyncGenerator[object, None]:
        self._validate_instrument(instrument)
        key = self._claim(stream_kind, instrument.id, None)
        stream = {
            "agg_trade": "aggTrade",
            "book_ticker": "bookTicker",
            "mark_price": "markPrice@1s",
        }[stream_kind]
        try:
            try:
                async for payload in self._messages(self._stream(instrument, stream)):
                    try:
                        yield parser(payload, instrument)
                    except (TypeError, ValueError) as error:
                        await self._publish_error(instrument.id, f"invalid_message: {error}")
                        continue
            except StreamRetryExhaustedError as error:
                await self._publish_error(instrument.id, f"retry_exhausted: {error.detail}")
                raise
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                await self._publish_error(instrument.id, f"protocol_error: {error}")
                raise
        finally:
            self._active_subscriptions.remove(key)

    async def _messages(self, stream: str) -> AsyncGenerator[Mapping[str, object], None]:
        reconnect_attempt = 0
        while True:
            try:
                settings: ConnectionSettings = {
                    "ping_interval": self._config.ping_interval_seconds,
                    "ping_timeout": self._config.ping_timeout_seconds,
                    "close_timeout": self._config.close_timeout_seconds,
                }
                async with self._connection_factory(stream, **settings) as websocket:
                    async for raw_message in websocket:
                        message = (
                            raw_message.decode()
                            if isinstance(raw_message, bytes)
                            else raw_message
                        )
                        decoded = json.loads(message)
                        if not isinstance(decoded, Mapping):
                            raise ValueError("Binance stream message must be an object")
                        yield cast("Mapping[str, object]", decoded)
                return
            except asyncio.CancelledError:
                raise
            except (ConnectionClosed, OSError, TimeoutError) as error:
                if reconnect_attempt >= self._max_reconnect_attempts:
                    raise StreamRetryExhaustedError(str(error)) from error
                reconnect_attempt += 1
                delay = min(
                    self._config.reconnect_backoff_seconds * (2 ** (reconnect_attempt - 1)),
                    self._config.reconnect_backoff_max_seconds,
                )
                await self._sleeper(delay)

    def _stream(self, instrument: Instrument, stream: str) -> str:
        symbol = instrument.symbol.replace("/", "").lower()
        route = (
            self._config.public_ws_base_url
            if stream == "bookTicker"
            else self._config.market_ws_base_url
        )
        return f"{route}{symbol}@{stream}"

    def _claim(
        self, kind: str, instrument_id: UUID, timeframe: str | None
    ) -> tuple[str, UUID, str | None]:
        key = (kind, instrument_id, timeframe)
        if key in self._active_subscriptions:
            raise ValueError(f"duplicate active Binance USDⓈ-M subscription: {key!r}")
        self._active_subscriptions.add(key)
        return key

    @staticmethod
    def _validate_instrument(instrument: Instrument) -> None:
        if instrument.provider != BINANCE_USDM_PROVIDER:
            raise ValueError("BinanceUsdMStreamingProvider requires a binance_usdm instrument")

    async def _publish_error(self, instrument_id: UUID, error: str) -> None:
        if self._error_publisher is None:
            return
        result = self._error_publisher(DataFeedError(instrument_id=instrument_id, error=error))
        if result is not None:
            await result


class StreamRetryExhaustedError(RuntimeError):
    """Raised after bounded transient reconnect attempts are exhausted."""

    def __init__(self, detail: str, data_feed_error: DataFeedError | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.data_feed_error = data_feed_error


def _timeframe_interval(timeframe: str) -> timedelta:
    if len(timeframe) < 2 or timeframe[-1] not in "mhdw" or not timeframe[:-1].isdigit():
        raise ValueError(f"unsupported Binance timeframe: {timeframe!r}")
    amount = int(timeframe[:-1])
    if amount <= 0:
        raise ValueError(f"unsupported Binance timeframe: {timeframe!r}")
    unit = timeframe[-1]
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return timedelta(weeks=amount)


def _default_connection_factory(
    url: str,
    *,
    ping_interval: float,
    ping_timeout: float,
    close_timeout: float,
) -> AbstractAsyncContextManager[_WebSocket]:
    return cast(
        "AbstractAsyncContextManager[_WebSocket]",
        connect(
            url,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            close_timeout=close_timeout,
        ),
    )
