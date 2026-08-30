from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    DatasetSnapshot,
    InputError,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import MarketSpecification, StrategyContext
from backend.market_data.aggregation import aggregate_m1_to_m15
from backend.market_data.coverage import (
    MissingMinute,
    coalesce_gaps,
    validate_coverage,
)
from backend.market_data.fingerprint import canonical_decimal, dataset_fingerprint
from backend.market_data.session_calendar import (
    classify_minute,
    eligible_m15_windows,
    required_warmup_range,
)
from backend.market_data.session_policy import (
    EXPECTED_DATA,
    OANDA_EUR_USD_POLICY,
    UNAVAILABLE_SESSION,
    ExpectedSessionPolicy,
    SessionException,
)

MARKET = MarketSpecification(Instrument.EUR_USD, Decimal("0.0001"))


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def m1(
    start: datetime, component: PriceComponent = PriceComponent.MID, n: int = 1
) -> Bar:
    value = Decimal(n)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M1,
        component,
        start,
        start + timedelta(minutes=1),
        value,
        value + Decimal(".2"),
        value - Decimal(".1"),
        value + Decimal(".1"),
        volume=Decimal(n),
    )


def test_ny_daily_break_and_dst_and_weekend_are_policy_classified() -> None:
    assert classify_minute(datetime(2026, 1, 5, 21, 0, tzinfo=UTC)).open
    assert not classify_minute(datetime(2026, 1, 5, 21, 59, tzinfo=UTC)).open
    assert classify_minute(datetime(2026, 1, 5, 22, 5, tzinfo=UTC)).open
    assert not classify_minute(datetime(2026, 7, 6, 20, 59, tzinfo=UTC)).open
    assert classify_minute(datetime(2026, 7, 6, 21, 5, tzinfo=UTC)).open
    assert not classify_minute(datetime(2026, 1, 10, 12, 0, tzinfo=UTC)).open


def test_versioned_policy_returns_stable_classification_reason_and_version() -> None:
    weekday = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 1, 5, 21, 0, tzinfo=UTC)
    )
    maintenance = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 1, 5, 21, 59, tzinfo=UTC)
    )
    weekend = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    )
    assert weekday == (EXPECTED_DATA, "EXPECTED_PROVIDER_SESSION", "OANDA_FX_NY_V2")
    assert maintenance == (
        UNAVAILABLE_SESSION,
        "PROVIDER_MAINTENANCE_ROLLOVER",
        "OANDA_FX_NY_V2",
    )
    assert weekend == (UNAVAILABLE_SESSION, "WEEKLY_CLOSURE", "OANDA_FX_NY_V2")


def test_policy_uses_iana_dst_not_a_fixed_utc_offset() -> None:
    before_dst = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 3, 9, 20, 59, tzinfo=UTC)
    )
    after_dst = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 3, 9, 21, 5, tzinfo=UTC)
    )
    assert before_dst[0] == UNAVAILABLE_SESSION
    assert after_dst[0] == EXPECTED_DATA


def test_effective_dated_exception_is_explicit_and_missing_data_is_not_inference(
) -> None:
    policy = ExpectedSessionPolicy(
        "TEST_V1",
        "America/New_York",
        16 * 60 + 59,
        17 * 60 + 5,
        (
            SessionException(
                date(2026, 1, 5),
                date(2026, 1, 5),
                0,
                1440,
                UNAVAILABLE_SESSION,
                "DECLARED_HOLIDAY",
            ),
        ),
    )
    assert policy.classify_minute(datetime(2026, 1, 5, 15, tzinfo=UTC)) == (
        UNAVAILABLE_SESSION,
        "DECLARED_HOLIDAY",
        "TEST_V1",
    )
    # The authoritative V2 table contains only source-pinned exceptions.
    assert OANDA_EUR_USD_POLICY.exceptions


