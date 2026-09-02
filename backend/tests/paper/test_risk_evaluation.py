from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.domain import (
    Action,
    Direction,
    EntryPolicy,
    PriceComponent,
    Rationale,
    StopProposal,
    StrategyDecision,
    TargetProposal,
)
from backend.domain.market_data import Provider
from backend.integrations.oanda import (
    OandaPracticeAccountIdentity,
    OandaPracticeAccountSummarySnapshot,
    OandaPracticeEurUsdPricingObservation,
    OandaPracticeOpenPositionInventory,
    OandaPracticeOpenTradeInventory,
    OandaPracticePriceBucket,
)
from backend.paper import PaperRiskOutcome, evaluate_paper_risk
from backend.risk import RiskConfig, RiskDecision, RiskPhase, RiskRejection, RiskService

ACCOUNT_ID = "001-011-5838423-001"
DECISION_TIME = datetime(2026, 8, 31, 12, tzinfo=UTC)


def identity(
    *, account_id: str = ACCOUNT_ID, alias: str | None = "Practice"
) -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=account_id,
        alias=alias,
        base_currency="USD",
    )


def summary(
    *,
    identity_value: OandaPracticeAccountIdentity | None = None,
    open_trade_count: int = 0,
    open_position_count: int = 0,
    pending_order_count: int = 0,
) -> OandaPracticeAccountSummarySnapshot:
    return OandaPracticeAccountSummarySnapshot(
        identity=identity_value or identity(),
        balance=Decimal("10000"),
        nav=Decimal("10000"),
        unrealized_pl=Decimal("0"),
        margin_used=Decimal("0"),
        margin_available=Decimal("10000"),
        open_trade_count=open_trade_count,
        open_position_count=open_position_count,
        pending_order_count=pending_order_count,
        last_transaction_id="10",
    )


def observations(
    *,
    summary_value: OandaPracticeAccountSummarySnapshot | None = None,
    pricing_value: OandaPracticeEurUsdPricingObservation | None = None,
) -> tuple[
    OandaPracticeAccountSummarySnapshot,
    OandaPracticeOpenTradeInventory,
    OandaPracticeOpenPositionInventory,
    OandaPracticeEurUsdPricingObservation,
]:
    account = summary_value or summary()
    account_identity = account.identity
    return (
        account,
        OandaPracticeOpenTradeInventory(account_identity, (), "11"),
        OandaPracticeOpenPositionInventory(account_identity, (), "12"),
        pricing_value
        or OandaPracticeEurUsdPricingObservation(
            identity=account_identity,
            provider_instrument="EUR_USD",
            price_time=DECISION_TIME,
            tradeable=True,
            bids=(OandaPracticePriceBucket(Decimal("1.1000"), Decimal("20000")),),
            asks=(OandaPracticePriceBucket(Decimal("1.1000"), Decimal("20000")),),
        ),
    )


def opening(
    direction: Direction = Direction.LONG,
    *,
    entry_policy: EntryPolicy = EntryPolicy.IMMEDIATE,
    decision_time: datetime = DECISION_TIME,
    stop: Decimal | None = None,
) -> StrategyDecision:
    expected_stop = stop or (
        Decimal("1.0950") if direction is Direction.LONG else Decimal("1.1050")
    )
    action = Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT
    return StrategyDecision(
        action=action,
        rationale=Rationale("TEST"),
        direction=direction,
        decision_time=decision_time,
        stop=StopProposal(expected_stop, direction),
        target=TargetProposal(multiple=Decimal("1.7")),
        entry_policy=entry_policy,
        trigger_price=Decimal("1.1000")
        if entry_policy is EntryPolicy.PRICE_TRIGGERED
        else None,
        trigger_price_basis=(
            None
            if entry_policy is EntryPolicy.IMMEDIATE
            else (
                PriceComponent.ASK
                if direction is Direction.LONG
                else PriceComponent.BID
            )
        ),
        expiry_bars=2 if entry_policy is EntryPolicy.PRICE_TRIGGERED else None,
    )


