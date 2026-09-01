"""PostgreSQL-backed runtime lifecycle store."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.broker import AccountIdentity, AccountMode, BrokerTransactionFact
from backend.domain.market_data import Provider
from backend.domain.strategy import (
    Action,
    Direction,
    ParameterSchema,
    StrategyEvaluation,
    StrategyStateEnvelope,
    StrategyVersion,
    TargetMethodology,
    TargetProposal,
    ValidatedParameterPayload,
)
from backend.execution.contract import Order
from backend.execution.fill_application import apply_fill
from backend.integrations.oanda.execution import (
    FillIdentityConflictError,
    OandaExecutionResult,
    ProtectionState,
    immutable_fill_facts_agree,
    order_provider_facts_agree,
    target_from_fill,
)
from backend.integrations.oanda.execution import (
    apply_execution_result as persist_execution_result,
)
from backend.market_data.live import CompletedM15Frontier
from backend.persistence.lifecycle_locks import (
    DeploymentRuntimeLock,
    deployment_advisory_lock_key,
)
from backend.persistence.models import (
    AccountTransactionCursorModel,
    DeploymentFrontierModel,
    DeploymentModel,
    FillModel,
    OandaTransactionReceiptModel,
    OrderEventModel,
    OrderModel,
    PendingEntryHandoffModel,
    PositionModel,
    ReconciliationRecordModel,
    RiskDecisionModel,
    RuntimeOwnershipModel,
    StrategyModel,
    StrategyStateModel,
    StrategyVersionModel,
    TradeIntentModel,
    TradeModel,
    TradingAccountModel,
    TradingAccountSnapshotModel,
)
from backend.persistence.paper_repository import (
    DeploymentRepository,
    PendingEntryRepository,
    SafetyRepository,
    StrategyStateRepository,
    stable_client_correlation_id,
)
from backend.risk import PaperRiskConfig, RiskDecision, RiskPhase
from backend.runtime.coordinator import (
    BrokerRead,
    ReconciliationOutcome,
    ReconciliationResult,
    RuntimeDeployment,
    RuntimeLease,
)
from backend.runtime.production import PendingOrderResolution, PendingPaperEntry


def _deployment(
    row: DeploymentModel, account: TradingAccountModel
) -> RuntimeDeployment:
    return RuntimeDeployment(
        id=row.id,
        account_id=account.external_account_id,
        desired_state=row.desired_state,
        actual_state=row.actual_state,
        execution_provenance=row.execution_provenance,
        trading_account=AccountIdentity(
            account.external_account_id,
            environment=account.environment,
            mode=AccountMode(account.mode),
            base_currency=account.base_currency,
            provider=Provider(account.broker),
        ),
    )


def _repair_required(broker: BrokerRead, reason: str) -> ReconciliationResult:
    return ReconciliationResult(
        ReconciliationOutcome.RECONCILIATION_REQUIRED,
        {"reason": reason},
        broker=broker,
        reason=reason,
        durable_gate_proven=False,
    )


class _DatabaseLease:
    def __init__(self, connection: Connection, lock: DeploymentRuntimeLock) -> None:
        self.connection = connection
        self.lock = lock

    def release(self) -> None:
        try:
            self.lock.release()
        finally:
            self.connection.close()

    def is_held(self) -> bool:
        return self.lock.is_held()


class AccountChangesApplicationError(ValueError):
    """A complete Account Changes fence could not be safely applied."""


class SqlAlchemyRuntimeStore:
    """Small transactional store; broker calls never occur in its transactions."""

    def __init__(self, engine: Engine, session_factory: sessionmaker[Session]) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.deployments = DeploymentRepository()
        self.safety = SafetyRepository()
        self.strategy_states = StrategyStateRepository()

    def eligible_deployments(self) -> Sequence[RuntimeDeployment]:
        with self.session_factory() as session:
            rows = session.execute(
                select(DeploymentModel, TradingAccountModel)
                .join(
                    TradingAccountModel,
                    TradingAccountModel.id == DeploymentModel.trading_account_id,
                )
                .where(DeploymentModel.actual_state != "ARCHIVED")
                .where(
                    DeploymentModel.desired_state.in_(
                        ("RUNNING", "PAUSED", "STOPPED", "ARCHIVED")
                    )
                )
                .order_by(DeploymentModel.created_at, DeploymentModel.id)
            ).all()
            return tuple(_deployment(row, account) for row, account in rows)

    def get_deployment(self, deployment_id: UUID) -> RuntimeDeployment | None:
        with self.session_factory() as session:
            row = session.get(DeploymentModel, deployment_id)
            if row is None:
                return None
            account = session.get(TradingAccountModel, row.trading_account_id)
            return _deployment(row, account) if account is not None else None

    def request_state(
        self, deployment_id: UUID, desired_state: str
    ) -> RuntimeDeployment:
        with self.session_factory() as session, session.begin():
            row = self.deployments.request_state(session, deployment_id, desired_state)
            account = session.get(TradingAccountModel, row.trading_account_id)
            if account is None:
                raise ValueError("Deployment account does not exist")
            return _deployment(row, account)

    def set_actual_state(
        self, deployment_id: UUID, actual_state: str, reason: str | None = None
    ) -> RuntimeDeployment:
        with self.session_factory() as session, session.begin():
            row = self.deployments.set_actual_state(
                session, deployment_id, actual_state, safety_reason=reason
            )
            account = session.get(TradingAccountModel, row.trading_account_id)
            if account is None:
                raise ValueError("Deployment account does not exist")
            return _deployment(row, account)

    def heartbeat(
        self,
        deployment_id: UUID,
        owner_id: str,
        *,
        lock_held: bool,
        db_connected: bool,
        health_status: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as session, session.begin():
            ownership = session.get(RuntimeOwnershipModel, deployment_id)
            if ownership is None:
                ownership = RuntimeOwnershipModel(
                    deployment_id=deployment_id,
                    owner_id=owner_id,
                    lock_key=deployment_advisory_lock_key(deployment_id),
                    acquired_at=now,
                    last_heartbeat_at=now,
                    lock_held=lock_held,
                    db_connected=db_connected,
                    health_status=health_status,
                )
                session.add(ownership)
            else:
                if (
                    ownership.lock_held
                    and ownership.owner_id != owner_id
                ):
                    raise RuntimeError("Deployment heartbeat owner conflict")
                ownership.owner_id = owner_id
                ownership.last_heartbeat_at = now
                ownership.lock_held = lock_held
                ownership.db_connected = db_connected
                ownership.health_status = health_status
                ownership.released_at = None if lock_held else now
            self.safety.record_heartbeat(
                session,
                deployment_id=deployment_id,
                owner_id=owner_id,
                observed_at=now,
                lock_held=lock_held,
                db_connected=db_connected,
                health_status=health_status,
                details=dict(details or {}),
            )

    def record_reconciliation(
        self,
        deployment_id: UUID,
        *,
        trigger: str,
        outcome: ReconciliationOutcome,
        started_at: datetime,
        finished_at: datetime,
        summary: Mapping[str, object],
        broker: BrokerRead | None = None,
    ) -> None:
        with self.session_factory() as session, session.begin():
            self.safety.record_reconciliation(
                session,
                deployment_id=deployment_id,
                trigger=trigger,
                outcome=outcome.value,
                started_at=started_at,
                finished_at=finished_at,
                summary=dict(summary),
            )
            if broker is not None:
                deployment = session.get(DeploymentModel, deployment_id)
                if deployment is None:
                    raise ValueError("Deployment does not exist")
                account = broker.account
                self.safety.record_account_snapshot(
                    session,
                    trading_account_id=deployment.trading_account_id,
                    balance=account.balance,
                    nav=account.nav,
                    equity=account.equity,
                    margin_available=account.margin_available,
                    margin_used=account.margin_used,
                    facts={
                        "external_account_id": account.identity.account_id,
                        "orders_known": account.orders_known,
                        "trades_known": account.trades_known,
                        "positions_known": account.positions_known,
                        "pending_order_count": len(account.pending_orders),
                        "open_trade_count": len(account.open_trades),
                        "open_position_side_count": len(account.position_sides),
                    },
                    observed_at=account.observed_at,
                    freshness="FRESH" if account.fresh else "STALE",
                    source=account.source,
                )

    def acquire_lease(self, deployment_id: UUID) -> RuntimeLease | None:
        connection = self.engine.connect()
        lock = DeploymentRuntimeLock(connection, deployment_id)
        try:
            if not lock.acquire():
                connection.close()
                return None
            return _DatabaseLease(connection, lock)
        except Exception:
            connection.close()
            raise

    def runtime_health(self, deployment_id: UUID) -> Mapping[str, object]:
        """Read the durable restart/safety facts; no process memory is authority."""

        with self.session_factory() as session:
            deployment = session.get(DeploymentModel, deployment_id)
            if deployment is None:
                raise ValueError("Deployment does not exist")
            ownership = session.get(RuntimeOwnershipModel, deployment_id)
            reconciliation = session.scalar(
                select(ReconciliationRecordModel)
                .where(ReconciliationRecordModel.deployment_id == deployment_id)
                .order_by(
                    ReconciliationRecordModel.finished_at.desc(),
                    ReconciliationRecordModel.id.desc(),
                )
            )
            broker = session.scalar(
                select(TradingAccountSnapshotModel)
                .where(
                    TradingAccountSnapshotModel.trading_account_id
                    == deployment.trading_account_id
                )
                .order_by(
                    TradingAccountSnapshotModel.observed_at.desc(),
                    TradingAccountSnapshotModel.id.desc(),
                )
            )
            frontier = session.get(DeploymentFrontierModel, deployment_id)
            state = session.scalar(
                select(StrategyStateModel)
                .where(StrategyStateModel.deployment_id == deployment_id)
                .order_by(StrategyStateModel.state_version.desc())
            )
            return {
                "actual_state": deployment.actual_state,
                "block_reason": deployment.safety_reason,
                "owner_heartbeat_at": (
                    ownership.last_heartbeat_at if ownership is not None else None
                ),
                "reconciled_at": (
                    reconciliation.finished_at if reconciliation is not None else None
                ),
                "broker_observed_at": (
                    broker.observed_at if broker is not None else None
                ),
                "analytical_frontier": (
                    frontier.completed_m15_frontier if frontier is not None else None
                ),
                "strategy_state_frontier": (
                    state.last_evaluated_bar_end if state is not None else None
                ),
            }

    def reconciliation_facts(self, deployment_id: UUID) -> Mapping[str, object]:
        """Read local projections for broker-authoritative comparison only."""

        with self.session_factory() as session:
            orders = tuple(
                {
                    "id": str(row.id),
                    "external_order_id": row.external_order_id,
                    "status": row.current_status,
                    "quantity": str(row.quantity),
                }
                for row in session.scalars(
                    select(OrderModel)
                    .where(OrderModel.deployment_id == deployment_id)
                    .order_by(OrderModel.created_at, OrderModel.id)
                )
            )
            order_ids = tuple(row.id for row in session.scalars(
                select(OrderModel).where(OrderModel.deployment_id == deployment_id)
            ))
            fills = tuple(
                {
                    "external_execution_id": row.external_execution_id,
                    "external_transaction_id": row.external_transaction_id,
                    "order_id": str(row.order_id),
                }
                for row in session.scalars(
                    select(FillModel).where(FillModel.order_id.in_(order_ids))
                )
            ) if order_ids else ()
            position = session.scalar(
                select(PositionModel).where(
                    PositionModel.deployment_id == deployment_id
                )
            )
            trades = tuple(
                {
                    "id": str(row.id),
                    "direction": row.direction,
                    "quantity": str(row.quantity),
                    "status": row.status,
                }
                for row in session.scalars(
                    select(TradeModel).where(TradeModel.deployment_id == deployment_id)
                )
            )
            deployment = session.get(DeploymentModel, deployment_id)
            cursor = (
                session.get(
                    AccountTransactionCursorModel,
                    deployment.trading_account_id,
                )
                if deployment is not None
                else None
            )
            return {
                "orders": orders,
                "fills": fills,
                "trades": trades,
                "transaction_cursor": cursor.last_transaction_id
                if cursor is not None
                else None,
                "position": (
                    {
                        "state": position.state,
                        "quantity": str(position.quantity)
                        if position.quantity is not None
                        else None,
                        "entry_price": str(position.entry_price)
                        if position.entry_price is not None
                        else None,
                    }
                    if position is not None
                    else {"state": "FLAT"}
                ),
            }

    def transaction_cursor(self, deployment: RuntimeDeployment) -> str | None:
        """Return the durable account cursor used for the next GET page."""

        with self.session_factory() as session:
            row = session.get(DeploymentModel, deployment.id)
            if row is None:
                raise ValueError("Deployment does not exist")
            cursor = session.get(AccountTransactionCursorModel, row.trading_account_id)
            return cursor.last_transaction_id if cursor is not None else None

    def strategy_runtime_inputs(
        self, deployment_id: UUID
    ) -> tuple[StrategyVersion, ValidatedParameterPayload, StrategyStateEnvelope]:
        """Restore immutable Strategy identity, parameters, and state together."""

        with self.session_factory() as session:
            deployment = session.get(DeploymentModel, deployment_id)
            if deployment is None:
                raise ValueError("Deployment does not exist")
            row = session.get(StrategyVersionModel, deployment.strategy_version_id)
            if row is None:
                raise ValueError("Deployment StrategyVersion is missing")
            strategy = session.get(StrategyModel, row.strategy_id)
            if strategy is None:
                raise ValueError("Deployment Strategy is missing")
            schema = tuple(
                ParameterSchema.from_json(item) for item in row.parameter_schema
            )
            parameters = ValidatedParameterPayload.with_defaults(
                schema, deployment.parameter_snapshot
            )
            version = StrategyVersion(
                row.id,
                strategy.strategy_key,
                row.version_number,
                row.source_fingerprint,
                row.implementation_key,
                schema,
                required_historical_context_bars=row.required_historical_context_bars,
                state_schema_version=row.state_schema_version,
                created_at=row.created_at,
            )
            state_row = self.strategy_states.latest(session, deployment_id)
            if state_row is None:
                raise ValueError("Deployment Strategy state is missing")
            if state_row.strategy_version_id != deployment.strategy_version_id:
                raise ValueError(
                    "Strategy state does not match Deployment StrategyVersion"
                )
            raw_schema = state_row.state_envelope.get("state_schema_version")
            if raw_schema != row.state_schema_version:
                raise ValueError("Strategy state schema does not match StrategyVersion")
            try:
                state = StrategyStateEnvelope.from_json(state_row.state_envelope)
            except Exception as error:
                raise ValueError(
                    "Deployment Strategy state is invalid; exposure is blocked"
                ) from error
            if (
                state.state_schema_version != row.state_schema_version
                or state.last_evaluated_bar_end != state_row.last_evaluated_bar_end
            ):
                raise ValueError("Strategy state persistence linkage is invalid")
            self._completed_m15_frontier(session, deployment_id, state)
            return version, parameters, state

    def completed_m15_frontier(
        self, deployment_id: UUID
    ) -> CompletedM15Frontier:
        with self.session_factory() as session:
            deployment = session.get(DeploymentModel, deployment_id)
            if deployment is None:
                raise ValueError("Deployment does not exist")
            version = session.get(
                StrategyVersionModel, deployment.strategy_version_id
            )
            state_row = self.strategy_states.latest(session, deployment_id)
            if version is None or state_row is None:
                raise ValueError("Deployment Strategy state linkage is missing")
            if state_row.strategy_version_id != deployment.strategy_version_id:
                raise ValueError(
                    "Strategy state does not match Deployment StrategyVersion"
                )
            state = StrategyStateEnvelope.from_json(state_row.state_envelope)
            if (
                state.state_schema_version != version.state_schema_version
                or state.last_evaluated_bar_end != state_row.last_evaluated_bar_end
            ):
                raise ValueError("Strategy state persistence linkage is invalid")
            return self._completed_m15_frontier(session, deployment_id, state)

    def validate_strategy_continuity(
        self, deployment_id: UUID, state: StrategyStateEnvelope
    ) -> None:
        """Prove envelope-owned pending methodology agrees with lifecycle linkage."""

        with self.session_factory() as session:
            deployment = session.get(DeploymentModel, deployment_id)
            if deployment is None:
                raise ValueError("Deployment does not exist")
            version = session.get(
                StrategyVersionModel, deployment.strategy_version_id
            )
            if (
                version is None
                or state.state_schema_version != version.state_schema_version
            ):
                raise ValueError("Strategy state schema does not match StrategyVersion")
            active = session.scalar(
                select(PendingEntryHandoffModel).where(
                    PendingEntryHandoffModel.deployment_id == deployment_id,
                    PendingEntryHandoffModel.status == "PENDING",
                )
            )
            methodology = state.pending_entry
            if methodology is None:
                if active is not None:
                    raise ValueError(
                        "pending PAPER lifecycle linkage disagrees with Strategy state"
                    )
                return
            if methodology.stop_price is None or methodology.stop_methodology is None:
                raise ValueError("pending Strategy stop methodology is incomplete")
            if active is None:
                raise ValueError(
                    "pending Strategy methodology has no lifecycle linkage"
                )
            intent = session.get(TradeIntentModel, active.trade_intent_id)
            if (
                intent is None
                or intent.deployment_id != deployment_id
                or intent.strategy_version_id != deployment.strategy_version_id
                or methodology.decision_frontier != intent.decision_frontier
                or methodology.direction.value != intent.direction
                or methodology.trigger_price != intent.trigger_price
                or methodology.trigger_price_basis.value != intent.trigger_price_basis
                or methodology.eligibility_limit != intent.expiry_bars
                or methodology.stop_price != intent.proposed_stop
            ):
                raise ValueError(
                    "pending PAPER lifecycle linkage disagrees with Strategy state"
                )

    @staticmethod
    def _completed_m15_frontier(
        session: Session,
        deployment_id: UUID,
        state: StrategyStateEnvelope,
    ) -> CompletedM15Frontier:
        row = session.get(DeploymentFrontierModel, deployment_id)
        state_frontier = state.last_evaluated_bar_end
        if row is None:
            if state_frontier is not None:
                raise ValueError("Strategy state has no durable analytical frontier")
            return CompletedM15Frontier()
        if row.completed_m15_frontier != state_frontier:
            raise ValueError("Strategy state and durable analytical frontier disagree")
        return CompletedM15Frontier(
            row.completed_m15_frontier, row.completed_m15_fingerprint
        )

    def _persist_analytical_state(
        self,
        session: Session,
        *,
        deployment_id: UUID,
        strategy_version_id: UUID,
        state: StrategyStateEnvelope,
        analytical_bar_fingerprint: str,
    ) -> None:
        if state.last_evaluated_bar_end is None:
            raise ValueError("evaluated Strategy state has no analytical frontier")
        self.strategy_states.append(
            session,
            deployment_id=deployment_id,
            strategy_version_id=strategy_version_id,
            envelope=state,
            analytical_bar_fingerprint=analytical_bar_fingerprint,
        )
        active_handoff = session.scalar(
            select(PendingEntryHandoffModel)
            .where(
                PendingEntryHandoffModel.deployment_id == deployment_id,
                PendingEntryHandoffModel.status == "PENDING",
            )
            .with_for_update()
        )
        if state.pending_entry is None and active_handoff is not None:
            active_handoff.status = "EXPIRED"
            active_handoff.resolved_at = state.last_evaluated_bar_end
        self.safety.record_frontier(
            session,
            deployment_id,
            completed_m15_frontier=state.last_evaluated_bar_end,
            completed_m15_fingerprint=analytical_bar_fingerprint,
            data_status="HEALTHY",
            source="OANDA",
        )

    def persist_strategy_state(
        self,
        deployment_id: UUID,
        strategy_version_id: UUID,
        state: StrategyStateEnvelope,
        analytical_bar_fingerprint: str,
    ) -> None:
        with self.session_factory() as session, session.begin():
            self._persist_analytical_state(
                session,
                deployment_id=deployment_id,
                strategy_version_id=strategy_version_id,
                state=state,
                analytical_bar_fingerprint=analytical_bar_fingerprint,
            )

    def persist_strategy_evaluation(
        self,
        deployment_id: UUID,
        strategy_version_id: UUID,
        state: StrategyStateEnvelope,
        evaluation: StrategyEvaluation,
        analytical_bar_fingerprint: str,
    ) -> None:
        """Commit state, TradeIntent, and the lifecycle-only handoff together."""

        from backend.persistence.trading_repository import TradingRepository

        decision = evaluation.decision
        with self.session_factory() as session, session.begin():
            self._persist_analytical_state(
                session,
                deployment_id=deployment_id,
                strategy_version_id=strategy_version_id,
                state=state,
                analytical_bar_fingerprint=analytical_bar_fingerprint,
            )
            if decision.action not in {Action.OPEN_LONG, Action.OPEN_SHORT}:
                return
            if (
                decision.decision_time is None
                or decision.direction is None
                or decision.stop is None
                or decision.target is None
                or state.pending_entry is None
            ):
                raise ValueError("opening Strategy evaluation has no valid handoff")
            if (
                state.pending_entry.stop_price != decision.stop.price
                or state.pending_entry.stop_methodology is None
            ):
                raise ValueError("opening Strategy stop methodology is not durable")
            repository = TradingRepository()
            existing = session.scalar(
                select(TradeIntentModel).where(
                    TradeIntentModel.deployment_id == deployment_id,
                    TradeIntentModel.decision_frontier == decision.decision_time,
                )
            )
            if existing is not None:
                if (
                    existing.action != decision.action.value
                    or existing.direction != decision.direction.value
                ):
                    raise ValueError(
                        "duplicate PAPER TradeIntent disagrees with Strategy"
                    )
                return
            deployment = session.get(DeploymentModel, deployment_id)
            if deployment is None:
                raise ValueError("Deployment does not exist")
            rationale: dict[str, object] = {"strategy": decision.rationale.to_json()}
            if decision.setup_facts is not None:
                rationale["setup_facts"] = decision.setup_facts.to_json()
            if decision.evidence is not None:
                rationale["evidence"] = decision.evidence.to_json()
            intent = repository.create_intent(
                session,
                deployment_id=deployment_id,
                strategy_version_id=strategy_version_id,
                venue_instrument_id=deployment.venue_instrument_id,
                decision_frontier=decision.decision_time,
                action=decision.action.value,
                direction=decision.direction.value,
                proposed_stop=decision.stop.price,
                target_multiple=decision.target.multiple,
                target_methodology=decision.target.methodology.value,
                rationale=rationale,
                entry_policy=decision.entry_policy.value,
                trigger_price=decision.trigger_price,
                trigger_price_basis=(
                    decision.trigger_price_basis.value
                    if decision.trigger_price_basis is not None
                    else None
                ),
                expiry_time=decision.expiry_time,
                expiry_bars=decision.expiry_bars,
                diagnostics={"source": "PAPER_STRATEGY_EVALUATION"},
            )
            PendingEntryRepository().create(
                session,
                deployment_id=deployment_id,
                trade_intent_id=intent.id,
                state_repository=self.strategy_states,
            )

    def pending_paper_entry(self, deployment_id: UUID) -> PendingPaperEntry | None:
        """Restore the lifecycle handoff as the Risk-owned TradeIntent noun."""

        from backend.risk import TradeIntent

        with self.session_factory() as session:
            handoff = session.scalar(
                select(PendingEntryHandoffModel)
                .where(
                    PendingEntryHandoffModel.deployment_id == deployment_id,
                    PendingEntryHandoffModel.status == "PENDING",
                )
            )
            if handoff is None:
                return None
            row = session.get(TradeIntentModel, handoff.trade_intent_id)
            if row is None or row.deployment_id != deployment_id:
                raise ValueError("pending PAPER TradeIntent is missing")
            if (
                row.direction is None
                or row.proposed_stop is None
                or row.target_multiple is None
            ):
                raise ValueError("pending PAPER TradeIntent is incomplete")
            state = self.strategy_states.restore(session, deployment_id)
            methodology = state.pending_entry
            if (
                methodology is None
                or methodology.decision_frontier != row.decision_frontier
                or methodology.direction.value != row.direction
                or methodology.trigger_price != row.trigger_price
                or methodology.trigger_price_basis.value != row.trigger_price_basis
                or methodology.eligibility_limit != row.expiry_bars
                or methodology.stop_price != row.proposed_stop
                or methodology.stop_methodology is None
            ):
                raise ValueError(
                    "pending PAPER lifecycle linkage disagrees with Strategy state"
                )
            target = TargetProposal(
                TargetMethodology(row.target_methodology or "R_MULTIPLE"),
                row.target_multiple,
            )
            return PendingPaperEntry(
                row.id,
                TradeIntent(
                    Action(row.action),
                    Direction(row.direction),
                    row.proposed_stop,
                    target,
                ),
                row.strategy_version_id,
            )

    def paper_risk_config(self, deployment_id: UUID) -> PaperRiskConfig:
        with self.session_factory() as session:
            row = session.get(DeploymentModel, deployment_id)
            if row is None:
                raise ValueError("Deployment does not exist")
            raw = row.risk_snapshot
            value = raw.get("risk_per_trade")
            if value is None:
                raise ValueError("Deployment Risk snapshot has no risk_per_trade")
            return PaperRiskConfig(
                Decimal(str(value)),
                max_quote_age=timedelta(
                    seconds=int(raw.get("max_quote_age_seconds", 60))
                ),
            )

    def persist_risk_decision(
        self, intent_id: UUID, decision: RiskDecision, evaluated_at: datetime
    ) -> UUID:
        from backend.persistence.trading_repository import TradingRepository

        with self.session_factory() as session, session.begin():
            row = TradingRepository().create_paper_risk_decision(
                session,
                trade_intent_id=intent_id,
                decision=decision,
                evaluated_at=evaluated_at,
            )
            return row.id

    def entry_order_resolution(
        self, deployment_id: UUID, intent_id: UUID
    ) -> PendingOrderResolution | None:
        """Return an existing ENTRY Order without making it retryable."""

        with self.session_factory() as session:
            row = session.scalar(
                select(OrderModel).where(
                    OrderModel.deployment_id == deployment_id,
                    OrderModel.trade_intent_id == intent_id,
                    OrderModel.purpose == "ENTRY",
                )
            )
            if row is None:
                return None
            return self._pending_order_resolution(session, row, created=False)

    def create_pending_order(
        self,
        deployment: RuntimeDeployment,
        pending: PendingPaperEntry,
        decision: RiskDecision,
        persisted_decision_id: UUID,
    ) -> PendingOrderResolution:
        from backend.persistence.trading_repository import TradingRepository

        with self.session_factory() as session, session.begin():
            deployment_row = session.scalar(
                select(DeploymentModel)
                .where(DeploymentModel.id == deployment.id)
                .with_for_update()
            )
            if deployment_row is None:
                raise ValueError("PAPER Order Deployment does not exist")
            account = session.get(
                TradingAccountModel, deployment_row.trading_account_id
            )
            if account is None:
                raise ValueError("PAPER Order TradingAccount does not exist")
            persisted_deployment = _deployment(deployment_row, account)
            if (
                persisted_deployment.trading_account != deployment.trading_account
                or persisted_deployment.account_id != deployment.account_id
                or deployment_row.actual_state != "RUNNING"
            ):
                raise ValueError("PAPER Order Deployment account binding is invalid")

            intent = session.scalar(
                select(TradeIntentModel)
                .where(TradeIntentModel.id == pending.intent_id)
                .with_for_update()
            )
            if (
                intent is None
                or intent.deployment_id != deployment.id
                or intent.experiment_id is not None
            ):
                raise ValueError("PAPER Order intent ownership is invalid")
            handoff = session.scalar(
                select(PendingEntryHandoffModel)
                .where(
                    PendingEntryHandoffModel.deployment_id == deployment.id,
                    PendingEntryHandoffModel.trade_intent_id == pending.intent_id,
                    PendingEntryHandoffModel.status == "PENDING",
                )
                .with_for_update()
            )
            if handoff is None or intent.proposal_status != "PENDING":
                raise ValueError("PAPER Order handoff is no longer pending")
            self._validate_pending_methodology(session, deployment_row, intent, pending)

            existing = session.scalar(
                select(OrderModel)
                .where(
                    OrderModel.deployment_id == deployment.id,
                    OrderModel.trade_intent_id == pending.intent_id,
                    OrderModel.purpose == "ENTRY",
                )
                .with_for_update()
            )
            if existing is not None:
                return self._pending_order_resolution(session, existing, created=False)

            risk = session.scalar(
                select(RiskDecisionModel)
                .where(RiskDecisionModel.id == persisted_decision_id)
                .with_for_update()
            )
            if not self._persisted_authorization_matches(
                risk, pending.intent_id, decision
            ):
                raise ValueError("persisted PRE_SUBMISSION authorization mismatch")
            assert risk is not None
            superseding = session.scalar(
                select(RiskDecisionModel.id)
                .where(
                    RiskDecisionModel.trade_intent_id == pending.intent_id,
                    RiskDecisionModel.evaluated_at > risk.evaluated_at,
                )
                .limit(1)
            )
            if superseding is not None:
                raise ValueError(
                    "persisted PRE_SUBMISSION authorization was superseded"
                )
            assert risk.quantity is not None
            assert risk.price_bound is not None
            assert intent.direction is not None
            order_id = uuid4()
            row = TradingRepository().create_order(
                session,
                deployment_id=deployment.id,
                trade_intent_id=pending.intent_id,
                risk_decision_id=risk.id,
                order_type="MARKET",
                purpose="ENTRY",
                direction=intent.direction,
                quantity=risk.quantity,
                order_id=order_id,
                client_correlation_id=stable_client_correlation_id(order_id),
                time_in_force="FOK",
                price_bound=risk.price_bound,
                request_provenance={
                    "source": "PAPER_RUNTIME",
                    "status": "PENDING_SUBMISSION",
                },
            )
            return self._pending_order_resolution(session, row, created=True)

    def _pending_order_resolution(
        self, session: Session, row: OrderModel, *, created: bool
    ) -> PendingOrderResolution:
        risk = session.get(RiskDecisionModel, row.risk_decision_id)
        if risk is None or risk.stop_price is None:
            raise ValueError("PAPER ENTRY Order has no persisted stop authorization")
        return PendingOrderResolution(
            Order(
                row.id,
                row.order_type,
                row.purpose,
                row.direction,
                row.quantity,
                client_correlation_id=row.client_correlation_id,
                time_in_force=row.time_in_force,
                price_bound=row.price_bound,
                stop_loss_price=risk.stop_price,
            ),
            created,
            row.current_status,
        )

    def _validate_pending_methodology(
        self,
        session: Session,
        deployment: DeploymentModel,
        intent: TradeIntentModel,
        pending: PendingPaperEntry,
    ) -> None:
        version = session.get(StrategyVersionModel, deployment.strategy_version_id)
        state_row = self.strategy_states.latest(session, deployment.id)
        if version is None or state_row is None:
            raise ValueError("Strategy state linkage is missing")
        if state_row.strategy_version_id != deployment.strategy_version_id:
            raise ValueError("Strategy state does not match Deployment StrategyVersion")
        state = StrategyStateEnvelope.from_json(state_row.state_envelope)
        if state.state_schema_version != version.state_schema_version:
            raise ValueError("Strategy state schema does not match StrategyVersion")
        methodology = state.pending_entry
        if methodology is None:
            raise ValueError("Strategy state has no pending entry methodology")
        if (
            pending.strategy_version_id != deployment.strategy_version_id
            or intent.strategy_version_id != deployment.strategy_version_id
            or pending.intent_id != intent.id
            or methodology.decision_frontier != intent.decision_frontier
            or methodology.direction.value != intent.direction
            or methodology.trigger_price != intent.trigger_price
            or methodology.trigger_price_basis.value != intent.trigger_price_basis
            or methodology.eligibility_limit != intent.expiry_bars
            or methodology.stop_price != intent.proposed_stop
            or methodology.stop_methodology is None
            or pending.intent.action.value != intent.action
            or pending.intent.direction is None
            or pending.intent.direction.value != intent.direction
            or pending.intent.stop != intent.proposed_stop
            or pending.intent.target is None
            or pending.intent.target.methodology.value != intent.target_methodology
            or pending.intent.target.multiple != intent.target_multiple
        ):
            raise ValueError("PAPER handoff disagrees with Strategy methodology")

    @staticmethod
    def _persisted_authorization_matches(
        risk: RiskDecisionModel | None,
        intent_id: UUID,
        decision: RiskDecision,
    ) -> bool:
        if (
            risk is None
            or decision.phase is not RiskPhase.PRE_SUBMISSION
            or not decision.approved
            or decision.rejection is not None
            or risk.trade_intent_id != intent_id
            or risk.phase != "PRE_SUBMISSION"
            or risk.outcome != "APPROVED"
            or risk.rejection_code is not None
            or risk.target_price is not None
        ):
            return False
        return (
            risk.quantity == decision.quantity
            and risk.entry_price == decision.entry_price
            and risk.stop_price == decision.stop_price
            and risk.target_price == decision.target_price
            and risk.risk_budget == decision.risk_budget
            and risk.quote_bid == decision.quote_bid
            and risk.quote_ask == decision.quote_ask
            and risk.actual_risk == decision.actual_risk
            and risk.target_methodology == decision.target_methodology
            and risk.target_multiple == decision.target_multiple
            and risk.quote_observed_at == decision.quote_observed_at
            and risk.price_bound == decision.price_bound
            and risk.evidence == dict(decision.evidence)
        )

    def apply_execution_result(
        self, deployment_id: UUID, result: OandaExecutionResult
    ) -> None:
        try:
            with self.session_factory() as session, session.begin():
                order = session.scalar(
                    select(OrderModel)
                    .where(
                        OrderModel.id == result.order_id,
                        OrderModel.deployment_id == deployment_id,
                    )
                    .with_for_update()
                )
                if order is None:
                    raise ValueError(
                        "execution result Order is not owned by Deployment"
                    )
                fill = persist_execution_result(session, order, result)
                if fill is not None:
                    intent = session.get(TradeIntentModel, order.trade_intent_id)
                    if intent is not None:
                        intent.proposal_status = "FILLED"
                    handoff = session.scalar(
                        select(PendingEntryHandoffModel)
                        .where(
                            PendingEntryHandoffModel.trade_intent_id
                            == order.trade_intent_id
                        )
                        .with_for_update()
                    )
                    if handoff is not None and handoff.status == "PENDING":
                        handoff.status = "FILLED"
                        handoff.resolved_at = fill.executed_at
                    self.deployments.mark_first_trade(
                        session, deployment_id, fill.executed_at
                    )
        except FillIdentityConflictError:
            # The application transaction is deliberately rolled back.  Record
            # the safety fact in a separate transaction so the collision remains
            # inspectable and the Deployment is durably blocked.
            self._record_fill_identity_conflict(
                deployment_id, result, "Conflicting external Fill identity"
            )
            raise
        except IntegrityError as error:
            # A uniqueness race can only be resolved from a new Session after
            # the failed transaction has been discarded.  Never retry the
            # insert on the broken session.
            if result.status != "FULL_FILLED" or result.fill is None:
                raise
            if self._resolve_fill_identity_race(deployment_id, result):
                return
            raise FillIdentityConflictError(
                "provider Fill identity race could not be resolved safely"
            ) from error

    def _record_fill_identity_conflict(
        self, deployment_id: UUID, result: OandaExecutionResult, reason: str
    ) -> None:
        fill = result.fill
        with self.session_factory() as session, session.begin():
            self.deployments.set_actual_state(
                session,
                deployment_id,
                "RECONCILIATION_REQUIRED",
                safety_reason="Conflicting external Fill identity",
            )
            self.safety.record_system_event(
                session,
                deployment_id=deployment_id,
                severity="CRITICAL",
                code="FILL_IDENTITY_CONFLICT",
                detail=(
                    "External Fill identity conflicts with canonical facts; "
                    "new exposure is blocked"
                ),
                details={
                    "order_id": str(result.order_id),
                    "external_execution_id": (
                        fill.external_execution_id if fill is not None else None
                    ),
                    "external_transaction_id": (
                        fill.external_transaction_id if fill is not None else None
                    ),
                    "reason": reason[:500],
                },
            )

    def _resolve_fill_identity_race(
        self, deployment_id: UUID, result: OandaExecutionResult
    ) -> bool:
        """Resolve a committed uniqueness winner, or durably block the collision."""

        fill = result.fill
        if (
            fill is None
            or fill.external_execution_id is None
            or fill.external_transaction_id is None
        ):
            self._record_fill_identity_conflict(
                deployment_id, result, "Required provider identity is missing"
            )
            return False
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(FillModel).where(
                        or_(
                            FillModel.external_execution_id
                            == fill.external_execution_id,
                            FillModel.external_transaction_id
                            == fill.external_transaction_id,
                        )
                    ).with_for_update()
                ).all()
            )
            order = session.get(OrderModel, result.order_id)
            if (
                len(rows) == 1
                and order is not None
                and order.deployment_id == deployment_id
                and immutable_fill_facts_agree(rows[0], fill)
                and order_provider_facts_agree(order, result)
            ):
                return True
        self._record_fill_identity_conflict(
            deployment_id,
            result,
            "Unique provider identity owner was not an exact replay",
        )
        return False

    def mark_entry_rejected(self, intent_id: UUID, reason: str) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as session, session.begin():
            intent = session.scalar(
                select(TradeIntentModel)
                .where(TradeIntentModel.id == intent_id)
                .with_for_update()
            )
            if intent is None:
                raise ValueError("TradeIntent does not exist")
            intent.proposal_status = "REJECTED"
            handoff = session.scalar(
                select(PendingEntryHandoffModel)
                .where(PendingEntryHandoffModel.trade_intent_id == intent_id)
                .with_for_update()
            )
            if handoff is not None and handoff.status == "PENDING":
                handoff.status = "REJECTED"
                handoff.safety_reason = reason[:500]
                handoff.resolved_at = now

    def record_protection(
        self, deployment_id: UUID, order_id: UUID, state: ProtectionState
    ) -> None:
        with self.session_factory() as session, session.begin():
            entry = session.scalar(
                select(OrderModel)
                .where(
                    OrderModel.id == order_id,
                    OrderModel.deployment_id == deployment_id,
                )
                .with_for_update()
            )
            if entry is None:
                raise ValueError("protection Entry Order is missing")
            trade = session.scalar(
                select(TradeModel)
                .where(TradeModel.entry_order_id == order_id)
                .with_for_update()
            )
            if trade is None or trade.quantity <= 0:
                raise ValueError("protection Trade is missing")
            fill = session.scalar(
                select(FillModel)
                .where(FillModel.order_id == order_id)
                .with_for_update()
            )
            risk = session.get(RiskDecisionModel, entry.risk_decision_id)
            if (
                fill is None
                or risk is None
                or risk.stop_price is None
                or risk.target_multiple is None
                or fill.external_trade_id is None
                or fill.quantity != trade.quantity
                or trade.direction != entry.direction
            ):
                raise ValueError("protection financial lineage is incomplete")
            expected_target = target_from_fill(
                fill.execution_price,
                risk.stop_price,
                entry.direction,
                risk.target_multiple,
            )
            from backend.integrations.oanda.execution import validate_protection_state

            validate_protection_state(
                state,
                trade_id=fill.external_trade_id,
                direction=entry.direction,
                quantity=fill.quantity,
                stop_price=risk.stop_price,
                target_price=expected_target,
            )
            protection_orders = (
                ("STOP", "STOP_LOSS", state.stop_order_id, state.stop_price, "stop"),
                (
                    "LIMIT",
                    "TAKE_PROFIT",
                    state.target_order_id,
                    state.target_price,
                    "target",
                ),
            )
            for order_type, purpose, external_id, price, suffix in protection_orders:
                existing = session.scalar(
                    select(OrderModel)
                    .where(
                        OrderModel.parent_entry_order_id == order_id,
                        OrderModel.purpose == purpose,
                    )
                )
                if existing is not None:
                    if (
                        existing.external_order_id != external_id
                        or existing.requested_price != price
                    ):
                        raise ValueError(f"{suffix} protection identity drifted")
                    continue
                protection = OrderModel(
                    experiment_id=None,
                    deployment_id=deployment_id,
                    trade_intent_id=entry.trade_intent_id,
                    risk_decision_id=entry.risk_decision_id,
                    order_type=order_type,
                    purpose=purpose,
                    direction=entry.direction,
                    quantity=trade.quantity,
                    requested_price=price,
                    current_status="SUBMITTED",
                    client_correlation_id=f"{entry.client_correlation_id}-{suffix}",
                    time_in_force="GTC",
                    external_order_id=external_id,
                    parent_entry_order_id=order_id,
                    request_provenance={"source": "OANDA_PROTECTION_CONFIRMATION"},
                )
                session.add(protection)
                session.flush()
                session.add(
                    OrderEventModel(
                        order_id=protection.id,
                        sequence_number=1,
                        event_type="PROTECTION_CONFIRMED",
                        occurred_at=datetime.now(UTC),
                        details={
                            "trade_id": state.trade_id,
                            "stop_order_id": state.stop_order_id,
                            "target_order_id": state.target_order_id,
                            "target_price": str(state.target_price),
                        },
                    )
                )

    def record_protection_failure(self, deployment_id: UUID, reason: str) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as session, session.begin():
            deployment = self.deployments.set_actual_state(
                session, deployment_id, "RECONCILIATION_REQUIRED", safety_reason=reason
            )
            self.safety.record_system_event(
                session,
                deployment_id=deployment.id,
                severity="CRITICAL",
                code="PROTECTION_FAILED",
                detail="Broker-hosted protection is missing or ambiguous",
                details={"reason": reason, "observed_at": now.isoformat()},
            )

    def _legacy_repair_reconciliation(
        self, deployment: RuntimeDeployment, broker: BrokerRead
    ) -> ReconciliationResult | None:
        """Apply only complete, attributable broker evidence in one transaction.

        This is deliberately not a general broker-repair engine.  PAPER 01 can
        repair one clear, currently protected full entry Fill, deduplicate an
        already-applied Fill, and advance a contiguous account cursor. Every
        unsafe or incomplete shape returns ``RECONCILIATION_REQUIRED`` so the
        caller leaves the Deployment blocked.
        """

        if not broker.transactions_known:
            return _repair_required(broker, "TRANSACTION_HISTORY_UNAVAILABLE")
        account = broker.account
        broker_cursor = account.last_transaction_id
        if broker_cursor is None:
            return _repair_required(broker, "BROKER_TRANSACTION_CURSOR_UNAVAILABLE")
        if not broker_cursor.isdecimal():
            return _repair_required(broker, "BROKER_TRANSACTION_CURSOR_INVALID")
        if (
            account.identity.account_id != deployment.account_id
            or not account.fresh
            or not account.account_state_known
        ):
            return _repair_required(broker, "ACCOUNT_SNAPSHOT_UNSAFE")
        observed_at = account.observed_at
        now = datetime.now(UTC)
        if (
            observed_at > now
            or now - observed_at > timedelta(minutes=2)
        ):
            return _repair_required(broker, "ACCOUNT_SNAPSHOT_STALE")

        # OANDA transaction identities are numeric account cursors.  A page
        # with a duplicate, malformed, future, or incomplete identity cannot be
        # used to advance the durable cursor.
        seen_transaction_ids: set[str] = set()
        for transaction in broker.transactions:
            if transaction.external_id in seen_transaction_ids:
                return _repair_required(broker, "DUPLICATE_TRANSACTION_IDENTITY")
            seen_transaction_ids.add(transaction.external_id)
            if not transaction.external_id.isdecimal():
                return _repair_required(broker, "TRANSACTION_ID_INVALID")
            if int(transaction.external_id) > int(broker_cursor):
                return _repair_required(broker, "TRANSACTION_AFTER_BROKER_CURSOR")
            if transaction.occurred_at is None or transaction.occurred_at > observed_at:
                return _repair_required(broker, "TRANSACTION_EVIDENCE_NOT_CURRENT")

        with self.session_factory() as session, session.begin():
            deployment_row = session.get(DeploymentModel, deployment.id)
            if deployment_row is None:
                return _repair_required(broker, "DEPLOYMENT_UNAVAILABLE")
            cursor = session.scalar(
                select(AccountTransactionCursorModel)
                .where(
                    AccountTransactionCursorModel.trading_account_id
                    == deployment_row.trading_account_id
                )
                .with_for_update()
            )
            local_cursor = cursor.last_transaction_id if cursor is not None else None
            if local_cursor is not None and not local_cursor.isdecimal():
                return _repair_required(broker, "LOCAL_TRANSACTION_CURSOR_INVALID")
            if (
                local_cursor is not None
                and int(broker_cursor) < int(local_cursor)
            ):
                return _repair_required(broker, "TRANSACTION_CURSOR_MOVED_BACKWARD")
            if (
                local_cursor is not None
                and int(broker_cursor) > int(local_cursor)
            ):
                expected = set(range(int(local_cursor) + 1, int(broker_cursor) + 1))
                supplied = {
                    int(transaction.external_id)
                    for transaction in broker.transactions
                    if transaction.external_id.isdecimal()
                }
                if expected != supplied:
                    return _repair_required(broker, "TRANSACTION_CURSOR_GAP")

            orders = tuple(
                session.scalars(
                    select(OrderModel)
                    .where(OrderModel.deployment_id == deployment.id)
                    .with_for_update()
                ).all()
            )
            # Identity keys are account/provider scoped for PAPER 01, so a
            # collision owned by another Deployment must be detected before the
            # local repair attempts an insert.
            existing_fills = tuple(session.scalars(select(FillModel)).all())
            by_external = {
                value: fill
                for fill in existing_fills
                for value in (fill.external_execution_id, fill.external_transaction_id)
                if value is not None
            }

            def existing_matches_transaction(
                existing: FillModel,
                order: OrderModel,
                transaction: BrokerTransactionFact,
            ) -> bool:
                return (
                    existing.order_id == order.id
                    and existing.sequence_number == 1
                    and existing.quantity == abs(transaction.units or Decimal("0"))
                    and existing.execution_price == transaction.price
                    and existing.executed_at == transaction.occurred_at
                    and existing.external_execution_id == transaction.external_id
                    and existing.external_transaction_id == transaction.external_id
                    and existing.external_trade_id == transaction.external_trade_id
                    and tuple(existing.related_transaction_ids)
                    == (transaction.external_id,)
                    and existing.fee == Decimal("0")
                    and existing.source_market_bar_id is None
                    and existing.price_basis == "OPEN"
                    and existing.executable_reference_price is None
                    and existing.slippage_per_unit == Decimal("0")
                    and existing.slippage_cost == Decimal("0")
                )

            # Validate every candidate before changing any local projection.  A
            # later unsafe candidate must not leave an earlier candidate applied.
            candidate_repairs: list[
                tuple[
                    OrderModel,
                    BrokerTransactionFact,
                    str,
                    Decimal,
                    Decimal,
                    datetime,
                    str,
                    str,
                    Decimal,
                    Decimal,
                ]
            ] = []
            for order in orders:
                if order.purpose != "ENTRY" or order.current_status not in {
                    "UNKNOWN", "SUBMITTED", "PENDING_SUBMISSION"
                }:
                    continue
                candidates = tuple(
                    transaction
                    for transaction in broker.transactions
                    if transaction.external_order_id == order.external_order_id
                    and transaction.transaction_type in {"ORDER_FILL", "TRADE_OPEN"}
                )
                if not candidates:
                    if order.current_status == "UNKNOWN":
                        return _repair_required(
                            broker, "UNKNOWN_ORDER_FILL_EVIDENCE_UNAVAILABLE"
                        )
                    continue
                if len(candidates) != 1:
                    return _repair_required(broker, "AMBIGUOUS_ENTRY_FILL_EVIDENCE")
                transaction = candidates[0]
                if (
                    transaction.units is None
                    or transaction.price is None
                    or transaction.occurred_at is None
                    or transaction.external_trade_id is None
                    or abs(transaction.units) != order.quantity
                    or (transaction.units > 0) != (order.direction == "LONG")
                ):
                    return _repair_required(broker, "ENTRY_FILL_FACTS_MISMATCH")
                transaction_trade_id = transaction.external_trade_id
                transaction_units = transaction.units
                transaction_price = transaction.price
                transaction_occurred_at = transaction.occurred_at

                open_trades = broker.account.open_trades
                if len(open_trades) != 1 or not open_trades[0].is_open:
                    return _repair_required(broker, "CURRENT_OPEN_TRADE_REQUIRED")
                trade = open_trades[0]
                if (
                    trade.external_id != transaction_trade_id
                    or trade.direction.value != order.direction
                    or trade.current_units != transaction_units
                    or abs(trade.initial_units) != order.quantity
                ):
                    return _repair_required(broker, "CURRENT_OPEN_TRADE_MISMATCH")

                open_sides = broker.account.position_sides
                if len(open_sides) != 1 or not open_sides[0].is_open:
                    return _repair_required(broker, "CURRENT_POSITION_SIDE_REQUIRED")
                side = open_sides[0]
                if (
                    side.direction.value != order.direction
                    or side.units != order.quantity
                    or tuple(side.trade_ids) != (trade.external_id,)
                ):
                    return _repair_required(broker, "CURRENT_POSITION_SIDE_MISMATCH")

                intent = session.get(TradeIntentModel, order.trade_intent_id)
                risk = session.get(RiskDecisionModel, order.risk_decision_id)
                if (
                    intent is None
                    or intent.deployment_id != deployment.id
                    or risk is None
                    or risk.phase != "PRE_SUBMISSION"
                    or risk.outcome != "APPROVED"
                    or risk.target_price is not None
                    or risk.stop_price is None
                    or risk.target_multiple is None
                    or intent.proposed_stop is None
                    or intent.target_multiple is None
                    or risk.stop_price != intent.proposed_stop
                    or risk.target_multiple != intent.target_multiple
                ):
                    return _repair_required(
                        broker, "PAPER_PROTECTION_LINEAGE_UNAVAILABLE"
                    )
                try:
                    expected_target = target_from_fill(
                        transaction_price,
                        risk.stop_price,
                        order.direction,
                        risk.target_multiple,
                    )
                except Exception:
                    return _repair_required(broker, "ACTUAL_FILL_TARGET_UNAVAILABLE")
                if (
                    not broker.protection_verified
                    or len(broker.protection_facts) != 1
                ):
                    return _repair_required(broker, "CURRENT_PROTECTION_UNVERIFIED")
                protection = broker.protection_facts[0]
                if (
                    protection.observed_at != observed_at
                    or protection.stop_order_id == protection.target_order_id
                ):
                    return _repair_required(broker, "CURRENT_PROTECTION_NOT_CURRENT")
                if not protection.matches(
                    trade,
                    stop_price=risk.stop_price,
                    target_price=expected_target,
                ):
                    return _repair_required(broker, "CURRENT_PROTECTION_MISMATCH")
                local_protection = tuple(
                    session.scalars(
                        select(OrderModel).where(
                            OrderModel.parent_entry_order_id == order.id,
                            OrderModel.purpose.in_(
                                ("STOP_LOSS", "TAKE_PROFIT")
                            ),
                        )
                    ).all()
                )
                expected_protection = {
                    "STOP_LOSS": (protection.stop_order_id, risk.stop_price),
                    "TAKE_PROFIT": (protection.target_order_id, expected_target),
                }
                for local_order in local_protection:
                    expected_id, expected_price = expected_protection[
                        local_order.purpose
                    ]
                    if (
                        local_order.external_order_id != expected_id
                        or local_order.requested_price != expected_price
                    ):
                        return _repair_required(
                            broker, "LOCAL_PROTECTION_IDENTITY_MISMATCH"
                        )

                already = by_external.get(transaction.external_id)
                if already is not None:
                    if not existing_matches_transaction(already, order, transaction):
                        return _repair_required(
                            broker, "CONFLICTING_ENTRY_FILL_IDENTITY"
                        )
                    continue
                candidate_repairs.append(
                    (
                        order,
                        transaction,
                        transaction_trade_id,
                        transaction_units,
                        transaction_price,
                        transaction_occurred_at,
                        protection.stop_order_id,
                        protection.target_order_id,
                        risk.stop_price,
                        expected_target,
                    )
                )

            repaired = 0
            cursor_applied = False
            for (
                order,
                transaction,
                transaction_trade_id,
                transaction_units,
                transaction_price,
                transaction_occurred_at,
                stop_order_id,
                target_order_id,
                approved_stop,
                actual_target,
            ) in candidate_repairs:
                order.external_trade_ids = [transaction_trade_id]
                order.related_transaction_ids = [transaction.external_id]
                if order.current_status in {"UNKNOWN", "PENDING_SUBMISSION"}:
                    order.current_status = "SUBMITTED"
                    sequence = session.scalar(
                        select(
                            func.coalesce(
                                func.max(OrderEventModel.sequence_number), 0
                            )
                            + 1
                        )
                        .where(OrderEventModel.order_id == order.id)
                    )
                    if sequence is None:
                        raise ValueError("cannot sequence reconciliation Order event")
                    session.add(
                        OrderEventModel(
                            order_id=order.id,
                            sequence_number=int(sequence),
                            event_type="ORDER_SUBMITTED",
                            occurred_at=transaction_occurred_at,
                            details={"source": "RECONCILIATION_REPAIR"},
                        )
                    )
                fill = FillModel(
                    order_id=order.id,
                    sequence_number=1,
                    quantity=abs(transaction_units),
                    execution_price=transaction_price,
                    executed_at=transaction_occurred_at,
                    external_execution_id=transaction.external_id,
                    external_transaction_id=transaction.external_id,
                    external_trade_id=transaction_trade_id,
                    related_transaction_ids=[transaction.external_id],
                    fee=Decimal("0"),
                    slippage_per_unit=Decimal("0"),
                    slippage_cost=Decimal("0"),
                    price_basis="OPEN",
                )
                apply_fill(session, fill)
                intent = session.get(TradeIntentModel, order.trade_intent_id)
                if intent is not None:
                    intent.proposal_status = "FILLED"
                handoff = session.scalar(
                    select(PendingEntryHandoffModel)
                    .where(
                        PendingEntryHandoffModel.trade_intent_id
                        == order.trade_intent_id
                    )
                    .with_for_update()
                )
                if handoff is not None and handoff.status == "PENDING":
                    handoff.status = "FILLED"
                    handoff.resolved_at = transaction_occurred_at
                self.deployments.mark_first_trade(
                    session, deployment.id, transaction_occurred_at
                )
                by_external[transaction.external_id] = fill
                repaired += 1
                for purpose, order_type, external_id, price in (
                    (
                        "STOP_LOSS",
                        "STOP",
                        stop_order_id,
                        approved_stop,
                    ),
                    (
                        "TAKE_PROFIT",
                        "LIMIT",
                        target_order_id,
                        actual_target,
                    ),
                ):
                    existing_protection = session.scalar(
                        select(OrderModel).where(
                            OrderModel.parent_entry_order_id == order.id,
                            OrderModel.purpose == purpose,
                        )
                    )
                    if existing_protection is not None:
                        continue
                    protection_order = OrderModel(
                        experiment_id=None,
                        deployment_id=deployment.id,
                        trade_intent_id=order.trade_intent_id,
                        risk_decision_id=order.risk_decision_id,
                        order_type=order_type,
                        purpose=purpose,
                        direction=order.direction,
                        quantity=order.quantity,
                        requested_price=price,
                        current_status="SUBMITTED",
                        client_correlation_id=(
                            f"{order.client_correlation_id}-"
                            f"{'stop' if purpose == 'STOP_LOSS' else 'target'}"
                        ),
                        time_in_force="GTC",
                        external_order_id=external_id,
                        parent_entry_order_id=order.id,
                        request_provenance={
                            "source": "OANDA_RECONCILIATION_REPAIR",
                            "trade_id": transaction_trade_id,
                        },
                    )
                    session.add(protection_order)
                    session.flush()
                    session.add(
                        OrderEventModel(
                            order_id=protection_order.id,
                            sequence_number=1,
                            event_type="PROTECTION_CONFIRMED",
                            occurred_at=account.observed_at,
                            details={
                                "trade_id": transaction_trade_id,
                                "provider_order_id": external_id,
                                "price": str(price),
                            },
                        )
                    )
            if local_cursor is None or int(broker_cursor) > int(local_cursor):
                self.safety.advance_cursor(
                    session,
                    trading_account_id=deployment_row.trading_account_id,
                    last_transaction_id=broker_cursor,
                    observed_at=account.observed_at,
                    source="OANDA_RECONCILIATION_REPAIR",
                )
                cursor_applied = True
            if repaired == 0 and not cursor_applied:
                return None
            self.safety.record_system_event(
                session,
                deployment_id=deployment.id,
                severity="INFO",
                code="RECONCILIATION_REPAIRED",
                detail="Clear broker evidence was applied transactionally",
                details={
                    "fills_applied": repaired,
                    "cursor_before": local_cursor,
                    "cursor_after": broker_cursor,
                },
            )
            return ReconciliationResult(
                ReconciliationOutcome.REPAIRED,
                {
                    "repair": "CLEAR_FULL_FILL" if repaired else "CURSOR_APPLICATION",
                    "fills_applied": repaired,
                    "cursor_before": local_cursor,
                    "cursor_after": broker_cursor,
                    "protection_verified": broker.protection_verified,
                },
                broker,
            )

    @staticmethod
    def _transaction_digest(transaction: BrokerTransactionFact) -> str:
        """Hash only normalized immutable provider facts; never retain raw DTOs."""

        value = {
            "external_id": transaction.external_id,
            "transaction_type": transaction.transaction_type,
            "external_order_id": transaction.external_order_id,
            "external_trade_id": transaction.external_trade_id,
            "units": str(transaction.units) if transaction.units is not None else None,
            "price": str(transaction.price) if transaction.price is not None else None,
            "occurred_at": (
                transaction.occurred_at.isoformat()
                if transaction.occurred_at is not None
                else None
            ),
            "instrument": transaction.instrument,
        }
        return sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _record_account_changes_failure(self, deployment_id: UUID, reason: str) -> None:
        """Persist the safety outcome after the failed application rolled back."""

        with self.session_factory() as session, session.begin():
            self.deployments.set_actual_state(
                session,
                deployment_id,
                "RECONCILIATION_REQUIRED",
                safety_reason=reason,
            )
            self.safety.record_system_event(
                session,
                deployment_id=deployment_id,
                severity="CRITICAL",
                code="ACCOUNT_CHANGES_UNSAFE",
                detail=(
                    "Account Changes could not be fully applied; "
                    "new exposure is blocked"
                ),
                details={"reason": reason},
            )

    def _blocked_repair(
        self, deployment: RuntimeDeployment, broker: BrokerRead, reason: str
    ) -> ReconciliationResult:
        """Return a blocked result after durably recording a preflight failure."""

        self._record_account_changes_failure(deployment.id, reason)
        return _repair_required(broker, reason)

    def _record_broker_snapshot(
        self,
        session: Session,
        *,
        deployment: DeploymentModel,
        broker: BrokerRead,
    ) -> None:
        """Persist the account evidence used by the cursor fence transaction."""

        account = broker.account
        self.safety.record_account_snapshot(
            session,
            trading_account_id=deployment.trading_account_id,
            balance=account.balance,
            nav=account.nav,
            equity=account.equity,
            margin_available=account.margin_available,
            margin_used=account.margin_used,
            facts={
                "external_account_id": account.identity.account_id,
                "orders_known": account.orders_known,
                "trades_known": account.trades_known,
                "positions_known": account.positions_known,
                "pending_order_count": len(account.pending_orders),
                "open_trade_count": len(account.open_trades),
                "open_position_side_count": len(account.position_sides),
                "transaction_fence": broker.transaction_fence,
                "transactions_known": broker.transactions_known,
                "baseline_flat": not account.has_open_position,
            },
            observed_at=account.observed_at,
            freshness="FRESH" if account.fresh else "STALE",
            source=account.source,
        )

    @staticmethod
    def _flat_for_initial_cursor(account: object) -> bool:
        from backend.domain.broker import AccountSnapshot

        return (
            isinstance(account, AccountSnapshot)
            and account.account_state_known
            and not account.pending_orders
            and not any(trade.is_open for trade in account.open_trades)
            and not any(side.is_open for side in account.position_sides)
        )

    @staticmethod
    def _local_state_is_safe_for_initial_cursor(
        session: Session, deployment: DeploymentModel
    ) -> bool:
        """Prove this Deployment has no unresolved local EUR/USD execution."""

        positions = tuple(
            session.scalars(
                select(PositionModel)
                .where(PositionModel.deployment_id == deployment.id)
                .with_for_update()
            ).all()
        )
        for position in positions:
            if (
                position.venue_instrument_id != deployment.venue_instrument_id
                or position.state != "FLAT"
                or position.quantity is not None
                or position.entry_price is not None
                or position.opened_at is not None
            ):
                return False

        orders = tuple(
            session.scalars(
                select(OrderModel)
                .where(OrderModel.deployment_id == deployment.id)
                .with_for_update()
            ).all()
        )
        terminal_order_statuses = {"CANCELED", "REJECTED", "EXPIRED"}
        if any(
            order.current_status not in terminal_order_statuses for order in orders
        ):
            return False

        if orders and session.scalar(
            select(FillModel.id).where(
                FillModel.order_id.in_(tuple(order.id for order in orders))
            )
        ) is not None:
            return False
        if session.scalar(
            select(TradeModel.id).where(TradeModel.deployment_id == deployment.id)
        ) is not None:
            return False
        if session.scalar(
            select(PendingEntryHandoffModel.id).where(
                PendingEntryHandoffModel.deployment_id == deployment.id,
                PendingEntryHandoffModel.status == "PENDING",
            )
        ) is not None:
            return False
        if session.scalar(
            select(TradeIntentModel.id).where(
                TradeIntentModel.deployment_id == deployment.id,
                TradeIntentModel.action.in_(
                    ("OPEN_LONG", "OPEN_SHORT")
                ),
                TradeIntentModel.proposal_status == "PENDING",
            )
        ) is not None:
            return False
        return True

    @staticmethod
    def _transaction_is_harmless_account_fact(
        transaction: BrokerTransactionFact,
    ) -> bool:
        return transaction.transaction_type in {
            "DAILY_FINANCING",
            "DIVIDEND_ADJUSTMENT",
            "RESET_RESETTABLE_PL",
            "CLIENT_CONFIGURE",
        }

    def repair_reconciliation(
        self, deployment: RuntimeDeployment, broker: BrokerRead
    ) -> ReconciliationResult | None:
        """Apply one complete Account Changes response, then advance its fence.

        Submission responses intentionally never enter this method.  Every write
        below is in one database transaction and the cursor update is its final
        write; an exception rolls back receipts and canonical projections before
        a separate, inspectable safety transaction blocks new exposure.
        """

        account = broker.account
        if (
            account.identity != deployment.trading_account
            or not account.fresh
            or not account.account_state_known
        ):
            return self._blocked_repair(deployment, broker, "ACCOUNT_SNAPSHOT_UNSAFE")
        now = datetime.now(UTC)
        account_fence = account.last_transaction_id
        if (
            account_fence is None
            or not account_fence.isdecimal()
            or broker.transaction_fence is None
            or not broker.transaction_fence.isdecimal()
        ):
            return self._blocked_repair(
                deployment, broker, "CURRENT_TRANSACTION_FENCE_UNAVAILABLE"
            )
        if int(account_fence) > int(broker.transaction_fence):
            return self._blocked_repair(
                deployment, broker, "CURRENT_TRANSACTION_FENCE_STALE"
            )
        if (
            account.observed_at > now
            or now - account.observed_at > timedelta(minutes=2)
        ):
            return self._blocked_repair(deployment, broker, "ACCOUNT_SNAPSHOT_STALE")

        try:
            with self.session_factory() as session, session.begin():
                deployment_row = session.scalar(
                    select(DeploymentModel)
                    .where(DeploymentModel.id == deployment.id)
                    .with_for_update()
                )
                if deployment_row is None:
                    raise AccountChangesApplicationError("DEPLOYMENT_UNAVAILABLE")
                cursor = session.scalar(
                    select(AccountTransactionCursorModel)
                    .where(
                        AccountTransactionCursorModel.trading_account_id
                        == deployment_row.trading_account_id
                    )
                    .with_for_update()
                )

                # A flat first deployment has no cursor and deliberately does
                # not import account history.  Its current account fence is the
                # only permitted baseline.
                if cursor is None:
                    if (
                        not self._flat_for_initial_cursor(account)
                        or not self._local_state_is_safe_for_initial_cursor(
                            session, deployment_row
                        )
                    ):
                        raise AccountChangesApplicationError(
                            "INITIAL_CURSOR_BASELINE_UNSAFE"
                        )
                    fence = broker.transaction_fence
                    if fence != account_fence:
                        raise AccountChangesApplicationError(
                            "INITIAL_CURSOR_BASELINE_FENCE_MISMATCH"
                        )
                    self.safety.record_reconciliation(
                        session,
                        deployment_id=deployment.id,
                        trigger="ACCOUNT_CHANGES_BASELINE",
                        outcome=ReconciliationOutcome.REPAIRED.value,
                        started_at=account.observed_at,
                        finished_at=account.observed_at,
                        summary={"cursor_before": None, "cursor_after": fence},
                    )
                    self._record_broker_snapshot(
                        session, deployment=deployment_row, broker=broker
                    )
                    self.safety.advance_cursor(
                        session,
                        trading_account_id=deployment_row.trading_account_id,
                        last_transaction_id=fence,
                        observed_at=account.observed_at,
                        source="OANDA_ACCOUNT_DETAILS_BASELINE",
                    )
                    return ReconciliationResult(
                        ReconciliationOutcome.REPAIRED,
                        {
                            "repair": "INITIAL_CURSOR_BASELINE",
                            "cursor_after": fence,
                        },
                        broker,
                        durable_gate_proven=True,
                    )

                if (
                    not broker.transactions_known
                    or not broker.transaction_fence.isdecimal()
                ):
                    raise AccountChangesApplicationError("ACCOUNT_CHANGES_UNAVAILABLE")
                if int(broker.transaction_fence) < int(cursor.last_transaction_id):
                    raise AccountChangesApplicationError(
                        "TRANSACTION_CURSOR_MOVED_BACKWARD"
                    )

                transaction_ids: set[str] = set()
                orders = {
                    row.external_order_id: row
                    for row in session.scalars(
                        select(OrderModel)
                        .where(OrderModel.deployment_id == deployment.id)
                        .with_for_update()
                    )
                    if row.external_order_id is not None
                }
                unresolved_entry_orders = {
                    row.external_order_id
                    for row in orders.values()
                    if row.purpose == "ENTRY"
                    and row.current_status
                    in {"UNKNOWN", "PENDING_SUBMISSION", "SUBMITTED"}
                }
                resolved_entry_orders = {
                    transaction.external_order_id
                    for transaction in broker.transactions
                    if transaction.transaction_type == "ORDER_FILL"
                    and transaction.instrument == "EUR/USD"
                    and transaction.external_order_id is not None
                }
                if not unresolved_entry_orders.issubset(resolved_entry_orders):
                    raise AccountChangesApplicationError(
                        "UNKNOWN_ORDER_FILL_EVIDENCE_UNAVAILABLE"
                    )
                applied = 0
                observed = 0
                ignored = 0
                for transaction in broker.transactions:
                    if (
                        not transaction.external_id.isdecimal()
                        or transaction.external_id in transaction_ids
                        or int(transaction.external_id) > int(broker.transaction_fence)
                        or (
                            transaction.occurred_at is not None
                            and transaction.occurred_at > account.observed_at
                        )
                    ):
                        raise AccountChangesApplicationError(
                            "ACCOUNT_CHANGES_IDENTITY_INVALID"
                        )
                    transaction_ids.add(transaction.external_id)
                    digest = self._transaction_digest(transaction)
                    receipt = session.scalar(
                        select(OandaTransactionReceiptModel)
                        .where(
                            OandaTransactionReceiptModel.trading_account_id
                            == deployment_row.trading_account_id,
                            OandaTransactionReceiptModel.external_transaction_id
                            == transaction.external_id,
                        )
                        .with_for_update()
                    )
                    if receipt is not None:
                        if receipt.normalized_digest != digest:
                            raise AccountChangesApplicationError(
                                "TRANSACTION_RECEIPT_CONFLICT"
                            )
                        observed += 1
                        continue

                    disposition = "OBSERVED_NO_PROJECTION"
                    canonical_order: OrderModel | None = None
                    canonical_fill: FillModel | None = None
                    if transaction.instrument not in {None, "EUR/USD"}:
                        disposition = "IGNORED_OTHER_INSTRUMENT"
                        ignored += 1
                    elif transaction.transaction_type == "ORDER_FILL":
                        canonical_order = (
                            orders.get(transaction.external_order_id)
                            if transaction.external_order_id is not None
                            else None
                        )
                        if (
                            canonical_order is None
                            or transaction.instrument != "EUR/USD"
                            or transaction.external_trade_id is None
                            or transaction.units is None
                            or transaction.price is None
                            or transaction.occurred_at is None
                            or abs(transaction.units) != canonical_order.quantity
                            or (transaction.units > 0)
                            != (canonical_order.direction == "LONG")
                        ):
                            raise AccountChangesApplicationError(
                                "UNATTRIBUTED_EUR_USD_FILL"
                            )
                        if not self._prove_repair_protection(
                            session, broker, canonical_order, transaction
                        ):
                            raise AccountChangesApplicationError(
                                "CURRENT_PROTECTION_MISMATCH"
                            )
                        canonical_fill = session.scalar(
                            select(FillModel).where(
                                FillModel.external_transaction_id
                                == transaction.external_id
                            )
                        )
                        if canonical_fill is not None:
                            if not self._replayed_fill_agrees(
                                canonical_fill, canonical_order, transaction
                            ):
                                raise AccountChangesApplicationError(
                                    "CONFLICTING_ENTRY_FILL_IDENTITY"
                                )
                            disposition = "IDEMPOTENT"
                            observed += 1
                        else:
                            canonical_order.external_trade_ids = [
                                transaction.external_trade_id
                            ]
                            canonical_order.related_transaction_ids = [
                                transaction.external_id
                            ]
                            canonical_fill = FillModel(
                                order_id=canonical_order.id,
                                sequence_number=1,
                                quantity=abs(transaction.units),
                                execution_price=transaction.price,
                                executed_at=transaction.occurred_at,
                                external_execution_id=transaction.external_id,
                                external_transaction_id=transaction.external_id,
                                external_trade_id=transaction.external_trade_id,
                                related_transaction_ids=[transaction.external_id],
                                fee=Decimal("0"),
                                slippage_per_unit=Decimal("0"),
                                slippage_cost=Decimal("0"),
                                price_basis="OPEN",
                            )
                            apply_fill(session, canonical_fill)
                            intent = session.get(
                                TradeIntentModel, canonical_order.trade_intent_id
                            )
                            if intent is not None:
                                intent.proposal_status = "FILLED"
                            self.deployments.mark_first_trade(
                                session, deployment.id, transaction.occurred_at
                            )
                            disposition = "APPLIED"
                            applied += 1
                    elif self._transaction_is_harmless_account_fact(transaction):
                        observed += 1
                    elif (
                        transaction.transaction_type
                        in {
                            "ORDER_CREATE",
                            "ORDER_CANCEL",
                            "ORDER_REJECT",
                            "STOP_LOSS_ORDER",
                            "TAKE_PROFIT_ORDER",
                        }
                        and transaction.external_order_id in orders
                    ):
                        canonical_order = orders[transaction.external_order_id]
                        observed += 1
                    else:
                        raise AccountChangesApplicationError(
                            "UNATTRIBUTED_EUR_USD_TRANSACTION"
                        )

                    session.add(
                        OandaTransactionReceiptModel(
                            trading_account_id=deployment_row.trading_account_id,
                            external_transaction_id=transaction.external_id,
                            transaction_type=transaction.transaction_type,
                            occurred_at=transaction.occurred_at,
                            instrument=transaction.instrument,
                            external_order_id=transaction.external_order_id,
                            external_trade_id=transaction.external_trade_id,
                            normalized_digest=digest,
                            disposition=disposition,
                            canonical_order_id=(
                                canonical_order.id if canonical_order else None
                            ),
                            canonical_fill_id=(
                                canonical_fill.id if canonical_fill else None
                            ),
                            observed_at=account.observed_at,
                        )
                    )

                self.safety.record_reconciliation(
                    session,
                    deployment_id=deployment.id,
                    trigger="ACCOUNT_CHANGES",
                    outcome=ReconciliationOutcome.REPAIRED.value,
                    started_at=account.observed_at,
                    finished_at=account.observed_at,
                    summary={
                        "transactions": len(broker.transactions),
                        "fills_applied": applied,
                        "observed": observed,
                        "ignored_other_instrument": ignored,
                        "cursor_before": cursor.last_transaction_id,
                        "cursor_after": broker.transaction_fence,
                    },
                )
                self._record_broker_snapshot(
                    session, deployment=deployment_row, broker=broker
                )
                # Cursor update is deliberately the final successful write.
                self.safety.advance_cursor(
                    session,
                    trading_account_id=deployment_row.trading_account_id,
                    last_transaction_id=broker.transaction_fence,
                    observed_at=account.observed_at,
                    source="OANDA_ACCOUNT_CHANGES",
                )
                return ReconciliationResult(
                    ReconciliationOutcome.REPAIRED,
                    {
                        "fills_applied": applied,
                        "cursor_after": broker.transaction_fence,
                    },
                    broker,
                    durable_gate_proven=True,
                )
        except AccountChangesApplicationError as error:
            self._record_account_changes_failure(deployment.id, str(error))
            return _repair_required(broker, str(error))
        except Exception:
            self._record_account_changes_failure(
                deployment.id, "ACCOUNT_CHANGES_APPLICATION_FAILED"
            )
            return _repair_required(broker, "ACCOUNT_CHANGES_APPLICATION_FAILED")

    def _prove_repair_protection(
        self,
        session: Session,
        broker: BrokerRead,
        order: OrderModel,
        transaction: BrokerTransactionFact,
    ) -> bool:
        if not broker.protection_verified or len(broker.protection_facts) != 1:
            return False
        if (
            len(broker.account.open_trades) != 1
            or len(broker.account.position_sides) != 1
        ):
            return False
        trade = broker.account.open_trades[0]
        side = broker.account.position_sides[0]
        # Read-only proof must bind Trade, Position side, approved stop, and the
        # actual-Fill target; no stop/target quantity is fabricated or trusted.
        decision = session.get(RiskDecisionModel, order.risk_decision_id)
        if (
            decision is None
            or decision.stop_price is None
            or decision.target_multiple is None
            or transaction.price is None
            or transaction.external_trade_id is None
            or not trade.is_open
            or trade.external_id != transaction.external_trade_id
            or trade.direction.value != order.direction
            or abs(trade.current_units) != order.quantity
            or side.direction.value != order.direction
            or side.units != order.quantity
            or tuple(side.trade_ids) != (trade.external_id,)
        ):
            return False
        try:
            target = target_from_fill(
                transaction.price,
                decision.stop_price,
                order.direction,
                decision.target_multiple,
            )
        except Exception:
            return False
        protection = broker.protection_facts[0]
        return (
            protection.observed_at == broker.account.observed_at
            and protection.matches(
                trade,
                stop_price=decision.stop_price,
                target_price=target,
            )
        )

    @staticmethod
    def _replayed_fill_agrees(
        fill: FillModel, order: OrderModel, transaction: BrokerTransactionFact
    ) -> bool:
        return (
            fill.order_id == order.id
            and fill.sequence_number == 1
            and transaction.units is not None
            and fill.quantity == abs(transaction.units)
            and fill.execution_price == transaction.price
            and fill.executed_at == transaction.occurred_at
            and fill.external_execution_id == transaction.external_id
            and fill.external_transaction_id == transaction.external_id
            and fill.external_trade_id == transaction.external_trade_id
            and tuple(fill.related_transaction_ids) == (transaction.external_id,)
        )


__all__ = ["SqlAlchemyRuntimeStore"]
