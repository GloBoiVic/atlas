"""Stateless, bounded composition of completed Experiment comparisons."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.persistence.models import (
    DatasetSnapshotModel,
    ExperimentModel,
    InstrumentModel,
    StrategyVersionModel,
    VenueInstrumentModel,
)
from backend.persistence.result_repository import ExperimentResultRepository

from .results import ExperimentResultReadService, ResultReadError


def _metrics_payload(metrics: Any) -> dict[str, Any] | None:
    if metrics is None:
        return None
    if isinstance(metrics, dict):
        return metrics
    names = {
        "netReturn": "net_return",
        "maxDrawdownAmount": "max_drawdown_amount",
        "maxDrawdownPercent": "max_drawdown_percent",
        "sharpe": "sharpe_ratio",
        "profitFactor": "profit_factor",
        "winRate": "win_rate",
        "expectancy": "expectancy_net_pnl",
    }
    return {
        **{
            output: getattr(metrics, source).as_dict()
            for output, source in names.items()
        },
        "tradeCount": {
            "state": "VALUE",
            "value": str(metrics.trade_count),
            "unit": "trades",
            "reason": None,
        },
    }


WARNING_DEFINITIONS = (
    (
        "STRATEGY_VERSION_DIFFERS",
        "Methodology differs because the StrategyVersion changed.",
    ),
    ("INSTRUMENT_DIFFERS", "The canonical trading Instrument differs."),
    ("DATASET_SNAPSHOT_DIFFERS", "Historical DatasetSnapshot provenance differs."),
    ("TRADING_PERIOD_DIFFERS", "The UTC trading period differs."),
    ("RISK_CONFIG_DIFFERS", "Risk assumptions differ."),
    ("STARTING_CAPITAL_DIFFERS", "The starting capital or base currency differs."),
    ("SIMULATION_CONFIG_DIFFERS", "Simulation assumptions differ."),
    ("MODEL_VERSION_DIFFERS", "The Experiment execution model differs."),
    ("METRIC_CONTRACT_DIFFERS", "Displayed metric contracts differ."),
)


class ComparisonReadError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ComparisonDifference:
    path: str
    values: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class ComparisonWarning:
    code: str
    severity: str
    explanation: str
    paths: tuple[str, ...]


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _canonical(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {
            str(k): _canonical(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(item) for item in value)
    return value


def _equal(left: object, right: object, *, decimal: bool = False) -> bool:
    if decimal:
        try:
            return _decimal(left) == _decimal(right)
        except (ArithmeticError, ValueError):
            return False
    return _canonical(left) == _canonical(right)


class ExperimentComparisonReadService:
    """Read and compose at most four immutable completed Experiment facts."""

    def __init__(
        self,
        *,
        results: ExperimentResultRepository | None = None,
        result_service: ExperimentResultReadService | None = None,
    ) -> None:
        self.results = results or ExperimentResultRepository()
        self.result_service = result_service or ExperimentResultReadService(
            results=self.results
        )

    def compare(
        self, session: Session, experiment_ids: tuple[UUID, ...]
    ) -> dict[str, object]:
        if (
            len(experiment_ids) < 2
            or len(experiment_ids) > 4
            or len(set(experiment_ids)) != len(experiment_ids)
        ):
            raise ComparisonReadError(
                "COMPARISON_SELECTION_INVALID",
                "Comparison requires two to four distinct Experiment IDs.",
                {
                    "count": len(experiment_ids),
                    "experimentIds": [str(item) for item in experiment_ids],
                },
            )
        rows: list[ExperimentModel] = []
        for experiment_id in experiment_ids:
            row = self.results.experiment(session, experiment_id)
            if row is None:
                raise ComparisonReadError(
                    "EXPERIMENT_NOT_FOUND",
                    "Experiment does not exist.",
                    {"experimentId": str(experiment_id)},
                )
            if row.status != "COMPLETED":
                raise ComparisonReadError(
                    "EXPERIMENT_NOT_COMPLETED",
                    "Only COMPLETED Experiments can be compared.",
                    {"experimentId": str(experiment_id), "status": row.status},
                )
            rows.append(row)

        entries = [self._entry(session, row, index) for index, row in enumerate(rows)]
        facts = [entry["facts"] for entry in entries]
        differences: list[ComparisonDifference] = []
        warning_paths: dict[str, list[str]] = {
            code: [] for code, _ in WARNING_DEFINITIONS
        }

        dimensions = (
            (
                "strategyVersionId",
                "strategy_version_id",
                False,
                "STRATEGY_VERSION_DIFFERS",
            ),
            ("instrument", "instrument", False, "INSTRUMENT_DIFFERS"),
            ("datasetSnapshot", "dataset_snapshot", False, "DATASET_SNAPSHOT_DIFFERS"),
            ("tradingPeriod", "trading_period", False, "TRADING_PERIOD_DIFFERS"),
            ("risk", "risk", False, "RISK_CONFIG_DIFFERS"),
            ("startingCapital", "starting_capital", False, "STARTING_CAPITAL_DIFFERS"),
            ("simulation", "simulation", False, "SIMULATION_CONFIG_DIFFERS"),
            ("modelVersion", "model_version", False, "MODEL_VERSION_DIFFERS"),
            ("metricContract", "metric_contract", False, "METRIC_CONTRACT_DIFFERS"),
        )
        for path, key, _, warning in dimensions:
            first = facts[0][key]
            if any(not _equal(first, item[key]) for item in facts[1:]):
                differences.append(
                    ComparisonDifference(
                        path,
                        tuple(
                            (entry["slot"], fact[key])
                            for entry, fact in zip(entries, facts, strict=True)
                        ),
                    )
                )
                warning_paths[warning].append(path)

        parameter_keys = sorted({key for fact in facts for key in fact["parameters"]})
        changed_parameters: list[str] = []
        for key in parameter_keys:
            values = tuple(
                (entry["slot"], fact["parameters"].get(key))
                for entry, fact in zip(entries, facts, strict=True)
            )
            descriptors = [fact["parameter_types"].get(key) for fact in facts]
            same = all(
                _equal(
                    values[0][1],
                    value,
                    decimal=all(
                        item == "decimal" for item in descriptors if item is not None
                    ),
                )
                and descriptors[0] == descriptor
                for (_, value), descriptor in zip(
                    values[1:], descriptors[1:], strict=True
                )
            )
            if not same:
                changed_parameters.append(key)
                differences.append(ComparisonDifference(f"parameters.{key}", values))

        warnings = tuple(
            ComparisonWarning(code, "CAUTION", explanation, tuple(paths))
            for code, explanation in WARNING_DEFINITIONS
            if (paths := warning_paths[code])
        )
        strong = not warnings and len(changed_parameters) == 1
        return {
            "experiments": tuple(
                {key: value for key, value in entry.items() if key != "facts"}
                for entry in entries
            ),
            "differences": tuple(differences),
            "warnings": warnings,
            "changedParameterKeys": tuple(changed_parameters),
            "strongParameterIsolation": strong,
        }

    def _entry(
        self, session: Session, row: ExperimentModel, index: int
    ) -> dict[str, object]:
        version = session.get(StrategyVersionModel, row.strategy_version_id)
        instrument_link = session.get(VenueInstrumentModel, row.venue_instrument_id)
        instrument = (
            session.get(InstrumentModel, instrument_link.instrument_id)
            if instrument_link
            else None
        )
        snapshot = session.get(DatasetSnapshotModel, row.dataset_snapshot_id)
        if version is None or instrument is None or snapshot is None:
            raise ComparisonReadError(
                "COMPARISON_RESULT_UNAVAILABLE",
                "Completed Experiment facts are inconsistent.",
                {"experimentId": str(row.id)},
            )
        try:
            composed = self.result_service.detail(session, row.id)
        except ResultReadError as exc:
            raise ComparisonReadError(
                "COMPARISON_RESULT_UNAVAILABLE", str(exc), {"experimentId": str(row.id)}
            ) from exc
        result = composed.get("result")
        if result is None or composed.get("metrics") is None:
            raise ComparisonReadError(
                "COMPARISON_RESULT_UNAVAILABLE",
                "Completed Experiment result facts are unavailable.",
                {"experimentId": str(row.id)},
            )
        parameter_types = {
            item.get("key"): item.get("type") for item in version.parameter_schema
        }
        base_currency = "USD"
        facts = {
            "strategy_version_id": row.strategy_version_id,
            "instrument": {"id": instrument.id, "code": instrument.code},
            "dataset_snapshot": {
                "id": snapshot.id,
                "fingerprint": snapshot.fingerprint,
            },
            "trading_period": {"start": row.trading_start, "end": row.trading_end},
            "parameters": row.parameter_snapshot,
            "parameter_types": parameter_types,
            "starting_capital": {
                "value": row.starting_capital,
                "currency": base_currency,
            },
            "risk": {"riskPerTrade": row.risk_per_trade, "config": row.risk_config},
            "simulation": row.simulation_config,
            "model_version": row.model_version,
            "metric_contract": {
                "result": result.result_schema_version,
                "metrics": result.metric_schema_version,
            },
        }
        identity = {
            "id": row.id,
            "label": (
                f"{version.strategy.name} v{version.version_number} · "
                f"{row.created_at:%d %b %Y %H:%M UTC}"
            ),
            "strategy": {
                "key": version.strategy.strategy_key,
                "name": version.strategy.name,
                "version": version.version_number,
                "versionId": version.id,
                "implementationKey": version.implementation_key,
                "sourceFingerprint": version.source_fingerprint,
            },
            "instrument": facts["instrument"],
            "datasetSnapshot": facts["dataset_snapshot"],
            "tradingPeriod": facts["trading_period"],
            "parameters": row.parameter_snapshot,
            "startingCapital": facts["starting_capital"],
            "risk": facts["risk"],
            "simulation": row.simulation_config,
            "modelVersion": row.model_version,
            "metricContract": facts["metric_contract"],
            "metrics": _metrics_payload(composed["metrics"]),
        }
        return {"slot": chr(65 + index), "facts": facts, **identity}
