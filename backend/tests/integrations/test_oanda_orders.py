from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.config import Settings
from backend.domain.market_data import Provider
from backend.integrations.oanda import (
    OandaAuthError,
    OandaConfigurationError,
    OandaPendingOrderNormalizationError,
    OandaPracticeAccountIdentity,
    OandaPracticePendingOrder,
    OandaPracticePendingOrderReader,
    OandaRequestError,
    read_oanda_practice_pending_order_inventory,
)

TEST_TOKEN = "unit" + "-credential"
ACCOUNT_ID = "001-011-5838423-001"


def account_identity() -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=ACCOUNT_ID,
        alias="Research Practice",
        base_currency="USD",
    )


def account_payload() -> dict[str, Any]:
    return {
        "account": {
            "id": ACCOUNT_ID,
            "currency": "USD",
            "alias": "Research Practice",
        },
        "lastTransactionID": "42",
    }


def provider_order(
    provider_order_id: str = "20",
    *,
    order_type: str = "LIMIT",
    state: str = "PENDING",
) -> dict[str, Any]:
    return {
        "id": provider_order_id,
        "type": order_type,
        "state": state,
        "instrument": {"malformed": "value"},
        "units": "malformed",
        "price": "malformed",
        "priceBound": "malformed",
        "timeInForce": "malformed",
        "gtdTime": "malformed",
        "positionFill": "malformed",
        "triggerCondition": "malformed",
        "tradeID": "malformed",
        "clientTradeID": "malformed",
        "distance": "malformed",
        "takeProfitOnFill": "malformed",
        "stopLossOnFill": "malformed",
        "guaranteedStopLossOnFill": "malformed",
        "trailingStopLossOnFill": "malformed",
        "tradeClientExtensions": "malformed",
        "clientExtensions": "malformed",
        "fillingTransactionID": "malformed",
        "filledTime": "malformed",
        "tradeOpenedID": "malformed",
        "tradeReducedID": "malformed",
        "tradeClosedIDs": "malformed",
        "cancellingTransactionID": "malformed",
        "cancelledTime": "malformed",
        "replacesOrderID": "malformed",
        "replacedByOrderID": "malformed",
        "createTime": "malformed",
    }


def pending_payload(
    orders: list[dict[str, Any]], last_transaction_id: str = "99"
) -> dict[str, Any]:
    return {"orders": orders, "lastTransactionID": last_transaction_id}


def reader(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    identity: OandaPracticeAccountIdentity | None = None,
    token: str = TEST_TOKEN,
) -> OandaPracticePendingOrderReader:
    return OandaPracticePendingOrderReader(
        SecretStr(token),
        identity or account_identity(),
        transport=httpx.MockTransport(handler),
    )


def test_settings_helper_validates_account_then_reads_pending_orders() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json=account_payload())
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/pendingOrders"
        assert request.method == "GET"
        assert len(request.url.params) == 0
        assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
        assert request.headers["Accept-Datetime-Format"] == "RFC3339"
        return httpx.Response(
            200,
            json=pending_payload([provider_order("20", order_type="STOP")]),
        )

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql+psycopg://user@localhost/atlas",
        oanda_api_token=SecretStr(TEST_TOKEN),
        oanda_account_id=ACCOUNT_ID,
    )
    inventory = read_oanda_practice_pending_order_inventory(
        settings, transport=httpx.MockTransport(handler)
    )

    assert [request.url.path for request in requests] == [
        f"/v3/accounts/{ACCOUNT_ID}/summary",
        f"/v3/accounts/{ACCOUNT_ID}/pendingOrders",
    ]
    assert inventory.identity == account_identity()
    assert inventory.last_transaction_id == "99"
    assert inventory.orders == (OandaPracticePendingOrder("20", "STOP", "PENDING"),)


