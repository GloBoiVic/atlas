"""Internal parsers for provider-format OANDA primitive values."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_TRANSACTION_ID_PATTERN = re.compile(r"[0-9]+")
_INSTRUMENT_PATTERN = re.compile(r"[^\s_]+_[^\s_]+")


class OandaPrimitiveError(ValueError):
    """An OANDA provider primitive had an invalid representation."""


def parse_transaction_id(value: Any) -> str:
    """Return an unchanged numerical provider transaction-ID string."""
    if type(value) is not str or _TRANSACTION_ID_PATTERN.fullmatch(value) is None:
        raise OandaPrimitiveError("invalid OANDA transaction ID")
    return value


def parse_decimal(value: Any) -> Decimal:
    """Return a finite Decimal parsed from an exact provider string."""
    if type(value) is not str:
        raise OandaPrimitiveError("invalid OANDA decimal")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise OandaPrimitiveError("invalid OANDA decimal") from None
    if not result.is_finite():
        raise OandaPrimitiveError("invalid OANDA decimal")
    return result


def parse_instrument(value: Any) -> str:
    """Return an unchanged provider instrument pair string."""
    if type(value) is not str or _INSTRUMENT_PATTERN.fullmatch(value) is None:
        raise OandaPrimitiveError("invalid OANDA instrument")
    return value
