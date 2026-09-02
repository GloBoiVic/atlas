from dataclasses import replace
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
    BrokerFillFacts,
    PaperBrokerObservation,
    PaperExecutionOutcome,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperPersistenceContractError,
    PaperRiskAuthoritySnapshot,
    PaperStrategyEvaluationReceipt,
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
