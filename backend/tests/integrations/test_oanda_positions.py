from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
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
    OandaOpenPositionNormalizationError,
    OandaPracticeAccountIdentity,
    OandaPracticeOpenPositionReader,
    OandaPracticePositionSide,
    OandaRequestError,
    read_oanda_practice_open_position_inventory,
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


def provider_side(
    units: str,
    *,
    average_price: str | None = "1.1000",
    include_average_price: bool = True,
    unrealized_pl: str = "1.25",
) -> dict[str, Any]:
    side: dict[str, Any] = {
        "units": units,
        "unrealizedPL": unrealized_pl,
        "tradeIDs": ["must-not-leak"],
        "pl": "must-not-leak",
        "resettablePL": "must-not-leak",
    }
    if include_average_price:
        side["averagePrice"] = average_price
    return side


def provider_position(
    instrument: str = "EUR_USD",
    *,
    unrealized_pl: str = "2.50",
    long_units: str = "100",
    short_units: str = "-50",
    long_average_price: str | None = "1.1000",
    short_average_price: str | None = "1.2000",
    long_include_average_price: bool = True,
    short_include_average_price: bool = True,
    long_unrealized_pl: str = "3.00",
    short_unrealized_pl: str = "-0.50",
) -> dict[str, Any]:
    return {
        "instrument": instrument,
        "unrealizedPL": unrealized_pl,
        "long": provider_side(
            long_units,
            average_price=long_average_price,
            include_average_price=long_include_average_price,
            unrealized_pl=long_unrealized_pl,
        ),
        "short": provider_side(
            short_units,
            average_price=short_average_price,
            include_average_price=short_include_average_price,
            unrealized_pl=short_unrealized_pl,
        ),
        "pl": "must-not-leak",
        "resettablePL": "must-not-leak",
        "marginUsed": "must-not-leak",
        "financing": "must-not-leak",
        "commission": "must-not-leak",
        "dividendAdjustment": "must-not-leak",
        "guaranteedExecutionFees": "must-not-leak",
    }


def reader(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    identity: OandaPracticeAccountIdentity | None = None,
    token: str = TEST_TOKEN,
) -> OandaPracticeOpenPositionReader:
    return OandaPracticeOpenPositionReader(
        SecretStr(token),
        identity or account_identity(),
        transport=httpx.MockTransport(handler),
    )


def position_payload(
    positions: list[dict[str, Any]], last_transaction_id: str = "99"
) -> dict[str, Any]:
    return {"positions": positions, "lastTransactionID": last_transaction_id}


def test_settings_helper_reads_open_positions_after_account_validation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json=account_payload())
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/openPositions"
        assert request.method == "GET"
        assert len(request.url.params) == 0
        assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
        assert request.headers["Accept-Datetime-Format"] == "RFC3339"
        return httpx.Response(
            200,
            json=position_payload(
                [provider_position("USD_CAD", long_units="0", short_units="-2")]
            ),
        )

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql+psycopg://user@localhost/atlas",
        oanda_api_token=SecretStr(TEST_TOKEN),
        oanda_account_id=ACCOUNT_ID,
    )
    inventory = read_oanda_practice_open_position_inventory(
        settings, transport=httpx.MockTransport(handler)
    )

    assert [request.url.path for request in requests] == [
        f"/v3/accounts/{ACCOUNT_ID}/summary",
        f"/v3/accounts/{ACCOUNT_ID}/openPositions",
    ]
    assert inventory.identity == account_identity()
    assert inventory.last_transaction_id == "99"
    assert [position.provider_instrument for position in inventory.positions] == [
        "USD_CAD"
    ]


def test_inventory_preserves_both_provider_sides_and_ignores_unretained_facts() -> None:
    position = (
        reader(
            lambda request: httpx.Response(
                200,
                json=position_payload(
                    [
                        provider_position(
                            "XAU_USD",
                            unrealized_pl="-8.25",
                            long_units="12.5",
                            short_units="-7.5",
                            long_unrealized_pl="-10",
                            short_unrealized_pl="1.75",
                        )
                    ]
                ),
            )
        )
        .read()
        .positions[0]
    )

    assert position.provider_instrument == "XAU_USD"
    assert position.unrealized_pl == Decimal("-8.25")
    assert position.long == OandaPracticePositionSide(
        units=Decimal("12.5"),
        average_price=Decimal("1.1000"),
        unrealized_pl=Decimal("-10"),
    )
    assert position.short == OandaPracticePositionSide(
        units=Decimal("-7.5"),
        average_price=Decimal("1.2000"),
        unrealized_pl=Decimal("1.75"),
    )
    assert {field.name for field in fields(position)} == {
        "provider_instrument",
        "unrealized_pl",
        "long",
        "short",
    }
    assert {field.name for field in fields(position.long)} == {
        "units",
        "average_price",
        "unrealized_pl",
    }
    for forbidden in (
        "pl",
        "resettable_pl",
        "margin_used",
        "financing",
        "commission",
        "dividend_adjustment",
        "guaranteed_execution_fees",
        "trade_ids",
        "direction",
        "position",
        "fill",
    ):
        assert not hasattr(position, forbidden)
        assert not hasattr(position.long, forbidden)


