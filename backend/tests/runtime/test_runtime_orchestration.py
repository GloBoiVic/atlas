# pyright: reportPrivateUsage=false, reportAttributeAccessIssue=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportIndexIssue=false

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from backend.domain import (
    Action,
    Bar,
    Direction,
    FinancialPositionState,
    Instrument,
    PriceComponent,
    Rationale,
    StopProposal,
    StrategyDecision,
    StrategyEvaluation,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    StrategyVersion,
    TargetProposal,
    Timeframe,
    ValidatedParameterPayload,
)
from backend.integrations.oanda import OandaPracticeAccountPropertiesReader
from backend.paper.current_analytical_frontier import CurrentAnalyticalFrontier
from backend.paper.execution import PaperExecutionOutcome
from backend.paper.persistence_contracts import PaperStrategyEvaluationReceipt
from backend.persistence.models import PaperExecutionAttemptModel
from backend.persistence.runtime_repository import (
    InvalidPaperRuntimeTransition,
    PaperRuntimeOwnerLost,
    is_unsafe_paper_attempt,
)
from backend.runtime import (
    PaperRuntimeAccountObservation,
    PaperRuntimeActivation,
    PaperRuntimeCycleStatus,
    PaperRuntimeFrontierDuplicate,
    PaperRuntimeLifecycleState,
    PaperRuntimeOrchestrator,
    PaperRuntimeStateAuthorityError,
    PaperRuntimeTickOutcome,
    PaperRuntimeTickResult,
    PaperRuntimeUnsupportedStrategyAction,
    runtime_parameter_fingerprint,
)

NOW = datetime(2026, 9, 2, 12, 15, tzinfo=UTC)
ACTIVATION_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")
CYCLE_ID = UUID("33333333-3333-3333-3333-333333333333")
CLAIM_ID = UUID("44444444-4444-4444-4444-444444444444")
ACCOUNT_ID = "001-002-003-004"


class _Session:
    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self) -> _Session:
        return self


class _Repository:
    def get_active_activation(
        self, _session: _Session, *, for_update: bool = False
    ) -> None:
        del for_update
        return None


class _Owner:
    acquired = True
    owner_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    owner_generation = 1

    def try_acquire(self) -> object:
        return object()

    def assert_current(self, _session: object) -> object:
        return object()


class _RecoveryRepository:
    def __init__(self) -> None:
        self.statuses: list[PaperRuntimeCycleStatus] = []

    def transition_cycle(
        self,
        _session: object,
        _cycle_id: UUID,
        status: PaperRuntimeCycleStatus,
        **_kwargs: object,
    ) -> object:
        self.statuses.append(status)
        return object()


class _Source:
    pass


class _AccountReader:
    def read(self) -> object:
        raise AssertionError("idle startup must not read the account")


class _StartupOwner:
    acquired = True
    owner_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    owner_generation = 1

    def try_acquire(self) -> object:
        return object()

    def attach_activation(self, _session: object, _activation_id: UUID) -> None:
        return None

    def assert_current(self, _session: object, **_kwargs: object) -> None:
        return None

    def close(self) -> None:
        return None


class _StartupRepository:
    def __init__(self) -> None:
        self.transitions: list[PaperRuntimeLifecycleState] = []

    def get_active_activation(
        self, _session: object, *, for_update: bool = False
    ) -> SimpleNamespace:
        del for_update
        return SimpleNamespace(
            activation_id=ACTIVATION_ID,
            lifecycle_state=PaperRuntimeLifecycleState.REQUESTED.value,
        )

    def transition_activation(
        self,
        _session: object,
        _activation_id: UUID,
        lifecycle_state: PaperRuntimeLifecycleState,
        **_kwargs: object,
    ) -> object:
        self.transitions.append(lifecycle_state)
        return object()


def _startup_runtime(
    capability_reader: object,
    *,
    events: list[str],
) -> PaperRuntimeOrchestrator:
    activation = _tick_activation(PaperRuntimeLifecycleState.STARTING)
    repository = _StartupRepository()
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._owner = _StartupOwner()
    runtime._session_factory = _Session
    runtime._repository = repository
    runtime._capability_reader = capability_reader
    runtime._account_reader = _AccountReader()
    runtime._activation_id = None
    runtime._started = False
    runtime._set_owner_phase = lambda _phase: None
    runtime._set_operational_phase = lambda *args, **kwargs: events.append(
        f"operational:{args[1].value}:{args[2]}"
    )
    runtime._recover_interrupted = lambda _activation_id: False
    runtime._activation_for_id = lambda _session, _activation_id: activation
    runtime._validate_strategy_registry = lambda *_args: None
    runtime._read_observation = lambda *_args: (
        events.append("account") or _tick_observation()
    )
    runtime._block = lambda *_args, **_kwargs: PaperRuntimeTickResult(
        PaperRuntimeTickOutcome.BLOCKED
    )
    return runtime


