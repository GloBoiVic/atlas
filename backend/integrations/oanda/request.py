"""Internal request mechanics for read-only OANDA Practice observations."""

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, cast

import httpx
from pydantic import SecretStr

from .source import (
    OANDA_PRACTICE_BASE_URL,
    OandaAuthError,
    OandaConfigurationError,
    OandaRequestError,
)

_MAX_ATTEMPTS = 3
_RETRY_AFTER_CAP_SECONDS = 30.0
_BACKOFF_SECONDS = (0.25, 0.5)


def validate_token(token: SecretStr | None) -> None:
    """Reject a missing or blank token without exposing or changing it."""
    if token is None or not token.get_secret_value().strip():
        raise OandaConfigurationError("OANDA API token is required")


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


class OandaObservationRequester:
    """Execute one safe authenticated GET for an OANDA observation path."""

    def __init__(
        self,
        token: SecretStr | None,
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
        self._client = client
        self._transport = transport
        self._timeout = httpx.Timeout(
            read=read_timeout_seconds,
            connect=connect_timeout_seconds,
            write=connect_timeout_seconds,
            pool=connect_timeout_seconds,
        )

    def get_json(
        self,
        path: str,
        *,
        error_subject: str,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        """Return decoded JSON from one authenticated, bounded observation GET."""
        request_params = None if params is None else dict(params)
        validate_token(self._token)
        token = cast(SecretStr, self._token)
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept-Datetime-Format": "RFC3339",
        }
        owned_client = self._client is None
        client = (
            self._client
            if self._client is not None
            else httpx.Client(
                transport=self._transport,
                timeout=self._timeout,
                base_url=OANDA_PRACTICE_BASE_URL,
                trust_env=False,
            )
        )
        try:
            attempts = 0
            while attempts < _MAX_ATTEMPTS:
                attempts += 1
                try:
                    response = client.get(
                        f"{OANDA_PRACTICE_BASE_URL}{path}",
                        headers=headers,
                        params=request_params,
                        timeout=self._timeout,
                    )
                except httpx.RequestError:
                    if attempts == _MAX_ATTEMPTS:
                        raise OandaRequestError(
                            None,
                            attempts,
                            f"OANDA {error_subject} request failed after retries",
                        ) from None
                    sleep(_BACKOFF_SECONDS[attempts - 1])
                    continue

                status = response.status_code
                if status in (401, 403):
                    raise OandaAuthError(status, attempts, "OANDA authorization failed")
                if status in (400, 404):
                    raise OandaRequestError(
                        status,
                        attempts,
                        f"OANDA {error_subject} request was rejected",
                    )
                if status == 408 or status == 429 or 500 <= status <= 599:
                    if attempts == _MAX_ATTEMPTS:
                        raise OandaRequestError(
                            status,
                            attempts,
                            f"OANDA {error_subject} request failed after retries",
                        )
                    delay = _retry_after(response)
                    if delay <= 0 or not math.isfinite(delay):
                        delay = _BACKOFF_SECONDS[attempts - 1]
                    sleep(delay)
                    continue
                if status < 200 or status >= 300:
                    raise OandaRequestError(
                        status,
                        attempts,
                        f"OANDA {error_subject} request failed",
                    )
                try:
                    return response.json()
                except ValueError:
                    raise OandaRequestError(
                        status,
                        attempts,
                        f"OANDA returned invalid {error_subject} JSON",
                    ) from None
            raise AssertionError("retry loop exhausted unexpectedly")
        finally:
            if owned_client:
                client.close()
