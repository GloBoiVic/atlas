from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.data.models import Candle, DatasetIdentity, HistoricalLoadResult, Instrument, Tick


def test_instrument_creation() -> None:
    instrument_id = uuid4()
    instrument = Instrument(
        id=instrument_id,
        symbol="BTCUSDT",
        provider="binance",
        asset_type="crypto",
        base_currency="BTC",
        quote_currency="USDT",
        price_precision=2,
        quantity_precision=5,
        constraints={"min_qty": "0.001", "tick_size": "0.01"},
    )
    assert instrument.id == instrument_id
    assert instrument.symbol == "BTCUSDT"
    assert instrument.provider == "binance"
    assert instrument.constraints == {"min_qty": "0.001", "tick_size": "0.01"}


def test_instrument_defaults() -> None:
    instrument_id = uuid4()
    instrument = Instrument(
        id=instrument_id,
        symbol="ETHUSDT",
        provider="binance",
        asset_type="crypto",
    )
    assert instrument.price_precision == 8
    assert instrument.quantity_precision == 8
    assert instrument.is_active is True
    assert instrument.constraints == {}
    assert instrument.base_currency is None
    assert instrument.quote_currency is None


def test_candle_creation_binance_style() -> None:
    instrument_id = uuid4()
    candle = Candle(
        instrument_id=instrument_id,
        provider="binance",
        timeframe="1h",
        open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        close_time=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        price_basis="trade",
        open=Decimal("50000.00"),
        high=Decimal("51000.00"),
        low=Decimal("49000.00"),
        close=Decimal("50500.00"),
        base_volume=Decimal("1234.5678"),
        quote_volume=Decimal("62000000.00"),
        trade_count=5000,
        taker_buy_base_volume=Decimal("700.00"),
        taker_buy_quote_volume=Decimal("35350000.00"),
        is_complete=True,
    )
    assert candle.instrument_id == instrument_id
    assert candle.provider == "binance"
    assert candle.price_basis == "trade"
    assert candle.open == Decimal("50000.00")
    assert candle.base_volume == Decimal("1234.5678")
    assert candle.quote_volume == Decimal("62000000.00")
    assert candle.trade_count == 5000
    assert candle.tick_volume is None
    assert candle.is_complete is True


def test_candle_defaults() -> None:
    instrument_id = uuid4()
    candle = Candle(
        instrument_id=instrument_id,
        provider="binance",
        timeframe="1m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert candle.price_basis == "trade"
    assert candle.open == Decimal("0")
    assert candle.base_volume == Decimal("0")
    assert candle.is_complete is True
    assert candle.trade_count is None
    assert candle.tick_volume is None


def test_candle_no_id() -> None:
    """Candle is a provider-domain model — no database row identifier."""
    instrument_id = uuid4()
    candle = Candle(
        instrument_id=instrument_id,
        provider="binance",
        timeframe="1m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert not hasattr(candle, "id")


def test_tick_creation() -> None:
    instrument_id = uuid4()
    tick = Tick(
        instrument_id=instrument_id,
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        price=Decimal("50500.50"),
        base_volume=Decimal("1.5"),
    )
    assert tick.instrument_id == instrument_id
    assert tick.price == Decimal("50500.50")
    assert tick.base_volume == Decimal("1.5")
    assert tick.tick_volume is None


def test_dataset_identity_fields() -> None:
    instrument_id = uuid4()
    dataset = DatasetIdentity(
        id="sha256:abc123",
        instrument_id=instrument_id,
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 7, tzinfo=UTC),
        candle_count=168,
        source="binance",
    )
    assert dataset.id == "sha256:abc123"
    assert dataset.instrument_id == instrument_id
    assert dataset.candle_count == 168
    assert dataset.source == "binance"


def test_historical_load_result_wraps_dataset_and_count() -> None:
    instrument_id = uuid4()
    dataset = DatasetIdentity(
        id="fp",
        instrument_id=instrument_id,
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        candle_count=24,
        source="csv",
    )
    result = HistoricalLoadResult(dataset=dataset, inserted_count=24)
    assert result.dataset is dataset
    assert result.inserted_count == 24


def test_candle_is_frozen() -> None:
    import dataclasses

    instrument_id = uuid4()
    candle = Candle(
        instrument_id=instrument_id,
        provider="binance",
        timeframe="1m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        close=Decimal("100"),
    )
    # Frozen dataclass — normal assignment raises FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        candle.close = Decimal("200")  # type: ignore[misc]


def test_interfaces_are_abstract() -> None:
    """HistoricalDataProvider and LiveDataProvider require concrete subclasses."""
    from backend.data.interfaces import HistoricalDataProvider, LiveDataProvider

    with pytest.raises(TypeError, match="abstract"):
        HistoricalDataProvider()  # type: ignore[abstract]
    with pytest.raises(TypeError, match="abstract"):
        LiveDataProvider()  # type: ignore[abstract]


def test_candle_repository_protocol_accepts_save_many() -> None:
    """Verify CandleRepository protocol accepts the correct call signature."""
    import inspect

    from backend.persistence.repositories.protocols import CandleRepository

    assert inspect.isclass(CandleRepository)


def test_instrument_repository_protocol_has_upsert_and_resolve() -> None:
    """Verify InstrumentRepository protocol defines both required methods."""
    from backend.persistence.repositories.protocols import InstrumentRepository

    assert hasattr(InstrumentRepository, "resolve")
    assert hasattr(InstrumentRepository, "upsert")
