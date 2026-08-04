from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.data.models import Candle
from backend.strategy import (
    DataRequirement,
    DataType,
    DuplicateStrategyRegistration,
    Signal,
    SignalDirection,
    Strategy,
    StrategyDecision,
    StrategyIdentityMismatch,
    StrategyNotRegistered,
    StrategyRegistry,
)


class StubStrategy(Strategy):
    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        return None


def invalid_factory(config: dict[str, object]) -> object:
    return object()


def test_strategy_decision_is_frozen_and_validates_decimal_strength() -> None:
    decision = StrategyDecision(SignalDirection.BUY, Decimal("0.5"), {"tag": "test"})

    with pytest.raises(FrozenInstanceError):
        decision.strength = Decimal("0.6")  # type: ignore[misc]
    with pytest.raises(TypeError):
        decision.metadata["tag"] = "changed"


@pytest.mark.parametrize("strength", [Decimal("-0.01"), Decimal("1.01"), Decimal("NaN")])
def test_strategy_decision_rejects_invalid_strength(strength: Decimal) -> None:
    with pytest.raises(ValueError):
        StrategyDecision(SignalDirection.BUY, strength, {})


def test_strategy_decision_rejects_float_strength() -> None:
    with pytest.raises(TypeError):
        StrategyDecision(SignalDirection.BUY, 0.5, {})  # type: ignore[arg-type]


def test_strategy_decision_rejects_non_json_metadata() -> None:
    with pytest.raises(TypeError):
        StrategyDecision(SignalDirection.BUY, Decimal("0.5"), {"bad": {1, 2}})


def test_signal_validates_uuid_and_utc_boundaries() -> None:
    signal = Signal(
        instrument_id=uuid4(),
        direction=SignalDirection.CLOSE,
        strength=Decimal("1"),
        metadata={},
        candle_timestamp=datetime(2026, 8, 4, tzinfo=UTC),
        strategy_version_id=uuid4(),
        strategy_name="stub",
        strategy_commit_sha="a" * 40,
    )
    assert signal.candle_timestamp.tzinfo is UTC

    with pytest.raises(ValueError):
        Signal(
            instrument_id=signal.instrument_id,
            direction=signal.direction,
            strength=signal.strength,
            metadata={},
            candle_timestamp=datetime(2026, 8, 4),
            strategy_version_id=signal.strategy_version_id,
            strategy_name="stub",
            strategy_commit_sha="a" * 40,
        )


def test_data_requirement_validates_timeframe() -> None:
    assert DataRequirement(DataType.CANDLE, "5m").timeframe == "5m"

    with pytest.raises(ValueError):
        DataRequirement(DataType.CANDLE, "")
    with pytest.raises(ValueError):
        DataRequirement(DataType.CANDLE, "hour")


def test_strategy_has_synchronous_default_hooks() -> None:
    strategy = StubStrategy({"period": 5})
    assert strategy.required_data() == DataRequirement(DataType.CANDLE, "1m")
    assert strategy.on_tick(None) is None  # type: ignore[arg-type]


def test_registry_registers_and_resolves_trusted_factory() -> None:
    registry = StrategyRegistry()
    version_id = uuid4()
    registry.register(version_id, "stub", "a" * 40, StubStrategy)

    resolved = registry.resolve(version_id, "stub", "a" * 40, {"period": 5})

    assert isinstance(resolved, StubStrategy)
    assert resolved.config == {"period": 5}


def test_registry_rejects_duplicate_registration() -> None:
    registry = StrategyRegistry()
    version_id = uuid4()
    registry.register(version_id, "stub", "a" * 40, StubStrategy)

    with pytest.raises(DuplicateStrategyRegistration):
        registry.register(version_id, "stub", "a" * 40, StubStrategy)


def test_registry_fails_closed_for_missing_version() -> None:
    with pytest.raises(StrategyNotRegistered):
        StrategyRegistry().resolve(uuid4(), "stub", "a" * 40, {})


def test_registry_fails_closed_for_commit_mismatch() -> None:
    registry = StrategyRegistry()
    version_id = uuid4()
    registry.register(version_id, "stub", "a" * 40, StubStrategy)

    with pytest.raises(StrategyIdentityMismatch):
        registry.resolve(version_id, "stub", "b" * 40, {})


def test_registry_fails_closed_for_strategy_name_mismatch() -> None:
    registry = StrategyRegistry()
    version_id = uuid4()
    registry.register(version_id, "stub", "a" * 40, StubStrategy)

    with pytest.raises(StrategyIdentityMismatch):
        registry.resolve(version_id, "different-stub", "a" * 40, {})


def test_registry_fails_closed_when_factory_returns_non_strategy() -> None:
    registry = StrategyRegistry()
    version_id = uuid4()
    registry.register(version_id, "stub", "a" * 40, invalid_factory)  # type: ignore[arg-type]

    with pytest.raises(StrategyIdentityMismatch):
        registry.resolve(version_id, "stub", "a" * 40, {})
