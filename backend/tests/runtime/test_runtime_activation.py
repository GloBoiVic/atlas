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
    PaperRuntimeRepository,
    is_new_session_safe_attempt,
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
HISTORY_ATTEMPT_ID = UUID("9530bab6-fea0-4f86-aa65-bbc9e1f1759a")
HISTORY_RUN_ID = UUID("44444444-4444-4444-4444-444444444444")


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


def _history_attempt(
    execution_outcome: object,
    reconciliation_status: object,
    *,
    attempt_id: UUID = HISTORY_ATTEMPT_ID,
    complete_fill: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        attempt_id=attempt_id,
        provider="OANDA",
        environment="PRACTICE",
        provider_account_id="001-002-003-004",
        base_currency="USD",
        instrument="EUR_USD",
        execution_outcome=execution_outcome,
        reconciliation_status=reconciliation_status,
        fill_broker_order_id="order-1" if complete_fill else None,
        fill_transaction_id="transaction-1" if complete_fill else None,
        fill_trade_id="trade-1" if complete_fill else None,
        fill_signed_units=Decimal("1000") if complete_fill else None,
        fill_price=Decimal("1.1") if complete_fill else None,
        fill_executed_at=NOW if complete_fill else None,
        fill_actual_initial_risk=Decimal("10") if complete_fill else None,
        last_reconciliation_run_id=HISTORY_RUN_ID if complete_fill else None,
        last_reconciled_at=NOW if complete_fill else None,
        reconciliation_block_code=None,
        projection_version=1,
    )


def _history_run(
    attempt: SimpleNamespace,
    *,
    status: object = "LIFECYCLE_ADVANCED",
    projection_version_observed: object = 0,
    projection_version_applied: object = 1,
    prior_execution_outcome: object = "FILLED_PROTECTION_INCOMPLETE",
    resulting_execution_outcome: object = "FILLED_PROTECTION_INCOMPLETE",
    completed_at: object = NOW,
    read_count: object = 1,
    read_budget: object = 8,
    non_atomic_read_set: object = False,
    finding_codes: object = ["TRADE_LIFECYCLE_ADVANCED"],
    diagnostic_summary: object = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=HISTORY_RUN_ID,
        attempt_id=attempt.attempt_id,
        run_sequence=1,
        status=status,
        projection_version_observed=projection_version_observed,
        projection_version_applied=projection_version_applied,
        prior_execution_outcome=prior_execution_outcome,
        resulting_execution_outcome=resulting_execution_outcome,
        completed_at=completed_at,
        read_count=read_count,
        read_budget=read_budget,
        non_atomic_read_set=non_atomic_read_set,
        finding_codes=finding_codes,
        diagnostic_summary=diagnostic_summary,
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


@pytest.mark.parametrize(
    ("execution_outcome", "reconciliation_status", "safe"),
    [
        ("REJECTED", "NOT_RUN", True),
        ("REJECTED", "CONSISTENT", True),
        ("REJECTED", "LIFECYCLE_ADVANCED", True),
        ("CANCELLED", "NOT_RUN", True),
        ("CANCELLED", "CONSISTENT", True),
        ("CANCELLED", "LIFECYCLE_ADVANCED", True),
        ("FILLED_PROTECTED", "NOT_RUN", True),
        ("FILLED_PROTECTED", "CONSISTENT", True),
        ("FILLED_PROTECTED", "LIFECYCLE_ADVANCED", True),
        ("REJECTED", "UNRESOLVED", False),
        ("CANCELLED", "CONFLICT", False),
        ("FILLED_PROTECTED", "UNRESOLVED", False),
        ("FILLED_PROTECTION_INCOMPLETE", "NOT_RUN", False),
        ("FILLED_PROTECTION_INCOMPLETE", "CONSISTENT", False),
        ("FILLED_PROTECTION_INCOMPLETE", "UNRESOLVED", False),
        ("FILLED_PROTECTION_INCOMPLETE", "CONFLICT", False),
        ("UNKNOWN", "NOT_RUN", False),
        ("UNKNOWN", "LIFECYCLE_ADVANCED", False),
        (None, "NOT_RUN", False),
        ({}, "NOT_RUN", False),
        ("MALFORMED", "NOT_RUN", False),
        ("REJECTED", None, False),
    ],
)
def test_new_session_history_classifier_has_separate_fail_closed_matrix(
    execution_outcome: object, reconciliation_status: object, safe: bool
) -> None:
    attempt = _history_attempt(execution_outcome, reconciliation_status)

    assert is_new_session_safe_attempt(attempt, None) is safe


def test_lifecycle_advanced_incomplete_fill_requires_applied_coherent_evidence() -> (
    None
):
    attempt = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        complete_fill=True,
    )
    run = _history_run(attempt)

    assert is_new_session_safe_attempt(attempt, run) is True

    for field in (
        "fill_broker_order_id",
        "fill_transaction_id",
        "fill_trade_id",
        "fill_signed_units",
        "fill_price",
        "fill_executed_at",
        "fill_actual_initial_risk",
        "last_reconciliation_run_id",
        "last_reconciled_at",
    ):
        missing = _history_attempt(
            "FILLED_PROTECTION_INCOMPLETE",
            "LIFECYCLE_ADVANCED",
            complete_fill=True,
        )
        setattr(missing, field, None)
        assert is_new_session_safe_attempt(missing, run) is False


