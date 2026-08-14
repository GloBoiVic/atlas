"""Deterministic Decimal indicators used by the reference Strategy.

The functions in this module deliberately operate on the canonical completed
bars rather than maintaining indicator state.  Callers therefore get the same
answer in Experiments, PAPER, and LIVE for the same ordered input.  All EMA and
ATR arithmetic uses an explicit 28-digit, ROUND_HALF_EVEN Decimal context.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from backend.domain.market_data import Bar, InputError


class IndicatorError(InputError):
    """Base class for failures while calculating a Strategy indicator."""


class IndicatorInputError(IndicatorError):
    """The indicator input is not an ordered canonical bar sequence."""


class InsufficientHistoryError(IndicatorError):
    """The supplied bars do not contain enough history for the indicator."""


class EMAInsufficientHistoryError(InsufficientHistoryError):
    """Fewer than 100 completed bars were supplied for EMA-100."""


class ATRInsufficientHistoryError(InsufficientHistoryError):
    """Fewer than 15 bars were supplied for ATR-14."""


EMA_PERIOD = 100
ATR_PERIOD = 14
DECIMAL_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


def _validate_bars(bars: Sequence[Bar]) -> None:
    if type(bars) not in (list, tuple):
        raise IndicatorInputError("bars must be an ordered sequence of canonical bars")
    if any(type(bar) is not Bar for bar in bars):
        raise IndicatorInputError("bars must contain canonical Bar values")
    if any(
        earlier.end_time >= later.end_time
        for earlier, later in zip(bars, bars[1:], strict=False)
    ):
        raise IndicatorInputError("bars must be strictly ordered by completion time")


def ema_100(bars: Sequence[Bar]) -> Decimal:
    """Return EMA-100 at the final completed bar.

    The seed is the arithmetic mean of the first 100 MID closes.  Later bars
    use the stated alpha of 2/101.
    """

    _validate_bars(bars)
    if len(bars) < EMA_PERIOD:
        raise EMAInsufficientHistoryError(
            f"EMA-100 requires {EMA_PERIOD} completed bars"
        )

    with localcontext(DECIMAL_CONTEXT):
        period = Decimal(EMA_PERIOD)
        ema = sum((bar.close for bar in bars[:EMA_PERIOD]), Decimal(0)) / period
        alpha = Decimal(2) / Decimal(EMA_PERIOD + 1)
        for bar in bars[EMA_PERIOD:]:
            ema = ema + alpha * (bar.close - ema)
        return ema


def true_range(previous_bar: Bar, bar: Bar) -> Decimal:
    """Return the true range of ``bar`` using its actual previous close."""

    if type(previous_bar) is not Bar or type(bar) is not Bar:
        raise IndicatorInputError("true range requires canonical Bar values")
    if previous_bar.end_time >= bar.end_time:
        raise IndicatorInputError("true range bars must be strictly ordered")
    return max(
        bar.high - bar.low,
        abs(bar.high - previous_bar.close),
        abs(bar.low - previous_bar.close),
    )


def atr_14(bars: Sequence[Bar]) -> Decimal:
    """Return Wilder ATR-14 at the final completed bar.

    The first bar has no fabricated previous close and consequently cannot
    produce a true range.  The first ATR is seeded from TRs for bars 1..14.
    """

    _validate_bars(bars)
    required_bars = ATR_PERIOD + 1
    if len(bars) < required_bars:
        raise ATRInsufficientHistoryError(
            f"ATR-14 requires {required_bars} bars for {ATR_PERIOD} valid true ranges"
        )

    with localcontext(DECIMAL_CONTEXT):
        atr = sum(
            (
                true_range(bars[index - 1], bars[index])
                for index in range(1, required_bars)
            ),
            Decimal(0),
        ) / Decimal(ATR_PERIOD)
        for index in range(required_bars, len(bars)):
            current_true_range = true_range(bars[index - 1], bars[index])
            atr = atr + (current_true_range - atr) / Decimal(ATR_PERIOD)
        return atr


__all__ = [
    "ATRInsufficientHistoryError",
    "EMAInsufficientHistoryError",
    "IndicatorError",
    "IndicatorInputError",
    "InsufficientHistoryError",
    "atr_14",
    "ema_100",
    "true_range",
]
