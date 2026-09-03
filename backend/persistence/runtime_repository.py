"""Repository primitives for the PAPER 06 runtime projection.

This module persists runtime evidence only.  It never acquires the live
advisory lock and never calls a provider.  The ownership methods are guarded
by ``owner_id`` and ``owner_generation``; T003 supplies the dedicated
session-level advisory-lock connection before using them.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain import (
    StrategyDecision,
    StrategyEvaluation,
    StrategyStateEnvelope,
    ValidatedParameterPayload,
)
from backend.runtime.persistence_contracts import (
    PaperRuntimeActivation,
    PaperRuntimeCycle,
    PaperRuntimeCycleStatus,
    PaperRuntimeLifecycleState,
    PaperRuntimeOperationalPhase,
    PaperRuntimeOwnership,
    PaperRuntimeOwnershipPhase,
    PaperRuntimePersistenceError,
    canonical_decimal_text,
    canonical_json_bytes,
    runtime_evaluation_key,
    validate_runtime_json_object,
)

from .models import (
    PaperExecutionAttemptModel,
    PaperRuntimeActivationModel,
    PaperRuntimeCycleModel,
    PaperRuntimeOwnershipModel,
    StrategyVersionModel,
)
from .strategy_repository import version_to_domain


class PaperRuntimeRepositoryError(RuntimeError):
    """Base error for unsafe or impossible runtime persistence operations."""


class PaperRuntimeActivationNotFound(PaperRuntimeRepositoryError):
    pass


class PaperRuntimeCycleNotFound(PaperRuntimeRepositoryError):
    pass


class PaperRuntimeOwnershipNotFound(PaperRuntimeRepositoryError):
    pass


class PaperRuntimeIdentityConflict(PaperRuntimeRepositoryError):
    """The same activation/cycle identity was presented with changed facts."""


class PaperRuntimeActivationAlreadyPresent(PaperRuntimeRepositoryError):
    """A different activation is already occupying the non-terminal slot."""


class PaperRuntimeOwnerLost(PaperRuntimeRepositoryError):
    """A guarded runtime write no longer has the current owner generation."""


class PaperRuntimeCycleConflict(PaperRuntimeRepositoryError):
    """A cycle identity or monotonic sequence conflicts with durable evidence."""


class InvalidPaperRuntimeTransition(PaperRuntimeRepositoryError):
    pass


_DEFINITE_TERMINAL_EXECUTION_OUTCOMES = frozenset(
    {
        "REJECTED",
        "CANCELLED",
        "FILLED_PROTECTED",
    }
)
_SAFE_RECONCILIATION_STATUSES = frozenset(
    {
        "NOT_RUN",
        "CONSISTENT",
        "LIFECYCLE_ADVANCED",
    }
)


def is_unsafe_paper_attempt(
    execution_outcome: object, reconciliation_status: object
) -> bool:
    """Classify durable PAPER truth before allowing another opening.

    ``NOT_RUN`` is the initial reconciliation projection, not an uncertainty
    by itself when P05 has already recorded a definite terminal outcome.
    Unknown, incomplete, malformed, and missing outcome/status values remain
    unsafe.  ``FILLED_PROTECTED`` is deliberately only execution-resolution
    truth; current account flatness is established by a separate fresh read.
    """
    if not isinstance(execution_outcome, str) or not isinstance(
        reconciliation_status, str
    ):
        return True
    return execution_outcome not in _DEFINITE_TERMINAL_EXECUTION_OUTCOMES or (
        reconciliation_status not in _SAFE_RECONCILIATION_STATUSES
    )


_ACTIVATION_TRANSITIONS: dict[
    PaperRuntimeLifecycleState, frozenset[PaperRuntimeLifecycleState]
] = {
    PaperRuntimeLifecycleState.REQUESTED: frozenset(
        {
            PaperRuntimeLifecycleState.REQUESTED,
            PaperRuntimeLifecycleState.STARTING,
            PaperRuntimeLifecycleState.STOPPED,
        }
    ),
    PaperRuntimeLifecycleState.STARTING: frozenset(
        {
            PaperRuntimeLifecycleState.STARTING,
            PaperRuntimeLifecycleState.RUNNING,
            PaperRuntimeLifecycleState.STOP_REQUESTED,
            PaperRuntimeLifecycleState.BLOCKED,
            PaperRuntimeLifecycleState.FAILED,
        }
    ),
    PaperRuntimeLifecycleState.RUNNING: frozenset(
        {
            PaperRuntimeLifecycleState.RUNNING,
            PaperRuntimeLifecycleState.STARTING,
            PaperRuntimeLifecycleState.STOP_REQUESTED,
            PaperRuntimeLifecycleState.BLOCKED,
            PaperRuntimeLifecycleState.FAILED,
        }
    ),
    PaperRuntimeLifecycleState.STOP_REQUESTED: frozenset(
        {
            PaperRuntimeLifecycleState.STOP_REQUESTED,
            PaperRuntimeLifecycleState.STOPPED,
        }
    ),
    PaperRuntimeLifecycleState.STOPPED: frozenset({PaperRuntimeLifecycleState.STOPPED}),
    PaperRuntimeLifecycleState.BLOCKED: frozenset({PaperRuntimeLifecycleState.BLOCKED}),
    PaperRuntimeLifecycleState.FAILED: frozenset({PaperRuntimeLifecycleState.FAILED}),
}

_CYCLE_TRANSITIONS: dict[
    PaperRuntimeCycleStatus, frozenset[PaperRuntimeCycleStatus]
] = {
    PaperRuntimeCycleStatus.CLAIMED: frozenset(
        {
            PaperRuntimeCycleStatus.CLAIMED,
            PaperRuntimeCycleStatus.EVALUATING,
            PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
        }
    ),
    PaperRuntimeCycleStatus.EVALUATING: frozenset(
        {
            PaperRuntimeCycleStatus.EVALUATING,
            PaperRuntimeCycleStatus.NO_ACTION,
            PaperRuntimeCycleStatus.REFUSED,
            PaperRuntimeCycleStatus.ENTRY_CLAIMED,
            PaperRuntimeCycleStatus.BLOCKED,
            PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
        }
    ),
    PaperRuntimeCycleStatus.NO_ACTION: frozenset({PaperRuntimeCycleStatus.NO_ACTION}),
    PaperRuntimeCycleStatus.REFUSED: frozenset({PaperRuntimeCycleStatus.REFUSED}),
    PaperRuntimeCycleStatus.ENTRY_CLAIMED: frozenset(
        {
            PaperRuntimeCycleStatus.ENTRY_CLAIMED,
            PaperRuntimeCycleStatus.ENTRY_RESOLVED,
            PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
        }
    ),
    PaperRuntimeCycleStatus.ENTRY_RESOLVED: frozenset(
        {
            PaperRuntimeCycleStatus.ENTRY_RESOLVED,
            PaperRuntimeCycleStatus.COMPLETE,
            PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
            PaperRuntimeCycleStatus.BLOCKED,
        }
    ),
    PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED: frozenset(
        {
            PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
            PaperRuntimeCycleStatus.COMPLETE,
            PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
        }
    ),
    PaperRuntimeCycleStatus.COMPLETE: frozenset({PaperRuntimeCycleStatus.COMPLETE}),
    PaperRuntimeCycleStatus.RECOVERY_REQUIRED: frozenset(
        {
            PaperRuntimeCycleStatus.RECOVERY_REQUIRED,
            PaperRuntimeCycleStatus.COMPLETE,
            PaperRuntimeCycleStatus.BLOCKED,
        }
    ),
    PaperRuntimeCycleStatus.BLOCKED: frozenset({PaperRuntimeCycleStatus.BLOCKED}),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _activation_identity(row: PaperRuntimeActivationModel) -> dict[str, object]:
    return {
        "strategy_version_id": str(row.strategy_version_id),
        "strategy_key": row.strategy_key,
        "strategy_version_number": row.strategy_version_number,
        "source_fingerprint": row.source_fingerprint,
        "implementation_key": row.implementation_key,
        "validated_parameter_snapshot": row.validated_parameter_snapshot,
        "parameter_fingerprint": row.parameter_fingerprint,
        "provider": row.provider,
        "environment": row.environment,
        "provider_account_id": row.provider_account_id,
        "base_currency": row.base_currency,
        "instrument": row.instrument,
        "risk_per_trade": canonical_decimal_text(row.risk_per_trade),
        "state_origin": row.state_origin,
        "runtime_policy_version": row.runtime_policy_version,
        "poll_interval_seconds": row.poll_interval_seconds,
        "approval_kind": row.approval_kind,
        "approval_code": row.approval_code,
    }


def _same_json(left: object, right: object) -> bool:
    if type(left) is not dict or type(right) is not dict:
        return left == right
    left_object = cast(dict[str, object], left)
    right_object = cast(dict[str, object], right)
    return canonical_json_bytes(left_object, maximum=32_768) == canonical_json_bytes(
        right_object, maximum=32_768
    )


def _assert_activation_identity(
    row: PaperRuntimeActivationModel, activation: PaperRuntimeActivation
) -> None:
    expected = activation.immutable_json()
    actual = _activation_identity(row)
    if not _same_json(actual, expected):
        raise PaperRuntimeIdentityConflict(
            f"activation {activation.activation_id} has different immutable facts"
        )


def _cycle_identity(row: PaperRuntimeCycleModel) -> dict[str, object]:
    return {
        "cycle_id": str(row.cycle_id),
        "activation_id": str(row.activation_id),
        "cycle_sequence": row.cycle_sequence,
        "evaluation_key": row.evaluation_key,
        "strategy_version_id": str(row.strategy_version_id),
        "parameter_fingerprint": row.parameter_fingerprint,
        "frontier_start": row.frontier_start.astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "frontier_end": row.frontier_end.astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "prior_frontier_end": (
            row.prior_frontier_end.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if row.prior_frontier_end is not None
            else None
        ),
        "state_before": row.state_before,
        "state_before_fingerprint": row.state_before_fingerprint,
        "financial_position_state": row.financial_position_state,
        "account_transaction_id": row.account_transaction_id,
        "account_observed_at": row.account_observed_at.astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "account_open_trade_count": row.account_open_trade_count,
        "account_open_position_count": row.account_open_position_count,
        "account_pending_order_count": row.account_pending_order_count,
        "account_gate_fingerprint": row.account_gate_fingerprint,
        "claimed_at": row.claimed_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def _assert_cycle_identity(
    row: PaperRuntimeCycleModel, cycle: PaperRuntimeCycle
) -> None:
    if not _same_json(_cycle_identity(row), _cycle_identity_from_contract(cycle)):
        raise PaperRuntimeIdentityConflict(
            f"cycle {cycle.cycle_id} has different immutable facts"
        )


def _cycle_identity_from_contract(cycle: PaperRuntimeCycle) -> dict[str, object]:
    value = cycle.to_json()
    return {
        key: value[key]
        for key in (
            "cycle_id",
            "activation_id",
            "cycle_sequence",
            "evaluation_key",
            "strategy_version_id",
            "parameter_fingerprint",
            "frontier_start",
            "frontier_end",
            "prior_frontier_end",
            "state_before",
            "state_before_fingerprint",
            "financial_position_state",
            "account_transaction_id",
            "account_observed_at",
            "account_open_trade_count",
            "account_open_position_count",
            "account_pending_order_count",
            "account_gate_fingerprint",
            "claimed_at",
        )
    }


class PaperRuntimeRepository:
    """Persistence boundary for activation, cycle, and owner projections."""

    def get_activation(
        self, session: Session, activation_id: UUID, *, for_update: bool = False
    ) -> PaperRuntimeActivationModel | None:
        statement = select(PaperRuntimeActivationModel).where(
            PaperRuntimeActivationModel.activation_id == activation_id
        )
        if for_update:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def get_active_activation(
        self, session: Session, *, for_update: bool = False
    ) -> PaperRuntimeActivationModel | None:
        statement = (
            select(PaperRuntimeActivationModel)
            .where(
                PaperRuntimeActivationModel.lifecycle_state.in_(
                    state.value
                    for state in (
                        PaperRuntimeLifecycleState.REQUESTED,
                        PaperRuntimeLifecycleState.STARTING,
                        PaperRuntimeLifecycleState.RUNNING,
                        PaperRuntimeLifecycleState.STOP_REQUESTED,
                    )
                )
            )
            .order_by(PaperRuntimeActivationModel.requested_at)
        )
        if for_update:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def create_activation(
        self, session: Session, activation: PaperRuntimeActivation
    ) -> PaperRuntimeActivationModel:
        """Insert an activation or return an exact same-ID replay."""
        if type(activation) is not PaperRuntimeActivation:
            raise PaperRuntimePersistenceError("activation has an invalid type")
        existing = self.get_activation(session, activation.activation_id)
        if existing is not None:
            _assert_activation_identity(existing, activation)
            return existing
        self._verify_strategy_version(session, activation)
        row = PaperRuntimeActivationModel(
            activation_id=activation.activation_id,
            strategy_version_id=activation.strategy_version_id,
            strategy_key=activation.strategy_key,
            strategy_version_number=activation.strategy_version_number,
            source_fingerprint=activation.source_fingerprint,
            implementation_key=activation.implementation_key,
            validated_parameter_snapshot=activation.validated_parameter_snapshot.to_json(),
            parameter_fingerprint=activation.parameter_fingerprint,
            provider=activation.provider,
            environment=activation.environment,
            provider_account_id=activation.provider_account_id,
            base_currency=activation.base_currency,
            instrument=activation.instrument,
            risk_per_trade=activation.risk_per_trade,
            state_origin=activation.state_origin.value,
            runtime_policy_version=activation.runtime_policy_version,
            poll_interval_seconds=activation.poll_interval_seconds,
            approval_kind=activation.approval_kind,
            approval_code=activation.approval_code,
            requested_at=activation.requested_at,
            lifecycle_state=activation.lifecycle_state.value,
            state_reason_code=activation.state_reason_code,
            state_detail=activation.state_detail,
            state_changed_at=activation.state_changed_at,
            operational_phase=activation.operational_phase.value,
            last_operational_reason_code=activation.last_operational_reason_code,
            last_operational_at=activation.last_operational_at,
            strategy_state=(
                activation.strategy_state.to_json()
                if activation.strategy_state is not None
                else None
            ),
            strategy_state_fingerprint=activation.strategy_state_fingerprint,
            last_frontier_end=activation.last_frontier_end,
            last_cycle_id=activation.last_cycle_id,
            control_version=activation.control_version,
            updated_at=activation.updated_at,
        )
        try:
            with session.begin_nested():
                session.add(row)
                session.flush()
        except IntegrityError as error:
            existing = self.get_activation(session, activation.activation_id)
            if existing is not None:
                _assert_activation_identity(existing, activation)
                return existing
            active = self.get_active_activation(session)
            if active is not None:
                raise PaperRuntimeActivationAlreadyPresent(
                    f"activation {active.activation_id} already occupies the PAPER slot"
                ) from error
            raise PaperRuntimeRepositoryError(
                "activation insert conflicted without visible durable evidence"
            ) from error
        return row

    def request_stop(
        self,
        session: Session,
        activation_id: UUID,
        *,
        reason_code: str,
        reason_detail: str | None = None,
    ) -> PaperRuntimeActivationModel:
        row = self.get_activation(session, activation_id, for_update=True)
        if row is None:
            raise PaperRuntimeActivationNotFound(str(activation_id))
        current = PaperRuntimeLifecycleState(row.lifecycle_state)
        if current in {
            PaperRuntimeLifecycleState.STOPPED,
            PaperRuntimeLifecycleState.BLOCKED,
            PaperRuntimeLifecycleState.FAILED,
            PaperRuntimeLifecycleState.STOP_REQUESTED,
        }:
            return row
        target = (
            PaperRuntimeLifecycleState.STOPPED
            if current is PaperRuntimeLifecycleState.REQUESTED
            else PaperRuntimeLifecycleState.STOP_REQUESTED
        )
        return self.transition_activation(
            session,
            activation_id,
            target,
            reason_code=reason_code,
            reason_detail=reason_detail,
        )

    def transition_activation(
        self,
        session: Session,
        activation_id: UUID,
        lifecycle_state: PaperRuntimeLifecycleState,
        *,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        owner_id: UUID | None = None,
        owner_generation: int | None = None,
        expected_control_version: int | None = None,
    ) -> PaperRuntimeActivationModel:
        if type(lifecycle_state) is not PaperRuntimeLifecycleState:
            raise PaperRuntimePersistenceError("lifecycle_state is invalid")
        if owner_id is not None or owner_generation is not None:
            if owner_id is None or owner_generation is None:
                raise PaperRuntimePersistenceError("owner guard is incomplete")
            self.assert_owner(
                session, owner_id, owner_generation, activation_id=activation_id
            )
        row = self.get_activation(session, activation_id, for_update=True)
        if row is None:
            raise PaperRuntimeActivationNotFound(str(activation_id))
        current = PaperRuntimeLifecycleState(row.lifecycle_state)
        if lifecycle_state not in _ACTIVATION_TRANSITIONS[current]:
            raise InvalidPaperRuntimeTransition(
                "activation cannot move from "
                f"{current.value} to {lifecycle_state.value}"
            )
        if (
            expected_control_version is not None
            and row.control_version != expected_control_version
        ):
            raise PaperRuntimeOwnerLost("activation control version is stale")
        row.lifecycle_state = lifecycle_state.value
        row.state_reason_code = reason_code
        row.state_detail = reason_detail
        row.state_changed_at = _now()
        row.control_version += 1
        row.updated_at = _now()
        session.flush()
        return row

    def update_operational_phase(
        self,
        session: Session,
        activation_id: UUID,
        phase: PaperRuntimeOperationalPhase,
        *,
        reason_code: str | None = None,
        owner_id: UUID | None = None,
        owner_generation: int | None = None,
    ) -> PaperRuntimeActivationModel:
        if type(phase) is not PaperRuntimeOperationalPhase:
            raise PaperRuntimePersistenceError("operational phase is invalid")
        if owner_id is not None or owner_generation is not None:
            if owner_id is None or owner_generation is None:
                raise PaperRuntimePersistenceError("owner guard is incomplete")
            self.assert_owner(
                session, owner_id, owner_generation, activation_id=activation_id
            )
        row = self.get_activation(session, activation_id, for_update=True)
        if row is None:
            raise PaperRuntimeActivationNotFound(str(activation_id))
        row.operational_phase = phase.value
        row.last_operational_reason_code = reason_code
        row.last_operational_at = _now()
        row.control_version += 1
        row.updated_at = _now()
        session.flush()
        return row

    def assert_entry_authority(
        self,
        session: Session,
        activation_id: UUID,
        *,
        owner_id: UUID,
        owner_generation: int,
    ) -> PaperRuntimeActivationModel:
        """Lock the activation row before staging a possible ENTRY claim.

        The activation row is the STOP/ENTRY linearization boundary.  Holding
        this lock for the caller-owned transaction means a concurrent STOP
        either commits first (and rejects the claim) or observes the committed
        claim after it has become the one already-authorized operation.
        """
        self.assert_owner(
            session, owner_id, owner_generation, activation_id=activation_id
        )
        row = self.get_activation(session, activation_id, for_update=True)
        if row is None:
            raise PaperRuntimeActivationNotFound(str(activation_id))
        self.assert_owner(
            session, owner_id, owner_generation, activation_id=activation_id
        )
        if (
            PaperRuntimeLifecycleState(row.lifecycle_state)
            is not PaperRuntimeLifecycleState.RUNNING
        ):
            raise InvalidPaperRuntimeTransition(
                "ENTRY claims require a RUNNING activation"
            )
        return row

    def list_cycles(
        self,
        session: Session,
        activation_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[PaperRuntimeCycleModel]:
        """Return one activation's cycles in deterministic sequence order."""
        statement = (
            select(PaperRuntimeCycleModel)
            .where(PaperRuntimeCycleModel.activation_id == activation_id)
            .order_by(PaperRuntimeCycleModel.cycle_sequence)
        )
        if for_update:
            statement = statement.with_for_update()
        return list(session.scalars(statement).all())

    def has_unsafe_attempt(self, session: Session, account_id: str) -> bool:
        """Return whether local PAPER truth must fence new exposure."""
        row = session.scalar(
            select(PaperExecutionAttemptModel.attempt_id)
            .where(
                PaperExecutionAttemptModel.provider == "OANDA",
                PaperExecutionAttemptModel.environment == "PRACTICE",
                PaperExecutionAttemptModel.provider_account_id == account_id,
                (
                    PaperExecutionAttemptModel.execution_outcome.is_(None)
                    | PaperExecutionAttemptModel.execution_outcome.not_in(
                        _DEFINITE_TERMINAL_EXECUTION_OUTCOMES
                    )
                    | PaperExecutionAttemptModel.reconciliation_status.is_(None)
                    | PaperExecutionAttemptModel.reconciliation_status.not_in(
                        _SAFE_RECONCILIATION_STATUSES
                    )
                ),
            )
            .limit(1)
        )
        return row is not None

    def get_cycle(
        self, session: Session, cycle_id: UUID, *, for_update: bool = False
    ) -> PaperRuntimeCycleModel | None:
        statement = select(PaperRuntimeCycleModel).where(
            PaperRuntimeCycleModel.cycle_id == cycle_id
        )
        if for_update:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def get_cycle_by_evaluation_frontier(
        self,
        session: Session,
        evaluation_key: str,
        frontier_end: datetime,
        *,
        for_update: bool = False,
    ) -> PaperRuntimeCycleModel | None:
        """Read the globally unique Strategy/frontier reservation."""
        statement = select(PaperRuntimeCycleModel).where(
            PaperRuntimeCycleModel.evaluation_key == evaluation_key,
            PaperRuntimeCycleModel.frontier_end == frontier_end,
        )
        if for_update:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def next_cycle_sequence(self, session: Session, activation_id: UUID) -> int:
        """Return the next monotonic sequence for an activation."""
        if type(activation_id) is not UUID:
            raise PaperRuntimePersistenceError("activation_id must be a UUID")
        latest = session.scalar(
            select(func.max(PaperRuntimeCycleModel.cycle_sequence)).where(
                PaperRuntimeCycleModel.activation_id == activation_id
            )
        )
        return int(latest or 0) + 1

    def reserve_cycle(
        self,
        session: Session,
        cycle: PaperRuntimeCycle,
        *,
        owner_id: UUID,
        owner_generation: int,
    ) -> PaperRuntimeCycleModel:
        """Reserve exactly one frontier under the current owner generation."""
        if type(cycle) is not PaperRuntimeCycle:
            raise PaperRuntimePersistenceError("cycle has an invalid type")
        self.assert_owner(session, owner_id, owner_generation)
        activation = self.get_activation(session, cycle.activation_id, for_update=True)
        if activation is None:
            raise PaperRuntimeActivationNotFound(str(cycle.activation_id))
        self.assert_owner(
            session,
            owner_id,
            owner_generation,
            activation_id=cycle.activation_id,
        )
        if (
            PaperRuntimeLifecycleState(activation.lifecycle_state)
            is not PaperRuntimeLifecycleState.RUNNING
        ):
            raise InvalidPaperRuntimeTransition("cycles require a RUNNING activation")
        if activation.strategy_version_id != cycle.strategy_version_id:
            raise PaperRuntimeIdentityConflict(
                "cycle StrategyVersion does not match activation"
            )
        if activation.parameter_fingerprint != cycle.parameter_fingerprint:
            raise PaperRuntimeIdentityConflict(
                "cycle parameters do not match activation"
            )
        if cycle.prior_frontier_end != activation.last_frontier_end:
            raise PaperRuntimeIdentityConflict(
                "cycle prior frontier does not match activation state"
            )
        if activation.strategy_state is None:
            if (
                cycle.state_before is not None
                or activation.last_frontier_end is not None
                or activation.last_cycle_id is not None
            ):
                raise PaperRuntimeIdentityConflict(
                    "fresh activation cycle cannot contain prior Strategy state"
                )
        else:
            if activation.last_cycle_id is None:
                raise PaperRuntimeIdentityConflict(
                    "restored Strategy state has no owning cycle"
                )
            if not _same_json(
                activation.strategy_state,
                cycle.state_before.to_json()
                if cycle.state_before is not None
                else None,
            ):
                raise PaperRuntimeIdentityConflict(
                    "cycle state_before does not match activation Strategy state"
                )
        if (
            activation.last_frontier_end is not None
            and cycle.frontier_end <= activation.last_frontier_end
        ):
            raise PaperRuntimeCycleConflict(
                "cycle frontier does not advance activation state"
            )
        expected_evaluation_key = runtime_evaluation_key(
            cycle.strategy_version_id, cycle.parameter_fingerprint
        )
        if cycle.evaluation_key != expected_evaluation_key:
            raise PaperRuntimeIdentityConflict(
                "cycle evaluation key does not match Strategy identity"
            )
        existing = self.get_cycle_by_evaluation_frontier(
            session, cycle.evaluation_key, cycle.frontier_end
        )
        if existing is not None:
            if existing.cycle_id != cycle.cycle_id:
                raise PaperRuntimeCycleConflict(
                    "evaluation key and frontier are already reserved"
                )
            _assert_cycle_identity(existing, cycle)
            return existing
        existing = session.scalar(
            select(PaperRuntimeCycleModel).where(
                PaperRuntimeCycleModel.activation_id == cycle.activation_id,
                PaperRuntimeCycleModel.frontier_end == cycle.frontier_end,
            )
        )
        if existing is not None:
            raise PaperRuntimeCycleConflict("activation frontier is already reserved")
        if (
            self.next_cycle_sequence(session, cycle.activation_id)
            != cycle.cycle_sequence
        ):
            raise PaperRuntimeCycleConflict("cycle sequence is not monotonic")
        row = PaperRuntimeCycleModel(
            cycle_id=cycle.cycle_id,
            activation_id=cycle.activation_id,
            cycle_sequence=cycle.cycle_sequence,
            evaluation_key=cycle.evaluation_key,
            strategy_version_id=cycle.strategy_version_id,
            parameter_fingerprint=cycle.parameter_fingerprint,
            frontier_start=cycle.frontier_start,
            frontier_end=cycle.frontier_end,
            prior_frontier_end=cycle.prior_frontier_end,
            state_before=(cycle.state_before.to_json() if cycle.state_before else None),
            state_before_fingerprint=cycle.state_before_fingerprint,
            state_after=(cycle.state_after.to_json() if cycle.state_after else None),
            state_after_fingerprint=cycle.state_after_fingerprint,
            financial_position_state=cycle.financial_position_state.value,
            account_transaction_id=cycle.account_transaction_id,
            account_observed_at=cycle.account_observed_at,
            account_open_trade_count=cycle.account_open_trade_count,
            account_open_position_count=cycle.account_open_position_count,
            account_pending_order_count=cycle.account_pending_order_count,
            account_gate_fingerprint=cycle.account_gate_fingerprint,
            strategy_evaluation_snapshot=cycle.strategy_evaluation_snapshot,
            decision_snapshot=cycle.decision_snapshot,
            attempt_id=cycle.attempt_id,
            cycle_status=cycle.cycle_status.value,
            cycle_reason_code=cycle.cycle_reason_code,
            claimed_at=cycle.claimed_at,
            evaluated_at=cycle.evaluated_at,
            completed_at=cycle.completed_at,
            updated_at=cycle.updated_at,
        )
        try:
            with session.begin_nested():
                session.add(row)
                session.flush()
        except IntegrityError as error:
            existing = session.scalar(
                select(PaperRuntimeCycleModel).where(
                    PaperRuntimeCycleModel.evaluation_key == cycle.evaluation_key,
                    PaperRuntimeCycleModel.frontier_end == cycle.frontier_end,
                )
            )
            if existing is not None:
                if existing.cycle_id != cycle.cycle_id:
                    raise PaperRuntimeCycleConflict(
                        "evaluation key and frontier are already reserved"
                    ) from error
                _assert_cycle_identity(existing, cycle)
                return existing
            raise PaperRuntimeCycleConflict("cycle reservation conflicted") from error
        return row

    def transition_cycle(
        self,
        session: Session,
        cycle_id: UUID,
        cycle_status: PaperRuntimeCycleStatus,
        *,
        owner_id: UUID,
        owner_generation: int,
        reason_code: str | None = None,
    ) -> PaperRuntimeCycleModel:
        if type(cycle_status) is not PaperRuntimeCycleStatus:
            raise PaperRuntimePersistenceError("cycle_status is invalid")
        self.assert_owner(session, owner_id, owner_generation)
        row = self.get_cycle(session, cycle_id, for_update=True)
        if row is None:
            raise PaperRuntimeCycleNotFound(str(cycle_id))
        self.assert_owner(
            session,
            owner_id,
            owner_generation,
            activation_id=row.activation_id,
        )
        current = PaperRuntimeCycleStatus(row.cycle_status)
        if cycle_status not in _CYCLE_TRANSITIONS[current]:
            raise InvalidPaperRuntimeTransition(
                f"cycle cannot move from {current.value} to {cycle_status.value}"
            )
        row.cycle_status = cycle_status.value
        row.cycle_reason_code = reason_code
        now = _now()
        if cycle_status not in {
            PaperRuntimeCycleStatus.CLAIMED,
            PaperRuntimeCycleStatus.EVALUATING,
        }:
            row.evaluated_at = row.evaluated_at or now
        if cycle_status in {
            PaperRuntimeCycleStatus.NO_ACTION,
            PaperRuntimeCycleStatus.REFUSED,
            PaperRuntimeCycleStatus.COMPLETE,
            PaperRuntimeCycleStatus.BLOCKED,
        }:
            row.completed_at = row.completed_at or now
        row.updated_at = now
        session.flush()
        return row

    def persist_cycle_evaluation(
        self,
        session: Session,
        cycle_id: UUID,
        *,
        state_after: StrategyStateEnvelope,
        strategy_evaluation_snapshot: StrategyEvaluation | dict[str, object],
        decision_snapshot: StrategyDecision | dict[str, object],
        cycle_status: PaperRuntimeCycleStatus,
        owner_id: UUID,
        owner_generation: int,
        attempt_id: UUID | None = None,
        reason_code: str | None = None,
    ) -> PaperRuntimeCycleModel:
        """Persist evaluation evidence and advance activation state atomically.

        The caller owns the surrounding transaction.  Consequently a later
        P05 attempt/claim can be added to the same transaction by T005 without
        exposing a partially advanced runtime projection.
        """
        if type(state_after) is not StrategyStateEnvelope:
            raise PaperRuntimePersistenceError("state_after is invalid")
        if type(strategy_evaluation_snapshot) is StrategyEvaluation:
            evaluation_json = strategy_evaluation_snapshot.to_json()
            if strategy_evaluation_snapshot.next_state != state_after:
                raise PaperRuntimeIdentityConflict(
                    "state_after does not belong to the Strategy evaluation"
                )
        elif type(strategy_evaluation_snapshot) is dict:
            evaluation_json = strategy_evaluation_snapshot
        else:
            raise PaperRuntimePersistenceError(
                "strategy evaluation snapshot is invalid"
            )
        if type(decision_snapshot) is StrategyDecision:
            decision_json = decision_snapshot.to_json()
        elif type(decision_snapshot) is dict:
            decision_json = decision_snapshot
        else:
            raise PaperRuntimePersistenceError("decision snapshot is invalid")
        evaluation_json = validate_runtime_json_object(
            evaluation_json, "strategy evaluation snapshot"
        )
        decision_json = validate_runtime_json_object(decision_json, "decision snapshot")
        state_json = state_after.to_json()
        state_json = validate_runtime_json_object(state_json, "state_after")
        state_fingerprint = hashlib.sha256(
            canonical_json_bytes(state_json, maximum=32_768)
        ).hexdigest()
        if reason_code is not None and (
            type(reason_code) is not str or not reason_code or len(reason_code) > 64
        ):
            raise PaperRuntimePersistenceError("reason_code is invalid")
        self.assert_owner(session, owner_id, owner_generation)
        cycle = self.get_cycle(session, cycle_id, for_update=True)
        if cycle is None:
            raise PaperRuntimeCycleNotFound(str(cycle_id))
        self.assert_owner(
            session,
            owner_id,
            owner_generation,
            activation_id=cycle.activation_id,
        )
        if state_after.last_evaluated_bar_end != cycle.frontier_end:
            raise PaperRuntimeIdentityConflict(
                "state_after frontier does not match the reserved cycle frontier"
            )
        activation = self.get_activation(session, cycle.activation_id, for_update=True)
        if activation is None:  # pragma: no cover - protected by the FK
            raise PaperRuntimeActivationNotFound(str(cycle.activation_id))
        version = session.get(StrategyVersionModel, cycle.strategy_version_id)
        if version is None or (
            version.state_schema_version != state_after.state_schema_version
        ):
            raise PaperRuntimeIdentityConflict(
                "state_after schema does not match the durable StrategyVersion"
            )
        if cycle.state_after is not None and not _same_json(
            cycle.state_after, state_json
        ):
            raise PaperRuntimeIdentityConflict(
                f"cycle {cycle_id} already has different state_after evidence"
            )
        current = PaperRuntimeCycleStatus(cycle.cycle_status)
        if cycle_status not in _CYCLE_TRANSITIONS[current]:
            raise InvalidPaperRuntimeTransition(
                f"cycle cannot move from {current.value} to {cycle_status.value}"
            )
        if attempt_id is not None and type(attempt_id) is not UUID:
            raise PaperRuntimePersistenceError("attempt_id must be a UUID")
        if (
            cycle_status
            in {
                PaperRuntimeCycleStatus.ENTRY_CLAIMED,
                PaperRuntimeCycleStatus.ENTRY_RESOLVED,
                PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
            }
            and attempt_id is None
        ):
            raise PaperRuntimePersistenceError(
                f"{cycle_status.value} requires an attempt_id"
            )
        if attempt_id is not None and cycle_status in {
            PaperRuntimeCycleStatus.EVALUATING,
            PaperRuntimeCycleStatus.NO_ACTION,
            PaperRuntimeCycleStatus.REFUSED,
            PaperRuntimeCycleStatus.BLOCKED,
        }:
            raise PaperRuntimeIdentityConflict(
                "non-opening cycle status cannot contain an execution attempt"
            )
        cycle.state_after = state_json
        cycle.state_after_fingerprint = state_fingerprint
        cycle.strategy_evaluation_snapshot = evaluation_json
        cycle.decision_snapshot = decision_json
        cycle.attempt_id = attempt_id
        cycle.cycle_status = cycle_status.value
        cycle.cycle_reason_code = reason_code
        now = _now()
        cycle.evaluated_at = cycle.evaluated_at or now
        if cycle_status in {
            PaperRuntimeCycleStatus.NO_ACTION,
            PaperRuntimeCycleStatus.REFUSED,
            PaperRuntimeCycleStatus.COMPLETE,
            PaperRuntimeCycleStatus.BLOCKED,
        }:
            cycle.completed_at = cycle.completed_at or now
        cycle.updated_at = now
        if activation.strategy_state is None:
            if cycle.state_before is not None:
                raise PaperRuntimeIdentityConflict(
                    "activation lost the cycle's prior Strategy state evidence"
                )
        elif not _same_json(
            activation.strategy_state,
            cycle.state_before,
        ):
            raise PaperRuntimeIdentityConflict(
                "activation Strategy state advanced outside this cycle"
            )
        activation.strategy_state = state_json
        activation.strategy_state_fingerprint = state_fingerprint
        activation.last_frontier_end = cycle.frontier_end
        activation.last_cycle_id = cycle.cycle_id
        activation.control_version += 1
        activation.updated_at = now
        session.flush()
        return cycle

    def get_ownership(
        self, session: Session, *, for_update: bool = False
    ) -> PaperRuntimeOwnershipModel | None:
        statement = select(PaperRuntimeOwnershipModel).where(
            PaperRuntimeOwnershipModel.slot_key == "ATLAS_PAPER_RUNTIME"
        )
        if for_update:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def record_ownership_after_lock(
        self, session: Session, ownership: PaperRuntimeOwnership
    ) -> PaperRuntimeOwnershipModel:
        """Write ownership evidence after the caller acquired the advisory lock.

        This method intentionally cannot determine PostgreSQL session-lock
        state.  Its name makes the required ordering explicit; T003 owns the
        pinned connection that establishes that precondition.
        """
        if type(ownership) is not PaperRuntimeOwnership:
            raise PaperRuntimePersistenceError("ownership has an invalid type")
        row = self.get_ownership(session, for_update=True)
        if row is None:
            row = PaperRuntimeOwnershipModel(
                slot_key=ownership.slot_key,
                owner_id=ownership.owner_id,
                activation_id=ownership.activation_id,
                owner_generation=ownership.owner_generation,
                acquired_at=ownership.acquired_at,
                heartbeat_at=ownership.heartbeat_at,
                phase=ownership.phase.value,
            )
            session.add(row)
        else:
            if ownership.owner_generation <= row.owner_generation:
                if ownership.owner_id != row.owner_id:
                    raise PaperRuntimeOwnerLost(
                        "ownership generation is not newer than durable evidence"
                    )
                if (
                    ownership.owner_generation == row.owner_generation
                    and ownership.activation_id != row.activation_id
                ):
                    raise PaperRuntimeOwnerLost(
                        "ownership generation cannot change activation identity"
                    )
            row.owner_id = ownership.owner_id
            row.activation_id = ownership.activation_id
            row.owner_generation = ownership.owner_generation
            row.acquired_at = ownership.acquired_at
            row.heartbeat_at = ownership.heartbeat_at
            row.phase = ownership.phase.value
        session.flush()
        return row

    def assert_owner(
        self,
        session: Session,
        owner_id: UUID,
        owner_generation: int,
        *,
        activation_id: UUID | None = None,
    ) -> PaperRuntimeOwnershipModel:
        if type(owner_id) is not UUID or type(owner_generation) is not int:
            raise PaperRuntimeOwnerLost("owner guard is invalid")
        row = self.get_ownership(session, for_update=True)
        if (
            row is None
            or row.owner_id != owner_id
            or row.owner_generation != owner_generation
        ):
            raise PaperRuntimeOwnerLost("runtime ownership is no longer current")
        if (
            activation_id is not None
            and row.activation_id is not None
            and row.activation_id != activation_id
        ):
            raise PaperRuntimeOwnerLost(
                "runtime owner is attached to another activation"
            )
        return row

    def heartbeat_ownership(
        self,
        session: Session,
        *,
        owner_id: UUID,
        owner_generation: int,
        heartbeat_at: datetime | None = None,
        phase: PaperRuntimeOwnershipPhase | None = None,
    ) -> PaperRuntimeOwnershipModel:
        values: dict[str, Any] = {
            "heartbeat_at": heartbeat_at or _now(),
        }
        if phase is not None:
            if type(phase) is not PaperRuntimeOwnershipPhase:
                raise PaperRuntimePersistenceError("ownership phase is invalid")
            values["phase"] = phase.value
        result = session.execute(
            update(PaperRuntimeOwnershipModel)
            .where(
                PaperRuntimeOwnershipModel.slot_key == "ATLAS_PAPER_RUNTIME",
                PaperRuntimeOwnershipModel.owner_id == owner_id,
                PaperRuntimeOwnershipModel.owner_generation == owner_generation,
            )
            .values(**values)
        )
        cursor_result = result if isinstance(result, CursorResult) else None
        if cursor_result is None or cursor_result.rowcount != 1:
            raise PaperRuntimeOwnerLost("ownership heartbeat guard matched no row")
        row = self.get_ownership(session)
        if row is None:  # pragma: no cover - guarded update proves existence
            raise PaperRuntimeOwnershipNotFound("ATLAS_PAPER_RUNTIME")
        return row

    def guarded_owner_update(
        self,
        session: Session,
        *,
        owner_id: UUID,
        owner_generation: int,
        values: dict[str, object],
    ) -> PaperRuntimeOwnershipModel:
        """Apply an explicitly guarded ownership projection update."""
        if not values:
            raise PaperRuntimePersistenceError("guarded ownership update is empty")
        if set(values) - {"heartbeat_at", "phase", "activation_id"}:
            raise PaperRuntimePersistenceError(
                "guarded ownership update contains immutable fields"
            )
        result = session.execute(
            update(PaperRuntimeOwnershipModel)
            .where(
                PaperRuntimeOwnershipModel.slot_key == "ATLAS_PAPER_RUNTIME",
                PaperRuntimeOwnershipModel.owner_id == owner_id,
                PaperRuntimeOwnershipModel.owner_generation == owner_generation,
            )
            .values(**values)
        )
        cursor_result = result if isinstance(result, CursorResult) else None
        if cursor_result is None or cursor_result.rowcount != 1:
            raise PaperRuntimeOwnerLost("guarded ownership update matched no row")
        row = self.get_ownership(session)
        if row is None:  # pragma: no cover - guarded update proves existence
            raise PaperRuntimeOwnershipNotFound("ATLAS_PAPER_RUNTIME")
        return row

    def _verify_strategy_version(
        self, session: Session, activation: PaperRuntimeActivation
    ) -> None:
        version = session.get(StrategyVersionModel, activation.strategy_version_id)
        if version is None:
            raise PaperRuntimeIdentityConflict(
                "activation StrategyVersion does not exist"
            )
        if (
            version.version_number != activation.strategy_version_number
            or version.source_fingerprint != activation.source_fingerprint
            or version.implementation_key != activation.implementation_key
        ):
            raise PaperRuntimeIdentityConflict(
                "activation StrategyVersion identity does not match durable version"
            )
        strategy = version.strategy
        if strategy.strategy_key != activation.strategy_key:
            raise PaperRuntimeIdentityConflict(
                "activation Strategy key does not match durable version"
            )
        try:
            domain_version = version_to_domain(version)
            expected_parameters = ValidatedParameterPayload.from_mapping(
                domain_version.parameter_schema,
                activation.validated_parameter_snapshot.to_json(),
            )
        except Exception as error:
            raise PaperRuntimeIdentityConflict(
                "activation parameters do not match the durable Strategy schema"
            ) from error
        if expected_parameters != activation.validated_parameter_snapshot:
            raise PaperRuntimeIdentityConflict(
                "activation parameters do not match the durable Strategy schema"
            )


# Short aliases keep the repository discoverable alongside the PAPER 05
# repository's exception names without changing the explicit runtime names.
RuntimeRepositoryError = PaperRuntimeRepositoryError
RuntimeOwnerLost = PaperRuntimeOwnerLost


__all__ = [
    "InvalidPaperRuntimeTransition",
    "PaperRuntimeActivationAlreadyPresent",
    "PaperRuntimeActivationNotFound",
    "PaperRuntimeCycleConflict",
    "PaperRuntimeCycleNotFound",
    "PaperRuntimeIdentityConflict",
    "PaperRuntimeOwnershipNotFound",
    "PaperRuntimeOwnerLost",
    "PaperRuntimeRepository",
    "PaperRuntimeRepositoryError",
    "RuntimeOwnerLost",
    "RuntimeRepositoryError",
]
