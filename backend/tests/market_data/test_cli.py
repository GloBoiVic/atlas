import os
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr

from backend.config import Environment, Settings, get_settings
from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.integrations.oanda.source import FetchDiagnostics, FetchResult
from backend.market_data.cli import build_parser, run
from backend.market_data.coverage import CoverageGap, CoverageReport, MissingMinute
from backend.market_data.ingestion import MarketDataService
from backend.persistence.database import create_database_engine, create_session_factory


class FakeEngine:
    def dispose(self) -> None:
        pass


def _coverage(valid: bool = True) -> CoverageReport:
    return (
        CoverageReport(1, 0, 1, (), (), (), ())
        if valid
        else CoverageReport(1, 0, 0, (), (), (), ())
    )


class FakeService:
    def inspect_coverage(self, start: datetime, end: datetime) -> object:
        return SimpleNamespace(
            requested_start=start,
            requested_end=end,
            coverage=_coverage(),
            valid=True,
        )

    def derive_m15(self, fingerprint: str, component: object) -> tuple[object, ...]:
        assert fingerprint == "a" * 64
        assert str(component) == "MID"
        return (object(),)


def factory(_needs_oanda: bool) -> tuple[FakeService, FakeEngine]:
    return FakeService(), FakeEngine()


def test_parser_rejects_naive_timestamp() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "coverage",
                "--start",
                "2025-01-01T00:00:00",
                "--end",
                "2025-01-01T01:00:00Z",
            ]
        )


def test_invalid_fingerprint_is_rejected_before_service_factory() -> None:
    called = False

    def unexpected_factory(_needs_oanda: bool) -> tuple[FakeService, FakeEngine]:
        nonlocal called
        called = True
        return FakeService(), FakeEngine()

    with pytest.raises(SystemExit):
        run(
            [
                "derive-m15",
                "--snapshot-fingerprint",
                "A" * 64,
                "--component",
                "MID",
            ],
            service_factory=unexpected_factory,
        )
    assert not called


def test_error_output_is_classified_without_secret_or_provider_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "super-secret-token"
    body = f"Bearer {secret} provider-body password={secret}"

    def failing_factory(_needs_oanda: bool) -> tuple[object, FakeEngine]:
        class FailingService:
            def derive_m15(
                self, _fingerprint: str, _component: object
            ) -> tuple[object, ...]:
                raise RuntimeError(body)

        return FailingService(), FakeEngine()

    result = run(
        [
            "derive-m15",
            "--snapshot-fingerprint",
            "a" * 64,
            "--component",
            "MID",
        ],
        service_factory=failing_factory,
    )
    output = capsys.readouterr().out
    assert result == 1
    assert '"error":"service_error"' in output
    assert secret not in output
    assert "provider-body" not in output
    assert "Traceback" not in output


def test_load_failure_reports_persistence_and_next_action(
    capsys: pytest.CaptureFixture[str],
) -> None:
    start = datetime(2025, 1, 6, 0, 0, tzinfo=UTC)
    end = datetime(2025, 1, 6, 1, 0, tzinfo=UTC)

    class PartiallyCommittedService:
        def load_missing(
            self, requested_start: datetime, requested_end: datetime
        ) -> object:
            return SimpleNamespace(
                requested_start=requested_start,
                requested_end=requested_end,
                committed_ranges=((start, start + (end - start)),),
                inserted=3,
                reactivated=0,
                unchanged=0,
                incomplete_minutes=(),
                coverage=_coverage(False),
                valid=False,
                failure=SimpleNamespace(
                    range_start=start,
                    range_end=end,
                    message="Bearer secret provider body",
                ),
            )

    result = run(
        [
            "load-missing",
            "--start",
            "2025-01-06T00:00:00Z",
            "--end",
            "2025-01-06T01:00:00Z",
            "--json",
        ],
        service_factory=lambda _needs_oanda: (
            PartiallyCommittedService(),
            FakeEngine(),
        ),
    )
    output = capsys.readouterr().out
    assert result == 1
    assert '"classification":"historical_source_failure"' in output
    assert '"inserted":3' in output
    assert '"snapshot_valid":null' in output
    assert "retry" in output
    assert "secret" not in output
    assert "provider body" not in output


