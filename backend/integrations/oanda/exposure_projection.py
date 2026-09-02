"""Pure exposure-state projections from normalized OANDA observations."""

from decimal import Decimal
from typing import NoReturn

from backend.domain import FinancialPositionState

from .positions import OandaPracticeOpenPositionInventory
from .source import OandaError
from .trades import OandaPracticeOpenTradeInventory

_SUPPORTED_INSTRUMENT = "EUR_USD"


class OandaExposureProjectionError(OandaError):
    """Valid OANDA observations cannot produce one supported Atlas state."""


def _projection_error(reason: str) -> NoReturn:
    raise OandaExposureProjectionError(f"OANDA exposure projection failed: {reason}")


def _same_financial_identity(
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
) -> bool:
    trade_identity = trades.identity
    position_identity = positions.identity
    return (
        trade_identity.provider == position_identity.provider
        and trade_identity.environment == position_identity.environment
        and trade_identity.provider_account_id == position_identity.provider_account_id
        and trade_identity.base_currency == position_identity.base_currency
    )


def project_oanda_practice_eur_usd_exposure_state(
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
) -> FinancialPositionState:
    """Project matching normalized OANDA views into one financial state."""
    if not _same_financial_identity(trades, positions):
        _projection_error("account financial identity mismatch")

    if any(
        trade.provider_instrument != _SUPPORTED_INSTRUMENT for trade in trades.trades
    ):
        _projection_error("unsupported Trade instrument")
    if any(
        position.provider_instrument != _SUPPORTED_INSTRUMENT
        for position in positions.positions
    ):
        _projection_error("unsupported Position instrument")

    if not trades.trades and not positions.positions:
        return FinancialPositionState.FLAT
    if not trades.trades:
        _projection_error("Position exposure has no Trade counterpart")
    if not positions.positions:
        _projection_error("Trade exposure has no Position counterpart")
    if len(positions.positions) != 1:
        _projection_error("exposure requires exactly one Position")

    position = positions.positions[0]
    has_positive_trades = all(trade.current_units > 0 for trade in trades.trades)
    has_negative_trades = all(trade.current_units < 0 for trade in trades.trades)
    if not has_positive_trades and not has_negative_trades:
        _projection_error("Trade inventory contains opposing directions")

    trade_units = sum((trade.current_units for trade in trades.trades), Decimal("0"))
    if has_positive_trades:
        if position.long.units <= 0 or position.short.units != 0:
            _projection_error("Trade and Position directions disagree")
        if trade_units != position.long.units:
            _projection_error("Trade and Position units disagree")
        return FinancialPositionState.LONG

    if position.long.units != 0 or position.short.units >= 0:
        _projection_error("Trade and Position directions disagree")
    if trade_units != position.short.units:
        _projection_error("Trade and Position units disagree")
    return FinancialPositionState.SHORT
