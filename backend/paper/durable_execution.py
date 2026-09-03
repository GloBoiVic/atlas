"""Durable PAPER execution around the existing one-shot PAPER 04 seams.

The coordinator owns only local persistence ordering.  OANDA normalization and
the non-retrying mutation requesters remain behind the injected PAPER 04
interfaces.  A committed claim is deliberately treated as possible dispatch,
not as proof that the provider received a request.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.domain import Direction, Instrument, Provider
from backend.persistence.models import (
    PaperExecutionAttemptModel,
    PaperMutationClaimModel,
)
from backend.persistence.paper_execution_repository import (
    DuplicateMutationClaim,
    PaperExecutionRepository,
    PaperIdentityConflict,
)
from backend.risk import RiskConfig, RiskDecision, RiskPhase, RiskRejection, RiskService

from .execution import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    BrokerRejection,
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
from .execution_application import (
    PaperEntryMutation,
    PaperExecutionApplication,
    PaperExecutionMutationBarrierError,
    PaperExecutionPreparation,
    PaperExecutionReader,
    PaperPricingReader,
    PaperProtectionCompletion,
    PricingReaderFactory,
)
from .persistence_contracts import (
    PAPER_STRATEGY_RECEIPT_SCHEMA_V1,
    PaperBrokerObservation,
    PaperExecutionAttempt,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperPersistenceContractError,
    PaperRiskAuthoritySnapshot,
    PaperStrategyEvaluationReceipt,
    canonical_decimal_text,
)


class PaperDurableExecutionPersistenceError(RuntimeError):
    """A post-mutation local commit failed; the permanent claim still applies."""

    def __init__(self, attempt_id: UUID, result: PaperExecutionResult) -> None:
        self.attempt_id = attempt_id
        self.result = result
        super().__init__(
            f"PAPER result persistence failed for attempt {attempt_id}; "
            "the mutation claim remains permanent"
        )


SessionFactory = Callable[[], Session]
MutationGuard = Callable[[], None]


@dataclass(frozen=True, slots=True)
class PaperDurableExecutionPreparation:
    """Fresh P05 evidence ready for a caller-owned ENTRY transaction.

    The contained attempt is the exact immutable P05 evidence produced by the
    fresh account/pricing/Risk preparation.  It is intentionally separate from
    the durable claim: callers must persist the attempt and claim in their own
    transaction, commit that transaction, and only then call
    :meth:`PaperDurableExecutionApplication.submit_claimed_entry`.
    """

    receipt: PaperStrategyEvaluationReceipt
    preparation: PaperExecutionPreparation
    attempt: PaperExecutionAttempt

    def __post_init__(self) -> None:
        if type(self.receipt) is not PaperStrategyEvaluationReceipt:
            raise PaperPersistenceContractError("receipt is required")
        if type(self.preparation) is not PaperExecutionPreparation:
            raise PaperPersistenceContractError("PAPER preparation is invalid")
        if type(self.attempt) is not PaperExecutionAttempt:
            raise PaperPersistenceContractError("PAPER attempt is invalid")
        if self.attempt.receipt != self.receipt:
            raise PaperIdentityConflict(
                "PAPER attempt receipt does not match preparation"
            )
        if self.attempt.instruction != self.preparation.instruction:
            raise PaperIdentityConflict(
                "PAPER attempt instruction does not match preparation"
            )

    @property
    def attempt_id(self) -> UUID:
        return self.attempt.attempt_id

    @property
    def entry_request_fingerprint(self) -> str:
        return self.preparation.entry_request_fingerprint


class PaperDurableExecutionApplication:
    """Execute one verified Strategy receipt through durable P04 barriers."""

    def __init__(
        self,
        *,
        repository: PaperExecutionRepository,
        session_factory: SessionFactory,
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
        self._repository = repository
        self._session_factory = session_factory
        self._attempt_id_factory = attempt_id_factory
        self._application = PaperExecutionApplication(
            account_properties_reader=account_properties_reader,
            execution_account_reader=execution_account_reader,
            execution_instrument_reader=execution_instrument_reader,
            entry_mutation=entry_mutation,
            protection_completion=protection_completion,
            pricing_reader=pricing_reader,
            pricing_reader_factory=pricing_reader_factory,
            risk_service=risk_service,
        )

    def prepare_entry_claim(
        self,
        receipt: PaperStrategyEvaluationReceipt,
        *,
        config: RiskConfig,
        attempt_id: UUID | None = None,
    ) -> PaperExecutionRefusal | PaperDurableExecutionPreparation:
        """Prepare one fresh P05 opening without changing local persistence.

        This method owns the existing P05 preparation/Risk path and returns all
        evidence needed by a runtime transaction.  It performs no persistence
        and cannot reach a broker mutation seam.
        """
        if type(receipt) is not PaperStrategyEvaluationReceipt:
            raise PaperPersistenceContractError("receipt is required")
        selected_attempt_id = (
            self._attempt_id_factory() if attempt_id is None else attempt_id
        )
        if type(selected_attempt_id) is not UUID:
            raise PaperExecutionContractError("attempt_id must be a UUID")

        preparation = self._application.prepare(
            receipt.evaluation.decision,
            config=config,
            attempt_id=selected_attempt_id,
        )
        if isinstance(preparation, PaperExecutionRefusal):
            return preparation

        try:
            authority = PaperRiskAuthoritySnapshot.from_evaluation(
                preparation.risk_evaluation,
                config=config,
                account_equity=preparation.account_equity,
            )
            attempt = PaperExecutionAttempt(receipt, authority, preparation.instruction)
            return PaperDurableExecutionPreparation(
                receipt=receipt,
                preparation=preparation,
                attempt=attempt,
            )
        except Exception:
            return PaperExecutionRefusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.LOCAL_SERIALIZATION_REJECTED,
                "DURABLE_EVIDENCE_REJECTED",
            )

    def persist_entry_claim(
        self,
        session: Session,
        prepared: PaperDurableExecutionPreparation,
    ) -> PaperMutationClaimModel:
        """Stage the exact P05 attempt/ENTRY claim in a caller-owned transaction.

        No commit is performed here.  The caller owns the transaction that must
        also contain runtime cycle/state evidence, and must commit successfully
        before invoking :meth:`submit_claimed_entry`.
        """
        if type(prepared) is not PaperDurableExecutionPreparation:
            raise PaperPersistenceContractError("prepared PAPER execution is invalid")
        return self._repository.persist_entry_claim(
            session,
            prepared.attempt,
            provider_endpoint_key="OANDA_ENTRY_POST",
            normalized_request_fingerprint=prepared.entry_request_fingerprint,
        )

    def submit_claimed_entry(
        self,
        prepared: PaperDurableExecutionPreparation,
        *,
        entry_claim_id: UUID,
        mutation_guard: MutationGuard | None = None,
        take_profit_claimed_callback: Callable[[UUID], None] | None = None,
    ) -> PaperExecutionResult:
        """Run the existing one-shot P05 chain after the ENTRY claim commits.

        The caller is responsible for transaction commit and any runtime owner
        guard immediately before this call.  This method creates no ENTRY or
        Take Profit claim itself; it only delegates broker mutation, Fill,
        protection, observation, and result persistence to the existing P05
        authority.
        """
        if type(prepared) is not PaperDurableExecutionPreparation:
            raise PaperPersistenceContractError("prepared PAPER execution is invalid")
        if type(entry_claim_id) is not UUID:
            raise PaperPersistenceContractError("entry_claim_id must be a UUID")
        return self._submit_claimed_entry(
            prepared,
            entry_claim_id,
            mutation_guard=mutation_guard,
            take_profit_claimed_callback=take_profit_claimed_callback,
        )

    def execute(
        self,
        receipt: PaperStrategyEvaluationReceipt,
        *,
        config: RiskConfig,
        attempt_id: UUID | None = None,
    ) -> PaperExecutionRefusal | PaperExecutionResult:
        """Execute a receipt, or return without mutation when state is durable."""
        if type(receipt) is not PaperStrategyEvaluationReceipt:
            raise PaperPersistenceContractError("receipt is required")
        selected_attempt_id = (
            self._attempt_id_factory() if attempt_id is None else attempt_id
        )
        if type(selected_attempt_id) is not UUID:
            raise PaperExecutionContractError("attempt_id must be a UUID")

        existing = self._get_attempt(selected_attempt_id)
        if existing is not None:
            self._assert_receipt_identity(existing, receipt, config)
            return _result_from_row(existing, receipt)

        prepared = self.prepare_entry_claim(
            receipt, config=config, attempt_id=selected_attempt_id
        )
        if isinstance(prepared, PaperExecutionRefusal):
            return prepared

        try:
            entry_claim_id = self._commit_entry_claim(
                prepared.attempt, prepared.entry_request_fingerprint
            )
        except (DuplicateMutationClaim, PaperIdentityConflict):
            existing = self._get_attempt(selected_attempt_id)
            if existing is None:
                raise
            self._assert_receipt_identity(existing, receipt, config)
            self._assert_attempt_identity(existing, prepared.attempt)
            return _result_from_row(existing, receipt)
        except Exception:
            return PaperExecutionRefusal(
                selected_attempt_id,
                PaperExecutionRefusalCode.LOCAL_SERIALIZATION_REJECTED,
                "ENTRY_CLAIM_COMMIT_FAILED",
            )

        return self._submit_claimed_entry(prepared, entry_claim_id)

    def _submit_claimed_entry(
        self,
        prepared: PaperDurableExecutionPreparation,
        entry_claim_id: UUID,
        *,
        mutation_guard: MutationGuard | None = None,
        take_profit_claimed_callback: Callable[[UUID], None] | None = None,
    ) -> PaperExecutionResult:
        preparation = prepared.preparation
        attempt = prepared.attempt
        if mutation_guard is not None:
            mutation_guard()
        entry_result = self._application.submit_entry(preparation)
        self._persist_result(
            entry_result,
            read_kind=PaperObservationReadKind.ENTRY_MUTATION_RESPONSE,
            mutation_claim_id=entry_claim_id,
            attempt=attempt,
        )
        if entry_result.outcome in (
            PaperExecutionOutcome.REJECTED,
            PaperExecutionOutcome.CANCELLED,
            PaperExecutionOutcome.UNKNOWN,
        ):
            return entry_result

        take_profit_claim_id: list[UUID] = []

        def before_take_profit(
            fill_result: PaperExecutionResult,
            protection: ProtectionConfirmation,
            request_fingerprint: str,
        ) -> None:
            del fill_result
            try:
                if mutation_guard is not None:
                    mutation_guard()
                claim_id = self._commit_take_profit_claim(
                    prepared.attempt_id,
                    protection,
                    request_fingerprint,
                )
                if take_profit_claimed_callback is not None:
                    take_profit_claimed_callback(claim_id)
                # The claim commit and runtime cycle transition are complete;
                # fence the dependent mutation again immediately before the
                # protection seam can dispatch its PUT.
                if mutation_guard is not None:
                    mutation_guard()
            except Exception as error:
                raise PaperExecutionMutationBarrierError(
                    "TAKE_PROFIT claim commit failed"
                ) from error
            take_profit_claim_id.append(claim_id)

        try:
            completed = self._application.complete_protection(
                preparation,
                entry_result,
                before_take_profit=before_take_profit,
                after_take_profit=(
                    lambda mutation_result: self._persist_take_profit_observation(
                        mutation_result, take_profit_claim_id
                    )
                ),
                after_trade_detail=lambda read_result: self._persist_observation(
                    read_result,
                    read_kind=PaperObservationReadKind.TRADE_DETAIL,
                    mutation_claim_id=None,
                ),
            )
        except PaperExecutionMutationBarrierError:
            # The Fill and entry result already committed.  No dependent PUT
            # was permitted, and the durable row remains protection-incomplete.
            return entry_result

        final_read_kind = _final_read_kind(completed)
        self._persist_result(
            completed,
            read_kind=final_read_kind
            if take_profit_claim_id
            and final_read_kind is PaperObservationReadKind.TRADE_DETAIL
            else None,
            mutation_claim_id=take_profit_claim_id[0]
            if take_profit_claim_id
            and final_read_kind is PaperObservationReadKind.TRADE_DETAIL
            else None,
            attempt=attempt,
        )
        return completed

    def _get_attempt(self, attempt_id: UUID) -> PaperExecutionAttemptModel | None:
        session = self._session_factory()
        try:
            return self._repository.get_attempt(session, attempt_id)
        finally:
            session.close()

    def _commit_entry_claim(
        self, attempt: PaperExecutionAttempt, request_fingerprint: str
    ) -> UUID:
        session = self._session_factory()
        try:
            claim = self._repository.commit_entry_claim(
                session,
                attempt,
                provider_endpoint_key="OANDA_ENTRY_POST",
                normalized_request_fingerprint=request_fingerprint,
            )
            return claim.claim_id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _commit_take_profit_claim(
        self,
        attempt_id: UUID,
        protection: ProtectionConfirmation,
        request_fingerprint: str,
    ) -> UUID:
        session = self._session_factory()
        try:
            claim = self._repository.commit_take_profit_claim(
                session,
                attempt_id,
                protection=protection,
                provider_endpoint_key="OANDA_TAKE_PROFIT_PUT",
                normalized_request_fingerprint=request_fingerprint,
            )
            return claim.claim_id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _persist_result(
        self,
        result: PaperExecutionResult,
        *,
        read_kind: PaperObservationReadKind | None,
        mutation_claim_id: UUID | None,
        attempt: PaperExecutionAttempt | None = None,
    ) -> None:
        session = self._session_factory()
        try:
            if read_kind is not None:
                observation = _observation_for_result(
                    result,
                    read_kind=read_kind,
                    mutation_claim_id=mutation_claim_id,
                )
                self._repository.append_observation(session, observation)
            self._repository.apply_result(session, result, attempt=attempt)
            session.commit()
        except Exception as error:
            session.rollback()
            raise PaperDurableExecutionPersistenceError(
                result.instruction.attempt_id, result
            ) from error
        finally:
            session.close()

    def _persist_observation(
        self,
        result: PaperExecutionResult,
        *,
        read_kind: PaperObservationReadKind,
        mutation_claim_id: UUID | None,
    ) -> None:
        observation = _observation_for_result(
            result,
            read_kind=read_kind,
            mutation_claim_id=mutation_claim_id,
        )
        session = self._session_factory()
        try:
            self._repository.append_observation(session, observation)
            session.commit()
        except Exception as error:
            session.rollback()
            raise PaperExecutionMutationBarrierError(
                "TAKE_PROFIT observation commit failed"
            ) from error
        finally:
            session.close()

    def _persist_take_profit_observation(
        self, result: PaperExecutionResult, claim_ids: list[UUID]
    ) -> None:
        if not claim_ids:
            raise PaperExecutionMutationBarrierError(
                "TAKE_PROFIT observation has no committed claim"
            )
        self._persist_observation(
            result,
            read_kind=PaperObservationReadKind.TAKE_PROFIT_MUTATION_RESPONSE,
            mutation_claim_id=claim_ids[0],
        )

    @staticmethod
    def _assert_receipt_identity(
        row: PaperExecutionAttemptModel,
        receipt: PaperStrategyEvaluationReceipt,
        config: RiskConfig,
    ) -> None:
        risk_snapshot = cast(object, row.risk_authority_snapshot)
        risk_config_value: object = (
            cast(dict[str, object], risk_snapshot).get("risk_config")
            if isinstance(risk_snapshot, dict)
            else None
        )
        stored_risk_value: object = (
            cast(dict[str, object], risk_config_value).get("risk_per_trade")
            if isinstance(risk_config_value, dict)
            else None
        )
        try:
            stored_risk_per_trade = (
                canonical_decimal_text(Decimal(cast(str, stored_risk_value)))
                if stored_risk_value is not None
                else None
            )
        except (ArithmeticError, TypeError, ValueError):
            stored_risk_per_trade = None
        if (
            row.strategy_version_id != receipt.strategy_version_id
            or row.strategy_key != receipt.strategy_key
            or row.strategy_version_number != receipt.version_number
            or row.source_fingerprint != receipt.source_fingerprint
            or row.implementation_key != receipt.implementation_key
            or row.validated_parameter_snapshot
            != receipt.validated_parameter_snapshot.to_json()
            or row.strategy_evaluation_snapshot != receipt.evaluation.to_json()
            or row.strategy_decision != receipt.evaluation.decision.to_json()
            or stored_risk_per_trade != canonical_decimal_text(config.risk_per_trade)
        ):
            raise PaperIdentityConflict(
                f"attempt {row.attempt_id} was presented with a changed "
                "Strategy receipt"
            )

    @staticmethod
    def _assert_attempt_identity(
        row: PaperExecutionAttemptModel, attempt: PaperExecutionAttempt
    ) -> None:
        stored = {
            "receipt": {
                "schema_version": PAPER_STRATEGY_RECEIPT_SCHEMA_V1,
                "strategy_version_id": str(row.strategy_version_id),
                "strategy_key": row.strategy_key,
                "version_number": row.strategy_version_number,
                "source_fingerprint": row.source_fingerprint,
                "implementation_key": row.implementation_key,
                "validated_parameter_snapshot": row.validated_parameter_snapshot,
                "evaluation": row.strategy_evaluation_snapshot,
            },
            "risk_authority": row.risk_authority_snapshot,
            "instruction": {
                "strategy_decision": row.strategy_decision,
                "provider": row.provider,
                "environment": row.environment,
                "provider_account_id": row.provider_account_id,
                "base_currency": row.base_currency,
                "instrument": row.instrument,
                "direction": row.direction,
                "requested_quantity": canonical_decimal_text(row.requested_quantity),
                "approved_entry_price": canonical_decimal_text(
                    row.approved_entry_price
                ),
                "stop_price": canonical_decimal_text(row.stop_price),
                "decision_time": row.decision_time.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "pricing_time": row.pricing_time.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "account_transaction_id": row.account_transaction_id,
                "instrument_transaction_id": row.instrument_transaction_id,
                "display_precision": row.display_precision,
                "trade_units_precision": row.trade_units_precision,
                "correlation": {
                    "client_order_id": row.client_order_id,
                    "client_trade_id": row.client_trade_id,
                    "client_stop_loss_order_id": row.client_stop_loss_order_id,
                    "client_take_profit_order_id": row.client_take_profit_order_id,
                },
            },
        }
        if stored != attempt.immutable_json():
            raise PaperIdentityConflict(
                f"attempt {row.attempt_id} was presented with changed immutable facts"
            )


def execute_durable_paper_execution(
    receipt: PaperStrategyEvaluationReceipt,
    *,
    config: RiskConfig,
    repository: PaperExecutionRepository,
    session_factory: SessionFactory,
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
    """Functional public seam for durable PAPER 04 execution."""
    return PaperDurableExecutionApplication(
        repository=repository,
        session_factory=session_factory,
        account_properties_reader=account_properties_reader,
        execution_account_reader=execution_account_reader,
        execution_instrument_reader=execution_instrument_reader,
        entry_mutation=entry_mutation,
        protection_completion=protection_completion,
        pricing_reader=pricing_reader,
        pricing_reader_factory=pricing_reader_factory,
        risk_service=risk_service,
        attempt_id_factory=attempt_id_factory,
    ).execute(receipt, config=config, attempt_id=attempt_id)


def _observation_for_result(
    result: PaperExecutionResult,
    *,
    read_kind: PaperObservationReadKind,
    mutation_claim_id: UUID | None,
) -> PaperBrokerObservation:
    instruction = result.instruction
    fill = result.fill
    rejection = result.rejection
    protection = result.protection
    provenance = result.transaction_provenance
    target_order = protection.take_profit
    stop_order = protection.stop_loss
    is_target = read_kind is PaperObservationReadKind.TAKE_PROFIT_MUTATION_RESPONSE
    is_trade = read_kind is PaperObservationReadKind.TRADE_DETAIL
    provider_order_id = (
        target_order.broker_order_id
        if is_target and target_order is not None
        else fill.broker_order_id
        if fill is not None
        else rejection.broker_order_id
        if rejection is not None
        else None
    )
    provider_transaction_id = (
        provenance.provider_transaction_ids[-1]
        if (is_target or is_trade) and provenance.provider_transaction_ids
        else fill.broker_fill_transaction_id
        if fill is not None
        else rejection.broker_transaction_id
        if rejection is not None
        else provenance.provider_transaction_ids[-1]
        if provenance.provider_transaction_ids
        else None
    )
    provider_trade_id = fill.broker_trade_id if fill is not None else None
    client_protection_id = (
        target_order.client_order_id
        if target_order is not None
        else stop_order.client_order_id
        if stop_order is not None
        else None
    )
    price = (
        target_order.price
        if is_target and target_order is not None
        else fill.price
        if fill is not None
        else None
    )
    provider_type = (
        "TRADE" if is_trade else "TAKE_PROFIT_ORDER" if is_target else "MARKET_ORDER"
    )
    provider_state = (
        target_order.state if is_target and target_order is not None else None
    )
    facts: dict[str, object] = {
        "account_id": instruction.account.account_id,
        "instrument": "EUR_USD",
        "client_order_id": instruction.correlation.client_order_id,
        "client_trade_id": instruction.correlation.client_trade_id,
        "outcome": result.outcome.value,
        "stop_loss": _protection_json(protection.stop_loss_status, stop_order),
        "take_profit": _protection_json(protection.take_profit_status, target_order),
    }
    if fill is not None:
        facts.update(
            {
                "order_id": fill.broker_order_id,
                "transaction_id": fill.broker_fill_transaction_id,
                "trade_id": fill.broker_trade_id,
                "units": str(fill.signed_units),
                "price": str(fill.price),
                "time": fill.executed_at.isoformat().replace("+00:00", "Z"),
                "actual_initial_risk": str(fill.actual_initial_risk),
            }
        )
    if rejection is not None:
        facts["reason_code"] = rejection.reason_code
    if protection.actual_target_price is not None:
        facts["target_price"] = str(protection.actual_target_price)
    return PaperBrokerObservation(
        attempt_id=instruction.attempt_id,
        read_kind=read_kind,
        object_kind=(
            PaperObservationObjectKind.TRADE
            if is_trade
            else PaperObservationObjectKind.MUTATION_RESULT
        ),
        provider_account_id=instruction.account.account_id,
        instrument=Instrument.EUR_USD,
        normalized_facts=facts,
        provider_order_id=provider_order_id,
        provider_transaction_id=provider_transaction_id,
        provider_trade_id=provider_trade_id,
        client_order_id=instruction.correlation.client_order_id,
        client_trade_id=instruction.correlation.client_trade_id,
        client_protection_order_id=client_protection_id,
        provider_type=provider_type,
        provider_state=provider_state,
        signed_units=fill.signed_units if fill is not None else None,
        price=price,
        executed_at=fill.executed_at if fill is not None else None,
        request_id=provenance.request_id,
        batch_id=provenance.batch_ids[-1] if provenance.batch_ids else None,
        related_transaction_ids=provenance.related_transaction_ids,
        last_transaction_id=provenance.last_transaction_id,
        provider_observed_at=fill.executed_at if fill is not None else None,
        mutation_claim_id=mutation_claim_id,
    )


def _protection_json(
    status: ProtectionLegStatus, order: BrokerProtectionOrder | None
) -> dict[str, object]:
    return {
        "status": status.value,
        "order_id": order.broker_order_id if order is not None else None,
        "client_order_id": order.client_order_id if order is not None else None,
        "price": str(order.price) if order is not None else None,
        "state": order.state if order is not None else None,
    }


def _final_read_kind(result: PaperExecutionResult) -> PaperObservationReadKind:
    if result.outcome is PaperExecutionOutcome.FILLED_PROTECTED or any(
        code.startswith("FINAL_PROTECTION") for code in result.diagnostic_codes
    ):
        return PaperObservationReadKind.TRADE_DETAIL
    return PaperObservationReadKind.TAKE_PROFIT_MUTATION_RESPONSE


def _result_from_row(
    row: PaperExecutionAttemptModel,
    receipt: PaperStrategyEvaluationReceipt,
) -> PaperExecutionResult:
    try:
        decision = receipt.evaluation.decision
        account = ExecutionAccountIdentity(
            provider=Provider(row.provider),
            environment=row.environment,
            account_id=row.provider_account_id,
            base_currency=row.base_currency,
        )
        instruction = PaperExecutionInstruction(
            attempt_id=row.attempt_id,
            strategy_decision=decision,
            account=account,
            instrument=Instrument(row.instrument.replace("_", "/")),
            direction=Direction(row.direction),
            requested_quantity=row.requested_quantity,
            approved_entry_price=row.approved_entry_price,
            stop_price=row.stop_price,
            decision_time=row.decision_time,
            pricing_time=row.pricing_time,
            pre_flight=_risk_decision(row.pre_flight_risk_decision),
            pre_submission=_risk_decision(row.pre_submission_risk_decision),
            observation_provenance=ExecutionObservationProvenance(
                identity=account,
                account_transaction_id=row.account_transaction_id,
                pricing_time=row.pricing_time,
                instrument_transaction_id=row.instrument_transaction_id,
            ),
            display_precision=row.display_precision,
            trade_units_precision=row.trade_units_precision,
        )
        fill = _fill_from_row(row)
        outcome = (
            PaperExecutionOutcome(row.execution_outcome)
            if row.execution_outcome is not None
            else PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
            if fill is not None
            else PaperExecutionOutcome.UNKNOWN
        )
        rejection = (
            BrokerRejection(
                row.rejection_code,
                row.rejection_broker_order_id,
                row.rejection_transaction_id,
            )
            if row.rejection_code is not None
            else None
        )
        uncertainty = (
            BrokerUncertainty(row.uncertainty_code)
            if row.uncertainty_code is not None
            else None
        )
        return PaperExecutionResult(
            outcome=outcome,
            instruction=instruction,
            correlation=instruction.correlation,
            fill=fill,
            protection=_protection_from_row(row),
            rejection=rejection,
            uncertainty=uncertainty,
            transaction_provenance=TransactionProvenance(),
        )
    except (KeyError, TypeError, ValueError, PaperExecutionContractError) as error:
        raise PaperIdentityConflict(
            f"durable attempt {row.attempt_id} contains invalid execution facts"
        ) from error


def _risk_decision(value: object) -> RiskDecision:
    data = cast(dict[str, object], value)
    rejection_value = data.get("rejection")
    return RiskDecision(
        phase=RiskPhase(cast(str, data["phase"])),
        approved=data["approved"] is True,
        rejection=(
            RiskRejection(cast(str, rejection_value))
            if rejection_value is not None
            else None
        ),
        entry_price=_decimal_or_none(data.get("entry_price")),
        stop_price=_decimal_or_none(data.get("stop_price")),
        target_price=_decimal_or_none(data.get("target_price")),
        risk_budget=_decimal_or_none(data.get("risk_budget")),
        quantity=_decimal_or_none(data.get("quantity")),
        actual_risk=_decimal_or_none(data.get("actual_risk")),
    )


def _decimal_or_none(value: object) -> Decimal | None:
    return Decimal(cast(str, value)) if value is not None else None


def _fill_from_row(row: PaperExecutionAttemptModel) -> BrokerFillFacts | None:
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
        raise PaperPersistenceContractError(
            "database contains partial PAPER Fill facts"
        )
    return BrokerFillFacts(
        broker_order_id=cast(str, values[0]),
        broker_fill_transaction_id=cast(str, values[1]),
        broker_trade_id=cast(str, values[2]),
        signed_units=cast(Decimal, values[3]),
        price=cast(Decimal, values[4]),
        executed_at=cast(datetime, values[5]),
        actual_initial_risk=cast(Decimal, values[6]),
    )


def _protection_from_row(row: PaperExecutionAttemptModel) -> ProtectionConfirmation:
    def order(prefix: str) -> BrokerProtectionOrder | None:
        values = (
            getattr(row, f"{prefix}_broker_order_id"),
            getattr(row, f"{prefix}_client_order_id"),
            getattr(row, f"{prefix}_price"),
            getattr(row, f"{prefix}_provider_state"),
        )
        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise PaperPersistenceContractError(
                "database contains partial protection facts"
            )
        return BrokerProtectionOrder(
            cast(str, values[0]),
            cast(str, values[1]),
            cast(Decimal, values[2]),
            cast(str, values[3]),
        )

    return ProtectionConfirmation(
        stop_loss_status=ProtectionLegStatus(row.stop_loss_status),
        stop_loss=order("stop_loss"),
        take_profit_status=ProtectionLegStatus(row.take_profit_status),
        take_profit=order("take_profit"),
        actual_target_price=row.actual_target_price,
    )


__all__ = [
    "PaperDurableExecutionPreparation",
    "PaperDurableExecutionApplication",
    "PaperDurableExecutionPersistenceError",
    "execute_durable_paper_execution",
]