@pytest.mark.parametrize(
    "order_type",
    [
        "LIMIT",
        "STOP",
        "MARKET_IF_TOUCHED",
        "TAKE_PROFIT",
        "STOP_LOSS",
        "GUARANTEED_STOP_LOSS",
        "TRAILING_STOP_LOSS",
    ],
)
def test_all_documented_pending_capable_types_are_observed_without_interpretation(
    order_type: str,
) -> None:
    order = (
        reader(
            lambda request: httpx.Response(
                200,
                json=pending_payload([provider_order(order_type=order_type)]),
            )
        )
        .read()
        .orders[0]
    )

    assert order.provider_order_id == "20"
    assert order.provider_order_type == order_type
    assert order.state == "PENDING"
    assert {field.name for field in fields(order)} == {
        "provider_order_id",
        "provider_order_type",
        "state",
    }
    for forbidden in (
        "instrument",
        "units",
        "price",
        "price_bound",
        "time_in_force",
        "gtd_time",
        "position_fill",
        "trigger_condition",
        "trade_id",
        "client_trade_id",
        "create_time",
        "direction",
        "quantity",
        "requested_price",
        "fill",
    ):
        assert not hasattr(order, forbidden)


def test_malformed_ignored_order_fields_do_not_invalidate_common_envelope() -> None:
    order = provider_order()
    order.pop("createTime")
    order["instrument"] = None
    order["units"] = {"unexpected": ["value"]}

    normalized = reader(
        lambda request: httpx.Response(200, json=pending_payload([order]))
    ).read()

    assert normalized.orders == (OandaPracticePendingOrder("20", "LIMIT", "PENDING"),)


def test_provider_array_order_does_not_change_equality_and_sorts_numeric_ids() -> None:
    first = pending_payload(
        [
            provider_order("10", order_type="STOP"),
            provider_order("0010"),
            provider_order("2", order_type="TAKE_PROFIT"),
            provider_order("1"),
            provider_order("01", order_type="STOP_LOSS"),
        ]
    )
    second = pending_payload(list(reversed(first["orders"])))

    left = reader(lambda request: httpx.Response(200, json=first)).read()
    right = reader(lambda request: httpx.Response(200, json=second)).read()

    assert left == right
    assert [order.provider_order_id for order in left.orders] == [
        "01",
        "1",
        "2",
        "0010",
        "10",
    ]


def test_empty_inventory_is_explicit_frozen_and_slotted() -> None:
    inventory = reader(
        lambda request: httpx.Response(
            200, json=pending_payload([], last_transaction_id="7")
        )
    ).read()

    assert inventory.orders == ()
    assert {field.name for field in fields(inventory)} == {
        "identity",
        "orders",
        "last_transaction_id",
    }
    with pytest.raises(FrozenInstanceError):
        inventory.__setattr__("orders", ())
    with pytest.raises(FrozenInstanceError):
        inventory.orders = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "provider_order_id",
    [None, "", "0", "00", "000", "-1", "1.5", " 1", 1, True],
)
def test_order_id_must_be_an_exact_positive_raw_digit_string(
    provider_order_id: Any,
) -> None:
    order = provider_order()
    order["id"] = provider_order_id

    with pytest.raises(OandaPendingOrderNormalizationError, match="id"):
        reader(
            lambda request: httpx.Response(200, json=pending_payload([order]))
        ).read()


@pytest.mark.parametrize("order_type", [None, "", "MARKET", "FIXED_PRICE", 1, True])
def test_immediate_or_unknown_order_types_fail_closed(order_type: Any) -> None:
    order = provider_order(order_type="LIMIT")
    order["type"] = order_type

    with pytest.raises(OandaPendingOrderNormalizationError, match="type"):
        reader(
            lambda request: httpx.Response(200, json=pending_payload([order]))
        ).read()


@pytest.mark.parametrize("state", [None, "", "FILLED", "TRIGGERED", "CANCELLED", 1])
def test_pending_orders_require_exact_pending_state(state: Any) -> None:
    order = provider_order()
    order["state"] = state

    with pytest.raises(OandaPendingOrderNormalizationError, match="state"):
        reader(
            lambda request: httpx.Response(200, json=pending_payload([order]))
        ).read()