class _StopEvent:
    def __init__(self) -> None:
        self.waited: list[float] = []
        self._set = False

    def is_set(self) -> bool:
        return self._set

    def wait(self, seconds: float) -> None:
        self.waited.append(seconds)
        self._set = True


def test_startup_without_activation_is_idle_and_does_not_read_provider() -> None:
    reader = _AccountReader()
    runtime = PaperRuntimeOrchestrator(
        owner=_Owner(),  # type: ignore[arg-type]
        session_factory=_Session,  # type: ignore[arg-type]
        strategy_registry=object(),  # type: ignore[arg-type]
        analytical_source=_Source(),  # type: ignore[arg-type]
        account_reader=reader,
        capability_reader=reader,  # type: ignore[arg-type]
        runtime_repository=_Repository(),  # type: ignore[arg-type]
    )

    result = runtime.startup()

    assert result.outcome is PaperRuntimeTickOutcome.IDLE
    assert result.owner_acquired is True
    assert runtime.activation_id is None


def test_startup_proves_non_mt4_capability_before_running() -> None:
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append("capability")
        return httpx.Response(200, json={"accounts": [{"id": ACCOUNT_ID}]})

    capability_reader = OandaPracticeAccountPropertiesReader(
        SecretStr("unit-credential"),
        ACCOUNT_ID,
        transport=httpx.MockTransport(handler),
    )
    runtime = _startup_runtime(capability_reader, events=events)

    result = runtime.startup()

    assert result.outcome is PaperRuntimeTickOutcome.STARTING
    assert result.lifecycle_state is PaperRuntimeLifecycleState.RUNNING
    assert result.reason_code is None
    assert runtime.running is True
    assert events == ["capability", "account"]


@pytest.mark.parametrize(
    "payload",
    [
        {"accounts": [{"id": ACCOUNT_ID, "mt4AccountID": 12345}]},
        {"accounts": []},
        {"accounts": [{"id": "001-002-003-005"}]},
        {"accounts": [{"id": "malformed"}]},
    ],
    ids=["mt4", "missing", "mismatched", "invalid"],
)
def test_startup_blocks_without_valid_non_mt4_capability(
    payload: dict[str, object],
) -> None:
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append("capability")
        return httpx.Response(200, json=payload)

    capability_reader = OandaPracticeAccountPropertiesReader(
        SecretStr("unit-credential"),
        ACCOUNT_ID,
        transport=httpx.MockTransport(handler),
    )
    runtime = _startup_runtime(capability_reader, events=events)

    result = runtime.startup()

    assert result.outcome is PaperRuntimeTickOutcome.BLOCKED
    assert result.lifecycle_state is PaperRuntimeLifecycleState.BLOCKED
    assert result.reason_code == "STARTUP_CAPABILITY_INVALID"
    assert runtime.running is False
    assert events == ["capability"]


def test_startup_waits_on_temporary_capability_read_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append("capability")
        return httpx.Response(503)

    monkeypatch.setattr("backend.integrations.oanda.request.sleep", lambda _: None)
    capability_reader = OandaPracticeAccountPropertiesReader(
        SecretStr("unit-credential"),
        ACCOUNT_ID,
        transport=httpx.MockTransport(handler),
    )
    runtime = _startup_runtime(capability_reader, events=events)

    result = runtime.startup()

    assert result.outcome is PaperRuntimeTickOutcome.STARTING
    assert result.lifecycle_state is PaperRuntimeLifecycleState.STARTING
    assert result.reason_code == "STARTUP_READ_UNAVAILABLE"
    assert runtime.running is False
    assert events == [
        "capability",
        "capability",
        "capability",
        "operational:WAITING_PROVIDER:STARTUP_READ_UNAVAILABLE",
    ]


