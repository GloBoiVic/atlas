"""PostgreSQL receipts for atomic analytical state/frontier persistence."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MethodType
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.models import (
    DeploymentFrontierModel,
    DeploymentModel,
    InstrumentModel,
    StrategyModel,
    StrategyStateModel,
    StrategyVersionModel,
    TradingAccountModel,
    VenueInstrumentModel,
)
from backend.runtime.coordinator import ReconciliationOutcome
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
        pytest.fail("integration tests require a database name ending in _test")
    engine = configure_utc_session_timezone(create_engine(value))
    factory = sessionmaker(engine, class_=Session)
    try:
        yield factory, SqlAlchemyRuntimeStore(engine, factory)
    finally:
        engine.dispose()


def _seed(factory: sessionmaker[Session]):
    with factory() as session, session.begin():
        strategy = StrategyModel(
            strategy_key=f"analytical-{uuid4()}", name="test", description="test"
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
        )
        session.add(deployment)
        session.flush()
        return deployment.id, version.id


def test_state_and_frontier_commit_and_roll_back_together(
    database, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, store = database
    deployment_id, version_id = _seed(factory)
    state = replace(
        EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
        last_evaluated_bar_end=NOW,
    )
    store.persist_strategy_state(deployment_id, version_id, state, "a" * 64)

    with factory() as session:
        persisted = session.scalar(
            select(StrategyStateModel).where(
                StrategyStateModel.deployment_id == deployment_id
            )
        )
        frontier = session.get(DeploymentFrontierModel, deployment_id)
        assert persisted is not None
        assert persisted.analytical_bar_fingerprint == "a" * 64
        assert frontier is not None
        assert frontier.completed_m15_frontier == NOW
        assert frontier.completed_m15_fingerprint == "a" * 64

    def fail_after_state(self, session, deployment_id, **values):
        raise RuntimeError("forced frontier failure")

    monkeypatch.setattr(
        store.safety,
        "record_frontier",
        MethodType(fail_after_state, store.safety),
    )
    next_state = replace(state, last_evaluated_bar_end=NOW + timedelta(minutes=15))
    with pytest.raises(RuntimeError, match="forced frontier failure"):
        store.persist_strategy_state(
            deployment_id, version_id, next_state, "b" * 64
        )

    with factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(StrategyStateModel)
            .where(StrategyStateModel.deployment_id == deployment_id)
        ) == 1
        frontier = session.get(DeploymentFrontierModel, deployment_id)
        assert frontier is not None
        assert frontier.completed_m15_frontier == NOW


def test_database_enforces_unique_deployment_analytical_frontier(database) -> None:
    factory, store = database
    deployment_id, version_id = _seed(factory)
    state = replace(
        EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
        last_evaluated_bar_end=NOW,
    )
    store.persist_strategy_state(deployment_id, version_id, state, "a" * 64)

    with factory() as session:
        session.add(
            StrategyStateModel(
                deployment_id=deployment_id,
                strategy_version_id=version_id,
                state_version=2,
                state_envelope=state.to_json(),
                last_evaluated_bar_end=NOW,
                analytical_bar_fingerprint="a" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

    with factory() as session, session.begin():
        frontier = session.get(DeploymentFrontierModel, deployment_id)
        assert frontier is not None
        frontier.completed_m15_frontier = NOW + timedelta(minutes=15)
        frontier.completed_m15_fingerprint = "b" * 64
        with pytest.raises(DBAPIError, match="matching persisted Strategy state"):
            session.flush()


def test_runtime_health_and_frontier_survive_a_new_store_instance(database) -> None:
    factory, store = database
    deployment_id, version_id = _seed(factory)
    state = replace(
        EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
        last_evaluated_bar_end=NOW,
    )
    store.persist_strategy_state(deployment_id, version_id, state, "a" * 64)
    store.heartbeat(
        deployment_id,
        "restart-test-owner",
        lock_held=True,
        db_connected=True,
        health_status="HEALTHY",
    )
    store.record_reconciliation(
        deployment_id,
        trigger="RUNTIME_START",
        outcome=ReconciliationOutcome.MATCHED,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=1),
        summary={"result": "matched"},
    )

    restored = SqlAlchemyRuntimeStore(store.engine, factory).runtime_health(
        deployment_id
    )

    assert restored["owner_heartbeat_at"] is not None
    assert restored["reconciled_at"] == NOW + timedelta(seconds=1)
    assert restored["analytical_frontier"] == NOW
    assert restored["strategy_state_frontier"] == NOW
