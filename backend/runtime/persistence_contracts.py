"""Bounded contracts for the durable PAPER runtime projection.

The runtime ledger is deliberately separate from the PAPER 05 execution
ledger.  These values describe an explicitly approved local runtime session,
the analytical frontiers it reserved, and the durable projection of its one
owner.  They contain no credentials and do not grant broker mutation
authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import cast
from uuid import UUID

from backend.domain import (
    FinancialPositionState,
    StrategyDecision,
    StrategyEvaluation,
    StrategyStateEnvelope,
    ValidatedParameterPayload,
)

MAX_RUNTIME_JSON_BYTES = 32_768
PAPER_RUNTIME_POLICY_V1 = "ATLAS_PAPER_RUNTIME_V1"
PAPER_RUNTIME_SLOT = "ATLAS_PAPER_RUNTIME"
PAPER_RUNTIME_PROVIDER = "OANDA"
PAPER_RUNTIME_ENVIRONMENT = "PRACTICE"
PAPER_RUNTIME_BASE_CURRENCY = "USD"
PAPER_RUNTIME_INSTRUMENT = "EUR_USD"
PAPER_RUNTIME_POLL_INTERVAL_SECONDS = 15
PAPER_RUNTIME_APPROVAL_KIND = "EXPLICIT_LOCAL_TRADER"
PAPER_RUNTIME_APPROVAL_CODE = "ACTIVATE_PAPER"


class PaperRuntimePersistenceError(ValueError):
    """A runtime persistence value is invalid or cannot be bounded safely."""


class PaperRuntimeLifecycleState(StrEnum):
    REQUESTED = "REQUESTED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOP_REQUESTED = "STOP_REQUESTED"
    STOPPED = "STOPPED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class PaperRuntimeStateOrigin(StrEnum):
    FRESH_BOOTSTRAP = "FRESH_BOOTSTRAP"


class PaperRuntimeOperationalPhase(StrEnum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    WAITING_FRONTIER = "WAITING_FRONTIER"
    WAITING_DATA = "WAITING_DATA"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    EVALUATING = "EVALUATING"
    EXECUTING = "EXECUTING"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class PaperRuntimeCycleStatus(StrEnum):
    CLAIMED = "CLAIMED"
    EVALUATING = "EVALUATING"
    NO_ACTION = "NO_ACTION"
    REFUSED = "REFUSED"
    ENTRY_CLAIMED = "ENTRY_CLAIMED"
    ENTRY_RESOLVED = "ENTRY_RESOLVED"
    TAKE_PROFIT_CLAIMED = "TAKE_PROFIT_CLAIMED"
    COMPLETE = "COMPLETE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


class PaperRuntimeOwnershipPhase(StrEnum):
    ACQUIRED = "ACQUIRED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOP_REQUESTED = "STOP_REQUESTED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


_NON_TERMINAL_LIFECYCLE = frozenset(
    {
        PaperRuntimeLifecycleState.REQUESTED,
        PaperRuntimeLifecycleState.STARTING,
        PaperRuntimeLifecycleState.RUNNING,
        PaperRuntimeLifecycleState.STOP_REQUESTED,
    }
)
_TERMINAL_CYCLE_STATUSES = frozenset(
    {
        PaperRuntimeCycleStatus.NO_ACTION,
        PaperRuntimeCycleStatus.REFUSED,
        PaperRuntimeCycleStatus.COMPLETE,
        PaperRuntimeCycleStatus.BLOCKED,
    }
)
_ATTEMPT_REQUIRED_CYCLE_STATUSES = frozenset(
    {
        PaperRuntimeCycleStatus.ENTRY_CLAIMED,
        PaperRuntimeCycleStatus.ENTRY_RESOLVED,
        PaperRuntimeCycleStatus.TAKE_PROFIT_CLAIMED,
    }
)
_ATTEMPT_FORBIDDEN_CYCLE_STATUSES = frozenset(
    {
        PaperRuntimeCycleStatus.CLAIMED,
        PaperRuntimeCycleStatus.EVALUATING,
        PaperRuntimeCycleStatus.NO_ACTION,
        PaperRuntimeCycleStatus.REFUSED,
        PaperRuntimeCycleStatus.BLOCKED,
    }
)


def _text(value: object, name: str, *, maximum: int = 512) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise PaperRuntimePersistenceError(f"{name} must be a bounded non-empty string")
    if any(ord(character) < 32 for character in value):
        raise PaperRuntimePersistenceError(f"{name} contains control characters")
    return value


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PaperRuntimePersistenceError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _sha256(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PaperRuntimePersistenceError(f"{name} must be lowercase SHA-256")
    return value


def _decimal(value: object, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise PaperRuntimePersistenceError(f"{name} must be a finite Decimal")
    if positive and value <= 0:
        raise PaperRuntimePersistenceError(f"{name} must be positive")
    return value


def canonical_decimal_text(value: Decimal) -> str:
    """Normalize Decimal scale for stable PostgreSQL round-trips."""
    _decimal(value, "value")
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _bounded_json_value(value: object, *, depth: int = 0) -> object:
    if depth > 8:
        raise PaperRuntimePersistenceError("JSON evidence is too deeply nested")
    if value is None or type(value) in (str, int, bool):
        if type(value) is str:
            _text(value, "JSON string", maximum=512)
        return value
    if type(value) is float:
        raise PaperRuntimePersistenceError("JSON evidence cannot contain floats")
    if type(value) is list:
        values = cast(list[object], value)
        if len(values) > 64:
            raise PaperRuntimePersistenceError("JSON evidence collection is too large")
        return [_bounded_json_value(item, depth=depth + 1) for item in values]
    if type(value) is dict:
        values = cast(dict[object, object], value)
        if len(values) > 64:
            raise PaperRuntimePersistenceError("JSON evidence object is too large")
        result: dict[str, object] = {}
        for key, item in values.items():
            result[_text(key, "JSON key", maximum=128)] = _bounded_json_value(
                item, depth=depth + 1
            )
        return result
    raise PaperRuntimePersistenceError(
        f"JSON evidence contains unsupported {type(value).__name__}"
    )


def canonical_json_bytes(value: Mapping[str, object], *, maximum: int) -> bytes:
    """Return canonical JSON after enforcing the runtime size boundary."""
    checked = _bounded_json_value(dict(value))
    if type(checked) is not dict:  # pragma: no cover - guarded by the signature
        raise PaperRuntimePersistenceError("canonical evidence must be an object")
    encoded = json.dumps(
        checked, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > maximum:
        raise PaperRuntimePersistenceError("canonical evidence exceeds size bound")
    return encoded


def _bounded_object(value: object, name: str) -> dict[str, object]:
    if type(value) is not dict:
        raise PaperRuntimePersistenceError(f"{name} must be an object")
    result = cast(dict[str, object], value)
    canonical_json_bytes(result, maximum=MAX_RUNTIME_JSON_BYTES)
    return result


def _reject_secret_keys(value: object, name: str) -> None:
    """Reject obvious credential-bearing keys before a value reaches JSONB."""
    forbidden = ("token", "password", "secret", "credential", "authorization")
    if type(value) is dict:
        for key, item in cast(dict[object, object], value).items():
            key_text = _text(key, f"{name} key", maximum=128).lower()
            if any(part in key_text for part in forbidden):
                raise PaperRuntimePersistenceError(f"{name} contains a secret field")
            _reject_secret_keys(item, name)
    elif type(value) is list:
        for item in cast(list[object], value):
            _reject_secret_keys(item, name)


def validate_runtime_json_object(
    value: object, name: str = "JSON evidence"
) -> dict[str, object]:
    """Validate one bounded, secret-free object before storing it in JSONB."""
    result = _bounded_object(value, name)
    _reject_secret_keys(result, name)
    return result


def _parameter_fingerprint(parameters: ValidatedParameterPayload) -> str:
    return hashlib.sha256(
        canonical_json_bytes(parameters.to_json(), maximum=MAX_RUNTIME_JSON_BYTES)
    ).hexdigest()


def runtime_parameter_fingerprint(parameters: ValidatedParameterPayload) -> str:
    """Return the canonical fingerprint stored with an activation."""
    if type(parameters) is not ValidatedParameterPayload:
        raise PaperRuntimePersistenceError("parameters must be validated")
    return _parameter_fingerprint(parameters)


def runtime_evaluation_key(
    strategy_version_id: UUID, parameter_fingerprint: str
) -> str:
    """Return the stable identity for one StrategyVersion/parameter pair."""
    if type(strategy_version_id) is not UUID:
        raise PaperRuntimePersistenceError("strategy_version_id must be a UUID")
    _sha256(parameter_fingerprint, "parameter_fingerprint")
    payload = {
        "strategy_version_id": str(strategy_version_id),
        "parameter_fingerprint": parameter_fingerprint,
    }
    return hashlib.sha256(
        canonical_json_bytes(payload, maximum=MAX_RUNTIME_JSON_BYTES)
    ).hexdigest()


def _state_json(
    value: StrategyStateEnvelope | None, name: str
) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not StrategyStateEnvelope:
        raise PaperRuntimePersistenceError(f"{name} must be StrategyStateEnvelope")
    return validate_runtime_json_object(value.to_json(), name)


def _state_fingerprint(value: StrategyStateEnvelope) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value.to_json(), maximum=MAX_RUNTIME_JSON_BYTES)
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperRuntimeActivation:
    """Immutable explicit activation facts plus guarded runtime projection."""

    activation_id: UUID
    strategy_version_id: UUID
    strategy_key: str
    strategy_version_number: int
    source_fingerprint: str
    implementation_key: str
    validated_parameter_snapshot: ValidatedParameterPayload
    parameter_fingerprint: str
    risk_per_trade: Decimal
    requested_at: datetime = dataclass_field(default_factory=lambda: datetime.now(UTC))
    provider: str = PAPER_RUNTIME_PROVIDER
    environment: str = PAPER_RUNTIME_ENVIRONMENT
    provider_account_id: str = ""
    base_currency: str = PAPER_RUNTIME_BASE_CURRENCY
    instrument: str = PAPER_RUNTIME_INSTRUMENT
    state_origin: PaperRuntimeStateOrigin = PaperRuntimeStateOrigin.FRESH_BOOTSTRAP
    runtime_policy_version: str = PAPER_RUNTIME_POLICY_V1
    poll_interval_seconds: int = PAPER_RUNTIME_POLL_INTERVAL_SECONDS
    approval_kind: str = PAPER_RUNTIME_APPROVAL_KIND
    approval_code: str = PAPER_RUNTIME_APPROVAL_CODE
    lifecycle_state: PaperRuntimeLifecycleState = PaperRuntimeLifecycleState.REQUESTED
    state_reason_code: str | None = None
    state_detail: str | None = None
    state_changed_at: datetime | None = None
    operational_phase: PaperRuntimeOperationalPhase = PaperRuntimeOperationalPhase.IDLE
    last_operational_reason_code: str | None = None
    last_operational_at: datetime | None = None
    strategy_state: StrategyStateEnvelope | None = None
    strategy_state_fingerprint: str | None = None
    last_frontier_end: datetime | None = None
    last_cycle_id: UUID | None = None
    control_version: int = 0
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.activation_id) is not UUID:
            raise PaperRuntimePersistenceError("activation_id must be a UUID")
        if type(self.strategy_version_id) is not UUID:
            raise PaperRuntimePersistenceError("strategy_version_id must be a UUID")
        _text(self.strategy_key, "strategy_key", maximum=200)
        if (
            type(self.strategy_version_number) is not int
            or self.strategy_version_number <= 0
        ):
            raise PaperRuntimePersistenceError(
                "strategy_version_number must be positive"
            )
        _sha256(self.source_fingerprint, "source_fingerprint")
        _text(self.implementation_key, "implementation_key", maximum=200)
        if type(self.validated_parameter_snapshot) is not ValidatedParameterPayload:
            raise PaperRuntimePersistenceError(
                "validated_parameter_snapshot must be validated"
            )
        _bounded_object(self.validated_parameter_snapshot.to_json(), "parameters")
        _reject_secret_keys(self.validated_parameter_snapshot.to_json(), "parameters")
        _sha256(self.parameter_fingerprint, "parameter_fingerprint")
        if self.parameter_fingerprint != _parameter_fingerprint(
            self.validated_parameter_snapshot
        ):
            raise PaperRuntimePersistenceError(
                "parameter_fingerprint does not match parameters"
            )
        _decimal(self.risk_per_trade, "risk_per_trade", positive=True)
        if self.risk_per_trade >= 1:
            raise PaperRuntimePersistenceError("risk_per_trade must be less than one")
        for value, name, maximum in (
            (self.provider, "provider", 20),
            (self.environment, "environment", 20),
            (self.provider_account_id, "provider_account_id", 128),
            (self.base_currency, "base_currency", 3),
            (self.instrument, "instrument", 20),
            (self.runtime_policy_version, "runtime_policy_version", 100),
            (self.approval_kind, "approval_kind", 64),
            (self.approval_code, "approval_code", 64),
        ):
            _text(value, name, maximum=maximum)
        if (
            self.provider != PAPER_RUNTIME_PROVIDER
            or self.environment != PAPER_RUNTIME_ENVIRONMENT
            or self.base_currency != PAPER_RUNTIME_BASE_CURRENCY
            or self.instrument != PAPER_RUNTIME_INSTRUMENT
        ):
            raise PaperRuntimePersistenceError("activation scope is not supported")
        if self.runtime_policy_version != PAPER_RUNTIME_POLICY_V1:
            raise PaperRuntimePersistenceError("runtime policy is not supported")
        if type(self.state_origin) is not PaperRuntimeStateOrigin:
            raise PaperRuntimePersistenceError("state_origin is invalid")
        if (
            type(self.poll_interval_seconds) is not int
            or self.poll_interval_seconds != 15
        ):
            raise PaperRuntimePersistenceError("poll_interval_seconds must be 15")
        if (
            self.approval_kind != PAPER_RUNTIME_APPROVAL_KIND
            or self.approval_code != PAPER_RUNTIME_APPROVAL_CODE
        ):
            raise PaperRuntimePersistenceError("activation approval is invalid")
        object.__setattr__(
            self, "requested_at", _utc(self.requested_at, "requested_at")
        )
        if type(self.lifecycle_state) is not PaperRuntimeLifecycleState:
            raise PaperRuntimePersistenceError("lifecycle_state is invalid")
        for value, name in (
            (self.state_reason_code, "state_reason_code"),
            (self.last_operational_reason_code, "last_operational_reason_code"),
        ):
            if value is not None:
                _text(value, name, maximum=64)
        if self.state_detail is not None:
            _text(self.state_detail, "state_detail", maximum=500)
        if self.state_changed_at is None:
            object.__setattr__(self, "state_changed_at", self.requested_at)
        else:
            object.__setattr__(
                self,
                "state_changed_at",
                _utc(self.state_changed_at, "state_changed_at"),
            )
        if type(self.operational_phase) is not PaperRuntimeOperationalPhase:
            raise PaperRuntimePersistenceError("operational_phase is invalid")
        if self.last_operational_at is not None:
            object.__setattr__(
                self,
                "last_operational_at",
                _utc(self.last_operational_at, "last_operational_at"),
            )
        if self.strategy_state is not None:
            _state_json(self.strategy_state, "strategy_state")
            expected = _state_fingerprint(self.strategy_state)
            if self.strategy_state_fingerprint is None:
                object.__setattr__(self, "strategy_state_fingerprint", expected)
            elif self.strategy_state_fingerprint != expected:
                raise PaperRuntimePersistenceError(
                    "strategy_state_fingerprint does not match strategy_state"
                )
        elif self.strategy_state_fingerprint is not None:
            raise PaperRuntimePersistenceError(
                "strategy_state_fingerprint requires strategy_state"
            )
        if self.last_frontier_end is not None:
            object.__setattr__(
                self,
                "last_frontier_end",
                _utc(self.last_frontier_end, "last_frontier_end"),
            )
        if self.last_cycle_id is not None and type(self.last_cycle_id) is not UUID:
            raise PaperRuntimePersistenceError("last_cycle_id must be a UUID")
        if type(self.control_version) is not int or self.control_version < 0:
            raise PaperRuntimePersistenceError("control_version must be nonnegative")
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.requested_at)
        else:
            object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))

    def immutable_json(self) -> dict[str, object]:
        return {
            "strategy_version_id": str(self.strategy_version_id),
            "strategy_key": self.strategy_key,
            "strategy_version_number": self.strategy_version_number,
            "source_fingerprint": self.source_fingerprint,
            "implementation_key": self.implementation_key,
            "validated_parameter_snapshot": self.validated_parameter_snapshot.to_json(),
            "parameter_fingerprint": self.parameter_fingerprint,
            "provider": self.provider,
            "environment": self.environment,
            "provider_account_id": self.provider_account_id,
            "base_currency": self.base_currency,
            "instrument": self.instrument,
            "risk_per_trade": canonical_decimal_text(self.risk_per_trade),
            "state_origin": self.state_origin.value,
            "runtime_policy_version": self.runtime_policy_version,
            "poll_interval_seconds": self.poll_interval_seconds,
            "approval_kind": self.approval_kind,
            "approval_code": self.approval_code,
        }

    @property
    def activation_request_id(self) -> UUID:
        """Return the caller-supplied idempotency identity."""
        return self.activation_id

    def to_json(self) -> dict[str, object]:
        return {
            "activation_id": str(self.activation_id),
            **self.immutable_json(),
            "lifecycle_state": self.lifecycle_state.value,
            "state_reason_code": self.state_reason_code,
            "state_detail": self.state_detail,
            "state_changed_at": self.state_changed_at.isoformat().replace("+00:00", "Z")
            if self.state_changed_at is not None
            else None,
            "operational_phase": self.operational_phase.value,
            "last_operational_reason_code": self.last_operational_reason_code,
            "last_operational_at": self.last_operational_at.isoformat().replace(
                "+00:00", "Z"
            )
            if self.last_operational_at is not None
            else None,
            "strategy_state": (
                self.strategy_state.to_json()
                if self.strategy_state is not None
                else None
            ),
            "strategy_state_fingerprint": self.strategy_state_fingerprint,
            "last_frontier_end": self.last_frontier_end.isoformat().replace(
                "+00:00", "Z"
            )
            if self.last_frontier_end is not None
            else None,
            "last_cycle_id": str(self.last_cycle_id) if self.last_cycle_id else None,
            "control_version": self.control_version,
            "updated_at": self.updated_at.isoformat().replace("+00:00", "Z")
            if self.updated_at is not None
            else None,
        }

    @property
    def identity_fingerprint(self) -> str:
        identity = {"activation_id": str(self.activation_id), **self.immutable_json()}
        return hashlib.sha256(
            canonical_json_bytes(identity, maximum=MAX_RUNTIME_JSON_BYTES)
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperRuntimeCycle:
    """One immutable analytical-frontier reservation and its evidence."""

    cycle_id: UUID
    activation_id: UUID
    cycle_sequence: int
    evaluation_key: str
    strategy_version_id: UUID
    parameter_fingerprint: str
    frontier_start: datetime
    frontier_end: datetime
    financial_position_state: FinancialPositionState
    account_transaction_id: str
    account_observed_at: datetime
    account_open_trade_count: int
    account_open_position_count: int
    account_pending_order_count: int
    account_gate_fingerprint: str
    cycle_status: PaperRuntimeCycleStatus
    claimed_at: datetime
    prior_frontier_end: datetime | None = None
    state_before: StrategyStateEnvelope | None = None
    state_before_fingerprint: str | None = None
    state_after: StrategyStateEnvelope | None = None
    state_after_fingerprint: str | None = None
    strategy_evaluation_snapshot: StrategyEvaluation | dict[str, object] | None = None
    decision_snapshot: StrategyDecision | dict[str, object] | None = None
    attempt_id: UUID | None = None
    cycle_reason_code: str | None = None
    evaluated_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.cycle_id, "cycle_id"),
            (self.activation_id, "activation_id"),
            (self.strategy_version_id, "strategy_version_id"),
        ):
            if type(value) is not UUID:
                raise PaperRuntimePersistenceError(f"{name} must be a UUID")
        if type(self.cycle_sequence) is not int or self.cycle_sequence <= 0:
            raise PaperRuntimePersistenceError("cycle_sequence must be positive")
        _text(self.evaluation_key, "evaluation_key", maximum=256)
        _sha256(self.parameter_fingerprint, "parameter_fingerprint")
        if self.evaluation_key != runtime_evaluation_key(
            self.strategy_version_id, self.parameter_fingerprint
        ):
            raise PaperRuntimePersistenceError(
                "evaluation_key does not match Strategy identity"
            )
        for value, name in (
            (self.frontier_start, "frontier_start"),
            (self.frontier_end, "frontier_end"),
            (self.account_observed_at, "account_observed_at"),
            (self.claimed_at, "claimed_at"),
        ):
            object.__setattr__(self, name, _utc(value, name))
        if self.frontier_end <= self.frontier_start:
            raise PaperRuntimePersistenceError(
                "frontier_end must follow frontier_start"
            )
        if self.frontier_end - self.frontier_start != timedelta(minutes=15):
            raise PaperRuntimePersistenceError("frontier interval must be M15")
        if self.prior_frontier_end is not None:
            object.__setattr__(
                self,
                "prior_frontier_end",
                _utc(self.prior_frontier_end, "prior_frontier_end"),
            )
            if self.prior_frontier_end >= self.frontier_end:
                raise PaperRuntimePersistenceError(
                    "prior_frontier_end must precede frontier_end"
                )
        if type(self.financial_position_state) is not FinancialPositionState:
            raise PaperRuntimePersistenceError("financial_position_state is invalid")
        _text(self.account_transaction_id, "account_transaction_id", maximum=64)
        for value, name in (
            (self.account_open_trade_count, "account_open_trade_count"),
            (self.account_open_position_count, "account_open_position_count"),
            (self.account_pending_order_count, "account_pending_order_count"),
        ):
            if type(value) is not int or value < 0:
                raise PaperRuntimePersistenceError(f"{name} must be nonnegative")
        has_exposure = (
            self.account_open_trade_count > 0 or self.account_open_position_count > 0
        )
        if (self.financial_position_state is FinancialPositionState.FLAT) is not (
            not has_exposure
        ):
            raise PaperRuntimePersistenceError(
                "financial_position_state does not match account exposure counts"
            )
        _sha256(self.account_gate_fingerprint, "account_gate_fingerprint")
        if type(self.cycle_status) is not PaperRuntimeCycleStatus:
            raise PaperRuntimePersistenceError("cycle_status is invalid")
        if self.cycle_reason_code is not None:
            _text(self.cycle_reason_code, "cycle_reason_code", maximum=64)
        for value, name in (
            (self.state_before, "state_before"),
            (self.state_after, "state_after"),
        ):
            _state_json(value, name)
        if self.state_before is None:
            if self.prior_frontier_end is not None:
                raise PaperRuntimePersistenceError(
                    "prior_frontier_end requires state_before"
                )
        elif self.state_before.last_evaluated_bar_end != self.prior_frontier_end:
            raise PaperRuntimePersistenceError(
                "state_before frontier does not match prior_frontier_end"
            )
        for state, fingerprint, name in (
            (self.state_before, self.state_before_fingerprint, "state_before"),
            (self.state_after, self.state_after_fingerprint, "state_after"),
        ):
            if state is None:
                if fingerprint is not None:
                    raise PaperRuntimePersistenceError(
                        f"{name}_fingerprint requires {name}"
                    )
            else:
                expected = _state_fingerprint(state)
                if fingerprint is None:
                    object.__setattr__(self, f"{name}_fingerprint", expected)
                elif fingerprint != expected:
                    raise PaperRuntimePersistenceError(
                        f"{name}_fingerprint does not match {name}"
                    )
        if self.strategy_evaluation_snapshot is not None:
            value = self.strategy_evaluation_snapshot
            if type(value) is StrategyEvaluation:
                value = value.to_json()
                object.__setattr__(self, "strategy_evaluation_snapshot", value)
            _bounded_object(value, "strategy_evaluation_snapshot")
            _reject_secret_keys(
                cast(dict[str, object], value), "strategy_evaluation_snapshot"
            )
        if self.decision_snapshot is not None:
            value = self.decision_snapshot
            if type(value) is StrategyDecision:
                value = value.to_json()
                object.__setattr__(self, "decision_snapshot", value)
            _bounded_object(value, "decision_snapshot")
            _reject_secret_keys(cast(dict[str, object], value), "decision_snapshot")
        if self.attempt_id is not None and type(self.attempt_id) is not UUID:
            raise PaperRuntimePersistenceError("attempt_id must be a UUID")
        if self.cycle_status in _ATTEMPT_REQUIRED_CYCLE_STATUSES and (
            self.attempt_id is None
        ):
            raise PaperRuntimePersistenceError(
                f"{self.cycle_status.value} requires an attempt_id"
            )
        if (
            self.attempt_id is not None
            and self.cycle_status in _ATTEMPT_FORBIDDEN_CYCLE_STATUSES
        ):
            raise PaperRuntimePersistenceError(
                "non-opening cycle status cannot contain an execution attempt"
            )
        for value, name in (
            (self.evaluated_at, "evaluated_at"),
            (self.completed_at, "completed_at"),
            (self.updated_at, "updated_at"),
        ):
            if value is not None:
                object.__setattr__(self, name, _utc(value, name))
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.claimed_at)

    def to_json(self) -> dict[str, object]:
        def state(value: StrategyStateEnvelope | None) -> dict[str, object] | None:
            return None if value is None else value.to_json()

        return {
            "cycle_id": str(self.cycle_id),
            "activation_id": str(self.activation_id),
            "cycle_sequence": self.cycle_sequence,
            "evaluation_key": self.evaluation_key,
            "strategy_version_id": str(self.strategy_version_id),
            "parameter_fingerprint": self.parameter_fingerprint,
            "frontier_start": self.frontier_start.isoformat().replace("+00:00", "Z"),
            "frontier_end": self.frontier_end.isoformat().replace("+00:00", "Z"),
            "prior_frontier_end": (
                self.prior_frontier_end.isoformat().replace("+00:00", "Z")
                if self.prior_frontier_end
                else None
            ),
            "state_before": state(self.state_before),
            "state_before_fingerprint": self.state_before_fingerprint,
            "state_after": state(self.state_after),
            "state_after_fingerprint": self.state_after_fingerprint,
            "financial_position_state": self.financial_position_state.value,
            "account_transaction_id": self.account_transaction_id,
            "account_observed_at": self.account_observed_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "account_open_trade_count": self.account_open_trade_count,
            "account_open_position_count": self.account_open_position_count,
            "account_pending_order_count": self.account_pending_order_count,
            "account_gate_fingerprint": self.account_gate_fingerprint,
            "strategy_evaluation_snapshot": self.strategy_evaluation_snapshot,
            "decision_snapshot": self.decision_snapshot,
            "attempt_id": str(self.attempt_id) if self.attempt_id else None,
            "cycle_status": self.cycle_status.value,
            "cycle_reason_code": self.cycle_reason_code,
            "claimed_at": self.claimed_at.isoformat().replace("+00:00", "Z"),
            "evaluated_at": (
                self.evaluated_at.isoformat().replace("+00:00", "Z")
                if self.evaluated_at
                else None
            ),
            "completed_at": (
                self.completed_at.isoformat().replace("+00:00", "Z")
                if self.completed_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat().replace("+00:00", "Z")
                if self.updated_at is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PaperRuntimeOwnership:
    """Durable audit projection of the owner holding the live advisory lock."""

    owner_id: UUID
    activation_id: UUID | None
    owner_generation: int
    acquired_at: datetime
    heartbeat_at: datetime
    phase: PaperRuntimeOwnershipPhase
    slot_key: str = PAPER_RUNTIME_SLOT

    def __post_init__(self) -> None:
        if type(self.owner_id) is not UUID:
            raise PaperRuntimePersistenceError("owner_id must be a UUID")
        if self.activation_id is not None and type(self.activation_id) is not UUID:
            raise PaperRuntimePersistenceError("activation_id must be a UUID")
        if type(self.owner_generation) is not int or self.owner_generation <= 0:
            raise PaperRuntimePersistenceError("owner_generation must be positive")
        for value, name in (
            (self.acquired_at, "acquired_at"),
            (self.heartbeat_at, "heartbeat_at"),
        ):
            object.__setattr__(self, name, _utc(value, name))
        if type(self.phase) is not PaperRuntimeOwnershipPhase:
            raise PaperRuntimePersistenceError("ownership phase is invalid")
        if self.heartbeat_at < self.acquired_at:
            raise PaperRuntimePersistenceError(
                "heartbeat_at cannot precede acquired_at"
            )
        if self.slot_key != PAPER_RUNTIME_SLOT:
            raise PaperRuntimePersistenceError("ownership slot is invalid")

    def to_json(self) -> dict[str, object]:
        return {
            "slot_key": self.slot_key,
            "owner_id": str(self.owner_id),
            "activation_id": str(self.activation_id) if self.activation_id else None,
            "owner_generation": self.owner_generation,
            "acquired_at": self.acquired_at.isoformat().replace("+00:00", "Z"),
            "heartbeat_at": self.heartbeat_at.isoformat().replace("+00:00", "Z"),
            "phase": self.phase.value,
        }


def is_non_terminal_lifecycle(state: PaperRuntimeLifecycleState) -> bool:
    return state in _NON_TERMINAL_LIFECYCLE


def is_terminal_cycle_status(status: PaperRuntimeCycleStatus) -> bool:
    return status in _TERMINAL_CYCLE_STATUSES


__all__ = [
    "MAX_RUNTIME_JSON_BYTES",
    "PAPER_RUNTIME_APPROVAL_CODE",
    "PAPER_RUNTIME_APPROVAL_KIND",
    "PAPER_RUNTIME_BASE_CURRENCY",
    "PAPER_RUNTIME_ENVIRONMENT",
    "PAPER_RUNTIME_INSTRUMENT",
    "PAPER_RUNTIME_POLL_INTERVAL_SECONDS",
    "PAPER_RUNTIME_POLICY_V1",
    "PAPER_RUNTIME_PROVIDER",
    "PAPER_RUNTIME_SLOT",
    "PaperRuntimeActivation",
    "PaperRuntimeCycle",
    "PaperRuntimeCycleStatus",
    "PaperRuntimeLifecycleState",
    "PaperRuntimeOperationalPhase",
    "PaperRuntimeOwnership",
    "PaperRuntimeOwnershipPhase",
    "PaperRuntimePersistenceError",
    "PaperRuntimeStateOrigin",
    "canonical_decimal_text",
    "canonical_json_bytes",
    "is_non_terminal_lifecycle",
    "is_terminal_cycle_status",
    "runtime_evaluation_key",
    "runtime_parameter_fingerprint",
    "validate_runtime_json_object",
]
