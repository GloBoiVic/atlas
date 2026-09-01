"""Read-only, provider-specific OANDA Practice open Position observations."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings

from .account import OandaPracticeAccountIdentity, bind_oanda_practice_account
from .source import (
    OANDA_PRACTICE_BASE_URL,
    OandaAuthError,
    OandaConfigurationError,
    OandaNormalizationError,
    OandaRequestError,
)

_MAX_ATTEMPTS = 3
_RETRY_AFTER_CAP_SECONDS = 30.0
_BACKOFF_SECONDS = (0.25, 0.5)
_OPEN_POSITIONS_PATH = "/v3/accounts/{account_id}/openPositions"
_TRANSACTION_ID_PATTERN = re.compile(r"[0-9]+")
_INSTRUMENT_PATTERN = re.compile(r"[^\s_]+_[^\s_]+")


class OandaOpenPositionNormalizationError(OandaNormalizationError):
    """An OANDA open-Positions observation could not become a safe inventory."""


def _transaction_id(value: Any) -> str:
    if type(value) is not str or _TRANSACTION_ID_PATTERN.fullmatch(value) is None:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Positions response has invalid lastTransactionID"
        )
    return value


def _decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not str:
        raise OandaOpenPositionNormalizationError(
            f"OANDA open Position has invalid {name}"
        )
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise OandaOpenPositionNormalizationError(
            f"OANDA open Position has invalid {name}"
        ) from None
    _valid_decimal(result, name, positive=positive)
    return result


def _valid_decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or (positive and value <= 0):
        raise OandaOpenPositionNormalizationError(
            f"OANDA open Position has invalid {name}"
        )
    return value


def _instrument(value: Any) -> str:
    if type(value) is not str or _INSTRUMENT_PATTERN.fullmatch(value) is None:
        raise OandaOpenPositionNormalizationError(
            "OANDA open Position has invalid instrument"
        )
    return value


def _retry_after(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After")
    if value is None:
        return 0.0
    try:
        seconds = float(value)
    except ValueError:
        seconds = -1.0
    if math.isfinite(seconds) and seconds >= 0:
        return min(seconds, _RETRY_AFTER_CAP_SECONDS)
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            return 0.0
        seconds = (retry_at.astimezone(UTC) - datetime.now(UTC)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not math.isfinite(seconds) or seconds < 0:
        return 0.0
    return min(seconds, _RETRY_AFTER_CAP_SECONDS)


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
        if not (0 < connect_timeout_seconds <= 30) or not (
            0 < read_timeout_seconds <= 120
        ):
            raise OandaConfigurationError("OANDA timeouts are outside bounded limits")
        if type(identity) is not OandaPracticeAccountIdentity:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position reader requires a validated account identity"
            )
        self._token = token
        self._identity = identity
        self._client = client
        self._transport = transport
        self._timeout = httpx.Timeout(
            read=read_timeout_seconds,
            connect=connect_timeout_seconds,
            write=connect_timeout_seconds,
            pool=connect_timeout_seconds,
        )

    def read(self) -> OandaPracticeOpenPositionInventory:
        """Read and normalize one immutable open-Positions observation."""
        payload = self._read_payload()
        return self._normalize_inventory(payload)

    def _read_payload(self) -> Mapping[str, Any]:
        self._validate_configuration()
        owned_client = self._client is None
        client = self._client or httpx.Client(
            transport=self._transport,
            timeout=self._timeout,
            base_url=OANDA_PRACTICE_BASE_URL,
            trust_env=False,
        )
        try:
            return self._request(client)
        finally:
            if owned_client:
                client.close()

    def _validate_configuration(self) -> None:
        if self._token is None or not self._token.get_secret_value().strip():
            raise OandaConfigurationError("OANDA API token is required")

    def _request(self, client: httpx.Client) -> Mapping[str, Any]:
        token = self._token
        if token is None:
            raise OandaConfigurationError("OANDA API token is required")
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept-Datetime-Format": "RFC3339",
        }
        path = _OPEN_POSITIONS_PATH.format(
            account_id=quote(self._identity.provider_account_id, safe="-")
        )
        attempts = 0
        while attempts < _MAX_ATTEMPTS:
            attempts += 1
            try:
                response = client.get(
                    f"{OANDA_PRACTICE_BASE_URL}{path}",
                    headers=headers,
                    timeout=self._timeout,
                )
            except httpx.RequestError:
                if attempts == _MAX_ATTEMPTS:
                    raise OandaRequestError(
                        None,
                        attempts,
                        "OANDA open Positions request failed after retries",
                    ) from None
                sleep(_BACKOFF_SECONDS[attempts - 1])
                continue

            status = response.status_code
            if status in (401, 403):
                raise OandaAuthError(status, attempts, "OANDA authorization failed")
            if status in (400, 404):
                raise OandaRequestError(
                    status, attempts, "OANDA open Positions request was rejected"
                )
            if status == 408 or status == 429 or 500 <= status <= 599:
                if attempts == _MAX_ATTEMPTS:
                    raise OandaRequestError(
                        status,
                        attempts,
                        "OANDA open Positions request failed after retries",
                    )
                delay = _retry_after(response)
                if delay <= 0 or not math.isfinite(delay):
                    delay = _BACKOFF_SECONDS[attempts - 1]
                sleep(delay)
                continue
            if status < 200 or status >= 300:
                raise OandaRequestError(
                    status, attempts, "OANDA open Positions request failed"
                )
            try:
                payload: Any = response.json()
            except ValueError:
                raise OandaRequestError(
                    status,
                    attempts,
                    "OANDA returned invalid open Positions JSON",
                ) from None
            if not isinstance(payload, dict):
                raise OandaOpenPositionNormalizationError(
                    "OANDA open Positions response is not an object"
                )
            return cast(Mapping[str, Any], payload)
        raise AssertionError("retry loop exhausted unexpectedly")

    def _normalize_inventory(
        self, payload: Mapping[str, Any]
    ) -> OandaPracticeOpenPositionInventory:
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
            normalized.append(self._normalize_position(position_item, instrument))
        return OandaPracticeOpenPositionInventory(
            identity=self._identity,
            positions=tuple(normalized),
            last_transaction_id=_transaction_id(payload.get("lastTransactionID")),
        )

    @staticmethod
    def _normalize_position(
        item: Mapping[str, Any], instrument: str
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
            long=OandaPracticeOpenPositionReader._normalize_side(
                cast(Mapping[str, Any], long_value), side="long"
            ),
            short=OandaPracticeOpenPositionReader._normalize_side(
                cast(Mapping[str, Any], short_value), side="short"
            ),
        )

    @staticmethod
    def _normalize_side(
        item: Mapping[str, Any], *, side: str
    ) -> OandaPracticePositionSide:
        units = _decimal(item.get("units"), "units")
        if side == "long" and units < 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has negative long units"
            )
        if side == "short" and units > 0:
            raise OandaOpenPositionNormalizationError(
                "OANDA open Position has positive short units"
            )
        if "averagePrice" in item:
            average_price = _decimal(
                item["averagePrice"], "averagePrice", positive=True
            )
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
    "read_oanda_practice_open_position_inventory",
]
