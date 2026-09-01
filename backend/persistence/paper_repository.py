"""Flush-only repositories for the bounded PAPER persistence boundary.

These repositories deliberately do not perform broker I/O or lifecycle
orchestration.  Callers own the transaction, and every method either records a
fact or makes a small, explicit mutable projection change.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.strategy import StrategyStateEnvelope

from .models import (
    AccountTransactionCursorModel,
    DeploymentFrontierModel,
    DeploymentModel,
    PendingEntryHandoffModel,
    ReconciliationRecordModel,
    RuntimeHeartbeatModel,
    StrategyStateModel,
    SystemEventModel,
    TradingAccountModel,
    TradingAccountSnapshotModel,
)
from .timestamps import (
    require_non_decreasing_utc,
    require_optional_utc,
    require_utc,
)


def _detail(value: str) -> str:
    sanitized = " ".join(value.split())[:500]
    if not sanitized:
        raise ValueError("diagnostic detail is required")
    return sanitized


def _safe_mapping(value: Mapping[str, object], *, depth: int = 0) -> dict[str, object]:
    """Keep JSON evidence bounded and reject common secret-bearing keys."""
    if depth > 4:
        raise ValueError("provider evidence is too deeply nested")
    result: dict[str, object] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if any(
            secret in lowered
            for secret in ("token", "secret", "password", "authorization", "api_key")
        ):
            raise ValueError("secret-bearing provider evidence is not persisted")
        if isinstance(item, Mapping):
            result[str(key)] = _safe_mapping(
                cast(Mapping[str, object], item), depth=depth + 1
            )
        elif isinstance(item, list):
            result[str(key)] = [
                (
                    _safe_mapping(
                        cast(Mapping[str, object], entry), depth=depth + 1
                    )
                    if isinstance(entry, Mapping)
                    else _detail(entry) if isinstance(entry, str) and entry else entry
                )
                for entry in cast(list[object], item)[:100]
            ]
        elif isinstance(item, str):
            result[str(key)] = _detail(item) if item else item
        else:
            result[str(key)] = item
    return result


def stable_client_correlation_id(order_id: UUID) -> str:
    """Derive the reusable OANDA client correlation from the local Order ID."""
    if type(order_id) is not UUID:
        raise TypeError("order_id must be a UUID")
    return f"atlas-paper-01-order-{order_id}"


class TradingAccountRepository:
    def create(
        self,
        session: Session,
        *,
        label: str,
        external_account_id: str,
        capabilities: Mapping[str, object] | None = None,
        mt4_association_status: str = "UNKNOWN",
        provenance: Mapping[str, object] | None = None,
        account_id: UUID | None = None,
    ) -> TradingAccountModel:
        if not label.strip() or not external_account_id.strip():
            raise ValueError("account label and external account ID are required")
        if mt4_association_status not in {"UNKNOWN", "NOT_ASSOCIATED", "ASSOCIATED"}:
            raise ValueError("invalid MT4 association status")
        row = TradingAccountModel(
            id=account_id,
            label=label.strip(),
            external_account_id=external_account_id.strip(),
            capabilities=_safe_mapping(capabilities or {}),
            mt4_association_status=mt4_association_status,
            provenance=_safe_mapping(provenance or {}),
        )
        session.add(row)
        session.flush()
        return row

    def get(self, session: Session, account_id: UUID) -> TradingAccountModel | None:
        return session.get(TradingAccountModel, account_id)


class DeploymentRepository:
    def create(
        self,
        session: Session,
        *,
        trading_account_id: UUID,
        strategy_version_id: UUID,
        venue_instrument_id: UUID,
        parameter_snapshot: Mapping[str, object],
        risk_snapshot: Mapping[str, object],
        execution_provenance: Mapping[str, object] | None = None,
        deployment_id: UUID | None = None,
    ) -> DeploymentModel:
        if not parameter_snapshot or not risk_snapshot:
            raise ValueError(
                "Deployment requires immutable parameter and Risk snapshots"
            )
        row = DeploymentModel(
            id=deployment_id,
            trading_account_id=trading_account_id,
            strategy_version_id=strategy_version_id,
            venue_instrument_id=venue_instrument_id,
            parameter_snapshot=_safe_mapping(parameter_snapshot),
            risk_snapshot=_safe_mapping(risk_snapshot),
            execution_provenance=_safe_mapping(execution_provenance or {}),
        )
        session.add(row)
        session.flush()
        return row

    def get(self, session: Session, deployment_id: UUID) -> DeploymentModel | None:
        return session.get(DeploymentModel, deployment_id)

    def get_for_update(
        self, session: Session, deployment_id: UUID
    ) -> DeploymentModel | None:
        return session.scalar(
            select(DeploymentModel)
            .where(DeploymentModel.id == deployment_id)
            .with_for_update()
        )

    def request_state(
        self, session: Session, deployment_id: UUID, desired_state: str
    ) -> DeploymentModel:
        if desired_state not in {"DRAFT", "RUNNING", "PAUSED", "STOPPED", "ARCHIVED"}:
            raise ValueError("invalid desired Deployment state")
        row = self.get_for_update(session, deployment_id)
        if row is None:
            raise ValueError("Deployment does not exist")
        if row.actual_state == "ARCHIVED" and desired_state != "ARCHIVED":
            raise ValueError("archived Deployment cannot be activated")
        row.desired_state = desired_state
        session.flush()
        return row

    def set_actual_state(
        self,
        session: Session,
        deployment_id: UUID,
        actual_state: str,
        *,
        safety_reason: str | None = None,
    ) -> DeploymentModel:
        allowed = {
            "DRAFT", "STARTING", "RUNNING", "PAUSED", "STOPPED", "FAILED",
            "RECONCILIATION_REQUIRED", "ARCHIVED",
        }
        if actual_state not in allowed:
            raise ValueError("invalid actual Deployment state")
        row = self.get_for_update(session, deployment_id)
        if row is None:
            raise ValueError("Deployment does not exist")
        row.actual_state = actual_state
        row.safety_reason = _detail(safety_reason) if safety_reason else None
        session.flush()
        return row

    def mark_first_trade(
        self, session: Session, deployment_id: UUID, traded_at: datetime
    ) -> DeploymentModel:
        require_utc(traded_at, "traded_at")
        row = self.get_for_update(session, deployment_id)
        if row is None:
            raise ValueError("Deployment does not exist")
        if row.first_trade_at is None:
            row.first_trade_at = traded_at
        session.flush()
        return row


class StrategyStateRepository:
    def append(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        strategy_version_id: UUID,
        envelope: StrategyStateEnvelope,
        analytical_bar_fingerprint: str | None = None,
        state_version: int | None = None,
    ) -> StrategyStateModel:
        if type(envelope) is not StrategyStateEnvelope:
            raise TypeError("envelope must be a StrategyStateEnvelope")
        current_frontier = require_optional_utc(
            envelope.last_evaluated_bar_end, "last_evaluated_bar_end"
        )
        if (current_frontier is None) != (analytical_bar_fingerprint is None):
            raise ValueError(
                "analytical frontier and bar fingerprint must be present together"
            )
        if analytical_bar_fingerprint is not None and (
            len(analytical_bar_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in analytical_bar_fingerprint
            )
        ):
            raise ValueError("analytical bar fingerprint must be lowercase SHA-256")
        if envelope.pending_entry is not None:
            require_utc(
                envelope.pending_entry.decision_frontier,
                "pending_entry.decision_frontier",
            )
            require_utc(
                envelope.pending_entry.decision_time,
                "pending_entry.decision_time",
            )
        deployment = session.scalar(
            select(DeploymentModel)
            .where(DeploymentModel.id == deployment_id)
            .with_for_update()
        )
        if deployment is None:
            raise ValueError("Deployment does not exist")
        if deployment.strategy_version_id != strategy_version_id:
            raise ValueError("Strategy state does not match Deployment StrategyVersion")
        latest = session.scalar(
            select(StrategyStateModel)
            .where(StrategyStateModel.deployment_id == deployment_id)
            .order_by(StrategyStateModel.state_version.desc())
        )
        if latest is not None:
            if latest.last_evaluated_bar_end == current_frontier:
                if (
                    latest.analytical_bar_fingerprint == analytical_bar_fingerprint
                    and latest.state_envelope == envelope.to_json()
                ):
                    return latest
                raise ValueError("conflicting Strategy state analytical replay")
            if latest.last_evaluated_bar_end is not None:
                if current_frontier is None:
                    raise ValueError("Strategy analytical frontier cannot be cleared")
                if current_frontier != latest.last_evaluated_bar_end + timedelta(
                    minutes=15
                ):
                    raise ValueError(
                        "Strategy analytical frontier must advance by one M15 bar"
                    )
        next_version = (latest.state_version + 1) if latest else 1
        if state_version is not None and state_version != next_version:
            raise ValueError("Strategy state version must advance exactly once")
        row = StrategyStateModel(
            deployment_id=deployment_id,
            strategy_version_id=strategy_version_id,
            state_version=next_version,
            state_envelope=envelope.to_json(),
            last_evaluated_bar_end=current_frontier,
            analytical_bar_fingerprint=analytical_bar_fingerprint,
        )
        session.add(row)
        session.flush()
        return row

    def latest(
        self, session: Session, deployment_id: UUID
    ) -> StrategyStateModel | None:
        return session.scalar(
            select(StrategyStateModel)
            .where(StrategyStateModel.deployment_id == deployment_id)
            .order_by(StrategyStateModel.state_version.desc())
        )

    def restore(self, session: Session, deployment_id: UUID) -> StrategyStateEnvelope:
        row = self.latest(session, deployment_id)
        if row is None:
            raise ValueError("Deployment Strategy state is missing")
        try:
            return StrategyStateEnvelope.from_json(row.state_envelope)
        except Exception as error:
            raise ValueError(
                "Deployment Strategy state is invalid; exposure is blocked"
            ) from error


class PendingEntryRepository:
    def create(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        trade_intent_id: UUID,
        state_repository: StrategyStateRepository | None = None,
    ) -> PendingEntryHandoffModel:
        from .models import TradeIntentModel

        intent = session.get(TradeIntentModel, trade_intent_id)
        if (
            intent is None
            or intent.deployment_id != deployment_id
            or intent.experiment_id is not None
        ):
            raise ValueError("pending entry intent has the wrong Deployment owner")
        state = (state_repository or StrategyStateRepository()).restore(
            session, deployment_id
        )
        pending = state.pending_entry
        if pending is None or pending.decision_frontier != intent.decision_frontier:
            raise ValueError("pending handoff does not match StrategyStateEnvelope")
        if (
            pending.trigger_price != intent.trigger_price
            or pending.direction.value != intent.direction
            or pending.stop_price is None
            or pending.stop_methodology is None
            or pending.stop_price != intent.proposed_stop
        ):
            raise ValueError("pending handoff methodology disagrees with TradeIntent")
        row = PendingEntryHandoffModel(
            deployment_id=deployment_id, trade_intent_id=trade_intent_id
        )
        session.add(row)
        session.flush()
        return row

    def pending(
        self, session: Session, deployment_id: UUID
    ) -> PendingEntryHandoffModel | None:
        return session.scalar(
            select(PendingEntryHandoffModel)
            .where(
                PendingEntryHandoffModel.deployment_id == deployment_id,
                PendingEntryHandoffModel.status == "PENDING",
            )
        )

    def transition(
        self,
        session: Session,
        handoff_id: UUID,
        status: str,
        *,
        resolved_at: datetime | None = None,
        safety_reason: str | None = None,
    ) -> PendingEntryHandoffModel:
        require_optional_utc(resolved_at, "resolved_at")
        if status not in {"FILLED", "EXPIRED", "REJECTED", "BLOCKED"}:
            raise ValueError("pending handoff transitions must be terminal")
        row = session.scalar(
            select(PendingEntryHandoffModel)
            .where(PendingEntryHandoffModel.id == handoff_id)
            .with_for_update()
        )
        if row is None or row.status != "PENDING":
            raise ValueError("only a pending handoff may transition")
        row.status = status
        row.resolved_at = resolved_at
        row.safety_reason = _detail(safety_reason) if safety_reason else None
        session.flush()
        return row


class SafetyRepository:
    def record_frontier(
        self, session: Session, deployment_id: UUID, **values: object
    ) -> DeploymentFrontierModel:
        completed_frontier = require_optional_utc(
            values.get("completed_m15_frontier"), "completed_m15_frontier"
        ) if "completed_m15_frontier" in values else None
        completed_fingerprint = values.get("completed_m15_fingerprint")
        execution_observation = require_optional_utc(
            values.get("last_execution_observation_at"),
            "last_execution_observation_at",
        ) if "last_execution_observation_at" in values else None
        row = session.scalar(
            select(DeploymentFrontierModel)
            .where(DeploymentFrontierModel.deployment_id == deployment_id)
            .with_for_update()
        )
        if row is None:
            row = DeploymentFrontierModel(
                deployment_id=deployment_id,
                source=str(values.pop("source", "unknown")),
            )
            session.add(row)
        if "completed_m15_frontier" in values:
            if not isinstance(completed_fingerprint, str) or (
                len(completed_fingerprint) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in completed_fingerprint
                )
            ):
                raise ValueError(
                    "completed M15 frontier requires a lowercase SHA-256 fingerprint"
                )
            require_non_decreasing_utc(
                row.completed_m15_frontier,
                completed_frontier,
                "completed-M15 frontier",
            )
            if (
                row.completed_m15_frontier == completed_frontier
                and row.completed_m15_fingerprint is not None
                and row.completed_m15_fingerprint != completed_fingerprint
            ):
                raise ValueError("conflicting completed-M15 frontier replay")
            values["completed_m15_frontier"] = completed_frontier
        if "last_execution_observation_at" in values:
            require_non_decreasing_utc(
                row.last_execution_observation_at,
                execution_observation,
                "execution observation frontier",
            )
            values["last_execution_observation_at"] = execution_observation
        for key, value in values.items():
            if not hasattr(row, key):
                raise ValueError(f"unknown frontier field: {key}")
            setattr(row, key, value)
        session.flush()
        return row

    def record_account_snapshot(
        self, session: Session, **values: object
    ) -> TradingAccountSnapshotModel:
        require_utc(values.get("observed_at"), "observed_at")
        if "created_at" in values:
            require_utc(values["created_at"], "created_at")
        if isinstance(values.get("facts"), Mapping):
            values["facts"] = _safe_mapping(values["facts"])  # type: ignore[index]
        row = TradingAccountSnapshotModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def record_heartbeat(
        self, session: Session, **values: object
    ) -> RuntimeHeartbeatModel:
        require_utc(values.get("observed_at"), "observed_at")
        if isinstance(values.get("details"), Mapping):
            values["details"] = _safe_mapping(values["details"])  # type: ignore[index]
        row = RuntimeHeartbeatModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def record_system_event(
        self, session: Session, *, detail: str, **values: object
    ) -> SystemEventModel:
        if "occurred_at" in values:
            require_utc(values["occurred_at"], "occurred_at")
        if isinstance(values.get("details"), Mapping):
            values["details"] = _safe_mapping(values["details"])  # type: ignore[index]
        row = SystemEventModel(detail=_detail(detail), **values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def record_reconciliation(
        self, session: Session, **values: object
    ) -> ReconciliationRecordModel:
        require_utc(values.get("started_at"), "started_at")
        require_utc(values.get("finished_at"), "finished_at")
        if "created_at" in values:
            require_utc(values["created_at"], "created_at")
        if isinstance(values.get("summary"), Mapping):
            values["summary"] = _safe_mapping(values["summary"])  # type: ignore[index]
        row = ReconciliationRecordModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def advance_cursor(
        self,
        session: Session,
        *,
        trading_account_id: UUID,
        last_transaction_id: str,
        observed_at: datetime,
        source: str,
    ) -> AccountTransactionCursorModel:
        require_utc(observed_at, "observed_at")
        if not last_transaction_id.isascii() or not last_transaction_id.isdecimal():
            raise ValueError("transaction cursor must be numeric")
        row = session.scalar(
            select(AccountTransactionCursorModel)
            .where(
                AccountTransactionCursorModel.trading_account_id
                == trading_account_id
            )
            .with_for_update()
        )
        if row is not None:
            if int(last_transaction_id) < int(row.last_transaction_id):
                raise ValueError("transaction cursor cannot move backwards")
            require_non_decreasing_utc(
                row.observed_at, observed_at, "transaction cursor observation"
            )
        if row is None:
            row = AccountTransactionCursorModel(
                trading_account_id=trading_account_id,
                last_transaction_id=last_transaction_id,
                observed_at=observed_at,
                source=source,
            )
            session.add(row)
        else:
            row.last_transaction_id = last_transaction_id
            row.observed_at = observed_at
            row.source = source
        session.flush()
        return row


__all__ = [
    "DeploymentRepository",
    "PendingEntryRepository",
    "SafetyRepository",
    "stable_client_correlation_id",
    "StrategyStateRepository",
    "TradingAccountRepository",
]