def pricing(
    direction: Direction,
    buckets: tuple[tuple[str, str], ...],
    *,
    price_time: datetime = DECISION_TIME,
    account_identity: OandaPracticeAccountIdentity | None = None,
) -> OandaPracticeEurUsdPricingObservation:
    account_identity = account_identity or identity()
    values = tuple(
        OandaPracticePriceBucket(Decimal(price), Decimal(quantity))
        for price, quantity in buckets
    )
    return OandaPracticeEurUsdPricingObservation(
        identity=account_identity,
        provider_instrument="EUR_USD",
        price_time=price_time,
        tradeable=True,
        bids=values if direction is Direction.SHORT else (),
        asks=values if direction is Direction.LONG else (),
    )


def evaluate(
    decision: StrategyDecision,
    *,
    summary_value: OandaPracticeAccountSummarySnapshot | None = None,
    pricing_value: OandaPracticeEurUsdPricingObservation | None = None,
    risk_service: RiskService | None = None,
):
    account, trades, positions, observed_pricing = observations(
        summary_value=summary_value,
        pricing_value=pricing_value,
    )
    return evaluate_paper_risk(
        decision,
        summary=account,
        trades=trades,
        positions=positions,
        pricing=observed_pricing,
        config=RiskConfig(Decimal("0.01")),
        risk_service=risk_service,
    )


def test_no_action_does_not_validate_observations_or_call_risk() -> None:
    result = evaluate_paper_risk(
        StrategyDecision(Action.NO_ACTION, Rationale("NONE")),
        summary=object(),  # type: ignore[arg-type]
        trades=object(),  # type: ignore[arg-type]
        positions=object(),  # type: ignore[arg-type]
        pricing=object(),  # type: ignore[arg-type]
        config=RiskConfig(Decimal("0.01")),
    )

    assert result.outcome is PaperRiskOutcome.NO_ACTION
    assert result.trade_intent is None
    assert result.pre_flight is None
    assert result.pricing_evidence is None


@pytest.mark.parametrize(
    "action",
    [Action.CLOSE_POSITION, Action.UPDATE_PROTECTION],
)
def test_nonopening_actions_are_explicitly_unsupported(action: Action) -> None:
    result = evaluate_paper_risk(
        StrategyDecision(action, Rationale("UNSUPPORTED")),
        summary=object(),  # type: ignore[arg-type]
        trades=object(),  # type: ignore[arg-type]
        positions=object(),  # type: ignore[arg-type]
        pricing=object(),  # type: ignore[arg-type]
        config=RiskConfig(Decimal("0.01")),
    )

    assert result.outcome is PaperRiskOutcome.UNSUPPORTED_ACTION


def test_price_triggered_open_is_deferred_without_risk_or_pricing() -> None:
    result = evaluate(opening(entry_policy=EntryPolicy.PRICE_TRIGGERED))

    assert result.outcome is PaperRiskOutcome.DEFERRED_ENTRY_POLICY
    assert result.trade_intent is None
    assert result.pre_flight is None
    assert result.pricing_evidence is None


def test_immediate_long_maps_intent_and_selects_adverse_supported_ask() -> None:
    result = evaluate(
        opening(),
        pricing_value=pricing(
            Direction.LONG,
            (("1.1002", "19230"), ("1.1000", "20000")),
        ),
    )

    assert result.outcome is PaperRiskOutcome.APPROVED
    assert result.trade_intent is not None
    assert result.trade_intent.action is Action.OPEN_LONG
    assert result.trade_intent.direction is Direction.LONG
    assert result.trade_intent.stop == Decimal("1.0950")
    assert result.pre_flight == RiskDecision(
        RiskPhase.PRE_FLIGHT,
        approved=True,
        stop_price=Decimal("1.0950"),
    )
    assert result.pre_submission is not None
    assert result.pre_submission.entry_price == Decimal("1.1002")
    assert result.pre_submission.quantity == Decimal("19230")
    assert result.pricing_evidence is not None
    assert result.pricing_evidence.selected_candidate is not None
    assert result.pricing_evidence.selected_candidate.price == Decimal("1.1002")
    assert len(result.pricing_evidence.candidate_results) == 2


