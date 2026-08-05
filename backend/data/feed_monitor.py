"""Deterministic freshness monitoring for live market-data components."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from backend.core.clock import Clock, LiveClock
from backend.core.events import DataFeedError

type ErrorPublisher = Callable[[DataFeedError], Awaitable[None] | None]


class DataFeedMonitor:
    """Track component timestamps and report each stale episode once.

    The monitor is deliberately timer-free.  The owning runner invokes
    :meth:`check_feed`, so no task is created here and simulation tests control
    every clock read.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        candle_timeout: timedelta = timedelta(minutes=5),
        book_ticker_timeout: timedelta = timedelta(seconds=5),
        mark_context_timeout: timedelta = timedelta(seconds=5),
        error_publisher: ErrorPublisher | None = None,
    ) -> None:
        for name, timeout in (
            ("candle_timeout", candle_timeout),
            ("book_ticker_timeout", book_ticker_timeout),
            ("mark_context_timeout", mark_context_timeout),
        ):
            if timeout <= timedelta(0):
                raise ValueError(f"{name} must be positive")
        self._clock = clock or LiveClock()
        self._timeouts = {
            "candle": candle_timeout,
            "book_ticker": book_ticker_timeout,
            "mark_context": mark_context_timeout,
        }
        self._last_seen: dict[tuple[UUID, str], datetime] = {}
        self._stale: set[tuple[UUID, str]] = set()
        self._error_publisher = error_publisher

    def record_candle(self, instrument_id: UUID, timestamp: datetime) -> None:
        """Record a completed candle open time for freshness purposes."""
        self._record(instrument_id, "candle", timestamp)

    def record_book_ticker(self, instrument_id: UUID, timestamp: datetime) -> None:
        """Record a best-bid/best-ask update timestamp."""
        self._record(instrument_id, "book_ticker", timestamp)

    def record_mark_price(self, instrument_id: UUID, timestamp: datetime) -> None:
        """Record a mark-price component timestamp."""
        self._record(instrument_id, "mark_context", timestamp)

    def record_context(self, instrument_id: UUID, timestamp: datetime) -> None:
        """Record a coherent context snapshot timestamp."""
        self._record(instrument_id, "mark_context", timestamp)

    async def check_feed(self, instrument_id: UUID) -> tuple[DataFeedError, ...]:
        """Publish and return newly detected timeout errors for one instrument."""
        now = self._now()
        errors: list[DataFeedError] = []
        for component, timeout in self._timeouts.items():
            key = (instrument_id, component)
            last_seen = self._last_seen.get(key)
            if last_seen is None or now - last_seen <= timeout:
                self._stale.discard(key)
                continue
            if key in self._stale:
                continue
            self._stale.add(key)
            error = DataFeedError(
                instrument_id=instrument_id,
                error=f"feed_timeout: {component} has no fresh data",
                occurred_at=now,
            )
            errors.append(error)
            if self._error_publisher is not None:
                result = self._error_publisher(error)
                if result is not None:
                    await result
        return tuple(errors)

    def _record(self, instrument_id: UUID, component: str, timestamp: datetime) -> None:
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise ValueError("feed timestamps must be UTC")
        key = (instrument_id, component)
        previous = self._last_seen.get(key)
        if previous is None or timestamp > previous:
            self._last_seen[key] = timestamp.astimezone(UTC)
            self._stale.discard(key)

    def _now(self) -> datetime:
        value = self._clock.now()
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("feed monitor clock must return UTC")
        return value.astimezone(UTC)


__all__ = ["DataFeedMonitor"]
