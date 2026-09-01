import json
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
    OandaConfigurationError,
    OandaPracticeAccountIdentity,
    OandaPracticeEurUsdPricingObservation,
    OandaPracticeEurUsdPricingReader,
    OandaPracticePriceBucket,
    OandaPricingNormalizationError,
    read_oanda_practice_eur_usd_pricing,
)
from backend.integrations.oanda.source import OandaRequestError

TEST_TOKEN = "unit" + "-credential"
ACCOUNT_ID = "001-011-5838423-001"


def account_payload() -> dict[str, Any]:
    return {
        "account": {
            "id": ACCOUNT_ID,
            "currency": "USD",
            "alias": "Research Practice",
        },
        "lastTransactionID": "42",
    }


def pricing_payload(
    *,
    instrument: str = "EUR_USD",
    price_time: Any = "2026-08-31T12:34:56.123456789Z",
    tradeable: Any = True,
    bids: Any = None,
    asks: Any = None,
) -> dict[str, Any]:
    return {
        "time": "not-a-timestamp-that-is-intentionally-ignored",
        "prices": [
            {
                "instrument": instrument,
                "time": price_time,
                "tradeable": tradeable,
                "bids": [{"price": "1.1000", "liquidity": 1000}]
                if bids is None
                else bids,
                "asks": [{"price": "1.1002", "liquidity": 2000}]
                if asks is None
                else asks,
                "status": {"malformed": True},
                "closeoutBid": {"malformed": True},
                "closeoutAsk": ["malformed"],
                "quoteHomeConversionFactors": "malformed",
                "unitsAvailable": {"malformed": True},
            }
        ],
    }


def identity() -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=ACCOUNT_ID,
        alias="Research Practice",
        base_currency="USD",
    )


def reader(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    token: str | None = TEST_TOKEN,
) -> OandaPracticeEurUsdPricingReader:
    return OandaPracticeEurUsdPricingReader(
        SecretStr(token) if token is not None else None,
        identity(),
        transport=httpx.MockTransport(handler),
    )


def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql+psycopg://user@localhost/atlas",
        oanda_api_token=SecretStr(TEST_TOKEN),
        oanda_account_id=ACCOUNT_ID,
    )


def response_with_nonstandard_json(payload: Any) -> httpx.Response:
    return httpx.Response(200, text=json.dumps(payload, allow_nan=True))


def test_helper_binds_account_then_reads_pricing_with_exact_query() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json=account_payload())
        return httpx.Response(200, json=pricing_payload())

    observation = read_oanda_practice_eur_usd_pricing(
        settings(), transport=httpx.MockTransport(handler)
    )

    assert [request.url.path for request in requests] == [
        f"/v3/accounts/{ACCOUNT_ID}/summary",
        f"/v3/accounts/{ACCOUNT_ID}/pricing",
    ]
    assert requests[0].url.query == b""
    assert dict(requests[1].url.params) == {"instruments": "EUR_USD"}
    assert requests[1].method == "GET"
    assert observation.identity == identity()
    assert observation.provider_instrument == "EUR_USD"


def test_reader_normalizes_only_provider_facts_to_immutable_contract() -> None:
    observation = reader(
        lambda request: httpx.Response(200, json=pricing_payload())
    ).read()

    assert observation.price_time == datetime(
        2026, 8, 31, 12, 34, 56, 123456, tzinfo=UTC
    )
    assert observation.tradeable is True
    assert observation.bids == (
        OandaPracticePriceBucket(Decimal("1.1000"), Decimal("1000")),
    )
    assert observation.asks == (
        OandaPracticePriceBucket(Decimal("1.1002"), Decimal("2000")),
    )
    assert {field.name for field in fields(observation)} == {
        "identity",
        "provider_instrument",
        "price_time",
        "tradeable",
        "bids",
        "asks",
    }
    assert not hasattr(observation, "status")
    assert not hasattr(observation, "closeout_bid")
    with pytest.raises(FrozenInstanceError):
        observation.__setattr__("tradeable", False)


