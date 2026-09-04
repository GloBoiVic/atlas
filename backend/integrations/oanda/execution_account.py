"""Read-only OANDA Practice account facts needed before PAPER execution."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings
from backend.domain import FinancialPositionState

from .account import (
    OandaPracticeAccountIdentity,
    OandaPracticeAccountSummarySnapshot,
    OandaPracticeAccountValidator,
    is_valid_oanda_practice_account_id,
)
from .exposure_projection import project_oanda_practice_eur_usd_exposure_state
from .orders import (
    OandaPracticePendingOrderInventory,
    normalize_oanda_practice_pending_order_inventory,
)
from .positions import (
    OandaPracticeOpenPositionInventory,
    normalize_oanda_practice_account_position_inventory,
)
from .primitives import OandaPrimitiveError, parse_transaction_id
from .request import OandaObservationRequester, validate_token
from .source import OandaConfigurationError, OandaNormalizationError
from .trades import (
    OandaPracticeOpenTradeInventory,
    normalize_oanda_practice_open_trade_inventory,
)

_ACCOUNT_PROPERTIES_PATH = "/v3/accounts"
_ACCOUNT_DETAILS_PATH = "/v3/accounts/{account_id}"
_ACCOUNT_PROPERTIES_REQUEST_SUBJECT = "account properties"
_ACCOUNT_DETAILS_REQUEST_SUBJECT = "account details"
_SUPPORTED_GSLO_MODES = ("DISABLED", "ALLOWED")


class OandaPracticeAccountPropertiesNormalizationError(OandaNormalizationError):
    """Account properties could not become a safe capability observation."""


class OandaPracticeExecutionAccountNormalizationError(OandaNormalizationError):
    """Full Account Details could not become a coherent execution snapshot."""


@dataclass(frozen=True, slots=True)
class OandaPracticeAccountProperties:
    """The configured account's read-only AccountProperties facts."""

    provider_account_id: str
    mt4_account_id: int | None

    def __post_init__(self) -> None:
        if not is_valid_oanda_practice_account_id(self.provider_account_id):
            raise OandaPracticeAccountPropertiesNormalizationError(
                "OANDA account properties has an invalid account ID"
            )
        if self.mt4_account_id is not None and (
            type(self.mt4_account_id) is not int or self.mt4_account_id < 0
        ):
            raise OandaPracticeAccountPropertiesNormalizationError(
                "OANDA account properties has an invalid MT4 account ID"
            )

    @property
    def is_non_mt4(self) -> bool:
        """Whether the provider proved this account is not MT4-associated."""
        return self.mt4_account_id is None


@dataclass(frozen=True, slots=True)
class OandaPracticeExecutionAccountSnapshot:
    """One coherent, immutable subset of a full Account Details response."""

    summary: OandaPracticeAccountSummarySnapshot
    trades: OandaPracticeOpenTradeInventory
    positions: OandaPracticeOpenPositionInventory
    pending_orders: OandaPracticePendingOrderInventory
    guaranteed_stop_loss_order_mode: str
    hedging_enabled: bool
    last_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.summary) is not OandaPracticeAccountSummarySnapshot:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has an invalid summary"
            )
        if type(self.trades) is not OandaPracticeOpenTradeInventory:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has invalid Trades"
            )
        if type(self.positions) is not OandaPracticeOpenPositionInventory:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has invalid Positions"
            )
        if type(self.pending_orders) is not OandaPracticePendingOrderInventory:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has invalid pending Orders"
            )
        identities = (
            self.summary.identity,
            self.trades.identity,
            self.positions.identity,
            self.pending_orders.identity,
        )
        if any(identity != self.summary.identity for identity in identities[1:]):
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has mismatched account identities"
            )
        frontier = self.last_transaction_id
        if type(frontier) is not str:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has an invalid transaction frontier"
            )
        try:
            parse_transaction_id(frontier)
        except OandaPrimitiveError:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has an invalid transaction frontier"
            ) from None
        if any(
            inventory.last_transaction_id != frontier
            for inventory in (
                self.summary,
                self.trades,
                self.positions,
                self.pending_orders,
            )
        ):
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has contradictory transaction IDs"
            )
        if (
            self.summary.open_trade_count != len(self.trades.trades)
            or self.summary.open_position_count != len(self.positions.positions)
            or self.summary.pending_order_count != len(self.pending_orders.orders)
        ):
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account snapshot has contradictory inventory counts"
            )
        if self.guaranteed_stop_loss_order_mode not in _SUPPORTED_GSLO_MODES:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account has an unsupported guaranteed Stop Loss mode"
            )
        if type(self.hedging_enabled) is not bool:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account has an invalid hedgingEnabled value"
            )

    @property
    def identity(self) -> OandaPracticeAccountIdentity:
        return self.summary.identity

    def require_flat_entry_state(self) -> None:
        """Reject any exposure or pending Order before an entry mutation."""
        if (
            self.summary.open_trade_count != 0
            or self.summary.open_position_count != 0
            or self.summary.pending_order_count != 0
        ):
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account is not flat or has pending Orders"
            )
        try:
            state = project_oanda_practice_eur_usd_exposure_state(
                self.trades, self.positions
            )
        except OandaNormalizationError as error:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account exposure is contradictory"
            ) from error
        if state is not FinancialPositionState.FLAT:
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA execution account is not flat"
            )


