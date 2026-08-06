"""Pydantic transport schemas for the REST API."""

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.analytics.metrics import EquityPoint, PerformanceMetrics
from backend.backtester.models import BacktestConfig, BacktestRun, BacktestStatus
from backend.journal.models import JournalEntry

_FORBIDDEN_KEYS = {
    "import",
    "import_path",
    "module",
    "entrypoint",
    "api_key",
    "api_secret",
    "secret",
    "password",
    "token",
}


def _reject_untrusted_values(value: Any) -> Any:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError(f"configuration field {key!r} is not accepted")
            _reject_untrusted_values(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_untrusted_values(nested)
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("datetime must be UTC")
    return value


class BacktestCreateRequest(BaseModel):
    """Validated API input; strategy and instrument are selected by UUID only."""

    model_config = ConfigDict(extra="forbid")

    instrument_id: UUID
    account_id: UUID
    strategy_version_id: UUID
    timeframe: str = Field(min_length=1)
    start_date: datetime
    end_date: datetime
    strategy_parameters: dict[str, Any] = Field(default_factory=dict)
    risk_config: dict[str, Any] = Field(default_factory=dict)
    execution_config: dict[str, Any] = Field(default_factory=dict)
    initial_balance: Decimal = Field(gt=0)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_config(self) -> "BacktestCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        for config in (self.strategy_parameters, self.risk_config, self.execution_config):
            _reject_untrusted_values(config)
        execution = dict(self.execution_config)
        for key in ("fee_rate", "slippage_rate"):
            if key in execution:
                try:
                    converted = Decimal(str(execution[key]))
                except (TypeError, ValueError) as error:
                    raise ValueError(f"execution_config.{key} must be a Decimal") from error
                if not converted.is_finite() or converted < 0:
                    raise ValueError(f"execution_config.{key} must be finite and non-negative")
                execution[key] = converted
        execution.setdefault("fill_model", "next_candle_open")
        execution.setdefault("protective_trigger_rule", "stop_loss_first")
        if execution["fill_model"] != "next_candle_open":
            raise ValueError("execution_config.fill_model must be next_candle_open")
        if execution["protective_trigger_rule"] != "stop_loss_first":
            raise ValueError(
                "execution_config.protective_trigger_rule must be stop_loss_first"
            )
        object.__setattr__(self, "execution_config", execution)
        return self

    def to_domain(self) -> BacktestConfig:
        """Convert validated transport input into the immutable service contract."""
        return BacktestConfig(
            instrument_id=self.instrument_id,
            account_id=self.account_id,
            strategy_version_id=self.strategy_version_id,
            timeframe=self.timeframe,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy_parameters=self.strategy_parameters,
            risk_config=self.risk_config,
            execution_config=self.execution_config,
            initial_balance=self.initial_balance,
        )


class BacktestResultResponse(BaseModel):
    total_return: str
    total_pnl: str
    starting_equity: str
    ending_equity: str
    max_drawdown: str | None
    win_rate: float | None
    sharpe_ratio: float | None
    profit_factor: float | None
    trade_count: int
    winning_trade_count: int
    losing_trade_count: int


class BacktestRunResponse(BaseModel):
    id: UUID
    strategy_name: str
    strategy_version: str
    strategy_commit_sha: str
    strategy_parameters: dict[str, Any]
    instrument_id: UUID
    symbol: str
    timeframe: str
    data_source: str
    dataset_id: str
    start_date: datetime
    end_date: datetime
    risk_config: dict[str, Any]
    execution_config: dict[str, Any]
    fill_model: str
    status: BacktestStatus
    created_at: datetime
    result: BacktestResultResponse | None
    error_message: str | None
    last_processed_timestamp: datetime | None
    completed_at: datetime | None


class BacktestTradeResponse(BaseModel):
    id: UUID
    backtest_run_id: UUID
    instrument_id: UUID
    symbol: str
    direction: str
    entry_price: str
    exit_price: str | None
    quantity: str
    pnl: str | None
    entry_time: datetime
    exit_time: datetime | None
    signal_metadata: dict[str, Any]


class JournalEntryResponse(BaseModel):
    """Enriched historical journal projection at the API boundary."""

    id: UUID
    account_id: UUID
    trade_id: UUID
    bot_id: UUID | None
    strategy_version_id: UUID | None
    instrument_id: UUID | None
    symbol: str
    direction: str
    entry_price: str
    exit_price: str | None
    quantity: str
    pnl: str | None
    strategy_name: str
    signal: dict[str, object]
    market_conditions: dict[str, object]
    notes: str | None
    risk_metadata: dict[str, object]
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JournalNotesUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=10_000)


