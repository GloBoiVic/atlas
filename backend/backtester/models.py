"""Immutable contracts for backtest configuration and result projections."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from backend.strategy.contracts import _FrozenJsonDict, _validate_metadata


def _validate_decimal(value: Decimal, field_name: str, *, non_negative: bool = False) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if non_negative and value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _validate_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


def _freeze_config(value: dict[str, Any], field_name: str) -> _FrozenJsonDict:
    try:
        frozen = _validate_metadata(value)
    except (TypeError, ValueError) as error:
        raise type(error)(f"{field_name}: {error}") from error
    return frozen


class BacktestStatus(StrEnum):
    """Lifecycle states for a backtest run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Validated, immutable input to a deterministic backtest."""

    instrument_id: UUID
    account_id: UUID
    strategy_version_id: UUID
    timeframe: str
    start_date: datetime
    end_date: datetime
    strategy_parameters: dict[str, Any]
    risk_config: dict[str, Any]
    execution_config: dict[str, Any]
    initial_balance: Decimal

    def __post_init__(self) -> None:
        for value, name in (
            (self.instrument_id, "instrument_id"),
            (self.account_id, "account_id"),
            (self.strategy_version_id, "strategy_version_id"),
        ):
            if not isinstance(value, UUID):
                raise TypeError(f"{name} must be a UUID")
        if not self.timeframe or self.timeframe.strip() != self.timeframe:
            raise ValueError("timeframe must be a non-empty value without surrounding whitespace")
        _validate_utc(self.start_date, "start_date")
        _validate_utc(self.end_date, "end_date")
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        _validate_decimal(self.initial_balance, "initial_balance")
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive")
        if not isinstance(self.execution_config, dict):
            raise TypeError("execution_config must be a dictionary")
        for name in ("fee_rate", "slippage_rate"):
            if name in self.execution_config and not isinstance(
                self.execution_config[name], Decimal
            ):
                raise TypeError(f"execution_config.{name} must be a Decimal")
        for name in ("strategy_parameters", "risk_config", "execution_config"):
            config = getattr(self, name)
            if not isinstance(config, dict):
                raise TypeError(f"{name} must be a dictionary")
            object.__setattr__(self, name, _freeze_config(config, name))
        execution = self.execution_config
        if execution.get("fill_model") != "next_candle_open":
            raise ValueError("execution_config.fill_model must be next_candle_open")
        if execution.get("protective_trigger_rule") != "stop_loss_first":
            raise ValueError(
                "execution_config.protective_trigger_rule must be stop_loss_first"
            )
        for name in ("fee_rate", "slippage_rate"):
            if name in execution:
                value = execution[name]
                if not isinstance(value, Decimal):
                    raise TypeError(f"execution_config.{name} must be a Decimal")
                _validate_decimal(value, f"execution_config.{name}", non_negative=True)


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Run-level result metrics using the canonical numeric categories."""

    total_return: Decimal
    total_pnl: Decimal
    starting_equity: Decimal
    ending_equity: Decimal
    max_drawdown: Decimal | None = None
    win_rate: float | None = None
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    trade_count: int = 0
    winning_trade_count: int = 0
    losing_trade_count: int = 0

    def __post_init__(self) -> None:
        for value, name in (
            (self.total_return, "total_return"),
            (self.total_pnl, "total_pnl"),
            (self.starting_equity, "starting_equity"),
            (self.ending_equity, "ending_equity"),
        ):
            _validate_decimal(value, name)
        if self.max_drawdown is not None:
            _validate_decimal(self.max_drawdown, "max_drawdown", non_negative=True)
        for metric, name in (
            (self.win_rate, "win_rate"),
            (self.sharpe_ratio, "sharpe_ratio"),
            (self.profit_factor, "profit_factor"),
        ):
            if metric is not None and not isinstance(metric, float):
                raise TypeError(f"{name} must be a float or None")
        if self.trade_count < 0 or self.winning_trade_count < 0 or self.losing_trade_count < 0:
            raise ValueError("trade counts must be non-negative")


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    """Projection of a completed execution Trade belonging to a run."""

    backtest_run_id: UUID
    instrument_id: UUID
    symbol: str
    direction: str
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    exit_price: Decimal | None = None
    pnl: Decimal | None = None
    exit_time: datetime | None = None
    signal_metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        for value, name in (
            (self.backtest_run_id, "backtest_run_id"),
            (self.instrument_id, "instrument_id"),
        ):
            if not isinstance(value, UUID):
                raise TypeError(f"{name} must be a UUID")
        _validate_decimal(self.entry_price, "entry_price")
        _validate_decimal(self.quantity, "quantity")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.exit_price is not None:
            _validate_decimal(self.exit_price, "exit_price")
        if self.pnl is not None:
            _validate_decimal(self.pnl, "pnl")
        _validate_utc(self.entry_time, "entry_time")
        if self.exit_time is not None:
            _validate_utc(self.exit_time, "exit_time")
        object.__setattr__(
            self,
            "signal_metadata",
            _freeze_config(self.signal_metadata, "signal_metadata"),
        )

    @property
    def net_pnl(self) -> Decimal | None:
        """Return the completed trade's net P&L using the canonical projection name."""
        return self.pnl


@dataclass(frozen=True, slots=True)
class BacktestRun:
    """Domain projection of a backtest run record."""

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
    result: BacktestResult | None = None
    error_message: str | None = None
    last_processed_timestamp: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.instrument_id, UUID):
            raise TypeError("id and instrument_id must be UUIDs")
        if not isinstance(self.status, BacktestStatus):
            raise TypeError("status must be a BacktestStatus")
        for value, name in (
            (self.start_date, "start_date"),
            (self.end_date, "end_date"),
            (self.created_at, "created_at"),
        ):
            _validate_utc(value, name)
        if self.last_processed_timestamp is not None:
            _validate_utc(self.last_processed_timestamp, "last_processed_timestamp")
        if self.completed_at is not None:
            _validate_utc(self.completed_at, "completed_at")
        for name in ("strategy_parameters", "risk_config", "execution_config"):
            config = getattr(self, name)
            if not isinstance(config, dict):
                raise TypeError(f"{name} must be a dictionary")
            object.__setattr__(self, name, _freeze_config(config, name))
