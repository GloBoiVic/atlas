"""Deterministic, non-filling M1 to M15 aggregation."""

from datetime import datetime, timedelta
from decimal import Decimal

from backend.domain.market_data import Bar, InputError, PriceComponent, Timeframe

from .session_calendar import is_session_open_minute


class AggregationError(ValueError):
    """An M15 interval cannot be safely derived from the supplied M1 bars."""


def aggregate_m1_to_m15(
    bars: tuple[Bar, ...] | list[Bar],
    component: PriceComponent,
    coverage_start: datetime,
    coverage_end: datetime,
) -> tuple[Bar, ...]:
    if type(component) is not PriceComponent:
        raise InputError("component must be a PriceComponent")
    if (
        coverage_start.tzinfo is None
        or coverage_end.tzinfo is None
        or coverage_start.utcoffset() != timedelta(0)
        or coverage_end.utcoffset() != timedelta(0)
    ):
        raise ValueError("coverage must be UTC")
    if (
        coverage_start.second
        or coverage_start.microsecond
        or coverage_end.second
        or coverage_end.microsecond
        or coverage_end <= coverage_start
    ):
        raise ValueError("coverage must be a positive minute-aligned range")
    selected = [
        bar
        for bar in bars
        if bar.price_component is component
        and coverage_start <= bar.start_time < coverage_end
    ]
    if any(bar.timeframe is not Timeframe.M1 for bar in selected):
        raise AggregationError("aggregation requires M1 bars")
    if any(not is_session_open_minute(bar.start_time) for bar in selected):
        raise AggregationError("M1 observation occurs during a scheduled closure")
    by_start: dict[datetime, Bar] = {}
    for bar in selected:
        if bar.start_time in by_start:
            raise AggregationError(
                f"duplicate M1 constituent in {bar.start_time.isoformat()}"
            )
        by_start[bar.start_time] = bar
    cursor = coverage_start - timedelta(minutes=coverage_start.minute % 15)
    output: list[Bar] = []
    while cursor < coverage_end:
        end = cursor + timedelta(minutes=15)
        if end <= coverage_start or cursor >= coverage_end:
            cursor = end
            continue
        constituent_times = [cursor + timedelta(minutes=offset) for offset in range(15)]
        open_times = [at for at in constituent_times if is_session_open_minute(at)]
        if not open_times:
            cursor = end
            continue
        if cursor < coverage_start or end > coverage_end:
            cursor = end
            continue
        constituents = [by_start.get(at) for at in open_times]
        if any(bar is None for bar in constituents):
            raise AggregationError(f"missing M1 constituent in {cursor.isoformat()}")
        actual = [bar for bar in constituents if bar is not None]
        if len({bar.start_time for bar in actual}) != len(actual):
            raise AggregationError(f"duplicate M1 constituent in {cursor.isoformat()}")
        if any(not is_session_open_minute(bar.start_time) for bar in actual):
            raise AggregationError("M1 observation occurs during a scheduled closure")
        volumes = [bar.volume for bar in actual]
        if all(item is not None for item in volumes):
            present_volumes = [item for item in volumes if item is not None]
            volume: Decimal | None = sum(present_volumes, Decimal(0))
        else:
            volume = None
        output.append(
            Bar(
                actual[0].instrument,
                Timeframe.M15,
                component,
                cursor,
                end,
                actual[0].open,
                max(bar.high for bar in actual),
                min(bar.low for bar in actual),
                actual[-1].close,
                volume=volume,
            )
        )
        cursor = end
    return tuple(output)


derive_m15 = aggregate_m1_to_m15

__all__ = ["AggregationError", "aggregate_m1_to_m15", "derive_m15"]
