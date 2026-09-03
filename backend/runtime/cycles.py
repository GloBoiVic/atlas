"""PAPER runtime frontier, Strategy-state, and cycle authority.

This module is the narrow handoff between the read-only PAPER analytical
boundary and the durable runtime ledger.  It does not schedule work or make
Risk/execution decisions.  It only proves that one exact completed frontier,
one exact activation state, and one coherent account observation can form one
cycle, then delegates Strategy evaluation to the immutable-frontier seam.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from backend.domain import (
    Action,
    FinancialPositionState,
    MarketSpecification,
    StrategyStateEnvelope,
)
from backend.integrations.oanda.account import is_valid_oanda_practice_account_id
from backend.integrations.oanda.execution_account import (
    OandaPracticeExecutionAccountSnapshot,
)
from backend.integrations.oanda.exposure_projection import (
    project_oanda_practice_eur_usd_exposure_state,
)
from backend.paper.current_analytical_frontier import CurrentAnalyticalFrontier
from backend.paper.persistence_contracts import PaperStrategyEvaluationReceipt
from backend.paper.strategy_evaluation import (
    evaluate_paper_strategy_frontier_receipt,
)
from backend.persistence.runtime_repository import (
    PaperRuntimeCycleConflict,
    PaperRuntimeRepository,
)
from backend.runtime.persistence_contracts import (
    PAPER_RUNTIME_BASE_CURRENCY,
    PAPER_RUNTIME_ENVIRONMENT,
    PAPER_RUNTIME_INSTRUMENT,
    PAPER_RUNTIME_PROVIDER,
    PaperRuntimeActivation,
    PaperRuntimeCycle,
    PaperRuntimeCycleStatus,
    PaperRuntimeLifecycleState,
    PaperRuntimePersistenceError,
    canonical_json_bytes,
    runtime_evaluation_key,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.paper.current_analytical_frontier import NativeM15Source
    from backend.persistence.strategy_repository import StrategyRepository
    from backend.strategies.registry import StrategyRegistry


Clock = Callable[[], datetime]


class PaperRuntimeStateAuthorityError(ValueError):
    """A state/frontier/account fact cannot safely authorize a cycle."""


class PaperRuntimeFrontierDuplicate(PaperRuntimeStateAuthorityError):
    """The activation already consumed this frontier."""


class PaperRuntimeFrontierGap(PaperRuntimeStateAuthorityError):
    """The activation missed the immediately next eligible frontier."""


class PaperRuntimeFrontierAlreadyConsumed(PaperRuntimeStateAuthorityError):
    """Another activation already consumed this global configuration/frontier."""


class PaperRuntimeUnattributedExposure(PaperRuntimeStateAuthorityError):
    """Non-flat exposure cannot be proven attributable to supported PAPER truth."""


class PaperRuntimeUnsupportedStrategyAction(PaperRuntimeStateAuthorityError):
    """Strategy requested a methodology action outside this runtime gate."""

    def __init__(
        self,
        message: str,
        *,
        receipt: PaperStrategyEvaluationReceipt | None = None,
    ) -> None:
        self.receipt = receipt
        super().__init__(message)


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PaperRuntimeStateAuthorityError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _bounded_text(value: object, name: str, maximum: int = 128) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise PaperRuntimeStateAuthorityError(f"{name} must be bounded and non-empty")
    if any(ord(character) < 32 for character in value):
        raise PaperRuntimeStateAuthorityError(f"{name} contains control characters")
    return value


@dataclass(frozen=True, slots=True)
class PaperRuntimeAccountObservation:
    """Bounded account facts used as Strategy-cycle input evidence.

    The observation is intentionally not Risk authority.  The opening path
    must obtain a later fresh PAPER 05 account read.  ``attributable`` is
    explicit so manual or otherwise unknown non-flat broker exposure cannot be
    silently fed into Strategy state.
    """

    provider_account_id: str
    account_transaction_id: str
    observed_at: datetime
    financial_position_state: FinancialPositionState
    open_trade_count: int
    open_position_count: int
    pending_order_count: int
    attributable: bool = True

    def __post_init__(self) -> None:
        if not is_valid_oanda_practice_account_id(self.provider_account_id):
            raise PaperRuntimeStateAuthorityError(
                "provider_account_id is not a supported OANDA Practice account"
            )
        _bounded_text(self.account_transaction_id, "account_transaction_id", 64)
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))
        if type(self.financial_position_state) is not FinancialPositionState:
            raise PaperRuntimeStateAuthorityError("financial_position_state is invalid")
        for name, value in (
            ("open_trade_count", self.open_trade_count),
            ("open_position_count", self.open_position_count),
            ("pending_order_count", self.pending_order_count),
        ):
            if type(value) is not int or value < 0:
                raise PaperRuntimeStateAuthorityError(f"{name} must be nonnegative")
        if type(self.attributable) is not bool:
            raise PaperRuntimeStateAuthorityError("attributable must be bool")
        exposed = self.open_trade_count > 0 or self.open_position_count > 0
        if (self.financial_position_state is FinancialPositionState.FLAT) is not (
            not exposed
        ):
            raise PaperRuntimeStateAuthorityError(
                "financial position does not match account exposure counts"
            )
        if exposed and not self.attributable:
            raise PaperRuntimeUnattributedExposure(
                "non-flat account exposure is unattributed"
            )

    @classmethod
    def from_oanda_snapshot(
        cls,
        snapshot: OandaPracticeExecutionAccountSnapshot,
        *,
        observed_at: datetime,
        attributable: bool = True,
    ) -> PaperRuntimeAccountObservation:
        """Convert normalized OANDA facts without retaining the provider body."""
        if type(snapshot) is not OandaPracticeExecutionAccountSnapshot:
            raise PaperRuntimeStateAuthorityError("OANDA account snapshot is invalid")
        try:
            financial_state = project_oanda_practice_eur_usd_exposure_state(
                snapshot.trades, snapshot.positions
            )
            return cls(
                provider_account_id=snapshot.identity.provider_account_id,
                account_transaction_id=snapshot.last_transaction_id,
                observed_at=observed_at,
                financial_position_state=financial_state,
                open_trade_count=snapshot.summary.open_trade_count,
                open_position_count=snapshot.summary.open_position_count,
                pending_order_count=snapshot.summary.pending_order_count,
                attributable=attributable,
            )
        except PaperRuntimeStateAuthorityError:
            raise
        except Exception as error:
            raise PaperRuntimeStateAuthorityError(
                "OANDA account facts cannot form a supported runtime observation"
            ) from error

    def to_json(self) -> dict[str, object]:
        return {
            "provider": PAPER_RUNTIME_PROVIDER,
            "environment": PAPER_RUNTIME_ENVIRONMENT,
            "provider_account_id": self.provider_account_id,
            "base_currency": PAPER_RUNTIME_BASE_CURRENCY,
            "instrument": PAPER_RUNTIME_INSTRUMENT,
            "account_transaction_id": self.account_transaction_id,
            "observed_at": self.observed_at.isoformat().replace("+00:00", "Z"),
            "financial_position_state": self.financial_position_state.value,
            "open_trade_count": self.open_trade_count,
            "open_position_count": self.open_position_count,
            "pending_order_count": self.pending_order_count,
            "attributable": self.attributable,
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            canonical_json_bytes(self.to_json(), maximum=32_768)
        ).hexdigest()


def _state_frontier(state: object) -> datetime | None:
    if type(state) is not StrategyStateEnvelope:
        raise PaperRuntimeStateAuthorityError(
            "durable Strategy state is not a StrategyStateEnvelope"
        )
    return state.last_evaluated_bar_end


class PaperRuntimeCycleAuthority:
    """Build, reserve, evaluate, and durably complete one runtime cycle."""

    def __init__(
        self,
        repository: PaperRuntimeRepository | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository or PaperRuntimeRepository()
        self._clock = clock or (lambda: datetime.now(UTC))

    def validate_frontier_progress(
        self,
        state: StrategyStateEnvelope | None,
        frontier: CurrentAnalyticalFrontier,
    ) -> None:
        """Require the current frontier to be the exact next eligible bar."""
        if type(frontier) is not CurrentAnalyticalFrontier:
            raise PaperRuntimeStateAuthorityError(
                "frontier must be CurrentAnalyticalFrontier"
            )
        try:
            frontier.validate()
        except Exception as error:
            raise PaperRuntimeStateAuthorityError(
                "frontier is not a validated completed analytical frontier"
            ) from error
        if state is None:
            return
        prior = _state_frontier(state)
        if prior is None:
            raise PaperRuntimeStateAuthorityError(
                "restored Strategy state has no prior analytical frontier"
            )
        if frontier.current_frontier <= prior:
            raise PaperRuntimeFrontierDuplicate(
                "frontier was already consumed by this activation"
            )
        if frontier.previous_frontier != prior:
            raise PaperRuntimeFrontierGap(
                "activation missed the immediately next eligible frontier"
            )

    def validate_activation_state(self, activation: PaperRuntimeActivation) -> None:
        """Prove the durable projection is internally resumable before a tick."""
        if type(activation) is not PaperRuntimeActivation:
            raise PaperRuntimeStateAuthorityError("activation is invalid")
        if activation.lifecycle_state is not PaperRuntimeLifecycleState.RUNNING:
            raise PaperRuntimeStateAuthorityError(
                "cycle authority requires a RUNNING activation"
            )
        state = activation.strategy_state
        if state is None:
            if (
                activation.last_frontier_end is not None
                or activation.last_cycle_id is not None
            ):
                raise PaperRuntimeStateAuthorityError(
                    "fresh activation contains stale Strategy frontier evidence"
                )
            return
        if activation.last_frontier_end != _state_frontier(state):
            raise PaperRuntimeStateAuthorityError(
                "activation frontier does not match Strategy state"
            )
        if activation.last_cycle_id is None:
            raise PaperRuntimeStateAuthorityError(
                "restored Strategy state has no owning cycle identity"
            )
        if state.pending_entry is not None:
            raise PaperRuntimeStateAuthorityError(
                "restored Strategy state has an unresolved pending entry"
            )

    def build_cycle(
        self,
        activation: PaperRuntimeActivation,
        frontier: CurrentAnalyticalFrontier,
        observation: PaperRuntimeAccountObservation,
        *,
        session: Session | None = None,
        cycle_id: UUID | None = None,
        claimed_at: datetime | None = None,
    ) -> PaperRuntimeCycle:
        """Create immutable cycle evidence before Strategy evaluation."""
        self.validate_activation_state(activation)
        if type(observation) is not PaperRuntimeAccountObservation:
            raise PaperRuntimeStateAuthorityError("account observation is invalid")
        if observation.provider_account_id != activation.provider_account_id:
            raise PaperRuntimeStateAuthorityError(
                "account observation identity does not match activation"
            )
        self.validate_frontier_progress(activation.strategy_state, frontier)
        selected_cycle_id = cycle_id or uuid4()
        if type(selected_cycle_id) is not UUID:
            raise PaperRuntimeStateAuthorityError("cycle_id must be a UUID")
        evaluation_key = runtime_evaluation_key(
            activation.strategy_version_id, activation.parameter_fingerprint
        )
        if session is not None:
            existing = self.repository.get_cycle_by_evaluation_frontier(
                session, evaluation_key, frontier.current_frontier
            )
            if existing is not None:
                if existing.activation_id != activation.activation_id:
                    raise PaperRuntimeFrontierAlreadyConsumed(
                        "Strategy configuration already consumed this frontier"
                    )
                raise PaperRuntimeFrontierDuplicate(
                    "frontier already has durable cycle evidence"
                )
            cycle_sequence = self.repository.next_cycle_sequence(
                session, activation.activation_id
            )
        else:
            cycle_sequence = 1
        try:
            return PaperRuntimeCycle(
                cycle_id=selected_cycle_id,
                activation_id=activation.activation_id,
                cycle_sequence=cycle_sequence,
                evaluation_key=evaluation_key,
                strategy_version_id=activation.strategy_version_id,
                parameter_fingerprint=activation.parameter_fingerprint,
                frontier_start=frontier.current_bar.start_time,
                frontier_end=frontier.current_frontier,
                prior_frontier_end=activation.last_frontier_end,
                state_before=activation.strategy_state,
                financial_position_state=observation.financial_position_state,
                account_transaction_id=observation.account_transaction_id,
                account_observed_at=observation.observed_at,
                account_open_trade_count=observation.open_trade_count,
                account_open_position_count=observation.open_position_count,
                account_pending_order_count=observation.pending_order_count,
                account_gate_fingerprint=observation.fingerprint,
                cycle_status=PaperRuntimeCycleStatus.CLAIMED,
                claimed_at=claimed_at or self._clock(),
            )
        except PaperRuntimePersistenceError as error:
            raise PaperRuntimeStateAuthorityError(
                "cycle evidence is not safely bounded"
            ) from error

    def reserve_cycle(
        self,
        session: Session,
        activation: PaperRuntimeActivation,
        frontier: CurrentAnalyticalFrontier,
        observation: PaperRuntimeAccountObservation,
        *,
        owner_id: UUID,
        owner_generation: int,
        cycle_id: UUID | None = None,
        claimed_at: datetime | None = None,
    ) -> object:
        """Reserve one cycle through the owner-guarded repository boundary."""
        cycle = self.build_cycle(
            activation,
            frontier,
            observation,
            session=session,
            cycle_id=cycle_id,
            claimed_at=claimed_at,
        )
        try:
            return self.repository.reserve_cycle(
                session,
                cycle,
                owner_id=owner_id,
                owner_generation=owner_generation,
            )
        except PaperRuntimeCycleConflict as error:
            raise PaperRuntimeFrontierAlreadyConsumed(
                "frontier reservation conflicted with durable evidence"
            ) from error

    def evaluate_cycle(
        self,
        session: Session,
        activation: PaperRuntimeActivation,
        frontier: CurrentAnalyticalFrontier,
        observation: PaperRuntimeAccountObservation,
        *,
        strategy_repository: StrategyRepository,
        strategy_registry: StrategyRegistry,
        analytical_source: NativeM15Source,
        market_specification: MarketSpecification,
        now: datetime,
    ) -> PaperStrategyEvaluationReceipt:
        """Evaluate the exact frontier with the exact activation state/input."""
        self.validate_activation_state(activation)
        if observation.provider_account_id != activation.provider_account_id:
            raise PaperRuntimeStateAuthorityError(
                "account observation identity does not match activation"
            )
        self.validate_frontier_progress(activation.strategy_state, frontier)
        receipt = evaluate_paper_strategy_frontier_receipt(
            session,
            strategy_version_id=activation.strategy_version_id,
            parameter_values=activation.validated_parameter_snapshot.to_json(),
            state=activation.strategy_state,
            financial_position_state=observation.financial_position_state,
            now=now,
            frontier=frontier,
            strategy_repository=strategy_repository,
            strategy_registry=strategy_registry,
            analytical_source=analytical_source,
            market_specification=market_specification,
        )
        if (
            observation.financial_position_state is not FinancialPositionState.FLAT
            and receipt.evaluation.decision.action is not Action.NO_ACTION
        ):
            raise PaperRuntimeUnsupportedStrategyAction(
                "non-flat runtime evaluation produced a capital action",
                receipt=receipt,
            )
        return receipt

    def persist_evaluation(
        self,
        session: Session,
        cycle_id: UUID,
        activation: PaperRuntimeActivation,
        receipt: PaperStrategyEvaluationReceipt,
        *,
        owner_id: UUID,
        owner_generation: int,
        cycle_status: PaperRuntimeCycleStatus = PaperRuntimeCycleStatus.NO_ACTION,
        attempt_id: UUID | None = None,
        reason_code: str | None = None,
    ) -> object:
        """Persist Strategy evidence/state through one caller-owned transaction."""
        if type(activation) is not PaperRuntimeActivation:
            raise PaperRuntimeStateAuthorityError("activation is invalid")
        if type(receipt) is not PaperStrategyEvaluationReceipt:
            raise PaperRuntimeStateAuthorityError("Strategy receipt is invalid")
        if (
            receipt.strategy_version_id != activation.strategy_version_id
            or receipt.strategy_key != activation.strategy_key
            or receipt.version_number != activation.strategy_version_number
            or receipt.source_fingerprint != activation.source_fingerprint
            or receipt.implementation_key != activation.implementation_key
            or receipt.validated_parameter_snapshot
            != activation.validated_parameter_snapshot
        ):
            raise PaperRuntimeStateAuthorityError(
                "Strategy receipt identity does not match activation"
            )
        evaluation = receipt.evaluation
        state_after = evaluation.next_state
        if type(state_after) is not StrategyStateEnvelope:
            raise PaperRuntimeStateAuthorityError(
                "Strategy evaluation did not produce a state envelope"
            )
        try:
            return self.repository.persist_cycle_evaluation(
                session,
                cycle_id,
                state_after=state_after,
                strategy_evaluation_snapshot=evaluation,
                decision_snapshot=evaluation.decision,
                cycle_status=cycle_status,
                owner_id=owner_id,
                owner_generation=owner_generation,
                attempt_id=attempt_id,
                reason_code=reason_code,
            )
        except PaperRuntimePersistenceError as error:
            raise PaperRuntimeStateAuthorityError(
                "Strategy evaluation evidence could not be persisted safely"
            ) from error


__all__ = [
    "PaperRuntimeAccountObservation",
    "PaperRuntimeCycleAuthority",
    "PaperRuntimeFrontierAlreadyConsumed",
    "PaperRuntimeFrontierDuplicate",
    "PaperRuntimeFrontierGap",
    "PaperRuntimeStateAuthorityError",
    "PaperRuntimeUnsupportedStrategyAction",
    "PaperRuntimeUnattributedExposure",
]
