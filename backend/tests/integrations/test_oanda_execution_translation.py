from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from backend.domain import Direction
from backend.integrations.oanda import OandaPracticeExecutionInstrument
from backend.integrations.oanda.execution import (
    OandaPracticeEntryTranslationError,
    translate_oanda_practice_market_order,
)
from backend.paper.execution import ExecutionCorrelation
from backend.tests.paper.test_execution_contracts import instruction

ATTEMPT_ID = UUID("12345678-1234-5678-1234-567812345678")


def instrument() -> OandaPracticeExecutionInstrument:
    return OandaPracticeExecutionInstrument(
        provider_instrument="EUR_USD",
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        maximum_order_units=Decimal("1000000"),
        last_transaction_id="42",
    )


def test_long_translation_is_exact_and_does_not_attach_target() -> None:
    payload = translate_oanda_practice_market_order(instruction(), instrument())

    assert payload == {
        "order": {
            "type": "MARKET",
            "instrument": "EUR_USD",
            "units": "19230",
            "timeInForce": "FOK",
            "priceBound": "1.10020",
            "positionFill": "OPEN_ONLY",
            "clientExtensions": {
                "id": "atlas-p04-o-12345678123456781234567812345678",
                "tag": "atlas-paper-04",
            },
            "tradeClientExtensions": {
                "id": "atlas-p04-t-12345678123456781234567812345678"
            },
            "stopLossOnFill": {
                "price": "1.09500",
                "timeInForce": "GTC",
                "clientExtensions": {
                    "id": "atlas-p04-sl-12345678123456781234567812345678"
                },
            },
        }
    }
    assert "takeProfitOnFill" not in payload["order"]


def test_short_translation_uses_negative_units_and_stable_correlation() -> None:
    value = instruction(Direction.SHORT)
    correlation = ExecutionCorrelation.for_attempt(ATTEMPT_ID)

    first = translate_oanda_practice_market_order(value, instrument())
    second = translate_oanda_practice_market_order(
        value, instrument(), correlation=correlation
    )

    assert first == second
    assert first["order"]["units"] == "-19230"
    assert first["order"]["priceBound"] == "1.09980"
    assert first["order"]["stopLossOnFill"]["price"] == "1.10500"


def test_translation_rejects_unrepresentable_price_without_rounding() -> None:
    value = instruction()
    value = replace(
        value,
        approved_entry_price=Decimal("1.100201"),
        pre_submission=replace(value.pre_submission, entry_price=Decimal("1.100201")),
    )

    with pytest.raises(OandaPracticeEntryTranslationError, match="representable"):
        translate_oanda_practice_market_order(value, instrument())
