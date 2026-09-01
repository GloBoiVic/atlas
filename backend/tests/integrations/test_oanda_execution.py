from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from backend.execution import Fill, Order
from backend.integrations.oanda import (
    OandaExecutionAdapter,
    OandaExecutionError,
    OandaOrderStatus,
    OandaPracticeExecutionClient,
    fill_model_from_canonical,
    normalize_create_response,
    normalize_protection_state,
    target_from_fill,
    validate_protection_state,
)
from backend.integrations.oanda.execution import (
    immutable_fill_facts_agree,
)

NOW = datetime(2026, 1, 5, 10, 15, tzinfo=UTC)


def order(direction: str = "LONG") -> Order:
    return Order(
        uuid4(), "MARKET", "ENTRY", direction, Decimal("1000"),
        client_correlation_id="atlas-paper-order",
        time_in_force="FOK",
        price_bound=Decimal("1.10020") if direction == "LONG" else Decimal("1.10000"),
        stop_loss_price=Decimal("1.0950") if direction == "LONG" else Decimal("1.1050"),
    )


def response(*, direction: str = "LONG", units: str = "1000") -> dict[str, object]:
    if direction == "SHORT" and units == "1000":
        units = "-1000"
    return {
        "orderCreateTransaction": {"id": "20", "requestID": "req-1"},
        "orderFillTransaction": {
            "id": "21",
            "orderID": "20",
            "units": units,
            "price": "1.1002" if direction == "LONG" else "1.1000",
            "time": "2026-01-05T10:15:01Z",
            "commission": "0.25",
            "tradeOpened": {"tradeID": "30", "units": units},
        },
        "relatedTransactionIDs": ["20", "21", "22"],
        "lastTransactionID": "22",
    }


def test_market_fok_payload_has_stable_correlation_and_stop_on_fill() -> None:
    payload = OandaExecutionAdapter().build_entry_payload(order())
    assert payload["order"]["type"] == "MARKET"  # type: ignore[index]
    assert payload["order"]["timeInForce"] == "FOK"  # type: ignore[index]
    assert payload["order"]["units"] == "1000"  # type: ignore[index]
    assert payload["order"]["clientExtensions"] == {"id": "atlas-paper-order"}  # type: ignore[index]
    assert payload["order"]["stopLossOnFill"]["price"] == "1.0950"  # type: ignore[index]


def test_ioc_is_rejected_before_the_mocked_provider_is_reached() -> None:
    ioc = Order(
        uuid4(), "MARKET", "ENTRY", "LONG", Decimal("1000"),
        client_correlation_id="atlas-paper-order", time_in_force="IOC",
        price_bound=Decimal("1.10020"), stop_loss_price=Decimal("1.0950"),
    )
    with pytest.raises(OandaExecutionError, match="FOK"):
        OandaExecutionAdapter().build_entry_payload(ioc)


def test_submission_timeout_is_unknown_and_never_retried() -> None:
    class TimeoutTransport:
        calls = 0

        def submit_market_fok(
            self, account_id: str, payload: dict[str, object]
        ) -> dict[str, object]:
            self.calls += 1
            raise TimeoutError

        def attach_take_profit(
            self, account_id: str, trade_id: str, payload: dict[str, object]
        ) -> dict[str, object]:
            raise AssertionError("target attach must not run")

        def trade(self, account_id: str, trade_id: str) -> dict[str, object]:
            raise AssertionError("confirmation must not run")

    transport = TimeoutTransport()
    persisted: list[str] = []
    result = OandaExecutionAdapter().submit_entry(
        transport,
        account_id="practice-1",
        order=order(),
        persist_pending=lambda: persisted.append("PENDING_SUBMISSION"),
    )
    assert persisted == ["PENDING_SUBMISSION"]
    assert transport.calls == 1
    assert result.status is OandaOrderStatus.UNKNOWN
    assert result.fill is None


def test_recorded_compound_response_accepts_only_a_full_fill() -> None:
    result = normalize_create_response(response(), order())
    assert result.status is OandaOrderStatus.FULL_FILLED
    assert result.fill is not None
    assert result.fill.quantity == Decimal("1000")
    assert result.fill.external_trade_id == "30"
    partial = normalize_create_response(response(units="400"), order())
    assert partial.status is OandaOrderStatus.PARTIAL
    assert partial.fill is None


def test_conflicting_provider_order_id_cannot_become_a_full_fill() -> None:
    payload = response()
    payload["orderFillTransaction"] = {
        "id": "21",
        "orderID": "21",
        "units": "1000",
        "price": "1.1002",
        "time": "2026-01-05T10:15:01Z",
        "commission": "0.25",
        "tradeOpened": {"tradeID": "30", "units": "1000"},
    }

    result = normalize_create_response(payload, order())

    assert result.status is OandaOrderStatus.UNKNOWN
    assert result.fill is None


