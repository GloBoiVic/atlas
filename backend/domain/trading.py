"""Strict financial Position value objects for the Phase 3 trading boundary.

This module is deliberately separate from ``domain.strategy``.  A strategy's
PositionState is an evaluation input; Position is the financial exposure
projection that is changed only by a Fill in later Phase 3 work.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from .market_data import InputError, Instrument
from .strategy import Direction


class TradingInputError(InputError):
    """Invalid financial trading-domain input."""


class FinancialPositionState(StrEnum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


def _decimal(value: Decimal, name: str) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise TradingInputError(f"{name} must be a finite Decimal")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise TradingInputError(f"{name} must be timezone-aware UTC")
    return value


@dataclass(frozen=True, slots=True)
class Position:
    """Current economic exposure for one Instrument.

    A flat Position has no quantity or entry facts.  An exposed Position has
    positive Decimal quantity and entry facts; these are deliberately not
    strategy state and cannot be inferred from a StrategyDecision.
    """

    instrument: Instrument
    state: FinancialPositionState = FinancialPositionState.FLAT
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal | None = None
    opened_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.instrument) is not Instrument:
            raise TradingInputError("instrument must be an Instrument")
        if type(self.state) is not FinancialPositionState:
            raise TradingInputError("state must be a FinancialPositionState")
        _decimal(self.quantity, "quantity")
        if self.state is FinancialPositionState.FLAT:
            if self.quantity != 0 or self.average_entry_price is not None:
                raise TradingInputError("FLAT Position cannot contain exposure facts")
            if self.opened_at is not None:
                raise TradingInputError("FLAT Position cannot have opened_at")
            return
        if self.quantity <= 0:
            raise TradingInputError("exposed Position quantity must be positive")
        if self.average_entry_price is None:
            raise TradingInputError("exposed Position requires an entry price")
        if _decimal(self.average_entry_price, "average_entry_price") <= 0:
            raise TradingInputError("average_entry_price must be positive")
        if self.opened_at is None:
            raise TradingInputError("exposed Position requires opened_at")
        _utc(self.opened_at, "opened_at")

    @property
    def direction(self) -> Direction | None:
        if self.state is FinancialPositionState.FLAT:
            return None
        return (
            Direction.LONG
            if self.state is FinancialPositionState.LONG
            else Direction.SHORT
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument.value,
            "state": self.state.value,
            "direction": self.direction.value if self.direction else None,
            "quantity": str(self.quantity),
            "average_entry_price": (
                str(self.average_entry_price)
                if self.average_entry_price is not None
                else None
            ),
            "opened_at": (
                self.opened_at.isoformat().replace("+00:00", "Z")
                if self.opened_at is not None
                else None
            ),
        }


__all__ = ["FinancialPositionState", "Position", "TradingInputError"]
