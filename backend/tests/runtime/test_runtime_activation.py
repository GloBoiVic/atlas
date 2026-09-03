from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.api.schemas import PaperActivationRequest as PaperActivationHttpRequest
from backend.api.schemas import PaperStopRequest as PaperStopHttpRequest
from backend.domain import ValidatedParameterPayload
from backend.paper.execution import PaperExecutionOutcome
from backend.paper.persistence_contracts import ReconciliationStatus
from backend.persistence.runtime_repository import (
    PaperRuntimeActivationAlreadyPresent,
    PaperRuntimeIdentityConflict,
    is_unsafe_paper_attempt,
)
from backend.runtime import (
    PaperActivationRequest,
    PaperRuntimeActivation,
    PaperRuntimeConfigurationError,
    PaperRuntimeLifecycleState,
    PaperRuntimeReconcileResult,
    PaperRuntimeService,
    PaperRuntimeServiceError,
    PaperStopRequest,
    runtime_parameter_fingerprint,
)

ACTIVATION_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def begin(self):
        return _Transaction()


def _activation(
    activation_id: UUID = ACTIVATION_ID,
    lifecycle_state: PaperRuntimeLifecycleState = PaperRuntimeLifecycleState.REQUESTED,
) -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    return PaperRuntimeActivation(
        activation_id=activation_id,
        strategy_version_id=VERSION_ID,
        strategy_key="runtime_fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="runtime_fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=Decimal("0.01"),
        requested_at=NOW,
        provider_account_id="001-002-003-004",
        lifecycle_state=lifecycle_state,
    )


def _service(repository, *, reconciliation=None):
    return PaperRuntimeService(
        session_factory=_Session,
        settings=SimpleNamespace(
            oanda_api_token=SimpleNamespace(get_secret_value=lambda: "token"),
            oanda_account_id="001-002-003-004",
        ),
        registry=SimpleNamespace(),  # type: ignore[arg-type]
        repository=repository,
        reconciliation=reconciliation,
        clock=lambda: NOW,
    )


def test_http_activation_contract_requires_exact_confirmation_and_decimal_wire_value():
    valid = {
        "activationRequestId": str(ACTIVATION_ID),
        "strategyVersionId": str(VERSION_ID),
        "parameters": {},
        "riskPerTrade": "0.0100",
        "confirmation": "ACTIVATE_PAPER",
    }
    request = PaperActivationHttpRequest.model_validate(valid)
    assert request.risk_per_trade == Decimal("0.0100")
    assert request.model_dump(by_alias=True, mode="json")["riskPerTrade"] == "0.0100"

    with pytest.raises(ValidationError):
        PaperActivationHttpRequest.model_validate({**valid, "riskPerTrade": 0.01})
    with pytest.raises(ValidationError):
        PaperActivationHttpRequest.model_validate(
            {**valid, "confirmation": "START_PAPER"}
        )
    with pytest.raises(ValidationError):
        PaperActivationHttpRequest.model_validate({**valid, "unexpected": True})


def test_typed_activation_and_stop_contracts_reject_unsafe_values():
    request = PaperActivationRequest(
        activation_request_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        parameters={},
        risk_per_trade=Decimal("0.01"),
        confirmation="ACTIVATE_PAPER",
    )
    assert request.parameters == {}

    with pytest.raises(ValueError, match="less than one"):
        PaperActivationRequest(
            activation_request_id=ACTIVATION_ID,
            strategy_version_id=VERSION_ID,
            parameters={},
            risk_per_trade=Decimal("1"),
            confirmation="ACTIVATE_PAPER",
        )
    with pytest.raises(ValueError, match="confirmation"):
        PaperActivationRequest(
            activation_request_id=ACTIVATION_ID,
            strategy_version_id=VERSION_ID,
            parameters={},
            risk_per_trade=Decimal("0.01"),
            confirmation="START_PAPER",
        )
    with pytest.raises(ValueError, match="non-empty"):
        PaperStopRequest("")
    with pytest.raises(ValidationError):
        PaperStopHttpRequest.model_validate({"reason": "\nunsafe"})


def test_capability_is_local_and_never_contains_token_material():
    settings = SimpleNamespace(
        oanda_api_token=SimpleNamespace(get_secret_value=lambda: "top-secret-token"),
        oanda_account_id="001-002-003-004",
    )
    service = PaperRuntimeService(
        session_factory=lambda: pytest.fail("activation capability opened a database"),
        settings=settings,
        registry=SimpleNamespace(),  # type: ignore[arg-type]
    )

    capability = service.capability()
    payload = capability.to_json()
    assert capability.available is True
    assert payload["token_configured"] is True
    assert "top-secret-token" not in repr(payload)


