from decimal import Decimal
from pathlib import Path

import pytest

from backend.experiments.configuration import (
    MODEL_VERSION,
    RISK_SCHEMA_VERSION,
    SIMULATION_SCHEMA_VERSION,
    ConfigurationError,
    risk_config,
    simulation_config,
)
from backend.strategies.production import create_production_strategy_registry


def test_configuration_derives_only_supported_phase4_assumptions() -> None:
    assert risk_config(Decimal("0.01")) == {
        "schema_version": RISK_SCHEMA_VERSION,
        "risk_per_trade": "0.01",
    }
    config = simulation_config(slippage_ticks=2, commission_per_unit=Decimal("0.10"))
    assert config == {
        "schema_version": SIMULATION_SCHEMA_VERSION,
        "execution_resolution": "M1",
        "analysis_component": "MID",
        "execution_components": ["BID", "ASK"],
        "spread_model": "DATASET_BID_ASK_EMBEDDED",
        "slippage_model": {
            "type": "ADVERSE_FIXED_TICKS",
            "ticks": 2,
            "tick_size": "0.00001",
        },
        "commission_model": {"type": "PER_FILL_PER_UNIT_USD", "amount": "0.10"},
        "financing_model": {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"},
        "intrabar_policy": "STOP_LOSS_ADVERSE_FIRST_V1",
        "target_fill_policy": "REQUESTED_PRICE_NO_IMPROVEMENT_V1",
        "end_policy": "FINAL_ELIGIBLE_M1_CLOSE_V1",
        "equity_sampling": "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1",
    }
    assert MODEL_VERSION == "PHASE5_HISTORICAL_EXECUTION_V2"


def test_configuration_rejects_negative_simulation_values_at_boundary() -> None:
    with pytest.raises(ConfigurationError):
        simulation_config(slippage_ticks=-1, commission_per_unit=Decimal("0"))


def test_production_registration_archives_once_and_evaluation_has_no_path_input() -> (
    None
):
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    entry = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    )
    assert entry.source_archive.fingerprint
    assert tuple(registry.catalog()) == (entry,)
    assert (
        entry.implementation.definition.implementation_key
        == "ema_sweep_confirmation_break.v2"
    )
    assert entry.implementation.definition.name == "EMA Sweep Confirmation Break"
