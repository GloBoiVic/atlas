"""Bounded, provider-neutral PAPER reconciliation.

The coordinator consumes already-normalized provider facts.  It deliberately
does not import a broker integration and exposes no operation that can mutate
an account.  Provider adapters own request paths, payload interpretation, and
strict provider attribution; this module owns only the PAPER state machine and
the local append/apply boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.domain import Direction, Provider
from backend.persistence.models import PaperExecutionAttemptModel
from backend.persistence.paper_execution_repository import (
    PaperAttemptNotFound,
    PaperExecutionRepository,
    PaperIdentityConflict,
    PaperRepositoryError,
    StaleReconciliationError,
)

from .execution import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    BrokerRejection,
    PaperExecutionOutcome,
    ProtectionConfirmation,
    ProtectionLegStatus,
)
from .persistence_contracts import (
    PaperBrokerObservation,
    PaperMutationPhase,
    PaperObservationObjectKind,
    PaperPersistenceContractError,
    PaperReconciliationFindingCode,
    PaperReconciliationRun,
    PaperReconciliationRunStatus,
    ReconciliationStatus,
)

MAX_ENTRY_RECONCILIATION_TRANSACTIONS = 32
MAX_RECONCILIATION_READS = 8


class PaperReconciliationReadState(StrEnum):
    """Finite normalized states a read-only adapter may report."""

    NOT_FOUND = "NOT_FOUND"
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ACCOUNT = "ACCOUNT"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class PaperReconciliationContext:
    """Immutable attempt facts needed by a provider normalizer."""

    attempt_id: UUID
    provider_account_id: str
    instrument: str
    direction: Direction
    signed_requested_units: Decimal
    approved_entry_price: Decimal
    stop_price: Decimal
    client_order_id: str
    client_trade_id: str
    client_stop_loss_order_id: str
    client_take_profit_order_id: str
    provider_order_id: str | None
    provider_trade_id: str | None
    actual_target_price: Decimal | None
    take_profit_claimed: bool
    pre_entry_transaction_id: str
    fill_signed_units: Decimal | None = None
    fill_price: Decimal | None = None
    stop_loss_broker_order_id: str | None = None
    take_profit_broker_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class PaperReconciliationTransaction:
    """One finite normalized transaction candidate from a range read."""

    state: PaperReconciliationReadState
    provider_transaction_id: str | None = None
    provider_order_id: str | None = None
    provider_trade_id: str | None = None
    fill: BrokerFillFacts | None = None
    rejection: BrokerRejection | None = None
    attributable: bool = False
    contradictory: bool = False

    def __post_init__(self) -> None:
        if type(self.state) is not PaperReconciliationReadState:
            raise PaperPersistenceContractError("transaction state is invalid")
        if self.fill is not None and type(self.fill) is not BrokerFillFacts:
            raise PaperPersistenceContractError("transaction Fill is invalid")
        if self.rejection is not None and type(self.rejection) is not BrokerRejection:
            raise PaperPersistenceContractError("transaction rejection is invalid")
        for value, name in (
            (self.provider_transaction_id, "provider_transaction_id"),
            (self.provider_order_id, "provider_order_id"),
            (self.provider_trade_id, "provider_trade_id"),
        ):
            if value is not None and (type(value) is not str or not value):
                raise PaperPersistenceContractError(f"{name} is invalid")
        if type(self.attributable) is not bool or type(self.contradictory) is not bool:
            raise PaperPersistenceContractError("transaction flags are invalid")


@dataclass(frozen=True, slots=True)
class PaperReconciliationRead:
    """A normalized read plus typed facts used by the coordinator."""

    observation: PaperBrokerObservation
    state: PaperReconciliationReadState
    fill: BrokerFillFacts | None = None
    rejection: BrokerRejection | None = None
    terminal_transaction_id: str | None = None
    trade_id: str | None = None
    protection: ProtectionConfirmation | None = None
    attributable: bool = True
    protection_drift: bool = False
    unexpected_exposure: bool = False
    range_truncated: bool = False
    transactions: tuple[PaperReconciliationTransaction, ...] = ()

    def __post_init__(self) -> None:
        if type(self.observation) is not PaperBrokerObservation:
            raise PaperPersistenceContractError("reconciliation observation is invalid")
        if type(self.state) is not PaperReconciliationReadState:
            raise PaperPersistenceContractError("reconciliation read state is invalid")
        if self.observation.attempt_id != self.attempt_id:
            raise PaperPersistenceContractError(
                "reconciliation observation does not belong to read"
            )
        if self.fill is not None and type(self.fill) is not BrokerFillFacts:
            raise PaperPersistenceContractError("reconciliation Fill is invalid")
        if self.rejection is not None and type(self.rejection) is not BrokerRejection:
            raise PaperPersistenceContractError("reconciliation rejection is invalid")
        if (
            self.protection is not None
            and type(self.protection) is not ProtectionConfirmation
        ):
            raise PaperPersistenceContractError("reconciliation protection is invalid")
        if self.transactions and self.state not in (
            PaperReconciliationReadState.RANGE,
            PaperReconciliationReadState.CONFLICT,
        ):
            raise PaperPersistenceContractError(
                "transaction candidates require a range read"
            )
        if (
            type(self.attributable) is not bool
            or type(self.protection_drift) is not bool
        ):
            raise PaperPersistenceContractError("reconciliation flags are invalid")

    @property
    def attempt_id(self) -> UUID:
        return self.observation.attempt_id

    @property
    def frontier(self) -> str | None:
        return self.observation.last_transaction_id


class PaperReconciliationProvider(Protocol):
    """GET-only provider boundary consumed by the coordinator."""

    def read_order(
        self, context: PaperReconciliationContext
    ) -> PaperReconciliationRead: ...

    def read_transaction(
        self, context: PaperReconciliationContext, transaction_id: str
    ) -> PaperReconciliationRead: ...

    def read_trade(
        self, context: PaperReconciliationContext, trade_id: str
    ) -> PaperReconciliationRead: ...

    def read_account(
        self, context: PaperReconciliationContext
    ) -> PaperReconciliationRead: ...

    def read_transaction_range(
        self, context: PaperReconciliationContext, from_id: str, to_id: str
    ) -> PaperReconciliationRead: ...


@dataclass(frozen=True, slots=True)
class PaperReconciliationResult:
    """Safe result of one explicit reconciliation request."""

    run: PaperReconciliationRun
    reconciliation_status: ReconciliationStatus
    execution_outcome: PaperExecutionOutcome | None
    stale: bool = False


class PaperReconciliationError(RuntimeError):
    """A local reconciliation operation could not be durably completed."""


SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]


class PaperReconciliationCoordinator:
    """Run one finite, read-only reconciliation pass for one attempt."""

    def __init__(
        self,
        *,
        repository: PaperExecutionRepository,
        session_factory: SessionFactory,
        provider: PaperReconciliationProvider,
        clock: Clock | None = None,
        max_entry_transactions: int = MAX_ENTRY_RECONCILIATION_TRANSACTIONS,
    ) -> None:
        if type(max_entry_transactions) is not int or not (
            0 < max_entry_transactions <= MAX_ENTRY_RECONCILIATION_TRANSACTIONS
        ):
            raise PaperPersistenceContractError(
                "entry transaction bound is outside the frozen limit"
            )
        self._repository = repository
        self._session_factory = session_factory
        self._provider = provider
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_entry_transactions = max_entry_transactions

    def reconcile(
        self, attempt_id: UUID, *, read_budget: int = MAX_RECONCILIATION_READS
    ) -> PaperReconciliationResult:
        if type(attempt_id) is not UUID:
            raise PaperPersistenceContractError("attempt_id must be a UUID")
        if type(read_budget) is not int or not (
            0 < read_budget <= MAX_RECONCILIATION_READS
        ):
            raise PaperPersistenceContractError("reconciliation read budget is invalid")

        row, run_sequence, context = self._load_context(attempt_id)
        requested_at = self._now()
        read_started_at = self._now()
        reads: list[PaperReconciliationRead] = []
        findings: list[PaperReconciliationFindingCode] = []
        read_error = False
        budget_exhausted = False
        fill: BrokerFillFacts | None = None
        rejection: BrokerRejection | None = None
        protection: ProtectionConfirmation | None = None
        resulting_outcome = _row_outcome(row)
        status = ReconciliationStatus.UNRESOLVED
        block_code: str | None = None
        range_truncated = False
        conflict_detected = False

        def record(code: PaperReconciliationFindingCode) -> None:
            if code not in findings:
                findings.append(code)

        def read(
            call: Callable[[], PaperReconciliationRead],
        ) -> PaperReconciliationRead | None:
            nonlocal read_error, budget_exhausted
            if len(reads) >= read_budget:
                budget_exhausted = True
                record(PaperReconciliationFindingCode.UNRESOLVED)
                return None
            try:
                value = call()
                self._validate_provider_read(value, context)
            except Exception:
                read_error = True
                record(PaperReconciliationFindingCode.UNRESOLVED)
                return None
            reads.append(value)
            return value

        try:
            if fill is not None:  # pragma: no cover - defensive; row load owns Fill
                raise AssertionError
            durable_fill = _row_fill(row)
            if durable_fill is not None:
                fill = durable_fill
                trade = read(
                    lambda: self._provider.read_trade(
                        context, durable_fill.broker_trade_id
                    )
                )
                if trade is not None:
                    resulting_outcome, protection, status = self._consume_trade(
                        context,
                        trade,
                        current=(
                            _row_outcome(row)
                            or PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
                        ),
                        fill=fill,
                        findings=findings,
                    )
                else:
                    status = ReconciliationStatus.UNRESOLVED
                    record(PaperReconciliationFindingCode.UNRESOLVED)
            else:
                order = read(lambda: self._provider.read_order(context))
                terminal_proven = False
                if order is not None:
                    if (
                        not order.attributable
                        or order.state is PaperReconciliationReadState.CONFLICT
                    ):
                        status = ReconciliationStatus.CONFLICT
                        conflict_detected = True
                        block_code = "ENTRY_ATTRIBUTION_CONFLICT"
                        record(PaperReconciliationFindingCode.CONFLICT)
                    elif order.state is PaperReconciliationReadState.NOT_FOUND:
                        record(PaperReconciliationFindingCode.ENTRY_READBACK_NOT_FOUND)
                    elif order.state in (
                        PaperReconciliationReadState.FILLED,
                        PaperReconciliationReadState.CANCELLED,
                        PaperReconciliationReadState.REJECTED,
                    ):
                        if order.observation.provider_order_id is not None:
                            context = replace(
                                context,
                                provider_order_id=order.observation.provider_order_id,
                            )
                        terminal_id = cast(str | None, order.terminal_transaction_id)
                        terminal = (
                            read(
                                lambda: self._provider.read_transaction(
                                    context, terminal_id
                                )
                            )
                            if terminal_id is not None
                            else None
                        )
                        if terminal is not None:
                            terminal_finding_start = len(findings)
                            fill, resulting_outcome, terminal_proven = (
                                self._consume_entry_terminal(
                                    terminal,
                                    current=_row_outcome(row),
                                    findings=findings,
                                )
                            )
                            if (
                                PaperReconciliationFindingCode.CONFLICT
                                in findings[terminal_finding_start:]
                            ):
                                status = ReconciliationStatus.CONFLICT
                                conflict_detected = True
                                block_code = "ENTRY_ATTRIBUTION_CONFLICT"
                            if terminal.rejection is not None:
                                rejection = terminal.rejection
                            if fill is not None:
                                discovered_fill = fill
                                context = replace(
                                    context,
                                    provider_order_id=discovered_fill.broker_order_id,
                                    provider_trade_id=discovered_fill.broker_trade_id,
                                    fill_signed_units=discovered_fill.signed_units,
                                    fill_price=discovered_fill.price,
                                )
                                trade = read(
                                    lambda: self._provider.read_trade(
                                        context,
                                        discovered_fill.broker_trade_id,
                                    )
                                )
                                if trade is not None:
                                    resulting_outcome, protection, status = (
                                        self._consume_trade(
                                            context,
                                            trade,
                                            current=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
                                            fill=discovered_fill,
                                            findings=findings,
                                        )
                                    )
                                    if conflict_detected:
                                        status = ReconciliationStatus.CONFLICT
                                else:
                                    status = (
                                        ReconciliationStatus.CONFLICT
                                        if conflict_detected
                                        else ReconciliationStatus.UNRESOLVED
                                    )
                                    record(PaperReconciliationFindingCode.UNRESOLVED)
                        else:
                            record(PaperReconciliationFindingCode.UNRESOLVED)
                        if terminal_proven and fill is None and not conflict_detected:
                            status = ReconciliationStatus.CONSISTENT
                    if order.state is PaperReconciliationReadState.PENDING:
                        record(PaperReconciliationFindingCode.UNRESOLVED)

                if fill is None and not terminal_proven:
                    account = read(lambda: self._provider.read_account(context))
                    if account is not None:
                        if account.unexpected_exposure:
                            status = ReconciliationStatus.CONFLICT
                            conflict_detected = True
                            block_code = "UNATTRIBUTED_EXPOSURE"
                            record(PaperReconciliationFindingCode.UNATTRIBUTED_EXPOSURE)
                        frontier = account.frontier
                        if frontier is not None and self._needs_range(
                            context.pre_entry_transaction_id, frontier
                        ):
                            from_id, to_id, truncated = self._range_bounds(
                                context.pre_entry_transaction_id, frontier
                            )
                            range_truncated = truncated
                            range_read = read(
                                lambda: self._provider.read_transaction_range(
                                    context, from_id, to_id
                                )
                            )
                            if range_read is not None:
                                range_finding_start = len(findings)
                                range_fill, range_outcome, range_proven = (
                                    self._consume_range(
                                        range_read,
                                        current=_row_outcome(row),
                                        findings=findings,
                                    )
                                )
                                if (
                                    PaperReconciliationFindingCode.CONFLICT
                                    in findings[range_finding_start:]
                                ):
                                    status = ReconciliationStatus.CONFLICT
                                    conflict_detected = True
                                    block_code = "ENTRY_ATTRIBUTION_CONFLICT"
                                if range_read.rejection is not None:
                                    rejection = range_read.rejection
                                if range_fill is not None:
                                    fill = range_fill
                                    context = replace(
                                        context,
                                        provider_order_id=fill.broker_order_id,
                                        provider_trade_id=fill.broker_trade_id,
                                        fill_signed_units=fill.signed_units,
                                        fill_price=fill.price,
                                    )
                                    resulting_outcome = range_outcome
                                    trade = read(
                                        lambda: self._provider.read_trade(
                                            context, fill.broker_trade_id
                                        )
                                    )
                                    if trade is not None:
                                        resulting_outcome, protection, status = (
                                            self._consume_trade(
                                                context,
                                                trade,
                                                current=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
                                                fill=fill,
                                                findings=findings,
                                            )
                                        )
                                        if conflict_detected:
                                            status = ReconciliationStatus.CONFLICT
                                    else:
                                        status = (
                                            ReconciliationStatus.CONFLICT
                                            if conflict_detected
                                            else ReconciliationStatus.UNRESOLVED
                                        )
                                        record(
                                            PaperReconciliationFindingCode.UNRESOLVED
                                        )
                                elif range_proven:
                                    resulting_outcome = range_outcome
                                    terminal_proven = True
                                    if not conflict_detected:
                                        status = ReconciliationStatus.CONSISTENT
                            if truncated:
                                record(
                                    PaperReconciliationFindingCode.TRANSACTION_RANGE_TRUNCATED
                                )

                if fill is None and not terminal_proven and resulting_outcome is None:
                    resulting_outcome = PaperExecutionOutcome.UNKNOWN

            if fill is not None and resulting_outcome is None:
                resulting_outcome = PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
            if fill is not None and status is ReconciliationStatus.UNRESOLVED:
                record(PaperReconciliationFindingCode.PROTECTION_INCOMPLETE)
            if not findings and status is ReconciliationStatus.UNRESOLVED:
                record(PaperReconciliationFindingCode.UNRESOLVED)
        except Exception:
            read_error = True
            record(PaperReconciliationFindingCode.UNRESOLVED)

        if status is ReconciliationStatus.CONFLICT and block_code is None:
            block_code = "RECONCILIATION_CONFLICT"
        elif status is ReconciliationStatus.UNRESOLVED and block_code is None:
            block_code = "RECONCILIATION_UNRESOLVED"

        if (budget_exhausted or read_error) and not conflict_detected:
            run_status = PaperReconciliationRunStatus.FAILED
            status = ReconciliationStatus.UNRESOLVED
            block_code = "RECONCILIATION_READ_FAILED"
        elif status is ReconciliationStatus.CONFLICT or conflict_detected:
            status = ReconciliationStatus.CONFLICT
            run_status = PaperReconciliationRunStatus.CONFLICT
            record(PaperReconciliationFindingCode.CONFLICT)
        elif status is ReconciliationStatus.LIFECYCLE_ADVANCED:
            run_status = PaperReconciliationRunStatus.LIFECYCLE_ADVANCED
        elif status is ReconciliationStatus.CONSISTENT:
            run_status = PaperReconciliationRunStatus.PROVEN
        else:
            run_status = PaperReconciliationRunStatus.UNRESOLVED

        completed_at = self._now()
        frontier_observed = _highest_frontier(reads)
        frontier_applied = (
            None
            if range_truncated
            else self._max_numeric_frontier(
                row.last_applied_transaction_id or row.account_transaction_id,
                frontier_observed,
            )
        )
        run = PaperReconciliationRun(
            attempt_id=attempt_id,
            run_sequence=run_sequence,
            requested_at=requested_at,
            read_started_at=read_started_at,
            completed_at=completed_at,
            status=run_status,
            projection_version_observed=row.projection_version,
            read_count=len(reads),
            read_budget=read_budget,
            prior_execution_outcome=_row_outcome(row),
            resulting_execution_outcome=resulting_outcome,
            finding_codes=tuple(findings),
            frontier_before=(
                row.last_applied_transaction_id or row.account_transaction_id
            ),
            frontier_observed=frontier_observed,
            frontier_applied=frontier_applied,
            non_atomic_read_set=len(reads) > 1,
            diagnostic_summary=block_code or "",
            run_id=uuid4(),
        )
        linked_observations = tuple(
            replace(read.observation, reconciliation_run_id=run.run_id)
            for read in reads
        )
        stale = False
        try:
            session = self._session_factory()
            try:
                self._repository.apply_reconciliation_run(
                    session,
                    run,
                    reconciliation_status=status,
                    observations=linked_observations,
                    reconciliation_block_code=block_code,
                    fill=fill if self._fill_is_attributable(fill, context) else None,
                    protection=(
                        protection
                        if self._protection_is_applicable(
                            protection,
                            context,
                            _row_outcome(row),
                            fill,
                        )
                        else None
                    ),
                    rejection_code=rejection.detail_code if rejection else None,
                    rejection_broker_order_id=(
                        rejection.broker_order_id if rejection else None
                    ),
                    rejection_transaction_id=(
                        rejection.broker_transaction_id if rejection else None
                    ),
                )
                session.commit()
            except StaleReconciliationError:
                session.commit()
                stale = True
                run = replace(
                    run,
                    status=PaperReconciliationRunStatus.FAILED,
                    projection_version_applied=None,
                    finding_codes=tuple(
                        dict.fromkeys(
                            (
                                *run.finding_codes,
                                PaperReconciliationFindingCode.STALE_RECONCILIATION,
                            )
                        )
                    ),
                    diagnostic_summary="stale reconciliation projection",
                )
            except Exception as error:
                session.rollback()
                raise PaperReconciliationError(
                    "reconciliation result could not be committed"
                ) from error
            finally:
                session.close()
        except PaperReconciliationError:
            raise
        return PaperReconciliationResult(
            run=run,
            reconciliation_status=(
                ReconciliationStatus.UNRESOLVED if stale else status
            ),
            execution_outcome=resulting_outcome,
            stale=stale,
        )

    def _load_context(
        self, attempt_id: UUID
    ) -> tuple[PaperExecutionAttemptModel, int, PaperReconciliationContext]:
        session = self._session_factory()
        try:
            row = self._repository.get_attempt(session, attempt_id)
            if row is None:
                raise PaperAttemptNotFound(str(attempt_id))
            run_sequence = self._repository.next_reconciliation_sequence(
                session, attempt_id
            )
            take_profit_claimed = self._repository.has_mutation_claim(
                session, attempt_id, PaperMutationPhase.TAKE_PROFIT
            )
            if (
                row.provider != Provider.OANDA.value
                or row.environment != "PRACTICE"
                or row.base_currency != "USD"
                or row.instrument != "EUR_USD"
            ):
                raise PaperIdentityConflict(
                    "attempt is outside the supported PAPER scope"
                )
            direction = Direction(row.direction)
            signed_units = (
                row.requested_quantity
                if direction is Direction.LONG
                else -row.requested_quantity
            )
            context = PaperReconciliationContext(
                attempt_id=attempt_id,
                provider_account_id=row.provider_account_id,
                instrument=row.instrument,
                direction=direction,
                signed_requested_units=signed_units,
                approved_entry_price=row.approved_entry_price,
                stop_price=row.stop_price,
                client_order_id=row.client_order_id,
                client_trade_id=row.client_trade_id,
                client_stop_loss_order_id=row.client_stop_loss_order_id,
                client_take_profit_order_id=row.client_take_profit_order_id,
                provider_order_id=row.fill_broker_order_id,
                provider_trade_id=row.fill_trade_id,
                actual_target_price=row.actual_target_price,
                take_profit_claimed=take_profit_claimed,
                pre_entry_transaction_id=row.account_transaction_id,
                fill_signed_units=row.fill_signed_units,
                fill_price=row.fill_price,
                stop_loss_broker_order_id=row.stop_loss_broker_order_id,
                take_profit_broker_order_id=row.take_profit_broker_order_id,
            )
            return row, run_sequence, context
        finally:
            session.close()

    @staticmethod
    def _validate_provider_read(
        value: PaperReconciliationRead, context: PaperReconciliationContext
    ) -> None:
        if type(value) is not PaperReconciliationRead:
            raise PaperPersistenceContractError("provider returned an invalid read")
        observation = value.observation
        if (
            observation.attempt_id != context.attempt_id
            or observation.provider_account_id != context.provider_account_id
            or observation.instrument is not None
            and observation.instrument.value.replace("/", "_") != context.instrument
        ):
            raise PaperIdentityConflict("provider read identity does not match attempt")
        if observation.object_kind is PaperObservationObjectKind.ACCOUNT:
            if observation.instrument is not None:
                raise PaperIdentityConflict("account observation has an instrument")

    @staticmethod
    def _terminal_history_conflicts(
        current: PaperExecutionOutcome | None,
        observed: PaperExecutionOutcome,
    ) -> bool:
        return (
            current
            in (
                PaperExecutionOutcome.REJECTED,
                PaperExecutionOutcome.CANCELLED,
            )
            and observed is not current
        )

    @staticmethod
    def _consume_entry_terminal(
        read: PaperReconciliationRead,
        *,
        current: PaperExecutionOutcome | None,
        findings: list[PaperReconciliationFindingCode],
    ) -> tuple[BrokerFillFacts | None, PaperExecutionOutcome | None, bool]:
        if not read.attributable or read.state is PaperReconciliationReadState.CONFLICT:
            if PaperReconciliationFindingCode.CONFLICT not in findings:
                findings.append(PaperReconciliationFindingCode.CONFLICT)
            return None, current, False
        if read.fill is not None:
            if PaperReconciliationCoordinator._terminal_history_conflicts(
                current, PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
            ):
                findings.append(PaperReconciliationFindingCode.CONFLICT)
            if read.rejection is not None:
                findings.append(PaperReconciliationFindingCode.CONFLICT)
            findings.append(PaperReconciliationFindingCode.ENTRY_FILLED)
            return read.fill, PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE, True
        if (
            read.state is PaperReconciliationReadState.REJECTED
            and read.rejection is not None
        ):
            if PaperReconciliationCoordinator._terminal_history_conflicts(
                current, PaperExecutionOutcome.REJECTED
            ):
                findings.append(PaperReconciliationFindingCode.CONFLICT)
                return None, current, True
            findings.append(PaperReconciliationFindingCode.ENTRY_REJECTED)
            return None, PaperExecutionOutcome.REJECTED, True
        if read.state is PaperReconciliationReadState.CANCELLED:
            if PaperReconciliationCoordinator._terminal_history_conflicts(
                current, PaperExecutionOutcome.CANCELLED
            ):
                findings.append(PaperReconciliationFindingCode.CONFLICT)
                return None, current, True
            findings.append(PaperReconciliationFindingCode.ENTRY_CANCELLED)
            return None, PaperExecutionOutcome.CANCELLED, True
        findings.append(PaperReconciliationFindingCode.UNRESOLVED)
        return None, current, False

    def _consume_range(
        self,
        read: PaperReconciliationRead,
        *,
        current: PaperExecutionOutcome | None,
        findings: list[PaperReconciliationFindingCode],
    ) -> tuple[BrokerFillFacts | None, PaperExecutionOutcome | None, bool]:
        if read.range_truncated:
            findings.append(PaperReconciliationFindingCode.TRANSACTION_RANGE_TRUNCATED)
        candidates = [item for item in read.transactions if item.attributable]
        all_terminal = [
            item
            for item in read.transactions
            if item.state
            in (
                PaperReconciliationReadState.FILLED,
                PaperReconciliationReadState.REJECTED,
                PaperReconciliationReadState.CANCELLED,
            )
        ]
        if read.state is PaperReconciliationReadState.CONFLICT or any(
            not item.attributable for item in all_terminal
        ):
            findings.append(PaperReconciliationFindingCode.CONFLICT)
        fills = [item for item in candidates if item.fill is not None]
        no_fill_terminals = [
            item
            for item in candidates
            if item.fill is None
            and item.state
            in (
                PaperReconciliationReadState.REJECTED,
                PaperReconciliationReadState.CANCELLED,
            )
        ]
        if len(fills) == 1 and (
            no_fill_terminals
            or read.state is PaperReconciliationReadState.CONFLICT
            or len(all_terminal) != len(candidates)
        ):
            if PaperReconciliationCoordinator._terminal_history_conflicts(
                current, PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
            ):
                findings.append(PaperReconciliationFindingCode.CONFLICT)
            findings.append(PaperReconciliationFindingCode.ENTRY_FILLED)
            for item in no_fill_terminals:
                findings.append(
                    PaperReconciliationFindingCode.ENTRY_REJECTED
                    if item.state is PaperReconciliationReadState.REJECTED
                    else PaperReconciliationFindingCode.ENTRY_CANCELLED
                )
            return (
                fills[0].fill,
                PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
                True,
            )
        if len(candidates) > 1:
            if len(fills) != 1 or no_fill_terminals:
                findings.append(PaperReconciliationFindingCode.CONFLICT)
                return None, current, False
        selected = next(
            (
                item
                for item in candidates
                if item.fill is not None
                or item.state
                in (
                    PaperReconciliationReadState.REJECTED,
                    PaperReconciliationReadState.CANCELLED,
                )
            ),
            None,
        )
        if selected is None:
            if read.fill is not None or read.rejection is not None:
                return self._consume_entry_terminal(
                    read, current=current, findings=findings
                )
            if any(item.contradictory for item in read.transactions):
                findings.append(PaperReconciliationFindingCode.CONFLICT)
            else:
                findings.append(PaperReconciliationFindingCode.UNRESOLVED)
            return None, current, False
        selected_read = replace(
            read,
            state=selected.state,
            fill=selected.fill,
            rejection=selected.rejection,
            attributable=selected.attributable,
            transactions=(),
        )
        return self._consume_entry_terminal(
            selected_read, current=current, findings=findings
        )

    def _consume_trade(
        self,
        context: PaperReconciliationContext,
        read: PaperReconciliationRead,
        *,
        current: PaperExecutionOutcome,
        fill: BrokerFillFacts,
        findings: list[PaperReconciliationFindingCode],
    ) -> tuple[
        PaperExecutionOutcome,
        ProtectionConfirmation | None,
        ReconciliationStatus,
    ]:
        if read.state is PaperReconciliationReadState.NOT_FOUND:
            findings.append(PaperReconciliationFindingCode.UNRESOLVED)
            return current, None, ReconciliationStatus.UNRESOLVED
        if not read.attributable:
            findings.append(PaperReconciliationFindingCode.CONFLICT)
            return current, None, ReconciliationStatus.CONFLICT
        if not self._trade_matches_context(read, context, fill):
            findings.append(PaperReconciliationFindingCode.CONFLICT)
            return current, None, ReconciliationStatus.CONFLICT
        if read.state is PaperReconciliationReadState.CLOSED:
            findings.append(PaperReconciliationFindingCode.TRADE_LIFECYCLE_ADVANCED)
            return current, None, ReconciliationStatus.LIFECYCLE_ADVANCED
        if read.state is not PaperReconciliationReadState.OPEN:
            findings.append(PaperReconciliationFindingCode.CONFLICT)
            return current, None, ReconciliationStatus.CONFLICT
        protection = read.protection
        if protection is None:
            findings.append(PaperReconciliationFindingCode.UNRESOLVED)
            return current, None, ReconciliationStatus.UNRESOLVED
        if not self._fill_matches_context(fill, context):
            findings.append(PaperReconciliationFindingCode.CONFLICT)
            return current, None, ReconciliationStatus.CONFLICT
        if read.protection_drift or not self._protection_matches_context(
            protection, context, fill
        ):
            findings.append(PaperReconciliationFindingCode.PROTECTION_DRIFT)
            return current, None, ReconciliationStatus.CONFLICT
        exact = (
            protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
            and protection.take_profit_status is ProtectionLegStatus.CONFIRMED
            and protection.actual_target_price is not None
            and context.take_profit_claimed
            and (
                context.actual_target_price is None
                or protection.actual_target_price == context.actual_target_price
            )
        )
        if exact:
            findings.append(PaperReconciliationFindingCode.PROTECTION_CONFIRMED)
            return (
                PaperExecutionOutcome.FILLED_PROTECTED,
                protection,
                ReconciliationStatus.CONSISTENT,
            )
        if (
            protection.take_profit_status is ProtectionLegStatus.CONFIRMED
            and not context.take_profit_claimed
        ):
            findings.append(PaperReconciliationFindingCode.CONFLICT)
            return current, None, ReconciliationStatus.CONFLICT
        findings.append(PaperReconciliationFindingCode.PROTECTION_INCOMPLETE)
        return current, protection, ReconciliationStatus.UNRESOLVED

    @staticmethod
    def _fill_matches_context(
        fill: BrokerFillFacts, context: PaperReconciliationContext
    ) -> bool:
        if fill.signed_units != context.signed_requested_units:
            return False
        if context.direction is Direction.LONG:
            if fill.price > context.approved_entry_price or not (
                context.stop_price < fill.price
            ):
                return False
        else:
            if fill.price < context.approved_entry_price or not (
                context.stop_price > fill.price
            ):
                return False
        return (
            context.provider_order_id is None
            or fill.broker_order_id == context.provider_order_id
        ) and (
            context.provider_trade_id is None
            or fill.broker_trade_id == context.provider_trade_id
        )

    @staticmethod
    def _trade_matches_context(
        read: PaperReconciliationRead,
        context: PaperReconciliationContext,
        fill: BrokerFillFacts,
    ) -> bool:
        observation = read.observation
        return (
            read.trade_id == fill.broker_trade_id
            and observation.provider_trade_id == fill.broker_trade_id
            and observation.client_trade_id == context.client_trade_id
            and observation.signed_units == fill.signed_units
            and observation.price == fill.price
        )

    @staticmethod
    def _protection_matches_context(
        protection: ProtectionConfirmation,
        context: PaperReconciliationContext,
        fill: BrokerFillFacts,
    ) -> bool:
        if not PaperReconciliationCoordinator._fill_matches_context(fill, context):
            return False

        def leg_matches(
            order: BrokerProtectionOrder | None,
            status: ProtectionLegStatus,
            expected_client_id: str,
            expected_price: Decimal | None,
            expected_broker_id: str | None,
        ) -> bool:
            if order is None:
                return status is not ProtectionLegStatus.CONFIRMED
            if (
                expected_price is None
                or order.client_order_id != expected_client_id
                or (
                    expected_broker_id is not None
                    and order.broker_order_id != expected_broker_id
                )
            ):
                return False
            if order.price != expected_price:
                return False
            if status is ProtectionLegStatus.CONFIRMED:
                return order.state == "PENDING"
            if status is ProtectionLegStatus.REJECTED:
                return order.state in {"CANCELLED", "FILLED", "REJECTED"}
            if status is ProtectionLegStatus.UNKNOWN:
                return order.state not in {"PENDING", "CANCELLED", "FILLED", "REJECTED"}
            return False

        if not leg_matches(
            protection.stop_loss,
            protection.stop_loss_status,
            context.client_stop_loss_order_id,
            context.stop_price,
            context.stop_loss_broker_order_id,
        ):
            return False
        if context.take_profit_claimed:
            if not leg_matches(
                protection.take_profit,
                protection.take_profit_status,
                context.client_take_profit_order_id,
                context.actual_target_price,
                context.take_profit_broker_order_id,
            ):
                return False
            return protection.actual_target_price == context.actual_target_price
        return (
            protection.take_profit is None
            and protection.take_profit_status
            in (ProtectionLegStatus.NOT_ATTEMPTED, ProtectionLegStatus.UNKNOWN)
            and protection.actual_target_price is None
        )

    @staticmethod
    def _protection_is_applicable(
        protection: ProtectionConfirmation | None,
        context: PaperReconciliationContext,
        current: PaperExecutionOutcome | None,
        fill: BrokerFillFacts | None,
    ) -> bool:
        if protection is None or fill is None:
            return False
        if not PaperReconciliationCoordinator._protection_matches_context(
            protection, context, fill
        ):
            return False
        if protection.take_profit_status is ProtectionLegStatus.CONFIRMED:
            return context.take_profit_claimed
        return current is not PaperExecutionOutcome.FILLED_PROTECTED

    @staticmethod
    def _fill_is_attributable(
        fill: BrokerFillFacts | None, context: PaperReconciliationContext
    ) -> bool:
        return fill is not None and (
            PaperReconciliationCoordinator._fill_matches_context(fill, context)
        )

    def _needs_range(self, before: str, observed: str) -> bool:
        return self._numeric_id(observed) > self._numeric_id(before)

    def _range_bounds(self, before: str, observed: str) -> tuple[str, str, bool]:
        before_number = self._numeric_id(before)
        observed_number = self._numeric_id(observed)
        upper = min(observed_number, before_number + self._max_entry_transactions)
        return str(before_number + 1), str(upper), observed_number > upper

    @classmethod
    def _max_numeric_frontier(
        cls, current: str | None, proposed: str | None
    ) -> str | None:
        if current is None:
            return proposed
        if proposed is None:
            return current
        current_number = cls._numeric_id(current)
        proposed_number = cls._numeric_id(proposed)
        return proposed if proposed_number >= current_number else current

    @staticmethod
    def _numeric_id(value: str) -> int:
        if type(value) is not str or not value.isdigit():
            raise PaperPersistenceContractError("transaction frontier is not numeric")
        return int(value)

    def _now(self) -> datetime:
        value = self._clock()
        if (
            type(value) is not datetime
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise PaperPersistenceContractError("reconciliation clock is invalid")
        return value.astimezone(UTC)


def _row_outcome(row: PaperExecutionAttemptModel) -> PaperExecutionOutcome | None:
    return (
        PaperExecutionOutcome(row.execution_outcome) if row.execution_outcome else None
    )


def _row_fill(row: PaperExecutionAttemptModel) -> BrokerFillFacts | None:
    values = (
        row.fill_broker_order_id,
        row.fill_transaction_id,
        row.fill_trade_id,
        row.fill_signed_units,
        row.fill_price,
        row.fill_executed_at,
        row.fill_actual_initial_risk,
    )
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise PaperRepositoryError("database contains partial PAPER Fill facts")
    return BrokerFillFacts(
        cast(str, values[0]),
        cast(str, values[1]),
        cast(str, values[2]),
        cast(Decimal, values[3]),
        cast(Decimal, values[4]),
        cast(datetime, values[5]),
        cast(Decimal, values[6]),
    )


def _highest_frontier(reads: Sequence[PaperReconciliationRead]) -> str | None:
    values = [read.frontier for read in reads if read.frontier is not None]
    numeric = [(int(value), value) for value in values if value.isdigit()]
    return max(numeric)[1] if numeric else None


__all__ = [
    "MAX_ENTRY_RECONCILIATION_TRANSACTIONS",
    "MAX_RECONCILIATION_READS",
    "PaperReconciliationContext",
    "PaperReconciliationCoordinator",
    "PaperReconciliationError",
    "PaperReconciliationProvider",
    "PaperReconciliationRead",
    "PaperReconciliationReadState",
    "PaperReconciliationResult",
    "PaperReconciliationTransaction",
]
