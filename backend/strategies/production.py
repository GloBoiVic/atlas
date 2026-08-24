"""Explicit production Strategy composition.

Source files are archived exactly once while composing the process. Evaluation
uses the resulting immutable registry and never performs filesystem discovery.
"""

from pathlib import Path

from .contract import StrategyRegistration
from .ema_sweep_engulfing import EmaSweepEngulfingStrategy
from .ema_sweep_engulfing_v2 import EmaSweepEngulfingV2Strategy
from .registry import StrategyRegistry


def create_production_strategy_registry(root: Path | None = None) -> StrategyRegistry:
    repository_root = root or Path(__file__).resolve().parents[2]
    registry = StrategyRegistry()
    registry.register(
        StrategyRegistration(
            EmaSweepEngulfingStrategy.definition, EmaSweepEngulfingStrategy()
        ),
        repository_root,
    )
    registry.register(
        StrategyRegistration(
            EmaSweepEngulfingV2Strategy.definition, EmaSweepEngulfingV2Strategy()
        ),
        repository_root,
    )
    return registry


__all__ = ["create_production_strategy_registry"]
