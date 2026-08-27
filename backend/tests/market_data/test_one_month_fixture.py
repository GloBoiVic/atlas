"""Regression fixtures derived from the recorded OANDA one-month measurement.

Architecture D5 / ARCHITECTURE.md:42 records ``2024-01-08 23:00 → 2024-02-10
00:00`` (769h, 102,618 M1 rows, 123 gaps) as the one-month fixture that prevents
the prior misclassification from returning.  Live evidence comes from the
prior ``fundamental-load-422`` load (``memberMinutes=34206``, ``expectedOpen=
34361``).  This module exercises the V1 policy against that SAME range and
asserts the deterministic semantics — it does NOT require real OANDA data.

The recorded F2 finding — 34361 expected vs 34206 observed → 155 minutes are
unaccounted for in the empirical fixture — is preserved.  We only assert the
classification shape and deterministic re-runnability here.  An actual
COMPLETED load remains environment-gated (see VALIDATION.md gate 12).
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    VenueInstrument,
)
from backend.market_data.fingerprint import dataset_fingerprint
from backend.market_data.session_policy import (
    EXPECTED_DATA,
    OANDA_EUR_USD_POLICY,
    UNAVAILABLE_SESSION,
)

FIXTURE_RANGE_START = datetime(2024, 1, 8, 23, 0, tzinfo=UTC)
FIXTURE_RANGE_END = datetime(2024, 2, 10, 0, 0, tzinfo=UTC)
RECORDED_EXPECTED_OPEN_MINUTES = 34361
RECORDED_LOAD_OBSERVED_MINUTES = 34206
RECORDED_INSERTED_ROWS = 102618


def _utc_minute(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("fixture times must be timezone-aware UTC")
    if value.second or value.microsecond:
        raise ValueError("fixture times must be minute-aligned")
    return value


def fixture_classifications() -> Counter[str]:
    counter: Counter[str] = Counter()
    cursor = _utc_minute(FIXTURE_RANGE_START)
    end = _utc_minute(FIXTURE_RANGE_END)
    while cursor < end:
        cls, _reason, _version = OANDA_EUR_USD_POLICY.classify_minute(cursor)
        counter[cls] += 1
        cursor = cursor + timedelta(minutes=1)
    return counter


def fixture_reason_classifications() -> Counter[str]:
    counter: Counter[str] = Counter()
    cursor = _utc_minute(FIXTURE_RANGE_START)
    end = _utc_minute(FIXTURE_RANGE_END)
    while cursor < end:
        _cls, reason, _version = OANDA_EUR_USD_POLICY.classify_minute(cursor)
        counter[reason] += 1
        cursor = cursor + timedelta(minutes=1)
    return counter


def fixture_policy_fingerprint() -> str:
    """A deterministic 1-month classification digest bound to the V1 policy.

    The fingerprint is the SHA-256 of the canonical ``(minute, classification,
    reason, version)`` stream for the fixture range.  It binds the test to the
    V1 policy version.  Any policy-version semantic change must mint a fresh
    digest; existing snapshots are never reinterpreted.
    """
    digest = sha256()
    cursor = _utc_minute(FIXTURE_RANGE_START)
    end = _utc_minute(FIXTURE_RANGE_END)
    while cursor < end:
        cls, reason, version = OANDA_EUR_USD_POLICY.classify_minute(cursor)
        digest.update(cursor.strftime("%Y-%m-%dT%H:%MZ").encode())
        digest.update(b"\t")
        digest.update(cls.encode())
        digest.update(b"\t")
        digest.update(reason.encode())
        digest.update(b"\t")
        digest.update(version.encode())
        digest.update(b"\n")
        cursor = cursor + timedelta(minutes=1)
    return digest.hexdigest()


def test_one_month_fixture_classification_counts_match_policy() -> None:
    classification_counts = fixture_classifications()
    assert classification_counts[EXPECTED_DATA] == RECORDED_EXPECTED_OPEN_MINUTES
    expected_closed = (
        classification_counts[UNAVAILABLE_SESSION]
        if UNAVAILABLE_SESSION in classification_counts
        else 0
    )
    assert expected_closed == (
        int(
            (FIXTURE_RANGE_END - FIXTURE_RANGE_START).total_seconds() // 60
        )
        - RECORDED_EXPECTED_OPEN_MINUTES
    )
    assert (
        RECORDED_INSERTED_ROWS // 3 == RECORDED_LOAD_OBSERVED_MINUTES
    ), "the recorded 102,618 M1 rows = 34206 component-minutes"


def test_one_month_fixture_reason_breakdown_lists_only_documented_reasons() -> None:
    reasons = fixture_reason_classifications()
    assert set(reasons) == {
        "EXPECTED_PROVIDER_SESSION",
        "WEEKLY_CLOSURE",
        "PROVIDER_MAINTENANCE_ROLLOVER",
    }


def test_one_month_fixture_digest_is_repeatable() -> None:
    first = fixture_policy_fingerprint()
    second = fixture_policy_fingerprint()
    assert first == second
    assert len(first) == 64


def test_one_month_fixture_rejects_misaligned_window_boundaries() -> None:
    cursor = FIXTURE_RANGE_START
    end = FIXTURE_RANGE_END
    while cursor < end:
        if cursor.second or cursor.microsecond:
            raise AssertionError("fixture window not minute-aligned")
        cursor = cursor + timedelta(minutes=1)


def test_one_month_fixture_session_policy_binds_to_fingerprint() -> None:
    venue = VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    components: tuple[PriceComponent, ...] = (
        PriceComponent.ASK,
        PriceComponent.BID,
        PriceComponent.MID,
    )
    bars: tuple[Bar, ...] = ()
    fp_v1 = dataset_fingerprint(
        venue,
        FIXTURE_RANGE_START,
        FIXTURE_RANGE_START + timedelta(minutes=1),
        components,
        bars,
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    fp_alt = dataset_fingerprint(
        venue,
        FIXTURE_RANGE_START,
        FIXTURE_RANGE_START + timedelta(minutes=1),
        components,
        bars,
            session_policy="OANDA_FX_NY_V1",
        alignment_convention=ALIGNMENT_CONVENTION,
    )
    assert fp_v1 != fp_alt
    assert fp_v1 == _expected_empty_fingerprint_for_v1()
    assert FINGERPRINT_SCHEMA == "ATLAS_DATASET_SHA256_V1"


def _expected_empty_fingerprint_for_v1() -> str:
    cursor = FIXTURE_RANGE_START
    end = FIXTURE_RANGE_START + timedelta(minutes=1)
    components: tuple[PriceComponent, ...] = (
        PriceComponent.ASK,
        PriceComponent.BID,
        PriceComponent.MID,
    )
    bars: tuple[Bar, ...] = ()
    return dataset_fingerprint(
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        cursor,
        end,
        components,
        bars,
        session_policy=SESSION_POLICY,
        alignment_convention=ALIGNMENT_CONVENTION,
    )


def test_one_month_fixture_idempotent_classification_call() -> None:
    cursor = FIXTURE_RANGE_START
    end = FIXTURE_RANGE_START + timedelta(minutes=15)
    seen: set[tuple[str, str, str]] = set()
    while cursor < end:
        first = OANDA_EUR_USD_POLICY.classify_minute(cursor)
        for _ in range(5):
            again = OANDA_EUR_USD_POLICY.classify_minute(cursor)
            assert again == first
        seen.add(first)
        cursor = cursor + timedelta(minutes=1)
    assert len(seen) <= 3


def test_daily_maintenance_window_v1_classifies_2159_to_2205_as_unavailable() -> None:
    samples = [
        (datetime(2024, 1, 9, 21, 58, tzinfo=UTC), EXPECTED_DATA),
        (datetime(2024, 1, 9, 21, 59, tzinfo=UTC), UNAVAILABLE_SESSION),
        (datetime(2024, 1, 9, 22, 0, tzinfo=UTC), UNAVAILABLE_SESSION),
        (datetime(2024, 1, 9, 22, 4, tzinfo=UTC), UNAVAILABLE_SESSION),
        (datetime(2024, 1, 9, 22, 5, tzinfo=UTC), EXPECTED_DATA),
    ]
    for moment, expected in samples:
        cls, reason, version = OANDA_EUR_USD_POLICY.classify_minute(moment)
        formatted = moment.isoformat()
        assert cls == expected, f"{formatted} → {cls}/{reason}/{version}"
        assert version == "OANDA_FX_NY_V2"


def test_weekend_window_v1_classifies_friday_2159_through_monday_2205_as_unavailable(
) -> None:
    """Architecture gate: weekend boundary = weekend closure UA, not corrupt.

    V1 represents Fri>=16:59 NY, full Sat, Sun<17:05 NY as WEEKLY_CLOSURE.
    Sample windows in January 2024 (EST) so the closure window runs from
    Fri 21:59Z through Sun 22:04Z, and the daily-maintenance window on Mon
    Tue Wed Thu also is UNAVAILABLE_SESSION for the 21:59-22:05Z span.
    """
    pre_weekend_open = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 1, 12, 21, 58, tzinfo=UTC)
    )
    assert pre_weekend_open == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    ), "Fri 16:58 NY EST is still expected, before Friday close"
    weekend_samples = [
        datetime(2024, 1, 12, 21, 59, tzinfo=UTC),
        datetime(2024, 1, 13, 12, 0, tzinfo=UTC),
        datetime(2024, 1, 14, 12, 0, tzinfo=UTC),
        datetime(2024, 1, 14, 22, 4, tzinfo=UTC),
    ]
    for moment in weekend_samples:
        cls, reason, version = OANDA_EUR_USD_POLICY.classify_minute(moment)
        assert cls == UNAVAILABLE_SESSION, (
            f"{moment.isoformat()} expected UNAVAILABLE_SESSION, got {cls}/{reason}"
        )
        assert reason == "WEEKLY_CLOSURE"
        assert version == "OANDA_FX_NY_V2"
    sunday_reopen = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 1, 14, 22, 5, tzinfo=UTC)
    )
    assert sunday_reopen == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    )
    monday_pre_maintenance = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 1, 15, 21, 58, tzinfo=UTC)
    )
    assert monday_pre_maintenance == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    ), "Mon 16:58 NY EST is expected — pre-maintenance minute"


def test_dst_transition_does_not_offset_v1_session_window() -> None:
    """Architecture gate: DST transition (IANA America/New_York).

    The V1 rule is expressed in local NY civil time — therefore the same NY
    local ``16:59-17:05`` minute classifies the same across the spring-forward
    DST shift.  ZoneInfo applies the EST→EDT transition; the resulting UTC
    window shifts from 21:59-22:05Z (EST) to 20:59-21:05Z (EDT) without an
    off-by-hour gap.
    """
    winter_pre = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 1, 9, 21, 58, tzinfo=UTC)
    )
    winter_in = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 1, 9, 21, 59, tzinfo=UTC)
    )
    winter_post = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 1, 9, 22, 5, tzinfo=UTC)
    )
    summer_pre = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 7, 8, 20, 58, tzinfo=UTC)
    )
    summer_in = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 7, 8, 20, 59, tzinfo=UTC)
    )
    summer_post = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2024, 7, 8, 21, 5, tzinfo=UTC)
    )
    assert winter_pre == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    )
    assert winter_in == (
        UNAVAILABLE_SESSION,
        "PROVIDER_MAINTENANCE_ROLLOVER",
        "OANDA_FX_NY_V2",
    )
    assert winter_post == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    )
    assert summer_pre == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    )
    assert summer_in == (
        UNAVAILABLE_SESSION,
        "PROVIDER_MAINTENANCE_ROLLOVER",
        "OANDA_FX_NY_V2",
    )
    assert summer_post == (
        EXPECTED_DATA,
        "EXPECTED_PROVIDER_SESSION",
        "OANDA_FX_NY_V2",
    )
    transition_day_open = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 3, 9, 14, 0, tzinfo=UTC)
    )
    transition_day_close = OANDA_EUR_USD_POLICY.classify_minute(
        datetime(2026, 3, 8, 6, 59, tzinfo=UTC)
    )
    assert transition_day_open[0] == EXPECTED_DATA
    assert transition_day_close[0] == UNAVAILABLE_SESSION
