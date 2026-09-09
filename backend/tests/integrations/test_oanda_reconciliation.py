from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from backend.domain import Direction
from backend.integrations.oanda import (
    OandaPracticeReconciliationReader,
    OandaReconciliationNormalizationError,
)
from backend.paper import (
    PAPER_BROKER_FACTS_SCHEMA_V2,
    PaperObservationReadKind,
    PaperReconciliationContext,
    PaperReconciliationReadState,
    PaperTradeExitCause,
)

TEST_TOKEN = "unit-credential"
ACCOUNT_ID = "001-011-5838423-001"
ATTEMPT_ID = UUID("12345678-1234-5678-1234-567812345678")
CLIENT_ORDER_ID = f"atlas-p04-o-{ATTEMPT_ID.hex}"
CLIENT_TRADE_ID = f"atlas-p04-t-{ATTEMPT_ID.hex}"
CLIENT_STOP_ID = f"atlas-p04-sl-{ATTEMPT_ID.hex}"
CLIENT_TARGET_ID = f"atlas-p04-tp-{ATTEMPT_ID.hex}"


def context() -> PaperReconciliationContext:
    return PaperReconciliationContext(
        attempt_id=ATTEMPT_ID,
        provider_account_id=ACCOUNT_ID,
        instrument="EUR_USD",
        direction=Direction.LONG,
        signed_requested_units=Decimal("19230"),
        approved_entry_price=Decimal("1.10020"),
        stop_price=Decimal("1.09500"),
        client_order_id=CLIENT_ORDER_ID,
        client_trade_id=CLIENT_TRADE_ID,
        client_stop_loss_order_id=CLIENT_STOP_ID,
        client_take_profit_order_id=CLIENT_TARGET_ID,
        provider_order_id=None,
        provider_trade_id=None,
        actual_target_price=Decimal("1.11030"),
        take_profit_claimed=True,
        pre_entry_transaction_id="10",
    )


def order_create() -> dict[str, Any]:
    return {
        "id": "11",
        "accountID": ACCOUNT_ID,
        "type": "MARKET_ORDER",
        "instrument": "EUR_USD",
        "units": "19230",
        "timeInForce": "FOK",
        "positionFill": "OPEN_ONLY",
        "priceBound": "1.10020",
        "state": "PENDING",
        "clientExtensions": {"id": CLIENT_ORDER_ID, "tag": "atlas-paper-04"},
        "tradeClientExtensions": {"id": CLIENT_TRADE_ID},
        "stopLossOnFill": {
            "price": "1.09500",
            "timeInForce": "GTC",
            "clientExtensions": {"id": CLIENT_STOP_ID},
        },
    }


def order_fill() -> dict[str, Any]:
    return {
        "id": "12",
        "accountID": ACCOUNT_ID,
        "type": "ORDER_FILL",
        "orderID": "11",
        "clientOrderID": CLIENT_ORDER_ID,
        "instrument": "EUR_USD",
        "units": "19230",
        "time": "2026-09-02T12:00:00.000000000Z",
        "tradeOpened": {
            "tradeID": "7001",
            "units": "19230",
            "price": "1.10010",
        },
    }


def account_details(
    *, positions: list[dict[str, Any]] | None = None, position_count: int = 0
) -> dict[str, Any]:
    return {
        "account": {
            "id": ACCOUNT_ID,
            "currency": "USD",
            "alias": "Research Practice",
            "balance": "100000.00",
            "NAV": "100000.00",
            "unrealizedPL": "0.00",
            "marginUsed": "0.00",
            "marginAvailable": "100000.00",
            "openTradeCount": 0,
            "openPositionCount": position_count,
            "pendingOrderCount": 0,
            "trades": [],
            "positions": positions or [],
            "orders": [],
            "guaranteedStopLossOrderMode": "DISABLED",
            "hedgingEnabled": True,
            "lastTransactionID": "12",
        },
        "lastTransactionID": "12",
    }


