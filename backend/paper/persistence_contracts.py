"""Provider-neutral, bounded contracts for the PAPER execution ledger.

The values in this module are deliberately separate from the historical
Experiment persistence graph.  They contain the evidence needed to explain one
PAPER 04 attempt, but they do not contain a broker payload, credentials, or a
permission to submit a later mutation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import cast
from uuid import UUID, uuid4

from backend.domain import (
    FinancialPositionState,
    Instrument,
    Provider,
    StrategyEvaluation,
    StrategyVersion,
    ValidatedParameterPayload,
)
from backend.paper.execution import (
    BrokerFillFacts,
    ExecutionCorrelation,
    PaperExecutionInstruction,
    PaperExecutionOutcome,
    ProtectionConfirmation,
    ProtectionLegStatus,
)
from backend.paper.risk_evaluation import (
    PaperObservationProvenance,
    PaperPricingEvidence,
    PaperRiskEvaluation,
    PaperRiskOutcome,
)
from backend.risk import RiskConfig, RiskDecision, RiskPhase, TradeIntent

MAX_CANONICAL_SNAPSHOT_BYTES = 32_768
MAX_NORMALIZED_FACTS_BYTES = 16_384
MAX_COLLECTION_ITEMS = 64
PAPER_BROKER_FACTS_SCHEMA_V1 = "ATLAS_PAPER_BROKER_FACTS_V1"
PAPER_STRATEGY_RECEIPT_SCHEMA_V1 = "ATLAS_PAPER_STRATEGY_RECEIPT_V1"
PAPER_RISK_AUTHORITY_SCHEMA_V1 = "ATLAS_PAPER_RISK_AUTHORITY_V1"


class PaperPersistenceContractError(ValueError):
    """A PAPER persistence value is invalid or cannot be bounded safely."""


class PaperMutationPhase(StrEnum):
    ENTRY = "ENTRY"
    TAKE_PROFIT = "TAKE_PROFIT"


class ReconciliationStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    CONSISTENT = "CONSISTENT"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"
    LIFECYCLE_ADVANCED = "LIFECYCLE_ADVANCED"


class PaperReconciliationRunStatus(StrEnum):
    PROVEN = "PROVEN"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"
    LIFECYCLE_ADVANCED = "LIFECYCLE_ADVANCED"
    FAILED = "FAILED"


class PaperObservationReadKind(StrEnum):
    ENTRY_MUTATION_RESPONSE = "ENTRY_MUTATION_RESPONSE"
    TAKE_PROFIT_MUTATION_RESPONSE = "TAKE_PROFIT_MUTATION_RESPONSE"
    ORDER_DETAIL = "ORDER_DETAIL"
    TRANSACTION_DETAIL = "TRANSACTION_DETAIL"
    TRANSACTION_RANGE = "TRANSACTION_RANGE"
    TRADE_DETAIL = "TRADE_DETAIL"
    ACCOUNT_DETAILS = "ACCOUNT_DETAILS"


class PaperObservationObjectKind(StrEnum):
    ORDER = "ORDER"
    TRANSACTION = "TRANSACTION"
    TRADE = "TRADE"
    ACCOUNT = "ACCOUNT"
    MUTATION_RESULT = "MUTATION_RESULT"


class PaperReconciliationFindingCode(StrEnum):
    ENTRY_FILLED = "ENTRY_FILLED"
    ENTRY_REJECTED = "ENTRY_REJECTED"
    ENTRY_CANCELLED = "ENTRY_CANCELLED"
    PROTECTION_CONFIRMED = "PROTECTION_CONFIRMED"
    PROTECTION_INCOMPLETE = "PROTECTION_INCOMPLETE"
    ENTRY_READBACK_NOT_FOUND = "ENTRY_READBACK_NOT_FOUND"
    TRANSACTION_RANGE_TRUNCATED = "TRANSACTION_RANGE_TRUNCATED"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"
    UNATTRIBUTED_EXPOSURE = "UNATTRIBUTED_EXPOSURE"
    TRADE_LIFECYCLE_ADVANCED = "TRADE_LIFECYCLE_ADVANCED"
    PROTECTION_DRIFT = "PROTECTION_DRIFT"
    STALE_RECONCILIATION = "STALE_RECONCILIATION"


def _text(value: object, name: str, *, maximum: int = 512) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise PaperPersistenceContractError(
            f"{name} must be a bounded non-empty string"
        )
    if any(ord(character) < 32 for character in value):
        raise PaperPersistenceContractError(f"{name} contains control characters")
    return value


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PaperPersistenceContractError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _decimal(value: object, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise PaperPersistenceContractError(f"{name} must be a finite Decimal")
    if positive and value <= 0:
        raise PaperPersistenceContractError(f"{name} must be positive")
    return value


def _bounded_json_value(value: object, *, depth: int = 0) -> object:
    """Validate the small JSON vocabulary used by persisted evidence."""
    if depth > 8:
        raise PaperPersistenceContractError("JSON evidence is too deeply nested")
    if value is None or type(value) in (str, int, bool):
        if type(value) is str:
            _text(value, "JSON string", maximum=512)
        return value
    if type(value) is float:
        raise PaperPersistenceContractError("JSON evidence cannot contain floats")
    if type(value) is list:
        values = cast(list[object], value)
        if len(values) > MAX_COLLECTION_ITEMS:
            raise PaperPersistenceContractError("JSON evidence collection is too large")
        return [_bounded_json_value(item, depth=depth + 1) for item in values]
    if type(value) is dict:
        values = cast(dict[object, object], value)
        if len(values) > MAX_COLLECTION_ITEMS:
            raise PaperPersistenceContractError("JSON evidence object is too large")
        result: dict[str, object] = {}
        for key, item in values.items():
            key_text = _text(key, "JSON key", maximum=128)
            result[key_text] = _bounded_json_value(item, depth=depth + 1)
        return result
    raise PaperPersistenceContractError(
        f"JSON evidence contains unsupported {type(value).__name__}"
    )


def canonical_json_bytes(value: Mapping[str, object], *, maximum: int) -> bytes:
    """Return canonical JSON after enforcing the persistence size boundary."""
    checked = _bounded_json_value(dict(value))
    if type(checked) is not dict:  # pragma: no cover - guarded by the signature
        raise PaperPersistenceContractError("canonical evidence must be an object")
    encoded = json.dumps(
        checked, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > maximum:
        raise PaperPersistenceContractError("canonical evidence exceeds size bound")
    return encoded


def _fingerprint(value: Mapping[str, object], *, maximum: int) -> str:
    return hashlib.sha256(canonical_json_bytes(value, maximum=maximum)).hexdigest()


def _decimal_json(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def canonical_decimal_text(value: Decimal) -> str:
    """Normalize Decimal scale so a database round-trip cannot alter identity."""
    _decimal(value, "value")
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _risk_decision_json(decision: RiskDecision) -> dict[str, object]:
    return {
        "phase": decision.phase.value,
        "approved": decision.approved,
        "rejection": decision.rejection.value if decision.rejection else None,
        "entry_price": _decimal_json(decision.entry_price),
        "stop_price": _decimal_json(decision.stop_price),
        "target_price": _decimal_json(decision.target_price),
        "risk_budget": _decimal_json(decision.risk_budget),
        "quantity": _decimal_json(decision.quantity),
        "actual_risk": _decimal_json(decision.actual_risk),
    }


def _intent_json(intent: TradeIntent) -> dict[str, object]:
    return {
        "action": intent.action.value,
        "direction": intent.direction.value if intent.direction else None,
        "stop": _decimal_json(intent.stop),
        "target": intent.target.to_json() if intent.target else None,
    }


def _provenance_json(provenance: PaperObservationProvenance) -> dict[str, object]:
    return {
        "provider": provenance.provider.value,
        "environment": provenance.environment,
        "provider_account_id": provenance.provider_account_id,
        "base_currency": provenance.base_currency,
        "price_time": provenance.price_time.isoformat().replace("+00:00", "Z"),
        "summary_last_transaction_id": provenance.summary_last_transaction_id,
        "trades_last_transaction_id": provenance.trades_last_transaction_id,
        "positions_last_transaction_id": provenance.positions_last_transaction_id,
    }


def _pricing_json(evidence: PaperPricingEvidence) -> dict[str, object]:
    projection = evidence.projection
    return {
        "required_side": evidence.required_side,
        "tradeable": projection.observation.tradeable,
        "price_time": projection.observation.price_time.isoformat().replace(
            "+00:00", "Z"
        ),
        "candidates": [
            {
                "price": str(item.candidate.price),
                "available_quantity": str(item.candidate.available_quantity),
                "approved": item.decision.approved,
                "rejection": (
                    item.decision.rejection.value if item.decision.rejection else None
                ),
            }
            for item in evidence.candidate_results
        ],
        "selected_candidate": (
            {
                "price": str(evidence.selected_candidate.price),
                "available_quantity": str(
                    evidence.selected_candidate.available_quantity
                ),
            }
            if evidence.selected_candidate
            else None
        ),
    }


@dataclass(frozen=True, slots=True)
class PaperStrategyEvaluationReceipt:
    """The exact verified Strategy evaluation handed to PAPER execution."""

    strategy_version_id: UUID
    strategy_key: str
    version_number: int
    source_fingerprint: str
    implementation_key: str
    validated_parameter_snapshot: ValidatedParameterPayload
    evaluation: StrategyEvaluation
    schema_version: str = PAPER_STRATEGY_RECEIPT_SCHEMA_V1

    def __post_init__(self) -> None:
        if type(self.strategy_version_id) is not UUID:
            raise PaperPersistenceContractError("strategy_version_id must be a UUID")
        _text(self.strategy_key, "strategy_key", maximum=200)
        if type(self.version_number) is not int or self.version_number <= 0:
            raise PaperPersistenceContractError("version_number must be positive")
        if (
            type(self.source_fingerprint) is not str
            or len(self.source_fingerprint) != 64
            or self.source_fingerprint != self.source_fingerprint.lower()
            or any(
                character not in "0123456789abcdef"
                for character in self.source_fingerprint
            )
        ):
            raise PaperPersistenceContractError(
                "source_fingerprint must be lowercase SHA-256"
            )
        _text(self.implementation_key, "implementation_key", maximum=200)
        if type(self.validated_parameter_snapshot) is not ValidatedParameterPayload:
            raise PaperPersistenceContractError(
                "validated_parameter_snapshot must be validated"
            )
        if type(self.evaluation) is not StrategyEvaluation:
            raise PaperPersistenceContractError("evaluation must be StrategyEvaluation")
        _text(self.schema_version, "schema_version", maximum=100)
        self._snapshot()

    @classmethod
    def from_verified(
        cls,
        version: StrategyVersion,
        validated_parameter_snapshot: ValidatedParameterPayload,
        evaluation: StrategyEvaluation,
    ) -> PaperStrategyEvaluationReceipt:
        if type(version) is not StrategyVersion:
            raise PaperPersistenceContractError("version must be StrategyVersion")
        return cls(
            strategy_version_id=version.id,
            strategy_key=version.strategy_key,
            version_number=version.version_number,
            source_fingerprint=version.source_fingerprint,
            implementation_key=version.implementation_key,
            validated_parameter_snapshot=validated_parameter_snapshot,
            evaluation=evaluation,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "strategy_version_id": str(self.strategy_version_id),
            "strategy_key": self.strategy_key,
            "version_number": self.version_number,
            "source_fingerprint": self.source_fingerprint,
            "implementation_key": self.implementation_key,
            "validated_parameter_snapshot": self.validated_parameter_snapshot.to_json(),
            "evaluation": self.evaluation.to_json(),
        }

    def _snapshot(self) -> dict[str, object]:
        value = self.to_json()
        canonical_json_bytes(value, maximum=MAX_CANONICAL_SNAPSHOT_BYTES)
        return value

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_json(), maximum=MAX_CANONICAL_SNAPSHOT_BYTES)


@dataclass(frozen=True, slots=True)
class PaperRiskAuthoritySnapshot:
    """Bounded evidence from the exact fresh Risk composition used for entry."""

    risk_config: RiskConfig
    account_equity: Decimal
    financial_position_state: FinancialPositionState
    trade_intent: TradeIntent
    pre_flight: RiskDecision
    pre_submission: RiskDecision
    provenance: PaperObservationProvenance
    pricing_evidence: PaperPricingEvidence
    schema_version: str = PAPER_RISK_AUTHORITY_SCHEMA_V1

    def __post_init__(self) -> None:
        if type(self.risk_config) is not RiskConfig:
            raise PaperPersistenceContractError("risk_config must be RiskConfig")
        _decimal(self.risk_config.risk_per_trade, "risk_per_trade", positive=True)
        if self.risk_config.risk_per_trade >= 1:
            raise PaperPersistenceContractError("risk_per_trade must be less than one")
        _decimal(self.account_equity, "account_equity", positive=True)
        if type(self.financial_position_state) is not FinancialPositionState:
            raise PaperPersistenceContractError("financial_position_state is invalid")
        if type(self.trade_intent) is not TradeIntent:
            raise PaperPersistenceContractError("trade_intent must be TradeIntent")
        for value, name, phase in (
            (self.pre_flight, "pre_flight", RiskPhase.PRE_FLIGHT),
            (self.pre_submission, "pre_submission", RiskPhase.PRE_SUBMISSION),
        ):
            if type(value) is not RiskDecision or value.phase is not phase:
                raise PaperPersistenceContractError(f"{name} has an invalid phase")
        if type(self.provenance) is not PaperObservationProvenance:
            raise PaperPersistenceContractError("provenance must be normalized")
        if type(self.pricing_evidence) is not PaperPricingEvidence:
            raise PaperPersistenceContractError("pricing_evidence must be normalized")
        _text(self.schema_version, "schema_version", maximum=100)
        self._snapshot()

    @classmethod
    def from_evaluation(
        cls,
        evaluation: PaperRiskEvaluation,
        *,
        config: RiskConfig,
        account_equity: Decimal,
        financial_position_state: FinancialPositionState = FinancialPositionState.FLAT,
    ) -> PaperRiskAuthoritySnapshot:
        if type(evaluation) is not PaperRiskEvaluation:
            raise PaperPersistenceContractError(
                "evaluation must be PaperRiskEvaluation"
            )
        if evaluation.outcome is not PaperRiskOutcome.APPROVED:
            raise PaperPersistenceContractError(
                "only an approved Risk evaluation can authorize a PAPER attempt"
            )
        if (
            evaluation.trade_intent is None
            or evaluation.pre_flight is None
            or evaluation.pre_submission is None
            or evaluation.provenance is None
            or evaluation.pricing_evidence is None
        ):
            raise PaperPersistenceContractError(
                "Risk evaluation evidence is incomplete"
            )
        return cls(
            risk_config=config,
            account_equity=account_equity,
            financial_position_state=financial_position_state,
            trade_intent=evaluation.trade_intent,
            pre_flight=evaluation.pre_flight,
            pre_submission=evaluation.pre_submission,
            provenance=evaluation.provenance,
            pricing_evidence=evaluation.pricing_evidence,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "risk_config": {"risk_per_trade": str(self.risk_config.risk_per_trade)},
            "account": {
                "base_currency": self.provenance.base_currency,
                "equity": str(self.account_equity),
                "financial_position_state": self.financial_position_state.value,
            },
            "trade_intent": _intent_json(self.trade_intent),
            "pre_flight": _risk_decision_json(self.pre_flight),
            "pre_submission": _risk_decision_json(self.pre_submission),
            "provenance": _provenance_json(self.provenance),
            "pricing_evidence": _pricing_json(self.pricing_evidence),
        }

    def _snapshot(self) -> dict[str, object]:
        value = self.to_json()
        canonical_json_bytes(value, maximum=MAX_CANONICAL_SNAPSHOT_BYTES)
        return value

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_json(), maximum=MAX_CANONICAL_SNAPSHOT_BYTES)


@dataclass(frozen=True, slots=True)
class PaperExecutionAttempt:
    """The immutable pre-mutation evidence owned by one attempt row."""

    receipt: PaperStrategyEvaluationReceipt
    risk_authority: PaperRiskAuthoritySnapshot
    instruction: PaperExecutionInstruction

    def __post_init__(self) -> None:
        if type(self.receipt) is not PaperStrategyEvaluationReceipt:
            raise PaperPersistenceContractError("receipt is invalid")
        if type(self.risk_authority) is not PaperRiskAuthoritySnapshot:
            raise PaperPersistenceContractError("risk_authority is invalid")
        if type(self.instruction) is not PaperExecutionInstruction:
            raise PaperPersistenceContractError("instruction is invalid")
        if self.receipt.evaluation.decision != self.instruction.strategy_decision:
            raise PaperPersistenceContractError(
                "instruction decision does not belong to the Strategy receipt"
            )
        if (
            self.risk_authority.pre_flight != self.instruction.pre_flight
            or self.risk_authority.pre_submission != self.instruction.pre_submission
        ):
            raise PaperPersistenceContractError(
                "instruction Risk facts do not belong to the Risk snapshot"
            )
        provenance = self.risk_authority.provenance
        account = self.instruction.account
        if (
            provenance.provider is not account.provider
            or provenance.environment != account.environment
            or provenance.provider_account_id != account.account_id
            or provenance.base_currency != account.base_currency
            or provenance.price_time != self.instruction.pricing_time
        ):
            raise PaperPersistenceContractError(
                "Risk provenance does not belong to the execution account/pricing"
            )
        strategy_decision = self.instruction.strategy_decision
        if self.risk_authority.trade_intent != TradeIntent(
            action=strategy_decision.action,
            direction=strategy_decision.direction,
            stop=strategy_decision.stop.price if strategy_decision.stop else None,
            target=strategy_decision.target,
        ):
            raise PaperPersistenceContractError(
                "Risk trade intent does not belong to the Strategy decision"
            )
        if self.risk_authority.provenance.provider is not Provider.OANDA:
            raise PaperPersistenceContractError(
                "PAPER attempt requires OANDA provenance"
            )

    @property
    def attempt_id(self) -> UUID:
        return self.instruction.attempt_id

    @property
    def correlation(self) -> ExecutionCorrelation:
        return self.instruction.correlation

    def immutable_json(self) -> dict[str, object]:
        instruction = self.instruction
        return {
            "receipt": self.receipt.to_json(),
            "risk_authority": self.risk_authority.to_json(),
            "instruction": {
                "strategy_decision": instruction.strategy_decision.to_json(),
                "provider": instruction.account.provider.value,
                "environment": instruction.account.environment,
                "provider_account_id": instruction.account.account_id,
                "base_currency": instruction.account.base_currency,
                "instrument": instruction.instrument.value.replace("/", "_"),
                "direction": instruction.direction.value,
                "requested_quantity": canonical_decimal_text(
                    instruction.requested_quantity
                ),
                "approved_entry_price": canonical_decimal_text(
                    instruction.approved_entry_price
                ),
                "stop_price": canonical_decimal_text(instruction.stop_price),
                "decision_time": instruction.decision_time.isoformat().replace(
                    "+00:00", "Z"
                ),
                "pricing_time": instruction.pricing_time.isoformat().replace(
                    "+00:00", "Z"
                ),
                "account_transaction_id": (
                    instruction.observation_provenance.account_transaction_id
                ),
                "instrument_transaction_id": (
                    instruction.observation_provenance.instrument_transaction_id
                ),
                "display_precision": instruction.display_precision,
                "trade_units_precision": instruction.trade_units_precision,
                "correlation": {
                    "client_order_id": self.correlation.client_order_id,
                    "client_trade_id": self.correlation.client_trade_id,
                    "client_stop_loss_order_id": (
                        self.correlation.client_stop_loss_order_id
                    ),
                    "client_take_profit_order_id": (
                        self.correlation.client_take_profit_order_id
                    ),
                },
            },
        }


@dataclass(frozen=True, slots=True)
class PaperMutationClaim:
    """A permanent possible-mutation barrier, never proof of dispatch."""

    attempt_id: UUID
    phase: PaperMutationPhase
    provider_endpoint_key: str
    normalized_request_fingerprint: str
    claim_id: UUID = dataclass_field(default_factory=uuid4)
    claimed_at: datetime = dataclass_field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if type(self.claim_id) is not UUID or type(self.attempt_id) is not UUID:
            raise PaperPersistenceContractError("claim identities must be UUIDs")
        if type(self.phase) is not PaperMutationPhase:
            raise PaperPersistenceContractError("phase must be ENTRY or TAKE_PROFIT")
        _text(self.provider_endpoint_key, "provider_endpoint_key", maximum=128)
        if (
            type(self.normalized_request_fingerprint) is not str
            or len(self.normalized_request_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.normalized_request_fingerprint
            )
        ):
            raise PaperPersistenceContractError(
                "normalized_request_fingerprint must be SHA-256"
            )
        object.__setattr__(self, "claimed_at", _utc(self.claimed_at, "claimed_at"))


_OBSERVATION_FACT_KEYS = frozenset(
    {
        "account_id",
        "instrument",
        "client_order_id",
        "client_trade_id",
        "client_protection_order_id",
        "order_id",
        "transaction_id",
        "trade_id",
        "type",
        "state",
        "units",
        "price",
        "time",
        "filling_transaction_id",
        "cancelling_transaction_id",
        "rejecting_transaction_id",
        "related_transaction_ids",
        "batch_id",
        "last_transaction_id",
        "request_id",
        "reason_code",
        "outcome",
        "target_price",
        "actual_initial_risk",
        "stop_loss",
        "take_profit",
        "found",
        "transaction_type",
        "order_type",
        "time_in_force",
        "position_fill",
        "price_bound",
        "transactions",
        "open_trades",
        "open_positions",
        "pending_orders",
    }
)


@dataclass(frozen=True, slots=True)
class PaperBrokerObservation:
    """One append-only, normalized provider fact."""

    attempt_id: UUID
    read_kind: PaperObservationReadKind
    object_kind: PaperObservationObjectKind
    provider_account_id: str
    instrument: Instrument | None
    normalized_facts: dict[str, object]
    provider_order_id: str | None = None
    provider_transaction_id: str | None = None
    provider_trade_id: str | None = None
    client_order_id: str | None = None
    client_trade_id: str | None = None
    client_protection_order_id: str | None = None
    provider_type: str | None = None
    provider_state: str | None = None
    signed_units: Decimal | None = None
    price: Decimal | None = None
    executed_at: datetime | None = None
    request_id: str | None = None
    batch_id: str | None = None
    related_transaction_ids: tuple[str, ...] = ()
    last_transaction_id: str | None = None
    provider_observed_at: datetime | None = None
    atlas_observed_at: datetime = dataclass_field(
        default_factory=lambda: datetime.now(UTC)
    )
    normalized_schema_version: str = PAPER_BROKER_FACTS_SCHEMA_V1
    observation_id: UUID = dataclass_field(default_factory=uuid4)
    mutation_claim_id: UUID | None = None
    reconciliation_run_id: UUID | None = None

    def __post_init__(self) -> None:
        if type(self.attempt_id) is not UUID or type(self.observation_id) is not UUID:
            raise PaperPersistenceContractError("observation identities must be UUIDs")
        if type(self.read_kind) is not PaperObservationReadKind:
            raise PaperPersistenceContractError("read_kind is invalid")
        if type(self.object_kind) is not PaperObservationObjectKind:
            raise PaperPersistenceContractError("object_kind is invalid")
        _text(self.provider_account_id, "provider_account_id")
        if self.instrument is not None and type(self.instrument) is not Instrument:
            raise PaperPersistenceContractError("instrument is invalid")
        if type(self.normalized_facts) is not dict:
            raise PaperPersistenceContractError("normalized_facts must be an object")
        unknown = set(self.normalized_facts) - _OBSERVATION_FACT_KEYS
        if unknown:
            raise PaperPersistenceContractError(
                "normalized_facts contains non-whitelisted keys: "
                + ", ".join(sorted(unknown))
            )
        canonical_json_bytes(self.normalized_facts, maximum=MAX_NORMALIZED_FACTS_BYTES)
        for value, name in (
            (self.provider_order_id, "provider_order_id"),
            (self.provider_transaction_id, "provider_transaction_id"),
            (self.provider_trade_id, "provider_trade_id"),
            (self.client_order_id, "client_order_id"),
            (self.client_trade_id, "client_trade_id"),
            (self.client_protection_order_id, "client_protection_order_id"),
            (self.provider_type, "provider_type"),
            (self.provider_state, "provider_state"),
            (self.request_id, "request_id"),
            (self.batch_id, "batch_id"),
            (self.last_transaction_id, "last_transaction_id"),
        ):
            if value is not None:
                _text(value, name)
        for values, name in (
            (self.related_transaction_ids, "related_transaction_ids"),
        ):
            if type(values) is not tuple or len(values) > MAX_COLLECTION_ITEMS:
                raise PaperPersistenceContractError(f"{name} is too large")
            for value in values:
                _text(value, name)
        if self.signed_units is not None:
            _decimal(self.signed_units, "signed_units")
            if self.signed_units == 0:
                raise PaperPersistenceContractError("signed_units must be nonzero")
        if self.price is not None:
            _decimal(self.price, "price", positive=True)
        for value, name in (
            (self.executed_at, "executed_at"),
            (self.provider_observed_at, "provider_observed_at"),
        ):
            if value is not None:
                object.__setattr__(self, name, _utc(value, name))
        object.__setattr__(
            self, "atlas_observed_at", _utc(self.atlas_observed_at, "atlas_observed_at")
        )
        _text(self.normalized_schema_version, "normalized_schema_version", maximum=100)

    @property
    def normalized_facts_fingerprint(self) -> str:
        envelope = {
            "schema_version": self.normalized_schema_version,
            "read_kind": self.read_kind.value,
            "object_kind": self.object_kind.value,
            "facts": self.normalized_facts,
        }
        return _fingerprint(envelope, maximum=MAX_NORMALIZED_FACTS_BYTES)

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": self.normalized_schema_version,
            "read_kind": self.read_kind.value,
            "object_kind": self.object_kind.value,
            "provider_account_id": self.provider_account_id,
            "instrument": self.instrument.value if self.instrument else None,
            "provider_order_id": self.provider_order_id,
            "provider_transaction_id": self.provider_transaction_id,
            "provider_trade_id": self.provider_trade_id,
            "client_order_id": self.client_order_id,
            "client_trade_id": self.client_trade_id,
            "client_protection_order_id": self.client_protection_order_id,
            "provider_type": self.provider_type,
            "provider_state": self.provider_state,
            "signed_units": _decimal_json(self.signed_units),
            "price": _decimal_json(self.price),
            "executed_at": (
                self.executed_at.isoformat().replace("+00:00", "Z")
                if self.executed_at
                else None
            ),
            "request_id": self.request_id,
            "batch_id": self.batch_id,
            "related_transaction_ids": list(self.related_transaction_ids),
            "last_transaction_id": self.last_transaction_id,
            "provider_observed_at": (
                self.provider_observed_at.isoformat().replace("+00:00", "Z")
                if self.provider_observed_at
                else None
            ),
            "atlas_observed_at": self.atlas_observed_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "facts": self.normalized_facts,
        }


@dataclass(frozen=True, slots=True)
class PaperReconciliationFinding:
    """A finite canonical conclusion code retained by a reconciliation run."""

    code: PaperReconciliationFindingCode
    detail: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not PaperReconciliationFindingCode:
            raise PaperPersistenceContractError("finding code is invalid")
        if self.detail is not None:
            _text(self.detail, "finding detail", maximum=256)

    def to_json(self) -> dict[str, str | None]:
        return {"code": self.code.value, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class PaperReconciliationRun:
    """The bounded, append-only summary of one explicit read-only pass."""

    attempt_id: UUID
    run_sequence: int
    requested_at: datetime
    read_started_at: datetime
    completed_at: datetime
    status: PaperReconciliationRunStatus
    projection_version_observed: int
    read_count: int
    read_budget: int
    prior_execution_outcome: PaperExecutionOutcome | None
    resulting_execution_outcome: PaperExecutionOutcome | None
    finding_codes: tuple[PaperReconciliationFindingCode, ...] = ()
    projection_version_applied: int | None = None
    frontier_before: str | None = None
    frontier_observed: str | None = None
    frontier_applied: str | None = None
    non_atomic_read_set: bool = True
    diagnostic_summary: str = ""
    run_id: UUID = dataclass_field(default_factory=uuid4)
    created_at: datetime = dataclass_field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for value, name in ((self.attempt_id, "attempt_id"), (self.run_id, "run_id")):
            if type(value) is not UUID:
                raise PaperPersistenceContractError(f"{name} must be a UUID")
        if type(self.run_sequence) is not int or self.run_sequence <= 0:
            raise PaperPersistenceContractError("run_sequence must be positive")
        for value, name in (
            (self.requested_at, "requested_at"),
            (self.read_started_at, "read_started_at"),
            (self.completed_at, "completed_at"),
            (self.created_at, "created_at"),
        ):
            object.__setattr__(self, name, _utc(value, name))
        if type(self.status) is not PaperReconciliationRunStatus:
            raise PaperPersistenceContractError("reconciliation run status is invalid")
        if type(self.projection_version_observed) is not int or (
            self.projection_version_observed < 0
        ):
            raise PaperPersistenceContractError(
                "projection_version_observed is invalid"
            )
        if self.projection_version_applied is not None and (
            type(self.projection_version_applied) is not int
            or self.projection_version_applied < 0
        ):
            raise PaperPersistenceContractError("projection_version_applied is invalid")
        if (
            type(self.read_count) is not int
            or type(self.read_budget) is not int
            or self.read_count < 0
            or self.read_budget <= 0
            or self.read_count > self.read_budget
        ):
            raise PaperPersistenceContractError("reconciliation read budget is invalid")
        if type(self.non_atomic_read_set) is not bool:
            raise PaperPersistenceContractError("non_atomic_read_set must be bool")
        for value, name in (
            (self.frontier_before, "frontier_before"),
            (self.frontier_observed, "frontier_observed"),
            (self.frontier_applied, "frontier_applied"),
        ):
            if value is not None:
                _text(value, name, maximum=64)
        if type(self.finding_codes) is not tuple or (
            len(self.finding_codes) > MAX_COLLECTION_ITEMS
        ):
            raise PaperPersistenceContractError("finding_codes is too large")
        for code in self.finding_codes:
            if type(code) is not PaperReconciliationFindingCode:
                raise PaperPersistenceContractError(
                    "finding_codes contains an invalid code"
                )
        for value, name in (
            (self.prior_execution_outcome, "prior_execution_outcome"),
            (self.resulting_execution_outcome, "resulting_execution_outcome"),
        ):
            if value is not None and type(value) is not PaperExecutionOutcome:
                raise PaperPersistenceContractError(f"{name} is invalid")
        if self.diagnostic_summary:
            _text(self.diagnostic_summary, "diagnostic_summary", maximum=500)

    @property
    def findings(self) -> tuple[PaperReconciliationFinding, ...]:
        return tuple(PaperReconciliationFinding(code) for code in self.finding_codes)

    def to_json(self) -> dict[str, object]:
        return {
            "run_id": str(self.run_id),
            "attempt_id": str(self.attempt_id),
            "run_sequence": self.run_sequence,
            "status": self.status.value,
            "projection_version_observed": self.projection_version_observed,
            "projection_version_applied": self.projection_version_applied,
            "read_count": self.read_count,
            "read_budget": self.read_budget,
            "frontier_before": self.frontier_before,
            "frontier_observed": self.frontier_observed,
            "frontier_applied": self.frontier_applied,
            "non_atomic_read_set": self.non_atomic_read_set,
            "prior_execution_outcome": (
                self.prior_execution_outcome.value
                if self.prior_execution_outcome
                else None
            ),
            "resulting_execution_outcome": (
                self.resulting_execution_outcome.value
                if self.resulting_execution_outcome
                else None
            ),
            "finding_codes": [code.value for code in self.finding_codes],
            "diagnostic_summary": self.diagnostic_summary,
        }


def validate_execution_outcome_transition(
    current: PaperExecutionOutcome | None,
    proposed: PaperExecutionOutcome,
    *,
    fill: BrokerFillFacts | None,
    protection: ProtectionConfirmation | None = None,
) -> None:
    """Validate a proof-driven outcome change without erasing Fill truth."""
    if type(proposed) is not PaperExecutionOutcome:
        raise PaperPersistenceContractError("proposed execution outcome is invalid")
    if current is not None and type(current) is not PaperExecutionOutcome:
        raise PaperPersistenceContractError("current execution outcome is invalid")
    if fill is not None and type(fill) is not BrokerFillFacts:
        raise PaperPersistenceContractError("fill facts are invalid")
    if protection is not None and type(protection) is not ProtectionConfirmation:
        raise PaperPersistenceContractError("protection facts are invalid")

    filled = proposed in (
        PaperExecutionOutcome.FILLED_PROTECTED,
        PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
    )
    if (
        proposed
        in (
            PaperExecutionOutcome.REJECTED,
            PaperExecutionOutcome.CANCELLED,
            PaperExecutionOutcome.UNKNOWN,
        )
        and fill is not None
    ):
        raise PaperPersistenceContractError(
            "a no-Fill outcome cannot be established with Fill facts"
        )
    if filled and fill is None:
        raise PaperPersistenceContractError("filled outcomes require Fill facts")
    if proposed is PaperExecutionOutcome.FILLED_PROTECTED:
        if protection is None or not (
            protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
            and protection.take_profit_status is ProtectionLegStatus.CONFIRMED
            and protection.actual_target_price is not None
        ):
            raise PaperPersistenceContractError(
                "FILLED_PROTECTED requires exact confirmed protections"
            )
    if current is PaperExecutionOutcome.FILLED_PROTECTED and proposed is not current:
        raise PaperPersistenceContractError("FILLED_PROTECTED cannot be downgraded")
    if current is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE and proposed in (
        PaperExecutionOutcome.UNKNOWN,
        PaperExecutionOutcome.REJECTED,
        PaperExecutionOutcome.CANCELLED,
    ):
        raise PaperPersistenceContractError("proven Fill cannot be downgraded")
    if current in (
        PaperExecutionOutcome.REJECTED,
        PaperExecutionOutcome.CANCELLED,
    ) and proposed not in (
        current,
        PaperExecutionOutcome.FILLED_PROTECTED,
        PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
    ):
        raise PaperPersistenceContractError("terminal no-Fill outcome cannot change")
    if (
        current is PaperExecutionOutcome.UNKNOWN
        and proposed is not current
        and not filled
        and proposed
        not in (PaperExecutionOutcome.REJECTED, PaperExecutionOutcome.CANCELLED)
    ):
        raise PaperPersistenceContractError("UNKNOWN has no valid proposed outcome")


__all__ = [
    "MAX_CANONICAL_SNAPSHOT_BYTES",
    "MAX_NORMALIZED_FACTS_BYTES",
    "PAPER_BROKER_FACTS_SCHEMA_V1",
    "PAPER_RISK_AUTHORITY_SCHEMA_V1",
    "PAPER_STRATEGY_RECEIPT_SCHEMA_V1",
    "PaperBrokerObservation",
    "PaperExecutionAttempt",
    "PaperMutationClaim",
    "PaperMutationPhase",
    "PaperObservationObjectKind",
    "PaperObservationReadKind",
    "PaperPersistenceContractError",
    "PaperReconciliationFinding",
    "PaperReconciliationFindingCode",
    "PaperReconciliationRun",
    "PaperReconciliationRunStatus",
    "PaperRiskAuthoritySnapshot",
    "PaperStrategyEvaluationReceipt",
    "ReconciliationStatus",
    "canonical_json_bytes",
    "canonical_decimal_text",
    "validate_execution_outcome_transition",
]
