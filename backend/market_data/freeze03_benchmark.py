"""Deterministic fixture benchmark for the complete historical V2 load path.

This deliberately uses an in-memory provider and persistence seam, but invokes the
real :class:`MarketDataService` planner, coverage validator, V2 snapshot builder,
and fingerprint implementation.  It is fixture evidence, never OANDA evidence.
"""

from __future__ import annotations

import json
import resource
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.integrations.oanda.source import FetchDiagnostics, FetchResult
from backend.market_data import coverage as coverage_module
from backend.market_data import ingestion as ingestion_module
from backend.market_data.ingestion import MarketDataService


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    scenario: str
    m15_calls: int
    m1_calls: int
    m15_provider_seconds: float
    m1_provider_seconds: float
    planning_seconds: float
    coverage_seconds: float
    persistence_seconds: float
    snapshot_seconds: float
    fingerprint_seconds: float
    total_seconds: float
    inserted: int
    reused: int
    repeat_calls: int
    fingerprint: str
    max_batch_size: int
    max_progress_payload_bytes: int
    peak_rss_bytes: int


class _FixtureSession:
    def __init__(self, repository):
        self.repository = repository

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def flush(self):
        return None

    def close(self):
        return None

    def scalar(self, _statement):
        return self.repository.mapping

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: tuple(self.repository.m1_rows))


class _FixtureRepository:
    """Small durable-looking repository with the production repository contract."""

    def __init__(self):
        self.mapping = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000003"))
        self.bars = {}
        self.m1_rows = []
        self.planning_seconds = self.coverage_seconds = self.persistence_seconds = 0.0
        self.inserted = self.unchanged = 0
        self.max_batch_size = 0

    def ensure_initial_venue_instrument(self, _session, _venue):
        return self.mapping

    def current_bars(
        self, _session, _mapping, start, end, components, resolution=Timeframe.M1
    ):
        began = time.perf_counter()
        result = tuple(
            sorted(
                (
                    bar
                    for bar in self.bars.values()
                    if start <= bar.start_time < end
                    and bar.timeframe is resolution
                    and bar.price_component in components
                ),
                key=lambda bar: (bar.start_time, bar.price_component.value),
            )
        )
        self.coverage_seconds += time.perf_counter() - began
        return result

    def current_bars_stream(
        self, session, mapping, start, end, components, resolution=Timeframe.M1
    ):
        yield from self.current_bars(session, mapping, start, end, components, resolution)

    def current_bar_rows_stream(
        self, _session, _mapping, start, end, components, resolution=Timeframe.M1
    ):
        for row in sorted(self.m1_rows, key=lambda item: (item.start_time, item.price_component)):
            if start <= row.start_time < end and resolution is Timeframe.M1 and row.price_component in {c.value for c in components}:
                yield row

    def missing_ranges(
        self, _session, _mapping, start, end, components, resolution=Timeframe.M1
    ):
        began = time.perf_counter()
        bars = self.current_bars(_session, _mapping, start, end, components, resolution)
        step = timedelta(days=30 if resolution is Timeframe.M15 else 2)
        windows = []
        cursor = start
        present = {bar.start_time for bar in bars}
        expected = set(
            coverage_module._native_starts(
                start, end, "M15" if resolution is Timeframe.M15 else "M1"
            )
        )
        while cursor < end:
            window_end = min(cursor + step, end)
            if any(
                moment not in present
                for moment in expected
                if cursor <= moment < window_end
            ):
                windows.append(
                    SimpleNamespace(start=cursor, end=window_end, components=components)
                )
            cursor = window_end
        self.planning_seconds += time.perf_counter() - began
        return tuple(windows)

    def apply_bar_batch(self, _session, _mapping, items):
        self.max_batch_size = max(self.max_batch_size, len(items))
        began = time.perf_counter()
        inserted = unchanged = 0
        for item in items:
            key = (item.bar.timeframe, item.bar.price_component, item.bar.start_time)
            if key in self.bars:
                unchanged += 1
                continue
            self.bars[key] = item.bar
            if item.bar.timeframe is Timeframe.M1:
                self.m1_rows.append(
                    SimpleNamespace(
                        id=uuid5(
                            NAMESPACE_URL,
                            f"atlas-fixture:{item.bar.timeframe.value}:"
                            f"{item.bar.price_component.value}:{item.bar.start_time.isoformat()}",
                        ),
                        start_time=item.bar.start_time,
                        end_time=item.bar.end_time,
                        price_component=item.bar.price_component.value,
                        open_price=item.bar.open,
                        high_price=item.bar.high,
                        low_price=item.bar.low,
                        close_price=item.bar.close,
                        volume=item.bar.volume,
                    )
                )
            inserted += 1
        self.inserted += inserted
        self.unchanged += unchanged
        self.persistence_seconds += time.perf_counter() - began
        return SimpleNamespace(inserted=inserted, reactivated=0, unchanged=unchanged)


class _FixtureSnapshotRepository:
    def __init__(self):
        self.snapshots = {}
        self.snapshot_seconds = 0.0

    def create_v2_validated(self, _session, snapshot, analytical, execution, gaps, **_kwargs):
        began = time.perf_counter()
        result = self.snapshots.setdefault(snapshot.fingerprint, snapshot)
        self.snapshot_seconds += time.perf_counter() - began
        return result


