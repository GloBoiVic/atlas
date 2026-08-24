from decimal import Decimal

import pytest

from backend.domain.strategy import ParameterError, StrategyParameters
from backend.strategies.ema_sweep_engulfing_v2 import (
    DEFINITION,
    EmaSweepEngulfingV2Strategy,
)
from backend.strategies.indicators_v2 import atr, ema


def test_v2_definition_has_approved_schema_and_warmup() -> None:
    assert DEFINITION.implementation_key == "ema_sweep_engulfing.v2"
    assert DEFINITION.warm_up_bars == 200
    assert [
        (item.key, item.minimum, item.maximum) for item in DEFINITION.parameter_schema
    ] == [
        ("ema_period", 20, 200),
        ("atr_period", 5, 50),
        ("stop_buffer", "0.1", "3.0"),
        ("target_r", "0.5", "5.0"),
        ("expiry_window", 5, 5),
    ]


@pytest.mark.parametrize(
    "field, value",
    [
        ("ema_period", 19),
        ("ema_period", 201),
        ("atr_period", 4),
        ("atr_period", 51),
        ("stop_buffer", Decimal("0.09")),
        ("stop_buffer", Decimal("3.01")),
        ("target_r", Decimal("0.49")),
        ("target_r", Decimal("5.01")),
    ],
)
def test_v2_rejects_values_outside_approved_bounds(field: str, value: object) -> None:
    values = {
        "ema_period": 100,
        "atr_period": 14,
        "stop_buffer": Decimal("0.5"),
        "target_r": Decimal("1.7"),
        "expiry_window": 5,
    }
    values[field] = value
    with pytest.raises(ParameterError):
        EmaSweepEngulfingV2Strategy._validate_parameters(StrategyParameters(**values))


def test_v2_indicators_accept_explicit_periods() -> None:
    from backend.tests.strategies.test_ema_sweep_engulfing import candle

    bars = tuple(
        candle(
            index,
            "1.1000",
            f"{Decimal('1.1100') + Decimal(index) / 100000}",
            "1.0990",
            f"{Decimal('1.1000') + Decimal(index) / 10000}",
        )
        for index in range(60)
    )
    assert ema(bars, 20) != ema(bars, 40)
    assert atr(bars, 5) != atr(bars, 14)
