"""The explicit, transactional deletion boundary for historical Experiments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from .base import Base
from .lifecycle_locks import (
    HISTORICAL_LOAD_LIFECYCLE_LOCK_KEY,
    acquire_historical_load_lifecycle_lock,
)
from .models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotGapModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentDeletionReceiptModel,
    ExperimentEquityPointModel,
    ExperimentGapDecisionModel,
    ExperimentModel,
    ExperimentProposalDiagnosticModel,
    ExperimentResultModel,
    FillModel,
    HistoricalDataLoadRequestModel,
    InstrumentModel,
    OrderEventModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    StrategyModel,
    StrategyVersionModel,
    TradeIntentModel,
    TradeModel,
    VenueInstrumentModel,
)

EXPERIMENT_DELETE_CONFIRMATION_SCHEMA_VERSION: Final[str] = (
    "ATLAS_EXPERIMENT_DELETE_CONFIRMATION_V1"
)
_DELETABLE_STATUSES = frozenset({"PENDING", "FAILED", "COMPLETED"})


class ExperimentDeletionError(RuntimeError):
    """A stable, non-diagnostic failure at the deletion boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ExperimentDeletionNotFound(ExperimentDeletionError):
    def __init__(self) -> None:
        super().__init__("NOT_FOUND", "Experiment does not exist.")


class ExperimentDeletionRunning(ExperimentDeletionError):
    def __init__(self) -> None:
        super().__init__(
            "EXPERIMENT_RUNNING", "Running Experiments cannot be deleted."
        )


class ExperimentDeletionStateInvalid(ExperimentDeletionError):
    def __init__(self) -> None:
        super().__init__(
            "EXPERIMENT_DELETE_STATE_INVALID",
            "Experiment cannot be deleted in its current state.",
        )


class ExperimentDeletionOwnershipConflict(ExperimentDeletionError):
    def __init__(
        self, message: str = "Experiment graph ownership is not valid."
    ) -> None:
        super().__init__("DELETE_OWNERSHIP_CONFLICT", message)


@dataclass(frozen=True, slots=True)
class ExperimentDeletionResult:
    experiment_id: UUID
    snapshot_id: UUID
    snapshot_deleted: bool
    receipt_id: UUID


@dataclass(frozen=True, slots=True)
class ExperimentDeletionLock:
    """The root rows locked for one caller-owned deletion transaction."""

    experiment: ExperimentModel
    snapshot: DatasetSnapshotModel


@dataclass(frozen=True, slots=True)
class _DeletionPlan:
    experiment_id: UUID
    snapshot_id: UUID
    status: str
    strategy_id: UUID
    strategy_version_id: UUID
    strategy_source_fingerprint: str
    instrument: str
    provider: str
    trading_start: datetime
    trading_end: datetime
    intent_ids: tuple[UUID, ...]
    risk_ids: tuple[UUID, ...]
    order_ids_by_depth: tuple[tuple[UUID, ...], ...]


def _delete_rows(
    session: Session, model: type[Base], column: Any, values: tuple[UUID, ...]
) -> None:
    if values:
        session.execute(delete(model).where(column.in_(values)))


