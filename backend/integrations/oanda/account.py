"""Read-only binding of one explicitly configured OANDA Practice account."""

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
from backend.domain.market_data import Provider

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
_ACCOUNT_SUMMARY_PATH = "/v3/accounts/{account_id}/summary"
_ACCOUNT_ID_PATTERN = re.compile(r"[^\s/?#\\%-]+(?:-[^\s/?#\\%-]+){3}")
_TRANSACTION_ID_PATTERN = re.compile(r"[0-9]+")


class OandaAccountNormalizationError(OandaNormalizationError):
    """A provider account summary could not become a safe identity."""


@dataclass(frozen=True, slots=True)
class OandaPracticeAccountIdentity:
    """The only account facts accepted from an OANDA Practice summary."""

    provider: Provider
    environment: Literal["PRACTICE"]
    provider_account_id: str
    alias: str | None
    base_currency: Literal["USD"]

    def __post_init__(self) -> None:
        if self.provider is not Provider.OANDA:
            raise OandaAccountNormalizationError(
                "OANDA identity has an invalid provider"
            )
        if self.environment != "PRACTICE":
            raise OandaAccountNormalizationError(
                "OANDA identity has an invalid environment"
            )
        if (
            type(self.provider_account_id) is not str
            or _ACCOUNT_ID_PATTERN.fullmatch(self.provider_account_id) is None
        ):
            raise OandaAccountNormalizationError(
                "OANDA identity has an invalid account ID"
            )
        if self.alias is not None and type(self.alias) is not str:
            raise OandaAccountNormalizationError("OANDA identity has an invalid alias")
        if self.base_currency != "USD":
            raise OandaAccountNormalizationError(
                "OANDA identity has an unsupported base currency"
            )


def _decimal(value: Any, name: str) -> Decimal:
    if type(value) is not str:
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        )
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        ) from None
    if not result.is_finite():
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        )
    return result


def _count(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        )
    return value


def _transaction_id(value: Any, name: str) -> str:
    if type(value) is not str or _TRANSACTION_ID_PATTERN.fullmatch(value) is None:
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        )
    return value


