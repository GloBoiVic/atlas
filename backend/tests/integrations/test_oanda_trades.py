from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.config import Settings
from backend.domain.market_data import Provider
from backend.integrations.oanda import (
    OandaAuthError,
    OandaConfigurationError,
    OandaOpenTradeNormalizationError,
    OandaPracticeAccountIdentity,
    OandaPracticeOpenTrade,
    OandaPracticeOpenTradeReader,
    OandaRequestError,
    read_oanda_practice_open_trade_inventory,
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


def provider_trade(
    provider_trade_id: str = "20",
    *,
    instrument: str = "USD_CAD",
    open_time: str = "2026-01-05T10:00:00.123456+02:00",
    price: str = "1.23450",
    current_units: str = "-1000",
    state: str = "CLOSE_WHEN_TRADEABLE",
    unrealized_pl: str = "-12.50",
) -> dict[str, Any]:
    return {
        "id": provider_trade_id,
        "instrument": instrument,
        "openTime": open_time,
        "price": price,
        "currentUnits": current_units,
        "state": state,
        "unrealizedPL": unrealized_pl,
        "initialUnits": "-1000",
        "initialMarginRequired": "100.00",
        "realizedPL": "4.00",
        "financing": "2.00",
        "dividendAdjustment": "0",
        "marginUsed": "100.00",
        "averageClosePrice": "1.2000",
        "closingTransactionIDs": ["999"],
        "closeTime": "2026-01-05T11:00:00Z",
        "clientExtensions": {"comment": "must not leak"},
        "takeProfitOrder": {"id": "must-not-leak"},
        "stopLossOrder": {"id": "must-not-leak"},
        "trailingStopLossOrder": {"id": "must-not-leak"},
    }


def reader(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    identity: OandaPracticeAccountIdentity | None = None,
    token: str = TEST_TOKEN,
) -> OandaPracticeOpenTradeReader:
    return OandaPracticeOpenTradeReader(
        SecretStr(token),
        identity or account_identity(),
        transport=httpx.MockTransport(handler),
    )


def test_settings_helper_reads_open_trades_after_account_validation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json=account_payload())
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/openTrades"
        assert len(request.url.params) == 0
        assert request.method == "GET"
        assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
        assert request.headers["Accept-Datetime-Format"] == "RFC3339"
        return httpx.Response(
            200,
            json={
                "trades": [provider_trade()],
                "lastTransactionID": "99",
            },
        )

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql+psycopg://user@localhost/atlas",
        oanda_api_token=SecretStr(TEST_TOKEN),
        oanda_account_id=ACCOUNT_ID,
    )
    inventory = read_oanda_practice_open_trade_inventory(
        settings, transport=httpx.MockTransport(handler)
    )

    assert [request.url.path for request in requests] == [
        f"/v3/accounts/{ACCOUNT_ID}/summary",
        f"/v3/accounts/{ACCOUNT_ID}/openTrades",
    ]
    assert len(requests) == 2
    assert inventory.identity == account_identity()
    assert inventory.last_transaction_id == "99"
    assert inventory.trades[0] == OandaPracticeOpenTrade(
        provider_trade_id="20",
        provider_instrument="USD_CAD",
        open_time=datetime(2026, 1, 5, 8, 0, 0, 123456, tzinfo=UTC),
        open_price=Decimal("1.23450"),
        current_units=Decimal("-1000"),
        state="CLOSE_WHEN_TRADEABLE",
        unrealized_pl=Decimal("-12.50"),
    )


def test_successful_inventory_keeps_provider_facts_and_ignores_details() -> None:
    payload = {
        "trades": [
            provider_trade(
                "20",
                current_units="-1000",
                unrealized_pl="-12.50",
            ),
            provider_trade(
                "3",
                instrument="EUR_USD",
                open_time="2026-01-05T10:00:00Z",
                price="1.1",
                current_units="250",
                state="OPEN",
                unrealized_pl="0",
            ),
            provider_trade(
                "100",
                instrument="XAU_USD",
                open_time="2026-01-05T10:00:01Z",
                price="2000",
                current_units="1",
                unrealized_pl="8.25",
            ),
        ],
        "lastTransactionID": "1000",
    }

    inventory = reader(lambda request: httpx.Response(200, json=payload)).read()

    assert [trade.provider_trade_id for trade in inventory.trades] == [
        "3",
        "20",
        "100",
    ]
    assert [trade.current_units for trade in inventory.trades] == [
        Decimal("250"),
        Decimal("-1000"),
        Decimal("1"),
    ]
    assert [trade.unrealized_pl for trade in inventory.trades] == [
        Decimal("0"),
        Decimal("-12.50"),
        Decimal("8.25"),
    ]
    assert inventory.trades[2].provider_instrument == "XAU_USD"
    assert {field.name for field in fields(inventory.trades[0])} == {
        "provider_trade_id",
        "provider_instrument",
        "open_time",
        "open_price",
        "current_units",
        "state",
        "unrealized_pl",
    }
    for forbidden in (
        "initial_units",
        "initial_margin_required",
        "realized_pl",
        "financing",
        "margin_used",
        "close_time",
        "client_extensions",
        "take_profit_order",
        "stop_loss_order",
    ):
        assert not hasattr(inventory.trades[0], forbidden)


def test_provider_array_order_does_not_change_inventory_equality() -> None:
    first = {
        "trades": [provider_trade("100"), provider_trade("2")],
        "lastTransactionID": "7",
    }
    second = {
        "trades": [provider_trade("2"), provider_trade("100")],
        "lastTransactionID": "7",
    }

    left = reader(lambda request: httpx.Response(200, json=first)).read()
    right = reader(lambda request: httpx.Response(200, json=second)).read()
    assert left == right


