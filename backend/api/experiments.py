"""FastAPI composition for the Experiment workflow."""

# Route signatures intentionally use FastAPI's dependency defaults; this keeps
# dependencies visible and replaceable in the app factory.
# ruff: noqa: E501, B008

import base64
import binascii
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.experiments.comparison import (
    ComparisonReadError,
    ExperimentComparisonReadService,
)
from backend.experiments.configuration import (
    ConfigurationError,
    ExperimentConfigurationService,
)
from backend.experiments.lifecycle import (
    ExperimentRunInfrastructureError,
    ExperimentRunService,
)
from backend.experiments.results import ExperimentResultReadService, ResultReadError
from backend.market_data.coverage import diagnostic_payloads
from backend.persistence.database import session_scope
from backend.persistence.models import (
    DatasetSnapshotModel,
    ExperimentModel,
    InstrumentModel,
    VenueInstrumentModel,
)
from backend.persistence.result_repository import ExperimentResultRepository
from backend.persistence.strategy_repository import StrategyRepository
from backend.strategies.registry import StrategyVersionUnavailableError

from .schemas import (
    ExperimentComparisonResponse,
    ExperimentConfigurationOptionsResponse,
    ExperimentCreateRequest,
    ExperimentListResponse,
    ExperimentReadResponse,
    PeriodRequest,
    PriceAnalysisResponse,
)


def _utc(value: datetime) -> str:
    # Database timestamps are persisted UTC instants.  A naive value is only
    # accepted as that explicit storage representation; local wall time is
    # never guessed or converted.
    instant = (
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    )
    return instant.isoformat().replace("+00:00", "Z")


