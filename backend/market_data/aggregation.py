"""Deterministic, non-filling M1 to M15 aggregation."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from backend.domain.market_data import Bar, InputError, PriceComponent, Timeframe

from .session_policy import EXPECTED_DATA, OANDA_EUR_USD_POLICY


class AggregationError(ValueError):
    """An M15 interval cannot be safely derived from the supplied M1 bars."""


@dataclass(frozen=True, slots=True)
class IntervalDiagnostic:
    reason: str
    policy_version: str
    missing_components: tuple[PriceComponent, ...]
    interval_start: datetime
    interval_end: datetime
    missing_times: tuple[datetime, ...] = ()


def _coalesce_diagnostics(
    items: list[IntervalDiagnostic],
) -> tuple[IntervalDiagnostic, ...]:
    ordered = sorted(
        items,
        key=lambda item: (
            item.interval_start,
            item.reason,
            item.policy_version,
            tuple(component.value for component in item.missing_components),
        ),
    )
    result: list[IntervalDiagnostic] = []
    for item in ordered:
        if result and (
            result[-1].interval_end == item.interval_start
            and result[-1].reason == item.reason
            and result[-1].policy_version == item.policy_version
            and result[-1].missing_components == item.missing_components
        ):
            previous = result[-1]
            result[-1] = IntervalDiagnostic(
                previous.reason, previous.policy_version, previous.missing_components,
                previous.interval_start, item.interval_end,
                previous.missing_times + item.missing_times,
            )
        else:
            result.append(item)
    return tuple(result)


def aggregate_m1_to_m15(
    bars: tuple[Bar, ...] | list[Bar],
    component: PriceComponent,
    coverage_start: datetime,
    coverage_end: datetime,
) -> tuple[list[Bar], list[IntervalDiagnostic]]:
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
    by_start: dict[datetime, Bar] = {}
    for bar in selected:
        if bar.start_time in by_start:
            raise AggregationError(
                f"duplicate M1 constituent in {bar.start_time.isoformat()}"
            )
        by_start[bar.start_time] = bar
    cursor = coverage_start - timedelta(minutes=coverage_start.minute % 15)
    output: list[Bar] = []
    diagnostics: list[IntervalDiagnostic] = []
    while cursor < coverage_end:
        end = cursor + timedelta(minutes=15)
        if end <= coverage_start or cursor >= coverage_end:
            cursor = end
            continue
        constituent_times = [cursor + timedelta(minutes=offset) for offset in range(15)]
        open_times = [
            at
            for at in constituent_times
            if OANDA_EUR_USD_POLICY.classify_minute(at)[0] == EXPECTED_DATA
        ]
        if not open_times:
            cursor = end
            continue
        expected_times = [
            at for at in open_times if coverage_start <= at < coverage_end
        ]
        if not expected_times:
            cursor = end
            continue
        constituents = [by_start.get(at) for at in expected_times]
        if any(bar is None for bar in constituents):
            diagnostics.append(
                IntervalDiagnostic(
                    "UNEXPECTED_MISSING_DATA",
                    OANDA_EUR_USD_POLICY.classify_minute(expected_times[0])[2],
                    (component,),
                    cursor,
                    end,
                    tuple(
                        at
                        for at, bar in zip(expected_times, constituents, strict=True)
                        if bar is None
                    ),
                )
            )
            cursor = end
            continue
        actual = [bar for bar in constituents if bar is not None]
        if len({bar.start_time for bar in actual}) != len(actual):
            raise AggregationError(f"duplicate M1 constituent in {cursor.isoformat()}")
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
    return output, list(_coalesce_diagnostics(diagnostics))

__all__ = [
    "AggregationError",
    "IntervalDiagnostic",
    "aggregate_m1_to_m15",
]
