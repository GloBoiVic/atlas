"""Async Binance USDⓈ-M public-stream subscriptions."""

import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

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


type ConnectionFactory = Callable[..., Any]
type Sleeper = Callable[[float], Awaitable[None]]
type CandleKey = tuple[UUID, str, str, datetime, str]


class BinanceUsdMStreamingProvider(LiveDataProvider):
    """Stream normalized public USDⓈ-M market data from Binance fstream."""

    def __init__(
        self,
        config: BinanceUsdMStreamingConfig | None = None,
        connection_factory: ConnectionFactory | None = None,
        sleeper: Sleeper | None = None,
        max_reconnect_attempts: int = 0,
    ) -> None:
        if max_reconnect_attempts < 0:
            raise ValueError("max_reconnect_attempts must not be negative")
        self._config = config or BinanceUsdMStreamingConfig()
        self._connection_factory = connection_factory or _default_connection_factory
        self._sleeper = sleeper or asyncio.sleep
        self._max_reconnect_attempts = max_reconnect_attempts
        self._active_subscriptions: set[tuple[str, UUID, str | None]] = set()
        self._emitted_candles: set[CandleKey] = set()

    async def subscribe_candles(
        self, instrument: Instrument, timeframe: str
    ) -> AsyncGenerator[Candle, None]:
        """Yield only completed, duplicate-free klines."""
        self._validate_instrument(instrument)
        if not timeframe:
            raise ValueError("timeframe must not be empty")
        key = self._claim("candle", instrument.id, timeframe)
        try:
            async for payload in self._messages(self._stream(instrument, f"kline_{timeframe}")):
                candle = parse_binance_usdm_kline(payload, instrument, timeframe)
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
                self._emitted_candles.add(candle_key)
                yield candle
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
            async for payload in self._messages(self._stream(instrument, stream)):
                yield parser(payload, instrument)
        finally:
            self._active_subscriptions.remove(key)

    async def _messages(self, stream: str) -> AsyncGenerator[Mapping[str, object], None]:
        reconnect_attempt = 0
        while True:
            try:
                async with self._connection_factory(
                    stream,
                    ping_interval=self._config.ping_interval_seconds,
                    ping_timeout=self._config.ping_timeout_seconds,
                    close_timeout=self._config.close_timeout_seconds,
                ) as websocket:
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
            except ConnectionClosed:
                if reconnect_attempt >= self._max_reconnect_attempts:
                    return
                reconnect_attempt += 1
                await self._sleeper(float(reconnect_attempt))

    def _stream(self, instrument: Instrument, stream: str) -> str:
        symbol = instrument.symbol.replace("/", "").lower()
        return f"{self._config.base_url}/{symbol}@{stream}"

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


def _default_connection_factory(
    url: str, **kwargs: object
) -> AbstractAsyncContextManager[_WebSocket]:
    return cast("AbstractAsyncContextManager[_WebSocket]", cast("Any", connect)(url, **kwargs))