@pytest.mark.parametrize(
    "prices",
    [
        [],
        [pricing_payload()["prices"][0], pricing_payload()["prices"][0]],
        [dict(pricing_payload()["prices"][0], instrument="USD_CAD")],
        [
            pricing_payload()["prices"][0],
            dict(pricing_payload()["prices"][0], instrument="USD_CAD"),
        ],
    ],
)
def test_empty_duplicate_extra_or_wrong_prices_fail_closed(
    prices: list[Any],
) -> None:
    payload = pricing_payload()
    payload["prices"] = prices
    with pytest.raises(OandaPricingNormalizationError):
        reader(lambda request: httpx.Response(200, json=payload)).read()


@pytest.mark.parametrize("payload", [[], None, "pricing"])
def test_non_object_top_level_payload_fails_closed(payload: Any) -> None:
    with pytest.raises(OandaPricingNormalizationError, match="not an object"):
        reader(lambda request: response_with_nonstandard_json(payload)).read()


@pytest.mark.parametrize("prices", [None, {}, "prices"])
def test_missing_or_non_list_prices_fail_closed(prices: Any) -> None:
    with pytest.raises(OandaPricingNormalizationError, match="exactly one"):
        reader(lambda request: httpx.Response(200, json={"prices": prices})).read()


def test_non_object_price_item_fails_closed() -> None:
    with pytest.raises(OandaPricingNormalizationError, match="invalid Price"):
        reader(lambda request: httpx.Response(200, json={"prices": ["price"]})).read()


@pytest.mark.parametrize(
    "price_time",
    ["2026-08-31T12:34:56", "not-a-timestamp", "2026-08-31T99:34:56Z", None],
)
def test_missing_malformed_or_timezone_less_timestamp_fails_closed(
    price_time: Any,
) -> None:
    with pytest.raises(OandaPricingNormalizationError, match="time"):
        reader(
            lambda request: httpx.Response(
                200, json=pricing_payload(price_time=price_time)
            )
        ).read()


def test_offset_timestamp_is_normalized_to_utc() -> None:
    observation = reader(
        lambda request: httpx.Response(
            200,
            json=pricing_payload(price_time="2026-08-31T14:34:56+02:00"),
        )
    ).read()
    assert observation.price_time == datetime(2026, 8, 31, 12, 34, 56, tzinfo=UTC)


@pytest.mark.parametrize("tradeable", [True, False])
def test_exact_boolean_tradeability_is_retained(tradeable: bool) -> None:
    observation = reader(
        lambda request: httpx.Response(200, json=pricing_payload(tradeable=tradeable))
    ).read()
    assert observation.tradeable is tradeable


@pytest.mark.parametrize("tradeable", [None, 0, 1, "true", "false"])
def test_non_boolean_tradeability_fails_closed(tradeable: Any) -> None:
    with pytest.raises(OandaPricingNormalizationError, match="tradeable"):
        reader(
            lambda request: httpx.Response(
                200, json=pricing_payload(tradeable=tradeable)
            )
        ).read()


@pytest.mark.parametrize("side", ["bids", "asks"])
@pytest.mark.parametrize("value", [None, {}, "buckets"])
def test_missing_or_non_list_liquidity_side_fails_closed(side: str, value: Any) -> None:
    payload = pricing_payload()
    payload["prices"][0][side] = value
    with pytest.raises(OandaPricingNormalizationError, match=side):
        reader(lambda request: httpx.Response(200, json=payload)).read()


@pytest.mark.parametrize("bucket", [None, [], "bucket", {"price": "1.1000"}])
def test_non_object_or_incomplete_bucket_fails_closed(bucket: Any) -> None:
    with pytest.raises(OandaPricingNormalizationError):
        reader(
            lambda request: httpx.Response(200, json=pricing_payload(bids=[bucket]))
        ).read()


@pytest.mark.parametrize(
    ("bids", "asks"),
    [
        ([], [{"price": "1.1002", "liquidity": 1}]),
        ([{"price": "1.1000", "liquidity": 1}], []),
        ([], []),
    ],
)
def test_empty_liquidity_sides_are_valid(
    bids: list[dict[str, Any]], asks: list[dict[str, Any]]
) -> None:
    observation = reader(
        lambda request: httpx.Response(200, json=pricing_payload(bids=bids, asks=asks))
    ).read()
    assert observation.bids == tuple(
        OandaPracticePriceBucket(Decimal(bucket["price"]), Decimal(bucket["liquidity"]))
        for bucket in bids
    )
    assert observation.asks == tuple(
        OandaPracticePriceBucket(Decimal(bucket["price"]), Decimal(bucket["liquidity"]))
        for bucket in asks
    )


