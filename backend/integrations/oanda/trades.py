"""Read-only, provider-specific OANDA Practice open Trade observations."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, Literal, cast
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
_OPEN_TRADES_PATH = "/v3/accounts/{account_id}/openTrades"
_POSITIVE_INTEGER_PATTERN = re.compile(r"[0-9]+")
_TRANSACTION_ID_PATTERN = re.compile(r"[0-9]+")
_INSTRUMENT_PATTERN = re.compile(r"[^\s_]+_[^\s_]+")
_RFC3339_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:"
    r"[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})"
)


class OandaOpenTradeNormalizationError(OandaNormalizationError):
    """An OANDA open-Trades observation could not become a safe inventory."""


def _positive_integer(value: Any, name: str) -> str:
    if (
        type(value) is not str
        or _POSITIVE_INTEGER_PATTERN.fullmatch(value) is None
        or not any(character != "0" for character in value)
    ):
        raise OandaOpenTradeNormalizationError(
            f"OANDA open Trades response has invalid {name}"
        )
    return value


def _transaction_id(value: Any) -> str:
    if type(value) is not str or _TRANSACTION_ID_PATTERN.fullmatch(value) is None:
        raise OandaOpenTradeNormalizationError(
            "OANDA open Trades response has invalid lastTransactionID"
        )
    return value


def _decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not str:
        raise OandaOpenTradeNormalizationError(f"OANDA open Trade has invalid {name}")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise OandaOpenTradeNormalizationError(
            f"OANDA open Trade has invalid {name}"
        ) from None
    _valid_decimal(result, name, positive=positive)
    return result


def _valid_decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or (positive and value <= 0):
        raise OandaOpenTradeNormalizationError(f"OANDA open Trade has invalid {name}")
    return value


def _instrument(value: Any) -> str:
    if type(value) is not str or _INSTRUMENT_PATTERN.fullmatch(value) is None:
        raise OandaOpenTradeNormalizationError(
            "OANDA open Trade has invalid instrument"
        )
    return value


def _timestamp(value: Any) -> datetime:
    if type(value) is not str or _RFC3339_PATTERN.fullmatch(value) is None:
        raise OandaOpenTradeNormalizationError("OANDA open Trade has invalid openTime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise OandaOpenTradeNormalizationError(
            "OANDA open Trade has invalid openTime"
        ) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OandaOpenTradeNormalizationError(
            "OANDA open Trade openTime is not timezone-aware"
        )
    return parsed.astimezone(UTC)


def _trade_id_sort_key(provider_trade_id: str) -> tuple[int, str, str]:
    significant = provider_trade_id.lstrip("0")
    return len(significant), significant, provider_trade_id


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
class OandaPracticeOpenTrade:
    """The approved provider-native facts for one currently open Trade."""

    provider_trade_id: str
    provider_instrument: str
    open_time: datetime
    open_price: Decimal
    current_units: Decimal
    state: Literal["OPEN", "CLOSE_WHEN_TRADEABLE"]
    unrealized_pl: Decimal

    def __post_init__(self) -> None:
        _positive_integer(self.provider_trade_id, "id")
        _instrument(self.provider_instrument)
        if type(self.open_time) is not datetime:
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade has invalid openTime"
            )
        if self.open_time.tzinfo is None or self.open_time.utcoffset() is None:
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade openTime is not timezone-aware"
            )
        object.__setattr__(self, "open_time", self.open_time.astimezone(UTC))
        _valid_decimal(self.open_price, "price", positive=True)
        units = _valid_decimal(self.current_units, "currentUnits")
        if units == 0:
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade has invalid currentUnits"
            )
        if self.state not in ("OPEN", "CLOSE_WHEN_TRADEABLE"):
            raise OandaOpenTradeNormalizationError("OANDA open Trade has invalid state")
        _valid_decimal(self.unrealized_pl, "unrealizedPL")


@dataclass(frozen=True, slots=True)
class OandaPracticeOpenTradeInventory:
    """An immutable observation of one validated account's open Trades."""

    identity: OandaPracticeAccountIdentity
    trades: tuple[OandaPracticeOpenTrade, ...]
    last_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not OandaPracticeAccountIdentity:
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade inventory has an invalid identity"
            )
        if type(self.trades) is not tuple or any(
            type(trade) is not OandaPracticeOpenTrade for trade in self.trades
        ):
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade inventory has invalid trades"
            )
        trade_ids = [trade.provider_trade_id for trade in self.trades]
        if len(trade_ids) != len(set(trade_ids)):
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade inventory contains duplicate Trade IDs"
            )
        ordered = tuple(
            sorted(
                self.trades,
                key=lambda trade: _trade_id_sort_key(trade.provider_trade_id),
            )
        )
        object.__setattr__(self, "trades", ordered)
        _transaction_id(self.last_transaction_id)