def test_run_uses_fixed_wait_and_does_not_catch_up_missed_frontiers() -> None:
    runtime = object.__new__(PaperRuntimeOrchestrator)
    calls: list[str] = []
    event = _StopEvent()

    def startup() -> object:
        calls.append("startup")
        return object()

    def tick() -> PaperRuntimeTickResult:
        calls.append("tick")
        return PaperRuntimeTickResult(PaperRuntimeTickOutcome.WAITING_FRONTIER)

    def close() -> None:
        calls.append("close")

    runtime.startup = startup  # type: ignore[method-assign]
    runtime.tick = tick  # type: ignore[method-assign]
    runtime.close = close  # type: ignore[method-assign]

    assert runtime.run(event) == 0
    assert calls == ["startup", "tick", "close"]
    assert event.waited == [15.0]


def test_tick_result_serialization_contains_only_bounded_runtime_evidence() -> None:
    result = PaperRuntimeTickResult(
        PaperRuntimeTickOutcome.EXECUTED,
        activation_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        cycle_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        reason_code="FILLED_PROTECTED",
    )

    assert result.to_json() == {
        "outcome": "EXECUTED",
        "activation_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "cycle_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "decision": None,
        "execution_outcome": None,
        "reason_code": "FILLED_PROTECTED",
    }


def test_recovery_closes_existing_claim_without_replaying_a_mutation() -> None:
    repository = _RecoveryRepository()
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._session_factory = _Session  # type: ignore[attr-defined]
    runtime._owner = _Owner()  # type: ignore[attr-defined]
    runtime._repository = repository  # type: ignore[attr-defined]

    runtime._complete_recovered_cycle(  # type: ignore[attr-defined]
        UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        status=PaperRuntimeCycleStatus.ENTRY_CLAIMED,
        filled=True,
    )

    assert repository.statuses == [
        PaperRuntimeCycleStatus.ENTRY_RESOLVED,
        PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
        PaperRuntimeCycleStatus.COMPLETE,
    ]


def _tick_activation(
    lifecycle_state: PaperRuntimeLifecycleState = PaperRuntimeLifecycleState.RUNNING,
) -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    return PaperRuntimeActivation(
        activation_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        strategy_key="runtime_fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="runtime_fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=Decimal("0.01"),
        provider_account_id="001-002-003-004",
        requested_at=NOW,
        lifecycle_state=lifecycle_state,
    )


def _tick_frontier() -> CurrentAnalyticalFrontier:
    start = NOW - timedelta(minutes=15)
    prior = start - timedelta(minutes=15)
    bars = (
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            prior,
            start,
            Decimal("1.1"),
            Decimal("1.11"),
            Decimal("1.09"),
            Decimal("1.1"),
        ),
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            start,
            NOW,
            Decimal("1.1"),
            Decimal("1.11"),
            Decimal("1.09"),
            Decimal("1.1"),
        ),
    )
    return CurrentAnalyticalFrontier(
        acquisition_cutoff=NOW,
        requested_start=prior,
        requested_end=NOW,
        bars=bars,
        current_bar=bars[-1],
        eligible_windows=((prior, start), (start, NOW)),
        previous_frontier=start,
    )


def _tick_observation(
    state: FinancialPositionState = FinancialPositionState.FLAT,
    *,
    pending_orders: int = 0,
) -> PaperRuntimeAccountObservation:
    exposed = state is not FinancialPositionState.FLAT
    return PaperRuntimeAccountObservation(
        provider_account_id="001-002-003-004",
        account_transaction_id="42",
        observed_at=NOW,
        financial_position_state=state,
        open_trade_count=1 if exposed else 0,
        open_position_count=1 if exposed else 0,
        pending_order_count=pending_orders,
    )


def _tick_receipt(
    action: Action,
    frontier: CurrentAnalyticalFrontier,
) -> PaperStrategyEvaluationReceipt:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    version = StrategyVersion(
        VERSION_ID,
        "runtime_fixture",
        1,
        "a" * 64,
        "runtime_fixture.v1",
        (),
    )
    decision = (
        StrategyDecision(Action.NO_ACTION, Rationale("NO_ENTRY"))
        if action is Action.NO_ACTION
        else StrategyDecision(
            action,
            Rationale("FIXTURE_OPEN"),
            direction=(
                Direction.LONG if action is Action.OPEN_LONG else Direction.SHORT
            ),
            decision_time=NOW,
            stop=StopProposal(
                Decimal("1.09"),
                Direction.LONG if action is Action.OPEN_LONG else Direction.SHORT,
            ),
            target=TargetProposal(),
        )
    )
    state_after = StrategyStateEnvelope(
        1,
        frontier.current_frontier,
        StrategyStatePayloadDocument.from_mapping("runtime_fixture.v1", 1, {}),
    )
    return PaperStrategyEvaluationReceipt.from_verified(
        version,
        parameters,
        StrategyEvaluation(decision, state_after),
    )


