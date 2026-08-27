# ruff: noqa: E501
"""The narrow Phase 3 historical Experiment orchestration boundary.

The runner is intentionally an application service, not a new execution
framework.  It composes the already-tested snapshot, clock, Strategy, Risk,
execution, repository, and Fill boundaries and keeps their ordering explicit.
"""

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.domain.strategy import (
    Action,
    EntryPolicy,
    Phase,
    PositionState,
    StrategyContext,
    StrategyParameters,
    StrategyState,
)
from backend.execution.contract import ExecutionObservation, ExecutionRejected, Order
from backend.execution.fill_application import apply_fill
from backend.execution.simulated import SimulatedExecutionAdapter
from backend.market_data.aggregation import aggregate_m1_to_m15
from backend.market_data.aggregation import AggregationError
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.market_data_repository import DatasetSnapshotRepository
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotGapModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentEquityPointModel,
    ExperimentGapDecisionModel,
    ExperimentModel,
    ExperimentProposalDiagnosticModel,
    FillModel,
    InstrumentModel,
    MarketBarModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    StrategyVersionModel,
    TradeIntentModel,
    TradeModel,
    VenueInstrumentModel,
)
from backend.persistence.strategy_repository import (
    StrategyRepository,
    version_to_domain,
)
from backend.persistence.trading_repository import TradingRepository
from backend.risk.service import (
    AccountState,
    ExecutableQuote,
    RiskConfig,
    RiskService,
    TradeIntent,
)
from backend.strategies.contract import evaluate_strategy
from backend.strategies.contract import StrategyContractError, StrategyEvaluationError
from backend.domain.strategy import StateError, VersionError
from backend.execution.contract import ExecutionInputError, ExecutionRejected
from backend.strategies.registry import StrategyRegistry

from .clock import ClockFrame, ClockPhase, M1Observation, SimulationClock
from .metric_contract import (
    RESULT_METRIC_SCHEMA_VERSION,
    PHASE5_RESULT_SCHEMA_VERSION,
    SHARPE_METHODOLOGY,
)
from .metrics import calculate_metrics


class FailureCategory(StrEnum):
    VALIDATION = "VALIDATION"
    MARKET_DATA = "MARKET_DATA"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    PERSISTENCE = "PERSISTENCE"


def terminal_protection_observation(observations, entry_time, trading_end):
    """Return an observation proving the account state at experiment end."""
    if entry_time is None:
        return None
    candidates = tuple(
        observation
        for observation in observations
        if observation.start_time >= entry_time and observation.end_time <= trading_end
    )
    terminal = max(candidates, key=lambda item: item.end_time, default=None)
    return (
        terminal if terminal is not None and terminal.end_time == trading_end else None
    )


def result_quality_for_gaps(gaps, gap_decisions, trading_start, trading_end, *, ambiguous=False):
    """Classify persisted uncertainty, with data uncertainty taking priority."""

    def material(item):
        return (
            bool(item.blocked)
            and item.end_time > trading_start
            and item.start_time < trading_end
        )

    if any(material(item) for item in (*gaps, *gap_decisions)):
        return "DEGRADED"
    if ambiguous:
        return "CONSERVATIVE_AMBIGUITY_RESOLVED"
    return "DETERMINED"


@dataclass(frozen=True, slots=True)
class ExperimentFailure:
    category: FailureCategory
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class ExperimentRunResult:
    experiment_id: UUID
    status: str
    trade_completed: bool
    failure: ExperimentFailure | None = None


class Phase4DiagnosticStage(StrEnum):
    PRECONDITIONS = "preconditions"
    CONFIG_VALIDATION = "config_validation"
    SNAPSHOT_MEMBER_LOAD = "snapshot_member_load"
    M15_AGGREGATION = "m15_aggregation"
    CLOCK_CONSTRUCTION = "clock_construction"
    CLOCK_MATERIALIZATION = "clock_materialization"
    INITIAL_EQUITY = "initial_equity"
    STRATEGY_OBSERVATION_LOOP = "strategy_observation_loop"
    END_CLOSE = "end_close"
    RESULT_FINALIZATION = "result_finalization"
    EXECUTION_ADAPTER_CONFIGURATION = "execution_adapter_configuration"
    FINANCIAL_PROJECTION_LOAD = "financial_projection_load"
    PRE_EXECUTION_INPUTS = "pre_execution_inputs"
    WARMUP_EVALUATION = "warmup_evaluation"
    DECISION_EVALUATION = "decision_evaluation"
    ENTRY_ATTEMPT = "entry_attempt"
    PROTECTION_APPLICATION = "protection_application"
    EQUITY_SAMPLING = "equity_sampling"
    TERMINAL_FACT_READ = "terminal_fact_read"
    METRICS_CALCULATION = "metrics_calculation"
    SEMANTIC_PAYLOAD = "semantic_payload"
    RESULT_CREATE = "result_create"
    MARK_COMPLETED = "mark_completed"


@dataclass(frozen=True, slots=True)
class Phase4ValueErrorDiagnostic:
    event: str
    experiment_id: UUID
    model_version: str
    run_path: str
    stage: Phase4DiagnosticStage
    reason_code: str
    at: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "event": self.event,
            "experiment_id": str(self.experiment_id),
            "model_version": self.model_version,
            "run_path": self.run_path,
            "stage": self.stage.value,
            "reason_code": self.reason_code,
        }
        if self.at is not None:
            result["at"] = self.at
        return result


_VALUE_ERROR_REASONS: dict[str, str] = {
    "experiment is not pending or running": "INVALID_EXPERIMENT_STATUS",
    "unsupported experiment model": "UNSUPPORTED_MODEL_VERSION",
    "strategy version does not exist": "STRATEGY_VERSION_MISSING",
    "dataset snapshot does not exist": "DATASET_SNAPSHOT_MISSING",
    "invalid simulation config": "SIMULATION_CONFIG_INVALID",
    "invalid slippage model": "SLIPPAGE_MODEL_INVALID",
    "invalid commission model": "COMMISSION_MODEL_INVALID",
    "invalid commission": "COMMISSION_INVALID",
    "invalid financing model": "FINANCING_MODEL_INVALID",
    "invalid intrabar policy": "INTRABAR_POLICY_INVALID",
    "invalid target fill policy": "TARGET_FILL_POLICY_INVALID",
    "invalid end policy": "END_POLICY_INVALID",
    "invalid equity sampling": "EQUITY_SAMPLING_INVALID",
    "invalid risk config": "RISK_CONFIG_INVALID",
    "experiment financial projections are missing": "FINANCIAL_PROJECTIONS_MISSING",
    "no final eligible M1 quote": "FINAL_QUOTE_MISSING",
    "open Position has no open Trade": "OPEN_TRADE_MISSING",
    "open Trade has incomplete protection": "PROTECTION_INCOMPLETE",
    "open Position has no Trade at experiment end": "END_TRADE_MISSING",
    "terminal financial state is incomplete": "TERMINAL_STATE_INCOMPLETE",
    "SimulationClock requires OANDA EUR/USD M1 bars": "CLOCK_M1_INPUT_INVALID",
    "SimulationClock requires OANDA EUR/USD M15 MID bars": "CLOCK_M15_INPUT_INVALID",
    "M1 bars must be UTC, minute-aligned, one-minute bars": "CLOCK_M1_ALIGNMENT_INVALID",
    "M15 bars must be UTC, aligned, complete bars": "CLOCK_M15_ALIGNMENT_INVALID",
    "duplicate M1 component at one frontier": "CLOCK_M1_DUPLICATE_COMPONENT",
    "duplicate M15 decision frontier": "CLOCK_M15_DUPLICATE_FRONTIER",
    "insufficient completed M15 bars for warmup": "CLOCK_WARMUP_INSUFFICIENT",
    "trading_start must be UTC and M15-aligned": "CLOCK_START_ALIGNMENT_INVALID",
    "trading_end must be UTC and M15-aligned": "CLOCK_END_ALIGNMENT_INVALID",
}


def _diagnostic_reason(message: str) -> str:
    return _VALUE_ERROR_REASONS.get(message, "UNCLASSIFIED_VALUE_ERROR")


_INCOMPLETE_M1_MESSAGE = re.compile(r"^incomplete M1 observation at (?P<at>.+)$")


def _diagnostic_details(message: str) -> tuple[str, str | None]:
    match = _INCOMPLETE_M1_MESSAGE.fullmatch(message)
    if match is None:
        return _diagnostic_reason(message), None
    try:
        observed_at = datetime.fromisoformat(match.group("at"))
        if observed_at.tzinfo is None:
            return "UNCLASSIFIED_VALUE_ERROR", None
        observed_at = observed_at.astimezone(UTC)
    except ValueError:
        return "UNCLASSIFIED_VALUE_ERROR", None
    return "INCOMPLETE_M1_OBSERVATION", observed_at.isoformat().replace("+00:00", "Z")


ValueErrorDiagnosticSink = Callable[[Phase4ValueErrorDiagnostic], None]


@dataclass(frozen=True, slots=True)
class Phase4RunnerComparisonDiagnostic:
    event: str
    checkpoint: str
    stage: Phase4DiagnosticStage
    strategy_identity: str
    strategy_contract_digest: str
    snapshot_identity: str
    snapshot_contract_digest: str
    snapshot_member_count: int | None
    snapshot_membership_digest: str
    parameters_digest: str
    risk_digest: str
    simulation_digest: str
    period_digest: str
    capital_digest: str
    financial_projection_digest: str
    effective_execution_digest: str
    seed_profile_digest: str
    runner_inputs_digest: str
    terminal_status: str | None
    failure_category: str | None
    failure_code: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "checkpoint": self.checkpoint,
            "stage": self.stage.value,
            "strategy_identity": self.strategy_identity,
            "strategy_contract_digest": self.strategy_contract_digest,
            "snapshot_identity": self.snapshot_identity,
            "snapshot_contract_digest": self.snapshot_contract_digest,
            "snapshot_member_count": self.snapshot_member_count,
            "snapshot_membership_digest": self.snapshot_membership_digest,
            "parameters_digest": self.parameters_digest,
            "risk_digest": self.risk_digest,
            "simulation_digest": self.simulation_digest,
            "period_digest": self.period_digest,
            "capital_digest": self.capital_digest,
            "financial_projection_digest": self.financial_projection_digest,
            "effective_execution_digest": self.effective_execution_digest,
            "seed_profile_digest": self.seed_profile_digest,
            "runner_inputs_digest": self.runner_inputs_digest,
            "terminal_status": self.terminal_status,
            "failure_category": self.failure_category,
            "failure_code": self.failure_code,
        }


