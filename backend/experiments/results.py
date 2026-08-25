"""Authoritative read composition for completed Experiment inspection."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.market_data.aggregation import AggregationError, aggregate_m1_to_m15
from backend.market_data.ingestion import MarketDataService
from backend.persistence.market_data_repository import DatasetSnapshotRepository
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotModel,
    ExperimentModel,
    InstrumentModel,
    StrategyVersionModel,
    TradeModel,
    VenueInstrumentModel,
)
from backend.persistence.result_repository import ExperimentResultRepository
from backend.strategies.indicators import ema_100
from backend.strategies.indicators_v2 import ema

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


@dataclass(frozen=True, slots=True)
class PriceAnalysisRead:
    m15: tuple[dict[str, object], ...]
    ema: tuple[dict[str, object], ...]
    trading_window: dict[str, datetime]
    trades: tuple[dict[str, object], ...]
    reference: tuple[dict[str, object], ...]
    diagnostics: dict[str, object]
    provenance: dict[str, object]
    gaps: tuple[dict[str, object], ...]


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
        market_data: MarketDataService | None = None,
    ) -> None:
        self.results = results or ExperimentResultRepository()
        self.snapshots = snapshots or DatasetSnapshotRepository()
        self.market_data = market_data

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

    def gap_decisions(
        self, session: Session, experiment_id: UUID
    ) -> tuple[object, ...]:
        """Expose persisted gap decisions without changing result semantics."""
        return self.results.gap_decisions(session, experiment_id)

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

    def price_analysis(
        self, session: Session, experiment_id: UUID
    ) -> PriceAnalysisRead:
        """Compose the bounded, immutable price context for a completed Experiment."""
        experiment = self._completed(session, experiment_id)
        if self.market_data is None:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Market-data reader is unavailable"
            )
        if self.results.result(session, experiment.id) is None:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Experiment result is unavailable"
            )
        snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
        version = session.get(StrategyVersionModel, experiment.strategy_version_id)
        if snapshot is None or version is None:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Experiment lineage is incomplete"
            )
        raw_period = experiment.parameter_snapshot.get("ema_period")
        if type(raw_period) is not int or raw_period <= 0:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Experiment EMA period is invalid"
            )
        v2 = (
            getattr(snapshot, "snapshot_schema", None)
            == "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2"
        )
        try:
            if v2:
                venue = session.get(VenueInstrumentModel, snapshot.venue_instrument_id)
                instrument = (
                    session.get(InstrumentModel, venue.instrument_id) if venue else None
                )
                if venue is None or instrument is None:
                    raise ValueError("snapshot lineage is incomplete")
                all_bars = tuple(
                    Bar(
                        instrument=Instrument(instrument.code),
                        provider=Provider(venue.provider),
                        timeframe=Timeframe.M15,
                        price_component=PriceComponent.MID,
                        start_time=row.start_time,
                        end_time=row.end_time,
                        open=row.open_price,
                        high=row.high_price,
                        low=row.low_price,
                        close=row.close_price,
                        volume=row.volume,
                    )
                    for row in session.scalars(
                        select(DatasetSnapshotAnalyticalBarModel)
                        .where(
                            DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id
                            == snapshot.id
                        )
                        .order_by(DatasetSnapshotAnalyticalBarModel.sequence)
                    ).all()
                )
            else:
                all_bars = self.market_data.derive_m15(
                    snapshot.fingerprint, PriceComponent.MID
                )
            warmup = tuple(
                bar for bar in all_bars if bar.end_time <= experiment.trading_start
            )
            window = tuple(
                bar
                for bar in all_bars
                if experiment.trading_start < bar.end_time <= experiment.trading_end
            )
            if len(warmup) < version.warm_up_bars:
                raise ValueError("strategy warm-up history is incomplete")
            bars = (
                warmup[-version.warm_up_bars :] + window
                if version.warm_up_bars
                else window
            )
            if not bars or any(
                a.end_time >= b.end_time for a, b in zip(bars, bars[1:], strict=False)
            ):
                raise ValueError("M15 history is not ordered")
        except Exception as exc:
            raise ResultReadError("INCOMPLETE_RESULT", "M15 derivation failed") from exc

        truncated = len(bars) > 10000
        returned_bars = bars[:10000]
        ema_points = tuple(
            {"t": bar.end_time, "v": str(ema(returned_bars[: index + 1], raw_period))}
            for index, bar in enumerate(returned_bars)
            if index + 1 >= raw_period
        )
        m15 = tuple(
            {
                "t": bar.end_time,
                "o": str(bar.open),
                "h": str(bar.high),
                "l": str(bar.low),
                "c": str(bar.close),
            }
            for bar in returned_bars
        )

        source_trades = self.results.trades(session, experiment.id, 251)
        trade_cap = len(source_trades) > 250
        trade_rows = source_trades[:250]
        trade_values: list[dict[str, object]] = []
        reference_values: list[dict[str, object]] = []
        omitted_facts = 0
        for row in trade_rows:
            intent = self.results.intent(session, row)
            risks = self.results.risks(session, intent.id) if intent else ()
            approved = next(
                (
                    risk
                    for risk in risks
                    if risk.phase == "PRE_SUBMISSION" and risk.outcome == "APPROVED"
                ),
                None,
            )
            end = row.closed_at or experiment.trading_end
            trade_values.append(
                {
                    "sequence": row.sequence_number,
                    "direction": row.direction,
                    "entry": {"t": row.opened_at, "price": str(row.entry_price)},
                    "exit": (
                        None
                        if row.closed_at is None
                        else {"t": row.closed_at, "price": str(row.exit_price)}
                    ),
                    "stop": (
                        None
                        if approved is None or approved.stop_price is None
                        else {
                            "price": str(approved.stop_price),
                            "from": row.opened_at,
                            "to": end,
                        }
                    ),
                    "target": (
                        None
                        if approved is None or approved.target_price is None
                        else {
                            "price": str(approved.target_price),
                            "from": row.opened_at,
                            "to": end,
                        }
                    ),
                }
            )
            fact = self._rationale_facts(
                getattr(intent, "rationale", None) if intent else None, row
            )
            if fact is None:
                omitted_facts += 1
            else:
                reference_values.append(fact)

        omitted_range = None
        if truncated:
            omitted_range = {"start": bars[10000].end_time, "end": bars[-1].end_time}
        diagnostics = {
            "truncated": truncated or trade_cap or omitted_facts > 0,
            "ema_period": raw_period,
            "warm_up_bars": version.warm_up_bars,
            "snapshot_fingerprint": snapshot.fingerprint,
            "m15_eligible_count": len(bars),
            "m15_returned_count": len(returned_bars),
            "trade_eligible_count": len(source_trades),
            "trade_returned_count": len(trade_values),
            "omitted_range": omitted_range,
            "omitted_m15_count": max(0, len(bars) - len(returned_bars)),
            "omitted_trade_count": (
                max(0, len(source_trades) - len(trade_rows)) + omitted_facts
            ),
        }
        gap_reader = getattr(self.results, "gap_decisions", None)
        gap_rows = gap_reader(session, experiment.id) if gap_reader else ()
        gaps = tuple(
            {
                "sequence": row.sequence,
                "start": row.start_time,
                "end": row.end_time,
                "resolution": row.resolution,
                "component": row.price_component,
                "classification": row.classification,
                "blocked": row.blocked,
                "policyVersion": row.policy_version,
                "ruleVersion": row.rule_version,
                "affectedState": row.affected_state,
                "affectedEvent": row.affected_event,
                "details": row.details,
            }
            for row in gap_rows
        )
        provenance = {
            "snapshotSchema": getattr(
                snapshot, "snapshot_schema", "ATLAS_HISTORICAL_SNAPSHOT_V1"
            ),
            "fingerprintSchema": getattr(
                snapshot, "fingerprint_schema", "ATLAS_DATASET_SHA256_V1"
            ),
            "analyticalSeries": "PERSISTED_NATIVE_M15_MID"
            if v2
            else "DERIVED_M15_FROM_V1_M1",
            "executionSeries": "SPARSE_PROVIDER_M1_BID_ASK"
            if v2
            else "V1_M1_BID_ASK_MID",
            "gapPolicyVersion": snapshot.integrity_summary.get("policy_version")
            if v2
            else None,
        }
        return PriceAnalysisRead(
            m15,
            ema_points,
            {"start": experiment.trading_start, "end": experiment.trading_end},
            tuple(trade_values),
            tuple(reference_values),
            diagnostics,
            provenance,
            gaps,
        )

    @staticmethod
    def _rationale_facts(
        rationale: object, trade: TradeModel
    ) -> dict[str, object] | None:
        fields = rationale.get("fields") if isinstance(rationale, dict) else None
        items = fields.items() if isinstance(fields, dict) else fields
        if not isinstance(items, (list, tuple)) and not hasattr(items, "__iter__"):
            return None
        try:
            values = dict(items)
            facts: dict[str, dict[str, object] | None] = {}
            for stage in ("reference", "sweep", "confirmation"):
                timestamp = datetime.fromisoformat(
                    str(values[f"{stage}_time"]).replace("Z", "+00:00")
                )
                if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(
                    timestamp
                ):
                    return None
                timestamp = timestamp.astimezone(UTC)
                high = Decimal(str(values[f"{stage}_high"]))
                low = Decimal(str(values[f"{stage}_low"]))
                if not high.is_finite() or not low.is_finite():
                    return None
                facts[stage] = {"t": timestamp, "high": str(high), "low": str(low)}
            return {"trade_sequence": trade.sequence_number, **facts}
        except (KeyError, TypeError, ValueError, ArithmeticError):
            return None

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
        snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
        if snapshot is None:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Dataset snapshot is unavailable"
            )
        if (
            getattr(snapshot, "snapshot_schema", None)
            == "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2"
        ):
            venue = session.get(VenueInstrumentModel, snapshot.venue_instrument_id)
            instrument = (
                session.get(InstrumentModel, venue.instrument_id) if venue else None
            )
            if venue is None or instrument is None:
                raise ResultReadError(
                    "INCOMPLETE_RESULT", "Dataset snapshot lineage is incomplete"
                )
            m15 = tuple(
                Bar(
                    instrument=Instrument(instrument.code),
                    provider=Provider(venue.provider),
                    timeframe=Timeframe.M15,
                    price_component=PriceComponent.MID,
                    start_time=row.start_time,
                    end_time=row.end_time,
                    open=row.open_price,
                    high=row.high_price,
                    low=row.low_price,
                    close=row.close_price,
                    volume=row.volume,
                )
                for row in session.scalars(
                    select(DatasetSnapshotAnalyticalBarModel)
                    .where(
                        DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id
                        == snapshot.id
                    )
                    .order_by(DatasetSnapshotAnalyticalBarModel.sequence)
                ).all()
            )
        else:
            bars = self.snapshots.ordered_members_with_sources(
                session,
                experiment.dataset_snapshot_id,
                None,
                None,
                (PriceComponent.MID,),
            )
            try:
                aggregated = aggregate_m1_to_m15(
                    tuple(item.bar for item in bars),
                    PriceComponent.MID,
                    snapshot.coverage_start,
                    snapshot.coverage_end,
                )
                m15 = aggregated[0] if isinstance(aggregated[0], list) else aggregated
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
