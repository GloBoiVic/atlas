"""Immutable provider-neutral contracts for the PAPER execution boundary.

This module stops at an approved execution instruction.  It contains no
provider payloads, HTTP behavior, persistence, or broker mutation logic.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from backend.domain import (
    Direction,
    EntryPolicy,
    Instrument,
    Provider,
    StrategyDecision,
)
from backend.risk import RiskDecision, RiskPhase


class PaperExecutionContractError(ValueError):
    """A PAPER execution contract value is invalid or internally inconsistent."""


# A short alias is useful to callers that do not need to distinguish contract
# validation from the other PAPER application errors.
PaperExecutionError = PaperExecutionContractError


def _text(value: object, name: str, *, maximum: int = 128) -> None:
    if type(value) is not str or not value or len(value) > maximum:
        raise PaperExecutionContractError(f"{name} must be a bounded non-empty string")


def _decimal(value: object, name: str, *, positive: bool = False) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise PaperExecutionContractError(f"{name} must be a finite Decimal")
    if positive and value <= 0:
        raise PaperExecutionContractError(f"{name} must be positive")


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PaperExecutionContractError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ExecutionAccountIdentity:
    """The provider/account facts to which one execution instruction belongs."""

    provider: Provider
    environment: str
    account_id: str
    base_currency: str

    def __post_init__(self) -> None:
        if type(self.provider) is not Provider or self.provider is not Provider.OANDA:
            raise PaperExecutionContractError(
                "execution account has an invalid provider"
            )
        _text(self.environment, "environment", maximum=32)
        if self.environment != "PRACTICE":
            raise PaperExecutionContractError(
                "execution account has an unsupported environment"
            )
        _text(self.account_id, "account_id")
        _text(self.base_currency, "base_currency", maximum=16)
        if self.base_currency != "USD":
            raise PaperExecutionContractError(
                "execution account has an unsupported base currency"
            )


@dataclass(frozen=True, slots=True)
class ExecutionObservationProvenance:
    """Bounded provenance for the account, price, and instrument observations."""

    identity: ExecutionAccountIdentity
    account_transaction_id: str
    pricing_time: datetime
    instrument_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not ExecutionAccountIdentity:
            raise PaperExecutionContractError(
                "execution provenance has an invalid account identity"
            )
        _text(self.account_transaction_id, "account_transaction_id")
        _text(self.instrument_transaction_id, "instrument_transaction_id")
        object.__setattr__(
            self, "pricing_time", _utc(self.pricing_time, "pricing_time")
        )


def _require_approved_risk(decision: RiskDecision, phase: RiskPhase, name: str) -> None:
    if type(decision) is not RiskDecision:
        raise PaperExecutionContractError(f"{name} must be a RiskDecision")
    if decision.phase is not phase or type(decision.approved) is not bool:
        raise PaperExecutionContractError(f"{name} has an invalid Risk phase")
    if not decision.approved or decision.rejection is not None:
        raise PaperExecutionContractError(f"{name} must be approved")


@dataclass(frozen=True, slots=True)
class PaperExecutionInstruction:
    """Fresh, provider-neutral facts approved for one entry attempt.

    The instruction deliberately has no provider order type, signed units,
    client-extension fields, JSON, broker IDs, credentials, or target price
    wire instruction.  Those facts belong to the OANDA translation boundary.
    """

    attempt_id: UUID
    strategy_decision: StrategyDecision
    account: ExecutionAccountIdentity
    instrument: Instrument
    direction: Direction
    requested_quantity: Decimal
    approved_entry_price: Decimal
    stop_price: Decimal
    decision_time: datetime
    pricing_time: datetime
    pre_flight: RiskDecision
    pre_submission: RiskDecision
    observation_provenance: ExecutionObservationProvenance
    display_precision: int
    trade_units_precision: int

    def __post_init__(self) -> None:
        if type(self.attempt_id) is not UUID:
            raise PaperExecutionContractError("attempt_id must be a UUID")
        if type(self.strategy_decision) is not StrategyDecision:
            raise PaperExecutionContractError(
                "strategy_decision must be a StrategyDecision"
            )
        if type(self.account) is not ExecutionAccountIdentity:
            raise PaperExecutionContractError("account must be an execution identity")
        if self.instrument is not Instrument.EUR_USD:
            raise PaperExecutionContractError("only EUR/USD execution is supported")
        if type(self.direction) is not Direction:
            raise PaperExecutionContractError("direction must be LONG or SHORT")
        _decimal(self.requested_quantity, "requested_quantity", positive=True)
        _decimal(self.approved_entry_price, "approved_entry_price", positive=True)
        _decimal(self.stop_price, "stop_price", positive=True)
        decision_time = _utc(self.decision_time, "decision_time")
        pricing_time = _utc(self.pricing_time, "pricing_time")
        if pricing_time < decision_time:
            raise PaperExecutionContractError(
                "pricing_time cannot precede decision_time"
            )
        if self.strategy_decision.entry_policy is not EntryPolicy.IMMEDIATE:
            raise PaperExecutionContractError(
                "execution instruction requires an IMMEDIATE entry"
            )
        if (
            self.strategy_decision.direction is not self.direction
            or self.strategy_decision.action.value != f"OPEN_{self.direction.value}"
            or self.strategy_decision.decision_time != decision_time
            or self.strategy_decision.stop is None
            or self.strategy_decision.stop.price != self.stop_price
        ):
            raise PaperExecutionContractError(
                "instruction does not match the Strategy opening proposal"
            )

        _require_approved_risk(self.pre_flight, RiskPhase.PRE_FLIGHT, "pre_flight")
        _require_approved_risk(
            self.pre_submission, RiskPhase.PRE_SUBMISSION, "pre_submission"
        )
        if self.pre_flight.stop_price != self.stop_price or any(
            value is not None
            for value in (
                self.pre_flight.entry_price,
                self.pre_flight.target_price,
                self.pre_flight.risk_budget,
                self.pre_flight.quantity,
                self.pre_flight.actual_risk,
            )
        ):
            raise PaperExecutionContractError(
                "pre_flight contains finalized PRE_SUBMISSION facts"
            )
        if (
            self.pre_submission.quantity != self.requested_quantity
            or self.pre_submission.entry_price != self.approved_entry_price
            or self.pre_submission.stop_price != self.stop_price
        ):
            raise PaperExecutionContractError(
                "instruction does not copy PRE_SUBMISSION quantity, entry, and stop "
                "facts exactly"
            )
        for value, name in (
            (self.pre_submission.quantity, "pre_submission.quantity"),
            (self.pre_submission.entry_price, "pre_submission.entry_price"),
            (self.pre_submission.stop_price, "pre_submission.stop_price"),
            (self.pre_submission.target_price, "pre_submission.target_price"),
            (self.pre_submission.risk_budget, "pre_submission.risk_budget"),
            (self.pre_submission.actual_risk, "pre_submission.actual_risk"),
        ):
            _decimal(value, name, positive=True)

        if type(self.observation_provenance) is not ExecutionObservationProvenance:
            raise PaperExecutionContractError(
                "observation_provenance has an invalid type"
            )
        if self.observation_provenance.identity != self.account:
            raise PaperExecutionContractError(
                "observation provenance identity does not match account"
            )
        if self.observation_provenance.pricing_time != pricing_time:
            raise PaperExecutionContractError(
                "observation provenance does not match pricing_time"
            )
        if type(self.display_precision) is not int or self.display_precision < 0:
            raise PaperExecutionContractError("display_precision must be nonnegative")
        if (
            type(self.trade_units_precision) is not int
            or self.trade_units_precision < 0
        ):
            raise PaperExecutionContractError(
                "trade_units_precision must be nonnegative"
            )
        object.__setattr__(self, "decision_time", decision_time)
        object.__setattr__(self, "pricing_time", pricing_time)

    @property
    def correlation(self) -> "ExecutionCorrelation":
        """Return the stable IDs for this attempt without allocating a new UUID."""
        return ExecutionCorrelation.for_attempt(self.attempt_id)


class PaperExecutionRefusalCode(StrEnum):
    """Finite pre-submission refusal reasons."""

    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    ACCOUNT_UNSUPPORTED = "ACCOUNT_UNSUPPORTED"
    INSTRUMENT_UNSUPPORTED = "INSTRUMENT_UNSUPPORTED"
    OBSERVATION_INVALID = "OBSERVATION_INVALID"
    ENTRY_STATE_BLOCKED = "ENTRY_STATE_BLOCKED"
    RISK_REJECTED = "RISK_REJECTED"
    LOCAL_SERIALIZATION_REJECTED = "LOCAL_SERIALIZATION_REJECTED"


@dataclass(frozen=True, slots=True)
class PaperExecutionRefusal:
    """A bounded refusal that proves no broker mutation was submitted."""

    attempt_id: UUID
    code: PaperExecutionRefusalCode
    detail_code: str
    submitted: Literal[False] = False

    def __post_init__(self) -> None:
        if type(self.attempt_id) is not UUID:
            raise PaperExecutionContractError("attempt_id must be a UUID")
        if type(self.code) is not PaperExecutionRefusalCode:
            raise PaperExecutionContractError("code must be a refusal code")
        _text(self.detail_code, "detail_code", maximum=64)
        if self.submitted is not False:
            raise PaperExecutionContractError(
                "a preparation refusal cannot be submitted"
            )


def _correlation_values(attempt_id: UUID) -> tuple[str, str, str, str]:
    if type(attempt_id) is not UUID:
        raise PaperExecutionContractError("attempt_id must be a UUID")
    attempt_hex = attempt_id.hex
    return (
        f"atlas-p04-o-{attempt_hex}",
        f"atlas-p04-t-{attempt_hex}",
        f"atlas-p04-sl-{attempt_hex}",
        f"atlas-p04-tp-{attempt_hex}",
    )


@dataclass(frozen=True, slots=True)
class ExecutionCorrelation:
    """Stable bounded client IDs derived once from one logical attempt."""

    attempt_id: UUID
    client_order_id: str
    client_trade_id: str
    client_stop_loss_order_id: str
    client_take_profit_order_id: str

    def __post_init__(self) -> None:
        expected = _correlation_values(self.attempt_id)
        actual = (
            self.client_order_id,
            self.client_trade_id,
            self.client_stop_loss_order_id,
            self.client_take_profit_order_id,
        )
        if actual != expected:
            raise PaperExecutionContractError(
                "correlation IDs must be deterministically derived from attempt_id"
            )

    @classmethod
    def for_attempt(cls, attempt_id: UUID) -> "ExecutionCorrelation":
        return cls(attempt_id, *_correlation_values(attempt_id))

    @classmethod
    def from_attempt(cls, attempt_id: UUID) -> "ExecutionCorrelation":
        return cls.for_attempt(attempt_id)


def correlation_for_attempt(attempt_id: UUID) -> ExecutionCorrelation:
    """Build stable client IDs for one independently allocated attempt."""
    return ExecutionCorrelation.for_attempt(attempt_id)


class PaperExecutionOutcome(StrEnum):
    FILLED_PROTECTED = "FILLED_PROTECTED"
    FILLED_PROTECTION_INCOMPLETE = "FILLED_PROTECTION_INCOMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class BrokerFillFacts:
    """Validated broker facts proving the actual entry Fill."""

    broker_order_id: str
    broker_fill_transaction_id: str
    broker_trade_id: str
    signed_units: Decimal
    price: Decimal
    executed_at: datetime
    actual_initial_risk: Decimal

    def __post_init__(self) -> None:
        for value, name in (
            (self.broker_order_id, "broker_order_id"),
            (self.broker_fill_transaction_id, "broker_fill_transaction_id"),
            (self.broker_trade_id, "broker_trade_id"),
        ):
            _text(value, name)
        _decimal(self.signed_units, "signed_units")
        if self.signed_units == 0:
            raise PaperExecutionContractError("signed_units must be nonzero")
        _decimal(self.price, "price", positive=True)
        object.__setattr__(self, "executed_at", _utc(self.executed_at, "executed_at"))
        _decimal(self.actual_initial_risk, "actual_initial_risk")
        if self.actual_initial_risk < 0:
            raise PaperExecutionContractError("actual_initial_risk cannot be negative")


class ProtectionLegStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


@dataclass(frozen=True, slots=True)
class BrokerProtectionOrder:
    broker_order_id: str
    client_order_id: str
    price: Decimal
    state: str

    def __post_init__(self) -> None:
        _text(self.broker_order_id, "broker_order_id")
        _text(self.client_order_id, "client_order_id")
        _decimal(self.price, "price", positive=True)
        _text(self.state, "state", maximum=64)


@dataclass(frozen=True, slots=True)
class ProtectionConfirmation:
    stop_loss_status: ProtectionLegStatus
    stop_loss: BrokerProtectionOrder | None
    take_profit_status: ProtectionLegStatus
    take_profit: BrokerProtectionOrder | None
    actual_target_price: Decimal | None

    def __post_init__(self) -> None:
        for value, name in (
            (self.stop_loss_status, "stop_loss_status"),
            (self.take_profit_status, "take_profit_status"),
        ):
            if type(value) is not ProtectionLegStatus:
                raise PaperExecutionContractError(f"{name} has an invalid status")
        for value, name in (
            (self.stop_loss, "stop_loss"),
            (self.take_profit, "take_profit"),
        ):
            if value is not None and type(value) is not BrokerProtectionOrder:
                raise PaperExecutionContractError(f"{name} has an invalid order")
        if self.stop_loss_status is ProtectionLegStatus.NOT_ATTEMPTED and (
            self.stop_loss is not None
        ):
            raise PaperExecutionContractError(
                "a non-attempted Stop Loss cannot have an order"
            )
        if self.take_profit_status is ProtectionLegStatus.NOT_ATTEMPTED and (
            self.take_profit is not None
        ):
            raise PaperExecutionContractError(
                "a non-attempted Take Profit cannot have an order"
            )
        if self.stop_loss_status is ProtectionLegStatus.CONFIRMED and (
            self.stop_loss is None
        ):
            raise PaperExecutionContractError(
                "a confirmed Stop Loss must have an order"
            )
        if self.take_profit_status is ProtectionLegStatus.CONFIRMED and (
            self.take_profit is None
        ):
            raise PaperExecutionContractError(
                "a confirmed Take Profit must have an order"
            )
        if self.actual_target_price is not None:
            _decimal(self.actual_target_price, "actual_target_price", positive=True)
        if (
            self.take_profit_status is ProtectionLegStatus.CONFIRMED
            and self.actual_target_price is None
        ):
            raise PaperExecutionContractError(
                "a confirmed Take Profit must have an actual target price"
            )


@dataclass(frozen=True, slots=True)
class BrokerRejection:
    """Sanitized, bounded broker rejection evidence."""

    detail_code: str
    broker_order_id: str | None = None
    broker_transaction_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.detail_code, "detail_code", maximum=64)
        for value, name in (
            (self.broker_order_id, "broker_order_id"),
            (self.broker_transaction_id, "broker_transaction_id"),
        ):
            if value is not None:
                _text(value, name)

    @property
    def reason_code(self) -> str:
        return self.detail_code


@dataclass(frozen=True, slots=True)
class BrokerUncertainty:
    """Sanitized evidence that entry state cannot be established."""

    detail_code: str
    request_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.detail_code, "detail_code", maximum=64)
        if self.request_id is not None:
            _text(self.request_id, "request_id")


@dataclass(frozen=True, slots=True)
class TransactionProvenance:
    """Bounded identifiers retained as execution evidence, never raw JSON."""

    request_id: str | None = None
    provider_transaction_ids: tuple[str, ...] = ()
    batch_ids: tuple[str, ...] = ()
    related_transaction_ids: tuple[str, ...] = ()
    last_transaction_id: str | None = None

    def __post_init__(self) -> None:
        if self.request_id is not None:
            _text(self.request_id, "request_id")
        for values, name in (
            (self.provider_transaction_ids, "provider_transaction_ids"),
            (self.batch_ids, "batch_ids"),
            (self.related_transaction_ids, "related_transaction_ids"),
        ):
            if type(values) is not tuple or len(values) > 64:
                raise PaperExecutionContractError(f"{name} must be a bounded tuple")
            for value in values:
                _text(value, name)
        if self.last_transaction_id is not None:
            _text(self.last_transaction_id, "last_transaction_id")


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    """Immutable entry/protection result contract for future mutation adapters."""

    outcome: PaperExecutionOutcome
    instruction: PaperExecutionInstruction
    correlation: ExecutionCorrelation
    fill: BrokerFillFacts | None
    protection: ProtectionConfirmation
    rejection: BrokerRejection | None
    uncertainty: BrokerUncertainty | None
    transaction_provenance: TransactionProvenance
    diagnostic_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.outcome) is not PaperExecutionOutcome:
            raise PaperExecutionContractError("outcome has an invalid value")
        if type(self.instruction) is not PaperExecutionInstruction:
            raise PaperExecutionContractError("instruction has an invalid type")
        if type(self.correlation) is not ExecutionCorrelation:
            raise PaperExecutionContractError("correlation has an invalid type")
        if self.correlation.attempt_id != self.instruction.attempt_id:
            raise PaperExecutionContractError(
                "correlation does not belong to instruction attempt"
            )
        if self.fill is not None and type(self.fill) is not BrokerFillFacts:
            raise PaperExecutionContractError("fill has an invalid type")
        if type(self.protection) is not ProtectionConfirmation:
            raise PaperExecutionContractError("protection has an invalid type")
        if self.rejection is not None and type(self.rejection) is not BrokerRejection:
            raise PaperExecutionContractError("rejection has an invalid type")
        if (
            self.uncertainty is not None
            and type(self.uncertainty) is not BrokerUncertainty
        ):
            raise PaperExecutionContractError("uncertainty has an invalid type")
        if type(self.transaction_provenance) is not TransactionProvenance:
            raise PaperExecutionContractError(
                "transaction_provenance has an invalid type"
            )
        if type(self.diagnostic_codes) is not tuple or len(self.diagnostic_codes) > 64:
            raise PaperExecutionContractError(
                "diagnostic_codes must be a bounded tuple"
            )
        for code in self.diagnostic_codes:
            _text(code, "diagnostic_code", maximum=64)
        if (
            self.outcome
            in (
                PaperExecutionOutcome.FILLED_PROTECTED,
                PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            )
            and self.fill is None
        ):
            raise PaperExecutionContractError("filled outcomes require Fill facts")
        if (
            self.outcome
            in (
                PaperExecutionOutcome.REJECTED,
                PaperExecutionOutcome.CANCELLED,
                PaperExecutionOutcome.UNKNOWN,
            )
            and self.fill is not None
        ):
            raise PaperExecutionContractError(
                "entry-terminal outcomes cannot contain Fill facts"
            )
        if self.outcome is PaperExecutionOutcome.FILLED_PROTECTED and (
            self.protection.stop_loss_status is not ProtectionLegStatus.CONFIRMED
            or self.protection.take_profit_status is not ProtectionLegStatus.CONFIRMED
            or self.protection.actual_target_price is None
            or self.rejection is not None
            or self.uncertainty is not None
        ):
            raise PaperExecutionContractError(
                "FILLED_PROTECTED requires both confirmed protections"
            )


__all__ = [
    "BrokerFillFacts",
    "BrokerProtectionOrder",
    "BrokerRejection",
    "BrokerUncertainty",
    "ExecutionAccountIdentity",
    "ExecutionCorrelation",
    "ExecutionObservationProvenance",
    "PaperExecutionContractError",
    "PaperExecutionError",
    "PaperExecutionInstruction",
    "PaperExecutionOutcome",
    "PaperExecutionRefusal",
    "PaperExecutionRefusalCode",
    "PaperExecutionResult",
    "ProtectionConfirmation",
    "ProtectionLegStatus",
    "TransactionProvenance",
    "correlation_for_attempt",
]
