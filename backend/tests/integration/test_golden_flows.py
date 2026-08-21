# ruff: noqa: E501
"""PostgreSQL acceptance evidence for the two Phase 3 golden flows."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import StrategyVersion
from backend.execution.simulated import ProtectionDecision, SimulatedExecutionAdapter
from backend.experiments.runner import MODEL_VERSION, ExperimentRunner
from backend.market_data.fingerprint import dataset_fingerprint
from backend.market_data.session_calendar import is_session_open_minute
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.market_data_repository import (
    BarBatchItem,
    MarketDataRepository,
)
from backend.persistence.models import (
    DatasetSnapshotBarModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentEquityPointModel,
    ExperimentModel,
    ExperimentResultModel,
    FillModel,
    MarketBarModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    TradeIntentModel,
    TradeModel,
)
from backend.persistence.strategy_repository import StrategyRepository
from backend.strategies.contract import StrategyRegistration
from backend.strategies.ema_sweep_engulfing import EmaSweepEngulfingStrategy
from backend.strategies.fingerprint import archive_source
from backend.strategies.registry import StrategyRegistry

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[3]
START = datetime(2026, 1, 5, tzinfo=UTC)
PARAMETERS = {
    "ema_period": 100,
    "atr_period": 14,
    "stop_buffer": "0.5",
    "target_r": "1.7",
    "expiry_window": 5,
}


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is required for golden flows")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    os.environ["ATLAS_DATABASE_URL"] = value
    command.upgrade(config, "head")
    return value


def _m1_bar(moment: datetime, component: PriceComponent, value: Decimal, high: Decimal, low: Decimal) -> Bar:
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M1,
        component,
        moment,
        moment + timedelta(minutes=1),
        value,
        max(value, high),
        min(value, low),
        value,
    )


def _golden_bars(direction: str, *, phase4: bool = False, end_open: bool = False) -> tuple[Bar, ...]:
    """Create complete M1 MID/BID/ASK data with one real reference/setup."""
    values: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]] = []
    for m15_index in range(106 if phase4 else 104):
        if m15_index == 100:
            candle = (Decimal("1.1020"), Decimal("1.1030"), Decimal("1.0995"), Decimal("1.1010")) if direction == "LONG" else (Decimal("1.0980"), Decimal("1.1010"), Decimal("1.0970"), Decimal("1.0990"))
        elif m15_index == 101:
            candle = (Decimal("1.1000"), Decimal("1.1040"), Decimal("1.0980"), Decimal("1.1035")) if direction == "LONG" else (Decimal("1.1000"), Decimal("1.1020"), Decimal("1.0950"), Decimal("1.0960"))
        elif phase4 and m15_index == 102 and end_open:
            candle = (Decimal("1.1020"), Decimal("1.1025"), Decimal("1.1015"), Decimal("1.1020")) if direction == "LONG" else (Decimal("1.0980"), Decimal("1.0985"), Decimal("1.0975"), Decimal("1.0980"))
        elif phase4 and m15_index == 102:
            candle = (Decimal("1.1020"), Decimal("1.1030"), Decimal("1.0990"), Decimal("1.1010")) if direction == "LONG" else (Decimal("1.0980"), Decimal("1.1010"), Decimal("1.0970"), Decimal("1.0990"))
        elif phase4 and m15_index == 103 and end_open:
            candle = (Decimal("1.1040"), Decimal("1.1045"), Decimal("1.1035"), Decimal("1.1040")) if direction == "LONG" else (Decimal("1.0960"), Decimal("1.0965"), Decimal("1.0955"), Decimal("1.0960"))
        elif phase4 and m15_index == 103:
            candle = (Decimal("1.1000"), Decimal("1.1050"), Decimal("1.0980"), Decimal("1.1040")) if direction == "LONG" else (Decimal("1.1000"), Decimal("1.1020"), Decimal("1.0940"), Decimal("1.0950"))
        elif m15_index == 102 and direction == "LONG":
            candle = (Decimal("1.1039"), Decimal("1.1042"), Decimal("1.1037"), Decimal("1.1039"))
        elif m15_index == 102 and direction == "SHORT":
            candle = (Decimal("1.0956"), Decimal("1.0958"), Decimal("1.0954"), Decimal("1.0956"))
        elif m15_index == 103 and direction == "LONG":
            candle = (Decimal("1.2000"), Decimal("1.2002"), Decimal("1.1998"), Decimal("1.2000"))
        elif m15_index == 103:
            candle = (Decimal("0.9000"), Decimal("0.9002"), Decimal("0.8998"), Decimal("0.9000"))
        else:
            candle = (Decimal("1.1000"), Decimal("1.1010"), Decimal("1.0990"), Decimal("1.1000"))
        for minute in range(15):
            moment = START + timedelta(minutes=m15_index * 15 + minute)
            if not is_session_open_minute(moment):
                continue
            if minute == 0:
                value = candle[0]
            elif minute == 1:
                value = candle[1]
            elif minute == 2:
                value = candle[2]
            elif minute == 14:
                value = candle[3]
            else:
                value = candle[0]
            values.append((moment, value, candle[1], candle[2], value))

    result: list[Bar] = []
    for moment, open_, high, low, _close in values:
        mid = _m1_bar(moment, PriceComponent.MID, open_, high, low)
        result.append(mid)
        for component, offset in ((PriceComponent.BID, Decimal("-0.0001")), (PriceComponent.ASK, Decimal("0.0001"))):
            result.append(_m1_bar(moment, component, open_ + offset, high + offset, low + offset))
    return tuple(result)


def _registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(
        StrategyRegistration(EmaSweepEngulfingStrategy.definition, EmaSweepEngulfingStrategy()),
        ROOT,
    )
    return registry


def _seed(session: Session, direction: str, *, phase4: bool = False, invalid_config: bool = False, slippage_ticks: int = 0, end_open: bool = False) -> tuple[UUID, UUID, UUID]:
    venue = MarketDataRepository().ensure_initial_venue_instrument(
        session, VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    )
    bars = _golden_bars(direction, phase4=phase4, end_open=end_open)
    retrieved = START + timedelta(days=1)
    MarketDataRepository().apply_bar_batch(
        session, venue.id, tuple(BarBatchItem(bar, retrieved, f"golden-{direction.lower()}") for bar in bars)
    )
    fingerprint = dataset_fingerprint(
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        START,
        START + timedelta(minutes=1590 if phase4 else 1560),
        (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID),
        bars,
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    snapshot = DatasetSnapshotModel(
        venue_instrument_id=venue.id, base_resolution="M1",
        components=["ASK", "BID", "MID"], coverage_start=START,
        coverage_end=START + timedelta(minutes=1590 if phase4 else 1560),
        alignment_convention=ALIGNMENT_CONVENTION, session_policy=SESSION_POLICY,
        fingerprint_schema=FINGERPRINT_SCHEMA, fingerprint=fingerprint,
        integrity_summary={"status": "VALID", "expected_open_minutes": 1590 if phase4 else 1560, "expected_closure_minutes": 0, "member_minutes": 1590 if phase4 else 1560, "bar_count": len(bars), "unexpected_gap_count": 0, "unexpected_observation_count": 0, "session_policy": SESSION_POLICY},
    )
    session.add(snapshot)
    session.flush()
    session.add_all(DatasetSnapshotBarModel(dataset_snapshot_id=snapshot.id, market_bar_id=row.id) for row in session.scalars(select(MarketBarModel).where(MarketBarModel.venue_instrument_id == venue.id)).all())
    session.flush()
    archive = archive_source(ROOT, EmaSweepEngulfingStrategy.definition.source_files)
    strategy_repo = StrategyRepository()
    version = StrategyVersion(
        id=uuid4(), strategy_key="ema_sweep_engulfing", version_number=1,
        source_fingerprint=archive.fingerprint, implementation_key="ema_sweep_engulfing.v1",
        parameter_schema=EmaSweepEngulfingStrategy.definition.parameter_schema,
        primary_timeframe=Timeframe.M15, warm_up_bars=100, state_schema_version=1,
        created_at=START,
    )
    version_row = strategy_repo.create_version(session, version, strategy_name="EMA Sweep Engulfing", strategy_description="golden", capabilities=("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT"), source_archive=archive)
    experiment = ExperimentRepository().create(
        session, strategy_version_id=version_row.id, dataset_snapshot_id=snapshot.id,
        venue_instrument_id=venue.id, trading_start=START + timedelta(minutes=1500),
         trading_end=START + timedelta(minutes=1545 if end_open else (1590 if phase4 else 1560)), starting_capital=Decimal("10000"),
        risk_per_trade=Decimal("0.01"), parameter_snapshot=PARAMETERS,
         risk_config={"schema_version": "PHASE4_RISK_CONFIG_V1", "risk_per_trade": "0.01"} if phase4 else {"risk_per_trade": "0.01"}, simulation_config=(
             {"schema_version": "PHASE4_SIMULATION_CONFIG_V1", "execution_resolution": "M1", "analysis_component": "MID", "execution_components": ["BID", "ASK"], "spread_model": "DATASET_BID_ASK_EMBEDDED", "slippage_model": {"type": "ADVERSE_FIXED_TICKS", "ticks": slippage_ticks, "tick_size": "0.00001"}, "commission_model": {"type": "PER_FILL_PER_UNIT_USD", "amount": "0.10"}, "financing_model": {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"}, "intrabar_policy": "STOP_LOSS_ADVERSE_FIRST_V1", "target_fill_policy": "REQUESTED_PRICE_NO_IMPROVEMENT_V1", "end_policy": "FINAL_ELIGIBLE_M1_CLOSE_V1", "equity_sampling": "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1"}
            if phase4 and not invalid_config else {"schema_version": "PHASE4_SIMULATION_CONFIG_V1"}
            if phase4 else {"resolution": "M1"}
        ),
        model_version="PHASE4_HISTORICAL_EXECUTION_V1" if phase4 else MODEL_VERSION,
    )
    ExperimentRepository().create_account_and_position(session, experiment)
    return experiment.id, snapshot.id, version_row.id


def _facts(session: Session, experiment_id: UUID) -> dict[str, Any]:
    intent = session.scalar(select(TradeIntentModel).where(TradeIntentModel.experiment_id == experiment_id))
    assert intent is not None
    risks = session.scalars(select(RiskDecisionModel).where(RiskDecisionModel.trade_intent_id == intent.id).order_by(RiskDecisionModel.phase)).all()
    orders = session.scalars(select(OrderModel).where(OrderModel.experiment_id == experiment_id).order_by(OrderModel.purpose)).all()
    fills = session.scalars(select(FillModel).join(OrderModel).where(OrderModel.experiment_id == experiment_id).order_by(FillModel.executed_at)).all()
    trade = session.scalar(select(TradeModel).where(TradeModel.experiment_id == experiment_id))
    account = session.get(ExperimentAccountModel, experiment_id)
    position = session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment_id)
    )
    assert trade is not None and account is not None and position is not None
    return {"intent": (intent.action, intent.direction, intent.decision_frontier, intent.proposed_stop, intent.target_multiple, intent.rationale), "risks": [(r.phase, r.outcome, r.quantity, r.entry_price, r.target_price, r.quote_bid, r.quote_ask) for r in risks], "orders": [(o.order_type, o.purpose, o.direction, o.quantity, o.requested_price) for o in orders], "fills": [(f.quantity, f.execution_price) for f in fills], "trade": (trade.direction, trade.quantity, trade.entry_price, trade.exit_price, trade.gross_pnl, trade.exit_reason), "account": (account.realized_pnl, account.equity), "position": position.state}


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_persisted_golden_flow_and_semantic_rerun(database_url: str, direction: str) -> None:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("TRUNCATE experiments, dataset_snapshots, market_bars, strategy_versions, strategies, venue_instruments, instruments CASCADE"))
            experiment_id, snapshot_id, version_id = _seed(session, direction)
        with Session(engine) as session, session.begin():
            session.execute(text("SET TIME ZONE 'UTC'"))
            result = ExperimentRunner(strategy_registry=_registry()).run(session, experiment_id)
            assert result.status == "COMPLETED" and result.trade_completed, result.failure
            completed = session.get(ExperimentModel, experiment_id)
            assert completed is not None
            assert completed.model_version == MODEL_VERSION
            assert completed.status == "COMPLETED"
            assert completed.dataset_snapshot_id == snapshot_id
            assert completed.strategy_version_id == version_id
            facts = _facts(session, experiment_id)
            assert facts["risks"][0][0:2] == ("PRE_FLIGHT", "APPROVED")
            assert facts["risks"][1][0:2] == ("PRE_SUBMISSION", "APPROVED")
            assert facts["intent"][2] == START + timedelta(minutes=1530)
            assert facts["position"] == "FLAT"
            assert facts["trade"][5] == "TAKE_PROFIT"
            assert facts["fills"][0][1] == facts["risks"][1][3]
            assert facts["fills"][1][1] == facts["trade"][3]
            entry, stop, exit_price = facts["trade"][2], facts["intent"][3], facts["trade"][3]
            r = (exit_price - entry) / (entry - stop) if direction == "LONG" else (entry - exit_price) / (stop - entry)
            assert abs(r - Decimal("1.7")) < Decimal("0.000001")
            source_ids = facts["intent"][5]["source_m1_ids"]
            assert len(source_ids) == 3
            assert all(session.get(MarketBarModel, UUID(value)) is not None for value in source_ids)
        with Session(engine) as session, session.begin():
            original = session.get(ExperimentModel, experiment_id)
            assert original is not None
            rerun = ExperimentRepository().create(
                session,
                strategy_version_id=original.strategy_version_id,
                dataset_snapshot_id=original.dataset_snapshot_id,
                venue_instrument_id=original.venue_instrument_id,
                trading_start=original.trading_start,
                trading_end=original.trading_end,
                starting_capital=original.starting_capital,
                risk_per_trade=original.risk_per_trade,
                parameter_snapshot=original.parameter_snapshot,
                risk_config=original.risk_config,
                simulation_config=original.simulation_config,
                model_version=original.model_version,
            )
            ExperimentRepository().create_account_and_position(session, rerun)
            rerun_id = rerun.id
        with Session(engine) as session, session.begin():
            session.execute(text("SET TIME ZONE 'UTC'"))
            assert ExperimentRunner(strategy_registry=_registry()).run(session, rerun_id).status == "COMPLETED"
            rerun_facts = _facts(session, rerun_id)
            assert {k: v for k, v in rerun_facts.items() if k != "intent"} == {k: v for k, v in facts.items() if k != "intent"}
            assert rerun_facts["intent"][0:5] == facts["intent"][0:5]
    finally:
        engine.dispose()


@pytest.mark.parametrize("direction,slippage_ticks", [("LONG", 0), ("SHORT", 0), ("LONG", 2), ("SHORT", 2)])
def test_phase4_remediation_is_reproducible_and_records_starting_equity(database_url: str, direction: str, slippage_ticks: int) -> None:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("TRUNCATE experiments, dataset_snapshots, market_bars, strategy_versions, strategies, venue_instruments, instruments CASCADE"))
            experiment_id, _, _ = _seed(session, direction, phase4=True, slippage_ticks=slippage_ticks)
        with Session(engine) as session, session.begin():
            session.execute(text("SET TIME ZONE 'UTC'"))
            result = ExperimentRunner(strategy_registry=_registry()).run(session, experiment_id)
            assert result.status == "COMPLETED", result.failure
            experiment = session.get(ExperimentModel, experiment_id)
            assert experiment is not None
            risks = session.scalars(select(RiskDecisionModel).join(TradeIntentModel).where(TradeIntentModel.experiment_id == experiment_id)).all()
            orders = session.scalars(select(OrderModel).where(OrderModel.experiment_id == experiment_id)).all()
            trades = session.scalars(select(TradeModel).where(TradeModel.experiment_id == experiment_id).order_by(TradeModel.sequence_number)).all()
            equity = session.scalars(select(ExperimentEquityPointModel).where(ExperimentEquityPointModel.experiment_id == experiment_id).order_by(ExperimentEquityPointModel.sequence_number)).all()
            result_row = session.get(ExperimentResultModel, experiment_id)
            assert result_row is not None
            assert len(trades) >= 2
            assert {trade.direction for trade in trades} == {direction}
            assert all(order.risk_decision_id in {risk.id for risk in risks if risk.phase == "PRE_SUBMISSION"} for order in orders)
            assert all(trade.initial_risk is not None for trade in trades)
            first_risk = next(r for r in risks if r.phase == "PRE_SUBMISSION" and r.outcome == "APPROVED")
            first_fill = session.scalar(select(FillModel).join(OrderModel).where(OrderModel.experiment_id == experiment_id, OrderModel.purpose == "ENTRY"))
            assert first_fill is not None
            assert first_risk.entry_price == first_fill.execution_price
            assert abs(first_risk.actual_risk - first_risk.quantity * abs(first_risk.entry_price - first_risk.stop_price)) < Decimal("0.000001")
            if slippage_ticks:
                raw = first_risk.quote_ask if direction == "LONG" else first_risk.quote_bid
                assert first_fill.execution_price == raw + Decimal("0.00002") * (1 if direction == "LONG" else -1)
            assert equity[0].observed_at == experiment.trading_start
            assert len(equity) > 1
            assert result_row.ambiguous_trade_count >= 1
            first_fingerprint = result_row.output_fingerprint
            rerun = ExperimentRepository().create(session, strategy_version_id=experiment.strategy_version_id, dataset_snapshot_id=experiment.dataset_snapshot_id, venue_instrument_id=experiment.venue_instrument_id, trading_start=experiment.trading_start, trading_end=experiment.trading_end, starting_capital=experiment.starting_capital, risk_per_trade=experiment.risk_per_trade, parameter_snapshot=experiment.parameter_snapshot, risk_config=experiment.risk_config, simulation_config=experiment.simulation_config, model_version=experiment.model_version)
            ExperimentRepository().create_account_and_position(session, rerun)
            rerun_id = rerun.id
        with Session(engine) as session, session.begin():
            assert ExperimentRunner(strategy_registry=_registry()).run(session, rerun_id).status == "COMPLETED"
            rerun_result = session.get(ExperimentResultModel, rerun_id)
            assert rerun_result is not None
            original_experiment = session.get(ExperimentModel, experiment_id)
            original_trades = tuple(session.scalars(select(TradeModel).where(TradeModel.experiment_id == experiment_id).order_by(TradeModel.sequence_number)).all())
            original_equity = tuple(session.scalars(select(ExperimentEquityPointModel).where(ExperimentEquityPointModel.experiment_id == experiment_id).order_by(ExperimentEquityPointModel.sequence_number)).all())
            original_payload = ExperimentRunner._semantic_payload(session, original_experiment, original_trades, original_equity)
            rerun_trades = tuple(session.scalars(select(TradeModel).where(TradeModel.experiment_id == rerun_id).order_by(TradeModel.sequence_number)).all())
            rerun_equity = tuple(session.scalars(select(ExperimentEquityPointModel).where(ExperimentEquityPointModel.experiment_id == rerun_id).order_by(ExperimentEquityPointModel.sequence_number)).all())
            rerun_payload = ExperimentRunner._semantic_payload(session, session.get(ExperimentModel, rerun_id), rerun_trades, rerun_equity)
            assert original_payload == rerun_payload
            assert rerun_result.output_fingerprint == first_fingerprint
    finally:
        engine.dispose()


def test_phase4_failure_has_no_result(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("TRUNCATE experiments, dataset_snapshots, market_bars, strategy_versions, strategies, venue_instruments, instruments CASCADE"))
            experiment_id, _, _ = _seed(session, "LONG", phase4=True, invalid_config=True)
        with Session(engine) as session, session.begin():
            session.execute(text("SET TIME ZONE 'UTC'"))
            assert ExperimentRunner(strategy_registry=_registry()).run(session, experiment_id).status == "FAILED"
            assert session.get(ExperimentResultModel, experiment_id) is None
    finally:
        engine.dispose()


def test_phase4_end_close_is_atomic_and_terminal_equity_reconciles(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("TRUNCATE experiments, dataset_snapshots, market_bars, strategy_versions, strategies, venue_instruments, instruments CASCADE"))
            experiment_id, _, _ = _seed(session, "LONG", phase4=True, end_open=True)
        with Session(engine) as session, session.begin():
            session.execute(text("SET TIME ZONE 'UTC'"))
            class EndOnlyExecution(SimulatedExecutionAdapter):
                def execute_protection(self, stop, target, observation):
                    return ProtectionDecision(None)

            result = ExperimentRunner(strategy_registry=_registry(), execution=EndOnlyExecution()).run(session, experiment_id)
            assert result.status == "COMPLETED", result.failure
            experiment = session.get(ExperimentModel, experiment_id)
            result_row = session.get(ExperimentResultModel, experiment_id)
            position = session.scalar(select(PositionModel).where(PositionModel.experiment_id == experiment_id))
            trade = session.scalar(select(TradeModel).where(TradeModel.experiment_id == experiment_id))
            orders = session.scalars(select(OrderModel).where(OrderModel.experiment_id == experiment_id)).all()
            fills = session.scalars(select(FillModel).join(OrderModel).where(OrderModel.experiment_id == experiment_id).order_by(FillModel.executed_at)).all()
            equity = session.scalars(select(ExperimentEquityPointModel).where(ExperimentEquityPointModel.experiment_id == experiment_id).order_by(ExperimentEquityPointModel.sequence_number)).all()
            assert experiment is not None and result_row is not None and position is not None and trade is not None
            assert position.state == "FLAT"
            assert trade.status == "COMPLETED" and trade.exit_reason == "END_OF_EXPERIMENT"
            assert fills[-1].price_basis == "END_CLOSE"
            assert {order.purpose: order.current_status for order in orders}["EXIT"] == "FILLED"
            assert {order.purpose: order.current_status for order in orders}["STOP_LOSS"] == "CANCELED"
            assert {order.purpose: order.current_status for order in orders}["TAKE_PROFIT"] == "CANCELED"
            assert equity[-1].observed_at == experiment.trading_end
            assert equity[-1].equity == result_row.ending_equity == result_row.ending_balance
            assert trade.commission_cost == Decimal("0.10") * Decimal("2") * trade.quantity
    finally:
        engine.dispose()
