"""Small, deterministic, fail-closed Risk service for Phase 3.

Risk accepts facts explicitly.  It does not read persistence, call a broker,
or submit an Order.  In particular, Strategy owns neither account state nor
quantity sizing.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Any

from backend.domain.broker import (
    AccountSnapshot,
    VenueInstrumentFacts,
)
from backend.domain.broker import ExecutableQuote as BrokerExecutableQuote
from backend.domain.market_data import Instrument
from backend.domain.strategy import Action, Direction, TargetMethodology, TargetProposal
from backend.domain.trading import FinancialPositionState, Position


def _empty_evidence() -> Mapping[str, object]:
    return {}


class RiskPhase(StrEnum):
    PRE_FLIGHT = "PRE_FLIGHT"
    PRE_SUBMISSION = "PRE_SUBMISSION"


class RiskRejection(StrEnum):
    POSITION_ALREADY_OPEN = "POSITION_ALREADY_OPEN"
    INVALID_STOP = "INVALID_STOP"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    ACCOUNT_STATE_UNKNOWN = "ACCOUNT_STATE_UNKNOWN"
    EXPERIMENT_NOT_RUNNING = "EXPERIMENT_NOT_RUNNING"
    UNSUPPORTED_INSTRUMENT_ECONOMICS = "UNSUPPORTED_INSTRUMENT_ECONOMICS"
    DEPLOYMENT_NOT_RUNNING = "DEPLOYMENT_NOT_RUNNING"
    RISK_LIMIT_REACHED = "RISK_LIMIT_REACHED"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    STALE_QUOTE = "STALE_QUOTE"
    VENUE_UNAVAILABLE = "VENUE_UNAVAILABLE"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    INVALID_PRICE_BOUND = "INVALID_PRICE_BOUND"


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
    quote_bid: Decimal | None = None
    quote_ask: Decimal | None = None
    quote_observed_at: datetime | None = None
    price_bound: Decimal | None = None
    target_methodology: str | None = None
    target_multiple: Decimal | None = None
    evidence: Mapping[str, object] = field(default_factory=_empty_evidence)


class RiskService:
    """The sole Phase 3 authority for entry eligibility and sizing."""

    def evaluate_pre_flight(
        self,
        intent: TradeIntent,
        *,
        experiment_status: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountState | None,
        config: RiskConfig,
        instrument: Instrument | str,
    ) -> RiskDecision:
        common = self._common(
            RiskPhase.PRE_FLIGHT, intent, experiment_status, position, account,
            config, instrument,
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
        experiment_status: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountState | None,
        config: RiskConfig,
        instrument: Instrument | str,
        quote: ExecutableQuote,
    ) -> RiskDecision:
        phase = RiskPhase.PRE_SUBMISSION
        common = self._common(
            phase, intent, experiment_status, position, account, config, instrument
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
        self, phase: RiskPhase, intent: TradeIntent, experiment_status: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountState | None, config: RiskConfig,
        instrument: Instrument | str,
    ) -> RiskDecision | None:
        if instrument is not Instrument.EUR_USD or (
            account is not None and account.base_currency != "USD"
        ):
            return self._reject(phase, RiskRejection.UNSUPPORTED_INSTRUMENT_ECONOMICS)
        if experiment_status != "RUNNING":
            return self._reject(phase, RiskRejection.EXPERIMENT_NOT_RUNNING)
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


@dataclass(frozen=True, slots=True)
class PaperRiskConfig:
    """The small immutable Risk snapshot used by the PAPER composition."""

    risk_per_trade: Decimal
    max_quote_age: timedelta = timedelta(minutes=1)
    max_open_positions: int = 1

    def __post_init__(self) -> None:
        if (
            type(self.risk_per_trade) is not Decimal
            or not self.risk_per_trade.is_finite()
        ):
            raise ValueError("risk_per_trade must be a finite Decimal")
        if self.risk_per_trade <= 0 or self.risk_per_trade >= 1:
            raise ValueError("risk_per_trade must be greater than zero and below one")
        if (
            type(self.max_quote_age) is not timedelta
            or self.max_quote_age <= timedelta(0)
        ):
            raise ValueError("max_quote_age must be positive")
        if type(self.max_open_positions) is not int or self.max_open_positions != 1:
            raise ValueError("PAPER 01 supports exactly one open Position")


class PaperRiskService:
    """Pure PAPER Risk composition over normalized broker facts.

    This deliberately lives beside, rather than inside, the historical Risk
    path.  Experiments retain their existing target-at-quote semantics; PAPER
    keeps the target methodology in PRE_SUBMISSION and resolves its price only
    after an authoritative broker Fill.
    """

    def evaluate_pre_flight(
        self,
        intent: TradeIntent,
        *,
        deployment_state: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountSnapshot | None,
        instrument: VenueInstrumentFacts | None,
        config: PaperRiskConfig,
        evaluated_at: datetime,
        reconciliation_required: bool = False,
        pending_entry: bool = False,
    ) -> RiskDecision:
        phase = RiskPhase.PRE_FLIGHT
        common = self._common(
            phase, intent, deployment_state, position, account, instrument, config,
            reconciliation_required=reconciliation_required,
            pending_entry=pending_entry,
        )
        if common is not None:
            return common
        if (
            type(evaluated_at) is not datetime
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() != timedelta(0)
        ):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.ACCOUNT_STATE_UNKNOWN,
            )
        assert intent.stop is not None and intent.target is not None
        return RiskDecision(
            phase=phase,
            approved=True,
            stop_price=intent.stop,
            target_methodology=intent.target.methodology.value,
            target_multiple=intent.target.multiple,
        )

    def evaluate_pre_submission(
        self,
        intent: TradeIntent,
        *,
        deployment_state: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountSnapshot | None,
        instrument: VenueInstrumentFacts | None,
        config: PaperRiskConfig,
        quote: BrokerExecutableQuote,
        evaluated_at: datetime,
        reconciliation_required: bool = False,
    ) -> RiskDecision:
        phase = RiskPhase.PRE_SUBMISSION
        common = self._common(
            phase, intent, deployment_state, position, account, instrument, config,
            reconciliation_required=reconciliation_required,
            pending_entry=False,
        )
        if common is not None:
            return common
        assert account is not None and instrument is not None
        if (
            type(evaluated_at) is not datetime
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() != timedelta(0)
        ):
            return self._reject(phase, RiskRejection.ACCOUNT_STATE_UNKNOWN)
        if type(quote) is not BrokerExecutableQuote or not quote.is_fresh(
            evaluated_at, config.max_quote_age
        ):
            return self._reject(phase, RiskRejection.STALE_QUOTE)
        assert (
            intent.direction is not None
            and intent.stop is not None
            and intent.target is not None
        )
        entry = quote.price_for(intent.direction)
        if (intent.direction is Direction.LONG and intent.stop >= entry) or (
            intent.direction is Direction.SHORT and intent.stop <= entry
        ):
            return self._reject(phase, RiskRejection.INVALID_STOP)

        increment = Decimal(1).scaleb(-instrument.trade_units_precision)
        budget = account.equity * config.risk_per_trade
        loss_per_unit = abs(entry - intent.stop)
        raw_quantity = budget / loss_per_unit
        margin_per_unit = entry * instrument.margin_rate
        if margin_per_unit <= 0:
            return self._reject(phase, RiskRejection.INSUFFICIENT_MARGIN)
        raw_quantity = min(raw_quantity, account.margin_available / margin_per_unit)
        if instrument.maximum_order_units is not None:
            raw_quantity = min(raw_quantity, instrument.maximum_order_units)
        if instrument.maximum_position_units is not None:
            raw_quantity = min(raw_quantity, instrument.maximum_position_units)
        quantity = (
            raw_quantity / increment
        ).to_integral_value(rounding=ROUND_FLOOR) * increment
        if quantity < instrument.minimum_order_units or quantity <= 0:
            return self._reject(phase, RiskRejection.INVALID_QUANTITY)
        actual_risk = quantity * loss_per_unit
        if actual_risk > budget:
            return self._reject(phase, RiskRejection.INVALID_QUANTITY)
        required_margin = quantity * margin_per_unit
        if required_margin > account.margin_available:
            return self._reject(phase, RiskRejection.INSUFFICIENT_MARGIN)
        price_bound = self._safe_price_bound(
            entry, intent.direction, instrument.display_precision
        )
        if price_bound is None:
            return self._reject(phase, RiskRejection.INVALID_PRICE_BOUND)
        return RiskDecision(
            phase=phase,
            approved=True,
            entry_price=entry,
            stop_price=intent.stop,
            # PAPER target is intentionally not final until the Fill exists.
            target_price=None,
            risk_budget=budget,
            quantity=quantity,
            actual_risk=actual_risk,
            quote_bid=quote.bid,
            quote_ask=quote.ask,
            quote_observed_at=quote.quote_time,
            price_bound=price_bound,
            target_methodology=intent.target.methodology.value,
            target_multiple=intent.target.multiple,
            evidence={
                "quote_source": quote.source,
                "quote_tradeable": quote.tradeable,
                "margin_available": str(account.margin_available),
                "margin_required": str(required_margin),
                "unit_increment": str(increment),
            },
        )

    def evaluate(
        self,
        intent: TradeIntent,
        *,
        deployment_state: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountSnapshot | None,
        instrument: VenueInstrumentFacts | None,
        config: PaperRiskConfig,
        quote: BrokerExecutableQuote,
        evaluated_at: datetime,
        reconciliation_required: bool = False,
        pending_entry: bool = False,
    ) -> tuple[RiskDecision, RiskDecision | None]:
        """Run the only valid PAPER authorization sequence."""
        pre_flight = self.evaluate_pre_flight(
            intent,
            deployment_state=deployment_state,
            position=position,
            account=account,
            instrument=instrument,
            config=config,
            evaluated_at=evaluated_at,
            reconciliation_required=reconciliation_required,
            pending_entry=pending_entry,
        )
        if not pre_flight.approved:
            return pre_flight, None
        return pre_flight, self.evaluate_pre_submission(
            intent,
            deployment_state=deployment_state,
            position=position,
            account=account,
            instrument=instrument,
            config=config,
            quote=quote,
            evaluated_at=evaluated_at,
            reconciliation_required=reconciliation_required,
        )

    @staticmethod
    def _common(
        phase: RiskPhase,
        intent: TradeIntent,
        deployment_state: str,
        position: Position | FinancialPositionState | str | None,
        account: AccountSnapshot | None,
        instrument: VenueInstrumentFacts | None,
        config: PaperRiskConfig,
        *,
        reconciliation_required: bool,
        pending_entry: bool,
    ) -> RiskDecision | None:
        if deployment_state != "RUNNING":
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.DEPLOYMENT_NOT_RUNNING,
            )
        if reconciliation_required:
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.RECONCILIATION_REQUIRED,
            )
        if pending_entry:
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.RISK_LIMIT_REACHED,
            )
        if position is None:
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.ACCOUNT_STATE_UNKNOWN,
            )
        state: Any = position.state if isinstance(position, Position) else position
        if state not in (FinancialPositionState.FLAT, "FLAT"):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.POSITION_ALREADY_OPEN,
            )
        if (
            account is None
            or not account.fresh
            or account.identity.mode.value != "PAPER"
        ):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.ACCOUNT_STATE_UNKNOWN,
            )
        if (
            account.identity.environment != "Practice"
            or account.identity.base_currency != "USD"
            or not account.account_state_known
            or account.has_open_position
        ):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.ACCOUNT_STATE_UNKNOWN,
            )
        if instrument is None or not instrument.available:
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.VENUE_UNAVAILABLE,
            )
        if not all(
            instrument.supports(capability)
            for capability in ("MARKET", "STOP_LOSS", "TAKE_PROFIT")
        ):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.UNSUPPORTED_CAPABILITY,
            )
        if (
            intent.action not in (Action.OPEN_LONG, Action.OPEN_SHORT)
            or intent.direction is None
            or intent.stop is None
            or intent.target is None
        ):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.INVALID_STOP,
            )
        expected = (
            Direction.LONG if intent.action is Action.OPEN_LONG else Direction.SHORT
        )
        if (
            intent.direction is not expected
            or intent.target.methodology is not TargetMethodology.R_MULTIPLE
        ):
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.INVALID_STOP,
            )
        if type(config) is not PaperRiskConfig:
            return RiskDecision(
                phase=phase,
                approved=False,
                rejection=RiskRejection.INVALID_QUANTITY,
            )
        return None

    @staticmethod
    def _reject(phase: RiskPhase, reason: RiskRejection) -> RiskDecision:
        return RiskDecision(phase=phase, approved=False, rejection=reason)

    @staticmethod
    def _safe_price_bound(
        entry: Decimal, direction: Direction, precision: int
    ) -> Decimal | None:
        quantum = Decimal(1).scaleb(-precision)
        rounding = ROUND_FLOOR if direction is Direction.LONG else ROUND_CEILING
        bound = entry.quantize(quantum, rounding=rounding)
        return bound if bound > 0 else None


__all__ = [
    "AccountState", "ExecutableQuote", "PaperRiskConfig", "PaperRiskService",
    "RiskConfig", "RiskDecision", "RiskPhase", "RiskRejection", "RiskService",
    "TradeIntent",
]
