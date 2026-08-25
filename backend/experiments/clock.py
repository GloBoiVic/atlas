"""The ordering boundary between historical decisions and execution data.

This module deliberately does not run a Strategy or submit an Order.  It only
turns immutable observations into an explicitly ordered sequence of frontiers.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.market_data.session_calendar import is_session_open_minute
from backend.persistence.market_data_repository import SnapshotBar


class ClockPhase(StrEnum):
    WARMUP = "WARMUP"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"


@dataclass(frozen=True, slots=True)
class M1Observation:
    """One complete, chronological executable-resolution observation."""

    start_time: datetime
    end_time: datetime
    bars: tuple[SnapshotBar, ...]
    sparse: bool = False

    def __post_init__(self) -> None:
        components = tuple(item.bar.price_component for item in self.bars)
        if self.sparse:
            if components != (PriceComponent.ASK, PriceComponent.BID):
                raise ValueError("sparse M1 observations require exactly ASK and BID")
        elif components != (
            PriceComponent.ASK,
            PriceComponent.BID,
            PriceComponent.MID,
        ):
            raise ValueError("M1 observations require exactly ASK, BID, and MID")
        if self.end_time != self.start_time + timedelta(minutes=1):
            raise ValueError("M1 observation must span exactly one minute")
        if any(
            item.bar.start_time != self.start_time or item.bar.end_time != self.end_time
            for item in self.bars
        ):
            raise ValueError("M1 observation bars must share one complete interval")


@dataclass(frozen=True, slots=True)
class ClockFrame:
    """One UTC M15 frontier, with decision and post-decision data separated."""

    frontier: datetime
    phase: ClockPhase
    completed_m1: tuple[SnapshotBar, ...]
    decision_bar: Bar
    executable_opens: tuple[SnapshotBar, ...]
    exposure_allowed: bool
    execution_observations: tuple[M1Observation, ...] = ()

    @property
    def warmup(self) -> bool:
        return self.phase is ClockPhase.WARMUP


def _utc_aligned(value: datetime, name: str) -> datetime:
    if (
        value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.second
        or value.microsecond
        or value.minute % 15
    ):
        raise ValueError(f"{name} must be UTC and M15-aligned")
    return value.astimezone(UTC)


class SimulationClock:
    """Produce the only observations a historical runner may consume.

    ``completed_m1`` is the minute ending at ``T`` and is available before the
    M15 decision.  ``executable_opens`` contains only BID/ASK observations
    beginning at ``T`` and is available after that decision.  Signal-bar data
    is therefore never returned as executable data.
    """

    def __init__(
        self,
        m1_bars: Sequence[SnapshotBar],
        m15_bars: Sequence[Bar],
        *,
        trading_start: datetime,
        trading_end: datetime,
        warmup_m15_bars: int = 0,
        sparse_execution: bool = False,
    ) -> None:
        self.trading_start = _utc_aligned(trading_start, "trading_start")
        self.trading_end = _utc_aligned(trading_end, "trading_end")
        if self.trading_end <= self.trading_start:
            raise ValueError("trading_end must be after trading_start")
        if type(warmup_m15_bars) is not int or warmup_m15_bars < 0:
            raise ValueError("warmup_m15_bars must be a non-negative integer")
        self.warmup_m15_bars = warmup_m15_bars
        self.sparse_execution = sparse_execution
        self._m1 = self._index_m1(m1_bars)
        self._m15 = self._index_m15(m15_bars)
        warmup = tuple(
            bar
            for end, bar in self._m15.items()
            if end <= self.trading_start
        )
        if len(warmup) < warmup_m15_bars:
            raise ValueError("insufficient completed M15 bars for warmup")
        self._warmup_ends = frozenset(
            bar.end_time for bar in warmup[-warmup_m15_bars:]
        ) if warmup_m15_bars else frozenset()

    @staticmethod
    def _index_m1(
        bars: Sequence[SnapshotBar],
    ) -> dict[datetime, tuple[SnapshotBar, ...]]:
        by_start: dict[datetime, list[SnapshotBar]] = {}
        for item in bars:
            bar = item.bar
            if (
                bar.instrument is not Instrument.EUR_USD
                or bar.provider is not Provider.OANDA
                or bar.timeframe is not Timeframe.M1
                or bar.price_component not in (
                    PriceComponent.MID,
                    PriceComponent.BID,
                    PriceComponent.ASK,
                )
            ):
                raise ValueError("SimulationClock requires OANDA EUR/USD M1 bars")
            if (
                bar.start_time.tzinfo is None
                or bar.start_time.utcoffset() != timedelta(0)
                or bar.start_time.second
                or bar.start_time.microsecond
                or bar.end_time != bar.start_time + timedelta(minutes=1)
            ):
                raise ValueError("M1 bars must be UTC, minute-aligned, one-minute bars")
            bucket = by_start.setdefault(bar.start_time, [])
            if any(
                existing.bar.price_component is bar.price_component
                for existing in bucket
            ):
                raise ValueError("duplicate M1 component at one frontier")
            bucket.append(item)
        return {
            start: tuple(sorted(items, key=lambda item: item.bar.price_component.value))
            for start, items in by_start.items()
        }

    @staticmethod
    def _index_m15(bars: Sequence[Bar]) -> dict[datetime, Bar]:
        result: dict[datetime, Bar] = {}
        for bar in bars:
            if (
                bar.instrument is not Instrument.EUR_USD
                or bar.provider is not Provider.OANDA
                or bar.timeframe is not Timeframe.M15
                or bar.price_component is not PriceComponent.MID
            ):
                raise ValueError("SimulationClock requires OANDA EUR/USD M15 MID bars")
            if (
                bar.end_time != bar.start_time + timedelta(minutes=15)
                or bar.start_time.tzinfo is None
                or bar.start_time.utcoffset() != timedelta(0)
                or bar.start_time.minute % 15
                or bar.start_time.second
                or bar.start_time.microsecond
            ):
                raise ValueError("M15 bars must be UTC, aligned, complete bars")
            if bar.end_time in result:
                raise ValueError("duplicate M15 decision frontier")
            result[bar.end_time] = bar
        return dict(sorted(result.items()))

    def observations(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Iterator[M1Observation]:
        """Yield complete M1 BID/ASK/MID observations without lookahead.

        The default range is the requested half-open trading period.  Scheduled
        session closures are absent by policy; an incomplete open-session minute
        is rejected rather than being turned into a synthetic observation.
        """
        start = self.trading_start if start is None else _minute_utc(start, "start")
        end = self.trading_end if end is None else _minute_utc(end, "end")
        if end <= start:
            raise ValueError("observation range must be positive")
        for minute in sorted(at for at in self._m1 if start <= at < end):
            if not is_session_open_minute(minute):
                continue
            items = self._m1[minute]
            by_component = {item.bar.price_component: item for item in items}
            required = {PriceComponent.ASK, PriceComponent.BID}
            if not self.sparse_execution:
                required.add(PriceComponent.MID)
            if set(by_component) != required:
                raise ValueError(f"incomplete M1 observation at {minute.isoformat()}")
            yield M1Observation(
                minute,
                minute + timedelta(minutes=1),
                tuple(by_component[component] for component in (
                    PriceComponent.ASK, PriceComponent.BID,
                    *(() if self.sparse_execution else (PriceComponent.MID,)),
                )), self.sparse_execution,
            )

    def frames(self) -> Iterator[ClockFrame]:
        """Yield warmup and trading frontiers in strictly increasing order."""
        for frontier, decision_bar in self._m15.items():
            if frontier > self.trading_end:
                break
            if frontier <= self.trading_start:
                if frontier not in self._warmup_ends:
                    continue
                phase = ClockPhase.WARMUP
                exposure_allowed = False
            elif frontier < self.trading_end:
                phase = ClockPhase.DECISION
                exposure_allowed = True
            else:
                continue
            completed = self._m1.get(frontier - timedelta(minutes=1), ())
            if not completed and not self.sparse_execution:
                # The NY daily break has no executable minute ending at the
                # frontier.  The derived M15 bar may still contain the
                # eligible minutes in that window; it is not a decision
                # frontier until a completed executable minute exists.
                if not is_session_open_minute(frontier - timedelta(minutes=1)):
                    continue
                raise ValueError(
                    f"missing completed M1 at frontier {frontier.isoformat()}"
                )
            opens = () if phase is ClockPhase.WARMUP else tuple(
                item
                for item in self._m1.get(frontier, ())
                if item.bar.price_component in (PriceComponent.BID, PriceComponent.ASK)
            )
            execution = ()
            if phase is ClockPhase.DECISION and (
                self.sparse_execution or is_session_open_minute(frontier)
            ):
                items = self._m1.get(frontier, ())
                if {item.bar.price_component for item in items} == {
                    PriceComponent.ASK,
                    PriceComponent.BID,
                    PriceComponent.MID,
                }:
                    execution = tuple(
                        self.observations(frontier, frontier + timedelta(minutes=1))
                    )
            yield ClockFrame(
                frontier,
                phase,
                completed,
                decision_bar,
                opens,
                exposure_allowed,
                execution,
            )

    def __iter__(self) -> Iterator[ClockFrame]:
        return self.frames()


def _minute_utc(value: datetime, name: str) -> datetime:
    if (
        value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.second
        or value.microsecond
    ):
        raise ValueError(f"{name} must be UTC and minute-aligned")
    return value.astimezone(UTC)


__all__ = ["ClockFrame", "ClockPhase", "M1Observation", "SimulationClock"]
