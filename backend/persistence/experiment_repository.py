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

from backend.experiments.metric_contract import (
    LEGACY_METRIC_SCHEMA_VERSION,
    LEGACY_METRIC_STATES,
)

from .models import (
    ExperimentAccountModel,
    ExperimentEquityPointModel,
    ExperimentGapDecisionModel,
    ExperimentModel,
    ExperimentResultModel,
    PositionModel,
)


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
            status="PENDING",
        )
        session.add(row)
        session.flush()
        return row

    def get(self, session: Session, experiment_id: UUID) -> ExperimentModel | None:
        return session.get(ExperimentModel, experiment_id)

    def get_for_update(
        self, session: Session, experiment_id: UUID
    ) -> ExperimentModel | None:
        """Load one Experiment while holding its database row lock."""
        return session.scalar(
            select(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .with_for_update()
        )

    def has_run_facts(self, session: Session, experiment_id: UUID) -> bool:
        """Return whether a RUNNING row has any committed simulation facts."""
        from .models import (
            ExperimentEquityPointModel,
            FillModel,
            OrderModel,
            TradeIntentModel,
            TradeModel,
        )

        for model in (
            TradeIntentModel,
            OrderModel,
            TradeModel,
            ExperimentEquityPointModel,
            ExperimentResultModel,
        ):
            query = select(model.experiment_id).where(
                model.experiment_id == experiment_id
            )
            if session.scalar(query) is not None:
                return True
        fill_query = (
            select(FillModel.id)
            .join(OrderModel, FillModel.order_id == OrderModel.id)
            .where(OrderModel.experiment_id == experiment_id)
        )
        if session.scalar(fill_query) is not None:
            return True
        return False

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
        if row.status not in {"PENDING", "RUNNING"}:
            raise ValueError("only a pending or running experiment may be completed")
        if session.get(ExperimentResultModel, experiment_id) is None:
            raise ValueError("completed experiment requires a persisted result")
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
        if row.status not in {"PENDING", "RUNNING"}:
            raise ValueError("only a pending or running experiment may fail")
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

    def mark_running(self, session: Session, experiment_id: UUID) -> ExperimentModel:
        row = session.scalar(
            select(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .with_for_update()
        )
        if row is None or row.status != "PENDING":
            raise ValueError("only a pending experiment may run")
        row.status = "RUNNING"
        session.flush()
        return row

    def append_equity_point(
        self, session: Session, **values: object
    ) -> ExperimentEquityPointModel:
        experiment_id = values.get("experiment_id")
        experiment = session.get(ExperimentModel, experiment_id)
        if experiment is None:
            raise ValueError("experiment does not exist")
        if experiment.status in {"COMPLETED", "FAILED"}:
            raise ValueError("terminal Experiment facts are immutable")
        row = ExperimentEquityPointModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def create_result(
        self, session: Session, **values: object
    ) -> ExperimentResultModel:
        raw_states = values.setdefault("metric_states", dict(LEGACY_METRIC_STATES))
        if isinstance(raw_states, Mapping):
            states: dict[str, dict[str, object]] = {}
            for key in LEGACY_METRIC_STATES:
                value = raw_states.get(key)
                if isinstance(value, Mapping):
                    state = dict(value)
                elif value is not None and str(value) != LEGACY_METRIC_SCHEMA_VERSION:
                    state = {"state": str(value), "reason": None}
                else:
                    numeric = values.get(key)
                    state = {
                        "state": "VALUE" if numeric is not None else "UNAVAILABLE",
                        "reason": None if numeric is not None else "LEGACY_RESULT",
                    }
                state.setdefault("reason", None)
                if state.get("state") in {"UNAVAILABLE", "INFINITE"} and not state.get("reason"):
                    state["reason"] = "LEGACY_RESULT"
                states[key] = state
            values["metric_states"] = states
        values.setdefault("metric_schema_version", LEGACY_METRIC_SCHEMA_VERSION)
        experiment_id = values.get("experiment_id")
        experiment = session.get(ExperimentModel, experiment_id)
        if experiment is None:
            raise ValueError("experiment does not exist")
        if experiment.status in {"COMPLETED", "FAILED"}:
            raise ValueError("terminal Experiment result graph is immutable")
        if session.get(ExperimentResultModel, experiment_id) is not None:
            raise ValueError("ExperimentResult is immutable and already exists")
        row = ExperimentResultModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def create_gap_decision(
        self, session: Session, **values: object
    ) -> ExperimentGapDecisionModel:
        experiment = session.get(ExperimentModel, values.get("experiment_id"))
        if experiment is None:
            raise ValueError("experiment does not exist")
        if experiment.status in {"COMPLETED", "FAILED"}:
            raise ValueError("terminal Experiment facts are immutable")
        row = ExperimentGapDecisionModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row


__all__ = ["ExperimentRepository"]
