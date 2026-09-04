"""Read-only, provider-specific OANDA Practice open Position observations."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings

from .account import OandaPracticeAccountIdentity, bind_oanda_practice_account
from .primitives import (
    OandaPrimitiveError,
    parse_decimal,
    parse_instrument,
    parse_transaction_id,
)
from .request import OandaObservationRequester, validate_token
from .source import (
    OandaNormalizationError,
)

_OPEN_POSITIONS_PATH = "/v3/accounts/{account_id}/openPositions"
_REQUEST_ERROR_SUBJECT = "open Positions"


class OandaOpenPositionNormalizationError(OandaNormalizationError):
    """An OANDA open-Positions observation could not become a safe inventory."""


def _transaction_id(value: Any) -> str:
    try:
        return parse_transaction_id(value)
    except OandaPrimitiveError:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Positions response has invalid lastTransactionID"
        ) from None


def _decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    try:
        result = parse_decimal(value)
    except OandaPrimitiveError:
        raise OandaOpenPositionNormalizationError(
            f"OANDA open Position has invalid {name}"
        ) from None
    return _valid_decimal(result, name, positive=positive)


def _valid_decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or (positive and value <= 0):
        raise OandaOpenPositionNormalizationError(
            f"OANDA open Position has invalid {name}"
        )
    return value


def _instrument(value: Any) -> str:
    try:
        return parse_instrument(value)
    except OandaPrimitiveError:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position has invalid instrument"
        ) from None


@dataclass(frozen=True, slots=True)
class OandaPracticePositionSide:
    """The retained provider facts for one OANDA Position side."""

    units: Decimal
    average_price: Decimal | None
    unrealized_pl: Decimal

    def __post_init__(self) -> None:
        _valid_decimal(self.units, "units")
        if self.average_price is not None:
            _valid_decimal(self.average_price, "averagePrice", positive=True)
        _valid_decimal(self.unrealized_pl, "unrealizedPL")


@dataclass(frozen=True, slots=True)
class OandaPracticeOpenPosition:
    """The retained provider facts for one currently open Position."""

    provider_instrument: str
    unrealized_pl: Decimal
    long: OandaPracticePositionSide
    short: OandaPracticePositionSide

    def __post_init__(self) -> None:
        _instrument(self.provider_instrument)
        _valid_decimal(self.unrealized_pl, "unrealizedPL")
        if type(self.long) is not OandaPracticePositionSide:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has invalid long side"
            )
        if type(self.short) is not OandaPracticePositionSide:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has invalid short side"
            )
        if self.long.units < 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has negative long units"
            )
        if self.short.units > 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has positive short units"
            )
        if self.long.units != 0 and self.long.average_price is None:
            raise OandaOpenPositionNormalizationError(
                "OANDA exposed long Position side is missing averagePrice"
            )
        if self.short.units != 0 and self.short.average_price is None:
            raise OandaOpenPositionNormalizationError(
                "OANDA exposed short Position side is missing averagePrice"
            )
        if self.long.units == 0 and self.short.units == 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has no exposed side"
            )


@dataclass(frozen=True, slots=True)
class OandaPracticeOpenPositionInventory:
    """An immutable observation of one validated account's open Positions."""

    identity: OandaPracticeAccountIdentity
    positions: tuple[OandaPracticeOpenPosition, ...]
    last_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not OandaPracticeAccountIdentity:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position inventory has an invalid identity"
            )
        if type(self.positions) is not tuple or any(
            type(position) is not OandaPracticeOpenPosition
            for position in self.positions
        ):
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position inventory has invalid positions"
            )
        instruments = [position.provider_instrument for position in self.positions]
        if len(instruments) != len(set(instruments)):
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position inventory contains duplicate instruments"
            )
        object.__setattr__(
            self,
            "positions",
            tuple(
                sorted(
                    self.positions, key=lambda position: position.provider_instrument
                )
            ),
        )
        _transaction_id(self.last_transaction_id)