def account_position(
    *, long_units: str = "0", short_units: str = "0", minimal: bool = False
) -> dict[str, Any]:
    long_side: dict[str, Any] = {"units": long_units}
    short_side: dict[str, Any] = {"units": short_units}
    if not minimal:
        long_side.update({"averagePrice": "1.1000", "unrealizedPL": "0.00"})
        short_side.update({"averagePrice": "1.1000", "unrealizedPL": "0.00"})
    return {
        "instrument": "EUR_USD",
        "long": long_side,
        "short": short_side,
        **({"unrealizedPL": "0.00"} if not minimal else {}),
    }


def trade_detail() -> dict[str, Any]:
    return {
        "trade": {
            "id": "7001",
            "instrument": "EUR_USD",
            "clientExtensions": {"id": CLIENT_TRADE_ID},
            "state": "OPEN",
            "currentUnits": "19230",
            "price": "1.10010",
            "openTime": "2026-09-02T12:00:00.000000000Z",
            "stopLossOrder": {
                "id": "8001",
                "type": "STOP_LOSS",
                "tradeID": "7001",
                "price": "1.09500",
                "timeInForce": "GTC",
                "state": "PENDING",
                "clientExtensions": {"id": CLIENT_STOP_ID},
            },
            "takeProfitOrder": {
                "id": "9001",
                "type": "TAKE_PROFIT",
                "tradeID": "7001",
                "price": "1.11030",
                "timeInForce": "GTC",
                "state": "PENDING",
                "clientExtensions": {"id": CLIENT_TARGET_ID},
            },
        }
    }


def closed_trade_detail(
    *, closing_transaction_ids: list[str] | None = None
) -> dict[str, Any]:
    trade = trade_detail()["trade"]
    trade.update(
        {
            "state": "CLOSED",
            "currentUnits": "0",
            "initialUnits": "19230",
            "closeTime": "2026-09-03T13:00:00.000000000+02:00",
            "averageClosePrice": "1.11030",
            "realizedPL": "196.1538",
            "financing": "-0.42",
            "dividendAdjustment": "0",
            "closingTransactionIDs": closing_transaction_ids or ["43"],
        }
    )
    return {"trade": trade}


def close_transaction(
    *,
    reason: str | None = "TAKE_PROFIT_ORDER",
    trade_id: str = "7001",
    transaction_id: str = "43",
    reduction_key: str = "tradesClosed",
) -> dict[str, Any]:
    reduction = {
        "tradeID": trade_id,
        "units": "19230",
        "price": "1.11035",
        "realizedPL": "196.1538",
        "financing": "-0.42",
    }
    transaction: dict[str, Any] = {
        "id": transaction_id,
        "accountID": ACCOUNT_ID,
        "type": "ORDER_FILL",
        "instrument": "EUR_USD",
        "time": "2026-09-03T11:00:00Z",
        "price": "9.99999",
        reduction_key: [reduction] if reduction_key == "tradesClosed" else reduction,
    }
    if reason is not None:
        transaction["reason"] = reason
    return {"orderFillTransaction": transaction}


def documented_transaction_response(
    transaction: dict[str, Any], *, last_transaction_id: str
) -> dict[str, Any]:
    return {
        "transaction": transaction,
        "lastTransactionID": last_transaction_id,
    }


def reader(handler: Any) -> OandaPracticeReconciliationReader:
    return OandaPracticeReconciliationReader(
        SecretStr(TEST_TOKEN),
        ACCOUNT_ID,
        transport=httpx.MockTransport(handler),
        clock=lambda: datetime(2026, 9, 2, 12, tzinfo=UTC),
    )


def static_response(
    payload: Any,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload, headers=headers)

    return handler


