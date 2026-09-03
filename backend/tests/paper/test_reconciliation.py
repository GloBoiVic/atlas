from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from backend.domain import Direction, Instrument
from backend.paper import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    BrokerRejection,
    PaperBrokerObservation,
    PaperExecutionOutcome,
    PaperMutationPhase,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperReconciliationContext,
    PaperReconciliationCoordinator,
    PaperReconciliationFindingCode,
    PaperReconciliationRead,
    PaperReconciliationReadState,
    PaperReconciliationTransaction,
    ProtectionConfirmation,
    ProtectionLegStatus,
    ReconciliationStatus,
)
from backend.persistence.paper_execution_repository import StaleReconciliationError

ATTEMPT_ID = UUID("12345678-1234-5678-1234-567812345678")
ACCOUNT_ID = "001-011-5838423-001"
NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)
ORDER_ID = "1001"
TRADE_ID = "7001"
STOP_ID = "8001"
TARGET_ID = "9001"
CORRELATION = (
    f"atlas-p04-o-{ATTEMPT_ID.hex}",
    f"atlas-p04-t-{ATTEMPT_ID.hex}",
    f"atlas-p04-sl-{ATTEMPT_ID.hex}",
    f"atlas-p04-tp-{ATTEMPT_ID.hex}",
)


class Session:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class Repository:
    def __init__(
        self,
        row: SimpleNamespace,
        *,
        stale: bool = False,
    ) -> None:
        self.row = row
        self.runs: list[Any] = []
        self.observations: list[PaperBrokerObservation] = []
        self.stale = stale

    def get_attempt(self, session: object, attempt_id: UUID) -> SimpleNamespace | None:
        return self.row if attempt_id == self.row.attempt_id else None

    def next_reconciliation_sequence(self, session: object, attempt_id: UUID) -> int:
        return len(self.runs) + 1

    def has_mutation_claim(
        self, session: object, attempt_id: UUID, phase: PaperMutationPhase
    ) -> bool:
        return phase is PaperMutationPhase.TAKE_PROFIT and self.row.take_profit_claimed

    def apply_reconciliation_run(
        self, session: object, run: Any, **kwargs: Any
    ) -> None:
        if self.stale:
            self.stale = False
            self.runs.append(run)
            raise StaleReconciliationError(str(run.run_id))
        self.runs.append(run)
        self.observations.extend(kwargs["observations"])
        fill = kwargs.get("fill")
        if fill is not None:
            self.row.fill_broker_order_id = fill.broker_order_id
            self.row.fill_transaction_id = fill.broker_fill_transaction_id
            self.row.fill_trade_id = fill.broker_trade_id
            self.row.fill_signed_units = fill.signed_units
            self.row.fill_price = fill.price
            self.row.fill_executed_at = fill.executed_at
            self.row.fill_actual_initial_risk = fill.actual_initial_risk
        protection = kwargs.get("protection")
        if protection is not None:
            self.row.stop_loss_status = protection.stop_loss_status.value
            self.row.take_profit_status = protection.take_profit_status.value
            self.row.actual_target_price = protection.actual_target_price
        if run.resulting_execution_outcome is not None:
            self.row.execution_outcome = run.resulting_execution_outcome.value
        self.row.reconciliation_status = kwargs["reconciliation_status"].value
        self.row.reconciliation_block_code = kwargs.get("reconciliation_block_code")
        if kwargs.get("rejection_code") is not None:
            self.row.rejection_code = kwargs["rejection_code"]
            self.row.rejection_broker_order_id = kwargs.get("rejection_broker_order_id")
            self.row.rejection_transaction_id = kwargs.get("rejection_transaction_id")
        self.row.projection_version += 1
        current_frontier = self.row.last_applied_transaction_id
        proposed_frontier = run.frontier_applied
        if current_frontier is None:
            self.row.last_applied_transaction_id = proposed_frontier
        elif proposed_frontier is None:
            self.row.last_applied_transaction_id = current_frontier
        else:
            self.row.last_applied_transaction_id = max(
                current_frontier, proposed_frontier, key=int
            )


class Provider:
    def __init__(self) -> None:
        self.reads: dict[str, PaperReconciliationRead] = {}
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.failures: set[str] = set()

    def _get(self, name: str) -> PaperReconciliationRead:
        self.calls.append((name, ()))
        if name in self.failures:
            raise RuntimeError(f"{name} failed")
        return self.reads[name]

    def read_order(
        self, context: PaperReconciliationContext
    ) -> PaperReconciliationRead:
        return self._get("order")

    def read_transaction(
        self, context: PaperReconciliationContext, transaction_id: str
    ) -> PaperReconciliationRead:
        self.calls.append(("transaction", (transaction_id,)))
        return self.reads["transaction"]

    def read_trade(
        self, context: PaperReconciliationContext, trade_id: str
    ) -> PaperReconciliationRead:
        self.calls.append(("trade", (trade_id,)))
        return self.reads["trade"]

    def read_account(
        self, context: PaperReconciliationContext
    ) -> PaperReconciliationRead:
        return self._get("account")

    def read_transaction_range(
        self, context: PaperReconciliationContext, from_id: str, to_id: str
    ) -> PaperReconciliationRead:
        self.calls.append(("range", (from_id, to_id)))
        return self.reads["range"]


def row(
    *,
    outcome: PaperExecutionOutcome | None = None,
    fill: BrokerFillFacts | None = None,
    target: Decimal | None = None,
    take_profit_claimed: bool = False,
    last_applied_transaction_id: str | None = None,
    rejection_code: str | None = None,
    rejection_broker_order_id: str | None = None,
    rejection_transaction_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        attempt_id=ATTEMPT_ID,
        provider="OANDA",
        environment="PRACTICE",
        provider_account_id=ACCOUNT_ID,
        base_currency="USD",
        instrument="EUR_USD",
        direction="LONG",
        requested_quantity=Decimal("19230"),
        approved_entry_price=Decimal("1.10020"),
        stop_price=Decimal("1.09500"),
        client_order_id=CORRELATION[0],
        client_trade_id=CORRELATION[1],
        client_stop_loss_order_id=CORRELATION[2],
        client_take_profit_order_id=CORRELATION[3],
        fill_broker_order_id=fill.broker_order_id if fill else None,
        fill_transaction_id=fill.broker_fill_transaction_id if fill else None,
        fill_trade_id=fill.broker_trade_id if fill else None,
        fill_signed_units=fill.signed_units if fill else None,
        fill_price=fill.price if fill else None,
        fill_executed_at=fill.executed_at if fill else None,
        fill_actual_initial_risk=fill.actual_initial_risk if fill else None,
        actual_target_price=target,
        stop_loss_status=ProtectionLegStatus.NOT_ATTEMPTED.value,
        stop_loss_broker_order_id=None,
        take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED.value,
        take_profit_broker_order_id=None,
        execution_outcome=outcome.value if outcome else None,
        reconciliation_status=ReconciliationStatus.NOT_RUN.value,
        reconciliation_block_code=None,
        rejection_code=rejection_code,
        rejection_broker_order_id=rejection_broker_order_id,
        rejection_transaction_id=rejection_transaction_id,
        last_applied_transaction_id=last_applied_transaction_id,
        account_transaction_id="10",
        projection_version=0,
        take_profit_claimed=take_profit_claimed,
    )


def context() -> PaperReconciliationContext:
    return PaperReconciliationContext(
        attempt_id=ATTEMPT_ID,
        provider_account_id=ACCOUNT_ID,
        instrument="EUR_USD",
        direction=Direction.LONG,
        signed_requested_units=Decimal("19230"),
        approved_entry_price=Decimal("1.10020"),
        stop_price=Decimal("1.09500"),
        client_order_id=CORRELATION[0],
        client_trade_id=CORRELATION[1],
        client_stop_loss_order_id=CORRELATION[2],
        client_take_profit_order_id=CORRELATION[3],
        provider_order_id=None,
        provider_trade_id=None,
        actual_target_price=None,
        take_profit_claimed=False,
        pre_entry_transaction_id="10",
    )


def observation(
    kind: PaperObservationReadKind,
    object_kind: PaperObservationObjectKind,
    *,
    frontier: str | None = None,
    provider_order_id: str | None = None,
    provider_trade_id: str | None = None,
    provider_transaction_id: str | None = None,
    client_trade_id: str | None = None,
    signed_units: Decimal | None = None,
    price: Decimal | None = None,
) -> PaperBrokerObservation:
    return PaperBrokerObservation(
        attempt_id=ATTEMPT_ID,
        read_kind=kind,
        object_kind=object_kind,
        provider_account_id=ACCOUNT_ID,
        instrument=(
            None
            if object_kind is PaperObservationObjectKind.ACCOUNT
            else Instrument.EUR_USD
        ),
        normalized_facts={"found": True},
        provider_order_id=provider_order_id,
        provider_trade_id=provider_trade_id,
        provider_transaction_id=provider_transaction_id,
        client_trade_id=client_trade_id,
        signed_units=signed_units,
        price=price,
        last_transaction_id=frontier,
        atlas_observed_at=NOW,
    )