def test_position_order_does_not_change_equality_and_sorts_instrument() -> None:
    first = position_payload(
        [
            provider_position(
                "XAU_USD",
                long_units="1",
                short_units="0",
                short_include_average_price=False,
            ),
            provider_position(
                "EUR_USD",
                long_units="2",
                short_units="0",
                short_include_average_price=False,
            ),
            provider_position(
                "USD_CAD",
                long_units="0",
                short_units="-3",
                long_include_average_price=False,
            ),
        ]
    )
    second = position_payload(list(reversed(first["positions"])))

    left = reader(lambda request: httpx.Response(200, json=first)).read()
    right = reader(lambda request: httpx.Response(200, json=second)).read()

    assert left == right
    assert [position.provider_instrument for position in left.positions] == [
        "EUR_USD",
        "USD_CAD",
        "XAU_USD",
    ]


def test_empty_inventory_is_explicit_and_immutable() -> None:
    inventory = reader(
        lambda request: httpx.Response(
            200, json=position_payload([], last_transaction_id="7")
        )
    ).read()

    assert inventory.positions == ()
    assert {field.name for field in fields(inventory)} == {
        "identity",
        "positions",
        "last_transaction_id",
    }
    with pytest.raises(FrozenInstanceError):
        inventory.__setattr__("positions", ())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("instrument", None),
        ("instrument", "EURUSD"),
        ("instrument", "_USD"),
        ("instrument", "EUR_"),
        ("instrument", "EUR_USD_EXTRA"),
        ("unrealizedPL", None),
        ("unrealizedPL", "NaN"),
        ("unrealizedPL", "Infinity"),
    ],
)
def test_malformed_position_fields_fail_closed(field: str, value: Any) -> None:
    payload_position = provider_position()
    payload_position[field] = value

    with pytest.raises(OandaOpenPositionNormalizationError):
        reader(
            lambda request: httpx.Response(
                200, json=position_payload([payload_position])
            )
        ).read()


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("value", [None, "NaN", "Infinity", 1])
def test_malformed_side_fields_fail_closed(side: str, value: Any) -> None:
    payload_position = provider_position()
    payload_position[side]["unrealizedPL"] = value

    with pytest.raises(OandaOpenPositionNormalizationError):
        reader(
            lambda request: httpx.Response(
                200, json=position_payload([payload_position])
            )
        ).read()


@pytest.mark.parametrize(
    ("side", "value"),
    [("long", "-1"), ("short", "1"), ("long", "NaN"), ("short", "Infinity")],
)
def test_side_units_are_finite_and_keep_provider_sign_semantics(
    side: str, value: str
) -> None:
    payload_position = provider_position()
    payload_position[side]["units"] = value

    with pytest.raises(OandaOpenPositionNormalizationError):
        reader(
            lambda request: httpx.Response(
                200, json=position_payload([payload_position])
            )
        ).read()


def test_zero_sides_are_explicit_but_both_zero_is_contradictory() -> None:
    position = (
        reader(
            lambda request: httpx.Response(
                200,
                json=position_payload(
                    [
                        provider_position(
                            long_units="0",
                            short_units="-2",
                            long_include_average_price=False,
                        )
                    ]
                ),
            )
        )
        .read()
        .positions[0]
    )
    assert position.long.units == Decimal("0")
    assert position.long.average_price is None
    assert position.short.units == Decimal("-2")

    with pytest.raises(OandaOpenPositionNormalizationError, match="no exposed"):
        reader(
            lambda request: httpx.Response(
                200,
                json=position_payload(
                    [
                        provider_position(
                            long_units="0",
                            short_units="0",
                            long_include_average_price=False,
                            short_include_average_price=False,
                        )
                    ]
                ),
            )
        ).read()


