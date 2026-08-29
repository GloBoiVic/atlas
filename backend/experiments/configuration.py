"""Coverage and immutable Experiment configuration orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import String, exists, func, literal, select, union_all
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.domain.strategy import ValidatedParameterPayload
from backend.domain.strategy_requirements import requirement_for_version
from backend.market_data.coverage import (
    CoverageGap,
    CoverageReport,
    MissingMinute,
    coalesce_gaps,
)
from backend.market_data.session_calendar import (
    eligible_m15_windows,
    is_session_open_minute,
)
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.market_data_repository import DatasetSnapshotRepository
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotGapModel,
    DatasetSnapshotModel,
    HistoricalAcquisitionWindowModel,
    InstrumentModel,
    MarketBarModel,
    StrategyVersionModel,
    VenueInstrumentModel,
)
from backend.persistence.strategy_repository import (
    StrategyRepository,
    version_to_domain,
)
from backend.strategies.registry import (
    StrategyRegistry,
    StrategyVersionUnavailableError,
)

RISK_SCHEMA_VERSION = "PHASE5_RISK_CONFIG_V1"
SIMULATION_SCHEMA_VERSION = "PHASE5_SIMULATION_CONFIG_V1"
MODEL_VERSION = "PHASE5_HISTORICAL_EXECUTION_V2"


def _execution_coverage_valid(report, successful_windows) -> bool:
    """Accept only fully absent minutes covered by successful M1 acquisition."""
    if report.closure_anomalies or report.unexpected_observations:
        return False
    return all(
        len(missing.components) == 2
        and any(
            window.start_time <= missing.start
            and window.end_time >= missing.start + timedelta(minutes=1)
            for window in successful_windows
        )
        for missing in report.missing
    )


def simulation_config(
    *, slippage_ticks: int, commission_per_unit: Decimal
) -> dict[str, Any]:
    if type(slippage_ticks) is not int or slippage_ticks < 0:
        raise ConfigurationError(
            "SIMULATION_INPUT_INVALID", "slippage ticks must be nonnegative"
        )
    if not commission_per_unit.is_finite() or commission_per_unit < 0:
        raise ConfigurationError(
            "SIMULATION_INPUT_INVALID", "commission must be finite and nonnegative"
        )
    return {
        "schema_version": SIMULATION_SCHEMA_VERSION,
        "execution_resolution": "M1",
        "analysis_component": "MID",
        "execution_components": ["BID", "ASK"],
        "spread_model": "DATASET_BID_ASK_EMBEDDED",
        "slippage_model": {
            "type": "ADVERSE_FIXED_TICKS",
            "ticks": slippage_ticks,
            "tick_size": "0.00001",
        },
        "commission_model": {
            "type": "PER_FILL_PER_UNIT_USD",
            "amount": str(commission_per_unit),
        },
        "financing_model": {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"},
        "intrabar_policy": "STOP_LOSS_ADVERSE_FIRST_V1",
        "target_fill_policy": "REQUESTED_PRICE_NO_IMPROVEMENT_V1",
        "end_policy": "FINAL_ELIGIBLE_M1_CLOSE_V1",
        "equity_sampling": "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1",
    }


def risk_config(risk_per_trade: Decimal) -> dict[str, str]:
    return {
        "schema_version": RISK_SCHEMA_VERSION,
        "risk_per_trade": str(risk_per_trade),
    }


@dataclass(frozen=True, slots=True)
class CoverageValidation:
    valid: bool
    requested_start: datetime
    requested_end: datetime
    required_start: datetime | None
    warm_up_required: int
    warm_up_available: int
    snapshot_id: UUID
    snapshot_fingerprint: str | None
    report: CoverageReport | None
    reasons: tuple[str, ...]

    @property
    def gaps(self) -> tuple[CoverageGap, ...]:
        return () if self.report is None else self.report.gaps[:100]

    @property
    def diagnostics(self):
        return () if self.report is None else self.report.interval_diagnostics[:100]


class ConfigurationError(ValueError):
    """A create request cannot produce a trustworthy immutable configuration."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class _V2ExecutionValidation:
    report: CoverageReport
    has_one_sided_observation: bool
    has_unacquired_absence: bool


def _unique_reasons(reasons: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)
    return tuple(ordered)


