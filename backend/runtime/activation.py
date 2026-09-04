"""Application contracts for explicit local PAPER runtime control.

This module is deliberately narrower than the runtime loop.  It validates and
persists an operator's activation intent, projects local control state, and
delegates reconciliation to PAPER 05.  It does not acquire runtime ownership,
evaluate a Strategy, read OANDA, or submit a broker mutation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain import (
    FinancialPositionState,
    Instrument,
    PriceComponent,
    StrategyStateEnvelope,
    ValidatedParameterPayload,
)
from backend.integrations.oanda.account import is_valid_oanda_practice_account_id
from backend.persistence.models import (
    PaperExecutionAttemptModel,
    PaperRuntimeActivationModel,
    PaperRuntimeCycleModel,
    StrategyVersionModel,
)
from backend.persistence.runtime_repository import (
    PaperRuntimeActivationAlreadyPresent,
    PaperRuntimeIdentityConflict,
    PaperRuntimeRepository,
    is_unsafe_paper_attempt,
)
from backend.persistence.strategy_repository import (
    StrategyRepository,
    version_to_domain,
)
from backend.runtime.persistence_contracts import (
    PAPER_RUNTIME_APPROVAL_CODE,
    PAPER_RUNTIME_APPROVAL_KIND,
    PAPER_RUNTIME_BASE_CURRENCY,
    PAPER_RUNTIME_ENVIRONMENT,
    PAPER_RUNTIME_INSTRUMENT,
    PAPER_RUNTIME_POLICY_V1,
    PAPER_RUNTIME_POLL_INTERVAL_SECONDS,
    PAPER_RUNTIME_PROVIDER,
    PaperRuntimeActivation,
    PaperRuntimeLifecycleState,
    PaperRuntimeOperationalPhase,
    PaperRuntimePersistenceError,
    PaperRuntimeStateOrigin,
    runtime_parameter_fingerprint,
)
from backend.strategies.registry import (
    StrategyRegistry,
    StrategyVersionUnavailableError,
)


class PaperRuntimeServiceError(RuntimeError):
    """Safe, bounded application error suitable for an HTTP error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


class PaperRuntimeConfigurationError(PaperRuntimeServiceError):
    """The local activation configuration cannot safely authorize a session."""


class PaperRuntimeControlConflict(PaperRuntimeServiceError):
    """A control operation is not permitted by the durable runtime state."""


@dataclass(frozen=True, slots=True)
class PaperActivationRequest:
    """Strict, non-secret facts supplied by an explicit local trader request."""

    activation_request_id: UUID
    strategy_version_id: UUID
    parameters: dict[str, object]
    risk_per_trade: Decimal
    confirmation: str

    def __post_init__(self) -> None:
        if type(self.activation_request_id) is not UUID:
            raise PaperRuntimePersistenceError("activation_request_id must be a UUID")
        if type(self.strategy_version_id) is not UUID:
            raise PaperRuntimePersistenceError("strategy_version_id must be a UUID")
        if type(self.parameters) is not dict:
            raise PaperRuntimePersistenceError("parameters must be an object")
        if (
            type(self.risk_per_trade) is not Decimal
            or not self.risk_per_trade.is_finite()
        ):
            raise PaperRuntimePersistenceError(
                "risk_per_trade must be a finite Decimal"
            )
        if not 0 < self.risk_per_trade < 1:
            raise PaperRuntimePersistenceError(
                "risk_per_trade must be greater than zero and less than one"
            )
        if self.confirmation != PAPER_RUNTIME_APPROVAL_CODE:
            raise PaperRuntimePersistenceError("activation confirmation is invalid")
        object.__setattr__(self, "parameters", dict(self.parameters))


@dataclass(frozen=True, slots=True)
class PaperStopRequest:
    """A bounded operator STOP request; it never describes broker cancellation."""

    reason: str

    def __post_init__(self) -> None:
        if type(self.reason) is not str or not self.reason or len(self.reason) > 500:
            raise PaperRuntimePersistenceError(
                "STOP reason must be bounded and non-empty"
            )
        if any(ord(character) < 32 for character in self.reason):
            raise PaperRuntimePersistenceError(
                "STOP reason contains control characters"
            )


