import ast
import inspect
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

# ruff: noqa: E501
import pytest

import backend.market_data.ingestion as ingestion_module
from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.integrations.oanda.source import FetchDiagnostics, FetchResult
from backend.market_data.freeze03_benchmark import run_fixture_benchmarks
from backend.market_data.ingestion import (
    MarketDataService,
    SnapshotReport,
    _coalesce_expected_ranges,
    _DurationStats,
    _v2_gap_members,
    _V2Telemetry,
)
from backend.persistence.historical_data_load_repository import (
    HistoricalDataLoadRepository,
)
from backend.persistence.market_data_repository import MarketDataRepository

START = datetime(2026, 1, 5, 12, tzinfo=UTC)


def _bar(start: datetime, timeframe: Timeframe, component: PriceComponent) -> Bar:
    from decimal import Decimal

    end = start + (
        timedelta(minutes=15)
        if timeframe is Timeframe.M15
        else timedelta(minutes=1)
    )
    price = Decimal("1.1000")
    return Bar(
        Instrument.EUR_USD,
        timeframe,
        component,
        start,
        end,
        price,
        price,
        price,
        price,
    )


class NativeSource:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.calls: list[tuple[str, datetime, datetime]] = []
        self.fail_after = fail_after

    def _result(self, product: str, start: datetime, end: datetime) -> FetchResult:
        self.calls.append((product, start, end))
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise RuntimeError("fixture interruption")
        if product == "m15":
            bars = (_bar(start, Timeframe.M15, PriceComponent.MID),)
        else:
            bars = tuple(
                _bar(start, Timeframe.M1, component)
                for component in (PriceComponent.BID, PriceComponent.ASK)
            )
        return FetchResult(bars, (), FetchDiagnostics(()))

    def fetch_native_m15(self, start, end):
        return self._result("m15", start, end)

    def fetch_execution_m1(self, start, end):
        return self._result("m1", start, end)


class EmptyRepository:
    def missing_ranges(
        self,
        _session,
        _mapping,
        start,
        end,
        components,
        resolution=Timeframe.M1,
    ):
        return ()

    def current_bars(self, *_args, **_kwargs):
        return ()


class PlannedRepository(EmptyRepository):
    def missing_ranges(
        self, _session, _mapping, start, end, components, resolution=Timeframe.M1
    ):
        if resolution is Timeframe.M15:
            return (SimpleNamespace(start=start, end=end),)
        return (SimpleNamespace(start=start, end=end),)

    def ensure_initial_venue_instrument(self, _session, _venue):
        return SimpleNamespace(id="mapping")


class Session:
    class _Begin:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def begin(self):
        return self._Begin()

    def flush(self):
        pass

    def close(self):
        pass


class PlanningBoundarySession(Session):
    def __init__(self) -> None:
        self.transaction_active = False

    @contextmanager
    def begin(self):
        self.transaction_active = True
        try:
            yield self
        finally:
            self.transaction_active = False


class AtomicSession:
    def __init__(self) -> None:
        self.durable: list[str] = []
        self.pending: list[str] | None = None

    @contextmanager
    def begin(self):
        self.pending = []
        try:
            yield self
        except Exception:
            self.pending = None
            raise
        else:
            self.durable.extend(self.pending or [])
            self.pending = None

    def close(self) -> None:
        pass


class AtomicRepository:
    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at

    def apply_bar_batch(self, session, _mapping, _items):
        assert session.pending is not None
        session.pending.append("canonical_observation")
        if self.fail_at == "canonical_observation":
            raise RuntimeError("interrupted during canonical persistence")
        return SimpleNamespace(inserted=1, reactivated=0, unchanged=0)

    def record_acquisition_window(
        self, session, _mapping, _resolution, _components, _start, _end,
        _outcome, _returned_count=0,
    ):
        assert session.pending is not None
        session.pending.append("acquisition_outcome")
        if self.fail_at == "acquisition_outcome":
            raise RuntimeError("interrupted during acquisition recording")


def test_successful_acquisition_commits_observation_and_window_together() -> None:
    session = AtomicSession()
    service = MarketDataService(
        lambda: session, SimpleNamespace(), repository=AtomicRepository()
    )
    result = SimpleNamespace(bars=())

    applied = service._apply_and_record_outcome(
        "mapping", result, Timeframe.M1,
        (PriceComponent.BID, PriceComponent.ASK),
        (START, START + timedelta(minutes=1)), 0,
    )

    assert applied.inserted == 1
    assert session.durable == ["canonical_observation", "acquisition_outcome"]


