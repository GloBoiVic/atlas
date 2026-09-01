from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from backend.domain.broker import BrokerFactsError
from backend.domain.strategy import Direction
from backend.integrations.oanda import (
    OandaPracticeReadOnlyClient,
    OandaReadOnlyError,
    normalize_account_selection,
    normalize_account_snapshot,
    normalize_executable_quote,
    normalize_instrument_facts,
)

NOW = datetime(2026, 1, 5, 10, 15, tzinfo=UTC)


def account_list() -> dict[str, object]:
    return {
        "accounts": [
            {"id": "practice-1", "mt4AccountID": None, "tags": []},
            {"id": "practice-2", "mt4AccountID": None, "tags": []},
        ]
    }


def account_summary_payload() -> dict[str, object]:
    return {
        "account": {
            "id": "practice-1",
            "currency": "USD",
            "balance": "10000.00",
            "NAV": "10005.50",
            "unrealizedPL": "5.50",
            "marginAvailable": "9000.00",
            "marginUsed": "1000.00",
            "orders": [],
            "trades": [],
            "positions": [],
        },
        "lastTransactionID": "tx-9",
    }


def test_account_selection_is_explicit_and_rejects_mt4_or_unknown_association() -> None:
    assert (
        normalize_account_selection(account_list(), "practice-2").account_id
        == "practice-2"
    )
    with pytest.raises(BrokerFactsError, match="explicit"):
        normalize_account_selection(account_list(), None)
    with pytest.raises(BrokerFactsError, match="not authorized"):
        normalize_account_selection(account_list(), "missing")
    with pytest.raises(BrokerFactsError, match="MT4"):
        normalize_account_selection(
            {"accounts": [{"id": "practice-1", "mt4AccountID": "mt4-1"}]},
            "practice-1",
        )
    with pytest.raises(BrokerFactsError, match="unknown"):
        normalize_account_selection({"accounts": [{"id": "practice-1"}]}, "practice-1")


def test_account_summary_normalizes_usd_facts_and_signed_short_position() -> None:
    payload = account_summary_payload()
    raw = payload["account"]
    assert isinstance(raw, dict)
    raw["orders"] = [
        {
            "id": "o-1",
            "instrument": "EUR_USD",
            "state": "PENDING",
            "units": "1000",
        }
    ]
    raw["trades"] = [
        {
            "id": "t-1",
            "instrument": "EUR_USD",
            "currentUnits": "-1000",
            "initialUnits": "-1000",
        }
    ]
    raw["positions"] = [
        {
            "instrument": "EUR_USD",
            "long": {"units": "0", "openTradeIDs": []},
            "short": {
                "units": "-1000",
                "averagePrice": "1.1000",
                "openTradeIDs": ["t-1"],
            },
        }
    ]
    result = normalize_account_snapshot(
        payload,
        "practice-1",
        observed_at=NOW,
    )
    assert result.identity.account_id == "practice-1"
    assert result.equity == Decimal("10005.50")
    assert result.last_transaction_id == "tx-9"
    assert result.has_open_position
    assert result.position_sides[1].direction is Direction.SHORT
    assert result.position_sides[1].units == Decimal("1000")
    with pytest.raises(BrokerFactsError, match="not USD"):
        normalize_account_snapshot(
            {"account": {"id": "practice-1", "currency": "EUR"}},
            "practice-1",
            observed_at=NOW,
        )


@pytest.mark.parametrize("missing_collection", ("orders", "trades", "positions"))
def test_account_summary_missing_broker_state_collection_is_rejected(
    missing_collection: str,
) -> None:
    payload = account_summary_payload()
    raw = payload["account"]
    assert isinstance(raw, dict)
    del raw[missing_collection]

    with pytest.raises(BrokerFactsError, match=missing_collection):
        normalize_account_snapshot(payload, "practice-1", observed_at=NOW)


def test_instrument_and_quote_normalization_preserve_constraints_and_freshness(
) -> None:
    instrument = normalize_instrument_facts(
        {
            "instruments": [
                {
                    "name": "EUR_USD",
                    "pipLocation": -4,
                    "displayPrecision": 5,
                    "tradeUnitsPrecision": 0,
                    "minimumTradeSize": "1",
                    "maximumOrderUnits": "1000000",
                    "maximumPositionSize": "0",
                    "marginRate": "0.02",
                    "orderTypes": ["MARKET", "STOP_LOSS", "TAKE_PROFIT"],
                }
            ]
        }
    )
    assert instrument.minimum_order_units == Decimal("1")
    assert instrument.maximum_position_units is None
    assert instrument.supports("TAKE_PROFIT")
    quote = normalize_executable_quote(
        {
            "time": "2026-01-05T10:15:00Z",
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "time": "2026-01-05T10:15:00Z",
                    "bids": [{"price": "1.1000"}],
                    "asks": [{"price": "1.1002"}],
                    "closeoutBid": "1.0998",
                    "closeoutAsk": "1.1004",
                    "tradeable": True,
                }
            ],
        }
    )
    assert quote.price_for(Direction.LONG) == Decimal("1.1002")
    assert quote.is_fresh(NOW + timedelta(seconds=30), timedelta(minutes=1))
    assert not quote.is_fresh(NOW + timedelta(minutes=2), timedelta(minutes=1))
    with pytest.raises(BrokerFactsError):
        normalize_executable_quote(
            {
                "prices": [
                    {
                        "instrument": "EUR_USD",
                        "bids": [],
                        "asks": [],
                        "tradeable": True,
                    }
                ]
            }
        )


def test_read_only_client_uses_only_get_and_requires_explicit_account() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"accounts": []})

    client = OandaPracticeReadOnlyClient(
        SecretStr("recorded-token"), transport=httpx.MockTransport(handler)
    )
    client.list_accounts()
    client.account_summary("practice-1")
    client.instrument("practice-1")
    client.pricing("practice-1")
    client.account_changes("practice-1", "42")
    assert methods == ["GET", "GET", "GET", "GET", "GET"]
    with pytest.raises(OandaReadOnlyError):
        client.account_summary("")  # type: ignore[arg-type]
