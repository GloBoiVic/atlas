from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    InputError,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import StrategyContext
from backend.market_data.aggregation import AggregationError, aggregate_m1_to_m15
from backend.market_data.coverage import MissingMinute, coalesce_gaps, validate_coverage
from backend.market_data.fingerprint import canonical_decimal, dataset_fingerprint
from backend.market_data.session_calendar import (
    classify_minute,
    eligible_m15_windows,
    required_warmup_range,
)


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
    result = aggregate_m1_to_m15(
        bars, PriceComponent.MID, start, start + timedelta(minutes=15)
    )
    assert len(result) == 1
    assert result[0].open == Decimal("1")
    assert result[0].close == Decimal("15.1")
    assert result[0].volume == Decimal("120")
    with pytest.raises(AggregationError):
        aggregate_m1_to_m15(
            bars[:-1], PriceComponent.MID, start, start + timedelta(minutes=15)
        )


def test_aggregation_allows_daily_break_minutes_to_be_absent() -> None:
    start = datetime(2026, 1, 5, 21, 45, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    open_minutes = [
        start + timedelta(minutes=offset)
        for offset in range(30)
        if classify_minute(start + timedelta(minutes=offset)).open
    ]
    bars = tuple(m1(moment, n=index + 1) for index, moment in enumerate(open_minutes))

    result = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)

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

    result = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)

    assert len(open_minutes) == 14
    assert len(result) == 1
    assert result[0].open == Decimal("1")
    assert result[0].close == Decimal("14.1")
    assert result[0].volume == Decimal("105")


def test_derived_m15_mid_is_strategy_input_but_other_components_are_not() -> None:
    start = at(5, 10)
    bars = tuple(m1(start + timedelta(minutes=i)) for i in range(15))
    end = start + timedelta(minutes=15)
    mid = aggregate_m1_to_m15(bars, PriceComponent.MID, start, end)

    assert StrategyContext(end, Instrument.EUR_USD, mid).bars == mid
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
            ),
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
    assert first == "8ba3453a7ee49acd4f06e884a57a5220036c61f2c7b3ed3696ee4f48da5a24a4"
    assert len(first) == 64
    assert FINGERPRINT_SCHEMA == "ATLAS_DATASET_SHA256_V1"
