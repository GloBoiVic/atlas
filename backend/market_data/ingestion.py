"""Application orchestration for historical market data.

This module deliberately keeps provider I/O and database transactions in
separate steps.  Repositories own persistence details; the application layer
only coordinates canonical bars, coverage, and immutable snapshots.
"""

import platform
import resource
import time
from bisect import bisect_left
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
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

from .coverage import CoverageReport, validate_coverage
from .fingerprint import (
    bar_content_fingerprint,
    bar_content_fingerprint_from_fields,
    dataset_fingerprint_v2,  # noqa: F401 - benchmark instrumentation seam
)
from .session_policy import EXPECTED_DATA, OANDA_EUR_USD_POLICY

VENUE = VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")


class CoverageValidator(Protocol):
    def validate(
        self,
        start: datetime,
        end: datetime,
        bars: Sequence[Bar],
        required_components: tuple[PriceComponent, ...],
    ) -> CoverageReport: ...


class NativeFetchResult(Protocol):
    @property
    def bars(self) -> tuple[Bar, ...]: ...

    @property
    def incomplete(self) -> Sequence[object]: ...


class NativeHistoricalBarSource(Protocol):
    def fetch_native_m15(
        self, start: datetime, end: datetime
    ) -> NativeFetchResult: ...

    def fetch_execution_m1(
        self, start: datetime, end: datetime
    ) -> NativeFetchResult: ...


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
class SnapshotReport:
    requested_start: datetime
    requested_end: datetime
    coverage: CoverageReport
    snapshot: DatasetSnapshot | None
    failure: str | None = None
    telemetry: dict[str, Any] | None = None

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


_P95_BUCKET_UPPER_BOUNDS = (0, *tuple(2**index for index in range(17)), 2**16 + 1)


