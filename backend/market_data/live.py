"""Pure live-data frontier and PAPER entry eligibility contracts."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from backend.domain.market_data import (
    Bar,
    InputError,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.domain.strategy import (
    Direction,
    PendingEntryHandoff,
)


class LiveDataError(InputError):
    """A live observation cannot safely cross the PAPER data boundary."""


def _utc(value: datetime, name: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise LiveDataError(f"{name} must be timezone-aware UTC")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class SparseM1ExecutionObservation:
    """One complete native M1 interval containing both executable sides."""

    bid: Bar
    ask: Bar

    def __post_init__(self) -> None:
        for bar, component in (
            (self.bid, PriceComponent.BID),
            (self.ask, PriceComponent.ASK),
        ):
            if (
                type(bar) is not Bar
                or bar.timeframe is not Timeframe.M1
                or bar.price_component is not component
                or not bar.complete
            ):
                raise LiveDataError(
                    "sparse execution requires complete M1 BID/ASK bars"
                )
        if (
            self.bid.start_time != self.ask.start_time
            or self.bid.end_time != self.ask.end_time
        ):
            raise LiveDataError("sparse BID/ASK bars must share one interval")
        if self.bid.end_time != self.bid.start_time + timedelta(minutes=1):
            raise LiveDataError("M1 execution observation must span one minute")

    @property
    def start_time(self) -> datetime:
        return self.bid.start_time

    @property
    def end_time(self) -> datetime:
        return self.bid.end_time

    @property
    def bid_open(self) -> Decimal:
        return self.bid.open

    @property
    def ask_open(self) -> Decimal:
        return self.ask.open

    @property
    def bid_high(self) -> Decimal:
        return self.bid.high

    @property
    def bid_low(self) -> Decimal:
        return self.bid.low

    @property
    def ask_high(self) -> Decimal:
        return self.ask.high

    @property
    def ask_low(self) -> Decimal:
        return self.ask.low


def pair_sparse_m1_bars(
    bars: tuple[Bar, ...],
) -> tuple[SparseM1ExecutionObservation, ...]:
    """Pair only complete same-minute BID/ASK bars; never fabricate a side."""

    if type(bars) is not tuple:
        raise LiveDataError("live M1 bars must be a tuple")
    grouped: dict[datetime, dict[PriceComponent, Bar]] = {}
    for bar in bars:
        if type(bar) is not Bar or bar.timeframe is not Timeframe.M1:
            raise LiveDataError("live execution data must contain native M1 bars")
        sides = grouped.setdefault(bar.start_time, {})
        previous = sides.get(bar.price_component)
        if previous is not None and previous != bar:
            raise LiveDataError("conflicting duplicate M1 execution bar")
        sides[bar.price_component] = bar
    result: list[SparseM1ExecutionObservation] = []
    for start in sorted(grouped):
        sides = grouped[start]
        if PriceComponent.BID in sides and PriceComponent.ASK in sides:
            result.append(
                SparseM1ExecutionObservation(
                    sides[PriceComponent.BID], sides[PriceComponent.ASK]
                )
            )
    return tuple(result)


def analytical_bar_fingerprint(bar: Bar) -> str:
    """Return the stable identity of one immutable analytical observation."""

    if type(bar) is not Bar:
        raise LiveDataError("analytical input must be a canonical Bar")
    payload = json.dumps(
        bar.to_json(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def validate_completed_native_m15(bar: Bar, as_of: datetime) -> None:
    """Reject invalid live analytical provenance before Strategy evaluation."""

    as_of = _utc(as_of, "as_of")
    if (
        type(bar) is not Bar
        or bar.provider is not Provider.OANDA
        or bar.instrument is not Instrument.EUR_USD
        or bar.timeframe is not Timeframe.M15
        or bar.price_component is not PriceComponent.MID
        or not bar.complete
    ):
        raise LiveDataError(
            "live analytical input must be a native completed M15 MID bar"
        )
    _utc(bar.start_time, "bar.start_time")
    _utc(bar.end_time, "bar.end_time")
    if bar.end_time != bar.start_time + timedelta(minutes=15):
        raise LiveDataError("live M15 bar must span exactly fifteen minutes")
    if (
        bar.start_time.second
        or bar.start_time.microsecond
        or bar.start_time.minute % 15
    ):
        raise LiveDataError("live M15 bar must be UTC quarter-hour aligned")
    if bar.end_time > as_of:
        raise LiveDataError("M15 bar has not completed at the supplied frontier")


@dataclass(frozen=True, slots=True)
class CompletedM15Frontier:
    """Immutable durable-compatible frontier for exactly-once M15 evaluation."""

    last_completed_end: datetime | None = None
    last_bar_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.last_completed_end is not None:
            _utc(self.last_completed_end, "last_completed_end")
        if (self.last_completed_end is None) != (self.last_bar_fingerprint is None):
            raise LiveDataError(
                "completed M15 frontier and bar fingerprint must be present together"
            )
        if self.last_bar_fingerprint is not None and (
            len(self.last_bar_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.last_bar_fingerprint
            )
        ):
            raise LiveDataError("completed M15 fingerprint must be lowercase SHA-256")

    def accept(self, bar: Bar, as_of: datetime) -> "CompletedM15Frontier":
        validate_completed_native_m15(bar, as_of)
        fingerprint = analytical_bar_fingerprint(bar)
        if self.last_completed_end is None:
            return CompletedM15Frontier(bar.end_time, fingerprint)
        if bar.end_time < self.last_completed_end:
            return self
        if bar.end_time == self.last_completed_end:
            if fingerprint == self.last_bar_fingerprint:
                return self
            raise LiveDataError("conflicting duplicate completed M15 bar")
        if bar.end_time != self.last_completed_end + timedelta(minutes=15):
            raise LiveDataError("completed M15 bars must advance chronologically")
        return CompletedM15Frontier(bar.end_time, fingerprint)


class EntryObservationStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    FRONTIER_EQUAL = "FRONTIER_EQUAL"
    BEFORE_FRONTIER = "BEFORE_FRONTIER"
    EXPIRED = "EXPIRED"
    NOT_TRIGGERED = "NOT_TRIGGERED"


@dataclass(frozen=True, slots=True)
class EntryObservationEvaluation:
    status: EntryObservationStatus
    triggered: bool

    @property
    def eligible(self) -> bool:
        return self.status is EntryObservationStatus.ELIGIBLE


def is_execution_observation_eligible(
    observation: SparseM1ExecutionObservation, decision_time: datetime
) -> bool:
    """Strictly enforce start_time > decision_time; equality is ineligible."""

    if type(observation) is not SparseM1ExecutionObservation:
        raise LiveDataError("execution observation is invalid")
    return observation.start_time > _utc(decision_time, "decision_time")


def entry_triggered(
    direction: Direction,
    trigger_price: Decimal,
    observation: SparseM1ExecutionObservation,
) -> bool:
    if (
        type(direction) is not Direction
        or type(trigger_price) is not Decimal
        or type(observation) is not SparseM1ExecutionObservation
    ):
        raise LiveDataError("entry trigger inputs are invalid")
    if not trigger_price.is_finite() or trigger_price <= 0:
        raise LiveDataError("entry trigger must be positive and finite")
    if direction is Direction.LONG:
        return (
            observation.ask_open > trigger_price
            or observation.ask_high >= trigger_price
        )
    return (
        observation.bid_open < trigger_price
        or observation.bid_low <= trigger_price
    )


def evaluate_entry_observation(
    handoff: PendingEntryHandoff, observation: SparseM1ExecutionObservation
) -> EntryObservationEvaluation:
    """Apply the exact Experiment predicate to one post-decision M1 interval."""

    if type(handoff) is not PendingEntryHandoff:
        raise LiveDataError("pending handoff is invalid")
    if observation.start_time == handoff.decision_frontier:
        return EntryObservationEvaluation(
            EntryObservationStatus.FRONTIER_EQUAL,
            False,
        )
    if observation.start_time < handoff.decision_frontier:
        return EntryObservationEvaluation(
            EntryObservationStatus.BEFORE_FRONTIER,
            False,
        )
    if handoff.consumed_count >= handoff.eligibility_limit:
        return EntryObservationEvaluation(EntryObservationStatus.EXPIRED, False)
    triggered = entry_triggered(handoff.direction, handoff.trigger_price, observation)
    return EntryObservationEvaluation(
        (
            EntryObservationStatus.ELIGIBLE
            if triggered
            else EntryObservationStatus.NOT_TRIGGERED
        ),
        triggered,
    )


# Concise aliases for composition and tests.
is_entry_observation_eligible = is_execution_observation_eligible
evaluate_pending_entry = evaluate_entry_observation


__all__ = [
    "CompletedM15Frontier",
    "EntryObservationEvaluation",
    "EntryObservationStatus",
    "LiveDataError",
    "SparseM1ExecutionObservation",
    "entry_triggered",
    "evaluate_entry_observation",
    "evaluate_pending_entry",
    "is_entry_observation_eligible",
    "is_execution_observation_eligible",
    "pair_sparse_m1_bars",
    "validate_completed_native_m15",
]