class _TickSession:
    def __enter__(self) -> _TickSession:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self) -> _TickSession:
        return self


class _TickOwner:
    acquired = True
    owner_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    owner_generation = 1

    def assert_current(self, _session: object, **_kwargs: object) -> None:
        return None


class _TickRepository:
    def get_activation(self, *_args: object, **_kwargs: object) -> object:
        return object()

    def transition_cycle(self, *_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(cycle_id=CYCLE_ID)


class _AttemptSafetyRepository(_TickRepository):
    def __init__(self) -> None:
        self.attempt_present = False
        self.execution_outcome: str | None = None
        self.reconciliation_status = "NOT_RUN"

    def has_unsafe_attempt(self, _session: object, _account_id: str) -> bool:
        return self.attempt_present and is_unsafe_paper_attempt(
            self.execution_outcome, self.reconciliation_status
        )

    def has_new_session_blocker(self, _session: object, _account_id: str) -> bool:
        return self.attempt_present and is_unsafe_paper_attempt(
            self.execution_outcome, self.reconciliation_status
        )

    def record_outcome(self, outcome: PaperExecutionOutcome) -> None:
        self.attempt_present = True
        self.execution_outcome = outcome.value


class _SequenceAccountReader:
    def __init__(self, observations: list[PaperRuntimeAccountObservation]) -> None:
        self.observations = iter(observations)
        self.read_calls = 0

    def read(self) -> object:
        self.read_calls += 1
        return next(self.observations)


class _TickAuthority:
    def __init__(self, receipt: PaperStrategyEvaluationReceipt) -> None:
        self.receipt = receipt
        self.reservations = 0
        self.evaluations = 0
        self.persisted: list[tuple[PaperRuntimeCycleStatus, str | None]] = []

    def reserve_cycle(self, *_args: object, **_kwargs: object) -> object:
        self.reservations += 1
        return SimpleNamespace(cycle_id=CYCLE_ID)

    def evaluate_cycle(
        self, *_args: object, **_kwargs: object
    ) -> PaperStrategyEvaluationReceipt:
        self.evaluations += 1
        return self.receipt

    def persist_evaluation(
        self,
        _session: object,
        _cycle_id: UUID,
        _activation: PaperRuntimeActivation,
        _receipt: PaperStrategyEvaluationReceipt,
        *,
        cycle_status: PaperRuntimeCycleStatus,
        reason_code: str | None = None,
        **_kwargs: object,
    ) -> object:
        self.persisted.append((cycle_status, reason_code))
        return object()


class _TickDurableExecution:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.prepare_calls = 0
        self.submit_calls = 0

    def prepare_entry_claim(self, *_args: object, **_kwargs: object) -> object:
        self.prepare_calls += 1
        return object()

    def submit_claimed_entry(
        self,
        _prepared: object,
        *,
        entry_claim_id: UUID,
        mutation_guard: Callable[[], None] | None = None,
        **_kwargs: object,
    ) -> object:
        assert entry_claim_id == CLAIM_ID
        self.submit_calls += 1
        if mutation_guard is not None:
            mutation_guard()
        callback = _kwargs.get("take_profit_claimed_callback")
        if self.outcome is PaperExecutionOutcome.FILLED_PROTECTED and callable(
            callback
        ):
            callback(CLAIM_ID)
        return SimpleNamespace(outcome=self.outcome)


def _tick_runtime(
    activation: PaperRuntimeActivation,
    authority: _TickAuthority,
    *,
    observation: PaperRuntimeAccountObservation,
    durable: object | None = None,
    monkeypatch: pytest.MonkeyPatch,
) -> PaperRuntimeOrchestrator:
    monkeypatch.setattr(
        "backend.runtime.orchestration._activation_from_row",
        lambda _session, _row: activation,
    )
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._owner = _TickOwner()
    runtime._session_factory = _TickSession
    runtime._repository = _TickRepository()
    runtime._cycle_authority = authority
    runtime._strategy_repository = object()
    runtime._strategy_registry = object()
    runtime._analytical_source = object()
    runtime._account_reader = object()
    runtime._durable_execution = durable
    runtime._reconciliation = None
    runtime._market_specification = object()
    runtime._risk_config_factory = lambda _activation: object()
    runtime._clock = lambda: NOW
    runtime._activation_id = activation.activation_id
    runtime._started = True
    runtime._current_activation = lambda: activation
    runtime._read_frontier = lambda _activation, _now: _tick_frontier()
    runtime._read_observation = lambda _session, _activation: observation
    runtime._heartbeat = lambda _phase: None
    runtime._set_operational_phase = lambda *_args, **_kwargs: None
    return runtime


def test_tick_evaluates_flat_and_known_open_exposure_without_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.EVALUATED
    assert authority.reservations == 1
    assert authority.evaluations == 1
    assert authority.persisted == [(PaperRuntimeCycleStatus.NO_ACTION, None)]

    open_authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    open_runtime = _tick_runtime(
        _tick_activation(),
        open_authority,
        observation=_tick_observation(FinancialPositionState.LONG),
        durable=None,
        monkeypatch=monkeypatch,
    )
    open_result = open_runtime.tick()
    assert open_result.outcome is PaperRuntimeTickOutcome.EVALUATED
    assert open_authority.persisted == [(PaperRuntimeCycleStatus.NO_ACTION, None)]


@pytest.mark.parametrize("outcome", ["REJECTED", "CANCELLED", "FILLED_PROTECTED"])
def test_terminal_not_run_outcome_reaches_fresh_account_observation(
    outcome: str,
) -> None:
    repository = _AttemptSafetyRepository()
    repository.record_outcome(PaperExecutionOutcome(outcome))
    reader = _SequenceAccountReader([_tick_observation(FinancialPositionState.LONG)])
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._repository = repository
    runtime._account_reader = reader

    observation = runtime._read_observation(  # type: ignore[attr-defined]
        _TickSession(), _tick_activation()
    )

    assert observation.financial_position_state is FinancialPositionState.LONG
    assert reader.read_calls == 1


def test_fresh_account_read_uses_new_session_history_rule() -> None:
    class FreshHistoryRepository(_AttemptSafetyRepository):
        def has_unsafe_attempt(self, _session: object, _account_id: str) -> bool:
            raise AssertionError("fresh account authority must not use strict recovery")

        def has_new_session_blocker(self, _session: object, _account_id: str) -> bool:
            return False

    repository = FreshHistoryRepository()
    reader = _SequenceAccountReader([_tick_observation()])
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._repository = repository
    runtime._account_reader = reader

    observation = runtime._read_observation(_TickSession(), _tick_activation())

    assert observation.financial_position_state is FinancialPositionState.FLAT
    assert reader.read_calls == 1


@pytest.mark.parametrize(
    ("outcome", "reconciliation_status"),
    [
        ("UNKNOWN", "NOT_RUN"),
        ("FILLED_PROTECTION_INCOMPLETE", "NOT_RUN"),
        ("REJECTED", "UNRESOLVED"),
        ("REJECTED", "CONFLICT"),
        (None, "NOT_RUN"),
        ("MALFORMED", "NOT_RUN"),
    ],
)
def test_unsafe_outcome_fences_account_observation(
    outcome: str | None, reconciliation_status: str
) -> None:
    repository = _AttemptSafetyRepository()
    repository.attempt_present = True
    repository.execution_outcome = outcome
    repository.reconciliation_status = reconciliation_status
    reader = _SequenceAccountReader([_tick_observation()])
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._repository = repository
    runtime._account_reader = reader

    with pytest.raises(PaperRuntimeStateAuthorityError):
        runtime._read_observation(_TickSession(), _tick_activation())  # type: ignore[attr-defined]
    assert reader.read_calls == 0


def test_repeated_runtime_keeps_filled_history_separate_from_fresh_entry_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontiers = [_tick_frontier() for _ in range(4)]
    receipts = iter(
        (
            _tick_receipt(Action.OPEN_LONG, frontiers[0]),
            _tick_receipt(Action.NO_ACTION, frontiers[1]),
            _tick_receipt(Action.OPEN_LONG, frontiers[2]),
            _tick_receipt(Action.OPEN_LONG, frontiers[3]),
        )
    )
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontiers[0]))
    authority.evaluate_cycle = lambda *_args, **_kwargs: next(receipts)
    durable = _TickDurableExecution(PaperExecutionOutcome.FILLED_PROTECTED)
    repository = _AttemptSafetyRepository()
    reader = _SequenceAccountReader(
        [
            _tick_observation(),
            _tick_observation(FinancialPositionState.LONG),
            _tick_observation(FinancialPositionState.LONG),
            _tick_observation(),
        ]
    )
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    runtime._repository = repository
    runtime._account_reader = reader
    runtime._read_frontier = lambda _activation, _now: frontiers.pop(0)
    runtime._read_observation = lambda session, activation: (  # type: ignore[method-assign]
        PaperRuntimeOrchestrator._read_observation(runtime, session, activation)
    )
    runtime._persist_entry_claim = lambda *_args: CLAIM_ID
    runtime._mark_cycle_take_profit_claimed = lambda *_args: None
    runtime._resolve_cycle = lambda *_args, **_kwargs: None

    first = runtime.tick()
    repository.record_outcome(PaperExecutionOutcome.FILLED_PROTECTED)
    read_only = runtime.tick()
    blocked_entry = runtime.tick()
    later_entry = runtime.tick()

    assert first.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert read_only.outcome is PaperRuntimeTickOutcome.EVALUATED
    assert blocked_entry.outcome is PaperRuntimeTickOutcome.REFUSED
    assert blocked_entry.reason_code == "ENTRY_STATE_NOT_FLAT"
    assert later_entry.outcome is PaperRuntimeTickOutcome.EXECUTED
    assert durable.prepare_calls == 2
    assert durable.submit_calls == 2
    assert reader.read_calls == 4