class EquityPointResponse(BaseModel):
    timestamp: datetime
    equity: str
    net_pnl: str
    trade_id: UUID | None


class PerformanceMetricsResponse(BaseModel):
    """Canonical analytics facts; the browser must not recalculate these values."""

    total_return: str
    total_pnl: str
    starting_equity: str
    ending_equity: str
    win_rate: float
    closed_trade_daily_sharpe: float | None
    max_drawdown: str
    profit_factor: float | None
    total_trades: int
    winning_trades: int
    losing_trades: int
    equity_curve: list[EquityPointResponse]


def journal_entry_response(entry: JournalEntry) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=entry.id,
        account_id=entry.account_id,
        trade_id=entry.trade_id,
        bot_id=entry.bot_id,
        strategy_version_id=entry.strategy_version_id,
        instrument_id=entry.instrument_id,
        symbol=entry.symbol,
        direction=entry.direction.value,
        entry_price=str(entry.entry_price),
        exit_price=_decimal(entry.exit_price),
        quantity=str(entry.quantity),
        pnl=_decimal(entry.pnl),
        strategy_name=entry.strategy_name,
        signal=dict(entry.signal),
        market_conditions=dict(entry.market_conditions),
        notes=entry.notes,
        risk_metadata=dict(entry.risk_metadata),
        opened_at=entry.opened_at,
        closed_at=entry.closed_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def metrics_response(metrics: PerformanceMetrics) -> PerformanceMetricsResponse:
    return PerformanceMetricsResponse(
        total_return=str(metrics.total_return),
        total_pnl=str(metrics.total_pnl),
        starting_equity=str(metrics.starting_equity),
        ending_equity=str(metrics.ending_equity),
        win_rate=metrics.win_rate,
        closed_trade_daily_sharpe=metrics.closed_trade_daily_sharpe,
        max_drawdown=str(metrics.max_drawdown),
        profit_factor=metrics.profit_factor,
        total_trades=metrics.total_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        equity_curve=[equity_point_response(point) for point in metrics.equity_curve],
    )


def equity_point_response(point: EquityPoint) -> EquityPointResponse:
    return EquityPointResponse(
        timestamp=point.timestamp,
        equity=str(point.equity),
        net_pnl=str(point.net_pnl),
        trade_id=point.trade_id,
    )


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def run_response(run: BacktestRun) -> BacktestRunResponse:
    result = run.result
    result_response = None
    if result is not None:
        result_response = BacktestResultResponse(
            total_return=str(result.total_return),
            total_pnl=str(result.total_pnl),
            starting_equity=str(result.starting_equity),
            ending_equity=str(result.ending_equity),
            max_drawdown=_decimal(result.max_drawdown),
            win_rate=result.win_rate,
            sharpe_ratio=result.sharpe_ratio,
            profit_factor=result.profit_factor,
            trade_count=result.trade_count,
            winning_trade_count=result.winning_trade_count,
            losing_trade_count=result.losing_trade_count,
        )
    values = asdict(run)
    values["result"] = result_response
    return BacktestRunResponse.model_validate(values)


def trade_response(trade: Any) -> BacktestTradeResponse:
    return BacktestTradeResponse(
        id=trade.id,
        backtest_run_id=trade.backtest_run_id,
        instrument_id=trade.instrument_id,
        symbol=trade.symbol,
        direction=trade.direction,
        entry_price=str(trade.entry_price),
        exit_price=_decimal(trade.exit_price),
        quantity=str(trade.quantity),
        pnl=_decimal(trade.pnl),
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        signal_metadata=dict(trade.signal_metadata),
    )