def test_bucket_order_is_preserved_without_market_interpretation() -> None:
    bids = [
        {"price": "1.1010", "liquidity": 10},
        {"price": "1.0990", "liquidity": 20},
        {"price": "1.1000", "liquidity": 30},
    ]
    asks = [
        {"price": "1.1050", "liquidity": 40},
        {"price": "1.1020", "liquidity": 50},
    ]
    observation = reader(
        lambda request: httpx.Response(200, json=pricing_payload(bids=bids, asks=asks))
    ).read()
    assert [bucket.price for bucket in observation.bids] == [
        Decimal("1.1010"),
        Decimal("1.0990"),
        Decimal("1.1000"),
    ]
    assert [bucket.price for bucket in observation.asks] == [
        Decimal("1.1050"),
        Decimal("1.1020"),
    ]


@pytest.mark.parametrize(
    "bucket_price",
    ["malformed", "0", "-1", "NaN", "Infinity", None, 1.1],
)
def test_bucket_price_requires_positive_finite_provider_string(
    bucket_price: Any,
) -> None:
    with pytest.raises(OandaPricingNormalizationError, match="price"):
        reader(
            lambda request: httpx.Response(
                200,
                json=pricing_payload(bids=[{"price": bucket_price, "liquidity": 1}]),
            )
        ).read()


@pytest.mark.parametrize("liquidity", [0, 12, 1.25])
def test_bucket_liquidity_accepts_finite_nonnegative_json_numbers(
    liquidity: int | float,
) -> None:
    observation = reader(
        lambda request: httpx.Response(
            200,
            json=pricing_payload(bids=[{"price": "1.1000", "liquidity": liquidity}]),
        )
    ).read()
    assert observation.bids[0].liquidity == Decimal(str(liquidity))


@pytest.mark.parametrize(
    "liquidity",
    [True, False, -1, -1.25, float("nan"), float("inf"), "10", None, {}, []],
)
def test_bucket_liquidity_rejects_bool_invalid_or_non_numeric_values(
    liquidity: Any,
) -> None:
    with pytest.raises(OandaPricingNormalizationError, match="liquidity"):
        reader(
            lambda request: response_with_nonstandard_json(
                pricing_payload(bids=[{"price": "1.1000", "liquidity": liquidity}])
            )
        ).read()


def test_ignored_malformed_fields_and_closeout_prices_do_not_invalidate_result() -> (
    None
):
    observation = reader(
        lambda request: httpx.Response(200, json=pricing_payload())
    ).read()
    assert observation.provider_instrument == "EUR_USD"
    assert observation.bids[0].price == Decimal("1.1000")


def test_request_failures_are_propagated_as_sanitized_request_errors() -> None:
    with pytest.raises(OandaRequestError, match="pricing request was rejected"):
        reader(lambda request: httpx.Response(400, text=f"secret {TEST_TOKEN}")).read()


def test_blank_reader_token_fails_before_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=pricing_payload())

    with pytest.raises(OandaConfigurationError, match="API token is required"):
        reader(handler, token=" ").read()
    assert calls == 0


def test_reader_rejects_an_unvalidated_account_identity() -> None:
    with pytest.raises(OandaPricingNormalizationError, match="validated account"):
        OandaPracticeEurUsdPricingReader(
            SecretStr(TEST_TOKEN),
            object(),  # type: ignore[arg-type]
        )


def test_pricing_contracts_reject_invalid_direct_values() -> None:
    with pytest.raises(OandaPricingNormalizationError):
        OandaPracticePriceBucket(Decimal("0"), Decimal("1"))
    with pytest.raises(OandaPricingNormalizationError):
        OandaPracticePriceBucket(Decimal("1"), Decimal("-1"))
    with pytest.raises(OandaPricingNormalizationError):
        OandaPracticeEurUsdPricingObservation(
            identity(),
            "EUR_USD",
            datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
            True,
            [],  # type: ignore[arg-type]
            (),
        )
