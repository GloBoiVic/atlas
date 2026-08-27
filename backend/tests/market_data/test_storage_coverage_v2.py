from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.market_data.coverage import (
    analytical_range_for_completed_bars,
    plan_product_coverage,
)


def _m15(start: datetime, value: str = "1.1000") -> Bar:
    price = Decimal(value)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        price,
        price + Decimal(".001"),
        price - Decimal(".001"),
        price,
    )


def test_analytical_warmup_counts_completed_bars_not_wall_clock_minutes() -> None:
    trading_start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    bars = (
        _m15(trading_start - timedelta(minutes=60)),
        _m15(trading_start - timedelta(minutes=30)),
        _m15(trading_start - timedelta(minutes=15)),
    )
    start, end, count = analytical_range_for_completed_bars(
        trading_start, trading_start + timedelta(minutes=30), 2, bars
    )
    assert (start, end, count) == (
        trading_start - timedelta(minutes=30),
        trading_start + timedelta(minutes=30),
        2,
    )


def test_products_plan_independently_and_reuse_fully_covered_native_bars() -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    analytical = plan_product_coverage(
        start,
        end,
        "M15",
        (PriceComponent.MID,),
        (_m15(start),),
    )
    execution = plan_product_coverage(
        start, end, "M1", (PriceComponent.BID, PriceComponent.ASK), ()
    )
    assert [(gap.start, gap.end) for gap in analytical.missing_ranges] == [
        (start + timedelta(minutes=15), end)
    ]
    assert execution.missing_ranges[0].start == start
    assert execution.missing_ranges[-1].end == end


def test_weekend_closure_is_not_planned_as_fabricated_m15_coverage() -> None:
    start = datetime(2026, 1, 3, 12, tzinfo=UTC)  # Saturday
    plan = plan_product_coverage(
        start, start + timedelta(minutes=30), "M15", (PriceComponent.MID,), ()
    )
    assert plan.fully_covered


def test_declared_oanda_holiday_is_not_planned_as_missing_m1_coverage() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    plan = plan_product_coverage(
        start,
        start + timedelta(hours=22, minutes=5),
        "M1",
        (PriceComponent.BID, PriceComponent.ASK),
        (),
    )
    assert plan.fully_covered
