from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from backend.domain import (
    StrategyEvaluation,
    StrategyState,
    StrategyVersion,
    ValidatedParameterPayload,
)
from backend.integrations.oanda import (
    OandaPracticeAccountProperties,
    OandaPracticeEntryMutation,
    OandaPracticeProtectionCompletion,
)
from backend.paper import (
    BrokerUncertainty,
    PaperBrokerObservation,
    PaperExecutionOutcome,
    PaperExecutionRefusal,
    PaperExecutionRefusalCode,
    PaperExecutionResult,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperStrategyEvaluationReceipt,
    ProtectionConfirmation,
    ProtectionLegStatus,
    TransactionProvenance,
)
from backend.paper.durable_execution import PaperDurableExecutionApplication
from backend.persistence.paper_execution_repository import DuplicateMutationClaim
from backend.risk import RiskConfig
from backend.tests.paper.test_execution_composition import (
    ACCOUNT_ID,
    ATTEMPT_ID,
    INSTRUMENT,
    account_snapshot,
    decision,
    pricing,
)

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)
VERSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class Session:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def commit(self) -> None:
        self._events.append("commit")

    def rollback(self) -> None:
        self._events.append("rollback")

    def close(self) -> None:
        pass


class SessionFactory:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def __call__(self) -> Session:
        return Session(self.events)


