from datetime import UTC, datetime, timedelta

import pytest

from backend.core.clock import Clock, LiveClock, SimulationClock


def test_clock_is_abstract():
    incomplete_clock = type("IncompleteClock", (Clock,), {})

    with pytest.raises(TypeError):
        incomplete_clock()


def test_live_clock_returns_utc_aware_timestamp():
    before = datetime.now(UTC)
    timestamp = LiveClock().now()
    after = datetime.now(UTC)

    assert timestamp.tzinfo == UTC
    assert before <= timestamp <= after


def test_simulation_clock_starts_at_exact_timestamp():
    start_time = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
    clock = SimulationClock(start_time)

    assert clock.now() is start_time


def test_simulation_clock_advances_to_exact_timestamp():
    start_time = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
    next_time = datetime(2026, 8, 1, 9, 31, tzinfo=UTC)
    clock = SimulationClock(start_time)

    clock.advance(next_time)

    assert clock.now() is next_time


def test_simulation_clock_preserves_each_advanced_timestamp():
    timestamps = [
        datetime(2026, 8, 1, 9, 30, tzinfo=UTC),
        datetime(2026, 8, 1, 9, 31, tzinfo=UTC),
        datetime(2026, 8, 1, 9, 32, tzinfo=UTC),
    ]
    clock = SimulationClock(timestamps[0])

    for timestamp in timestamps[1:]:
        clock.advance(timestamp)
        assert clock.now() is timestamp


def test_simulation_clock_accepts_non_monotonic_exact_assignment():
    start_time = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
    earlier_time = start_time - timedelta(minutes=1)
    clock = SimulationClock(start_time)

    clock.advance(earlier_time)

    assert clock.now() is earlier_time
