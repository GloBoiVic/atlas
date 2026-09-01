"""PostgreSQL receipts for the bounded PAPER reconciliation repair seams."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    BrokerPositionSide,
    BrokerProtectionFact,
    BrokerTradeFact,
    BrokerTransactionFact,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import (
    Instrument,
    Provider,
    VenueInstrument,
)
from backend.domain.strategy import Direction
from backend.execution.contract import Fill
from backend.integrations.oanda.execution import (
    FillIdentityConflictError,
    OandaExecutionResult,
    OandaOrderStatus,
)
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.models import (
    AccountTransactionCursorModel,
    DeploymentModel,
    FillModel,
    InstrumentModel,
    OandaTransactionReceiptModel,
    OrderModel,
    PendingEntryHandoffModel,
    PositionModel,
    RiskDecisionModel,
    StrategyModel,
    StrategyVersionModel,
    SystemEventModel,
    TradeIntentModel,
    TradeModel,
    TradingAccountModel,
    TradingAccountSnapshotModel,
    VenueInstrumentModel,
)
from backend.runtime.coordinator import BrokerRead, RuntimeDeployment
from backend.runtime.store import SqlAlchemyRuntimeStore

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)


@pytest.fixture()
def database() -> Generator[tuple[Session, SqlAlchemyRuntimeStore]]:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("integration tests require a database name ending in _test")
    engine = configure_utc_session_timezone(create_engine(value))
    session_factory = sessionmaker(engine, class_=Session)
    with Session(engine) as session:
        yield session, SqlAlchemyRuntimeStore(engine, session_factory)
    engine.dispose()


def _seed(
    session: Session,
    *,
    existing_fill_on_other_order: bool = False,
    include_execution: bool = True,
    include_cursor: bool = True,
) -> tuple[DeploymentModel, OrderModel | None]:
    strategy = StrategyModel(
        strategy_key=f"test-{uuid4()}", name="test", description="test"
    )
    session.add(strategy)
    session.flush()
    version = StrategyVersionModel(
        strategy_id=strategy.id,
        version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="test",
        parameter_schema=[],
        context_timeframes=[],
        capabilities=[],
        source_manifest=[],
        exact_source_snapshot={},
        primary_timeframe="M15",
        required_historical_context_bars=100,
        state_schema_version=2,
    )
    instrument = InstrumentModel(
        code="EUR/USD", base_currency="EUR", quote_currency="USD"
    )
    session.add_all([version, instrument])
    session.flush()
    venue = VenueInstrumentModel(
        instrument_id=instrument.id, provider="OANDA", provider_symbol="EUR_USD"
    )
    account = TradingAccountModel(
        label="Practice",
        external_account_id="101-1",
        capabilities={"MARKET": True, "STOP_LOSS": True, "TAKE_PROFIT": True},
        mt4_association_status="NOT_ASSOCIATED",
    )
    session.add_all([venue, account])
    session.flush()
    deployment = DeploymentModel(
        trading_account_id=account.id,
        strategy_version_id=version.id,
        venue_instrument_id=venue.id,
        parameter_snapshot={"ema_period": 100},
        risk_snapshot={"risk_per_trade": "0.01"},
        desired_state="RUNNING",
        actual_state="RECONCILIATION_REQUIRED",
    )
    session.add(deployment)
    session.flush()
    position = PositionModel(
        deployment_id=deployment.id, venue_instrument_id=venue.id
    )
    session.add(position)
    session.flush()
    if not include_execution:
        if include_cursor:
            session.add(
                AccountTransactionCursorModel(
                    trading_account_id=account.id,
                    last_transaction_id="9",
                    observed_at=NOW,
                    source="test",
                )
            )
        session.commit()
        return deployment, None
    intent = TradeIntentModel(
        deployment_id=deployment.id,
        strategy_version_id=version.id,
        venue_instrument_id=venue.id,
        decision_frontier=NOW,
        action="OPEN_LONG",
        direction="LONG",
        proposed_stop=Decimal("1.09"),
        target_multiple=Decimal("1.7"),
        target_methodology="R_MULTIPLE",
        rationale={},
    )
    session.add(intent)
    session.flush()
    risk = RiskDecisionModel(
        trade_intent_id=intent.id,
        phase="PRE_SUBMISSION",
        outcome="APPROVED",
        quantity=Decimal("10"),
        entry_price=Decimal("1.1"),
        stop_price=Decimal("1.09"),
        target_price=None,
        target_methodology="R_MULTIPLE",
        target_multiple=Decimal("1.7"),
        price_bound=Decimal("1.1002"),
        risk_budget=Decimal("100"),
        evaluated_at=NOW,
    )
    session.add(risk)
    session.flush()
    order = OrderModel(
        deployment_id=deployment.id,
        trade_intent_id=intent.id,
        risk_decision_id=risk.id,
        order_type="MARKET",
        purpose="ENTRY",
        direction="LONG",
        quantity=Decimal("10"),
        client_correlation_id=f"atlas-{uuid4()}",
        current_status="PENDING_SUBMISSION",
        time_in_force="FOK",
        price_bound=Decimal("1.1002"),
        external_order_id="order-1",
    )
    session.add(order)
    session.flush()
    if existing_fill_on_other_order:
        other_intent = TradeIntentModel(
            deployment_id=deployment.id,
            strategy_version_id=version.id,
            venue_instrument_id=venue.id,
            decision_frontier=NOW + timedelta(minutes=15),
            action="OPEN_LONG",
            direction="LONG",
            proposed_stop=Decimal("1.09"),
            target_multiple=Decimal("1.7"),
            target_methodology="R_MULTIPLE",
            rationale={},
        )
        session.add(other_intent)
        session.flush()
        other_risk = RiskDecisionModel(
            trade_intent_id=other_intent.id,
            phase="PRE_SUBMISSION",
            outcome="APPROVED",
            quantity=Decimal("10"),
            entry_price=Decimal("1.1"),
            stop_price=Decimal("1.09"),
            target_price=None,
            target_methodology="R_MULTIPLE",
            target_multiple=Decimal("1.7"),
            risk_budget=Decimal("100"),
            price_bound=Decimal("1.1002"),
            evaluated_at=NOW,
        )
        session.add(other_risk)
        session.flush()
        other = OrderModel(
            deployment_id=deployment.id,
            trade_intent_id=other_intent.id,
            risk_decision_id=other_risk.id,
            order_type="MARKET",
            purpose="ENTRY",
            direction="LONG",
            quantity=Decimal("10"),
            client_correlation_id=f"atlas-{uuid4()}",
            current_status="FILLED",
            time_in_force="FOK",
            price_bound=Decimal("1.1002"),
            external_order_id="order-other",
        )
        session.add(other)
        session.flush()
        session.add(
            FillModel(
                order_id=other.id,
                sequence_number=1,
                quantity=Decimal("10"),
                execution_price=Decimal("1.1"),
                executed_at=NOW,
                external_execution_id="10",
                external_transaction_id="10",
                external_trade_id="trade-other",
                related_transaction_ids=["10"],
                fee=Decimal("0"),
                price_basis="OPEN",
            )
        )
    if include_cursor:
        session.add(
            AccountTransactionCursorModel(
                trading_account_id=account.id,
                last_transaction_id="9",
                observed_at=NOW,
                source="test",
            )
        )
    session.commit()
    return deployment, order


def _broker(
    *,
    open_trade: bool = True,
    protection_verified: bool = True,
    target_price: Decimal = Decimal("1.117"),
) -> BrokerRead:
    identity = AccountIdentity("101-1")
    trades = (
        BrokerTradeFact("trade-1", Instrument.EUR_USD, Decimal("10"), Decimal("10")),
    ) if open_trade else ()
    sides = (
        BrokerPositionSide(Direction.LONG, Decimal("10"), trade_ids=("trade-1",)),
    ) if open_trade else ()
    account = AccountSnapshot(
        identity,
        Decimal("10000"),
        Decimal("10000"),
        Decimal("0"),
        Decimal("10000"),
        Decimal("9000"),
        Decimal("1000"),
        NOW,
        "test",
        pending_orders=(),
        open_trades=trades,
        position_sides=sides,
        last_transaction_id="10",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    instrument = VenueInstrumentFacts(
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        -4,
        5,
        0,
        Decimal("1"),
        Decimal("1000000"),
        Decimal("1000000"),
        Decimal("0.02"),
        frozenset({"LONG", "SHORT", "MARKET", "STOP_LOSS", "TAKE_PROFIT"}),
    )
    quote = ExecutableQuote(
        Instrument.EUR_USD, Decimal("1.1"), Decimal("1.1002"), NOW, "test", True
    )
    transaction = BrokerTransactionFact(
        "10",
        "ORDER_FILL",
        "order-1",
        "trade-1",
        Decimal("10"),
        Decimal("1.1"),
        NOW,
        "EUR/USD",
    )
    protection = (
        BrokerProtectionFact(
            "trade-1",
            "stop-1",
            "target-1",
            Decimal("1.09"),
            target_price,
            Decimal("10"),
            Decimal("10"),
            NOW,
        ),
    ) if protection_verified else ()
    return BrokerRead(
        account,
        instrument,
        quote,
        protection_verified=protection_verified,
        protection_facts=protection,
        transactions=(transaction,),
        transactions_known=True,
        transaction_fence="10",
    )


def test_fill_identity_collision_rolls_back_and_blocks_deployment(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session, existing_fill_on_other_order=True)
    assert order is not None
    result = OandaExecutionResult(
        OandaOrderStatus.FULL_FILLED,
        order.id,
        external_order_id="order-1",
        external_trade_ids=("trade-1",),
        related_transaction_ids=("10",),
        fill=Fill(
            order.id,
            1,
            Decimal("10"),
            Decimal("1.1"),
            NOW,
            external_execution_id="10",
            external_transaction_id="10",
            external_trade_id="trade-1",
            related_transaction_ids=("10",),
        ),
    )

    with pytest.raises(FillIdentityConflictError):
        store.apply_execution_result(deployment.id, result)

    with Session(store.engine) as check:
        current = check.get(OrderModel, order.id)
        deployment_row = check.get(DeploymentModel, deployment.id)
        assert current is not None and current.current_status == "PENDING_SUBMISSION"
        intent = check.get(TradeIntentModel, current.trade_intent_id)
        assert intent is not None and intent.proposal_status == "PENDING"
        assert deployment_row is not None
        assert deployment_row.actual_state == "RECONCILIATION_REQUIRED"
        assert check.scalar(
            select(FillModel).where(FillModel.order_id == order.id)
        ) is None
        event = check.scalar(
            select(SystemEventModel).where(
                SystemEventModel.deployment_id == deployment.id,
                SystemEventModel.code == "FILL_IDENTITY_CONFLICT",
            )
        )
        assert event is not None and event.severity == "CRITICAL"


def test_submission_fill_does_not_advance_account_changes_cursor(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session)
    assert order is not None
    result = OandaExecutionResult(
        OandaOrderStatus.FULL_FILLED,
        order.id,
        external_order_id="order-1",
        external_trade_ids=("trade-1",),
        related_transaction_ids=("10",),
        last_transaction_id="10",
        fill=Fill(
            order.id,
            1,
            Decimal("10"),
            Decimal("1.1"),
            NOW,
            external_execution_id="10",
            external_transaction_id="10",
            external_trade_id="trade-1",
            related_transaction_ids=("10",),
        ),
    )

    store.apply_execution_result(deployment.id, result)

    with Session(store.engine) as check:
        assert check.scalar(
            select(AccountTransactionCursorModel.last_transaction_id)
        ) == "9"
        assert check.scalar(select(FillModel).where(FillModel.order_id == order.id))


def test_fill_is_preserved_when_protection_confirmation_fails(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session)
    assert order is not None
    result = OandaExecutionResult(
        OandaOrderStatus.FULL_FILLED,
        order.id,
        external_order_id="order-1",
        external_trade_ids=("trade-1",),
        related_transaction_ids=("10",),
        fill=Fill(
            order.id,
            1,
            Decimal("10"),
            Decimal("1.1"),
            NOW,
            external_execution_id="10",
            external_transaction_id="10",
            external_trade_id="trade-1",
            related_transaction_ids=("10",),
        ),
    )
    store.apply_execution_result(deployment.id, result)
    store.record_protection_failure(deployment.id, "MISSING_TARGET")

    with Session(store.engine) as check:
        assert check.scalar(select(FillModel).where(FillModel.order_id == order.id))
        position = check.scalar(
            select(PositionModel).where(PositionModel.deployment_id == deployment.id)
        )
        current = check.get(DeploymentModel, deployment.id)
        assert position is not None and position.state == "LONG"
        assert current is not None
        assert current.actual_state == "RECONCILIATION_REQUIRED"


@pytest.mark.parametrize(
    ("open_trade", "protection_verified", "target_price"),
    [
        (False, True, Decimal("1.117")),
        (True, False, Decimal("1.117")),
        (True, True, Decimal("1.118")),
    ],
)
def test_missed_entry_repair_requires_current_protected_exposure(
    database: tuple[Session, SqlAlchemyRuntimeStore],
    open_trade: bool,
    protection_verified: bool,
    target_price: Decimal,
) -> None:
    session, store = database
    deployment, order = _seed(session)
    assert order is not None
    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(
            open_trade=open_trade,
            protection_verified=protection_verified,
            target_price=target_price,
        ),
    )

    assert result is not None
    assert result.outcome.value == "RECONCILIATION_REQUIRED"
    with Session(store.engine) as check:
        assert check.scalar(
            select(AccountTransactionCursorModel.last_transaction_id)
        ) == "9"
        assert check.scalar(
            select(FillModel).where(FillModel.order_id == order.id)
        ) is None
        current = check.get(OrderModel, order.id)
        assert current is not None and current.current_status == "PENDING_SUBMISSION"


def test_missed_entry_repair_is_one_durable_fill_and_cursor_follows_application(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session)
    assert order is not None
    runtime_deployment = RuntimeDeployment(
        deployment.id, "101-1", "RUNNING", "STARTING"
    )
    broker = _broker()

    repaired = store.repair_reconciliation(runtime_deployment, broker)
    assert (
        repaired is not None
        and repaired.outcome.value == "REPAIRED"
        and repaired.durable_gate_proven
    )
    with Session(store.engine) as check:
        assert check.scalar(
            select(AccountTransactionCursorModel.last_transaction_id)
        ) == "10"
        assert len(
            check.scalars(select(FillModel).where(FillModel.order_id == order.id)).all()
        ) == 1
        receipt = check.scalar(select(OandaTransactionReceiptModel))
        assert receipt is not None
        assert receipt.disposition == "APPLIED"
        current = check.get(OrderModel, order.id)
        assert current is not None and current.current_status == "FILLED"
        position = check.scalar(
            select(PositionModel).where(PositionModel.deployment_id == deployment.id)
        )
        trade = check.scalar(
            select(TradeModel).where(TradeModel.deployment_id == deployment.id)
        )
        assert (
            position is not None
            and position.state == "LONG"
            and position.quantity == Decimal("10")
        )
        assert (
            trade is not None
            and trade.status == "OPEN"
            and trade.quantity == Decimal("10")
        )

    replay = store.repair_reconciliation(runtime_deployment, broker)
    assert replay is not None and replay.outcome.value == "REPAIRED"
    with Session(store.engine) as check:
        assert len(
            check.scalars(select(FillModel).where(FillModel.order_id == order.id)).all()
        ) == 1
        assert len(check.scalars(select(OandaTransactionReceiptModel)).all()) == 1


def test_account_changes_conflicting_receipt_replay_rolls_back_and_blocks(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, _ = _seed(session)
    runtime_deployment = RuntimeDeployment(
        deployment.id, "101-1", "RUNNING", "STARTING"
    )
    assert store.repair_reconciliation(runtime_deployment, _broker()) is not None
    broker = _broker(target_price=Decimal("1.11727"))
    changed = BrokerTransactionFact(
        "10", "ORDER_FILL", "order-1", "trade-1", Decimal("10"),
        Decimal("1.1001"), NOW, "EUR/USD",
    )
    broker = BrokerRead(
        broker.account,
        broker.instrument,
        broker.quote,
        protection_verified=True,
        protection_facts=broker.protection_facts,
        transactions=(changed,),
        transactions_known=True,
        transaction_fence="10",
    )

    result = store.repair_reconciliation(runtime_deployment, broker)

    assert result is not None
    assert result.reason == "TRANSACTION_RECEIPT_CONFLICT"
    with Session(store.engine) as check:
        cursor = check.scalar(
            select(AccountTransactionCursorModel.last_transaction_id)
        )
        assert cursor == "10"
        current = check.get(DeploymentModel, deployment.id)
        assert current is not None and current.actual_state == "RECONCILIATION_REQUIRED"
        receipt = check.scalar(select(OandaTransactionReceiptModel))
        assert receipt is not None
        assert len(receipt.normalized_digest) == 64


def test_flat_deployment_initializes_cursor_without_importing_history(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, _ = _seed(
        session, include_execution=False, include_cursor=False
    )
    broker = _broker(open_trade=False)
    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"), broker
    )

    assert result is not None
    assert result.durable_gate_proven is True
    assert result.summary["repair"] == "INITIAL_CURSOR_BASELINE"
    with Session(store.engine) as check:
        cursor = check.scalar(
            select(AccountTransactionCursorModel.last_transaction_id)
        )
        assert cursor == "10"
        cursor_row = check.scalar(select(AccountTransactionCursorModel))
        assert cursor_row is not None
        assert cursor_row.source == "OANDA_ACCOUNT_DETAILS_BASELINE"
        assert check.scalar(select(OandaTransactionReceiptModel)) is None
        snapshot = check.scalar(select(TradingAccountSnapshotModel))
        assert snapshot is not None
        assert snapshot.facts["transaction_fence"] == "10"
        assert not check.scalars(
            select(TradeModel).where(TradeModel.deployment_id == deployment.id)
        ).all()


def test_cursorless_baseline_rejects_existing_local_execution_fact(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session, include_cursor=False)
    assert order is not None

    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(open_trade=False),
    )

    assert result is not None
    assert result.outcome.value == "RECONCILIATION_REQUIRED"
    assert result.reason == "INITIAL_CURSOR_BASELINE_UNSAFE"
    with Session(store.engine) as check:
        assert check.scalar(select(AccountTransactionCursorModel)) is None
        current = check.get(DeploymentModel, deployment.id)
        assert current is not None
        assert current.actual_state == "RECONCILIATION_REQUIRED"


def test_cursorless_baseline_rejects_open_local_position(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, _ = _seed(session, include_execution=False, include_cursor=False)
    with Session(store.engine) as update, update.begin():
        position = update.scalar(
            select(PositionModel).where(PositionModel.deployment_id == deployment.id)
        )
        assert position is not None
        position.state = "LONG"
        position.quantity = Decimal("10")
        position.entry_price = Decimal("1.1")
        position.opened_at = NOW

    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(open_trade=False),
    )

    assert result is not None
    assert result.reason == "INITIAL_CURSOR_BASELINE_UNSAFE"
    with Session(store.engine) as check:
        assert check.scalar(select(AccountTransactionCursorModel)) is None
        current = check.get(DeploymentModel, deployment.id)
        assert current is not None
        assert current.actual_state == "RECONCILIATION_REQUIRED"


def test_cursorless_baseline_rejects_open_local_trade(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session, include_cursor=False)
    assert order is not None
    with Session(store.engine) as update, update.begin():
        local_order = update.get(OrderModel, order.id)
        assert local_order is not None
        local_order.current_status = "REJECTED"
        update.add(
            TradeModel(
                deployment_id=deployment.id,
                trade_intent_id=local_order.trade_intent_id,
                entry_order_id=local_order.id,
                direction="LONG",
                status="OPEN",
                quantity=Decimal("10"),
                entry_price=Decimal("1.1"),
                opened_at=NOW,
            )
        )

    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(open_trade=False),
    )

    assert result is not None
    assert result.reason == "INITIAL_CURSOR_BASELINE_UNSAFE"
    with Session(store.engine) as check:
        assert check.scalar(select(AccountTransactionCursorModel)) is None


@pytest.mark.parametrize("status", ["PENDING_SUBMISSION", "UNKNOWN"])
def test_cursorless_baseline_rejects_unresolved_entry_order(
    database: tuple[Session, SqlAlchemyRuntimeStore], status: str
) -> None:
    session, store = database
    deployment, order = _seed(session, include_cursor=False)
    assert order is not None
    with Session(store.engine) as update, update.begin():
        local_order = update.get(OrderModel, order.id)
        assert local_order is not None
        local_order.current_status = status

    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(open_trade=False),
    )

    assert result is not None
    assert result.reason == "INITIAL_CURSOR_BASELINE_UNSAFE"
    with Session(store.engine) as check:
        assert check.scalar(select(AccountTransactionCursorModel)) is None


def test_cursorless_baseline_rejects_unresolved_broker_fill(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session, include_cursor=False)
    assert order is not None
    with Session(store.engine) as update, update.begin():
        local_order = update.get(OrderModel, order.id)
        assert local_order is not None
        local_order.current_status = "REJECTED"
        update.add(
            FillModel(
                order_id=local_order.id,
                sequence_number=1,
                quantity=Decimal("10"),
                execution_price=Decimal("1.1"),
                executed_at=NOW,
                external_execution_id="fill-1",
                external_transaction_id="11",
                external_trade_id="trade-1",
                related_transaction_ids=["11"],
                fee=Decimal("0"),
                price_basis="OPEN",
            )
        )

    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(open_trade=False),
    )

    assert result is not None
    assert result.reason == "INITIAL_CURSOR_BASELINE_UNSAFE"
    with Session(store.engine) as check:
        assert check.scalar(select(AccountTransactionCursorModel)) is None


def test_cursorless_baseline_rejects_pending_opening_handoff_and_intent(
    database: tuple[Session, SqlAlchemyRuntimeStore],
) -> None:
    session, store = database
    deployment, order = _seed(session, include_cursor=False)
    assert order is not None
    with Session(store.engine) as update, update.begin():
        local_order = update.get(OrderModel, order.id)
        assert local_order is not None
        local_order.current_status = "REJECTED"
        update.add(
            PendingEntryHandoffModel(
                deployment_id=deployment.id,
                trade_intent_id=local_order.trade_intent_id,
            )
        )

    result = store.repair_reconciliation(
        RuntimeDeployment(deployment.id, "101-1", "RUNNING", "STARTING"),
        _broker(open_trade=False),
    )

    assert result is not None
    assert result.reason == "INITIAL_CURSOR_BASELINE_UNSAFE"
    with Session(store.engine) as check:
        assert check.scalar(select(AccountTransactionCursorModel)) is None