class OandaPracticeOpenPositionReader:
    """Read only the open Positions for an already validated Practice identity."""

    def __init__(
        self,
        token: SecretStr | None,
        identity: OandaPracticeAccountIdentity,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
    ) -> None:
        self._requester = OandaObservationRequester(
            token,
            client=client,
            transport=transport,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )
        if type(identity) is not OandaPracticeAccountIdentity:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position reader requires a validated account identity"
            )
        self._token = token
        self._identity = identity

    def read(self) -> OandaPracticeOpenPositionInventory:
        """Read and normalize one immutable open-Positions observation."""
        payload = self._read_payload()
        return self._normalize_inventory(payload)

    def _read_payload(self) -> Mapping[str, Any]:
        self._validate_configuration()
        path = _OPEN_POSITIONS_PATH.format(
            account_id=quote(self._identity.provider_account_id, safe="-")
        )
        payload = self._requester.get_json(path, error_subject=_REQUEST_ERROR_SUBJECT)
        if not isinstance(payload, dict):
            raise OandaOpenPositionNormalizationError(
                "OANDA open Positions response is not an object"
            )
        return cast(Mapping[str, Any], payload)

    def _validate_configuration(self) -> None:
        validate_token(self._token)

    def _normalize_inventory(
        self, payload: Mapping[str, Any]
    ) -> OandaPracticeOpenPositionInventory:
        return normalize_oanda_practice_open_position_inventory(payload, self._identity)

    @staticmethod
    def _normalize_position(
        item: Mapping[str, Any], instrument: str
    ) -> OandaPracticeOpenPosition:
        return _normalize_position(item, instrument)

    @staticmethod
    def _normalize_side(
        item: Mapping[str, Any], *, side: str
    ) -> OandaPracticePositionSide:
        return _normalize_side(item, side=side)


def normalize_oanda_practice_open_position_inventory(
    payload: Mapping[str, Any], identity: OandaPracticeAccountIdentity
) -> OandaPracticeOpenPositionInventory:
    """Normalize open Positions without issuing a separate observation GET."""
    if type(identity) is not OandaPracticeAccountIdentity:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position inventory has an invalid identity"
        )
    positions_value = payload.get("positions")
    if not isinstance(positions_value, list):
        raise OandaOpenPositionNormalizationError(
            "OANDA open Positions response has invalid positions"
        )
    raw_positions = cast(list[Any], positions_value)
    if any(not isinstance(item, dict) for item in raw_positions):
        raise OandaOpenPositionNormalizationError(
            "OANDA open Positions response has invalid positions"
        )
    normalized: list[OandaPracticeOpenPosition] = []
    seen_instruments: set[str] = set()
    for item in raw_positions:
        position_item = cast(dict[str, Any], item)
        instrument = _instrument(position_item.get("instrument"))
        if instrument in seen_instruments:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position inventory contains duplicate instruments"
            )
        seen_instruments.add(instrument)
        normalized.append(_normalize_position(position_item, instrument))
    return OandaPracticeOpenPositionInventory(
        identity=identity,
        positions=tuple(normalized),
        last_transaction_id=_transaction_id(payload.get("lastTransactionID")),
    )


