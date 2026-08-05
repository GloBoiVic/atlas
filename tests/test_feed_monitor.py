from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.core.clock import Clock
from backend.data.feed_monitor import DataFeedMonitor


class FixedClock(Clock):
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


@pytest.mark.asyncio
async def test_monitor_reports_one_error_per_stale_episode_and_recovers() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FixedClock(now)
    monitor = DataFeedMonitor(
        clock=clock,
        candle_timeout=timedelta(seconds=5),
        book_ticker_timeout=timedelta(seconds=5),
        mark_context_timeout=timedelta(seconds=5),
    )
    instrument_id = uuid4()
    monitor.record_candle(instrument_id, now)

    clock.value = now + timedelta(seconds=6)
    first = await monitor.check_feed(instrument_id)
    second = await monitor.check_feed(instrument_id)

    assert len(first) == 1
    assert first[0].error == "feed_timeout: candle has no fresh data"
    assert second == ()

    monitor.record_candle(instrument_id, clock.value)
    assert await monitor.check_feed(instrument_id) == ()
    clock.value += timedelta(seconds=6)
    assert len(await monitor.check_feed(instrument_id)) == 1


@pytest.mark.asyncio
async def test_monitor_checks_book_and_mark_context_independently() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FixedClock(now)
    monitor = DataFeedMonitor(
        clock=clock,
        book_ticker_timeout=timedelta(seconds=1),
        mark_context_timeout=timedelta(seconds=1),
    )
    instrument_id = uuid4()
    monitor.record_book_ticker(instrument_id, now)
    monitor.record_mark_price(instrument_id, now)

    clock.value += timedelta(seconds=2)
    errors = await monitor.check_feed(instrument_id)

    assert {error.error for error in errors} == {
        "feed_timeout: book_ticker has no fresh data",
        "feed_timeout: mark_context has no fresh data",
    }