def _normalize_account_properties(
    payload: Mapping[str, Any], configured_account_id: str
) -> OandaPracticeAccountProperties:
    accounts_value = payload.get("accounts")
    if not isinstance(accounts_value, list):
        raise OandaPracticeAccountPropertiesNormalizationError(
            "OANDA account properties response has invalid accounts"
        )

    normalized: list[OandaPracticeAccountProperties] = []
    raw_accounts = cast(list[Any], accounts_value)
    for item in raw_accounts:
        if not isinstance(item, dict):
            raise OandaPracticeAccountPropertiesNormalizationError(
                "OANDA account properties response has invalid account properties"
            )
        account_item = cast(dict[str, Any], item)
        account_id = account_item.get("id")
        if not isinstance(account_id, str) or not is_valid_oanda_practice_account_id(
            account_id
        ):
            raise OandaPracticeAccountPropertiesNormalizationError(
                "OANDA account properties has an invalid account ID"
            )
        mt4_value = account_item.get("mt4AccountID")
        if mt4_value is not None and type(mt4_value) is not int:
            raise OandaPracticeAccountPropertiesNormalizationError(
                "OANDA account properties has an invalid MT4 account ID"
            )
        normalized.append(OandaPracticeAccountProperties(account_id, mt4_value))

    matches = [
        account
        for account in normalized
        if account.provider_account_id == configured_account_id
    ]
    if len(matches) != 1:
        raise OandaPracticeAccountPropertiesNormalizationError(
            "configured OANDA account properties must occur exactly once"
        )
    if not matches[0].is_non_mt4:
        raise OandaPracticeAccountPropertiesNormalizationError(
            "configured OANDA account is MT4-associated and unsupported"
        )
    return matches[0]


class OandaPracticeAccountPropertiesReader:
    """Read and normalize AccountProperties without any broker mutation."""

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

    def read(self) -> OandaPracticeAccountProperties:
        validate_token(self._token)
        account_id = self._configured_account_id()
        payload = self._requester.get_json(
            _ACCOUNT_PROPERTIES_PATH,
            error_subject=_ACCOUNT_PROPERTIES_REQUEST_SUBJECT,
        )
        if not isinstance(payload, dict):
            raise OandaPracticeAccountPropertiesNormalizationError(
                "OANDA account properties response is not an object"
            )
        return _normalize_account_properties(
            cast(Mapping[str, Any], payload), account_id
        )

    def _configured_account_id(self) -> str:
        if not is_valid_oanda_practice_account_id(self._account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )
        return cast(str, self._account_id)