def test_exact_duplicate_raw_order_ids_fail_without_merge_or_partial_output() -> None:
    for duplicate in (
        provider_order("20"),
        provider_order("20", order_type="STOP"),
    ):
        with pytest.raises(
            OandaPendingOrderNormalizationError, match="duplicate Order IDs"
        ):
            reader(
                lambda request, duplicate=duplicate: httpx.Response(
                    200,
                    json=pending_payload([provider_order("20"), duplicate]),
                )
            ).read()


@pytest.mark.parametrize(
    "orders_value",
    [None, {}, [None], ["order"], [provider_order() | {"type": None}]],
)
def test_malformed_order_collection_fails_closed_without_partial_inventory(
    orders_value: Any,
) -> None:
    with pytest.raises(OandaPendingOrderNormalizationError):
        reader(
            lambda request: httpx.Response(
                200,
                json={"orders": orders_value, "lastTransactionID": "7"},
            )
        ).read()


@pytest.mark.parametrize("last_transaction_id", [None, "", "1.5", "-1", 7, True])
def test_invalid_transaction_provenance_fails_closed(
    last_transaction_id: Any,
) -> None:
    with pytest.raises(OandaPendingOrderNormalizationError, match="lastTransactionID"):
        reader(
            lambda request: httpx.Response(
                200,
                json={"orders": [], "lastTransactionID": last_transaction_id},
            )
        ).read()


def test_non_object_json_remains_pending_order_normalization_failure() -> None:
    with pytest.raises(
        OandaPendingOrderNormalizationError,
        match="pending Orders response is not an object",
    ):
        reader(lambda request: httpx.Response(200, json=[])).read()


def test_invalid_json_and_provider_errors_are_sanitized_and_not_retried() -> None:
    body = f"provider body {TEST_TOKEN}"
    with pytest.raises(OandaRequestError) as invalid_json:
        reader(lambda request: httpx.Response(200, text=body)).read()
    assert "invalid pending Orders JSON" in str(invalid_json.value)
    assert body not in str(invalid_json.value)
    assert TEST_TOKEN not in str(invalid_json.value)

    calls = 0

    def rejected(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, text=body)

    with pytest.raises(OandaAuthError) as auth_error:
        reader(rejected).read()
    assert auth_error.value.attempts == 1
    assert calls == 1
    assert body not in str(auth_error.value)
    assert TEST_TOKEN not in str(auth_error.value)


def test_transient_pending_order_read_retries_only_same_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "GET"
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/pendingOrders"
        assert len(request.url.params) == 0
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "999"})
        return httpx.Response(200, json=pending_payload([]))

    monkeypatch.setattr("backend.integrations.oanda.request.sleep", sleeps.append)
    result = reader(handler).read()

    assert result.orders == ()
    assert calls == 2
    assert sleeps == [30.0]


def test_exhausted_transport_retries_are_bounded_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout(f"provider timeout {TEST_TOKEN}")

    monkeypatch.setattr("backend.integrations.oanda.request.sleep", sleeps.append)
    with pytest.raises(OandaRequestError) as error:
        reader(handler).read()

    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert error.value.status_code is None
    assert error.value.attempts == 3
    assert TEST_TOKEN not in str(error.value)


@pytest.mark.parametrize("token", [None, " "])
def test_missing_or_blank_token_fails_without_network(token: str | None) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=pending_payload([]))

    value = SecretStr(token) if token is not None else None
    with pytest.raises(OandaConfigurationError, match="API token is required"):
        OandaPracticePendingOrderReader(
            value,
            account_identity(),
            transport=httpx.MockTransport(handler),
        ).read()
    assert calls == 0


def test_reader_requires_validated_account_identity() -> None:
    with pytest.raises(
        OandaPendingOrderNormalizationError, match="validated account identity"
    ):
        OandaPracticePendingOrderReader(
            SecretStr(TEST_TOKEN),
            object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("connect_timeout_seconds", "read_timeout_seconds"),
    [(0, 20), (31, 20), (5, 0), (5, 121)],
)
def test_invalid_timeout_configuration_fails_closed(
    connect_timeout_seconds: float, read_timeout_seconds: float
) -> None:
    with pytest.raises(OandaConfigurationError, match="timeouts"):
        OandaPracticePendingOrderReader(
            SecretStr(TEST_TOKEN),
            account_identity(),
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )
