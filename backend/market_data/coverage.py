"""Pure validation and reporting for required M1 market-data coverage."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.domain.market_data import Bar, PriceComponent

from .aggregation import IntervalDiagnostic, aggregate_m1_to_m15
from .session_policy import EXPECTED_DATA, OANDA_EUR_USD_POLICY


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
    interval_diagnostics: tuple[IntervalDiagnostic, ...] = ()

    @property
    def valid(self) -> bool:
        return (
            not self.missing
            and not self.closure_anomalies
            and not self.unexpected_observations
            and not self.interval_diagnostics
        )


def diagnostic_payloads(
    report: CoverageReport, *, limit: int = 100
) -> tuple[list[dict[str, object]], bool]:
    """Return the bounded, durable diagnostic view of a coverage report.

    The report itself is deliberately untouched: callers decide validity from
    the complete report before using this presentation boundary.
    """
    if limit < 1:
        raise ValueError("diagnostic limit must be positive")
    values: list[tuple[datetime, dict[str, object]]] = []
    for gap in report.gaps:
        policy_version = OANDA_EUR_USD_POLICY.classify_minute(gap.start)[2]
        values.append(
            (
                gap.start,
                {
                    "start": gap.start.isoformat().replace("+00:00", "Z"),
                    "end": gap.end.isoformat().replace("+00:00", "Z"),
                    "reason": "UNEXPECTED_MISSING_DATA",
                    "policy_version": policy_version,
                    "missing_components": [item.value for item in gap.components],
                },
            )
        )
    for item in getattr(report, "interval_diagnostics", ()):
        values.append(
            (
                item.interval_start,
                {
                    "start": item.interval_start.isoformat().replace("+00:00", "Z"),
                    "end": item.interval_end.isoformat().replace("+00:00", "Z"),
                    "reason": item.reason,
                    "policy_version": item.policy_version,
                    "missing_components": [
                        component.value for component in item.missing_components
                    ],
                },
            )
        )
    for moment in getattr(report, "closure_anomalies", ()):
        values.append(
            (
                moment,
                {
                    "start": moment.isoformat().replace("+00:00", "Z"),
                    "end": (moment + timedelta(minutes=1))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "reason": "UNEXPECTED_OBSERVATION_DURING_UNAVAILABLE_SESSION",
                    "policy_version": OANDA_EUR_USD_POLICY.classify_minute(moment)[2],
                    "missing_components": [],
                },
            )
        )
    values.sort(key=lambda value: (value[0], str(value[1]["reason"])))
    return [item for _, item in values[:limit]], len(values) > limit


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
    bars = tuple(bars)
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
        if OANDA_EUR_USD_POLICY.classify_minute(cursor)[0] == EXPECTED_DATA:
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
        elif OANDA_EUR_USD_POLICY.classify_minute(bar.start_time)[0] != EXPECTED_DATA:
            closure_anomalies.add(bar.start_time)
        else:
            by_minute[bar.start_time].add(bar.price_component)
    missing: list[MissingMinute] = []
    cursor = start
    while cursor < end:
        if OANDA_EUR_USD_POLICY.classify_minute(cursor)[0] == EXPECTED_DATA:
            absent = tuple(
                component
                for component in required_components
                if component not in by_minute[cursor]
            )
            if absent:
                missing.append(MissingMinute(cursor, absent))
        cursor += timedelta(minutes=1)
    interval_diagnostics: list[IntervalDiagnostic] = []
    for component in required_components:
        _eligible, diagnostics = aggregate_m1_to_m15(
            tuple(bar for bar in bars if bar.price_component is component),
            component,
            start,
            end,
        )
        interval_diagnostics.extend(diagnostics)
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
        tuple(sorted(interval_diagnostics, key=lambda item: item.interval_start)),
    )


__all__ = [
    "CoverageGap",
    "CoverageReport",
    "MissingMinute",
    "coalesce_gaps",
    "diagnostic_payloads",
    "validate_coverage",
]
