from collections.abc import Callable
from dataclasses import FrozenInstanceError
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.integrations.oanda import (
    OandaConfigurationError,
    OandaPracticeAccountPropertiesNormalizationError,
    OandaPracticeAccountPropertiesReader,
    OandaPracticeExecutionAccountNormalizationError,
    OandaPracticeExecutionAccountReader,
    OandaPracticeExecutionInstrument,
    OandaPracticeExecutionInstrumentNormalizationError,
    OandaPracticeExecutionInstrumentReader,
)

TEST_TOKEN = "unit-credential"
ACCOUNT_ID = "001-011-5838423-001"


def properties_payload(
    accounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {"accounts": accounts or [{"id": ACCOUNT_ID}]}


def account_details_payload(
    *,
    trade_count: int = 0,
    position_count: int = 0,
    pending_count: int = 0,
    orders: list[dict[str, Any]] | None = None,
    guaranteed_mode: str = "DISABLED",
    frontier: str = "42",
) -> dict[str, Any]:
    account: dict[str, Any] = {
        "id": ACCOUNT_ID,
        "currency": "USD",
        "alias": "Research Practice",
        "balance": "100000.00",
        "NAV": "100000.00",
        "unrealizedPL": "0.00",
        "marginUsed": "0.00",
        "marginAvailable": "100000.00",
        "openTradeCount": trade_count,
        "openPositionCount": position_count,
        "pendingOrderCount": pending_count,
        "trades": [],
        "positions": [],
        "orders": orders or [],
        "guaranteedStopLossOrderMode": guaranteed_mode,
        "hedgingEnabled": True,
        "lastTransactionID": frontier,
    }
    return {"account": account, "lastTransactionID": frontier}


def instrument_payload(
    *,
    name: str = "EUR_USD",
    display_precision: int = 5,
    trade_units_precision: int = 0,
    minimum_trade_size: str = "1",
    maximum_order_units: str = "1000000",
    frontier: str = "42",
) -> dict[str, Any]:
    return {
        "instruments": [
            {
                "name": name,
                "displayPrecision": display_precision,
                "tradeUnitsPrecision": trade_units_precision,
                "minimumTradeSize": minimum_trade_size,
                "maximumOrderUnits": maximum_order_units,
            }
        ],
        "lastTransactionID": frontier,
    }


def pending_order(order_id: str = "10") -> dict[str, Any]:
    return {"id": order_id, "type": "LIMIT", "state": "PENDING"}


def reader(
    reader_type: type[Any],
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    account_id: str | None = ACCOUNT_ID,
) -> Any:
    return reader_type(
        SecretStr(TEST_TOKEN),
        account_id,
        transport=httpx.MockTransport(handler),
    )


def test_account_properties_prove_non_mt4_with_one_read_only_get() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=properties_payload())

    properties = reader(OandaPracticeAccountPropertiesReader, handler).read()

    assert properties.provider_account_id == ACCOUNT_ID
    assert properties.mt4_account_id is None
    assert properties.is_non_mt4
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/v3/accounts"
    assert requests[0].url.params == httpx.QueryParams()


@pytest.mark.parametrize(
    "accounts",
    [
        [{"id": ACCOUNT_ID, "mt4AccountID": 12345}],
        [{"id": "001-011-5838423-002"}],
        [{"id": ACCOUNT_ID}, {"id": ACCOUNT_ID}],
        [{"id": "malformed"}],
        [{"id": ACCOUNT_ID, "mt4AccountID": "12345"}],
        [None],
    ],
)
def test_account_properties_fail_closed_for_unsupported_or_malformed_facts(
    accounts: list[dict[str, Any]] | None,
) -> None:
    payload = {"accounts": accounts}
    with pytest.raises(OandaPracticeAccountPropertiesNormalizationError):
        reader(
            OandaPracticeAccountPropertiesReader,
            lambda request: httpx.Response(200, json=payload),
        ).read()


def test_account_properties_configuration_errors_happen_without_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=properties_payload())

    with pytest.raises(OandaConfigurationError, match="account ID"):
        reader(OandaPracticeAccountPropertiesReader, handler, account_id=None).read()
    assert calls == 0


