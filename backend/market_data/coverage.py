"""Pure validation and reporting for required M1 market-data coverage."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.domain.market_data import Bar, PriceComponent

from .session_calendar import is_session_open_minute


@dataclass(frozen=True, slots=True)
class MissingMinute:
    start: datetime
    components: tuple[PriceComponent, ...]


@dataclass(frozen=True, slots=True)
class CoverageGap:
    start: datetime
    end: datetime
    components: tuple[PriceComponent, ...]
    minutes: tuple[MissingMinute, ...]


@dataclass(frozen=True, slots=True)
class CoverageReport:
    expected_open_minutes: int
    expected_closure_minutes: int
    member_minutes: int
    missing: tuple[MissingMinute, ...]
    gaps: tuple[CoverageGap, ...]
    closure_anomalies: tuple[datetime, ...]
    unexpected_observations: tuple[datetime, ...]

    @property
    def valid(self) -> bool:
        return (
            not self.missing
            and not self.closure_anomalies
            and not self.unexpected_observations
        )


def _validate_range(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or start.utcoffset() != timedelta(0):
        raise ValueError("start must be UTC")
    if end.tzinfo is None or end.utcoffset() != timedelta(0):
        raise ValueError("end must be UTC")
    if start.second or start.microsecond or end.second or end.microsecond:
        raise ValueError("coverage range must be minute-aligned")
    if end <= start:
        raise ValueError("coverage range must be positive")


def coalesce_gaps(missing: Iterable[MissingMinute]) -> tuple[CoverageGap, ...]:
    ordered = sorted(missing, key=lambda item: item.start)
    if not ordered:
        return ()
    groups: list[list[MissingMinute]] = [[ordered[0]]]
    for item in ordered[1:]:
        previous = groups[-1][-1]
        if item.start == previous.start + timedelta(minutes=1):
            groups[-1].append(item)
        else:
            groups.append([item])
    return tuple(
        CoverageGap(
            group[0].start,
            group[-1].start + timedelta(minutes=1),
            tuple(
                sorted(
                    {component for item in group for component in item.components},
                    key=lambda c: c.value,
                )
            ),
            tuple(group),
        )
        for group in groups
    )


def validate_coverage(
    start: datetime,
    end: datetime,
    bars: Iterable[Bar],
    required_components: tuple[PriceComponent, ...] = (
        PriceComponent.ASK,
        PriceComponent.BID,
        PriceComponent.MID,
    ),
) -> CoverageReport:
    _validate_range(start, end)
    if not required_components or len(set(required_components)) != len(
        required_components
    ):
        raise ValueError("required_components must be a non-empty unique tuple")
    by_minute: dict[datetime, set[PriceComponent]] = defaultdict(set)
    closure_anomalies: set[datetime] = set()
    unexpected: set[datetime] = set()
    cursor = start
    expected_open = 0
    expected_closed = 0
    while cursor < end:
        if is_session_open_minute(cursor):
            expected_open += 1
        else:
            expected_closed += 1
        cursor += timedelta(minutes=1)
    for bar in bars:
        if (
            bar.start_time < start
            or bar.start_time >= end
            or bar.end_time != bar.start_time + timedelta(minutes=1)
        ):
            unexpected.add(bar.start_time)
        elif not is_session_open_minute(bar.start_time):
            closure_anomalies.add(bar.start_time)
        else:
            by_minute[bar.start_time].add(bar.price_component)
    missing: list[MissingMinute] = []
    cursor = start
    while cursor < end:
        if is_session_open_minute(cursor):
            absent = tuple(
                component
                for component in required_components
                if component not in by_minute[cursor]
            )
            if absent:
                missing.append(MissingMinute(cursor, absent))
        cursor += timedelta(minutes=1)
    return CoverageReport(
        expected_open,
        expected_closed,
        sum(
            1
            for components in by_minute.values()
            if all(component in components for component in required_components)
        ),
        tuple(missing),
        coalesce_gaps(missing),
        tuple(sorted(closure_anomalies)),
        tuple(sorted(unexpected)),
    )


__all__ = [
    "CoverageGap",
    "CoverageReport",
    "MissingMinute",
    "coalesce_gaps",
    "validate_coverage",
]
