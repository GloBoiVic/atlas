from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.core.events import DataFeedError, MarketContextUpdated
from backend.data.binance_usdm import (
    BINANCE_USDM_FSTREAM_BASE_URL,
    BINANCE_USDM_PROVIDER,
    BinanceUsdMStreamingConfig,
    parse_binance_usdm_agg_trade,
    parse_binance_usdm_book_ticker,
    parse_binance_usdm_kline,
    parse_binance_usdm_mark_price,
)
from backend.data.models import Instrument, MarketContext


@pytest.fixture
def futures_instrument() -> Instrument:
    return Instrument(
        id=uuid4(),
        symbol="BTCUSDT",
        provider=BINANCE_USDM_PROVIDER,
        asset_type="crypto_futures",
        base_currency="BTC",
        quote_currency="USDT",
    )


def test_streaming_config_is_public_and_typed() -> None:
    config = BinanceUsdMStreamingConfig()

    assert config.base_url == BINANCE_USDM_FSTREAM_BASE_URL
    assert config.ping_interval_seconds == 20.0


@pytest.mark.parametrize(
    "field", ["ping_interval_seconds", "ping_timeout_seconds", "close_timeout_seconds"]
)
def test_streaming_config_rejects_non_positive_timeouts(field: str) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        BinanceUsdMStreamingConfig(**{field: 0})  # type: ignore[arg-type]


def test_streaming_config_rejects_non_public_endpoint() -> None:
    with pytest.raises(ValueError, match="public fstream endpoint"):
        BinanceUsdMStreamingConfig(base_url="wss://example.test/ws")


def test_kline_parser_normalizes_decimal_and_utc(futures_instrument: Instrument) -> None:
    candle = parse_binance_usdm_kline(
        {
            "e": "kline",
            "k": {
                "t": 1_754_064_000_123,
                "T": 1_754_064_059_999,
                "o": "100.0100",
                "h": "101.0200",
                "l": "99.9900",
                "c": "100.5000",
                "v": "2.3000",
                "q": "231.1500",
                "n": 17,
                "V": "1.2000",
                "Q": "120.6000",
                "x": True,
            },
        },
        futures_instrument,
        "1m",
    )

    assert candle.provider == BINANCE_USDM_PROVIDER
    assert candle.open == Decimal("100.0100")
    assert candle.base_volume == Decimal("2.3000")
    assert candle.open_time == datetime.fromtimestamp(1_754_064_000.123, tz=UTC)
    assert candle.close_time is not None and candle.close_time.tzinfo is UTC
    assert candle.is_complete is True


def test_kline_parser_preserves_incomplete_completion_flag(futures_instrument: Instrument) -> None:
    payload = {
        "k": {
            "t": 1_000,
            "T": 2_000,
            "o": "1",
            "h": "2",
            "l": "1",
            "c": "1.5",
            "v": "0",
            "q": "0",
            "n": 0,
            "V": "0",
            "Q": "0",
            "x": False,
        }
    }

    assert parse_binance_usdm_kline(payload, futures_instrument, "1m").is_complete is False


def test_aggregate_trade_parser_maps_price_quantity_and_time(
    futures_instrument: Instrument,
) -> None:
    tick = parse_binance_usdm_agg_trade(
        {"e": "aggTrade", "a": 42, "p": "100.2500", "q": "0.125", "T": 1_000},
        futures_instrument,
    )

    assert tick.price == Decimal("100.2500")
    assert tick.base_volume == Decimal("0.125")
    assert tick.timestamp == datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)


def test_book_ticker_parser_rejects_crossed_prices(futures_instrument: Instrument) -> None:
    with pytest.raises(ValueError, match="crossed"):
        parse_binance_usdm_book_ticker(
            {"e": "bookTicker", "E": 1_000, "b": "101", "a": "100"},
            futures_instrument,
        )


def test_book_ticker_parser_normalizes_values(futures_instrument: Instrument) -> None:
    ticker = parse_binance_usdm_book_ticker(
        {"e": "bookTicker", "E": 1_000, "b": "100.00", "a": "100.10"},
        futures_instrument,
    )

    assert ticker.bid == Decimal("100.00")
    assert ticker.ask == Decimal("100.10")
    assert ticker.timestamp.tzinfo is UTC


def test_mark_price_parser_maps_non_executable_context(futures_instrument: Instrument) -> None:
    update = parse_binance_usdm_mark_price(
        {
            "e": "markPriceUpdate",
            "E": 1_754_064_000_123,
            "p": "100.125",
            "i": "100.000",
            "r": "-0.00010000",
            "T": 1_754_067_600_000,
        },
        futures_instrument,
    )

    assert update.mark_price == Decimal("100.125")
    assert update.index_price == Decimal("100.000")
    assert update.funding_rate == Decimal("-0.00010000")
    assert update.next_funding_time.tzinfo is UTC


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (parse_binance_usdm_agg_trade, {"p": "NaN", "q": "1", "T": 1}),
        (parse_binance_usdm_book_ticker, {"b": "0", "a": "1", "E": 1}),
        (
            parse_binance_usdm_mark_price,
            {"p": "1", "i": "Infinity", "r": "0", "T": 1, "E": 1},
        ),
    ],
)
def test_parsers_reject_invalid_numeric_values(
    parser: object, payload: dict[str, object], futures_instrument: Instrument
) -> None:
    with pytest.raises(ValueError):
        parser(payload, futures_instrument)  # type: ignore[operator]


def test_parsers_reject_spot_instrument(futures_instrument: Instrument) -> None:
    spot = Instrument(uuid4(), "BTCUSDT", "binance", "crypto")

    with pytest.raises(ValueError, match="binance_usdm"):
        parse_binance_usdm_agg_trade({"p": "1", "q": "1", "T": 1}, spot)


def test_data_feed_error_payload_is_keyword_only() -> None:
    instrument_id = uuid4()
    event = DataFeedError(instrument_id=instrument_id, error="stream ended")

    assert event.instrument_id == instrument_id
    assert event.error == "stream ended"
    with pytest.raises(TypeError):
        DataFeedError(instrument_id, "stream ended")  # type: ignore[arg-type,call-arg]


def test_market_context_contract_validates_and_event_wraps_it(
    futures_instrument: Instrument,
) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    context = MarketContext(
        instrument_id=futures_instrument.id,
        provider=BINANCE_USDM_PROVIDER,
        bid=Decimal("100"),
        ask=Decimal("101"),
        mark_price=Decimal("100.5"),
        index_price=Decimal("100.4"),
        funding_rate=Decimal("0.0001"),
        next_funding_time=timestamp + timedelta(hours=8),
        as_of=timestamp,
        bid_at=timestamp,
        ask_at=timestamp,
        mark_at=timestamp,
        index_at=timestamp,
        funding_at=timestamp,
    )

    assert MarketContextUpdated(context=context).context is context


@pytest.mark.parametrize(
    "changes",
    [{"bid": Decimal("0")}, {"ask": Decimal("99")}, {"as_of": datetime(2026, 1, 1)}],
)
def test_market_context_rejects_invalid_snapshot(
    futures_instrument: Instrument, changes: dict[str, object]
) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    values: dict[str, object] = {
        "instrument_id": futures_instrument.id,
        "provider": BINANCE_USDM_PROVIDER,
        "bid": Decimal("100"),
        "ask": Decimal("101"),
        "mark_price": Decimal("100.5"),
        "index_price": Decimal("100.4"),
        "funding_rate": Decimal("0.0001"),
        "next_funding_time": timestamp + timedelta(hours=8),
        "as_of": timestamp,
        "bid_at": timestamp,
        "ask_at": timestamp,
        "mark_at": timestamp,
        "index_at": timestamp,
        "funding_at": timestamp,
    }
    values.update(changes)

    with pytest.raises(ValueError):
        MarketContext(**values)  # type: ignore[arg-type]
