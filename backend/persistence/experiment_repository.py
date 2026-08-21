"""Focused persistence boundary for historical Experiments.

Methods are flush-only.  The caller owns the Session and the transaction so an
Experiment, its simulated account, and its initial Position can be created as
one unit when required.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ExperimentAccountModel, ExperimentModel, PositionModel


def _sanitize_failure_detail(detail: str) -> str:
    """Keep terminal diagnostics bounded and free of control characters."""
    return " ".join(detail.split())[:500]


class ExperimentRepository:
    """Create and read immutable Experiment configuration and projections."""

    def create(
        self,
        session: Session,
        *,
        strategy_version_id: UUID,
        dataset_snapshot_id: UUID,
        venue_instrument_id: UUID,
        trading_start: datetime,
        trading_end: datetime,
        starting_capital: Decimal,
        risk_per_trade: Decimal,
        parameter_snapshot: Mapping[str, object],
        risk_config: Mapping[str, object],
        simulation_config: Mapping[str, object],
        model_version: str,
        experiment_id: UUID | None = None,
    ) -> ExperimentModel:
        row = ExperimentModel(
            id=experiment_id,
            strategy_version_id=strategy_version_id,
            dataset_snapshot_id=dataset_snapshot_id,
            venue_instrument_id=venue_instrument_id,
            trading_start=trading_start,
            trading_end=trading_end,
            starting_capital=starting_capital,
            risk_per_trade=risk_per_trade,
            parameter_snapshot=dict(parameter_snapshot),
            risk_config=dict(risk_config),
            simulation_config=dict(simulation_config),
            model_version=model_version,
        )
        session.add(row)
        session.flush()
        return row

    def get(self, session: Session, experiment_id: UUID) -> ExperimentModel | None:
        return session.get(ExperimentModel, experiment_id)

    def create_account_and_position(
        self,
        session: Session,
        experiment: ExperimentModel,
        *,
        base_currency: str = "USD",
    ) -> tuple[ExperimentAccountModel, PositionModel]:
        """Seed the two mutable projections without changing exposure."""
        account = ExperimentAccountModel(
            experiment_id=experiment.id,
            base_currency=base_currency,
            starting_capital=experiment.starting_capital,
            equity=experiment.starting_capital,
        )
        position = PositionModel(
            experiment_id=experiment.id,
            venue_instrument_id=experiment.venue_instrument_id,
        )
        session.add_all([account, position])
        session.flush()
        return account, position

    def mark_completed(
        self, session: Session, experiment_id: UUID, completed_at: datetime
    ) -> ExperimentModel:
        row = session.scalar(
            select(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .with_for_update()
        )
        if row is None:
            raise ValueError("experiment does not exist")
        if row.status != "RUNNING":
            raise ValueError("only a running experiment may be completed")
        row.status = "COMPLETED"
        row.completed_at = completed_at
        session.flush()
        return row

    def mark_failed(
        self,
        session: Session,
        experiment_id: UUID,
        *,
        category: str,
        code: str,
        detail: str,
        completed_at: datetime,
    ) -> ExperimentModel:
        row = session.scalar(
            select(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .with_for_update()
        )
        if row is None:
            raise ValueError("experiment does not exist")
        if row.status != "RUNNING":
            raise ValueError("only a running experiment may fail")
        if category not in {
            "VALIDATION", "MARKET_DATA", "STRATEGY", "RISK", "EXECUTION", "PERSISTENCE"
        }:
            raise ValueError("invalid failure category")
        if not code.isascii() or not code or not all(
            char.isupper() or char.isdigit() or char == "_" for char in code
        ):
            raise ValueError("invalid failure code")
        sanitized = _sanitize_failure_detail(detail)
        if not sanitized:
            raise ValueError("failure detail is required")
        row.status = "FAILED"
        row.completed_at = completed_at
        row.failure_category = category
        row.failure_code = code
        row.failure_detail = sanitized
        session.flush()
        return row


__all__ = ["ExperimentRepository"]