RunnerComparisonDiagnosticSink = Callable[[Phase4RunnerComparisonDiagnostic], None]


def _comparison_json(value: object) -> object:
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, datetime):
        return {"datetime": value.astimezone(UTC).isoformat().replace("+00:00", "Z")}
    if isinstance(value, StrEnum):
        return {"enum": value.value}
    if isinstance(value, Mapping):
        return {
            str(key): _comparison_json(value[key]) for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple)):
        return [_comparison_json(item) for item in value]
    return value


def _comparison_digest(field: str, value: object) -> str:
    payload = {
        "domain": "ATLAS_V2_RUNNER_COMPARISON_V1",
        "field": field,
        "value": _comparison_json(value),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


MODEL_VERSION = "PHASE5_HISTORICAL_EXECUTION_V2"
RESULT_SCHEMA_VERSION = PHASE5_RESULT_SCHEMA_VERSION
NOT_COMPLETED = "PHASE3_TRADE_NOT_COMPLETED"


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str):
        result = Decimal(value)
    else:
        raise ValueError(f"{name} must be a Decimal or string")
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _parameters(values: Mapping[str, object]) -> StrategyParameters:
    defaults = StrategyParameters().to_json()
    merged = {**defaults, **values}
    return StrategyParameters(
        ema_period=merged["ema_period"],
        atr_period=merged["atr_period"],
        stop_buffer=_decimal(merged["stop_buffer"], "stop_buffer"),
        target_r=_decimal(merged["target_r"], "target_r"),
        expiry_window=merged["expiry_window"],
    )


def _source_ids(frame: ClockFrame) -> list[str]:
    return [str(item.source.market_bar_id) for item in frame.completed_m1]


def _observation(frame: ClockFrame) -> ExecutionObservation:
    by_component = {item.bar.price_component: item for item in frame.executable_opens}
    bid = by_component.get(PriceComponent.BID)
    ask = by_component.get(PriceComponent.ASK)
    if bid is None or ask is None:
        raise ValueError("missing executable BID/ASK opens")
    completed = {item.bar.price_component: item.bar for item in frame.completed_m1}
    bid_bar, ask_bar = (
        completed.get(PriceComponent.BID),
        completed.get(PriceComponent.ASK),
    )
    return ExecutionObservation(
        observed_at=bid.bar.start_time,
        bid_open=bid.bar.open,
        ask_open=ask.bar.open,
        bid_high=bid_bar.high if bid_bar else None,
        bid_low=bid_bar.low if bid_bar else None,
        ask_high=ask_bar.high if ask_bar else None,
        ask_low=ask_bar.low if ask_bar else None,
    )


def _observation_from_m1(item: M1Observation) -> ExecutionObservation:
    bars = {entry.bar.price_component: entry for entry in item.bars}
    bid, ask = bars[PriceComponent.BID].bar, bars[PriceComponent.ASK].bar
    return ExecutionObservation(
        observed_at=item.start_time,
        bid_open=bid.open,
        ask_open=ask.open,
        bid_high=bid.high,
        bid_low=bid.low,
        ask_high=ask.high,
        ask_low=ask.low,
        bid_close=bid.close,
        ask_close=ask.close,
        bid_source_market_bar_id=bars[PriceComponent.BID].source.market_bar_id,
        ask_source_market_bar_id=bars[PriceComponent.ASK].source.market_bar_id,
    )


