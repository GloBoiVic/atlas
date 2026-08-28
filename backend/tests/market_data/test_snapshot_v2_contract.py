from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.market_data import (
    FINGERPRINT_SCHEMA_V2,
    GAP_POLICY_V1,
    NATIVE_M15_CONTRACT_V1,
    SNAPSHOT_SCHEMA_V2,
    Bar,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.market_data.fingerprint import (
    bar_content_fingerprint,
    bar_content_fingerprint_from_fields,
    dataset_fingerprint_v2,
)
from backend.persistence.market_data_repository import MarketDataRepository


def test_v2_snapshot_accepts_native_m15_contract() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    snapshot = DatasetSnapshot(
        id=uuid4(),
        venue_instrument=VenueInstrument(
            Instrument.EUR_USD, Provider.OANDA, "EUR_USD"
        ),
        base_resolution=Timeframe.M15,
        components=(PriceComponent.MID,),
        coverage_start=now,
        coverage_end=now.replace(hour=1),
        alignment_convention="UTC_HALF_OPEN_V1",
        session_policy="OANDA_FX_NY_V1",
        fingerprint_schema=FINGERPRINT_SCHEMA_V2,
        fingerprint="a" * 64,
        integrity_summary={"status": "VALID", "policy_version": GAP_POLICY_V1},
        created_at=now,
        snapshot_schema=SNAPSHOT_SCHEMA_V2,
    )
    assert snapshot.to_json()["snapshot_schema"] == SNAPSHOT_SCHEMA_V2
    assert NATIVE_M15_CONTRACT_V1 == "OANDA_M15_NATIVE_UTC_V1"


def test_v2_snapshot_descriptor_is_immutable() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    snapshot = DatasetSnapshot(
        uuid4(),
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        Timeframe.M15,
        (PriceComponent.MID,),
        now,
        now.replace(hour=1),
        "UTC_HALF_OPEN_V1",
        "OANDA_FX_NY_V1",
        FINGERPRINT_SCHEMA_V2,
        "a" * 64,
        {"status": "VALID", "policy_version": GAP_POLICY_V1},
        now,
        SNAPSHOT_SCHEMA_V2,
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.fingerprint = "b" * 64  # type: ignore[misc]


def test_v2_fingerprint_distinguishes_native_execution_contract() -> None:
    common = {
        "provider": "OANDA",
        "analytical_contract": "OANDA_M15_NATIVE_UTC_V1",
        "execution_components": ["BID", "ASK"],
    }
    native = dataset_fingerprint_v2(
        metadata={**common, "execution_contract": "OANDA_M1_NATIVE_BID_ASK_UTC_V1"},
        analytical_members=[],
        execution_members=[],
        gaps=[],
    )
    derived = dataset_fingerprint_v2(
        metadata={**common, "execution_contract": "M1_DERIVED_M15_V1"},
        analytical_members=[],
        execution_members=[],
        gaps=[],
    )
    assert native != derived


def test_v2_fingerprint_includes_ordered_contract_sections() -> None:
    metadata = {"provider": "OANDA", "coverage_start": "2026-01-01T00:00:00Z"}
    first = dataset_fingerprint_v2(
        metadata=metadata,
        analytical_members=[{"sequence": 1}],
        execution_members=[{"sequence": 1}],
        gaps=[],
    )
    second = dataset_fingerprint_v2(
        metadata=metadata,
        analytical_members=[{"sequence": 2}],
        execution_members=[{"sequence": 1}],
        gaps=[],
    )
    assert first != second
    with pytest.raises(TypeError):
        dataset_fingerprint_v2(
            metadata=metadata,
            analytical_members=None,
            execution_members=[],
            gaps=[],
        )


def test_v2_fingerprint_bytes_have_a_stable_golden_value() -> None:
    assert dataset_fingerprint_v2(
        metadata={"provider": "OANDA", "coverage_start": "2026-01-01T00:00:00Z"},
        analytical_members=[
            {
                "sequence": 1,
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:15:00Z",
                "content_fingerprint": "a" * 64,
            }
        ],
        execution_members=[
            {
                "sequence": 1,
                "market_bar_id": "00000000-0000-0000-0000-000000000001",
                "price_component": "BID",
                "start_time": "2026-01-01T00:00:00Z",
                "observation_fingerprint": "b" * 64,
            }
        ],
        gaps=[],
    ) == "3b55d114bc6e99037fb4da65d6d7cd6d7a759f60a578a8da70fb968e58e93d86"


def test_field_fingerprint_is_byte_equivalent_to_domain_bar() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bar = Bar(
        Instrument.EUR_USD,
        Timeframe.M1,
        PriceComponent.BID,
        start,
        start.replace(minute=1),
        Decimal("1.1000"),
        Decimal("1.1010"),
        Decimal("1.0990"),
        Decimal("1.1005"),
        provider=Provider.OANDA,
        volume=Decimal("2"),
    )
    assert bar_content_fingerprint_from_fields(
        instrument="EUR/USD",
        provider="OANDA",
        timeframe="1m",
        price_component="BID",
        start_time=bar.start_time,
        end_time=bar.end_time,
        open_price=bar.open,
        high_price=bar.high,
        low_price=bar.low,
        close_price=bar.close,
        volume=bar.volume,
    ) == bar_content_fingerprint(bar)


def test_v2_fingerprint_canonicalizes_nested_utc_gap_datetimes() -> None:
    metadata = {
        "provider": "OANDA",
        "bounds": {"start": datetime(2026, 7, 1, tzinfo=UTC)},
    }
    gaps = [
        {
            "start_time": datetime(2026, 7, 2, tzinfo=UTC),
            "details": {"end": datetime(2026, 7, 2, 0, 15, tzinfo=UTC)},
        }
    ]
    fingerprint = dataset_fingerprint_v2(
        metadata=metadata, analytical_members=[], execution_members=[], gaps=gaps
    )
    assert len(fingerprint) == 64
    assert fingerprint == dataset_fingerprint_v2(
        metadata={"provider": "OANDA", "bounds": {"start": "2026-07-01T00:00:00Z"}},
        analytical_members=[],
        execution_members=[],
        gaps=[
            {
                "start_time": "2026-07-02T00:00:00Z",
                "details": {"end": "2026-07-02T00:15:00Z"},
            }
        ],
    )


def test_v2_fingerprint_is_independent_of_producer_batch_size() -> None:
    metadata = {"provider": "OANDA", "coverage_start": "2026-01-01T00:00:00Z"}
    analytical = tuple({"sequence": i, "value": i * 2} for i in range(1, 1001))
    execution = tuple({"sequence": i, "market_bar_id": str(i)} for i in range(1, 1001))

    def batches(values, size):
        for offset in range(0, len(values), size):
            yield from values[offset : offset + size]

    expected = dataset_fingerprint_v2(
        metadata=metadata, analytical_members=analytical,
        execution_members=execution, gaps=(),
    )
    for analytical_size, execution_size in ((1, 7), (37, 113), (10_000, 3)):
        assert dataset_fingerprint_v2(
            metadata=metadata,
            analytical_members=batches(analytical, analytical_size),
            execution_members=batches(execution, execution_size),
            gaps=(),
        ) == expected


def test_current_bar_snapshot_read_uses_bounded_result_stream(monkeypatch) -> None:
    class Result:
        def yield_per(self, size):
            assert size == 10_000
            return iter(())

        def all(self):  # pragma: no cover - proves the forbidden path is unused
            raise AssertionError("snapshot read must not call ORM all()")

    class Session:
        def scalars(self, _statement):
            return Result()

    repository = MarketDataRepository()
    monkeypatch.setattr(
        repository, "_venue_rows", lambda _session, _venue_id: (object(), object())
    )
    assert repository.current_bars(
        Session(), uuid4(), datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC), (PriceComponent.MID,),
    ) == ()
