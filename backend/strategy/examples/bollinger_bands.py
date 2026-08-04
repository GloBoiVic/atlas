"""Decimal Bollinger Bands mean-reversion example strategy."""

from decimal import Decimal, getcontext
from typing import Any

from backend.data.models import Candle
from backend.strategy.base import Strategy
from backend.strategy.contracts import (
    DataRequirement,
    DataType,
    SignalDirection,
    StrategyDecision,
)


class BollingerBandsStrategy(Strategy):
    """Buy below the lower band and sell above the upper band on a band crossing."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        period = config.get("period")
        if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
            raise ValueError("period must be a positive integer")
        multiplier = config.get("std_dev_multiplier")
        if not isinstance(multiplier, Decimal) or not multiplier.is_finite() or multiplier <= 0:
            raise ValueError("std_dev_multiplier must be a positive finite Decimal")
        timeframe = config.get("timeframe", "1m")
        if not isinstance(timeframe, str):
            raise ValueError("timeframe must be a string")
        self.period = period
        self.std_dev_multiplier = multiplier
        self._data_requirement = DataRequirement(DataType.CANDLE, timeframe)
        self._candles: list[Candle] = []
        self._previous_bands: tuple[Decimal, Decimal] | None = None

    def required_data(self) -> DataRequirement:
        """Return the configured candle timeframe."""
        return self._data_requirement

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        """Evaluate a completed candle and signal only when it crosses a band."""
        self._candles.append(candle)
        if len(self._candles) < self.period:
            return None

        closes = [item.close for item in self._candles[-self.period :]]
        divisor = Decimal(self.period)
        middle = sum(closes, Decimal("0")) / divisor
        variance = sum((close - middle) ** 2 for close in closes) / divisor
        deviation = variance.sqrt(context=getcontext())
        lower = middle - self.std_dev_multiplier * deviation
        upper = middle + self.std_dev_multiplier * deviation

        direction: SignalDirection | None = None
        if self._previous_bands is not None:
            previous_lower, previous_upper = self._previous_bands
            previous_close = self._candles[-2].close
            current_close = self._candles[-1].close
            if previous_close >= previous_lower and current_close < lower:
                direction = SignalDirection.BUY
            elif previous_close <= previous_upper and current_close > upper:
                direction = SignalDirection.SELL
        self._previous_bands = (lower, upper)
        if direction is None:
            return None
        return StrategyDecision(
            direction=direction,
            strength=Decimal("0.8"),
            metadata={
                "middle_band": middle,
                "upper_band": upper,
                "lower_band": lower,
                "standard_deviation": deviation,
            },
        )
