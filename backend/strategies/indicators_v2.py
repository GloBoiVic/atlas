"""Period-driven deterministic EMA and Wilder ATR indicators for Strategy v2."""

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from backend.domain.market_data import Bar, InputError


class IndicatorError(InputError):
    """Base class for v2 indicator failures."""


class IndicatorInputError(IndicatorError):
    """The input is not an ordered canonical bar sequence."""


class InsufficientHistoryError(IndicatorError):
    """The supplied bars do not contain enough history."""


DECIMAL_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


def _validate_bars(bars: Sequence[Bar]) -> None:
    if type(bars) not in (list, tuple):
        raise IndicatorInputError("bars must be an ordered sequence of canonical bars")
    if any(type(bar) is not Bar for bar in bars):
        raise IndicatorInputError("bars must contain canonical Bar values")
    if any(a.end_time >= b.end_time for a, b in zip(bars, bars[1:], strict=False)):
        raise IndicatorInputError("bars must be strictly ordered by completion time")


def ema(bars: Sequence[Bar], period: int) -> Decimal:
    """Return the EMA at the final completed bar, seeded by the first period."""
    _validate_bars(bars)
    if type(period) is not int or period <= 0:
        raise IndicatorInputError("EMA period must be a positive integer")
    if len(bars) < period:
        raise InsufficientHistoryError(f"EMA-{period} requires {period} completed bars")
    with localcontext(DECIMAL_CONTEXT):
        p = Decimal(period)
        value = sum((bar.close for bar in bars[:period]), Decimal(0)) / p
        alpha = Decimal(2) / Decimal(period + 1)
        for bar in bars[period:]:
            value = value + alpha * (bar.close - value)
        return value


def true_range(previous_bar: Bar, bar: Bar) -> Decimal:
    if type(previous_bar) is not Bar or type(bar) is not Bar:
        raise IndicatorInputError("true range requires canonical Bar values")
    if previous_bar.end_time >= bar.end_time:
        raise IndicatorInputError("true range bars must be strictly ordered")
    return max(
        bar.high - bar.low,
        abs(bar.high - previous_bar.close),
        abs(bar.low - previous_bar.close),
    )


def atr(bars: Sequence[Bar], period: int) -> Decimal:
    """Return Wilder ATR at the final completed bar."""
    _validate_bars(bars)
    if type(period) is not int or period <= 0:
        raise IndicatorInputError("ATR period must be a positive integer")
    required = period + 1
    if len(bars) < required:
        raise InsufficientHistoryError(
            f"ATR-{period} requires {required} bars for {period} valid true ranges"
        )
    with localcontext(DECIMAL_CONTEXT):
        value = sum(
            (true_range(bars[index - 1], bars[index]) for index in range(1, required)),
            Decimal(0),
        ) / Decimal(period)
        for index in range(required, len(bars)):
            current = true_range(bars[index - 1], bars[index])
            value = value + (current - value) / Decimal(period)
        return value


__all__ = [
    "IndicatorError",
    "IndicatorInputError",
    "InsufficientHistoryError",
    "atr",
    "ema",
    "true_range",
]