def test_tick_opening_claim_is_persisted_before_the_one_shot_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(PaperExecutionOutcome.REJECTED)
    events: list[str] = []
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    runtime._persist_entry_claim = lambda *_args: events.append("claim") or CLAIM_ID
    runtime._resolve_cycle = lambda *_args, **_kwargs: events.append("resolve")
    original_submit = durable.submit_claimed_entry

    def submit(*args: object, **kwargs: object) -> object:
        events.append("dispatch")
        return original_submit(*args, **kwargs)

    durable.submit_claimed_entry = submit  # type: ignore[method-assign]

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.EXECUTED
    assert result.execution_outcome is PaperExecutionOutcome.REJECTED
    assert events == ["claim", "dispatch", "resolve"]
    assert durable.prepare_calls == 1
    assert durable.submit_calls == 1


def test_tick_filled_opening_records_dependent_claim_before_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(PaperExecutionOutcome.FILLED_PROTECTED)
    events: list[str] = []

    # Use the same harness as the rejection case, but record the cycle's
    # already-authorized dependent-protection transition.
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    runtime._persist_entry_claim = lambda *_args: events.append("claim") or CLAIM_ID
    runtime._mark_cycle_take_profit_claimed = lambda *_args: events.append("tp-claim")
    runtime._resolve_cycle = lambda *_args, **_kwargs: events.append("resolve")

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.EXECUTED
    assert result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert events == ["claim", "tp-claim", "resolve"]