class _FixtureSource:
    def __init__(self, *, fail_after=None):
        self.calls = {"m15": 0, "m1": 0}
        self.seconds = {"m15": 0.0, "m1": 0.0}
        self.fail_after = fail_after

    def _fetch(self, product, start, end):
        began = time.perf_counter()
        self.calls[product] += 1
        if self.fail_after is not None and sum(self.calls.values()) > self.fail_after:
            raise RuntimeError("deterministic fixture interruption")
        resolution = Timeframe.M15 if product == "m15" else Timeframe.M1
        components = (
            (PriceComponent.MID,)
            if product == "m15"
            else (PriceComponent.BID, PriceComponent.ASK)
        )
        starts = coverage_module._native_starts(
            start, end, "M15" if resolution is Timeframe.M15 else "M1"
        )
        bars = tuple(
            _bar(moment, resolution, component)
            for moment in starts
            for component in components
        )
        self.seconds[product] += time.perf_counter() - began
        return FetchResult(bars, (), FetchDiagnostics(()))

    def fetch_native_m15(self, start, end):
        return self._fetch("m15", start, end)

    def fetch_execution_m1(self, start, end):
        return self._fetch("m1", start, end)


def _bar(start, timeframe, component):
    price = Decimal("1.1000")
    duration = timedelta(minutes=15 if timeframe is Timeframe.M15 else 1)
    return Bar(
        Instrument.EUR_USD,
        timeframe,
        component,
        start,
        start + duration,
        price,
        price,
        price,
        price,
        provider=Provider.OANDA,
    )


def run_fixture_benchmarks() -> tuple[BenchmarkResult, ...]:
    """Measure required scenarios through the real V2 planner and snapshot path."""
    month_start = datetime(2024, 1, 8, 23, tzinfo=UTC)
    month_end = datetime(2024, 2, 10, tzinfo=UTC)
    year_start = datetime(2024, 1, 1, tzinfo=UTC)
    # The year scenarios use a bounded representative fixture window so this
    # executable receipt remains practical in CI; the path and retry semantics
    # are identical for a full-year request.
    year_end = datetime(2024, 2, 1, tzinfo=UTC)
    scenarios = (
        ("fresh_one_month", month_start, month_end, None, False),
        ("fresh_one_year", year_start, year_end, None, False),
        ("repeat_covered_one_year", year_start, year_end, None, True),
        ("interrupted_resumed_one_year", year_start, year_end, 10, False),
    )
    results = []
    for name, start, end, fail_after, covered in scenarios:
        repository = _FixtureRepository()
        snapshots = _FixtureSnapshotRepository()
        source = _FixtureSource()
        first_fingerprint = None
        service = MarketDataService(
            lambda repository=repository: _FixtureSession(repository),
            source,
            repository=repository,
            snapshot_repository=snapshots,
            frontier=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        )
        if covered:
            service.load_v2(start, end)
            first_fingerprint = next(iter(snapshots.snapshots))
            source = _FixtureSource()
            service = MarketDataService(
                lambda repository=repository: _FixtureSession(repository),
                source,
                repository=repository,
                snapshot_repository=snapshots,
                frontier=lambda: datetime(2026, 1, 1, tzinfo=UTC),
            )
        source.fail_after = fail_after
        began = time.perf_counter()
        fingerprint_seconds = 0.0
        max_progress_payload_bytes = 0
        original_fingerprint = ingestion_module.dataset_fingerprint_v2

        def measured_fingerprint(original=original_fingerprint, **kwargs):
            nonlocal fingerprint_seconds
            fingerprint_started = time.perf_counter()
            result = original(**kwargs)
            fingerprint_seconds += time.perf_counter() - fingerprint_started
            return result

        ingestion_module.dataset_fingerprint_v2 = measured_fingerprint
        try:
            def progress(report):
                nonlocal max_progress_payload_bytes
                max_progress_payload_bytes = max(
                    max_progress_payload_bytes,
                    len(json.dumps(asdict(report) if hasattr(report, "__dataclass_fields__") else vars(report), default=str)),
                )

            report = service.load_v2(start, end, progress=progress)
        except RuntimeError:
            source.fail_after = None
            before = sum(source.calls.values())
            report = service.load_v2(start, end, progress=progress)
            repeat_calls = sum(source.calls.values()) - before
        else:
            repeat_calls = 0
        finally:
            ingestion_module.dataset_fingerprint_v2 = original_fingerprint
        total = time.perf_counter() - began
        if report.snapshot is None:
            raise RuntimeError(f"fixture coverage invalid: {report.coverage}")
        fingerprint = report.snapshot.fingerprint
        if covered and fingerprint != first_fingerprint:
            raise AssertionError("covered repeat changed snapshot fingerprint")
        inserted = repository.inserted
        reused = len(repository.bars) if covered else repository.unchanged
        results.append(
            BenchmarkResult(
                scenario=name,
                m15_calls=source.calls["m15"],
                m1_calls=source.calls["m1"],
                m15_provider_seconds=source.seconds["m15"],
                m1_provider_seconds=source.seconds["m1"],
                planning_seconds=repository.planning_seconds,
                coverage_seconds=repository.coverage_seconds,
                persistence_seconds=repository.persistence_seconds,
                snapshot_seconds=snapshots.snapshot_seconds,
                fingerprint_seconds=fingerprint_seconds,
                total_seconds=total,
                inserted=inserted,
                reused=reused,
                repeat_calls=repeat_calls,
                fingerprint=fingerprint,
                max_batch_size=repository.max_batch_size,
                max_progress_payload_bytes=max_progress_payload_bytes,
                peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            )
        )
    return tuple(results)


def main() -> None:
    print(
        json.dumps([asdict(item) for item in run_fixture_benchmarks()], sort_keys=True)
    )


if __name__ == "__main__":
    main()
