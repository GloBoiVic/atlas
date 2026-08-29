from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.experiments.clock import ClockPhase, SimulationClock
from backend.persistence.market_data_repository import (
    SnapshotBar,
    SnapshotBarSourceIdentity,
)


def _m1(start: datetime, component: PriceComponent, value: str) -> SnapshotBar:
    price = Decimal(value)
    bar = Bar(
        Instrument.EUR_USD,
        Timeframe.M1,
        component,
        start,
        start + timedelta(minutes=1),
        price, price + Decimal(".001"), price - Decimal(".001"), price,
    )
    return SnapshotBar(bar, SnapshotBarSourceIdentity(uuid4(), "a" * 64, None, start))


def _m15(start: datetime, value: str = "1.1000") -> Bar:
    price = Decimal(value)
    return Bar(
        Instrument.EUR_USD, Timeframe.M15, PriceComponent.MID, start,
        start + timedelta(minutes=15), price, price + Decimal(".001"),
        price - Decimal(".001"), price,
    )


def test_signal_bar_is_not_reused_as_post_decision_execution_data() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    m1 = tuple(
        item
        for minute in (start + timedelta(minutes=14), start + timedelta(minutes=15))
        for item in (
            _m1(minute, PriceComponent.MID, "1.1000"),
            _m1(minute, PriceComponent.BID, "1.0999"),
            _m1(minute, PriceComponent.ASK, "1.1001"),
        )
    )
    frame = next(iter(SimulationClock(
        m1, (_m15(start),), trading_start=start - timedelta(minutes=15),
        trading_end=start + timedelta(minutes=30), required_historical_context_bars=0,
    )))
    assert frame.phase is ClockPhase.DECISION
    assert frame.frontier == start + timedelta(minutes=15)
    assert {item.bar.start_time for item in frame.completed_m1} == {
        start + timedelta(minutes=14)
    }
    assert {item.bar.start_time for item in frame.executable_opens} == {
        start + timedelta(minutes=15)
    }
    assert all(
        item.bar.price_component in (PriceComponent.BID, PriceComponent.ASK)
        for item in frame.executable_opens
    )
    assert not set(frame.completed_m1).intersection(frame.executable_opens)


def test_sparse_v2_execution_accepts_bid_ask_without_wall_clock_continuity() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    frontier = start + timedelta(minutes=15)
    clock = SimulationClock(
        (_m1(frontier, PriceComponent.ASK, "1.1001"),
         _m1(frontier, PriceComponent.BID, "1.0999")),
        (_m15(start),),
        trading_start=start,
        trading_end=start + timedelta(minutes=30),
        sparse_execution=True,
    )
    frames = tuple(clock.frames())
    assert frames[0].phase is ClockPhase.DECISION
    assert frames[0].decision_bar.timeframe is Timeframe.M15
    assert frames[0].decision_bar.price_component is PriceComponent.MID
    observations = tuple(clock.observations())
    assert observations[0].sparse is True
    assert tuple(item.bar.price_component for item in observations[0].bars) == (
        PriceComponent.ASK,
        PriceComponent.BID,
    )


def test_exact_frontier_is_exposed_as_post_decision_data_but_not_pre_decision() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    frontier = start + timedelta(minutes=15)
    clock = SimulationClock(
        tuple(
            item
            for minute in (frontier, frontier + timedelta(minutes=1))
            for item in (
                _m1(minute, PriceComponent.ASK, "1.1001"),
                _m1(minute, PriceComponent.BID, "1.0999"),
            )
        ),
        (_m15(start),),
        trading_start=start,
        trading_end=start + timedelta(minutes=30),
        sparse_execution=True,
    )

    frame = next(iter(clock.frames()))
    assert {item.bar.start_time for item in frame.executable_opens} == {frontier}
    assert [item.start_time for item in clock.observations()] == [
        frontier,
        frontier + timedelta(minutes=1),
    ]
    assert clock.entry_observation(frontier) is not None


def test_warmup_is_ordered_before_trading_and_disables_exposure() -> None:
    first = datetime(2026, 1, 5, 9, 45, tzinfo=UTC)
    m15 = (_m15(first), _m15(first + timedelta(minutes=15)))
    m1 = tuple(
        _m1(first + timedelta(minutes=minute), PriceComponent.MID, "1.1000")
        for minute in (14, 29, 30)
    )
    frames = tuple(SimulationClock(
        m1, m15, trading_start=first + timedelta(minutes=15),
        trading_end=first + timedelta(minutes=45), required_historical_context_bars=1,
    ))
    assert frames[0].phase is ClockPhase.WARMUP
    assert not frames[0].exposure_allowed
    assert frames[1].phase is ClockPhase.DECISION
    assert frames[1].exposure_allowed


def test_clock_rejects_non_aligned_trading_range() -> None:
    with pytest.raises(ValueError, match="M15-aligned"):
        SimulationClock((), (), trading_start=datetime(2026, 1, 5, 10, 1, tzinfo=UTC),
                         trading_end=datetime(2026, 1, 5, 11, tzinfo=UTC))


def test_zero_warmup_does_not_emit_historical_frames() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    m15 = (_m15(start - timedelta(minutes=15)), _m15(start))
    m1 = tuple(
        _m1(start - timedelta(minutes=minute), PriceComponent.MID, "1.1000")
        for minute in (1,)
    ) + tuple(
        _m1(start + timedelta(minutes=minute), PriceComponent.MID, "1.1000")
        for minute in (14,)
    )
    frames = tuple(SimulationClock(
        m1, m15, trading_start=start, trading_end=start + timedelta(minutes=15)
    ))
    assert all(frame.phase is ClockPhase.DECISION for frame in frames)


def test_observations_are_complete_chronological_and_half_open() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    m1 = tuple(
        item
        for minute in (0, 1, 2)
        for item in (
            _m1(start + timedelta(minutes=minute), PriceComponent.MID, "1.1000"),
            _m1(start + timedelta(minutes=minute), PriceComponent.BID, "1.0999"),
            _m1(start + timedelta(minutes=minute), PriceComponent.ASK, "1.1001"),
        )
    )
    clock = SimulationClock(
        m1, (), trading_start=start, trading_end=start + timedelta(minutes=15)
    )
    observations = tuple(clock.observations())
    assert [item.start_time for item in observations] == [
        start, start + timedelta(minutes=1), start + timedelta(minutes=2)
    ]
    assert all(len(item.bars) == 3 for item in observations)


def test_sparse_entry_lookup_is_exact_and_does_not_use_later_quote() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    frontier = start + timedelta(minutes=15)
    later = frontier + timedelta(minutes=1)
    clock = SimulationClock(
        tuple(
            item
            for minute in (later,)
            for item in (
                _m1(minute, PriceComponent.ASK, "1.1001"),
                _m1(minute, PriceComponent.BID, "1.0999"),
            )
        ),
        (_m15(start),),
        trading_start=start,
        trading_end=start + timedelta(minutes=30),
        sparse_execution=True,
    )
    assert clock.entry_observation(frontier) is None
    assert clock.entry_observation(later) is not None


def test_sparse_incomplete_bucket_is_unavailable_not_fabricated() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    frontier = start + timedelta(minutes=15)
    clock = SimulationClock(
        (_m1(frontier, PriceComponent.BID, "1.0999"),),
        (_m15(start),),
        trading_start=start,
        trading_end=start + timedelta(minutes=30),
        sparse_execution=True,
    )
    assert tuple(clock.observations()) == ()
    assert clock.entry_observation(frontier) is None