def read(
    kind: PaperObservationReadKind,
    object_kind: PaperObservationObjectKind,
    state: PaperReconciliationReadState,
    *,
    fill: BrokerFillFacts | None = None,
    rejection: BrokerRejection | None = None,
    transaction_id: str | None = None,
    frontier: str | None = None,
    protection: ProtectionConfirmation | None = None,
    attributable: bool = True,
    protection_drift: bool = False,
    unexpected_exposure: bool = False,
    transactions: tuple[PaperReconciliationTransaction, ...] = (),
    provider_order_id: str | None = None,
    provider_trade_id: str | None = None,
    provider_transaction_id: str | None = None,
    trade_id: str | None = None,
    client_trade_id: str | None = None,
    signed_units: Decimal | None = None,
    price: Decimal | None = None,
) -> PaperReconciliationRead:
    return PaperReconciliationRead(
        observation(
            kind,
            object_kind,
            frontier=frontier,
            provider_order_id=provider_order_id,
            provider_trade_id=provider_trade_id,
            provider_transaction_id=provider_transaction_id,
            client_trade_id=client_trade_id,
            signed_units=signed_units,
            price=price,
        ),
        state,
        fill=fill,
        rejection=rejection,
        terminal_transaction_id=transaction_id,
        trade_id=trade_id,
        protection=protection,
        attributable=attributable,
        protection_drift=protection_drift,
        unexpected_exposure=unexpected_exposure,
        transactions=transactions,
    )


def coordinator(
    repository: Repository, provider: Provider
) -> PaperReconciliationCoordinator:
    return PaperReconciliationCoordinator(
        repository=cast(Any, repository),
        session_factory=cast(Any, Session),
        provider=provider,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )


def fill() -> BrokerFillFacts:
    return BrokerFillFacts(
        ORDER_ID,
        "1002",
        TRADE_ID,
        Decimal("19230"),
        Decimal("1.10010"),
        NOW,
        Decimal("98.1150"),
    )


def protection(*, target: bool = True) -> ProtectionConfirmation:
    return ProtectionConfirmation(
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(STOP_ID, CORRELATION[2], Decimal("1.09500"), "PENDING"),
        ProtectionLegStatus.CONFIRMED if target else ProtectionLegStatus.UNKNOWN,
        (
            BrokerProtectionOrder(
                TARGET_ID, CORRELATION[3], Decimal("1.11030"), "PENDING"
            )
            if target
            else None
        ),
        Decimal("1.11030") if target else None,
    )


def configure_later_fill(provider: Provider, *, bounded: bool) -> BrokerFillFacts:
    later_fill = fill()
    if bounded:
        provider.reads["order"] = read(
            PaperObservationReadKind.ORDER_DETAIL,
            PaperObservationObjectKind.ORDER,
            PaperReconciliationReadState.NOT_FOUND,
        )
        provider.reads["account"] = read(
            PaperObservationReadKind.ACCOUNT_DETAILS,
            PaperObservationObjectKind.ACCOUNT,
            PaperReconciliationReadState.ACCOUNT,
            frontier="12",
        )
        provider.reads["range"] = read(
            PaperObservationReadKind.TRANSACTION_RANGE,
            PaperObservationObjectKind.TRANSACTION,
            PaperReconciliationReadState.RANGE,
            frontier="12",
            transactions=(
                PaperReconciliationTransaction(
                    PaperReconciliationReadState.FILLED,
                    provider_transaction_id="12",
                    provider_order_id=ORDER_ID,
                    provider_trade_id=TRADE_ID,
                    fill=later_fill,
                    attributable=True,
                ),
            ),
        )
    else:
        provider.reads["order"] = read(
            PaperObservationReadKind.ORDER_DETAIL,
            PaperObservationObjectKind.ORDER,
            PaperReconciliationReadState.FILLED,
            transaction_id="12",
            provider_order_id=ORDER_ID,
        )
        provider.reads["transaction"] = read(
            PaperObservationReadKind.TRANSACTION_DETAIL,
            PaperObservationObjectKind.TRANSACTION,
            PaperReconciliationReadState.FILLED,
            fill=later_fill,
        )
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.NOT_FOUND,
        provider_trade_id=TRADE_ID,
    )
    return later_fill