@pytest.mark.parametrize("fail_at", ("canonical_observation", "acquisition_outcome"))
def test_interrupted_acquisition_never_commits_a_partial_durable_outcome(
    fail_at: str,
) -> None:
    session = AtomicSession()
    service = MarketDataService(
        lambda: session, SimpleNamespace(), repository=AtomicRepository(fail_at)
    )

    with pytest.raises(RuntimeError, match="interrupted"):
        service._apply_and_record_outcome(
            "mapping", SimpleNamespace(bars=()), Timeframe.M1,
            (PriceComponent.BID, PriceComponent.ASK),
            (START, START + timedelta(minutes=1)), 0,
        )

    assert session.durable == []


def test_v2_requires_both_native_provider_products() -> None:
    source = SimpleNamespace(fetch_native_m15=lambda *_: None)
    service = MarketDataService(lambda: Session(), source, repository=EmptyRepository())
    with pytest.raises(ValueError, match="Alternative A"):
        service.load_v2(START, START + timedelta(minutes=15))


def test_v2_authoritative_reads_do_not_use_full_range_or_compatibility_materialization() -> None:
    source = inspect.getsource(ingestion_module.MarketDataService)
    tree = ast.parse(source)
    coverage = next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_coverage_product"
    )
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "current_bars"
        for node in ast.walk(coverage)
    )
    snapshot = next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "create_snapshot_v2"
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"tuple", "list", "set"}
        for node in ast.walk(snapshot)
    )
    plans = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "plans"
    )
    authoritative = (*ast.walk(snapshot), *ast.walk(plans))
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in {"tuple", "list", "set"})
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "all")
        )
        for node in authoritative
    )
    assert not any(isinstance(node, ast.AugAssign) for node in ast.walk(plans))


def test_v2_repository_streams_core_rows_without_orm_identity_buffer() -> None:
    repository_source = inspect.getsource(
        __import__(
            "backend.persistence.market_data_repository",
            fromlist=["MarketDataRepository"],
        ).MarketDataRepository
    )
    tree = ast.parse(repository_source)
    for name in ("current_bars_stream", "current_bar_rows_stream"):
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        ]
        assert any(node.func.attr == "execute" for node in calls)
        assert not any(node.func.attr == "scalars" for node in calls)
        assert any(
            isinstance(node, ast.keyword)
            and node.arg == "stream_results"
            for node in ast.walk(function)
        )


def test_covered_v2_request_makes_no_provider_calls(monkeypatch) -> None:
    source = NativeSource()
    service = MarketDataService(lambda: Session(), source, repository=EmptyRepository())
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    monkeypatch.setattr(
        service, "create_snapshot_v2", lambda *args, **kwargs: "snapshot"
    )
    assert service.load_v2(START, START + timedelta(minutes=15)) == "snapshot"
    assert source.calls == []


def test_fresh_v2_acquires_native_m15_and_independent_m1_products(monkeypatch) -> None:
    source = NativeSource()
    service = MarketDataService(
        lambda: Session(), source, repository=PlannedRepository()
    )
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    monkeypatch.setattr(
        service,
        "_apply",
        lambda *_args: SimpleNamespace(inserted=1, reactivated=0, unchanged=0),
    )
    monkeypatch.setattr(
        service, "create_snapshot_v2", lambda *args, **kwargs: "snapshot"
    )

    assert service.load_v2(START, START + timedelta(minutes=15)) == "snapshot"
    assert [call[0] for call in source.calls] == ["m15", "m1"]


def test_v2_planning_reports_per_product_totals_before_provider_io(monkeypatch) -> None:
    source = NativeSource()
    reports = []
    calls_at_report = []
    service = MarketDataService(
        lambda: Session(), source, repository=PlannedRepository()
    )
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    monkeypatch.setattr(
        service,
        "_apply",
        lambda *_args: SimpleNamespace(inserted=0, reactivated=0, unchanged=0),
    )
    monkeypatch.setattr(
        service, "create_snapshot_v2", lambda *args, **kwargs: "snapshot"
    )

    def progress(report):
        reports.append(report)
        calls_at_report.append(len(source.calls))

    service.load_v2(START, START + timedelta(minutes=15), progress=progress)

    planning = reports[0].to_payload()
    assert planning["phase"] == "PLANNING"
    assert planning["completed_units"] == {"m15": 0, "m1": 0}
    assert planning["total_units"] == {"m15": 1, "m1": 1}
    assert set(planning["products"]) == {"m15", "m1"}
    assert calls_at_report[0] == 0