def test_oanda_reader_normalizes_bounded_fill_range_and_uses_only_get() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
        assert request.headers["Accept-Datetime-Format"] == "RFC3339"
        create = order_create()
        create["batchID"] = "10"
        create["relatedTransactionIDs"] = ["10", "11"]
        fill = order_fill()
        fill["batchID"] = "11"
        fill["relatedTransactionIDs"] = ["11", "12"]
        return httpx.Response(
            200,
            json={
                "transactions": [create, fill],
                "lastTransactionID": "12",
            },
            headers={"RequestID": "request-range"},
        )

    result = reader(handler).read_transaction_range(context(), "11", "12")

    assert result.state is PaperReconciliationReadState.RANGE
    assert result.attributable is True
    assert result.fill is not None
    assert result.fill.broker_order_id == "11"
    assert result.fill.broker_trade_id == "7001"
    assert result.observation.request_id == "request-range"
    assert result.observation.batch_id == "10"
    assert result.observation.related_transaction_ids == ("10", "11", "12")
    transactions = result.observation.normalized_facts["transactions"]
    assert isinstance(transactions, list)
    assert transactions[0]["batch_id"] == "10"
    assert transactions[0]["related_transaction_ids"] == ["10", "11"]
    assert transactions[1]["batch_id"] == "11"
    assert transactions[1]["related_transaction_ids"] == ["11", "12"]
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}/transactions/idrange"
    assert dict(requests[0].url.params) == {"from": "11", "to": "12"}


def test_oanda_reader_normalizes_trade_protection_and_account_frontier() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/trades/7001"):
            return httpx.Response(
                200, json=trade_detail(), headers={"RequestID": "trade"}
            )
        if request.url.path == f"/v3/accounts/{ACCOUNT_ID}":
            return httpx.Response(
                200, json=account_details(), headers={"RequestID": "account"}
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    provider = reader(handler)
    trade = provider.read_trade(context(), "7001")
    account = provider.read_account(context())

    assert trade.attributable is True
    assert trade.protection is not None
    assert trade.protection.stop_loss_status.value == "CONFIRMED"
    assert trade.protection.take_profit_status.value == "CONFIRMED"
    assert account.state is PaperReconciliationReadState.ACCOUNT
    assert account.frontier == "12"
    assert account.unexpected_exposure is False
    assert [request.method for request in requests] == ["GET", "GET"]


def test_oanda_reader_normalizes_closed_trade_aggregate_with_initial_units() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=closed_trade_detail(),
            headers={"RequestID": "closed-trade"},
        )

    result = reader(handler).read_trade(known_fill_context(), "7001")

    assert result.state is PaperReconciliationReadState.CLOSED
    assert result.attributable is True
    assert result.observation.signed_units == Decimal("19230")
    assert result.observation.normalized_schema_version == PAPER_BROKER_FACTS_SCHEMA_V2
    assert result.trade_closure is not None
    assert result.trade_closure.closed_at == datetime(2026, 9, 3, 11, tzinfo=UTC)
    assert result.trade_closure.average_close_price == Decimal("1.11030")
    assert result.trade_closure.realized_pl == Decimal("196.1538")
    assert result.trade_closure.financing == Decimal("-0.42")
    assert result.trade_closure.dividend_adjustment == Decimal("0")
    assert result.trade_closure.closing_transaction_ids == ("43",)
    assert result.trade_closure.exit_cause is PaperTradeExitCause.UNRESOLVED
    assert result.observation.normalized_facts["units"] == "0"
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}/trades/7001"


def test_oanda_reader_preserves_all_closed_transaction_ids_without_fan_out() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=closed_trade_detail(closing_transaction_ids=["43", "44"]),
        )

    result = reader(handler).read_trade(known_fill_context(), "7001")

    assert result.trade_closure is not None
    assert result.trade_closure.exit_cause is PaperTradeExitCause.MULTIPLE
    assert result.trade_closure.closing_transaction_ids == ("43", "44")
    assert result.trade_closure.closing_transaction_id is None
    assert result.trade_closure.exact_close_price is None
    assert result.trade_closure.provider_reason is None
    assert len(requests) == 1


@pytest.mark.parametrize(
    "field",
    [
        "closeTime",
        "averageClosePrice",
        "realizedPL",
        "financing",
        "dividendAdjustment",
        "closingTransactionIDs",
    ],
)
def test_oanda_reader_rejects_malformed_closed_trade_aggregate(field: str) -> None:
    payload = closed_trade_detail()
    payload["trade"][field] = None

    with pytest.raises(OandaReconciliationNormalizationError, match="invalid"):
        reader(static_response(payload)).read_trade(known_fill_context(), "7001")