def test_unknown_not_found_is_unresolved_and_reads_account_once() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="10",
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is PaperExecutionOutcome.UNKNOWN
    assert result.reconciliation_status is ReconciliationStatus.UNRESOLVED
    assert result.run.read_count == 2
    assert [name for name, _ in provider.calls] == ["order", "account"]
    assert repository.row.execution_outcome == PaperExecutionOutcome.UNKNOWN.value


def test_exact_cancel_transaction_resolves_without_account_or_mutation() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.CANCELLED,
        transaction_id="11",
    )
    provider.reads["transaction"] = read(
        PaperObservationReadKind.TRANSACTION_DETAIL,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.CANCELLED,
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is PaperExecutionOutcome.CANCELLED
    assert result.reconciliation_status is ReconciliationStatus.CONSISTENT
    assert [name for name, _ in provider.calls] == ["order", "transaction"]
    assert len(repository.observations) == 2
    assert repository.row.reconciliation_block_code is None


def test_exact_reject_transaction_resolves_as_rejected() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.REJECTED,
        transaction_id="11",
        provider_order_id=ORDER_ID,
    )
    provider.reads["transaction"] = read(
        PaperObservationReadKind.TRANSACTION_DETAIL,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.REJECTED,
        rejection=BrokerRejection("BROKER_ORDER_REJECTED", ORDER_ID, "11"),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is PaperExecutionOutcome.REJECTED
    assert result.reconciliation_status is ReconciliationStatus.CONSISTENT
    assert repository.row.rejection_code == "BROKER_ORDER_REJECTED"
    assert repository.row.rejection_broker_order_id == ORDER_ID
    assert repository.row.rejection_transaction_id == "11"


def test_exact_fill_persists_fill_truth_but_stays_incomplete_without_trade() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.FILLED,
        transaction_id="12",
        provider_order_id=ORDER_ID,
    )
    provider.reads["transaction"] = read(
        PaperObservationReadKind.TRANSACTION_DETAIL,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.FILLED,
        fill=fill(),
    )
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.NOT_FOUND,
        provider_trade_id=TRADE_ID,
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    outcome = result.execution_outcome
    assert outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.reconciliation_status is ReconciliationStatus.UNRESOLVED
    assert repository.row.fill_trade_id == TRADE_ID


@pytest.mark.parametrize(
    "prior_outcome",
    [PaperExecutionOutcome.REJECTED, PaperExecutionOutcome.CANCELLED],
)
@pytest.mark.parametrize("bounded", [False, True], ids=["exact", "range"])
def test_later_fill_after_terminal_history_is_conflict(
    prior_outcome: PaperExecutionOutcome, bounded: bool
) -> None:
    repository = Repository(
        row(
            outcome=prior_outcome,
            rejection_code=(
                "PRIOR_REJECTION"
                if prior_outcome is PaperExecutionOutcome.REJECTED
                else None
            ),
            rejection_broker_order_id=(
                ORDER_ID if prior_outcome is PaperExecutionOutcome.REJECTED else None
            ),
            rejection_transaction_id=(
                "11" if prior_outcome is PaperExecutionOutcome.REJECTED else None
            ),
        )
    )
    provider = Provider()
    later_fill = configure_later_fill(provider, bounded=bounded)

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert (
        result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    )
    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert result.run.status.value == "CONFLICT"
    assert PaperReconciliationFindingCode.ENTRY_FILLED in result.run.finding_codes
    assert PaperReconciliationFindingCode.CONFLICT in result.run.finding_codes
    assert repository.row.fill_trade_id == later_fill.broker_trade_id
    assert result.run.prior_execution_outcome is prior_outcome
    assert repository.row.rejection_code == (
        "PRIOR_REJECTION" if prior_outcome is PaperExecutionOutcome.REJECTED else None
    )
    assert repository.row.rejection_broker_order_id == (
        ORDER_ID if prior_outcome is PaperExecutionOutcome.REJECTED else None
    )
    assert repository.row.rejection_transaction_id == (
        "11" if prior_outcome is PaperExecutionOutcome.REJECTED else None
    )


