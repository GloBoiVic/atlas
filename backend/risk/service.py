"""Small, deterministic, fail-closed Risk service for Phase 3.

Risk accepts facts explicitly.  It does not read persistence, call a broker,
or submit an Order.  In particular, Strategy owns neither account state nor
quantity sizing.
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Any

from backend.domain.market_data import Instrument
from backend.domain.strategy import Action, Direction, TargetProposal
from backend.domain.trading import FinancialPositionState, Position


class RiskPhase(StrEnum):
    PRE_FLIGHT = "PRE_FLIGHT"
    PRE_SUBMISSION = "PRE_SUBMISSION"


class RiskRejection(StrEnum):
    POSITION_ALREADY_OPEN = "POSITION_ALREADY_OPEN"
    INVALID_STOP = "INVALID_STOP"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    ACCOUNT_STATE_UNKNOWN = "ACCOUNT_STATE_UNKNOWN"
    # Retained as a readable historical rejection vocabulary; Risk no longer emits it.
    EXPERIMENT_NOT_RUNNING = "EXPERIMENT_NOT_RUNNING"
    UNSUPPORTED_INSTRUMENT_ECONOMICS = "UNSUPPORTED_INSTRUMENT_ECONOMICS"


@dataclass(frozen=True, slots=True)
class RiskConfig:
    risk_per_trade: Decimal


@dataclass(frozen=True, slots=True)
class AccountState:
    base_currency: str
    equity: Decimal | None


@dataclass(frozen=True, slots=True)
class ExecutableQuote:
    bid: Decimal
    ask: Decimal


@dataclass(frozen=True, slots=True)
class TradeIntent:
    """The opening facts Risk needs; this is not an Order."""

    action: Action
    direction: Direction | None
    stop: Decimal | None
    target: TargetProposal | None


@dataclass(frozen=True, slots=True)
class RiskDecision:
    phase: RiskPhase
    approved: bool
    rejection: RiskRejection | None = None
    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    risk_budget: Decimal | None = None
    quantity: Decimal | None = None
    actual_risk: Decimal | None = None


class RiskService:
    """The sole Phase 3 authority for entry eligibility and sizing."""

    def evaluate_pre_flight(
        self,
        intent: TradeIntent,
        *,
        position: Position | FinancialPositionState | str | None,
        account: AccountState | None,
        config: RiskConfig,
        instrument: Instrument | str,
    ) -> RiskDecision:
        common = self._common(
            RiskPhase.PRE_FLIGHT, intent, position, account, config, instrument,
        )
        if common is not None:
            return common
        # Price is intentionally absent at PRE_FLIGHT.  Quantity is finalized
        # only against the executable quote at PRE_SUBMISSION.
        return RiskDecision(
            phase=RiskPhase.PRE_FLIGHT, approved=True, stop_price=intent.stop
        )

    def evaluate_pre_submission(
        self,
        intent: TradeIntent,
        *,
        position: Position | FinancialPositionState | str | None,
        account: AccountState | None,
        config: RiskConfig,
        instrument: Instrument | str,
        quote: ExecutableQuote,
    ) -> RiskDecision:
        phase = RiskPhase.PRE_SUBMISSION
        common = self._common(
            phase, intent, position, account, config, instrument
        )
        if common is not None:
            return common
        if (
            type(quote) is not ExecutableQuote
            or not self._positive(quote.bid)
            or not self._positive(quote.ask)
        ):
            return self._reject(phase, RiskRejection.INVALID_STOP)
        assert account is not None
        assert intent.direction is not None and intent.stop is not None
        entry = quote.ask if intent.direction is Direction.LONG else quote.bid
        valid_geometry = (
            intent.stop < entry
            if intent.direction is Direction.LONG
            else intent.stop > entry
        )
        if not valid_geometry:
            return self._reject(phase, RiskRejection.INVALID_STOP)
        assert config.risk_per_trade is not None
        equity = account.equity
        risk_rate = config.risk_per_trade
        assert type(equity) is Decimal and type(risk_rate) is Decimal
        budget = equity * risk_rate
        loss_per_unit = abs(entry - intent.stop)
        quantity = (budget / loss_per_unit).to_integral_value(rounding=ROUND_FLOOR)
        if quantity < 1 or quantity != quantity.to_integral_value():
            return self._reject(phase, RiskRejection.INVALID_QUANTITY)
        actual_risk = quantity * loss_per_unit
        if actual_risk > budget:
            return self._reject(phase, RiskRejection.INVALID_QUANTITY)
        assert intent.target is not None
        target = intent.target.resolve(entry, intent.stop, intent.direction)
        return RiskDecision(
            phase=phase, approved=True, entry_price=entry, stop_price=intent.stop,
            target_price=target, risk_budget=budget, quantity=quantity,
            actual_risk=actual_risk,
        )

    def _common(
        self, phase: RiskPhase, intent: TradeIntent,
        position: Position | FinancialPositionState | str | None,
        account: AccountState | None, config: RiskConfig,
        instrument: Instrument | str,
    ) -> RiskDecision | None:
        if instrument is not Instrument.EUR_USD or (
            account is not None and account.base_currency != "USD"
        ):
            return self._reject(phase, RiskRejection.UNSUPPORTED_INSTRUMENT_ECONOMICS)
        if position is None:
            return self._reject(phase, RiskRejection.ACCOUNT_STATE_UNKNOWN)
        if not self._flat(position):
            return self._reject(phase, RiskRejection.POSITION_ALREADY_OPEN)
        if account is None or not self._positive(account.equity):
            return self._reject(phase, RiskRejection.ACCOUNT_STATE_UNKNOWN)
        if (
            intent.action not in (Action.OPEN_LONG, Action.OPEN_SHORT)
            or intent.direction is None
        ):
            return self._reject(phase, RiskRejection.INVALID_STOP)
        expected = (
            Direction.LONG if intent.action is Action.OPEN_LONG else Direction.SHORT
        )
        if (
            intent.direction is not expected
            or not self._positive(intent.stop)
            or intent.target is None
        ):
            return self._reject(phase, RiskRejection.INVALID_STOP)
        if not self._positive(config.risk_per_trade) or config.risk_per_trade >= 1:
            return self._reject(phase, RiskRejection.INVALID_QUANTITY)
        return None

    @staticmethod
    def _flat(position: Position | FinancialPositionState | str) -> bool:
        state: Any = position.state if isinstance(position, Position) else position
        return state in (FinancialPositionState.FLAT, "FLAT")

    @staticmethod
    def _positive(value: Decimal | None) -> bool:
        return type(value) is Decimal and value.is_finite() and value > 0

    @staticmethod
    def _reject(phase: RiskPhase, reason: RiskRejection) -> RiskDecision:
        return RiskDecision(phase=phase, approved=False, rejection=reason)


__all__ = [
    "AccountState", "ExecutableQuote", "RiskConfig", "RiskDecision", "RiskPhase",
    "RiskRejection", "RiskService", "TradeIntent",
]