def test_short_selects_lowest_approved_bid_and_retains_provenance() -> None:
    result = evaluate(
        opening(Direction.SHORT),
        pricing_value=pricing(
            Direction.SHORT,
            (("1.1000", "20000"), ("1.0998", "20000")),
        ),
    )

    assert result.outcome is PaperRiskOutcome.APPROVED
    assert result.pre_submission is not None
    assert result.pre_submission.entry_price == Decimal("1.0998")
    assert result.provenance is not None
    assert result.provenance.transaction_ids == ("10", "11", "12")


def test_identity_mismatch_and_count_mismatch_fail_before_risk() -> None:
    class RecordingRisk(RiskService):
        calls = 0

        def evaluate_pre_flight(self, *args: object, **kwargs: object) -> RiskDecision:
            self.calls += 1
            return super().evaluate_pre_flight(*args, **kwargs)  # type: ignore[arg-type]

    service = RecordingRisk()
    account, trades, positions, observed_pricing = observations(
        summary_value=summary(open_trade_count=1),
    )
    result = evaluate_paper_risk(
        opening(),
        summary=account,
        trades=trades,
        positions=positions,
        pricing=observed_pricing,
        config=RiskConfig(Decimal("0.01")),
        risk_service=service,
    )
    assert result.outcome is PaperRiskOutcome.OBSERVATION_MISMATCH
    assert service.calls == 0

    mismatch = replace(account, identity=identity(account_id="001-011-5838423-002"))
    result = evaluate_paper_risk(
        opening(),
        summary=mismatch,
        trades=trades,
        positions=positions,
        pricing=observed_pricing,
        config=RiskConfig(Decimal("0.01")),
        risk_service=service,
    )
    assert result.outcome is PaperRiskOutcome.IDENTITY_MISMATCH
    assert service.calls == 0


def test_pending_orders_block_before_risk() -> None:
    result = evaluate(
        opening(),
        summary_value=summary(pending_order_count=1),
    )

    assert result.outcome is PaperRiskOutcome.ENTRY_STATE_BLOCKED
    assert result.pre_flight is None


def test_stale_pricing_is_rejected_after_preflight() -> None:
    result = evaluate(
        opening(),
        pricing_value=pricing(
            Direction.LONG,
            (("1.1000", "20000"),),
            price_time=datetime(2026, 8, 31, 11, 59, tzinfo=UTC),
        ),
    )

    assert result.outcome is PaperRiskOutcome.PRICING_REJECTED
    assert result.pre_flight is not None and result.pre_flight.approved
    assert result.pre_submission is None


def test_capacity_only_failure_is_pricing_rejection_with_candidate_evidence() -> None:
    result = evaluate(
        opening(),
        pricing_value=pricing(Direction.LONG, (("1.1002", "19229"),)),
    )

    assert result.outcome is PaperRiskOutcome.PRICING_REJECTED
    assert result.pre_submission is None
    assert result.pricing_evidence is not None
    candidate_result = result.pricing_evidence.candidate_results[0]
    assert (
        candidate_result.decision.rejection
        is RiskRejection.INSUFFICIENT_EXECUTABLE_CAPACITY
    )


@pytest.mark.parametrize(
    "tradeable,buckets",
    [(False, (("1.1000", "20000"),)), (True, ())],
)
def test_unusable_required_side_is_pricing_rejection(
    tradeable: bool, buckets: tuple[tuple[str, str], ...]
) -> None:
    observed = pricing(Direction.LONG, buckets)
    observed = replace(observed, tradeable=tradeable)

    result = evaluate(opening(), pricing_value=observed)

    assert result.outcome is PaperRiskOutcome.PRICING_REJECTED
    assert result.pricing_evidence is not None
    assert result.pricing_evidence.candidate_results == ()


def test_generic_candidate_failure_is_pre_submission_rejection() -> None:
    result = evaluate(
        opening(stop=Decimal("1.1005")),
        pricing_value=pricing(Direction.LONG, (("1.1000", "20000"),)),
    )

    assert result.outcome is PaperRiskOutcome.PRE_SUBMISSION_REJECTED
    assert result.pre_submission is not None
    assert result.pre_submission.rejection is RiskRejection.INVALID_STOP
