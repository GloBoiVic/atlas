"""Read-only binding of one explicitly configured OANDA Practice account."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
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
            payload = self._request(client, account_id)
            return self._normalize(payload, account_id)
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
    def _normalize(
        payload: Mapping[str, Any], configured_account_id: str
    ) -> OandaPracticeAccountIdentity:
        account_value = payload.get("account")
        if not isinstance(account_value, dict):
            raise OandaAccountNormalizationError(
                "OANDA account response is missing account details"
            )
        account = cast(dict[str, Any], account_value)
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


__all__ = [
    "OandaAccountNormalizationError",
    "OandaPracticeAccountIdentity",
    "OandaPracticeAccountValidator",
    "bind_oanda_practice_account",
]
