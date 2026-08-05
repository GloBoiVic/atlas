from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from backend.core.clock import Clock
from backend.core.events import MarketContextUpdated
from backend.data.binance_usdm import BookTicker, MarkPriceUpdate
from backend.data.market_context import MarketContextAggregator


class FixedClock(Clock):
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


def _book(
    instrument_id: UUID,
    timestamp: datetime,
    bid: str = "100",
    ask: str = "101",
) -> BookTicker:
    return BookTicker(instrument_id, timestamp, Decimal(bid), Decimal(ask))


def _mark(instrument_id: UUID, timestamp: datetime, mark: str = "100.5") -> MarkPriceUpdate:
    return MarkPriceUpdate(
        instrument_id,
        timestamp,
        Decimal(mark),
        Decimal("100.25"),
        Decimal("-0.0001"),
        timestamp + timedelta(hours=8),
    )


def test_partial_updates_do_not_publish_until_both_components_are_present() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    instrument_id = uuid4()
    aggregator = MarketContextAggregator("test-provider", clock=FixedClock(timestamp))

    assert aggregator.update_book_ticker(_book(instrument_id, timestamp)) is None
    event = aggregator.update_mark_price(_mark(instrument_id, timestamp))

    assert isinstance(event, MarketContextUpdated)


def test_publication_uses_one_clock_read_and_carries_component_timestamps() -> None:
    timestamp = datetime(2026, 1, 1, 12, tzinfo=UTC)
    instrument_id = uuid4()
    book_time = timestamp - timedelta(seconds=1)
    mark_time = timestamp - timedelta(seconds=2)
    aggregator = MarketContextAggregator("provider", clock=FixedClock(timestamp))

    aggregator.update_book_ticker(_book(instrument_id, book_time))
    event = aggregator.update_mark_price(_mark(instrument_id, mark_time))

    assert event is not None
    context = event.context
    assert context.as_of == timestamp
    assert event.occurred_at == timestamp
    assert context.bid_at == context.ask_at == book_time
    assert context.mark_at == context.index_at == context.funding_at == mark_time
    assert context.bid == Decimal("100")
    assert context.funding_rate == Decimal("-0.0001")


def test_missing_or_stale_components_suppress_publication_and_recover() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    instrument_id = uuid4()
    clock = FixedClock(timestamp)
    aggregator = MarketContextAggregator(
        "provider", clock=clock, book_ticker_max_age=timedelta(seconds=2)
    )
    aggregator.update_mark_price(_mark(instrument_id, timestamp - timedelta(seconds=1)))
    assert (
        aggregator.update_book_ticker(_book(instrument_id, timestamp - timedelta(seconds=3)))
        is None
    )

    clock.current = timestamp + timedelta(seconds=1)
    event = aggregator.update_book_ticker(_book(instrument_id, timestamp + timedelta(seconds=1)))
    assert event is not None


def test_crossed_or_non_positive_components_are_suppressed_without_corrupting_state() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    instrument_id = uuid4()
    aggregator = MarketContextAggregator("provider", clock=FixedClock(timestamp))

    assert aggregator.update_book_ticker(_book(instrument_id, timestamp, "101", "100")) is None
    assert aggregator.update_mark_price(_mark(instrument_id, timestamp, "0")) is None
    assert aggregator.latest_context is None


def test_out_of_order_updates_do_not_replace_newer_components() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    instrument_id = uuid4()
    aggregator = MarketContextAggregator("provider", clock=FixedClock(timestamp))
    newer = timestamp - timedelta(seconds=1)
    older = timestamp - timedelta(seconds=2)

    aggregator.update_book_ticker(_book(instrument_id, newer, "100", "101"))
    aggregator.update_book_ticker(_book(instrument_id, older, "90", "91"))
    event = aggregator.update_mark_price(_mark(instrument_id, newer))

    assert event is not None
    assert event.context.bid == Decimal("100")


def test_different_instruments_cannot_form_a_snapshot() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    aggregator = MarketContextAggregator("provider", clock=FixedClock(timestamp))
    aggregator.update_book_ticker(_book(uuid4(), timestamp))

    assert aggregator.update_mark_price(_mark(uuid4(), timestamp)) is None


def test_invalid_timezone_is_rejected_by_suppression() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    instrument_id = uuid4()
    aggregator = MarketContextAggregator("provider", clock=FixedClock(timestamp))

    assert aggregator.update_book_ticker(_book(instrument_id, datetime(2026, 1, 1))) is None
