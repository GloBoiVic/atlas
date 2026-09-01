from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Thread
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.market_data import PriceComponent
from backend.domain.strategy import Direction, EntryPolicy, PendingEntryHandoff
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.models import (
    DeploymentModel,
    InstrumentModel,
    OrderModel,
    PendingEntryHandoffModel,
    StrategyModel,
    StrategyStateModel,
    StrategyVersionModel,
    TradingAccountModel,
    VenueInstrumentModel,
)
from backend.persistence.paper_repository import stable_client_correlation_id
from backend.persistence.trading_repository import TradingRepository
from backend.risk import RiskDecision, RiskPhase
from backend.runtime.store import SqlAlchemyRuntimeStore
from backend.strategies.production import (
    EmaSweepConfirmationBreakCompatibilityAdaptor,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


@pytest.fixture()
def database():
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("authorization tests require a database name ending in _test")
    engine = configure_utc_session_timezone(create_engine(value))
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    try:
        yield factory, SqlAlchemyRuntimeStore(engine, factory)
    finally:
        engine.dispose()


def _approved_decision(**changes: object) -> RiskDecision:
    values: dict[str, object] = {
        "phase": RiskPhase.PRE_SUBMISSION,
        "approved": True,
        "entry_price": Decimal("1.1002"),
        "stop_price": Decimal("1.0950"),
        "target_price": None,
        "risk_budget": Decimal("100"),
        "quantity": Decimal("1000"),
        "actual_risk": Decimal("5.2"),
        "quote_bid": Decimal("1.1000"),
        "quote_ask": Decimal("1.1002"),
        "quote_observed_at": NOW,
        "price_bound": Decimal("1.1002"),
        "target_methodology": "R_MULTIPLE",
        "target_multiple": Decimal("1.7"),
        "evidence": {
            "quote_source": "recorded-oanda",
            "quote_tradeable": True,
            "margin_available": "9000",
        },
    }
    values.update(changes)
    return RiskDecision(**values)  # type: ignore[arg-type]


def _seed(
    factory: sessionmaker[Session],
    *,
    persisted_decision: RiskDecision | None = None,
):
    decision = persisted_decision or _approved_decision()
    with factory() as session, session.begin():
        strategy = StrategyModel(
            strategy_key=f"authorization-{uuid4()}", name="test", description="test"
        )
        session.add(strategy)
        session.flush()
        version = StrategyVersionModel(
            strategy_id=strategy.id,
            version_number=1,
            source_fingerprint="a" * 64,
            implementation_key="ema_sweep_confirmation_break_v2",
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
            instrument_id=instrument.id,
            provider="OANDA",
            provider_symbol="EUR_USD",
        )
        account = TradingAccountModel(
            label="Practice",
            external_account_id=f"101-{uuid4()}",
            capabilities={},
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
            actual_state="RUNNING",
        )
        session.add(deployment)
        session.flush()
        methodology = PendingEntryHandoff(
            EntryPolicy.PRICE_TRIGGERED,
            Direction.LONG,
            Decimal("1.1001"),
            PriceComponent.ASK,
            NOW,
            NOW,
            5,
        )
        state = replace(
            EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
            pending_entry=methodology,
            last_evaluated_bar_end=NOW,
        )
        session.add(
            StrategyStateModel(
                deployment_id=deployment.id,
                strategy_version_id=version.id,
                state_version=1,
                state_envelope=state.to_json(),
                last_evaluated_bar_end=NOW,
                analytical_bar_fingerprint="b" * 64,
            )
        )
        repository = TradingRepository()
        intent = repository.create_intent(
            session,
            deployment_id=deployment.id,
            strategy_version_id=version.id,
            venue_instrument_id=venue.id,
            decision_frontier=NOW,
            action="OPEN_LONG",
            direction="LONG",
            proposed_stop=Decimal("1.0950"),
            target_multiple=Decimal("1.7"),
            target_methodology="R_MULTIPLE",
            rationale={"strategy": "test"},
            entry_policy="PRICE_TRIGGERED",
            trigger_price=Decimal("1.1001"),
            trigger_price_basis="ASK",
            expiry_bars=5,
        )
        session.add(
            PendingEntryHandoffModel(
                deployment_id=deployment.id,
                trade_intent_id=intent.id,
            )
        )
        risk = repository.create_paper_risk_decision(
            session,
            trade_intent_id=intent.id,
            decision=decision,
            evaluated_at=NOW,
        )
        ids = deployment.id, intent.id, version.id, risk.id
    store = SqlAlchemyRuntimeStore(factory.kw["bind"], factory)
    runtime_deployment = store.get_deployment(ids[0])
    pending = store.pending_paper_entry(ids[0])
    assert runtime_deployment is not None and pending is not None
    return runtime_deployment, pending, decision, ids[3]


@pytest.mark.parametrize(
    ("persisted", "memory"),
    [
        (
            RiskDecision(
                phase=RiskPhase.PRE_SUBMISSION,
                approved=False,
            ),
            _approved_decision(),
        ),
        (_approved_decision(), _approved_decision(quantity=Decimal("999"))),
        (_approved_decision(), _approved_decision(stop_price=Decimal("1.0949"))),
        (_approved_decision(), _approved_decision(price_bound=Decimal("1.1003"))),
        (
            _approved_decision(),
            _approved_decision(quote_ask=Decimal("1.1003")),
        ),
    ],
)
def test_persisted_authorization_mismatch_blocks_order(
    database, persisted: RiskDecision, memory: RiskDecision
) -> None:
    factory, store = database
    deployment, pending, _, risk_id = _seed(
        factory, persisted_decision=persisted
    )

    with pytest.raises(ValueError, match="persisted PRE_SUBMISSION"):
        store.create_pending_order(deployment, pending, memory, risk_id)

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OrderModel)) == 0