class ExperimentRunner:
    """Run one persisted Experiment until its first completed Trade."""

    def __init__(
        self,
        *,
        strategy_registry: StrategyRegistry,
        snapshot_repository: DatasetSnapshotRepository | None = None,
        strategy_repository: StrategyRepository | None = None,
        experiment_repository: ExperimentRepository | None = None,
        trading_repository: TradingRepository | None = None,
        risk_service: RiskService | None = None,
        execution: SimulatedExecutionAdapter | None = None,
        value_error_diagnostic_sink: ValueErrorDiagnosticSink | None = None,
        comparison_diagnostic_sink: RunnerComparisonDiagnosticSink | None = None,
    ) -> None:
        self.registry = strategy_registry
        self.snapshots = snapshot_repository or DatasetSnapshotRepository()
        self.strategies = strategy_repository or StrategyRepository()
        self.experiments = experiment_repository or ExperimentRepository()
        self.trading = trading_repository or TradingRepository()
        self.risk = risk_service or RiskService()
        self.execution = execution or SimulatedExecutionAdapter()
        self._execution_supplied = execution is not None
        self._value_error_diagnostic_sink = value_error_diagnostic_sink
        self._comparison_diagnostic_sink = comparison_diagnostic_sink

    def run(self, session: Session, experiment_id: UUID) -> ExperimentRunResult:
        experiment = self.experiments.get(session, experiment_id)
        if experiment is not None:
            snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
            if (
                snapshot is not None
                and snapshot.snapshot_schema
                == "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2"
            ):
                return self._run_v2(session, experiment)
        # V2 is the sole historical execution architecture.  Never fall back
        # to the old M1->M15 aggregation runner for a new or malformed run.
        return self._fail(
            session,
            experiment,
            FailureCategory.VALIDATION,
            "UNSUPPORTED_EXPERIMENT_MODEL",
            "Experiment uses an unsupported execution model",
        )

    def _run_v2(
        self, session: Session, experiment: ExperimentModel
    ) -> ExperimentRunResult:
        """Run V2 using native M15 input and sparse BID/ASK observations."""
        stage = Phase4DiagnosticStage.PRECONDITIONS
        try:
            if experiment.status == "PENDING":
                self.experiments.mark_running(session, experiment.id)
            elif experiment.status != "RUNNING":
                raise ValueError("experiment is not pending or running")
            stage = Phase4DiagnosticStage.STRATEGY_OBSERVATION_LOOP
            version_row = self.strategies.get_version(
                session, experiment.strategy_version_id
            )
            if version_row is None:
                raise ValueError("strategy version does not exist")
            version = version_to_domain(version_row)
            implementation = self.registry.implementation_for_version(version)
            stage = Phase4DiagnosticStage.SNAPSHOT_MEMBER_LOAD
            snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
            if snapshot is None:
                raise ValueError("dataset snapshot does not exist")
            venue = session.get(VenueInstrumentModel, snapshot.venue_instrument_id)
            if venue is None:
                raise ValueError("snapshot venue instrument does not exist")
            instrument = session.get(InstrumentModel, venue.instrument_id)
            if instrument is None:
                raise ValueError("snapshot instrument does not exist")
            analytical = tuple(
                Bar(
                    instrument=Instrument(instrument.code),
                    provider=Provider(venue.provider),
                    timeframe=Timeframe.M15,
                    price_component=PriceComponent.MID,
                    start_time=row.start_time,
                    end_time=row.end_time,
                    open=row.open_price,
                    high=row.high_price,
                    low=row.low_price,
                    close=row.close_price,
                    volume=row.volume,
                )
                for row in session.scalars(
                    select(DatasetSnapshotAnalyticalBarModel)
                    .where(
                        DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id
                        == snapshot.id
                    )
                    .order_by(DatasetSnapshotAnalyticalBarModel.sequence)
                ).all()
            )
            execution_members = []
            for member in session.scalars(
                select(DatasetSnapshotExecutionObservationModel)
                .where(
                    DatasetSnapshotExecutionObservationModel.dataset_snapshot_id
                    == snapshot.id
                )
                .order_by(DatasetSnapshotExecutionObservationModel.sequence)
            ).all():
                row = session.get(MarketBarModel, member.market_bar_id)
                if row is None:
                    raise ValueError("snapshot execution observation does not exist")
                execution_members.append(
                    self._snapshot_bar(
                        row, instrument, venue, member.observation_fingerprint
                    )
                )
            stage = Phase4DiagnosticStage.CLOCK_CONSTRUCTION
            clock = SimulationClock(
                execution_members,
                analytical,
                trading_start=experiment.trading_start,
                trading_end=experiment.trading_end,
                required_historical_context_bars=version.required_historical_context_bars,
                sparse_execution=True,
            )
            stage = Phase4DiagnosticStage.FINANCIAL_PROJECTION_LOAD
            account = session.scalar(
                select(ExperimentAccountModel).where(
                    ExperimentAccountModel.experiment_id == experiment.id
                )
            )
            position = session.scalar(
                select(PositionModel).where(
                    PositionModel.experiment_id == experiment.id
                )
            )
            if account is None or position is None:
                raise ValueError("experiment financial projections are missing")
            # V2 policy: initial account boundary, then each eligible M1 close.
            self._sample_equity(session, experiment, account, position, None, 0)
            params, state, history = (
                _parameters(experiment.parameter_snapshot),
                StrategyState(schema_version=version.state_schema_version),
                [],
            )
            frames = tuple(clock.frames())
            observations = tuple(clock.observations())
            decisions = tuple(
                frame for frame in frames if frame.phase is ClockPhase.DECISION
            )
            stage = Phase4DiagnosticStage.STRATEGY_OBSERVATION_LOOP
            for frame in frames:
                if frame.phase is ClockPhase.WARMUP:
                    history.append(frame.decision_bar)
                    state = evaluate_strategy(
                        implementation,
                        StrategyContext(
                            frame.frontier,
                            frame.decision_bar.instrument,
                            tuple(history),
                            PositionState.FLAT,
                            False,
                        ),
                        params,
                        state,
                    ).next_state
            risk_config = RiskConfig(
                _decimal(experiment.risk_per_trade, "risk_per_trade")
            )
            commission = _decimal(
                experiment.simulation_config.get("commission_model", {}).get(
                    "amount", "0"
                ),
                "commission",
            )
            observation_index = 0
            pending = None

            def consume(observation):
                nonlocal pending
                if pending is not None:
                    intent_row, pending_frame, pending_decision = pending
                    # Strategy state is the sole authority: before the next
                    # analytical frontier, its persisted watch count identifies
                    # the currently eligible window.  No wall-clock or runner
                    # slot calculation is performed here.
                    if (
                        observation.start_time > pending_decision.decision_time
                        and state.phase is Phase.ARMED
                        and state.watch_bars < 5
                    ):
                        executable = _observation_from_m1(observation)
                        direction = pending_decision.direction
                        assert (
                            direction is not None
                            and pending_decision.trigger_price is not None
                        )
                        reached = (
                            (
                                (executable.ask_open > pending_decision.trigger_price)
                                or (
                                    executable.ask_high is not None
                                    and executable.ask_high
                                    >= pending_decision.trigger_price
                                )
                            )
                            if direction.value == "LONG"
                            else (
                                (executable.bid_open < pending_decision.trigger_price)
                                or (
                                    executable.bid_low is not None
                                    and executable.bid_low
                                    <= pending_decision.trigger_price
                                )
                            )
                        )
                        if reached:
                            # Preserve the original observation and provenance while
                            # presenting the selected executable trigger/open to the
                            # existing adapter. Slippage is applied exactly once there.
                            price = (
                                executable.ask_open
                                if direction.value == "LONG"
                                and executable.ask_open > pending_decision.trigger_price
                                else executable.bid_open
                                if direction.value == "SHORT"
                                and executable.bid_open < pending_decision.trigger_price
                                else pending_decision.trigger_price
                            )
                            if direction.value == "LONG":
                                executable = replace(executable, ask_open=price)
                            else:
                                executable = replace(executable, bid_open=price)
                            filled = self._attempt_entry(
                                session,
                                experiment,
                                version.id,
                                pending_frame,
                                pending_decision,
                                account,
                                position,
                                observation,
                                risk_config,
                                commission,
                                intent_row=intent_row,
                                execution_observation=executable,
                            )
                            pending = None
                            if filled:
                                return
                self._apply_protection(
                    session, experiment, position, observation, commission
                )
                if not (observation is observations[-1] and position.state != "FLAT"):
                    self._sample_equity(
                        session, experiment, account, position, observation, None
                    )

            for frame in decisions:
                while (
                    observation_index < len(observations)
                    and observations[observation_index].start_time < frame.frontier
                ):
                    consume(observations[observation_index])
                    observation_index += 1
                # Every native frontier is evaluated exactly once, regardless
                # of sparse execution availability.
                history.append(frame.decision_bar)
                evaluation = evaluate_strategy(
                    implementation,
                    StrategyContext(
                        frame.frontier,
                        frame.decision_bar.instrument,
                        tuple(history),
                        self._position_state(position.state),
                        True,
                    ),
                    params,
                    state,
                )
                state = evaluation.next_state
                if evaluation.decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                    decision = evaluation.decision
                    intent_row = self._create_intent(
                        session, experiment, version.id, frame, decision
                    )
                    if decision.entry_policy is EntryPolicy.IMMEDIATE:
                        observation = next(
                            (
                                item
                                for item in observations
                                if item.start_time > frame.frontier
                            ),
                            None,
                        )
                        if observation is None:
                            self._record_execution_gap(
                                session, experiment, frame.frontier
                            )
                            self._proposal_diagnostic(
                                session,
                                experiment,
                                intent_row,
                                "EXECUTION_DATA_UNAVAILABLE",
                                frame.frontier,
                                {},
                            )
                        else:
                            self._attempt_entry(
                                session,
                                experiment,
                                version.id,
                                frame,
                                decision,
                                account,
                                position,
                                observation,
                                risk_config,
                                commission,
                                intent_row=intent_row,
                            )
                            self._apply_protection(
                                session, experiment, position, observation, commission
                            )
                            if not (
                                observation is observations[-1]
                                and position.state != "FLAT"
                            ):
                                self._sample_equity(
                                    session,
                                    experiment,
                                    account,
                                    position,
                                    observation,
                                    None,
                                )
                            observation_index = max(
                                observation_index, observations.index(observation) + 1
                            )
                    else:
                        pending = (intent_row, frame, decision)
                # W6 is the first analytical frontier after the five fully
                # eligible execution windows.  Strategy state is authoritative
                # and clears the runner's pending handoff at that point.
                if pending is not None and state.phase is Phase.SEARCHING:
                    intent_row, _, decision = pending
                    self._proposal_diagnostic(
                        session,
                        experiment,
                        intent_row,
                        "EXPIRED",
                        frame.frontier,
                        {"reason": "STRATEGY_WINDOW_EXPIRED"},
                    )
                    pending = None
            while observation_index < len(observations):
                consume(observations[observation_index])
                observation_index += 1
            if pending is not None:
                intent_row, _, decision = pending
                self._proposal_diagnostic(
                    session,
                    experiment,
                    intent_row,
                    "EXPIRED",
                    experiment.trading_end,
                    {"reason": "NO_TRIGGER"},
                )
                pending = None
            if position.state != "FLAT":
                terminal = terminal_protection_observation(
                    observations, position.opened_at, experiment.trading_end
                )
                if terminal is None:
                    raise ExperimentFailureError(
                        ExperimentFailure(
                            FailureCategory.MARKET_DATA,
                            "EXECUTION_DATA_UNAVAILABLE",
                            "Historical protection outcome is unknowable",
                        )
                    )
                self._close_at_end(session, experiment, position, terminal, commission)
                self._sample_equity(
                    session, experiment, account, position, terminal, None
                )
            self._complete_v2(session, experiment, account)
            return ExperimentRunResult(
                experiment.id,
                "COMPLETED",
                bool(
                    session.scalar(
                        select(TradeModel.id).where(
                            TradeModel.experiment_id == experiment.id
                        )
                    )
                ),
            )
        except ExperimentFailureError as error:
            return self._fail(
                session,
                experiment,
                error.failure.category,
                error.failure.code,
                error.failure.detail,
            )
        except (StrategyContractError, StrategyEvaluationError, StateError, VersionError) as error:
            return self._fail(
                session,
                experiment,
                FailureCategory.STRATEGY,
                "STRATEGY_VERSION_UNAVAILABLE",
                _safe_failure_detail(error, "Strategy evaluation failed"),
            )
        except (ExecutionInputError, ExecutionRejected) as error:
            return self._fail(
                session, experiment, FailureCategory.EXECUTION,
                "EXECUTION_REJECTED", _safe_failure_detail(error, "Execution failed"),
            )
        except LookupError:
            return self._fail(
                session, experiment, FailureCategory.STRATEGY,
                "STRATEGY_VERSION_UNAVAILABLE",
                "Verified StrategyVersion implementation unavailable",
            )
        except SQLAlchemyError:
            return self._fail(
                session, experiment, FailureCategory.PERSISTENCE,
                "PERSISTENCE_FAILURE", "Experiment persistence failed",
            )
        except AggregationError as error:
            return self._fail(
                session, experiment, FailureCategory.MARKET_DATA,
                "MARKET_DATA_INVALID", _safe_failure_detail(error, "Market data is invalid"),
            )
        except ValueError as error:
            category, code = classify_runner_value_error(
                error, category=_failure_category_for_stage(stage)
            )
            return self._fail(
                session,
                experiment,
                category,
                code,
                _safe_failure_detail(error, "Experiment could not be run"),
            )
        except Exception:
            return self._fail(
                session,
                experiment,
                FailureCategory.VALIDATION,
                "UNEXPECTED_ENGINE_FAILURE",
                "Unexpected experiment engine failure",
            )

    def _record_execution_gap(self, session, experiment, frontier):
        existing = session.scalar(
            select(DatasetSnapshotGapModel).where(
                DatasetSnapshotGapModel.dataset_snapshot_id
                == experiment.dataset_snapshot_id,
                DatasetSnapshotGapModel.start_time == frontier,
                DatasetSnapshotGapModel.end_time == frontier + timedelta(minutes=1),
            )
        )
        sequence = (
            session.scalar(
                select(ExperimentGapDecisionModel.sequence)
                .where(ExperimentGapDecisionModel.experiment_id == experiment.id)
                .order_by(ExperimentGapDecisionModel.sequence.desc())
                .limit(1)
            )
            or 0
        )
        self.experiments.create_gap_decision(
            session,
            experiment_id=experiment.id,
            sequence=sequence + 1,
            start_time=frontier,
            end_time=frontier + timedelta(minutes=1),
            resolution="M1",
            price_component="BID",
            classification="BLOCKING",
            blocked=True,
            rule_version="ATLAS_HISTORICAL_GAP_POLICY_V1",
            policy_version="ATLAS_HISTORICAL_GAP_POLICY_V1",
            affected_state="ENTRY",
            affected_event="EXECUTION_DATA_UNAVAILABLE",
            details={
                "reason": "missing complete BID+ASK at exact decision frontier",
                "frontier": frontier.isoformat(),
                "source_gap": existing is not None,
            },
        )

    @staticmethod
    def _snapshot_bar(row, instrument, venue, fingerprint):
        from backend.persistence.market_data_repository import (
            SnapshotBar,
            SnapshotBarSourceIdentity,
        )

        bar = Bar(
            instrument=Instrument(instrument.code),
            provider=Provider(venue.provider),
            timeframe=Timeframe.M1,
            price_component=PriceComponent(row.price_component),
            start_time=row.start_time,
            end_time=row.end_time,
            open=row.open_price,
            high=row.high_price,
            low=row.low_price,
            close=row.close_price,
            volume=row.volume,
        )
        return SnapshotBar(
            bar,
            SnapshotBarSourceIdentity(
                row.id, fingerprint, row.source_request_id, row.retrieved_at
            ),
        )

    def _complete_v2(self, session, experiment, account):
        gaps = session.scalars(
            select(DatasetSnapshotGapModel)
            .where(
                DatasetSnapshotGapModel.dataset_snapshot_id
                == experiment.dataset_snapshot_id
            )
            .order_by(DatasetSnapshotGapModel.sequence)
        ).all()
        next_sequence = (
            session.scalar(
                select(ExperimentGapDecisionModel.sequence)
                .where(ExperimentGapDecisionModel.experiment_id == experiment.id)
                .order_by(ExperimentGapDecisionModel.sequence.desc())
                .limit(1)
            )
            or 0
        )
        for offset, gap in enumerate(gaps, 1):
            self.experiments.create_gap_decision(
                session,
                experiment_id=experiment.id,
                sequence=next_sequence + offset,
                start_time=gap.start_time,
                end_time=gap.end_time,
                resolution=gap.resolution,
                price_component=gap.price_component,
                classification=gap.classification,
                rule_version="ATLAS_HISTORICAL_GAP_POLICY_V1",
                policy_version="ATLAS_HISTORICAL_GAP_POLICY_V1",
                affected_state=None,
                affected_event=None,
                blocked=gap.blocked,
                details={"source": gap.source, "reason": gap.reason},
            )
        decisions = session.scalars(
            select(ExperimentGapDecisionModel).where(
                ExperimentGapDecisionModel.experiment_id == experiment.id
            )
        ).all()
        ambiguous = bool(
            session.scalar(
                select(TradeModel.id)
                .where(
                    TradeModel.experiment_id == experiment.id,
                    TradeModel.intrabar_ambiguous.is_(True),
                )
            )
        )
        quality = {
            "schema": "ATLAS_RESULT_QUALITY_V1",
            "value": result_quality_for_gaps(
                gaps,
                decisions,
                experiment.trading_start,
                experiment.trading_end,
                ambiguous=ambiguous,
            ),
        }
        self._complete_phase4(session, experiment, account, result_quality=quality)

    def _run_phase4(
        self, session: Session, experiment: ExperimentModel
    ) -> ExperimentRunResult:
        """Run the complete historical loop.  The caller owns the transaction."""
        stage = Phase4DiagnosticStage.PRECONDITIONS
        comparison: Phase4RunnerComparisonDiagnostic | None = None

        def mark(value: Phase4DiagnosticStage) -> None:
            nonlocal stage
            stage = value

        try:
            if experiment.status == "PENDING":
                self.experiments.mark_running(session, experiment.id)
            elif experiment.status != "RUNNING":
                raise ValueError("experiment is not pending or running")
            stage = Phase4DiagnosticStage.PRECONDITIONS
            if experiment.model_version != MODEL_VERSION:
                raise ValueError("unsupported experiment model")
            version_row = self.strategies.get_version(
                session, experiment.strategy_version_id
            )
            if version_row is None:
                raise ValueError("strategy version does not exist")
            version = version_to_domain(version_row)
            implementation = self.registry.implementation_for_version(version)
            snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
            if snapshot is None:
                raise ValueError("dataset snapshot does not exist")
            stage = Phase4DiagnosticStage.CONFIG_VALIDATION
            self._validate_phase4_config(experiment)
            slippage = experiment.simulation_config["slippage_model"]
            stage = Phase4DiagnosticStage.EXECUTION_ADAPTER_CONFIGURATION
            if not self._execution_supplied:
                self.execution = SimulatedExecutionAdapter(
                    slippage_ticks=slippage["ticks"],
                    tick_size=_decimal(slippage["tick_size"], "slippage tick_size"),
                )
            stage = Phase4DiagnosticStage.SNAPSHOT_MEMBER_LOAD
            descriptor = self.snapshots.by_fingerprint(session, snapshot.fingerprint)
            members = self.snapshots.ordered_members_with_sources(
                session,
                descriptor.id,
                descriptor.coverage_start,
                descriptor.coverage_end,
            )
            stage = Phase4DiagnosticStage.M15_AGGREGATION
            mid = tuple(
                item.bar
                for item in members
                if item.bar.price_component is PriceComponent.MID
            )
            m15, _diagnostics = aggregate_m1_to_m15(
                mid,
                PriceComponent.MID,
                descriptor.coverage_start,
                descriptor.coverage_end,
            )
            stage = Phase4DiagnosticStage.CLOCK_CONSTRUCTION
            clock = SimulationClock(
                members,
                m15,
                trading_start=experiment.trading_start,
                trading_end=experiment.trading_end,
                required_historical_context_bars=version.required_historical_context_bars,
            )
            account = session.scalar(
                select(ExperimentAccountModel).where(
                    ExperimentAccountModel.experiment_id == experiment.id
                )
            )
            position = session.scalar(
                select(PositionModel).where(
                    PositionModel.experiment_id == experiment.id
                )
            )
            if account is None or position is None:
                raise ValueError("experiment financial projections are missing")
            stage = Phase4DiagnosticStage.FINANCIAL_PROJECTION_LOAD
            stage = Phase4DiagnosticStage.CLOCK_MATERIALIZATION
            observations = tuple(clock.observations())
            frames = tuple(clock.frames())
            stage = Phase4DiagnosticStage.PRE_EXECUTION_INPUTS
            comparison = self._comparison_record(
                session,
                experiment,
                version_row,
                snapshot,
                members,
                account,
                position,
                execution=self.execution,
                execution_supplied=self._execution_supplied,
            )
            self._emit_comparison(comparison)
            decisions = {
                frame.frontier: frame
                for frame in frames
                if frame.phase is ClockPhase.DECISION
            }
            history: list = []
            state = StrategyState()
            # The first point is a balance snapshot at the requested period
            # boundary, not a proxy for the first executable candle close.
            stage = Phase4DiagnosticStage.INITIAL_EQUITY
            mark(Phase4DiagnosticStage.EQUITY_SAMPLING)
            self._sample_equity(session, experiment, account, position, None, 0)
            risk_config = RiskConfig(
                _decimal(experiment.risk_per_trade, "risk_per_trade")
            )
            params = _parameters(experiment.parameter_snapshot)
            commission = _decimal(
                experiment.simulation_config["commission_model"]["amount"], "commission"
            )
            stage = Phase4DiagnosticStage.STRATEGY_OBSERVATION_LOOP
            for warmup in (
                frame for frame in frames if frame.phase is ClockPhase.WARMUP
            ):
                mark(Phase4DiagnosticStage.WARMUP_EVALUATION)
                history.append(warmup.decision_bar)
                evaluation = evaluate_strategy(
                    implementation,
                    StrategyContext(
                        warmup.frontier,
                        warmup.decision_bar.instrument,
                        tuple(history),
                        PositionState.FLAT,
                        False,
                    ),
                    params,
                    state,
                )
                state = evaluation.next_state
            for observation_index, observation in enumerate(observations):
                frame = decisions.get(observation.start_time)
                if frame is not None:
                    mark(Phase4DiagnosticStage.DECISION_EVALUATION)
                    history.append(frame.decision_bar)
                    try:
                        evaluation = evaluate_strategy(
                            implementation,
                            StrategyContext(
                                frame.frontier,
                                frame.decision_bar.instrument,
                                tuple(history),
                                self._position_state(position.state),
                                True,
                            ),
                            params,
                            state,
                        )
                    except Exception as error:
                        raise ExperimentFailureError(
                            ExperimentFailure(
                                FailureCategory.STRATEGY,
                                "STRATEGY_EVALUATION_FAILED",
                                "Strategy evaluation failed",
                            )
                        ) from error
                    state = evaluation.next_state
                    if evaluation.decision.action in (
                        Action.OPEN_LONG,
                        Action.OPEN_SHORT,
                    ):
                        mark(Phase4DiagnosticStage.ENTRY_ATTEMPT)
                        self._attempt_entry(
                            session,
                            experiment,
                            version.id,
                            frame,
                            evaluation.decision,
                            account,
                            position,
                            observation,
                            risk_config,
                            commission,
                        )
                mark(Phase4DiagnosticStage.PROTECTION_APPLICATION)
                self._apply_protection(
                    session, experiment, position, observation, commission
                )
                # If the last eligible quote must close an exposed Position, defer
                # its equity point until after the END_OF_EXPERIMENT Fill.  The
                # terminal point must be the same realized state used by results.
                if not (
                    observation_index == len(observations) - 1
                    and position.state != "FLAT"
                ):
                    mark(Phase4DiagnosticStage.EQUITY_SAMPLING)
                    self._sample_equity(
                        session, experiment, account, position, observation, None
                    )
            stage = Phase4DiagnosticStage.END_CLOSE
            if position.state != "FLAT":
                if not observations:
                    raise ValueError("no final eligible M1 quote")
                final = observations[-1]
                self._close_at_end(session, experiment, position, final, commission)
                mark(Phase4DiagnosticStage.EQUITY_SAMPLING)
                self._sample_equity(session, experiment, account, position, final, None)
            stage = Phase4DiagnosticStage.RESULT_FINALIZATION
            self._complete_phase4(session, experiment, account, set_stage=mark)
            result = ExperimentRunResult(
                experiment.id,
                "COMPLETED",
                bool(
                    session.scalar(
                        select(TradeModel.id).where(
                            TradeModel.experiment_id == experiment.id
                        )
                    )
                ),
            )
            self._emit_terminal_comparison(comparison, stage, result)
            return result
        except ExperimentFailureError as error:
            result = self._fail(
                session,
                experiment,
                error.failure.category,
                error.failure.code,
                error.failure.detail,
            )
            self._emit_terminal_comparison(comparison, stage, result)
            return result
        except LookupError:
            result = self._fail(
                session,
                experiment,
                FailureCategory.STRATEGY,
                "STRATEGY_VERSION_UNAVAILABLE",
                "Verified StrategyVersion implementation unavailable",
            )
            self._emit_terminal_comparison(comparison, stage, result)
            return result
        except SQLAlchemyError:
            result = self._fail(
                session, experiment, FailureCategory.PERSISTENCE,
                "PERSISTENCE_FAILURE", "Experiment persistence failed",
            )
            self._emit_terminal_comparison(comparison, stage, result)
            return result
        except ValueError as error:
            self._emit_value_error_diagnostic(experiment, stage, error)
            category, code = classify_runner_value_error(
                error, category=_failure_category_for_stage(stage)
            )
            result = self._fail(
                session,
                experiment,
                category,
                code,
                "Experiment could not be run",
            )
            self._emit_terminal_comparison(comparison, stage, result)
            return result
        except Exception:
            result = self._fail(
                session,
                experiment,
                FailureCategory.VALIDATION,
                "UNEXPECTED_ENGINE_FAILURE",
                "Unexpected experiment engine failure",
            )
            self._emit_terminal_comparison(comparison, stage, result)
            return result

    def _emit_comparison(self, record: Phase4RunnerComparisonDiagnostic) -> None:
        if self._comparison_diagnostic_sink is None:
            return
        try:
            self._comparison_diagnostic_sink(record)
        except Exception:
            return

    def _emit_terminal_comparison(self, record, stage, result) -> None:
        if record is None:
            return
        self._emit_comparison(
            Phase4RunnerComparisonDiagnostic(
                **{
                    **record.as_dict(),
                    "checkpoint": "TERMINAL_RETURN",
                    "stage": stage,
                    "terminal_status": result.status,
                    "failure_category": result.failure.category.value
                    if result.failure
                    else None,
                    "failure_code": result.failure.code if result.failure else None,
                }
            )
        )

    @staticmethod
    def _comparison_record(
        session,
        experiment,
        version,
        snapshot,
        members,
        account,
        position,
        *,
        execution,
        execution_supplied,
    ):
        def digest(field, value):
            return _comparison_digest(field, value)

        strategy = {
            "version": version.version_number,
            "fingerprint": version.source_fingerprint,
            "implementation": version.implementation_key,
            "schema": version.parameter_schema,
            "timeframes": version.context_timeframes,
            "capabilities": version.capabilities,
            "primary": version.primary_timeframe,
            "required_historical_context_bars": version.required_historical_context_bars,
            "state_schema": version.state_schema_version,
        }
        snapshot_contract = {
            "base_resolution": snapshot.base_resolution,
            "components": snapshot.components,
            "coverage_start": snapshot.coverage_start,
            "coverage_end": snapshot.coverage_end,
            "alignment": snapshot.alignment_convention,
            "session_policy": snapshot.session_policy,
            "fingerprint_schema": snapshot.fingerprint_schema,
            "fingerprint": snapshot.fingerprint,
        }
        member_values = [
            {
                "venue": item.bar.instrument.value,
                "provider": item.bar.provider.value,
                "resolution": item.bar.timeframe.value,
                "component": item.bar.price_component.value,
                "start": item.bar.start_time,
                "end": item.bar.end_time,
                "open": item.bar.open,
                "high": item.bar.high,
                "low": item.bar.low,
                "close": item.bar.close,
                "volume": item.bar.volume,
                "source": item.source.content_fingerprint,
            }
            for item in members
        ]
        values = {
            "strategy_contract_digest": digest("strategy_contract", strategy),
            "snapshot_contract_digest": digest("snapshot_contract", snapshot_contract),
            "snapshot_membership_digest": digest("snapshot_membership", member_values),
            "parameters_digest": digest("parameters", experiment.parameter_snapshot),
            "risk_digest": digest(
                "risk",
                {"value": experiment.risk_per_trade, "config": experiment.risk_config},
            ),
            "simulation_digest": digest("simulation", experiment.simulation_config),
            "period_digest": digest(
                "period", [experiment.trading_start, experiment.trading_end]
            ),
            "capital_digest": digest("capital", experiment.starting_capital),
            "financial_projection_digest": digest(
                "financial_projection",
                {
                    "currency": account.base_currency,
                    "starting": account.starting_capital,
                    "realized": account.realized_pnl,
                    "unrealized": account.unrealized_pnl,
                    "equity": account.equity,
                    "position": position.state,
                },
            ),
            "effective_execution_digest": digest(
                "effective_execution",
                {
                    "supplied": execution_supplied,
                    "slippage": getattr(execution, "slippage", None),
                    "tick_size": getattr(execution, "tick_size", None),
                },
            ),
        }
        values["seed_profile_digest"] = digest(
            "seed_profile",
            [
                values["strategy_contract_digest"],
                values["snapshot_contract_digest"],
                values["snapshot_membership_digest"],
            ],
        )
        values["runner_inputs_digest"] = digest(
            "runner_inputs", list(values.values()) + [experiment.model_version]
        )
        return Phase4RunnerComparisonDiagnostic(
            "experiment_runner_comparison",
            "PRE_EXECUTION",
            Phase4DiagnosticStage.PRE_EXECUTION_INPUTS,
            "RESOLVED_SAME_ROW",
            values["strategy_contract_digest"],
            "RESOLVED_SAME_ROW",
            values["snapshot_contract_digest"],
            len(members),
            values["snapshot_membership_digest"],
            values["parameters_digest"],
            values["risk_digest"],
            values["simulation_digest"],
            values["period_digest"],
            values["capital_digest"],
            values["financial_projection_digest"],
            values["effective_execution_digest"],
            values["seed_profile_digest"],
            values["runner_inputs_digest"],
            None,
            None,
            None,
        )

    def _emit_value_error_diagnostic(
        self,
        experiment: ExperimentModel,
        stage: Phase4DiagnosticStage,
        error: ValueError,
    ) -> None:
        sink = self._value_error_diagnostic_sink
        if sink is None:
            return
        reason_code, observed_at = _diagnostic_details(str(error))
        diagnostic = Phase4ValueErrorDiagnostic(
            event="experiment_runner_value_error",
            experiment_id=experiment.id,
            model_version=experiment.model_version,
            run_path="V2",
            stage=stage,
            reason_code=reason_code,
            at=observed_at,
        )
        try:
            sink(diagnostic)
        except Exception:
            return

    @staticmethod
    def _position_state(value: str) -> PositionState:
        return {
            "FLAT": PositionState.FLAT,
            "LONG": PositionState.LONG,
            "SHORT": PositionState.SHORT,
        }[value]

    @staticmethod
    def _validate_phase4_config(experiment: ExperimentModel) -> None:
        config = experiment.simulation_config
        if config.get("schema_version") != "PHASE5_SIMULATION_CONFIG_V1":
            raise ValueError("invalid simulation config")
        if (
            config.get("execution_resolution") != "M1"
            or config.get("analysis_component") != "MID"
        ):
            raise ValueError("invalid simulation config")
        if config.get("execution_components") != ["BID", "ASK"]:
            raise ValueError("invalid simulation config")
        if config.get("spread_model") != "DATASET_BID_ASK_EMBEDDED":
            raise ValueError("invalid simulation config")
        slippage = config.get("slippage_model")
        if (
            not isinstance(slippage, dict)
            or slippage.get("type") != "ADVERSE_FIXED_TICKS"
        ):
            raise ValueError("invalid slippage model")
        if type(slippage.get("ticks")) is not int or slippage["ticks"] < 0:
            raise ValueError("invalid slippage model")
        tick_size = _decimal(slippage.get("tick_size"), "slippage tick_size")
        if tick_size <= 0:
            raise ValueError("invalid slippage model")
        commission_model = config.get("commission_model")
        if (
            not isinstance(commission_model, dict)
            or commission_model.get("type") != "PER_FILL_PER_UNIT_USD"
        ):
            raise ValueError("invalid commission model")
        commission = _decimal(commission_model.get("amount"), "commission")
        if commission < 0:
            raise ValueError("invalid commission")
        if config.get("financing_model") != {
            "type": "EXCLUDED",
            "disclosure": "FINANCING EXCLUDED",
        }:
            raise ValueError("invalid financing model")
        if config.get("intrabar_policy") != "STOP_LOSS_ADVERSE_FIRST_V1":
            raise ValueError("invalid intrabar policy")
        if config.get("target_fill_policy") != "REQUESTED_PRICE_NO_IMPROVEMENT_V1":
            raise ValueError("invalid target fill policy")
        if config.get("end_policy") != "FINAL_ELIGIBLE_M1_CLOSE_V1":
            raise ValueError("invalid end policy")
        if (
            config.get("equity_sampling")
            != "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1"
        ):
            raise ValueError("invalid equity sampling")
        risk_config = experiment.risk_config
        if (
            risk_config.get("schema_version") != "PHASE5_RISK_CONFIG_V1"
            or _decimal(risk_config.get("risk_per_trade"), "risk_per_trade")
            != _decimal(experiment.risk_per_trade, "risk_per_trade")
            or len(risk_config) != 2
        ):
            raise ValueError("invalid risk config")

    def _create_intent(self, session, experiment, version_id, frame, decision):
        assert (
            decision.direction is not None
            and decision.stop is not None
            and decision.target is not None
        )
        setup_facts = (
            decision.setup_facts.to_json() if decision.setup_facts is not None else None
        )
        evidence = {"setup_facts": setup_facts} if setup_facts is not None else {}
        landmarks = []
        if decision.setup_facts is not None:
            for name in ("reference", "sweep", "confirmation"):
                candle = getattr(decision.setup_facts, name)
                landmarks.append(
                    {
                        "kind": name,
                        "timestamp": candle.to_json()["timestamp"],
                        "price": candle.to_json()["close"],
                    }
                )
        return self.trading.create_intent(
            session,
            experiment_id=experiment.id,
            strategy_version_id=version_id,
            venue_instrument_id=experiment.venue_instrument_id,
            decision_frontier=frame.frontier,
            action=decision.action.value,
            direction=decision.direction.value,
            proposed_stop=decision.stop.price,
            target_multiple=decision.target.multiple,
            rationale={
                **decision.rationale.to_json(),
                "model_version": MODEL_VERSION,
                "source_m15_id": str(frame.decision_bar.start_time),
                "source_m1_ids": _source_ids(frame),
                "setup_facts": setup_facts,
                "evidence": evidence,
                "landmarks": landmarks,
            },
            entry_policy=decision.entry_policy.value,
            trigger_price=decision.trigger_price,
            trigger_price_basis=decision.trigger_price_basis.value
            if decision.trigger_price_basis
            else None,
            # The corrected Strategy's window is bar/frontier based.  The
            # legacy persistence column remains nullable but is not populated.
            expiry_time=None,
            expiry_bars=decision.expiry_bars,
        )

    def _proposal_diagnostic(
        self, session, experiment, intent, event, occurred_at, details
    ):
        sequence = (
            session.scalar(
                select(ExperimentProposalDiagnosticModel.sequence)
                .where(ExperimentProposalDiagnosticModel.experiment_id == experiment.id)
                .order_by(ExperimentProposalDiagnosticModel.sequence.desc())
                .limit(1)
            )
            or 0
        )
        self.trading.create_proposal_diagnostic(
            session,
            experiment_id=experiment.id,
            sequence=sequence + 1,
            trade_intent_id=intent.id,
            event_type=event,
            occurred_at=occurred_at,
            details={"event": event, **details},
        )

    def _attempt_entry(
        self,
        session,
        experiment,
        version_id,
        frame,
        decision,
        account,
        position,
        observation,
        risk_config,
        commission,
        *,
        intent_row=None,
        execution_observation=None,
    ):
        assert (
            decision.direction is not None
            and decision.stop is not None
            and decision.target is not None
        )
        intent = intent_row or self._create_intent(
            session, experiment, version_id, frame, decision
        )
        account_state = AccountState(account.base_currency, account.equity)
        intent_data = TradeIntent(
            decision.action, decision.direction, decision.stop.price, decision.target
        )
        preflight = self.risk.evaluate_pre_flight(
            intent_data,
            experiment_status=experiment.status,
            position=position.state,
            account=account_state,
            config=risk_config,
            instrument=frame.decision_bar.instrument,
        )
        self._persist_risk(session, intent.id, preflight, frame.frontier)
        if not preflight.approved:
            self._proposal_diagnostic(
                session,
                experiment,
                intent,
                "REJECTED",
                frame.frontier,
                {
                    "phase": "PRE_FLIGHT",
                    "reason": preflight.rejection.value
                    if preflight.rejection
                    else "UNKNOWN",
                },
            )
            return
        obs = execution_observation or _observation_from_m1(observation)
        # Risk must size from the same adverse-slipped entry that the adapter
        # will fill, while retaining raw BID/ASK as the executable provenance.
        slipped_quote = ExecutableQuote(
            obs.bid_open - self.execution.slippage
            if decision.direction.value == "SHORT"
            else obs.bid_open,
            obs.ask_open + self.execution.slippage
            if decision.direction.value == "LONG"
            else obs.ask_open,
        )
        submission = self.risk.evaluate_pre_submission(
            intent_data,
            experiment_status=experiment.status,
            position=position.state,
            account=account_state,
            config=risk_config,
            instrument=frame.decision_bar.instrument,
            quote=slipped_quote,
        )
        observation_time = (
            observation.start_time
            if hasattr(observation, "start_time")
            else observation.observed_at
        )
        submission_row = self._persist_risk(
            session, intent.id, submission, observation_time, obs
        )
        if not submission.approved:
            self._proposal_diagnostic(
                session,
                experiment,
                intent,
                "REJECTED",
                observation.start_time,
                {
                    "phase": "PRE_SUBMISSION",
                    "reason": submission.rejection.value
                    if submission.rejection
                    else "UNKNOWN",
                },
            )
            return
        assert submission.quantity is not None and submission.target_price is not None
        risk_decision_id = submission_row.id
        entry = self.trading.create_order(
            session,
            experiment_id=experiment.id,
            trade_intent_id=intent.id,
            risk_decision_id=risk_decision_id,
            order_type="MARKET",
            purpose="ENTRY",
            direction=decision.direction.value,
            quantity=submission.quantity,
            client_correlation_id=f"{experiment.id}:trade:{self._next_trade_sequence(session, experiment.id)}:entry",
        )
        fill = self.execution.execute(
            Order(
                entry.id,
                "MARKET",
                "ENTRY",
                decision.direction.value,
                submission.quantity,
            ),
            obs,
        )
        self._apply_fill(
            session,
            FillModel(
                order_id=fill.order_id,
                sequence_number=1,
                quantity=fill.quantity,
                execution_price=fill.execution_price,
                executed_at=fill.executed_at,
                fee=commission * fill.quantity,
                source_market_bar_id=fill.source_market_bar_id,
                price_basis=fill.price_basis,
                executable_reference_price=fill.executable_reference_price,
                slippage_per_unit=fill.slippage_per_unit,
                slippage_cost=fill.slippage_cost,
            ),
        )
        # Resolve protection from the Fill, never from a second slippage pass or
        # the pre-fill quote.  The pre-submission quote is deliberately the
        # adapter's predicted executable price; the equality check makes any
        # adapter/runner slippage drift a hard failure.
        if fill.execution_price != submission.entry_price:
            raise ValueError(
                "simulated fill diverged from pre-submission executable price"
            )
        actual_target = decision.target.resolve(
            fill.execution_price, submission.stop_price, decision.direction
        )
        stop = self.trading.create_order(
            session,
            experiment_id=experiment.id,
            trade_intent_id=intent.id,
            risk_decision_id=risk_decision_id,
            order_type="STOP",
            purpose="STOP_LOSS",
            direction=decision.direction.value,
            quantity=submission.quantity,
            requested_price=submission.stop_price,
            parent_entry_order_id=entry.id,
            client_correlation_id=f"{entry.id}:stop",
        )
        target = self.trading.create_order(
            session,
            experiment_id=experiment.id,
            trade_intent_id=intent.id,
            risk_decision_id=risk_decision_id,
            order_type="LIMIT",
            purpose="TAKE_PROFIT",
            direction=decision.direction.value,
            quantity=submission.quantity,
            requested_price=actual_target,
            parent_entry_order_id=entry.id,
            client_correlation_id=f"{entry.id}:target",
        )
        self._submit_order(session, stop, observation_time)
        self._submit_order(session, target, observation_time)
        self._apply_pair(
            session, experiment, position, stop, target, observation, commission
        )
        self._proposal_diagnostic(
            session,
            experiment,
            intent,
            "FILLED",
            fill.executed_at,
            {"price_basis": fill.price_basis},
        )
        return True

    def _submit_order(self, session, order, timestamp):
        order.current_status = "SUBMITTED"
        order.submitted_at = timestamp
        self.trading.append_order_event(
            session,
            order_id=order.id,
            sequence_number=2,
            event_type="ORDER_SUBMITTED",
            occurred_at=timestamp,
            details={},
        )

    @staticmethod
    def _next_trade_sequence(session, experiment_id):
        value = session.scalar(
            select(TradeModel.sequence_number)
            .where(TradeModel.experiment_id == experiment_id)
            .order_by(TradeModel.sequence_number.desc())
            .limit(1)
        )
        return int(value or 0) + 1

    def _apply_pair(
        self, session, experiment, position, stop, target, observation, commission
    ):
        decision = self.execution.execute_protection(
            Order(
                stop.id,
                "STOP",
                "STOP_LOSS",
                stop.direction,
                stop.quantity,
                stop.requested_price,
            ),
            Order(
                target.id,
                "LIMIT",
                "TAKE_PROFIT",
                target.direction,
                target.quantity,
                target.requested_price,
            ),
            _observation_from_m1(observation),
        )
        if decision.fill is None:
            return
        order = stop if decision.fill.order_id == stop.id else target
        self._apply_exit_fill(
            session, experiment, position, order, decision.fill, commission, decision
        )

    def _apply_protection(self, session, experiment, position, observation, commission):
        if position.state == "FLAT":
            return
        entry_id = session.scalar(
            select(TradeModel.entry_order_id).where(
                TradeModel.experiment_id == experiment.id, TradeModel.status == "OPEN"
            )
        )
        if entry_id is None:
            raise ValueError("open Position has no open Trade")
        stop = session.scalar(
            select(OrderModel).where(
                OrderModel.parent_entry_order_id == entry_id,
                OrderModel.purpose == "STOP_LOSS",
            )
        )
        target = session.scalar(
            select(OrderModel).where(
                OrderModel.parent_entry_order_id == entry_id,
                OrderModel.purpose == "TAKE_PROFIT",
            )
        )
        if stop is None or target is None:
            raise ValueError("open Trade has incomplete protection")
        self._apply_pair(
            session, experiment, position, stop, target, observation, commission
        )

    def _apply_exit_fill(
        self, session, experiment, position, order, fill, commission, decision=None
    ):
        self._apply_fill(
            session,
            FillModel(
                order_id=fill.order_id,
                sequence_number=1,
                quantity=fill.quantity,
                execution_price=fill.execution_price,
                executed_at=fill.executed_at,
                fee=commission * fill.quantity,
                source_market_bar_id=fill.source_market_bar_id,
                price_basis=fill.price_basis,
                executable_reference_price=fill.executable_reference_price,
                slippage_per_unit=fill.slippage_per_unit,
                slippage_cost=fill.slippage_cost,
            ),
            ambiguity_policy=decision.ambiguity_policy if decision else None,
            ambiguity_observed_at=fill.executed_at
            if decision and decision.ambiguous
            else None,
            ambiguity_source_market_bar_id=fill.source_market_bar_id
            if decision and decision.ambiguous
            else None,
        )

    def _close_at_end(self, session, experiment, position, observation, commission):
        trade = session.scalar(
            select(TradeModel).where(
                TradeModel.experiment_id == experiment.id, TradeModel.status == "OPEN"
            )
        )
        if trade is None:
            raise ValueError("open Position has no Trade at experiment end")
        order = self.trading.create_order(
            session,
            experiment_id=experiment.id,
            trade_intent_id=trade.trade_intent_id,
            risk_decision_id=session.scalar(
                select(OrderModel.risk_decision_id).where(
                    OrderModel.id == trade.entry_order_id
                )
            ),
            order_type="MARKET",
            purpose="EXIT",
            direction=trade.direction,
            quantity=trade.quantity,
            client_correlation_id=f"{experiment.id}:trade:{trade.sequence_number}:exit",
        )
        fill = self.execution.execute(
            Order(order.id, "MARKET", "EXIT", trade.direction, trade.quantity),
            _observation_from_m1(observation),
        )
        self._apply_exit_fill(session, experiment, position, order, fill, commission)

    def _sample_equity(
        self, session, experiment, account, position, observation, sequence
    ):
        if observation is None:
            when, bid, ask, bid_id, ask_id = (
                experiment.trading_start,
                None,
                None,
                None,
                None,
            )
        else:
            obs = _observation_from_m1(observation)
            when, bid, ask = observation.end_time, obs.bid_close, obs.ask_close
            bid_id, ask_id = obs.bid_source_market_bar_id, obs.ask_source_market_bar_id
        unrealized = Decimal("0")
        if position.state != "FLAT":
            if (
                bid is None
                or ask is None
                or position.entry_price is None
                or position.quantity is None
            ):
                raise ValueError("missing valuation quote")
            close = bid if position.state == "LONG" else ask
            unrealized = (
                (close - position.entry_price)
                if position.state == "LONG"
                else (position.entry_price - close)
            ) * position.quantity
        account.unrealized_pnl = unrealized
        account.equity = account.starting_capital + account.realized_pnl + unrealized
        previous = session.scalar(
            select(ExperimentEquityPointModel)
            .where(ExperimentEquityPointModel.experiment_id == experiment.id)
            .order_by(ExperimentEquityPointModel.sequence_number.desc())
            .limit(1)
        )
        seq = (previous.sequence_number + 1) if previous else 1
        peak = max(
            previous.running_peak if previous else experiment.starting_capital,
            account.equity,
        )
        drawdown = peak - account.equity
        percent = drawdown / peak if peak else Decimal("0")
        if previous is not None and previous.observed_at == when:
            return
        self.experiments.append_equity_point(
            session,
            experiment_id=experiment.id,
            sequence_number=seq,
            observed_at=when,
            balance=account.starting_capital + account.realized_pnl,
            realized_pnl=account.realized_pnl,
            unrealized_pnl=unrealized,
            equity=account.equity,
            running_peak=peak,
            drawdown_amount=drawdown,
            drawdown_percent=percent,
            valuation_bid=bid,
            valuation_ask=ask,
            source_bid_market_bar_id=bid_id,
            source_ask_market_bar_id=ask_id,
        )

    def _complete_phase4(
        self, session, experiment, account, set_stage=None, result_quality=None
    ):
        if set_stage is not None:
            set_stage(Phase4DiagnosticStage.TERMINAL_FACT_READ)
        trades = tuple(
            session.scalars(
                select(TradeModel)
                .where(TradeModel.experiment_id == experiment.id)
                .order_by(TradeModel.sequence_number)
            ).all()
        )
        equity = tuple(
            session.scalars(
                select(ExperimentEquityPointModel)
                .where(ExperimentEquityPointModel.experiment_id == experiment.id)
                .order_by(ExperimentEquityPointModel.sequence_number)
            ).all()
        )
        if not equity or any(trade.status != "COMPLETED" for trade in trades):
            raise ValueError("terminal financial state is incomplete")
        if set_stage is not None:
            set_stage(Phase4DiagnosticStage.METRICS_CALCULATION)
        metrics = calculate_metrics(
            trades, equity, starting_equity=experiment.starting_capital
        )
        gross = sum((trade.gross_pnl or Decimal("0") for trade in trades), Decimal("0"))
        commission = sum(
            (trade.commission_cost or Decimal("0") for trade in trades), Decimal("0")
        )
        max_dd = metrics.max_drawdown_amount.value or Decimal("0")
        max_dd_pct = metrics.max_drawdown_percent.value or Decimal("0")
        if set_stage is not None:
            set_stage(Phase4DiagnosticStage.SEMANTIC_PAYLOAD)
        payload = self._semantic_payload(
            session, experiment, trades, equity,
            metric_schema=RESULT_METRIC_SCHEMA_VERSION,
            sharpe_methodology=SHARPE_METHODOLOGY,
            result_quality=result_quality,
        )
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if set_stage is not None:
            set_stage(Phase4DiagnosticStage.RESULT_CREATE)
        self.experiments.create_result(
            session,
            experiment_id=experiment.id,
            result_schema_version=RESULT_SCHEMA_VERSION,
            trade_count=metrics.trade_count,
            ambiguous_trade_count=sum(bool(t.intrabar_ambiguous) for t in trades),
            gross_pnl=gross,
            commission_cost=commission,
            financing_cost=None,
            modeled_net_pnl=gross - commission,
            ending_balance=account.starting_capital + account.realized_pnl,
            ending_equity=account.equity,
            net_return=metrics.net_return.value or Decimal("0"),
            max_drawdown_amount=max_dd,
            max_drawdown_percent=max_dd_pct,
            financing_disclosure="FINANCING EXCLUDED",
            completed_market_time=experiment.trading_end,
            output_fingerprint=fingerprint,
            sharpe_ratio=metrics.sharpe_ratio.value,
            profit_factor=metrics.profit_factor.value,
            win_rate=metrics.win_rate.value,
            expectancy_net_pnl=metrics.expectancy_net_pnl.value,
            metric_states={
                name: getattr(metrics, name).as_dict()
                for name in (
                    "net_return", "max_drawdown_amount", "max_drawdown_percent",
                    "sharpe_ratio", "profit_factor", "win_rate", "expectancy_net_pnl",
                )
            },
            metric_schema_version=RESULT_METRIC_SCHEMA_VERSION,
            result_quality=result_quality,
        )
        if set_stage is not None:
            set_stage(Phase4DiagnosticStage.MARK_COMPLETED)
        self.experiments.mark_completed(session, experiment.id, datetime.now(UTC))

    @staticmethod
    def _semantic_payload(session, experiment, trades, equity, *, metric_schema,
                          sharpe_methodology, result_quality):
        def dec(value):
            return None if value is None else str(value)

        version = session.get(StrategyVersionModel, experiment.strategy_version_id)
        snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
        intents = session.scalars(
            select(TradeIntentModel)
            .where(TradeIntentModel.experiment_id == experiment.id)
            .order_by(TradeIntentModel.decision_frontier)
        ).all()
        risks = session.scalars(
            select(RiskDecisionModel)
            .join(TradeIntentModel)
            .where(TradeIntentModel.experiment_id == experiment.id)
            .order_by(RiskDecisionModel.evaluated_at, RiskDecisionModel.phase)
        ).all()
        order_rows = session.scalars(
            select(OrderModel).where(OrderModel.experiment_id == experiment.id)
        ).all()
        intent_frontiers = {i.id: i.decision_frontier for i in intents}
        purpose_order = {"ENTRY": 0, "STOP_LOSS": 1, "TAKE_PROFIT": 2, "EXIT": 3}
        orders = sorted(
            order_rows,
            key=lambda o: (
                intent_frontiers[o.trade_intent_id],
                purpose_order[o.purpose],
            ),
        )
        fills = session.scalars(
            select(FillModel)
            .join(OrderModel)
            .where(OrderModel.experiment_id == experiment.id)
            .order_by(FillModel.executed_at, FillModel.price_basis)
        ).all()
        risk_by_id = {r.id: r for r in risks}
        return {
            "model_version": experiment.model_version,
            "strategy_fingerprint": version.source_fingerprint if version else None,
            "dataset_fingerprint": snapshot.fingerprint if snapshot else None,
            "range": [
                experiment.trading_start.isoformat(),
                experiment.trading_end.isoformat(),
            ],
            "capital": dec(experiment.starting_capital),
            "risk": dec(experiment.risk_per_trade),
            "parameters": experiment.parameter_snapshot,
            "risk_config": experiment.risk_config,
            "simulation": experiment.simulation_config,
            "metric_schema": metric_schema,
            "sharpe_methodology": sharpe_methodology,
            "result_quality": result_quality,
            "intents": [
                [
                    i.decision_frontier.isoformat(),
                    i.action,
                    i.direction,
                    dec(i.proposed_stop),
                    dec(i.target_multiple),
                    i.rationale,
                ]
                for i in intents
            ],
            "risks": [
                [
                    r.phase,
                    r.outcome,
                    dec(r.quantity),
                    dec(r.entry_price),
                    dec(r.stop_price),
                    dec(r.target_price),
                    dec(r.risk_budget),
                    dec(r.actual_risk),
                    r.rejection_code,
                ]
                for r in risks
            ],
            "orders": [
                [
                    o.order_type,
                    o.purpose,
                    o.direction,
                    dec(o.quantity),
                    dec(o.requested_price),
                    o.parent_entry_order_id is not None,
                    risk_by_id[o.risk_decision_id].phase,
                    dec(risk_by_id[o.risk_decision_id].actual_risk),
                ]
                for o in orders
            ],
            "fills": [
                [
                    dec(f.quantity),
                    dec(f.execution_price),
                    f.price_basis,
                    dec(f.executable_reference_price),
                    dec(f.slippage_per_unit),
                    dec(f.fee),
                ]
                for f in fills
            ],
            "trades": [
                [
                    t.sequence_number,
                    t.direction,
                    dec(t.quantity),
                    dec(t.entry_price),
                    dec(t.exit_price),
                    t.exit_reason,
                    dec(t.initial_risk),
                    dec(t.gross_pnl),
                    dec(t.net_pnl),
                    bool(t.intrabar_ambiguous),
                ]
                for t in trades
            ],
            "equity": [
                [
                    p.sequence_number,
                    p.observed_at.isoformat(),
                    dec(p.balance),
                    dec(p.unrealized_pnl),
                    dec(p.equity),
                    dec(p.running_peak),
                    dec(p.drawdown_amount),
                    dec(p.drawdown_percent),
                ]
                for p in equity
            ],
        }

    def _open_and_close(
        self,
        session: Session,
        experiment: ExperimentModel,
        version_id: UUID,
        frame: ClockFrame,
        decision,
        account: ExperimentAccountModel,
        position: PositionModel,
        frames,
    ) -> ExperimentRunResult:
        direction = decision.direction
        assert (
            direction is not None
            and decision.stop is not None
            and decision.target is not None
        )
        intent = self.trading.create_intent(
            session,
            experiment_id=experiment.id,
            strategy_version_id=version_id,
            venue_instrument_id=experiment.venue_instrument_id,
            decision_frontier=frame.frontier,
            action=decision.action.value,
            direction=direction.value,
            proposed_stop=decision.stop.price,
            target_multiple=decision.target.multiple,
            rationale={
                **decision.rationale.to_json(),
                "model_version": MODEL_VERSION,
                "source_m1_ids": _source_ids(frame),
            },
        )
        account_state = AccountState(account.base_currency, account.equity)
        risk_config = RiskConfig(_decimal(experiment.risk_per_trade, "risk_per_trade"))
        risk_intent = TradeIntent(
            decision.action, direction, decision.stop.price, decision.target
        )
        preflight = self.risk.evaluate_pre_flight(
            risk_intent,
            experiment_status=experiment.status,
            position="FLAT",
            account=account_state,
            config=risk_config,
            instrument=frame.decision_bar.instrument,
        )
        self._persist_risk(session, intent.id, preflight, frame.frontier)
        if not preflight.approved:
            raise ExperimentFailureError(
                ExperimentFailure(
                    FailureCategory.RISK,
                    preflight.rejection.value if preflight.rejection else "REJECTED",
                    "Risk rejected the entry",
                )
            )
        observation = _observation(frame)
        submission = self.risk.evaluate_pre_submission(
            risk_intent,
            experiment_status=experiment.status,
            position="FLAT",
            account=account_state,
            config=risk_config,
            instrument=frame.decision_bar.instrument,
            quote=ExecutableQuote(observation.bid_open, observation.ask_open),
        )
        self._persist_risk(
            session, intent.id, submission, observation.observed_at, observation
        )
        if (
            not submission.approved
            or submission.quantity is None
            or submission.target_price is None
        ):
            raise ExperimentFailureError(
                ExperimentFailure(
                    FailureCategory.RISK,
                    submission.rejection.value if submission.rejection else "REJECTED",
                    "Risk rejected the entry",
                )
            )
        entry_order = self.trading.create_order(
            session,
            experiment_id=experiment.id,
            trade_intent_id=intent.id,
            risk_decision_id=self._last_risk_id(session, intent.id),
            order_type="MARKET",
            purpose="ENTRY",
            direction=direction.value,
            quantity=submission.quantity,
            client_correlation_id=f"{experiment.id}:entry",
        )
        fill = self.execution.execute(
            Order(
                entry_order.id, "MARKET", "ENTRY", direction.value, submission.quantity
            ),
            observation,
        )
        self._apply_fill(
            session,
            FillModel(
                order_id=fill.order_id,
                sequence_number=1,
                quantity=fill.quantity,
                execution_price=fill.execution_price,
                executed_at=fill.executed_at,
                fee=fill.fee,
            ),
        )
        target_order = self.trading.create_order(
            session,
            experiment_id=experiment.id,
            trade_intent_id=intent.id,
            risk_decision_id=self._last_risk_id(session, intent.id),
            order_type="LIMIT",
            purpose="TAKE_PROFIT",
            direction=direction.value,
            quantity=submission.quantity,
            requested_price=submission.target_price,
            client_correlation_id=f"{experiment.id}:target",
        )
        for next_frame in frames:
            try:
                exit_fill = self.execution.execute(
                    Order(
                        target_order.id,
                        "LIMIT",
                        "TAKE_PROFIT",
                        direction.value,
                        submission.quantity,
                        submission.target_price,
                    ),
                    _observation(next_frame),
                )
            except ExecutionRejected as error:
                if error.code.value == "UNSUPPORTED_PHASE3_INTRABAR_TRIGGER":
                    raise
                continue
            self._apply_fill(
                session,
                FillModel(
                    order_id=exit_fill.order_id,
                    sequence_number=1,
                    quantity=exit_fill.quantity,
                    execution_price=exit_fill.execution_price,
                    executed_at=exit_fill.executed_at,
                    fee=exit_fill.fee,
                ),
            )
            self.experiments.mark_completed(
                session, experiment.id, exit_fill.executed_at
            )
            return ExperimentRunResult(experiment.id, "COMPLETED", True)
        return self._fail(
            session, experiment, FailureCategory.EXECUTION, NOT_COMPLETED, NOT_COMPLETED
        )

    def _persist_risk(self, session, intent_id, decision, timestamp, observation=None):
        return self.trading.create_risk_decision(
            session,
            trade_intent_id=intent_id,
            phase=decision.phase.value,
            outcome="APPROVED" if decision.approved else "REJECTED",
            quantity=decision.quantity,
            entry_price=decision.entry_price,
            stop_price=decision.stop_price,
            target_price=decision.target_price,
            risk_budget=decision.risk_budget,
            actual_risk=decision.actual_risk,
            quote_bid=observation.bid_open if observation else None,
            quote_ask=observation.ask_open if observation else None,
            rejection_code=decision.rejection.value if decision.rejection else None,
            evaluated_at=timestamp,
        )

    def _last_risk_id(self, session, intent_id):
        return session.scalar(
            select(RiskDecisionModel.id)
            .where(RiskDecisionModel.trade_intent_id == intent_id)
            .order_by(RiskDecisionModel.id.desc())
        )

    def _fail(self, session, experiment, category, code, detail):
        sanitized_detail = " ".join(detail.split())[:500]
        if experiment is not None and experiment.status == "RUNNING":
            self.experiments.mark_failed(
                session,
                experiment.id,
                category=category.value,
                code=code,
                detail=sanitized_detail,
                completed_at=datetime.now(UTC),
            )
        return ExperimentRunResult(
            experiment.id if experiment else UUID(int=0),
            "FAILED",
            False,
            ExperimentFailure(category, code, sanitized_detail),
        )

    @staticmethod
    def _apply_fill(session, fill, **kwargs):
        """Keep fill/accounting validation owned by the accounting seam."""
        try:
            return apply_fill(session, fill, **kwargs)
        except ValueError as error:
            raise ExperimentFailureError(
                ExperimentFailure(
                    FailureCategory.VALIDATION,
                    "ACCOUNTING_INVARIANT",
                    _safe_failure_detail(error, "Accounting invariant failed"),
                )
            ) from error


