"""Decimal SMA crossover example strategy."""

from decimal import Decimal
from typing import Any

from backend.data.models import Candle
from backend.strategy.base import Strategy
from backend.strategy.contracts import (
    DataRequirement,
    DataType,
    SignalDirection,
    StrategyDecision,
)


def _positive_period(config: dict[str, Any], name: str) -> int:
    value = config.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


class SMACrossoverStrategy(Strategy):
    """Emit one decision when fast and slow simple moving averages cross."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.fast_period = _positive_period(config, "fast_period")
        self.slow_period = _positive_period(config, "slow_period")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")
        timeframe = config.get("timeframe", "1m")
        if not isinstance(timeframe, str):
            raise ValueError("timeframe must be a string")
        self._data_requirement = DataRequirement(DataType.CANDLE, timeframe)
        self._candles: list[Candle] = []

    def required_data(self) -> DataRequirement:
        """Return the configured candle timeframe."""
        return self._data_requirement

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        """Evaluate a completed candle and return only actual crossover decisions."""
        self._candles.append(candle)
        if len(self._candles) <= self.slow_period:
            return None

        closes = [item.close for item in self._candles]
        fast_divisor = Decimal(self.fast_period)
        slow_divisor = Decimal(self.slow_period)
        fast_sma = sum(closes[-self.fast_period:], Decimal("0")) / fast_divisor
        slow_sma = sum(closes[-self.slow_period:], Decimal("0")) / slow_divisor
        previous_fast = sum(closes[-self.fast_period - 1 : -1], Decimal("0")) / fast_divisor
        previous_slow = sum(closes[-self.slow_period - 1 : -1], Decimal("0")) / slow_divisor

        direction: SignalDirection | None = None
        if fast_sma > slow_sma and previous_fast <= previous_slow:
            direction = SignalDirection.BUY
        elif fast_sma < slow_sma and previous_fast >= previous_slow:
            direction = SignalDirection.SELL
        if direction is None:
            return None
        return StrategyDecision(
            direction=direction,
            strength=Decimal("0.8"),
            metadata={"fast_sma": fast_sma, "slow_sma": slow_sma},
        )
