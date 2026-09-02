from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.market_data.session_calendar import (
    eligible_m15_windows,
    required_warmup_range,
)
from backend.paper.current_analytical_frontier import (
    AnalyticalFrontierDataError,
    AnalyticalFrontierError,
    NoCurrentAnalyticalFrontierError,
    load_current_analytical_frontier,
)


def moment(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 5, hour, minute, tzinfo=UTC)


def bar(start: datetime, *, component: PriceComponent = PriceComponent.MID) -> Bar:
    value = Decimal("1.1000") + Decimal(start.minute) / Decimal("100000")
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        component,
        start,
        start + timedelta(minutes=15),
        value,
        value + Decimal("0.0010"),
        value - Decimal("0.0010"),
        value + Decimal("0.0005"),
    )


def bars_for(start: datetime, end: datetime) -> tuple[Bar, ...]:
    return tuple(
        bar(window_start) for window_start, _ in eligible_m15_windows(start, end)
    )


@dataclass(frozen=True)
class FetchResult:
    bars: tuple[Bar, ...]
    incomplete: tuple[object, ...] = ()


@dataclass
class RecordingSource:
    factory: Callable[[datetime, datetime], tuple[Bar, ...]]

    def __post_init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    def fetch_native_m15(self, start: datetime, end: datetime) -> FetchResult:
        self.calls.append((start, end))
        return FetchResult(self.factory(start, end))


def test_cutoff_is_utc_quarter_hour_and_excludes_forming_candle() -> None:
    source = RecordingSource(lambda start, end: bars_for(start, end) + (bar(end),))

    with pytest.raises(AnalyticalFrontierDataError, match="outside the requested"):
        load_current_analytical_frontier(
            source,
            now=moment(10, 17).replace(second=42),
            warm_up_m15_bars=2,
        )

    assert source.calls == [(moment(9, 30), moment(10, 15))]


@pytest.mark.parametrize(
    "now",
    (
        datetime(2026, 1, 5, 10, 17),
        datetime(2026, 1, 5, 10, 17, tzinfo=timezone(timedelta(hours=1))),
    ),
)
def test_now_must_be_explicit_utc(now: datetime) -> None:
    source = RecordingSource(lambda start, end: bars_for(start, end))

    with pytest.raises(AnalyticalFrontierError, match="UTC"):
        load_current_analytical_frontier(source, now=now, warm_up_m15_bars=1)

    assert source.calls == []


def test_open_candidate_returns_ordered_native_context_and_previous_frontier() -> None:
    source = RecordingSource(lambda start, end: tuple(reversed(bars_for(start, end))))

    result = load_current_analytical_frontier(
        source,
        now=moment(10, 17),
        warm_up_m15_bars=2,
    )

    assert result.requested_start == moment(9, 30)
    assert result.requested_end == moment(10, 15)
    assert result.acquisition_cutoff == moment(10, 15)
    assert [item.start_time for item in result.bars] == [
        moment(9, 30),
        moment(9, 45),
        moment(10, 0),
    ]
    assert result.current_bar.start_time == moment(10, 0)
    assert result.current_frontier == moment(10, 15)
    assert result.previous_frontier == moment(10, 0)
    assert result.context_bars == result.bars


def test_closed_session_has_no_current_frontier_and_does_not_search_backward() -> None:
    source = RecordingSource(lambda start, end: bars_for(start, end))

    with pytest.raises(NoCurrentAnalyticalFrontierError, match="no current"):
        load_current_analytical_frontier(
            source,
            now=datetime(2026, 1, 10, 12, 7, tzinfo=UTC),
            warm_up_m15_bars=100,
        )

    assert source.calls == []


def test_warmup_uses_eligible_policy_across_weekly_closure() -> None:
    source = RecordingSource(lambda start, end: bars_for(start, end))
    now = datetime(2026, 1, 12, 10, 12, tzinfo=UTC)

    result = load_current_analytical_frontier(
        source,
        now=now,
        warm_up_m15_bars=100,
    )

    expected_start, expected_end = required_warmup_range(
        datetime(2026, 1, 12, 9, 45, tzinfo=UTC),
        datetime(2026, 1, 12, 10, 0, tzinfo=UTC),
        100,
    )
    assert source.calls == [(expected_start, expected_end)]
    assert result.requested_start == expected_start
    assert expected_start < datetime(2026, 1, 9, 22, 0, tzinfo=UTC)
    assert result.current_bar.start_time == datetime(2026, 1, 12, 9, 45, tzinfo=UTC)


def test_missing_bars_fail_closed() -> None:
    source = RecordingSource(lambda start, end: bars_for(start, end)[1:])

    with pytest.raises(AnalyticalFrontierDataError, match="missing"):
        load_current_analytical_frontier(source, now=moment(10, 17), warm_up_m15_bars=1)


def test_malformed_bars_fail_closed() -> None:
    def malformed(start: datetime, end: datetime) -> tuple[Bar, ...]:
        return cast(
            tuple[Bar, ...],
            bars_for(start, end) + (SimpleNamespace(start_time=start),),
        )

    source = RecordingSource(malformed)

    with pytest.raises(AnalyticalFrontierDataError, match="non-canonical"):
        load_current_analytical_frontier(source, now=moment(10, 17), warm_up_m15_bars=1)


def test_incomplete_duplicate_conflicting_and_unsupported_data_fail_closed() -> None:
    complete = bars_for(moment(10, 0), moment(10, 15))[0]

    class FixedSource:
        def __init__(
            self, bars: tuple[object, ...], incomplete: tuple[object, ...] = ()
        ):
            self.bars = bars
            self.incomplete = incomplete

        def fetch_native_m15(self, start: datetime, end: datetime) -> FetchResult:
            return FetchResult(cast(tuple[Bar, ...], self.bars), self.incomplete)

    with pytest.raises(AnalyticalFrontierDataError, match="incomplete"):
        load_current_analytical_frontier(
            FixedSource(
                (complete,), (SimpleNamespace(start_time=complete.start_time),)
            ),
            now=moment(10, 17),
            warm_up_m15_bars=0,
        )

    with pytest.raises(AnalyticalFrontierDataError, match="duplicate"):
        load_current_analytical_frontier(
            FixedSource((complete, complete)),
            now=moment(10, 17),
            warm_up_m15_bars=0,
        )

    conflicting = replace(complete, close=complete.close + Decimal("0.0001"))
    with pytest.raises(AnalyticalFrontierDataError, match="duplicate"):
        load_current_analytical_frontier(
            FixedSource((complete, conflicting)),
            now=moment(10, 17),
            warm_up_m15_bars=0,
        )

    with pytest.raises(AnalyticalFrontierDataError, match="contract"):
        load_current_analytical_frontier(
            FixedSource((bar(complete.start_time, component=PriceComponent.BID),)),
            now=moment(10, 17),
            warm_up_m15_bars=0,
        )


def test_native_m15_source_only_and_out_of_cutoff_bar_is_rejected() -> None:
    source = RecordingSource(lambda start, end: (bar(end),))

    with pytest.raises(AnalyticalFrontierDataError, match="outside the requested"):
        load_current_analytical_frontier(source, now=moment(10, 17), warm_up_m15_bars=0)

    assert source.calls == [(moment(10, 0), moment(10, 15))]
