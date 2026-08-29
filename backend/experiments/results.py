"""Authoritative read composition for completed Experiment inspection."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    SNAPSHOT_SCHEMA_V1,
    SNAPSHOT_SCHEMA_V2,
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.market_data.aggregation import AggregationError, aggregate_m1_to_m15
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
    # These are persisted Strategy facts, never reconstructed by the reader.
    evidence: tuple[dict[str, object], ...] = ()
    landmarks: tuple[dict[str, object], ...] = ()
    proposal_diagnostics: tuple[dict[str, object], ...] = ()
    setup_facts: tuple[dict[str, object], ...] = ()


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
        strategy_version = (
            self.results.strategy_version(session, experiment.strategy_version_id)
            if hasattr(self.results, "strategy_version")
            else session.get(StrategyVersionModel, experiment.strategy_version_id)
            if session is not None
            else None
        )
        if experiment.status == "COMPLETED":
            result = self.results.result(session, experiment_id)
            if result is None:
                raise ResultReadError(
                    "INCOMPLETE_RESULT", "Completed Experiment result is unavailable"
                )
            metrics = self._persisted_metrics(result)
        return {"experiment": experiment, "result": result, "metrics": metrics,
                "strategy_version": strategy_version}

    @staticmethod
    def _persisted_metrics(result: object) -> dict[str, object]:
        """Project the immutable result row without reopening financial facts."""
        states = getattr(result, "metric_states", {})
        if not isinstance(states, dict) or not states:
            return {}
        names = (
            ("netReturn", "net_return", "net_return"),
            ("maxDrawdownAmount", "max_drawdown_amount", "max_drawdown_amount"),
            ("maxDrawdownPercent", "max_drawdown_percent", "max_drawdown_percent"),
            ("sharpe", "sharpe_ratio", "sharpe_ratio"),
            ("profitFactor", "profit_factor", "profit_factor"),
            ("winRate", "win_rate", "win_rate"),
            ("expectancy", "expectancy_net_pnl", "expectancy_net_pnl"),
        )
        metrics: dict[str, object] = {}
        for output, key, column in names:
            state = states.get(key, {}) if isinstance(states, dict) else {}
            if not isinstance(state, dict):
                state = {"state": state, "reason": "LEGACY_RESULT"}
            value = getattr(result, column, None)
            metrics[output] = {
                "state": state.get("state"),
                "value": None if value is None else str(value),
                "unit": state.get("unit", "ratio"),
                "reason": state.get("reason"),
            }
        metrics["tradeCount"] = {
            "state": "VALUE", "value": str(getattr(result, "trade_count", 0)),
            "unit": "trades", "reason": None,
        }
        return metrics

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
        schema = getattr(snapshot, "snapshot_schema", None)
        v2 = schema == SNAPSHOT_SCHEMA_V2
        context_bars = version.required_historical_context_bars
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
            elif schema == SNAPSHOT_SCHEMA_V1:
                all_bars = self._legacy_v1_m15(session, snapshot)
            else:
                raise ValueError("unsupported dataset snapshot schema")
            warmup = tuple(
                bar for bar in all_bars if bar.end_time <= experiment.trading_start
            )
            window = tuple(
                bar
                for bar in all_bars
                if experiment.trading_start < bar.end_time <= experiment.trading_end
            )
            if len(warmup) < context_bars:
                raise ValueError("strategy warm-up history is incomplete")
            bars = (
                warmup[-context_bars:] + window
                if context_bars
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
        evidence_values: list[dict[str, object]] = []
        landmark_values: list[dict[str, object]] = []
        proposal_values: list[dict[str, object]] = []
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
            proposal_values.append(self._proposal_payload(intent, row))
            rationale = getattr(intent, "rationale", None) if intent else None
            if isinstance(rationale, dict):
                persisted_evidence = rationale.get("evidence", ())
                if isinstance(persisted_evidence, dict):
                    evidence_values.append({
                        "trade_sequence": row.sequence_number,
                        "setup": persisted_evidence,
                    })
                elif isinstance(persisted_evidence, (list, tuple)):
                    evidence_values.extend(
                        {"trade_sequence": row.sequence_number, "setup": item}
                        for item in persisted_evidence if isinstance(item, dict)
                    )
                persisted_landmarks = rationale.get("landmarks", ())
                if isinstance(persisted_landmarks, (list, tuple)):
                    for item in persisted_landmarks:
                        if not isinstance(item, dict):
                            continue
                        marker = dict(item)
                        marker["trade_sequence"] = row.sequence_number
                        if "time" not in marker and "timestamp" in marker:
                            marker["time"] = marker.pop("timestamp")
                        landmark_values.append(marker)
            fact = self._rationale_facts(
                rationale, row
            )
            if fact is None:
                omitted_facts += 1
            else:
                reference_values.append(fact)
                if not isinstance(rationale, dict) or not rationale.get("evidence"):
                    evidence_values.append({"trade_sequence": row.sequence_number, "setup": fact})
                landmark_values.append({"kind": "entry", "trade_sequence": row.sequence_number,
                                        "time": row.opened_at, "price": str(row.entry_price)})
                if approved is not None:
                    for kind, price in (("stop", approved.stop_price), ("target", approved.target_price)):
                        if price is not None:
                            landmark_values.append({"kind": kind, "trade_sequence": row.sequence_number,
                                                    "time": row.opened_at, "price": str(price)})
                if row.closed_at is not None and row.exit_price is not None:
                    landmark_values.append({"kind": "exit", "trade_sequence": row.sequence_number,
                                            "time": row.closed_at, "price": str(row.exit_price)})

        omitted_range = None
        if truncated:
            omitted_range = {"start": bars[10000].end_time, "end": bars[-1].end_time}
        result_row = self.results.result(session, experiment.id)
        diagnostics = {
            "truncated": truncated or trade_cap or omitted_facts > 0,
            "ema_period": raw_period,
            "required_historical_context_bars": (
                context_bars
            ),
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
            "modelVersion": experiment.model_version,
            "resultSchemaVersion": getattr(
                result_row, "result_schema_version", None
            ),
            "metricSchemaVersion": getattr(result_row, "metric_schema_version", None),
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
            "quality": getattr(result_row, "result_quality", None),
            "gapCount": len(gaps),
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
            tuple(evidence_values),
            tuple(landmark_values),
            tuple(proposal_values),
            tuple(reference_values),
        )

    def _legacy_v1_m15(
        self, session: Session, snapshot: DatasetSnapshotModel
    ) -> tuple[Bar, ...]:
        """Read immutable V1 membership for legacy chart and price views only."""
        if snapshot.snapshot_schema != SNAPSHOT_SCHEMA_V1:
            raise ValueError("legacy reader requires a V1 dataset snapshot")
        members = self.snapshots.ordered_members_with_sources(
            session,
            snapshot.id,
            None,
            None,
            (PriceComponent.MID,),
        )
        bars, _diagnostics = aggregate_m1_to_m15(
            tuple(item.bar for item in members),
            PriceComponent.MID,
            snapshot.coverage_start,
            snapshot.coverage_end,
        )
        return tuple(bars)

    @staticmethod
    def _proposal_payload(intent: object | None, trade: TradeModel) -> dict[str, object]:
        """Expose the immutable proposal and its terminal read-side status."""
        if intent is None:
            return {"tradeSequence": trade.sequence_number, "proposalStatus": "INCOMPLETE"}
        expiry = getattr(intent, "expiry_time", None)
        return {
            "tradeSequence": trade.sequence_number,
            "entryPolicy": getattr(intent, "entry_policy", None),
            "triggerPrice": _decimal(getattr(intent, "trigger_price", None)),
            "triggerPriceBasis": getattr(intent, "trigger_price_basis", None),
            "expiry": expiry,
            "expiryBars": getattr(intent, "expiry_bars", None),
            "proposalStatus": getattr(intent, "proposal_status", "UNKNOWN"),
            "diagnostics": getattr(intent, "diagnostics", {}),
        }

    @staticmethod
    def _rationale_facts(
        rationale: object, trade: TradeModel
    ) -> dict[str, object] | None:
        if isinstance(rationale, dict) and isinstance(rationale.get("setup_facts"), dict):
            setup = rationale["setup_facts"]
            result: dict[str, object] = {"trade_sequence": trade.sequence_number}
            try:
                for stage in ("reference", "sweep", "confirmation"):
                    candle = setup[stage]
                    timestamp = datetime.fromisoformat(str(candle["timestamp"]).replace("Z", "+00:00"))
                    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
                        return None
                    result[stage] = {
                        "t": timestamp.astimezone(UTC),
                        "open": str(Decimal(str(candle["open"]))),
                        "high": str(Decimal(str(candle["high"]))),
                        "low": str(Decimal(str(candle["low"]))),
                        "close": str(Decimal(str(candle["close"]))),
                    }
                result["trendRelation"] = setup.get("trend_relation")
                result["atr"] = str(Decimal(str(setup["atr"])))
                result["stopPrice"] = str(Decimal(str(setup["stop_price"])))
                result["triggerPrice"] = str(Decimal(str(setup["trigger_price"])))
                return result
            except (KeyError, TypeError, ValueError, ArithmeticError):
                return None
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
            "entryPolicy": self._proposal_payload(intent, row),
            "setupFacts": self._rationale_facts(getattr(intent, "rationale", None), row),
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
            == SNAPSHOT_SCHEMA_V2
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
        elif getattr(snapshot, "snapshot_schema", None) == SNAPSHOT_SCHEMA_V1:
            try:
                m15 = self._legacy_v1_m15(session, snapshot)
            except (AggregationError, ValueError):
                m15 = ()
        else:
            raise ResultReadError(
                "INCOMPLETE_RESULT", "Dataset snapshot schema is unsupported"
            )
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
        candles: tuple[dict[str, object], ...] = tuple(
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
