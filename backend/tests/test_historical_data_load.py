import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.api.historical_data import _active_conflict_details
from backend.market_data.historical_load import (
    MAX_ELAPSED_DAYS,
    MAX_WINDOWS,
    HistoricalDataLoadCoordinator,
    _warmup_plan,
)
from backend.market_data.ingestion import classify_failure
from backend.persistence.historical_data_load_repository import (
    HistoricalDataLoadRepository,
)
from backend.persistence.models import HistoricalDataLoadRequestModel

UTC_START = datetime(2026, 1, 5, 15, 0, tzinfo=UTC)


def test_warmup_plan_accepts_exactly_100_observed_bars() -> None:
    plan = _warmup_plan(
        UTC_START,
        UTC_START + timedelta(minutes=15),
        UTC_START - timedelta(hours=25),
        100,
        1,
        100,
    )
    assert plan.outcome == "READY"


def test_warmup_plan_fails_at_both_hard_bounds() -> None:
    plan = _warmup_plan(
        UTC_START,
        UTC_START + timedelta(minutes=15),
        UTC_START - timedelta(days=MAX_ELAPSED_DAYS),
        99,
        MAX_WINDOWS,
        100,
    )
    assert plan.outcome == "INSUFFICIENT_WARMUP"


def test_warmup_plan_extension_is_deterministic_across_closure_ranges() -> None:
    first = _warmup_plan(
        UTC_START,
        UTC_START + timedelta(minutes=15),
        UTC_START - timedelta(hours=25),
        80,
        3,
        100,
    )
    second = _warmup_plan(
        UTC_START,
        UTC_START + timedelta(minutes=15),
        UTC_START - timedelta(hours=25),
        80,
        3,
        100,
    )
    assert first == second
    assert first.load_start == UTC_START - timedelta(hours=50)


def test_prepare_rejects_non_utc_misaligned_and_overlong_ranges() -> None:
    coordinator = HistoricalDataLoadCoordinator(
        lambda: None, SimpleNamespace(), SimpleNamespace(), SimpleNamespace()
    )
    for start, end in (
        (UTC_START.replace(tzinfo=None), UTC_START + timedelta(minutes=15)),
        (UTC_START + timedelta(minutes=1), UTC_START + timedelta(minutes=16)),
    ):
        with pytest.raises(ValueError, match="Trading period"):
            coordinator.prepare(
                SimpleNamespace(),
                strategy_version_id=uuid4(),
                trading_start=start,
                trading_end=end,
            )


def test_model_declares_json_checks_and_one_active_partial_unique_index() -> None:
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in HistoricalDataLoadRequestModel.__table__.constraints
        if hasattr(constraint, "sqltext")
    }
    progress_check = constraints["ck_historical_data_load_requests_progress_arrays"]
    assert "atlas_historical_ranges_valid(fetched_ranges)" in progress_check
    assert "atlas_historical_ranges_valid(committed_ranges)" in progress_check
    assert (
        "jsonb_typeof(experiment_validation)"
        in constraints["ck_historical_data_load_requests_validation_object"]
    )
    indexes = {
        index.name: str(index.dialect_options["postgresql"].get("where"))
        for index in HistoricalDataLoadRequestModel.__table__.indexes
    }
    assert (
        "status IN ('PENDING','RUNNING')"
        in indexes["uq_historical_data_load_requests_active"]
    )
    assert any(
        index.name == "uq_historical_data_load_requests_active" and index.unique
        for index in HistoricalDataLoadRequestModel.__table__.indexes
    )


def test_progress_check_is_bounded_and_ordered_in_migration() -> None:
    migration = (
        __import__(
            "pathlib"
        ).Path(__file__).parents[1]
        / "persistence/migrations/versions/0008_historical_load.py"
    ).read_text()
    assert "jsonb_array_length(value) > 40" in migration
    assert "current_end <= current_start" in migration
    assert "current_start < previous_end" in migration