def test_reject_and_malformed_response_are_not_falsely_filled() -> None:
    rejected = normalize_create_response(
        {
            "orderCreateTransaction": {"id": "20"},
            "orderRejectTransaction": {"id": "21"},
        },
        order(),
    )
    assert rejected.status is OandaOrderStatus.REJECTED
    malformed = normalize_create_response(
        {"orderCreateTransaction": {"id": "20"}}, order()
    )
    assert malformed.status is OandaOrderStatus.UNKNOWN


def test_target_uses_authoritative_fill_and_protection_is_verified() -> None:
    assert target_from_fill(
        Decimal("1.1002"), Decimal("1.0950"), "LONG"
    ) == Decimal("1.10904")
    state = normalize_protection_state({
        "trade": {
            "id": "30",
            "state": "OPEN",
            "currentUnits": "1000",
            "initialUnits": "1000",
            "stopLossOrder": {"id": "31", "price": "1.0950"},
            "takeProfitOrder": {"id": "32", "price": "1.10904"},
        }
    }, observed_at=NOW, fresh=True)
    validate_protection_state(
        state, trade_id="30", direction="LONG", quantity=Decimal("1000"),
        stop_price=Decimal("1.0950"), target_price=Decimal("1.10904"),
        now=NOW,
    )


def test_protection_with_partial_current_trade_units_is_rejected() -> None:
    state = normalize_protection_state(
        {
            "trade": {
                "id": "30",
                "state": "OPEN",
                "currentUnits": "5",
                "initialUnits": "5",
                "stopLossOrder": {"id": "31", "price": "1.0950"},
                "takeProfitOrder": {"id": "32", "price": "1.10904"},
            }
        },
        observed_at=NOW,
        fresh=True,
    )

    with pytest.raises(OandaExecutionError, match="partial"):
        validate_protection_state(
            state,
            trade_id="30",
            direction="LONG",
            quantity=Decimal("1000"),
            stop_price=Decimal("1.0950"),
            target_price=Decimal("1.10904"),
            now=NOW,
        )


def test_protection_requires_distinct_provider_order_identities() -> None:
    state = normalize_protection_state(
        {
            "trade": {
                "id": "30",
                "state": "OPEN",
                "currentUnits": "1000",
                "stopLossOrder": {"id": "31", "price": "1.0950"},
                "takeProfitOrder": {"id": "31", "price": "1.10904"},
            }
        },
        observed_at=NOW,
        fresh=True,
    )

    with pytest.raises(OandaExecutionError, match="missing, wrong, or orphaned"):
        validate_protection_state(
            state,
            trade_id="30",
            direction="LONG",
            quantity=Decimal("1000"),
            stop_price=Decimal("1.0950"),
            target_price=Decimal("1.10904"),
            now=NOW,
        )


@pytest.mark.parametrize(
    ("state_overrides", "expected"),
    [
        ({"trade_id": "foreign"}, "missing, wrong, or orphaned"),
        ({"stop_price": Decimal("1.0949")}, "missing, wrong, or orphaned"),
        ({"observed_at": NOW - timedelta(minutes=3)}, "stale"),
    ],
)
def test_protection_rejects_foreign_wrong_or_stale_broker_truth(
    state_overrides: dict[str, object], expected: str
) -> None:
    state = normalize_protection_state(
        {
            "trade": {
                "id": "30",
                "state": "OPEN",
                "currentUnits": "1000",
                "stopLossOrder": {"id": "31", "price": "1.0950"},
                "takeProfitOrder": {"id": "32", "price": "1.10904"},
            }
        },
        observed_at=state_overrides.get("observed_at", NOW),  # type: ignore[arg-type]
        fresh=True,
    )
    if "trade_id" in state_overrides or "stop_price" in state_overrides:
        state = state.__class__(
            state_overrides.get("trade_id", state.trade_id),
            state.stop_order_id,
            state.target_order_id,
            state_overrides.get("stop_price", state.stop_price),
            state.target_price,
            state.stop_units,
            state.target_units,
            state.current_units,
            state.initial_units,
            state.trade_state,
            state.observed_at,
            state.fresh,
        )

    with pytest.raises(OandaExecutionError, match=expected):
        validate_protection_state(
            state,
            trade_id="30",
            direction="LONG",
            quantity=Decimal("1000"),
            stop_price=Decimal("1.0950"),
            target_price=Decimal("1.10904"),
            now=NOW,
        )


def test_fill_model_preserves_source_bar_and_replay_facts() -> None:
    source_bar_id = uuid4()
    fill = Fill(
        uuid4(),
        1,
        Decimal("1000"),
        Decimal("1.1002"),
        NOW,
        source_market_bar_id=source_bar_id,
        external_execution_id="21",
        external_transaction_id="22",
        external_trade_id="30",
        related_transaction_ids=("20", "21", "22"),
    )

    model = fill_model_from_canonical(fill)

    assert model.source_market_bar_id == source_bar_id
    assert immutable_fill_facts_agree(model, fill)


def test_non_capital_http_check_is_get_only() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"trade": {}})

    client = OandaPracticeExecutionClient(
        SecretStr("recorded-token"), transport=httpx.MockTransport(handler)
    )
    client.trade("practice-1", "30")
    assert methods == ["GET"]
