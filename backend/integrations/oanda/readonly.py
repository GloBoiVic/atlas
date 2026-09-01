"""Read-only OANDA Practice transport contracts.

The concrete client intentionally has one private ``GET`` path.  It exposes
provider mappings only to the OANDA normalization layer and has no mutating
endpoint methods.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

import httpx
from pydantic import SecretStr

from .source import OANDA_PRACTICE_BASE_URL

RawResponse = Mapping[str, object]


class OandaReadOnlyTransport(Protocol):
    def list_accounts(self) -> RawResponse: ...

    def account_summary(self, account_id: str) -> RawResponse: ...

    def instrument(
        self, account_id: str, instrument: str = "EUR_USD"
    ) -> RawResponse: ...

    def pricing(self, account_id: str, instrument: str = "EUR_USD") -> RawResponse: ...

    def orders(self, account_id: str) -> RawResponse: ...

    def open_trades(self, account_id: str) -> RawResponse: ...

    def trade(self, account_id: str, trade_id: str) -> RawResponse: ...

    def account_changes(
        self, account_id: str, since_transaction_id: str | None = None
    ) -> RawResponse: ...

    def candles(
        self,
        start: datetime,
        end: datetime,
        *,
        granularity: str,
        price: str,
    ) -> RawResponse: ...


class OandaReadOnlyError(RuntimeError):
    """A sanitized read-only provider transport failure."""


class OandaPracticeReadOnlyClient:
    """Bounded GET-only OANDA Practice client for account/data facts."""

    def __init__(
        self,
        token: SecretStr | None,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = client
        self._transport = transport

    def _get(self, path: str, params: Mapping[str, str] | None = None) -> RawResponse:
        if self._token is None or not self._token.get_secret_value():
            raise OandaReadOnlyError("OANDA API token is required")
        owned = self._client is None
        client = self._client or httpx.Client(
            transport=self._transport,
            base_url=OANDA_PRACTICE_BASE_URL,
            follow_redirects=True,
            trust_env=False,
        )
        try:
            response = client.get(
                f"{OANDA_PRACTICE_BASE_URL}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {self._token.get_secret_value()}",
                    "Accept-Datetime-Format": "RFC3339",
                },
            )
            if response.status_code < 200 or response.status_code >= 300:
                raise OandaReadOnlyError(
                    f"OANDA read-only request failed ({response.status_code})"
                )
            try:
                value: Any = response.json()
            except ValueError:
                raise OandaReadOnlyError("OANDA returned invalid JSON") from None
            if not isinstance(value, Mapping):
                raise OandaReadOnlyError("OANDA returned an invalid object")
            return cast(RawResponse, value)
        except httpx.RequestError:
            raise OandaReadOnlyError("OANDA read-only request failed") from None
        finally:
            if owned:
                client.close()

    @staticmethod
    def _account_id(account_id: str) -> str:
        if (
            type(account_id) is not str
            or not account_id
            or "/" in account_id
            or "?" in account_id
            or "#" in account_id
        ):
            raise OandaReadOnlyError("an explicit OANDA account ID is required")
        return account_id

    def list_accounts(self) -> RawResponse:
        return self._get("/v3/accounts")

    def account_summary(self, account_id: str) -> RawResponse:
        return self._get(f"/v3/accounts/{self._account_id(account_id)}/summary")

    def instrument(self, account_id: str, instrument: str = "EUR_USD") -> RawResponse:
        if instrument != "EUR_USD":
            raise OandaReadOnlyError("only EUR_USD is supported")
        return self._get(
            f"/v3/accounts/{self._account_id(account_id)}/instruments",
            {"instruments": instrument},
        )

    def pricing(self, account_id: str, instrument: str = "EUR_USD") -> RawResponse:
        if instrument != "EUR_USD":
            raise OandaReadOnlyError("only EUR_USD is supported")
        return self._get(
            f"/v3/accounts/{self._account_id(account_id)}/pricing",
            {"instruments": instrument},
        )

    def orders(self, account_id: str) -> RawResponse:
        return self._get(
            f"/v3/accounts/{self._account_id(account_id)}/orders",
            {"state": "PENDING"},
        )

    def open_trades(self, account_id: str) -> RawResponse:
        return self._get(f"/v3/accounts/{self._account_id(account_id)}/openTrades")

    def trade(self, account_id: str, trade_id: str) -> RawResponse:
        safe_account = self._account_id(account_id)
        if type(trade_id) is not str or not trade_id or any(
            character in trade_id for character in "/?#"
        ):
            raise OandaReadOnlyError("an explicit OANDA trade ID is required")
        return self._get(f"/v3/accounts/{safe_account}/trades/{trade_id}")

    def account_changes(
        self, account_id: str, since_transaction_id: str | None = None
    ) -> RawResponse:
        params = (
            {"sinceTransactionID": since_transaction_id}
            if since_transaction_id is not None
            else None
        )
        return self._get(
            f"/v3/accounts/{self._account_id(account_id)}/changes",
            params,
        )

    def candles(
        self,
        start: datetime,
        end: datetime,
        *,
        granularity: str,
        price: str,
    ) -> RawResponse:
        if granularity not in {"M1", "M15"} or price not in {"M", "BA", "MBA"}:
            raise OandaReadOnlyError("unsupported read-only candle contract")
        if (
            start.tzinfo is None
            or start.utcoffset() != timedelta(0)
            or end.tzinfo is None
            or end.utcoffset() != timedelta(0)
            or start.second
            or start.microsecond
            or end.second
            or end.microsecond
            or end <= start
        ):
            raise OandaReadOnlyError("candle range must be a positive UTC minute range")
        return self._get(
            "/v3/instruments/EUR_USD/candles",
            {
                "from": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "to": end.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "granularity": granularity,
                "price": price,
                "smooth": "false",
            },
        )


__all__ = [
    "OandaPracticeReadOnlyClient",
    "OandaReadOnlyError",
    "OandaReadOnlyTransport",
]
