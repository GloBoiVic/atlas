"""Read-only Strategy catalog and immutable version history routes."""

# ruff: noqa: E501, B008

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.persistence.database import session_scope
from backend.persistence.strategy_repository import StrategyRepository
from backend.strategies.registry import (
    StrategyRegistry,
    StrategyVersionUnavailableError,
)

from .schemas import StrategyCatalogResponse, StrategyDetailResponse


def _utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    instant = (
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    )
    return instant.isoformat().replace("+00:00", "Z")


def _availability(registry: StrategyRegistry, row: Any) -> tuple[bool, str | None]:
    try:
        registry.get(
            row.strategy.strategy_key,
            implementation_key=row.implementation_key,
            source_fingerprint=row.source_fingerprint,
        )
    except StrategyVersionUnavailableError:
        return (
            False,
            "No exact local implementation is registered for this StrategyVersion.",
        )
    return True, None


def _version(registry: StrategyRegistry, row: Any, usage: Any) -> dict[str, Any]:
    available, reason = _availability(registry, row)
    definition = None
    if available:
        definition = registry.get(
            row.strategy.strategy_key,
            implementation_key=row.implementation_key,
            source_fingerprint=row.source_fingerprint,
        ).definition
    return {
        "id": row.id,
        "displayName": f"{row.strategy.name} v{row.version_number}",
        "versionNumber": row.version_number,
        "implementationKey": row.implementation_key,
        "sourceFingerprint": row.source_fingerprint,
        "createdAt": _utc(row.created_at),
        "gitSha": row.git_sha,
        "sourceManifest": row.source_manifest,
        "parameterSchema": row.parameter_schema,
        "contextTimeframes": row.context_timeframes,
        "timeframe": row.primary_timeframe,
        "requiredHistoricalContextBars": row.required_historical_context_bars,
        "stateSchemaVersion": row.state_schema_version,
        "capabilities": row.capabilities,
        "experimentCount": usage.count,
        "lastUsedAt": _utc(usage.last_used_at),
        "executionAvailable": available,
        "unavailableReason": reason,
        "marketRequirements": {
            "instrument": definition.required_instrument.value if definition else None,
            "resolution": definition.required_resolution.value if definition else row.primary_timeframe,
            "priceComponent": definition.required_price_component.value if definition else None,
            "requiredHistoricalContextBars": row.required_historical_context_bars,
            "completedOnly": definition.completed_only if definition else None,
        },
        "methodology": {
            "summary": definition.description if definition else row.strategy.description,
            "capabilities": list(definition.capabilities) if definition else row.capabilities,
        },
    }


def create_strategy_router(
    *,
    session_factory: Any,
    registry: StrategyRegistry,
    repository: StrategyRepository | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
    repo = repository or StrategyRepository()

    def session() -> Any:
        with session_scope(session_factory) as db:
            yield db

    @router.get("", response_model=StrategyCatalogResponse)
    def listing(db: Session = Depends(session)) -> dict[str, Any]:
        items = []
        for projection in repo.list_catalog_projections(db):
            strategy = projection.strategy
            latest = projection.latest_version
            items.append(
                {
                    "strategyKey": strategy.strategy_key,
                    "name": strategy.name,
                    "description": strategy.description,
                    "latestVersion": {
                        "id": latest.id,
                        "versionNumber": latest.version_number,
                        "displayName": f"{strategy.name} v{latest.version_number}",
                    }
                    if latest
                    else None,
                    "versionCount": projection.version_count,
                    "experimentCount": projection.experiment_count,
                    "lastExperimentAt": _utc(projection.last_experiment_at),
                }
            )
        return {"items": items}

    @router.get("/{strategy_key}", response_model=StrategyDetailResponse)
    def detail(strategy_key: str, db: Session = Depends(session)) -> dict[str, Any]:
        strategy = repo.get_strategy(db, strategy_key)
        if strategy is None:
            raise HTTPException(
                404,
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Strategy does not exist",
                        "details": {},
                    }
                },
            )
        versions = repo.list_versions(db, strategy_key)
        items = [
            _version(registry, row, repo.version_usage(db, row.id))
            for row in reversed(versions)
        ]
        usage = repo.strategy_usage(db, strategy.id)
        return {
            "strategyKey": strategy.strategy_key,
            "name": strategy.name,
            "description": strategy.description,
            "versionCount": len(items),
            "experimentCount": usage.count,
            "lastExperimentAt": _utc(usage.last_used_at),
            "versions": items,
        }

    return router
