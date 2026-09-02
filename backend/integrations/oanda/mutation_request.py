"""Non-retrying OANDA Practice mutation transport.

The observation requester deliberately owns only safe, retryable GETs.  This
module is the separate write boundary: a caller receives at most one POST
attempt and must treat a transport failure as an uncertain broker outcome.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from .account import is_valid_oanda_practice_account_id
from .primitives import OandaPrimitiveError, parse_transaction_id
from .request import validate_token
from .source import (
    OANDA_PRACTICE_BASE_URL,
    OandaAuthError,
    OandaConfigurationError,
    OandaRequestError,
)

_ENTRY_ORDER_PATH = "/v3/accounts/{account_id}/orders"
_TRADE_ORDERS_PATH = "/v3/accounts/{account_id}/trades/{trade_id}/orders"


class OandaMutationTransportError(OandaRequestError):
    """The entry POST may have reached OANDA, but its result was not received."""

    def __init__(self) -> None:
        super().__init__(None, 1, "OANDA entry mutation transport outcome is uncertain")


class OandaProtectionMutationTransportError(OandaRequestError):
    """The dependent protection mutation may have reached OANDA."""

    def __init__(self) -> None:
        super().__init__(
            None,
            1,
            "OANDA protection mutation transport outcome is uncertain",
        )


@dataclass(frozen=True, slots=True)
class OandaMutationResponse:
    """Bounded transport data passed to the entry normalizer.

    ``payload`` is an internal handoff to normalization and is intentionally
    excluded from the representation so provider bodies cannot leak through
    diagnostics or exception text.
    """

    status_code: int
    request_id: str | None
    payload: Any = field(repr=False)
    json_valid: bool


class OandaPracticeMutationRequester:
    """Make exact OANDA Practice mutations without retrying."""

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

    def post_entry_order(
        self, account_id: str, payload: Mapping[str, Any]
    ) -> OandaMutationResponse:
        """POST the approved entry payload exactly once.

        HTTP errors are returned as one bounded response for the normalizer;
        they are never retried.  Authentication and transport failures use
        sanitized exceptions and still represent exactly one attempt.
        """
        validate_token(self._token)
        if not is_valid_oanda_practice_account_id(account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )
        if type(payload) is not dict:
            raise OandaConfigurationError(
                "OANDA entry mutation payload must be an object"
            )

        path = _ENTRY_ORDER_PATH.format(account_id=quote(account_id, safe="-"))
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
        token = self._token
        if token is None:  # validate_token above is deliberately explicit.
            raise OandaConfigurationError("OANDA API token is required")
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept-Datetime-Format": "RFC3339",
        }
        json_payload = cast(dict[str, Any], payload)
        try:
            try:
                response = client.post(
                    f"{OANDA_PRACTICE_BASE_URL}{path}",
                    headers=headers,
                    json=json_payload,
                    timeout=self._timeout,
                )
            except httpx.RequestError:
                raise OandaMutationTransportError() from None

            if response.status_code in (401, 403):
                raise OandaAuthError(
                    response.status_code, 1, "OANDA authorization failed"
                )

            try:
                payload_value = response.json()
            except ValueError:
                return OandaMutationResponse(
                    status_code=response.status_code,
                    request_id=_request_id(response),
                    payload=None,
                    json_valid=False,
                )
            return OandaMutationResponse(
                status_code=response.status_code,
                request_id=_request_id(response),
                payload=payload_value,
                json_valid=True,
            )
        finally:
            if owned_client:
                client.close()

    def put_trade_orders(
        self, account_id: str, trade_id: str, payload: Mapping[str, Any]
    ) -> OandaMutationResponse:
        """PUT one dependent Trade-order mutation exactly once.

        The caller owns the narrow payload contract.  This transport only
        provides the authenticated Practice endpoint and never retries an
        outcome that might have created a broker order.
        """
        validate_token(self._token)
        if not is_valid_oanda_practice_account_id(account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )
        if type(trade_id) is not str:
            raise OandaConfigurationError("OANDA Trade ID is required")
        try:
            parsed_trade_id = parse_transaction_id(trade_id)
        except OandaPrimitiveError:
            raise OandaConfigurationError("OANDA Trade ID is invalid") from None
        if not any(character != "0" for character in parsed_trade_id):
            raise OandaConfigurationError("OANDA Trade ID is invalid")
        if type(payload) is not dict:
            raise OandaConfigurationError(
                "OANDA protection mutation payload must be an object"
            )

        path = _TRADE_ORDERS_PATH.format(
            account_id=quote(account_id, safe="-"),
            trade_id=quote(parsed_trade_id, safe="-"),
        )
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
        token = self._token
        if token is None:  # validate_token above is deliberately explicit.
            raise OandaConfigurationError("OANDA API token is required")
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept-Datetime-Format": "RFC3339",
        }
        json_payload = cast(dict[str, Any], payload)
        try:
            try:
                response = client.put(
                    f"{OANDA_PRACTICE_BASE_URL}{path}",
                    headers=headers,
                    json=json_payload,
                    timeout=self._timeout,
                )
            except httpx.RequestError:
                raise OandaProtectionMutationTransportError() from None

            if response.status_code in (401, 403):
                raise OandaAuthError(
                    response.status_code, 1, "OANDA authorization failed"
                )

            try:
                payload_value = response.json()
            except ValueError:
                return OandaMutationResponse(
                    status_code=response.status_code,
                    request_id=_request_id(response),
                    payload=None,
                    json_valid=False,
                )
            return OandaMutationResponse(
                status_code=response.status_code,
                request_id=_request_id(response),
                payload=payload_value,
                json_valid=True,
            )
        finally:
            if owned_client:
                client.close()


def _request_id(response: httpx.Response) -> str | None:
    value = response.headers.get("RequestID")
    if value is None or not value or len(value) > 128:
        return None
    return value


__all__ = [
    "OandaMutationResponse",
    "OandaMutationTransportError",
    "OandaProtectionMutationTransportError",
    "OandaPracticeMutationRequester",
]