def _iter_eligible_m15_starts(
    start: datetime, end: datetime
):
    """Yield eligible native M15 starts without retaining the requested range."""
    cursor = start - timedelta(minutes=start.minute % 15)
    while cursor < end:
        window_end = cursor + timedelta(minutes=15)
        if window_end > start and any(
            is_session_open_minute(cursor + timedelta(minutes=offset))
            for offset in range(15)
        ):
            yield cursor
        cursor = window_end


def _stream_v2_execution_coverage(
    session: Session,
    snapshot: DatasetSnapshotModel,
    trading_start: datetime,
    trading_end: datetime,
) -> _V2ExecutionValidation:
    """Validate sparse execution membership from one bounded result stream."""
    observation_events = select(
        MarketBarModel.start_time.label("start_time"),
        MarketBarModel.end_time.label("end_time"),
        MarketBarModel.price_component.label("price_component"),
        literal(0).label("event_kind"),
    ).join(
        DatasetSnapshotExecutionObservationModel,
        DatasetSnapshotExecutionObservationModel.market_bar_id == MarketBarModel.id,
    ).where(
        DatasetSnapshotExecutionObservationModel.dataset_snapshot_id == snapshot.id,
        MarketBarModel.start_time >= trading_start,
        MarketBarModel.start_time < trading_end,
    )
    window_events = select(
        HistoricalAcquisitionWindowModel.start_time.label("start_time"),
        HistoricalAcquisitionWindowModel.end_time.label("end_time"),
        literal(None, String(3)).label("price_component"),
        literal(1).label("event_kind"),
    ).where(
        HistoricalAcquisitionWindowModel.venue_instrument_id
        == snapshot.venue_instrument_id,
        HistoricalAcquisitionWindowModel.resolution == "M1",
        HistoricalAcquisitionWindowModel.components == "ASK,BID",
        HistoricalAcquisitionWindowModel.outcome == "SUCCESS_EMPTY_OR_SPARSE",
        HistoricalAcquisitionWindowModel.start_time < trading_end,
        HistoricalAcquisitionWindowModel.end_time > trading_start,
    )
    events = union_all(observation_events, window_events).subquery()
    rows = session.execute(
        select(
            events.c.start_time,
            events.c.end_time,
            events.c.price_component,
            events.c.event_kind,
        )
        .order_by(
            events.c.start_time,
            events.c.event_kind,
            events.c.end_time,
            events.c.price_component,
        )
        .execution_options(stream_results=True)
    ).yield_per(1000)

    next_event = iter(rows)
    event = next(next_event, None)
    maximum_successful_window_end: datetime | None = None
    missing_preview: list[MissingMinute] = []
    closure_preview: list[datetime] = []
    unexpected_preview: list[datetime] = []
    has_one_sided_observation = False
    has_unacquired_absence = False
    expected_open_minutes = 0
    expected_closure_minutes = 0
    member_minutes = 0
    cursor = trading_start
    while cursor < trading_end:
        has_bid = False
        has_ask = False
        closure_seen = False
        unexpected_seen = False
        while event is not None and event.start_time <= cursor:
            if event.event_kind == 1:
                if (
                    maximum_successful_window_end is None
                    or event.end_time > maximum_successful_window_end
                ):
                    maximum_successful_window_end = event.end_time
            elif event.start_time != cursor or event.end_time != cursor + timedelta(
                minutes=1
            ):
                if not unexpected_seen and len(unexpected_preview) < 101:
                    unexpected_preview.append(event.start_time)
                unexpected_seen = True
            elif not is_session_open_minute(cursor):
                if not closure_seen and len(closure_preview) < 101:
                    closure_preview.append(cursor)
                closure_seen = True
            elif event.price_component == PriceComponent.BID.value:
                if has_bid and not unexpected_seen and len(unexpected_preview) < 101:
                    unexpected_preview.append(event.start_time)
                if has_bid:
                    unexpected_seen = True
                has_bid = True
            elif event.price_component == PriceComponent.ASK.value:
                if has_ask and not unexpected_seen and len(unexpected_preview) < 101:
                    unexpected_preview.append(event.start_time)
                if has_ask:
                    unexpected_seen = True
                has_ask = True
            else:
                if not unexpected_seen and len(unexpected_preview) < 101:
                    unexpected_preview.append(event.start_time)
                unexpected_seen = True
            event = next(next_event, None)

        if is_session_open_minute(cursor):
            expected_open_minutes += 1
            if has_bid and has_ask:
                member_minutes += 1
            else:
                if not has_bid:
                    missing_components = (
                        PriceComponent.BID, PriceComponent.ASK
                    ) if not has_ask else (PriceComponent.BID,)
                else:
                    missing_components = (PriceComponent.ASK,)
                if len(missing_preview) < 101:
                    missing_preview.append(MissingMinute(cursor, missing_components))
                if len(missing_components) == 1:
                    has_one_sided_observation = True
                elif (
                    maximum_successful_window_end is None
                    or maximum_successful_window_end < cursor + timedelta(minutes=1)
                ):
                    has_unacquired_absence = True
        else:
            expected_closure_minutes += 1
        cursor += timedelta(minutes=1)

    return _V2ExecutionValidation(
        CoverageReport(
            expected_open_minutes,
            expected_closure_minutes,
            member_minutes,
            tuple(missing_preview),
            coalesce_gaps(missing_preview),
            tuple(closure_preview),
            tuple(unexpected_preview),
        ),
        has_one_sided_observation,
        has_unacquired_absence,
    )