def test_oanda_2025_holiday_closures_are_explicit_and_coverage_ignores_them() -> None:
    assert OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2025, 1, 1, 15, 0, tzinfo=UTC)
    ) == (UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE", "OANDA_FX_NY_V2")
    assert OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2025, 1, 1, 22, 5, tzinfo=UTC)
    )[0] == EXPECTED_DATA
    assert OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2025, 12, 25, 16, 59, tzinfo=UTC)
    ) == (UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE", "OANDA_FX_NY_V2")


def test_warmup_counts_eligible_windows_not_closure_minutes() -> None:
    start, end = required_warmup_range(at(12, 22), at(12, 23), 2)
    assert end == at(12, 23)
    assert start == at(12, 21, 30)
    assert len(eligible_m15_windows(start, at(12, 22))) == 2


def test_gap_coalescing_keeps_component_details() -> None:
    gaps = coalesce_gaps(
        (
            MissingMinute(at(5, 10, 0), (PriceComponent.MID,)),
            MissingMinute(at(5, 10, 1), (PriceComponent.ASK, PriceComponent.MID)),
            MissingMinute(at(5, 10, 3), (PriceComponent.BID,)),
        )
    )
    assert [(gap.start, gap.end) for gap in gaps] == [
        (at(5, 10, 0), at(5, 10, 2)),
        (at(5, 10, 3), at(5, 10, 4)),
    ]
    assert gaps[0].components == (PriceComponent.ASK, PriceComponent.MID)


def test_coverage_detects_missing_components_and_scheduled_observation() -> None:
    start = at(5, 10)
    bars = [m1(start, PriceComponent.MID), m1(start, PriceComponent.BID)]
    report = validate_coverage(start, start + timedelta(minutes=1), bars)
    assert report.valid is False
    assert report.missing[0].components == (PriceComponent.ASK,)
    complete = [m1(start, component) for component in PriceComponent]
    assert validate_coverage(start, start + timedelta(minutes=1), complete).valid
    closure = m1(at(5, 22), PriceComponent.MID)
    assert not validate_coverage(closure.start_time, closure.end_time, [closure]).valid


def test_aggregation_uses_exact_boundaries_and_never_forward_fills() -> None:
    start = at(5, 10)
    bars = tuple(m1(start + timedelta(minutes=i), n=i + 1) for i in range(15))
    result, diagnostics = aggregate_m1_to_m15(
        bars, PriceComponent.MID, start, start + timedelta(minutes=15)
    )
    assert len(result) == 1
    assert diagnostics == []
    assert result[0].open == Decimal("1")
    assert result[0].close == Decimal("15.1")
    assert result[0].volume == Decimal("120")
    incomplete, diagnostics = aggregate_m1_to_m15(
        bars[:-1], PriceComponent.MID, start, start + timedelta(minutes=15)
    )
    assert incomplete == []
    assert diagnostics[0].reason == "UNEXPECTED_MISSING_DATA"
    assert diagnostics[0].missing_times == (start + timedelta(minutes=14),)


def test_aggregation_allows_daily_break_minutes_to_be_absent() -> None:
    start = datetime(2026, 1, 5, 21, 45, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    open_minutes = [
        start + timedelta(minutes=offset)
        for offset in range(30)
        if classify_minute(start + timedelta(minutes=offset)).open
    ]
    bars = tuple(m1(moment, n=index + 1) for index, moment in enumerate(open_minutes))

    result, diagnostics = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)

    assert len(open_minutes) == 24
    assert [bar.start_time for bar in result] == [start, start + timedelta(minutes=15)]
    assert result[0].open == Decimal("1")
    assert result[0].high == Decimal("14.2")
    assert result[0].low == Decimal("0.9")
    assert result[0].close == Decimal("14.1")
    assert result[0].volume == Decimal("105")
    assert result[1].open == Decimal("15")
    assert result[1].close == Decimal("24.1")
    assert result[1].volume == Decimal("195")


def test_aggregation_allows_friday_close_minutes_to_be_absent() -> None:
    start = datetime(2026, 1, 9, 21, 45, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    open_minutes = [
        start + timedelta(minutes=offset)
        for offset in range(15)
        if classify_minute(start + timedelta(minutes=offset)).open
    ]
    bars = tuple(m1(moment, n=index + 1) for index, moment in enumerate(open_minutes))

    result, diagnostics = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)

    assert len(open_minutes) == 14
    assert len(result) == 1
    assert result[0].open == Decimal("1")
    assert result[0].close == Decimal("14.1")
    assert result[0].volume == Decimal("105")


def test_derived_m15_mid_is_strategy_input_but_other_components_are_not() -> None:
    start = at(5, 10)
    bars = tuple(m1(start + timedelta(minutes=i)) for i in range(15))
    end = start + timedelta(minutes=15)
    mid, _diagnostics = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)

    assert StrategyContext(
        end, Instrument.EUR_USD, tuple(mid), market=MARKET
    ).bars == tuple(mid)
    with pytest.raises(InputError):
        StrategyContext(
            end,
            Instrument.EUR_USD,
            aggregate_m1_to_m15(
                tuple(
                    m1(start + timedelta(minutes=i), PriceComponent.BID)
                    for i in range(15)
                ),
                PriceComponent.BID,
                start,
                end,
            )[0],
            market=MARKET,
        )