def test_tick_pending_orders_refuse_opening_without_reaching_p05(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(PaperExecutionOutcome.REJECTED)
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(pending_orders=1),
        durable=durable,
        monkeypatch=monkeypatch,
    )

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.REFUSED
    assert result.reason_code == "ENTRY_PENDING_ORDERS"
    assert durable.prepare_calls == 0
    assert authority.persisted == [
        (PaperRuntimeCycleStatus.REFUSED, "ENTRY_PENDING_ORDERS")
    ]


def test_tick_transient_account_failure_retries_without_reserving_a_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )
    phases: list[object] = []
    runtime._read_observation = lambda *_args: (_ for _ in ()).throw(
        httpx.RequestError("temporary account read")
    )
    runtime._set_operational_phase = lambda *args, **_kwargs: phases.append(args[1])

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.WAITING_PROVIDER
    assert result.reason_code == "ACCOUNT_READ_UNAVAILABLE"
    assert authority.reservations == 0
    assert phases


def test_evaluation_persistence_failure_fences_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )
    runtime._persist_evaluation = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("database commit failed")
    )
    blocked: list[str] = []
    runtime._block_cycle_and_activation = lambda *_args: blocked.append("blocked")

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.BLOCKED
    assert result.reason_code == "EVALUATION_PERSISTENCE_UNCERTAIN"
    assert blocked == ["blocked"]


