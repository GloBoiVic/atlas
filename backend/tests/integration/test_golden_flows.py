# ruff: noqa: E501
"""PostgreSQL acceptance evidence for the V2 golden flows."""

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
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA_V2,
    GAP_POLICY_V1,
    SESSION_POLICY,
    Bar,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import StrategyVersion
from backend.experiments.runner import MODEL_VERSION, ExperimentRunner
from backend.integrations.oanda.capabilities import OANDA_CAPABILITY
from backend.market_data.fingerprint import (
    bar_content_fingerprint,
    dataset_fingerprint_v2,
)
from backend.market_data.ingestion import NATIVE_M15_CONTRACT_V1
from backend.market_data.session_calendar import is_session_open_minute
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.market_data_repository import (
    BarBatchItem,
    DatasetSnapshotRepository,
    MarketDataRepository,
)
from backend.persistence.models import (
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
from backend.strategies.ema_sweep_confirmation_break import (
    EmaSweepConfirmationBreakStrategy,
)
from backend.strategies.fingerprint import archive_source
from backend.strategies.production import EmaSweepConfirmationBreakCompatibilityAdaptor
from backend.strategies.registry import StrategyRegistry

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[3]
START = datetime(2026, 1, 5, tzinfo=UTC)


def _market_specification():
    return OANDA_CAPABILITY.market_specification(Instrument.EUR_USD)
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


def _m1_bar(
    moment: datetime,
    component: PriceComponent,
    value: Decimal,
    high: Decimal,
    low: Decimal,
) -> Bar:
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


def _golden_bars(
    direction: str, *, end_open: bool = False, m15_count: int = 104
) -> tuple[Bar, ...]:
    """Create sparse M1 BID/ASK data with one real reference/setup."""
    values: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]] = []
    for m15_index in range(m15_count):
        if m15_index == 100:
            candle = (
                (
                    Decimal("1.1020"),
                    Decimal("1.1030"),
                    Decimal("1.0995"),
                    Decimal("1.1010"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.0980"),
                    Decimal("1.1010"),
                    Decimal("1.0970"),
                    Decimal("1.0990"),
                )
            )
        elif m15_index == 101:
            candle = (
                (
                    Decimal("1.1000"),
                    Decimal("1.1040"),
                    Decimal("1.0980"),
                    Decimal("1.1035"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.1000"),
                    Decimal("1.1020"),
                    Decimal("1.0950"),
                    Decimal("1.0960"),
                )
            )
        elif m15_index == 102 and end_open:
            candle = (
                (
                    Decimal("1.1040"),
                    Decimal("1.1045"),
                    Decimal("1.1035"),
                    Decimal("1.1040"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.0960"),
                    Decimal("1.0965"),
                    Decimal("1.0955"),
                    Decimal("1.0960"),
                )
            )
        elif m15_index == 103 and end_open:
            candle = (
                (
                    Decimal("1.1000"),
                    Decimal("1.1050"),
                    Decimal("1.0980"),
                    Decimal("1.1040"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.1000"),
                    Decimal("1.1020"),
                    Decimal("1.0940"),
                    Decimal("1.0950"),
                )
            )
        elif m15_index == 102 and direction == "LONG":
            candle = (
                Decimal("1.1039"),
                Decimal("1.1042"),
                Decimal("1.1037"),
                Decimal("1.1039"),
            )
        elif m15_index == 102 and direction == "SHORT":
            candle = (
                Decimal("1.0956"),
                Decimal("1.0958"),
                Decimal("1.0954"),
                Decimal("1.0956"),
            )
        elif m15_index == 103 and direction == "LONG":
            candle = (
                Decimal("1.2000"),
                Decimal("1.2002"),
                Decimal("1.1998"),
                Decimal("1.2000"),
            )
        elif m15_index == 103:
            candle = (
                Decimal("0.9000"),
                Decimal("0.9002"),
                Decimal("0.8998"),
                Decimal("0.9000"),
            )
        else:
            candle = (
                Decimal("1.1000"),
                Decimal("1.1010"),
                Decimal("1.0990"),
                Decimal("1.1000"),
            )
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
        for component, offset in (
            (PriceComponent.BID, Decimal("-0.0001")),
            (PriceComponent.ASK, Decimal("0.0001")),
        ):
            result.append(
                _m1_bar(moment, component, open_ + offset, high + offset, low + offset)
            )
    return tuple(result)


def _native_m15_bars(
    direction: str, *, end_open: bool = False, m15_count: int = 104
) -> tuple[Bar, ...]:
    """Build the immutable native analytical product independently of M1 membership."""
    result: list[Bar] = []
    for m15_index in range(m15_count):
        if m15_index == 100:
            candle = (
                (
                    Decimal("1.1020"),
                    Decimal("1.1030"),
                    Decimal("1.0995"),
                    Decimal("1.1010"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.0980"),
                    Decimal("1.1010"),
                    Decimal("1.0970"),
                    Decimal("1.0990"),
                )
            )
        elif m15_index == 101:
            candle = (
                (
                    Decimal("1.1000"),
                    Decimal("1.1040"),
                    Decimal("1.0980"),
                    Decimal("1.1035"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.1000"),
                    Decimal("1.1020"),
                    Decimal("1.0950"),
                    Decimal("1.0960"),
                )
            )
        elif m15_index == 102 and end_open:
            candle = (
                (
                    Decimal("1.1040"),
                    Decimal("1.1045"),
                    Decimal("1.1035"),
                    Decimal("1.1040"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.0960"),
                    Decimal("1.0965"),
                    Decimal("1.0955"),
                    Decimal("1.0960"),
                )
            )
        elif m15_index == 103 and end_open:
            candle = (
                (
                    Decimal("1.1000"),
                    Decimal("1.1050"),
                    Decimal("1.0980"),
                    Decimal("1.1040"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.1000"),
                    Decimal("1.1020"),
                    Decimal("1.0940"),
                    Decimal("1.0950"),
                )
            )
        elif m15_index == 102:
            candle = (
                (
                    Decimal("1.1039"),
                    Decimal("1.1042"),
                    Decimal("1.1037"),
                    Decimal("1.1039"),
                )
                if direction == "LONG"
                else (
                    Decimal("1.0956"),
                    Decimal("1.0958"),
                    Decimal("1.0954"),
                    Decimal("1.0956"),
                )
            )
        elif m15_index == 103:
            candle = (
                (
                    Decimal("1.2000"),
                    Decimal("1.2002"),
                    Decimal("1.1998"),
                    Decimal("1.2000"),
                )
                if direction == "LONG"
                else (
                    Decimal("0.9000"),
                    Decimal("0.9002"),
                    Decimal("0.8998"),
                    Decimal("0.9000"),
                )
            )
        else:
            candle = (
                Decimal("1.1000"),
                Decimal("1.1010"),
                Decimal("1.0990"),
                Decimal("1.1000"),
            )
        moment = START + timedelta(minutes=m15_index * 15)
        result.append(
            Bar(
                Instrument.EUR_USD,
                Timeframe.M15,
                PriceComponent.MID,
                moment,
                moment + timedelta(minutes=15),
                *candle,
            )
        )
    return tuple(result)


def _registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(
        StrategyRegistration(
            EmaSweepConfirmationBreakStrategy.definition,
            EmaSweepConfirmationBreakCompatibilityAdaptor(),
        ),
        ROOT,
    )
    return registry


def _seed(
    session: Session,
    direction: str,
    *,
    slippage_ticks: int = 0,
    end_open: bool = False,
    complete_execution: bool = False,
    m15_count: int = 104,
) -> tuple[UUID, UUID, UUID]:
    venue = MarketDataRepository().ensure_initial_venue_instrument(
        session, VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    )
    bars = _golden_bars(direction, end_open=end_open, m15_count=m15_count)
    retrieved = START + timedelta(days=1)
    MarketDataRepository().apply_bar_batch(
        session,
        venue.id,
        tuple(
            BarBatchItem(bar, retrieved, f"golden-{direction.lower()}") for bar in bars
        ),
    )
    native = _native_m15_bars(
        direction, end_open=end_open, m15_count=m15_count
    )
    stored_bars = {
        (row.start_time, row.price_component): row
        for row in session.scalars(
            select(MarketBarModel).where(MarketBarModel.venue_instrument_id == venue.id)
        ).all()
    }
    # Keep the executable product intentionally sparse: the bounded entry quote
    # and one later quote that establishes the protected terminal outcome.
    executable_times = (
        {
            START + timedelta(minutes=1500 + offset)
            for offset in range(m15_count * 15 - 1500)
        }
        if complete_execution
        else {
            START + timedelta(minutes=1530),
            START + timedelta(minutes=1545),
            START + timedelta(minutes=1559),
        }
    )
    execution = tuple(
        (stored_bars[(bar.start_time, bar.price_component.value)], bar)
        for bar in bars
        if bar.start_time in executable_times
    )
    metadata = {
        "provider": "OANDA",
        "instrument": "EUR/USD",
        "coverage_start": START.isoformat(),
        "coverage_end": (START + timedelta(minutes=m15_count * 15)).isoformat(),
        "native_resolution": "M15",
        "analytical_contract": NATIVE_M15_CONTRACT_V1,
        "gap_policy": GAP_POLICY_V1,
    }
    analytical_members = tuple(
        {
            "sequence": i,
            "start_time": bar.start_time.isoformat(),
            "end_time": bar.end_time.isoformat(),
            "content_fingerprint": bar_content_fingerprint(bar),
        }
        for i, bar in enumerate(native, 1)
    )
    execution_members = tuple(
        {
            "sequence": i,
            "market_bar_id": str(row.id),
            "price_component": bar.price_component.value,
            "start_time": bar.start_time.isoformat(),
            "observation_fingerprint": bar_content_fingerprint(bar),
        }
        for i, (row, bar) in enumerate(execution, 1)
    )
    fingerprint = dataset_fingerprint_v2(
        metadata=metadata,
        analytical_members=analytical_members,
        execution_members=execution_members,
        gaps=(),
    )
    snapshot = DatasetSnapshot(
        uuid4(),
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        Timeframe.M15,
        (PriceComponent.MID,),
        START,
        START + timedelta(minutes=m15_count * 15),
        ALIGNMENT_CONVENTION,
        SESSION_POLICY,
        FINGERPRINT_SCHEMA_V2,
        fingerprint,
        integrity_summary={
            "status": "VALID",
            "policy_version": GAP_POLICY_V1,
            "analytical_count": len(native),
            "execution_count": len(execution),
            "gap_count": 0,
            "analytical_contract": NATIVE_M15_CONTRACT_V1,
        },
        created_at=START + timedelta(days=1),
        snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
    )
    snapshot = DatasetSnapshotRepository().create_v2_validated(
        session, snapshot, native, execution, ()
    )
    archive = archive_source(
        ROOT, EmaSweepConfirmationBreakStrategy.definition.source_files
    )
    strategy_repo = StrategyRepository()
    version = StrategyVersion(
        id=uuid4(),
        strategy_key="ema_sweep_confirmation_break",
        version_number=1,
        source_fingerprint=archive.fingerprint,
        implementation_key="ema_sweep_confirmation_break.v2",
        parameter_schema=EmaSweepConfirmationBreakStrategy.definition.parameter_schema,
        primary_timeframe=Timeframe.M15,
        required_historical_context_bars=100,
        state_schema_version=2,
        created_at=START,
    )
    version_row = strategy_repo.create_version(
        session,
        version,
        strategy_name="EMA Sweep Confirmation Break",
        strategy_description="golden",
        capabilities=("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT"),
        source_archive=archive,
    )
    experiment = ExperimentRepository().create(
        session,
        strategy_version_id=version_row.id,
        dataset_snapshot_id=snapshot.id,
        venue_instrument_id=venue.id,
        trading_start=START + timedelta(minutes=1500),
        trading_end=START + timedelta(minutes=1560),
        starting_capital=Decimal("10000"),
        risk_per_trade=Decimal("0.01"),
        parameter_snapshot=PARAMETERS,
        risk_config={"risk_per_trade": "0.01"},
        simulation_config={
            "resolution": "M1",
            "analysis_component": "MID",
            "execution_components": ["BID", "ASK"],
            "spread_model": "DATASET_BID_ASK_EMBEDDED",
            "slippage_model": {
                "type": "ADVERSE_FIXED_TICKS",
                "ticks": slippage_ticks,
                "tick_size": "0.00001",
            },
            "commission_model": {"type": "PER_FILL_PER_UNIT_USD", "amount": "0.10"},
            "financing_model": {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"},
        },
        model_version=MODEL_VERSION,
    )
    ExperimentRepository().create_account_and_position(session, experiment)
    return experiment.id, snapshot.id, version_row.id


def _facts(session: Session, experiment_id: UUID) -> dict[str, Any]:
    intents = session.scalars(
        select(TradeIntentModel)
        .where(TradeIntentModel.experiment_id == experiment_id)
        .order_by(TradeIntentModel.decision_frontier)
    ).all()
    assert intents
    risks = session.scalars(
        select(RiskDecisionModel)
        .where(RiskDecisionModel.trade_intent_id.in_([item.id for item in intents]))
        .order_by(RiskDecisionModel.evaluated_at, RiskDecisionModel.phase)
    ).all()
    orders = session.scalars(
        select(OrderModel)
        .where(OrderModel.experiment_id == experiment_id)
        .order_by(OrderModel.purpose)
    ).all()
    fills = session.scalars(
        select(FillModel)
        .join(OrderModel)
        .where(OrderModel.experiment_id == experiment_id)
        .order_by(FillModel.executed_at)
    ).all()
    trade = session.scalar(
        select(TradeModel)
        .where(TradeModel.experiment_id == experiment_id)
        .order_by(TradeModel.sequence_number)
    )
    equity = session.scalars(
        select(ExperimentEquityPointModel)
        .where(ExperimentEquityPointModel.experiment_id == experiment_id)
        .order_by(ExperimentEquityPointModel.sequence_number)
    ).all()
    result = session.get(ExperimentResultModel, experiment_id)
    account = session.get(ExperimentAccountModel, experiment_id)
    position = session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment_id)
    )
    assert trade is not None and account is not None and position is not None
    assert equity and result is not None
    return {
        "intents": [
            (
                intent.action,
                intent.direction,
                intent.decision_frontier,
                intent.proposed_stop,
                intent.target_multiple,
                intent.entry_policy,
                intent.trigger_price,
                intent.trigger_price_basis,
                intent.rationale,
            )
            for intent in intents
        ],
        "risks": [
            (
                r.phase,
                r.outcome,
                r.quantity,
                r.entry_price,
                r.stop_price,
                r.target_price,
                r.quote_bid,
                r.quote_ask,
            )
            for r in risks
        ],
        "orders": [
            (
                o.order_type,
                o.purpose,
                o.direction,
                o.quantity,
                o.requested_price,
                o.current_status,
            )
            for o in orders
        ],
        "fills": [
            (
                f.quantity,
                f.execution_price,
                f.price_basis,
                f.executable_reference_price,
                f.slippage_per_unit,
                f.slippage_cost,
                f.fee,
                f.source_market_bar_id,
            )
            for f in fills
        ],
        "trade": (
            trade.direction,
            trade.quantity,
            trade.entry_price,
            trade.exit_price,
            trade.gross_pnl,
            trade.net_pnl,
            trade.exit_reason,
            trade.initial_risk,
            trade.commission_cost,
            trade.intrabar_ambiguous,
        ),
        "account": (account.realized_pnl, account.equity),
        "position": position.state,
        "equity": [
            (
                point.sequence_number,
                point.observed_at,
                point.balance,
                point.realized_pnl,
                point.unrealized_pnl,
                point.equity,
                point.running_peak,
                point.drawdown_amount,
                point.drawdown_percent,
                point.valuation_bid,
                point.valuation_ask,
                point.source_bid_market_bar_id,
                point.source_ask_market_bar_id,
            )
            for point in equity
        ],
        "result": (
            result.result_schema_version,
            result.trade_count,
            result.ambiguous_trade_count,
            result.gross_pnl,
            result.commission_cost,
            result.financing_cost,
            result.modeled_net_pnl,
            result.ending_balance,
            result.ending_equity,
            result.net_return,
            result.max_drawdown_amount,
            result.max_drawdown_percent,
            result.sharpe_ratio,
            result.profit_factor,
            result.win_rate,
            result.expectancy_net_pnl,
            result.metric_states,
            result.metric_schema_version,
            result.result_quality,
            result.output_fingerprint,
        ),
    }


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_persisted_golden_flow_and_semantic_rerun(
    database_url: str, direction: str
) -> None:
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        with Session(engine) as session, session.begin():
            experiment_id, snapshot_id, version_id = _seed(session, direction)
        with Session(engine) as session, session.begin():
            result = ExperimentRunner(
                strategy_registry=_registry(),
                market_specification=_market_specification(),
            ).run(
                session, experiment_id
            )
            assert result.status == "COMPLETED" and result.trade_completed, (
                result.failure
            )
            completed = session.get(ExperimentModel, experiment_id)
            assert completed is not None
            assert completed.model_version == MODEL_VERSION
            assert completed.status == "COMPLETED"
            assert completed.dataset_snapshot_id == snapshot_id
            assert completed.strategy_version_id == version_id
            facts = _facts(session, experiment_id)
            assert facts["risks"][0][0:2] == ("PRE_FLIGHT", "APPROVED")
            assert facts["risks"][1][0:2] == ("PRE_SUBMISSION", "APPROVED")
            assert facts["intents"][0][2] == START + timedelta(minutes=1530)
            assert facts["position"] == "FLAT"
            assert facts["trade"][6] == "END_OF_EXPERIMENT"
            assert facts["fills"][0][1] == facts["risks"][1][3]
            assert facts["fills"][1][1] == facts["trade"][3]
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
            assert (
                ExperimentRunner(
                    strategy_registry=_registry(),
                    market_specification=_market_specification(),
                )
                .run(session, rerun_id)
                .status
                == "COMPLETED"
            )
            rerun_facts = _facts(session, rerun_id)
            assert rerun_facts == facts
            # A rerun is a new Experiment; it must not rewrite the completed
            # immutable facts of the original Experiment.
            assert _facts(session, experiment_id) == facts
    finally:
        engine.dispose()