@dataclass(frozen=True, slots=True)
class PaperRuntimeCapability:
    """Local capability/configuration facts, with no credential material."""

    provider: str = PAPER_RUNTIME_PROVIDER
    environment: str = PAPER_RUNTIME_ENVIRONMENT
    base_currency: str = PAPER_RUNTIME_BASE_CURRENCY
    instrument: str = PAPER_RUNTIME_INSTRUMENT
    analytical_resolution: str = "M15"
    analytical_price_component: str = "MID"
    poll_interval_seconds: int = PAPER_RUNTIME_POLL_INTERVAL_SECONDS
    token_configured: bool = False
    account_configured: bool = False
    configured_account_id: str | None = None
    available: bool = False
    reason_code: str | None = None
    activation_required: bool = True

    def __post_init__(self) -> None:
        if (
            self.provider != PAPER_RUNTIME_PROVIDER
            or self.environment != PAPER_RUNTIME_ENVIRONMENT
        ):
            raise PaperRuntimePersistenceError("capability scope is not supported")
        if self.base_currency != PAPER_RUNTIME_BASE_CURRENCY:
            raise PaperRuntimePersistenceError("capability currency is not supported")
        if self.instrument != PAPER_RUNTIME_INSTRUMENT:
            raise PaperRuntimePersistenceError("capability instrument is not supported")
        if (
            self.analytical_resolution != "M15"
            or self.analytical_price_component != "MID"
        ):
            raise PaperRuntimePersistenceError(
                "capability analytical contract is not supported"
            )
        if self.poll_interval_seconds != PAPER_RUNTIME_POLL_INTERVAL_SECONDS:
            raise PaperRuntimePersistenceError(
                "capability poll interval is not supported"
            )
        if (
            type(self.token_configured) is not bool
            or type(self.account_configured) is not bool
        ):
            raise PaperRuntimePersistenceError(
                "capability configuration flags are invalid"
            )
        if (
            type(self.available) is not bool
            or type(self.activation_required) is not bool
        ):
            raise PaperRuntimePersistenceError("capability flags are invalid")
        if (
            self.configured_account_id is not None
            and not is_valid_oanda_practice_account_id(self.configured_account_id)
        ):
            raise PaperRuntimePersistenceError("capability account ID is invalid")
        expected = self.token_configured and self.account_configured
        if self.available is not expected:
            raise PaperRuntimePersistenceError(
                "capability availability is inconsistent"
            )

    def to_json(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "environment": self.environment,
            "base_currency": self.base_currency,
            "instrument": self.instrument,
            "analytical_resolution": self.analytical_resolution,
            "analytical_price_component": self.analytical_price_component,
            "poll_interval_seconds": self.poll_interval_seconds,
            "token_configured": self.token_configured,
            "account_configured": self.account_configured,
            "configured_account_id": self.configured_account_id,
            "available": self.available,
            "reason_code": self.reason_code,
            "activation_required": self.activation_required,
        }


@dataclass(frozen=True, slots=True)
class PaperRuntimeActivationResult:
    """Activation evidence and whether the request was an exact replay."""

    activation: PaperRuntimeActivation
    replayed: bool

    def to_json(self) -> dict[str, object]:
        return {"activation": self.activation.to_json(), "replayed": self.replayed}


@dataclass(frozen=True, slots=True)
class PaperRuntimeReconcileResult:
    """Bounded reconciliation result without granting mutation authority."""

    activation_id: UUID
    attempt_id: UUID | None
    performed: bool
    reconciliation_status: str | None
    execution_outcome: str | None
    stale: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "activation_id": str(self.activation_id),
            "attempt_id": str(self.attempt_id) if self.attempt_id else None,
            "performed": self.performed,
            "reconciliation_status": (
                _enum_text(self.reconciliation_status)
                if self.reconciliation_status is not None
                else None
            ),
            "execution_outcome": (
                _enum_text(self.execution_outcome)
                if self.execution_outcome is not None
                else None
            ),
            "stale": self.stale,
        }