class Repository:
    def __init__(self, events: list[str], *, fail_entry_commit: bool = False) -> None:
        self.events = events
        self.attempts: dict[UUID, SimpleNamespace] = {}
        self.observations: list[PaperBrokerObservation] = []
        self.fail_entry_commit = fail_entry_commit
        self.entry_claim_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        self.take_profit_claim_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    def get_attempt(self, session: object, attempt_id: UUID) -> SimpleNamespace | None:
        return self.attempts.get(attempt_id)

    def commit_entry_claim(
        self, session: object, attempt: Any, **kwargs: object
    ) -> Any:
        if self.fail_entry_commit:
            raise RuntimeError("database unavailable")
        if attempt.attempt_id in self.attempts:
            raise DuplicateMutationClaim("duplicate")
        authority = attempt.risk_authority.to_json()
        instruction = attempt.instruction
        self.attempts[attempt.attempt_id] = SimpleNamespace(
            attempt_id=attempt.attempt_id,
            strategy_version_id=attempt.receipt.strategy_version_id,
            strategy_key=attempt.receipt.strategy_key,
            strategy_version_number=attempt.receipt.version_number,
            source_fingerprint=attempt.receipt.source_fingerprint,
            implementation_key=attempt.receipt.implementation_key,
            validated_parameter_snapshot=attempt.receipt.validated_parameter_snapshot.to_json(),
            strategy_evaluation_snapshot=attempt.receipt.evaluation.to_json(),
            risk_authority_snapshot=authority,
            strategy_decision=instruction.strategy_decision.to_json(),
            pre_flight_risk_decision=authority["pre_flight"],
            pre_submission_risk_decision=authority["pre_submission"],
            provider=instruction.account.provider.value,
            environment=instruction.account.environment,
            provider_account_id=instruction.account.account_id,
            base_currency=instruction.account.base_currency,
            instrument="EUR_USD",
            direction=instruction.direction.value,
            requested_quantity=instruction.requested_quantity,
            approved_entry_price=instruction.approved_entry_price,
            stop_price=instruction.stop_price,
            decision_time=instruction.decision_time,
            pricing_time=instruction.pricing_time,
            account_transaction_id=instruction.observation_provenance.account_transaction_id,
            instrument_transaction_id=instruction.observation_provenance.instrument_transaction_id,
            display_precision=instruction.display_precision,
            trade_units_precision=instruction.trade_units_precision,
            client_order_id=instruction.correlation.client_order_id,
            client_trade_id=instruction.correlation.client_trade_id,
            client_stop_loss_order_id=instruction.correlation.client_stop_loss_order_id,
            client_take_profit_order_id=instruction.correlation.client_take_profit_order_id,
            execution_outcome=None,
            rejection_code=None,
            rejection_broker_order_id=None,
            rejection_transaction_id=None,
            uncertainty_code=None,
            fill_broker_order_id=None,
            fill_transaction_id=None,
            fill_trade_id=None,
            fill_signed_units=None,
            fill_price=None,
            fill_executed_at=None,
            fill_actual_initial_risk=None,
            actual_target_price=None,
            stop_loss_status=ProtectionLegStatus.NOT_ATTEMPTED.value,
            stop_loss_broker_order_id=None,
            stop_loss_client_order_id=None,
            stop_loss_price=None,
            stop_loss_provider_state=None,
            take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED.value,
            take_profit_broker_order_id=None,
            take_profit_client_order_id=None,
            take_profit_price=None,
            take_profit_provider_state=None,
        )
        self.events.append("entry-claim")
        return SimpleNamespace(claim_id=self.entry_claim_id)

    def commit_take_profit_claim(
        self,
        session: object,
        attempt_id: UUID,
        *,
        protection: ProtectionConfirmation,
        **kwargs: object,
    ) -> Any:
        row = self.attempts[attempt_id]
        row.stop_loss_status = protection.stop_loss_status.value
        row.stop_loss_broker_order_id = (
            protection.stop_loss.broker_order_id if protection.stop_loss else None
        )
        row.stop_loss_client_order_id = (
            protection.stop_loss.client_order_id if protection.stop_loss else None
        )
        row.stop_loss_price = (
            protection.stop_loss.price if protection.stop_loss else None
        )
        row.stop_loss_provider_state = (
            protection.stop_loss.state if protection.stop_loss else None
        )
        row.actual_target_price = protection.actual_target_price
        self.events.append("take-profit-claim")
        return SimpleNamespace(claim_id=self.take_profit_claim_id)

    def append_observation(
        self, session: object, observation: PaperBrokerObservation
    ) -> None:
        self.observations.append(observation)
        self.events.append("observation")

    def apply_result(
        self,
        session: object,
        result: PaperExecutionResult,
        *,
        attempt: Any = None,
    ) -> None:
        del attempt
        row = self.attempts[result.instruction.attempt_id]
        row.execution_outcome = result.outcome.value
        row.rejection_code = result.rejection.detail_code if result.rejection else None
        row.rejection_broker_order_id = (
            result.rejection.broker_order_id if result.rejection else None
        )
        row.rejection_transaction_id = (
            result.rejection.broker_transaction_id if result.rejection else None
        )
        row.uncertainty_code = (
            result.uncertainty.detail_code if result.uncertainty else None
        )
        if result.fill is not None:
            row.fill_broker_order_id = result.fill.broker_order_id
            row.fill_transaction_id = result.fill.broker_fill_transaction_id
            row.fill_trade_id = result.fill.broker_trade_id
            row.fill_signed_units = result.fill.signed_units
            row.fill_price = result.fill.price
            row.fill_executed_at = result.fill.executed_at
            row.fill_actual_initial_risk = result.fill.actual_initial_risk
        protection = result.protection
        row.stop_loss_status = protection.stop_loss_status.value
        row.take_profit_status = protection.take_profit_status.value
        row.actual_target_price = protection.actual_target_price
        if protection.stop_loss is not None:
            row.stop_loss_broker_order_id = protection.stop_loss.broker_order_id
            row.stop_loss_client_order_id = protection.stop_loss.client_order_id
            row.stop_loss_price = protection.stop_loss.price
            row.stop_loss_provider_state = protection.stop_loss.state
        if protection.take_profit is not None:
            row.take_profit_broker_order_id = protection.take_profit.broker_order_id
            row.take_profit_client_order_id = protection.take_profit.client_order_id
            row.take_profit_price = protection.take_profit.price
            row.take_profit_provider_state = protection.take_profit.state
        self.events.append("projection")