class _DurationStats:
    """Bounded integer-millisecond duration statistics."""

    __slots__ = ("count", "total_ms", "buckets")

    def __init__(self) -> None:
        self.count = 0
        self.total_ms = 0
        self.buckets = [0] * len(_P95_BUCKET_UPPER_BOUNDS)

    def add(self, elapsed_seconds: float) -> int:
        duration_ms = max(0, int(round(elapsed_seconds * 1000)))
        self.count += 1
        self.total_ms += duration_ms
        if duration_ms == 0:
            bucket = 0
        else:
            bucket = 1 + bisect_left(_P95_BUCKET_UPPER_BOUNDS[1:-1], duration_ms)
        self.buckets[bucket] += 1
        return duration_ms

    def report(self) -> dict[str, int | None]:
        if not self.count:
            return {
                "count": 0,
                "elapsed_ms": 0,
                "average_ms": None,
                "p95_ms": None,
            }
        rank = max(1, (95 * self.count + 99) // 100)
        seen = 0
        for bucket, count in enumerate(self.buckets):
            seen += count
            if seen >= rank:
                p95 = _P95_BUCKET_UPPER_BOUNDS[bucket]
                break
        else:  # pragma: no cover - every observation enters a bucket
            p95 = _P95_BUCKET_UPPER_BOUNDS[-1]
        return {
            "count": self.count,
            "elapsed_ms": self.total_ms,
            "average_ms": self.total_ms // self.count,
            "p95_ms": p95,
        }


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Darwin reports bytes; Linux and the other supported Unix platforms report
    # KiB.  The telemetry contract is host-normalized bytes.
    return value if platform.system() == "Darwin" else value * 1024


class _V2Telemetry:
    """In-process bounded metrics collector for one active V2 load segment."""

    __slots__ = (
        "started",
        "baseline_rss",
        "peak_rss",
        "provider",
        "persistence",
        "inserted_rows",
        "planning_ms",
        "validation_ms",
        "snapshot_ms",
        "fingerprint_ms",
        "membership_rows",
        "membership_batches",
        "analytical_rows",
        "execution_rows",
        "gap_rows",
    )

    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.baseline_rss = _rss_bytes()
        self.peak_rss = self.baseline_rss
        self.provider = {key: _DurationStats() for key in ("m15", "m1")}
        self.persistence = {key: _DurationStats() for key in ("m15", "m1")}
        self.inserted_rows = {key: 0 for key in ("m15", "m1")}
        self.planning_ms = 0
        self.validation_ms = 0
        self.snapshot_ms = 0
        self.fingerprint_ms = 0
        self.membership_rows = 0
        self.membership_batches = 0
        self.analytical_rows = 0
        self.execution_rows = 0
        self.gap_rows = 0

    def sample(self) -> None:
        self.peak_rss = max(self.peak_rss, _rss_bytes())

    def record(self, stream: dict[str, _DurationStats], key: str, began: float) -> None:
        stream[key].add(time.perf_counter() - began)
        self.sample()

    def report(
        self,
        *,
        expected: dict[str, int],
        completed: dict[str, int],
        planning_ms: int,
        validation_ms: int,
        snapshot_ms: int,
        fingerprint_ms: int,
        valid: bool = True,
    ) -> dict[str, Any]:
        self.sample()
        persistence = {}
        for key in ("m15", "m1"):
            metric = self.persistence[key].report()
            seconds = metric["elapsed_ms"] / 1000
            inserted = self.inserted_rows[key]
            metric.update(
                batches=metric.pop("count"),
                inserted_rows=inserted,
                rows_per_second=(inserted / seconds if inserted and seconds else None),
            )
            persistence[key] = metric
        provider = {
            key: {
                "calls": self.provider[key].count,
                "elapsed_ms": self.provider[key].total_ms,
                "average_ms": self.provider[key].report()["average_ms"],
                "p95_ms": self.provider[key].report()["p95_ms"],
            }
            for key in ("m15", "m1")
        }
        total_elapsed_ms = max(
            0, int(round((time.perf_counter() - self.started) * 1000))
        )
        return {
            "schema": "ATLAS_HISTORICAL_TELEMETRY_V1",
            "expected_requests": {key: int(expected[key]) for key in ("m15", "m1")},
            "completed_requests": {key: int(completed[key]) for key in ("m15", "m1")},
            "timing": {
                "planning": {"elapsed_ms": planning_ms},
                "provider": provider,
                "persistence": persistence,
                "validation": {"elapsed_ms": validation_ms, "valid": valid},
                "snapshot_membership": {
                    "elapsed_ms": snapshot_ms,
                    "rows": self.membership_rows,
                    "analytical_rows": self.analytical_rows,
                    "execution_rows": self.execution_rows,
                    "gap_rows": self.gap_rows,
                    "batches": self.membership_batches,
                },
                "fingerprinting": {
                    "elapsed_ms": fingerprint_ms,
                    "records_hashed": self.membership_rows,
                    "analytical_rows": self.analytical_rows,
                    "execution_rows": self.execution_rows,
                    "gap_rows": self.gap_rows,
                },
                "total_elapsed_ms": total_elapsed_ms,
                "p95_method": "fixed_log2_ms_v1",
            },
            "rss": {
                "baseline_bytes": self.baseline_rss,
                "peak_bytes": max(self.baseline_rss, self.peak_rss),
                "delta_bytes": max(0, self.peak_rss - self.baseline_rss),
            },
        }


class V2Progress:
    """Strict, redacted progress notification matching architecture section 11."""

    __slots__ = ("_payload", "product", "window", "telemetry")

    def __init__(
        self,
        payload: dict[str, Any],
        *,
        product: str | None = None,
        window: dict[str, Any] | None = None,
        telemetry: dict[str, Any] | None = None,
    ) -> None:
        self._payload = payload
        self.product = product
        self.window = window
        self.telemetry = telemetry

    def to_payload(self) -> dict[str, Any]:
        return dict(self._payload)

    @property
    def operation(self) -> str:
        return "load_v2"

    @property
    def requested_start(self):
        return None

    @property
    def requested_end(self):
        return None

    @property
    def inserted(self) -> int:
        return int(self._payload.get("inserted_rows", 0))

    @property
    def reactivated(self) -> int:
        return int(self._payload.get("reactivated_rows", 0))

    @property
    def unchanged(self) -> int:
        return int(self._payload.get("unchanged_rows", 0))

    @property
    def incomplete_minutes(self) -> tuple[datetime, ...]:
        return ()

    @property
    def coverage(self):
        return None

    @property
    def fetched_ranges(self) -> tuple[tuple[datetime, datetime], ...]:
        return ()

    @property
    def committed_ranges(self) -> tuple[tuple[datetime, datetime], ...]:
        return ()


def _coalesce_expected_ranges(
    ranges: Iterable[BarRange],
    *,
    step: timedelta = timedelta(minutes=1),
) -> Iterable[tuple[datetime, datetime]]:
    """Coalesce expected missing spans and split only at the OANDA bound.

    Session closures belong to expected-observation validation.  They are not
    provider range boundaries: one calendar request may bridge a closure.  A
    remainder containing no expected observation is not provider work.
    """
    bound_minutes = 60_000 if step == timedelta(minutes=15) else 4_000
    current_start: datetime | None = None
    current_end: datetime | None = None
    current_components = None
    current_has_expected = False

    def has_expected_observation(start: datetime, end: datetime) -> bool:
        cursor = start
        constituent_minutes = 15 if step == timedelta(minutes=15) else 1
        while cursor < end:
            if all(
                OANDA_EUR_USD_POLICY.classify_minute(
                    cursor + timedelta(minutes=offset)
                )[0]
                == EXPECTED_DATA
                for offset in range(constituent_minutes)
            ):
                return True
            cursor += step
        return False

    def bounded(start: datetime, end: datetime):
        bound = timedelta(minutes=bound_minutes)
        cursor = start
        while cursor < end:
            right = min(cursor + bound, end)
            yield cursor, right
            cursor = right

    for item in ranges:
        item_start = item.start if hasattr(item, "start") else item[0]
        item_end = item.end if hasattr(item, "end") else item[1]
        item_components = getattr(item, "components", ())
        if (
            current_start is not None
            and current_end == item_start
            and current_components == item_components
        ):
            current_end = item_end
            if not current_has_expected:
                current_has_expected = has_expected_observation(item_start, item_end)
            continue
        if current_start is not None and current_has_expected:
            yield from bounded(current_start, current_end)
        current_start, current_end, current_components, current_has_expected = (
            item_start,
            item_end,
            item_components,
            has_expected_observation(item_start, item_end),
        )
    if current_start is not None and current_has_expected:
        yield from bounded(current_start, current_end)


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


def _v2_gap_members(
    start: datetime, end: datetime, analytical: Iterable[Bar]
) -> Iterable[dict[str, object]]:
    """Yield the canonical V2 gap facts without retaining the native stream."""
    cursor = start
    for member in analytical:
        while cursor < member.start_time:
            yield {
                "start_time": cursor,
                "end_time": cursor + timedelta(minutes=15),
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
            cursor += timedelta(minutes=15)
        cursor = member.start_time + timedelta(minutes=15)
    while cursor < end:
        yield {
            "start_time": cursor,
            "end_time": cursor + timedelta(minutes=15),
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
        cursor += timedelta(minutes=15)


class MarketDataService:
    """Coordinate historical loading, coverage inspection, and snapshots."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        source: NativeHistoricalBarSource,
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

    def _apply(
        self,
        mapping_id: UUID,
        result: NativeFetchResult,
        session: Session | None = None,
    ) -> BarBatchResult:
        if session is not None:
            return self._repository.apply_bar_batch(
                session,
                mapping_id,
                tuple(BarBatchItem(bar, self._clock()) for bar in result.bars),
            )
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

    def _apply_and_record_outcome(
        self,
        mapping_id: UUID,
        result: NativeFetchResult,
        resolution: Timeframe,
        components: tuple[PriceComponent, ...],
        window: tuple[datetime, datetime],
        returned_count: int,
    ) -> BarBatchResult:
        """Commit canonical rows and successful coverage as one durable fact."""
        recorder = getattr(self._repository, "record_acquisition_window", None)
        if recorder is None:
            # Keep the narrow seam usable by repositories predating acquisition
            # coverage. The authoritative repository always has the recorder.
            return self._apply(mapping_id, result)

        session = self._session_factory()
        try:
            # Provider I/O has completed before this short transaction begins.
            with session.begin():
                applied = self._apply(mapping_id, result, session)
                recorder(
                    session,
                    mapping_id,
                    resolution,
                    components,
                    window[0],
                    window[1],
                    "SUCCESS_EMPTY_OR_SPARSE",
                    returned_count,
                )
                return applied
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
        _telemetry: _V2Telemetry | None = None,
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
        validation_started = time.perf_counter()
        coverage = self._coverage_product(
            start, end, (PriceComponent.BID, PriceComponent.ASK), Timeframe.M1
        )
        validation_ms = max(
            0, int(round((time.perf_counter() - validation_started) * 1000))
        )
        if _telemetry is not None:
            _telemetry.validation_ms = validation_ms
            _telemetry.sample()
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
                    def analytical_source():
                        return analytical
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
                        telemetry=None,
                    )
                metadata: dict[str, object] = {
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
                        yield {
                            "sequence": sequence,
                            "market_bar_id": str(row.id),
                            "price_component": row.price_component,
                            "start_time": row.start_time.isoformat(),
                            "observation_fingerprint": (
                                bar_content_fingerprint_from_fields(
                                    instrument=Instrument.EUR_USD.value,
                                    provider=Provider.OANDA.value,
                                    timeframe=Timeframe.M1.value,
                                    price_component=row.price_component,
                                    start_time=row.start_time,
                                    end_time=row.end_time,
                                    open_price=row.open_price,
                                    high_price=row.high_price,
                                    low_price=row.low_price,
                                    close_price=row.close_price,
                                    volume=row.volume,
                                )
                            ),
                        }

                def analytical_members():
                    for sequence, bar in enumerate(analytical_source(), 1):
                        yield {
                            "sequence": sequence,
                            "start_time": bar.start_time.isoformat(),
                            "end_time": bar.end_time.isoformat(),
                            "content_fingerprint": bar_content_fingerprint(bar),
                        }

                def gap_members():
                    yield from _v2_gap_members(start, end, analytical_source())

                fingerprint_started = time.perf_counter()
                snapshot_fingerprint = dataset_fingerprint_v2(
                    metadata={
                        **metadata,
                        "successful_execution_coverage_count": coverage_count,
                        "successful_execution_coverage_digest": coverage_digest,
                    },
                    analytical_members=analytical_members(),
                    execution_members=execution_members(),
                    gaps=gap_members(),
                )
                fingerprint_ms = max(
                    0, int(round((time.perf_counter() - fingerprint_started) * 1000))
                )
                if _telemetry is not None:
                    _telemetry.fingerprint_ms = fingerprint_ms
                    _telemetry.sample()
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
                membership_started = time.perf_counter()
                stored = self._snapshots.create_v2_validated(
                    session, snapshot, analytical_source(), execution, None,
                    metadata=metadata,
                )
                membership_ms = max(
                    0, int(round((time.perf_counter() - membership_started) * 1000))
                )
                if _telemetry is not None:
                    _telemetry.snapshot_ms = membership_ms
                    finalization = getattr(
                        self._snapshots, "last_v2_finalization_telemetry", {}
                    )
                    _telemetry.analytical_rows = int(
                        finalization.get("analytical_rows", 0)
                    )
                    _telemetry.execution_rows = int(
                        finalization.get("execution_rows", 0)
                    )
                    _telemetry.gap_rows = int(finalization.get("gap_rows", 0))
                    _telemetry.membership_rows = (
                        _telemetry.analytical_rows
                        + _telemetry.execution_rows
                        + _telemetry.gap_rows
                    )
                    _telemetry.membership_batches = sum(
                        int(finalization.get(f"{key}_batches", 0))
                        for key in ("analytical", "execution", "gap")
                    )
                    _telemetry.sample()
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
        progress: Callable[[Any], None] | None = None,
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
        telemetry = _V2Telemetry()
        mapping_id = self._mapping_id()

        def plans(
            resolution: Timeframe,
            components: tuple[PriceComponent, ...],
        ) -> Iterator[tuple[datetime, datetime]]:
            step = timedelta(minutes=15 if resolution is Timeframe.M15 else 1)
            scan_start = start
            while scan_start < end:
                session = self._session_factory()
                next_window = None
                try:
                    with session.begin():
                        acquired_method = getattr(
                            self._repository, "acquired_windows", None
                        )
                        if acquired_method is None:
                            candidate = _coalesce_expected_ranges(
                                self._repository.missing_ranges(
                                    session,
                                    mapping_id,
                                    scan_start,
                                    end,
                                    components,
                                    resolution,
                                ),
                                step=step,
                            )
                            next_window = next(candidate, None)
                        else:
                            acquired = acquired_method(
                                session,
                                mapping_id,
                                resolution,
                                components,
                                scan_start,
                                end,
                            )
                            # Coverage is checked before the expensive
                            # observation scan. Only uncovered remainders
                            # consult current canonical rows; sparse acquired
                            # windows therefore make repeat planning O(windows),
                            # not O(calendar minutes).
                            for left, right in _uncovered_range(
                                scan_start, end, acquired
                            ):
                                candidate = _coalesce_expected_ranges(
                                    self._repository.missing_ranges(
                                        session,
                                        mapping_id,
                                        left,
                                        right,
                                        components,
                                        resolution,
                                    ),
                                    step=step,
                                )
                                next_window = next(candidate, None)
                                if next_window is not None:
                                    break
                finally:
                    session.close()
                if next_window is None:
                    return
                # This transaction is closed before the planned provider window
                # is yielded to acquire().
                yield next_window
                scan_start = next_window[1]

        totals = [0, 0, 0]
        completed = {"m15": 0, "m1": 0}
        product_totals: dict[str, int] = {}
        planning_started = telemetry.started
        # Count both deterministic generators before issuing either provider
        # call.  Replaying the generators keeps planning bounded to one DB
        # frontier rather than retaining a request-sized range collection.
        for key, resolution, components in (
            ("m15", Timeframe.M15, (PriceComponent.MID,)),
            ("m1", Timeframe.M1, (PriceComponent.BID, PriceComponent.ASK)),
        ):
            product_totals[key] = sum(1 for _window in plans(resolution, components))
        telemetry.planning_ms = max(
            0, int(round((time.perf_counter() - planning_started) * 1000))
        )
        telemetry.sample()

        def progress_payload(
            phase: str,
            *,
            product: str | None = None,
            window: dict[str, str] | None = None,
            elapsed_ms: int | None = None,
            rows: int | None = None,
            batches: int | None = None,
        ) -> V2Progress:
            products = {
                key: {
                    "expected_requests": product_totals[key],
                    "completed_requests": completed[key],
                }
                for key in ("m15", "m1")
            }
            if phase == "PLANNING":
                for key in products:
                    products[key].update(
                        already_covered_window_count=0,
                        uncovered_span_count=product_totals[key],
                        planning_elapsed_ms=telemetry.planning_ms,
                    )
            payload: dict[str, Any] = {
                "schema": "ATLAS_HISTORICAL_PROGRESS_V1",
                "phase": phase,
                "unit": "provider_request",
                "completed_units": dict(completed),
                "total_units": dict(product_totals),
                "products": products,
            }
            if phase == "ACQUIRING":
                payload.update(
                    current_product=product,
                    provider_calls_total=telemetry.provider[product].count
                    if product
                    else 0,
                    inserted_rows=totals[0],
                    reactivated_rows=totals[1],
                    unchanged_rows=totals[2],
                    latest_window=window,
                )
            elif phase != "PLANNING":
                payload.update(
                    elapsed_ms=elapsed_ms or 0,
                    rows=rows or 0,
                    batches=batches or 0,
                )
            return V2Progress(
                payload, product=product, window=window
            )

        if progress:
            progress(progress_payload("PLANNING"))

        def acquire(
            product: str,
            fetch: Callable[[datetime, datetime], NativeFetchResult],
            resolution: Timeframe,
            components: tuple[PriceComponent, ...],
            ranges: Iterator[tuple[datetime, datetime]],
        ) -> None:
            def record_outcome(
                window: tuple[datetime, datetime],
                outcome: str,
                returned_count: int = 0,
            ) -> None:
                recorder = getattr(self._repository, "record_acquisition_window", None)
                if recorder is None:
                    return
                session = self._session_factory()
                try:
                    with session.begin():
                        recorder(
                            session,
                            mapping_id,
                            resolution,
                            components,
                            window[0],
                            window[1],
                            outcome,
                            returned_count,
                        )
                finally:
                    session.close()

            for window in ranges:
                # No database transaction is held during this provider call.
                provider_started = time.perf_counter()
                try:
                    result = fetch(*window)
                except Exception:
                    telemetry.record(telemetry.provider, product, provider_started)
                    record_outcome(window, "PROVIDER_FAILURE")
                    raise
                telemetry.record(telemetry.provider, product, provider_started)
                if result.incomplete:
                    record_outcome(window, "PROVIDER_FAILURE")
                    raise ValueError(
                        "provider returned incomplete historical observations"
                    )
                persistence_started = time.perf_counter()
                try:
                    applied = self._apply_and_record_outcome(
                        mapping_id,
                        result,
                        resolution,
                        components,
                        window,
                        len(result.bars),
                    )
                except Exception:
                    record_outcome(window, "PROVIDER_FAILURE")
                    raise
                finally:
                    telemetry.record(
                        telemetry.persistence, product, persistence_started
                    )
                telemetry.inserted_rows[product] += applied.inserted
                totals[0] += applied.inserted
                totals[1] += applied.reactivated
                totals[2] += applied.unchanged
                # A request becomes completed only after both canonical rows and
                # its durable acquisition-window outcome are committed.
                completed[product] += 1
                if progress:
                    bounded_window = {
                        "start": window[0].isoformat(),
                        "end": window[1].isoformat(),
                    }
                    progress(
                        progress_payload(
                            "ACQUIRING",
                            product=product,
                            window=bounded_window,
                        )
                    )
                telemetry.sample()

        try:
            acquire(
                "m15", native, Timeframe.M15, (PriceComponent.MID,),
                plans(Timeframe.M15, (PriceComponent.MID,)),
            )
            acquire(
                "m1", execution, Timeframe.M1,
                (PriceComponent.BID, PriceComponent.ASK),
                plans(Timeframe.M1, (PriceComponent.BID, PriceComponent.ASK)),
            )
        except Exception:
            if progress:
                failed = progress_payload("FAILED")
                failed.telemetry = telemetry.report(
                    expected=product_totals,
                    completed=completed,
                    planning_ms=telemetry.planning_ms,
                    validation_ms=telemetry.validation_ms,
                    snapshot_ms=telemetry.snapshot_ms,
                    fingerprint_ms=telemetry.fingerprint_ms,
                    valid=False,
                )
                progress(failed)
            raise

        # Snapshot construction consumes the persisted native M15 membership,
        # including work committed by an earlier attempt.
        try:
            snapshot_report = self.create_snapshot_v2(
                start, end, analytical=None, _telemetry=telemetry
            )
        except Exception:
            if progress:
                failed = progress_payload("FAILED")
                failed.telemetry = telemetry.report(
                    expected=product_totals,
                    completed=completed,
                    planning_ms=telemetry.planning_ms,
                    validation_ms=telemetry.validation_ms,
                    snapshot_ms=telemetry.snapshot_ms,
                    fingerprint_ms=telemetry.fingerprint_ms,
                    valid=False,
                )
                progress(failed)
            raise
        if not isinstance(snapshot_report, SnapshotReport):
            return snapshot_report
        if progress:
            for phase, elapsed, rows, batches in (
                ("VALIDATING", telemetry.validation_ms, 0, 0),
                (
                    "SNAPSHOT_MEMBERSHIP",
                    telemetry.snapshot_ms,
                    telemetry.membership_rows,
                    telemetry.membership_batches,
                ),
                (
                    "FINGERPRINTING",
                    telemetry.fingerprint_ms,
                    telemetry.membership_rows,
                    0,
                ),
                ("FINALIZING", 0, 0, 0),
            ):
                progress(
                    progress_payload(
                        phase, elapsed_ms=elapsed, rows=rows, batches=batches
                    )
                )
            terminal_telemetry = telemetry.report(
                expected=product_totals,
                completed=completed,
                planning_ms=telemetry.planning_ms,
                validation_ms=telemetry.validation_ms,
                snapshot_ms=telemetry.snapshot_ms,
                fingerprint_ms=telemetry.fingerprint_ms,
                valid=snapshot_report.valid,
            )
            snapshot_report = replace(snapshot_report, telemetry=terminal_telemetry)
            completed_report = progress_payload(
                "COMPLETED",
                elapsed_ms=telemetry.snapshot_ms,
                rows=telemetry.membership_rows,
                batches=telemetry.membership_batches,
            )
            completed_report.telemetry = terminal_telemetry
            progress(completed_report)
        else:
            snapshot_report = replace(snapshot_report, telemetry=telemetry.report(
                expected=product_totals,
                completed=completed,
                planning_ms=telemetry.planning_ms,
                validation_ms=telemetry.validation_ms,
                snapshot_ms=telemetry.snapshot_ms,
                fingerprint_ms=telemetry.fingerprint_ms,
                valid=snapshot_report.valid,
            ))
        return snapshot_report

__all__ = [
    "CoverageValidator",
    "MarketDataService",
    "SnapshotReport",
    "V2Progress",
    "classify_failure",
]
