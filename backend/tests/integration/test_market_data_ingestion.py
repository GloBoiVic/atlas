import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.domain.strategy import StrategyContext
from backend.integrations.oanda.source import (
    FetchDiagnostics,
    FetchResult,
    IncompleteCandle,
)
from backend.market_data.ingestion import (
    HistoricalFetchResult,
    MarketDataService,
)
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.market_data_repository import DatasetSnapshotRepository

pytestmark = pytest.mark.integration


def _url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is required for integration tests")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("ingestion tests require a database name ending in _test")
    return value


@pytest.fixture(scope="module")
def database_url() -> str:
    value = _url()
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    os.environ["ATLAS_DATABASE_URL"] = value
    command.upgrade(config, "head")
    return value


@pytest.fixture()
def session_factory(database_url: str) -> Generator[sessionmaker[Session]]:
    engine = configure_utc_session_timezone(
        create_engine(database_url, pool_pre_ping=True)
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE dataset_snapshot_bars, dataset_snapshots, market_bars, "
                "venue_instruments, instruments CASCADE"
            )
        )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _bars(moment: datetime, value: str = "1.1000") -> tuple[Bar, ...]:
    price = Decimal(value)
    return tuple(
        Bar(
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
        for component in (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID)
    )


class FakeSource:
    def __init__(
        self, responses: list[tuple[Bar, ...] | FetchResult | Exception]
    ) -> None:
        self.responses = responses
        self.calls: list[tuple[datetime, datetime]] = []

    def fetch(self, start: datetime, end: datetime) -> HistoricalFetchResult:
        self.calls.append((start, end))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, FetchResult):
            return cast(HistoricalFetchResult, response)
        return cast(
            HistoricalFetchResult,
            FetchResult(response, (), FetchDiagnostics(())),
        )


def _service(factory: sessionmaker[Session], source: FakeSource) -> MarketDataService:
    def frontier() -> datetime:
        return datetime(2026, 1, 5, 12, tzinfo=UTC)

    def clock() -> datetime:
        return datetime(2026, 1, 5, 13, tzinfo=UTC)

    return MarketDataService(factory, source, clock=clock, frontier=frontier)


def test_partial_provider_failure_is_inspectable_and_network_is_outside_transactions(
    session_factory: sessionmaker[Session],
) -> None:
    first = datetime(2026, 1, 5, 10, tzinfo=UTC)
    second = first + timedelta(minutes=1)
    source = FakeSource(
        [_bars(second), _bars(first), RuntimeError("provider unavailable")]
    )
    service = _service(session_factory, source)
    service.refresh_range(second, second + timedelta(minutes=1))
    source.calls.clear()

    # The two missing minutes are intentionally non-adjacent, producing two fetches.
    result = service.load_missing(first, second + timedelta(minutes=3))

    assert result.failure is not None
    assert result.committed_ranges == ((first, first + timedelta(minutes=1)),)
    assert result.coverage.valid is False
    assert result.coverage.gaps
    assert source.calls == [
        (first, first + timedelta(minutes=1)),
        (second + timedelta(minutes=1), second + timedelta(minutes=3)),
    ]


def test_incomplete_and_closure_anomaly_block_snapshot(
    session_factory: sessionmaker[Session],
) -> None:
    moment = datetime(2026, 1, 5, 10, tzinfo=UTC)
    incomplete = FakeSource(
        [
            FetchResult(
                (),
                (IncompleteCandle(moment),),
                FetchDiagnostics(()),
            )
        ]
    )
    service = _service(session_factory, incomplete)
    loaded = service.refresh_range(moment, moment + timedelta(minutes=1))
    assert loaded.coverage.valid is False
    assert (
        service.create_snapshot(moment, moment + timedelta(minutes=1)).snapshot is None
    )

    closure = datetime(2026, 1, 4, 12, tzinfo=UTC)
    anomalous = FakeSource([_bars(closure)])
    anomaly_service = _service(session_factory, anomalous)
    anomaly_service.refresh_range(closure, closure + timedelta(minutes=1))
    report = anomaly_service.create_snapshot(closure, closure + timedelta(minutes=1))
    assert report.snapshot is None
    assert report.coverage.closure_anomalies == (closure,)


def test_correction_creates_new_snapshot_without_changing_old_members(
    session_factory: sessionmaker[Session],
) -> None:
    moment = datetime(2026, 1, 5, 10, tzinfo=UTC)
    source = FakeSource([_bars(moment), _bars(moment, "1.2000")])
    service = _service(session_factory, source)
    end = moment + timedelta(minutes=1)

    service.refresh_range(moment, end)
    old = service.create_snapshot(moment, end)
    assert old.snapshot is not None
    old_session = session_factory()
    try:
        old_members = DatasetSnapshotRepository().members(old_session, old.snapshot.id)
    finally:
        old_session.close()

    service.refresh_range(moment, end)
    new = service.create_snapshot(moment, end)
    assert new.snapshot is not None
    assert new.snapshot.fingerprint != old.snapshot.fingerprint

    check = session_factory()
    try:
        assert (
            DatasetSnapshotRepository().members(check, old.snapshot.id) == old_members
        )
    finally:
        check.close()


def test_v2_snapshot_creation_returns_without_nested_mapping_lock(
    session_factory: sessionmaker[Session],
) -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    source = FakeSource([
        tuple(bar for i in range(15) for bar in _bars(start + timedelta(minutes=i)))
    ])
    service = _service(session_factory, source)
    service.refresh_range(start, end)
    analytical = Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        end,
        Decimal("1.1000"),
        Decimal("1.1010"),
        Decimal("1.0990"),
        Decimal("1.1005"),
    )

    report = service.create_snapshot_v2(start, end, analytical=(analytical,))

    assert report.snapshot is not None
    assert report.snapshot.snapshot_schema == "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2"


def test_m15_derivation_reads_snapshot_membership_and_binds_strategy_input(
    session_factory: sessionmaker[Session],
) -> None:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    end = start + timedelta(minutes=15)

    def minute_bars(correction_offset: int | None = None) -> tuple[Bar, ...]:
        return tuple(
            bar
            for offset in range(15)
            for bar in _bars(
                start + timedelta(minutes=offset),
                "1.2000" if offset == correction_offset else "1.1000",
            )
        )

    source = FakeSource([minute_bars(), minute_bars(7)])
    service = _service(session_factory, source)

    service.refresh_range(start, end)
    old_report = service.create_snapshot(start, end)
    assert old_report.snapshot is not None
    old_mid = service.derive_m15(old_report.snapshot.fingerprint, PriceComponent.MID)
    assert len(old_mid) == 1
    assert StrategyContext(end, Instrument.EUR_USD, old_mid).bars == old_mid

    service.refresh_range(start, end)
    new_report = service.create_snapshot(start, end)
    assert new_report.snapshot is not None
    new_mid = service.derive_m15(new_report.snapshot.fingerprint, PriceComponent.MID)
    assert new_mid != old_mid
    assert (
        service.derive_m15(old_report.snapshot.fingerprint, PriceComponent.MID)
        == old_mid
    )

    bid = service.derive_m15(new_report.snapshot.fingerprint, PriceComponent.BID)
    ask = service.derive_m15(new_report.snapshot.fingerprint, PriceComponent.ASK)
    assert StrategyContext(end, Instrument.EUR_USD, bid).bars == bid
    assert StrategyContext(end, Instrument.EUR_USD, ask).bars == ask
    assert StrategyContext(end, Instrument.EUR_USD, tuple(_bars(start)[2:3])).bars
