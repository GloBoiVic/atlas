from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest

from backend.domain import (
    Action,
    Instrument,
    Rationale,
    StrategyDecision,
    StrategyEvaluation,
    StrategyState,
    StrategyVersion,
    ValidatedParameterPayload,
)
from backend.paper import (
    PAPER_BROKER_FACTS_SCHEMA_V1,
    PAPER_BROKER_FACTS_SCHEMA_V2,
    BrokerFillFacts,
    PaperBrokerObservation,
    PaperExecutionOutcome,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperPersistenceContractError,
    PaperRiskAuthoritySnapshot,
    PaperStrategyEvaluationReceipt,
    PaperTradeCloseTransaction,
    PaperTradeClosure,
    PaperTradeExitCause,
    canonical_json_bytes,
    validate_execution_outcome_transition,
)
from backend.risk import RiskConfig
from backend.tests.paper.test_risk_evaluation import evaluate, opening

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")
ATTEMPT_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_strategy_receipt_binds_exact_evaluation_and_parameters() -> None:
    decision = StrategyDecision(Action.NO_ACTION, Rationale("NO_ENTRY"))
    evaluation = StrategyEvaluation(decision, StrategyState())
    version = StrategyVersion(
        id=VERSION_ID,
        strategy_key="fixture",
        version_number=3,
        source_fingerprint="a" * 64,
        implementation_key="fixture.v3",
        parameter_schema=(),
        created_at=NOW,
    )
    parameters = ValidatedParameterPayload.from_mapping((), {})

    receipt = PaperStrategyEvaluationReceipt.from_verified(
        version, parameters, evaluation
    )

    assert receipt.evaluation.decision == decision
    assert receipt.to_json()["validated_parameter_snapshot"] == {}
    assert (
        receipt.fingerprint
        == PaperStrategyEvaluationReceipt.from_verified(
            version, parameters, evaluation
        ).fingerprint
    )


def test_risk_authority_snapshot_retains_config_equity_and_pricing_evidence() -> None:
    risk_evaluation = evaluate(opening())
    snapshot = PaperRiskAuthoritySnapshot.from_evaluation(
        risk_evaluation,
        config=RiskConfig(Decimal("0.01")),
        account_equity=Decimal("10000"),
    )

    payload = snapshot.to_json()
    assert payload["risk_config"] == {"risk_per_trade": "0.01"}
    account = cast(dict[str, object], payload["account"])
    pricing = cast(dict[str, object], payload["pricing_evidence"])
    assert account["equity"] == "10000"
    assert pricing["candidates"]
    assert len(canonical_json_bytes(payload, maximum=32_768)) <= 32_768


def test_normalized_observations_are_whitelisted_and_fingerprint_is_canonical() -> None:
    observation = PaperBrokerObservation(
        attempt_id=ATTEMPT_ID,
        read_kind=PaperObservationReadKind.ORDER_DETAIL,
        object_kind=PaperObservationObjectKind.ORDER,
        provider_account_id="001-011-5838423-001",
        instrument=Instrument.EUR_USD,
        normalized_facts={"order_id": "42", "state": "PENDING"},
        provider_order_id="42",
        client_order_id="atlas-p04-o-22222222222222222222222222222222",
        atlas_observed_at=NOW,
    )
    same_facts = replace(
        observation,
        normalized_facts={"state": "PENDING", "order_id": "42"},
    )
    assert (
        observation.normalized_facts_fingerprint
        == same_facts.normalized_facts_fingerprint
    )
    with pytest.raises(PaperPersistenceContractError, match="non-whitelisted"):
        replace(observation, normalized_facts={"raw_body": {"secret": "no"}})


def test_trade_closure_is_immutable_and_preserves_exact_decimal_evidence() -> None:
    closure = PaperTradeClosure(
        trade_id="7001",
        closed_at=datetime(2026, 9, 2, 14, tzinfo=UTC),
        average_close_price=Decimal("1.11030"),
        realized_pl=Decimal("196.1538"),
        financing=Decimal("-0.42"),
        dividend_adjustment=Decimal("0"),
        closing_transaction_ids=("43",),
        exit_cause=PaperTradeExitCause.TAKE_PROFIT,
        provider_reason="TAKE_PROFIT_ORDER",
        closing_transaction_id="43",
        exact_close_price=Decimal("1.11035"),
    )

    assert closure.to_json() == {
        "trade_id": "7001",
        "closed_at": "2026-09-02T14:00:00Z",
        "average_close_price": "1.11030",
        "realized_pl": "196.1538",
        "financing": "-0.42",
        "dividend_adjustment": "0",
        "closing_transaction_ids": ["43"],
        "exit_cause": "TAKE_PROFIT",
        "provider_reason": "TAKE_PROFIT_ORDER",
        "closing_transaction_id": "43",
        "exact_close_price": "1.11035",
    }
    with pytest.raises(FrozenInstanceError):
        closure.__setattr__("realized_pl", Decimal("0"))


