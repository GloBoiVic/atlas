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
    FINGERPRINT_SCHEMA_V2,
    GAP_POLICY_V1,
    NATIVE_M15_CONTRACT_V1,
    SESSION_POLICY,
    SNAPSHOT_SCHEMA_V2,
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
from .coverage import CoverageReport, diagnostic_payloads, validate_coverage
from .fingerprint import (
    bar_content_fingerprint,
    dataset_fingerprint,
    dataset_fingerprint_v2,
)
from .session_policy import EXPECTED_DATA, OANDA_EUR_USD_POLICY

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
    category: str
    code: str
    detail: str
    range_start: datetime
    range_end: datetime

    @property
    def message(self) -> str:
        return self.detail


def classify_failure(error: Exception) -> tuple[str, str, str]:
    """Return only stable, non-sensitive failure facts."""
    name = type(error).__name__.lower()
    module = type(error).__module__
    if "validation" in name or isinstance(error, ValueError):
        return "VALIDATION", "INVALID_MARKET_DATA", "Historical data failed validation."
    if "sqlalchemy" in module or "database" in name:
        return (
            "PERSISTENCE",
            "DATABASE_WRITE_FAILED",
            "Historical data could not be persisted.",
        )
    if "oanda" in module or name.startswith("oanda"):
        code = (
            "OANDA_AUTHORIZATION_FAILED" if "auth" in name else "OANDA_REQUEST_FAILED"
        )
        return (
            "MARKET_DATA",
            code,
            "The historical market-data provider request failed.",
        )
    return (
        "RUNTIME",
        "HISTORICAL_LOAD_FAILED",
        "Historical data load stopped unexpectedly.",
    )


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
    for item in ranges:
        cursor = item.start
        while cursor < item.end:
            if OANDA_EUR_USD_POLICY.classify_minute(cursor)[0] == EXPECTED_DATA:
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
        progress: Callable[[IngestionReport], None] | None = None,
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
                category, code, detail = classify_failure(error)
                failure = SourceFailure(category, code, detail, range_start, range_end)
                break
            counts[0] += applied.inserted
            counts[1] += applied.reactivated
            counts[2] += applied.unchanged
            committed.append((range_start, range_end))
            if progress:
                progress(
                    IngestionReport(
                        operation,
                        start,
                        end,
                        tuple(fetched),
                        tuple(committed),
                        counts[0],
                        counts[1],
                        counts[2],
                        tuple(sorted(incomplete)),
                        self._coverage(start, end),
                    )
                )
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

    def plan_missing(
        self, start: datetime, end: datetime
    ) -> tuple[tuple[datetime, datetime], ...]:
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
        return _coalesce_expected_ranges(missing)

    def load_missing(
        self,
        start: datetime,
        end: datetime,
        *,
        progress: Callable[[IngestionReport], None] | None = None,
    ) -> IngestionReport:
        ranges = self.plan_missing(start, end)
        return self._ingest("load_missing", start, end, ranges, progress)

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
                    # The session-policy identifier is the immutable semantic
                    # version.  A future rule change mints a new version;
                    # existing snapshots are never reinterpreted.
                    "policy_version": SESSION_POLICY,
                    "diagnostics": diagnostic_payloads(coverage)[0],
                    "diagnostics_truncated": diagnostic_payloads(coverage)[1],
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

    def create_snapshot_v2(
        self,
        start: datetime,
        end: datetime,
        *,
        analytical: Sequence[Bar],
        execution_components: tuple[PriceComponent, ...] = (
            PriceComponent.BID,
            PriceComponent.ASK,
        ),
    ) -> SnapshotReport:
        """Capture native M15 analysis and sparse current M1 execution facts."""
        _validate_range(start, end)
        self._check_frontier(end)
        # Coverage opens its own read transaction. Compute it before taking the
        # V2 mapping lock so PostgreSQL never sees a nested FOR UPDATE on the
        # same venue row from a second session.
        coverage = self._coverage(start, end)
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                rows = tuple(
                    session.scalars(
                        select(MarketBarModel)
                        .where(
                            MarketBarModel.venue_instrument_id == mapping_id,
                            MarketBarModel.resolution == "M1",
                            MarketBarModel.is_current.is_(True),
                            MarketBarModel.start_time >= start,
                            MarketBarModel.start_time < end,
                            MarketBarModel.price_component.in_(
                                [c.value for c in execution_components]
                            ),
                        )
                        .order_by(
                            MarketBarModel.start_time, MarketBarModel.price_component
                        )
                    ).all()
                )
                execution = tuple(
                    (
                        row,
                        Bar(
                            Instrument.EUR_USD,
                            Timeframe.M1,
                            PriceComponent(row.price_component),
                            row.start_time,
                            row.end_time,
                            row.open_price,
                            row.high_price,
                            row.low_price,
                            row.close_price,
                            volume=row.volume,
                        ),
                    )
                    for row in rows
                )
                ordered_analytical = tuple(
                    sorted(analytical, key=lambda b: b.start_time)
                )
                analytical_members = tuple(
                    {
                        "sequence": i,
                        "start_time": bar.start_time.isoformat(),
                        "end_time": bar.end_time.isoformat(),
                        "content_fingerprint": bar_content_fingerprint(bar),
                    }
                    for i, bar in enumerate(ordered_analytical, 1)
                )
                execution_members = tuple(
                    {
                        "sequence": i,
                        "market_bar_id": str(row.id),
                        "price_component": bar.price_component.value,
                        "start_time": bar.start_time.isoformat(),
                        "observation_fingerprint": bar_content_fingerprint(bar),
                    }
                    for i, (row, bar) in enumerate(execution, 1)
                )
                gaps: list[dict[str, object]] = []
                expected_m15 = set(
                    start + timedelta(minutes=15 * i)
                    for i in range(int((end - start).total_seconds() // 900))
                )
                for gap_start in sorted(
                    expected_m15 - {bar.start_time for bar in ordered_analytical}
                ):
                    gaps.append(
                        {
                            "start_time": gap_start,
                            "end_time": gap_start + timedelta(minutes=15),
                            "price_component": "MID",
                            "resolution": "M15",
                            "source": "OANDA",
                            "reason": "MISSING_NATIVE_COMPLETED_CANDLE",
                            "classification": "NON_BLOCKING",
                            "affected_state": None,
                            "affected_event": None,
                            "policy_version": GAP_POLICY_V1,
                            "blocked": False,
                        }
                    )
                metadata = {
                    "provider": "OANDA",
                    "instrument": "EUR/USD",
                    "coverage_start": start.isoformat(),
                    "coverage_end": end.isoformat(),
                    "native_resolution": "M15",
                    "analytical_contract": NATIVE_M15_CONTRACT_V1,
                    "gap_policy": GAP_POLICY_V1,
                }
                fingerprint = dataset_fingerprint_v2(
                    metadata=metadata,
                    analytical_members=analytical_members,
                    execution_members=execution_members,
                    gaps=gaps,
                )
                summary = {
                    "status": "VALID",
                    "policy_version": GAP_POLICY_V1,
                    "analytical_count": len(ordered_analytical),
                    "execution_count": len(execution),
                    "gap_count": len(gaps),
                    "analytical_contract": NATIVE_M15_CONTRACT_V1,
                }
                snapshot = DatasetSnapshot(
                    uuid4(),
                    VENUE,
                    Timeframe.M15,
                    (PriceComponent.MID,),
                    start,
                    end,
                    ALIGNMENT_CONVENTION,
                    SESSION_POLICY,
                    FINGERPRINT_SCHEMA_V2,
                    fingerprint,
                    summary,
                    self._clock(),
                    SNAPSHOT_SCHEMA_V2,
                )
                stored = self._snapshots.create_v2_validated(
                    session, snapshot, ordered_analytical, execution, gaps
                )
                return SnapshotReport(start, end, coverage, stored)
        finally:
            session.close()

    def load_v2(self, start: datetime, end: datetime):
        """Acquire both native products, then atomically create a V2 snapshot."""
        native = getattr(self._source, "fetch_native_m15", None)
        execution = getattr(self._source, "fetch_execution_m1", None)
        if native is None or execution is None:
            raise ValueError("source does not support Alternative A acquisition")
        native_result = native(start, end)
        execution_result = execution(start, end)
        if native_result.incomplete or execution_result.incomplete:
            raise ValueError("provider returned incomplete historical observations")
        self._apply(self._mapping_id(), execution_result)
        return self.create_snapshot_v2(start, end, analytical=native_result.bars)

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
                bars, _diagnostics = aggregate_m1_to_m15(
                    members,
                    component,
                    snapshot.coverage_start,
                    snapshot.coverage_end,
                )
                return tuple(bars)
        finally:
            session.close()

    def current_m15(
        self, start: datetime, end: datetime, component: PriceComponent
    ) -> tuple[Bar, ...]:
        """Plan warm-up from current canonical M1, before a snapshot exists.

        This is deliberately separate from ``derive_m15``: the latter must
        remain snapshot-membership-only.  The planner uses this read only to
        decide whether another historical provider window is needed; the
        final derivation still goes through the immutable snapshot.
        """
        _validate_range(start, end)
        if type(component) is not PriceComponent:
            raise ValueError("component must be a PriceComponent")
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                bars = self._repository.current_bars(
                    session, mapping_id, start, end, (component,)
                )
                derived, _diagnostics = aggregate_m1_to_m15(bars, component, start, end)
                return tuple(derived)
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
    "classify_failure",
]