def test_v2_provider_fetch_runs_after_planning_transaction_closes(monkeypatch) -> None:
    session = PlanningBoundarySession()

    class CoveragePlannedRepository(PlannedRepository):
        def acquired_windows(self, *_args):
            return ()

    class TransactionAwareSource(NativeSource):
        def _result(self, product, start, end):
            assert not session.transaction_active
            return super()._result(product, start, end)

    source = TransactionAwareSource()
    service = MarketDataService(
        lambda: session, source, repository=CoveragePlannedRepository()
    )
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    monkeypatch.setattr(
        service,
        "_apply",
        lambda *_args: SimpleNamespace(inserted=0, reactivated=0, unchanged=0),
    )
    monkeypatch.setattr(
        service, "create_snapshot_v2", lambda *args, **kwargs: "snapshot"
    )

    assert service.load_v2(START, START + timedelta(minutes=15)) == "snapshot"
    assert [call[0] for call in source.calls] == ["m15", "m1"]


def test_v2_finalizing_progress_is_emitted_and_durable(monkeypatch) -> None:
    source = NativeSource()
    end = START + timedelta(minutes=15)
    row = SimpleNamespace(
        id="request",
        status="RUNNING",
        coverage_summary=None,
        fetched_ranges=[],
        committed_ranges=[],
        inserted=0,
        reactivated=0,
        unchanged=0,
        incomplete_minute_count=0,
        updated_at=START,
    )

    class ProgressSession:
        def scalar(self, _statement):
            return row

        def flush(self):
            pass

    progress_repository = HistoricalDataLoadRepository()
    progress_session = ProgressSession()
    durable_phases: list[str] = []

    def progress(report):
        assert progress_repository.record_progress(
            progress_session,
            row.id,
            progress_payload=report.to_payload(),
            telemetry=report.telemetry,
        )
        durable_phases.append(row.coverage_summary["progress"]["phase"])

    service = MarketDataService(
        lambda: Session(), source, repository=PlannedRepository()
    )
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    monkeypatch.setattr(
        service,
        "_apply",
        lambda *_args: SimpleNamespace(inserted=0, reactivated=0, unchanged=0),
    )
    monkeypatch.setattr(
        service,
        "create_snapshot_v2",
        lambda *_args, **_kwargs: SnapshotReport(
            START,
            end,
            SimpleNamespace(),
            SimpleNamespace(id="snapshot"),
        ),
    )

    service.load_v2(START, end, progress=progress)

    assert durable_phases == [
        "PLANNING",
        "ACQUIRING",
        "ACQUIRING",
        "VALIDATING",
        "SNAPSHOT_MEMBERSHIP",
        "FINGERPRINTING",
        "FINALIZING",
        "COMPLETED",
    ]


def test_provider_range_coalescing_bridges_closure_and_splits_only_at_bound() -> None:
    closure_start = datetime(2026, 1, 9, 21, 59, tzinfo=UTC)
    closure_end = datetime(2026, 1, 11, 22, 5, tzinfo=UTC)
    assert list(
        _coalesce_expected_ranges(
            (SimpleNamespace(start=closure_start, end=closure_end),),
            step=timedelta(minutes=1),
        )
    ) == []

    start = closure_start - timedelta(minutes=1)
    assert list(
        _coalesce_expected_ranges(
            (SimpleNamespace(start=start, end=closure_end + timedelta(minutes=1)),),
            step=timedelta(minutes=1),
        )
    ) == [(start, closure_end + timedelta(minutes=1))]

    # The half-open closure end is excluded; the minute beginning at
    # closure_end is the first expected observation and must be included.
    assert list(
        _coalesce_expected_ranges(
            (SimpleNamespace(start=closure_start, end=closure_end + timedelta(minutes=1)),),
            step=timedelta(minutes=1),
        )
    ) == [(closure_start, closure_end + timedelta(minutes=1))]

    end = start + timedelta(minutes=4_001)
    assert list(
        _coalesce_expected_ranges(
            (SimpleNamespace(start=start, end=end),),
            step=timedelta(minutes=1),
        )
    ) == [
        (start, start + timedelta(minutes=4_000)),
        (start + timedelta(minutes=4_000), end),
    ]

    m15_start = datetime(2026, 1, 5, tzinfo=UTC)
    m15_end = m15_start + timedelta(minutes=60_001)
    assert list(
        _coalesce_expected_ranges(
            (SimpleNamespace(start=m15_start, end=m15_end),),
            step=timedelta(minutes=15),
        )
    ) == [
        (m15_start, m15_start + timedelta(minutes=60_000)),
        (m15_start + timedelta(minutes=60_000), m15_end),
    ]


