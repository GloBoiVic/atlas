from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from backend.domain import (
    Action,
    Direction,
    EntryPolicy,
    Provider,
    Rationale,
    StopProposal,
    StrategyDecision,
    TargetProposal,
)
from backend.execution.contract import Fill, Order
from backend.integrations.oanda import (
    OandaPracticeAccountIdentity,
    OandaPracticeAccountProperties,
    OandaPracticeAccountSummarySnapshot,
    OandaPracticeEntryMutation,
    OandaPracticeEurUsdPricingObservation,
    OandaPracticeExecutionAccountSnapshot,
    OandaPracticeExecutionInstrument,
    OandaPracticeOpenPositionInventory,
    OandaPracticeOpenTradeInventory,
    OandaPracticePendingOrderInventory,
    OandaPracticePriceBucket,
    OandaPracticeProtectionCompletion,
)
from backend.paper import (
    PaperExecutionOutcome,
    PaperExecutionRefusal,
    PaperExecutionRefusalCode,
    evaluate_paper_risk,
    execute_paper_execution,
)
from backend.risk import RiskConfig

ACCOUNT_ID = "001-011-5838423-001"
ATTEMPT_ID = UUID("12345678-1234-5678-1234-567812345678")
DECISION_TIME = datetime(2026, 9, 2, 12, tzinfo=UTC)
PRICING_TIME = datetime(2026, 9, 2, 12, 0, 1, tzinfo=UTC)
IDENTITY = OandaPracticeAccountIdentity(
    provider=Provider.OANDA,
    environment="PRACTICE",
    provider_account_id=ACCOUNT_ID,
    alias="Composition test",
    base_currency="USD",
)
INSTRUMENT = OandaPracticeExecutionInstrument(
    provider_instrument="EUR_USD",
    display_precision=5,
    trade_units_precision=0,
    minimum_trade_size=Decimal("1"),
    maximum_order_units=Decimal("1000000"),
    last_transaction_id="42",
)


class ValueReader:
    def __init__(self, value: object, events: list[str], name: str) -> None:
        self.value = value
        self.events = events
        self.name = name

    def read(self) -> object:
        self.events.append(self.name)
        return self.value


