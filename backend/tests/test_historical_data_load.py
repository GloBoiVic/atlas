import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.api.historical_data import _active_conflict_details, _payload
from backend.market_data.historical_load import (
    HistoricalDataLoadCoordinator,
    _warmup_plan,
)
from backend.market_data.ingestion import classify_failure
from backend.market_data.session_calendar import required_warmup_range
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


def test_warmup_plan_has_no_window_or_elapsed_time_ceiling() -> None:
    plan = _warmup_plan(
        UTC_START,
        UTC_START + timedelta(minutes=15),
        UTC_START - timedelta(days=365),
        99,
        40,
        100,
    )
    assert plan.outcome == "EXTEND"
    assert plan.load_start == UTC_START - timedelta(days=365, hours=25)


def test_warmup_readiness_uses_observed_native_m15_count() -> None:
    plan = _warmup_plan(
        UTC_START,
        UTC_START + timedelta(minutes=15),
        UTC_START - timedelta(days=365),
        100,
        400,
        100,
    )
    assert plan.outcome == "READY"


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


def test_prepare_does_not_invoke_legacy_shared_m1_planner(monkeypatch) -> None:
    ingestion = SimpleNamespace(
        plan_missing=lambda *_args: pytest.fail("legacy planner was invoked")
    )
    strategies = SimpleNamespace(get_version=lambda *_args: object())
    registry = SimpleNamespace(implementation_for_version=lambda _version: object())
    monkeypatch.setattr(
        "backend.market_data.historical_load.version_to_domain",
        lambda _row: SimpleNamespace(id="version", warm_up_bars=100),
    )
    coordinator = HistoricalDataLoadCoordinator(
        lambda: None, ingestion, SimpleNamespace(), registry, strategies=strategies
    )
    load_start, load_end = coordinator.prepare(
        SimpleNamespace(),
        strategy_version_id=uuid4(),
        trading_start=UTC_START,
        trading_end=UTC_START + timedelta(minutes=15),
    )
    assert load_start == required_warmup_range(
        UTC_START, UTC_START + timedelta(minutes=15), 100
    )[0]
    assert load_end == UTC_START + timedelta(minutes=15)


def test_prepare_uses_eligible_completed_m15_warmup_across_market_closure() -> None:
    version_id = uuid4()
    strategies = SimpleNamespace(
        get_version=lambda *_args: SimpleNamespace(
            id=version_id, warm_up_bars=100, primary_timeframe="15m",
            strategy=SimpleNamespace(strategy_key="ema_sweep_engulfing"),
            version_number=2, source_fingerprint="f" * 64,
            implementation_key="ema_sweep_engulfing.v2", parameter_schema=[],
            required_historical_context_bars=100, state_schema_version=2,
            created_at=UTC_START,
        )
    )
    coordinator = HistoricalDataLoadCoordinator(
        lambda: None,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(implementation_for_version=lambda _version: object()),
        strategies=strategies,
    )

    load_start, load_end = coordinator.prepare(
        SimpleNamespace(),
        strategy_version_id=version_id,
        trading_start=UTC_START,
        trading_end=UTC_START + timedelta(minutes=15),
    )

    assert (load_start, load_end) == required_warmup_range(
        UTC_START, UTC_START + timedelta(minutes=15), 100
    )
    assert load_start == datetime(2026, 1, 2, 14, tzinfo=UTC)


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


def test_historical_status_metadata_exposes_independent_native_products() -> None:
    row = SimpleNamespace(
        id=uuid4(), created_at=UTC_START, status="PENDING",
        fetched_ranges=[], committed_ranges=[], inserted=0, reactivated=0,
        unchanged=0, incomplete_minute_count=0, coverage_summary=None,
        snapshot_id=None, experiment_validation=None, failure_category=None,
        failure_code=None, failure_detail=None, trading_start=UTC_START,
        trading_end=UTC_START + timedelta(minutes=15), load_start=UTC_START,
        load_end=UTC_START + timedelta(minutes=15), started_at=None,
        finished_at=None,
    )
    products = _payload(row)["source"]["products"]
    assert products == [
        {"product": "analytical", "resolution": "M15", "components": ["MID"]},
        {"product": "execution", "resolution": "M1", "components": ["BID", "ASK"]},
    ]


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


