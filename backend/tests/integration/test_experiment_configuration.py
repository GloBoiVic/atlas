from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import StrategyVersion
from backend.experiments.configuration import (
    ConfigurationError,
    ExperimentConfigurationService,
)
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.market_data_repository import (
    BarBatchItem,
    MarketDataRepository,
)
from backend.persistence.models import (
    DatasetSnapshotBarModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentModel,
    MarketBarModel,
    PositionModel,
)
from backend.persistence.strategy_repository import StrategyRepository
from backend.strategies.ema_sweep_engulfing import EmaSweepEngulfingStrategy
from backend.strategies.fingerprint import archive_source
from backend.tests.integration.test_golden_flows import (
    PARAMETERS,
    ROOT,
    START,
    _golden_bars,
    _registry,
    database_url,  # noqa: F401  # imported fixture is registered by pytest
)

pytestmark = pytest.mark.integration


def _seed_configuration(session: Session) -> tuple[object, object]:
    venue = MarketDataRepository().ensure_initial_venue_instrument(
        session, VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    )
    bars = _golden_bars("LONG", phase4=True)
    retrieved = START + timedelta(days=1)
    MarketDataRepository().apply_bar_batch(
        session,
        venue.id,
        tuple(BarBatchItem(bar, retrieved, "configuration-test") for bar in bars),
    )
    end = START + timedelta(minutes=1590)
    from backend.market_data.fingerprint import dataset_fingerprint

    fingerprint = dataset_fingerprint(
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        START,
        end,
        (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID),
        bars,
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    snapshot = DatasetSnapshotModel(
        venue_instrument_id=venue.id,
        base_resolution="M1",
        components=["ASK", "BID", "MID"],
        coverage_start=START,
        coverage_end=end,
        alignment_convention=ALIGNMENT_CONVENTION,
        session_policy=SESSION_POLICY,
        fingerprint_schema=FINGERPRINT_SCHEMA,
        fingerprint=fingerprint,
        integrity_summary={
            "status": "VALID",
            "expected_open_minutes": 1590,
            "expected_closure_minutes": 0,
            "member_minutes": 1590,
            "bar_count": len(bars),
            "unexpected_gap_count": 0,
            "unexpected_observation_count": 0,
            "session_policy": SESSION_POLICY,
        },
    )
    session.add(snapshot)
    session.flush()
    session.add_all(
        DatasetSnapshotBarModel(dataset_snapshot_id=snapshot.id, market_bar_id=row.id)
        for row in session.scalars(
            select(MarketBarModel).where(MarketBarModel.venue_instrument_id == venue.id)
        )
    )
    archive = archive_source(ROOT, EmaSweepEngulfingStrategy.definition.source_files)
    version = StrategyRepository().create_version(
        session,
        StrategyVersion(
            id=uuid4(),
            strategy_key="ema_sweep_engulfing",
            version_number=1,
            source_fingerprint=archive.fingerprint,
            implementation_key="ema_sweep_engulfing.v1",
            parameter_schema=EmaSweepEngulfingStrategy.definition.parameter_schema,
            primary_timeframe=Timeframe.M15,
            warm_up_bars=100,
            state_schema_version=1,
            created_at=START,
        ),
        strategy_name="EMA Sweep Engulfing",
        strategy_description="configuration integration fixture",
        capabilities=("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT"),
        source_archive=archive,
    )
    return version, snapshot


def test_invalid_create_rejects_and_persists_no_graph(database_url: str) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    engine = configure_utc_session_timezone(create_engine(database_url))
    with Session(engine) as session:
        version, snapshot = _seed_configuration(session)
        service = ExperimentConfigurationService(_registry())
        with pytest.raises(ConfigurationError, match="RANGE_OUTSIDE_SNAPSHOT"):
            service.create(
                session,
                strategy_version_id=version.id,
                dataset_snapshot_id=snapshot.id,
                trading_start=START + timedelta(minutes=1500),
                trading_end=START + timedelta(minutes=1605),
                starting_capital=Decimal("10000"),
                risk_per_trade=Decimal("0.01"),
                parameters=PARAMETERS,
                slippage_ticks=0,
                commission_per_unit=Decimal("0"),
            )
        assert session.scalar(select(ExperimentModel.id)) is None
        session.rollback()
    engine.dispose()


def test_valid_create_commits_exactly_one_pending_graph(database_url: str) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    engine = configure_utc_session_timezone(create_engine(database_url))
    with Session(engine) as session:
        version, snapshot = _seed_configuration(session)
        service = ExperimentConfigurationService(_registry())
        experiment = service.create(
            session,
            strategy_version_id=version.id,
            dataset_snapshot_id=snapshot.id,
            trading_start=START + timedelta(minutes=1500),
            trading_end=START + timedelta(minutes=1590),
            starting_capital=Decimal("10000"),
            risk_per_trade=Decimal("0.01"),
            parameters=PARAMETERS,
            slippage_ticks=0,
            commission_per_unit=Decimal("0"),
        )
        session.commit()
        assert experiment.status == "PENDING"
        assert session.scalars(select(ExperimentModel)).all() == [experiment]
        accounts = session.scalars(select(ExperimentAccountModel)).all()
        positions = session.scalars(select(PositionModel)).all()
        assert len(accounts) == 1 and accounts[0].base_currency == "USD"
        assert len(positions) == 1 and positions[0].state == "FLAT"
    engine.dispose()