def _cursor(row: ExperimentModel) -> str:
    payload = json.dumps(
        {"createdAt": _utc(row.created_at), "id": str(row.id)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if set(payload) != {"createdAt", "id"}:
            raise ValueError
        created_at = datetime.fromisoformat(payload["createdAt"].replace("Z", "+00:00"))
        if created_at.tzinfo is None or created_at.utcoffset() != UTC.utcoffset(
            created_at
        ):
            raise ValueError
        return created_at.astimezone(UTC), UUID(payload["id"])
    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ) as exc:
        raise _error("INVALID_CURSOR", "cursor is invalid", http_status=422) from exc


def _decimal(value: Any) -> str | None:
    return None if value is None else str(Decimal(value))


def _json(value: Any) -> Any:
    """Convert read-service dataclasses/ORM rows without exposing internals."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (UUID, datetime)):
        return str(value) if isinstance(value, UUID) else _utc(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    if is_dataclass(value):
        return _json(asdict(value))
    mapper = getattr(value, "__mapper__", None)
    if mapper is not None:
        return {
            column.key: _json(getattr(value, column.key)) for column in mapper.columns
        }
    if hasattr(value, "__dict__"):
        return {
            key: _json(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def _failure(row: ExperimentModel) -> dict[str, Any] | None:
    if row.status != "FAILED":
        return None
    return {
        "category": row.failure_category,
        "code": row.failure_code,
        "detail": row.failure_detail,
    }


def _identity(
    db: Session,
    row: ExperimentModel,
    strategy_version: Any = None,
    *,
    snapshot: Any = None,
    venue: Any = None,
    instrument: Any = None,
) -> dict[str, Any]:
    """Expose immutable Experiment identity assembled from persisted facts."""
    if snapshot is None:
        snapshot = db.get(DatasetSnapshotModel, row.dataset_snapshot_id)
    if venue is None and snapshot is not None:
        venue = db.get(VenueInstrumentModel, snapshot.venue_instrument_id)
    if instrument is None and venue is not None:
        instrument = db.get(InstrumentModel, venue.instrument_id)
    components = snapshot.components if snapshot is not None else []
    strategy = (
        None
        if strategy_version is None
        else {
            "id": str(strategy_version.id),
            "displayName": f"{strategy_version.strategy.name} v{strategy_version.version_number}",
            "key": strategy_version.strategy.strategy_key,
            "version": strategy_version.version_number,
        }
    )
    return {
        "strategyVersion": strategy,
        "instrument": (
            None
            if instrument is None
            else {
                "code": instrument.code,
                "baseCurrency": instrument.base_currency,
                "quoteCurrency": instrument.quote_currency,
            }
        ),
        "analytical": {
            "resolution": snapshot.base_resolution if snapshot is not None else None,
            "priceComponent": components[0] if components else None,
        },
        "provider": (
            None
            if venue is None
            else {"name": venue.provider, "symbol": venue.provider_symbol}
        ),
        "tradingPeriod": {
            "start": _utc(row.trading_start),
            "end": _utc(row.trading_end),
        },
    }


def _detail(
    row: ExperimentModel, metrics: Any = None, result: Any = None,
    gap_decisions: Any = (), strategy_version: Any = None,
    identity: Any = None,
) -> dict[str, Any]:
    result_payload = _json(result)
    result_quality = getattr(result, "result_quality", None)
    if result_quality is None and isinstance(result_payload, dict):
        result_quality = result_payload.get("result_quality")
    if result_quality is None and row.status == "FAILED":
        result_quality = {"schema": "ATLAS_RESULT_QUALITY_V1", "value": "FAILED"}
    result_schema_version = getattr(result, "result_schema_version", None)
    if result_schema_version is None and isinstance(result_payload, dict):
        result_schema_version = result_payload.get("result_schema_version")
    gap_decisions = _json(gap_decisions)
    payload: dict[str, Any] = {
        "id": str(row.id),
        "label": f"Experiment · {_utc(row.trading_start)[:10]} → {_utc(row.trading_end)[:10]}",
        "status": row.status,
        "createdAt": _utc(row.created_at),
        "completedAt": _utc(row.completed_at) if row.completed_at else None,
        "tradingStart": _utc(row.trading_start),
        "tradingEnd": _utc(row.trading_end),
        "strategyVersionId": str(row.strategy_version_id),
        "strategy": (
            None if strategy_version is None else {
                "key": strategy_version.strategy.strategy_key,
                "name": strategy_version.strategy.name,
                "version": strategy_version.version_number,
                "displayName": f"{strategy_version.strategy.name} v{strategy_version.version_number}",
                "implementationKey": strategy_version.implementation_key,
                "sourceFingerprint": strategy_version.source_fingerprint,
            }
        ),
        "identity": identity or {},
        "datasetSnapshotId": str(row.dataset_snapshot_id),
        "startingCapital": str(row.starting_capital),
        "riskPerTrade": str(row.risk_per_trade),
        "parameters": row.parameter_snapshot,
        "riskConfig": row.risk_config,
        "simulationConfig": row.simulation_config,
        "modelVersion": row.model_version,
        "failure": _failure(row),
        "metrics": metrics,
        "result": result_payload,
        "resultQuality": result_quality,
        "resultSchemaVersion": result_schema_version,
        "gapDecisions": gap_decisions,
        "provenance": {
            "strategyVersionId": str(row.strategy_version_id),
            "datasetSnapshotId": str(row.dataset_snapshot_id),
            "requestedPeriod": {
                "start": _utc(row.trading_start),
                "end": _utc(row.trading_end),
            },
            "startingCapital": str(row.starting_capital),
            "baseCurrency": "USD",
            "risk": row.risk_config,
            "simulation": row.simulation_config,
            "modelVersion": row.model_version,
            "resultSchemaVersion": result_schema_version,
            "quality": result_quality,
            "gapCount": len(gap_decisions),
        },
    }
    return payload


def _metrics_payload(metrics: Any) -> dict[str, Any] | None:
    if metrics is None:
        return None
    if isinstance(metrics, dict):
        return metrics
    metric_names = {
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
            for output, source in metric_names.items()
        },
        "tradeCount": {
            "state": "VALUE",
            "value": str(metrics.trade_count),
            "unit": "trades",
            "reason": None,
        },
    }


def _error(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    http_status: int = 400,
) -> HTTPException:
    return HTTPException(
        http_status,
        {"error": {"code": code, "message": message, "details": details or {}}},
    )


def create_experiment_router(
    *,
    session_factory: Any,
    configuration: ExperimentConfigurationService,
    lifecycle: ExperimentRunService,
    results: ExperimentResultReadService,
    strategies: StrategyRepository | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])
    result_repo = ExperimentResultRepository()
    strategy_repo = strategies or StrategyRepository()
    comparison = ExperimentComparisonReadService(
        results=result_repo, result_service=results
    )

    def session() -> Any:
        with session_scope(session_factory) as db:
            yield db

    @router.get(
        "/configuration-options", response_model=ExperimentConfigurationOptionsResponse
    )
    def options(db: Session = Depends(session)) -> dict[str, Any]:
        versions = []
        for row in strategy_repo.list_all_versions(db):
            try:
                registration = configuration.registry.get(
                    row.strategy.strategy_key,
                    implementation_key=row.implementation_key,
                    source_fingerprint=row.source_fingerprint,
                )
            except StrategyVersionUnavailableError:
                # Configuration options are executable catalog entries, not a
                # version-suffix allowlist.  This keeps the API aligned with
                # the exact immutable StrategyVersion provenance in the
                # registry.
                continue
            versions.append(
                {
                    "id": str(row.id),
                    "strategyKey": row.strategy.strategy_key,
                    "name": row.strategy.name,
                    "version": row.version_number,
                    "displayName": f"{row.strategy.name} v{row.version_number}",
                    "createdAt": _utc(row.created_at),
                    "implementationKey": row.implementation_key,
                    "sourceFingerprint": row.source_fingerprint,
                    "parameterSchema": row.parameter_schema,
                    "requiredHistoricalContextBars": row.required_historical_context_bars,
                    "architecture": "HISTORICAL_EXECUTION",
                    "executionAvailable": True,
                    "unavailableReason": None,
                    "marketRequirements": {
                        "instrument": registration.definition.required_instrument.value,
                        "resolution": registration.definition.required_resolution.value,
                        "priceComponent": registration.definition.required_price_component.value,
                        "requiredHistoricalContextBars": row.required_historical_context_bars,
                        "completedOnly": registration.definition.completed_only,
                    },
                }
            )
        snapshots = []
        for snapshot in configuration.snapshots.list_options(db):
            if snapshot.snapshot_schema != "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2":
                continue
            snapshots.append(
                {
                    "id": str(snapshot.id),
                    "fingerprint": snapshot.fingerprint,
                    "coverageStart": _utc(snapshot.coverage_start),
                    "coverageEnd": _utc(snapshot.coverage_end),
                    "snapshotSchema": snapshot.snapshot_schema,
                    "integrity": snapshot.integrity_summary,
                }
            )
        return {
            "strategyVersions": versions,
            "datasetSnapshots": snapshots,
            "defaults": {
                "startingCapital": "10000",
                "riskPerTrade": "0.01",
                "slippageTicks": 0,
                "commissionPerUnit": "0",
            },
            "simulationAssumptions": {
                "executionResolution": "M1",
                "analysisComponent": "MID",
                "executionComponents": ["BID", "ASK"],
                "financing": "FINANCING EXCLUDED",
            },
        }

    @router.post("/coverage-validations")
    def coverage(
        request: PeriodRequest, db: Session = Depends(session)
    ) -> dict[str, Any]:
        try:
            value = configuration.validate_coverage(db, **request.model_dump())
        except ConfigurationError as exc:
            raise _error(exc.code, str(exc), http_status=422) from exc
        report = value.report
        diagnostics, diagnostics_truncated = (
            diagnostic_payloads(report) if report else ([], False)
        )
        policy_version = (
            diagnostics[0].get("policy_version", "ATLAS_HISTORICAL_GAP_POLICY_V1")
            if diagnostics
            else "ATLAS_HISTORICAL_GAP_POLICY_V1"
        )
        return {
            "valid": value.valid,
            "requested": {
                "start": _utc(value.requested_start),
                "end": _utc(value.requested_end),
            },
            "required": {
                "start": _utc(value.required_start) if value.required_start else None,
                "end": _utc(value.requested_end),
            },
            "historicalContext": {
                "required": value.warm_up_required,
                "available": value.warm_up_available,
            },
            "modelVersion": "V2",
            "analysis": "native M15 MID",
            "execution": "sparse M1 BID/ASK",
            "entryPolicy": "[frontier, frontier + 1 minute)",
            "snapshot": {
                "id": str(value.snapshot_id),
                "fingerprint": value.snapshot_fingerprint,
            },
            "counts": {
                "expectedOpenMinutes": report.expected_open_minutes if report else 0,
                "memberMinutes": report.member_minutes if report else 0,
            },
            "gaps": [
                {
                    "start": _utc(g.start),
                    "end": _utc(g.end),
                    "components": [c.value for c in g.components],
                    "reason": "UNEXPECTED_MISSING_DATA",
                    "policy_version": policy_version,
                    "missing_components": [c.value for c in g.components],
                }
                for g in value.gaps
            ],
            "anomalies": [
                _utc(item) for item in (report.closure_anomalies if report else ())
            ],
            "blockingReasons": list(value.reasons),
            "truncated": diagnostics_truncated,
            "policy_version": policy_version,
            "diagnostics": diagnostics,
            "diagnosticCount": len(diagnostics),
        }

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ExperimentReadResponse)
    def create(
        request: ExperimentCreateRequest, db: Session = Depends(session)
    ) -> dict[str, Any]:
        try:
            with db.begin():
                row = configuration.create(
                    db,
                    strategy_version_id=request.strategy_version_id,
                    dataset_snapshot_id=request.dataset_snapshot_id,
                    trading_start=request.trading_start,
                    trading_end=request.trading_end,
                    starting_capital=request.starting_capital,
                    risk_per_trade=request.risk_per_trade,
                    parameters=request.parameters,
                    slippage_ticks=request.slippage_ticks,
                    commission_per_unit=request.commission_per_unit,
                )
        except ConfigurationError as exc:
            code = exc.code
            http_status = 409 if code == "COVERAGE_INVALID" else 422
            raise _error(code, str(exc), http_status=http_status) from exc
        strategy_version = strategy_repo.get_version(db, row.strategy_version_id)
        return _detail(row, strategy_version=strategy_version, identity=_identity(db, row, strategy_version))

    @router.get("", response_model=ExperimentListResponse)
    def listing(
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = None,
        db: Session = Depends(session),
    ) -> dict[str, Any]:
        before_created_at = before_id = None
        if cursor:
            before_created_at, before_id = _decode_cursor(cursor)
        projections = results.list_projection(
            db,
            limit,
            before_created_at=before_created_at,
            before_id=before_id,
        )
        rows = tuple(item.experiment for item in projections)
        next_cursor = _cursor(rows[-1]) if len(rows) == limit else None
        experiment_ids = tuple(row.id for row in rows)
        result_rows = results.list_result_rows(db, experiment_ids)
        gap_rows = results.list_gap_decision_rows(db, experiment_ids)
        items = []
        for projection in projections:
            row = projection.experiment
            # Result rows are authoritative only after the Experiment reaches
            # COMPLETED. Do not let an orphaned/premature persisted row bypass
            # the completed-only result contract on the optimized list path.
            result = (
                result_rows.get(row.id) if row.status == "COMPLETED" else None
            )
            if row.status == "COMPLETED" and result is None:
                raise _error(
                    "INCOMPLETE_RESULT",
                    "Completed Experiment result is unavailable",
                    http_status=409,
                )
            items.append(
                _detail(
                    row,
                    _metrics_payload(results.persisted_metrics(result))
                    if result is not None
                    else None,
                    result,
                    gap_rows.get(row.id, ()),
                    projection.strategy_version,
                    _identity(
                        db,
                        row,
                        projection.strategy_version,
                        snapshot=projection.snapshot,
                        venue=projection.venue,
                        instrument=projection.instrument,
                    ),
                )
            )
        return {"items": items, "nextCursor": next_cursor}

    def get_row(experiment_id: UUID, db: Session) -> ExperimentModel:
        row = result_repo.experiment(db, experiment_id)
        if row is None:
            raise _error("NOT_FOUND", "Experiment does not exist", http_status=404)
        return row

    @router.get("/comparison", response_model=ExperimentComparisonResponse)
    def compare(
        experiment_id: list[UUID] = Query(..., alias="experimentId"),
        db: Session = Depends(session),
    ) -> dict[str, Any]:
        try:
            value = comparison.compare(db, tuple(experiment_id))
        except ComparisonReadError as exc:
            code_status = {
                "EXPERIMENT_NOT_FOUND": 404,
                "EXPERIMENT_NOT_COMPLETED": 409,
                "COMPARISON_RESULT_UNAVAILABLE": 409,
            }
            raise _error(
                exc.code, str(exc), exc.details, code_status.get(exc.code, 422)
            ) from exc
        payload = _json(value)
        for difference in payload["differences"]:
            difference["values"] = dict(difference["values"])
        return payload

    @router.get("/{experiment_id}", response_model=ExperimentReadResponse)
    def detail(experiment_id: UUID, db: Session = Depends(session)) -> dict[str, Any]:
        row = get_row(experiment_id, db)
        try:
            composed = results.detail(db, experiment_id)
        except ResultReadError as exc:
            raise _error(
                exc.code, str(exc), http_status=404 if exc.code == "NOT_FOUND" else 409
            ) from exc
        return _detail(
            row, _metrics_payload(composed["metrics"]), composed["result"],
            results.gap_decisions(db, row.id), composed.get("strategy_version"),
            _identity(db, row, composed.get("strategy_version")),
        )

    @router.post("/{experiment_id}/run")
    def run(experiment_id: UUID, db: Session = Depends(session)) -> dict[str, Any]:
        get_row(
            experiment_id, db
        )  # distinguish 404 from lifecycle infrastructure errors
        try:
            lifecycle.run(experiment_id)
        except ExperimentRunInfrastructureError as exc:
            raise _error(exc.code, str(exc), http_status=500) from exc
        with session_scope(session_factory) as fresh:
            return detail(experiment_id, fresh)

    def subresource(experiment_id: UUID, db: Session) -> None:
        try:
            results._completed(db, experiment_id)
        except ResultReadError as exc:
            code = exc.code
            http_status = 404 if code == "NOT_FOUND" else 409
            raise _error(code, str(exc), http_status=http_status) from exc

    @router.get("/{experiment_id}/equity")
    def equity(experiment_id: UUID, db: Session = Depends(session)) -> Any:
        subresource(experiment_id, db)
        try:
            value = results.equity(db, experiment_id)
        except ResultReadError as exc:
            raise _error(exc.code, str(exc), http_status=409) from exc
        return {
            "points": _json(value.points),
            "sourceCount": value.source_count,
            "returnedCount": len(value.points),
            "samplingPolicy": value.sampling_policy,
        }

    @router.get("/{experiment_id}/price-analysis", response_model=PriceAnalysisResponse)
    def price_analysis(experiment_id: UUID, db: Session = Depends(session)) -> Any:
        try:
            value = results.price_analysis(db, experiment_id)
        except ResultReadError as exc:
            code_status = {
                "NOT_FOUND": 404,
                "RESULT_NOT_READY": 409,
                "EXPERIMENT_FAILED": 409,
                "INCOMPLETE_RESULT": 409,
            }
            raise _error(exc.code, str(exc), http_status=code_status.get(exc.code, 422)) from exc
        return _json(value)

    @router.get("/{experiment_id}/trades")
    def trades(
        experiment_id: UUID,
        limit: int = Query(100, ge=1, le=250),
        after_sequence: int = Query(0, ge=0, alias="afterSequence"),
        db: Session = Depends(session),
    ) -> Any:
        subresource(experiment_id, db)
        try:
            items = results.trades(db, experiment_id, limit, after_sequence)
        except ResultReadError as exc:
            raise _error(
                exc.code,
                str(exc),
                http_status=409 if exc.code != "INVALID_LIMIT" else 422,
            ) from exc
        return {
            "items": _json(items),
            "nextSequence": items[-1]["sequence_number"]
            if len(items) == limit
            else None,
        }

    @router.get("/{experiment_id}/trades/{sequence_number}")
    def trade(
        experiment_id: UUID, sequence_number: int, db: Session = Depends(session)
    ) -> Any:
        try:
            return _json(results.trade(db, experiment_id, sequence_number))
        except ResultReadError as exc:
            raise _error(
                exc.code, str(exc), http_status=404 if exc.code == "NOT_FOUND" else 409
            ) from exc

    return router