def test_tick_semantic_frontier_failure_blocks_instead_of_looking_like_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )
    runtime._read_frontier = lambda *_args: (_ for _ in ()).throw(
        PaperRuntimeStateAuthorityError("forming frontier")
    )
    runtime._block = lambda activation_id, reason_code, cycle_id=None: (
        PaperRuntimeTickResult(
            PaperRuntimeTickOutcome.BLOCKED,
            activation_id=activation_id,
            cycle_id=cycle_id,
            reason_code=reason_code,
        )
    )

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.BLOCKED
    assert result.reason_code == "FRONTIER_INVALID"
    assert authority.reservations == 0


def test_duplicate_frontier_waits_without_evaluating_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    authority.reserve_cycle = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        PaperRuntimeFrontierDuplicate("frontier already consumed")
    )
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.WAITING_FRONTIER
    assert result.reason_code == "FRONTIER_ALREADY_CONSUMED"
    assert authority.evaluations == 0


def test_stop_after_frontier_read_prevents_account_read_and_cycle_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    states = iter(
        (
            _tick_activation(),
            _tick_activation(PaperRuntimeLifecycleState.STOP_REQUESTED),
        )
    )
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )
    runtime._current_activation = lambda: next(states)
    events: list[str] = []
    runtime._finalize_stop = lambda _activation_id: events.append("stop")
    runtime._read_observation = lambda *_args: (_ for _ in ()).throw(
        AssertionError("STOP must fence the account read")
    )

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.STOPPED
    assert events == ["stop"]
    assert authority.reservations == 0


def test_stop_before_entry_claim_fences_the_claim_and_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(PaperExecutionOutcome.REJECTED)
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    states = iter(
        (
            _tick_activation(),
            _tick_activation(),
            _tick_activation(PaperRuntimeLifecycleState.STOP_REQUESTED),
        )
    )
    runtime._current_activation = lambda: next(states)
    runtime._persist_entry_claim = lambda *_args: (_ for _ in ()).throw(
        InvalidPaperRuntimeTransition("STOP won the ENTRY linearization")
    )
    events: list[str] = []
    runtime._finalize_stop = lambda _activation_id: events.append("stop")

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.STOPPED
    assert events == ["stop"]
    assert durable.submit_calls == 0


def test_owner_loss_before_entry_claim_and_before_dispatch_fences_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(PaperExecutionOutcome.REJECTED)
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    runtime._persist_entry_claim = lambda *_args: (_ for _ in ()).throw(
        PaperRuntimeOwnerLost("owner lost before claim")
    )
    claim_result = runtime.tick()
    assert claim_result.outcome is PaperRuntimeTickOutcome.OWNER_LOST
    assert durable.submit_calls == 0

    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(PaperExecutionOutcome.REJECTED)
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    runtime._persist_entry_claim = lambda *_args: CLAIM_ID
    runtime._assert_mutation_owner = lambda *_args: (_ for _ in ()).throw(
        PaperRuntimeOwnerLost("owner lost before broker dispatch")
    )

    dispatch_result = runtime.tick()

    assert dispatch_result.outcome is PaperRuntimeTickOutcome.OWNER_LOST
    assert durable.submit_calls == 1
    assert durable.outcome is PaperExecutionOutcome.REJECTED


def test_unsupported_nonflat_action_is_recorded_before_activation_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontier = _tick_frontier()
    receipt = _tick_receipt(Action.OPEN_LONG, frontier)
    authority = _TickAuthority(receipt)
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(FinancialPositionState.LONG),
        durable=None,
        monkeypatch=monkeypatch,
    )
    authority.evaluate_cycle = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        PaperRuntimeUnsupportedStrategyAction("non-flat action", receipt=receipt)
    )
    evidence: list[object] = []
    runtime._persist_blocked_evaluation = lambda *args: evidence.append(args)

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.BLOCKED
    assert result.reason_code == "UNSUPPORTED_STRATEGY_ACTION"
    assert len(evidence) == 1
    assert evidence[0][3] == "UNSUPPORTED_STRATEGY_ACTION"


