from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from backend.domain import (
    Action,
    Direction,
    EntryPolicy,
    Instrument,
    Provider,
    Rationale,
    StopProposal,
    StrategyDecision,
    TargetProposal,
)
from backend.paper.execution import (
    ExecutionAccountIdentity,
    ExecutionObservationProvenance,
    PaperExecutionContractError,
    PaperExecutionInstruction,
    PaperExecutionRefusal,
    PaperExecutionRefusalCode,
)
from backend.risk import RiskDecision, RiskPhase

ACCOUNT_ID = "001-011-5838423-001"
DECISION_TIME = datetime(2026, 9, 1, 12, tzinfo=UTC)
PRICING_TIME = datetime(2026, 9, 1, 12, 0, 1, tzinfo=UTC)
ATTEMPT_ID = UUID("12345678-1234-5678-1234-567812345678")


def decision(direction: Direction = Direction.LONG) -> StrategyDecision:
    action = Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT
    stop = Decimal("1.0950") if direction is Direction.LONG else Decimal("1.1050")
    return StrategyDecision(
        action=action,
        rationale=Rationale("TEST"),
        direction=direction,
        decision_time=DECISION_TIME,
        stop=StopProposal(stop, direction),
        target=TargetProposal(multiple=Decimal("1.7")),
        entry_policy=EntryPolicy.IMMEDIATE,
    )


def instruction(direction: Direction = Direction.LONG) -> PaperExecutionInstruction:
    strategy_decision = decision(direction)
    stop = strategy_decision.stop
    assert stop is not None
    entry = Decimal("1.1002") if direction is Direction.LONG else Decimal("1.0998")
    return PaperExecutionInstruction(
        attempt_id=ATTEMPT_ID,
        strategy_decision=strategy_decision,
        account=ExecutionAccountIdentity(
            provider=Provider.OANDA,
            environment="PRACTICE",
            account_id=ACCOUNT_ID,
            base_currency="USD",
        ),
        instrument=Instrument.EUR_USD,
        direction=direction,
        requested_quantity=Decimal("19230"),
        approved_entry_price=entry,
        stop_price=stop.price,
        decision_time=DECISION_TIME,
        pricing_time=PRICING_TIME,
        pre_flight=RiskDecision(
            phase=RiskPhase.PRE_FLIGHT,
            approved=True,
            stop_price=stop.price,
        ),
        pre_submission=RiskDecision(
            phase=RiskPhase.PRE_SUBMISSION,
            approved=True,
            entry_price=entry,
            stop_price=stop.price,
            target_price=Decimal("1.10904")
            if direction is Direction.LONG
            else Decimal("1.09146"),
            risk_budget=Decimal("100"),
            quantity=Decimal("19230"),
            actual_risk=Decimal("100"),
        ),
        observation_provenance=ExecutionObservationProvenance(
            identity=ExecutionAccountIdentity(
                provider=Provider.OANDA,
                environment="PRACTICE",
                account_id=ACCOUNT_ID,
                base_currency="USD",
            ),
            account_transaction_id="42",
            pricing_time=PRICING_TIME,
            instrument_transaction_id="43",
        ),
        display_precision=5,
        trade_units_precision=0,
    )


def test_instruction_preserves_fresh_risk_facts_and_is_immutable() -> None:
    value = instruction()

    assert value.requested_quantity == value.pre_submission.quantity
    assert value.approved_entry_price == value.pre_submission.entry_price
    assert value.stop_price == value.pre_submission.stop_price
    assert value.correlation.client_order_id.startswith("atlas-p04-o-")
    with pytest.raises(FrozenInstanceError):
        value.__setattr__("requested_quantity", Decimal("1"))


def test_instruction_rejects_stale_or_mismatched_pre_submission_facts() -> None:
    with pytest.raises(PaperExecutionContractError, match="PRE_SUBMISSION"):
        value = instruction()
        replace(
            value,
            pre_submission=replace(value.pre_submission, quantity=Decimal("19229")),
        )


def test_refusal_is_bounded_and_never_marked_submitted() -> None:
    refusal = PaperExecutionRefusal(
        ATTEMPT_ID,
        PaperExecutionRefusalCode.RISK_REJECTED,
        "PRE_SUBMISSION_REJECTED",
    )

    assert refusal.submitted is False
    assert refusal.detail_code == "PRE_SUBMISSION_REJECTED"
    with pytest.raises(PaperExecutionContractError):
        PaperExecutionRefusal(
            ATTEMPT_ID,
            PaperExecutionRefusalCode.RISK_REJECTED,
            "provider said " + "x" * 1000,
        )