class OandaPracticeExecutionAccountReader:
    """Read one full Account Details response for a configured account."""

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

    def read(self) -> OandaPracticeExecutionAccountSnapshot:
        validate_token(self._token)
        account_id = self._configured_account_id()
        path = _ACCOUNT_DETAILS_PATH.format(account_id=quote(account_id, safe="-"))
        payload = self._requester.get_json(
            path,
            error_subject=_ACCOUNT_DETAILS_REQUEST_SUBJECT,
        )
        if not isinstance(payload, dict):
            raise OandaPracticeExecutionAccountNormalizationError(
                "OANDA account details response is not an object"
            )
        return _normalize_execution_account(
            cast(Mapping[str, Any], payload), account_id
        )

    def _configured_account_id(self) -> str:
        if not is_valid_oanda_practice_account_id(self._account_id):
            raise OandaConfigurationError(
                "OANDA Practice account ID is required and must be a four-part "
                "AccountID"
            )
        return cast(str, self._account_id)


def _normalize_execution_account(
    payload: Mapping[str, Any], configured_account_id: str
) -> OandaPracticeExecutionAccountSnapshot:
    account_value = payload.get("account")
    if not isinstance(account_value, dict):
        raise OandaPracticeExecutionAccountNormalizationError(
            "OANDA account details response is missing account details"
        )
    account = cast(dict[str, Any], account_value)
    try:
        identity = OandaPracticeAccountValidator.normalize_identity(
            payload, configured_account_id
        )
        summary = OandaPracticeAccountValidator.normalize_summary(payload, identity)
        frontier = summary.last_transaction_id
        trades = normalize_oanda_practice_open_trade_inventory(
            {"trades": account.get("trades"), "lastTransactionID": frontier},
            identity,
        )
        positions = normalize_oanda_practice_account_position_inventory(
            {"positions": account.get("positions"), "lastTransactionID": frontier},
            identity,
        )
        pending_orders = normalize_oanda_practice_pending_order_inventory(
            {"orders": account.get("orders"), "lastTransactionID": frontier},
            identity,
        )
    except OandaNormalizationError as error:
        raise OandaPracticeExecutionAccountNormalizationError(
            "OANDA account details could not be normalized"
        ) from error

    guaranteed_mode = account.get("guaranteedStopLossOrderMode")
    hedging_enabled = account.get("hedgingEnabled")
    if type(guaranteed_mode) is not str:
        raise OandaPracticeExecutionAccountNormalizationError(
            "OANDA account details has an invalid guaranteed Stop Loss mode"
        )
    if type(hedging_enabled) is not bool:
        raise OandaPracticeExecutionAccountNormalizationError(
            "OANDA account details has an invalid hedgingEnabled value"
        )
    if guaranteed_mode not in _SUPPORTED_GSLO_MODES:
        raise OandaPracticeExecutionAccountNormalizationError(
            "OANDA account requires an unsupported guaranteed Stop Loss mode"
        )
    return OandaPracticeExecutionAccountSnapshot(
        summary=summary,
        trades=trades,
        positions=positions,
        pending_orders=pending_orders,
        guaranteed_stop_loss_order_mode=guaranteed_mode,
        hedging_enabled=hedging_enabled,
        last_transaction_id=frontier,
    )


def read_oanda_practice_account_properties(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeAccountProperties:
    """Read the configured account's AccountProperties capability proof."""
    return OandaPracticeAccountPropertiesReader(
        settings.oanda_api_token,
        settings.oanda_account_id,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


def read_oanda_practice_execution_account_snapshot(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeExecutionAccountSnapshot:
    """Read one coherent full Account Details execution snapshot."""
    return OandaPracticeExecutionAccountReader(
        settings.oanda_api_token,
        settings.oanda_account_id,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


def normalize_oanda_practice_execution_account_snapshot(
    payload: Mapping[str, Any], configured_account_id: str
) -> OandaPracticeExecutionAccountSnapshot:
    """Normalize one already-fetched Account Details response."""
    return _normalize_execution_account(payload, configured_account_id)


__all__ = [
    "OandaPracticeAccountProperties",
    "OandaPracticeAccountPropertiesNormalizationError",
    "OandaPracticeAccountPropertiesReader",
    "OandaPracticeExecutionAccountNormalizationError",
    "OandaPracticeExecutionAccountReader",
    "OandaPracticeExecutionAccountSnapshot",
    "read_oanda_practice_account_properties",
    "read_oanda_practice_execution_account_snapshot",
    "normalize_oanda_practice_execution_account_snapshot",
]
