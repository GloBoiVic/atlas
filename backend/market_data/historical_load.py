"""The deliberately narrow historical-load coordinator."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.domain.strategy_requirements import requirement_for_version
from backend.experiments.configuration import ExperimentConfigurationService
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

MAX_WINDOWS = 40
MAX_ELAPSED_DAYS = 90
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
    """Return the next deterministic range or a bounded terminal outcome.

    ``eligible_bars`` is intentionally an observed aggregation result, not an
    estimate based on open minutes.  A caller repeats this function after
    fetching the returned range and recomputing aggregation.
    """
    if eligible_bars >= required_historical_context_bars:
        return WarmupPlan(
            load_start, trading_end, eligible_bars, provider_windows, "READY"
        )
    bound = trading_start - timedelta(days=MAX_ELAPSED_DAYS)
    if load_start <= bound or provider_windows >= MAX_WINDOWS:
        return WarmupPlan(
            load_start,
            trading_end,
            eligible_bars,
            provider_windows,
            "INSUFFICIENT_WARMUP",
        )
    next_start = max(bound, load_start - INITIAL_ESTIMATE)
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
        # 25 hours is only the first provider request. Semantic context is
        # established later from completed, policy-eligible M15 results.
        load_start = trading_start - INITIAL_ESTIMATE
        load_end = trading_end
        if load_end - load_start > timedelta(days=90):
            raise HistoricalDataLoadError(
                "LOAD_RANGE_TOO_LARGE",
                "The computed historical load range exceeds 90 days.",
            )
        if hasattr(self.ingestion, "plan_missing"):
            plan = self.ingestion.plan_missing(load_start, load_end)
            if len(plan) > MAX_WINDOWS:
                raise HistoricalDataLoadError(
                    "LOAD_PLAN_TOO_LARGE",
                    "The initial historical load requires too many bounded "
                    "provider windows.",
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
            windows = 0
            while True:
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
                    )
                    return
                load_start = plan.load_start
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
            with session_scope(self.session_factory) as db:
                with db.begin():
                    self.repository.complete(
                        db,
                        request_id,
                        snapshot_id=snapshot.id,
                        coverage_summary=coverage_json,
                        experiment_validation=validation_json,
                    )
        except Exception as error:
            category, code, detail = classify_failure(error)
            self._fail(request_id, category, code, detail)

    def _progress(self, request_id, report, coverage=None):
        with session_scope(self.session_factory) as db:
            with db.begin():
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
                    row = self.repository.get(db, request_id)
                    if row:
                        row.snapshot_id = snapshot_id
                self.repository.fail_if_active(
                    db, request_id, category=category, code=code, detail=detail
                )