class EntryRequester:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.calls = 0
        self.payloads: list[Mapping[str, Any]] = []

    def post_entry_order(
        self, account_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.calls += 1
        self.payloads.append(payload)
        return self.response


class ProtectionRequester:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.calls = 0
        self.payloads: list[Mapping[str, Any]] = []

    def put_trade_orders(
        self, account_id: str, trade_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.calls += 1
        self.payloads.append(payload)
        return self.response


class TradeReader:
    def __init__(self, trades: list[Mapping[str, Any] | None]) -> None:
        self.trades = trades
        self.calls = 0

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None:
        self.calls += 1
        return self.trades.pop(0) if self.trades else None


def decision(direction: Direction = Direction.LONG) -> StrategyDecision:
    stop = Decimal("1.0950") if direction is Direction.LONG else Decimal("1.1050")
    return StrategyDecision(
        action=Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT,
        rationale=Rationale("COMPOSITION_TEST"),
        direction=direction,
        decision_time=DECISION_TIME,
        stop=StopProposal(stop, direction),
        target=TargetProposal(multiple=Decimal("1.7")),
        entry_policy=EntryPolicy.IMMEDIATE,
    )


def account_snapshot() -> OandaPracticeExecutionAccountSnapshot:
    summary = OandaPracticeAccountSummarySnapshot(
        identity=IDENTITY,
        balance=Decimal("10000"),
        nav=Decimal("10000"),
        unrealized_pl=Decimal("0"),
        margin_used=Decimal("0"),
        margin_available=Decimal("10000"),
        open_trade_count=0,
        open_position_count=0,
        pending_order_count=0,
        last_transaction_id="42",
    )
    return OandaPracticeExecutionAccountSnapshot(
        summary=summary,
        trades=OandaPracticeOpenTradeInventory(IDENTITY, (), "42"),
        positions=OandaPracticeOpenPositionInventory(IDENTITY, (), "42"),
        pending_orders=OandaPracticePendingOrderInventory(IDENTITY, (), "42"),
        guaranteed_stop_loss_order_mode="DISABLED",
        hedging_enabled=True,
        last_transaction_id="42",
    )


def pricing() -> OandaPracticeEurUsdPricingObservation:
    return OandaPracticeEurUsdPricingObservation(
        identity=IDENTITY,
        provider_instrument="EUR_USD",
        price_time=PRICING_TIME,
        tradeable=True,
        bids=(OandaPracticePriceBucket(Decimal("1.10000"), Decimal("30000")),),
        asks=(OandaPracticePriceBucket(Decimal("1.10020"), Decimal("30000")),),
    )


def _create() -> dict[str, Any]:
    correlation = _correlation()
    return {
        "id": "1001",
        "accountID": ACCOUNT_ID,
        "type": "MARKET_ORDER",
        "instrument": "EUR_USD",
        "units": "19230",
        "timeInForce": "FOK",
        "priceBound": "1.10020",
        "positionFill": "OPEN_ONLY",
        "clientOrderID": correlation[0],
        "clientExtensions": {"id": correlation[0], "tag": "atlas-paper-04"},
        "tradeClientExtensions": {"id": correlation[1]},
    }


def _fill(*, price: str = "1.10010") -> dict[str, Any]:
    correlation = _correlation()
    return {
        "id": "1002",
        "accountID": ACCOUNT_ID,
        "type": "ORDER_FILL",
        "orderID": "1001",
        "clientOrderID": correlation[0],
        "instrument": "EUR_USD",
        "units": "19230",
        "time": "2026-09-02T12:00:02.000000000Z",
        "tradeOpened": {"tradeID": "7001", "units": "19230", "price": price},
    }


def _trade(
    *,
    stop: Mapping[str, Any] | None = None,
    target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    trade: dict[str, Any] = {
        "id": "7001",
        "accountID": ACCOUNT_ID,
        "instrument": "EUR_USD",
        "state": "OPEN",
        "initialUnits": "19230",
        "currentUnits": "19230",
        "price": "1.10010",
        "clientExtensions": {"id": _correlation()[1]},
    }
    if stop is not None:
        trade["stopLossOrder"] = dict(stop)
    if target is not None:
        trade["takeProfitOrder"] = dict(target)
    return trade


def _stop() -> dict[str, Any]:
    return {
        "id": "8001",
        "type": "STOP_LOSS",
        "state": "PENDING",
        "tradeID": "7001",
        "price": "1.09500",
        "timeInForce": "GTC",
        "clientExtensions": {"id": _correlation()[2]},
    }


def _target() -> dict[str, Any]:
    return {
        "id": "9001",
        "type": "TAKE_PROFIT",
        "state": "PENDING",
        "tradeID": "7001",
        "clientTradeID": _correlation()[1],
        "price": "1.10877",
        "timeInForce": "GTC",
        "clientExtensions": {"id": _correlation()[3]},
    }


def _correlation() -> tuple[str, str, str, str]:
    attempt = ATTEMPT_ID.hex
    return (
        f"atlas-p04-o-{attempt}",
        f"atlas-p04-t-{attempt}",
        f"atlas-p04-sl-{attempt}",
        f"atlas-p04-tp-{attempt}",
    )


def _entry_payload(
    *,
    fill: bool = False,
    fill_price: str = "1.10010",
    cancel: bool = False,
    reject: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "orderCreateTransaction": _create(),
        "lastTransactionID": "1002",
        "relatedTransactionIDs": ["1001", "1002"],
    }
    if fill:
        payload["orderFillTransaction"] = _fill(price=fill_price)
    if cancel:
        payload["orderCancelTransaction"] = {
            "id": "1003",
            "accountID": ACCOUNT_ID,
            "type": "ORDER_CANCEL",
            "orderID": "1001",
            "reason": "FOK",
        }
    if reject:
        payload["orderRejectTransaction"] = {
            "id": "1004",
            "accountID": ACCOUNT_ID,
            "type": "ORDER_REJECT",
            "orderID": "1001",
            "clientOrderID": _correlation()[0],
            "instrument": "EUR_USD",
            "rejectReason": "INSUFFICIENT_MARGIN",
        }
    return payload


def _target_payload() -> dict[str, Any]:
    return {
        "takeProfitOrderTransaction": {
            "id": "9002",
            "accountID": ACCOUNT_ID,
            "type": "TAKE_PROFIT_ORDER",
            "tradeID": "7001",
            "clientTradeID": _correlation()[1],
            "price": "1.10877",
            "timeInForce": "GTC",
            "clientExtensions": {"id": _correlation()[3]},
        },
        "lastTransactionID": "9002",
        "relatedTransactionIDs": ["9002"],
    }


def _operation(
    entry_response: Mapping[str, Any],
    *,
    trade_values: list[Mapping[str, Any] | None] | None = None,
    target_response: Mapping[str, Any] | None = None,
    events: list[str] | None = None,
) -> tuple[Any, EntryRequester, ProtectionRequester, TradeReader, list[str]]:
    ordered_events = events if events is not None else []
    entry_requester = EntryRequester(entry_response)
    protection_requester = ProtectionRequester(target_response or {})
    trade_reader = TradeReader(trade_values or [])
    operation = execute_paper_execution(
        decision(),
        config=RiskConfig(Decimal("0.01")),
        account_properties_reader=ValueReader(
            OandaPracticeAccountProperties(ACCOUNT_ID, None),
            ordered_events,
            "properties",
        ),
        execution_account_reader=ValueReader(
            account_snapshot(), ordered_events, "account"
        ),
        execution_instrument_reader=ValueReader(
            INSTRUMENT, ordered_events, "instrument"
        ),
        pricing_reader=ValueReader(pricing(), ordered_events, "pricing"),
        entry_mutation=OandaPracticeEntryMutation(entry_requester),
        protection_completion=OandaPracticeProtectionCompletion(
            protection_requester, trade_reader
        ),
        attempt_id=ATTEMPT_ID,
    )
    return (
        operation,
        entry_requester,
        protection_requester,
        trade_reader,
        ordered_events,
    )


def test_public_composition_returns_filled_protected_from_fresh_current_facts() -> None:
    result, entry, protection, trade_reader, events = _operation(
        _entry_payload(fill=True),
        trade_values=[_trade(stop=_stop()), _trade(stop=_stop(), target=_target())],
        target_response=_target_payload(),
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert result.fill is not None
    assert result.fill.price == Decimal("1.10010")
    assert result.protection.actual_target_price == Decimal("1.10877")
    assert entry.calls == 1
    assert protection.calls == 1
    assert trade_reader.calls == 2
    assert events == ["properties", "account", "instrument", "pricing"]


def test_public_composition_distinguishes_filled_protection_incomplete() -> None:
    result, entry, protection, _, _ = _operation(
        _entry_payload(fill=True), trade_values=[_trade()]
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.fill is not None
    assert result.protection.stop_loss_status.value == "UNKNOWN"
    assert entry.calls == 1
    assert protection.calls == 0


@pytest.mark.parametrize(
    ("fill_price", "diagnostic", "expected_risk"),
    [
        ("1.10021", "ENTRY_FILL_BOUND_VIOLATION", Decimal("100.18830")),
        ("1.09490", "ENTRY_FILL_STOP_GEOMETRY_VIOLATION", Decimal("1.92300")),
    ],
)
def test_public_composition_preserves_confirmed_fill_on_entry_invariant_failure(
    fill_price: str, diagnostic: str, expected_risk: Decimal
) -> None:
    result, entry, protection, _, _ = _operation(
        _entry_payload(fill=True, fill_price=fill_price)
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.fill is not None
    assert result.fill.broker_order_id == "1001"
    assert result.fill.broker_fill_transaction_id == "1002"
    assert result.fill.broker_trade_id == "7001"
    assert result.fill.price == Decimal(fill_price)
    assert result.fill.actual_initial_risk == expected_risk
    assert result.transaction_provenance.provider_transaction_ids == (
        "1001",
        "1002",
    )
    assert result.transaction_provenance.last_transaction_id == "1002"
    assert diagnostic in result.diagnostic_codes
    assert result.uncertainty is not None
    assert result.uncertainty.detail_code == diagnostic
    assert entry.calls == 1
    assert protection.calls == 0


def test_public_composition_preserves_confirmed_fill_on_actual_risk_budget_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = evaluate_paper_risk

    def below_actual_risk(*args: Any, **kwargs: Any) -> Any:
        evaluation = original(*args, **kwargs)
        assert evaluation.pre_submission is not None
        return replace(
            evaluation,
            pre_submission=replace(
                evaluation.pre_submission, risk_budget=Decimal("90")
            ),
        )

    monkeypatch.setattr(
        "backend.paper.execution_application.evaluate_paper_risk", below_actual_risk
    )
    result, entry, protection, _, _ = _operation(
        _entry_payload(fill=True, fill_price="1.10010")
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.fill is not None
    assert result.fill.price == Decimal("1.10010")
    assert result.fill.actual_initial_risk == Decimal("98.07300")
    assert result.transaction_provenance.provider_transaction_ids == (
        "1001",
        "1002",
    )
    assert result.transaction_provenance.last_transaction_id == "1002"
    assert "ENTRY_FILL_RISK_BUDGET_EXCEEDED" in result.diagnostic_codes
    assert result.uncertainty is not None
    assert result.uncertainty.detail_code == "ENTRY_FILL_RISK_BUDGET_EXCEEDED"
    assert entry.calls == 1
    assert protection.calls == 0


@pytest.mark.parametrize(
    ("payload", "outcome"),
    [
        (_entry_payload(reject=True), PaperExecutionOutcome.REJECTED),
        (_entry_payload(cancel=True), PaperExecutionOutcome.CANCELLED),
    ],
)
def test_public_composition_preserves_definite_entry_terminals(
    payload: Mapping[str, Any], outcome: PaperExecutionOutcome
) -> None:
    result, entry, protection, _, _ = _operation(payload)

    assert result.outcome is outcome
    assert result.fill is None
    assert entry.calls == 1
    assert protection.calls == 0


def test_public_composition_returns_unknown_without_resubmission() -> None:
    result, entry, protection, _, _ = _operation(_entry_payload())

    assert result.outcome is PaperExecutionOutcome.UNKNOWN
    assert result.fill is None
    assert result.uncertainty is not None
    assert entry.calls == 1
    assert protection.calls == 0


def test_public_composition_evaluates_paper_risk_once_and_cannot_accept_stale_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = evaluate_paper_risk

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        "backend.paper.execution_application.evaluate_paper_risk", counted
    )
    stale = original(
        decision(),
        summary=account_snapshot().summary,
        trades=account_snapshot().trades,
        positions=account_snapshot().positions,
        pricing=pricing(),
        config=RiskConfig(Decimal("0.01")),
    )
    result, entry, _, _, _ = _operation(_entry_payload(reject=True))
    assert result.outcome is PaperExecutionOutcome.REJECTED
    assert calls == 1
    assert entry.calls == 1

    refusal = execute_paper_execution(
        stale,  # type: ignore[arg-type]
        config=RiskConfig(Decimal("0.01")),
        account_properties_reader=ValueReader(
            OandaPracticeAccountProperties(ACCOUNT_ID, None), [], "properties"
        ),
        execution_account_reader=ValueReader(account_snapshot(), [], "account"),
        execution_instrument_reader=ValueReader(INSTRUMENT, [], "instrument"),
        pricing_reader=ValueReader(pricing(), [], "pricing"),
        entry_mutation=OandaPracticeEntryMutation(
            EntryRequester(_entry_payload(fill=True))
        ),
        protection_completion=OandaPracticeProtectionCompletion(
            ProtectionRequester(_target_payload()), TradeReader([])
        ),
        attempt_id=ATTEMPT_ID,
    )
    assert isinstance(refusal, PaperExecutionRefusal)
    assert refusal.code is PaperExecutionRefusalCode.UNSUPPORTED_INPUT
    assert calls == 1


def test_public_composition_keeps_historical_and_risk_contracts_isolated() -> None:
    assert Order is not Fill
    assert PaperExecutionOutcome is not None
    read_only = evaluate_paper_risk(
        decision(),
        summary=account_snapshot().summary,
        trades=account_snapshot().trades,
        positions=account_snapshot().positions,
        pricing=pricing(),
        config=RiskConfig(Decimal("0.01")),
    )
    assert read_only.pre_submission is not None
    assert read_only.pre_submission.entry_price == Decimal("1.10020")