@pytest.mark.parametrize(
    ("side", "include_average_price", "average_price"),
    [
        ("long", False, None),
        ("short", False, None),
        ("long", True, None),
        ("short", True, None),
    ],
)
def test_average_price_is_conditional_on_exposure(
    side: str, include_average_price: bool, average_price: str | None
) -> None:
    payload_position = provider_position()
    payload_position[side]["units"] = "0" if side == "long" else "-1"
    payload_position[side]["averagePrice"] = average_price
    if not include_average_price:
        del payload_position[side]["averagePrice"]

    if side == "short" and not include_average_price:
        with pytest.raises(OandaOpenPositionNormalizationError, match="averagePrice"):
            reader(
                lambda request: httpx.Response(
                    200, json=position_payload([payload_position])
                )
            ).read()
        return
    if side == "long" and not include_average_price:
        position = (
            reader(
                lambda request: httpx.Response(
                    200, json=position_payload([payload_position])
                )
            )
            .read()
            .positions[0]
        )
        assert position.long.average_price is None
        return

    with pytest.raises(OandaOpenPositionNormalizationError, match="averagePrice"):
        reader(
            lambda request: httpx.Response(
                200, json=position_payload([payload_position])
            )
        ).read()


@pytest.mark.parametrize("average_price", ["NaN", "Infinity", "0", "-1", 1, None])
def test_supplied_average_price_must_be_finite_positive_provider_decimal(
    average_price: Any,
) -> None:
    payload_position = provider_position()
    payload_position["long"]["units"] = "0"
    payload_position["long"]["averagePrice"] = average_price

    with pytest.raises(OandaOpenPositionNormalizationError, match="averagePrice"):
        reader(
            lambda request: httpx.Response(
                200, json=position_payload([payload_position])
            )
        ).read()


def test_duplicate_instruments_fail_without_merge_or_deduplication() -> None:
    for duplicate in (
        provider_position(
            "EUR_USD",
            long_units="1",
            short_units="0",
            short_include_average_price=False,
        ),
        provider_position(
            "EUR_USD",
            long_units="9",
            short_units="0",
            short_include_average_price=False,
        ),
    ):
        with pytest.raises(
            OandaOpenPositionNormalizationError, match="duplicate instruments"
        ):
            reader(
                lambda request, duplicate=duplicate: httpx.Response(
                    200,
                    json=position_payload(
                        [
                            provider_position(
                                "EUR_USD",
                                long_units="1",
                                short_units="0",
                                short_include_average_price=False,
                            ),
                            duplicate,
                        ]
                    ),
                )
            ).read()


@pytest.mark.parametrize(
    "positions_value",
    [None, {}, [None], ["position"], [provider_position() | {"long": None}]],
)
def test_malformed_position_collection_fails_without_partial_inventory(
    positions_value: Any,
) -> None:
    with pytest.raises(OandaOpenPositionNormalizationError):
        reader(
            lambda request: httpx.Response(
                200,
                json={"positions": positions_value, "lastTransactionID": "7"},
            )
        ).read()


@pytest.mark.parametrize("last_transaction_id", [None, "", "1.5", "-1", 7])
def test_invalid_position_transaction_provenance_fails_closed(
    last_transaction_id: Any,
) -> None:
    with pytest.raises(OandaOpenPositionNormalizationError, match="lastTransactionID"):
        reader(
            lambda request: httpx.Response(
                200,
                json={"positions": [], "lastTransactionID": last_transaction_id},
            )
        ).read()


def test_invalid_json_and_provider_errors_are_sanitized_and_not_retried() -> None:
    body = f"provider body {TEST_TOKEN}"
    with pytest.raises(OandaRequestError) as invalid_json:
        reader(lambda request: httpx.Response(200, text=body)).read()
    assert "invalid open Positions JSON" in str(invalid_json.value)
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


def test_transient_position_read_retries_only_same_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "GET"
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/openPositions"
        assert len(request.url.params) == 0
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "999"})
        return httpx.Response(200, json=position_payload([]))

    monkeypatch.setattr("backend.integrations.oanda.positions.sleep", sleeps.append)
    result = reader(handler).read()

    assert result.positions == ()
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

    monkeypatch.setattr("backend.integrations.oanda.positions.sleep", sleeps.append)
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
        return httpx.Response(200, json=position_payload([]))

    value = SecretStr(token) if token is not None else None
    with pytest.raises(OandaConfigurationError, match="API token is required"):
        OandaPracticeOpenPositionReader(
            value,
            account_identity(),
            transport=httpx.MockTransport(handler),
        ).read()
    assert calls == 0


def test_reader_requires_validated_account_identity() -> None:
    with pytest.raises(OandaOpenPositionNormalizationError, match="identity"):
        OandaPracticeOpenPositionReader(
            SecretStr(TEST_TOKEN),
            object(),  # type: ignore[arg-type]
        )
