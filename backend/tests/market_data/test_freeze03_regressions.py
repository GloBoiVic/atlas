from datetime import UTC, datetime, timedelta
import ast
import inspect
from types import SimpleNamespace

# ruff: noqa: E501
import pytest

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.integrations.oanda.source import FetchDiagnostics, FetchResult
from backend.market_data.freeze03_benchmark import run_fixture_benchmarks
from backend.market_data.ingestion import MarketDataService
import backend.market_data.ingestion as ingestion_module

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


def test_successful_empty_window_is_acquisition_coverage_not_continuity(monkeypatch) -> None:
    source = NativeSource()
    source._result = lambda product, start, end: (  # type: ignore[method-assign]
        source.calls.append((product, start, end)) or FetchResult((), (), FetchDiagnostics(()))
    )
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
    service.load_v2(START, START + timedelta(minutes=15))
    first_calls = len(source.calls)
    service.load_v2(START, START + timedelta(minutes=15))
    assert len(source.calls) == first_calls + 1
    assert [call[0] for call in source.calls].count("m1") == 1


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
    assert results["fresh_one_year"].max_batch_size <= 4000
    assert results["fresh_one_year"].max_progress_payload_bytes < 4096
    assert results["fresh_one_year"].peak_rss_bytes > 0
