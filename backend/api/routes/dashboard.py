"""Read-only operational dashboard endpoints."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query

from backend.api.dashboard_schemas import (
    AccountSummaryResponse,
    BotResponse,
    DashboardSummaryResponse,
    PositionResponse,
    StrategyResponse,
    StrategyVersionResponse,
    TradeResponse,
    account_summary_response,
    bot_response,
    dashboard_response,
    position_response,
    strategy_response,
    strategy_version_response,
    trade_response,
)
from backend.api.deps import AnalyticsScopeDep, DashboardReadServiceDep

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummaryResponse)
@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    service: DashboardReadServiceDep,
    scope: AnalyticsScopeDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> DashboardSummaryResponse:
    return dashboard_response(await _read(service.get_dashboard_summary, scope, limit=limit))


@router.get("/account", response_model=AccountSummaryResponse)
@router.get("/account/summary", response_model=AccountSummaryResponse)
async def get_account_summary(
    service: DashboardReadServiceDep, scope: AnalyticsScopeDep
) -> AccountSummaryResponse:
    return account_summary_response(await _read(service.get_account_summary, scope))


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    service: DashboardReadServiceDep, scope: AnalyticsScopeDep
) -> list[PositionResponse]:
    return [position_response(item) for item in await _read(service.list_positions, scope)]


@router.get("/dashboard/bots", response_model=list[BotResponse])
async def list_bots(
    service: DashboardReadServiceDep, scope: AnalyticsScopeDep
) -> list[BotResponse]:
    return [bot_response(item) for item in await _read(service.list_bots, scope)]


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    service: DashboardReadServiceDep,
    scope: AnalyticsScopeDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[TradeResponse]:
    return [trade_response(item) for item in await _read(service.list_trades, scope, limit)]


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(service: DashboardReadServiceDep) -> list[StrategyResponse]:
    return [strategy_response(item) for item in await service.list_strategies()]


@router.get("/strategies/{strategy_id}/versions", response_model=list[StrategyVersionResponse])
async def list_strategy_versions(
    strategy_id: UUID, service: DashboardReadServiceDep
) -> list[StrategyVersionResponse]:
    return [
        strategy_version_response(item)
        for item in await service.list_strategy_versions(strategy_id)
    ]


async def _read(call: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
    if args and args[0] is None:
        raise HTTPException(status_code=503, detail="analytics account scope is not configured")
    try:
        return await call(*args, **kwargs)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("dashboard_read_failure")
        raise HTTPException(status_code=500, detail="dashboard infrastructure failure") from error