class ValueReader:
    def __init__(self, value: object, events: list[str], name: str) -> None:
        self.value = value
        self.events = events
        self.name = name

    def read(self) -> object:
        self.events.append(self.name)
        return self.value


class EntryRequester:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0

    def post_entry_order(self, account_id: str, payload: object) -> object:
        self.calls += 1
        self.events.append("entry-post")
        return _entry_payload(fill=True)


class ProtectionRequester:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0

    def put_trade_orders(
        self, account_id: str, trade_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.calls += 1
        self.events.append("take-profit-put")
        return {
            "takeProfitOrderTransaction": {
                "id": "9002",
                "accountID": ACCOUNT_ID,
                "type": "TAKE_PROFIT_ORDER",
                "tradeID": "7001",
                "clientTradeID": f"atlas-p04-t-{ATTEMPT_ID.hex}",
                "price": "1.10877",
                "timeInForce": "GTC",
                "clientExtensions": {"id": f"atlas-p04-tp-{ATTEMPT_ID.hex}"},
            },
            "lastTransactionID": "9002",
            "relatedTransactionIDs": ["9002"],
        }


class TradeReader:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None:
        self.calls += 1
        self.events.append("trade-read")
        return (
            _trade(stop=_stop(), target=_target())
            if self.calls == 2
            else _trade(stop=_stop())
        )


class StaticTradeReader:
    def __init__(self, events: list[str], trade: Mapping[str, Any] | None) -> None:
        self.events = events
        self.calls = 0
        self.trade = trade

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None:
        self.calls += 1
        self.events.append("trade-read")
        return self.trade


def _correlation() -> tuple[str, str, str, str]:
    attempt = ATTEMPT_ID.hex
    return (
        f"atlas-p04-o-{attempt}",
        f"atlas-p04-t-{attempt}",
        f"atlas-p04-sl-{attempt}",
        f"atlas-p04-tp-{attempt}",
    )


def _stop(*, price: str = "1.09500") -> dict[str, Any]:
    return {
        "id": "8001",
        "type": "STOP_LOSS",
        "state": "PENDING",
        "tradeID": "7001",
        "price": price,
        "timeInForce": "GTC",
        "clientExtensions": {"id": _correlation()[2]},
    }


def _target() -> dict[str, Any]:
    return {
        "id": "9001",
        "type": "TAKE_PROFIT",
        "state": "PENDING",
        "tradeID": "7001",
        "clientTradeID": _correlation()[1],
        "price": "1.10877",
        "timeInForce": "GTC",
        "clientExtensions": {"id": _correlation()[3]},
    }


def _trade(
    *, stop: Mapping[str, Any] | None = None, target: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    trade: dict[str, Any] = {
        "id": "7001",
        "accountID": ACCOUNT_ID,
        "instrument": "EUR_USD",
        "state": "OPEN",
        "initialUnits": "19230",
        "currentUnits": "19230",
        "price": "1.10010",
        "clientExtensions": {"id": _correlation()[1]},
    }
    if stop is not None:
        trade["stopLossOrder"] = dict(stop)
    if target is not None:
        trade["takeProfitOrder"] = dict(target)
    return trade


def _entry_payload(*, fill: bool) -> dict[str, Any]:
    correlation = _correlation()
    create = {
        "id": "1001",
        "accountID": ACCOUNT_ID,
        "type": "MARKET_ORDER",
        "instrument": "EUR_USD",
        "units": "19230",
        "timeInForce": "FOK",
        "priceBound": "1.10020",
        "positionFill": "OPEN_ONLY",
        "clientOrderID": correlation[0],
        "clientExtensions": {"id": correlation[0], "tag": "atlas-paper-04"},
        "tradeClientExtensions": {"id": correlation[1]},
    }
    payload: dict[str, Any] = {
        "orderCreateTransaction": create,
        "lastTransactionID": "1002",
        "relatedTransactionIDs": ["1001", "1002"],
    }
    if fill:
        payload["orderFillTransaction"] = {
            "id": "1002",
            "accountID": ACCOUNT_ID,
            "type": "ORDER_FILL",
            "orderID": "1001",
            "clientOrderID": correlation[0],
            "instrument": "EUR_USD",
            "units": "19230",
            "time": "2026-09-02T12:00:02.000000000Z",
            "tradeOpened": {
                "tradeID": "7001",
                "units": "19230",
                "price": "1.10010",
            },
        }
    return payload


def receipt() -> PaperStrategyEvaluationReceipt:
    version = StrategyVersion(
        id=VERSION_ID,
        strategy_key="fixture",
        version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="fixture.v1",
        parameter_schema=(),
        created_at=NOW,
    )
    return PaperStrategyEvaluationReceipt.from_verified(
        version,
        ValidatedParameterPayload.from_mapping((), {}),
        StrategyEvaluation(decision(), StrategyState()),
    )


def app(
    repository: Repository,
    events: list[str],
    entry: EntryRequester,
    protection: ProtectionRequester,
    trade_reader: Any,
) -> PaperDurableExecutionApplication:
    return PaperDurableExecutionApplication(
        repository=repository,  # type: ignore[arg-type]
        session_factory=SessionFactory(events),  # type: ignore[arg-type]
        account_properties_reader=ValueReader(
            OandaPracticeAccountProperties(ACCOUNT_ID, None), events, "properties"
        ),
        execution_account_reader=ValueReader(account_snapshot(), events, "account"),
        execution_instrument_reader=ValueReader(INSTRUMENT, events, "instrument"),
        pricing_reader=ValueReader(pricing(), events, "pricing"),
        entry_mutation=OandaPracticeEntryMutation(entry),  # type: ignore[arg-type]
        protection_completion=OandaPracticeProtectionCompletion(
            protection, trade_reader
        ),  # type: ignore[arg-type]
    )


def test_durable_barriers_commit_before_each_mutation_and_risk_is_used_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    repository = Repository(events)
    entry = EntryRequester(events)
    protection = ProtectionRequester(events)
    operation = app(repository, events, entry, protection, TradeReader(events))
    calls = 0
    from backend.paper import execution_application

    original = execution_application.evaluate_paper_risk

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(execution_application, "evaluate_paper_risk", counted)
    result = operation.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )

    assert isinstance(result, PaperExecutionResult)
    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert result.protection.actual_target_price == Decimal("1.10877")
    assert calls == 1
    assert entry.calls == 1
    assert protection.calls == 1
    assert len(repository.observations) == 3
    assert repository.observations[0].read_kind.value == "ENTRY_MUTATION_RESPONSE"
    assert repository.observations[1].read_kind.value == "TAKE_PROFIT_MUTATION_RESPONSE"
    assert repository.observations[2].object_kind.value == "TRADE"
    assert (
        repository.observations[1].mutation_claim_id == repository.take_profit_claim_id
    )
    assert (
        repository.observations[2].mutation_claim_id == repository.take_profit_claim_id
    )
    assert events.index("entry-claim") < events.index("entry-post")
    assert events.index("take-profit-claim") < events.index("take-profit-put")
    assert events.index("observation") < events.index("projection")
    assert events.count("take-profit-claim") == 1


@pytest.mark.parametrize(
    "trade",
    [
        pytest.param(None, id="missing-trade"),
        pytest.param(_trade(stop=_stop(price="1.09501")), id="stop-mismatch"),
    ],
)
def test_no_put_protection_read_is_trade_observation_without_claim(
    trade: Mapping[str, Any] | None,
) -> None:
    events: list[str] = []
    repository = Repository(events)
    entry = EntryRequester(events)
    protection = ProtectionRequester(events)
    operation = app(
        repository,
        events,
        entry,
        protection,
        StaticTradeReader(events, trade),
    )

    result = operation.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )

    assert isinstance(result, PaperExecutionResult)
    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert entry.calls == 1
    assert protection.calls == 0
    assert len(repository.observations) == 2
    trade_observation = repository.observations[1]
    assert trade_observation.read_kind is PaperObservationReadKind.TRADE_DETAIL
    assert trade_observation.object_kind is PaperObservationObjectKind.TRADE
    assert trade_observation.mutation_claim_id is None
    assert "take-profit-put" not in events


