"""The single-process PAPER runtime orchestration boundary.

This module owns cadence and ordering only.  Strategy evaluation, Risk, PAPER
05 execution, OANDA normalization, and GET-only reconciliation remain behind
their existing seams.  In particular, a durable claim is never treated as a
broker receipt and a process restart never dispatches an existing claim.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain import Action, FinancialPositionState, MarketSpecification
from backend.integrations.oanda.capabilities import OANDA_CAPABILITY
from backend.integrations.oanda.execution_account import (
    OandaPracticeAccountPropertiesNormalizationError,
    OandaPracticeExecutionAccountSnapshot,
)
from backend.integrations.oanda.source import OandaRequestError
from backend.paper.current_analytical_frontier import (
    AnalyticalFrontierDataError,
    AnalyticalFrontierError,
    CurrentAnalyticalFrontier,
    NativeM15Source,
    NoCurrentAnalyticalFrontierError,
    load_current_analytical_frontier,
)
from backend.paper.durable_execution import (
    PaperDurableExecutionApplication,
    PaperDurableExecutionPersistenceError,
    PaperDurableExecutionPreparation,
)
from backend.paper.execution import PaperExecutionOutcome, PaperExecutionRefusal
from backend.paper.persistence_contracts import PaperStrategyEvaluationReceipt
from backend.persistence.models import (
    PaperExecutionAttemptModel,
    PaperMutationClaimModel,
    PaperRuntimeCycleModel,
)
from backend.persistence.runtime_repository import (
    InvalidPaperRuntimeTransition,
    PaperRuntimeCycleConflict,
    PaperRuntimeOwnerLost,
    PaperRuntimeRepository,
    is_unsafe_paper_attempt,
)
from backend.persistence.strategy_repository import (
    StrategyRepository,
    version_to_domain,
)
from backend.risk import RiskConfig
from backend.strategies.registry import StrategyRegistry

from .activation import _activation_from_row  # pyright: ignore[reportPrivateUsage]
from .cycles import (
    PaperRuntimeAccountObservation,
    PaperRuntimeCycleAuthority,
    PaperRuntimeFrontierAlreadyConsumed,
    PaperRuntimeFrontierDuplicate,
    PaperRuntimeFrontierGap,
    PaperRuntimeStateAuthorityError,
    PaperRuntimeUnsupportedStrategyAction,
)
from .ownership import PaperRuntimeOwner
from .persistence_contracts import (
    PaperRuntimeActivation,
    PaperRuntimeCycleStatus,
    PaperRuntimeLifecycleState,
    PaperRuntimeOperationalPhase,
    PaperRuntimeOwnershipPhase,
    PaperRuntimePersistenceError,
)

SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]


class _PaperRuntimeFrontierFailure(PaperRuntimeStateAuthorityError):
    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        super().__init__(message)


def _default_risk_config(activation: PaperRuntimeActivation) -> RiskConfig:
    return RiskConfig(activation.risk_per_trade)


class PaperRuntimeAccountReader(Protocol):
    """A normalized, read-only current Account Details seam."""

    def read(self) -> object: ...


class PaperRuntimeCapabilityReader(Protocol):
    """A normalized, read-only provider capability proof seam.

    A successful read is the provider-specific proof.  Runtime orchestration
    deliberately does not inspect or reinterpret the provider payload.
    """

    def read(self) -> object: ...


class PaperRuntimeReconciliation(Protocol):
    """The existing bounded GET-only recovery seam."""

    def reconcile(self, attempt_id: UUID, *, read_budget: int = 8) -> object: ...


class PaperRuntimeTickOutcome(StrEnum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    WAITING_FRONTIER = "WAITING_FRONTIER"
    WAITING_DATA = "WAITING_DATA"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    EVALUATED = "EVALUATED"
    REFUSED = "REFUSED"
    EXECUTED = "EXECUTED"
    RECOVERED = "RECOVERED"
    STOPPED = "STOPPED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    OWNER_LOST = "OWNER_LOST"


@dataclass(frozen=True, slots=True)
class PaperRuntimeStartupResult:
    """Bounded evidence from one ownership/startup attempt."""

    outcome: PaperRuntimeTickOutcome
    activation_id: UUID | None = None
    lifecycle_state: PaperRuntimeLifecycleState | None = None
    owner_acquired: bool = False
    reason_code: str | None = None

    @property
    def started(self) -> bool:
        return self.outcome is PaperRuntimeTickOutcome.STARTING or (
            self.lifecycle_state is PaperRuntimeLifecycleState.RUNNING
        )

    def to_json(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "activation_id": str(self.activation_id) if self.activation_id else None,
            "lifecycle_state": (
                self.lifecycle_state.value if self.lifecycle_state else None
            ),
            "owner_acquired": self.owner_acquired,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class PaperRuntimeTickResult:
    """One bounded poll result; no raw provider response is retained."""

    outcome: PaperRuntimeTickOutcome
    activation_id: UUID | None = None
    cycle_id: UUID | None = None
    decision: Action | None = None
    execution_outcome: PaperExecutionOutcome | None = None
    reason_code: str | None = None

    @property
    def status(self) -> PaperRuntimeTickOutcome:
        return self.outcome

    def to_json(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "activation_id": str(self.activation_id) if self.activation_id else None,
            "cycle_id": str(self.cycle_id) if self.cycle_id else None,
            "decision": self.decision.value if self.decision else None,
            "execution_outcome": (
                self.execution_outcome.value if self.execution_outcome else None
            ),
            "reason_code": self.reason_code,
        }


class PaperRuntimeOrchestrator:
    """Run one explicitly activated local PAPER session.

    ``startup`` acquires the singleton owner and is safe to call repeatedly.
    ``tick`` performs at most one frontier evaluation.  ``run`` sleeps on the
    fixed fifteen-second cadence and never performs missed-frontier catch-up.
    """

    def __init__(
        self,
        *,
        owner: PaperRuntimeOwner,
        session_factory: SessionFactory,
        strategy_registry: StrategyRegistry,
        analytical_source: NativeM15Source,
        account_reader: PaperRuntimeAccountReader,
        capability_reader: PaperRuntimeCapabilityReader | None = None,
        strategy_repository: StrategyRepository | None = None,
        runtime_repository: PaperRuntimeRepository | None = None,
        cycle_authority: PaperRuntimeCycleAuthority | None = None,
        durable_execution: PaperDurableExecutionApplication | None = None,
        reconciliation: PaperRuntimeReconciliation | None = None,
        market_specification: MarketSpecification | None = None,
        risk_config_factory: (
            Callable[[PaperRuntimeActivation], RiskConfig] | None
        ) = None,
        clock: Clock | None = None,
    ) -> None:
        self._owner = owner
        self._session_factory = session_factory
        self._strategy_registry = strategy_registry
        self._strategy_repository = strategy_repository or StrategyRepository()
        self._repository = runtime_repository or PaperRuntimeRepository()
        self._cycle_authority = cycle_authority or PaperRuntimeCycleAuthority(
            self._repository, clock=clock
        )
        self._analytical_source = analytical_source
        self._account_reader = account_reader
        self._capability_reader = capability_reader
        self._durable_execution = durable_execution
        self._reconciliation = reconciliation
        self._market_specification = (
            market_specification or OANDA_CAPABILITY.market_specification()
        )
        self._risk_config_factory: Callable[[PaperRuntimeActivation], RiskConfig] = (
            risk_config_factory or _default_risk_config
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._activation_id: UUID | None = None
        self._started = False

    @property
    def owner(self) -> PaperRuntimeOwner:
        return self._owner

    @property
    def activation_id(self) -> UUID | None:
        return self._activation_id

    @property
    def running(self) -> bool:
        return self._started and self._owner.acquired

    def startup(self) -> PaperRuntimeStartupResult:
        """Acquire ownership and recover the one active activation, if any."""
        try:
            ownership = self._owner.try_acquire()
        except PaperRuntimeOwnerLost:
            return PaperRuntimeStartupResult(PaperRuntimeTickOutcome.OWNER_LOST)
        except Exception:
            return PaperRuntimeStartupResult(PaperRuntimeTickOutcome.FAILED)
        if ownership is None:
            return PaperRuntimeStartupResult(
                PaperRuntimeTickOutcome.IDLE,
                owner_acquired=False,
                reason_code="RUNTIME_OWNER_PRESENT",
            )

        try:
            result = self._start_active_activation()
        except PaperRuntimeOwnerLost:
            self._started = False
            return PaperRuntimeStartupResult(
                PaperRuntimeTickOutcome.OWNER_LOST, owner_acquired=True
            )
        except Exception:
            self._started = False
            self._owner.close()
            return PaperRuntimeStartupResult(
                PaperRuntimeTickOutcome.FAILED, owner_acquired=True
            )
        return result

    def tick(self) -> PaperRuntimeTickResult:
        """Process at most one newly observed completed M15 frontier."""
        if not self._owner.acquired:
            startup = self.startup()
            return PaperRuntimeTickResult(
                startup.outcome,
                activation_id=startup.activation_id,
                reason_code=startup.reason_code,
            )
        if not self._started:
            startup = self._start_active_activation()
            if startup.outcome is not PaperRuntimeTickOutcome.STARTING:
                return PaperRuntimeTickResult(
                    startup.outcome,
                    activation_id=startup.activation_id,
                    reason_code=startup.reason_code,
                )

        activation = self._current_activation()
        if activation is None:
            self._started = False
            self._activation_id = None
            return PaperRuntimeTickResult(PaperRuntimeTickOutcome.IDLE)
        if activation.lifecycle_state is PaperRuntimeLifecycleState.STOP_REQUESTED:
            self._finalize_stop(activation.activation_id)
            self._started = False
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.STOPPED,
                activation_id=activation.activation_id,
                reason_code="OPERATOR_STOP",
            )
        if activation.lifecycle_state is not PaperRuntimeLifecycleState.RUNNING:
            self._started = False
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                reason_code=activation.state_reason_code,
            )

        try:
            self._heartbeat(PaperRuntimeOwnershipPhase.RUNNING)
            now = self._now()
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id)
        try:
            frontier = self._read_frontier(activation, now)
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id)
        except _PaperRuntimeFrontierFailure as error:
            return self._block(activation.activation_id, error.reason_code)
        except PaperRuntimeStateAuthorityError:
            return self._block(activation.activation_id, "FRONTIER_INVALID")
        except Exception:
            return self._block(activation.activation_id, "FRONTIER_READ_FAILED")
        if frontier is None:
            return self._waiting_result(activation.activation_id)

        # A STOP may have linearized while the read-only frontier request was in
        # flight.  Recheck before the account read and before cycle reservation.
        activation = self._current_activation()
        if activation is None:
            return PaperRuntimeTickResult(PaperRuntimeTickOutcome.IDLE)
        if activation.lifecycle_state is PaperRuntimeLifecycleState.STOP_REQUESTED:
            self._finalize_stop(activation.activation_id)
            self._started = False
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.STOPPED,
                activation_id=activation.activation_id,
                reason_code="OPERATOR_STOP",
            )
        if activation.lifecycle_state is not PaperRuntimeLifecycleState.RUNNING:
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                reason_code=activation.state_reason_code,
            )

        try:
            with self._session_factory() as session:
                observation = self._read_observation(session, activation)
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id)
        except Exception as error:
            if self._is_transient(error):
                try:
                    self._set_operational_phase(
                        activation.activation_id,
                        PaperRuntimeOperationalPhase.WAITING_PROVIDER,
                        "ACCOUNT_READ_UNAVAILABLE",
                    )
                except PaperRuntimeOwnerLost:
                    return self._owner_lost(activation.activation_id)
                return PaperRuntimeTickResult(
                    PaperRuntimeTickOutcome.WAITING_PROVIDER,
                    activation_id=activation.activation_id,
                    reason_code="ACCOUNT_READ_UNAVAILABLE",
                )
            return self._block(
                activation.activation_id,
                "ACCOUNT_STATE_INVALID",
            )

        try:
            with self._session_factory() as session:
                with session.begin():
                    self._owner.assert_current(
                        session, activation_id=activation.activation_id
                    )
                    row = self._repository.get_activation(
                        session, activation.activation_id, for_update=True
                    )
                    if row is None:
                        raise PaperRuntimeOwnerLost("active activation disappeared")
                    current = _activation_from_row(session, row)
                    if (
                        current.lifecycle_state
                        is not PaperRuntimeLifecycleState.RUNNING
                    ):
                        raise InvalidPaperRuntimeTransition(
                            "activation stopped before cycle reservation"
                        )
                    reserved_cycle = self._cycle_authority.reserve_cycle(
                        session,
                        current,
                        frontier,
                        observation,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                    cycle_row = self._repository.transition_cycle(
                        session,
                        cast(PaperRuntimeCycleModel, reserved_cycle).cycle_id,
                        PaperRuntimeCycleStatus.EVALUATING,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                    cycle_id = cycle_row.cycle_id
        except (PaperRuntimeFrontierDuplicate, PaperRuntimeFrontierAlreadyConsumed):
            self._set_operational_phase(
                activation.activation_id,
                PaperRuntimeOperationalPhase.WAITING_FRONTIER,
                "FRONTIER_ALREADY_CONSUMED",
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.WAITING_FRONTIER,
                activation_id=activation.activation_id,
                reason_code="FRONTIER_ALREADY_CONSUMED",
            )
        except PaperRuntimeFrontierGap:
            return self._block(activation.activation_id, "FRONTIER_GAP")
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id)
        except InvalidPaperRuntimeTransition:
            latest = self._current_activation()
            if (
                latest is not None
                and latest.lifecycle_state is PaperRuntimeLifecycleState.STOP_REQUESTED
            ):
                self._finalize_stop(latest.activation_id)
                self._started = False
                return PaperRuntimeTickResult(
                    PaperRuntimeTickOutcome.STOPPED,
                    activation_id=latest.activation_id,
                    reason_code="OPERATOR_STOP",
                )
            return self._block(activation.activation_id, "ENTRY_FENCE_ACTIVE")
        except (PaperRuntimeStateAuthorityError, PaperRuntimeCycleConflict):
            return self._block(activation.activation_id, "RUNTIME_STATE_INVALID")
        except Exception:
            return self._block(activation.activation_id, "CYCLE_RESERVATION_FAILED")

        try:
            with self._session_factory() as session:
                receipt = self._cycle_authority.evaluate_cycle(
                    session,
                    activation,
                    frontier,
                    observation,
                    strategy_repository=self._strategy_repository,
                    strategy_registry=self._strategy_registry,
                    analytical_source=self._analytical_source,
                    market_specification=self._market_specification,
                    now=now,
                )
        except PaperRuntimeUnsupportedStrategyAction as error:
            if error.receipt is not None:
                self._persist_blocked_evaluation(
                    activation,
                    cycle_id,
                    error.receipt,
                    "UNSUPPORTED_STRATEGY_ACTION",
                )
            else:
                self._block_cycle_and_activation(
                    activation.activation_id, cycle_id, "UNSUPPORTED_STRATEGY_ACTION"
                )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                reason_code="UNSUPPORTED_STRATEGY_ACTION",
            )
        except Exception:
            self._block_cycle_and_activation(
                activation.activation_id, cycle_id, "STRATEGY_EVALUATION_FAILED"
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                reason_code="STRATEGY_EVALUATION_FAILED",
            )

        decision = receipt.evaluation.decision
        if not self._is_supported_opening(decision.action, decision.entry_policy.value):
            if decision.action is Action.NO_ACTION:
                persistence_failure = self._persist_evaluation_or_block(
                    activation,
                    cycle_id,
                    receipt,
                    PaperRuntimeCycleStatus.NO_ACTION,
                    decision=decision.action,
                )
                if persistence_failure is not None:
                    return persistence_failure
                try:
                    self._set_operational_phase(
                        activation.activation_id,
                        PaperRuntimeOperationalPhase.WAITING_FRONTIER,
                        None,
                    )
                except PaperRuntimeOwnerLost:
                    return self._owner_lost(activation.activation_id, cycle_id)
                except Exception:
                    return self._block(
                        activation.activation_id,
                        "OPERATIONAL_STATE_UNCERTAIN",
                        cycle_id,
                    )
                return PaperRuntimeTickResult(
                    PaperRuntimeTickOutcome.EVALUATED,
                    activation_id=activation.activation_id,
                    cycle_id=cycle_id,
                    decision=decision.action,
                )
            try:
                self._persist_blocked_evaluation(
                    activation, cycle_id, receipt, "UNSUPPORTED_STRATEGY_ACTION"
                )
            except PaperRuntimeOwnerLost:
                return self._owner_lost(activation.activation_id, cycle_id)
            except Exception:
                return self._block(
                    activation.activation_id,
                    "BLOCKED_EVALUATION_PERSISTENCE_FAILED",
                    cycle_id,
                )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code="UNSUPPORTED_STRATEGY_ACTION",
            )

        if (
            observation.financial_position_state is not FinancialPositionState.FLAT
            or observation.pending_order_count != 0
        ):
            refusal_reason = (
                "ENTRY_STATE_NOT_FLAT"
                if observation.financial_position_state
                is not FinancialPositionState.FLAT
                else "ENTRY_PENDING_ORDERS"
            )
            persistence_failure = self._persist_evaluation_or_block(
                activation,
                cycle_id,
                receipt,
                PaperRuntimeCycleStatus.REFUSED,
                reason_code=refusal_reason,
                decision=decision.action,
            )
            if persistence_failure is not None:
                return persistence_failure
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.REFUSED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code=refusal_reason,
            )

        if self._durable_execution is None:
            self._persist_blocked_evaluation(
                activation, cycle_id, receipt, "EXECUTION_UNAVAILABLE"
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code="EXECUTION_UNAVAILABLE",
            )

        try:
            prepared = self._durable_execution.prepare_entry_claim(
                receipt,
                config=self._risk_config_factory(activation),
            )
        except Exception:
            self._persist_blocked_evaluation(
                activation, cycle_id, receipt, "PAPER_PREPARATION_FAILED"
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code="PAPER_PREPARATION_FAILED",
            )

        if isinstance(prepared, PaperExecutionRefusal):
            reason = _bounded_reason(prepared.detail_code, "PAPER_EXECUTION_REFUSED")
            persistence_failure = self._persist_evaluation_or_block(
                activation,
                cycle_id,
                receipt,
                PaperRuntimeCycleStatus.REFUSED,
                reason_code=reason,
                decision=decision.action,
            )
            if persistence_failure is not None:
                return persistence_failure
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.REFUSED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code=reason,
            )
        try:
            claim_id = self._persist_entry_claim(
                activation, cycle_id, receipt, prepared
            )
        except InvalidPaperRuntimeTransition:
            latest = self._current_activation()
            if (
                latest is not None
                and latest.lifecycle_state is PaperRuntimeLifecycleState.STOP_REQUESTED
            ):
                self._finalize_stop(latest.activation_id)
                self._started = False
                return PaperRuntimeTickResult(
                    PaperRuntimeTickOutcome.STOPPED,
                    activation_id=activation.activation_id,
                    cycle_id=cycle_id,
                    decision=decision.action,
                    reason_code="OPERATOR_STOP",
                )
            return self._block(activation.activation_id, "ENTRY_FENCE_ACTIVE", cycle_id)
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id, cycle_id)
        except Exception:
            self._block_cycle_and_activation(
                activation.activation_id, cycle_id, "ENTRY_CLAIM_COMMIT_FAILED"
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code="ENTRY_CLAIM_COMMIT_FAILED",
            )

        try:
            result = self._durable_execution.submit_claimed_entry(
                prepared,
                entry_claim_id=claim_id,
                mutation_guard=lambda: self._assert_mutation_owner(
                    activation.activation_id
                ),
                take_profit_claimed_callback=lambda _claim_id: (
                    self._mark_cycle_take_profit_claimed(cycle_id)
                ),
            )
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id, cycle_id)
        except PaperDurableExecutionPersistenceError:
            self._block_cycle_and_activation(
                activation.activation_id,
                cycle_id,
                "POST_CLAIM_PERSISTENCE_UNCERTAIN",
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code="POST_CLAIM_PERSISTENCE_UNCERTAIN",
            )
        except Exception:
            self._block_cycle_and_activation(
                activation.activation_id, cycle_id, "EXECUTION_FAILED"
            )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                reason_code="EXECUTION_FAILED",
            )

        if result.outcome in {
            PaperExecutionOutcome.REJECTED,
            PaperExecutionOutcome.CANCELLED,
        }:
            try:
                self._resolve_cycle(cycle_id, filled=False)
            except PaperRuntimeOwnerLost:
                return self._owner_lost(activation.activation_id, cycle_id)
            except Exception:
                self._block_cycle_and_activation(
                    activation.activation_id,
                    cycle_id,
                    "CYCLE_RESOLUTION_UNCERTAIN",
                )
                return PaperRuntimeTickResult(
                    PaperRuntimeTickOutcome.BLOCKED,
                    activation_id=activation.activation_id,
                    cycle_id=cycle_id,
                    decision=decision.action,
                    execution_outcome=result.outcome,
                    reason_code="CYCLE_RESOLUTION_UNCERTAIN",
                )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.EXECUTED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                execution_outcome=result.outcome,
            )
        if result.outcome is PaperExecutionOutcome.FILLED_PROTECTED:
            try:
                self._resolve_cycle(cycle_id, filled=True)
            except PaperRuntimeOwnerLost:
                return self._owner_lost(activation.activation_id, cycle_id)
            except Exception:
                self._block_cycle_and_activation(
                    activation.activation_id,
                    cycle_id,
                    "CYCLE_RESOLUTION_UNCERTAIN",
                )
                return PaperRuntimeTickResult(
                    PaperRuntimeTickOutcome.BLOCKED,
                    activation_id=activation.activation_id,
                    cycle_id=cycle_id,
                    decision=decision.action,
                    execution_outcome=result.outcome,
                    reason_code="CYCLE_RESOLUTION_UNCERTAIN",
                )
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.EXECUTED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision.action,
                execution_outcome=result.outcome,
            )

        self._block_cycle_and_activation(
            activation.activation_id, cycle_id, "EXECUTION_UNCERTAIN"
        )
        return PaperRuntimeTickResult(
            PaperRuntimeTickOutcome.BLOCKED,
            activation_id=activation.activation_id,
            cycle_id=cycle_id,
            decision=decision.action,
            execution_outcome=result.outcome,
            reason_code="EXECUTION_UNCERTAIN",
        )

    def run(self, stop_event: object) -> int:
        """Run fixed-cadence ticks until the caller's stop event is set."""
        wait = getattr(stop_event, "wait", None)
        is_set = getattr(stop_event, "is_set", None)
        if not callable(wait) or not callable(is_set):
            raise PaperRuntimePersistenceError(
                "stop_event must provide wait and is_set"
            )
        if bool(is_set()):
            self.close()
            return 0
        self.startup()
        while not bool(is_set()):
            try:
                self.tick()
            except PaperRuntimeOwnerLost:
                break
            except Exception:
                if self._activation_id is not None:
                    self._block(self._activation_id, "RUNTIME_FATAL_ERROR")
                break
            # The event wait is the only cadence clock.  It does not catch up
            # missed bars and permits a prompt process shutdown.
            wait(15.0)
        self.close()
        return 0

    def close(self) -> None:
        """Release the live owner without inventing a trader STOP request."""
        self._started = False
        self._owner.close()

    def _start_active_activation(self) -> PaperRuntimeStartupResult:
        with self._session_factory() as session:
            with session.begin():
                row = self._repository.get_active_activation(session, for_update=True)
                if row is None:
                    self._activation_id = None
                    return PaperRuntimeStartupResult(
                        PaperRuntimeTickOutcome.IDLE, owner_acquired=True
                    )
                activation_id = row.activation_id
                self._owner.attach_activation(session, activation_id)
                lifecycle = PaperRuntimeLifecycleState(row.lifecycle_state)
                if lifecycle in {
                    PaperRuntimeLifecycleState.REQUESTED,
                    PaperRuntimeLifecycleState.RUNNING,
                }:
                    self._repository.transition_activation(
                        session,
                        activation_id,
                        PaperRuntimeLifecycleState.STARTING,
                        reason_code="RUNTIME_STARTING",
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                elif lifecycle is PaperRuntimeLifecycleState.STARTING:
                    self._repository.transition_activation(
                        session,
                        activation_id,
                        PaperRuntimeLifecycleState.STARTING,
                        reason_code="RUNTIME_STARTING",
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                self._activation_id = activation_id

        self._set_owner_phase(PaperRuntimeOwnershipPhase.STARTING)
        if self._recover_interrupted(activation_id):
            self._started = False
            current = self._current_activation()
            return PaperRuntimeStartupResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation_id,
                lifecycle_state=current.lifecycle_state if current else None,
                owner_acquired=True,
                reason_code=current.state_reason_code if current else None,
            )

        try:
            with self._session_factory() as session:
                activation = self._activation_for_id(session, activation_id)
                if activation is None:
                    raise PaperRuntimeOwnerLost("activation disappeared during startup")
                if (
                    activation.lifecycle_state
                    is PaperRuntimeLifecycleState.STOP_REQUESTED
                ):
                    self._finalize_stop(activation_id)
                    return PaperRuntimeStartupResult(
                        PaperRuntimeTickOutcome.STOPPED,
                        activation_id=activation_id,
                        lifecycle_state=PaperRuntimeLifecycleState.STOPPED,
                        owner_acquired=True,
                        reason_code="OPERATOR_STOP",
                    )
                self._validate_strategy_registry(session, activation)
                self._read_startup_capability()
                observation = self._read_observation(session, activation)
                if activation.strategy_state is None:
                    if (
                        observation.financial_position_state
                        is not FinancialPositionState.FLAT
                        or observation.pending_order_count != 0
                    ):
                        self._block_in_transaction(
                            session, activation_id, "BOOTSTRAP_REQUIRES_FLAT"
                        )
                        self._started = False
                        return PaperRuntimeStartupResult(
                            PaperRuntimeTickOutcome.BLOCKED,
                            activation_id=activation_id,
                            lifecycle_state=PaperRuntimeLifecycleState.BLOCKED,
                            owner_acquired=True,
                            reason_code="BOOTSTRAP_REQUIRES_FLAT",
                        )
                else:
                    self._cycle_authority.validate_activation_state(
                        replace(
                            activation,
                            lifecycle_state=PaperRuntimeLifecycleState.RUNNING,
                        )
                    )
        except PaperRuntimeOwnerLost:
            raise
        except OandaPracticeAccountPropertiesNormalizationError:
            self._block(activation_id, "STARTUP_CAPABILITY_INVALID")
            return PaperRuntimeStartupResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation_id,
                lifecycle_state=PaperRuntimeLifecycleState.BLOCKED,
                owner_acquired=True,
                reason_code="STARTUP_CAPABILITY_INVALID",
            )
        except Exception as error:
            if self._is_transient(error):
                self._set_operational_phase(
                    activation_id,
                    PaperRuntimeOperationalPhase.WAITING_PROVIDER,
                    "STARTUP_READ_UNAVAILABLE",
                )
                return PaperRuntimeStartupResult(
                    PaperRuntimeTickOutcome.STARTING,
                    activation_id=activation_id,
                    lifecycle_state=PaperRuntimeLifecycleState.STARTING,
                    owner_acquired=True,
                    reason_code="STARTUP_READ_UNAVAILABLE",
                )
            self._block(activation_id, "STARTUP_SAFETY_CHECK_FAILED")
            return PaperRuntimeStartupResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation_id,
                lifecycle_state=PaperRuntimeLifecycleState.BLOCKED,
                owner_acquired=True,
                reason_code="STARTUP_SAFETY_CHECK_FAILED",
            )

        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session, activation_id=activation_id)
                self._repository.transition_activation(
                    session,
                    activation_id,
                    PaperRuntimeLifecycleState.RUNNING,
                    reason_code="RUNTIME_RUNNING",
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )
        self._set_owner_phase(PaperRuntimeOwnershipPhase.RUNNING)
        self._started = True
        return PaperRuntimeStartupResult(
            PaperRuntimeTickOutcome.STARTING,
            activation_id=activation_id,
            lifecycle_state=PaperRuntimeLifecycleState.RUNNING,
            owner_acquired=True,
        )

    def _recover_interrupted(self, activation_id: UUID) -> bool:
        """Recover claims with GET-only P05 reconciliation before RUNNING."""
        with self._session_factory() as session:
            cycles = self._repository.list_cycles(session, activation_id)
        for cycle in cycles:
            status = PaperRuntimeCycleStatus(cycle.cycle_status)
            if status in {
                PaperRuntimeCycleStatus.CLAIMED,
                PaperRuntimeCycleStatus.EVALUATING,
            }:
                with self._session_factory() as session:
                    with session.begin():
                        self._repository.transition_cycle(
                            session,
                            cycle.cycle_id,
                            PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
                            owner_id=self._owner.owner_id,
                            owner_generation=self._owner.owner_generation,
                        )
                self._block(activation_id, "RECOVERY_REQUIRED")
                return True
            if status not in {
                PaperRuntimeCycleStatus.ENTRY_CLAIMED,
                PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
                PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
            }:
                continue
            if cycle.attempt_id is None:
                self._block(activation_id, "RECOVERY_ATTEMPT_MISSING")
                return True
            if self._reconciliation is None:
                self._block(activation_id, "RECONCILIATION_UNAVAILABLE")
                return True
            try:
                self._set_operational_phase(
                    activation_id,
                    PaperRuntimeOperationalPhase.RECOVERING,
                    "CLAIM_RECOVERY",
                )
                self._reconciliation.reconcile(cycle.attempt_id)
            except Exception:
                self._mark_cycle_blocked_if_possible(
                    cycle.cycle_id, "RECONCILIATION_FAILED"
                )
                self._block(activation_id, "RECONCILIATION_FAILED")
                return True
            with self._session_factory() as session:
                attempt = session.get(PaperExecutionAttemptModel, cycle.attempt_id)
                refreshed_cycle = self._repository.get_cycle(session, cycle.cycle_id)
                if attempt is None or refreshed_cycle is None:
                    self._block(activation_id, "RECOVERY_EVIDENCE_MISSING")
                    return True
                outcome = attempt.execution_outcome
                take_profit_claimed = (
                    session.scalar(
                        select(PaperMutationClaimModel.claim_id).where(
                            PaperMutationClaimModel.attempt_id == cycle.attempt_id,
                            PaperMutationClaimModel.phase == "TAKE_PROFIT",
                        )
                    )
                    is not None
                )
                safe_terminal = not is_unsafe_paper_attempt(
                    outcome, attempt.reconciliation_status
                ) and (
                    outcome in {"REJECTED", "CANCELLED"}
                    or outcome == "FILLED_PROTECTED"
                    and take_profit_claimed
                )
            if not safe_terminal:
                self._mark_cycle_blocked_if_possible(
                    cycle.cycle_id, "RECOVERY_UNRESOLVED"
                )
                self._block(activation_id, "RECOVERY_UNRESOLVED")
                return True
            self._complete_recovered_cycle(
                cycle.cycle_id,
                status=status,
                filled=outcome == "FILLED_PROTECTED",
            )
        return False

    def _read_frontier(
        self, activation: PaperRuntimeActivation, now: datetime
    ) -> CurrentAnalyticalFrontier | None:
        try:
            with self._session_factory() as session:
                version_row = self._strategy_repository.get_version(
                    session, activation.strategy_version_id
                )
                if version_row is None:
                    raise PaperRuntimeStateAuthorityError("StrategyVersion is missing")
                warm_up = version_to_domain(
                    version_row
                ).required_historical_context_bars
                if activation.strategy_state is not None:
                    warm_up = max(warm_up, 1)
            return load_current_analytical_frontier(
                self._analytical_source,
                now=now,
                warm_up_m15_bars=warm_up,
            )
        except PaperRuntimeOwnerLost:
            raise
        except NoCurrentAnalyticalFrontierError:
            self._set_operational_phase(
                activation.activation_id,
                PaperRuntimeOperationalPhase.WAITING_FRONTIER,
                "NO_CURRENT_FRONTIER",
            )
            return None
        except OandaRequestError as error:
            if self._is_transient(error):
                self._set_operational_phase(
                    activation.activation_id,
                    PaperRuntimeOperationalPhase.WAITING_DATA,
                    "FRONTIER_READ_UNAVAILABLE",
                )
                return None
            raise _PaperRuntimeFrontierFailure(
                "FRONTIER_PROVIDER_UNSAFE", "frontier provider state is unsafe"
            ) from error
        except (httpx.RequestError, TimeoutError, ConnectionError):
            self._set_operational_phase(
                activation.activation_id,
                PaperRuntimeOperationalPhase.WAITING_DATA,
                "FRONTIER_READ_UNAVAILABLE",
            )
            return None
        except AnalyticalFrontierDataError:
            raise _PaperRuntimeFrontierFailure(
                "FRONTIER_INVALID", "frontier data is invalid"
            ) from None
        except AnalyticalFrontierError:
            raise _PaperRuntimeFrontierFailure(
                "FRONTIER_READ_FAILED", "frontier read failed"
            ) from None
        except Exception as error:
            if self._is_transient(error):
                self._set_operational_phase(
                    activation.activation_id,
                    PaperRuntimeOperationalPhase.WAITING_DATA,
                    "FRONTIER_READ_UNAVAILABLE",
                )
                return None
            raise _PaperRuntimeFrontierFailure(
                "FRONTIER_READ_FAILED", "frontier read failed"
            ) from error

    def _validate_strategy_registry(
        self, session: Session, activation: PaperRuntimeActivation
    ) -> None:
        """Prove that the exact persisted StrategyVersion is locally executable."""
        version_row = self._strategy_repository.get_version(
            session, activation.strategy_version_id
        )
        if version_row is None:
            raise PaperRuntimeStateAuthorityError("StrategyVersion is missing")
        version = version_to_domain(version_row)
        if (
            version.strategy_key != activation.strategy_key
            or version.version_number != activation.strategy_version_number
            or version.source_fingerprint != activation.source_fingerprint
            or version.implementation_key != activation.implementation_key
        ):
            raise PaperRuntimeStateAuthorityError(
                "persisted StrategyVersion identity does not match activation"
            )
        try:
            self._strategy_registry.implementation_for_version(version)
        except Exception as error:
            raise PaperRuntimeStateAuthorityError(
                "StrategyVersion is not represented by local registry"
            ) from error

    def _read_startup_capability(self) -> None:
        """Require a successful normalized account capability observation.

        The injected provider reader owns account interpretation, including the
        exact configured OANDA Practice account and non-MT4 restriction.  The
        runtime only treats a successful read as proof and never inspects raw
        provider fields here.
        """
        if self._capability_reader is None:
            raise PaperRuntimeStateAuthorityError(
                "startup capability reader is unavailable"
            )
        self._capability_reader.read()

    def _read_observation(
        self, session: Session, activation: PaperRuntimeActivation
    ) -> PaperRuntimeAccountObservation:
        if self._repository.has_unsafe_attempt(session, activation.provider_account_id):
            raise PaperRuntimeStateAuthorityError(
                "unsafe PAPER attempt prevents current account authority"
            )
        raw = self._account_reader.read()
        if isinstance(raw, PaperRuntimeAccountObservation):
            if raw.provider_account_id != activation.provider_account_id:
                raise PaperRuntimeStateAuthorityError("account identity changed")
            return raw
        if not isinstance(raw, OandaPracticeExecutionAccountSnapshot):
            raise PaperRuntimeStateAuthorityError(
                "account reader returned invalid facts"
            )
        attributable = self._exposure_is_attributable(session, activation, raw)
        observation = PaperRuntimeAccountObservation.from_oanda_snapshot(
            raw,
            observed_at=self._now(),
            attributable=attributable,
        )
        if observation.provider_account_id != activation.provider_account_id:
            raise PaperRuntimeStateAuthorityError("account identity changed")
        return observation

    @staticmethod
    def _exposure_is_attributable(
        session: Session,
        activation: PaperRuntimeActivation,
        snapshot: OandaPracticeExecutionAccountSnapshot,
    ) -> bool:
        if (
            snapshot.summary.open_trade_count == 0
            and snapshot.summary.open_position_count == 0
        ):
            return True
        trade_ids = {trade.provider_trade_id for trade in snapshot.trades.trades}
        if not trade_ids:
            return False
        rows = session.scalars(
            select(PaperExecutionAttemptModel).where(
                PaperExecutionAttemptModel.provider_account_id
                == activation.provider_account_id,
                PaperExecutionAttemptModel.provider == "OANDA",
                PaperExecutionAttemptModel.environment == "PRACTICE",
                PaperExecutionAttemptModel.instrument == "EUR_USD",
                PaperExecutionAttemptModel.strategy_version_id
                == activation.strategy_version_id,
                PaperExecutionAttemptModel.validated_parameter_snapshot
                == activation.validated_parameter_snapshot.to_json(),
                PaperExecutionAttemptModel.fill_trade_id.in_(trade_ids),
                PaperExecutionAttemptModel.execution_outcome == "FILLED_PROTECTED",
            )
        ).all()
        if len(rows) != len(trade_ids):
            return False
        direction = snapshot.trades.trades[0].current_units
        state = (
            FinancialPositionState.LONG
            if direction > 0
            else FinancialPositionState.SHORT
        )
        return state in {
            FinancialPositionState.LONG,
            FinancialPositionState.SHORT,
        }

    def _persist_evaluation(
        self,
        activation: PaperRuntimeActivation,
        cycle_id: UUID,
        receipt: PaperStrategyEvaluationReceipt,
        status: PaperRuntimeCycleStatus,
        *,
        attempt_id: UUID | None = None,
        reason_code: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            with session.begin():
                self._cycle_authority.persist_evaluation(
                    session,
                    cycle_id,
                    activation,
                    receipt,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                    cycle_status=status,
                    attempt_id=attempt_id,
                    reason_code=reason_code,
                )

    def _persist_evaluation_or_block(
        self,
        activation: PaperRuntimeActivation,
        cycle_id: UUID,
        receipt: PaperStrategyEvaluationReceipt,
        cycle_status: PaperRuntimeCycleStatus,
        *,
        decision: Action | None,
        reason_code: str | None = None,
    ) -> PaperRuntimeTickResult | None:
        """Persist evidence, fencing the session if the boundary is uncertain."""
        try:
            self._persist_evaluation(
                activation,
                cycle_id,
                receipt,
                cycle_status,
                reason_code=reason_code,
            )
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation.activation_id, cycle_id)
        except Exception:
            try:
                self._block_cycle_and_activation(
                    activation.activation_id,
                    cycle_id,
                    "EVALUATION_PERSISTENCE_UNCERTAIN",
                )
            except PaperRuntimeOwnerLost:
                return self._owner_lost(activation.activation_id, cycle_id)
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation.activation_id,
                cycle_id=cycle_id,
                decision=decision,
                reason_code="EVALUATION_PERSISTENCE_UNCERTAIN",
            )
        return None

    def _persist_entry_claim(
        self,
        activation: PaperRuntimeActivation,
        cycle_id: UUID,
        receipt: PaperStrategyEvaluationReceipt,
        prepared: PaperDurableExecutionPreparation,
    ) -> UUID:
        assert self._durable_execution is not None
        with self._session_factory() as session:
            with session.begin():
                self._repository.assert_entry_authority(
                    session,
                    activation.activation_id,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )
                claim = self._durable_execution.persist_entry_claim(session, prepared)
                self._cycle_authority.persist_evaluation(
                    session,
                    cycle_id,
                    activation,
                    receipt,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                    cycle_status=PaperRuntimeCycleStatus.ENTRY_CLAIMED,
                    attempt_id=prepared.attempt_id,
                )
                return claim.claim_id

    def _persist_blocked_evaluation(
        self,
        activation: PaperRuntimeActivation,
        cycle_id: UUID,
        receipt: PaperStrategyEvaluationReceipt,
        reason_code: str,
    ) -> None:
        try:
            self._persist_evaluation(
                activation,
                cycle_id,
                receipt,
                PaperRuntimeCycleStatus.BLOCKED,
                reason_code=reason_code,
            )
        finally:
            self._block(activation.activation_id, reason_code, cycle_id)

    def _resolve_cycle(self, cycle_id: UUID, *, filled: bool) -> None:
        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session)
                cycle = self._repository.get_cycle(session, cycle_id, for_update=True)
                if cycle is None:
                    raise PaperRuntimeCycleConflict(
                        "cycle disappeared before resolution"
                    )
                current_status = PaperRuntimeCycleStatus(cycle.cycle_status)
                if current_status is PaperRuntimeCycleStatus.ENTRY_CLAIMED:
                    self._repository.transition_cycle(
                        session,
                        cycle_id,
                        PaperRuntimeCycleStatus.ENTRY_RESOLVED,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                    current_status = PaperRuntimeCycleStatus.ENTRY_RESOLVED
                if filled:
                    if current_status is PaperRuntimeCycleStatus.ENTRY_RESOLVED:
                        self._repository.transition_cycle(
                            session,
                            cycle_id,
                            PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
                            owner_id=self._owner.owner_id,
                            owner_generation=self._owner.owner_generation,
                        )
                        current_status = PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED
                    if (
                        current_status
                        is not PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED
                    ):
                        raise InvalidPaperRuntimeTransition(
                            "filled execution is missing a Take Profit claim"
                        )
                elif current_status is not PaperRuntimeCycleStatus.ENTRY_RESOLVED:
                    raise InvalidPaperRuntimeTransition(
                        "no-Fill execution has an invalid cycle status"
                    )
                self._repository.transition_cycle(
                    session,
                    cycle_id,
                    PaperRuntimeCycleStatus.COMPLETE,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )

    def _mark_cycle_take_profit_claimed(self, cycle_id: UUID) -> None:
        """Record the dependent claim before P05 performs its one PUT."""
        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session)
                cycle = self._repository.get_cycle(session, cycle_id, for_update=True)
                if cycle is None:
                    raise PaperRuntimeCycleConflict(
                        "cycle disappeared before protection"
                    )
                current_status = PaperRuntimeCycleStatus(cycle.cycle_status)
                if current_status is PaperRuntimeCycleStatus.ENTRY_CLAIMED:
                    self._repository.transition_cycle(
                        session,
                        cycle_id,
                        PaperRuntimeCycleStatus.ENTRY_RESOLVED,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                elif current_status is not PaperRuntimeCycleStatus.ENTRY_RESOLVED:
                    raise InvalidPaperRuntimeTransition(
                        "Take Profit claim requires an entry-resolved cycle"
                    )
                self._repository.transition_cycle(
                    session,
                    cycle_id,
                    PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )

    def _complete_recovered_cycle(
        self,
        cycle_id: UUID,
        *,
        status: PaperRuntimeCycleStatus,
        filled: bool,
    ) -> None:
        """Close a claim cycle without creating or replaying a mutation claim."""
        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session)
                if status is PaperRuntimeCycleStatus.ENTRY_CLAIMED:
                    self._repository.transition_cycle(
                        session,
                        cycle_id,
                        PaperRuntimeCycleStatus.ENTRY_RESOLVED,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
                    if filled:
                        self._repository.transition_cycle(
                            session,
                            cycle_id,
                            PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
                            owner_id=self._owner.owner_id,
                            owner_generation=self._owner.owner_generation,
                        )
                elif status not in {
                    PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
                    PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
                }:
                    raise InvalidPaperRuntimeTransition(
                        "recovered cycle is not claim-authoritative"
                    )
                self._repository.transition_cycle(
                    session,
                    cycle_id,
                    PaperRuntimeCycleStatus.COMPLETE,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )

    def _block_cycle_and_activation(
        self, activation_id: UUID, cycle_id: UUID, reason_code: str
    ) -> None:
        self._mark_cycle_blocked_if_possible(cycle_id, reason_code)
        self._block(activation_id, reason_code, cycle_id)

    def _mark_cycle_blocked_if_possible(self, cycle_id: UUID, reason_code: str) -> None:
        try:
            with self._session_factory() as session:
                with session.begin():
                    self._repository.transition_cycle(
                        session,
                        cycle_id,
                        PaperRuntimeCycleStatus.BLOCKED,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                        reason_code=reason_code,
                    )
        except PaperRuntimeOwnerLost:
            raise
        except Exception:
            pass

    def _block(
        self,
        activation_id: UUID,
        reason_code: str,
        cycle_id: UUID | None = None,
    ) -> PaperRuntimeTickResult:
        try:
            with self._session_factory() as session:
                with session.begin():
                    self._owner.assert_current(session, activation_id=activation_id)
                    if cycle_id is not None:
                        try:
                            self._repository.transition_cycle(
                                session,
                                cycle_id,
                                PaperRuntimeCycleStatus.BLOCKED,
                                owner_id=self._owner.owner_id,
                                owner_generation=self._owner.owner_generation,
                                reason_code=reason_code,
                            )
                        except InvalidPaperRuntimeTransition:
                            # A claim/terminal cycle can be durably unsafe
                            # without accepting a second cycle transition.  The
                            # activation still must be fenced in this transaction.
                            pass
                    self._repository.transition_activation(
                        session,
                        activation_id,
                        PaperRuntimeLifecycleState.BLOCKED,
                        reason_code=reason_code,
                        owner_id=self._owner.owner_id,
                        owner_generation=self._owner.owner_generation,
                    )
            self._started = False
            self._set_owner_phase(PaperRuntimeOwnershipPhase.BLOCKED)
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation_id,
                cycle_id=cycle_id,
                reason_code=reason_code,
            )
        except PaperRuntimeOwnerLost:
            return self._owner_lost(activation_id, cycle_id)
        except InvalidPaperRuntimeTransition:
            return PaperRuntimeTickResult(
                PaperRuntimeTickOutcome.BLOCKED,
                activation_id=activation_id,
                cycle_id=cycle_id,
                reason_code=reason_code,
            )

    def _block_in_transaction(
        self, session: Session, activation_id: UUID, reason: str
    ) -> None:
        self._owner.assert_current(session, activation_id=activation_id)
        self._repository.transition_activation(
            session,
            activation_id,
            PaperRuntimeLifecycleState.BLOCKED,
            reason_code=reason,
            owner_id=self._owner.owner_id,
            owner_generation=self._owner.owner_generation,
        )

    def _finalize_stop(self, activation_id: UUID) -> None:
        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session, activation_id=activation_id)
                self._repository.transition_activation(
                    session,
                    activation_id,
                    PaperRuntimeLifecycleState.STOPPED,
                    reason_code="OPERATOR_STOP",
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )
        self._set_owner_phase(PaperRuntimeOwnershipPhase.STOPPED)

    def _assert_mutation_owner(self, activation_id: UUID) -> None:
        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session, activation_id=activation_id)

    def _heartbeat(self, phase: PaperRuntimeOwnershipPhase) -> None:
        with self._session_factory() as session:
            with session.begin():
                self._owner.set_phase(session, phase)

    def _set_owner_phase(self, phase: PaperRuntimeOwnershipPhase) -> None:
        try:
            self._heartbeat(phase)
        except PaperRuntimeOwnerLost:
            raise

    def _set_operational_phase(
        self,
        activation_id: UUID,
        phase: PaperRuntimeOperationalPhase,
        reason_code: str | None,
    ) -> None:
        with self._session_factory() as session:
            with session.begin():
                self._owner.assert_current(session, activation_id=activation_id)
                self._repository.update_operational_phase(
                    session,
                    activation_id,
                    phase,
                    reason_code=reason_code,
                    owner_id=self._owner.owner_id,
                    owner_generation=self._owner.owner_generation,
                )

    def _current_activation(self) -> PaperRuntimeActivation | None:
        with self._session_factory() as session:
            row = self._repository.get_active_activation(session)
            return _activation_from_row(session, row) if row is not None else None

    def _activation_for_id(
        self, session: Session, activation_id: UUID
    ) -> PaperRuntimeActivation | None:
        row = self._repository.get_activation(session, activation_id)
        return _activation_from_row(session, row) if row is not None else None

    def _owner_lost(
        self, activation_id: UUID | None, cycle_id: UUID | None = None
    ) -> PaperRuntimeTickResult:
        self._started = False
        return PaperRuntimeTickResult(
            PaperRuntimeTickOutcome.OWNER_LOST,
            activation_id=activation_id,
            cycle_id=cycle_id,
            reason_code="RUNTIME_OWNER_LOST",
        )

    def _waiting_result(self, activation_id: UUID) -> PaperRuntimeTickResult:
        return PaperRuntimeTickResult(
            PaperRuntimeTickOutcome.WAITING_FRONTIER,
            activation_id=activation_id,
            reason_code="NO_NEW_FRONTIER",
        )

    def _now(self) -> datetime:
        value = self._clock()
        if (
            type(value) is not datetime
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise PaperRuntimePersistenceError("runtime clock is invalid")
        return value.astimezone(UTC)

    @staticmethod
    def _is_supported_opening(action: Action, entry_policy: str) -> bool:
        return action in {Action.OPEN_LONG, Action.OPEN_SHORT} and (
            entry_policy == "IMMEDIATE"
        )

    @staticmethod
    def _is_transient(error: BaseException) -> bool:
        if isinstance(error, (httpx.RequestError, TimeoutError, ConnectionError)):
            return True
        if isinstance(error, OandaRequestError):
            status_code = error.status_code
            return (
                status_code is None
                or status_code in (408, 429)
                or (500 <= status_code <= 599)
            )
        return False


def _bounded_reason(value: object, fallback: str) -> str:
    if (
        type(value) is str
        and value
        and len(value) <= 64
        and not any(ord(character) < 32 for character in value)
    ):
        return value
    return fallback


# Discoverable compatibility names for callers that use process/runtime
# terminology rather than the orchestration-specific name.
PaperRuntimeRunner = PaperRuntimeOrchestrator
PaperRuntimeLoop = PaperRuntimeOrchestrator
PaperRuntime = PaperRuntimeOrchestrator


__all__ = [
    "PaperRuntime",
    "PaperRuntimeAccountReader",
    "PaperRuntimeCapabilityReader",
    "PaperRuntimeLoop",
    "PaperRuntimeOrchestrator",
    "PaperRuntimeReconciliation",
    "PaperRuntimeRunner",
    "PaperRuntimeStartupResult",
    "PaperRuntimeTickOutcome",
    "PaperRuntimeTickResult",
]
