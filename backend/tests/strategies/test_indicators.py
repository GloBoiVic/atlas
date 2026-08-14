from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

import pytest

from backend.domain.market_data import (
    Bar,
    InputError,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.strategies.indicators import (
    ATRInsufficientHistoryError,
    EMAInsufficientHistoryError,
    IndicatorInputError,
    atr_14,
    ema_100,
    true_range,
)


def bar(index: int, close: Decimal = Decimal("1")) -> Bar:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        close,
        close,
        close,
        close,
    )


def atr_bar(index: int, true_range: Decimal) -> Bar:
    start = datetime(2026, 2, 1, tzinfo=UTC) + timedelta(minutes=15 * index)
    close = Decimal("100")
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        close,
        close + true_range,
        close,
        close,
    )


def test_ema_has_a_varied_literal_seed() -> None:
    bars = tuple(
        bar(index, Decimal("1.1") if index < 50 else Decimal("1.3"))
        for index in range(100)
    )
    assert ema_100(bars) == Decimal("1.2")


def test_ema_uses_literal_decimal_recursion_golden() -> None:
    bars = tuple(
        [
            bar(index, Decimal("1.1") if index < 50 else Decimal("1.3"))
            for index in range(100)
        ]
        + [bar(100, Decimal("1.5")), bar(101, Decimal("0.9"))]
    )
    # Independent hand derivation under the intended 28-digit, half-even
    # Decimal semantics: seed=1.2, then 1.2 + (2/101)*(1.5-1.2), then
    # that result + (2/101)*(0.9-that result).
    expected = Decimal("1.199882364474071169493186943")
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        assert ema_100(bars) == expected


def test_atr_has_a_varied_literal_seed_and_recursion() -> None:
    seed_ranges = tuple(
        Decimal(value)
        for value in (
            "0.8",
            "1.2",
            "0.9",
            "1.5",
            "1.1",
            "1.8",
            "0.7",
            "1.4",
            "1.0",
            "1.6",
            "1.3",
            "0.6",
            "1.7",
            "1.9",
        )
    )
    bars = tuple(atr_bar(index, value) for index, value in enumerate(seed_ranges, 1))
    bars = (atr_bar(0, Decimal("0.5")),) + bars
    assert atr_14(bars) == Decimal("1.25")

    extended = bars + (atr_bar(15, Decimal("2.3")), atr_bar(16, Decimal("0.4")))
    assert atr_14(extended) == Decimal("1.258928571428571428571428571")


def test_true_range_uses_literal_normal_and_gap_maxima() -> None:
    previous = bar(0, Decimal("100"))
    assert true_range(
        previous,
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            previous.end_time,
            previous.end_time + timedelta(minutes=15),
            Decimal("101"),
            Decimal("104"),
            Decimal("99"),
            Decimal("101"),
        ),
    ) == Decimal("5")
    assert true_range(
        previous,
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            previous.end_time,
            previous.end_time + timedelta(minutes=15),
            Decimal("107"),
            Decimal("110"),
            Decimal("106"),
            Decimal("107"),
        ),
    ) == Decimal("10")
    assert true_range(
        previous,
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            previous.end_time,
            previous.end_time + timedelta(minutes=15),
            Decimal("93"),
            Decimal("94"),
            Decimal("90"),
            Decimal("93"),
        ),
    ) == Decimal("10")


def test_indicators_report_required_history_with_typed_errors() -> None:
    with pytest.raises(EMAInsufficientHistoryError):
        ema_100(tuple(bar(index) for index in range(99)))
    with pytest.raises(ATRInsufficientHistoryError):
        atr_14(tuple(atr_bar(index, Decimal("1")) for index in range(14)))


def test_indicators_reject_invalid_or_unordered_input() -> None:
    with pytest.raises(IndicatorInputError):
        ema_100([bar(0), "not a bar"])  # type: ignore[list-item]
    with pytest.raises(IndicatorInputError):
        atr_14((bar(1), bar(0)))


def test_canonical_bar_rejects_non_decimal_price_before_calculation() -> None:
    with pytest.raises(InputError, match="must be a Decimal"):
        bar(0, "1")  # type: ignore[arg-type]
