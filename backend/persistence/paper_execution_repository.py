"""Persistence boundary for the PAPER execution ledger.

This repository owns local transaction boundaries and semantic validation.  It
does not know how to call OANDA and never treats a mutation claim as proof that
an HTTP request was sent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain import Direction
from backend.domain.strategy import ParameterSchema
from backend.paper.execution import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    PaperExecutionOutcome,
    PaperExecutionResult,
    ProtectionConfirmation,
    ProtectionLegStatus,
)
from backend.paper.persistence_contracts import (
    PaperBrokerObservation,
    PaperExecutionAttempt,
    PaperMutationClaim,
    PaperMutationPhase,
    PaperPersistenceContractError,
    PaperReconciliationFindingCode,
    PaperReconciliationRun,
    PaperReconciliationRunStatus,
    ReconciliationStatus,
    canonical_decimal_text,
    validate_execution_outcome_transition,
)
from backend.risk import RiskDecision

from .models import (
    PaperBrokerObservationModel,
    PaperExecutionAttemptModel,
    PaperMutationClaimModel,
    PaperReconciliationRunModel,
    StrategyVersionModel,
)
from .strategy_repository import version_to_domain


class PaperRepositoryError(RuntimeError):
    """Base error for unsafe or impossible PAPER persistence operations."""


class PaperAttemptNotFound(PaperRepositoryError):
    pass


class PaperIdentityConflict(PaperRepositoryError):
    """The same attempt identity was presented with changed immutable facts."""


class DuplicateMutationClaim(PaperRepositoryError):
    """A permanent phase claim already exists and cannot be reacquired."""


class FillConflict(PaperRepositoryError):
    """A second or contradictory Fill was presented for one attempt."""


class StaleReconciliationError(PaperRepositoryError):
    """A reconciliation read began from an obsolete attempt projection version."""


class InvalidPaperTransition(PaperRepositoryError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _strategy_schema(row: StrategyVersionModel) -> tuple[ParameterSchema, ...]:
    return tuple(
        ParameterSchema(
            key=item["key"],
            label=item["label"],
            type=item["type"],
            default=item["default"],
            nullable=item["nullable"],
            minimum=item["min"],
            maximum=item["max"],
            description=item["description"],
            allowed_values=tuple(item.get("allowed_values", [])),
        )
        for item in row.parameter_schema
    )


class PaperExecutionRepository:
    """Provider-neutral repository for one bounded PAPER attempt ledger."""

    def get_attempt(
        self, session: Session, attempt_id: UUID, *, for_update: bool = False
    ) -> PaperExecutionAttemptModel | None:
        statement = select(PaperExecutionAttemptModel).where(
            PaperExecutionAttemptModel.attempt_id == attempt_id
        )
        if for_update:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def create_attempt(
        self, session: Session, attempt: PaperExecutionAttempt
    ) -> PaperExecutionAttemptModel:
        """Insert immutable evidence, or load it after an exact same-ID replay."""
        if type(attempt) is not PaperExecutionAttempt:
            raise PaperPersistenceContractError("attempt must be PaperExecutionAttempt")
        existing = self.get_attempt(session, attempt.attempt_id)
        if existing is not None:
            self._assert_identity(existing, attempt)
            return existing

        self._verify_strategy_receipt(session, attempt)
        instruction = attempt.instruction
        receipt = attempt.receipt
        row = PaperExecutionAttemptModel(
            attempt_id=attempt.attempt_id,
            strategy_version_id=receipt.strategy_version_id,
            strategy_key=receipt.strategy_key,
            strategy_version_number=receipt.version_number,
            source_fingerprint=receipt.source_fingerprint,
            implementation_key=receipt.implementation_key,
            validated_parameter_snapshot=receipt.validated_parameter_snapshot.to_json(),
            strategy_evaluation_snapshot=receipt.evaluation.to_json(),
            risk_authority_snapshot=attempt.risk_authority.to_json(),
            strategy_decision=instruction.strategy_decision.to_json(),
            pre_flight_risk_decision=attempt.risk_authority.to_json()["pre_flight"],
            pre_submission_risk_decision=attempt.risk_authority.to_json()[
                "pre_submission"
            ],
            provider=instruction.account.provider.value,
            environment=instruction.account.environment,
            provider_account_id=instruction.account.account_id,
            base_currency=instruction.account.base_currency,
            instrument=instruction.instrument.value.replace("/", "_"),
            direction=instruction.direction.value,
            requested_quantity=instruction.requested_quantity,
            approved_entry_price=instruction.approved_entry_price,
            stop_price=instruction.stop_price,
            decision_time=instruction.decision_time,
            pricing_time=instruction.pricing_time,
            account_transaction_id=instruction.observation_provenance.account_transaction_id,
            instrument_transaction_id=instruction.observation_provenance.instrument_transaction_id,
            display_precision=instruction.display_precision,
            trade_units_precision=instruction.trade_units_precision,
            client_order_id=instruction.correlation.client_order_id,
            client_trade_id=instruction.correlation.client_trade_id,
            client_stop_loss_order_id=instruction.correlation.client_stop_loss_order_id,
            client_take_profit_order_id=instruction.correlation.client_take_profit_order_id,
        )
        try:
            with session.begin_nested():
                session.add(row)
                session.flush()
        except IntegrityError:
            existing = self.get_attempt(session, attempt.attempt_id)
            if existing is None:
                raise PaperRepositoryError(
                    "attempt insert conflicted without a visible existing attempt"
                ) from None
            self._assert_identity(existing, attempt)
            return existing
        return row

    def commit_entry_claim(
        self,
        session: Session,
        attempt: PaperExecutionAttempt,
        *,
        provider_endpoint_key: str,
        normalized_request_fingerprint: str,
    ) -> PaperMutationClaimModel:
        """Commit the attempt and permanent ENTRY barrier before any network call."""
        claim = self.persist_entry_claim(
            session,
            attempt,
            provider_endpoint_key=provider_endpoint_key,
            normalized_request_fingerprint=normalized_request_fingerprint,
        )
        session.commit()
        return claim

    def persist_entry_claim(
        self,
        session: Session,
        attempt: PaperExecutionAttempt,
        *,
        provider_endpoint_key: str,
        normalized_request_fingerprint: str,
    ) -> PaperMutationClaimModel:
        """Stage the attempt and permanent ENTRY barrier in the caller's transaction.

        This is the caller-owned variant of :meth:`commit_entry_claim`.  It only
        flushes the immutable attempt and possible-mutation claim; the caller
        must commit before any broker mutation is allowed.  Keeping this seam at
        the PAPER 05 repository means runtime code cannot reconstruct or
        reinterpret attempt/claim persistence contracts.
        """
        self.create_attempt(session, attempt)
        claim = self.claim_mutation(
            session,
            attempt.attempt_id,
            phase=PaperMutationPhase.ENTRY,
            provider_endpoint_key=provider_endpoint_key,
            normalized_request_fingerprint=normalized_request_fingerprint,
        )
        return claim

    def claim_mutation(
        self,
        session: Session,
        attempt_id: UUID,
        *,
        phase: PaperMutationPhase,
        provider_endpoint_key: str,
        normalized_request_fingerprint: str,
        claim: PaperMutationClaim | None = None,
    ) -> PaperMutationClaimModel:
        """Insert one permanent phase barrier in the caller's transaction."""
        attempt = self.get_attempt(session, attempt_id, for_update=True)
        if attempt is None:
            raise PaperAttemptNotFound(str(attempt_id))
        if type(phase) is not PaperMutationPhase:
            raise PaperPersistenceContractError("phase must be a PaperMutationPhase")
        existing = session.scalar(
            select(PaperMutationClaimModel).where(
                PaperMutationClaimModel.attempt_id == attempt_id,
                PaperMutationClaimModel.phase == phase.value,
            )
        )
        if existing is not None:
            raise DuplicateMutationClaim(
                f"{phase.value} claim already exists for {attempt_id}"
            )
        value = claim or PaperMutationClaim(
            attempt_id=attempt_id,
            phase=phase,
            provider_endpoint_key=provider_endpoint_key,
            normalized_request_fingerprint=normalized_request_fingerprint,
        )
        if value.attempt_id != attempt_id or value.phase is not phase:
            raise PaperPersistenceContractError("claim does not belong to attempt")
        row = PaperMutationClaimModel(
            claim_id=value.claim_id,
            attempt_id=value.attempt_id,
            phase=value.phase.value,
            claimed_at=value.claimed_at,
            provider_endpoint_key=value.provider_endpoint_key,
            normalized_request_fingerprint=value.normalized_request_fingerprint,
        )
        session.add(row)
        session.flush()
        return row

    def claim_entry(
        self,
        session: Session,
        attempt_id: UUID,
        *,
        provider_endpoint_key: str,
        normalized_request_fingerprint: str,
    ) -> PaperMutationClaimModel:
        return self.claim_mutation(
            session,
            attempt_id,
            phase=PaperMutationPhase.ENTRY,
            provider_endpoint_key=provider_endpoint_key,
            normalized_request_fingerprint=normalized_request_fingerprint,
        )

    def claim_take_profit(
        self,
        session: Session,
        attempt_id: UUID,
        *,
        provider_endpoint_key: str,
        normalized_request_fingerprint: str,
    ) -> PaperMutationClaimModel:
        return self.claim_mutation(
            session,
            attempt_id,
            phase=PaperMutationPhase.TAKE_PROFIT,
            provider_endpoint_key=provider_endpoint_key,
            normalized_request_fingerprint=normalized_request_fingerprint,
        )

    def commit_take_profit_claim(
        self,
        session: Session,
        attempt_id: UUID,
        *,
        protection: ProtectionConfirmation,
        provider_endpoint_key: str,
        normalized_request_fingerprint: str,
    ) -> PaperMutationClaimModel:
        """Commit Fill/target/protection evidence before the dependent PUT."""
        row = self.get_attempt(session, attempt_id, for_update=True)
        if row is None:
            raise PaperAttemptNotFound(str(attempt_id))
        if _row_fill(row) is None:
            raise PaperRepositoryError(
                "Take Profit cannot be claimed before a durable Fill"
            )
        if protection.actual_target_price is None:
            raise PaperRepositoryError(
                "Take Profit cannot be claimed without an actual target"
            )
        self._validate_protection_for_attempt(row, protection, fill=_row_fill(row))
        if (
            protection.stop_loss_status is not ProtectionLegStatus.CONFIRMED
            or protection.stop_loss is None
        ):
            raise PaperRepositoryError(
                "Take Profit cannot be claimed before the Stop is confirmed"
            )
        self._apply_protection_to_row(row, protection)
        row.updated_at = _now()
        session.flush()
        claim = self.claim_take_profit(
            session,
            attempt_id,
            provider_endpoint_key=provider_endpoint_key,
            normalized_request_fingerprint=normalized_request_fingerprint,
        )
        session.commit()
        return claim

    def append_observation(
        self,
        session: Session,
        observation: PaperBrokerObservation,
    ) -> PaperBrokerObservationModel:
        """Append a normalized fact; exact replay is idempotent."""
        if type(observation) is not PaperBrokerObservation:
            raise PaperPersistenceContractError("observation has an invalid type")
        attempt = self.get_attempt(session, observation.attempt_id, for_update=True)
        if attempt is None:
            raise PaperAttemptNotFound(str(observation.attempt_id))
        existing = session.scalar(
            select(PaperBrokerObservationModel).where(
                PaperBrokerObservationModel.attempt_id == observation.attempt_id,
                PaperBrokerObservationModel.normalized_facts_fingerprint
                == observation.normalized_facts_fingerprint,
            )
        )
        if existing is not None:
            return existing
        sequence = session.scalar(
            select(func.max(PaperBrokerObservationModel.observation_sequence)).where(
                PaperBrokerObservationModel.attempt_id == observation.attempt_id
            )
        )
        claim = None
        if observation.mutation_claim_id is not None:
            claim = session.scalar(
                select(PaperMutationClaimModel).where(
                    PaperMutationClaimModel.claim_id == observation.mutation_claim_id,
                    PaperMutationClaimModel.attempt_id == observation.attempt_id,
                )
            )
            if claim is None:
                raise PaperRepositoryError("observation claim is not owned by attempt")
        run = None
        if observation.reconciliation_run_id is not None:
            run = session.scalar(
                select(PaperReconciliationRunModel).where(
                    PaperReconciliationRunModel.run_id
                    == observation.reconciliation_run_id,
                    PaperReconciliationRunModel.attempt_id == observation.attempt_id,
                )
            )
            if run is None:
                raise PaperRepositoryError("observation run is not owned by attempt")
        row = PaperBrokerObservationModel(
            observation_id=observation.observation_id,
            attempt_id=observation.attempt_id,
            mutation_claim_id=observation.mutation_claim_id,
            reconciliation_run_id=observation.reconciliation_run_id,
            observation_sequence=int(sequence or 0) + 1,
            read_kind=observation.read_kind.value,
            object_kind=observation.object_kind.value,
            provider="OANDA",
            environment="PRACTICE",
            provider_account_id=observation.provider_account_id,
            instrument=(
                observation.instrument.value.replace("/", "_")
                if observation.instrument
                else None
            ),
            provider_order_id=observation.provider_order_id,
            provider_transaction_id=observation.provider_transaction_id,
            provider_trade_id=observation.provider_trade_id,
            client_order_id=observation.client_order_id,
            client_trade_id=observation.client_trade_id,
            client_protection_order_id=observation.client_protection_order_id,
            provider_type=observation.provider_type,
            provider_state=observation.provider_state,
            signed_units=observation.signed_units,
            price=observation.price,
            executed_at=observation.executed_at,
            request_id=observation.request_id,
            batch_id=observation.batch_id,
            related_transaction_ids=list(observation.related_transaction_ids),
            last_transaction_id=observation.last_transaction_id,
            provider_observed_at=observation.provider_observed_at,
            atlas_observed_at=observation.atlas_observed_at,
            normalized_schema_version=observation.normalized_schema_version,
            normalized_facts=observation.normalized_facts,
            normalized_facts_fingerprint=observation.normalized_facts_fingerprint,
        )
        session.add(row)
        session.flush()
        return row

    def record_fill(
        self, session: Session, attempt_id: UUID, fill: BrokerFillFacts
    ) -> PaperExecutionAttemptModel:
        """Persist one complete Fill set, with write-once non-erasure semantics."""
        if type(fill) is not BrokerFillFacts:
            raise PaperPersistenceContractError("fill has an invalid type")
        row = self.get_attempt(session, attempt_id, for_update=True)
        if row is None:
            raise PaperAttemptNotFound(str(attempt_id))
        current = _row_fill(row)
        if current is not None:
            if current != fill:
                raise FillConflict(
                    f"attempt {attempt_id} already has different Fill facts"
                )
            return row
        row.fill_broker_order_id = fill.broker_order_id
        row.fill_transaction_id = fill.broker_fill_transaction_id
        row.fill_trade_id = fill.broker_trade_id
        row.fill_signed_units = fill.signed_units
        row.fill_price = fill.price
        row.fill_executed_at = fill.executed_at
        row.fill_actual_initial_risk = fill.actual_initial_risk
        row.updated_at = _now()
        session.flush()
        return row

    def apply_protection(
        self,
        session: Session,
        attempt_id: UUID,
        protection: ProtectionConfirmation,
        *,
        actual_target_price: object = None,
    ) -> PaperExecutionAttemptModel:
        """Apply independent current Stop/Take Profit facts without touching Fill."""
        if type(protection) is not ProtectionConfirmation:
            raise PaperPersistenceContractError("protection has an invalid type")
        row = self.get_attempt(session, attempt_id, for_update=True)
        if row is None:
            raise PaperAttemptNotFound(str(attempt_id))
        fill = _row_fill(row)
        if actual_target_price is not None and type(actual_target_price) is not Decimal:
            raise PaperPersistenceContractError("actual target must be a Decimal")
        if actual_target_price is not None and (
            actual_target_price != protection.actual_target_price
        ):
            raise PaperPersistenceContractError(
                "actual target does not match protection"
            )
        self._validate_protection_for_attempt(row, protection, fill=fill)
        row.stop_loss_status = protection.stop_loss_status.value
        if protection.stop_loss is not None:
            row.stop_loss_broker_order_id = protection.stop_loss.broker_order_id
            row.stop_loss_client_order_id = protection.stop_loss.client_order_id
            row.stop_loss_price = protection.stop_loss.price
            row.stop_loss_provider_state = protection.stop_loss.state
        row.take_profit_status = protection.take_profit_status.value
        if protection.take_profit is not None:
            row.take_profit_broker_order_id = protection.take_profit.broker_order_id
            row.take_profit_client_order_id = protection.take_profit.client_order_id
            row.take_profit_price = protection.take_profit.price
            row.take_profit_provider_state = protection.take_profit.state
        if protection.actual_target_price is not None:
            row.actual_target_price = protection.actual_target_price
        row.updated_at = _now()
        session.flush()
        return row

    def apply_execution_outcome(
        self,
        session: Session,
        attempt_id: UUID,
        outcome: PaperExecutionOutcome,
        *,
        protection: ProtectionConfirmation | None = None,
        fill: BrokerFillFacts | None = None,
        rejection_code: str | None = None,
        rejection_broker_order_id: str | None = None,
        rejection_transaction_id: str | None = None,
        uncertainty_code: str | None = None,
    ) -> PaperExecutionAttemptModel:
        """Apply only a proof-valid outcome; existing Fill facts are retained."""
        row = self.get_attempt(session, attempt_id, for_update=True)
        if row is None:
            raise PaperAttemptNotFound(str(attempt_id))
        current_fill = _row_fill(row)
        if fill is not None and current_fill is not None and fill != current_fill:
            raise FillConflict(f"attempt {attempt_id} already has different Fill facts")
        effective_fill = fill or current_fill
        if protection is not None:
            self._validate_protection_for_attempt(row, protection, fill=effective_fill)
        current_outcome = (
            PaperExecutionOutcome(row.execution_outcome)
            if row.execution_outcome is not None
            else None
        )
        proposed_protection = protection or _row_protection(row)
        try:
            validate_execution_outcome_transition(
                current_outcome,
                outcome,
                fill=effective_fill,
                protection=proposed_protection,
            )
        except PaperPersistenceContractError as error:
            raise InvalidPaperTransition(str(error)) from error
        if fill is not None:
            current = current_fill
            if current is None:
                row = self.record_fill(session, attempt_id, fill)
        current_fill = _row_fill(row)
        if protection is not None:
            self._apply_protection_to_row(row, protection)
        projection_protection = protection or _row_protection(row)
        try:
            validate_execution_outcome_transition(
                PaperExecutionOutcome(row.execution_outcome)
                if row.execution_outcome is not None
                else None,
                outcome,
                fill=current_fill,
                protection=projection_protection,
            )
        except PaperPersistenceContractError as error:
            raise InvalidPaperTransition(str(error)) from error
        row.execution_outcome = outcome.value
        if rejection_code is not None:
            row.rejection_code = rejection_code
        if rejection_broker_order_id is not None:
            row.rejection_broker_order_id = rejection_broker_order_id
        if rejection_transaction_id is not None:
            row.rejection_transaction_id = rejection_transaction_id
        if uncertainty_code is not None:
            row.uncertainty_code = uncertainty_code
        row.updated_at = _now()
        session.flush()
        return row

    def apply_result(
        self,
        session: Session,
        result: PaperExecutionResult,
        *,
        attempt: PaperExecutionAttempt | None = None,
    ) -> PaperExecutionAttemptModel:
        """Persist normalized P04 result facts through the guarded public seam."""
        if type(result) is not PaperExecutionResult:
            raise PaperPersistenceContractError("result has an invalid type")
        row = self.get_attempt(session, result.instruction.attempt_id, for_update=True)
        if row is None:
            raise PaperAttemptNotFound(str(result.instruction.attempt_id))
        if attempt is not None:
            if type(attempt) is not PaperExecutionAttempt:
                raise PaperPersistenceContractError("attempt has an invalid type")
            if attempt.attempt_id != result.instruction.attempt_id:
                raise PaperIdentityConflict(
                    "result attempt does not match durable attempt"
                )
            self._assert_identity(row, attempt)
        self._assert_result_identity(row, result)
        return self.apply_execution_outcome(
            session,
            result.instruction.attempt_id,
            result.outcome,
            fill=result.fill,
            protection=result.protection,
            rejection_code=result.rejection.detail_code if result.rejection else None,
            rejection_broker_order_id=(
                result.rejection.broker_order_id if result.rejection else None
            ),
            rejection_transaction_id=(
                result.rejection.broker_transaction_id if result.rejection else None
            ),
            uncertainty_code=(
                result.uncertainty.detail_code if result.uncertainty else None
            ),
        )

    def create_reconciliation_run(
        self, session: Session, run: PaperReconciliationRun
    ) -> PaperReconciliationRunModel:
        if type(run) is not PaperReconciliationRun:
            raise PaperPersistenceContractError("run has an invalid type")
        attempt = self.get_attempt(session, run.attempt_id, for_update=True)
        if attempt is None:
            raise PaperAttemptNotFound(str(run.attempt_id))
        self._verify_next_run_sequence(session, run)
        row = self._run_model(run)
        session.add(row)
        session.flush()
        return row

    def next_reconciliation_sequence(self, session: Session, attempt_id: UUID) -> int:
        """Return the next per-attempt run number without taking a long lock."""
        if self.get_attempt(session, attempt_id) is None:
            raise PaperAttemptNotFound(str(attempt_id))
        latest = session.scalar(
            select(func.max(PaperReconciliationRunModel.run_sequence)).where(
                PaperReconciliationRunModel.attempt_id == attempt_id
            )
        )
        return int(latest or 0) + 1

    def has_mutation_claim(
        self,
        session: Session,
        attempt_id: UUID,
        phase: PaperMutationPhase,
    ) -> bool:
        """Return whether the permanent phase barrier has already been committed."""
        if type(phase) is not PaperMutationPhase:
            raise PaperPersistenceContractError("phase must be a PaperMutationPhase")
        return (
            session.scalar(
                select(PaperMutationClaimModel.claim_id).where(
                    PaperMutationClaimModel.attempt_id == attempt_id,
                    PaperMutationClaimModel.phase == phase.value,
                )
            )
            is not None
        )

    def apply_reconciliation_run(
        self,
        session: Session,
        run: PaperReconciliationRun,
        *,
        reconciliation_status: ReconciliationStatus,
        observations: Sequence[PaperBrokerObservation] = (),
        reconciliation_block_code: str | None = None,
        fill: BrokerFillFacts | None = None,
        protection: ProtectionConfirmation | None = None,
        rejection_code: str | None = None,
        rejection_broker_order_id: str | None = None,
        rejection_transaction_id: str | None = None,
    ) -> PaperReconciliationRunModel:
        """Append observations and apply a run only against its observed version."""
        if type(run) is not PaperReconciliationRun:
            raise PaperPersistenceContractError("run has an invalid type")
        if type(reconciliation_status) is not ReconciliationStatus:
            raise PaperPersistenceContractError("reconciliation_status is invalid")
        attempt = self.get_attempt(session, run.attempt_id, for_update=True)
        if attempt is None:
            raise PaperAttemptNotFound(str(run.attempt_id))
        if attempt.projection_version != run.projection_version_observed:
            latest = session.scalar(
                select(func.max(PaperReconciliationRunModel.run_sequence)).where(
                    PaperReconciliationRunModel.attempt_id == run.attempt_id
                )
            )
            stale = replace(
                run,
                run_sequence=max(run.run_sequence, int(latest or 0) + 1),
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
            stale_row = self._run_model(stale)
            session.add(stale_row)
            session.flush()
            raise StaleReconciliationError(str(run.run_id))
        self._verify_next_run_sequence(session, run)
        new_projection_version = attempt.projection_version + 1
        applied_run = replace(
            run,
            projection_version_applied=new_projection_version,
            frontier_applied=_max_transaction_id(
                attempt.last_applied_transaction_id or attempt.account_transaction_id,
                run.frontier_applied,
            ),
        )
        run_row = self._run_model(applied_run)
        session.add(run_row)
        session.flush()
        for observation in observations:
            if observation.reconciliation_run_id != run.run_id:
                raise PaperPersistenceContractError(
                    "reconciliation observation must reference its run"
                )
            self.append_observation(session, observation)
        if fill is not None:
            self.record_fill(session, run.attempt_id, fill)
            attempt = self.get_attempt(session, run.attempt_id, for_update=True)
            if attempt is None:  # pragma: no cover - protected by the FK
                raise PaperAttemptNotFound(str(run.attempt_id))
        if protection is not None:
            self.apply_protection(session, run.attempt_id, protection)
            attempt = self.get_attempt(session, run.attempt_id, for_update=True)
            if attempt is None:  # pragma: no cover - protected by the FK
                raise PaperAttemptNotFound(str(run.attempt_id))
        if run.resulting_execution_outcome is not None:
            current_fill = _row_fill(attempt)
            try:
                validate_execution_outcome_transition(
                    PaperExecutionOutcome(attempt.execution_outcome)
                    if attempt.execution_outcome is not None
                    else None,
                    run.resulting_execution_outcome,
                    fill=current_fill,
                    protection=_row_protection(attempt),
                )
            except PaperPersistenceContractError as error:
                raise InvalidPaperTransition(str(error)) from error
            attempt.execution_outcome = run.resulting_execution_outcome.value
        if rejection_code is not None:
            attempt.rejection_code = rejection_code
            attempt.rejection_broker_order_id = rejection_broker_order_id
            attempt.rejection_transaction_id = rejection_transaction_id
        attempt.reconciliation_status = reconciliation_status.value
        attempt.reconciliation_block_code = reconciliation_block_code
        attempt.last_reconciliation_run_id = run.run_id
        attempt.last_reconciled_at = run.completed_at
        attempt.last_applied_transaction_id = applied_run.frontier_applied
        attempt.projection_version = new_projection_version
        attempt.updated_at = _now()
        session.flush()
        return run_row

    def _verify_strategy_receipt(
        self, session: Session, attempt: PaperExecutionAttempt
    ) -> None:
        receipt = attempt.receipt
        row = session.get(StrategyVersionModel, receipt.strategy_version_id)
        if row is None:
            raise PaperRepositoryError("StrategyVersion receipt does not exist")
        version = version_to_domain(row)
        if (
            version.id != receipt.strategy_version_id
            or version.strategy_key != receipt.strategy_key
            or version.version_number != receipt.version_number
            or version.source_fingerprint != receipt.source_fingerprint
            or version.implementation_key != receipt.implementation_key
        ):
            raise PaperIdentityConflict(
                "StrategyVersion receipt does not match database"
            )
        try:
            validated = type(receipt.validated_parameter_snapshot).from_mapping(
                _strategy_schema(row), receipt.validated_parameter_snapshot.to_json()
            )
        except Exception as error:
            raise PaperIdentityConflict(
                "Strategy parameter snapshot is invalid"
            ) from error
        if validated != receipt.validated_parameter_snapshot:
            raise PaperIdentityConflict(
                "Strategy parameter snapshot does not match version"
            )

    def _assert_identity(
        self, row: PaperExecutionAttemptModel, attempt: PaperExecutionAttempt
    ) -> None:
        stored = {
            "receipt": {
                "schema_version": "ATLAS_PAPER_STRATEGY_RECEIPT_V1",
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
                f"attempt {attempt.attempt_id} was presented with changed "
                "immutable facts"
            )

    @staticmethod
    def _assert_result_identity(
        row: PaperExecutionAttemptModel, result: PaperExecutionResult
    ) -> None:
        instruction = result.instruction
        if result.correlation != instruction.correlation:
            raise PaperIdentityConflict("result correlation does not match instruction")
        stored = {
            "strategy_decision": row.strategy_decision,
            "provider": row.provider,
            "environment": row.environment,
            "provider_account_id": row.provider_account_id,
            "base_currency": row.base_currency,
            "instrument": row.instrument,
            "direction": row.direction,
            "requested_quantity": canonical_decimal_text(row.requested_quantity),
            "approved_entry_price": canonical_decimal_text(row.approved_entry_price),
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
            "pre_flight": row.pre_flight_risk_decision,
            "pre_submission": row.pre_submission_risk_decision,
            "correlation": {
                "client_order_id": row.client_order_id,
                "client_trade_id": row.client_trade_id,
                "client_stop_loss_order_id": row.client_stop_loss_order_id,
                "client_take_profit_order_id": row.client_take_profit_order_id,
            },
        }
        presented = {
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
            "pricing_time": instruction.pricing_time.isoformat().replace("+00:00", "Z"),
            "account_transaction_id": (
                instruction.observation_provenance.account_transaction_id
            ),
            "instrument_transaction_id": (
                instruction.observation_provenance.instrument_transaction_id
            ),
            "display_precision": instruction.display_precision,
            "trade_units_precision": instruction.trade_units_precision,
            "pre_flight": _risk_decision_json(instruction.pre_flight),
            "pre_submission": _risk_decision_json(instruction.pre_submission),
            "correlation": {
                "client_order_id": instruction.correlation.client_order_id,
                "client_trade_id": instruction.correlation.client_trade_id,
                "client_stop_loss_order_id": (
                    instruction.correlation.client_stop_loss_order_id
                ),
                "client_take_profit_order_id": (
                    instruction.correlation.client_take_profit_order_id
                ),
            },
        }
        if stored != presented:
            raise PaperIdentityConflict(
                f"result for attempt {instruction.attempt_id} has changed "
                "immutable instruction facts"
            )

    @classmethod
    def _validate_protection_for_attempt(
        cls,
        row: PaperExecutionAttemptModel,
        protection: ProtectionConfirmation,
        *,
        fill: BrokerFillFacts | None,
    ) -> None:
        if type(protection) is not ProtectionConfirmation:
            raise PaperPersistenceContractError("protection has an invalid type")

        expected_target = None
        if fill is not None:
            expected_target = cls._expected_target_price(row, fill)
        elif (
            protection.actual_target_price is not None
            or protection.take_profit is not None
            or protection.take_profit_status is ProtectionLegStatus.CONFIRMED
            or protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
        ):
            raise PaperIdentityConflict(
                "confirmed protection requires a durable attributable Fill"
            )

        cls._validate_protection_leg(
            row,
            protection.stop_loss,
            protection.stop_loss_status,
            expected_client_id=row.client_stop_loss_order_id,
            expected_price=row.stop_price,
            name="Stop Loss",
        )
        cls._validate_protection_leg(
            row,
            protection.take_profit,
            protection.take_profit_status,
            expected_client_id=row.client_take_profit_order_id,
            expected_price=expected_target,
            name="Take Profit",
        )
        if protection.actual_target_price is not None and (
            expected_target is None or protection.actual_target_price != expected_target
        ):
            raise PaperIdentityConflict(
                "actual target is not derived from the durable Fill and Strategy"
            )
        if row.actual_target_price is not None and (
            protection.actual_target_price is not None
            and row.actual_target_price != protection.actual_target_price
        ):
            raise PaperIdentityConflict("actual target conflicts with durable evidence")

    @staticmethod
    def _validate_protection_leg(
        row: PaperExecutionAttemptModel,
        order: BrokerProtectionOrder | None,
        status: ProtectionLegStatus,
        *,
        expected_client_id: str,
        expected_price: Decimal | None,
        name: str,
    ) -> None:
        if order is None:
            if status is ProtectionLegStatus.CONFIRMED:
                raise PaperIdentityConflict(f"confirmed {name} is missing")
            return
        if expected_price is None:
            raise PaperIdentityConflict(f"{name} cannot be attributed without a Fill")
        if order.client_order_id != expected_client_id or order.price != expected_price:
            raise PaperIdentityConflict(f"{name} is not attributed to this attempt")
        if status is ProtectionLegStatus.CONFIRMED and order.state != "PENDING":
            raise PaperIdentityConflict(
                f"confirmed {name} has an invalid provider state"
            )
        if status is ProtectionLegStatus.REJECTED and order.state not in {
            "CANCELLED",
            "FILLED",
            "REJECTED",
        }:
            raise PaperIdentityConflict(
                f"rejected {name} has an invalid provider state"
            )
        if status is ProtectionLegStatus.UNKNOWN and order.state in {
            "PENDING",
            "CANCELLED",
            "FILLED",
            "REJECTED",
        }:
            raise PaperIdentityConflict(
                f"unknown {name} has a classified provider state"
            )

        prefix = "stop_loss" if name == "Stop Loss" else "take_profit"
        durable_broker_id = getattr(row, f"{prefix}_broker_order_id")
        if durable_broker_id is not None and durable_broker_id != order.broker_order_id:
            raise PaperIdentityConflict(
                f"{name} broker identity conflicts with durable evidence"
            )

    @staticmethod
    def _expected_target_price(
        row: PaperExecutionAttemptModel, fill: BrokerFillFacts
    ) -> Decimal:
        snapshot = cast(dict[str, object], row.risk_authority_snapshot)
        intent_value = snapshot.get("trade_intent")
        if type(intent_value) is not dict:
            raise PaperRepositoryError("durable Risk trade intent is not an object")
        intent = cast(dict[str, object], intent_value)
        target_value = intent.get("target")
        if type(target_value) is not dict:
            raise PaperRepositoryError("durable Risk target is missing")
        target = cast(dict[str, object], target_value)
        multiple_value = target.get("multiple")
        if type(multiple_value) is not str:
            raise PaperRepositoryError("durable Risk target multiple is invalid")
        try:
            multiple = Decimal(multiple_value)
        except Exception as error:
            raise PaperRepositoryError(
                "durable Risk target multiple is invalid"
            ) from error
        if not multiple.is_finite() or multiple <= 0:
            raise PaperRepositoryError("durable Risk target multiple is invalid")
        distance = abs(fill.price - row.stop_price)
        if distance <= 0:
            raise PaperRepositoryError("durable Fill and Stop do not define risk")
        if row.direction == Direction.LONG.value:
            return fill.price + multiple * distance
        if row.direction == Direction.SHORT.value:
            return fill.price - multiple * distance
        raise PaperRepositoryError("durable attempt direction is invalid")

    @staticmethod
    def _apply_protection_to_row(
        row: PaperExecutionAttemptModel, protection: ProtectionConfirmation
    ) -> None:
        row.stop_loss_status = protection.stop_loss_status.value
        row.take_profit_status = protection.take_profit_status.value
        if protection.stop_loss is not None:
            row.stop_loss_broker_order_id = protection.stop_loss.broker_order_id
            row.stop_loss_client_order_id = protection.stop_loss.client_order_id
            row.stop_loss_price = protection.stop_loss.price
            row.stop_loss_provider_state = protection.stop_loss.state
        if protection.take_profit is not None:
            row.take_profit_broker_order_id = protection.take_profit.broker_order_id
            row.take_profit_client_order_id = protection.take_profit.client_order_id
            row.take_profit_price = protection.take_profit.price
            row.take_profit_provider_state = protection.take_profit.state
        if protection.actual_target_price is not None:
            row.actual_target_price = protection.actual_target_price

    @staticmethod
    def _run_model(run: PaperReconciliationRun) -> PaperReconciliationRunModel:
        return PaperReconciliationRunModel(
            run_id=run.run_id,
            attempt_id=run.attempt_id,
            run_sequence=run.run_sequence,
            requested_at=run.requested_at,
            read_started_at=run.read_started_at,
            completed_at=run.completed_at,
            status=run.status.value,
            projection_version_observed=run.projection_version_observed,
            projection_version_applied=run.projection_version_applied,
            read_count=run.read_count,
            read_budget=run.read_budget,
            frontier_before=run.frontier_before,
            frontier_observed=run.frontier_observed,
            frontier_applied=run.frontier_applied,
            non_atomic_read_set=run.non_atomic_read_set,
            prior_execution_outcome=(
                run.prior_execution_outcome.value
                if run.prior_execution_outcome
                else None
            ),
            resulting_execution_outcome=(
                run.resulting_execution_outcome.value
                if run.resulting_execution_outcome
                else None
            ),
            finding_codes=[code.value for code in run.finding_codes],
            diagnostic_summary=run.diagnostic_summary,
        )

    @staticmethod
    def _verify_next_run_sequence(
        session: Session, run: PaperReconciliationRun
    ) -> None:
        latest = session.scalar(
            select(func.max(PaperReconciliationRunModel.run_sequence)).where(
                PaperReconciliationRunModel.attempt_id == run.attempt_id
            )
        )
        expected = int(latest or 0) + 1
        if run.run_sequence != expected:
            raise PaperRepositoryError(
                f"reconciliation run sequence must be {expected}, "
                f"got {run.run_sequence}"
            )


def _risk_decision_json(decision: RiskDecision) -> dict[str, object]:
    return {
        "phase": decision.phase.value,
        "approved": decision.approved,
        "rejection": decision.rejection.value if decision.rejection else None,
        "entry_price": (
            str(decision.entry_price) if decision.entry_price is not None else None
        ),
        "stop_price": (
            str(decision.stop_price) if decision.stop_price is not None else None
        ),
        "target_price": (
            str(decision.target_price) if decision.target_price is not None else None
        ),
        "risk_budget": (
            str(decision.risk_budget) if decision.risk_budget is not None else None
        ),
        "quantity": str(decision.quantity) if decision.quantity is not None else None,
        "actual_risk": (
            str(decision.actual_risk) if decision.actual_risk is not None else None
        ),
    }


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
    (
        broker_order_id,
        fill_transaction_id,
        fill_trade_id,
        signed_units,
        price,
        executed_at,
        actual_initial_risk,
    ) = values
    assert broker_order_id is not None
    assert fill_transaction_id is not None
    assert fill_trade_id is not None
    assert signed_units is not None
    assert price is not None
    assert executed_at is not None
    assert actual_initial_risk is not None
    return BrokerFillFacts(
        broker_order_id=broker_order_id,
        broker_fill_transaction_id=fill_transaction_id,
        broker_trade_id=fill_trade_id,
        signed_units=signed_units,
        price=price,
        executed_at=executed_at,
        actual_initial_risk=actual_initial_risk,
    )


def _row_protection(row: PaperExecutionAttemptModel) -> ProtectionConfirmation:
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
            raise PaperRepositoryError("database contains partial protection facts")
        return BrokerProtectionOrder(
            broker_order_id=values[0],
            client_order_id=values[1],
            price=values[2],
            state=values[3],
        )

    return ProtectionConfirmation(
        stop_loss_status=ProtectionLegStatus(row.stop_loss_status),
        stop_loss=order("stop_loss"),
        take_profit_status=ProtectionLegStatus(row.take_profit_status),
        take_profit=order("take_profit"),
        actual_target_price=row.actual_target_price,
    )


def _max_transaction_id(current: str | None, proposed: str | None) -> str | None:
    """Return the greatest numeric OANDA frontier without allowing regression."""
    for value in (current, proposed):
        if value is not None and not value.isdigit():
            raise PaperPersistenceContractError("transaction frontier is not numeric")
    if current is None:
        return proposed
    if proposed is None:
        return current
    return proposed if int(proposed) >= int(current) else current


__all__ = [
    "DuplicateMutationClaim",
    "FillConflict",
    "InvalidPaperTransition",
    "PaperAttemptNotFound",
    "PaperExecutionRepository",
    "PaperIdentityConflict",
    "PaperRepositoryError",
    "StaleReconciliationError",
]
