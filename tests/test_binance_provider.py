import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.core.errors import HistoricalDataTimeoutError
from backend.data.binance_provider import BinanceHistoricalProvider, BinanceTimeoutPolicy
from backend.data.models import Instrument


class MockExchange:
    def __init__(self, pages: list[list[list[object]]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, str, int | None, int | None]] = []
        self.closed = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.wait_on_fetch = False
        self.stall_after_calls: int | None = None

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int | None = None, limit: int | None = None
    ) -> list[list[object]]:
        self.calls.append((symbol, timeframe, since, limit))
        if self.wait_on_fetch or (
            self.stall_after_calls is not None and len(self.calls) > self.stall_after_calls
        ):
            self.started.set()
            await self.release.wait()
        return self.pages.pop(0) if self.pages else []

    async def close(self) -> None:
        self.closed = True


class AdvancingClock:
    def __init__(self, current_time: datetime) -> None:
        self.current_time = current_time
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.current_time if self.calls == 1 else self.current_time.replace(year=2025)


def _instrument(provider: str = "binance") -> Instrument:
    return Instrument(
        id=uuid4(),
        symbol="BTCUSDT",
        provider=provider,
        asset_type="crypto",
        base_currency="BTC",
        quote_currency="USDT",
    )


def _row(timestamp: int, price: str = "100") -> list[object]:
    return [timestamp, price, "101", "99", price, "2.50"]


@pytest.mark.asyncio
async def test_binance_provider_paginates_maps_symbol_and_normalizes_values() -> None:
    first_page = [_row(1_704_067_200_000 + index * 60_000) for index in range(1000)]
    second_timestamp = 1_704_067_200_000 + 1000 * 60_000
    exchange = MockExchange([first_page, [_row(second_timestamp, "100.10")]])

    candles = await BinanceHistoricalProvider(exchange=exchange).get_historical_candles(
        _instrument(),
        "1m",
        datetime.fromtimestamp(1_704_067_200, tz=UTC),
        datetime.fromtimestamp(1_704_067_200 + 1000 * 60, tz=UTC),
    )

    assert len(candles) == 1001
    assert exchange.calls[0] == ("BTC/USDT", "1m", 1_704_067_200_000, 1000)
    assert exchange.calls[1][2] == second_timestamp
    assert candles[0].open == Decimal("100")
    assert candles[-1].open == Decimal("100.10")
    assert candles[0].close_time == candles[0].open_time.replace(minute=1)
    assert candles[0].quote_volume is None
    assert exchange.closed is True


@pytest.mark.asyncio
async def test_binance_provider_collapses_identical_duplicates_and_sorts() -> None:
    timestamp = 1_704_067_200_000
    exchange = MockExchange([[_row(timestamp), _row(timestamp)]])
    candles = await BinanceHistoricalProvider(exchange=exchange).get_historical_candles(
        _instrument(), "1m", datetime.fromtimestamp(timestamp / 1000, tz=UTC),
        datetime.fromtimestamp(timestamp / 1000, tz=UTC),
    )
    assert len(candles) == 1


@pytest.mark.asyncio
async def test_binance_provider_rejects_provider_symbol_or_range_before_network() -> None:
    exchange = MockExchange([])
    with pytest.raises(ValueError, match="provider='binance'"):
        await BinanceHistoricalProvider(exchange=exchange).get_historical_candles(
            _instrument("csv"),
            "1m",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
    assert exchange.calls == []
    with pytest.raises(ValueError, match="start must not be after"):
        await BinanceHistoricalProvider(exchange=exchange).get_historical_candles(
            _instrument(), "1m", datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
        )
    assert exchange.calls == []


@pytest.mark.asyncio
async def test_binance_provider_closes_exchange_on_error_and_cancellation() -> None:
    error_exchange = MockExchange([[[_row(1_704_067_200_000)[0], "bad"]]])
    with pytest.raises(ValueError, match="exactly six"):
        await BinanceHistoricalProvider(exchange=error_exchange).get_historical_candles(
            _instrument(),
            "1m",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        )
    assert error_exchange.closed is True

    cancellation_exchange = MockExchange([[_row(1_704_067_200_000)]])
    cancellation_exchange.wait_on_fetch = True
    task = asyncio.create_task(
        BinanceHistoricalProvider(exchange=cancellation_exchange).get_historical_candles(
            _instrument(),
            "1m",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        )
    )
    await cancellation_exchange.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancellation_exchange.closed is True


@pytest.mark.asyncio
async def test_binance_provider_rejects_invalid_ohlcv_values() -> None:
    exchange = MockExchange([[_row(1_704_067_200_000, "NaN")]])
    with pytest.raises(ValueError, match="finite"):
        await BinanceHistoricalProvider(exchange=exchange).get_historical_candles(
            _instrument(),
            "1m",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        )
    assert exchange.closed is True


@pytest.mark.asyncio
async def test_binance_provider_times_out_a_stalled_page_without_partial_success() -> None:
    exchange = MockExchange([[_row(1_704_067_200_000)]])
    exchange.wait_on_fetch = True

    with pytest.raises(HistoricalDataTimeoutError, match="page request"):
        await BinanceHistoricalProvider(
            exchange=exchange,
            timeout_policy=BinanceTimeoutPolicy(page_timeout_seconds=0.01),
        ).get_historical_candles(
            _instrument(),
            "1m",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        )

    assert exchange.closed is True


@pytest.mark.asyncio
async def test_binance_provider_uses_clock_for_domain_deadline_without_network_wait() -> None:
    exchange = MockExchange([])
    clock = AdvancingClock(datetime(2024, 1, 1, tzinfo=UTC))

    with pytest.raises(HistoricalDataTimeoutError, match="overall timeout"):
        await BinanceHistoricalProvider(
            exchange=exchange,
            clock=clock,
            timeout_policy=BinanceTimeoutPolicy(overall_timeout_seconds=10.0),
        ).get_historical_candles(
            _instrument(),
            "1m",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        )

    assert exchange.calls == []
    assert exchange.closed is True


@pytest.mark.asyncio
async def test_binance_provider_times_out_total_pagination_after_successful_page() -> None:
    first_page = [_row(1_704_067_200_000 + index * 60_000) for index in range(1000)]
    exchange = MockExchange([first_page, []])
    exchange.stall_after_calls = 1

    with pytest.raises(HistoricalDataTimeoutError, match="overall timeout"):
        await BinanceHistoricalProvider(
            exchange=exchange,
            timeout_policy=BinanceTimeoutPolicy(
                page_timeout_seconds=1.0,
                overall_timeout_seconds=0.01,
            ),
        ).get_historical_candles(
            _instrument(),
            "1m",
            datetime.fromtimestamp(1_704_067_200, tz=UTC),
            datetime.fromtimestamp(1_704_067_200 + 1000 * 60, tz=UTC),
        )

    assert len(exchange.calls) == 1
    assert exchange.closed is True