def test_leading_zero_trade_ids_have_total_permutation_invariant_order() -> None:
    first = {
        "trades": [provider_trade("01"), provider_trade("1")],
        "lastTransactionID": "7",
    }
    second = {
        "trades": [provider_trade("1"), provider_trade("01")],
        "lastTransactionID": "7",
    }

    left = reader(lambda request: httpx.Response(200, json=first)).read()
    right = reader(lambda request: httpx.Response(200, json=second)).read()

    assert left == right
    assert [trade.provider_trade_id for trade in left.trades] == ["01", "1"]


def test_empty_inventory_is_explicit_and_immutable() -> None:
    inventory = reader(
        lambda request: httpx.Response(
            200, json={"trades": [], "lastTransactionID": "7"}
        )
    ).read()

    assert inventory.trades == ()
    assert {field.name for field in fields(inventory)} == {
        "identity",
        "trades",
        "last_transaction_id",
    }
    with pytest.raises(FrozenInstanceError):
        inventory.__setattr__("trades", ())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", None),
        ("id", "0"),
        ("id", "-1"),
        ("id", 1),
        ("instrument", "EURUSD"),
        ("instrument", "_USD"),
        ("instrument", "EUR_"),
        ("instrument", "EUR_USD_EXTRA"),
        ("price", None),
        ("price", "NaN"),
        ("price", "Infinity"),
        ("price", "0"),
        ("price", "-1"),
        ("currentUnits", None),
        ("currentUnits", "NaN"),
        ("currentUnits", "0"),
        ("openTime", None),
        ("openTime", "2026-01-05T10:00:00"),
        ("openTime", "not-a-time"),
        ("state", "CLOSED"),
        ("state", "UNKNOWN"),
        ("unrealizedPL", None),
        ("unrealizedPL", "NaN"),
    ],
)
def test_malformed_retained_trade_fields_fail_closed(field: str, value: Any) -> None:
    payload_trade = provider_trade()
    payload_trade[field] = value
    payload = {"trades": [payload_trade], "lastTransactionID": "7"}

    with pytest.raises(OandaOpenTradeNormalizationError):
        reader(lambda request: httpx.Response(200, json=payload)).read()


def test_trade_state_and_signed_units_are_normalized_without_atlas_state() -> None:
    payload_trade = provider_trade(
        state="OPEN", current_units="100.25", unrealized_pl="0"
    )
    trade = (
        reader(
            lambda request: httpx.Response(
                200, json={"trades": [payload_trade], "lastTransactionID": "7"}
            )
        )
        .read()
        .trades[0]
    )

    assert trade.state == "OPEN"
    assert trade.current_units == Decimal("100.25")
    assert not hasattr(trade, "direction")
    assert not hasattr(trade, "position")
    assert not hasattr(trade, "fill")


@pytest.mark.parametrize(
    "trades_value",
    [None, {}, [None], ["trade"], [provider_trade() | {"state": "CLOSED"}]],
)
def test_malformed_trade_collection_fails_without_partial_inventory(
    trades_value: Any,
) -> None:
    with pytest.raises(OandaOpenTradeNormalizationError):
        reader(
            lambda request: httpx.Response(
                200,
                json={"trades": trades_value, "lastTransactionID": "7"},
            )
        ).read()


def test_duplicate_identical_and_conflicting_trade_ids_fail_closed() -> None:
    for duplicate in (
        provider_trade("20"),
        provider_trade("20", price="9.9"),
    ):
        with pytest.raises(OandaOpenTradeNormalizationError, match="duplicate"):
            reader(
                lambda request, duplicate=duplicate: httpx.Response(
                    200,
                    json={
                        "trades": [provider_trade("20"), duplicate],
                        "lastTransactionID": "7",
                    },
                )
            ).read()


@pytest.mark.parametrize("last_transaction_id", [None, "", "1.5", "-1", 7])
def test_invalid_open_trade_transaction_provenance_fails_closed(
    last_transaction_id: Any,
) -> None:
    with pytest.raises(OandaOpenTradeNormalizationError, match="lastTransactionID"):
        reader(
            lambda request: httpx.Response(
                200,
                json={
                    "trades": [],
                    "lastTransactionID": last_transaction_id,
                },
            )
        ).read()


def test_invalid_json_and_provider_errors_are_sanitized_and_not_retried() -> None:
    body = f"provider body {TEST_TOKEN}"
    with pytest.raises(OandaRequestError) as invalid_json:
        reader(lambda request: httpx.Response(200, text=body)).read()
    assert "invalid open Trades JSON" in str(invalid_json.value)
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


def test_non_object_json_remains_trade_normalization_failure() -> None:
    with pytest.raises(
        OandaOpenTradeNormalizationError,
        match="open Trades response is not an object",
    ):
        reader(lambda request: httpx.Response(200, json=[])).read()


def test_transient_open_trade_read_retries_only_same_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "GET"
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/openTrades"
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "999"})
        return httpx.Response(200, json={"trades": [], "lastTransactionID": "7"})

    monkeypatch.setattr("backend.integrations.oanda.request.sleep", sleeps.append)
    result = reader(handler).read()

    assert result.trades == ()
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


@pytest.mark.parametrize(
    "token",
    [None, " "],
)
def test_missing_or_blank_token_fails_without_network(token: str | None) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"trades": [], "lastTransactionID": "7"})

    value = SecretStr(token) if token is not None else None
    with pytest.raises(OandaConfigurationError, match="API token is required"):
        OandaPracticeOpenTradeReader(
            value,
            account_identity(),
            transport=httpx.MockTransport(handler),
        ).read()
    assert calls == 0