@pytest.mark.parametrize("wrong_owner", ["intent", "deployment"])
def test_wrong_intent_or_deployment_ownership_blocks(
    database, wrong_owner: str
) -> None:
    factory, store = database
    deployment, pending, decision, risk_id = _seed(factory)
    if wrong_owner == "intent":
        pending = replace(pending, intent_id=uuid4())
    else:
        deployment = replace(deployment, id=uuid4())

    with pytest.raises(ValueError, match="(Deployment|ownership)"):
        store.create_pending_order(deployment, pending, decision, risk_id)


def test_superseded_persisted_approval_blocks(database) -> None:
    factory, store = database
    deployment, pending, decision, risk_id = _seed(factory)
    with factory() as session, session.begin():
        TradingRepository().create_paper_risk_decision(
            session,
            trade_intent_id=pending.intent_id,
            decision=RiskDecision(
                phase=RiskPhase.PRE_SUBMISSION,
                approved=False,
            ),
            evaluated_at=NOW + timedelta(seconds=1),
        )

    with pytest.raises(ValueError, match="superseded"):
        store.create_pending_order(deployment, pending, decision, risk_id)


def test_crash_reentry_resolves_existing_pending_order(database) -> None:
    factory, store = database
    deployment, pending, decision, risk_id = _seed(factory)

    first = store.create_pending_order(deployment, pending, decision, risk_id)
    second = store.create_pending_order(deployment, pending, decision, risk_id)

    assert first.created is True
    assert second.created is False
    assert second.order.id == first.order.id
    assert second.current_status == "PENDING_SUBMISSION"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OrderModel)) == 1


def test_unknown_order_is_never_recreated(database) -> None:
    factory, store = database
    deployment, pending, decision, risk_id = _seed(factory)
    first = store.create_pending_order(deployment, pending, decision, risk_id)
    with factory() as session, session.begin():
        row = session.get(OrderModel, first.order.id)
        assert row is not None
        row.current_status = "UNKNOWN"

    resolution = store.create_pending_order(deployment, pending, decision, risk_id)

    assert resolution.created is False
    assert resolution.current_status == "UNKNOWN"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OrderModel)) == 1


def test_concurrent_entry_creation_leaves_one_order(database) -> None:
    factory, store = database
    deployment, pending, decision, risk_id = _seed(factory)
    barrier = Barrier(2)
    resolutions = []
    failures: list[BaseException] = []

    def create() -> None:
        try:
            barrier.wait()
            resolutions.append(
                store.create_pending_order(deployment, pending, decision, risk_id)
            )
        except BaseException as error:  # pragma: no cover - asserted below
            failures.append(error)

    threads = [Thread(target=create), Thread(target=create)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert failures == []
    assert sorted(resolution.created for resolution in resolutions) == [False, True]
    assert len({resolution.order.id for resolution in resolutions}) == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(OrderModel)) == 1


def test_database_uniqueness_rejects_second_entry_order(database) -> None:
    factory, store = database
    deployment, pending, decision, risk_id = _seed(factory)
    store.create_pending_order(deployment, pending, decision, risk_id)
    second_id = uuid4()
    assert decision.quantity is not None

    with pytest.raises(IntegrityError), factory() as session, session.begin():
        TradingRepository().create_order(
            session,
            deployment_id=deployment.id,
            trade_intent_id=pending.intent_id,
            risk_decision_id=risk_id,
            order_type="MARKET",
            purpose="ENTRY",
            direction="LONG",
            quantity=decision.quantity,
            order_id=second_id,
            client_correlation_id=stable_client_correlation_id(second_id),
            time_in_force="FOK",
            price_bound=decision.price_bound,
        )


def test_latest_strategy_state_remains_methodology_authority(database) -> None:
    factory, store = database
    deployment, _, _, _ = _seed(factory)
    next_frontier = NOW + timedelta(minutes=15)
    state = replace(
        EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
        last_evaluated_bar_end=next_frontier,
    )
    with factory() as session, session.begin():
        deployment_row = session.get(DeploymentModel, deployment.id)
        assert deployment_row is not None
        session.add(
            StrategyStateModel(
                deployment_id=deployment.id,
                strategy_version_id=deployment_row.strategy_version_id,
                state_version=2,
                state_envelope=state.to_json(),
                last_evaluated_bar_end=next_frontier,
                analytical_bar_fingerprint="c" * 64,
            )
        )

    with pytest.raises(ValueError, match="Strategy state"):
        store.pending_paper_entry(deployment.id)
