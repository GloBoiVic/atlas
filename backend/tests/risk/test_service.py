from decimal import Decimal
from typing import TypedDict

import pytest

from backend.domain import Action, Direction, Instrument, TargetProposal
from backend.risk import (
    AccountState,
    ExecutableQuote,
    RiskConfig,
    RiskRejection,
    RiskService,
    TradeIntent,
)


class Inputs(TypedDict):
    position: str | None
    account: AccountState | None
    config: RiskConfig
    instrument: Instrument | str


def intent(direction: Direction = Direction.LONG) -> TradeIntent:
    return TradeIntent(
        Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT,
        direction,
        Decimal("1.0950") if direction is Direction.LONG else Decimal("1.1050"),
        TargetProposal(multiple=Decimal("1.7")),
    )


def inputs() -> Inputs:
    return {
        "position": "FLAT",
        "account": AccountState("USD", Decimal("10000")),
        "config": RiskConfig(Decimal("0.01")),
        "instrument": Instrument.EUR_USD,
    }


def test_preflight_approves_without_sizing_and_submission_sizes_whole_units() -> None:
    service = RiskService()
    flight = service.evaluate_pre_flight(intent(), **inputs())
    assert flight.approved and flight.quantity is None
    decision = service.evaluate_pre_submission(
        intent(),
        quote=ExecutableQuote(Decimal("1.1000"), Decimal("1.1002")),
        **inputs(),
    )
    assert decision.approved
    assert decision.quantity == Decimal("19230")
    assert decision.actual_risk is not None
    assert decision.risk_budget is not None
    assert decision.actual_risk <= decision.risk_budget
    assert decision.target_price == Decimal("1.10904")


def test_short_uses_bid_entry_and_resolves_target_from_actual_entry() -> None:
    decision = RiskService().evaluate_pre_submission(
        intent(Direction.SHORT),
        quote=ExecutableQuote(Decimal("1.1000"), Decimal("1.1002")),
        **inputs(),
    )
    assert decision.approved and decision.entry_price == Decimal("1.1000")
    assert decision.target_price == Decimal("1.0915")


@pytest.mark.parametrize("field, value, reason", [
    ("position", "LONG", RiskRejection.POSITION_ALREADY_OPEN),
    ("account", None, RiskRejection.ACCOUNT_STATE_UNKNOWN),
    ("instrument", "GBP/USD", RiskRejection.UNSUPPORTED_INSTRUMENT_ECONOMICS),
])
def test_required_financial_rejections(
    field: str, value: object, reason: RiskRejection
) -> None:
    values = inputs()
    values[field] = value  # type: ignore[typeddict-item]
    result = RiskService().evaluate_pre_flight(intent(), **values)
    assert not result.approved and result.rejection is reason


def test_market_movement_invalidates_stop_and_tiny_budget_rejects_quantity() -> None:
    service = RiskService()
    values = inputs()
    invalid = service.evaluate_pre_submission(
        intent(),
        quote=ExecutableQuote(Decimal("1.0900"), Decimal("1.0902")),
        **values,
    )
    assert invalid.rejection is RiskRejection.INVALID_STOP
    values["config"] = RiskConfig(Decimal("0.0000001"))
    tiny = service.evaluate_pre_submission(
        intent(),
        quote=ExecutableQuote(Decimal("1.1000"), Decimal("1.1002")),
        **values,
    )
    assert tiny.rejection is RiskRejection.INVALID_QUANTITY
