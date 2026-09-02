"""Read-only, provider-specific OANDA Practice pending Order observations."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings

from .account import OandaPracticeAccountIdentity, bind_oanda_practice_account
from .primitives import OandaPrimitiveError, parse_transaction_id
from .request import OandaObservationRequester, validate_token
from .source import OandaNormalizationError

_PENDING_ORDERS_PATH = "/v3/accounts/{account_id}/pendingOrders"
_REQUEST_ERROR_SUBJECT = "pending Orders"
_PENDING_ORDER_TYPES = (
    "LIMIT",
    "STOP",
    "MARKET_IF_TOUCHED",
    "TAKE_PROFIT",
    "STOP_LOSS",
    "GUARANTEED_STOP_LOSS",
    "TRAILING_STOP_LOSS",
)
type _PendingOrderType = Literal[
    "LIMIT",
    "STOP",
    "MARKET_IF_TOUCHED",
    "TAKE_PROFIT",
    "STOP_LOSS",
    "GUARANTEED_STOP_LOSS",
    "TRAILING_STOP_LOSS",
]


class OandaPendingOrderNormalizationError(OandaNormalizationError):
    """An OANDA pending-Orders observation could not become a safe inventory."""


def _positive_order_id(value: Any) -> str:
    try:
        result = parse_transaction_id(value)
    except OandaPrimitiveError:
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Order has invalid id"
        ) from None
    if not any(character != "0" for character in result):
        raise OandaPendingOrderNormalizationError("OANDA pending Order has invalid id")
    return result


def _transaction_id(value: Any) -> str:
    try:
        return parse_transaction_id(value)
    except OandaPrimitiveError:
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Orders response has invalid lastTransactionID"
        ) from None


def _order_type(value: Any) -> _PendingOrderType:
    if type(value) is not str or value not in _PENDING_ORDER_TYPES:
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Order has invalid type"
        )
    return value


def _pending_state(value: Any) -> Literal["PENDING"]:
    if type(value) is not str or value != "PENDING":
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Order has invalid state"
        )
    return "PENDING"


def _order_id_sort_key(provider_order_id: str) -> tuple[int, str, str]:
    significant = provider_order_id.lstrip("0")
    return len(significant), significant, provider_order_id


@dataclass(frozen=True, slots=True)
class OandaPracticePendingOrder:
    """The approved provider-native facts for one currently pending Order."""

    provider_order_id: str
    provider_order_type: _PendingOrderType
    state: Literal["PENDING"]

    def __post_init__(self) -> None:
        _positive_order_id(self.provider_order_id)
        _order_type(self.provider_order_type)
        _pending_state(self.state)


@dataclass(frozen=True, slots=True)
class OandaPracticePendingOrderInventory:
    """An immutable observation of one validated account's pending Orders."""

    identity: OandaPracticeAccountIdentity
    orders: tuple[OandaPracticePendingOrder, ...]
    last_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not OandaPracticeAccountIdentity:
            raise OandaPendingOrderNormalizationError(
                "OANDA pending Order inventory has an invalid identity"
            )
        if type(self.orders) is not tuple or any(
            type(order) is not OandaPracticePendingOrder for order in self.orders
        ):
            raise OandaPendingOrderNormalizationError(
                "OANDA pending Order inventory has invalid orders"
            )
        order_ids = [order.provider_order_id for order in self.orders]
        if len(order_ids) != len(set(order_ids)):
            raise OandaPendingOrderNormalizationError(
                "OANDA pending Order inventory contains duplicate Order IDs"
            )
        object.__setattr__(
            self,
            "orders",
            tuple(
                sorted(
                    self.orders,
                    key=lambda order: _order_id_sort_key(order.provider_order_id),
                )
            ),
        )
        _transaction_id(self.last_transaction_id)


class OandaPracticePendingOrderReader:
    """Read pending Orders for an already validated Practice identity."""

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
            raise OandaPendingOrderNormalizationError(
                "OANDA pending Order reader requires a validated account identity"
            )
        self._token = token
        self._identity = identity

    def read(self) -> OandaPracticePendingOrderInventory:
        """Read and normalize one immutable pending-Orders observation."""
        payload = self._read_payload()
        return self._normalize_inventory(payload)

    def _read_payload(self) -> Mapping[str, Any]:
        self._validate_configuration()
        path = _PENDING_ORDERS_PATH.format(
            account_id=quote(self._identity.provider_account_id, safe="-")
        )
        payload = self._requester.get_json(path, error_subject=_REQUEST_ERROR_SUBJECT)
        if not isinstance(payload, dict):
            raise OandaPendingOrderNormalizationError(
                "OANDA pending Orders response is not an object"
            )
        return cast(Mapping[str, Any], payload)

    def _validate_configuration(self) -> None:
        validate_token(self._token)

    def _normalize_inventory(
        self, payload: Mapping[str, Any]
    ) -> OandaPracticePendingOrderInventory:
        return normalize_oanda_practice_pending_order_inventory(payload, self._identity)

    @staticmethod
    def _normalize_order(
        item: Mapping[str, Any], order_id: str
    ) -> OandaPracticePendingOrder:
        return _normalize_order(item, order_id)


def normalize_oanda_practice_pending_order_inventory(
    payload: Mapping[str, Any], identity: OandaPracticeAccountIdentity
) -> OandaPracticePendingOrderInventory:
    """Normalize pending Orders without issuing a separate observation GET."""
    if type(identity) is not OandaPracticeAccountIdentity:
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Order inventory has an invalid identity"
        )
    orders_value = payload.get("orders")
    if not isinstance(orders_value, list):
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Orders response has invalid orders"
        )
    raw_orders = cast(list[Any], orders_value)
    if any(not isinstance(item, dict) for item in raw_orders):
        raise OandaPendingOrderNormalizationError(
            "OANDA pending Orders response has invalid orders"
        )

    normalized: list[OandaPracticePendingOrder] = []
    seen_ids: set[str] = set()
    for item in raw_orders:
        order_item = cast(dict[str, Any], item)
        order_id = _positive_order_id(order_item.get("id"))
        if order_id in seen_ids:
            raise OandaPendingOrderNormalizationError(
                "OANDA pending Order inventory contains duplicate Order IDs"
            )
        seen_ids.add(order_id)
        normalized.append(_normalize_order(order_item, order_id))

    return OandaPracticePendingOrderInventory(
        identity=identity,
        orders=tuple(normalized),
        last_transaction_id=_transaction_id(payload.get("lastTransactionID")),
    )


def _normalize_order(
    item: Mapping[str, Any], order_id: str
) -> OandaPracticePendingOrder:
    return OandaPracticePendingOrder(
        provider_order_id=order_id,
        provider_order_type=_order_type(item.get("type")),
        state=_pending_state(item.get("state")),
    )


def read_oanda_practice_pending_order_inventory(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticePendingOrderInventory:
    """Validate settings' account, then read its independent pending-Orders view."""
    identity = bind_oanda_practice_account(
        settings,
        client=client,
        transport=transport,
    )
    return OandaPracticePendingOrderReader(
        settings.oanda_api_token,
        identity,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


__all__ = [
    "OandaPendingOrderNormalizationError",
    "OandaPracticePendingOrder",
    "OandaPracticePendingOrderInventory",
    "OandaPracticePendingOrderReader",
    "normalize_oanda_practice_pending_order_inventory",
    "read_oanda_practice_pending_order_inventory",
]