def test_oanda_closed_trade_does_not_use_current_units_for_identity() -> None:
    payload = closed_trade_detail()
    payload["trade"]["initialUnits"] = None
    payload["trade"]["currentUnits"] = "19230"

    result = reader(static_response(payload)).read_trade(known_fill_context(), "7001")

    assert result.state is PaperReconciliationReadState.CLOSED
    assert result.attributable is False
    assert result.trade_closure is None


@pytest.mark.parametrize(
    ("reason", "cause"),
    [
        ("TAKE_PROFIT_ORDER", PaperTradeExitCause.TAKE_PROFIT),
        ("STOP_LOSS_ORDER", PaperTradeExitCause.STOP_LOSS),
        ("GUARANTEED_STOP_LOSS_ORDER", PaperTradeExitCause.STOP_LOSS),
        ("TRAILING_STOP_LOSS_ORDER", PaperTradeExitCause.STOP_LOSS),
        ("MARKET_ORDER_TRADE_CLOSE", PaperTradeExitCause.MARKET_CLOSE),
        ("MARKET_ORDER_MARGIN_CLOSEOUT", PaperTradeExitCause.MARGIN_CLOSEOUT),
        ("UNSUPPORTED_PROVIDER_REASON", PaperTradeExitCause.OTHER),
    ],
)
def test_oanda_reader_maps_exact_close_reason_and_uses_trade_reduce_price(
    reason: str, cause: PaperTradeExitCause
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=close_transaction(reason=reason),
            headers={"RequestID": "close-transaction"},
        )

    result = reader(handler).read_trade_close_transaction(
        known_fill_context(), "43", "7001"
    )

    assert result.state is PaperReconciliationReadState.CLOSED
    assert result.attributable is True
    assert result.trade_close_transaction is not None
    assert result.trade_close_transaction.exit_cause is cause
    assert result.trade_close_transaction.provider_reason == reason
    assert result.trade_close_transaction.close_price == Decimal("1.11035")
    assert result.observation.read_kind is PaperObservationReadKind.TRANSACTION_DETAIL
    assert result.observation.normalized_facts["close_price"] == "1.11035"
    assert result.observation.normalized_facts["price"] == "9.99999"
    assert result.observation.normalized_schema_version == PAPER_BROKER_FACTS_SCHEMA_V2
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}/transactions/43"


def test_oanda_reader_unwraps_transaction_envelope_for_read_transaction() -> None:
    result = reader(
        static_response(
            documented_transaction_response(order_fill(), last_transaction_id="12")
        )
    ).read_transaction(known_fill_context(), "12")

    assert result.state is PaperReconciliationReadState.FILLED
    assert result.attributable is True
    assert result.fill is not None
    assert result.fill.broker_fill_transaction_id == "12"
    assert result.fill.broker_trade_id == "7001"
    assert result.observation.provider_transaction_id == "12"


def test_oanda_reader_unwraps_transaction_envelope_for_stop_loss_close() -> None:
    response = close_transaction(reason="STOP_LOSS_ORDER")
    transaction = cast(dict[str, Any], response["orderFillTransaction"])

    result = reader(
        static_response(
            documented_transaction_response(transaction, last_transaction_id="43")
        )
    ).read_trade_close_transaction(known_fill_context(), "43", "7001")

    assert result.state is PaperReconciliationReadState.CLOSED
    assert result.attributable is True
    assert result.trade_close_transaction is not None
    assert result.trade_close_transaction.transaction_id == "43"
    assert result.trade_close_transaction.close_price == Decimal("1.11035")
    assert result.trade_close_transaction.provider_reason == "STOP_LOSS_ORDER"
    assert result.trade_close_transaction.exit_cause is PaperTradeExitCause.STOP_LOSS


