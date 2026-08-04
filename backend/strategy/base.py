"""Base contract for synchronous, computation-only strategies."""

from abc import ABC, abstractmethod
from typing import Any

from backend.data.models import Candle, Tick
from backend.strategy.contracts import DataRequirement, DataType, StrategyDecision


class Strategy(ABC):
    """A strategy instance isolated to one bot pipeline."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = dict(config)

    @abstractmethod
    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        """Evaluate one completed candle and optionally return a decision."""

    def on_tick(self, tick: Tick) -> None:
        """Observe a tick without producing a trading signal."""
        return None

    def required_data(self) -> DataRequirement:
        """Declare the default one-minute candle requirement."""
        return DataRequirement(data_type=DataType.CANDLE, timeframe="1m")