@dataclass(frozen=True, slots=True)
class PaperRuntimeStatus:
    """Separate runtime lifecycle from broker/execution evidence."""

    activation: PaperRuntimeActivation
    current_financial_position_state: FinancialPositionState | None = None
    execution_outcome: str | None = None
    reconciliation_status: str = "NOT_RUN"
    terminal_runtime_state_does_not_prove_flat: bool = True

    def __post_init__(self) -> None:
        if type(self.activation) is not PaperRuntimeActivation:
            raise PaperRuntimePersistenceError("status activation is invalid")
        if (
            self.current_financial_position_state is not None
            and type(self.current_financial_position_state)
            is not FinancialPositionState
        ):
            raise PaperRuntimePersistenceError("status financial position is invalid")
        if self.execution_outcome is not None and _enum_text(
            self.execution_outcome
        ) not in {
            "FILLED_PROTECTED",
            "FILLED_PROTECTION_INCOMPLETE",
            "REJECTED",
            "CANCELLED",
            "UNKNOWN",
        }:
            raise PaperRuntimePersistenceError("status execution outcome is invalid")
        if _enum_text(self.reconciliation_status) not in {
            "NOT_RUN",
            "CONSISTENT",
            "UNRESOLVED",
            "CONFLICT",
            "LIFECYCLE_ADVANCED",
        }:
            raise PaperRuntimePersistenceError(
                "status reconciliation status is invalid"
            )
        if self.terminal_runtime_state_does_not_prove_flat is not True:
            raise PaperRuntimePersistenceError(
                "terminal runtime status must not be used as flatness proof"
            )

    def to_json(self) -> dict[str, object]:
        return {
            "activation": self.activation.to_json(),
            "current_financial_position_state": (
                self.current_financial_position_state.value
                if self.current_financial_position_state is not None
                else None
            ),
            "execution_outcome": (
                _enum_text(self.execution_outcome)
                if self.execution_outcome is not None
                else None
            ),
            "reconciliation_status": _enum_text(self.reconciliation_status),
            "terminal_runtime_state_does_not_prove_flat": (
                self.terminal_runtime_state_does_not_prove_flat
            ),
        }


class ReconciliationCoordinator(Protocol):
    """The existing PAPER 05 GET-only application seam."""

    def reconcile(self, attempt_id: UUID, *, read_budget: int = 8) -> Any: ...


SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PaperRuntimeServiceError("RUNTIME_STATE_INVALID", f"{name} is invalid")
    return value.astimezone(UTC)


def _token_is_configured(settings: object) -> bool:
    token = getattr(settings, "oanda_api_token", None)
    if token is None:
        return False
    getter = getattr(token, "get_secret_value", None)
    if callable(getter):
        try:
            return bool(getter())
        except Exception:
            return False
    return isinstance(token, str) and bool(token)


def _configured_account_id(settings: object) -> str | None:
    value = getattr(settings, "oanda_account_id", None)
    return value if is_valid_oanda_practice_account_id(value) else None


def _enum_text(value: object) -> str:
    candidate = getattr(value, "value", value)
    if type(candidate) is not str:
        raise PaperRuntimePersistenceError("runtime status value is invalid")
    return candidate


def _safe_configuration_error(
    code: str, message: str
) -> PaperRuntimeConfigurationError:
    return PaperRuntimeConfigurationError(code, message)


