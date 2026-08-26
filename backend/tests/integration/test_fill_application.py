"""PostgreSQL receipts for the Fill-only financial transition boundary."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.execution.fill_application import apply_fill
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.models import (
    ExperimentAccountModel,
    ExperimentModel,
    FillModel,
    InstrumentModel,
    OrderEventModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    StrategyModel,
    StrategyVersionModel,
    TradeIntentModel,
    TradeModel,
    VenueInstrumentModel,
)

pytestmark = pytest.mark.integration


@pytest.fixture()
def session() -> Generator[Session]:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("integration tests require a database name ending in _test")
    engine = configure_utc_session_timezone(create_engine(value))
    with Session(engine) as db:
        yield db
        db.rollback()
    engine.dispose()


def _seed(session: Session) -> tuple[ExperimentModel, OrderModel]:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    strategy = StrategyModel(
        strategy_key=f"test-{uuid4()}", name="test", description="test"
    )
    session.add(strategy)
    session.flush()
    version = StrategyVersionModel(
        strategy_id=strategy.id, version_number=1, source_fingerprint="a" * 64,
        implementation_key="test", parameter_schema=[], context_timeframes=[],
        capabilities=[], source_manifest=[], exact_source_snapshot={},
        primary_timeframe="M15",
        required_historical_context_bars=100,
        state_schema_version=1,
    )
    instrument = InstrumentModel(
        code="EUR/USD", base_currency="EUR", quote_currency="USD"
    )
    session.add_all([version, instrument])
    session.flush()
    venue = VenueInstrumentModel(
        instrument_id=instrument.id, provider="OANDA", provider_symbol="EUR_USD"
    )
    session.add(venue)
    session.flush()
    snapshot_id = uuid4()
    session.execute(
        text(
            "INSERT INTO dataset_snapshots "
            "(id, venue_instrument_id, base_resolution, components, coverage_start, "
            "coverage_end, alignment_convention, session_policy, fingerprint_schema, "
            "fingerprint, integrity_summary) VALUES "
            "(:id, :venue, 'M1', :components, :start, :end, "
            "'UTC_HALF_OPEN_V1', 'OANDA_FX_NY_V1', "
            "'ATLAS_DATASET_SHA256_V1', :fingerprint, :summary)"
        ),
        {"id": snapshot_id, "venue": venue.id,
         "start": now, "end": now + timedelta(hours=1),
         "components": '["ASK","BID","MID"]',
         "fingerprint": "b" * 64,
         "summary": '{"status":"VALID","expected_open_minutes":60,'
         '"expected_closure_minutes":0,"member_minutes":60,'
         '"bar_count":1,"unexpected_gap_count":0,'
         '"unexpected_observation_count":0,"session_policy":"OANDA_FX_NY_V1"}'},
    )
    experiment = ExperimentModel(
        strategy_version_id=version.id, dataset_snapshot_id=snapshot_id,
        venue_instrument_id=venue.id, trading_start=now,
        trading_end=now + timedelta(hours=1), starting_capital=Decimal("10000"),
        risk_per_trade=Decimal("0.01"), parameter_snapshot={}, risk_config={},
        simulation_config={}, model_version="PHASE5_HISTORICAL_EXECUTION_V2",
    )
    session.add(experiment)
    session.flush()
    session.add_all([
        ExperimentAccountModel(experiment_id=experiment.id,
                               starting_capital=Decimal("10000"),
                               equity=Decimal("10000")),
        PositionModel(experiment_id=experiment.id, venue_instrument_id=venue.id),
    ])
    intent = TradeIntentModel(
        experiment_id=experiment.id, strategy_version_id=version.id,
        venue_instrument_id=venue.id, decision_frontier=now,
        action="OPEN_LONG", direction="LONG", proposed_stop=Decimal("1.09"),
        target_multiple=Decimal("2"), rationale={
            "setup_facts": {"reference": {"timestamp": now.isoformat().replace("+00:00", "Z"), "close": "1.11"}},
            "evidence": {"setup_facts": {"reference": {"close": "1.11"}}},
            "landmarks": [{"kind": "reference", "timestamp": now.isoformat().replace("+00:00", "Z"), "price": "1.11"}],
        },
    )
    session.add(intent)
    session.flush()
    risk = RiskDecisionModel(
        trade_intent_id=intent.id, phase="PRE_SUBMISSION", outcome="APPROVED",
        quantity=Decimal("10"), entry_price=Decimal("1.10"),
        stop_price=Decimal("1.09"), target_price=Decimal("1.12"),
        risk_budget=Decimal("1"), evaluated_at=now,
    )
    session.add(risk)
    session.flush()
    order = OrderModel(
        experiment_id=experiment.id, trade_intent_id=intent.id,
        risk_decision_id=risk.id, order_type="MARKET", purpose="ENTRY",
        direction="LONG", quantity=Decimal("10"),
        client_correlation_id=str(uuid4()),
    )
    session.add(order)
    session.flush()
    return experiment, order


def test_trade_intent_structured_setup_facts_survive_retrieval(session: Session) -> None:
    experiment, _ = _seed(session)
    intent = session.scalar(select(TradeIntentModel).where(TradeIntentModel.experiment_id == experiment.id))
    assert intent is not None
    assert intent.rationale["setup_facts"]["reference"]["close"] == "1.11"
    assert intent.rationale["evidence"]["setup_facts"]["reference"]["close"] == "1.11"
    assert intent.rationale["landmarks"][0]["kind"] == "reference"


def test_entry_fill_is_the_only_exposure_transition(session: Session) -> None:
    experiment, order = _seed(session)
    position = session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment.id)
    )
    assert position is not None and position.state == "FLAT"
    apply_fill(session, FillModel(
        order_id=order.id, sequence_number=1, quantity=Decimal("10"),
        execution_price=Decimal("1.10"),
        executed_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        fee=Decimal("0"),
    ))
    position = session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment.id)
    )
    assert position is not None
    assert position.state == "LONG"
    assert position.quantity == Decimal("10")
    assert session.scalar(
        select(OrderModel.current_status).where(OrderModel.id == order.id)
    ) == "FILLED"
    assert session.scalar(
        select(OrderModel.submitted_at).where(OrderModel.id == order.id)
    ) == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    events = session.scalars(
        select(OrderEventModel)
        .where(OrderEventModel.order_id == order.id)
        .order_by(OrderEventModel.sequence_number)
    ).all()
    assert [event.event_type for event in events] == ["ORDER_SUBMITTED", "ORDER_FILLED"]


def test_failed_fill_rolls_back_all_projections(session: Session) -> None:
    experiment, order = _seed(session)
    position = session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment.id)
    )
    assert position is not None
    position.state = "LONG"
    position.quantity = Decimal("10")
    position.entry_price = Decimal("1.10")
    position.opened_at = datetime(2026, 1, 1, tzinfo=UTC)
    session.flush()
    with pytest.raises(ValueError, match="entry Fill"):
        apply_fill(session, FillModel(
            order_id=order.id, sequence_number=1, quantity=Decimal("10"),
            execution_price=Decimal("1.10"),
            executed_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            fee=Decimal("0"),
        ))
    order_after = session.get(OrderModel, order.id)
    assert order_after is not None
    assert order_after.current_status == "PENDING_SUBMISSION"
    assert session.scalar(
        select(FillModel).where(FillModel.order_id == order.id)
    ) is None


def test_v2_end_close_uses_constrained_historical_exit_reason(session: Session) -> None:
    experiment, entry = _seed(session)
    apply_fill(session, FillModel(
        order_id=entry.id, sequence_number=1, quantity=Decimal("10"),
        execution_price=Decimal("1.10"),
        executed_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC), fee=Decimal("0"),
    ))
    risk_id = entry.risk_decision_id
    intent_id = entry.trade_intent_id
    exit_order = OrderModel(
        experiment_id=experiment.id, trade_intent_id=intent_id,
        risk_decision_id=risk_id, order_type="MARKET", purpose="EXIT",
        direction="LONG", quantity=Decimal("10"),
        client_correlation_id=str(uuid4()),
    )
    session.add(exit_order)
    session.flush()
    apply_fill(session, FillModel(
        order_id=exit_order.id, sequence_number=1, quantity=Decimal("10"),
        execution_price=Decimal("1.11"),
        executed_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC), fee=Decimal("0"),
    ))
    trade = session.scalar(
        select(TradeModel).where(TradeModel.experiment_id == experiment.id)
    )
    assert trade is not None and trade.exit_reason == "END_OF_EXPERIMENT"