def test_durable_restart_returns_persisted_result_without_resubmitting() -> None:
    events: list[str] = []
    repository = Repository(events)
    entry = EntryRequester(events)
    protection = ProtectionRequester(events)
    operation = app(repository, events, entry, protection, TradeReader(events))
    first = operation.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    second = app(repository, events, entry, protection, TradeReader(events)).execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )

    assert isinstance(first, PaperExecutionResult)
    assert isinstance(second, PaperExecutionResult)
    assert second.outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert entry.calls == 1
    assert protection.calls == 1


def test_entry_commit_failure_prohibits_entry_post() -> None:
    events: list[str] = []
    repository = Repository(events, fail_entry_commit=True)
    entry = EntryRequester(events)
    operation = app(
        repository, events, entry, ProtectionRequester(events), TradeReader(events)
    )
    result = operation.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )

    assert isinstance(result, PaperExecutionRefusal)
    assert result.code is PaperExecutionRefusalCode.LOCAL_SERIALIZATION_REJECTED
    assert entry.calls == 0
    assert "entry-post" not in events


class UnknownEntry:
    def __init__(self) -> None:
        self.calls = 0

    def submit(
        self, instruction: Any, execution_instrument: Any
    ) -> PaperExecutionResult:
        self.calls += 1
        return PaperExecutionResult(
            outcome=PaperExecutionOutcome.UNKNOWN,
            instruction=instruction,
            correlation=instruction.correlation,
            fill=None,
            protection=ProtectionConfirmation(
                ProtectionLegStatus.NOT_ATTEMPTED,
                None,
                ProtectionLegStatus.NOT_ATTEMPTED,
                None,
                None,
            ),
            rejection=None,
            uncertainty=BrokerUncertainty("ENTRY_TRANSPORT_UNCERTAIN"),
            transaction_provenance=TransactionProvenance(),
        )