def test_later_fill_after_rejection_history_keeps_conflict_through_protection() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.REJECTED,
            target=Decimal("1.11030"),
            take_profit_claimed=True,
            rejection_code="PRIOR_REJECTION",
            rejection_broker_order_id=ORDER_ID,
            rejection_transaction_id="11",
        )
    )
    provider = Provider()
    configure_later_fill(provider, bounded=False)
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.OPEN,
        trade_id=TRADE_ID,
        provider_trade_id=TRADE_ID,
        client_trade_id=CORRELATION[1],
        signed_units=Decimal("19230"),
        price=Decimal("1.10010"),
        protection=protection(),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert PaperReconciliationFindingCode.CONFLICT in result.run.finding_codes
    assert (
        PaperReconciliationFindingCode.PROTECTION_CONFIRMED in result.run.finding_codes
    )
    assert (
        repository.row.execution_outcome == PaperExecutionOutcome.FILLED_PROTECTED.value
    )
    assert repository.row.stop_loss_status == ProtectionLegStatus.CONFIRMED.value
    assert repository.row.take_profit_status == ProtectionLegStatus.CONFIRMED.value
    assert repository.row.rejection_code == "PRIOR_REJECTION"
    assert repository.row.rejection_broker_order_id == ORDER_ID
    assert repository.row.rejection_transaction_id == "11"


def test_terminal_history_conflict_survives_trade_read_failure() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.CANCELLED,
        )
    )
    provider = Provider()
    configure_later_fill(provider, bounded=False)
    provider.failures.add("trade")

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert (
        result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    )
    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert result.run.status.value == "CONFLICT"
    assert PaperReconciliationFindingCode.CONFLICT in result.run.finding_codes


@pytest.mark.parametrize(
    "prior_outcome",
    [None, PaperExecutionOutcome.UNKNOWN],
)
def test_later_fill_without_terminal_history_is_not_conflict(
    prior_outcome: PaperExecutionOutcome | None,
) -> None:
    repository = Repository(row(outcome=prior_outcome))
    provider = Provider()
    configure_later_fill(provider, bounded=False)

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert (
        result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    )
    assert result.reconciliation_status is ReconciliationStatus.UNRESOLVED
    assert PaperReconciliationFindingCode.CONFLICT not in result.run.finding_codes


@pytest.mark.parametrize(
    "terminal_outcome",
    [PaperExecutionOutcome.REJECTED, PaperExecutionOutcome.CANCELLED],
)
def test_same_later_terminal_history_remains_consistent(
    terminal_outcome: PaperExecutionOutcome,
) -> None:
    repository = Repository(row(outcome=terminal_outcome))
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState(terminal_outcome.value),
        transaction_id="12",
        provider_order_id=ORDER_ID,
    )
    provider.reads["transaction"] = read(
        PaperObservationReadKind.TRANSACTION_DETAIL,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState(terminal_outcome.value),
        rejection=(
            BrokerRejection("BROKER_ORDER_REJECTED", ORDER_ID, "12")
            if terminal_outcome is PaperExecutionOutcome.REJECTED
            else None
        ),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is terminal_outcome
    assert result.reconciliation_status is ReconciliationStatus.CONSISTENT
    assert PaperReconciliationFindingCode.CONFLICT not in result.run.finding_codes


@pytest.mark.parametrize(
    ("prior_outcome", "later_outcome"),
    [
        (PaperExecutionOutcome.REJECTED, PaperExecutionOutcome.CANCELLED),
        (PaperExecutionOutcome.CANCELLED, PaperExecutionOutcome.REJECTED),
    ],
)
def test_contradictory_later_terminal_history_fails_closed(
    prior_outcome: PaperExecutionOutcome, later_outcome: PaperExecutionOutcome
) -> None:
    repository = Repository(row(outcome=prior_outcome))
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState(later_outcome.value),
        transaction_id="12",
        provider_order_id=ORDER_ID,
    )
    provider.reads["transaction"] = read(
        PaperObservationReadKind.TRANSACTION_DETAIL,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState(later_outcome.value),
        rejection=(
            BrokerRejection("BROKER_ORDER_REJECTED", ORDER_ID, "12")
            if later_outcome is PaperExecutionOutcome.REJECTED
            else None
        ),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is prior_outcome
    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert result.run.status.value == "CONFLICT"
    assert PaperReconciliationFindingCode.CONFLICT in result.run.finding_codes
    assert repository.row.execution_outcome == prior_outcome.value


def test_missing_order_uses_one_numeric_bounded_range_for_reject() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="12",
    )
    rejected = PaperReconciliationTransaction(
        PaperReconciliationReadState.REJECTED,
        provider_transaction_id="12",
        provider_order_id=ORDER_ID,
        rejection=BrokerRejection("BROKER_ORDER_REJECTED", ORDER_ID, "12"),
        attributable=True,
    )
    provider.reads["range"] = read(
        PaperObservationReadKind.TRANSACTION_RANGE,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.RANGE,
        frontier="12",
        transactions=(rejected,),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is PaperExecutionOutcome.REJECTED
    assert result.reconciliation_status is ReconciliationStatus.CONSISTENT
    assert ("range", ("11", "12")) in provider.calls


def test_range_frontier_boundary_is_truncated_and_not_advanced() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="100",
    )
    provider.reads["range"] = read(
        PaperObservationReadKind.TRANSACTION_RANGE,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.RANGE,
        frontier="37",
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.UNRESOLVED
    assert (
        PaperReconciliationFindingCode.TRANSACTION_RANGE_TRUNCATED
        in result.run.finding_codes
    )
    assert ("range", ("11", "42")) in provider.calls
    assert repository.row.last_applied_transaction_id is None


def test_known_fill_promotes_only_with_claimed_exact_independent_protection() -> None:
    known_fill = fill()
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            fill=known_fill,
            target=Decimal("1.11030"),
            take_profit_claimed=True,
        )
    )
    provider = Provider()
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.OPEN,
        trade_id=TRADE_ID,
        provider_trade_id=TRADE_ID,
        client_trade_id=CORRELATION[1],
        signed_units=Decimal("19230"),
        price=Decimal("1.10010"),
        protection=protection(),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert result.reconciliation_status is ReconciliationStatus.CONSISTENT
    assert (
        repository.row.execution_outcome == PaperExecutionOutcome.FILLED_PROTECTED.value
    )
    assert repository.row.stop_loss_status == ProtectionLegStatus.CONFIRMED.value