def test_activation_without_token_is_rejected_before_database_or_provider_access():
    service = PaperRuntimeService(
        session_factory=lambda: pytest.fail("invalid activation opened a database"),
        settings=SimpleNamespace(
            oanda_api_token=None,
            oanda_account_id="001-002-003-004",
        ),
        registry=SimpleNamespace(),  # type: ignore[arg-type]
    )
    request = PaperActivationRequest(
        activation_request_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        parameters={},
        risk_per_trade=Decimal("0.01"),
        confirmation="ACTIVATE_PAPER",
    )

    with pytest.raises(PaperRuntimeConfigurationError) as error:
        service.activate(request)
    assert error.value.code == "OANDA_TOKEN_REQUIRED"
    assert "token" not in str(error.value).lower() or "required" in str(error.value)


def test_reconcile_result_is_bounded_and_reports_read_only_evidence():
    value = PaperRuntimeReconcileResult(
        activation_id=ACTIVATION_ID,
        attempt_id=VERSION_ID,
        performed=True,
        reconciliation_status=ReconciliationStatus.UNRESOLVED,
        execution_outcome=PaperExecutionOutcome.UNKNOWN,
        stale=True,
    )
    assert value.to_json() == {
        "activation_id": str(ACTIVATION_ID),
        "attempt_id": str(VERSION_ID),
        "performed": True,
        "reconciliation_status": "UNRESOLVED",
        "execution_outcome": "UNKNOWN",
        "stale": True,
    }


def test_service_activation_replays_exact_id_and_maps_conflicts(monkeypatch):
    class Repository:
        def __init__(self):
            self.row = None
            self.mode = "create"

        def get_activation(self, _session, _activation_id, *, for_update=False):
            return self.row

        def create_activation(self, _session, activation):
            if self.mode == "identity":
                raise PaperRuntimeIdentityConflict("different durable identity")
            if self.mode == "occupied":
                raise PaperRuntimeActivationAlreadyPresent("occupied")
            self.row = SimpleNamespace(domain=activation)
            return self.row

    repository = Repository()
    service = _service(repository)
    durable = _activation()
    monkeypatch.setattr(
        service,
        "_build_activation",
        lambda _session, _request, _requested_at: durable,
    )
    monkeypatch.setattr(service, "_unsafe_attempt_exists", lambda *_args: False)
    monkeypatch.setattr(
        "backend.runtime.activation._activation_from_row",
        lambda _session, row: row.domain,
    )
    request = PaperActivationRequest(
        activation_request_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        parameters={},
        risk_per_trade=Decimal("0.01"),
        confirmation="ACTIVATE_PAPER",
    )

    first = service.activate(request)
    assert first.replayed is False
    replay = service.activate(request)
    assert replay.replayed is True

    repository.row = None
    repository.mode = "identity"
    with pytest.raises(PaperRuntimeServiceError) as identity_error:
        service.activate(request)
    assert identity_error.value.code == "ACTIVATION_IDENTITY_CONFLICT"

    repository.mode = "occupied"
    with pytest.raises(PaperRuntimeServiceError) as occupied_error:
        service.activate(request)
    assert occupied_error.value.code == "PAPER_ACTIVATION_ALREADY_PRESENT"


def test_service_stop_is_idempotent_and_fenced(monkeypatch):
    class Repository:
        def __init__(self):
            self.row = SimpleNamespace(
                lifecycle_state=PaperRuntimeLifecycleState.RUNNING.value,
                domain=_activation(lifecycle_state=PaperRuntimeLifecycleState.RUNNING),
            )
            self.stop_calls = 0

        def get_activation(self, _session, _activation_id, *, for_update=False):
            return self.row

        def request_stop(self, _session, _activation_id, **_kwargs):
            self.stop_calls += 1
            self.row.lifecycle_state = PaperRuntimeLifecycleState.STOP_REQUESTED.value
            self.row.domain = _activation(
                lifecycle_state=PaperRuntimeLifecycleState.STOP_REQUESTED
            )
            return self.row

    repository = Repository()
    service = _service(repository)
    monkeypatch.setattr(
        "backend.runtime.activation._activation_from_row",
        lambda _session, row: row.domain,
    )

    stopped = service.stop(ACTIVATION_ID, PaperStopRequest("operator requested stop"))
    assert stopped.lifecycle_state is PaperRuntimeLifecycleState.STOP_REQUESTED
    repeated = service.stop(ACTIVATION_ID, PaperStopRequest("same request"))
    assert repeated.lifecycle_state is PaperRuntimeLifecycleState.STOP_REQUESTED
    assert repository.stop_calls == 1


