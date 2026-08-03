from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.data.csv_provider import CSVDataProvider
from backend.data.loader import HistoricalDataLoader, build_dataset_identity
from backend.data.models import Candle, Instrument
from backend.persistence.repositories.memory import (
    InMemoryCandleRepository,
    InMemoryInstrumentRepository,
)


def _instrument() -> Instrument:
    return Instrument(
        id=uuid4(),
        symbol="BTCUSDT",
        provider="csv",
        asset_type="crypto",
    )


def _write_csv(directory: Path, body: str) -> None:
    (directory / "BTCUSDT.csv").write_text(body, encoding="utf-8")


@pytest.mark.asyncio
async def test_csv_provider_normalizes_sorts_deduplicates_and_filters(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        "timestamp,open,high,low,close,base_volume\n"
        "2026-01-01T02:00:00+02:00,100,101,99,100.5,1\n"
        "2025-12-31T23:00:00Z,99,100,98,99.5,1\n"
        "2026-01-01T00:00:00Z,100,101,99,100.5,1\n"
        "2026-01-01T00:00:00Z,100,101,99,100.5,1\n",
    )
    candles = await CSVDataProvider(tmp_path).get_historical_candles(
        _instrument(), "1h", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 1, tzinfo=UTC)
    )
    assert [c.open_time.hour for c in candles] == [0]
    assert candles[0].open == Decimal("100")
    assert candles[0].provider == "csv"
    assert candles[0].price_basis == "trade"
    assert candles[0].is_complete is True


