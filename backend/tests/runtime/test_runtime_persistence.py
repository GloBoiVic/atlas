from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.domain import FinancialPositionState, ValidatedParameterPayload
from backend.runtime import (
    PaperRuntimeActivation,
    PaperRuntimeCycle,
    PaperRuntimeCycleStatus,
    PaperRuntimeLifecycleState,
    PaperRuntimeOwnership,
    PaperRuntimeOwnershipPhase,
    PaperRuntimePersistenceError,
    runtime_evaluation_key,
    runtime_parameter_fingerprint,
    validate_runtime_json_object,
)

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


def activation() -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    version_id = uuid4()
    return PaperRuntimeActivation(
        activation_id=uuid4(),
        strategy_version_id=version_id,
        strategy_key="fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=Decimal("0.0100"),
        provider_account_id="001-002-003-004",
        requested_at=NOW,
    )


def test_activation_is_fixed_scope_and_decimal_identity_is_canonical() -> None:
    value = activation()

    assert value.provider == "OANDA"
    assert value.environment == "PRACTICE"
    assert value.immutable_json()["risk_per_trade"] == "0.01"
    assert value.to_json()["lifecycle_state"] == PaperRuntimeLifecycleState.REQUESTED

    with pytest.raises(PaperRuntimePersistenceError, match="less than one"):
        activation_with(risk_per_trade=Decimal("1"))


def test_runtime_json_accepts_nested_object_and_list_sentinels() -> None:
    value = {
        "outer": [{"inner": [{"label": "sentinel-value"}]}],
    }

    assert validate_runtime_json_object(value) == value


def test_runtime_json_rejects_secret_key_inside_nested_lists() -> None:
    value = {
        "outer": [{"inner": [{"api_token": "sentinel-value"}]}],
    }

    with pytest.raises(PaperRuntimePersistenceError, match="secret field"):
        validate_runtime_json_object(value)


def test_cycle_binds_position_and_unique_configuration_key() -> None:
    value = activation()
    cycle = PaperRuntimeCycle(
        cycle_id=uuid4(),
        activation_id=value.activation_id,
        cycle_sequence=1,
        evaluation_key=runtime_evaluation_key(
            value.strategy_version_id, value.parameter_fingerprint
        ),
        strategy_version_id=value.strategy_version_id,
        parameter_fingerprint=value.parameter_fingerprint,
        frontier_start=NOW,
        frontier_end=NOW + timedelta(minutes=15),
        financial_position_state=FinancialPositionState.LONG,
        account_transaction_id="42",
        account_observed_at=NOW,
        account_open_trade_count=1,
        account_open_position_count=1,
        account_pending_order_count=0,
        account_gate_fingerprint="b" * 64,
        cycle_status=PaperRuntimeCycleStatus.CLAIMED,
        claimed_at=NOW,
    )

    assert cycle.to_json()["financial_position_state"] == "LONG"
    assert cycle.to_json()["cycle_status"] == "CLAIMED"


def cycle_with_status(
    status: PaperRuntimeCycleStatus, *, attempt_id: UUID | None = None
) -> PaperRuntimeCycle:
    value = activation()
    return PaperRuntimeCycle(
        cycle_id=uuid4(),
        activation_id=value.activation_id,
        cycle_sequence=1,
        evaluation_key=runtime_evaluation_key(
            value.strategy_version_id, value.parameter_fingerprint
        ),
        strategy_version_id=value.strategy_version_id,
        parameter_fingerprint=value.parameter_fingerprint,
        frontier_start=NOW,
        frontier_end=NOW + timedelta(minutes=15),
        financial_position_state=FinancialPositionState.FLAT,
        account_transaction_id="42",
        account_observed_at=NOW,
        account_open_trade_count=0,
        account_open_position_count=0,
        account_pending_order_count=0,
        account_gate_fingerprint="b" * 64,
        cycle_status=status,
        claimed_at=NOW,
        attempt_id=attempt_id,
    )


@pytest.mark.parametrize(
    "status",
    [
        PaperRuntimeCycleStatus.ENTRY_CLAIMED,
        PaperRuntimeCycleStatus.ENTRY_RESOLVED,
        PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
    ],
)
def test_opening_cycle_status_requires_attempt_id(
    status: PaperRuntimeCycleStatus,
) -> None:
    with pytest.raises(PaperRuntimePersistenceError, match="requires an attempt"):
        cycle_with_status(status)

    attempt_id = uuid4()
    cycle = cycle_with_status(status, attempt_id=attempt_id)
    assert cycle.attempt_id == attempt_id


@pytest.mark.parametrize(
    "status",
    [
        PaperRuntimeCycleStatus.CLAIMED,
        PaperRuntimeCycleStatus.EVALUATING,
        PaperRuntimeCycleStatus.NO_ACTION,
        PaperRuntimeCycleStatus.REFUSED,
        PaperRuntimeCycleStatus.BLOCKED,
    ],
)
def test_non_opening_cycle_status_rejects_attempt_id(
    status: PaperRuntimeCycleStatus,
) -> None:
    with pytest.raises(
        PaperRuntimePersistenceError,
        match="cannot contain an execution attempt",
    ):
        cycle_with_status(status, attempt_id=uuid4())


def test_ownership_requires_positive_generation_and_fixed_slot() -> None:
    value = activation()
    owner = PaperRuntimeOwnership(
        owner_id=uuid4(),
        activation_id=value.activation_id,
        owner_generation=1,
        acquired_at=NOW,
        heartbeat_at=NOW,
        phase=PaperRuntimeOwnershipPhase.ACQUIRED,
    )
    assert owner.to_json()["slot_key"] == "ATLAS_PAPER_RUNTIME"

    with pytest.raises(PaperRuntimePersistenceError, match="positive"):
        PaperRuntimeOwnership(
            owner_id=uuid4(),
            activation_id=None,
            owner_generation=0,
            acquired_at=NOW,
            heartbeat_at=NOW,
            phase=PaperRuntimeOwnershipPhase.ACQUIRED,
        )


def activation_with(**changes: object) -> PaperRuntimeActivation:
    value = activation()
    payload: dict[str, object] = {
        "activation_id": value.activation_id,
        "strategy_version_id": value.strategy_version_id,
        "strategy_key": value.strategy_key,
        "strategy_version_number": value.strategy_version_number,
        "source_fingerprint": value.source_fingerprint,
        "implementation_key": value.implementation_key,
        "validated_parameter_snapshot": value.validated_parameter_snapshot,
        "parameter_fingerprint": value.parameter_fingerprint,
        "risk_per_trade": value.risk_per_trade,
        "provider_account_id": value.provider_account_id,
        "requested_at": value.requested_at,
    }
    payload.update(changes)
    return PaperRuntimeActivation(**payload)  # type: ignore[arg-type]
