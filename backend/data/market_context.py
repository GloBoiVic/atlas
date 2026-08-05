"""Deterministic aggregation of live executable and reference-price context."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from backend.core.clock import Clock, LiveClock
from backend.core.events import MarketContextUpdated
from backend.data.binance_usdm import BookTicker, MarkPriceUpdate
from backend.data.models import MarketContext

ClockSource = Clock | Callable[[], datetime]


class MarketContextAggregator:
    """Combine independent book and mark streams into fresh immutable snapshots.

    A component update is retained only when it is valid and not older than the
    currently retained component.  Publication is suppressed until both components
    exist and are fresh at the same clock reading.  No task or timer is created;
    callers simply receive ``None`` until a coherent update can be published.
    """

    def __init__(
        self,
        provider: str,
        *,
        clock: ClockSource | None = None,
        book_ticker_max_age: timedelta = timedelta(seconds=3),
        mark_price_max_age: timedelta = timedelta(seconds=3),
    ) -> None:
        if not provider:
            raise ValueError("provider must not be empty")
        if book_ticker_max_age <= timedelta(0):
            raise ValueError("book_ticker_max_age must be positive")
        if mark_price_max_age <= timedelta(0):
            raise ValueError("mark_price_max_age must be positive")
        self._provider = provider
        self._clock = clock or LiveClock()
        self._book_ticker_max_age = book_ticker_max_age
        self._mark_price_max_age = mark_price_max_age
        self._book_ticker: BookTicker | None = None
        self._mark_price: MarkPriceUpdate | None = None
        self._last_context: MarketContext | None = None

    def update_book_ticker(self, update: BookTicker) -> MarketContextUpdated | None:
        """Apply a book update and return an event only for a coherent snapshot."""
        if not self._valid_book(update):
            return None
        if self._book_ticker is not None and update.timestamp < self._book_ticker.timestamp:
            return None
        self._book_ticker = update
        return self._build_event()

    def update_mark_price(self, update: MarkPriceUpdate) -> MarketContextUpdated | None:
        """Apply a mark update and return an event only for a coherent snapshot."""
        if not self._valid_mark(update):
            return None
        if self._mark_price is not None and update.timestamp < self._mark_price.timestamp:
            return None
        self._mark_price = update
        return self._build_event()

    def ingest(self, update: BookTicker | MarkPriceUpdate) -> MarketContextUpdated | None:
        """Dispatch one parsed component update to the appropriate aggregation method."""
        if isinstance(update, BookTicker):
            return self.update_book_ticker(update)
        if isinstance(update, MarkPriceUpdate):
            return self.update_mark_price(update)
        raise TypeError("unsupported market-context component")

    @property
    def latest_context(self) -> MarketContext | None:
        """Return the last published immutable context, if any."""
        return self._last_context

    def _build_event(self) -> MarketContextUpdated | None:
        book = self._book_ticker
        mark = self._mark_price
        if book is None or mark is None:
            return None
        if book.instrument_id != mark.instrument_id:
            return None
        as_of = self._now()
        if as_of - book.timestamp > self._book_ticker_max_age:
            return None
        if as_of - mark.timestamp > self._mark_price_max_age:
            return None
        if book.timestamp > as_of or mark.timestamp > as_of:
            return None
        context = MarketContext(
            instrument_id=book.instrument_id,
            provider=self._provider,
            bid=book.bid,
            ask=book.ask,
            mark_price=mark.mark_price,
            index_price=mark.index_price,
            funding_rate=mark.funding_rate,
            next_funding_time=mark.next_funding_time,
            as_of=as_of,
            bid_at=book.timestamp,
            ask_at=book.timestamp,
            mark_at=mark.timestamp,
            index_at=mark.timestamp,
            funding_at=mark.timestamp,
        )
        self._last_context = context
        return MarketContextUpdated(context=context, occurred_at=as_of)

    def _now(self) -> datetime:
        now = self._clock.now() if isinstance(self._clock, Clock) else self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("market-context clock must return UTC")
        return now.astimezone(UTC)

    def _valid_book(self, update: BookTicker) -> bool:
        return (
            update.instrument_id is not None
            and self._is_utc(update.timestamp)
            and self._positive_finite(update.bid)
            and self._positive_finite(update.ask)
            and update.bid <= update.ask
            and (self._mark_price is None or update.instrument_id == self._mark_price.instrument_id)
        )

    def _valid_mark(self, update: MarkPriceUpdate) -> bool:
        return (
            update.instrument_id is not None
            and self._is_utc(update.timestamp)
            and self._is_utc(update.next_funding_time)
            and self._positive_finite(update.mark_price)
            and self._positive_finite(update.index_price)
            and self._finite(update.funding_rate)
            and (
                self._book_ticker is None
                or update.instrument_id == self._book_ticker.instrument_id
            )
        )

    @staticmethod
    def _is_utc(value: datetime) -> bool:
        return value.tzinfo is not None and value.utcoffset() == timedelta(0)

    @staticmethod
    def _finite(value: Decimal) -> bool:
        return value.is_finite()

    @classmethod
    def _positive_finite(cls, value: Decimal) -> bool:
        if not cls._finite(value):
            return False
        try:
            return value > Decimal(0)
        except InvalidOperation:
            return False


__all__ = ["MarketContextAggregator"]