def test_aggregation_coalesces_adjacent_missing_intervals_and_is_repeatable() -> None:
    start = at(5, 10)
    bars = tuple(
        m1(start + timedelta(minutes=i))
        for i in range(45)
        if i not in (1, 16)
    )
    end = start + timedelta(minutes=45)
    first = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)
    second = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)
    assert first == second
    eligible, diagnostics = first
    assert len(eligible) == 1
    assert len(diagnostics) == 1
    assert diagnostics[0].interval_start == start
    assert diagnostics[0].interval_end == start + timedelta(minutes=30)
    assert diagnostics[0].missing_components == (PriceComponent.MID,)
    assert diagnostics[0].missing_times == (
        start + timedelta(minutes=1),
        start + timedelta(minutes=16),
    )


def test_fingerprint_decimal_canonicalization_and_repeatability() -> None:
    assert canonical_decimal(Decimal("-0.000")) == "0"
    assert canonical_decimal(Decimal("1.2300E+2")) == "123"
    venue = VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    bars = tuple(
        m1(at(5, 10) + timedelta(minutes=i), PriceComponent.MID, i + 1)
        for i in range(2)
    )
    first = dataset_fingerprint(
        venue,
        at(5, 10),
        at(5, 12),
        (PriceComponent.MID,),
        bars,
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    second = dataset_fingerprint(
        venue,
        at(5, 10),
        at(5, 12),
        (PriceComponent.MID,),
        reversed(bars),
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    assert first == second
    assert first == "87ffdb8f6bdfaf8396fd428c8b8acb0978984cb0af09351f0f0767cb857ac24e"
    assert len(first) == 64
    assert FINGERPRINT_SCHEMA == "ATLAS_DATASET_SHA256_V1"


def test_snapshot_integrity_and_fingerprint_bind_policy_version() -> None:
    venue = VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    start, end = at(5, 10), at(5, 12)
    bars = tuple(
        m1(start + timedelta(minutes=i), PriceComponent.MID, i + 1)
        for i in range(2)
    )
    fingerprint = dataset_fingerprint(
        venue, start, end, (PriceComponent.MID,), bars,
        session_policy=SESSION_POLICY, alignment_convention=ALIGNMENT_CONVENTION,
    )
    alternate = dataset_fingerprint(
        venue, start, end, (PriceComponent.MID,), bars,
        session_policy="OANDA_FX_NY_V1", alignment_convention=ALIGNMENT_CONVENTION,
    )
    assert fingerprint != alternate
    snapshot = DatasetSnapshot(
        uuid4(), venue, Timeframe.M1,
        (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID), start, end,
        ALIGNMENT_CONVENTION, SESSION_POLICY, FINGERPRINT_SCHEMA, "a" * 64,
        {"status": "VALID", "policy_version": SESSION_POLICY}, end,
    )
    assert snapshot.integrity_summary["policy_version"] == SESSION_POLICY


def test_native_product_coverage_does_not_rebuild_analytical_series() -> None:
    start = at(5, 10)
    bars = tuple(m1(start + timedelta(minutes=i)) for i in range(15))
    report = validate_coverage(start, start + timedelta(minutes=15), bars[:-1])
    assert report.interval_diagnostics == ()