@dataclass(frozen=True, slots=True)
class OandaPracticeAccountSummarySnapshot:
    """Immutable selected facts from one OANDA Practice account summary."""

    identity: OandaPracticeAccountIdentity
    balance: Decimal
    nav: Decimal
    unrealized_pl: Decimal
    margin_used: Decimal
    margin_available: Decimal
    open_trade_count: int
    open_position_count: int
    pending_order_count: int
    last_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not OandaPracticeAccountIdentity:
            raise OandaAccountNormalizationError(
                "OANDA account summary has an invalid identity"
            )
        for name in (
            "balance",
            "nav",
            "unrealized_pl",
            "margin_used",
            "margin_available",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise OandaAccountNormalizationError(
                    f"OANDA account summary has invalid {name}"
                )
        for name in (
            "open_trade_count",
            "open_position_count",
            "pending_order_count",
        ):
            _count(getattr(self, name), name)
        _transaction_id(self.last_transaction_id, "last_transaction_id")


def _valid_account_id(value: str | None) -> bool:
    return value is not None and _ACCOUNT_ID_PATTERN.fullmatch(value) is not None


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


class OandaPracticeAccountValidator:
    """Validate exactly one configured account through its summary endpoint."""

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
        if not (0 < connect_timeout_seconds <= 30) or not (
            0 < read_timeout_seconds <= 120
        ):
            raise OandaConfigurationError("OANDA timeouts are outside bounded limits")
        self._token = token
        self._account_id = account_id
        self._client = client
        self._transport = transport
        self._timeout = httpx.Timeout(
            read=read_timeout_seconds,
            connect=connect_timeout_seconds,
            write=connect_timeout_seconds,
            pool=connect_timeout_seconds,
        )

    def validate(self) -> OandaPracticeAccountIdentity:
        """Return a normalized identity or fail before/after the safe GET."""
        payload, account_id = self._read_payload()
        return self._normalize_identity(payload, account_id)

    def read_summary(self) -> OandaPracticeAccountSummarySnapshot:
        """Read and normalize one immutable Practice account summary."""
        payload, account_id = self._read_payload()
        identity = self._normalize_identity(payload, account_id)
        return self._normalize_summary(payload, identity)

    def _read_payload(self) -> tuple[Mapping[str, Any], str]:
        self._validate_configuration()
        account_id = cast(str, self._account_id)
        owned_client = self._client is None
        client = self._client or httpx.Client(
            transport=self._transport,
            timeout=self._timeout,
            base_url=OANDA_PRACTICE_BASE_URL,
            trust_env=False,
        )
        try:
            return self._request(client, account_id), account_id
        finally:
            if owned_client:
                client.close()

    def _validate_configuration(self) -> None:
        if self._token is None or not self._token.get_secret_value().strip():
            raise OandaConfigurationError("OANDA API token is required")
        if not _valid_account_id(self._account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )

    def _request(self, client: httpx.Client, account_id: str) -> Mapping[str, Any]:
        token = self._token
        if token is None:
            raise OandaConfigurationError("OANDA API token is required")
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept-Datetime-Format": "RFC3339",
        }
        path = _ACCOUNT_SUMMARY_PATH.format(account_id=quote(account_id, safe="-"))
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
                        None, attempts, "OANDA account request failed after retries"
                    ) from None
                sleep(_BACKOFF_SECONDS[attempts - 1])
                continue

            status = response.status_code
            if status in (401, 403):
                raise OandaAuthError(status, attempts, "OANDA authorization failed")
            if status in (400, 404):
                raise OandaRequestError(
                    status, attempts, "OANDA account request was rejected"
                )
            if status == 408 or status == 429 or 500 <= status <= 599:
                if attempts == _MAX_ATTEMPTS:
                    raise OandaRequestError(
                        status,
                        attempts,
                        "OANDA account request failed after retries",
                    )
                delay = _retry_after(response)
                if delay <= 0 or not math.isfinite(delay):
                    delay = _BACKOFF_SECONDS[attempts - 1]
                sleep(delay)
                continue
            if status < 200 or status >= 300:
                raise OandaRequestError(
                    status, attempts, "OANDA account request failed"
                )
            try:
                payload: Any = response.json()
            except ValueError:
                raise OandaRequestError(
                    status, attempts, "OANDA returned invalid account JSON"
                ) from None
            if not isinstance(payload, dict):
                raise OandaAccountNormalizationError(
                    "OANDA account response is not an object"
                )
            return cast(Mapping[str, Any], payload)
        raise AssertionError("retry loop exhausted unexpectedly")

    @staticmethod
    def _account(payload: Mapping[str, Any]) -> dict[str, Any]:
        account_value = payload.get("account")
        if not isinstance(account_value, dict):
            raise OandaAccountNormalizationError(
                "OANDA account response is missing account details"
            )
        return cast(dict[str, Any], account_value)

    @classmethod
    def _normalize_identity(
        cls, payload: Mapping[str, Any], configured_account_id: str
    ) -> OandaPracticeAccountIdentity:
        account = cls._account(payload)
        returned_account_id = account.get("id")
        currency = account.get("currency")
        if not isinstance(returned_account_id, str) or not isinstance(currency, str):
            raise OandaAccountNormalizationError(
                "OANDA account response has invalid required fields"
            )
        if returned_account_id != configured_account_id:
            raise OandaAccountNormalizationError(
                "OANDA returned an account different from the configured account"
            )
        if currency != "USD":
            raise OandaAccountNormalizationError(
                "OANDA account base currency is not supported"
            )

        alias_value = account.get("alias")
        if alias_value is not None and not isinstance(alias_value, str):
            raise OandaAccountNormalizationError("OANDA account alias is invalid")
        return OandaPracticeAccountIdentity(
            provider=Provider.OANDA,
            environment="PRACTICE",
            provider_account_id=configured_account_id,
            alias=alias_value,
            base_currency="USD",
        )

    @classmethod
    def _normalize_summary(
        cls,
        payload: Mapping[str, Any],
        identity: OandaPracticeAccountIdentity,
    ) -> OandaPracticeAccountSummarySnapshot:
        account = cls._account(payload)
        top_level_transaction_id = _transaction_id(
            payload.get("lastTransactionID"), "lastTransactionID"
        )
        nested_transaction_id = _transaction_id(
            account.get("lastTransactionID"), "account.lastTransactionID"
        )
        if nested_transaction_id != top_level_transaction_id:
            raise OandaAccountNormalizationError(
                "OANDA account summary has contradictory transaction IDs"
            )
        return OandaPracticeAccountSummarySnapshot(
            identity=identity,
            balance=_decimal(account.get("balance"), "balance"),
            nav=_decimal(account.get("NAV"), "NAV"),
            unrealized_pl=_decimal(account.get("unrealizedPL"), "unrealizedPL"),
            margin_used=_decimal(account.get("marginUsed"), "marginUsed"),
            margin_available=_decimal(
                account.get("marginAvailable"), "marginAvailable"
            ),
            open_trade_count=_count(account.get("openTradeCount"), "openTradeCount"),
            open_position_count=_count(
                account.get("openPositionCount"), "openPositionCount"
            ),
            pending_order_count=_count(
                account.get("pendingOrderCount"), "pendingOrderCount"
            ),
            last_transaction_id=top_level_transaction_id,
        )


def bind_oanda_practice_account(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeAccountIdentity:
    """Validate the Practice account selected by application settings."""
    return OandaPracticeAccountValidator(
        settings.oanda_api_token,
        settings.oanda_account_id,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).validate()


def read_oanda_practice_account_summary(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeAccountSummarySnapshot:
    """Read the Practice account summary selected by application settings."""
    return OandaPracticeAccountValidator(
        settings.oanda_api_token,
        settings.oanda_account_id,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read_summary()


__all__ = [
    "OandaAccountNormalizationError",
    "OandaPracticeAccountIdentity",
    "OandaPracticeAccountSummarySnapshot",
    "OandaPracticeAccountValidator",
    "bind_oanda_practice_account",
    "read_oanda_practice_account_summary",
]
