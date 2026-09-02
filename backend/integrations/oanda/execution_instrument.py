"""Read-only OANDA Practice EUR/USD execution capability and exactness gates."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Literal, NoReturn, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings

from .account import is_valid_oanda_practice_account_id
from .primitives import OandaPrimitiveError, parse_decimal, parse_transaction_id
from .request import OandaObservationRequester, validate_token
from .source import OandaConfigurationError, OandaNormalizationError

_INSTRUMENT_PATH = "/v3/accounts/{account_id}/instruments"
_REQUEST_ERROR_SUBJECT = "execution instrument"
_SUPPORTED_INSTRUMENT = "EUR_USD"
_SUPPORTED_DISPLAY_PRECISION = 5
_SUPPORTED_TRADE_UNITS_PRECISION = 0


class OandaPracticeExecutionInstrumentNormalizationError(OandaNormalizationError):
    """An OANDA instrument capability could not become safe execution metadata."""


def _invalid(detail: str) -> NoReturn:
    raise OandaPracticeExecutionInstrumentNormalizationError(
        f"OANDA execution instrument {detail}"
    )


def _parse_positive_decimal(value: Any, name: str) -> Decimal:
    try:
        result = parse_decimal(value)
    except OandaPrimitiveError:
        _invalid(f"has invalid {name}")
    if result <= 0:
        _invalid(f"has invalid {name}")
    return result


def _parse_nonnegative_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        _invalid(f"has invalid {name}")
    return value


def _parse_transaction_id(value: Any) -> str:
    try:
        return parse_transaction_id(value)
    except OandaPrimitiveError:
        _invalid("has invalid lastTransactionID")


def _exact_at_scale(value: Decimal, precision: int) -> bool:
    if type(value) is not Decimal or not value.is_finite():
        return False
    quantum = Decimal(1).scaleb(-precision)
    digits = len(value.as_tuple().digits)
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        return False
    context_precision = max(64, digits + abs(exponent) + precision + 4)
    try:
        with localcontext() as context:
            context.prec = context_precision
            return value.quantize(quantum) == value
    except InvalidOperation:
        return False


def _serialize_exact(value: Decimal, precision: int, name: str) -> str:
    if not _exact_at_scale(value, precision):
        raise OandaPracticeExecutionInstrumentNormalizationError(
            f"OANDA execution instrument {name} is not exactly representable"
        )
    # The exactness check above makes this formatting operation incapable of
    # changing the mathematical value; it only supplies provider scale.
    return format(value, f".{precision}f")


@dataclass(frozen=True, slots=True)
class OandaPracticeExecutionInstrument:
    """Observed EUR/USD precision and quantity bounds for one account."""

    provider_instrument: Literal["EUR_USD"]
    display_precision: int
    trade_units_precision: int
    minimum_trade_size: Decimal
    maximum_order_units: Decimal
    last_transaction_id: str

    def __post_init__(self) -> None:
        if self.provider_instrument != _SUPPORTED_INSTRUMENT:
            _invalid("has an unsupported instrument")
        if self.display_precision != _SUPPORTED_DISPLAY_PRECISION:
            _invalid("has unsupported displayPrecision")
        if self.trade_units_precision != _SUPPORTED_TRADE_UNITS_PRECISION:
            _invalid("has unsupported tradeUnitsPrecision")
        _parse_nonnegative_int(self.display_precision, "displayPrecision")
        _parse_nonnegative_int(self.trade_units_precision, "tradeUnitsPrecision")
        if (
            type(self.minimum_trade_size) is not Decimal
            or not self.minimum_trade_size.is_finite()
        ):
            _invalid("has invalid minimumTradeSize")
        if (
            type(self.maximum_order_units) is not Decimal
            or not self.maximum_order_units.is_finite()
        ):
            _invalid("has invalid maximumOrderUnits")
        if self.minimum_trade_size <= 0:
            _invalid("has invalid minimumTradeSize")
        if self.maximum_order_units <= 0:
            _invalid("has invalid maximumOrderUnits")
        if self.minimum_trade_size > self.maximum_order_units:
            _invalid("has contradictory quantity bounds")
        _parse_transaction_id(self.last_transaction_id)
        if not _exact_at_scale(self.minimum_trade_size, self.trade_units_precision):
            _invalid("has an unrepresentable minimumTradeSize")
        if not _exact_at_scale(self.maximum_order_units, self.trade_units_precision):
            _invalid("has an unrepresentable maximumOrderUnits")

    def serialize_price(self, value: Decimal) -> str:
        """Serialize a positive price only when no rounding is necessary."""
        if type(value) is not Decimal or not value.is_finite() or value <= 0:
            raise OandaPracticeExecutionInstrumentNormalizationError(
                "OANDA execution instrument price is invalid"
            )
        return _serialize_exact(value, self.display_precision, "price")

    def serialize_quantity(self, value: Decimal) -> str:
        """Serialize a positive quantity only when precision and bounds pass."""
        if type(value) is not Decimal or not value.is_finite() or value <= 0:
            raise OandaPracticeExecutionInstrumentNormalizationError(
                "OANDA execution instrument quantity is invalid"
            )
        if value < self.minimum_trade_size or value > self.maximum_order_units:
            raise OandaPracticeExecutionInstrumentNormalizationError(
                "OANDA execution instrument quantity is outside provider bounds"
            )
        return _serialize_exact(value, self.trade_units_precision, "quantity")

    def validate_price(self, value: Decimal) -> str:
        """Validate and return the exact provider price representation."""
        return self.serialize_price(value)

    def validate_quantity(self, value: Decimal) -> str:
        """Validate and return the exact provider quantity representation."""
        return self.serialize_quantity(value)


def _normalize_execution_instrument(
    payload: Mapping[str, Any],
) -> OandaPracticeExecutionInstrument:
    instruments_value = payload.get("instruments")
    if not isinstance(instruments_value, list):
        _invalid("response must contain exactly one instrument")
    raw_instruments = cast(list[Any], instruments_value)
    if len(raw_instruments) != 1:
        _invalid("response must contain exactly one instrument")
    item = raw_instruments[0]
    if not isinstance(item, dict):
        _invalid("response has invalid instrument metadata")
    instrument = cast(dict[str, Any], item)
    if instrument.get("name") != _SUPPORTED_INSTRUMENT:
        _invalid("response has an unsupported instrument")
    return OandaPracticeExecutionInstrument(
        provider_instrument=_SUPPORTED_INSTRUMENT,
        display_precision=_parse_nonnegative_int(
            instrument.get("displayPrecision"), "displayPrecision"
        ),
        trade_units_precision=_parse_nonnegative_int(
            instrument.get("tradeUnitsPrecision"), "tradeUnitsPrecision"
        ),
        minimum_trade_size=_parse_positive_decimal(
            instrument.get("minimumTradeSize"), "minimumTradeSize"
        ),
        maximum_order_units=_parse_positive_decimal(
            instrument.get("maximumOrderUnits"), "maximumOrderUnits"
        ),
        last_transaction_id=_parse_transaction_id(payload.get("lastTransactionID")),
    )


class OandaPracticeExecutionInstrumentReader:
    """Read the exact EUR/USD instrument capability for one account."""

    def __init__(
        self,
        token: SecretStr | None,
        account_id: str | None,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
    ) -> None:
        self._token = token
        self._account_id = account_id
        self._requester = OandaObservationRequester(
            token,
            client=client,
            transport=transport,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )

    def read(self) -> OandaPracticeExecutionInstrument:
        validate_token(self._token)
        account_id = self._configured_account_id()
        path = _INSTRUMENT_PATH.format(account_id=quote(account_id, safe="-"))
        payload = self._requester.get_json(
            path,
            error_subject=_REQUEST_ERROR_SUBJECT,
            params={"instruments": _SUPPORTED_INSTRUMENT},
        )
        if not isinstance(payload, dict):
            _invalid("response is not an object")
        return _normalize_execution_instrument(cast(Mapping[str, Any], payload))

    def _configured_account_id(self) -> str:
        if not is_valid_oanda_practice_account_id(self._account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )
        return cast(str, self._account_id)


def read_oanda_practice_execution_instrument(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeExecutionInstrument:
    """Read the configured account's EUR/USD execution metadata."""
    return OandaPracticeExecutionInstrumentReader(
        settings.oanda_api_token,
        settings.oanda_account_id,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


__all__ = [
    "OandaPracticeExecutionInstrument",
    "OandaPracticeExecutionInstrumentNormalizationError",
    "OandaPracticeExecutionInstrumentReader",
    "read_oanda_practice_execution_instrument",
]
