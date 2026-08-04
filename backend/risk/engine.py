"""Deterministic, broker-agnostic pre-trade risk evaluation."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from enum import StrEnum
from inspect import isawaitable
from typing import Protocol, cast
from uuid import UUID, uuid4

import structlog

from backend.config import RiskConfig
from backend.core.account_mode import AccountMode
from backend.core.events import (
    EventBus,
    EventHandler,
    RiskApproved,
    RiskRejected,
    SignalGenerated,
    Subscription,
)
from backend.data.models import Instrument
from backend.strategy.contracts import Signal, SignalDirection

logger = structlog.get_logger(__name__)
ZERO = Decimal("0")


class PositionStatus(StrEnum):
    OPEN = "open"
    REDUCING = "reducing"


@dataclass(frozen=True, slots=True)
class PositionInfo:
    """Minimal immutable position snapshot required by the risk evaluator."""

    account_id: UUID
    bot_id: UUID | None
    instrument_id: UUID
    direction: SignalDirection
    quantity: Decimal
    status: PositionStatus
    strategy_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Caller-owned account, market, and simulation-time snapshot."""

    equity: Decimal
    available_balance: Decimal
    open_positions: tuple[PositionInfo, ...]
    entry_price: Decimal
    instrument: Instrument
    bot_id: UUID
    account_id: UUID
    mode: AccountMode
    clock_timestamp: datetime


class RiskContextProvider(Protocol):
    """Pipeline-owned provider of a fresh context for each signal."""

    def get_context(self, signal: Signal) -> RiskContext | Awaitable[RiskContext]:
        """Return the current account and instrument snapshot."""


