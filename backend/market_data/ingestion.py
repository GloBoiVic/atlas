"""Application orchestration for historical market data.

This module deliberately keeps provider I/O and database transactions in
separate steps.  Repositories own persistence details; the application layer
only coordinates canonical bars, coverage, and immutable snapshots.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.persistence.market_data_repository import (
    BarBatchItem,
    BarBatchResult,
    BarRange,
    DatasetSnapshotRepository,
    MarketDataRepository,
)
from backend.persistence.models import MarketBarModel

from .aggregation import aggregate_m1_to_m15
from .coverage import CoverageReport, validate_coverage
from .fingerprint import dataset_fingerprint

REQUIRED_COMPONENTS = (
    PriceComponent.ASK,
    PriceComponent.BID,
    PriceComponent.MID,
)
VENUE = VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")


class CoverageValidator(Protocol):
    def validate(
        self,
        start: datetime,
        end: datetime,
        bars: Sequence[Bar],
        required_components: tuple[PriceComponent, ...],
    ) -> CoverageReport: ...


class HistoricalFetchResult(Protocol):
    bars: tuple[Bar, ...]
    incomplete: Any


class HistoricalBarSource(Protocol):
    def fetch(self, start: datetime, end: datetime) -> HistoricalFetchResult: ...


@dataclass(frozen=True, slots=True)
class SourceFailure:
    message: str
    range_start: datetime
    range_end: datetime


@dataclass(frozen=True, slots=True)
class IngestionReport:
    operation: str
    requested_start: datetime
    requested_end: datetime
    fetched_ranges: tuple[tuple[datetime, datetime], ...]
    committed_ranges: tuple[tuple[datetime, datetime], ...]
    inserted: int
    reactivated: int
    unchanged: int
    incomplete_minutes: tuple[datetime, ...]
    coverage: CoverageReport
    failure: SourceFailure | None = None

    @property
    def valid(self) -> bool:
        return self.failure is None and self.coverage.valid


@dataclass(frozen=True, slots=True)
class CoverageInspection:
    requested_start: datetime
    requested_end: datetime
    coverage: CoverageReport

    @property
    def valid(self) -> bool:
        return self.coverage.valid


@dataclass(frozen=True, slots=True)
class SnapshotReport:
    requested_start: datetime
    requested_end: datetime
    coverage: CoverageReport
    snapshot: DatasetSnapshot | None
    failure: str | None = None

    @property
    def valid(self) -> bool:
        return self.snapshot is not None and self.failure is None


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_frontier() -> datetime:
    now = _default_clock()
    return now.replace(second=0, microsecond=0)


def _validate_range(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or start.utcoffset() != timedelta(0):
        raise ValueError("range start must be UTC")
    if end.tzinfo is None or end.utcoffset() != timedelta(0):
        raise ValueError("range end must be UTC")
    if start.second or start.microsecond or end.second or end.microsecond:
        raise ValueError("range must be minute-aligned")
    if end <= start:
        raise ValueError("range must be positive")


def _coalesce_expected_ranges(
    ranges: Sequence[BarRange],
) -> tuple[tuple[datetime, datetime], ...]:
    """Coalesce only adjacent missing session-open minutes."""
    minutes: set[datetime] = set()
    from .session_calendar import is_session_open_minute

    for item in ranges:
        cursor = item.start
        while cursor < item.end:
            if is_session_open_minute(cursor):
                minutes.add(cursor)
            cursor += timedelta(minutes=1)
    ordered = sorted(minutes)
    result: list[tuple[datetime, datetime]] = []
    for minute in ordered:
        if result and result[-1][1] == minute:
            result[-1] = (result[-1][0], minute + timedelta(minutes=1))
        else:
            result.append((minute, minute + timedelta(minutes=1)))
    return tuple(result)


class MarketDataService:
    """Coordinate historical loading, coverage inspection, and snapshots."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        source: HistoricalBarSource,
        *,
        clock: Callable[[], datetime] = _default_clock,
        frontier: Callable[[], datetime] = _default_frontier,
        repository: MarketDataRepository | None = None,
        snapshot_repository: DatasetSnapshotRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._source = source
        self._clock = clock
        self._frontier = frontier
        self._repository = repository or MarketDataRepository()
        self._snapshots = snapshot_repository or DatasetSnapshotRepository()

    def _check_frontier(self, end: datetime) -> None:
        frontier = self._frontier()
        if (
            frontier.tzinfo is None
            or frontier.utcoffset() != timedelta(0)
            or frontier.second
            or frontier.microsecond
        ):
            raise ValueError("frontier must be a UTC minute boundary")
        if end > frontier:
            raise ValueError("range end exceeds latest completed-minute frontier")

    def _mapping_id(self) -> UUID:
        session = self._session_factory()
        try:
            with session.begin():
                mapping = self._repository.ensure_initial_venue_instrument(
                    session, VENUE
                )
                session.flush()
                return mapping.id
        finally:
            session.close()

    def _coverage(self, start: datetime, end: datetime) -> CoverageReport:
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                bars = self._repository.current_bars(
                    session, mapping_id, start, end, REQUIRED_COMPONENTS
                )
                return validate_coverage(start, end, bars, REQUIRED_COMPONENTS)
        finally:
            session.close()

    def inspect_coverage(self, start: datetime, end: datetime) -> CoverageInspection:
        _validate_range(start, end)
        self._check_frontier(end)
        return CoverageInspection(start, end, self._coverage(start, end))

    def _apply(self, mapping_id: UUID, result: HistoricalFetchResult) -> BarBatchResult:
        session = self._session_factory()
        try:
            with session.begin():
                return self._repository.apply_bar_batch(
                    session,
                    mapping_id,
                    tuple(BarBatchItem(bar, self._clock()) for bar in result.bars),
                )
        finally:
            session.close()

    def _ingest(
        self,
        operation: str,
        start: datetime,
        end: datetime,
        ranges: Sequence[tuple[datetime, datetime]],
    ) -> IngestionReport:
        mapping_id = self._mapping_id()
        fetched: list[tuple[datetime, datetime]] = []
        committed: list[tuple[datetime, datetime]] = []
        incomplete: list[datetime] = []
        counts = [0, 0, 0]
        failure: SourceFailure | None = None
        for range_start, range_end in ranges:
            fetched.append((range_start, range_end))
            try:
                # The provider call is before opening the apply transaction.
                result = self._source.fetch(range_start, range_end)
                incomplete.extend(item.start_time for item in result.incomplete)
                applied = self._apply(mapping_id, result)
            except Exception as error:
                failure = SourceFailure(str(error), range_start, range_end)
                break
            counts[0] += applied.inserted
            counts[1] += applied.reactivated
            counts[2] += applied.unchanged
            committed.append((range_start, range_end))
        coverage = self._coverage(start, end)
        return IngestionReport(
            operation,
            start,
            end,
            tuple(fetched),
            tuple(committed),
            counts[0],
            counts[1],
            counts[2],
            tuple(sorted(incomplete)),
            coverage,
            failure,
        )

    def load_missing(self, start: datetime, end: datetime) -> IngestionReport:
        _validate_range(start, end)
        self._check_frontier(end)
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                missing = self._repository.missing_ranges(
                    session, mapping_id, start, end, REQUIRED_COMPONENTS
                )
        finally:
            session.close()
        return self._ingest(
            "load_missing", start, end, _coalesce_expected_ranges(missing)
        )

    def refresh_range(self, start: datetime, end: datetime) -> IngestionReport:
        _validate_range(start, end)
        self._check_frontier(end)
        return self._ingest("refresh_range", start, end, ((start, end),))

    def create_snapshot(self, start: datetime, end: datetime) -> SnapshotReport:
        _validate_range(start, end)
        self._check_frontier(end)
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                bars = self._repository.current_bars(
                    session, mapping_id, start, end, REQUIRED_COMPONENTS
                )
                coverage = validate_coverage(start, end, bars, REQUIRED_COMPONENTS)
                if not coverage.valid:
                    return SnapshotReport(
                        start, end, coverage, None, "coverage is invalid"
                    )
                fingerprint = dataset_fingerprint(
                    VENUE,
                    start,
                    end,
                    REQUIRED_COMPONENTS,
                    bars,
                    session_policy=SESSION_POLICY,
                    alignment_convention=ALIGNMENT_CONVENTION,
                )
                summary = {
                    "status": "VALID",
                    "expected_open_minutes": coverage.expected_open_minutes,
                    "expected_closure_minutes": coverage.expected_closure_minutes,
                    "member_minutes": coverage.member_minutes,
                    "bar_count": len(bars),
                    "unexpected_gap_count": len(coverage.missing),
                    "unexpected_observation_count": len(
                        coverage.unexpected_observations
                    )
                    + len(coverage.closure_anomalies),
                    "session_policy": SESSION_POLICY,
                }
                rows = tuple(
                    session.scalars(
                        select(MarketBarModel).where(
                            MarketBarModel.venue_instrument_id == mapping_id,
                            MarketBarModel.resolution == "M1",
                            MarketBarModel.is_current.is_(True),
                            MarketBarModel.start_time >= start,
                            MarketBarModel.start_time < end,
                            MarketBarModel.price_component.in_(
                                [component.value for component in REQUIRED_COMPONENTS]
                            ),
                        )
                    ).all()
                )
                snapshot = DatasetSnapshot(
                    uuid4(),
                    VENUE,
                    Timeframe.M1,
                    REQUIRED_COMPONENTS,
                    start,
                    end,
                    ALIGNMENT_CONVENTION,
                    SESSION_POLICY,
                    FINGERPRINT_SCHEMA,
                    fingerprint,
                    summary,
                    self._clock(),
                )
                stored = self._snapshots.create_validated(session, snapshot, rows)
                return SnapshotReport(start, end, coverage, stored)
        finally:
            session.close()

    def derive_m15(
        self, snapshot_fingerprint: str, component: PriceComponent
    ) -> tuple[Bar, ...]:
        """Derive M15 bars exclusively from the immutable snapshot membership.

        The membership read is intentionally the only source of M1 observations
        here.  In particular, this must not be replaced with a current-bar range
        query: a later provider correction belongs to a new snapshot.
        """
        if type(component) is not PriceComponent:
            raise ValueError("component must be a PriceComponent")
        session = self._session_factory()
        try:
            with session.begin():
                snapshot = self._snapshots.by_fingerprint(session, snapshot_fingerprint)
                if component not in snapshot.components:
                    raise ValueError("component is not present in snapshot")
                self._check_frontier(snapshot.coverage_end)
                members = self._snapshots.members(session, snapshot.id)
                return aggregate_m1_to_m15(
                    members,
                    component,
                    snapshot.coverage_start,
                    snapshot.coverage_end,
                )
        finally:
            session.close()


__all__ = [
    "CoverageInspection",
    "CoverageValidator",
    "HistoricalBarSource",
    "HistoricalFetchResult",
    "IngestionReport",
    "MarketDataService",
    "SnapshotReport",
    "SourceFailure",
]