def test_explicit_resume_reopens_failed_request_without_erasing_coverage() -> None:
    row = SimpleNamespace(
        id=uuid4(), status="FAILED", started_at=UTC_START,
        finished_at=UTC_START + timedelta(minutes=1),
        failure_category="MARKET_DATA", failure_code="OANDA_REQUEST_FAILED",
        failure_detail="The provider request failed.", updated_at=UTC_START,
        coverage_summary={
            "progress": {"products": {"analytical": {"completed_units": 3}}}
        },
    )

    class ResumeSession:
        def scalar(self, _statement):
            return row

        def flush(self):
            pass

    assert HistoricalDataLoadRepository().resume(ResumeSession(), row.id)
    assert row.status == "RUNNING"
    assert row.finished_at is None
    assert row.failure_code is None
    assert (
        row.coverage_summary["progress"]["products"]["analytical"]["completed_units"]
        == 3
    )


def test_product_progress_is_additive_and_records_only_committed_window() -> None:
    row = SimpleNamespace(
        id=uuid4(), status="RUNNING", coverage_summary=None,
        fetched_ranges=[], committed_ranges=[], inserted=0, reactivated=0,
        unchanged=0, incomplete_minute_count=0, updated_at=UTC_START,
    )

    class ProgressSession:
        def scalar(self, _statement):
            return row

        def flush(self):
            pass

    repo = HistoricalDataLoadRepository()
    window = {"start": "2026-01-05T15:00:00Z", "end": "2026-01-05T15:15:00Z"}
    assert repo.record_progress(
        ProgressSession(),
        row.id,
        committed_ranges=((UTC_START, UTC_START + timedelta(minutes=15)),),
        completed_units=1, total_units=100, product="analytical", window=window,
    )
    assert (
        row.coverage_summary["progress"]["products"]["analytical"]
        ["last_committed_window"]
        == window
    )


def test_v2_progress_is_durable_per_product_before_acquisition() -> None:
    row = SimpleNamespace(
        id=uuid4(), status="RUNNING", coverage_summary=None,
        fetched_ranges=[], committed_ranges=[], inserted=0, reactivated=0,
        unchanged=0, incomplete_minute_count=0, updated_at=UTC_START,
    )

    class ProgressSession:
        def scalar(self, _statement):
            return row

        def flush(self):
            pass

    payload = {
        "schema": "ATLAS_HISTORICAL_PROGRESS_V1",
        "phase": "PLANNING",
        "unit": "provider_request",
        "completed_units": {"m15": 0, "m1": 0},
        "total_units": {"m15": 8, "m1": 40},
        "products": {
            "m15": {
                "expected_requests": 8,
                "completed_requests": 0,
                "already_covered_window_count": 0,
                "uncovered_span_count": 1,
                "planning_elapsed_ms": 2,
            },
            "m1": {
                "expected_requests": 40,
                "completed_requests": 0,
                "already_covered_window_count": 0,
                "uncovered_span_count": 1,
                "planning_elapsed_ms": 2,
            },
        },
    }

    assert HistoricalDataLoadRepository().record_progress(
        ProgressSession(), row.id, progress_payload=payload
    )
    progress = row.coverage_summary["progress"]
    assert progress["plan_generation"] == 1
    assert progress["completed_units"] == {"m15": 0, "m1": 0}
    assert progress["total_units"] == {"m15": 8, "m1": 40}


class FakeSession:
    @contextmanager
    def begin(self):
        yield self

    def close(self) -> None:
        pass


class FakeStrategies:
    def get_version(self, _session, version_id):
        return SimpleNamespace(
            id=version_id,
            strategy=SimpleNamespace(strategy_key="ema_sweep_engulfing"),
            version_number=2,
            source_fingerprint="f" * 64,
            implementation_key="ema_sweep_engulfing.v2",
            parameter_schema=[], primary_timeframe="15m",
            required_historical_context_bars=100,
            state_schema_version=2, created_at=UTC_START,
        )


class FakeRegistry:
    def implementation_for_version(self, _version):
        return object()


class FakeRepository:
    def __init__(self, row, *, completion_result=True):
        self.row = row
        self.events: list[str] = []
        self.completed_snapshot_id = None
        self.completion_result = completion_result

    def claim(self, _session, _request_id):
        self.events.append("claim")
        self.row.status = "RUNNING"
        return self.row

    def record_progress(self, _session, *_args, **_kwargs):
        self.events.append("progress")

    def complete(self, _session, *_args, **kwargs):
        self.events.append("complete")
        self.completed_snapshot_id = kwargs["snapshot_id"]
        if self.completion_result:
            self.row.status = "COMPLETED"
        return self.completion_result

    def fail_if_active(self, _session, *_args, **kwargs):
        self.events.append("fail")
        self.row.status = "FAILED"
        self.row.failure_category = kwargs["category"]
        self.row.failure_code = kwargs["code"]
        self.row.failure_detail = kwargs["detail"]


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
        FakeRegistry(),
        repository=repository,
        strategies=FakeStrategies(),
    )

    @contextmanager
    def fake_scope(_factory):
        yield FakeSession()

    monkeypatch.setattr("backend.market_data.historical_load.session_scope", fake_scope)
    coordinator.run(row.id)
    assert row.status == "FAILED"