def _activation_from_row(
    session: Session, row: PaperRuntimeActivationModel
) -> PaperRuntimeActivation:
    """Restore the exact typed activation projection without exposing secrets."""
    try:
        version_row = session.get(StrategyVersionModel, row.strategy_version_id)
        if version_row is None:
            raise ValueError("StrategyVersion is missing")
        version = version_to_domain(version_row)
        parameters = ValidatedParameterPayload.from_mapping(
            version.parameter_schema,
            cast(dict[str, object], row.validated_parameter_snapshot),
        )
        state = (
            StrategyStateEnvelope.from_json(cast(dict[str, object], row.strategy_state))
            if row.strategy_state is not None
            else None
        )
        return PaperRuntimeActivation(
            activation_id=row.activation_id,
            strategy_version_id=row.strategy_version_id,
            strategy_key=row.strategy_key,
            strategy_version_number=row.strategy_version_number,
            source_fingerprint=row.source_fingerprint,
            implementation_key=row.implementation_key,
            validated_parameter_snapshot=parameters,
            parameter_fingerprint=row.parameter_fingerprint,
            risk_per_trade=Decimal(row.risk_per_trade),
            requested_at=_utc(row.requested_at, "requested_at"),
            provider=row.provider,
            environment=row.environment,
            provider_account_id=row.provider_account_id,
            base_currency=row.base_currency,
            instrument=row.instrument,
            state_origin=PaperRuntimeStateOrigin(row.state_origin),
            runtime_policy_version=row.runtime_policy_version,
            poll_interval_seconds=row.poll_interval_seconds,
            approval_kind=row.approval_kind,
            approval_code=row.approval_code,
            lifecycle_state=PaperRuntimeLifecycleState(row.lifecycle_state),
            state_reason_code=row.state_reason_code,
            state_detail=row.state_detail,
            state_changed_at=_utc(row.state_changed_at, "state_changed_at"),
            operational_phase=PaperRuntimeOperationalPhase(row.operational_phase),
            last_operational_reason_code=row.last_operational_reason_code,
            last_operational_at=(
                _utc(row.last_operational_at, "last_operational_at")
                if row.last_operational_at is not None
                else None
            ),
            strategy_state=state,
            strategy_state_fingerprint=row.strategy_state_fingerprint,
            last_frontier_end=(
                _utc(row.last_frontier_end, "last_frontier_end")
                if row.last_frontier_end is not None
                else None
            ),
            last_cycle_id=row.last_cycle_id,
            control_version=row.control_version,
            updated_at=_utc(row.updated_at, "updated_at"),
        )
    except PaperRuntimePersistenceError:
        raise
    except Exception as error:
        raise PaperRuntimeServiceError(
            "RUNTIME_STATE_INVALID", "durable runtime state is invalid"
        ) from error


