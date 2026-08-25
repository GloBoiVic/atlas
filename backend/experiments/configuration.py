"""Coverage and immutable Experiment configuration orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import Instrument, Provider
from backend.domain.strategy import StrategyParameters
from backend.domain.strategy_requirements import requirement_for_version
from backend.market_data.coverage import CoverageGap, CoverageReport
from backend.market_data.session_calendar import eligible_m15_windows
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.market_data_repository import DatasetSnapshotRepository
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotGapModel,
    DatasetSnapshotModel,
    InstrumentModel,
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


def _validate_parameters(
    row: StrategyVersionModel, values: Mapping[str, object], implementation: object
) -> dict[str, object]:
    schema = {item["key"]: item for item in row.parameter_schema}
    if set(values) != set(schema):
        raise ConfigurationError(
            "PARAMETERS_INVALID",
            "parameter keys must exactly match the persisted schema",
        )
    for key, descriptor in schema.items():
        value = values[key]
        if descriptor["type"] == "integer" and type(value) is not int:
            raise ConfigurationError("PARAMETERS_INVALID", f"{key} must be an integer")
        if descriptor["type"] == "decimal":
            try:
                value = Decimal(str(value))
            except Exception as error:
                raise ConfigurationError(
                    "PARAMETERS_INVALID", f"{key} must be a decimal"
                ) from error
            if not value.is_finite():
                raise ConfigurationError("PARAMETERS_INVALID", f"{key} must be finite")
        minimum, maximum = descriptor.get("min"), descriptor.get("max")
        if minimum is not None and Decimal(str(value)) < Decimal(str(minimum)):
            raise ConfigurationError(
                "PARAMETERS_INVALID", f"{key} is below its minimum"
            )
        if maximum is not None and Decimal(str(value)) > Decimal(str(maximum)):
            raise ConfigurationError("PARAMETERS_INVALID", f"{key} exceeds its maximum")
    try:
        params = StrategyParameters(
            ema_period=values["ema_period"],
            atr_period=values["atr_period"],
            stop_buffer=Decimal(str(values["stop_buffer"])),
            target_r=Decimal(str(values["target_r"])),
            expiry_window=values["expiry_window"],
        )
        implementation._validate_parameters(params)  # noqa: B009  # registered Strategy validation hook
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
        analytical = tuple(
            session.scalars(
                select(DatasetSnapshotAnalyticalBarModel)
                .where(
                    DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id
                    == snapshot.id,
                    DatasetSnapshotAnalyticalBarModel.complete.is_(True),
                )
                .order_by(DatasetSnapshotAnalyticalBarModel.end_time)
            ).all()
        )
        warm = tuple(item for item in analytical if item.end_time <= trading_start)
        selected = warm[-warm_up_required:] if warm_up_required else ()
        required_start = (
            selected[0].start_time if len(selected) == warm_up_required else None
        )
        reasons: list[str] = []
        if required_start is None:
            reasons.append("INSUFFICIENT_WARMUP")
            required_start = trading_start
        if (
            required_start < snapshot.coverage_start
            or trading_end > snapshot.coverage_end
        ):
            reasons.append("RANGE_OUTSIDE_SNAPSHOT")

        requested_analytical = tuple(
            item
            for item in analytical
            if trading_start <= item.start_time < trading_end
        )
        if not requested_analytical:
            reasons.append("INSUFFICIENT_ANALYTICAL_DATA")
        if missing_analytical_frontiers(
            {item.start_time for item in analytical}, required_start, trading_end
        ):
            reasons.append("MISSING_ANALYTICAL_FRONTIERS")

        blocked_gaps = session.scalars(
            select(DatasetSnapshotGapModel)
            .where(
                DatasetSnapshotGapModel.dataset_snapshot_id == snapshot.id,
                DatasetSnapshotGapModel.blocked.is_(True),
                DatasetSnapshotGapModel.end_time > required_start,
                DatasetSnapshotGapModel.start_time < trading_end,
            )
            .order_by(DatasetSnapshotGapModel.sequence)
        ).all()
        if blocked_gaps:
            reasons.append("BLOCKING_GAPS")

        return CoverageValidation(
            not reasons,
            trading_start,
            trading_end,
            required_start,
            warm_up_required,
            len(warm),
            snapshot.id,
            snapshot.fingerprint,
            None,
            tuple(dict.fromkeys(reasons)),
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