def test_success_order_is_load_snapshot_m15_then_validation() -> None:
    events: list[str] = []
    snapshot = SimpleNamespace(
        id=uuid4(),
        snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
        integrity_summary={"warmup_count": 100, "gap_count": 0},
    )
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
        load_v2=lambda *_args, **_kwargs: (
            events.append("load")
            or SimpleNamespace(
                snapshot=SimpleNamespace(
                    id=snapshot.id,
                    snapshot_schema=snapshot.snapshot_schema,
                    integrity_summary=snapshot.integrity_summary,
                ),
            )
        ),
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
        FakeRegistry(),
        repository=repository,
        strategies=FakeStrategies(),
    )

    coordinator.run(row.id)

    assert events == ["load"]
    assert row.status == "COMPLETED"
    assert repository.completed_snapshot_id == snapshot.id


def test_failed_completion_transition_becomes_inspectable_terminal_failure() -> None:
    snapshot = SimpleNamespace(
        id=uuid4(),
        snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
        integrity_summary={"warmup_count": 100, "gap_count": 0},
    )
    row = SimpleNamespace(
        id=uuid4(),
        status="PENDING",
        load_start=UTC_START,
        load_end=UTC_START + timedelta(minutes=15),
        trading_start=UTC_START,
        trading_end=UTC_START + timedelta(minutes=15),
        strategy_version_id=uuid4(),
        snapshot_id=None,
        failure_category=None,
        failure_code=None,
        failure_detail=None,
    )
    repository = FakeRepository(row, completion_result=False)
    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(),
        SimpleNamespace(
            load_v2=lambda *_args, **_kwargs: SimpleNamespace(snapshot=snapshot)
        ),
        SimpleNamespace(),
        FakeRegistry(),
        repository=repository,
        strategies=FakeStrategies(),
    )

    coordinator.run(row.id)

    assert repository.events == ["claim", "complete", "fail"]
    assert row.status == "FAILED"
    assert row.failure_category == "PERSISTENCE"
    assert row.failure_code == "COMPLETION_TRANSITION_FAILED"
    assert "no snapshot was linked" in row.failure_detail
    assert row.snapshot_id is None


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
    )
    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(), ingestion, SimpleNamespace(), FakeRegistry(),
        repository=repository,
        strategies=FakeStrategies(),
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
    counts = iter((99, 200))

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
        SimpleNamespace(), FakeRegistry(), repository=repository,
        strategies=FakeStrategies(),
    )
    coordinator.run(row.id)

    assert starts == [UTC_START, UTC_START - timedelta(hours=25)]
    assert row.status == "COMPLETED"


def test_v2_warmup_extension_uses_missing_only_union_seam() -> None:
    events: list[tuple[str, int]] = []
    row = SimpleNamespace(
        id=uuid4(), status="PENDING", load_start=UTC_START,
        load_end=UTC_START + timedelta(minutes=15),
        trading_start=UTC_START, trading_end=UTC_START + timedelta(minutes=15),
        strategy_version_id=uuid4(),
    )
    repository = FakeRepository(row)
    first = SimpleNamespace(
        id=uuid4(), snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
        integrity_summary={"warmup_count": 99},
    )
    extended = SimpleNamespace(
        id=uuid4(), snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
        integrity_summary={"warmup_count": 100},
    )

    snapshots = iter((first, extended))

    def load_v2(*_args, **_kwargs):
        events.append(("full", 1))
        return SimpleNamespace(snapshot=next(snapshots))

    coordinator = HistoricalDataLoadCoordinator(
        lambda: FakeSession(),
        SimpleNamespace(
            load_v2=load_v2,
            load_v2_incremental=lambda **_: pytest.fail(
                "legacy incremental path invoked"
            ),
        ),
        SimpleNamespace(), FakeRegistry(), repository=repository,
        strategies=FakeStrategies(),
    )
    coordinator.run(row.id)

    assert events == [("full", 1), ("full", 1)]
    assert row.status == "COMPLETED"