class OandaPracticeOpenTradeReader:
    """Read only the open Trades for an already validated Practice identity."""

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
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trade reader requires a validated account identity"
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

    def read(self) -> OandaPracticeOpenTradeInventory:
        """Read and normalize one immutable open-Trades observation."""
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
        path = _OPEN_TRADES_PATH.format(
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
                        "OANDA open Trades request failed after retries",
                    ) from None
                sleep(_BACKOFF_SECONDS[attempts - 1])
                continue

            status = response.status_code
            if status in (401, 403):
                raise OandaAuthError(status, attempts, "OANDA authorization failed")
            if status in (400, 404):
                raise OandaRequestError(
                    status, attempts, "OANDA open Trades request was rejected"
                )
            if status == 408 or status == 429 or 500 <= status <= 599:
                if attempts == _MAX_ATTEMPTS:
                    raise OandaRequestError(
                        status,
                        attempts,
                        "OANDA open Trades request failed after retries",
                    )
                delay = _retry_after(response)
                if delay <= 0 or not math.isfinite(delay):
                    delay = _BACKOFF_SECONDS[attempts - 1]
                sleep(delay)
                continue
            if status < 200 or status >= 300:
                raise OandaRequestError(
                    status, attempts, "OANDA open Trades request failed"
                )
            try:
                payload: Any = response.json()
            except ValueError:
                raise OandaRequestError(
                    status,
                    attempts,
                    "OANDA returned invalid open Trades JSON",
                ) from None
            if not isinstance(payload, dict):
                raise OandaOpenTradeNormalizationError(
                    "OANDA open Trades response is not an object"
                )
            return cast(Mapping[str, Any], payload)
        raise AssertionError("retry loop exhausted unexpectedly")

    def _normalize_inventory(
        self, payload: Mapping[str, Any]
    ) -> OandaPracticeOpenTradeInventory:
        trades_value = payload.get("trades")
        if not isinstance(trades_value, list):
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trades response has invalid trades"
            )
        raw_trades = cast(list[Any], trades_value)
        if any(not isinstance(item, dict) for item in raw_trades):
            raise OandaOpenTradeNormalizationError(
                "OANDA open Trades response has invalid trades"
            )
        normalized: list[OandaPracticeOpenTrade] = []
        seen_ids: set[str] = set()
        for item in raw_trades:
            trade_item = cast(dict[str, Any], item)
            trade_id = _positive_integer(trade_item.get("id"), "id")
            if trade_id in seen_ids:
                raise OandaOpenTradeNormalizationError(
                    "OANDA open Trade inventory contains duplicate Trade IDs"
                )
            seen_ids.add(trade_id)
            normalized.append(self._normalize_trade(trade_item))
        return OandaPracticeOpenTradeInventory(
            identity=self._identity,
            trades=tuple(normalized),
            last_transaction_id=_transaction_id(payload.get("lastTransactionID")),
        )

    @staticmethod
    def _normalize_trade(item: Mapping[str, Any]) -> OandaPracticeOpenTrade:
        state = item.get("state")
        if state not in ("OPEN", "CLOSE_WHEN_TRADEABLE"):
            raise OandaOpenTradeNormalizationError("OANDA open Trade has invalid state")
        return OandaPracticeOpenTrade(
            provider_trade_id=_positive_integer(item.get("id"), "id"),
            provider_instrument=_instrument(item.get("instrument")),
            open_time=_timestamp(item.get("openTime")),
            open_price=_decimal(item.get("price"), "price", positive=True),
            current_units=_decimal(item.get("currentUnits"), "currentUnits"),
            state=state,
            unrealized_pl=_decimal(item.get("unrealizedPL"), "unrealizedPL"),
        )


def read_oanda_practice_open_trade_inventory(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeOpenTradeInventory:
    """Validate settings' account, then read its independent open-Trades view."""
    identity = bind_oanda_practice_account(
        settings,
        client=client,
        transport=transport,
    )
    return OandaPracticeOpenTradeReader(
        settings.oanda_api_token,
        identity,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


__all__ = [
    "OandaOpenTradeNormalizationError",
    "OandaPracticeOpenTrade",
    "OandaPracticeOpenTradeInventory",
    "OandaPracticeOpenTradeReader",
    "read_oanda_practice_open_trade_inventory",
]
