"""Binance Spot historical market-data provider backed by async ccxt."""

import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

import ccxt.async_support as ccxt  # type: ignore[import-untyped]

from backend.data.interfaces import HistoricalDataProvider
from backend.data.models import Candle, Instrument

_MAX_PAGE_SIZE = 1000
_TIMEFRAME = re.compile(r"^(?P<count>[1-9][0-9]*)(?P<unit>[mhdwM])$")


class _AsyncExchange(Protocol):
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int | None = None, limit: int | None = None
    ) -> Sequence[Sequence[object]]: ...

    async def close(self) -> None: ...


type ExchangeFactory = Callable[[], _AsyncExchange]


class BinanceHistoricalProvider(HistoricalDataProvider):
    """Fetch and normalize bounded Binance Spot OHLCV history.

    The provider deliberately consumes only ccxt's six-value OHLCV contract.  Binance
    kline enrichment fields are not available through ``fetch_ohlcv`` and remain null.
    """

    def __init__(
        self,
        exchange: _AsyncExchange | None = None,
        exchange_factory: ExchangeFactory | None = None,
    ) -> None:
        if exchange is not None and exchange_factory is not None:
            raise ValueError("provide exchange or exchange_factory, not both")
        self._exchange = exchange
        self._exchange_factory = exchange_factory or _create_binance

    async def get_historical_candles(
        self,
        instrument: Instrument,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch complete Spot candles in the inclusive UTC range.

        Args:
            instrument: Resolved Binance instrument with base and quote currencies.
            timeframe: ccxt timeframe such as ``1m`` or ``1h``.
            start: Inclusive, timezone-aware range start.
            end: Inclusive, timezone-aware range end.

        Returns:
            Sorted, duplicate-free Decimal-normalized candles.

        Raises:
            ValueError: If the request, symbol, or exchange response is invalid.
            asyncio.CancelledError: If the caller cancels the fetch.
        """
        start_utc, end_utc, interval = _validate_request(instrument, timeframe, start, end)
        symbol = _ccxt_symbol(instrument)
        exchange = self._exchange or self._exchange_factory()
        candles: dict[datetime, Candle] = {}
        since = _milliseconds(start_utc)

        try:
            while since <= _milliseconds(end_utc):
                rows = await exchange.fetch_ohlcv(symbol, timeframe, since, _MAX_PAGE_SIZE)
                if not rows:
                    break
                page_last_timestamp: int | None = None
                for row in rows:
                    candle, timestamp_ms = _parse_row(row, instrument, timeframe, interval)
                    if page_last_timestamp is not None and timestamp_ms < page_last_timestamp:
                        raise ValueError("Binance returned OHLCV rows out of order")
                    page_last_timestamp = timestamp_ms
                    if start_utc <= candle.open_time <= end_utc:
                        previous = candles.get(candle.open_time)
                        if previous is not None and previous != candle:
                            raise ValueError(
                                "conflicting duplicate Binance candle at "
                                f"{candle.open_time.isoformat()}"
                            )
                        candles[candle.open_time] = candle
                if page_last_timestamp is None or page_last_timestamp < since:
                    raise ValueError("Binance returned a page with no forward timestamp progress")
                next_since = page_last_timestamp + _milliseconds(interval)
                if next_since <= since:
                    raise ValueError("Binance pagination timestamp overflow")
                since = int(next_since)
                if len(rows) < _MAX_PAGE_SIZE:
                    break
        finally:
            await exchange.close()

        return [candles[open_time] for open_time in sorted(candles)]


def _create_binance() -> _AsyncExchange:
    return cast("_AsyncExchange", ccxt.binance({"options": {"defaultType": "spot"}}))


def _milliseconds(value: datetime | timedelta) -> int:
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return value.days * 86_400_000 + value.seconds * 1000 + value.microseconds // 1000


def _validate_request(
    instrument: Instrument, timeframe: str, start: datetime, end: datetime
) -> tuple[datetime, datetime, timedelta]:
    if instrument.provider != "binance":
        raise ValueError("BinanceHistoricalProvider requires an instrument with provider='binance'")
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("historical range timestamps must be timezone-aware")
    start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)
    if start_utc > end_utc:
        raise ValueError("historical range start must not be after end")
    match = _TIMEFRAME.fullmatch(timeframe)
    if match is None:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    count, unit = int(match["count"]), match["unit"]
    seconds = count * {"m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000}[unit]
    return start_utc, end_utc, timedelta(seconds=seconds)


def _ccxt_symbol(instrument: Instrument) -> str:
    if not instrument.base_currency or not instrument.quote_currency:
        raise ValueError("Binance instrument must define base_currency and quote_currency")
    normalized_base = instrument.base_currency.upper()
    normalized_quote = instrument.quote_currency.upper()
    expected_symbol = f"{normalized_base}{normalized_quote}"
    if instrument.symbol.upper().replace("/", "") != expected_symbol:
        raise ValueError("Binance instrument symbol does not match its base and quote currencies")
    return f"{normalized_base}/{normalized_quote}"


def _parse_row(
    row: Sequence[object], instrument: Instrument, timeframe: str, interval: timedelta
) -> tuple[Candle, int]:
    if len(row) != 6:
        raise ValueError("Binance OHLCV row must contain exactly six values")
    timestamp_ms = _timestamp_ms(row[0])
    open_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    values = [
        _decimal(value, name)
        for value, name in zip(
            row[1:],
            ("open", "high", "low", "close", "base_volume"),
            strict=True,
        )
    ]
    open_price, high, low, close, base_volume = values
    if min(open_price, high, low, close) <= 0:
        raise ValueError("Binance candle prices must be positive")
    if high < max(open_price, close) or low > min(open_price, close):
        raise ValueError("Binance candle OHLC bounds are invalid")
    if base_volume < 0:
        raise ValueError("Binance base volume cannot be negative")
    candle = Candle(
        instrument_id=instrument.id,
        provider="binance",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + interval,
        price_basis="trade",
        open=open_price,
        high=high,
        low=low,
        close=close,
        base_volume=base_volume,
        is_complete=True,
    )
    return candle, timestamp_ms


def _timestamp_ms(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Binance candle timestamp must be an integer millisecond value")
    try:
        timestamp = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Binance candle timestamp is invalid") from None
    if not timestamp.is_finite() or timestamp != timestamp.to_integral_value() or timestamp < 0:
        raise ValueError("Binance candle timestamp is invalid")
    return int(timestamp)


def _decimal(value: object, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"Binance candle {name} is missing")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Binance candle {name} is invalid") from None
    if not decimal.is_finite():
        raise ValueError(f"Binance candle {name} must be finite")
    return decimal