def normalize_oanda_practice_account_position_inventory(
    payload: Mapping[str, Any], identity: OandaPracticeAccountIdentity
) -> OandaPracticeOpenPositionInventory:
    """Project lifetime Account Details Positions into current open Positions.

    This is intentionally separate from the strict ``/openPositions`` normalizer:
    Account Details can retain zero/zero historical Position representations.
    """
    if type(identity) is not OandaPracticeAccountIdentity:
        raise OandaOpenPositionNormalizationError(
            "OANDA Account Details Position inventory has an invalid identity"
        )
    positions_value = payload.get("positions")
    if not isinstance(positions_value, list):
        raise OandaOpenPositionNormalizationError(
            "OANDA Account Details response has invalid positions"
        )
    raw_positions = cast(list[Any], positions_value)
    if any(not isinstance(item, dict) for item in raw_positions):
        raise OandaOpenPositionNormalizationError(
            "OANDA Account Details response has invalid positions"
        )

    normalized: list[OandaPracticeOpenPosition] = []
    seen_instruments: set[str] = set()
    for item in raw_positions:
        position_item = cast(dict[str, Any], item)
        instrument = _instrument(position_item.get("instrument"))
        if instrument in seen_instruments:
            raise OandaOpenPositionNormalizationError(
                "OANDA Account Details Position inventory contains duplicate "
                "instruments"
            )
        seen_instruments.add(instrument)

        long_value = position_item.get("long")
        short_value = position_item.get("short")
        if not isinstance(long_value, dict):
            raise OandaOpenPositionNormalizationError(
                "OANDA Account Details Position has invalid long side"
            )
        if not isinstance(short_value, dict):
            raise OandaOpenPositionNormalizationError(
                "OANDA Account Details Position has invalid short side"
            )
        long_item = cast(dict[str, Any], long_value)
        short_item = cast(dict[str, Any], short_value)

        # Parse and sign-check both exposure facts before deciding that a
        # lifetime Position is closed.  A malformed unit must never be hidden
        # by the other side being zero.
        long_units = _decimal(long_item.get("units"), "long.units")
        short_units = _decimal(short_item.get("units"), "short.units")
        if long_units < 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA Account Details Position has negative long units"
            )
        if short_units > 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA Account Details Position has positive short units"
            )
        if long_units == 0 and short_units == 0:
            continue

        normalized.append(
            _normalize_position(
                position_item,
                instrument,
                long_units=long_units,
                short_units=short_units,
            )
        )

    return OandaPracticeOpenPositionInventory(
        identity=identity,
        positions=tuple(normalized),
        last_transaction_id=_transaction_id(payload.get("lastTransactionID")),
    )


def _normalize_position(
    item: Mapping[str, Any],
    instrument: str,
    *,
    long_units: Decimal | None = None,
    short_units: Decimal | None = None,
) -> OandaPracticeOpenPosition:
    long_value = item.get("long")
    short_value = item.get("short")
    if not isinstance(long_value, dict):
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position has invalid long side"
        )
    if not isinstance(short_value, dict):
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position has invalid short side"
        )
    return OandaPracticeOpenPosition(
        provider_instrument=instrument,
        unrealized_pl=_decimal(item.get("unrealizedPL"), "unrealizedPL"),
        long=_normalize_side(
            cast(Mapping[str, Any], long_value), side="long", units=long_units
        ),
        short=_normalize_side(
            cast(Mapping[str, Any], short_value), side="short", units=short_units
        ),
    )


def _normalize_side(
    item: Mapping[str, Any], *, side: str, units: Decimal | None = None
) -> OandaPracticePositionSide:
    units = units if units is not None else _decimal(item.get("units"), "units")
    if side == "long" and units < 0:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position has negative long units"
        )
    if side == "short" and units > 0:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position has positive short units"
        )
    if "averagePrice" in item:
        average_price = _decimal(item["averagePrice"], "averagePrice", positive=True)
    elif units == 0:
        average_price = None
    else:
        raise OandaOpenPositionNormalizationError(
            f"OANDA exposed {side} Position side is missing averagePrice"
        )
    return OandaPracticePositionSide(
        units=units,
        average_price=average_price,
        unrealized_pl=_decimal(item.get("unrealizedPL"), "unrealizedPL"),
    )


def read_oanda_practice_open_position_inventory(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeOpenPositionInventory:
    """Validate settings' account, then read its independent open-Positions view."""
    identity = bind_oanda_practice_account(
        settings,
        client=client,
        transport=transport,
    )
    return OandaPracticeOpenPositionReader(
        settings.oanda_api_token,
        identity,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


__all__ = [
    "OandaOpenPositionNormalizationError",
    "OandaPracticeOpenPosition",
    "OandaPracticeOpenPositionInventory",
    "OandaPracticeOpenPositionReader",
    "OandaPracticePositionSide",
    "normalize_oanda_practice_account_position_inventory",
    "normalize_oanda_practice_open_position_inventory",
    "read_oanda_practice_open_position_inventory",
]
