from pathlib import Path

from backend.strategies.production import create_production_strategy_registry


def test_production_registry_exposes_only_current_reference_strategy() -> None:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    entries = tuple(registry.catalog())
    assert len(entries) == 1
    assert entries[0].definition.strategy_key == "ema_sweep_confirmation_break"
    assert entries[0].definition.name == "EMA Sweep Confirmation Break"
    assert entries[0].definition.implementation_key == "ema_sweep_confirmation_break.v1"