def test_full_account_details_is_one_coherent_read() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=account_details_payload())

    snapshot = reader(OandaPracticeExecutionAccountReader, handler).read()

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}"
    assert snapshot.identity.provider_account_id == ACCOUNT_ID
    assert snapshot.summary.last_transaction_id == "42"
    assert snapshot.trades.last_transaction_id == "42"
    assert snapshot.positions.last_transaction_id == "42"
    assert snapshot.pending_orders.last_transaction_id == "42"
    assert snapshot.guaranteed_stop_loss_order_mode == "DISABLED"
    snapshot.require_flat_entry_state()
    with pytest.raises(FrozenInstanceError):
        snapshot.__setattr__("last_transaction_id", "43")


def test_allowed_guaranteed_stop_loss_mode_is_accepted() -> None:
    snapshot = reader(
        OandaPracticeExecutionAccountReader,
        lambda request: httpx.Response(
            200, json=account_details_payload(guaranteed_mode="ALLOWED")
        ),
    ).read()
    assert snapshot.guaranteed_stop_loss_order_mode == "ALLOWED"


@pytest.mark.parametrize("mode", ["REQUIRED", "UNKNOWN", None])
def test_unsupported_guaranteed_stop_loss_mode_fails_before_any_mutation(
    mode: str | None,
) -> None:
    payload = account_details_payload(guaranteed_mode=mode)  # type: ignore[arg-type]
    with pytest.raises(OandaPracticeExecutionAccountNormalizationError, match="Stop"):
        reader(
            OandaPracticeExecutionAccountReader,
            lambda request: httpx.Response(200, json=payload),
        ).read()


def test_count_coherence_and_pending_order_gate_are_explicit() -> None:
    with pytest.raises(OandaPracticeExecutionAccountNormalizationError, match="counts"):
        reader(
            OandaPracticeExecutionAccountReader,
            lambda request: httpx.Response(
                200,
                json=account_details_payload(pending_count=1),
            ),
        ).read()

    snapshot = reader(
        OandaPracticeExecutionAccountReader,
        lambda request: httpx.Response(
            200,
            json=account_details_payload(pending_count=1, orders=[pending_order()]),
        ),
    ).read()
    with pytest.raises(OandaPracticeExecutionAccountNormalizationError, match="flat"):
        snapshot.require_flat_entry_state()


def test_instrument_capability_observes_provider_precision_and_exact_bounds() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=instrument_payload())

    instrument = reader(OandaPracticeExecutionInstrumentReader, handler).read()

    assert instrument == OandaPracticeExecutionInstrument(
        provider_instrument="EUR_USD",
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        maximum_order_units=Decimal("1000000"),
        last_transaction_id="42",
    )
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}/instruments"
    assert requests[0].url.params == httpx.QueryParams("instruments=EUR_USD")
    assert instrument.serialize_price(Decimal("1.2345")) == "1.23450"
    assert instrument.serialize_quantity(Decimal("10")) == "10"


@pytest.mark.parametrize(
    "payload",
    [
        instrument_payload(display_precision=4),
        instrument_payload(trade_units_precision=1),
        instrument_payload(name="USD_CAD"),
        {
            "instruments": [
                instrument_payload()["instruments"][0],
                instrument_payload()["instruments"][0],
            ],
            "lastTransactionID": "42",
        },
        instrument_payload(minimum_trade_size="0"),
        instrument_payload(maximum_order_units="0"),
    ],
)
def test_instrument_capability_mismatches_fail_closed(payload: dict[str, Any]) -> None:
    with pytest.raises(OandaPracticeExecutionInstrumentNormalizationError):
        reader(
            OandaPracticeExecutionInstrumentReader,
            lambda request: httpx.Response(200, json=payload),
        ).read()


def test_instrument_exactness_rejects_rounding_and_quantity_bound_violations() -> None:
    instrument = reader(
        OandaPracticeExecutionInstrumentReader,
        lambda request: httpx.Response(200, json=instrument_payload()),
    ).read()

    with pytest.raises(
        OandaPracticeExecutionInstrumentNormalizationError, match="price"
    ):
        instrument.serialize_price(Decimal("1.234567"))
    with pytest.raises(
        OandaPracticeExecutionInstrumentNormalizationError, match="quantity"
    ):
        instrument.serialize_quantity(Decimal("1.5"))
    with pytest.raises(
        OandaPracticeExecutionInstrumentNormalizationError, match="bounds"
    ):
        instrument.serialize_quantity(Decimal("1000001"))
