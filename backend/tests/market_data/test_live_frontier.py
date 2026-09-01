from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import Direction, EntryPolicy, PendingEntryHandoff
from backend.market_data.live import (
    CompletedM15Frontier,
    EntryObservationStatus,
    LiveDataError,
    SparseM1ExecutionObservation,
    entry_triggered,
    evaluate_entry_observation,
    pair_sparse_m1_bars,
    validate_completed_native_m15,
)

FRONTIER = datetime(2026, 1, 5, 10, 15, tzinfo=UTC)


def bar(start: datetime, component: PriceComponent, value: str = "1.1000") -> Bar:
    price = Decimal(value)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M1,
        component,
        start,
        start + timedelta(minutes=1),
        price,
        price + Decimal(".0010"),
        price - Decimal(".0010"),
        price + Decimal(".0005"),
    )


def m15(start: datetime) -> Bar:
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        Decimal("1.1"), Decimal("1.11"), Decimal("1.09"), Decimal("1.105"),
    )


def handoff(direction: Direction, trigger: str) -> PendingEntryHandoff:
    return PendingEntryHandoff(
        EntryPolicy.PRICE_TRIGGERED,
        direction,
        Decimal(trigger),
        PriceComponent.ASK if direction is Direction.LONG else PriceComponent.BID,
        FRONTIER,
        FRONTIER,
        5,
    )


def test_completed_frontier_accepts_only_elapsed_native_m15_and_advances_once() -> None:
    current = m15(datetime(2026, 1, 5, 10, 0, tzinfo=UTC))
    validate_completed_native_m15(current, FRONTIER)
    frontier = CompletedM15Frontier().accept(current, FRONTIER)
    assert frontier.last_completed_end == FRONTIER
    assert frontier.accept(current, FRONTIER) is frontier
    with pytest.raises(LiveDataError, match="conflicting duplicate"):
        frontier.accept(
            Bar(
                Instrument.EUR_USD,
                Timeframe.M15,
                PriceComponent.MID,
                current.start_time,
                current.end_time,
                Decimal("1.2"),
                Decimal("1.21"),
                Decimal("1.19"),
                Decimal("1.205"),
            ),
            FRONTIER,
        )
    with pytest.raises(LiveDataError, match="not completed"):
        validate_completed_native_m15(
            m15(datetime(2026, 1, 5, 10, 15, tzinfo=UTC)), FRONTIER
        )


def test_sparse_m1_requires_both_sides_and_does_not_aggregate_or_fill_missing() -> None:
    start = FRONTIER + timedelta(minutes=1)
    bid, ask = bar(start, PriceComponent.BID), bar(start, PriceComponent.ASK, "1.1002")
    observation = pair_sparse_m1_bars((ask, bid))[0]
    assert observation.bid_open == Decimal("1.1000")
    assert pair_sparse_m1_bars((bid,))[0:] == ()
    with pytest.raises(LiveDataError):
        SparseM1ExecutionObservation(
            bid, bar(start + timedelta(minutes=1), PriceComponent.ASK)
        )


def test_frontier_equality_and_exact_long_short_predicates() -> None:
    equal = SparseM1ExecutionObservation(
        bar(FRONTIER, PriceComponent.BID, "1.0990"),
        bar(FRONTIER, PriceComponent.ASK, "1.1050"),
    )
    assert (
        evaluate_entry_observation(handoff(Direction.LONG, "1.1050"), equal).status
        is EntryObservationStatus.FRONTIER_EQUAL
    )

    later = SparseM1ExecutionObservation(
        bar(FRONTIER + timedelta(minutes=1), PriceComponent.BID, "1.0950"),
        bar(FRONTIER + timedelta(minutes=1), PriceComponent.ASK, "1.1050"),
    )
    long_result = evaluate_entry_observation(handoff(Direction.LONG, "1.1050"), later)
    short_result = evaluate_entry_observation(handoff(Direction.SHORT, "1.0950"), later)
    assert long_result.status is EntryObservationStatus.ELIGIBLE
    assert short_result.status is EntryObservationStatus.ELIGIBLE
    assert entry_triggered(Direction.LONG, Decimal("1.1050"), later)
    assert entry_triggered(Direction.SHORT, Decimal("1.0950"), later)