def test_service_refuses_active_reconcile_and_delegates_terminal_attempt(monkeypatch):
    active_row = SimpleNamespace(
        lifecycle_state=PaperRuntimeLifecycleState.RUNNING.value,
        domain=_activation(lifecycle_state=PaperRuntimeLifecycleState.RUNNING),
    )
    coordinator = Mock()
    service = _service(
        SimpleNamespace(get_activation=lambda *_args, **_kwargs: active_row),
        reconciliation=coordinator,
    )
    monkeypatch.setattr(service, "_latest_attempt", lambda *_args: None)

    with pytest.raises(PaperRuntimeServiceError) as busy_error:
        service.reconcile(ACTIVATION_ID)
    assert busy_error.value.code == "RUNTIME_RECONCILIATION_BUSY"
    coordinator.reconcile.assert_not_called()

    attempt_id = UUID("33333333-3333-3333-3333-333333333333")
    terminal_row = SimpleNamespace(
        lifecycle_state=PaperRuntimeLifecycleState.STOPPED.value,
        domain=_activation(lifecycle_state=PaperRuntimeLifecycleState.STOPPED),
    )
    repository = SimpleNamespace(get_activation=lambda *_args, **_kwargs: terminal_row)
    coordinator.reconcile.return_value = SimpleNamespace(
        reconciliation_status=ReconciliationStatus.UNRESOLVED,
        execution_outcome=PaperExecutionOutcome.UNKNOWN,
        stale=True,
    )
    service = _service(repository, reconciliation=coordinator)
    monkeypatch.setattr(
        service,
        "_latest_attempt",
        lambda *_args: SimpleNamespace(
            attempt_id=attempt_id,
            execution_outcome=None,
            reconciliation_status="UNRESOLVED",
        ),
    )

    result = service.reconcile(ACTIVATION_ID, read_budget=4)
    assert result.performed is True
    assert result.attempt_id == attempt_id
    assert result.reconciliation_status == "UNRESOLVED"
    assert result.execution_outcome == "UNKNOWN"
    coordinator.reconcile.assert_called_once_with(attempt_id, read_budget=4)


@pytest.mark.parametrize(
    ("execution_outcome", "reconciliation_status", "unsafe"),
    [
        ("REJECTED", "NOT_RUN", False),
        ("CANCELLED", "NOT_RUN", False),
        ("FILLED_PROTECTED", "NOT_RUN", False),
        ("UNKNOWN", "NOT_RUN", True),
        ("FILLED_PROTECTION_INCOMPLETE", "NOT_RUN", True),
        ("REJECTED", "UNRESOLVED", True),
        ("CANCELLED", "CONFLICT", True),
        (None, "NOT_RUN", True),
        ({}, "NOT_RUN", True),
        ("MALFORMED", "NOT_RUN", True),
    ],
)
def test_paper_attempt_safety_truth_table(
    execution_outcome, reconciliation_status, unsafe
):
    assert is_unsafe_paper_attempt(execution_outcome, reconciliation_status) is unsafe


@pytest.mark.parametrize(
    ("execution_outcome", "reconciliation_status", "unsafe"),
    [
        ("REJECTED", "NOT_RUN", False),
        ("CANCELLED", "NOT_RUN", False),
        ("FILLED_PROTECTED", "NOT_RUN", False),
        ("UNKNOWN", "NOT_RUN", True),
        ("FILLED_PROTECTION_INCOMPLETE", "NOT_RUN", True),
        ("REJECTED", "UNRESOLVED", True),
        ("REJECTED", "CONFLICT", True),
        (None, "NOT_RUN", True),
        ("MALFORMED", "NOT_RUN", True),
    ],
)
def test_activation_eligibility_uses_the_terminal_safety_matrix(
    monkeypatch,
    execution_outcome,
    reconciliation_status,
    unsafe,
):
    class Repository:
        def has_unsafe_attempt(self, _session, _account_id):
            return is_unsafe_paper_attempt(execution_outcome, reconciliation_status)

        def get_activation(self, _session, _activation_id):
            return None

        def create_activation(self, _session, activation):
            return SimpleNamespace(domain=activation)

    service = _service(Repository())
    durable = _activation()
    monkeypatch.setattr(service, "_build_activation", lambda *_args, **_kwargs: durable)
    monkeypatch.setattr(
        "backend.runtime.activation._activation_from_row",
        lambda _session, row: row.domain,
    )
    request = PaperActivationRequest(
        activation_request_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        parameters={},
        risk_per_trade=Decimal("0.01"),
        confirmation="ACTIVATE_PAPER",
    )

    if unsafe:
        with pytest.raises(PaperRuntimeServiceError) as error:
            service.activate(request)
        assert error.value.code == "PAPER_ATTEMPT_UNSAFE"
    else:
        result = service.activate(request)
        assert result.replayed is False


@pytest.mark.parametrize(
    ("execution_outcome", "reconciliation_status", "outstanding"),
    [
        ("REJECTED", "NOT_RUN", False),
        ("CANCELLED", "NOT_RUN", False),
        ("FILLED_PROTECTED", "NOT_RUN", False),
        ("UNKNOWN", "NOT_RUN", True),
        ("FILLED_PROTECTION_INCOMPLETE", "NOT_RUN", True),
        ("REJECTED", "UNRESOLVED", True),
        ("REJECTED", "CONFLICT", True),
        (None, "NOT_RUN", True),
        ("MALFORMED", "NOT_RUN", True),
    ],
)
def test_activation_reconcile_only_treats_unsafe_truth_as_outstanding(
    execution_outcome, reconciliation_status, outstanding
):
    row = SimpleNamespace(
        execution_outcome=execution_outcome,
        reconciliation_status=reconciliation_status,
    )
    assert PaperRuntimeService._attempt_is_outstanding(row) is outstanding
