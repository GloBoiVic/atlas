"""The one capital-capable PAPER execution composition boundary.

This module owns the complete one-shot sequence.  Callers provide only an
immutable Strategy proposal and Risk configuration; a PAPER 03 evaluation or
any other precomputed observation is deliberately not an input to this seam.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

from backend.domain import Action, Direction, EntryPolicy, Instrument, StrategyDecision
from backend.integrations.oanda import (
    OandaPracticeAccountIdentity,
    OandaPracticeAccountProperties,
    OandaPracticeEntryMutationNormalizationError,
    OandaPracticeEntryTranslationError,
    OandaPracticeEurUsdPricingObservation,
    OandaPracticeExecutionAccountNormalizationError,
    OandaPracticeExecutionAccountSnapshot,
    OandaPracticeExecutionInstrument,
    OandaPracticeExecutionInstrumentNormalizationError,
    translate_oanda_practice_market_order,
)
from backend.risk import RiskConfig, RiskService

from .execution import (
    BrokerUncertainty,
    ExecutionAccountIdentity,
    ExecutionObservationProvenance,
    PaperExecutionContractError,
    PaperExecutionInstruction,
    PaperExecutionOutcome,
    PaperExecutionRefusal,
    PaperExecutionRefusalCode,
    PaperExecutionResult,
    ProtectionConfirmation,
    ProtectionLegStatus,
    TransactionProvenance,
)
from .risk_evaluation import (
    PaperRiskEvaluation,
    PaperRiskEvaluationError,
    PaperRiskOutcome,
    evaluate_paper_risk,
)


class PaperExecutionMutationBarrierError(RuntimeError):
    """A durable mutation barrier could not be committed before a mutation."""


BeforeTakeProfitMutation = Callable[
    [PaperExecutionResult, ProtectionConfirmation, str], None
]
AfterTakeProfitMutation = Callable[[PaperExecutionResult], None]
AfterTradeDetailRead = Callable[[PaperExecutionResult], None]


@dataclass(frozen=True, slots=True)
class PaperExecutionPreparation:
    """Validated fresh PAPER facts before the first broker mutation."""

    instruction: PaperExecutionInstruction
    execution_instrument: OandaPracticeExecutionInstrument
    risk_evaluation: PaperRiskEvaluation
    account_equity: Decimal
    entry_request_fingerprint: str


class PaperExecutionReader(Protocol):
    """A normalized read-only PAPER observation seam."""

    def read(self) -> object: ...


class PaperPricingReader(Protocol):
    """A normalized current-pricing observation seam."""

    def read(self) -> object: ...


class PaperEntryMutation(Protocol):
    """The one-entry mutation seam owned by the OANDA adapter."""

    def submit(
        self,
        instruction: PaperExecutionInstruction,
        execution_instrument: OandaPracticeExecutionInstrument,
    ) -> PaperExecutionResult: ...


class PaperProtectionCompletion(Protocol):
    """The post-Fill protection completion seam owned by the OANDA adapter."""

    def complete(
        self,
        entry_result: PaperExecutionResult,
        execution_instrument: OandaPracticeExecutionInstrument,
        *,
        before_take_profit: BeforeTakeProfitMutation | None = None,
        after_take_profit: AfterTakeProfitMutation | None = None,
        after_trade_detail: AfterTradeDetailRead | None = None,
    ) -> PaperExecutionResult: ...


PricingReaderFactory = Callable[[OandaPracticeAccountIdentity], PaperPricingReader]


class PaperExecutionApplication:
    """Compose one fresh, bounded OANDA Practice PAPER attempt.

    The application has no persistence or retry state.  Mutation adapters own
    their own one-attempt guards and are injected so this public seam can be
    exercised entirely with deterministic fakes.
    """

    def __init__(
        self,
        *,
        account_properties_reader: PaperExecutionReader,
        execution_account_reader: PaperExecutionReader,
        execution_instrument_reader: PaperExecutionReader,
        entry_mutation: PaperEntryMutation,
        protection_completion: PaperProtectionCompletion,
        pricing_reader: PaperPricingReader | None = None,
        pricing_reader_factory: PricingReaderFactory | None = None,
        risk_service: RiskService | None = None,
        attempt_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        if (pricing_reader is None) == (pricing_reader_factory is None):
            raise PaperExecutionContractError(
                "provide exactly one current pricing reader or reader factory"
            )
        self._account_properties_reader = account_properties_reader
        self._execution_account_reader = execution_account_reader
        self._execution_instrument_reader = execution_instrument_reader
        self._pricing_reader = pricing_reader
        self._pricing_reader_factory = pricing_reader_factory
        self._entry_mutation = entry_mutation
        self._protection_completion = protection_completion
        self._risk_service = risk_service
        self._attempt_id_factory = attempt_id_factory

    def prepare(
        self,
        strategy_decision: StrategyDecision,
        *,
        config: RiskConfig,
        attempt_id: UUID | None = None,
    ) -> PaperExecutionRefusal | PaperExecutionPreparation:
        """Prepare one fresh independent attempt before broker mutation.

        The only accepted input authority is ``strategy_decision``.  In
        particular, this method has no parameter for a PAPER 03 result, so an
        old approval cannot be passed through to a broker mutation.
        """
        selected_attempt_id = (
            self._attempt_id_factory() if attempt_id is None else attempt_id
        )
        if type(selected_attempt_id) is not UUID:
            raise PaperExecutionContractError("attempt_id must be a UUID")

        if not _supported_strategy_decision(strategy_decision):
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.UNSUPPORTED_INPUT,
                "STRATEGY_SCOPE_UNSUPPORTED",
            )

        properties = self._read_account_properties(selected_attempt_id)
        if isinstance(properties, PaperExecutionRefusal):
            return properties
        if not properties.is_non_mt4:
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.ACCOUNT_UNSUPPORTED,
                "ACCOUNT_MT4_UNSUPPORTED",
            )

        snapshot = self._read_execution_account(selected_attempt_id)
        if isinstance(snapshot, PaperExecutionRefusal):
            return snapshot
        if snapshot.identity.provider_account_id != properties.provider_account_id:
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.ACCOUNT_UNSUPPORTED,
                "ACCOUNT_IDENTITY_MISMATCH",
            )
        try:
            snapshot.require_flat_entry_state()
        except OandaPracticeExecutionAccountNormalizationError:
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.ENTRY_STATE_BLOCKED,
                "ENTRY_STATE_NOT_FLAT",
            )
        except Exception:
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "ENTRY_STATE_INVALID",
            )

        execution_instrument = self._read_execution_instrument(selected_attempt_id)
        if isinstance(execution_instrument, PaperExecutionRefusal):
            return execution_instrument

        pricing = self._read_pricing(selected_attempt_id, snapshot.identity)
        if isinstance(pricing, PaperExecutionRefusal):
            return pricing

        try:
            evaluation = evaluate_paper_risk(
                strategy_decision,
                summary=snapshot.summary,
                trades=snapshot.trades,
                positions=snapshot.positions,
                pricing=pricing,
                config=config,
                risk_service=self._risk_service,
            )
        except (PaperRiskEvaluationError, ValueError, TypeError):
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "PAPER_RISK_EVALUATION_INVALID",
            )
        except Exception:
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "PAPER_RISK_EVALUATION_FAILED",
            )

        if evaluation.outcome is not PaperRiskOutcome.APPROVED:
            return _risk_refusal(selected_attempt_id, evaluation.outcome)
        if (
            evaluation.pre_flight is None
            or evaluation.pre_submission is None
            or evaluation.provenance is None
        ):
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "PAPER_RISK_APPROVAL_INCOMPLETE",
            )

        try:
            account = ExecutionAccountIdentity(
                provider=snapshot.identity.provider,
                environment=snapshot.identity.environment,
                account_id=snapshot.identity.provider_account_id,
                base_currency=snapshot.identity.base_currency,
            )
            instruction = PaperExecutionInstruction(
                attempt_id=selected_attempt_id,
                strategy_decision=strategy_decision,
                account=account,
                instrument=Instrument.EUR_USD,
                direction=_direction(strategy_decision),
                requested_quantity=_required_decimal(
                    evaluation.pre_submission.quantity, "quantity"
                ),
                approved_entry_price=_required_decimal(
                    evaluation.pre_submission.entry_price, "entry price"
                ),
                stop_price=_required_decimal(
                    evaluation.pre_submission.stop_price, "stop price"
                ),
                decision_time=_required_time(strategy_decision.decision_time),
                pricing_time=pricing.price_time,
                pre_flight=evaluation.pre_flight,
                pre_submission=evaluation.pre_submission,
                observation_provenance=ExecutionObservationProvenance(
                    identity=account,
                    account_transaction_id=snapshot.last_transaction_id,
                    pricing_time=pricing.price_time,
                    instrument_transaction_id=execution_instrument.last_transaction_id,
                ),
                display_precision=execution_instrument.display_precision,
                trade_units_precision=execution_instrument.trade_units_precision,
            )
            # Validate all entry values before the first possible mutation.
            entry_payload = translate_oanda_practice_market_order(
                instruction, execution_instrument, correlation=instruction.correlation
            )
            entry_request_fingerprint = _request_fingerprint(entry_payload)
        except (
            PaperExecutionContractError,
            OandaPracticeEntryTranslationError,
            OandaPracticeExecutionInstrumentNormalizationError,
            ValueError,
            TypeError,
        ):
            return _refusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.LOCAL_SERIALIZATION_REJECTED,
                "ENTRY_SERIALIZATION_REJECTED",
            )

        return PaperExecutionPreparation(
            instruction=instruction,
            execution_instrument=execution_instrument,
            risk_evaluation=evaluation,
            account_equity=snapshot.summary.nav,
            entry_request_fingerprint=entry_request_fingerprint,
        )

    def submit_entry(
        self, preparation: PaperExecutionPreparation
    ) -> PaperExecutionResult:
        """Invoke the existing single-attempt entry mutation seam."""
        instruction = preparation.instruction
        execution_instrument = preparation.execution_instrument

        try:
            entry_result = self._entry_mutation.submit(
                instruction, execution_instrument
            )
        except OandaPracticeEntryMutationNormalizationError as error:
            if error.fill is not None and error.transaction_provenance is not None:
                return _entry_invariant_failure(instruction, error)
            return _unknown_result(instruction, "ENTRY_INVARIANT_VIOLATION")
        except Exception:
            return _unknown_result(instruction, "ENTRY_MUTATION_FAILED")

        if not _matches_instruction(entry_result, instruction):
            return _unknown_result(instruction, "ENTRY_RESULT_INVALID")
        if entry_result.outcome in (
            PaperExecutionOutcome.REJECTED,
            PaperExecutionOutcome.CANCELLED,
            PaperExecutionOutcome.UNKNOWN,
        ):
            return entry_result
        if (
            entry_result.outcome
            is not PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
        ):
            return _unknown_result(instruction, "ENTRY_RESULT_INVALID")

        return entry_result

    def complete_protection(
        self,
        preparation: PaperExecutionPreparation,
        entry_result: PaperExecutionResult,
        *,
        before_take_profit: BeforeTakeProfitMutation | None = None,
        after_take_profit: AfterTakeProfitMutation | None = None,
        after_trade_detail: AfterTradeDetailRead | None = None,
    ) -> PaperExecutionResult:
        """Complete protection while exposing the pre-PUT durable barrier."""
        instruction = preparation.instruction
        execution_instrument = preparation.execution_instrument

        try:
            if (
                before_take_profit is None
                and after_take_profit is None
                and after_trade_detail is None
            ):
                completed = self._protection_completion.complete(
                    entry_result, execution_instrument
                )
            else:
                completed = self._protection_completion.complete(
                    entry_result,
                    execution_instrument,
                    before_take_profit=before_take_profit,
                    after_take_profit=after_take_profit,
                    after_trade_detail=after_trade_detail,
                )
        except PaperExecutionMutationBarrierError:
            raise
        except Exception:
            return _protection_failure(entry_result, "PROTECTION_COMPLETION_FAILED")
        if not _matches_instruction(completed, instruction):
            return _protection_failure(entry_result, "PROTECTION_RESULT_INVALID")
        if completed.outcome not in (
            PaperExecutionOutcome.FILLED_PROTECTED,
            PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
        ):
            return _protection_failure(entry_result, "PROTECTION_RESULT_INVALID")
        return completed

    def execute(
        self,
        strategy_decision: StrategyDecision,
        *,
        config: RiskConfig,
        attempt_id: UUID | None = None,
    ) -> PaperExecutionRefusal | PaperExecutionResult:
        """Execute one independent attempt, or return a bounded refusal."""
        preparation = self.prepare(
            strategy_decision, config=config, attempt_id=attempt_id
        )
        if isinstance(preparation, PaperExecutionRefusal):
            return preparation

        entry_result = self.submit_entry(preparation)
        if entry_result.outcome in (
            PaperExecutionOutcome.REJECTED,
            PaperExecutionOutcome.CANCELLED,
            PaperExecutionOutcome.UNKNOWN,
        ):
            return entry_result
        return self.complete_protection(preparation, entry_result)

    def _read_account_properties(
        self, attempt_id: UUID
    ) -> OandaPracticeAccountProperties | PaperExecutionRefusal:
        try:
            properties = self._account_properties_reader.read()
        except Exception:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.ACCOUNT_UNSUPPORTED,
                "ACCOUNT_PROPERTIES_UNAVAILABLE",
            )
        if type(properties) is not OandaPracticeAccountProperties:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.ACCOUNT_UNSUPPORTED,
                "ACCOUNT_PROPERTIES_INVALID",
            )
        return properties

    def _read_execution_account(
        self, attempt_id: UUID
    ) -> OandaPracticeExecutionAccountSnapshot | PaperExecutionRefusal:
        try:
            snapshot = self._execution_account_reader.read()
        except OandaPracticeExecutionAccountNormalizationError:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.ACCOUNT_UNSUPPORTED,
                "ACCOUNT_CAPABILITY_UNSUPPORTED",
            )
        except Exception:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "ACCOUNT_SNAPSHOT_UNAVAILABLE",
            )
        if type(snapshot) is not OandaPracticeExecutionAccountSnapshot:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "ACCOUNT_SNAPSHOT_INVALID",
            )
        return snapshot

    def _read_execution_instrument(
        self, attempt_id: UUID
    ) -> OandaPracticeExecutionInstrument | PaperExecutionRefusal:
        try:
            execution_instrument = self._execution_instrument_reader.read()
        except Exception:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.INSTRUMENT_UNSUPPORTED,
                "INSTRUMENT_CAPABILITY_UNAVAILABLE",
            )
        if type(execution_instrument) is not OandaPracticeExecutionInstrument:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.INSTRUMENT_UNSUPPORTED,
                "INSTRUMENT_CAPABILITY_INVALID",
            )
        return execution_instrument

    def _read_pricing(
        self,
        attempt_id: UUID,
        identity: OandaPracticeAccountIdentity,
    ) -> OandaPracticeEurUsdPricingObservation | PaperExecutionRefusal:
        try:
            if self._pricing_reader_factory is not None:
                reader = self._pricing_reader_factory(identity)
            else:
                reader = self._pricing_reader
            if reader is None:
                raise PaperExecutionContractError("pricing reader is unavailable")
            pricing = reader.read()
        except Exception:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "PRICING_OBSERVATION_UNAVAILABLE",
            )
        if type(pricing) is not OandaPracticeEurUsdPricingObservation:
            return _refusal(
                attempt_id,
                PaperExecutionRefusalCode.OBSERVATION_INVALID,
                "PRICING_OBSERVATION_INVALID",
            )
        return pricing


def execute_paper_execution(
    strategy_decision: StrategyDecision,
    *,
    config: RiskConfig,
    account_properties_reader: PaperExecutionReader,
    execution_account_reader: PaperExecutionReader,
    execution_instrument_reader: PaperExecutionReader,
    entry_mutation: PaperEntryMutation,
    protection_completion: PaperProtectionCompletion,
    pricing_reader: PaperPricingReader | None = None,
    pricing_reader_factory: PricingReaderFactory | None = None,
    risk_service: RiskService | None = None,
    attempt_id: UUID | None = None,
    attempt_id_factory: Callable[[], UUID] = uuid4,
) -> PaperExecutionRefusal | PaperExecutionResult:
    """Public capital-capable PAPER operation with no stale approval input."""
    return PaperExecutionApplication(
        account_properties_reader=account_properties_reader,
        execution_account_reader=execution_account_reader,
        execution_instrument_reader=execution_instrument_reader,
        pricing_reader=pricing_reader,
        pricing_reader_factory=pricing_reader_factory,
        entry_mutation=entry_mutation,
        protection_completion=protection_completion,
        risk_service=risk_service,
        attempt_id_factory=attempt_id_factory,
    ).execute(strategy_decision, config=config, attempt_id=attempt_id)


def _supported_strategy_decision(value: object) -> bool:
    if type(value) is not StrategyDecision:
        return False
    decision = value
    direction = decision.direction
    return (
        decision.entry_policy is EntryPolicy.IMMEDIATE
        and decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT)
        and direction in (Direction.LONG, Direction.SHORT)
        and decision.stop is not None
        and decision.target is not None
        and decision.decision_time is not None
        and direction is not None
        and decision.action.value == f"OPEN_{direction.value}"
    )


def _request_fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _direction(decision: StrategyDecision) -> Direction:
    if decision.direction is None:
        raise PaperExecutionContractError("opening decision has no direction")
    return decision.direction


def _required_decimal(value: object, name: str) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise PaperExecutionContractError(f"Risk {name} is unavailable")
    return value


def _required_time(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PaperExecutionContractError("decision time is unavailable")
    return value


def _refusal(
    attempt_id: UUID,
    code: PaperExecutionRefusalCode,
    detail_code: str,
) -> PaperExecutionRefusal:
    return PaperExecutionRefusal(attempt_id, code, detail_code)


def _risk_refusal(attempt_id: UUID, outcome: PaperRiskOutcome) -> PaperExecutionRefusal:
    code = (
        PaperExecutionRefusalCode.ENTRY_STATE_BLOCKED
        if outcome is PaperRiskOutcome.ENTRY_STATE_BLOCKED
        else PaperExecutionRefusalCode.OBSERVATION_INVALID
        if outcome
        in (PaperRiskOutcome.IDENTITY_MISMATCH, PaperRiskOutcome.OBSERVATION_MISMATCH)
        else PaperExecutionRefusalCode.RISK_REJECTED
    )
    return _refusal(attempt_id, code, f"PAPER_RISK_{outcome.value}")


def _matches_instruction(
    result: object, instruction: PaperExecutionInstruction
) -> bool:
    return (
        type(result) is PaperExecutionResult
        and result.instruction == instruction
        and result.correlation == instruction.correlation
    )


def _unknown_result(
    instruction: PaperExecutionInstruction, detail_code: str
) -> PaperExecutionResult:
    return PaperExecutionResult(
        outcome=PaperExecutionOutcome.UNKNOWN,
        instruction=instruction,
        correlation=instruction.correlation,
        fill=None,
        protection=ProtectionConfirmation(
            stop_loss_status=ProtectionLegStatus.NOT_ATTEMPTED,
            stop_loss=None,
            take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
            take_profit=None,
            actual_target_price=None,
        ),
        rejection=None,
        uncertainty=BrokerUncertainty(detail_code),
        transaction_provenance=TransactionProvenance(),
        diagnostic_codes=(detail_code,),
    )


def _entry_invariant_failure(
    instruction: PaperExecutionInstruction,
    error: OandaPracticeEntryMutationNormalizationError,
) -> PaperExecutionResult:
    """Keep known exposure visible while preventing protection completion."""
    if error.fill is None or error.transaction_provenance is None:
        return _unknown_result(instruction, "ENTRY_INVARIANT_VIOLATION")
    diagnostic_code = error.diagnostic_code
    return PaperExecutionResult(
        outcome=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
        instruction=instruction,
        correlation=instruction.correlation,
        fill=error.fill,
        protection=ProtectionConfirmation(
            stop_loss_status=ProtectionLegStatus.NOT_ATTEMPTED,
            stop_loss=None,
            take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
            take_profit=None,
            actual_target_price=None,
        ),
        rejection=None,
        uncertainty=BrokerUncertainty(diagnostic_code),
        transaction_provenance=error.transaction_provenance,
        diagnostic_codes=(diagnostic_code,),
    )


def _protection_failure(
    entry_result: PaperExecutionResult, detail_code: str
) -> PaperExecutionResult:
    return replace(
        entry_result,
        outcome=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
        rejection=None,
        uncertainty=BrokerUncertainty(detail_code),
        diagnostic_codes=tuple(
            dict.fromkeys((*entry_result.diagnostic_codes, detail_code))
        ),
    )


__all__ = [
    "BeforeTakeProfitMutation",
    "AfterTakeProfitMutation",
    "AfterTradeDetailRead",
    "PaperEntryMutation",
    "PaperExecutionApplication",
    "PaperExecutionMutationBarrierError",
    "PaperExecutionPreparation",
    "PaperExecutionReader",
    "PaperPricingReader",
    "PricingReaderFactory",
    "PaperProtectionCompletion",
    "execute_paper_execution",
]