def test_protected_closed_trade_is_lifecycle_advanced_without_downgrade() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.FILLED_PROTECTED,
            fill=fill(),
            target=Decimal("1.11030"),
        )
    )
    provider = Provider()
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.CLOSED,
        trade_id=TRADE_ID,
        provider_trade_id=TRADE_ID,
        client_trade_id=CORRELATION[1],
        signed_units=Decimal("19230"),
        price=Decimal("1.10010"),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.LIFECYCLE_ADVANCED
    assert (
        repository.row.execution_outcome == PaperExecutionOutcome.FILLED_PROTECTED.value
    )


def test_protection_drift_is_conflict_and_does_not_adopt_broker_leg() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.FILLED_PROTECTED,
            fill=fill(),
            target=Decimal("1.11030"),
        )
    )
    provider = Provider()
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.OPEN,
        trade_id=TRADE_ID,
        provider_trade_id=TRADE_ID,
        client_trade_id=CORRELATION[1],
        signed_units=Decimal("19230"),
        price=Decimal("1.10010"),
        protection=protection(),
        protection_drift=True,
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert (
        repository.row.execution_outcome == PaperExecutionOutcome.FILLED_PROTECTED.value
    )
    assert repository.row.stop_loss_status == ProtectionLegStatus.NOT_ATTEMPTED.value


def test_provider_read_failure_is_failed_closed() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.failures.add("order")

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.run.status.value == "FAILED"
    assert result.reconciliation_status is ReconciliationStatus.UNRESOLVED
    assert result.execution_outcome is PaperExecutionOutcome.UNKNOWN
    assert repository.row.execution_outcome == PaperExecutionOutcome.UNKNOWN.value


def test_unexpected_account_exposure_remains_conflict_even_if_range_is_proven() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="12",
        unexpected_exposure=True,
    )
    provider.reads["range"] = read(
        PaperObservationReadKind.TRANSACTION_RANGE,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.RANGE,
        frontier="12",
        transactions=(
            PaperReconciliationTransaction(
                PaperReconciliationReadState.REJECTED,
                provider_transaction_id="12",
                provider_order_id=ORDER_ID,
                rejection=BrokerRejection("BROKER_ORDER_REJECTED", ORDER_ID, "12"),
                attributable=True,
            ),
        ),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert result.run.status.value == "CONFLICT"


def test_stale_projection_is_reported_without_overwriting_row() -> None:
    repository = Repository(row(), stale=True)
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="10",
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.stale is True
    assert result.reconciliation_status is ReconciliationStatus.UNRESOLVED
    assert repository.row.projection_version == 0


def test_unattributed_closed_trade_cannot_prove_lifecycle_advancement() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.FILLED_PROTECTED,
            fill=fill(),
            target=Decimal("1.11030"),
        )
    )
    provider = Provider()
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.CLOSED,
        trade_id="7002",
        provider_trade_id="7002",
        attributable=False,
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert (
        PaperReconciliationFindingCode.TRADE_LIFECYCLE_ADVANCED
        not in result.run.finding_codes
    )


