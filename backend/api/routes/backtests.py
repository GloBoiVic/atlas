"""Backtest HTTP endpoints; orchestration remains in BacktestService."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, status

from backend.api.deps import BacktestServiceDep
from backend.api.schemas import (
    BacktestCreateRequest,
    BacktestRunResponse,
    BacktestTradeResponse,
    run_response,
    trade_response,
)
from backend.backtester.service import BacktestRunConflict

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=BacktestRunResponse, status_code=status.HTTP_200_OK)
async def create_backtest(
    request: BacktestCreateRequest,
    service: BacktestServiceDep,
) -> BacktestRunResponse:
    try:
        return run_response(await service.run(request.to_domain()))
    except BacktestRunConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        logger.exception("backtest_infrastructure_failure")
        raise HTTPException(status_code=500, detail="backtest infrastructure failure") from error
    except Exception as error:
        logger.exception("backtest_unexpected_failure")
        raise HTTPException(status_code=500, detail="backtest infrastructure failure") from error


@router.get("", response_model=list[BacktestRunResponse])
async def list_backtests(service: BacktestServiceDep) -> list[BacktestRunResponse]:
    try:
        return [run_response(run) for run in await service.list_runs()]
    except Exception as error:
        logger.exception("backtest_list_failure")
        raise HTTPException(status_code=500, detail="backtest infrastructure failure") from error


@router.get("/{backtest_id}", response_model=BacktestRunResponse)
async def get_backtest(
    backtest_id: UUID,
    service: BacktestServiceDep,
) -> BacktestRunResponse:
    try:
        run = await service.get_run(backtest_id)
    except Exception as error:
        logger.exception("backtest_lookup_failure", backtest_id=str(backtest_id))
        raise HTTPException(status_code=500, detail="backtest infrastructure failure") from error
    if run is None:
        raise HTTPException(status_code=404, detail="backtest not found")
    return run_response(run)


@router.get("/{backtest_id}/trades", response_model=list[BacktestTradeResponse])
async def get_backtest_trades(
    backtest_id: UUID,
    service: BacktestServiceDep,
) -> list[BacktestTradeResponse]:
    try:
        run = await service.get_run(backtest_id)
        if run is None:
            raise HTTPException(status_code=404, detail="backtest not found")
        trades = await service.get_trades(backtest_id)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("backtest_trades_lookup_failure", backtest_id=str(backtest_id))
        raise HTTPException(status_code=500, detail="backtest infrastructure failure") from error
    return [trade_response(trade) for trade in trades]