@pytest.mark.parametrize(
    "run_changes",
    [
        {"status": "PROVEN"},
        {"projection_version_applied": None},
        {"projection_version_applied": 2},
        {"resulting_execution_outcome": "FILLED_PROTECTED"},
        {"prior_execution_outcome": "UNKNOWN"},
        {"completed_at": NOW.replace(minute=13)},
    ],
)
def test_lifecycle_advanced_incomplete_fill_rejects_contradictory_run_evidence(
    run_changes: dict[str, object],
) -> None:
    attempt = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        complete_fill=True,
    )
    run = _history_run(attempt, **run_changes)

    assert is_new_session_safe_attempt(attempt, run) is False


@pytest.mark.parametrize(
    "run_changes",
    [
        {"read_count": 0},
        {"read_count": None},
        {"read_count": "1"},
        {"read_count": 9},
        {"read_budget": 0},
        {"read_budget": None},
        {"read_budget": True},
        {"read_budget": 9},
        {"non_atomic_read_set": None},
        {"non_atomic_read_set": 1},
        {"non_atomic_read_set": "false"},
        {"non_atomic_read_set": True},
        {"read_count": 2, "non_atomic_read_set": False},
        {"finding_codes": None},
        {"finding_codes": "TRADE_LIFECYCLE_ADVANCED"},
        {"finding_codes": []},
        {"finding_codes": ["CONFLICT"]},
        {"finding_codes": ["UNRESOLVED"]},
        {"finding_codes": ["TRADE_LIFECYCLE_ADVANCED", "CONFLICT"]},
        {"finding_codes": ["TRADE_LIFECYCLE_ADVANCED", "ENTRY_REJECTED"]},
        {"finding_codes": ["TRADE_LIFECYCLE_ADVANCED", "ENTRY_CANCELLED"]},
        {"finding_codes": ["NOT_A_FINDING"]},
        {"diagnostic_summary": None},
        {"diagnostic_summary": "RECONCILIATION_CONFLICT"},
        {"diagnostic_summary": []},
    ],
)
def test_lifecycle_advanced_incomplete_fill_rejects_malformed_run_evidence(
    run_changes: dict[str, object],
) -> None:
    attempt = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        complete_fill=True,
    )
    run = _history_run(attempt, **run_changes)

    assert is_new_session_safe_attempt(attempt, run) is False


def test_lifecycle_advanced_incomplete_fill_rejects_durable_block_code() -> None:
    attempt = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        complete_fill=True,
    )
    attempt.reconciliation_block_code = "RECONCILIATION_CONFLICT"

    assert is_new_session_safe_attempt(attempt, _history_run(attempt)) is False


@pytest.mark.parametrize(
    ("read_count", "non_atomic_read_set"),
    [(1, False), (2, True)],
)
def test_lifecycle_advanced_incomplete_fill_accepts_provider_read_set_metadata(
    read_count: int, non_atomic_read_set: bool
) -> None:
    attempt = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        complete_fill=True,
    )
    run = _history_run(
        attempt,
        read_count=read_count,
        non_atomic_read_set=non_atomic_read_set,
    )

    assert is_new_session_safe_attempt(attempt, run) is True


def test_new_session_semantics_do_not_depend_on_the_incident_attempt_uuid() -> None:
    dogfood = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        attempt_id=HISTORY_ATTEMPT_ID,
        complete_fill=True,
    )
    synthetic = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        attempt_id=UUID("99999999-9999-9999-9999-999999999999"),
        complete_fill=True,
    )

    assert is_new_session_safe_attempt(dogfood, _history_run(dogfood)) is True
    assert is_new_session_safe_attempt(synthetic, _history_run(synthetic)) is True


class _HistoryResult:
    def __init__(self, rows: list[tuple[object, object | None]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, object | None]]:
        return self.rows


class _HistorySession:
    def __init__(self, rows: list[tuple[object, object | None]]) -> None:
        self.rows = rows

    def execute(self, _statement: object) -> _HistoryResult:
        return _HistoryResult(self.rows)


def test_new_session_history_is_account_wide_and_any_blocker_wins() -> None:
    repository = PaperRuntimeRepository()
    safe = _history_attempt("FILLED_PROTECTED", "NOT_RUN")
    ended = _history_attempt(
        "FILLED_PROTECTION_INCOMPLETE",
        "LIFECYCLE_ADVANCED",
        attempt_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        complete_fill=True,
    )
    blocker = _history_attempt("UNKNOWN", "LIFECYCLE_ADVANCED")

    assert (
        repository.has_new_session_blocker(
            _HistorySession([(safe, None), (ended, _history_run(ended))]),
            "001-002-003-004",
        )
        is False
    )
    assert (
        repository.has_new_session_blocker(
            _HistorySession(
                [(safe, None), (ended, _history_run(ended)), (blocker, None)]
            ),
            "001-002-003-004",
        )
        is True
    )


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
    monkeypatch.setattr(
        service, "_new_session_history_blocker_exists", lambda *_args: False
    )
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
        ("FILLED_PROTECTION_INCOMPLETE", "LIFECYCLE_ADVANCED", True),
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
        def has_new_session_blocker(self, _session, _account_id):
            attempt = _history_attempt(execution_outcome, reconciliation_status)
            return not is_new_session_safe_attempt(attempt, None)

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
