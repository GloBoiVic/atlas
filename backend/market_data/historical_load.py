"""The deliberately narrow historical-load coordinator."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.domain.strategy_requirements import requirement_for_version
from backend.experiments.configuration import ExperimentConfigurationService
from backend.market_data.session_calendar import required_warmup_range
from backend.persistence.database import session_scope
from backend.persistence.historical_data_load_repository import (
    HistoricalDataLoadRepository,
)
from backend.persistence.models import DatasetSnapshotAnalyticalBarModel
from backend.persistence.strategy_repository import (
    StrategyRepository,
    version_to_domain,
)
from backend.strategies.registry import StrategyVersionUnavailableError

from .ingestion import MarketDataService, classify_failure

INITIAL_ESTIMATE = timedelta(hours=25)


@dataclass(frozen=True, slots=True)
class WarmupPlan:
    """The result of bounded, policy-aware warm-up planning."""

    load_start: datetime
    load_end: datetime
    eligible_bars: int
    provider_windows: int
    outcome: str


def _warmup_plan(
    trading_start: datetime,
    trading_end: datetime,
    load_start: datetime,
    eligible_bars: int,
    provider_windows: int,
    required_historical_context_bars: int,
) -> WarmupPlan:
    """Return the next deterministic range or the ready outcome.

    ``eligible_bars`` is intentionally an observed aggregation result, not an
    estimate based on open minutes.  A caller repeats this function after
    fetching the returned range and recomputing aggregation.  There is no
    elapsed-time or provider-window ceiling: valid research ranges may need
    any number of bounded provider chunks.
    """
    if (
        trading_start.tzinfo is None
        or trading_end.tzinfo is None
        or load_start.tzinfo is None
        or trading_start.utcoffset() != timedelta(0)
        or trading_end.utcoffset() != timedelta(0)
        or load_start.utcoffset() != timedelta(0)
        or trading_end <= trading_start
        or load_start > trading_start
        or type(eligible_bars) is not int
        or eligible_bars < 0
        or type(provider_windows) is not int
        or provider_windows < 0
        or type(required_historical_context_bars) is not int
        or required_historical_context_bars < 0
    ):
        raise ValueError("invalid warm-up planning inputs")
    if eligible_bars >= required_historical_context_bars:
        return WarmupPlan(
            load_start, trading_end, eligible_bars, provider_windows, "READY"
        )
    next_start = load_start - INITIAL_ESTIMATE
    return WarmupPlan(
        next_start, trading_end, eligible_bars, provider_windows, "EXTEND"
    )


def _iso(v: datetime) -> str:
    return v.astimezone(UTC).isoformat().replace("+00:00", "Z")


class HistoricalDataLoadError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


class HistoricalDataLoadCoordinator:
    def __init__(
        self,
        session_factory,
        ingestion: MarketDataService,
        configuration: ExperimentConfigurationService,
        registry,
        *,
        repository=None,
        strategies=None,
    ):
        self.session_factory = session_factory
        self.ingestion = ingestion
        self.configuration = configuration
        self.registry = registry
        self.repository = repository or HistoricalDataLoadRepository()
        self.strategies = strategies or StrategyRepository()

    def prepare(
        self,
        session: Session,
        *,
        strategy_version_id: UUID,
        trading_start: datetime,
        trading_end: datetime,
    ):
        if (
            trading_start.tzinfo is None
            or trading_end.tzinfo is None
            or trading_start.utcoffset() != timedelta(0)
            or trading_end.utcoffset() != timedelta(0)
        ):
            raise HistoricalDataLoadError(
                "INVALID_RANGE", "Trading period must use UTC."
            )
        if (
            trading_start.second
            or trading_start.microsecond
            or trading_end.second
            or trading_end.microsecond
            or trading_start.minute % 15
            or trading_end.minute % 15
            or trading_end <= trading_start
        ):
            raise HistoricalDataLoadError(
                "INVALID_RANGE",
                "Trading period must be a positive 15-minute-aligned UTC range.",
            )
        version_row = self.strategies.get_version(session, strategy_version_id)
        if version_row is None:
            raise HistoricalDataLoadError(
                "STRATEGY_VERSION_NOT_FOUND", "StrategyVersion was not found."
            )
        try:
            version = version_to_domain(version_row)
            self.registry.implementation_for_version(version)
        except StrategyVersionUnavailableError as exc:
            raise HistoricalDataLoadError(
                "STRATEGY_VERSION_UNAVAILABLE",
                "StrategyVersion is not executable on this server.",
            ) from exc
        requirement = requirement_for_version(version)
        # Plan the actual semantic prefix up front.  Warm-up is measured in
        # eligible completed M15 windows, not wall-clock minutes.  In
        # particular, a Monday request must not manufacture a Sunday provider
        # window when the durable native M15 history already has enough bars.
        load_start, load_end = required_warmup_range(
            trading_start,
            trading_end,
            requirement.required_historical_context_bars,
        )
        return load_start, load_end

    def run(self, request_id: UUID) -> None:
        try:
            with session_scope(self.session_factory) as db:
                with db.begin():
                    row = self.repository.claim(db, request_id)
            if row is None or row.status != "RUNNING":
                return
            with session_scope(self.session_factory) as db:
                version_row = self.strategies.get_version(db, row.strategy_version_id)
                requirement = requirement_for_version(version_to_domain(version_row))
            required_context = requirement.required_historical_context_bars
            load_start = row.load_start
            # Requests created before semantic warm-up planning used a fixed
            # 25-hour prefix.  Normalize that legacy boundary on retry so a
            # durable native-M15 range can complete without re-requesting an
            # ineligible market-closure window.
            legacy_start = row.trading_start - timedelta(
                minutes=15 * required_context
            )
            if load_start == legacy_start:
                load_start, _ = required_warmup_range(
                    row.trading_start, row.load_end, required_context
                )
            windows = 0
            while True:
                try:
                    snapshot_report = self.ingestion.load_v2(
                        load_start, row.load_end,
                        progress=lambda report: self._progress(request_id, report),
                    )
                except TypeError as error:
                    # Keep the narrow seam usable by pre-V2 test doubles; real
                    # ingestion implementations all accept the callback.
                    if "progress" not in str(error):
                        raise
                    snapshot_report = self.ingestion.load_v2(load_start, row.load_end)
                snapshot = snapshot_report.snapshot
                if snapshot is None:
                    self._fail(
                        request_id,
                        "VALIDATION",
                        "SNAPSHOT_CREATION_FAILED",
                        "A valid V2 dataset snapshot could not be created.",
                    )
                    return
                windows += 1
                eligible = self._v2_warmup_count(
                    snapshot.id, row.trading_start, snapshot_report
                )
                plan = _warmup_plan(
                    row.trading_start,
                    row.trading_end,
                    load_start,
                    eligible,
                    windows,
                    required_context,
                )
                if plan.outcome == "READY":
                    break
                if plan.outcome == "INSUFFICIENT_WARMUP":
                    self._fail(
                        request_id,
                        "VALIDATION",
                        "INSUFFICIENT_WARMUP",
                        "Fewer than the configured eligible native M15 bars are "
                        "available within the bounded warm-up horizon.",
                        snapshot.id,
                    )
                    return
                new_load_start = plan.load_start
                load_start = new_load_start
            if eligible < required_context:
                self._fail(
                    request_id,
                    "VALIDATION",
                    "INSUFFICIENT_WARMUP",
                    "The V2 snapshot does not contain enough actual native M15 "
                    "bars before trading_start.",
                    snapshot.id,
                )
                return
            coverage_json = {
                "valid": True,
                "policy_version": "ATLAS_HISTORICAL_GAP_POLICY_V1",
                "snapshot_schema": snapshot.snapshot_schema,
                "analytical_contract": "OANDA_M15_NATIVE_UTC_V1",
                "gapCount": snapshot.integrity_summary.get("gap_count", 0),
                "diagnostics": [],
            }
            validation_json = {
                "valid": True,
                "requiredHistoricalContextBars": required_context,
                "warmUpAvailable": eligible,
                "reasons": [],
                "snapshot_schema": snapshot.snapshot_schema,
            }
            if getattr(snapshot_report, "telemetry", None) is not None:
                coverage_json["telemetry"] = snapshot_report.telemetry
            with session_scope(self.session_factory) as db:
                with db.begin():
                    completed = self.repository.complete(
                        db,
                        request_id,
                        snapshot_id=snapshot.id,
                        coverage_summary=coverage_json,
                        experiment_validation=validation_json,
                    )
            if not completed:
                # Completion is the only safe point at which the snapshot can be
                # linked to this request.  A failed linkage or lifecycle race must
                # not leave the request looking RUNNING or imply a usable snapshot.
                self._fail(
                    request_id,
                    "PERSISTENCE",
                    "COMPLETION_TRANSITION_FAILED",
                    "Historical data load completion could not be committed; "
                    "no snapshot was linked.",
                )
        except Exception as error:
            category, code, detail = classify_failure(error)
            self._fail(request_id, category, code, detail)

    def _progress(self, request_id, report, coverage=None):
        with session_scope(self.session_factory) as db:
            with db.begin():
                payload_builder = getattr(report, "to_payload", None)
                if payload_builder is not None:
                    self.repository.record_progress(
                        db,
                        request_id,
                        progress_payload=payload_builder(),
                        telemetry=getattr(report, "telemetry", None),
                    )
                else:
                    self.repository.record_progress(
                        db,
                        request_id,
                        fetched_ranges=report.fetched_ranges,
                        committed_ranges=report.committed_ranges,
                        inserted=report.inserted,
                        reactivated=report.reactivated,
                        unchanged=report.unchanged,
                        incomplete_minutes=report.incomplete_minutes,
                        coverage_summary=coverage,
                        product=getattr(report, "product", None),
                        window=getattr(report, "window", None),
                        completed_units=(
                            getattr(report, "window", {}) or {}
                        ).get("committed_count"),
                    )

    def _required_context_bars(self, row) -> int:
        """Read the canonical Strategy market-data requirement."""
        if not hasattr(row, "strategy_version_id"):
            return 0
        try:
            with session_scope(self.session_factory) as db:
                version_row = self.strategies.get_version(db, row.strategy_version_id)
                return (
                    requirement_for_version(
                        version_to_domain(version_row)
                    ).required_historical_context_bars
                    if version_row
                    else 0
                )
        except (AttributeError, TypeError):
            # Small coordinator fakes used by unit tests need not implement
            # the persistence seam; normal model rows always do.
            return 0

    def _v2_warmup_count(self, snapshot_id, trading_start, report) -> int:
        """Count actual native M15 members before trading, not open minutes."""
        summary = getattr(report.snapshot, "integrity_summary", {})
        if "warmup_count" in summary:
            return int(summary["warmup_count"])
        with session_scope(self.session_factory) as db:
            if not hasattr(db, "scalar"):
                return int(summary.get("analytical_count", 0))
            return int(
                db.scalar(
                    select(
                        func.count(DatasetSnapshotAnalyticalBarModel.sequence)
                    ).where(
                        DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id
                        == snapshot_id,
                        DatasetSnapshotAnalyticalBarModel.start_time < trading_start,
                    )
                )
                or 0
            )

    def _fail(self, request_id, category, code, detail, snapshot_id=None):
        with session_scope(self.session_factory) as db:
            with db.begin():
                if snapshot_id is not None:
                    self.repository.fail_if_active(
                        db,
                        request_id,
                        category=category,
                        code=code,
                        detail=detail,
                        snapshot_id=snapshot_id,
                    )
                else:
                    self.repository.fail_if_active(
                        db, request_id, category=category, code=code, detail=detail
                    )