def missing_analytical_frontiers(
    analytical_starts: set[datetime], required_start: datetime, trading_end: datetime
) -> tuple[datetime, ...]:
    """Return eligible native M15 frontiers absent from the snapshot."""
    expected = (
        window_start
        for window_start, _window_end in eligible_m15_windows(
            required_start, trading_end
        )
    )
    return tuple(frontier for frontier in expected if frontier not in analytical_starts)


def _utc_aligned(value: datetime, name: str, *, fifteen: bool = False) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ConfigurationError("INVALID_RANGE", f"{name} must be UTC")
    if value.second or value.microsecond or (fifteen and value.minute % 15):
        raise ConfigurationError("INVALID_RANGE", f"{name} is not aligned")


def _execution_bar(row: MarketBarModel) -> Bar:
    """Normalize a persisted execution observation using Bar's field order."""
    return Bar(
        instrument=Instrument.EUR_USD,
        timeframe=Timeframe.M1,
        price_component=PriceComponent(row.price_component),
        start_time=row.start_time,
        end_time=row.end_time,
        open=row.open_price,
        high=row.high_price,
        low=row.low_price,
        close=row.close_price,
        volume=row.volume,
        provider=Provider.OANDA,
    )


def _validate_parameters(
    row: StrategyVersionModel, values: Mapping[str, object], implementation: object
) -> dict[str, object]:
    try:
        definition = implementation.definition
        payload = ValidatedParameterPayload.from_mapping(
            definition.parameter_schema, dict(values)
        )
        parser = getattr(implementation, "parse_parameters", None)
        if not callable(parser):
            raise TypeError("registered Strategy has no parameter parser")
        params = parser(payload)
    except Exception as error:
        raise ConfigurationError(
            "PARAMETERS_INVALID", "parameters are rejected by the registered Strategy"
        ) from error
    return params.to_json()


