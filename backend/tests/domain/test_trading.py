from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.domain import (
    FinancialPositionState,
    InputError,
    Instrument,
    Position,
    PositionState,
)
from backend.domain.trading import TradingInputError


def test_strategy_position_state_and_financial_position_are_distinct() -> None:
    assert PositionState is not FinancialPositionState
    assert PositionState.FLAT.value == FinancialPositionState.FLAT.value
    assert Position(Instrument.EUR_USD).direction is None


def test_flat_position_has_no_exposure_facts() -> None:
    position = Position(Instrument.EUR_USD)
    assert position.quantity == Decimal("0")
    assert position.to_json()["state"] == "FLAT"
    with pytest.raises(TradingInputError):
        Position(Instrument.EUR_USD, quantity=Decimal("1"))


@pytest.mark.parametrize(
    "state, quantity, price, opened_at",
    [
        (
            FinancialPositionState.LONG,
            Decimal("0"),
            Decimal("1.1"),
            datetime(2026, 1, 1, tzinfo=UTC),
        ),
        (
            FinancialPositionState.SHORT,
            Decimal("1"),
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
        ),
        (FinancialPositionState.LONG, Decimal("1"), Decimal("1.1"), None),
        (
            FinancialPositionState.SHORT,
            Decimal("1"),
            Decimal("0"),
            datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ],
)
def test_exposed_position_requires_strict_positive_financial_facts(
    state: FinancialPositionState,
    quantity: Decimal,
    price: Decimal | None,
    opened_at: datetime | None,
) -> None:
    with pytest.raises(InputError):
        Position(Instrument.EUR_USD, state, quantity, price, opened_at)


def test_exposed_position_has_direction_and_decimal_serialization() -> None:
    position = Position(
        Instrument.EUR_USD,
        FinancialPositionState.LONG,
        Decimal("2"),
        Decimal("1.1050"),
        datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
    )
    assert position.direction is not None
    assert position.direction.value == "LONG"
    assert position.to_json()["quantity"] == "2"
    assert position.to_json()["average_entry_price"] == "1.1050"


def test_strategy_context_requires_position_state_not_financial_position() -> None:
    from backend.domain import Bar, PriceComponent, StrategyContext, Timeframe

    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    bar = Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
        Decimal("1.1"),
        Decimal("1.11"),
        Decimal("1.09"),
        Decimal("1.105"),
    )
    with pytest.raises(InputError):
        StrategyContext(
            bar.end_time,
            Instrument.EUR_USD,
            (bar,),
            position=Position(Instrument.EUR_USD),  # type: ignore[arg-type]
        )
