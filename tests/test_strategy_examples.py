from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.data.models import Candle
from backend.strategy import DataRequirement, DataType, SignalDirection
from backend.strategy.examples import BollingerBandsStrategy, SMACrossoverStrategy


def make_candle(close: str, index: int = 0) -> Candle:
    return Candle(
        instrument_id=uuid4(),
        provider="csv",
        timeframe="1m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        close=Decimal(close),
    )


def test_sma_returns_no_decision_until_previous_slow_window_exists() -> None:
    strategy = SMACrossoverStrategy({"fast_period": 2, "slow_period": 3})

    decisions = [
        strategy.on_candle(make_candle(price, index))
        for index, price in enumerate([3, 2, 1])
    ]

    assert decisions == [None, None, None]


def test_sma_emits_buy_and_sell_only_on_actual_crossovers() -> None:
    strategy = SMACrossoverStrategy({"fast_period": 2, "slow_period": 3})
    prices = ["3", "2", "1", "4", "0", "1"]

    decisions = [
        strategy.on_candle(make_candle(price, index)) for index, price in enumerate(prices)
    ]

    assert [decision.direction for decision in decisions if decision is not None] == [
        SignalDirection.BUY,
        SignalDirection.SELL,
    ]


def test_sma_decision_metadata_uses_decimal_values() -> None:
    strategy = SMACrossoverStrategy({"fast_period": 2, "slow_period": 3})
    for index, price in enumerate(["3", "2", "1", "4"]):
        decision = strategy.on_candle(make_candle(price, index))

    assert decision is not None
    assert isinstance(decision.strength, Decimal)
    assert all(isinstance(value, Decimal) for value in decision.metadata.values())


def test_bollinger_returns_no_decision_until_period_is_available() -> None:
    strategy = BollingerBandsStrategy(
        {"period": 3, "std_dev_multiplier": Decimal("1")},
    )

    assert strategy.on_candle(make_candle("10", 0)) is None
    assert strategy.on_candle(make_candle("10", 1)) is None


def test_bollinger_emits_buy_and_sell_when_price_crosses_bands() -> None:
    buy_strategy = BollingerBandsStrategy(
        {"period": 3, "std_dev_multiplier": Decimal("1")},
    )
    buy_prices = ["10", "10", "10", "8"]
    buy_decisions = [
        buy_strategy.on_candle(make_candle(price, index))
        for index, price in enumerate(buy_prices)
    ]

    sell_strategy = BollingerBandsStrategy(
        {"period": 3, "std_dev_multiplier": Decimal("1")},
    )
    sell_prices = ["10", "10", "10", "12"]
    sell_decisions = [
        sell_strategy.on_candle(make_candle(price, index))
        for index, price in enumerate(sell_prices)
    ]

    assert buy_decisions[-1] is not None
    assert buy_decisions[-1].direction is SignalDirection.BUY
    assert sell_decisions[-1] is not None
    assert sell_decisions[-1].direction is SignalDirection.SELL


def test_bollinger_does_not_repeat_signal_while_price_remains_outside_band() -> None:
    strategy = BollingerBandsStrategy(
        {"period": 3, "std_dev_multiplier": Decimal("1")},
    )
    prices = ["10", "10", "10", "8", "7"]

    decisions = [
        strategy.on_candle(make_candle(price, index)) for index, price in enumerate(prices)
    ]

    assert [decision for decision in decisions if decision is not None] == [decisions[3]]


def test_bollinger_metadata_uses_decimal_values() -> None:
    strategy = BollingerBandsStrategy(
        {"period": 3, "std_dev_multiplier": Decimal("1")},
    )
    for index, price in enumerate(["10", "10", "10"]):
        strategy.on_candle(make_candle(price, index))
    decision = strategy.on_candle(make_candle("8", 3))

    assert decision is not None
    assert all(isinstance(value, Decimal) for value in decision.metadata.values())


@pytest.mark.parametrize(
    "factory, config",
    [
        (SMACrossoverStrategy, {"fast_period": 0, "slow_period": 3}),
        (SMACrossoverStrategy, {"fast_period": 3, "slow_period": 3}),
        (BollingerBandsStrategy, {"period": 0, "std_dev_multiplier": Decimal("2")}),
        (BollingerBandsStrategy, {"period": 3, "std_dev_multiplier": Decimal("0")}),
        (BollingerBandsStrategy, {"period": 3, "std_dev_multiplier": 2.0}),
    ],
)
def test_examples_reject_invalid_configuration(factory: type, config: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        factory(config)


def test_examples_declare_configured_timeframe() -> None:
    strategy = SMACrossoverStrategy({"fast_period": 2, "slow_period": 3, "timeframe": "5m"})

    assert strategy.required_data() == DataRequirement(DataType.CANDLE, "5m")


def test_strategy_instances_do_not_share_candle_state() -> None:
    first = SMACrossoverStrategy({"fast_period": 2, "slow_period": 3})
    second = SMACrossoverStrategy({"fast_period": 2, "slow_period": 3})

    for index, price in enumerate(["3", "2", "1"]):
        first.on_candle(make_candle(price, index))
    decision = second.on_candle(make_candle("10", 0))

    assert decision is None