class ExperimentConfigurationService:
    """Read coverage and create one atomic PENDING Experiment graph."""

    def __init__(
        self,
        registry: StrategyRegistry,
        *,
        strategies: StrategyRepository | None = None,
        snapshots: DatasetSnapshotRepository | None = None,
        experiments: ExperimentRepository | None = None,
    ) -> None:
        self.registry = registry
        self.strategies = strategies or StrategyRepository()
        self.snapshots = snapshots or DatasetSnapshotRepository()
        self.experiments = experiments or ExperimentRepository()

    def validate_coverage(
        self,
        session: Session,
        *,
        strategy_version_id: UUID,
        dataset_snapshot_id: UUID,
        trading_start: datetime,
        trading_end: datetime,
    ) -> CoverageValidation:
        _utc_aligned(trading_start, "trading_start", fifteen=True)
        _utc_aligned(trading_end, "trading_end", fifteen=True)
        if trading_end <= trading_start:
            raise ConfigurationError(
                "INVALID_RANGE", "trading_end must be after trading_start"
            )
        version_row = self.strategies.get_version(session, strategy_version_id)
        snapshot_row = session.get(DatasetSnapshotModel, dataset_snapshot_id)
        if version_row is None or snapshot_row is None:
            return CoverageValidation(
                False,
                trading_start,
                trading_end,
                None,
                0,
                0,
                dataset_snapshot_id,
                None,
                None,
                ("INCOMPATIBLE_ID",),
            )
        try:
            version = version_to_domain(version_row)
            requirement = requirement_for_version(version)
            self.registry.implementation_for_version(version)
        except StrategyVersionUnavailableError:
            return CoverageValidation(
                False,
                trading_start,
                trading_end,
                None,
                requirement.required_historical_context_bars,
                0,
                dataset_snapshot_id,
                snapshot_row.fingerprint,
                None,
                ("STRATEGY_VERSION_UNAVAILABLE",),
            )
        venue = session.get(VenueInstrumentModel, snapshot_row.venue_instrument_id)
        instrument = (
            session.get(InstrumentModel, venue.instrument_id) if venue else None
        )
        if (
            venue is None
            or instrument is None
            or venue.provider != Provider.OANDA.value
            or venue.provider_symbol != "EUR_USD"
            or instrument.code != Instrument.EUR_USD.value
        ):
            return CoverageValidation(
                False,
                trading_start,
                trading_end,
                None,
                requirement.required_historical_context_bars,
                0,
                dataset_snapshot_id,
                snapshot_row.fingerprint,
                None,
                ("SNAPSHOT_VENUE_INCOMPATIBLE",),
            )
        if snapshot_row.snapshot_schema != "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2":
            return CoverageValidation(
                False,
                trading_start,
                trading_end,
                None,
                requirement.required_historical_context_bars,
                0,
                dataset_snapshot_id,
                snapshot_row.fingerprint,
                None,
                ("UNSUPPORTED_SNAPSHOT_SCHEMA",),
            )
        return self._validate_v2_coverage(
            session,
            snapshot_row,
            requirement.required_historical_context_bars,
            trading_start,
            trading_end,
        )

    @staticmethod
    def _validate_v2_coverage(
        session: Session,
        snapshot: DatasetSnapshotModel,
        warm_up_required: int,
        trading_start: datetime,
        trading_end: datetime,
    ) -> CoverageValidation:
        """Validate V2 from its immutable native analytical membership.

        V2 execution observations are intentionally sparse.  Configuration
        must therefore never pass them through the V1 wall-clock coverage
        validator; only native completed M15 availability and persisted,
        explicitly blocking snapshot gaps can invalidate the requested range.
        """
        analytical_base = (
            DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id == snapshot.id,
            DatasetSnapshotAnalyticalBarModel.complete.is_(True),
        )
        warm_up_available = session.scalar(
            select(func.count())
            .select_from(DatasetSnapshotAnalyticalBarModel)
            .where(
                *analytical_base,
                DatasetSnapshotAnalyticalBarModel.end_time <= trading_start,
            )
        ) or 0
        required_start = None
        if warm_up_required and warm_up_available >= warm_up_required:
            required_start = session.scalar(
                select(DatasetSnapshotAnalyticalBarModel.start_time)
                .where(
                    *analytical_base,
                    DatasetSnapshotAnalyticalBarModel.end_time <= trading_start,
                )
                .order_by(
                    DatasetSnapshotAnalyticalBarModel.end_time.desc(),
                    DatasetSnapshotAnalyticalBarModel.start_time.desc(),
                    DatasetSnapshotAnalyticalBarModel.sequence.desc(),
                )
                .offset(warm_up_required - 1)
                .limit(1)
            )
        elif not warm_up_required:
            required_start = trading_start
        reasons: list[str] = []
        if required_start is None:
            reasons.append("INSUFFICIENT_WARMUP")
            required_start = trading_start
        if (
            required_start < snapshot.coverage_start
            or trading_end > snapshot.coverage_end
        ):
            reasons.append("RANGE_OUTSIDE_SNAPSHOT")

        if not session.scalar(
            select(
                exists().where(
                    *analytical_base,
                    DatasetSnapshotAnalyticalBarModel.start_time >= trading_start,
                    DatasetSnapshotAnalyticalBarModel.start_time < trading_end,
                )
            )
        ):
            reasons.append("INSUFFICIENT_ANALYTICAL_DATA")
        analytical_rows = session.execute(
            select(DatasetSnapshotAnalyticalBarModel.start_time)
            .where(
                *analytical_base,
                DatasetSnapshotAnalyticalBarModel.start_time >= required_start,
                DatasetSnapshotAnalyticalBarModel.start_time < trading_end,
            )
            .order_by(DatasetSnapshotAnalyticalBarModel.start_time)
            .execution_options(stream_results=True)
        ).yield_per(1000)
        analytical_iter = iter(analytical_rows)
        analytical_row = next(analytical_iter, None)
        missing_frontier = False
        for expected_start in _iter_eligible_m15_starts(
            required_start, trading_end
        ):
            while (
                analytical_row is not None
                and analytical_row[0] < expected_start
            ):
                analytical_row = next(analytical_iter, None)
            if analytical_row is None or analytical_row[0] != expected_start:
                missing_frontier = True
            if analytical_row is not None and analytical_row[0] == expected_start:
                analytical_row = next(analytical_iter, None)
        if missing_frontier:
            reasons.append("MISSING_ANALYTICAL_FRONTIERS")

        # Execution is an independent immutable native product. Validate its
        # BID/ASK membership and successful sparse-window provenance, never
        # mutable market-bar heads or M1-derived M15. The joined event stream is
        # ordered and bounded; it retains only the current minute's two flags.
        execution_validation = _stream_v2_execution_coverage(
            session, snapshot, trading_start, trading_end
        )
        execution_report = execution_validation.report
        if (
            execution_validation.has_one_sided_observation
            or execution_validation.has_unacquired_absence
            or execution_report.closure_anomalies
            or execution_report.unexpected_observations
        ):
            reasons.append("INCOMPLETE_EXECUTION_DATA")

        if session.scalar(
            select(
                exists().where(
                    DatasetSnapshotGapModel.dataset_snapshot_id == snapshot.id,
                    DatasetSnapshotGapModel.blocked.is_(True),
                    DatasetSnapshotGapModel.end_time > required_start,
                    DatasetSnapshotGapModel.start_time < trading_end,
                )
            )
        ):
            reasons.append("BLOCKING_GAPS")

        return CoverageValidation(
            not reasons,
            trading_start,
            trading_end,
            required_start,
            warm_up_required,
            warm_up_available,
            snapshot.id,
            snapshot.fingerprint,
            None,
            _unique_reasons(reasons),
        )

    def create(
        self,
        session: Session,
        *,
        strategy_version_id: UUID,
        dataset_snapshot_id: UUID,
        trading_start: datetime,
        trading_end: datetime,
        starting_capital: Decimal,
        risk_per_trade: Decimal,
        parameters: Mapping[str, object],
        slippage_ticks: int,
        commission_per_unit: Decimal,
    ):
        coverage = self.validate_coverage(
            session,
            strategy_version_id=strategy_version_id,
            dataset_snapshot_id=dataset_snapshot_id,
            trading_start=trading_start,
            trading_end=trading_end,
        )
        if not coverage.valid:
            raise ConfigurationError("COVERAGE_INVALID", ";".join(coverage.reasons))
        if (
            not starting_capital.is_finite()
            or starting_capital <= 0
            or not risk_per_trade.is_finite()
            or not (Decimal("0") < risk_per_trade < Decimal("1"))
        ):
            raise ConfigurationError(
                "FINANCIAL_INPUT_INVALID",
                "capital and risk must be finite and in range",
            )
        if (
            type(slippage_ticks) is not int
            or slippage_ticks < 0
            or not commission_per_unit.is_finite()
            or commission_per_unit < 0
        ):
            raise ConfigurationError(
                "SIMULATION_INPUT_INVALID", "slippage and commission are out of range"
            )
        version_row = self.strategies.get_version(session, strategy_version_id)
        assert version_row is not None
        implementation = self.registry.implementation_for_version(
            version_to_domain(version_row)
        )
        snapshot = session.get(DatasetSnapshotModel, dataset_snapshot_id)
        assert snapshot is not None
        params = _validate_parameters(version_row, parameters, implementation)
        experiment = self.experiments.create(
            session,
            strategy_version_id=strategy_version_id,
            dataset_snapshot_id=dataset_snapshot_id,
            venue_instrument_id=snapshot.venue_instrument_id,
            trading_start=trading_start,
            trading_end=trading_end,
            starting_capital=starting_capital,
            risk_per_trade=risk_per_trade,
            parameter_snapshot=params,
            risk_config=risk_config(risk_per_trade),
            simulation_config=simulation_config(
                slippage_ticks=slippage_ticks, commission_per_unit=commission_per_unit
            ),
            model_version=MODEL_VERSION,
        )
        self.experiments.create_account_and_position(session, experiment)
        return experiment