class ExperimentFailureError(Exception):
    def __init__(self, failure: ExperimentFailure):
        self.failure = failure


def _safe_failure_detail(error: BaseException, fallback: str) -> str:
    detail = " ".join(str(error).split())[:500]
    return detail or fallback


def _failure_category_for_stage(stage: Phase4DiagnosticStage) -> FailureCategory:
    """Map the typed runner seam, rather than exception text, to ownership."""
    if stage in {
        Phase4DiagnosticStage.SNAPSHOT_MEMBER_LOAD,
        Phase4DiagnosticStage.M15_AGGREGATION,
        Phase4DiagnosticStage.CLOCK_CONSTRUCTION,
        Phase4DiagnosticStage.CLOCK_MATERIALIZATION,
    }:
        return FailureCategory.MARKET_DATA
    if stage in {
        Phase4DiagnosticStage.WARMUP_EVALUATION,
        Phase4DiagnosticStage.DECISION_EVALUATION,
        Phase4DiagnosticStage.STRATEGY_OBSERVATION_LOOP,
    }:
        return FailureCategory.STRATEGY
    return FailureCategory.VALIDATION


def classify_runner_value_error(
    error: ValueError,
    *,
    category: FailureCategory = FailureCategory.VALIDATION,
    code: str | None = None,
) -> tuple[FailureCategory, str]:
    """Classify a value error from its typed seam ownership, never its text."""
    return category, code or "INVALID_INPUT"


__all__ = [
    "ExperimentFailure",
    "ExperimentRunResult",
    "ExperimentRunner",
    "FailureCategory",
    "Phase4DiagnosticStage",
    "Phase4ValueErrorDiagnostic",
    "ValueErrorDiagnosticSink",
    "MODEL_VERSION",
    "RESULT_SCHEMA_VERSION",
    "NOT_COMPLETED",
]