class PaperRuntimeService:
    """Guarded activation/control service over T001 persistence primitives."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        settings: object,
        registry: StrategyRegistry,
        repository: PaperRuntimeRepository | None = None,
        strategies: StrategyRepository | None = None,
        reconciliation: ReconciliationCoordinator | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._registry = registry
        self._repository = repository or PaperRuntimeRepository()
        self._strategies = strategies or StrategyRepository()
        self._reconciliation = reconciliation
        self._clock = clock or (lambda: datetime.now(UTC))

    def capability(self) -> PaperRuntimeCapability:
        token_configured = _token_is_configured(self._settings)
        account_id = _configured_account_id(self._settings)
        account_configured = account_id is not None
        reason_code = None
        if not token_configured:
            reason_code = "OANDA_TOKEN_NOT_CONFIGURED"
        elif not account_configured:
            reason_code = "OANDA_ACCOUNT_NOT_CONFIGURED"
        return PaperRuntimeCapability(
            token_configured=token_configured,
            account_configured=account_configured,
            configured_account_id=account_id,
            available=token_configured and account_configured,
            reason_code=reason_code,
        )

    def activate(self, request: PaperActivationRequest) -> PaperRuntimeActivationResult:
        if type(request) is not PaperActivationRequest:
            raise _safe_configuration_error(
                "ACTIVATION_REQUEST_INVALID", "activation request is invalid"
            )
        self._require_activation_configuration()
        now = self._now()
        with self._session_factory() as session:
            with session.begin():
                existing = self._repository.get_activation(
                    session, request.activation_request_id
                )
                if existing is None and self._new_session_history_blocker_exists(
                    session, cast(str, _configured_account_id(self._settings))
                ):
                    raise PaperRuntimeServiceError(
                        "PAPER_ATTEMPT_UNSAFE",
                        "an unresolved PAPER execution prevents activation",
                    )
                activation = self._build_activation(session, request, now)
                try:
                    row = self._repository.create_activation(session, activation)
                except PaperRuntimeIdentityConflict as error:
                    raise PaperRuntimeServiceError(
                        "ACTIVATION_IDENTITY_CONFLICT",
                        "activation request identity conflicts with durable evidence",
                    ) from error
                except PaperRuntimeActivationAlreadyPresent as error:
                    raise PaperRuntimeServiceError(
                        "PAPER_ACTIVATION_ALREADY_PRESENT",
                        "another PAPER activation is already active",
                    ) from error
                except PaperRuntimePersistenceError as error:
                    raise _safe_configuration_error(
                        "ACTIVATION_CONFIGURATION_INVALID",
                        "activation configuration is invalid",
                    ) from error
                return PaperRuntimeActivationResult(
                    activation=_activation_from_row(session, row),
                    replayed=existing is not None,
                )

    def get_active(self) -> PaperRuntimeActivation | None:
        with self._session_factory() as session:
            row = self._repository.get_active_activation(session)
            return _activation_from_row(session, row) if row is not None else None

    def get(self, activation_id: UUID) -> PaperRuntimeActivation:
        if type(activation_id) is not UUID:
            raise PaperRuntimeServiceError(
                "ACTIVATION_NOT_FOUND", "activation was not found"
            )
        with self._session_factory() as session:
            row = self._repository.get_activation(session, activation_id)
            if row is None:
                raise PaperRuntimeServiceError(
                    "ACTIVATION_NOT_FOUND", "activation was not found"
                )
            return _activation_from_row(session, row)

    def stop(
        self, activation_id: UUID, request: PaperStopRequest
    ) -> PaperRuntimeActivation:
        if type(request) is not PaperStopRequest:
            raise PaperRuntimeServiceError(
                "STOP_REQUEST_INVALID", "STOP request is invalid"
            )
        if type(activation_id) is not UUID:
            raise PaperRuntimeServiceError(
                "ACTIVATION_NOT_FOUND", "activation was not found"
            )
        with self._session_factory() as session:
            with session.begin():
                row = self._repository.get_activation(
                    session, activation_id, for_update=True
                )
                if row is None:
                    raise PaperRuntimeServiceError(
                        "ACTIVATION_NOT_FOUND", "activation was not found"
                    )
                current = PaperRuntimeLifecycleState(row.lifecycle_state)
                if current not in {
                    PaperRuntimeLifecycleState.STOP_REQUESTED,
                    PaperRuntimeLifecycleState.STOPPED,
                    PaperRuntimeLifecycleState.BLOCKED,
                    PaperRuntimeLifecycleState.FAILED,
                }:
                    try:
                        row = self._repository.request_stop(
                            session,
                            activation_id,
                            reason_code="OPERATOR_STOP",
                            reason_detail=request.reason,
                        )
                    except PaperRuntimeIdentityConflict as error:
                        raise PaperRuntimeControlConflict(
                            "STOP_CONFLICT", "STOP could not be applied safely"
                        ) from error
                return _activation_from_row(session, row)

    def status(self, activation_id: UUID) -> PaperRuntimeStatus:
        activation = self.get(activation_id)
        with self._session_factory() as session:
            attempt = self._latest_attempt(session, activation_id)
            outcome: str | None = None
            reconciliation_status = "NOT_RUN"
            if attempt is not None:
                outcome = attempt.execution_outcome
                reconciliation_status = attempt.reconciliation_status
            # Current account position is deliberately unknown here.  It must be
            # projected from a fresh supported account observation by the runtime;
            # an old attempt or terminal lifecycle is never flatness proof.
            return PaperRuntimeStatus(
                activation=activation,
                execution_outcome=outcome,
                reconciliation_status=reconciliation_status,
            )

    def reconcile(
        self, activation_id: UUID, *, read_budget: int | None = None
    ) -> PaperRuntimeReconcileResult:
        if type(activation_id) is not UUID:
            raise PaperRuntimeServiceError(
                "ACTIVATION_NOT_FOUND", "activation was not found"
            )
        if self._reconciliation is None:
            raise PaperRuntimeServiceError(
                "RECONCILIATION_UNAVAILABLE", "PAPER reconciliation is unavailable"
            )
        with self._session_factory() as session:
            row = self._repository.get_activation(
                session, activation_id, for_update=True
            )
            if row is None:
                raise PaperRuntimeServiceError(
                    "ACTIVATION_NOT_FOUND", "activation was not found"
                )
            lifecycle = PaperRuntimeLifecycleState(row.lifecycle_state)
            if lifecycle in {
                PaperRuntimeLifecycleState.REQUESTED,
                PaperRuntimeLifecycleState.STARTING,
                PaperRuntimeLifecycleState.RUNNING,
                PaperRuntimeLifecycleState.STOP_REQUESTED,
            }:
                raise PaperRuntimeServiceError(
                    "RUNTIME_RECONCILIATION_BUSY",
                    "the active runtime owns reconciliation recovery",
                )
            attempt = self._latest_attempt(session, activation_id)
            if attempt is None or not self._attempt_is_outstanding(attempt):
                return PaperRuntimeReconcileResult(
                    activation_id=activation_id,
                    attempt_id=attempt.attempt_id if attempt is not None else None,
                    performed=False,
                    reconciliation_status=(
                        attempt.reconciliation_status if attempt is not None else None
                    ),
                    execution_outcome=(
                        attempt.execution_outcome if attempt is not None else None
                    ),
                )
            attempt_id = attempt.attempt_id

        # The coordinator owns its own bounded read/apply transaction.  Keeping
        # this call outside the activation read transaction avoids pretending the
        # non-atomic provider reads are protected by the activation row lock.
        try:
            result = (
                self._reconciliation.reconcile(attempt_id)
                if read_budget is None
                else self._reconciliation.reconcile(attempt_id, read_budget=read_budget)
            )
        except Exception as error:
            from backend.persistence.paper_execution_repository import (
                PaperAttemptNotFound,
            )

            if isinstance(error, PaperAttemptNotFound):
                raise PaperRuntimeServiceError(
                    "RECONCILIATION_ATTEMPT_NOT_FOUND",
                    "the durable reconciliation attempt was not found",
                ) from error
            raise PaperRuntimeServiceError(
                "RECONCILIATION_FAILED", "the bounded reconciliation pass failed"
            ) from error
        execution_outcome = getattr(result, "execution_outcome", None)
        return PaperRuntimeReconcileResult(
            activation_id=activation_id,
            attempt_id=attempt_id,
            performed=True,
            reconciliation_status=(
                _enum_text(result.reconciliation_status)
                if result.reconciliation_status is not None
                else None
            ),
            execution_outcome=(
                _enum_text(execution_outcome) if execution_outcome is not None else None
            ),
            stale=bool(getattr(result, "stale", False)),
        )

    def _require_activation_configuration(self) -> None:
        if not _token_is_configured(self._settings):
            raise _safe_configuration_error(
                "OANDA_TOKEN_REQUIRED", "OANDA Practice token configuration is required"
            )
        if _configured_account_id(self._settings) is None:
            raise _safe_configuration_error(
                "OANDA_ACCOUNT_REQUIRED",
                "OANDA Practice account configuration is required",
            )

    def _build_activation(
        self,
        session: Session,
        request: PaperActivationRequest,
        requested_at: datetime,
    ) -> PaperRuntimeActivation:
        row = self._strategies.get_version(session, request.strategy_version_id)
        if row is None:
            raise _safe_configuration_error(
                "STRATEGY_VERSION_NOT_FOUND", "StrategyVersion was not found"
            )
        try:
            version = version_to_domain(row)
            registration = self._registry.get(
                row.strategy.strategy_key,
                implementation_key=row.implementation_key,
                source_fingerprint=row.source_fingerprint,
            )
        except StrategyVersionUnavailableError as error:
            raise _safe_configuration_error(
                "STRATEGY_VERSION_UNAVAILABLE",
                "no exact local Strategy implementation is registered",
            ) from error
        except Exception as error:
            raise _safe_configuration_error(
                "STRATEGY_VERSION_INVALID", "StrategyVersion provenance is invalid"
            ) from error

        definition = registration.definition
        if (
            definition.strategy_key != version.strategy_key
            or definition.implementation_key != version.implementation_key
            or definition.required_instrument is not Instrument.EUR_USD
            or definition.required_resolution.value != "15m"
            or definition.required_price_component is not PriceComponent.MID
            or not definition.completed_only
            or definition.parameter_schema != version.parameter_schema
        ):
            raise _safe_configuration_error(
                "STRATEGY_PROVENANCE_DRIFT",
                "local Strategy provenance does not match the durable version",
            )
        try:
            parameters = ValidatedParameterPayload.from_mapping(
                version.parameter_schema, request.parameters
            )
            parser = getattr(registration.implementation, "parse_parameters", None)
            if not callable(parser):
                raise TypeError("Strategy parameter parser is unavailable")
            parser(parameters)
        except Exception as error:
            raise _safe_configuration_error(
                "PARAMETERS_INVALID",
                "parameters do not exactly match the Strategy schema",
            ) from error

        account_id = cast(str, _configured_account_id(self._settings))
        try:
            return PaperRuntimeActivation(
                activation_id=request.activation_request_id,
                strategy_version_id=request.strategy_version_id,
                strategy_key=version.strategy_key,
                strategy_version_number=version.version_number,
                source_fingerprint=version.source_fingerprint,
                implementation_key=version.implementation_key,
                validated_parameter_snapshot=parameters,
                parameter_fingerprint=runtime_parameter_fingerprint(parameters),
                risk_per_trade=request.risk_per_trade,
                requested_at=requested_at,
                provider=PAPER_RUNTIME_PROVIDER,
                environment=PAPER_RUNTIME_ENVIRONMENT,
                provider_account_id=account_id,
                base_currency=PAPER_RUNTIME_BASE_CURRENCY,
                instrument=PAPER_RUNTIME_INSTRUMENT,
                state_origin=PaperRuntimeStateOrigin.FRESH_BOOTSTRAP,
                runtime_policy_version=PAPER_RUNTIME_POLICY_V1,
                poll_interval_seconds=PAPER_RUNTIME_POLL_INTERVAL_SECONDS,
                approval_kind=PAPER_RUNTIME_APPROVAL_KIND,
                approval_code=PAPER_RUNTIME_APPROVAL_CODE,
            )
        except PaperRuntimePersistenceError as error:
            raise _safe_configuration_error(
                "ACTIVATION_CONFIGURATION_INVALID",
                "activation configuration is invalid",
            ) from error

    def _latest_attempt(
        self, session: Session, activation_id: UUID
    ) -> PaperExecutionAttemptModel | None:
        return session.scalar(
            select(PaperExecutionAttemptModel)
            .join(
                PaperRuntimeCycleModel,
                PaperRuntimeCycleModel.attempt_id
                == PaperExecutionAttemptModel.attempt_id,
            )
            .where(
                PaperRuntimeCycleModel.activation_id == activation_id,
                PaperRuntimeCycleModel.attempt_id.is_not(None),
            )
            .order_by(PaperRuntimeCycleModel.cycle_sequence.desc())
            .limit(1)
        )

    def _unsafe_attempt_exists(self, session: Session, account_id: str) -> bool:
        """Use the repository's single durable-attempt safety predicate."""
        return self._repository.has_unsafe_attempt(session, account_id)

    def _new_session_history_blocker_exists(
        self, session: Session, account_id: str
    ) -> bool:
        """Use the separate account-wide fresh-session history classifier."""
        return self._repository.has_new_session_blocker(session, account_id)

    @staticmethod
    def _attempt_is_outstanding(row: PaperExecutionAttemptModel) -> bool:
        return is_unsafe_paper_attempt(row.execution_outcome, row.reconciliation_status)

    def _now(self) -> datetime:
        try:
            return _utc(self._clock(), "activation clock")
        except PaperRuntimeServiceError:
            raise
        except Exception as error:
            raise PaperRuntimeServiceError(
                "RUNTIME_CLOCK_INVALID", "runtime clock is invalid"
            ) from error


# Explicit aliases make the control seams discoverable without duplicating
# persistence or reconciliation logic.  T006/T007 can depend on the specific
# name that best matches their call site.
PaperRuntimeActivationService = PaperRuntimeService
PaperRuntimeControlService = PaperRuntimeService
PaperRuntimeReconciliationService = PaperRuntimeService


__all__ = [
    "PaperActivationRequest",
    "PaperRuntimeActivationResult",
    "PaperRuntimeActivationService",
    "PaperRuntimeCapability",
    "PaperRuntimeConfigurationError",
    "PaperRuntimeControlConflict",
    "PaperRuntimeControlService",
    "PaperRuntimeReconcileResult",
    "PaperRuntimeReconciliationService",
    "PaperRuntimeService",
    "PaperRuntimeServiceError",
    "PaperRuntimeStatus",
    "PaperStopRequest",
]
