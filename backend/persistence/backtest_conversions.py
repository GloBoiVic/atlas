"""Conversions between backtest domain projections and SQLAlchemy rows."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.backtester.models import BacktestResult, BacktestRun, BacktestStatus, BacktestTrade
from backend.persistence.models import BacktestRunModel, BacktestTradeModel

_DECIMAL_TAG = "__atlas_decimal__"


def _json_encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {_DECIMAL_TAG: str(value)}
    if isinstance(value, dict):
        return {str(key): _json_encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_encode(item) for item in value]
    return value


def _json_decode(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {_DECIMAL_TAG}:
            return Decimal(value[_DECIMAL_TAG])
        return {key: _json_decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_json_decode(item) for item in value)
    return value


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _required_utc(value: datetime) -> datetime:
    normalized = _utc(value)
    assert normalized is not None
    return normalized


def _result(row: BacktestRunModel) -> BacktestResult | None:
    if row.total_return is None or row.total_pnl is None:
        return None
    if row.starting_equity is None or row.ending_equity is None:
        return None
    return BacktestResult(
        total_return=row.total_return,
        total_pnl=row.total_pnl,
        starting_equity=row.starting_equity,
        ending_equity=row.ending_equity,
        max_drawdown=row.max_drawdown,
        win_rate=row.win_rate,
        sharpe_ratio=row.sharpe_ratio,
        profit_factor=row.profit_factor,
        trade_count=row.total_trades,
        winning_trade_count=row.winning_trades,
        losing_trade_count=row.losing_trades,
    )


def backtest_run_from_orm(row: BacktestRunModel) -> BacktestRun:
    """Convert a database row to an immutable domain run."""
    created_at = _utc(row.created_at)
    assert created_at is not None
    return BacktestRun(
        id=row.id,
        strategy_name=row.strategy_name,
        strategy_version=row.strategy_version,
        strategy_commit_sha=row.strategy_commit_sha,
        strategy_parameters=_json_decode(row.strategy_parameters),
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        timeframe=row.timeframe,
        data_source=row.data_source,
        dataset_id=row.dataset_id,
        start_date=_required_utc(row.start_date),
        end_date=_required_utc(row.end_date),
        risk_config=_json_decode(row.risk_config),
        execution_config=_json_decode(row.execution_config),
        fill_model=row.fill_model,
        status=BacktestStatus(row.status),
        created_at=created_at,
        result=_result(row),
        error_message=row.error_message,
        last_processed_timestamp=_utc(row.last_processed_timestamp),
        completed_at=_utc(row.completed_at),
    )


def backtest_run_to_orm(run: BacktestRun) -> BacktestRunModel:
    """Convert an immutable domain run to a new database row."""
    result = run.result
    return BacktestRunModel(
        id=run.id,
        strategy_name=run.strategy_name,
        strategy_version=run.strategy_version,
        strategy_commit_sha=run.strategy_commit_sha,
        strategy_parameters=_json_encode(run.strategy_parameters),
        instrument_id=run.instrument_id,
        symbol=run.symbol,
        timeframe=run.timeframe,
        data_source=run.data_source,
        dataset_id=run.dataset_id,
        start_date=run.start_date,
        end_date=run.end_date,
        risk_config=_json_encode(run.risk_config),
        execution_config=_json_encode(run.execution_config),
        fill_model=run.fill_model,
        status=run.status.value,
        total_return=result.total_return if result else None,
        total_pnl=result.total_pnl if result else None,
        starting_equity=result.starting_equity if result else None,
        ending_equity=result.ending_equity if result else None,
        win_rate=result.win_rate if result else None,
        sharpe_ratio=result.sharpe_ratio if result else None,
        max_drawdown=result.max_drawdown if result else None,
        profit_factor=result.profit_factor if result else None,
        total_trades=result.trade_count if result else 0,
        winning_trades=result.winning_trade_count if result else 0,
        losing_trades=result.losing_trade_count if result else 0,
        error_message=run.error_message,
        last_processed_timestamp=run.last_processed_timestamp,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def backtest_trade_from_orm(row: BacktestTradeModel) -> BacktestTrade:
    """Convert a database row to an immutable domain trade."""
    entry_time = _utc(row.entry_time)
    assert entry_time is not None
    return BacktestTrade(
        id=row.id,
        backtest_run_id=row.backtest_run_id,
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        direction=row.direction,
        entry_price=row.entry_price,
        exit_price=row.exit_price,
        quantity=row.quantity,
        pnl=row.pnl,
        entry_time=entry_time,
        exit_time=_utc(row.exit_time),
        signal_metadata=_json_decode(row.signal_metadata),
    )


def backtest_trade_to_orm(trade: BacktestTrade) -> BacktestTradeModel:
    """Convert an immutable domain trade to a new database row."""
    return BacktestTradeModel(
        id=trade.id,
        backtest_run_id=trade.backtest_run_id,
        instrument_id=trade.instrument_id,
        symbol=trade.symbol,
        direction=trade.direction,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        pnl=trade.pnl,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        signal_metadata=_json_encode(trade.signal_metadata),
    )