def test_missing_range_planning_streams_large_disjoint_ranges() -> None:
    consumed_rows = 0

    class LargeDisjointRepository(MarketDataRepository):
        def current_bar_rows_stream(
            self, _session, _mapping, start, _end, _components, _resolution
        ):
            nonlocal consumed_rows
            for minute in range(20_000):
                if minute % 2 == 0:
                    moment = start + timedelta(minutes=minute)
                    for component in (PriceComponent.BID, PriceComponent.ASK):
                        consumed_rows += 1
                        yield SimpleNamespace(
                            start_time=moment, price_component=component.value
                        )

    repository = LargeDisjointRepository()
    planned = _coalesce_expected_ranges(
        repository.missing_ranges(
            None,
            "mapping",
            START,
            START + timedelta(minutes=20_000),
            (PriceComponent.BID, PriceComponent.ASK),
        )
    )

    first = next(planned)
    assert first == (START + timedelta(minutes=1), START + timedelta(minutes=2))
    assert consumed_rows < 100


def test_duration_histogram_is_bounded_and_uses_nearest_rank_p95() -> None:
    stats = _DurationStats()
    for milliseconds in (0, 1, 2, 3, 65_537):
        stats.add(milliseconds / 1000)

    report = stats.report()
    assert report["count"] == 5
    assert report["elapsed_ms"] == 65_543
    assert report["average_ms"] == 13_108
    assert report["p95_ms"] == 65_537
    assert len(stats.buckets) == 19


def test_v2_progress_rejects_unbounded_or_redacted_fields() -> None:
    from backend.persistence.historical_data_load_repository import (
        _validate_progress_payload,
    )

    payload = {
        "schema": "ATLAS_HISTORICAL_PROGRESS_V1",
        "phase": "PLANNING",
        "unit": "provider_request",
        "completed_units": {"m15": 0, "m1": 0},
        "total_units": {"m15": 1, "m1": 1},
        "products": {
            "m15": {"expected_requests": 1, "completed_requests": 0},
            "m1": {"expected_requests": 1, "completed_requests": 0},
        },
    }
    _validate_progress_payload(payload)
    with pytest.raises(ValueError):
        _validate_progress_payload(
            {**payload, "fetched_ranges": ["window"] * 10_000}
        )


def test_v2_incomplete_provider_observation_fails_closed(monkeypatch) -> None:
    class IncompleteSource(NativeSource):
        def fetch_native_m15(self, start, end):
            self.calls.append(("m15", start, end))
            return FetchResult(
                (), (SimpleNamespace(start_time=start),), FetchDiagnostics(())
            )

    source = IncompleteSource()
    service = MarketDataService(
        lambda: Session(), source, repository=PlannedRepository()
    )
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    with pytest.raises(ValueError, match="incomplete"):
        service.load_v2(START, START + timedelta(minutes=15))
    assert [call[0] for call in source.calls] == ["m15"]


