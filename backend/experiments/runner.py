# ruff: noqa: E501
"""The narrow Phase 3 historical Experiment orchestration boundary.

The runner is intentionally an application service, not a new execution
framework.  It composes the already-tested snapshot, clock, Strategy, Risk,
execution, repository, and Fill boundaries and keeps their ordering explicit.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import PriceComponent
from backend.domain.strategy import (
    Action,
    PositionState,
    StrategyContext,
    StrategyParameters,
    StrategyState,
)
from backend.execution.contract import ExecutionObservation, ExecutionRejected, Order
from backend.execution.fill_application import apply_fill
from backend.execution.simulated import SimulatedExecutionAdapter
from backend.market_data.aggregation import aggregate_m1_to_m15
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.market_data_repository import DatasetSnapshotRepository
from backend.persistence.models import (
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentModel,
    FillModel,
    PositionModel,
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
from backend.strategies.registry import StrategyRegistry

from .clock import ClockFrame, ClockPhase, SimulationClock


class FailureCategory(StrEnum):
    VALIDATION = "VALIDATION"
    MARKET_DATA = "MARKET_DATA"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    PERSISTENCE = "PERSISTENCE"


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


MODEL_VERSION = "PHASE3_OPEN_CHECKPOINT_V1"
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
    bid_bar, ask_bar = completed.get(PriceComponent.BID), completed.get(PriceComponent.ASK)
    return ExecutionObservation(
        observed_at=bid.bar.start_time,
        bid_open=bid.bar.open,
        ask_open=ask.bar.open,
        bid_high=bid_bar.high if bid_bar else None,
        bid_low=bid_bar.low if bid_bar else None,
        ask_high=ask_bar.high if ask_bar else None,
        ask_low=ask_bar.low if ask_bar else None,
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
    ) -> None:
        self.registry = strategy_registry
        self.snapshots = snapshot_repository or DatasetSnapshotRepository()
        self.strategies = strategy_repository or StrategyRepository()
        self.experiments = experiment_repository or ExperimentRepository()
        self.trading = trading_repository or TradingRepository()
        self.risk = risk_service or RiskService()
        self.execution = execution or SimulatedExecutionAdapter()

    def run(self, session: Session, experiment_id: UUID) -> ExperimentRunResult:
        experiment = self.experiments.get(session, experiment_id)
        try:
            if experiment is None or experiment.status != "RUNNING":
                raise ValueError("experiment is not running")
            if experiment.model_version != MODEL_VERSION:
                raise ValueError("unsupported experiment model")
            version_row = self.strategies.get_version(session, experiment.strategy_version_id)
            if version_row is None:
                raise ValueError("strategy version does not exist")
            version = version_to_domain(version_row)
            implementation = self.registry.implementation_for_version(version)
            snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
            if snapshot is None:
                raise ValueError("dataset snapshot does not exist")
            descriptor = self.snapshots.by_fingerprint(session, snapshot.fingerprint)
            members = self.snapshots.ordered_members_with_sources(
                session, descriptor.id, descriptor.coverage_start, descriptor.coverage_end
            )
            mid = tuple(item.bar for item in members if item.bar.price_component is PriceComponent.MID)
            m15 = aggregate_m1_to_m15(mid, PriceComponent.MID, descriptor.coverage_start, descriptor.coverage_end)
            clock = SimulationClock(
                members, m15, trading_start=experiment.trading_start,
                trading_end=experiment.trading_end, warmup_m15_bars=version.warm_up_bars,
            )
            account = session.scalar(select(ExperimentAccountModel).where(ExperimentAccountModel.experiment_id == experiment.id))
            position = session.scalar(select(PositionModel).where(PositionModel.experiment_id == experiment.id))
            if account is None or position is None:
                raise ValueError("experiment financial projections are missing")
            params = _parameters(experiment.parameter_snapshot)
            state = StrategyState()
            history: list = []
            frames = iter(clock)
            for frame in frames:
                history.append(frame.decision_bar)
                try:
                    evaluation = evaluate_strategy(
                        implementation,
                        StrategyContext(frame.frontier, frame.decision_bar.instrument, tuple(history), PositionState.FLAT, frame.exposure_allowed),
                        params, state,
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
                if frame.phase is ClockPhase.WARMUP or evaluation.decision.action not in (Action.OPEN_LONG, Action.OPEN_SHORT):
                    continue
                return self._open_and_close(session, experiment, version.id, frame, evaluation.decision, account, position, frames)
            return self._fail(session, experiment, FailureCategory.STRATEGY, NOT_COMPLETED, NOT_COMPLETED)
        except ExperimentFailureError as error:
            return self._fail(session, experiment, error.failure.category, error.failure.code, error.failure.detail)
        except ExecutionRejected as error:
            return self._fail(session, experiment, FailureCategory.EXECUTION, error.code.value, error.code.value)
        except LookupError:
            return self._fail(session, experiment, FailureCategory.STRATEGY, "STRATEGY_VERSION_UNAVAILABLE", "Verified StrategyVersion implementation unavailable")
        except ValueError as error:
            category = FailureCategory.VALIDATION
            text = str(error)
            if "snapshot" in text or "M1" in text or "bar" in text or "market" in text:
                category = FailureCategory.MARKET_DATA
            return self._fail(session, experiment, category, "INVALID_INPUT", "Experiment could not be run")
        except Exception:
            return self._fail(session, experiment, FailureCategory.PERSISTENCE, "PERSISTENCE_FAILURE", "Experiment persistence failed")

    def _open_and_close(self, session: Session, experiment: ExperimentModel, version_id: UUID, frame: ClockFrame, decision, account: ExperimentAccountModel, position: PositionModel, frames) -> ExperimentRunResult:
        direction = decision.direction
        assert direction is not None and decision.stop is not None and decision.target is not None
        intent = self.trading.create_intent(
            session, experiment_id=experiment.id, strategy_version_id=version_id,
            venue_instrument_id=experiment.venue_instrument_id, decision_frontier=frame.frontier,
            action=decision.action.value, direction=direction.value, proposed_stop=decision.stop.price,
            target_multiple=decision.target.multiple, rationale={**decision.rationale.to_json(), "model_version": MODEL_VERSION, "source_m1_ids": _source_ids(frame)},
        )
        account_state = AccountState(account.base_currency, account.equity)
        risk_config = RiskConfig(_decimal(experiment.risk_per_trade, "risk_per_trade"))
        risk_intent = TradeIntent(decision.action, direction, decision.stop.price, decision.target)
        preflight = self.risk.evaluate_pre_flight(risk_intent, experiment_status=experiment.status, position="FLAT", account=account_state, config=risk_config, instrument=frame.decision_bar.instrument)
        self._persist_risk(session, intent.id, preflight, frame.frontier)
        if not preflight.approved:
            raise ExperimentFailureError(ExperimentFailure(FailureCategory.RISK, preflight.rejection.value if preflight.rejection else "REJECTED", "Risk rejected the entry"))
        observation = _observation(frame)
        submission = self.risk.evaluate_pre_submission(risk_intent, experiment_status=experiment.status, position="FLAT", account=account_state, config=risk_config, instrument=frame.decision_bar.instrument, quote=ExecutableQuote(observation.bid_open, observation.ask_open))
        self._persist_risk(session, intent.id, submission, observation.observed_at, observation)
        if not submission.approved or submission.quantity is None or submission.target_price is None:
            raise ExperimentFailureError(ExperimentFailure(FailureCategory.RISK, submission.rejection.value if submission.rejection else "REJECTED", "Risk rejected the entry"))
        entry_order = self.trading.create_order(session, experiment_id=experiment.id, trade_intent_id=intent.id, risk_decision_id=self._last_risk_id(session, intent.id), order_type="MARKET", purpose="ENTRY", direction=direction.value, quantity=submission.quantity, client_correlation_id=f"{experiment.id}:entry")
        fill = self.execution.execute(Order(entry_order.id, "MARKET", "ENTRY", direction.value, submission.quantity), observation)
        apply_fill(session, FillModel(order_id=fill.order_id, sequence_number=1, quantity=fill.quantity, execution_price=fill.execution_price, executed_at=fill.executed_at, fee=fill.fee))
        target_order = self.trading.create_order(session, experiment_id=experiment.id, trade_intent_id=intent.id, risk_decision_id=self._last_risk_id(session, intent.id), order_type="LIMIT", purpose="TAKE_PROFIT", direction=direction.value, quantity=submission.quantity, requested_price=submission.target_price, client_correlation_id=f"{experiment.id}:target")
        for next_frame in frames:
            try:
                exit_fill = self.execution.execute(Order(target_order.id, "LIMIT", "TAKE_PROFIT", direction.value, submission.quantity, submission.target_price), _observation(next_frame))
            except ExecutionRejected as error:
                if error.code.value == "UNSUPPORTED_PHASE3_INTRABAR_TRIGGER":
                    raise
                continue
            apply_fill(session, FillModel(order_id=exit_fill.order_id, sequence_number=1, quantity=exit_fill.quantity, execution_price=exit_fill.execution_price, executed_at=exit_fill.executed_at, fee=exit_fill.fee))
            self.experiments.mark_completed(session, experiment.id, exit_fill.executed_at)
            return ExperimentRunResult(experiment.id, "COMPLETED", True)
        return self._fail(session, experiment, FailureCategory.EXECUTION, NOT_COMPLETED, NOT_COMPLETED)

    def _persist_risk(self, session, intent_id, decision, timestamp, observation=None):
        self.trading.create_risk_decision(session, trade_intent_id=intent_id, phase=decision.phase.value, outcome="APPROVED" if decision.approved else "REJECTED", quantity=decision.quantity, entry_price=decision.entry_price, stop_price=decision.stop_price, target_price=decision.target_price, risk_budget=decision.risk_budget, quote_bid=observation.bid_open if observation else None, quote_ask=observation.ask_open if observation else None, rejection_code=decision.rejection.value if decision.rejection else None, evaluated_at=timestamp)

    def _last_risk_id(self, session, intent_id):
        from backend.persistence.models import RiskDecisionModel
        return session.scalar(select(RiskDecisionModel.id).where(RiskDecisionModel.trade_intent_id == intent_id).order_by(RiskDecisionModel.id.desc()))

    def _fail(self, session, experiment, category, code, detail):
        sanitized_detail = " ".join(detail.split())[:500]
        if experiment is not None and experiment.status == "RUNNING":
            self.experiments.mark_failed(
                session, experiment.id, category=category.value,
                code=code, detail=sanitized_detail, completed_at=datetime.now(UTC),
            )
        return ExperimentRunResult(experiment.id if experiment else UUID(int=0), "FAILED", False, ExperimentFailure(category, code, sanitized_detail))


class ExperimentFailureError(Exception):
    def __init__(self, failure: ExperimentFailure):
        self.failure = failure


__all__ = ["ExperimentFailure", "ExperimentRunResult", "ExperimentRunner", "FailureCategory", "MODEL_VERSION", "NOT_COMPLETED"]
