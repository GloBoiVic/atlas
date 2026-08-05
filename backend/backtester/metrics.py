"""Canonical closed-trade projections and run-level backtest metrics."""

from decimal import Decimal
from uuid import UUID

from backend.backtester.models import BacktestResult, BacktestTrade
from backend.data.models import Instrument
from backend.execution.models import Trade


def project_trade(run_id: UUID, instrument: Instrument, trade: Trade) -> BacktestTrade:
    """Project one completed execution trade into the isolated backtest result shape."""
    if trade.exit_price is None or trade.exit_time is None or trade.net_pnl is None:
        raise ValueError("TradeClosed must contain a completed trade")
    return BacktestTrade(
        id=trade.id,
        backtest_run_id=run_id,
        instrument_id=instrument.id,
        symbol=instrument.symbol,
        direction=trade.direction.value,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        pnl=trade.net_pnl,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        signal_metadata=trade.signal_metadata,
    )


def calculate_metrics(
    starting: Decimal, trades: tuple[BacktestTrade, ...]
) -> BacktestResult:
    """Calculate Feature 10's canonical metrics from closed projections only."""
    pnls = [trade.pnl for trade in trades if trade.pnl is not None]
    total_pnl = sum(pnls, Decimal("0"))
    ending = starting + total_pnl
    equity = starting
    peak = starting
    drawdown = Decimal("0")
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    winners = [pnl for pnl in pnls if pnl > 0]
    losers = [pnl for pnl in pnls if pnl < 0]
    profit_factor = (
        float(sum(winners, Decimal("0")) / abs(sum(losers, Decimal("0"))))
        if losers
        else None
    )
    return BacktestResult(
        total_return=total_pnl / starting,
        total_pnl=total_pnl,
        starting_equity=starting,
        ending_equity=ending,
        max_drawdown=drawdown,
        win_rate=len(winners) / len(pnls) if pnls else 0.0,
        sharpe_ratio=None,
        profit_factor=profit_factor,
        trade_count=len(pnls),
        winning_trade_count=len(winners),
        losing_trade_count=len(losers),
    )