def test_known_fill_trade_units_mismatch_cannot_promote_protection() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            fill=fill(),
            target=Decimal("1.11030"),
            take_profit_claimed=True,
        )
    )
    provider = Provider()
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.OPEN,
        trade_id=TRADE_ID,
        provider_trade_id=TRADE_ID,
        client_trade_id=CORRELATION[1],
        signed_units=Decimal("1"),
        price=Decimal("1.10010"),
        protection=protection(),
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert (
        result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    )
    assert repository.row.execution_outcome == (
        PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE.value
    )


def test_structurally_valid_unrelated_protection_cannot_be_adopted() -> None:
    repository = Repository(
        row(
            outcome=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            fill=fill(),
            target=Decimal("1.11030"),
            take_profit_claimed=True,
        )
    )
    provider = Provider()
    unrelated = ProtectionConfirmation(
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "unrelated-stop", "unrelated-stop-client", Decimal("9.98"), "PENDING"
        ),
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "unrelated-target", "unrelated-target-client", Decimal("9.98"), "PENDING"
        ),
        Decimal("9.98"),
    )
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.OPEN,
        trade_id=TRADE_ID,
        provider_trade_id=TRADE_ID,
        client_trade_id=CORRELATION[1],
        signed_units=Decimal("19230"),
        price=Decimal("1.10010"),
        protection=unrelated,
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert (
        result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    )
    assert repository.row.actual_target_price == Decimal("1.11030")


def test_fill_and_reject_range_evidence_preserves_fill_and_marks_conflict() -> None:
    repository = Repository(row())
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="12",
    )
    filled = PaperReconciliationTransaction(
        PaperReconciliationReadState.FILLED,
        provider_transaction_id="12",
        provider_order_id=ORDER_ID,
        provider_trade_id=TRADE_ID,
        fill=fill(),
        attributable=True,
    )
    rejected = PaperReconciliationTransaction(
        PaperReconciliationReadState.REJECTED,
        provider_transaction_id="13",
        provider_order_id=ORDER_ID,
        rejection=BrokerRejection("BROKER_ORDER_REJECTED", ORDER_ID, "13"),
        attributable=True,
    )
    provider.reads["range"] = read(
        PaperObservationReadKind.TRANSACTION_RANGE,
        PaperObservationObjectKind.TRANSACTION,
        PaperReconciliationReadState.CONFLICT,
        frontier="13",
        transactions=(filled, rejected),
        rejection=rejected.rejection,
    )
    provider.reads["trade"] = read(
        PaperObservationReadKind.TRADE_DETAIL,
        PaperObservationObjectKind.TRADE,
        PaperReconciliationReadState.NOT_FOUND,
        provider_trade_id=TRADE_ID,
    )

    result = coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert result.reconciliation_status is ReconciliationStatus.CONFLICT
    assert (
        result.execution_outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    )
    assert repository.row.fill_trade_id == TRADE_ID
    assert repository.row.rejection_transaction_id == "13"
    assert PaperReconciliationFindingCode.CONFLICT in result.run.finding_codes


def test_stale_numeric_frontier_does_not_regress_durable_attempt_frontier() -> None:
    repository = Repository(row(last_applied_transaction_id="20"))
    provider = Provider()
    provider.reads["order"] = read(
        PaperObservationReadKind.ORDER_DETAIL,
        PaperObservationObjectKind.ORDER,
        PaperReconciliationReadState.NOT_FOUND,
    )
    provider.reads["account"] = read(
        PaperObservationReadKind.ACCOUNT_DETAILS,
        PaperObservationObjectKind.ACCOUNT,
        PaperReconciliationReadState.ACCOUNT,
        frontier="15",
    )

    coordinator(repository, provider).reconcile(ATTEMPT_ID)

    assert repository.row.last_applied_transaction_id == "20"