@pytest.mark.asyncio
async def test_csv_provider_rejects_malformed_rows_and_naive_timestamps(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        "timestamp,open,high,low,close,base_volume\n"
        "2026-01-01T00:00:00,100,101,99,100,1\n",
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        await CSVDataProvider(tmp_path).get_historical_candles(
            _instrument(), "1m", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
        )


@pytest.mark.asyncio
async def test_csv_provider_accepts_utf8_bom_exports(tmp_path: Path) -> None:
    (tmp_path / "BTCUSDT.csv").write_bytes(
        b"\xef\xbb\xbf"
        b"timestamp,open,high,low,close,base_volume\n"
        b"2026-01-01T00:00:00Z,100,101,99,100,1\n"
    )
    candles = await CSVDataProvider(tmp_path).get_historical_candles(
        _instrument(), "1m", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
    )
    assert len(candles) == 1


@pytest.mark.asyncio
async def test_csv_provider_rejects_conflicting_duplicates_and_ohlc_bounds(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        "timestamp,open,high,low,close,base_volume\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1\n"
        "2026-01-01T00:00:00Z,100,102,99,100,1\n",
    )
    with pytest.raises(ValueError, match="conflicting duplicate"):
        await CSVDataProvider(tmp_path).get_historical_candles(
            _instrument(), "1m", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
        )


@pytest.mark.asyncio
async def test_loader_fingerprint_is_deterministic_and_repeat_import_is_idempotent(
    tmp_path: Path,
) -> None:
    _write_csv(
        tmp_path,
        "timestamp,open,high,low,close,base_volume\n"
        "2026-01-01T00:00:00Z,100.00,101.00,99.00,100.50,1.00\n",
    )
    instrument_repo = InMemoryInstrumentRepository()
    candle_repo = InMemoryCandleRepository()
    loader = HistoricalDataLoader(CSVDataProvider(tmp_path), instrument_repo, candle_repo)
    first = await loader.load_historical_data(
        symbol="BTCUSDT",
        provider_name="csv",
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
    )
    second = await loader.load_historical_data(
        symbol="BTCUSDT",
        provider_name="csv",
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert first.dataset.id == second.dataset.id
    assert first.dataset.candle_count == 1
    assert first.inserted_count == 1
    assert second.inserted_count == 0


@pytest.mark.asyncio
async def test_csv_load_resolve_preserves_existing_instrument_metadata(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        "timestamp,open,high,low,close,base_volume\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1\n",
    )
    instrument_repo = InMemoryInstrumentRepository()
    existing = await instrument_repo.upsert(
        symbol="BTCUSDT",
        provider="csv",
        asset_type="crypto",
        base_currency="BTC",
        quote_currency="USDT",
        price_precision=2,
        quantity_precision=4,
        constraints={"tick_size": "0.01"},
    )
    loader = HistoricalDataLoader(
        CSVDataProvider(tmp_path), instrument_repo, InMemoryCandleRepository()
    )
    await loader.load_historical_data(
        symbol="BTCUSDT",
        provider_name="csv",
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
    )
    resolved = await instrument_repo.resolve(symbol="BTCUSDT", provider="csv")
    assert resolved.id == existing.id
    assert resolved.price_precision == 2
    assert resolved.quantity_precision == 4
    assert resolved.base_currency == "BTC"
    assert resolved.constraints == {"tick_size": "0.01"}


def test_fingerprint_canonicalizes_decimal_and_timestamp_values() -> None:
    instrument_id = uuid4()
    candle_a = _make_identity_candle(instrument_id, "100.0", datetime(2026, 1, 1, tzinfo=UTC))
    candle_b = _make_identity_candle(
        instrument_id,
        "100.00",
        datetime(2025, 12, 31, 19, 0, tzinfo=timezone(timedelta(hours=-5))),
    )
    first = build_dataset_identity(
        instrument_id=instrument_id,
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        source="csv",
        candles=[candle_a],
    )
    second = build_dataset_identity(
        instrument_id=instrument_id,
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        source="csv",
        candles=[candle_b],
    )
    assert first.id == second.id


def _make_identity_candle(instrument_id: UUID, price: str, timestamp: datetime) -> Candle:
    value = Decimal(price)
    return Candle(
        instrument_id=instrument_id,
        provider="csv",
        timeframe="1h",
        open_time=timestamp,
        open=value,
        high=value,
        low=value,
        close=value,
        base_volume=Decimal("1"),
    )


# ---------------------------------------------------------------------------
# CSV contract edge cases (focused additions for the accepted slice contract)
# ---------------------------------------------------------------------------


_HEADER = "timestamp,open,high,low,close,base_volume\n"


async def _reject(tmp_path: Path, body: str, match: str) -> None:
    _write_csv(tmp_path, body)
    with pytest.raises(ValueError, match=match):
        await CSVDataProvider(tmp_path).get_historical_candles(
            _instrument(),
            "1m",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_csv_provider_rejects_ohlc_bounds_violations(tmp_path: Path) -> None:
    # high below open or close
    await _reject(
        tmp_path,
        _HEADER + "2026-01-01T00:00:00Z,100,99,99,100,1\n",
        "high is below open or close",
    )
    # low above open or close
    await _reject(
        tmp_path,
        _HEADER + "2026-01-01T00:00:00Z,100,101,101,100,1\n",
        "low is above open or close",
    )
    # non-positive price (zero low)
    await _reject(
        tmp_path,
        _HEADER + "2026-01-01T00:00:00Z,100,101,0,100,1\n",
        "prices must be positive",
    )


@pytest.mark.asyncio
async def test_csv_provider_rejects_negative_volume_and_trade_count(
    tmp_path: Path,
) -> None:
    await _reject(
        tmp_path,
        _HEADER + "2026-01-01T00:00:00Z,100,101,99,100,-1\n",
        "volume cannot be negative",
    )
    await _reject(
        tmp_path,
        "timestamp,open,high,low,close,base_volume,quote_volume\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1,-5\n",
        "volume cannot be negative",
    )
    await _reject(
        tmp_path,
        "timestamp,open,high,low,close,base_volume,trade_count\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1,-3\n",
        "trade_count cannot be negative",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
async def test_csv_provider_rejects_non_finite_decimal_values(
    tmp_path: Path, value: str
) -> None:
    await _reject(
        tmp_path,
        _HEADER + f"2026-01-01T00:00:00Z,{value},101,99,100,1\n",
        "open must be finite",
    )


@pytest.mark.asyncio
async def test_csv_provider_rejects_close_time_before_open_time(tmp_path: Path) -> None:
    await _reject(
        tmp_path,
        "timestamp,open,high,low,close,base_volume,close_time\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1,2025-12-31T23:00:00Z\n",
        "close_time precedes timestamp",
    )


@pytest.mark.asyncio
async def test_csv_provider_rejects_missing_and_unsupported_columns(tmp_path: Path) -> None:
    await _reject(
        tmp_path,
        "timestamp,open,high,close,base_volume\n"
        "2026-01-01T00:00:00Z,100,101,100,1\n",
        "CSV missing required columns",
    )
    await _reject(
        tmp_path,
        "timestamp,open,high,low,close,base_volume,foo\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1,1\n",
        "CSV contains unsupported columns",
    )


@pytest.mark.asyncio
async def test_csv_provider_rejects_tick_volume_as_intentionally_excluded(
    tmp_path: Path,
) -> None:
    """CSV excludes OANDA tick-count volume from its trade-volume contract."""
    await _reject(
        tmp_path,
        "timestamp,open,high,low,close,base_volume,tick_volume\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1,10\n",
        "CSV contains unsupported columns",
    )


@pytest.mark.asyncio
async def test_csv_provider_range_is_inclusive_on_both_ends(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        _HEADER
        + "2025-12-31T23:00:00Z,99,100,98,99,1\n"
        + "2026-01-01T00:00:00Z,100,101,99,100,1\n"
        + "2026-01-01T02:00:00Z,102,103,101,102,1\n"
        + "2026-01-01T03:00:00Z,103,104,102,103,1\n",
    )
    candles = await CSVDataProvider(tmp_path).get_historical_candles(
        _instrument(),
        "1m",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 2, tzinfo=UTC),
    )
    assert [c.open_time.hour for c in candles] == [0, 2]


@pytest.mark.asyncio
async def test_csv_provider_rejects_naive_range_and_requires_csv_instrument(
    tmp_path: Path,
) -> None:
    _write_csv(tmp_path, _HEADER + "2026-01-01T00:00:00Z,100,101,99,100,1\n")
    with pytest.raises(ValueError, match="timezone-aware"):
        await CSVDataProvider(tmp_path).get_historical_candles(
            _instrument(), "1m", datetime(2026, 1, 1), datetime(2026, 1, 2)
        )

    from backend.data.models import Instrument as Inst

    non_csv = Inst(
        id=uuid4(),
        symbol="BTCUSDT",
        provider="binance",
        asset_type="crypto",
    )
    with pytest.raises(ValueError, match="provider='csv'"):
        await CSVDataProvider(tmp_path).get_historical_candles(
            non_csv,
            "1m",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_csv_provider_rejects_symbol_path_escaping(tmp_path: Path) -> None:
    from backend.data.models import Instrument as Inst

    evil = Inst(
        id=uuid4(),
        symbol="../../etc/passwd",
        provider="csv",
        asset_type="crypto",
    )
    with pytest.raises(ValueError, match="simple CSV filename stem"):
        await CSVDataProvider(tmp_path).get_historical_candles(
            evil, "1m", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
        )


@pytest.mark.asyncio
async def test_csv_provider_parses_optional_detail_columns(tmp_path: Path) -> None:
    _write_csv(
        tmp_path,
        "timestamp,open,high,low,close,base_volume,close_time,quote_volume,"
        "trade_count,taker_buy_base_volume,taker_buy_quote_volume\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1,"
        "2026-01-01T01:00:00Z,5000,25,0.6,3000\n",
    )
    candles = await CSVDataProvider(tmp_path).get_historical_candles(
        _instrument(),
        "1m",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )
    candle = candles[0]
    assert candle.close_time == datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    assert candle.quote_volume == Decimal("5000")
    assert candle.trade_count == 25
    assert candle.taker_buy_base_volume == Decimal("0.6")
    assert candle.taker_buy_quote_volume == Decimal("3000")