def test_uncertain_entry_claim_is_not_reacquired_after_restart() -> None:
    events: list[str] = []
    repository = Repository(events)
    unknown = UnknownEntry()
    operation = PaperDurableExecutionApplication(
        repository=repository,  # type: ignore[arg-type]
        session_factory=SessionFactory(events),  # type: ignore[arg-type]
        account_properties_reader=ValueReader(
            OandaPracticeAccountProperties(ACCOUNT_ID, None), events, "properties"
        ),
        execution_account_reader=ValueReader(account_snapshot(), events, "account"),
        execution_instrument_reader=ValueReader(INSTRUMENT, events, "instrument"),
        pricing_reader=ValueReader(pricing(), events, "pricing"),
        entry_mutation=unknown,  # type: ignore[arg-type]
        protection_completion=OandaPracticeProtectionCompletion(
            ProtectionRequester(events), TradeReader(events)
        ),
    )
    first = operation.execute(
        receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID
    )
    second = app(
        repository,
        events,
        EntryRequester(events),
        ProtectionRequester(events),
        TradeReader(events),
    ).execute(receipt(), config=RiskConfig(Decimal("0.01")), attempt_id=ATTEMPT_ID)

    assert isinstance(first, PaperExecutionResult)
    assert first.outcome is PaperExecutionOutcome.UNKNOWN
    assert isinstance(second, PaperExecutionResult)
    assert second.outcome is PaperExecutionOutcome.UNKNOWN
    assert unknown.calls == 1
