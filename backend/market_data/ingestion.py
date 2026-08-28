"""Application orchestration for historical market data.

This module deliberately keeps provider I/O and database transactions in
separate steps.  Repositories own persistence details; the application layer
only coordinates canonical bars, coverage, and immutable snapshots.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    FINGERPRINT_SCHEMA_V2,
    GAP_POLICY_V1,
    NATIVE_M1_EXECUTION_CONTRACT_V1,
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
    dataset_fingerprint_v2,  # noqa: F401 - benchmark instrumentation seam
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
    *,
    step: timedelta = timedelta(minutes=1),
) -> tuple[tuple[datetime, datetime], ...]:
    """Coalesce only adjacent missing session-open intervals."""
    result: list[tuple[datetime, datetime]] = []
    for item in ranges:
        item_start = item.start if hasattr(item, "start") else item[0]
        item_end = item.end if hasattr(item, "end") else item[1]
        cursor = item_start
        while cursor < item_end:
            if OANDA_EUR_USD_POLICY.classify_minute(cursor)[0] == EXPECTED_DATA:
                if result and result[-1][1] == cursor:
                    result[-1] = (result[-1][0], cursor + step)
                else:
                    result.append((cursor, cursor + step))
            cursor += step
    return tuple(result)


def _subtract_acquisition_windows(
    missing: Sequence[BarRange],
    acquired: Sequence[object],
) -> tuple[BarRange, ...]:
    """Remove the union of successful provider coverage from missing spans."""
    result: list[BarRange] = []
    for item in missing:
        item_start = item.start if hasattr(item, "start") else item[0]
        item_end = item.end if hasattr(item, "end") else item[1]
        item_components = getattr(item, "components", ())
        pieces = [(item_start, item_end)]
        for window in sorted(acquired, key=lambda value: value.start_time):
            next_pieces: list[tuple[datetime, datetime]] = []
            for left, right in pieces:
                if window.end_time <= left or window.start_time >= right:
                    next_pieces.append((left, right))
                    continue
                if left < window.start_time:
                    next_pieces.append((left, min(right, window.start_time)))
                if window.end_time < right:
                    next_pieces.append((max(left, window.end_time), right))
            pieces = next_pieces
        result.extend(
            BarRange(left, right, item_components)
            for left, right in pieces
            if left < right
        )
    return tuple(result)


def _uncovered_range(
    start: datetime, end: datetime, acquired: Iterable[object]
) -> tuple[tuple[datetime, datetime], ...]:
    """Subtract an ordered acquisition stream without retaining its history."""
    cursor = start
    merged_end = start
    for window in acquired:
        left = max(start, window.start_time)
        right = min(end, window.end_time)
        if right <= left:
            continue
        if left > merged_end:
            # The caller only needs the uncovered request pieces; the current
            # merged frontier is enough to emit each piece incrementally.
            yield_piece = (cursor, left)
            if yield_piece[0] < yield_piece[1]:
                yield yield_piece
            cursor = right
            merged_end = right
        else:
            if right > merged_end:
                merged_end = right
                cursor = max(cursor, merged_end)
    if cursor < end:
        yield (cursor, end)


def _acquisition_union(
    start: datetime, end: datetime, acquired: Iterable[object]
) -> tuple[tuple[datetime, datetime], ...]:
    """Return the canonical clipped union, retaining intervals not requests."""
    merged: list[tuple[datetime, datetime]] = []
    for window in acquired:
        left, right = max(start, window.start_time), min(end, window.end_time)
        if right <= left:
            continue
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return tuple(merged)


def _acquisition_coverage_digest(
    start: datetime, end: datetime, acquired: Iterable[object]
) -> tuple[int, str]:
    """Digest the ordered coverage union without retaining its intervals."""
    digest = sha256()
    count = 0
    frontier: tuple[datetime, datetime] | None = None
    for window in acquired:
        left, right = max(start, window.start_time), min(end, window.end_time)
        if right <= left:
            continue
        if frontier is not None and left <= frontier[1]:
            frontier = (frontier[0], max(frontier[1], right))
            continue
        if frontier is not None:
            digest.update(f"{frontier[0].isoformat()}|{frontier[1].isoformat()}\n".encode())
            count += 1
        frontier = (left, right)
    if frontier is not None:
        digest.update(f"{frontier[0].isoformat()}|{frontier[1].isoformat()}\n".encode())
        count += 1
    return count, digest.hexdigest()


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
                bars = self._repository.current_bars_stream(
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
        analytical: Iterable[Bar] | None,
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
        # V2 has two independent native products.  Do not use the legacy
        # three-component/M1 coverage validator here: it both admits the old
        # shared-range contract and cannot prove native M15 provenance.
        coverage = self._coverage_product(
            start, end, (PriceComponent.BID, PriceComponent.ASK), Timeframe.M1
        )
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                if analytical is None:
                    def analytical_source():
                        return self._repository.current_bars_stream(
                            session, mapping_id, start, end,
                            (PriceComponent.MID,), Timeframe.M15,
                        )
                else:
                    analytical_source = lambda: analytical
                row_stream = getattr(self._repository, "current_bar_rows_stream", None)
                if row_stream is None:
                    raise ValueError("V2 repository must provide ordered row streaming")
                execution = (
                    (row, Bar(
                        Instrument.EUR_USD, Timeframe.M1,
                        PriceComponent(row.price_component), row.start_time,
                        row.end_time, row.open_price, row.high_price, row.low_price,
                        row.close_price, volume=row.volume,
                    ))
                    for row in row_stream(
                        session, mapping_id, start, end, execution_components
                    )
                )
                if not coverage.execution_valid:
                    return SnapshotReport(
                        start,
                        end,
                        coverage,
                        None,
                        "execution coverage is invalid",
                    )
                metadata = {
                    "provider": "OANDA",
                    "instrument": "EUR/USD",
                    "coverage_start": start.isoformat(),
                    "coverage_end": end.isoformat(),
                    "native_resolution": "M15",
                    "analytical_contract": NATIVE_M15_CONTRACT_V1,
                    "execution_resolution": "M1",
                    "execution_components": ["BID", "ASK"],
                    "execution_contract": NATIVE_M1_EXECUTION_CONTRACT_V1,
                    "gap_policy": GAP_POLICY_V1,
                }
                acquired_method = getattr(self._repository, "acquired_windows", None)
                if acquired_method is None:
                    coverage_count, coverage_digest = 0, sha256(b"").hexdigest()
                else:
                    coverage_count, coverage_digest = _acquisition_coverage_digest(
                        start, end, acquired_method(
                            session, mapping_id, Timeframe.M1,
                            (PriceComponent.BID, PriceComponent.ASK), start, end,
                        )
                    )
                metadata["successful_execution_coverage_count"] = coverage_count
                metadata["successful_execution_coverage_digest"] = coverage_digest
                summary = {
                    "status": "VALID",
                    "policy_version": GAP_POLICY_V1,
                    "analytical_contract": NATIVE_M15_CONTRACT_V1,
                    "execution_observation_continuity": "SPARSE_ALLOWED",
                    "successful_execution_window_count": coverage_count,
                }
                # The append-only snapshot row must be born with its final
                # identity.  Build the digest from bounded, repeatable DB
                # streams before inserting memberships; the streams are then
                # opened again for the atomic membership insert.
                def execution_members():
                    rows = row_stream(
                        session, mapping_id, start, end, execution_components
                    )
                    for sequence, row in enumerate(rows, 1):
                        bar = Bar(
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
                        )
                        yield {
                            "sequence": sequence,
                            "market_bar_id": str(row.id),
                            "price_component": bar.price_component.value,
                            "start_time": bar.start_time.isoformat(),
                            "observation_fingerprint": bar_content_fingerprint(bar),
                        }

                def analytical_members():
                    for sequence, bar in enumerate(analytical_source(), 1):
                        yield {
                            "sequence": sequence,
                            "start_time": bar.start_time.isoformat(),
                            "end_time": bar.end_time.isoformat(),
                            "content_fingerprint": bar_content_fingerprint(bar),
                        }

                snapshot_fingerprint = dataset_fingerprint_v2(
                    metadata={
                        **metadata,
                        "successful_execution_coverage_count": coverage_count,
                        "successful_execution_coverage_digest": coverage_digest,
                    },
                    analytical_members=analytical_members(),
                    execution_members=execution_members(),
                    gaps=(),
                )
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
                    snapshot_fingerprint,
                    summary,
                    self._clock(),
                    SNAPSHOT_SCHEMA_V2,
                )
                stored = self._snapshots.create_v2_validated(
                    session, snapshot, analytical_source(), execution, None,
                    metadata=metadata,
                )
                return SnapshotReport(start, end, coverage, stored)
        finally:
            session.close()

    def _coverage_product(
        self,
        start: datetime,
        end: datetime,
        components: tuple[PriceComponent, ...],
        resolution: Timeframe,
    ) -> CoverageReport:
        """Validate one native product without mixing resolutions/components."""
        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                bars = self._repository.current_bars_stream(
                    session, mapping_id, start, end, components, resolution
                )
                return validate_coverage(start, end, bars, components)
        finally:
            session.close()

    def load_v2(
        self,
        start: datetime,
        end: datetime,
        *,
        progress: Callable[[IngestionReport], None] | None = None,
    ):
        """Acquire native products in missing-only, independently committed windows.

        Provider calls deliberately happen before ``_apply`` opens its short
        transaction.  Replanning on every invocation makes this operation safe
        after an interrupted process: durable coverage, rather than progress
        JSON, is the resume authority.
        """
        native = getattr(self._source, "fetch_native_m15", None)
        execution = getattr(self._source, "fetch_execution_m1", None)
        if native is None or execution is None:
            raise ValueError("source does not support Alternative A acquisition")
        mapping_id = self._mapping_id()

        def plans(resolution, components):
            session = self._session_factory()
            try:
                with session.begin():
                    acquired_method = getattr(
                        self._repository, "acquired_windows", None
                    )
                    if acquired_method is None or resolution is not Timeframe.M1:
                        yield from _coalesce_expected_ranges(
                            self._repository.missing_ranges(
                                session, mapping_id, start, end, components, resolution
                            ),
                            step=timedelta(
                                minutes=15 if resolution is Timeframe.M15 else 1
                            ),
                        )
                        return
                    acquired = acquired_method(
                        session, mapping_id, resolution, components, start, end
                    )
                    # Coverage is checked before the expensive observation scan.
                    # Only uncovered remainders consult current M1 rows; sparse
                    # acquired windows therefore make repeat planning O(windows),
                    # not O(calendar minutes).
                    remainder = _uncovered_range(start, end, acquired)
                    for left, right in remainder:
                        yield from _coalesce_expected_ranges(
                            self._repository.missing_ranges(
                                session, mapping_id, left, right, components, resolution
                            ),
                            step=timedelta(minutes=1),
                        )
            finally:
                session.close()

        totals = [0, 0, 0]
        # Progress is an O(1) notification.  Durable resume authority is the
        # observation table plus acquisition-window union, not this callback;
        # retaining the complete window history here made a full-year load grow
        # linearly with the number of provider requests.
        fetched_count = 0
        committed_count = 0

        def acquire(product, fetch, ranges):
            nonlocal fetched_count, committed_count
            for window in ranges:
                # No database transaction is held during this provider call.
                try:
                    result = fetch(*window)
                    if result.incomplete:
                        raise ValueError(
                            "provider returned incomplete historical observations"
                        )
                    applied = self._apply(mapping_id, result)
                except Exception:
                    recorder = getattr(
                        self._repository, "record_acquisition_window", None
                    )
                    if recorder is not None:
                        session = self._session_factory()
                        try:
                            with session.begin():
                                recorder(
                                    session,
                                    mapping_id,
                                    Timeframe.M15
                                    if product == "analytical"
                                    else Timeframe.M1,
                                    (PriceComponent.MID,)
                                    if product == "analytical"
                                    else (PriceComponent.BID, PriceComponent.ASK),
                                    window[0],
                                    window[1],
                                    "PROVIDER_FAILURE",
                                )
                        finally:
                            session.close()
                    raise
                recorder = getattr(self._repository, "record_acquisition_window", None)
                if recorder is not None:
                    session = self._session_factory()
                    try:
                        with session.begin():
                            recorder(
                                session,
                                mapping_id,
                                Timeframe.M15
                                if product == "analytical"
                                else Timeframe.M1,
                                (PriceComponent.MID,)
                                if product == "analytical"
                                else (PriceComponent.BID, PriceComponent.ASK),
                                window[0],
                                window[1],
                                "SUCCESS_EMPTY_OR_SPARSE",
                                len(result.bars),
                            )
                    finally:
                        session.close()
                fetched_count += 1
                committed_count += 1
                totals[0] += applied.inserted
                totals[1] += applied.reactivated
                totals[2] += applied.unchanged
                if progress:
                    progress(
                        SimpleNamespace(
                            operation="load_v2",
                            requested_start=start,
                            requested_end=end,
                            fetched_ranges=(),
                            committed_ranges=(),
                            inserted=totals[0],
                            reactivated=totals[1],
                            unchanged=totals[2],
                            incomplete_minutes=(),
                            coverage=None,
                            product=product,
                            window={
                                "start": window[0].isoformat(),
                                "end": window[1].isoformat(),
                                "fetched_count": fetched_count,
                                "committed_count": committed_count,
                            },
                        )
                    )

        native_ranges = plans(Timeframe.M15, (PriceComponent.MID,))
        execution_ranges = plans(Timeframe.M1, (PriceComponent.BID, PriceComponent.ASK))
        acquire("analytical", native, native_ranges)
        acquire("execution", execution, execution_ranges)

        # Snapshot construction consumes the persisted native M15 membership,
        # including work committed by an earlier attempt.
        return self.create_snapshot_v2(start, end, analytical=None)

    def load_v2_incremental(
        self,
        start: datetime,
        end: datetime,
        *,
        previous_snapshot_id: UUID,
        previous_start: datetime,
        progress: Callable[[IngestionReport], None] | None = None,
    ):
        """Extend a V2 snapshot without reacquiring its covered prefix.

        Native M15 is only available through snapshot membership, while execution
        observations are durable canonical M1 rows.  They are therefore planned
        independently and combined into a new snapshot; the old snapshot is
        never edited.
        """
        if not (start < previous_start <= end):
            raise ValueError("incremental load must add a positive prefix")
        native = getattr(self._source, "fetch_native_m15", None)
        execution = getattr(self._source, "fetch_execution_m1", None)
        if native is None or execution is None:
            raise ValueError("source does not support Alternative A acquisition")
        native_result = native(start, previous_start)
        if native_result.incomplete:
            raise ValueError("provider returned incomplete native observations")

        mapping_id = self._mapping_id()
        session = self._session_factory()
        try:
            with session.begin():
                execution_ranges = _coalesce_expected_ranges(
                    self._repository.missing_ranges(
                        session,
                        mapping_id,
                        start,
                        end,
                        (PriceComponent.BID, PriceComponent.ASK),
                    )
                )
                prior_analytical = self._snapshots.v2_analytical_members(
                    session, previous_snapshot_id
                )
        finally:
            session.close()

        fetched: list[tuple[datetime, datetime]] = []
        committed: list[tuple[datetime, datetime]] = []
        counts = [0, 0, 0]
        for range_start, range_end in execution_ranges:
            fetched.append((range_start, range_end))
            result = execution(range_start, range_end)
            if result.incomplete:
                raise ValueError("provider returned incomplete execution observations")
            applied = self._apply(mapping_id, result)
            counts[0] += applied.inserted
            counts[1] += applied.reactivated
            counts[2] += applied.unchanged
            committed.append((range_start, range_end))
            if progress:
                progress(
                    SimpleNamespace(
                        fetched_ranges=tuple(fetched),
                        committed_ranges=tuple(committed),
                        inserted=counts[0],
                        reactivated=counts[1],
                        unchanged=counts[2],
                        incomplete_minutes=(),
                        coverage=self._coverage(start, end),
                    )
                )
        analytical = tuple(
            sorted(
                (*native_result.bars, *prior_analytical),
                key=lambda bar: bar.start_time,
            )
        )
        return self.create_snapshot_v2(start, end, analytical=analytical)

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
                if snapshot.snapshot_schema == SNAPSHOT_SCHEMA_V2:
                    if component is not PriceComponent.MID:
                        raise ValueError("V2 analytical path supports native MID only")
                    return self._snapshots.v2_analytical_members(session, snapshot.id)
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
