# pyright: reportPrivateUsage=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false

"""Cross-seam deterministic evidence for the PAPER 06 completion boundary."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from backend.domain import (
    Action,
    Direction,
    EntryPolicy,
    FinancialPositionState,
    PriceComponent,
    Rationale,
    StopProposal,
    StrategyDecision,
    StrategyEvaluation,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    StrategyVersion,
    TargetProposal,
    ValidatedParameterPayload,
)
from backend.integrations.oanda import (
    OandaPracticeAccountProperties,
    OandaPracticeEntryMutation,
    OandaPracticeProtectionCompletion,
)
from backend.integrations.oanda.mutation_request import OandaPracticeMutationRequester
from backend.paper import PaperExecutionOutcome, PaperExecutionResult
from backend.paper.durable_execution import (
    PaperDurableExecutionApplication,
    PaperDurableExecutionPersistenceError,
    PaperDurableExecutionPreparation,
)
from backend.paper.persistence_contracts import PaperStrategyEvaluationReceipt
from backend.risk import RiskConfig
from backend.runtime import PaperRuntimeOwnerLost
from backend.tests.paper.test_durable_execution import (
    Repository,
    Session,
    SessionFactory,
    TradeReader,
    ValueReader,
    receipt,
)
from backend.tests.paper.test_execution_composition import (
    ACCOUNT_ID,
    ATTEMPT_ID,
    INSTRUMENT,
    _entry_payload,
    _target_payload,
    account_snapshot,
    pricing,
)


def _operation(
    repository: Repository,
    handler: Any,
    events: list[str],
) -> tuple[PaperDurableExecutionApplication, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(recording_handler)
    entry_requester = OandaPracticeMutationRequester(
        SecretStr("unit-credential"), transport=transport
    )
    protection_requester = OandaPracticeMutationRequester(
        SecretStr("unit-credential"), transport=transport
    )
    operation = PaperDurableExecutionApplication(
        repository=repository,  # type: ignore[arg-type]
        session_factory=SessionFactory(events),  # type: ignore[arg-type]
        account_properties_reader=ValueReader(
            OandaPracticeAccountProperties(ACCOUNT_ID, None), events, "properties"
        ),
        execution_account_reader=ValueReader(account_snapshot(), events, "account"),
        execution_instrument_reader=ValueReader(INSTRUMENT, events, "instrument"),
        pricing_reader=ValueReader(pricing(), events, "pricing"),
        entry_mutation=OandaPracticeEntryMutation(entry_requester),
        protection_completion=OandaPracticeProtectionCompletion(
            protection_requester, TradeReader(events)
        ),
    )
    return operation, requests


def _claim(
    operation: PaperDurableExecutionApplication,
    repository: Repository,
    events: list[str],
) -> PaperDurableExecutionPreparation:
    prepared = operation.prepare_entry_claim(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    assert isinstance(prepared, PaperDurableExecutionPreparation)
    claim = operation.persist_entry_claim(Session(events), prepared)  # type: ignore[arg-type]
    assert claim.claim_id == repository.entry_claim_id
    events.append("caller-commit")
    return prepared


def _filled_or_rejected(request: httpx.Request) -> httpx.Response:
    if request.method == "POST":
        return httpx.Response(201, json=_entry_payload(fill=True))
    assert request.method == "PUT"
    return httpx.Response(200, json=_target_payload())


def test_stop_during_entry_network_preserves_one_authorized_protection_chain() -> None:
    events: list[str] = []
    repository = Repository(events)
    stop_requested = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal stop_requested
        if request.method == "POST":
            # The durable ENTRY claim is already committed.  This models STOP
            # linearizing while the already-authorized POST is in flight.
            stop_requested = True
            events.append("entry-post")
        else:
            events.append("take-profit-put")
        return _filled_or_rejected(request)

    operation, requests = _operation(repository, handler, events)
    prepared = _claim(operation, repository, events)
    claimed: list[str] = []

    result = operation.submit_claimed_entry(
        prepared,
        entry_claim_id=repository.entry_claim_id,
        mutation_guard=lambda: None,
        take_profit_claimed_callback=lambda _claim_id: claimed.append("TP"),
    )

    assert stop_requested is True
    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert [request.method for request in requests] == ["POST", "PUT"]
    assert claimed == ["TP"]
    assert events.index("caller-commit") < events.index("entry-post")


def test_owner_loss_after_entry_claim_before_network_never_posts() -> None:
    events: list[str] = []
    repository = Repository(events)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    prepared = _claim(operation, repository, events)

    with pytest.raises(PaperRuntimeOwnerLost):
        operation.submit_claimed_entry(
            prepared,
            entry_claim_id=repository.entry_claim_id,
            mutation_guard=lambda: (_ for _ in ()).throw(
                PaperRuntimeOwnerLost("owner lost before entry dispatch")
            ),
        )

    assert requests == []


def test_owner_loss_after_fill_before_dependent_claim_is_read_only_on_restart() -> None:
    events: list[str] = []
    repository = Repository(events)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    prepared = _claim(operation, repository, events)
    guard_calls = 0

    def owner_guard() -> None:
        nonlocal guard_calls
        guard_calls += 1
        if guard_calls == 2:
            raise PaperRuntimeOwnerLost("owner lost before dependent claim")

    result = operation.submit_claimed_entry(
        prepared,
        entry_claim_id=repository.entry_claim_id,
        mutation_guard=owner_guard,
    )
    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert [request.method for request in requests] == ["POST"]
    assert "take-profit-claim" not in events

    restarted, _ = _operation(repository, _filled_or_rejected, events)
    replay = restarted.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    assert isinstance(replay, PaperExecutionResult)
    assert replay.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert [request.method for request in requests] == ["POST"]


def test_owner_loss_after_committed_take_profit_claim_never_puts() -> None:
    events: list[str] = []
    repository = Repository(events)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    prepared = _claim(operation, repository, events)
    guard_calls = 0

    def owner_guard() -> None:
        nonlocal guard_calls
        guard_calls += 1
        if guard_calls == 3:
            raise PaperRuntimeOwnerLost("owner lost after Take Profit claim")

    claimed: list[str] = []
    result = operation.submit_claimed_entry(
        prepared,
        entry_claim_id=repository.entry_claim_id,
        mutation_guard=owner_guard,
        take_profit_claimed_callback=lambda _claim_id: claimed.append("TP"),
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert [request.method for request in requests] == ["POST"]
    assert events.count("take-profit-claim") == 1
    assert claimed == ["TP"]
    assert guard_calls == 3


def test_restart_after_committed_entry_claim_never_posts_or_creates_a_claim() -> None:
    events: list[str] = []
    repository = Repository(events)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    _claim(operation, repository, events)

    restarted, _ = _operation(repository, _filled_or_rejected, events)
    result = restarted.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )

    assert result.outcome is PaperExecutionOutcome.UNKNOWN
    assert requests == []
    assert events.count("entry-claim") == 1


class _FailingProjectionRepository(Repository):
    def __init__(self, events: list[str], *, fail_on_call: int) -> None:
        super().__init__(events)
        self._apply_calls = 0
        self._fail_on_call = fail_on_call

    def apply_result(self, *args: Any, **kwargs: Any) -> None:
        self._apply_calls += 1
        if self._apply_calls == self._fail_on_call:
            raise RuntimeError("simulated process loss at result persistence")
        super().apply_result(*args, **kwargs)


def test_restart_after_entry_post_before_result_persistence_is_read_only() -> None:
    events: list[str] = []
    repository = _FailingProjectionRepository(events, fail_on_call=1)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    prepared = _claim(operation, repository, events)

    with pytest.raises(PaperDurableExecutionPersistenceError):
        operation.submit_claimed_entry(
            prepared, entry_claim_id=repository.entry_claim_id
        )

    assert [request.method for request in requests] == ["POST"]
    restarted, _ = _operation(repository, _filled_or_rejected, events)
    replay = restarted.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    assert replay.outcome is PaperExecutionOutcome.UNKNOWN
    assert [request.method for request in requests] == ["POST"]


def test_process_loss_after_dependent_claim_before_put_never_retries_put() -> None:
    events: list[str] = []
    repository = Repository(events)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    prepared = _claim(operation, repository, events)

    def process_loss_after_claim(_claim_id: Any) -> None:
        raise RuntimeError("simulated process loss after TP claim")

    result = operation.submit_claimed_entry(
        prepared,
        entry_claim_id=repository.entry_claim_id,
        take_profit_claimed_callback=process_loss_after_claim,
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert [request.method for request in requests] == ["POST"]
    assert events.count("take-profit-claim") == 1

    restarted, _ = _operation(repository, _filled_or_rejected, events)
    replay = restarted.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    assert isinstance(replay, PaperExecutionResult)
    assert replay.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert [request.method for request in requests] == ["POST"]


def test_process_loss_after_put_before_final_persistence_never_retries_put() -> None:
    events: list[str] = []
    repository = _FailingProjectionRepository(events, fail_on_call=2)
    operation, requests = _operation(repository, _filled_or_rejected, events)
    prepared = _claim(operation, repository, events)

    with pytest.raises(PaperDurableExecutionPersistenceError):
        operation.submit_claimed_entry(
            prepared, entry_claim_id=repository.entry_claim_id
        )

    assert [request.method for request in requests] == ["POST", "PUT"]
    restarted, _ = _operation(repository, _filled_or_rejected, events)
    replay = restarted.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    assert isinstance(replay, PaperExecutionResult)
    assert replay.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert [request.method for request in requests] == ["POST", "PUT"]


def _runtime_receipt(
    action: Action,
    frontier: Any,
    *,
    entry_policy: EntryPolicy = EntryPolicy.IMMEDIATE,
) -> Any:
    version = StrategyVersion(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        strategy_key="runtime_fixture",
        version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="runtime_fixture.v1",
        parameter_schema=(),
    )
    parameters = ValidatedParameterPayload.from_mapping((), {})
    if action in {Action.OPEN_LONG, Action.OPEN_SHORT}:
        direction = Direction.LONG if action is Action.OPEN_LONG else Direction.SHORT
        decision = StrategyDecision(
            action,
            Rationale("UNSUPPORTED_RUNTIME_ACTION"),
            direction=direction,
            decision_time=frontier.current_frontier,
            stop=StopProposal(
                Decimal("1.09") if direction is Direction.LONG else Decimal("1.11"),
                direction,
            ),
            target=TargetProposal(),
            entry_policy=entry_policy,
            trigger_price=(
                Decimal("1.1") if entry_policy is EntryPolicy.PRICE_TRIGGERED else None
            ),
            trigger_price_basis=(
                PriceComponent.ASK
                if entry_policy is EntryPolicy.PRICE_TRIGGERED
                else None
            ),
            expiry_bars=(2 if entry_policy is EntryPolicy.PRICE_TRIGGERED else None),
        )
    else:
        decision = StrategyDecision(action, Rationale("UNSUPPORTED_RUNTIME_ACTION"))
    state = StrategyStateEnvelope(
        1,
        frontier.current_frontier,
        StrategyStatePayloadDocument.from_mapping("runtime_fixture.v1", 1, {}),
    )
    return PaperStrategyEvaluationReceipt.from_verified(
        version, parameters, StrategyEvaluation(decision, state)
    )


@pytest.mark.parametrize("expected", [Direction.LONG, Direction.SHORT])
def test_known_directional_exposure_advances_read_only_strategy_state(
    expected: Direction,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.tests.runtime.test_runtime_orchestration import (
        _tick_activation,
        _tick_frontier,
        _tick_observation,
        _tick_receipt,
        _tick_runtime,
        _TickAuthority,
    )

    frontier = _tick_frontier()
    authority = _TickAuthority(_tick_receipt(Action.NO_ACTION, frontier))
    position = (
        FinancialPositionState.LONG
        if expected is Direction.LONG
        else FinancialPositionState.SHORT
    )
    observed: list[FinancialPositionState] = []
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(position),
        durable=None,
        monkeypatch=monkeypatch,
    )
    runtime._read_observation = lambda *_args: (
        observed.append(position) or _tick_observation(position)
    )

    result = runtime.tick()

    assert result.outcome.value == "EVALUATED"
    assert authority.evaluations == 1
    assert authority.persisted[0][0].value == "NO_ACTION"
    assert observed == [position]


@pytest.mark.parametrize(
    ("action", "entry_policy"),
    [
        (Action.CLOSE_POSITION, EntryPolicy.IMMEDIATE),
        (Action.UPDATE_PROTECTION, EntryPolicy.IMMEDIATE),
        (Action.OPEN_LONG, EntryPolicy.PRICE_TRIGGERED),
    ],
)
def test_unsupported_strategy_action_blocks_without_reaching_p05(
    action: Action,
    entry_policy: EntryPolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.tests.runtime.test_runtime_orchestration import (
        _tick_activation,
        _tick_frontier,
        _tick_observation,
        _tick_runtime,
        _TickAuthority,
    )

    frontier = _tick_frontier()
    authority = _TickAuthority(
        _runtime_receipt(action, frontier, entry_policy=entry_policy)
    )
    runtime = _tick_runtime(
        _tick_activation(),
        authority,
        observation=_tick_observation(),
        durable=None,
        monkeypatch=monkeypatch,
    )
    blocked_evidence: list[str] = []
    runtime._persist_blocked_evaluation = lambda *args: blocked_evidence.append(
        "evidence"
    )

    result = runtime.tick()

    assert result.outcome.value == "BLOCKED"
    assert result.reason_code == "UNSUPPORTED_STRATEGY_ACTION"
    assert blocked_evidence == ["evidence"]