def test_oanda_reader_keeps_exact_close_with_missing_reason_unresolved() -> None:
    result = reader(
        static_response(close_transaction(reason=None))
    ).read_trade_close_transaction(known_fill_context(), "43", "7001")

    assert result.state is PaperReconciliationReadState.CLOSED
    assert result.attributable is True
    assert result.trade_close_transaction is not None
    assert result.trade_close_transaction.provider_reason is None
    assert result.trade_close_transaction.exit_cause is PaperTradeExitCause.UNRESOLVED


def test_oanda_reader_rejects_oversized_exact_close_transaction_id() -> None:
    requested_id = "9" * 65
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=close_transaction())

    with pytest.raises(OandaReconciliationNormalizationError, match="transaction"):
        reader(handler).read_trade_close_transaction(
            known_fill_context(), requested_id, "7001"
        )

    assert requests == []
    with pytest.raises(OandaReconciliationNormalizationError, match="transaction"):
        reader(
            static_response(close_transaction(transaction_id=requested_id))
        ).read_trade_close_transaction(known_fill_context(), "43", "7001")


def test_oanda_reader_normalizes_trade_reduced_close_and_rejects_unrelated_trade() -> (
    None
):
    result = reader(
        static_response(close_transaction(reduction_key="tradeReduced"))
    ).read_trade_close_transaction(known_fill_context(), "43", "7001")

    assert result.attributable is True
    assert result.trade_close_transaction is not None
    assert result.trade_close_transaction.trade_id == "7001"

    unrelated = reader(
        static_response(close_transaction(trade_id="7002"))
    ).read_trade_close_transaction(known_fill_context(), "43", "7001")

    assert unrelated.state is PaperReconciliationReadState.CONFLICT
    assert unrelated.attributable is False
    assert unrelated.trade_close_transaction is None


def test_oanda_reader_rejects_close_transaction_body_id_mismatch() -> None:
    result = reader(
        static_response(close_transaction(transaction_id="44"))
    ).read_trade_close_transaction(known_fill_context(), "43", "7001")

    assert result.state is PaperReconciliationReadState.CONFLICT
    assert result.attributable is False
    assert result.trade_close_transaction is None


def test_oanda_reader_excludes_historical_position_from_exposure() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=account_details(
                positions=[account_position(minimal=True)], position_count=0
            ),
        )

    result = reader(handler).read_account(context())

    assert result.unexpected_exposure is False
    assert result.observation.normalized_facts["open_positions"] == []
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}"


def test_oanda_reader_retains_genuine_derived_position_as_exposure() -> None:
    result = reader(
        static_response(
            account_details(
                positions=[account_position(long_units="100")], position_count=1
            )
        )
    ).read_account(context())

    assert result.unexpected_exposure is True
    assert result.observation.normalized_facts["open_positions"] == [
        {"instrument": "EUR_USD", "long": "100", "short": "0"}
    ]


def test_oanda_reader_accepts_explicit_matching_trade_account() -> None:
    trade = trade_detail()["trade"]
    trade["accountID"] = ACCOUNT_ID

    result = reader(static_response({"trade": trade})).read_trade(
        known_fill_context(), "7001"
    )

    assert result.state is PaperReconciliationReadState.OPEN
    assert result.attributable is True


def test_oanda_order_not_found_is_normalized_without_mutation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            404,
            json={"errorCode": "ORDER_NOT_FOUND"},
            headers={"RequestID": "not-found-request"},
        )

    result = reader(handler).read_order(context())

    assert result.state is PaperReconciliationReadState.NOT_FOUND
    assert result.observation.normalized_facts == {"found": False}
    assert result.observation.request_id == "not-found-request"
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == (
        f"/v3/accounts/{ACCOUNT_ID}/orders/@{CLIENT_ORDER_ID}"
    )


def test_oanda_order_not_found_without_request_id_does_not_invent_metadata() -> None:
    result = reader(
        static_response({"errorCode": "ORDER_NOT_FOUND"}, status=404)
    ).read_order(context())

    assert result.observation.request_id is None


def test_oanda_reader_rejects_transaction_body_id_mismatch() -> None:
    transaction = order_fill()
    transaction["id"] = "13"

    result = reader(
        static_response({"orderFillTransaction": transaction})
    ).read_transaction(context(), "12")

    assert result.state is PaperReconciliationReadState.CONFLICT
    assert result.attributable is False
    assert result.observation.provider_transaction_id == "13"


