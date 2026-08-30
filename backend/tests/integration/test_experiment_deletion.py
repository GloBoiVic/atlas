# ruff: noqa: F401, F811
# pyright: reportPrivateUsage=false, reportUnusedImport=false
"""PostgreSQL proof for the explicit Experiment deletion boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.persistence.experiment_deletion import (
    ExperimentDeletionOwnershipConflict,
    ExperimentDeletionRepository,
    ExperimentDeletionRunning,
)
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentDeletionReceiptModel,
    ExperimentEquityPointModel,
    ExperimentGapDecisionModel,
    ExperimentModel,
    ExperimentProposalDiagnosticModel,
    ExperimentResultModel,
    FillModel,
    HistoricalAcquisitionWindowModel,
    MarketBarModel,
    OrderEventModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    TradeIntentModel,
    TradeModel,
)
from backend.tests.integration.test_golden_flows import (  # pyright: ignore[reportPrivateUsage]
    _registry,
    _seed,
    database_url,
)

pytestmark = pytest.mark.integration


def _engine(database_url: str):
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    return configure_utc_session_timezone(create_engine(database_url))


def _seed_one(session: Session) -> tuple[UUID, UUID, UUID]:
    experiment_id, snapshot_id, version_id = _seed(session, "LONG")
    # The compatibility insert trigger keeps newer runner fixtures RUNNING;
    # deletion tests need an explicitly persisted deletable lifecycle state.
    session.execute(
        update(ExperimentModel)
        .where(ExperimentModel.id == experiment_id)
        .values(status="PENDING")
    )
    session.flush()
    return experiment_id, snapshot_id, version_id


def _intent(
    experiment: ExperimentModel, version_id: UUID, *, frontier: datetime
) -> TradeIntentModel:
    return TradeIntentModel(
        id=uuid4(),
        experiment_id=experiment.id,
        strategy_version_id=version_id,
        venue_instrument_id=experiment.venue_instrument_id,
        decision_frontier=frontier,
        action="OPEN_LONG",
        direction="LONG",
        proposed_stop=Decimal("1.09"),
        target_multiple=Decimal("2"),
        rationale={},
    )


def _risk(intent_id: UUID) -> RiskDecisionModel:
    return RiskDecisionModel(
        id=uuid4(),
        trade_intent_id=intent_id,
        phase="PRE_FLIGHT",
        outcome="APPROVED",
        evaluated_at=datetime(2026, 1, 5, 1, tzinfo=UTC),
    )


def _entry_order(
    experiment_id: UUID, intent_id: UUID, risk_id: UUID, correlation: str
) -> OrderModel:
    return OrderModel(
        id=uuid4(),
        experiment_id=experiment_id,
        trade_intent_id=intent_id,
        risk_decision_id=risk_id,
        order_type="MARKET",
        purpose="ENTRY",
        direction="LONG",
        quantity=Decimal("1"),
        current_status="PENDING_SUBMISSION",
        client_correlation_id=correlation,
    )


def _populate_graph(session: Session, status: str = "PENDING") -> dict[str, Any]:
    """Create one genuinely populated graph before an allowed terminal state."""
    experiment_id, snapshot_id, version_id = _seed_one(session)
    experiment = session.get(ExperimentModel, experiment_id)
    assert experiment is not None
    frontier = datetime(2026, 1, 5, 2, tzinfo=UTC)
    acquisition_start = frontier + timedelta(minutes=experiment_id.int % 10000)
    acquisition_end = acquisition_start + timedelta(minutes=1)
    source_bar_id = session.scalar(select(MarketBarModel.id))
    assert source_bar_id is not None
    if session.get(
        DatasetSnapshotBarModel, (snapshot_id, source_bar_id)
    ) is None:
        session.add(
            DatasetSnapshotBarModel(
                dataset_snapshot_id=snapshot_id, market_bar_id=source_bar_id
            )
        )
        session.flush()

    intent = _intent(experiment, version_id, frontier=frontier)
    session.add(intent)
    session.flush()
    diagnostic = ExperimentProposalDiagnosticModel(
        experiment_id=experiment_id,
        sequence=1,
        trade_intent_id=intent.id,
        event_type="FILLED",
        occurred_at=frontier,
        details={"source": "deletion-proof"},
    )
    risk = _risk(intent.id)
    session.add_all((diagnostic, risk))
    session.flush()

    entry = _entry_order(experiment_id, intent.id, risk.id, f"entry-{uuid4()}")
    session.add(entry)
    session.flush()
    protection = OrderModel(
        id=uuid4(),
        experiment_id=experiment_id,
        trade_intent_id=intent.id,
        risk_decision_id=risk.id,
        order_type="STOP",
        purpose="STOP_LOSS",
        direction="LONG",
        quantity=Decimal("1"),
        requested_price=Decimal("1.09"),
        current_status="SUBMITTED",
        client_correlation_id=f"stop-{uuid4()}",
        parent_entry_order_id=entry.id,
    )
    target = OrderModel(
        id=uuid4(),
        experiment_id=experiment_id,
        trade_intent_id=intent.id,
        risk_decision_id=risk.id,
        order_type="LIMIT",
        purpose="TAKE_PROFIT",
        direction="LONG",
        quantity=Decimal("1"),
        requested_price=Decimal("1.12"),
        current_status="SUBMITTED",
        client_correlation_id=f"target-{uuid4()}",
        parent_entry_order_id=entry.id,
    )
    exit_order = OrderModel(
        id=uuid4(),
        experiment_id=experiment_id,
        trade_intent_id=intent.id,
        risk_decision_id=risk.id,
        order_type="MARKET",
        purpose="EXIT",
        direction="SHORT",
        quantity=Decimal("1"),
        current_status="FILLED",
        client_correlation_id=f"exit-{uuid4()}",
    )
    session.add_all((protection, target, exit_order))
    session.flush()
    orders = (entry, protection, target, exit_order)

    session.add_all(
        OrderEventModel(
            id=uuid4(),
            order_id=order.id,
            sequence_number=1,
            event_type="ORDER_CREATED",
            occurred_at=frontier + timedelta(minutes=index),
            source_market_bar_id=source_bar_id if index == 0 else None,
            details={"proof": True},
        )
        for index, order in enumerate(orders)
    )
    session.add_all(
        FillModel(
            id=uuid4(),
            order_id=order.id,
            sequence_number=1,
            quantity=Decimal("1"),
            execution_price=Decimal("1.10") + Decimal(index) / Decimal("100"),
            executed_at=frontier + timedelta(minutes=10 + index),
            external_execution_id=f"fill-{uuid4()}",
            source_market_bar_id=source_bar_id if index == 0 else None,
            price_basis="OPEN",
        )
        for index, order in enumerate(orders)
    )
    trade = TradeModel(
        id=uuid4(),
        experiment_id=experiment_id,
        trade_intent_id=intent.id,
        entry_order_id=entry.id,
        exit_order_id=exit_order.id,
        direction="LONG",
        status="COMPLETED",
        quantity=Decimal("1"),
        entry_price=Decimal("1.10"),
        exit_price=Decimal("1.12"),
        opened_at=frontier,
        closed_at=frontier + timedelta(minutes=30),
        gross_pnl=Decimal("0.02"),
        exit_reason="TAKE_PROFIT",
        ambiguity_source_market_bar_id=source_bar_id,
    )
    account = session.get(ExperimentAccountModel, experiment_id)
    position = session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment_id)
    )
    assert account is not None and position is not None
    position.state = "LONG"
    position.quantity = Decimal("1")
    position.entry_price = Decimal("1.10")
    position.opened_at = frontier
    account.realized_pnl = Decimal("0.02")
    account.equity = Decimal("10000.02")
    equity = ExperimentEquityPointModel(
        experiment_id=experiment_id,
        sequence_number=1,
        observed_at=frontier,
        balance=Decimal("10000.02"),
        realized_pnl=Decimal("0.02"),
        unrealized_pnl=Decimal("0"),
        equity=Decimal("10000.02"),
        running_peak=Decimal("10000.02"),
        drawdown_amount=Decimal("0"),
        drawdown_percent=Decimal("0"),
        valuation_bid=Decimal("1.12"),
        valuation_ask=Decimal("1.13"),
        source_bid_market_bar_id=source_bar_id,
        source_ask_market_bar_id=source_bar_id,
    )
    session.add_all((trade, equity))
    ExperimentRepository().create_result(
        session,
        experiment_id=experiment_id,
        result_schema_version="TEST_RESULT_V1",
        trade_count=1,
        ambiguous_trade_count=0,
        gross_pnl=Decimal("0.02"),
        commission_cost=Decimal("0"),
        financing_cost=Decimal("0"),
        modeled_net_pnl=Decimal("0.02"),
        ending_balance=Decimal("10000.02"),
        ending_equity=Decimal("10000.02"),
        net_return=Decimal("0.000002"),
        max_drawdown_amount=Decimal("0"),
        max_drawdown_percent=Decimal("0"),
        financing_disclosure="EXCLUDED",
        completed_market_time=frontier + timedelta(minutes=30),
        output_fingerprint="a" * 64,
    )
    ExperimentRepository().create_gap_decision(
        session,
        experiment_id=experiment_id,
        sequence=1,
        start_time=frontier,
        end_time=frontier + timedelta(minutes=1),
        resolution="M1",
        price_component="MID",
        classification="NON_BLOCKING",
        rule_version="TEST_GAP_RULE",
        policy_version="ATLAS_HISTORICAL_GAP_POLICY_V1",
        affected_state="FLAT",
        affected_event="NONE",
        blocked=False,
        details={"proof": True},
    )
    acquisition = HistoricalAcquisitionWindowModel(
        venue_instrument_id=experiment.venue_instrument_id,
        resolution="M1",
        components="MID",
        start_time=acquisition_start,
        end_time=acquisition_end,
        outcome="SUCCESS_EMPTY_OR_SPARSE",
        request_identity=f"deletion-proof-{uuid4().hex[:16]}",
        returned_count=1,
    )
    session.add(acquisition)
    session.flush()
    if status == "FAILED":
        ExperimentRepository().mark_failed(
            session,
            experiment_id,
            category="STRATEGY",
            code="TEST_FAILURE",
            detail="Populated deletion proof",
            completed_at=frontier + timedelta(minutes=31),
        )
    elif status == "COMPLETED":
        ExperimentRepository().mark_completed(
            session, experiment_id, frontier + timedelta(minutes=31)
        )
    return {
        "experiment_id": experiment_id,
        "snapshot_id": snapshot_id,
        "version_id": version_id,
        "source_bar_id": source_bar_id,
        "acquisition_key": (
            experiment.venue_instrument_id,
            "M1",
            "MID",
            acquisition_start,
            acquisition_end,
        ),
        "intent_id": intent.id,
        "risk_id": risk.id,
        "order_ids": tuple(order.id for order in orders),
        "event_ids": tuple(
            event.id
            for event in session.scalars(
                select(OrderEventModel).where(
                    OrderEventModel.order_id.in_([order.id for order in orders])
                )
            ).all()
        ),
        "fill_ids": tuple(
            fill.id
            for fill in session.scalars(
                select(FillModel).where(
                    FillModel.order_id.in_([order.id for order in orders])
                )
            ).all()
        ),
        "trade_id": trade.id,
    }


def _assert_graph_present(session: Session, graph: dict[str, Any]) -> None:
    experiment_id = graph["experiment_id"]
    snapshot_id = graph["snapshot_id"]
    assert session.get(ExperimentModel, experiment_id) is not None
    assert session.get(DatasetSnapshotModel, snapshot_id) is not None
    for model in (
        DatasetSnapshotBarModel,
        DatasetSnapshotAnalyticalBarModel,
        DatasetSnapshotExecutionObservationModel,
    ):
        assert session.scalars(
            select(model).where(model.dataset_snapshot_id == snapshot_id)
        ).all()
    assert session.get(TradeIntentModel, graph["intent_id"]) is not None
    assert session.get(RiskDecisionModel, graph["risk_id"]) is not None
    assert session.get(TradeModel, graph["trade_id"]) is not None
    assert session.scalars(
        select(OrderModel).where(OrderModel.id.in_(graph["order_ids"]))
    ).all()
    assert session.scalars(
        select(OrderEventModel).where(OrderEventModel.id.in_(graph["event_ids"]))
    ).all()
    assert session.scalars(
        select(FillModel).where(FillModel.id.in_(graph["fill_ids"]))
    ).all()
    assert session.get(ExperimentEquityPointModel, (experiment_id, 1)) is not None
    assert session.get(ExperimentResultModel, experiment_id) is not None
    assert session.get(ExperimentGapDecisionModel, (experiment_id, 1)) is not None
    assert session.get(ExperimentAccountModel, experiment_id) is not None
    assert session.scalar(
        select(PositionModel).where(PositionModel.experiment_id == experiment_id)
    ) is not None
    assert session.scalar(
        select(ExperimentDeletionReceiptModel.receipt_id).where(
            ExperimentDeletionReceiptModel.deleted_experiment_id == experiment_id
        )
    ) is None


def _api_client(engine):
    app = create_app(
        engine=engine,
        registry=_registry(),
        peer_address_resolver=lambda _client: "127.0.0.1",
    )
    return TestClient(app, base_url="http://localhost")


def _confirmation(detail: dict[str, object]) -> dict[str, object]:
    return {
        "confirmation": "DELETE",
        "expected": {
            "label": detail["label"],
            "status": detail["status"],
            "strategy": detail["strategy"]["displayName"],
            "instrument": detail["identity"]["instrument"]["code"],
            "provider": detail["identity"]["provider"]["name"],
            "analysis": "native M15 MID",
            "tradingPeriod": {
                "start": detail["tradingStart"],
                "end": detail["tradingEnd"],
            },
        },
    }


def test_pending_delete_removes_owned_snapshot_but_not_canonical_bars(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, _version_id = _seed_one(session)
        bar_id = session.scalar(select(MarketBarModel.id))
        session.commit()

    stages: list[str] = []
    with Session(engine) as session, session.begin():
        result = ExperimentDeletionRepository().delete(
            session, experiment_id, stage_hook=stages.append
        )
        assert result.snapshot_deleted is True
        assert result.snapshot_id == snapshot_id
        assert stages == [
            "experiment_gap_decisions",
            "experiment_equity_points",
            "experiment_results",
            "experiment_proposal_diagnostics",
            "trades",
            "order_events",
            "fills",
            "orders",
            "risk_decisions",
            "trade_intents",
            "positions",
            "experiment_accounts",
            "experiments",
            "receipt",
        ]

    with Session(engine) as session:
        assert session.get(ExperimentModel, experiment_id) is None
        assert session.get(DatasetSnapshotModel, snapshot_id) is None
        assert session.get(MarketBarModel, bar_id) is not None
        receipt = session.scalar(
            select(ExperimentDeletionReceiptModel).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == experiment_id
            )
        )
        assert receipt is not None
        assert receipt.dataset_snapshot_id == snapshot_id
        assert receipt.snapshot_deleted is True
        assert receipt.strategy_source_fingerprint
    engine.dispose()


@pytest.mark.parametrize("status", ["PENDING", "FAILED", "COMPLETED"])
def test_populated_graph_delete_all_allowed_statuses(
    database_url: str, status: str
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        graph = _populate_graph(session, status)
        session.commit()

    stages: list[str] = []
    with Session(engine) as session, session.begin():
        result = ExperimentDeletionRepository().delete(
            session, graph["experiment_id"], stage_hook=stages.append
        )
        assert result.snapshot_deleted is True
        assert result.snapshot_id == graph["snapshot_id"]
        assert stages == [
            "experiment_gap_decisions",
            "experiment_equity_points",
            "experiment_results",
            "experiment_proposal_diagnostics",
            "trades",
            "order_events",
            "fills",
            "orders",
            "risk_decisions",
            "trade_intents",
            "positions",
            "experiment_accounts",
            "experiments",
            "receipt",
        ]

    with Session(engine) as session:
        assert session.get(ExperimentModel, graph["experiment_id"]) is None
        assert session.get(DatasetSnapshotModel, graph["snapshot_id"]) is None
        assert session.get(MarketBarModel, graph["source_bar_id"]) is not None
        assert session.get(
            HistoricalAcquisitionWindowModel, graph["acquisition_key"]
        ) is not None
        for model, identifier in (
            (TradeIntentModel, graph["intent_id"]),
            (RiskDecisionModel, graph["risk_id"]),
            (TradeModel, graph["trade_id"]),
        ):
            assert session.get(model, identifier) is None
        assert not session.scalars(
            select(OrderModel).where(OrderModel.id.in_(graph["order_ids"]))
        ).all()
        assert not session.scalars(
            select(OrderEventModel).where(OrderEventModel.id.in_(graph["event_ids"]))
        ).all()
        assert not session.scalars(
            select(FillModel).where(FillModel.id.in_(graph["fill_ids"]))
        ).all()
        assert session.get(
            ExperimentEquityPointModel, (graph["experiment_id"], 1)
        ) is None
        assert session.get(ExperimentResultModel, graph["experiment_id"]) is None
        assert session.get(
            ExperimentGapDecisionModel, (graph["experiment_id"], 1)
        ) is None
        assert session.get(ExperimentAccountModel, graph["experiment_id"]) is None
        assert session.scalar(
            select(PositionModel).where(
                PositionModel.experiment_id == graph["experiment_id"]
            )
        ) is None
        receipt = session.scalar(
            select(ExperimentDeletionReceiptModel).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id
                == graph["experiment_id"]
            )
        )
        assert receipt is not None
        assert receipt.pre_delete_status == status
        assert receipt.strategy_version_id == graph["version_id"]
        assert receipt.instrument == "EUR/USD"
        assert receipt.provider == "OANDA"
        assert receipt.snapshot_deleted is True
        assert receipt.strategy_source_fingerprint
    engine.dispose()


@pytest.mark.parametrize(
    "partial_shape",
    ["account_only", "intent_only", "diagnostic_only", "order_only", "result_only"],
)
def test_failed_partial_graph_shapes_are_deletable(
    database_url: str, partial_shape: str
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, version_id = _seed_one(session)
        experiment = session.get(ExperimentModel, experiment_id)
        assert experiment is not None
        frontier = datetime(2026, 1, 6, 2, tzinfo=UTC)
        intent = None
        if partial_shape in {"intent_only", "diagnostic_only", "order_only"}:
            intent = _intent(experiment, version_id, frontier=frontier)
            session.add(intent)
            session.flush()
        if partial_shape == "diagnostic_only":
            assert intent is not None
            session.add(
                ExperimentProposalDiagnosticModel(
                    experiment_id=experiment_id,
                    sequence=1,
                    trade_intent_id=intent.id,
                    event_type="REJECTED",
                    occurred_at=frontier,
                    details={},
                )
            )
        elif partial_shape == "order_only":
            assert intent is not None
            risk = _risk(intent.id)
            session.add(risk)
            session.flush()
            session.add(
                _entry_order(experiment_id, intent.id, risk.id, f"partial-{uuid4()}")
            )
        elif partial_shape == "result_only":
            ExperimentRepository().create_result(
                session,
                experiment_id=experiment_id,
                result_schema_version="TEST_RESULT_V1",
                trade_count=0,
                ambiguous_trade_count=0,
                gross_pnl=Decimal("0"),
                commission_cost=Decimal("0"),
                financing_cost=Decimal("0"),
                modeled_net_pnl=Decimal("0"),
                ending_balance=Decimal("10000"),
                ending_equity=Decimal("10000"),
                net_return=Decimal("0"),
                max_drawdown_amount=Decimal("0"),
                max_drawdown_percent=Decimal("0"),
                financing_disclosure="EXCLUDED",
                completed_market_time=frontier,
                output_fingerprint="b" * 64,
            )
        session.flush()
        ExperimentRepository().mark_failed(
            session,
            experiment_id,
            category="STRATEGY",
            code="PARTIAL_TEST_FAILURE",
            detail="Partial graph deletion proof",
            completed_at=frontier + timedelta(minutes=1),
        )
        session.commit()

    with Session(engine) as session, session.begin():
        result = ExperimentDeletionRepository().delete(session, experiment_id)
        assert result.snapshot_deleted is True
    with Session(engine) as session:
        assert session.get(ExperimentModel, experiment_id) is None
        assert session.get(DatasetSnapshotModel, snapshot_id) is None
        assert session.scalar(
            select(ExperimentDeletionReceiptModel.receipt_id).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == experiment_id
            )
        ) is not None
    engine.dispose()


_DELETE_STAGES = (
    "experiment_gap_decisions",
    "experiment_equity_points",
    "experiment_results",
    "experiment_proposal_diagnostics",
    "trades",
    "order_events",
    "fills",
    "orders",
    "risk_decisions",
    "trade_intents",
    "positions",
    "experiment_accounts",
    "experiments",
)


@pytest.mark.parametrize("failed_stage", _DELETE_STAGES)
def test_rollback_after_each_explicit_delete_stage(
    database_url: str, failed_stage: str
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        graph = _populate_graph(session)
        session.commit()

    def fail(stage: str) -> None:
        if stage == failed_stage:
            raise RuntimeError(f"failure at {stage}")

    with pytest.raises(RuntimeError, match=f"failure at {failed_stage}"):
        with Session(engine) as session, session.begin():
            ExperimentDeletionRepository().delete(
                session, graph["experiment_id"], stage_hook=fail
            )

    with Session(engine) as session:
        _assert_graph_present(session, graph)
    engine.dispose()


def test_receipt_insert_failure_rolls_back_populated_graph(database_url: str) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        graph = _populate_graph(session)
        session.commit()

    with pytest.raises(Exception, match="receipt insertion failure"):
        with Session(engine) as session, session.begin():
            session.execute(
                text(
                    """
                    CREATE FUNCTION deletion_receipt_test_failure()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'receipt insertion failure'; END;
                    $$
                    """
                )
            )
            session.execute(
                text(
                    """
                    CREATE TRIGGER aaa_deletion_receipt_test_failure
                    BEFORE INSERT ON experiment_deletion_receipts
                    FOR EACH ROW EXECUTE FUNCTION deletion_receipt_test_failure()
                    """
                )
            )
            ExperimentDeletionRepository().delete(session, graph["experiment_id"])

    with Session(engine) as session:
        _assert_graph_present(session, graph)
    engine.dispose()


@pytest.mark.parametrize("cycle", ["self", "multi_node"])
def test_order_parent_cycles_fail_closed_without_mutation(
    database_url: str, cycle: str
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        graph = _populate_graph(session)
        root_id, child_id = graph["order_ids"][:2]
        session.execute(text("ALTER TABLE orders DISABLE TRIGGER orders_fact_guard"))
        session.execute(text("ALTER TABLE orders DISABLE TRIGGER orders_phase_4_guard"))
        session.execute(
            text(
                "UPDATE orders SET parent_entry_order_id = :parent WHERE id = :id"
            ),
            {"parent": root_id if cycle == "self" else child_id, "id": root_id},
        )
        session.execute(text("ALTER TABLE orders ENABLE TRIGGER orders_phase_4_guard"))
        session.execute(text("ALTER TABLE orders ENABLE TRIGGER orders_fact_guard"))
        session.commit()

    with Session(engine) as session:
        with pytest.raises(
            ExperimentDeletionOwnershipConflict, match="cycle"
        ):
            ExperimentDeletionRepository().delete(session, graph["experiment_id"])
        session.rollback()
        _assert_graph_present(session, graph)
    engine.dispose()


def test_order_parent_external_edge_fails_closed_without_mutation(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        target = _populate_graph(session)
        outside = _populate_graph(session)
        target_root = target["order_ids"][0]
        outside_root = outside["order_ids"][0]
        session.execute(text("ALTER TABLE orders DISABLE TRIGGER orders_fact_guard"))
        session.execute(text("ALTER TABLE orders DISABLE TRIGGER orders_phase_4_guard"))
        session.execute(
            text(
                "UPDATE orders SET parent_entry_order_id = :parent WHERE id = :id"
            ),
            {"parent": outside_root, "id": target_root},
        )
        session.execute(text("ALTER TABLE orders ENABLE TRIGGER orders_phase_4_guard"))
        session.execute(text("ALTER TABLE orders ENABLE TRIGGER orders_fact_guard"))
        session.commit()

    with Session(engine) as session:
        with pytest.raises(ExperimentDeletionOwnershipConflict):
            ExperimentDeletionRepository().delete(session, target["experiment_id"])
        session.rollback()
        _assert_graph_present(session, target)
        _assert_graph_present(session, outside)
    engine.dispose()


def test_inbound_fk_inventory_matches_reviewed_deletion_contract(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    expected = {
        ("experiment_proposal_diagnostics", "trade_intent_id", "trade_intents"),
        ("risk_decisions", "trade_intent_id", "trade_intents"),
        ("orders", "trade_intent_id", "trade_intents"),
        ("trades", "trade_intent_id", "trade_intents"),
        ("orders", "risk_decision_id", "risk_decisions"),
        ("orders", "parent_entry_order_id", "orders"),
        ("order_events", "order_id", "orders"),
        ("fills", "order_id", "orders"),
        ("trades", "entry_order_id", "orders"),
        ("trades", "exit_order_id", "orders"),
    }
    with Session(engine) as session:
        rows = session.execute(
            text(
                """
                SELECT child.relname, child_column.attname, parent.relname
                FROM pg_constraint AS constraint_row
                JOIN pg_class AS child ON child.oid = constraint_row.conrelid
                JOIN pg_class AS parent ON parent.oid = constraint_row.confrelid
                CROSS JOIN LATERAL unnest(constraint_row.conkey)
                    WITH ORDINALITY AS child_key(attnum, ordinal)
                JOIN pg_attribute AS child_column
                  ON child_column.attrelid = child.oid
                 AND child_column.attnum = child_key.attnum
                WHERE constraint_row.contype = 'f'
                  AND parent.relname IN ('trade_intents', 'risk_decisions', 'orders')
                """
            )
        ).all()
    assert {tuple(row) for row in rows} == expected
    engine.dispose()


def test_direct_immutable_dml_remains_fail_closed_without_delete_context(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        graph = _populate_graph(session)
        session.commit()

    with Session(engine) as session:
        statements = (
            (
                "UPDATE trade_intents SET rationale = '{\"changed\": true}'::jsonb "
                "WHERE id = :id",
                graph["intent_id"],
            ),
            (
                "DELETE FROM trade_intents WHERE id = :id",
                graph["intent_id"],
            ),
            ("DELETE FROM risk_decisions WHERE id = :id", graph["risk_id"]),
            ("DELETE FROM fills WHERE id = :id", graph["fill_ids"][0]),
            ("DELETE FROM trades WHERE id = :id", graph["trade_id"]),
            ("DELETE FROM orders WHERE id = :id", graph["order_ids"][0]),
        )
        for statement, identifier in statements:
            with pytest.raises(SQLAlchemyError):
                with session.begin_nested():
                    session.execute(text(statement), {"id": identifier})
        _assert_graph_present(session, graph)
    engine.dispose()


def test_running_delete_is_rejected_without_mutation(database_url: str) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, _version_id = _seed_one(session)
        session.execute(
            update(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .values(status="RUNNING")
        )
        session.commit()

    with Session(engine) as session:
        with pytest.raises(ExperimentDeletionRunning):
            ExperimentDeletionRepository().delete(session, experiment_id)
        session.rollback()

    with Session(engine) as session:
        assert session.get(ExperimentModel, experiment_id) is not None
        assert session.get(DatasetSnapshotModel, snapshot_id) is not None
        assert session.scalar(
            select(ExperimentDeletionReceiptModel.receipt_id).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == experiment_id
            )
        ) is None
    engine.dispose()


def test_failure_after_child_stage_rolls_back_everything(database_url: str) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, _version_id = _seed_one(session)
        session.commit()

    def fail(stage: str) -> None:
        if stage == "orders":
            raise RuntimeError("injected deletion failure")

    with pytest.raises(RuntimeError, match="injected deletion failure"):
        with Session(engine) as session, session.begin():
            ExperimentDeletionRepository().delete(
                session, experiment_id, stage_hook=fail
            )

    with Session(engine) as session:
        assert session.get(ExperimentModel, experiment_id) is not None
        assert session.get(DatasetSnapshotModel, snapshot_id) is not None
        assert session.scalar(
            select(ExperimentDeletionReceiptModel.receipt_id).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == experiment_id
            )
        ) is None
    engine.dispose()


def test_direct_diagnostic_cross_owner_conflict_rolls_back_without_mutation(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    frontier = datetime(2026, 1, 5, 2, tzinfo=UTC)
    with Session(engine) as session:
        target_id, target_snapshot_id, target_version_id = _seed_one(session)
        outside_id, _outside_snapshot_id, outside_version_id = _seed_one(session)
        target = session.get(ExperimentModel, target_id)
        outside = session.get(ExperimentModel, outside_id)
        assert target is not None and outside is not None
        target_intent = _intent(target, target_version_id, frontier=frontier)
        outside_intent = _intent(
            outside, outside_version_id, frontier=frontier + timedelta(minutes=1)
        )
        session.add_all((target_intent, outside_intent))
        session.flush()
        # The direct Experiment edge is malformed: its intent belongs to the
        # other Experiment. It is valid to insert while both Experiments are
        # pending, but deletion must reject it before deleting any row.
        session.add(
            ExperimentProposalDiagnosticModel(
                experiment_id=target_id,
                sequence=1,
                trade_intent_id=outside_intent.id,
                event_type="FILLED",
                occurred_at=frontier,
                details={},
            )
        )
        session.commit()

    with Session(engine) as session:
        with pytest.raises(ExperimentDeletionOwnershipConflict):
            ExperimentDeletionRepository().delete(session, target_id)
        session.rollback()
        assert session.get(ExperimentModel, target_id) is not None
        assert session.get(DatasetSnapshotModel, target_snapshot_id) is not None
        assert session.get(
            ExperimentProposalDiagnosticModel, (target_id, 1)
        ) is not None
        assert session.scalar(
            select(ExperimentDeletionReceiptModel.receipt_id).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == target_id
            )
        ) is None
    engine.dispose()


def test_direct_trade_cross_owner_edges_conflict_without_mutation(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    frontier = datetime(2026, 1, 5, 3, tzinfo=UTC)
    with Session(engine) as session:
        target_id, target_snapshot_id, target_version_id = _seed_one(session)
        outside_id, _outside_snapshot_id, outside_version_id = _seed_one(session)
        target = session.get(ExperimentModel, target_id)
        outside = session.get(ExperimentModel, outside_id)
        assert target is not None and outside is not None
        target_intent = _intent(target, target_version_id, frontier=frontier)
        outside_intent = _intent(
            outside, outside_version_id, frontier=frontier + timedelta(minutes=1)
        )
        session.add_all((target_intent, outside_intent))
        session.flush()
        target_risk = _risk(target_intent.id)
        outside_risk = _risk(outside_intent.id)
        session.add_all((target_risk, outside_risk))
        session.flush()
        target_order = _entry_order(
            target_id, target_intent.id, target_risk.id, "target-entry"
        )
        outside_order = _entry_order(
            outside_id, outside_intent.id, outside_risk.id, "outside-entry"
        )
        session.add_all((target_order, outside_order))
        session.flush()
        # Both direct Trade edges are outside the target sets. The direct
        # Experiment edge makes this row part of the target's malformed graph.
        session.add(
            TradeModel(
                id=uuid4(),
                experiment_id=target_id,
                trade_intent_id=outside_intent.id,
                entry_order_id=outside_order.id,
                direction="LONG",
                status="OPEN",
                quantity=Decimal("1"),
                entry_price=Decimal("1.1"),
                opened_at=frontier,
            )
        )
        session.commit()

    with Session(engine) as session:
        with pytest.raises(ExperimentDeletionOwnershipConflict):
            ExperimentDeletionRepository().delete(session, target_id)
        session.rollback()
        assert session.get(ExperimentModel, target_id) is not None
        assert session.get(DatasetSnapshotModel, target_snapshot_id) is not None
        assert session.scalar(
            select(TradeModel.id).where(TradeModel.experiment_id == target_id)
        ) is not None
        assert session.scalar(
            select(ExperimentDeletionReceiptModel.receipt_id).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == target_id
            )
        ) is None
    engine.dispose()


def test_http_delete_is_confirmed_once_and_repeat_is_not_found(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, _snapshot_id, _version_id = _seed_one(session)
        session.commit()

    with _api_client(engine) as client:
        detail = client.get(f"/api/v1/experiments/{experiment_id}")
        assert detail.status_code == 200, detail.text
        confirmation = _confirmation(detail.json())
        deleted = client.request(
            "DELETE", f"/api/v1/experiments/{experiment_id}", json=confirmation
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] is True
        assert deleted.json()["snapshot"]["deleted"] is True
        repeated = client.request(
            "DELETE", f"/api/v1/experiments/{experiment_id}", json=confirmation
        )
        assert repeated.status_code == 404
        assert repeated.json()["error"]["code"] == "NOT_FOUND"
        assert client.get(f"/api/v1/experiments/{experiment_id}").status_code == 404
    engine.dispose()


def test_http_delete_locks_snapshot_before_experiment_once(database_url: str) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, _snapshot_id, _version_id = _seed_one(session)
        session.commit()

    with _api_client(engine) as client:
        detail = client.get(f"/api/v1/experiments/{experiment_id}")
        assert detail.status_code == 200, detail.text
        statements: list[str] = []

        def record_select(
            _conn, _cursor, statement, _parameters, _context, _executemany
        ):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement.upper())

        event.listen(engine, "before_cursor_execute", record_select)
        try:
            response = client.request(
                "DELETE",
                f"/api/v1/experiments/{experiment_id}",
                json=_confirmation(detail.json()),
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_select)

        assert response.status_code == 200, response.text
        snapshot_locks = [
            index
            for index, statement in enumerate(statements)
            if "FROM DATASET_SNAPSHOTS" in statement and "FOR UPDATE" in statement
        ]
        experiment_selects = [
            (index, statement)
            for index, statement in enumerate(statements)
            if "FROM EXPERIMENTS" in statement and "WHERE EXPERIMENTS.ID =" in statement
        ]
        experiment_locks = [
            index
            for index, statement in experiment_selects
            if "FOR UPDATE" in statement
        ]
        assert len(snapshot_locks) == 1
        assert len(experiment_selects) == 2
        assert len(experiment_locks) == 1
        assert "FOR UPDATE" not in experiment_selects[0][1]
        assert snapshot_locks[0] < experiment_locks[0]
    engine.dispose()


def test_http_delete_locked_running_precedes_stale_confirmation(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, _version_id = _seed_one(session)
        session.commit()
    with _api_client(engine) as client:
        detail = client.get(f"/api/v1/experiments/{experiment_id}").json()
        with Session(engine) as session:
            session.execute(
                update(ExperimentModel)
                .where(ExperimentModel.id == experiment_id)
                .values(status="RUNNING")
            )
            session.commit()
        body = _confirmation(detail)
        response = client.request(
            "DELETE", f"/api/v1/experiments/{experiment_id}", json=body
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "EXPERIMENT_RUNNING"
        with Session(engine) as session:
            assert session.get(ExperimentModel, experiment_id) is not None
            assert session.get(DatasetSnapshotModel, snapshot_id) is not None
    engine.dispose()


def test_http_delete_requires_case_sensitive_confirmation(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, _snapshot_id, _version_id = _seed_one(session)
        session.commit()
    with _api_client(engine) as client:
        detail = client.get(f"/api/v1/experiments/{experiment_id}").json()
        body = _confirmation(detail)
        body["confirmation"] = "delete"
        response = client.request(
            "DELETE", f"/api/v1/experiments/{experiment_id}", json=body
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DELETE_CONFIRMATION_REQUIRED"
        assert client.get(f"/api/v1/experiments/{experiment_id}").status_code == 200
    engine.dispose()


def test_http_delete_stale_deletable_status_requires_fresh_confirmation(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, _snapshot_id, _version_id = _seed_one(session)
        session.commit()
    with _api_client(engine) as client:
        detail = client.get(f"/api/v1/experiments/{experiment_id}").json()
        with Session(engine) as session, session.begin():
            ExperimentRepository().mark_failed(
                session,
                experiment_id,
                category="STRATEGY",
                code="TEST_FAILURE",
                detail="Test failure",
                completed_at=datetime.fromisoformat(
                    str(detail["tradingEnd"]).replace("Z", "+00:00")
                ),
            )
        response = client.request(
            "DELETE",
            f"/api/v1/experiments/{experiment_id}",
            json=_confirmation(detail),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DELETE_CONFIRMATION_MISMATCH"
    engine.dispose()


def test_surviving_completed_reads_are_equivalent_after_another_delete(
    database_url: str,
) -> None:
    """Deleting one completed Experiment cannot change another's read facts."""
    engine = _engine(database_url)
    with Session(engine) as session:
        survivor = _populate_graph(session, "COMPLETED")
        deleted = _populate_graph(session, "COMPLETED")
        comparison_peer = _populate_graph(session, "COMPLETED")
        session.commit()

    with _api_client(engine) as client:
        survivor_id = survivor["experiment_id"]
        comparison_peer_id = comparison_peer["experiment_id"]
        detail_before = client.get(f"/api/v1/experiments/{survivor_id}")
        equity_before = client.get(f"/api/v1/experiments/{survivor_id}/equity")
        trades_before = client.get(f"/api/v1/experiments/{survivor_id}/trades")
        assert detail_before.status_code == 200, detail_before.text
        assert equity_before.status_code == 200, equity_before.text
        assert trades_before.status_code == 200, trades_before.text
        trade_sequence = trades_before.json()["items"][0]["sequence_number"]
        trade_before = client.get(
            f"/api/v1/experiments/{survivor_id}/trades/{trade_sequence}"
        )
        price_before = client.get(
            f"/api/v1/experiments/{survivor_id}/price-analysis"
        )
        comparison_before = client.get(
            "/api/v1/experiments/comparison"
            f"?experimentId={survivor_id}&experimentId={comparison_peer_id}"
        )
        assert trade_before.status_code == 200, trade_before.text
        assert price_before.status_code == 200, price_before.text
        assert comparison_before.status_code == 200, comparison_before.text

        deleted_detail = client.get(f"/api/v1/experiments/{deleted['experiment_id']}")
        assert deleted_detail.status_code == 200, deleted_detail.text
        deletion = client.request(
            "DELETE",
            f"/api/v1/experiments/{deleted['experiment_id']}",
            json=_confirmation(deleted_detail.json()),
        )
        assert deletion.status_code == 200, deletion.text

        assert (
            client.get(f"/api/v1/experiments/{survivor_id}").json()
            == detail_before.json()
        )
        assert (
            client.get(f"/api/v1/experiments/{survivor_id}/equity").json()
            == equity_before.json()
        )
        assert (
            client.get(f"/api/v1/experiments/{survivor_id}/trades").json()
            == trades_before.json()
        )
        assert client.get(
            f"/api/v1/experiments/{survivor_id}/trades/{trade_sequence}"
        ).json() == trade_before.json()
        assert client.get(
            f"/api/v1/experiments/{survivor_id}/price-analysis"
        ).json() == price_before.json()
        assert client.get(
            "/api/v1/experiments/comparison"
            f"?experimentId={survivor_id}&experimentId={comparison_peer_id}"
        ).json() == comparison_before.json()
    engine.dispose()