def test_trade_closure_enforces_multiple_and_unresolved_semantics() -> None:
    multiple = PaperTradeClosure(
        trade_id="7001",
        closed_at=NOW,
        average_close_price=Decimal("1.11030"),
        realized_pl=Decimal("1"),
        financing=Decimal("2"),
        dividend_adjustment=Decimal("0"),
        closing_transaction_ids=("43", "44"),
        exit_cause=PaperTradeExitCause.MULTIPLE,
    )
    unresolved = PaperTradeClosure(
        trade_id="7001",
        closed_at=NOW,
        average_close_price=Decimal("1.11030"),
        realized_pl=Decimal("1"),
        financing=Decimal("2"),
        dividend_adjustment=Decimal("0"),
        closing_transaction_ids=("43",),
        exit_cause=PaperTradeExitCause.UNRESOLVED,
    )

    assert multiple.closing_transaction_id is None
    assert multiple.exact_close_price is None
    assert multiple.provider_reason is None
    assert unresolved.exit_cause is PaperTradeExitCause.UNRESOLVED
    with pytest.raises(PaperPersistenceContractError, match="multiple closes"):
        replace(multiple, exit_cause=PaperTradeExitCause.STOP_LOSS)


def test_close_transaction_contract_is_bounded_and_decimal_exact() -> None:
    close = PaperTradeCloseTransaction(
        transaction_id="43",
        trade_id="7001",
        closed_units=Decimal("19230"),
        close_price=Decimal("1.11035"),
        realized_pl=Decimal("196.1538"),
        financing=Decimal("-0.42"),
        provider_reason="TAKE_PROFIT_ORDER",
        exit_cause=PaperTradeExitCause.TAKE_PROFIT,
    )

    assert close.to_json()["close_price"] == "1.11035"
    assert replace(close, provider_reason=None).to_json()["provider_reason"] is None
    with pytest.raises(PaperPersistenceContractError, match="positive"):
        replace(close, close_price=Decimal("0"))
    with pytest.raises(PaperPersistenceContractError, match="bounded"):
        replace(close, transaction_id="9" * 65)


def test_v2_normalized_closure_facts_keep_v1_observation_defaults() -> None:
    observation = PaperBrokerObservation(
        attempt_id=ATTEMPT_ID,
        read_kind=PaperObservationReadKind.TRADE_DETAIL,
        object_kind=PaperObservationObjectKind.TRADE,
        provider_account_id="001-011-5838423-001",
        instrument=Instrument.EUR_USD,
        normalized_facts={
            "trade_id": "7001",
            "state": "CLOSED",
            "close_time": "2026-09-02T14:00:00Z",
            "average_close_price": "1.11030",
            "realized_pl": "1",
            "financing": "-0.42",
            "dividend_adjustment": "0",
            "closing_transaction_ids": ["43"],
            "exit_cause": "UNRESOLVED",
        },
        normalized_schema_version=PAPER_BROKER_FACTS_SCHEMA_V2,
        atlas_observed_at=NOW,
    )

    assert observation.normalized_schema_version == PAPER_BROKER_FACTS_SCHEMA_V2
    assert observation.to_json()["facts"] == observation.normalized_facts
    with pytest.raises(PaperPersistenceContractError, match="V2"):
        replace(observation, normalized_schema_version=PAPER_BROKER_FACTS_SCHEMA_V1)


def test_execution_outcome_validator_preserves_fill_truth_and_protection_boundary() -> (
    None
):
    fill = BrokerFillFacts(
        broker_order_id="42",
        broker_fill_transaction_id="43",
        broker_trade_id="44",
        signed_units=Decimal("1000"),
        price=Decimal("1.1000"),
        executed_at=NOW,
        actual_initial_risk=Decimal("50"),
    )
    validate_execution_outcome_transition(
        None, PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE, fill=fill
    )
    with pytest.raises(PaperPersistenceContractError, match="downgraded"):
        validate_execution_outcome_transition(
            PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            PaperExecutionOutcome.UNKNOWN,
            fill=None,
        )
    with pytest.raises(PaperPersistenceContractError, match="no-Fill"):
        validate_execution_outcome_transition(
            None,
            PaperExecutionOutcome.REJECTED,
            fill=fill,
        )
    with pytest.raises(PaperPersistenceContractError, match="confirmed protections"):
        validate_execution_outcome_transition(
            PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            PaperExecutionOutcome.FILLED_PROTECTED,
            fill=fill,
        )
