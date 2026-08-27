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
    FINGERPRINT_SCHEMA_V2,
    GAP_POLICY_V1,
    SESSION_POLICY,
    SNAPSHOT_SCHEMA_V2,
    Bar,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.market_data.fingerprint import dataset_fingerprint
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.market_data_repository import (
    BarBatchItem,
    BarBatchResult,
    _SNAPSHOT_MEMBERSHIP_BATCH_SIZE,
    DatasetSnapshotRepository,
    MarketDataRepository,
)
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotGapModel,
    MarketBarModel,
    VenueInstrumentModel,
)

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
    engine = configure_utc_session_timezone(create_engine(_url(), pool_pre_ping=True))
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
    engine = configure_utc_session_timezone(create_engine(_url(), pool_pre_ping=True))
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
    session.flush()
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
        tuple(
            BarBatchItem(
                bar,
                start + timedelta(minutes=2),
                f"request-{bar.price_component.value}",
            )
            for bar in bars
        ),
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
    snapshot_repo = DatasetSnapshotRepository()
    captured = snapshot_repo.ordered_members_with_sources(
        session, stored.id, start, start + timedelta(minutes=1)
    )
    assert [item.bar.price_component for item in captured] == sorted(
        PriceComponent, key=lambda component: component.value
    )
    assert {item.source.source_request_id for item in captured} == {
        "request-ASK",
        "request-BID",
        "request-MID",
    }

    # A correction changes the mutable head only.  The snapshot read remains
    # pinned to the originally captured MarketBar identities and values.
    corrected = BarBatchItem(
        _bar(start, PriceComponent.MID, "1.2500"),
        start + timedelta(minutes=4),
        "correction-1",
    )
    repo.apply_bar_batch(session, mapping.id, (corrected,))
    reread = snapshot_repo.ordered_members_with_sources(
        session, stored.id, start, start + timedelta(minutes=1)
    )
    assert reread == captured
    assert reread[2].bar.close == Decimal("1.1000")
    assert (
        session.scalar(
            select(MarketBarModel.content_fingerprint).where(
                MarketBarModel.venue_instrument_id == mapping.id,
                MarketBarModel.start_time == start,
                MarketBarModel.price_component == PriceComponent.MID.value,
                MarketBarModel.is_current.is_(True),
            )
        )
        != reread[2].source.content_fingerprint
    )


def test_v2_bulk_memberships_persist_representative_large_batch(
    repository_session: tuple[Session, Engine],
) -> None:
    # Regression guard for the full-year sparse execution shape: bounded
    # payloads must stay well below the live 740k-row membership while not
    # regressing to the former ~740 round trips.
    assert _SNAPSHOT_MEMBERSHIP_BATCH_SIZE == 10_000
    assert (740_226 + _SNAPSHOT_MEMBERSHIP_BATCH_SIZE - 1) // _SNAPSHOT_MEMBERSHIP_BATCH_SIZE == 75
    session, _ = repository_session
    _mapping(session)
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    analytical = tuple(
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            start + timedelta(minutes=15 * index),
            start + timedelta(minutes=15 * (index + 1)),
            Decimal("1.1000"),
            Decimal("1.1010"),
            Decimal("1.0990"),
            Decimal("1.1005"),
        )
        # Full-year native M15 acquisition produces tens of thousands of
        # analytical rows. This crosses the bounded persistence batch size and
        # guards against regressing to one oversized executemany payload while
        # keeping the fixture deterministic and representative of chunking.
        for index in range(1_201)
    )
    end = start + timedelta(minutes=15 * len(analytical))
    gaps = tuple(
        {
            "start_time": start + timedelta(minutes=15 * index),
            "end_time": start + timedelta(minutes=15 * (index + 1)),
            "price_component": "MID",
            "resolution": "M15",
            "source": "OANDA",
            "reason": "MISSING_NATIVE_COMPLETED_CANDLE",
            "classification": "NON_BLOCKING",
            "affected_state": None,
            "affected_event": None,
            "policy_version": GAP_POLICY_V1,
            "blocked": False,
        }
        for index in range(100)
    )
    snapshot = DatasetSnapshot(
        uuid4(),
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        Timeframe.M15,
        (PriceComponent.MID,),
        start,
        end,
        ALIGNMENT_CONVENTION,
        SESSION_POLICY,
        FINGERPRINT_SCHEMA_V2,
        "b" * 64,
        {"status": "VALID", "policy_version": GAP_POLICY_V1},
        start + timedelta(days=1),
        SNAPSHOT_SCHEMA_V2,
    )
    stored = DatasetSnapshotRepository().create_v2_validated(
        session, snapshot, analytical, (), gaps
    )
    assert stored.id == snapshot.id
    assert (
        session.scalar(
            select(func.count(DatasetSnapshotAnalyticalBarModel.sequence)).where(
                DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id == snapshot.id
            )
        )
        == 1_201
    )
    assert (
        session.scalar(
            select(func.count(DatasetSnapshotGapModel.sequence)).where(
                DatasetSnapshotGapModel.dataset_snapshot_id == snapshot.id
            )
        )
        == 100
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


def test_large_m1_batch_uses_set_based_existing_row_lookup(
    repository_session: tuple[Session, Engine],
) -> None:
    session, _ = repository_session
    mapping = _mapping(session)
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    items = tuple(
        BarBatchItem(
            _bar(
                start + timedelta(minutes=index),
                component,
            ),
            start,
            "large-batch",
        )
        for index in range(25_000)
        for component in (PriceComponent.BID, PriceComponent.ASK)
    )

    result = MarketDataRepository().apply_bar_batch(session, mapping.id, items)

    assert result == BarBatchResult(inserted=50_000)
