"""Authoritative read composition for completed Experiment inspection."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.domain.market_data import PriceComponent
from backend.market_data.aggregation import AggregationError, aggregate_m1_to_m15
from backend.persistence.market_data_repository import DatasetSnapshotRepository
from backend.persistence.models import DatasetSnapshotModel, ExperimentModel, TradeModel
from backend.persistence.result_repository import ExperimentResultRepository
from backend.strategies.indicators import ema_100

from .metrics import ExperimentMetrics, MetricValue, calculate_metrics


class ResultReadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class EquityRead:
    points: tuple[dict[str, object], ...]
    source_count: int
    sampling_policy: str


@dataclass(frozen=True, slots=True)
class ChartContext:
    candles: tuple[dict[str, object], ...]
    annotations: tuple[dict[str, object], ...]
    omitted_range: dict[str, str] | None


def _metric(value: MetricValue) -> dict[str, object]:
    return value.as_dict()


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class ExperimentResultReadService:
    """Compose bounded views without recalculating from mutable defaults."""

    def __init__(
        self,
        *,
        results: ExperimentResultRepository | None = None,
        snapshots: DatasetSnapshotRepository | None = None,
    ) -> None:
        self.results = results or ExperimentResultRepository()
        self.snapshots = snapshots or DatasetSnapshotRepository()

    def _completed(self, session: Session, experiment_id: UUID) -> ExperimentModel:
        experiment = self.results.experiment(session, experiment_id)
        if experiment is None:
            raise ResultReadError("NOT_FOUND", "Experiment does not exist")
        if experiment.status == "FAILED":
            raise ResultReadError(
                "EXPERIMENT_FAILED", "Experiment failed; no trustworthy result exists"
            )
        if experiment.status != "COMPLETED":
            raise ResultReadError("RESULT_NOT_READY", "Experiment result is not ready")
        return experiment

    def list(
        self,
        session: Session,
        limit: int = 50,
        *,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> tuple[ExperimentModel, ...]:
        if not 1 <= limit <= 100:
            raise ResultReadError("INVALID_LIMIT", "limit must be between 1 and 100")
        return self.results.list_experiments(
            session,
            limit,
            before_created_at=before_created_at,
            before_id=before_id,
        )

    def detail(self, session: Session, experiment_id: UUID) -> dict[str, object]:
        experiment = self.results.experiment(session, experiment_id)
        if experiment is None:
            raise ResultReadError("NOT_FOUND", "Experiment does not exist")
        result = None
        metrics = None
        if experiment.status == "COMPLETED":
            result = self.results.result(session, experiment_id)
            trades = self.results.trades(session, experiment_id, 100000)
            equity = self.results.equity(session, experiment_id)
            metrics = self._metrics(experiment, trades, equity)
        return {"experiment": experiment, "result": result, "metrics": metrics}

    def _metrics(
        self,
        experiment: ExperimentModel,
        trades: tuple[TradeModel, ...],
        equity: tuple[object, ...],
    ) -> ExperimentMetrics:
        # This deliberately derives legacy projections without mutating them.
        return calculate_metrics(
            trades, equity, starting_equity=experiment.starting_capital
        )

    def equity(self, session: Session, experiment_id: UUID) -> EquityRead:
        experiment = self._completed(session, experiment_id)
        rows = self.results.equity(session, experiment.id)
        selected = list(rows)
        if len(selected) > 2000:
            # Four envelope representatives per bucket fit the 6,000-point cap.
            bucket = max(1, (len(selected) + 1499) // 1500)
            keep: set[int] = set()
            for offset in range(0, len(selected), bucket):
                group = selected[offset : offset + bucket]
                keep.update(
                    {
                        offset,
                        offset + len(group) - 1,
                        offset + min(range(len(group)), key=lambda i: group[i].equity),
                        offset
                        + max(
                            range(len(group)), key=lambda i: group[i].drawdown_amount
                        ),
                    }
                )
            selected = [row for index, row in enumerate(rows) if index in keep]
        return EquityRead(
            tuple(
                {
                    "sequence": row.sequence_number,
                    "observed_at": row.observed_at,
                    "equity": str(row.equity),
                    "drawdown_amount": str(row.drawdown_amount),
                    "drawdown_percent": str(row.drawdown_percent),
                    "valuation_bid": _decimal(row.valuation_bid),
                    "valuation_ask": _decimal(row.valuation_ask),
                }
                for row in selected
            ),
            len(rows),
            "EQUITY_ENVELOPE_V1" if len(rows) > 2000 else "FULL_CANONICAL_SERIES",
        )

    def trades(
        self,
        session: Session,
        experiment_id: UUID,
        limit: int = 100,
        after_sequence: int = 0,
    ) -> tuple[dict[str, object], ...]:
        self._completed(session, experiment_id)
        if not 1 <= limit <= 250 or after_sequence < 0:
            raise ResultReadError("INVALID_LIMIT", "trade pagination is out of bounds")
        return tuple(
            self._trade_summary(row)
            for row in self.results.trades(
                session, experiment_id, limit, after_sequence
            )
        )

    @staticmethod
    def _trade_summary(row: TradeModel) -> dict[str, object]:
        return {
            "label": f"Trade {row.sequence_number}",
            "sequence_number": row.sequence_number,
            "direction": row.direction,
            "status": row.status,
            "opened_at": row.opened_at,
            "closed_at": row.closed_at,
            "entry_price": str(row.entry_price),
            "exit_price": _decimal(row.exit_price),
            "exit_reason": row.exit_reason,
            "net_pnl": _decimal(row.net_pnl),
            "r_multiple": _decimal(row.r_multiple),
            "ambiguous": row.intrabar_ambiguous,
            "ambiguity_policy": row.ambiguity_policy,
        }

    def trade(
        self, session: Session, experiment_id: UUID, sequence_number: int
    ) -> dict[str, object]:
        experiment = self._completed(session, experiment_id)
        row = self.results.trade(session, experiment.id, sequence_number)
        if row is None:
            raise ResultReadError("NOT_FOUND", "Trade does not exist")
        intent = self.results.intent(session, row)
        if intent is None:
            raise ResultReadError("INCOMPLETE_RESULT", "Trade lineage is incomplete")
        risks = self.results.risks(session, intent.id)
        orders = self.results.orders(session, experiment.id, intent.id)
        events = {order.id: self.results.events(session, order.id) for order in orders}
        fills = self.results.fills(session, tuple(order.id for order in orders))
        return {
            "summary": self._trade_summary(row),
            "financing_disclosure": (
                experiment.simulation_config.get("financing_model", {}).get(
                    "disclosure"
                )
            ),
            "rationale": intent.rationale,
            "risks": tuple(risks),
            "orders": tuple((order, events[order.id]) for order in orders),
            "fills": fills,
            "initial_stop": next(
                (
                    risk.stop_price
                    for risk in risks
                    if risk.phase == "PRE_SUBMISSION" and risk.outcome == "APPROVED"
                ),
                None,
            ),
            "target": next(
                (
                    risk.target_price
                    for risk in risks
                    if risk.phase == "PRE_SUBMISSION" and risk.outcome == "APPROVED"
                ),
                None,
            ),
            "chart": self._chart(session, experiment, row, intent),
        }

    def _chart(
        self,
        session: Session,
        experiment: ExperimentModel,
        trade: TradeModel,
        intent: object,
    ) -> ChartContext:
        bars = self.snapshots.ordered_members_with_sources(
            session, experiment.dataset_snapshot_id, None, None, (PriceComponent.MID,)
        )
        snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
        if snapshot is None:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Dataset snapshot is unavailable"
            )
        try:
            m15 = aggregate_m1_to_m15(
                tuple(item.bar for item in bars),
                PriceComponent.MID,
                snapshot.coverage_start,
                snapshot.coverage_end,
            )
        except (AggregationError, ValueError):
            m15 = ()
        values = tuple(
            (bar, ema_100(m15[: index + 1]) if index + 1 >= 100 else None)
            for index, bar in enumerate(m15)
        )
        fields = getattr(intent, "rationale", {})
        # Rationale.to_json() persists ``fields`` as an object. Keep the
        # chart reader tolerant of older pair-sequence fixtures, but never
        # unpack object keys as pairs.
        rationale_fields = fields.get("fields", {})
        field_items = (
            rationale_fields.items()
            if isinstance(rationale_fields, dict)
            else rationale_fields
        )
        times = {
            datetime.fromisoformat(value)
            for key, value in field_items
            if key.endswith("_time")
        }
        setup_indices = [
            index
            for index, (bar, _) in enumerate(values)
            if any(abs((bar.end_time - marker).total_seconds()) < 1 for marker in times)
        ]
        exit_time = trade.closed_at or trade.opened_at
        exit_indices = [
            index
            for index, (bar, _) in enumerate(values)
            if abs((bar.end_time - exit_time).total_seconds()) < 1
        ]
        indices: set[int] = set()
        for center in (*setup_indices, *exit_indices):
            indices.update(range(max(0, center - 21), min(len(values), center + 2)))
        selected_indices = sorted(indices)
        omitted = None
        if len(selected_indices) > 500:
            omitted = {
                "start": values[selected_indices[0]][0].start_time.isoformat(),
                "end": values[selected_indices[-1]][0].end_time.isoformat(),
            }
            selected_indices = selected_indices[:500]
        context = [values[index] for index in selected_indices]
        candles = tuple(
            {
                "time": bar.end_time,
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "ema": _decimal(ema),
            }
            for bar, ema in context
        )
        annotations = tuple(
            {"kind": "strategy_marker", "time": time} for time in sorted(times)
        ) + tuple(
            {"kind": kind, "price": price}
            for kind, price in (
                ("entry", trade.entry_price),
                ("exit", trade.exit_price),
            )
        )
        return ChartContext(candles, annotations, omitted)