class ExperimentDeletionRepository:
    """Preflight and delete exactly one Experiment-owned graph."""

    def delete(
        self,
        session: Session,
        experiment_id: UUID,
        *,
        stage_hook: Callable[[str], None] | None = None,
        locked: ExperimentDeletionLock | None = None,
    ) -> ExperimentDeletionResult:
        plan = self._preflight(session, experiment_id, locked=locked)
        # The snapshot row was locked during preflight.  Acquire the shared
        # lifecycle lock before any mutation and retain it through the orphan
        # decision and caller-owned transaction commit.  Load activation takes
        # this lock without taking a snapshot row, so this order cannot form a
        # cycle with the snapshot-first attachment helper.
        acquire_historical_load_lifecycle_lock(session)
        self._set_deletion_context(session, experiment_id)

        self._delete_stage(
            session, stage_hook, "experiment_gap_decisions",
            lambda: session.execute(
                delete(ExperimentGapDecisionModel).where(
                    ExperimentGapDecisionModel.experiment_id == experiment_id
                )
            ),
        )
        self._delete_stage(
            session, stage_hook, "experiment_equity_points",
            lambda: session.execute(
                delete(ExperimentEquityPointModel).where(
                    ExperimentEquityPointModel.experiment_id == experiment_id
                )
            ),
        )
        self._delete_stage(
            session, stage_hook, "experiment_results",
            lambda: session.execute(
                delete(ExperimentResultModel).where(
                    ExperimentResultModel.experiment_id == experiment_id
                )
            ),
        )
        self._delete_stage(
            session, stage_hook, "experiment_proposal_diagnostics",
            lambda: session.execute(
                delete(ExperimentProposalDiagnosticModel).where(
                    ExperimentProposalDiagnosticModel.experiment_id == experiment_id
                )
            ),
        )
        self._delete_stage(
            session, stage_hook, "trades",
            lambda: session.execute(
                delete(TradeModel).where(TradeModel.experiment_id == experiment_id)
            ),
        )
        self._delete_stage(
            session, stage_hook, "order_events",
            lambda: _delete_rows(
                session,
                OrderEventModel,
                OrderEventModel.order_id,
                self._order_ids(plan),
            ),
        )
        self._delete_stage(
            session, stage_hook, "fills",
            lambda: _delete_rows(
                session, FillModel, FillModel.order_id, self._order_ids(plan)
            ),
        )
        self._delete_stage(
            session, stage_hook, "orders",
            lambda: self._delete_orders(session, plan.order_ids_by_depth),
        )
        self._delete_stage(
            session, stage_hook, "risk_decisions",
            lambda: _delete_rows(
                session, RiskDecisionModel, RiskDecisionModel.id, plan.risk_ids
            ),
        )
        self._delete_stage(
            session, stage_hook, "trade_intents",
            lambda: _delete_rows(
                session, TradeIntentModel, TradeIntentModel.id, plan.intent_ids
            ),
        )
        self._delete_stage(
            session, stage_hook, "positions",
            lambda: session.execute(
                delete(PositionModel).where(
                    PositionModel.experiment_id == experiment_id
                )
            ),
        )
        self._delete_stage(
            session, stage_hook, "experiment_accounts",
            lambda: session.execute(
                delete(ExperimentAccountModel).where(
                    ExperimentAccountModel.experiment_id == experiment_id
                )
            ),
        )
        self._delete_stage(
            session, stage_hook, "experiments",
            lambda: session.execute(
                delete(ExperimentModel).where(ExperimentModel.id == experiment_id)
            ),
        )

        snapshot_deleted = self._delete_orphan_snapshot(session, plan.snapshot_id)
        receipt = ExperimentDeletionReceiptModel(
            deleted_experiment_id=plan.experiment_id,
            pre_delete_status=plan.status,
            strategy_id=plan.strategy_id,
            strategy_version_id=plan.strategy_version_id,
            strategy_source_fingerprint=plan.strategy_source_fingerprint,
            instrument=plan.instrument,
            provider=plan.provider,
            trading_period_start=plan.trading_start,
            trading_period_end=plan.trading_end,
            dataset_snapshot_id=plan.snapshot_id,
            snapshot_deleted=snapshot_deleted,
            confirmation_schema_version=EXPERIMENT_DELETE_CONFIRMATION_SCHEMA_VERSION,
        )
        session.add(receipt)
        session.flush()
        self._hook(stage_hook, "receipt")
        return ExperimentDeletionResult(
            experiment_id=plan.experiment_id,
            snapshot_id=plan.snapshot_id,
            snapshot_deleted=snapshot_deleted,
            receipt_id=receipt.receipt_id,
        )

    def delete_experiment(
        self,
        session: Session,
        experiment_id: UUID,
        *,
        stage_hook: Callable[[str], None] | None = None,
    ) -> ExperimentDeletionResult:
        return self.delete(session, experiment_id, stage_hook=stage_hook)

    def lock_for_delete(
        self, session: Session, experiment_id: UUID
    ) -> ExperimentDeletionLock:
        """Acquire the canonical root lock order for a delete transaction."""
        initial = session.get(ExperimentModel, experiment_id)
        if initial is None:
            raise ExperimentDeletionNotFound()
        snapshot = session.scalar(
            select(DatasetSnapshotModel)
            .where(DatasetSnapshotModel.id == initial.dataset_snapshot_id)
            .with_for_update()
        )
        if snapshot is None:
            raise ExperimentDeletionError(
                "EXPERIMENT_DELETE_FAILED", "Experiment snapshot integrity is invalid."
            )
        experiment = session.scalar(
            select(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .with_for_update()
        )
        if experiment is None:
            raise ExperimentDeletionNotFound()
        if experiment.dataset_snapshot_id != snapshot.id:
            raise ExperimentDeletionError(
                "EXPERIMENT_DELETE_FAILED",
                "Experiment snapshot changed during deletion.",
            )
        return ExperimentDeletionLock(experiment=experiment, snapshot=snapshot)

    def _preflight(
        self,
        session: Session,
        experiment_id: UUID,
        *,
        locked: ExperimentDeletionLock | None = None,
    ) -> _DeletionPlan:
        if locked is None:
            locked = self.lock_for_delete(session, experiment_id)
        root = locked
        experiment = root.experiment
        snapshot = root.snapshot
        if experiment.status == "RUNNING":
            raise ExperimentDeletionRunning()
        if experiment.status not in _DELETABLE_STATUSES:
            raise ExperimentDeletionStateInvalid()
        if session.scalar(
            select(ExperimentDeletionReceiptModel.receipt_id).where(
                ExperimentDeletionReceiptModel.deleted_experiment_id == experiment_id
            )
        ) is not None:
            raise ExperimentDeletionOwnershipConflict(
                "Experiment already has a deletion receipt."
            )

        intents = tuple(
            session.scalars(
                select(TradeIntentModel)
                .where(TradeIntentModel.experiment_id == experiment_id)
                .with_for_update()
            ).all()
        )
        intent_ids = tuple(row.id for row in intents)
        risks = tuple(
            session.scalars(
                select(RiskDecisionModel)
                .where(RiskDecisionModel.trade_intent_id.in_(intent_ids))
                .with_for_update()
            ).all()
        )
        risk_ids = tuple(row.id for row in risks)
        orders = tuple(
            session.scalars(
                select(OrderModel)
                .where(OrderModel.experiment_id == experiment_id)
                .with_for_update()
            ).all()
        )
        order_ids = {row.id for row in orders}
        # Lock every directly owned row before validating or mutating the graph.
        # The row locks make the preflight decision authoritative for this
        # transaction instead of relying only on the root Experiment lock.
        for model in (
            ExperimentProposalDiagnosticModel,
            TradeModel,
            ExperimentEquityPointModel,
            ExperimentResultModel,
            ExperimentGapDecisionModel,
            PositionModel,
            ExperimentAccountModel,
        ):
            session.scalars(
                select(model)
                .where(model.experiment_id == experiment_id)
                .with_for_update()
            ).all()
        order_ids_tuple = tuple(order_ids)
        if order_ids_tuple:
            session.scalars(
                select(OrderEventModel)
                .where(OrderEventModel.order_id.in_(order_ids_tuple))
                .with_for_update()
            ).all()
            session.scalars(
                select(FillModel)
                .where(FillModel.order_id.in_(order_ids_tuple))
                .with_for_update()
            ).all()
        self._validate_cross_owner_edges(
            session, experiment_id, intents, risks, orders, order_ids
        )
        depths: dict[UUID, int] = {}
        by_id = {row.id: row for row in orders}

        for order in orders:
            parent = order.parent_entry_order_id
            if parent is not None and parent not in order_ids:
                raise ExperimentDeletionOwnershipConflict(
                    "Order parent is outside the Experiment graph."
                )
        for start in order_ids:
            if start in depths:
                continue
            path: list[UUID] = []
            path_index: dict[UUID, int] = {}
            current = start
            while current not in depths:
                if current in path_index:
                    raise ExperimentDeletionOwnershipConflict(
                        "Order parent graph contains a cycle."
                    )
                path_index[current] = len(path)
                path.append(current)
                parent = by_id[current].parent_entry_order_id
                if parent is None:
                    break
                current = parent
            for order_id in reversed(path):
                parent = by_id[order_id].parent_entry_order_id
                depths[order_id] = 0 if parent is None else depths[parent] + 1
        order_ids_by_depth = tuple(
            tuple(
                order_id
                for order_id, value in sorted(depths.items())
                if value == current
            )
            for current in range(max(depths.values(), default=-1), -1, -1)
        )
        identity = session.execute(
            select(
                StrategyModel.id,
                StrategyVersionModel.id,
                StrategyVersionModel.source_fingerprint,
                InstrumentModel.code,
                VenueInstrumentModel.provider,
            )
            .join(StrategyModel, StrategyModel.id == StrategyVersionModel.strategy_id)
            .join(
                VenueInstrumentModel,
                VenueInstrumentModel.id == experiment.venue_instrument_id,
            )
            .join(
                InstrumentModel,
                InstrumentModel.id == VenueInstrumentModel.instrument_id,
            )
            .where(StrategyVersionModel.id == experiment.strategy_version_id)
        ).one_or_none()
        if identity is None:
            raise ExperimentDeletionError(
                "EXPERIMENT_DELETE_FAILED",
                "Experiment provenance integrity is invalid.",
            )
        return _DeletionPlan(
            experiment_id=experiment.id,
            snapshot_id=snapshot.id,
            status=experiment.status,
            strategy_id=identity[0],
            strategy_version_id=identity[1],
            strategy_source_fingerprint=identity[2],
            instrument=identity[3],
            provider=identity[4],
            trading_start=experiment.trading_start,
            trading_end=experiment.trading_end,
            intent_ids=intent_ids,
            risk_ids=risk_ids,
            order_ids_by_depth=order_ids_by_depth,
        )

    def _validate_cross_owner_edges(
        self,
        session: Session,
        experiment_id: UUID,
        intents: tuple[TradeIntentModel, ...],
        risks: tuple[RiskDecisionModel, ...],
        orders: tuple[OrderModel, ...],
        order_ids: set[UUID],
    ) -> None:
        intent_ids = {row.id for row in intents}
        risk_ids = {row.id for row in risks}
        diagnostics = tuple(
            session.scalars(
                select(ExperimentProposalDiagnosticModel).where(
                    (ExperimentProposalDiagnosticModel.experiment_id == experiment_id)
                    | (
                        ExperimentProposalDiagnosticModel.trade_intent_id.in_(
                            intent_ids
                        )
                    )
                ).with_for_update()
            ).all()
        )
        if any(
            row.experiment_id != experiment_id or row.trade_intent_id not in intent_ids
            for row in diagnostics
        ):
            raise ExperimentDeletionOwnershipConflict()
        all_risks = tuple(
            session.scalars(
                select(RiskDecisionModel).where(
                    RiskDecisionModel.trade_intent_id.in_(intent_ids)
                ).with_for_update()
            ).all()
        )
        if {row.id for row in all_risks} != risk_ids or any(
            row.trade_intent_id not in intent_ids for row in risks
        ):
            raise ExperimentDeletionOwnershipConflict()
        all_orders = tuple(
            session.scalars(
                select(OrderModel).where(
                    (OrderModel.trade_intent_id.in_(intent_ids))
                    | (OrderModel.risk_decision_id.in_(risk_ids))
                    | (OrderModel.parent_entry_order_id.in_(order_ids))
                ).with_for_update()
            ).all()
        )
        if {row.id for row in all_orders} != order_ids or any(
            row.trade_intent_id not in intent_ids
            or row.risk_decision_id not in risk_ids
            for row in orders
        ):
            raise ExperimentDeletionOwnershipConflict()
        trades = tuple(
            session.scalars(
                select(TradeModel).where(
                    (TradeModel.experiment_id == experiment_id)
                    | (TradeModel.trade_intent_id.in_(intent_ids))
                    | (TradeModel.entry_order_id.in_(order_ids))
                    | (TradeModel.exit_order_id.in_(order_ids))
                ).with_for_update()
            ).all()
        )
        if any(
            row.experiment_id != experiment_id
            or row.trade_intent_id not in intent_ids
            or row.entry_order_id not in order_ids
            or (row.exit_order_id is not None and row.exit_order_id not in order_ids)
            for row in trades
        ):
            raise ExperimentDeletionOwnershipConflict()
        events = tuple(
            session.scalars(
                select(OrderEventModel).where(OrderEventModel.order_id.in_(order_ids))
                .with_for_update()
            ).all()
        )
        fills = tuple(
            session.scalars(
                select(FillModel).where(FillModel.order_id.in_(order_ids))
                .with_for_update()
            ).all()
        )
        # These two tables have no Experiment column; every row is owned through
        # the already validated target Order ID set.
        if any(row.order_id not in order_ids for row in (*events, *fills)):
            raise ExperimentDeletionOwnershipConflict()

    @staticmethod
    def _order_ids(plan: _DeletionPlan) -> tuple[UUID, ...]:
        return tuple(
            order_id
            for group in plan.order_ids_by_depth
            for order_id in group
        )

    @staticmethod
    def _delete_orders(session: Session, groups: tuple[tuple[UUID, ...], ...]) -> None:
        for group in groups:
            _delete_rows(session, OrderModel, OrderModel.id, group)

    @staticmethod
    def _set_deletion_context(session: Session, experiment_id: UUID) -> None:
        session.execute(
            text("SELECT set_config('atlas.experiment_deletion_id', :value, true)"),
            {"value": str(experiment_id)},
        )

    @staticmethod
    def _hook(hook: Callable[[str], None] | None, stage: str) -> None:
        if hook is not None:
            hook(stage)

    def _delete_stage(
        self,
        session: Session,
        hook: Callable[[str], None] | None,
        stage: str,
        operation: Callable[[], object],
    ) -> None:
        operation()
        session.flush()
        self._hook(hook, stage)

    def _delete_orphan_snapshot(self, session: Session, snapshot_id: UUID) -> bool:
        remaining_experiment = session.scalar(
            select(ExperimentModel.id)
            .where(ExperimentModel.dataset_snapshot_id == snapshot_id)
            .limit(1)
        )
        remaining_load_reference = session.scalar(
            select(HistoricalDataLoadRequestModel.id)
            .where(HistoricalDataLoadRequestModel.snapshot_id == snapshot_id)
            .limit(1)
        )
        active_load = session.scalar(
            select(HistoricalDataLoadRequestModel.id)
            .where(HistoricalDataLoadRequestModel.status.in_(("PENDING", "RUNNING")))
            .limit(1)
        )
        if remaining_experiment or remaining_load_reference or active_load:
            return False
        self._set_deletion_context(session, snapshot_id)
        for model in (
            DatasetSnapshotBarModel,
            DatasetSnapshotAnalyticalBarModel,
            DatasetSnapshotExecutionObservationModel,
            DatasetSnapshotGapModel,
        ):
            session.execute(
                delete(model).where(model.dataset_snapshot_id == snapshot_id)
            )
            session.flush()
        session.execute(
            delete(DatasetSnapshotModel).where(DatasetSnapshotModel.id == snapshot_id)
        )
        session.flush()
        self._set_deletion_context(session, snapshot_id)
        return True


class ExperimentDeletionService:
    """Application-facing name for the focused repository boundary."""

    def __init__(self, repository: ExperimentDeletionRepository | None = None) -> None:
        self.repository = repository or ExperimentDeletionRepository()

    def lock_for_delete(
        self, session: Session, experiment_id: UUID
    ) -> ExperimentDeletionLock:
        return self.repository.lock_for_delete(session, experiment_id)

    def delete(
        self,
        session: Session,
        experiment_id: UUID,
        *,
        stage_hook: Callable[[str], None] | None = None,
        locked: ExperimentDeletionLock | None = None,
    ) -> ExperimentDeletionResult:
        return self.repository.delete(
            session, experiment_id, stage_hook=stage_hook, locked=locked
        )


__all__ = [
    "EXPERIMENT_DELETE_CONFIRMATION_SCHEMA_VERSION",
    "HISTORICAL_LOAD_LIFECYCLE_LOCK_KEY",
    "ExperimentDeletionError",
    "ExperimentDeletionLock",
    "ExperimentDeletionNotFound",
    "ExperimentDeletionOwnershipConflict",
    "ExperimentDeletionRepository",
    "ExperimentDeletionResult",
    "ExperimentDeletionRunning",
    "ExperimentDeletionService",
    "ExperimentDeletionStateInvalid",
    "acquire_historical_load_lifecycle_lock",
]