@pytest.mark.parametrize(
    "outcome",
    [PaperExecutionOutcome.UNKNOWN, PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE],
)
def test_uncertain_execution_result_blocks_without_resolving_cycle(
    monkeypatch: pytest.MonkeyPatch,
    outcome: PaperExecutionOutcome,
) -> None:
    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.OPEN_LONG, frontier))
    durable = _TickDurableExecution(outcome)
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=durable,
        monkeypatch=monkeypatch,
    )
    runtime._persist_entry_claim = lambda *_args: CLAIM_ID
    blocked: list[str] = []
    runtime._block_cycle_and_activation = lambda *_args: blocked.append("blocked")

    result = runtime.tick()

    assert result.outcome is PaperRuntimeTickOutcome.BLOCKED
    assert result.reason_code == "EXECUTION_UNCERTAIN"
    assert blocked == ["blocked"]


class _RecoverySession:
    def __init__(self, attempt: object, *, take_profit_claimed: bool = False) -> None:
        self.attempt = attempt
        self.take_profit_claimed = take_profit_claimed

    def __enter__(self) -> _RecoverySession:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self) -> _RecoverySession:
        return self

    def get(self, model: object, _identity: UUID) -> object | None:
        return self.attempt if model is PaperExecutionAttemptModel else None

    def scalar(self, *_args: object, **_kwargs: object) -> object | None:
        return CLAIM_ID if self.take_profit_claimed else None


class _RecoveryCycleRepository(_RecoveryRepository):
    def __init__(self, cycle: object, attempt: object) -> None:
        super().__init__()
        self.cycle = cycle
        self.attempt = attempt

    def list_cycles(self, _session: object, _activation_id: UUID) -> list[object]:
        return [self.cycle]

    def get_cycle(self, _session: object, _cycle_id: UUID) -> object:
        return self.cycle


@pytest.mark.parametrize(
    ("outcome", "reconciliation_status", "take_profit_claimed", "safe"),
    [
        ("REJECTED", "NOT_RUN", False, True),
        ("CANCELLED", "NOT_RUN", False, True),
        ("REJECTED", "CONSISTENT", False, True),
        ("REJECTED", "UNRESOLVED", False, False),
        ("CANCELLED", "CONFLICT", False, False),
        ("FILLED_PROTECTED", "NOT_RUN", True, True),
        ("FILLED_PROTECTED", "CONSISTENT", True, True),
        ("FILLED_PROTECTED", "CONSISTENT", False, False),
        ("UNKNOWN", "NOT_RUN", False, False),
        ("FILLED_PROTECTION_INCOMPLETE", "NOT_RUN", False, False),
        (None, "NOT_RUN", False, False),
        ("MALFORMED", "NOT_RUN", False, False),
    ],
)
def test_restart_reconciles_claims_read_only_and_requires_definite_resolution(
    outcome: str,
    reconciliation_status: str,
    take_profit_claimed: bool,
    safe: bool,
) -> None:
    attempt_id = UUID("55555555-5555-5555-5555-555555555555")
    cycle = SimpleNamespace(
        cycle_id=CYCLE_ID,
        cycle_status=PaperRuntimeCycleStatus.ENTRY_CLAIMED.value,
        attempt_id=attempt_id,
    )
    attempt = SimpleNamespace(
        attempt_id=attempt_id,
        execution_outcome=outcome,
        reconciliation_status=reconciliation_status,
    )
    repository = _RecoveryCycleRepository(cycle, attempt)
    runtime = object.__new__(PaperRuntimeOrchestrator)
    runtime._session_factory = lambda: _RecoverySession(
        attempt, take_profit_claimed=take_profit_claimed
    )
    runtime._owner = _TickOwner()
    runtime._repository = repository
    runtime._reconciliation = MockReconciliation()
    runtime._set_operational_phase = lambda *_args, **_kwargs: None
    completed: list[object] = []
    blocked: list[object] = []
    runtime._complete_recovered_cycle = lambda *args, **kwargs: completed.append(
        (args, kwargs)
    )
    runtime._block = lambda *args, **kwargs: blocked.append((args, kwargs))
    runtime._mark_cycle_blocked_if_possible = lambda *args, **kwargs: None

    interrupted = runtime._recover_interrupted(ACTIVATION_ID)

    assert interrupted is (not safe)
    assert runtime._reconciliation.calls == [attempt_id]
    assert bool(completed) is safe
    assert bool(blocked) is (not safe)


class MockReconciliation:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    def reconcile(self, attempt_id: UUID, **_kwargs: object) -> object:
        self.calls.append(attempt_id)
        return object()
