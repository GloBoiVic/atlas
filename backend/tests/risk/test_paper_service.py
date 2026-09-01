from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.domain.broker import (
    AccountIdentity,
    AccountMode,
    AccountSnapshot,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import Instrument, Provider, VenueInstrument
from backend.domain.strategy import Action, Direction, TargetProposal
from backend.domain.trading import FinancialPositionState
from backend.risk import PaperRiskConfig, PaperRiskService, RiskRejection, TradeIntent

NOW = datetime(2026, 1, 5, 10, 15, tzinfo=UTC)


def intent(direction: Direction = Direction.LONG) -> TradeIntent:
    return TradeIntent(
        Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT,
        direction,
        Decimal("1.0950") if direction is Direction.LONG else Decimal("1.1050"),
        TargetProposal(multiple=Decimal("1.7")),
    )


def account(*, margin_available: str = "9000") -> AccountSnapshot:
    return AccountSnapshot(
        identity=AccountIdentity("practice-1", mode=AccountMode.PAPER),
        balance=Decimal("10000"),
        nav=Decimal("10000"),
        unrealized_pl=Decimal("0"),
        equity=Decimal("10000"),
        margin_available=Decimal(margin_available),
        margin_used=Decimal("1000"),
        observed_at=NOW,
        source="recorded",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )


def instrument() -> VenueInstrumentFacts:
    return VenueInstrumentFacts(
        venue_instrument=VenueInstrument(
            Instrument.EUR_USD, Provider.OANDA, "EUR_USD"
        ),
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_order_units=Decimal("1"),
        maximum_order_units=Decimal("1000000"),
        maximum_position_units=None,
        margin_rate=Decimal("0.02"),
        capabilities=frozenset({"LONG", "SHORT", "MARKET", "STOP_LOSS", "TAKE_PROFIT"}),
    )


def quote(*, observed_at: datetime = NOW) -> ExecutableQuote:
    return ExecutableQuote(
        Instrument.EUR_USD,
        Decimal("1.1000"),
        Decimal("1.1002"),
        observed_at,
        "recorded",
        True,
    )


def kwargs() -> dict[str, object]:
    return {
        "deployment_state": "RUNNING",
        "position": FinancialPositionState.FLAT,
        "account": account(),
        "instrument": instrument(),
        "config": PaperRiskConfig(Decimal("0.01")),
        "evaluated_at": NOW,
    }


def test_paper_risk_runs_two_stages_and_keeps_target_unresolved() -> None:
    pre_flight, pre_submission = PaperRiskService().evaluate(
        intent(), quote=quote(), **kwargs()
    )
    assert pre_flight.approved
    assert pre_submission is not None and pre_submission.approved
    assert pre_submission.target_price is None
    assert pre_submission.target_multiple == Decimal("1.7")
    assert pre_submission.quantity == Decimal("19230")
    assert pre_submission.price_bound == Decimal("1.10020")
    assert pre_submission.actual_risk is not None
    assert pre_submission.actual_risk <= pre_submission.risk_budget


def test_paper_risk_rejects_stale_quote_and_unknown_reconciliation() -> None:
    values = kwargs()
    stale = PaperRiskService().evaluate_pre_submission(
        intent(), quote=quote(observed_at=NOW - timedelta(minutes=2)), **values
    )
    assert stale.rejection is RiskRejection.STALE_QUOTE
    blocked = PaperRiskService().evaluate_pre_flight(
        intent(), reconciliation_required=True, **values
    )
    assert blocked.rejection is RiskRejection.RECONCILIATION_REQUIRED


def test_paper_risk_rejects_unknown_broker_state_collections() -> None:
    values = kwargs()
    decision = PaperRiskService().evaluate_pre_flight(
        intent(), account=AccountSnapshot(
            identity=AccountIdentity("practice-1", mode=AccountMode.PAPER),
            balance=Decimal("10000"),
            nav=Decimal("10000"),
            unrealized_pl=Decimal("0"),
            equity=Decimal("10000"),
            margin_available=Decimal("9000"),
            margin_used=Decimal("1000"),
            observed_at=NOW,
            source="recorded",
            orders_known=True,
            trades_known=False,
            positions_known=True,
        ),
        **{key: value for key, value in values.items() if key != "account"},
    )
    assert decision.rejection is RiskRejection.ACCOUNT_STATE_UNKNOWN


def test_paper_risk_caps_quantity_by_margin_without_exceeding_budget() -> None:
    values = kwargs()
    values["account"] = account(margin_available="10")
    decision = PaperRiskService().evaluate_pre_submission(
        intent(), quote=quote(), **values
    )
    assert decision.approved
    assert decision.quantity == Decimal("454")
    assert decision.actual_risk == Decimal("2.3608")


def test_paper_risk_rejects_non_tradeable_quote() -> None:
    values = kwargs()
    values["account"] = account()
    bad_quote = ExecutableQuote(
        Instrument.EUR_USD, Decimal("1.1000"), Decimal("1.1002"), NOW, "recorded", False
    )
    decision = PaperRiskService().evaluate_pre_submission(
        intent(), quote=bad_quote, **values
    )
    assert decision.rejection is RiskRejection.STALE_QUOTE
