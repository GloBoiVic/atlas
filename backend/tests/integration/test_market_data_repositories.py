import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.market_data.fingerprint import dataset_fingerprint
from backend.persistence.market_data_repository import (
    BarBatchItem,
    DatasetSnapshotRepository,
    MarketDataRepository,
)
from backend.persistence.models import MarketBarModel, VenueInstrumentModel

pytestmark = pytest.mark.integration


def _url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is required for integration tests")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("repository tests require a database name ending in _test")
    return value


@pytest.fixture(scope="module", autouse=True)
def prepare_repository_database() -> None:
    """Make this module independent of pytest's integration-file ordering."""
    url = _url()
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    # env.py deliberately reads this explicit test-only URL for migrations.
    os.environ["ATLAS_DATABASE_URL"] = url
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def isolate_repository_facts() -> Generator[None]:
    """Keep committed concurrency fixtures from leaking across tests/modules."""
    engine = create_engine(_url(), pool_pre_ping=True)
    statement = text(
        "TRUNCATE dataset_snapshot_bars, dataset_snapshots, market_bars, "
        "venue_instruments, instruments CASCADE"
    )
    with engine.begin() as connection:
        connection.execute(statement)
    try:
        yield
    finally:
        with engine.begin() as connection:
            connection.execute(statement)
        engine.dispose()


def _bar(moment: datetime, component: PriceComponent, value: str = "1.1000") -> Bar:
    price = Decimal(value)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M1,
        component,
        moment,
        moment + timedelta(minutes=1),
        price,
        price + Decimal(".001"),
        price - Decimal(".001"),
        price,
    )


@pytest.fixture()
def repository_session() -> Generator[tuple[Session, Engine]]:
    engine = create_engine(_url(), pool_pre_ping=True)
    session = Session(engine)
    session.begin()
    try:
        yield session, engine
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _mapping(session: Session) -> VenueInstrumentModel:
    return MarketDataRepository().ensure_initial_venue_instrument(
        session, VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    )


def test_first_load_replay_correction_and_reversion(
    repository_session: tuple[Session, Engine],
) -> None:
    session, _ = repository_session
    repo = MarketDataRepository()
    mapping = _mapping(session)
    moment = datetime(2026, 1, 5, 10, tzinfo=UTC)
    item = BarBatchItem(_bar(moment, PriceComponent.MID), moment + timedelta(minutes=2))
    assert repo.apply_bar_batch(session, mapping.id, (item,)).inserted == 1
    stored = session.scalar(
        select(MarketBarModel).where(
            MarketBarModel.venue_instrument_id == mapping.id,
            MarketBarModel.start_time == moment,
        )
    )
    assert stored is not None
    assert stored.resolution == "M1"
    assert item.bar.to_json()["timeframe"] == "1m"
    assert repo.apply_bar_batch(session, mapping.id, (item,)).unchanged == 1
    corrected = BarBatchItem(
        _bar(moment, PriceComponent.MID, "1.2000"), moment + timedelta(minutes=3)
    )
    assert repo.apply_bar_batch(session, mapping.id, (corrected,)).inserted == 1
    assert repo.apply_bar_batch(session, mapping.id, (item,)).reactivated == 1
    current = repo.current_bars(
        session,
        mapping.id,
        moment,
        moment + timedelta(minutes=1),
        (PriceComponent.MID,),
    )
    assert current[0].start_time.tzinfo is UTC
    assert current[0].start_time == moment
    rows = session.scalars(
        select(MarketBarModel).where(
            MarketBarModel.venue_instrument_id == mapping.id,
            MarketBarModel.start_time == moment,
        )
    ).all()
    assert len(rows) == 2
    assert sum(row.is_current for row in rows) == 1


def test_missing_ranges_and_snapshot_membership_are_immutable_boundary(
    repository_session: tuple[Session, Engine],
) -> None:
    session, _ = repository_session
    repo = MarketDataRepository()
    mapping = _mapping(session)
    start = datetime(2026, 1, 5, 11, tzinfo=UTC)
    bars = tuple(_bar(start, component) for component in PriceComponent)
    repo.apply_bar_batch(
        session,
        mapping.id,
        tuple(BarBatchItem(bar, start + timedelta(minutes=2)) for bar in bars),
    )
    assert (
        repo.missing_ranges(
            session,
            mapping.id,
            start,
            start + timedelta(minutes=1),
            tuple(PriceComponent),
        )
        == ()
    )
    expected_fingerprint = dataset_fingerprint(
        snapshot_venue := VenueInstrument(
            Instrument.EUR_USD, Provider.OANDA, "EUR_USD"
        ),
        start,
        start + timedelta(minutes=1),
        (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID),
        bars,
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    snapshot = DatasetSnapshot(
        uuid4(),
        snapshot_venue,
        Timeframe.M1,
        (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID),
        start,
        start + timedelta(minutes=1),
        ALIGNMENT_CONVENTION,
        SESSION_POLICY,
        FINGERPRINT_SCHEMA,
        expected_fingerprint,
        {
            "status": "VALID",
            "expected_open_minutes": 1,
            "expected_closure_minutes": 0,
            "member_minutes": 1,
            "bar_count": 3,
            "unexpected_gap_count": 0,
            "unexpected_observation_count": 0,
            "session_policy": SESSION_POLICY,
        },
        start + timedelta(minutes=3),
    )
    rows = session.scalars(
        select(MarketBarModel).where(
            MarketBarModel.venue_instrument_id == mapping.id,
            MarketBarModel.start_time >= start,
            MarketBarModel.start_time < start + timedelta(minutes=1),
            MarketBarModel.is_current.is_(True),
        )
    ).all()
    stored = DatasetSnapshotRepository().create_validated(session, snapshot, rows)
    assert DatasetSnapshotRepository().members(session, stored.id) == tuple(
        sorted(bars, key=lambda bar: (bar.start_time, bar.price_component.value))
    )


def test_concurrent_batches_serialize_current_projection(
    repository_session: tuple[Session, Engine],
) -> None:
    _, engine = repository_session
    setup = Session(engine)
    mapping = _mapping(setup)
    setup.commit()
    mapping_id = mapping.id
    setup.close()
    moment = datetime(2026, 1, 5, 12, tzinfo=UTC)

    def apply(value: str) -> None:
        session = Session(engine)
        try:
            session.begin()
            MarketDataRepository().apply_bar_batch(
                session,
                mapping_id,
                (BarBatchItem(_bar(moment, PriceComponent.MID, value), moment),),
            )
            session.commit()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tuple(pool.map(apply, ("1.3000", "1.4000")))
    check = Session(engine)
    try:
        assert (
            check.scalar(
                select(MarketBarModel.id).where(
                    MarketBarModel.venue_instrument_id == mapping_id,
                    MarketBarModel.start_time == moment,
                    MarketBarModel.is_current.is_(True),
                )
            )
            is not None
        )
        assert (
            check.scalar(
                select(func.count(MarketBarModel.id)).where(
                    MarketBarModel.venue_instrument_id == mapping_id,
                    MarketBarModel.start_time == moment,
                    MarketBarModel.is_current.is_(True),
                )
            )
            == 1
        )
    finally:
        check.close()
