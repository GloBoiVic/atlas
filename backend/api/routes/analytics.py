"""Canonical closed-trade analytics endpoint."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import AnalyticsScopeDep, AnalyticsServiceDep
from backend.api.schemas import PerformanceMetricsResponse, metrics_response

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def _validate_dates(start_date: datetime | None, end_date: datetime | None) -> None:
    for value, name in ((start_date, "start_date"), (end_date, "end_date")):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise HTTPException(status_code=422, detail=f"{name} must be UTC")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")


@router.get("", response_model=PerformanceMetricsResponse)
async def get_analytics(
    service: AnalyticsServiceDep,
    scope: AnalyticsScopeDep,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
) -> PerformanceMetricsResponse:
    _validate_dates(start_date, end_date)
    if scope is None:
        raise HTTPException(
            status_code=503,
            detail="analytics account scope is not configured",
        )
    period_start = start_date or datetime(1970, 1, 1, tzinfo=UTC)
    period_end = end_date or datetime.now(UTC)
    try:
        metrics = await service.get_metrics(
            account_id=scope.account_id,
            starting_equity=scope.starting_equity,
            period_start=period_start,
            period_end=period_end,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("analytics_failure")
        raise HTTPException(status_code=500, detail="analytics infrastructure failure") from error
    return metrics_response(metrics)