def test_oanda_reader_rejects_order_request_field_mismatch() -> None:
    order = order_create()
    order["units"] = "19231"
    order["timeInForce"] = "GTC"
    order["positionFill"] = "DEFAULT"
    order["priceBound"] = "1.10021"

    result = reader(static_response({"order": order})).read_order(context())

    assert result.state is PaperReconciliationReadState.PENDING
    assert result.attributable is False


def test_oanda_reader_rejects_terminal_transaction_order_lineage_mismatch() -> None:
    transaction = order_fill()
    transaction["orderID"] = "99"

    result = reader(
        static_response({"orderFillTransaction": transaction})
    ).read_transaction(context(), "12")

    assert result.state is PaperReconciliationReadState.CONFLICT
    assert result.attributable is False
    assert result.fill is None


def test_oanda_reader_recovers_attributable_market_order_reject_from_range() -> None:
    reject = {
        "id": "12",
        "accountID": ACCOUNT_ID,
        "type": "MARKET_ORDER_REJECT",
        "orderID": "11",
        "clientOrderID": CLIENT_ORDER_ID,
        "instrument": "EUR_USD",
        "units": "19230",
        "timeInForce": "FOK",
        "positionFill": "OPEN_ONLY",
        "priceBound": "1.10020",
    }

    result = reader(
        static_response(
            {"transactions": [order_create(), reject], "lastTransactionID": "12"}
        )
    ).read_transaction_range(context(), "11", "12")

    assert result.attributable is True
    assert result.rejection is not None
    assert result.rejection.broker_order_id == "11"
    assert result.transactions[1].state is PaperReconciliationReadState.REJECTED
    assert result.transactions[1].attributable is True


def test_oanda_reader_attributes_range_cancel_to_discovered_create_order() -> None:
    cancel = {
        "id": "12",
        "accountID": ACCOUNT_ID,
        "type": "ORDER_CANCEL",
        "orderID": "11",
        "reason": "FOK",
    }

    result = reader(
        static_response(
            {"transactions": [order_create(), cancel], "lastTransactionID": "12"}
        )
    ).read_transaction_range(context(), "11", "12")

    assert result.attributable is True
    assert result.transactions[1].state is PaperReconciliationReadState.CANCELLED
    assert result.transactions[1].attributable is True


def known_fill_context() -> PaperReconciliationContext:
    return replace(
        context(),
        provider_order_id="11",
        provider_trade_id="7001",
        fill_signed_units=Decimal("19230"),
        fill_price=Decimal("1.10010"),
    )


def test_oanda_reader_rejects_known_trade_units_and_price_mismatch() -> None:
    trade = trade_detail()["trade"]
    trade["currentUnits"] = "1"
    trade["price"] = "9.0"

    result = reader(static_response({"trade": trade})).read_trade(
        known_fill_context(), "7001"
    )

    assert result.state is PaperReconciliationReadState.OPEN
    assert result.attributable is False


def test_oanda_reader_rejects_returned_trade_id_mismatch() -> None:
    trade = trade_detail()["trade"]
    trade["id"] = "7002"

    result = reader(static_response({"trade": trade})).read_trade(
        known_fill_context(), "7001"
    )

    assert result.attributable is False


def test_oanda_reader_rejects_explicit_mismatching_trade_account() -> None:
    trade = trade_detail()["trade"]
    trade["accountID"] = "001-011-5838423-002"

    result = reader(static_response({"trade": trade})).read_trade(
        known_fill_context(), "7001"
    )

    assert result.state is PaperReconciliationReadState.OPEN
    assert result.attributable is False


def test_oanda_reader_rejects_explicit_null_trade_account() -> None:
    trade = trade_detail()["trade"]
    trade["accountID"] = None

    result = reader(static_response({"trade": trade})).read_trade(
        known_fill_context(), "7001"
    )

    assert result.state is PaperReconciliationReadState.OPEN
    assert result.attributable is False
