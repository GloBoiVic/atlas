"""Small adapters used by the isolated replay composition."""

from typing import Any

from backend.core.events import InMemoryFailureRecorder
from backend.execution.models import PositionSide, PositionStatus
from backend.risk.engine import PositionInfo
from backend.risk.engine import PositionStatus as RiskPositionStatus
from backend.strategy.contracts import SignalDirection


def risk_position(position: Any) -> PositionInfo:
    """Translate a broker position into the risk engine's read-only context shape."""
    return PositionInfo(
        account_id=position.account_id,
        bot_id=position.bot_id,
        instrument_id=position.instrument_id,
        direction=(
            SignalDirection.BUY
            if position.side is PositionSide.LONG
            else SignalDirection.SELL
        ),
        quantity=position.quantity,
        status=(
            RiskPositionStatus.OPEN
            if position.status is PositionStatus.OPEN
            else RiskPositionStatus.REDUCING
        ),
        strategy_version_id=position.strategy_version_id,
    )


def raise_event_failures(recorder: InMemoryFailureRecorder) -> None:
    """Turn recorded critical handler failures into a failed replay."""
    if recorder.failures:
        raise RuntimeError(
            "backtest trading-critical event handler failed"
        ) from recorder.failures[0].exception
