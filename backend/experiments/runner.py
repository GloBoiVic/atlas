# ruff: noqa: E501
"""The narrow Phase 3 historical Experiment orchestration boundary.

The runner is intentionally an application service, not a new execution
framework.  It composes the already-tested snapshot, clock, Strategy, Risk,
execution, repository, and Fill boundaries and keeps their ordering explicit.
"""

import hashlib
import json
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
    ExperimentEquityPointModel,
    ExperimentModel,
    FillModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    StrategyVersionModel,
    TradeIntentModel,
    TradeModel,
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

from .clock import ClockFrame, ClockPhase, M1Observation, SimulationClock


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
PHASE4_MODEL_VERSION = "PHASE4_HISTORICAL_EXECUTION_V1"
RESULT_SCHEMA_VERSION = "PHASE4_EXPERIMENT_RESULT_V1"
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


def _observation_from_m1(item: M1Observation) -> ExecutionObservation:
    bars = {entry.bar.price_component: entry for entry in item.bars}
    bid, ask = bars[PriceComponent.BID].bar, bars[PriceComponent.ASK].bar
    return ExecutionObservation(
        observed_at=item.start_time, bid_open=bid.open, ask_open=ask.open,
        bid_high=bid.high, bid_low=bid.low, ask_high=ask.high, ask_low=ask.low,
        bid_close=bid.close, ask_close=ask.close,
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
    ) -> None:
        self.registry = strategy_registry
        self.snapshots = snapshot_repository or DatasetSnapshotRepository()
        self.strategies = strategy_repository or StrategyRepository()
        self.experiments = experiment_repository or ExperimentRepository()
        self.trading = trading_repository or TradingRepository()
        self.risk = risk_service or RiskService()
        self.execution = execution or SimulatedExecutionAdapter()
        self._execution_supplied = execution is not None

    def run(self, session: Session, experiment_id: UUID) -> ExperimentRunResult:
        experiment = self.experiments.get(session, experiment_id)
        if experiment is not None and experiment.model_version == PHASE4_MODEL_VERSION:
            return self._run_phase4(session, experiment)
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

    def _run_phase4(self, session: Session, experiment: ExperimentModel) -> ExperimentRunResult:
        """Run the complete historical loop.  The caller owns the transaction."""
        try:
            if experiment.status == "PENDING":
                self.experiments.mark_running(session, experiment.id)
            elif experiment.status != "RUNNING":
                raise ValueError("experiment is not pending or running")
            if experiment.model_version != PHASE4_MODEL_VERSION:
                raise ValueError("unsupported experiment model")
            version_row = self.strategies.get_version(session, experiment.strategy_version_id)
            if version_row is None:
                raise ValueError("strategy version does not exist")
            version = version_to_domain(version_row)
            implementation = self.registry.implementation_for_version(version)
            snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
            if snapshot is None:
                raise ValueError("dataset snapshot does not exist")
            self._validate_phase4_config(experiment)
            slippage = experiment.simulation_config["slippage_model"]
            if not self._execution_supplied:
                self.execution = SimulatedExecutionAdapter(
                    slippage_ticks=slippage["ticks"],
                    tick_size=_decimal(slippage["tick_size"], "slippage tick_size"),
                )
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
            observations = tuple(clock.observations())
            frames = tuple(clock.frames())
            decisions = {frame.frontier: frame for frame in frames if frame.phase is ClockPhase.DECISION}
            history: list = []
            state = StrategyState()
            # The first point is a balance snapshot at the requested period
            # boundary, not a proxy for the first executable candle close.
            self._sample_equity(session, experiment, account, position, None, 0)
            risk_config = RiskConfig(_decimal(experiment.risk_per_trade, "risk_per_trade"))
            params = _parameters(experiment.parameter_snapshot)
            commission = _decimal(experiment.simulation_config["commission_model"]["amount"], "commission")
            for warmup in (frame for frame in frames if frame.phase is ClockPhase.WARMUP):
                history.append(warmup.decision_bar)
                evaluation = evaluate_strategy(
                    implementation,
                    StrategyContext(warmup.frontier, warmup.decision_bar.instrument, tuple(history), PositionState.FLAT, False),
                    params, state,
                )
                state = evaluation.next_state
            for observation_index, observation in enumerate(observations):
                frame = decisions.get(observation.start_time)
                if frame is not None:
                    history.append(frame.decision_bar)
                    try:
                        evaluation = evaluate_strategy(
                            implementation,
                            StrategyContext(frame.frontier, frame.decision_bar.instrument, tuple(history), self._position_state(position.state), True),
                            params, state,
                        )
                    except Exception as error:
                        raise ExperimentFailureError(ExperimentFailure(FailureCategory.STRATEGY, "STRATEGY_EVALUATION_FAILED", "Strategy evaluation failed")) from error
                    state = evaluation.next_state
                    if evaluation.decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                        self._attempt_entry(session, experiment, version.id, frame, evaluation.decision, account, position, observation, risk_config, commission)
                self._apply_protection(session, experiment, position, observation, commission)
                # If the last eligible quote must close an exposed Position, defer
                # its equity point until after the END_OF_EXPERIMENT Fill.  The
                # terminal point must be the same realized state used by results.
                if not (
                    observation_index == len(observations) - 1
                    and position.state != "FLAT"
                ):
                    self._sample_equity(session, experiment, account, position, observation, None)
            if position.state != "FLAT":
                if not observations:
                    raise ValueError("no final eligible M1 quote")
                final = observations[-1]
                self._close_at_end(session, experiment, position, final, commission)
                self._sample_equity(session, experiment, account, position, final, None)
            self._complete_phase4(session, experiment, account)
            return ExperimentRunResult(experiment.id, "COMPLETED", bool(session.scalar(select(TradeModel.id).where(TradeModel.experiment_id == experiment.id))))
        except ExperimentFailureError as error:
            return self._fail(session, experiment, error.failure.category, error.failure.code, error.failure.detail)
        except LookupError:
            return self._fail(session, experiment, FailureCategory.STRATEGY, "STRATEGY_VERSION_UNAVAILABLE", "Verified StrategyVersion implementation unavailable")
        except ValueError as error:
            category = FailureCategory.MARKET_DATA if any(word in str(error).lower() for word in ("snapshot", "m1", "bar", "market", "quote")) else FailureCategory.VALIDATION
            return self._fail(session, experiment, category, "INVALID_INPUT", "Experiment could not be run")
        except Exception:
            return self._fail(session, experiment, FailureCategory.PERSISTENCE, "PERSISTENCE_FAILURE", "Experiment persistence failed")

    @staticmethod
    def _position_state(value: str) -> PositionState:
        return {"FLAT": PositionState.FLAT, "LONG": PositionState.LONG, "SHORT": PositionState.SHORT}[value]

    @staticmethod
    def _validate_phase4_config(experiment: ExperimentModel) -> None:
        config = experiment.simulation_config
        if config.get("schema_version") != "PHASE4_SIMULATION_CONFIG_V1":
            raise ValueError("invalid simulation config")
        if config.get("execution_resolution") != "M1" or config.get("analysis_component") != "MID":
            raise ValueError("invalid simulation config")
        if config.get("execution_components") != ["BID", "ASK"]:
            raise ValueError("invalid simulation config")
        if config.get("spread_model") != "DATASET_BID_ASK_EMBEDDED":
            raise ValueError("invalid simulation config")
        slippage = config.get("slippage_model")
        if not isinstance(slippage, dict) or slippage.get("type") != "ADVERSE_FIXED_TICKS":
            raise ValueError("invalid slippage model")
        if type(slippage.get("ticks")) is not int or slippage["ticks"] < 0:
            raise ValueError("invalid slippage model")
        tick_size = _decimal(slippage.get("tick_size"), "slippage tick_size")
        if tick_size <= 0:
            raise ValueError("invalid slippage model")
        commission_model = config.get("commission_model")
        if not isinstance(commission_model, dict) or commission_model.get("type") != "PER_FILL_PER_UNIT_USD":
            raise ValueError("invalid commission model")
        commission = _decimal(commission_model.get("amount"), "commission")
        if commission < 0:
            raise ValueError("invalid commission")
        if config.get("financing_model") != {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"}:
            raise ValueError("invalid financing model")
        if config.get("intrabar_policy") != "STOP_LOSS_ADVERSE_FIRST_V1":
            raise ValueError("invalid intrabar policy")
        if config.get("target_fill_policy") != "REQUESTED_PRICE_NO_IMPROVEMENT_V1":
            raise ValueError("invalid target fill policy")
        if config.get("end_policy") != "FINAL_ELIGIBLE_M1_CLOSE_V1":
            raise ValueError("invalid end policy")
        if config.get("equity_sampling") != "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1":
            raise ValueError("invalid equity sampling")
        risk_config = experiment.risk_config
        if (
            risk_config.get("schema_version") != "PHASE4_RISK_CONFIG_V1"
            or _decimal(risk_config.get("risk_per_trade"), "risk_per_trade")
            != _decimal(experiment.risk_per_trade, "risk_per_trade")
            or len(risk_config) != 2
        ):
            raise ValueError("invalid risk config")

    def _attempt_entry(self, session, experiment, version_id, frame, decision, account, position, observation, risk_config, commission):
        assert decision.direction is not None and decision.stop is not None and decision.target is not None
        intent = self.trading.create_intent(
            session, experiment_id=experiment.id, strategy_version_id=version_id,
            venue_instrument_id=experiment.venue_instrument_id, decision_frontier=frame.frontier,
            action=decision.action.value, direction=decision.direction.value, proposed_stop=decision.stop.price,
            target_multiple=decision.target.multiple, rationale={**decision.rationale.to_json(), "model_version": PHASE4_MODEL_VERSION, "source_m1_ids": _source_ids(frame)},
        )
        account_state = AccountState(account.base_currency, account.equity)
        intent_data = TradeIntent(decision.action, decision.direction, decision.stop.price, decision.target)
        preflight = self.risk.evaluate_pre_flight(intent_data, experiment_status=experiment.status, position=position.state, account=account_state, config=risk_config, instrument=frame.decision_bar.instrument)
        self._persist_risk(session, intent.id, preflight, frame.frontier)
        if not preflight.approved:
            return
        obs = _observation_from_m1(observation)
        # Risk must size from the same adverse-slipped entry that the adapter
        # will fill, while retaining raw BID/ASK as the executable provenance.
        slipped_quote = ExecutableQuote(
            obs.bid_open - self.execution.slippage if decision.direction.value == "SHORT" else obs.bid_open,
            obs.ask_open + self.execution.slippage if decision.direction.value == "LONG" else obs.ask_open,
        )
        submission = self.risk.evaluate_pre_submission(intent_data, experiment_status=experiment.status, position=position.state, account=account_state, config=risk_config, instrument=frame.decision_bar.instrument, quote=slipped_quote)
        submission_row = self._persist_risk(session, intent.id, submission, observation.start_time, obs)
        if not submission.approved:
            return
        assert submission.quantity is not None and submission.target_price is not None
        risk_decision_id = submission_row.id
        entry = self.trading.create_order(session, experiment_id=experiment.id, trade_intent_id=intent.id, risk_decision_id=risk_decision_id, order_type="MARKET", purpose="ENTRY", direction=decision.direction.value, quantity=submission.quantity, client_correlation_id=f"{experiment.id}:trade:{self._next_trade_sequence(session, experiment.id)}:entry")
        fill = self.execution.execute(Order(entry.id, "MARKET", "ENTRY", decision.direction.value, submission.quantity), obs)
        apply_fill(session, FillModel(order_id=fill.order_id, sequence_number=1, quantity=fill.quantity, execution_price=fill.execution_price, executed_at=fill.executed_at, fee=commission * fill.quantity, source_market_bar_id=fill.source_market_bar_id, price_basis=fill.price_basis, executable_reference_price=fill.executable_reference_price, slippage_per_unit=fill.slippage_per_unit, slippage_cost=fill.slippage_cost))
        stop = self.trading.create_order(session, experiment_id=experiment.id, trade_intent_id=intent.id, risk_decision_id=risk_decision_id, order_type="STOP", purpose="STOP_LOSS", direction=decision.direction.value, quantity=submission.quantity, requested_price=submission.stop_price, parent_entry_order_id=entry.id, client_correlation_id=f"{entry.id}:stop")
        target = self.trading.create_order(session, experiment_id=experiment.id, trade_intent_id=intent.id, risk_decision_id=risk_decision_id, order_type="LIMIT", purpose="TAKE_PROFIT", direction=decision.direction.value, quantity=submission.quantity, requested_price=submission.target_price, parent_entry_order_id=entry.id, client_correlation_id=f"{entry.id}:target")
        self._submit_order(session, stop, observation.start_time)
        self._submit_order(session, target, observation.start_time)
        self._apply_pair(session, experiment, position, stop, target, observation, commission)

    def _submit_order(self, session, order, timestamp):
        order.current_status = "SUBMITTED"
        order.submitted_at = timestamp
        self.trading.append_order_event(session, order_id=order.id, sequence_number=2, event_type="ORDER_SUBMITTED", occurred_at=timestamp, details={})

    @staticmethod
    def _next_trade_sequence(session, experiment_id):
        value = session.scalar(select(TradeModel.sequence_number).where(TradeModel.experiment_id == experiment_id).order_by(TradeModel.sequence_number.desc()).limit(1))
        return int(value or 0) + 1

    def _apply_pair(self, session, experiment, position, stop, target, observation, commission):
        decision = self.execution.execute_protection(
            Order(stop.id, "STOP", "STOP_LOSS", stop.direction, stop.quantity, stop.requested_price),
            Order(target.id, "LIMIT", "TAKE_PROFIT", target.direction, target.quantity, target.requested_price),
            _observation_from_m1(observation),
        )
        if decision.fill is None:
            return
        order = stop if decision.fill.order_id == stop.id else target
        self._apply_exit_fill(session, experiment, position, order, decision.fill, commission, decision)

    def _apply_protection(self, session, experiment, position, observation, commission):
        if position.state == "FLAT":
            return
        entry_id = session.scalar(select(TradeModel.entry_order_id).where(TradeModel.experiment_id == experiment.id, TradeModel.status == "OPEN"))
        if entry_id is None:
            raise ValueError("open Position has no open Trade")
        stop = session.scalar(select(OrderModel).where(OrderModel.parent_entry_order_id == entry_id, OrderModel.purpose == "STOP_LOSS"))
        target = session.scalar(select(OrderModel).where(OrderModel.parent_entry_order_id == entry_id, OrderModel.purpose == "TAKE_PROFIT"))
        if stop is None or target is None:
            raise ValueError("open Trade has incomplete protection")
        self._apply_pair(session, experiment, position, stop, target, observation, commission)

    def _apply_exit_fill(self, session, experiment, position, order, fill, commission, decision=None):
        apply_fill(
            session,
            FillModel(order_id=fill.order_id, sequence_number=1, quantity=fill.quantity,
                      execution_price=fill.execution_price, executed_at=fill.executed_at,
                      fee=commission * fill.quantity, source_market_bar_id=fill.source_market_bar_id,
                      price_basis=fill.price_basis, executable_reference_price=fill.executable_reference_price,
                      slippage_per_unit=fill.slippage_per_unit, slippage_cost=fill.slippage_cost),
            ambiguity_policy=decision.ambiguity_policy if decision else None,
            ambiguity_observed_at=fill.executed_at if decision and decision.ambiguous else None,
            ambiguity_source_market_bar_id=fill.source_market_bar_id if decision and decision.ambiguous else None,
        )

    def _close_at_end(self, session, experiment, position, observation, commission):
        trade = session.scalar(select(TradeModel).where(TradeModel.experiment_id == experiment.id, TradeModel.status == "OPEN"))
        if trade is None:
            raise ValueError("open Position has no Trade at experiment end")
        order = self.trading.create_order(
            session, experiment_id=experiment.id, trade_intent_id=trade.trade_intent_id,
            risk_decision_id=session.scalar(select(OrderModel.risk_decision_id).where(OrderModel.id == trade.entry_order_id)),
            order_type="MARKET", purpose="EXIT", direction=trade.direction, quantity=trade.quantity,
            client_correlation_id=f"{experiment.id}:trade:{trade.sequence_number}:exit",
        )
        fill = self.execution.execute(Order(order.id, "MARKET", "EXIT", trade.direction, trade.quantity), _observation_from_m1(observation))
        self._apply_exit_fill(session, experiment, position, order, fill, commission)

    def _sample_equity(self, session, experiment, account, position, observation, sequence):
        if observation is None:
            when, bid, ask, bid_id, ask_id = experiment.trading_start, None, None, None, None
        else:
            obs = _observation_from_m1(observation)
            when, bid, ask = observation.end_time, obs.bid_close, obs.ask_close
            bid_id, ask_id = obs.bid_source_market_bar_id, obs.ask_source_market_bar_id
        unrealized = Decimal("0")
        if position.state != "FLAT":
            if bid is None or ask is None or position.entry_price is None or position.quantity is None:
                raise ValueError("missing valuation quote")
            close = bid if position.state == "LONG" else ask
            unrealized = ((close - position.entry_price) if position.state == "LONG" else (position.entry_price - close)) * position.quantity
        account.unrealized_pnl = unrealized
        account.equity = account.starting_capital + account.realized_pnl + unrealized
        previous = session.scalar(select(ExperimentEquityPointModel).where(ExperimentEquityPointModel.experiment_id == experiment.id).order_by(ExperimentEquityPointModel.sequence_number.desc()).limit(1))
        seq = (previous.sequence_number + 1) if previous else 1
        peak = max(previous.running_peak if previous else experiment.starting_capital, account.equity)
        drawdown = peak - account.equity
        percent = drawdown / peak if peak else Decimal("0")
        if previous is not None and previous.observed_at == when:
            return
        self.experiments.append_equity_point(session, experiment_id=experiment.id, sequence_number=seq, observed_at=when, balance=account.starting_capital + account.realized_pnl, realized_pnl=account.realized_pnl, unrealized_pnl=unrealized, equity=account.equity, running_peak=peak, drawdown_amount=drawdown, drawdown_percent=percent, valuation_bid=bid, valuation_ask=ask, source_bid_market_bar_id=bid_id, source_ask_market_bar_id=ask_id)

    def _complete_phase4(self, session, experiment, account):
        trades = tuple(session.scalars(select(TradeModel).where(TradeModel.experiment_id == experiment.id).order_by(TradeModel.sequence_number)).all())
        equity = tuple(session.scalars(select(ExperimentEquityPointModel).where(ExperimentEquityPointModel.experiment_id == experiment.id).order_by(ExperimentEquityPointModel.sequence_number)).all())
        if not equity or any(trade.status != "COMPLETED" for trade in trades):
            raise ValueError("terminal financial state is incomplete")
        gross = sum((trade.gross_pnl or Decimal("0") for trade in trades), Decimal("0"))
        commission = sum((trade.commission_cost or Decimal("0") for trade in trades), Decimal("0"))
        max_dd = max((point.drawdown_amount for point in equity), default=Decimal("0"))
        max_dd_pct = max((point.drawdown_percent for point in equity), default=Decimal("0"))
        payload = self._semantic_payload(session, experiment, trades, equity)
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.experiments.create_result(session, experiment_id=experiment.id, result_schema_version=RESULT_SCHEMA_VERSION, trade_count=len(trades), ambiguous_trade_count=sum(bool(t.intrabar_ambiguous) for t in trades), gross_pnl=gross, commission_cost=commission, financing_cost=None, modeled_net_pnl=gross - commission, ending_balance=account.starting_capital + account.realized_pnl, ending_equity=account.equity, net_return=(account.equity - account.starting_capital) / account.starting_capital, max_drawdown_amount=max_dd, max_drawdown_percent=max_dd_pct, financing_disclosure="FINANCING EXCLUDED", completed_market_time=experiment.trading_end, output_fingerprint=fingerprint)
        self.experiments.mark_completed(session, experiment.id, experiment.trading_end)

    @staticmethod
    def _semantic_payload(session, experiment, trades, equity):
        def dec(value): return None if value is None else str(value)
        version = session.get(StrategyVersionModel, experiment.strategy_version_id)
        snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
        intents = session.scalars(select(TradeIntentModel).where(TradeIntentModel.experiment_id == experiment.id).order_by(TradeIntentModel.decision_frontier)).all()
        risks = session.scalars(select(RiskDecisionModel).join(TradeIntentModel).where(TradeIntentModel.experiment_id == experiment.id).order_by(RiskDecisionModel.evaluated_at, RiskDecisionModel.phase)).all()
        order_rows = session.scalars(select(OrderModel).where(OrderModel.experiment_id == experiment.id)).all()
        intent_frontiers = {i.id: i.decision_frontier for i in intents}
        purpose_order = {"ENTRY": 0, "STOP_LOSS": 1, "TAKE_PROFIT": 2, "EXIT": 3}
        orders = sorted(order_rows, key=lambda o: (intent_frontiers[o.trade_intent_id], purpose_order[o.purpose]))
        fills = session.scalars(select(FillModel).join(OrderModel).where(OrderModel.experiment_id == experiment.id).order_by(FillModel.executed_at, FillModel.price_basis)).all()
        risk_by_id = {r.id: r for r in risks}
        return {"model_version": experiment.model_version, "strategy_fingerprint": version.source_fingerprint if version else None, "dataset_fingerprint": snapshot.fingerprint if snapshot else None, "range": [experiment.trading_start.isoformat(), experiment.trading_end.isoformat()], "capital": dec(experiment.starting_capital), "risk": dec(experiment.risk_per_trade), "parameters": experiment.parameter_snapshot, "risk_config": experiment.risk_config, "simulation": experiment.simulation_config, "intents": [[i.decision_frontier.isoformat(), i.action, i.direction, dec(i.proposed_stop), dec(i.target_multiple), i.rationale] for i in intents], "risks": [[r.phase, r.outcome, dec(r.quantity), dec(r.entry_price), dec(r.stop_price), dec(r.target_price), dec(r.risk_budget), dec(r.actual_risk), r.rejection_code] for r in risks], "orders": [[o.order_type, o.purpose, o.direction, dec(o.quantity), dec(o.requested_price), o.parent_entry_order_id is not None, risk_by_id[o.risk_decision_id].phase, dec(risk_by_id[o.risk_decision_id].actual_risk)] for o in orders], "fills": [[dec(f.quantity), dec(f.execution_price), f.price_basis, dec(f.executable_reference_price), dec(f.slippage_per_unit), dec(f.fee)] for f in fills], "trades": [[t.sequence_number, t.direction, dec(t.quantity), dec(t.entry_price), dec(t.exit_price), t.exit_reason, dec(t.initial_risk), dec(t.gross_pnl), dec(t.net_pnl), bool(t.intrabar_ambiguous)] for t in trades], "equity": [[p.sequence_number, p.observed_at.isoformat(), dec(p.balance), dec(p.unrealized_pnl), dec(p.equity), dec(p.running_peak), dec(p.drawdown_amount), dec(p.drawdown_percent)] for p in equity]}

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
        return self.trading.create_risk_decision(session, trade_intent_id=intent_id, phase=decision.phase.value, outcome="APPROVED" if decision.approved else "REJECTED", quantity=decision.quantity, entry_price=decision.entry_price, stop_price=decision.stop_price, target_price=decision.target_price, risk_budget=decision.risk_budget, actual_risk=decision.actual_risk, quote_bid=observation.bid_open if observation else None, quote_ask=observation.ask_open if observation else None, rejection_code=decision.rejection.value if decision.rejection else None, evaluated_at=timestamp)

    def _last_risk_id(self, session, intent_id):
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


__all__ = ["ExperimentFailure", "ExperimentRunResult", "ExperimentRunner", "FailureCategory", "MODEL_VERSION", "PHASE4_MODEL_VERSION", "RESULT_SCHEMA_VERSION", "NOT_COMPLETED"]
