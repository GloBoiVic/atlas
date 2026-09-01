from decimal import Decimal
from typing import Any

import pytest

from backend.integrations.oanda.primitives import (
    OandaPrimitiveError,
    parse_decimal,
    parse_instrument,
    parse_transaction_id,
)


@pytest.mark.parametrize("value", ["0", "000", "1", "001", "999999"])
def test_parse_transaction_id_accepts_numerical_provider_strings(value: str) -> None:
    assert parse_transaction_id(value) == value


@pytest.mark.parametrize(
    "value",
    [None, 42, "", "-1", "+1", "1.0", " 1", "1 "],
)
def test_parse_transaction_id_rejects_non_numerical_provider_values(
    value: Any,
) -> None:
    with pytest.raises(OandaPrimitiveError):
        parse_transaction_id(value)


@pytest.mark.parametrize("value", ["-100", "0", "0.0", "1.25", "1000000"])
def test_parse_decimal_accepts_finite_provider_strings(value: str) -> None:
    assert parse_decimal(value) == Decimal(value)


@pytest.mark.parametrize(
    "value",
    [None, 1, 1.25, Decimal("1"), "", "abc", "NaN", "sNaN", "Infinity", "-Infinity"],
)
def test_parse_decimal_rejects_non_string_or_non_finite_values(value: Any) -> None:
    with pytest.raises(OandaPrimitiveError):
        parse_decimal(value)


@pytest.mark.parametrize("value", ["EUR_USD", "USD_CAD", "XAU_USD"])
def test_parse_instrument_accepts_provider_pair_strings(value: str) -> None:
    assert parse_instrument(value) == value


@pytest.mark.parametrize(
    "value",
    ["", "EUR", "_USD", "EUR_", "EUR_USD_EXTRA", "EUR USD", " EUR_USD", "EUR_USD "],
)
def test_parse_instrument_rejects_invalid_provider_pair_strings(value: str) -> None:
    with pytest.raises(OandaPrimitiveError):
        parse_instrument(value)


def test_primitive_errors_do_not_include_rejected_values() -> None:
    with pytest.raises(OandaPrimitiveError) as error:
        parse_decimal("secret-provider-value")

    assert "secret-provider-value" not in str(error.value)