def test_coverage_json_is_stable_and_has_no_uuid(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(
        [
            "coverage",
            "--start",
            "2025-01-06T00:00:00Z",
            "--end",
            "2025-01-06T01:00:00Z",
            "--json",
        ],
        service_factory=factory,
    )
    output = capsys.readouterr().out
    assert result == 0
    assert '"Instrument":"EUR/USD"' in output
    assert "00000000-0000-0000-0000-000000000000" not in output
    assert "token" not in output.lower()


def test_derive_reports_fingerprint_and_component() -> None:
    assert (
        run(
            [
                "derive-m15",
                "--snapshot-fingerprint",
                "a" * 64,
                "--component",
                "MID",
            ],
            service_factory=factory,
        )
        == 0
    )


def test_snapshot_failure_reports_integrity_status_without_identifiers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    start = datetime(2025, 1, 6, 0, 0, tzinfo=UTC)
    end = datetime(2025, 1, 6, 1, 0, tzinfo=UTC)
    gap = CoverageGap(
        start,
        end,
        (PriceComponent.MID,),
        (MissingMinute(start, (PriceComponent.MID,)),),
    )

    class InvalidSnapshotService:
        def create_snapshot(
            self, requested_start: datetime, requested_end: datetime
        ) -> object:
            return SimpleNamespace(
                requested_start=requested_start,
                requested_end=requested_end,
                coverage=CoverageReport(1, 0, 0, (), (gap,), (), ()),
                snapshot=None,
                failure="coverage is incomplete",
                valid=False,
            )

    result = run(
        [
            "snapshot",
            "--start",
            "2025-01-06T00:00:00Z",
            "--end",
            "2025-01-06T01:00:00Z",
            "--json",
        ],
        service_factory=lambda _needs_oanda: (InvalidSnapshotService(), FakeEngine()),
    )
    output = capsys.readouterr().out
    assert result == 1
    assert '"classification":"snapshot_integrity"' in output
    assert '"next_action":"repair reported gaps and retry"' in output
    assert '"components":["MID"]' in output or '"gap_ranges"' in output
    assert "failure" not in output
    assert "00000000-0000-0000-0000-000000000000" not in output


@pytest.mark.integration
def test_cli_load_uses_fake_source_and_dedicated_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not set")
    # This test owns its database setup so it is independent of integration
    # test ordering and works against a freshly created *_test database.
    monkeypatch.setenv("ATLAS_DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        get_settings.cache_clear()
    settings = Settings(
        database_url=SecretStr(database_url), environment=Environment.TEST
    )
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    class FakeSource:
        def fetch(self, start: datetime, end: datetime) -> FetchResult:
            assert (start, end) == (
                datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
                datetime(2026, 1, 5, 10, 1, tzinfo=UTC),
            )
            bars = tuple(
                Bar(
                    instrument=Instrument.EUR_USD,
                    timeframe=Timeframe.M1,
                    price_component=component,
                    start_time=start,
                    end_time=end,
                    open=Decimal("1.1"),
                    high=Decimal("1.2"),
                    low=Decimal("1.0"),
                    close=Decimal("1.15"),
                )
                for component in (
                    PriceComponent.ASK,
                    PriceComponent.BID,
                    PriceComponent.MID,
                )
            )
            return FetchResult(bars, (), FetchDiagnostics(()))

    service = MarketDataService(factory, cast(Any, FakeSource()))
    try:
        result = run(
            [
                "load-missing",
                "--start",
                "2026-01-05T10:00:00Z",
                "--end",
                "2026-01-05T10:01:00Z",
                "--json",
            ],
            service_factory=lambda _needs_oanda: (service, engine),
        )
        assert result == 0
    finally:
        engine.dispose()