@pytest.mark.integration
def test_postgres_installs_bounded_progress_constraint() -> None:
    url = os.getenv("ATLAS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as connection:
        definition = connection.scalar(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'historical_data_load_requests'::regclass
                  AND conname = 'ck_historical_data_load_requests_progress_arrays'
                """
            )
        )
    assert definition is not None
    assert "atlas_historical_ranges_valid" in definition
    assert engine.url.database and engine.url.database.endswith("_test")
    engine.dispose()


def test_active_conflict_exposes_attachable_status_facts() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        status="RUNNING",
        created_at=datetime(2026, 1, 5, 15, 0, tzinfo=UTC),
    )
    details = _active_conflict_details(row)
    assert details["requestId"] == str(row.id)
    assert details["status"] == "RUNNING"
    assert details["displayLabel"].startswith("EUR/USD historical load ·")
    assert details["statusUrl"].endswith(str(row.id))


def test_failure_classification_redacts_provider_details() -> None:
    error = RuntimeError("token=do-not-persist Authorization: secret")
    category, code, detail = classify_failure(error)
    assert (category, code) == ("RUNTIME", "HISTORICAL_LOAD_FAILED")
    assert "secret" not in detail
    assert "do-not-persist" not in detail


class RecoverySession:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: self.rows)

    def flush(self):
        pass


def test_repository_claim_uses_a_row_lock() -> None:
    class LockSession:
        def __init__(self):
            self.statement = None

        def scalar(self, statement):
            self.statement = statement
            return None

        def flush(self):
            pass

    session = LockSession()
    HistoricalDataLoadRepository().claim(session, uuid4())
    assert session.statement is not None
    assert session.statement._for_update_arg is not None


def test_startup_recovery_uses_distinct_fail_closed_codes() -> None:
    pending = SimpleNamespace(status="PENDING")
    running = SimpleNamespace(status="RUNNING")

    recovered = HistoricalDataLoadRepository().recover_interrupted(
        RecoverySession([pending, running])
    )

    assert recovered == 2
    assert (pending.status, pending.failure_code) == (
        "FAILED",
        "LOAD_INTERRUPTED_BEFORE_START",
    )
    assert (running.status, running.failure_code) == ("FAILED", "LOAD_INTERRUPTED")


class FakeSession:
    @contextmanager
    def begin(self):
        yield self

    def close(self) -> None:
        pass


class FakeRepository:
    def __init__(self, row):
        self.row = row
        self.events: list[str] = []

    def claim(self, _session, _request_id):
        self.events.append("claim")
        self.row.status = "RUNNING"
        return self.row

    def record_progress(self, _session, *_args, **_kwargs):
        self.events.append("progress")

    def complete(self, _session, *_args, **_kwargs):
        self.events.append("complete")
        self.row.status = "COMPLETED"


def test_claim_failure_is_attempted_as_sanitized_terminal_failure(monkeypatch) -> None:
    row = SimpleNamespace(id=uuid4(), status="PENDING")
    repository = SimpleNamespace(
        claim=lambda *_args: (_ for _ in ()).throw(RuntimeError("claim failed")),
        fail_if_active=lambda *args, **kwargs: setattr(row, "status", "FAILED"),
    )
    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        repository=repository,
    )

    @contextmanager
    def fake_scope(_factory):
        yield FakeSession()

    monkeypatch.setattr("backend.market_data.historical_load.session_scope", fake_scope)
    coordinator.run(row.id)
    assert row.status == "FAILED"


def test_success_order_is_load_snapshot_m15_then_validation() -> None:
    events: list[str] = []
    row = SimpleNamespace(
        id=uuid4(),
        status="PENDING",
        load_start=UTC_START,
        load_end=UTC_START + timedelta(minutes=15),
        trading_start=UTC_START,
        trading_end=UTC_START + timedelta(minutes=15),
        strategy_version_id=uuid4(),
    )
    repository = FakeRepository(row)
    ingestion = SimpleNamespace(
        load_missing=lambda *_args, **_kwargs: (
            events.append("load")
            or SimpleNamespace(
                coverage=SimpleNamespace(
                    valid=True, expected_open_minutes=15, member_minutes=15, gaps=[]
                ),
                failure=None,
                incomplete_minutes=(),
                fetched_ranges=(),
                committed_ranges=(),
                inserted=1,
                reactivated=0,
                unchanged=0,
            )
        ),
        create_snapshot=lambda *_args: (
            events.append("snapshot")
            or SimpleNamespace(
                snapshot=SimpleNamespace(id=uuid4(), fingerprint="a" * 64)
            )
        ),
        derive_m15=lambda *_args: events.append("m15"),
    )
    configuration = SimpleNamespace(
        validate_coverage=lambda *_args, **_kwargs: (
            events.append("validation")
            or SimpleNamespace(
                valid=True, warm_up_required=0, warm_up_available=0, reasons=()
            )
        )
    )
    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(),
        ingestion,
        configuration,
        SimpleNamespace(),
        repository=repository,
    )

    coordinator.run(row.id)

    assert events == ["load", "snapshot", "m15", "validation"]
    assert row.status == "COMPLETED"


def test_durable_load_prefers_v2_acquisition_when_available() -> None:
    events: list[str] = []
    snapshot = SimpleNamespace(
        id=uuid4(),
        snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
        integrity_summary={"gap_count": 1, "analytical_count": 200},
    )
    row = SimpleNamespace(
        id=uuid4(), status="PENDING", load_start=UTC_START,
        load_end=UTC_START + timedelta(minutes=15),
        trading_start=UTC_START, trading_end=UTC_START + timedelta(minutes=15),
        strategy_version_id=uuid4(),
    )
    repository = FakeRepository(row)
    ingestion = SimpleNamespace(
        load_v2=lambda *_args: (
            events.append("v2")
            or SimpleNamespace(snapshot=snapshot)
        ),
        load_missing=lambda *_args, **_kwargs: events.append("legacy"),
    )
    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(), ingestion, SimpleNamespace(), SimpleNamespace(),
        repository=repository,
    )

    coordinator.run(row.id)

    assert events == ["v2"]
    assert row.status == "COMPLETED"


def test_v2_warmup_extends_on_actual_native_count_with_session_closures() -> None:
    starts: list[datetime] = []
    row = SimpleNamespace(
        id=uuid4(), status="PENDING", load_start=UTC_START,
        load_end=UTC_START + timedelta(minutes=15),
        trading_start=UTC_START, trading_end=UTC_START + timedelta(minutes=15),
        strategy_version_id=uuid4(),
    )
    repository = FakeRepository(row)
    counts = iter((100, 200))

    def load_v2(start: datetime, _end: datetime):
        starts.append(start)
        return SimpleNamespace(
            snapshot=SimpleNamespace(
                id=uuid4(), snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
                integrity_summary={"warmup_count": next(counts)},
            )
        )

    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(), SimpleNamespace(load_v2=load_v2),
        SimpleNamespace(), SimpleNamespace(), repository=repository,
    )
    coordinator._warmup_bars = lambda _row: 200

    coordinator.run(row.id)

    assert starts == [UTC_START, UTC_START - timedelta(hours=25)]
    assert row.status == "COMPLETED"