@pytest.mark.parametrize("sparse_m15", (False, True))
def test_successful_empty_or_sparse_m15_window_is_reused_on_repeat(
    sparse_m15: bool, monkeypatch
) -> None:
    source = NativeSource()

    def result(product, start, end):
        source.calls.append((product, start, end))
        bars = (
            (_bar(start, Timeframe.M15, PriceComponent.MID),)
            if product == "m15" and sparse_m15
            else ()
        )
        return FetchResult(bars, (), FetchDiagnostics(()))

    source._result = result  # type: ignore[method-assign]

    class WindowRepository(PlannedRepository):
        def __init__(self):
            self.windows = set()
        def record_acquisition_window(self, _session, _mapping, resolution, components, start, end, outcome, returned_count=0):
            self.windows.add((resolution, start, end, outcome))
        def acquired_windows(self, _session, _mapping, resolution, components, start, end):
            return tuple(SimpleNamespace(start_time=s, end_time=e, outcome=o, request_identity="x")
                         for r, s, e, o in self.windows if r is resolution)
    repo = WindowRepository()
    service = MarketDataService(lambda: Session(), source, repository=repo)
    monkeypatch.setattr(service, "_mapping_id", lambda: "mapping")
    monkeypatch.setattr(service, "_apply", lambda *_args: SimpleNamespace(inserted=0, reactivated=0, unchanged=0))
    monkeypatch.setattr(service, "create_snapshot_v2", lambda *args, **kwargs: "snapshot")
    end = START + timedelta(minutes=30)
    service.load_v2(START, end)
    service.load_v2(START, end)
    assert [call[0] for call in source.calls] == ["m15", "m1"]


def test_acquisition_reuse_subtracts_smaller_request_inside_larger_window() -> None:
    from backend.market_data.ingestion import _subtract_acquisition_windows

    missing = (SimpleNamespace(start=START, end=START + timedelta(minutes=30), components=(PriceComponent.BID, PriceComponent.ASK)),)
    acquired = (SimpleNamespace(start_time=START - timedelta(minutes=15), end_time=START + timedelta(minutes=45)),)
    assert _subtract_acquisition_windows(missing, acquired) == ()


def test_benchmark_harness_reports_all_required_recovery_scenarios() -> None:
    results = {item.scenario: item for item in run_fixture_benchmarks()}
    assert set(results) == {
        "fresh_one_month",
        "fresh_one_year",
        "repeat_covered_one_year",
        "interrupted_resumed_one_year",
    }
    assert results["repeat_covered_one_year"].m15_calls == 0
    assert results["repeat_covered_one_year"].m1_calls == 0
    assert results["repeat_covered_one_year"].reused > 0
    assert results["interrupted_resumed_one_year"].repeat_calls > 0
    assert results["repeat_covered_one_year"].fingerprint == results["fresh_one_year"].fingerprint
    assert results["interrupted_resumed_one_year"].fingerprint == results["fresh_one_year"].fingerprint
    # The OANDA M1 bound is 4,000 minutes; BID + ASK produces two rows/minute.
    assert results["fresh_one_year"].max_batch_size <= 8000
    assert results["fresh_one_year"].max_progress_payload_bytes < 4096
    assert results["fresh_one_year"].peak_rss_bytes > 0


def test_v2_fingerprint_gap_stream_matches_snapshot_gap_contract() -> None:
    start = datetime(2026, 1, 5, 12, tzinfo=UTC)
    end = start + timedelta(minutes=60)
    analytical = (_bar(start, Timeframe.M15, PriceComponent.MID),
                  _bar(start + timedelta(minutes=60), Timeframe.M15, PriceComponent.MID))

    gaps = tuple(_v2_gap_members(start, end, iter(analytical)))

    assert [(item["start_time"], item["end_time"]) for item in gaps] == [
        (start + timedelta(minutes=15), start + timedelta(minutes=30)),
        (start + timedelta(minutes=30), start + timedelta(minutes=45)),
        (start + timedelta(minutes=45), start + timedelta(minutes=60)),
    ]
    assert all(item["policy_version"] == "ATLAS_HISTORICAL_GAP_POLICY_V1" for item in gaps)


def test_v2_terminal_metrics_count_hashed_gap_records() -> None:
    telemetry = _V2Telemetry()
    telemetry.analytical_rows = 12
    telemetry.execution_rows = 24
    telemetry.gap_rows = 3
    telemetry.membership_rows = 39

    report = telemetry.report(
        expected={"m15": 0, "m1": 0},
        completed={"m15": 0, "m1": 0},
        planning_ms=0,
        validation_ms=0,
        snapshot_ms=0,
        fingerprint_ms=0,
    )

    assert report["timing"]["snapshot_membership"] == {
        "elapsed_ms": 0,
        "rows": 39,
        "analytical_rows": 12,
        "execution_rows": 24,
        "gap_rows": 3,
        "batches": 0,
    }
    assert report["timing"]["fingerprinting"] == {
        "elapsed_ms": 0,
        "records_hashed": 39,
        "analytical_rows": 12,
        "execution_rows": 24,
        "gap_rows": 3,
    }