class _Reject(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.reason = f"{code}: {detail}"


ReservationKey = tuple[UUID, UUID, UUID, AccountMode]
ContextProviderLike = RiskContextProvider | Callable[[Signal], RiskContext | Awaitable[RiskContext]]


class RiskEngine:
    """Evaluate signals synchronously and adapt them to the asynchronous EventBus."""

    def __init__(
        self,
        event_bus: EventBus,
        bot_id: UUID,
        account_id: UUID,
        mode: AccountMode,
        config: RiskConfig,
        context_provider: ContextProviderLike,
    ) -> None:
        self._event_bus = event_bus
        self._bot_id = bot_id
        self._account_id = account_id
        self._mode = mode
        self._config = config
        self._context_provider = context_provider
        self._reservations: set[ReservationKey] = set()
        self._subscription: Subscription = event_bus.subscribe(
            SignalGenerated,
            cast("EventHandler", self._handler),
        )

    def evaluate(self, signal: Signal, context: RiskContext) -> RiskApproved | RiskRejected:
        """Evaluate one signal without I/O or mutation.

        Business rule failures are represented as ``RiskRejected``. Unexpected programming or
        provider-independent errors are deliberately allowed to propagate to the adapter.
        """
        try:
            self._validate_identity(signal, context)
            if signal.direction is SignalDirection.CLOSE:
                return RiskApproved(
                    signal=signal,
                    position_size=ZERO,
                    stop_loss=ZERO,
                    take_profit=ZERO,
                    occurred_at=context.clock_timestamp,
                )
            self._validate_entry_context(context)
            reservation_key = (
                context.account_id,
                signal.instrument_id,
                signal.strategy_version_id,
                context.mode,
            )
            self._check_position_conflict(context, reservation_key, signal.strategy_version_id)
            stop = self._resolve_stop(signal.direction, context.entry_price)
            stop = self._round_stop(signal.direction, stop, context.instrument)
            if (
                not _finite_positive(stop)
                or (signal.direction is SignalDirection.BUY and stop >= context.entry_price)
                or (signal.direction is SignalDirection.SELL and stop <= context.entry_price)
            ):
                raise _Reject("invalid_stop", "rounded stop has invalid geometry")
            stop_distance = abs(context.entry_price - stop)
            if not _finite_positive(stop_distance):
                raise _Reject("invalid_stop", "rounded stop distance must be positive")
            take_profit = self._resolve_take_profit(
                signal.direction, context.entry_price, stop_distance, context.instrument
            )
            quantity = self._calculate_quantity(context.equity, stop_distance, context.instrument)
            self._validate_quantity(quantity, context.entry_price, context.instrument)
            return RiskApproved(
                signal=signal,
                position_size=quantity,
                stop_loss=stop,
                take_profit=take_profit,
                occurred_at=context.clock_timestamp,
            )
        except _Reject as rejection:
            return RiskRejected(
                signal=signal,
                reason=rejection.reason,
                occurred_at=_safe_event_timestamp(context, signal),
            )

    async def _handler(self, event: SignalGenerated) -> None:
        """Filter one signal, obtain a fresh context, and publish exactly one decision."""
        if event.bot_id != self._bot_id:
            return
        if event.account_id != self._account_id or event.mode is not self._mode:
            await self._publish_rejection(
                event, "identity_mismatch: event scope does not match engine"
            )
            return
        try:
            context = self._get_context(event.signal)
            if isawaitable(context):
                context = await context
            decision = self.evaluate(event.signal, context)
            if (
                isinstance(decision, RiskApproved)
                and event.signal.direction is not SignalDirection.CLOSE
            ):
                key = (
                    self._account_id,
                    event.signal.instrument_id,
                    event.signal.strategy_version_id,
                    self._mode,
                )
                self._reservations.add(key)
            await self._event_bus.publish(
                replace(
                    decision,
                    event_id=uuid4(),
                    account_id=event.account_id,
                    bot_id=event.bot_id,
                    mode=event.mode,
                    correlation_id=event.correlation_id,
                )
            )
        except Exception:
            logger.exception(
                "risk_evaluation_failed",
                bot_id=str(self._bot_id),
                account_id=str(self._account_id),
                signal_instrument_id=str(event.signal.instrument_id),
                correlation_id=str(event.correlation_id),
            )
            raise

    def _get_context(self, signal: Signal) -> RiskContext | Awaitable[RiskContext]:
        provider = self._context_provider
        if callable(provider) and not hasattr(provider, "get_context"):
            return provider(signal)
        return provider.get_context(signal)

    async def _publish_rejection(self, event: SignalGenerated, reason: str) -> None:
        await self._event_bus.publish(
            RiskRejected(
                signal=event.signal,
                reason=reason,
                account_id=event.account_id,
                bot_id=event.bot_id,
                mode=event.mode,
                correlation_id=event.correlation_id,
            )
        )

    def _validate_identity(self, signal: Signal, context: RiskContext) -> None:
        if context.bot_id != self._bot_id or context.account_id != self._account_id:
            raise _Reject("identity_mismatch", "context identity does not match engine")
        if context.mode is not self._mode:
            raise _Reject("identity_mismatch", "context mode does not match engine")
        if signal.instrument_id != context.instrument.id:
            raise _Reject("identity_mismatch", "signal instrument does not match context")
        if not isinstance(context.clock_timestamp, datetime) or (
            context.clock_timestamp.tzinfo is None
            or context.clock_timestamp.utcoffset() != timedelta(0)
        ):
            raise _Reject("invalid_timestamp", "context timestamp must be UTC")

    def _validate_entry_context(self, context: RiskContext) -> None:
        if not context.instrument.is_active:
            raise _Reject("invalid_instrument_constraint", "instrument is inactive")
        if not _finite_non_negative(context.equity):
            raise _Reject("invalid_equity", "equity must be finite and non-negative")
        if not _finite_non_negative(context.available_balance):
            raise _Reject("invalid_balance", "available balance must be finite and non-negative")
        if not _finite_positive(context.entry_price):
            raise _Reject("invalid_entry_price", "entry price must be finite and positive")
        risk = self._config.per_trade_risk
        if not _finite_positive(risk) or risk > Decimal("0.02"):
            raise _Reject("risk_limit_exceeded", "per-trade risk must be at most 0.02")

    def _check_position_conflict(
        self, context: RiskContext, key: ReservationKey, strategy_version_id: UUID
    ) -> None:
        scoped_positions = {
            (context.account_id, context.mode, position.instrument_id)
            for position in context.open_positions
            if position.account_id == context.account_id
            and position.status in (PositionStatus.OPEN, PositionStatus.REDUCING)
            and (
                position.strategy_version_id == strategy_version_id
                or (position.strategy_version_id is None and position.bot_id == context.bot_id)
            )
        }
        # A RiskContext is a mode-scoped snapshot. Keep mode in the derived scope key rather
        # than treating positions from another execution mode as interchangeable state.
        instrument_key = (context.account_id, context.mode, context.instrument.id)
        if instrument_key in scoped_positions:
            raise _Reject("direction_conflict", "an open net position already exists")
        if key in self._reservations:
            raise _Reject("pending_entry", "an entry for this instrument is pending")
        pending: set[tuple[UUID, AccountMode, UUID]] = set()
        for account, instrument, _strategy, mode in self._reservations:
            if account == context.account_id and mode is context.mode:
                pending.add((account, mode, instrument))
        if len(scoped_positions | pending) >= self._config.max_open_positions:
            raise _Reject("max_open_positions", "maximum open positions reached")

    def _resolve_stop(self, direction: SignalDirection, entry: Decimal) -> Decimal:
        source = self._config.stop_source
        value = {
            "percentage_of_entry": self._config.stop_percentage,
            "absolute_price_distance": self._config.stop_distance,
            "explicit_stop_price": self._config.stop_price,
        }.get(source)
        if not isinstance(value, Decimal) or not _finite_positive(value):
            raise _Reject("missing_stop", "selected stop source is not configured")
        if source == "percentage_of_entry":
            distance = entry * value
            stop = entry - distance if direction is SignalDirection.BUY else entry + distance
        elif source == "absolute_price_distance":
            stop = entry - value if direction is SignalDirection.BUY else entry + value
        else:
            stop = value
        if (
            not _finite_positive(stop)
            or (direction is SignalDirection.BUY and stop >= entry)
            or (direction is SignalDirection.SELL and stop <= entry)
        ):
            raise _Reject("invalid_stop", "stop is on the wrong side of entry")
        return stop

    def _round_stop(
        self, direction: SignalDirection, stop: Decimal, instrument: Instrument
    ) -> Decimal:
        tick = self._constraint(instrument, "tick_size")
        rounding = ROUND_FLOOR if direction is SignalDirection.BUY else ROUND_CEILING
        return (stop / tick).to_integral_value(rounding=rounding) * tick

    def _resolve_take_profit(
        self, direction: SignalDirection, entry: Decimal, distance: Decimal, instrument: Instrument
    ) -> Decimal:
        ratio = self._config.take_profit_risk_reward
        if ratio is None:
            return ZERO
        if not _finite_positive(ratio):
            raise _Reject("invalid_take_profit", "risk/reward must be positive and finite")
        raw = (
            entry + distance * ratio
            if direction is SignalDirection.BUY
            else entry - distance * ratio
        )
        tick = self._constraint(instrument, "tick_size")
        rounding = ROUND_CEILING if direction is SignalDirection.BUY else ROUND_FLOOR
        take = (raw / tick).to_integral_value(rounding=rounding) * tick
        if (direction is SignalDirection.BUY and take <= entry) or (
            direction is SignalDirection.SELL and take >= entry
        ):
            raise _Reject("invalid_take_profit", "take-profit has invalid geometry")
        return take

    def _calculate_quantity(
        self, equity: Decimal, distance: Decimal, instrument: Instrument
    ) -> Decimal:
        step = self._constraint(instrument, "step_size")
        raw = equity * self._config.per_trade_risk / distance
        return (raw / step).to_integral_value(rounding=ROUND_FLOOR) * step

    def _validate_quantity(self, quantity: Decimal, entry: Decimal, instrument: Instrument) -> None:
        step = self._constraint(instrument, "step_size")
        min_qty = self._optional_constraint(instrument, "min_qty") or ZERO
        max_qty = self._optional_constraint(instrument, "max_qty")
        min_notional = self._optional_constraint(instrument, "min_notional") or ZERO
        if quantity <= ZERO or quantity % step != ZERO:
            raise _Reject("invalid_quantity", "quantity is not a positive step multiple")
        if quantity < min_qty or (max_qty is not None and quantity > max_qty):
            raise _Reject("invalid_quantity", "quantity violates instrument limits")
        if quantity * entry < min_notional:
            raise _Reject("quantity_below_min_notional", "quantity does not meet minimum notional")

    @staticmethod
    def _constraint(instrument: Instrument, name: str) -> Decimal:
        try:
            value = Decimal(str(instrument.constraints[name]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as error:
            raise _Reject("invalid_instrument_constraint", f"{name} is required") from error
        if not _finite_positive(value):
            raise _Reject("invalid_instrument_constraint", f"{name} must be positive and finite")
        return value

    @staticmethod
    def _optional_constraint(instrument: Instrument, name: str) -> Decimal | None:
        value = instrument.constraints.get(name)
        if value is None:
            return ZERO if name != "max_qty" else None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise _Reject("invalid_instrument_constraint", f"{name} is malformed") from error
        if not result.is_finite() or result < ZERO:
            raise _Reject(
                "invalid_instrument_constraint", f"{name} must be finite and non-negative"
            )
        return result

    def release_reservation(
        self,
        instrument_id: UUID,
        mode: AccountMode | None = None,
        strategy_version_id: UUID | None = None,
    ) -> None:
        """Release a terminal reservation, scoped to strategy when identity is available.

        ``strategy_version_id=None`` is an intentional full-scope fallback for lifecycle
        callers that genuinely cannot recover strategy identity (for example, an old
        un-attributed cancellation record).
        """
        selected_mode = mode or self._mode
        retained: set[ReservationKey] = set()
        for account, reserved_instrument, strategy, reserved_mode in self._reservations:
            if not (
                account == self._account_id
                and reserved_instrument == instrument_id
                and reserved_mode is selected_mode
                and (
                    strategy_version_id is None
                    or strategy == strategy_version_id
                )
            ):
                retained.add((account, reserved_instrument, strategy, reserved_mode))
        self._reservations = retained

    def reset(self) -> None:
        """Clear transient reservations during pipeline reset or restart."""
        self._reservations.clear()

    def reset_reservations(self) -> None:
        """Explicit lifecycle alias for clearing transient pending entries."""
        self.reset()

    def on_terminal_outcome(
        self,
        instrument_id: UUID,
        mode: AccountMode | None = None,
        strategy_version_id: UUID | None = None,
    ) -> None:
        """Release a terminal order reservation with strategy-aware attribution."""
        self.release_reservation(instrument_id, mode, strategy_version_id)

    def unsubscribe(self) -> None:
        """Remove the engine's EventBus subscription."""
        self._subscription.unsubscribe()

    def close(self) -> None:
        """Release the EventBus subscription and transient state."""
        self.unsubscribe()
        self.reset()


def _finite_positive(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value > ZERO


def _finite_non_negative(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value >= ZERO


def _safe_event_timestamp(context: RiskContext, signal: Signal) -> datetime:
    """Keep business rejections constructible when the supplied clock is invalid."""
    if (
        isinstance(context.clock_timestamp, datetime)
        and context.clock_timestamp.tzinfo is not None
        and context.clock_timestamp.utcoffset() == timedelta(0)
    ):
        return context.clock_timestamp
    return signal.candle_timestamp
