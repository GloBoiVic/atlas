"""Read-only binding of one explicitly configured OANDA Practice account."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings
from backend.domain.market_data import Provider

from .primitives import OandaPrimitiveError, parse_decimal, parse_transaction_id
from .request import OandaObservationRequester, validate_token
from .source import (
    OandaConfigurationError,
    OandaNormalizationError,
)

_ACCOUNT_SUMMARY_PATH = "/v3/accounts/{account_id}/summary"
_ACCOUNT_ID_PATTERN = re.compile(r"[^\s/?#\\%-]+(?:-[^\s/?#\\%-]+){3}")
_REQUEST_ERROR_SUBJECT = "account"


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
    try:
        return parse_decimal(value)
    except OandaPrimitiveError:
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        ) from None


def _count(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        )
    return value


def _transaction_id(value: Any, name: str) -> str:
    try:
        return parse_transaction_id(value)
    except OandaPrimitiveError:
        raise OandaAccountNormalizationError(
            f"OANDA account summary has invalid {name}"
        ) from None


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
        self._token = token
        self._account_id = account_id
        self._requester = OandaObservationRequester(
            token,
            client=client,
            transport=transport,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )

    def validate(self) -> OandaPracticeAccountIdentity:
        """Return a normalized identity or fail before/after the safe GET."""
        payload, account_id = self._read_payload()
        return self.normalize_identity(payload, account_id)

    def read_summary(self) -> OandaPracticeAccountSummarySnapshot:
        """Read and normalize one immutable Practice account summary."""
        payload, account_id = self._read_payload()
        identity = self.normalize_identity(payload, account_id)
        return self.normalize_summary(payload, identity)

    def _read_payload(self) -> tuple[Mapping[str, Any], str]:
        self._validate_configuration()
        account_id = cast(str, self._account_id)
        path = _ACCOUNT_SUMMARY_PATH.format(account_id=quote(account_id, safe="-"))
        payload = self._requester.get_json(path, error_subject=_REQUEST_ERROR_SUBJECT)
        if not isinstance(payload, dict):
            raise OandaAccountNormalizationError(
                "OANDA account response is not an object"
            )
        return cast(Mapping[str, Any], payload), account_id

    def _validate_configuration(self) -> None:
        validate_token(self._token)
        if not _valid_account_id(self._account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )

    @staticmethod
    def _account(payload: Mapping[str, Any]) -> dict[str, Any]:
        account_value = payload.get("account")
        if not isinstance(account_value, dict):
            raise OandaAccountNormalizationError(
                "OANDA account response is missing account details"
            )
        return cast(dict[str, Any], account_value)

    @classmethod
    def normalize_identity(
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
    def normalize_summary(
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

    @classmethod
    def _normalize_identity(
        cls, payload: Mapping[str, Any], configured_account_id: str
    ) -> OandaPracticeAccountIdentity:
        return cls.normalize_identity(payload, configured_account_id)

    @classmethod
    def _normalize_summary(
        cls,
        payload: Mapping[str, Any],
        identity: OandaPracticeAccountIdentity,
    ) -> OandaPracticeAccountSummarySnapshot:
        return cls.normalize_summary(payload, identity)


def is_valid_oanda_practice_account_id(value: str | None) -> bool:
    """Return whether a value has OANDA's safe four-part AccountID shape."""
    return _valid_account_id(value)


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
    "is_valid_oanda_practice_account_id",
    "read_oanda_practice_account_summary",
]
