"""Acquire one validated, current native analytical frontier for PAPER.

This module deliberately stops at canonical market data.  It does not resolve a
Strategy, own Strategy state, or interpret the resulting bars as executable
market facts.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.market_data.session_calendar import (
    eligible_m15_windows,
    required_warmup_range,
)

M15 = timedelta(minutes=15)


class AnalyticalFrontierError(ValueError):
    """Base error for a PAPER analytical-frontier read that cannot proceed."""


class NoCurrentAnalyticalFrontierError(AnalyticalFrontierError):
    """The immediately preceding calendar M15 window is not an open frontier."""


class AnalyticalFrontierDataError(AnalyticalFrontierError):
    """The provider result cannot prove the required analytical data set."""


class NativeM15FetchResult(Protocol):
    """The small provider-result shape required by this read-only seam."""

    @property
    def bars(self) -> Sequence[Bar]: ...

    @property
    def incomplete(self) -> Sequence[object]: ...


class NativeM15Source(Protocol):
    """A source that exposes provider-native completed M15 candles."""

    def fetch_native_m15(
        self, start: datetime, end: datetime
    ) -> NativeM15FetchResult: ...


@dataclass(frozen=True, slots=True)
class CurrentAnalyticalFrontier:
    """Validated context and one selected current analytical decision bar."""

    acquisition_cutoff: datetime
    requested_start: datetime
    requested_end: datetime
    bars: tuple[Bar, ...]
    current_bar: Bar
    eligible_windows: tuple[tuple[datetime, datetime], ...]
    previous_frontier: datetime | None

    @property
    def cutoff(self) -> datetime:
        """Compatibility spelling for the acquisition cutoff."""
        return self.acquisition_cutoff

    @property
    def candidate_bar(self) -> Bar:
        """The selected bar, using the terminology from the task boundary."""
        return self.current_bar

    @property
    def current_frontier(self) -> datetime:
        """The completed analytical frontier represented by ``current_bar``."""
        return self.current_bar.end_time

    @property
    def context_bars(self) -> tuple[Bar, ...]:
        """Ordered bars suitable for the Strategy's analytical context."""
        return self.bars


