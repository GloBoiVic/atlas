"""Bounded, read-only persistence queries for completed Experiment results."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ExperimentEquityPointModel,
    ExperimentModel,
    ExperimentResultModel,
    FillModel,
    OrderEventModel,
    OrderModel,
    RiskDecisionModel,
    TradeIntentModel,
    TradeModel,
)


class ExperimentResultRepository:
    """Keep SQL composition focused and leave result semantics to the service."""

    def experiment(
        self, session: Session, experiment_id: UUID
    ) -> ExperimentModel | None:
        return session.get(ExperimentModel, experiment_id)

    def list_experiments(
        self,
        session: Session,
        limit: int,
        *,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> tuple[ExperimentModel, ...]:
        query = select(ExperimentModel)
        if before_created_at is not None and before_id is not None:
            query = query.where(
                (ExperimentModel.created_at < before_created_at)
                | (
                    (ExperimentModel.created_at == before_created_at)
                    & (ExperimentModel.id < before_id)
                )
            )
        return tuple(
            session.scalars(
                query
                .order_by(ExperimentModel.created_at.desc(), ExperimentModel.id.desc())
                .limit(limit)
            ).all()
        )

    def result(
        self, session: Session, experiment_id: UUID
    ) -> ExperimentResultModel | None:
        return session.get(ExperimentResultModel, experiment_id)

    def equity(
        self, session: Session, experiment_id: UUID
    ) -> tuple[ExperimentEquityPointModel, ...]:
        return tuple(
            session.scalars(
                select(ExperimentEquityPointModel)
                .where(ExperimentEquityPointModel.experiment_id == experiment_id)
                .order_by(ExperimentEquityPointModel.sequence_number)
            ).all()
        )

    def trades(
        self, session: Session, experiment_id: UUID, limit: int, after_sequence: int = 0
    ) -> tuple[TradeModel, ...]:
        return tuple(
            session.scalars(
                select(TradeModel)
                .where(
                    TradeModel.experiment_id == experiment_id,
                    TradeModel.sequence_number > after_sequence,
                )
                .order_by(TradeModel.sequence_number)
                .limit(limit)
            ).all()
        )

    def trade(
        self, session: Session, experiment_id: UUID, sequence_number: int
    ) -> TradeModel | None:
        return session.scalar(
            select(TradeModel).where(
                TradeModel.experiment_id == experiment_id,
                TradeModel.sequence_number == sequence_number,
            )
        )

    def intent(self, session: Session, trade: TradeModel) -> TradeIntentModel | None:
        return session.get(TradeIntentModel, trade.trade_intent_id)

    def risks(self, session: Session, intent_id: UUID) -> tuple[RiskDecisionModel, ...]:
        return tuple(
            session.scalars(
                select(RiskDecisionModel)
                .where(RiskDecisionModel.trade_intent_id == intent_id)
                .order_by(RiskDecisionModel.evaluated_at, RiskDecisionModel.phase)
            ).all()
        )

    def orders(
        self, session: Session, experiment_id: UUID, intent_id: UUID
    ) -> tuple[OrderModel, ...]:
        return tuple(
            session.scalars(
                select(OrderModel)
                .where(
                    OrderModel.experiment_id == experiment_id,
                    OrderModel.trade_intent_id == intent_id,
                )
                .order_by(OrderModel.created_at, OrderModel.purpose, OrderModel.id)
            ).all()
        )

    def events(self, session: Session, order_id: UUID) -> tuple[OrderEventModel, ...]:
        return tuple(
            session.scalars(
                select(OrderEventModel)
                .where(OrderEventModel.order_id == order_id)
                .order_by(OrderEventModel.sequence_number)
            ).all()
        )

    def fills(
        self, session: Session, order_ids: tuple[UUID, ...]
    ) -> tuple[FillModel, ...]:
        if not order_ids:
            return ()
        return tuple(
            session.scalars(
                select(FillModel)
                .where(FillModel.order_id.in_(order_ids))
                .order_by(FillModel.executed_at, FillModel.sequence_number)
            ).all()
        )