def _require_utc(value: datetime, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise AnalyticalFrontierError(f"{name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise AnalyticalFrontierError(f"{name} must be UTC")
    return value.astimezone(UTC)


def _cutoff(now: datetime) -> datetime:
    now = _require_utc(now, "now")
    return now.replace(
        minute=now.minute - now.minute % 15,
        second=0,
        microsecond=0,
    )


def _validate_incomplete(
    incomplete: Sequence[object],
    *,
    expected_starts: set[datetime],
) -> None:
    for observation in incomplete:
        start = getattr(observation, "start_time", None)
        if type(start) is not datetime or start.tzinfo is None:
            raise AnalyticalFrontierDataError(
                "incomplete provider observation has no valid UTC start"
            )
        if start.utcoffset() != timedelta(0):
            raise AnalyticalFrontierDataError(
                "incomplete provider observation is not UTC"
            )
        if start.astimezone(UTC) in expected_starts:
            raise AnalyticalFrontierDataError(
                "required analytical candle is incomplete"
            )


def _validate_bars(
    bars: Sequence[Bar],
    *,
    requested_start: datetime,
    cutoff: datetime,
    expected_windows: tuple[tuple[datetime, datetime], ...],
) -> tuple[Bar, ...]:
    expected_by_start = {start: end for start, end in expected_windows}
    seen_starts: set[datetime] = set()
    seen_ends: set[datetime] = set()
    validated: list[Bar] = []

    for bar in bars:
        if type(bar) is not Bar:
            raise AnalyticalFrontierDataError(
                "native analytical result contains a non-canonical bar"
            )
        if (
            bar.instrument is not Instrument.EUR_USD
            or bar.provider is not Provider.OANDA
            or bar.timeframe is not Timeframe.M15
            or bar.price_component is not PriceComponent.MID
            or bar.complete is not True
        ):
            raise AnalyticalFrontierDataError(
                "native analytical bar does not match the EUR/USD M15 MID contract"
            )
        if bar.start_time.utcoffset() != timedelta(
            0
        ) or bar.end_time.utcoffset() != timedelta(0):
            raise AnalyticalFrontierDataError(
                "native analytical bar timestamps must be UTC"
            )
        if bar.start_time < requested_start or bar.start_time >= cutoff:
            raise AnalyticalFrontierDataError(
                "native analytical result contains a bar outside the requested range"
            )
        if bar.end_time > cutoff:
            raise AnalyticalFrontierDataError(
                "native analytical result contains a bar beyond the acquisition cutoff"
            )
        expected_end = expected_by_start.get(bar.start_time.astimezone(UTC))
        if expected_end is None:
            raise AnalyticalFrontierDataError(
                "native analytical result contains an ineligible or unexpected bar"
            )
        if bar.end_time != expected_end:
            raise AnalyticalFrontierDataError(
                "native analytical bar interval does not match the session window"
            )
        if bar.start_time in seen_starts or bar.end_time in seen_ends:
            raise AnalyticalFrontierDataError("duplicate native analytical bar")
        seen_starts.add(bar.start_time)
        seen_ends.add(bar.end_time)
        validated.append(bar)

    missing = tuple(
        start for start, _end in expected_windows if start not in seen_starts
    )
    if missing:
        raise AnalyticalFrontierDataError(
            f"missing required analytical candle at {missing[0].isoformat()}"
        )
    return tuple(sorted(validated, key=lambda bar: bar.start_time))


def load_current_analytical_frontier(
    source: NativeM15Source,
    *,
    now: datetime,
    warm_up_m15_bars: int,
) -> CurrentAnalyticalFrontier:
    """Load one current completed native M15 frontier and its context.

    ``now`` limits what the source may return.  The returned current frontier is
    the preceding completed bar's end time, never ``now`` or the forming candle.
    ``warm_up_m15_bars`` is supplied by the caller so this seam remains
    independent of any particular StrategyVersion.
    """
    if type(warm_up_m15_bars) is not int or warm_up_m15_bars < 0:
        raise AnalyticalFrontierError("warm_up_m15_bars must be a non-negative integer")

    cutoff = _cutoff(now)
    candidate_start = cutoff - M15
    candidate_window = (candidate_start, cutoff)
    if eligible_m15_windows(*candidate_window) != (candidate_window,):
        raise NoCurrentAnalyticalFrontierError(
            "the immediately preceding M15 window has no current analytical frontier"
        )

    requested_start, requested_end = required_warmup_range(
        candidate_start,
        cutoff,
        warm_up_m15_bars,
    )
    expected_windows = eligible_m15_windows(requested_start, requested_end)

    try:
        result = source.fetch_native_m15(requested_start, requested_end)
        raw_bars = tuple(result.bars)
        incomplete = tuple(result.incomplete)
    except AnalyticalFrontierError:
        raise
    except (AttributeError, TypeError) as error:
        raise AnalyticalFrontierDataError(
            "native analytical source returned an invalid result"
        ) from error

    expected_starts = {start for start, _end in expected_windows}
    _validate_incomplete(incomplete, expected_starts=expected_starts)
    bars = _validate_bars(
        raw_bars,
        requested_start=requested_start,
        cutoff=cutoff,
        expected_windows=expected_windows,
    )
    current_bar = next(bar for bar in bars if bar.start_time == candidate_start)
    current_index = bars.index(current_bar)
    previous_frontier = bars[current_index - 1].end_time if current_index else None
    return CurrentAnalyticalFrontier(
        acquisition_cutoff=cutoff,
        requested_start=requested_start,
        requested_end=requested_end,
        bars=bars,
        current_bar=current_bar,
        eligible_windows=expected_windows,
        previous_frontier=previous_frontier,
    )


__all__ = [
    "AnalyticalFrontierDataError",
    "AnalyticalFrontierError",
    "CurrentAnalyticalFrontier",
    "NativeM15FetchResult",
    "NativeM15Source",
    "NoCurrentAnalyticalFrontierError",
    "load_current_analytical_frontier",
]
