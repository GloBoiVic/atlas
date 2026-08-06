"""Account-netted execution coordination and the RiskApproved adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode

if TYPE_CHECKING:
    from datetime import datetime

    from backend.execution.broker import Broker
    from backend.persistence.repositories.protocols import ExecutionRepository

from backend.core.events import (
    EventBus,
    EventHandler,
    OrderFailed,
    OrderFilled,
    OrderRejected,
    OrderSubmitted,
    PositionClosed,
    PositionOpened,
    PositionUpdated,
    RiskApproved,
    Subscription,
    TradeClosed,
)
from backend.execution.models import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    PositionSide,
    PositionStatus,
    Trade,
    TradeStatus,
)
from backend.strategy.contracts import SignalDirection

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class VirtualPosition:
    """A strategy-owned exposure; it is never submitted to a broker."""

    account_id: UUID
    bot_id: UUID
    strategy_version_id: UUID
    instrument_id: UUID
    mode: AccountMode
    side: PositionSide
    quantity: Decimal
    opened_at: datetime
    signal_metadata: dict[str, object]


class AccountExposureCoordinator:
    """Serialize one account/instrument and translate virtual targets to net orders."""

    def __init__(self, repository: ExecutionRepository) -> None:
        self._repository = repository
        self._virtual: dict[tuple[UUID, UUID, UUID, UUID, AccountMode], VirtualPosition] = {}
        self._locks: dict[tuple[UUID, UUID, AccountMode], asyncio.Lock] = {}
        self._blocked: set[tuple[UUID, UUID, AccountMode]] = set()

    def _lock(self, key: tuple[UUID, UUID, AccountMode]) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def apply_approval(self, event: RiskApproved, submit: SubmitOrder) -> tuple[Order, ...]:
        signal = event.signal
        key = (
            event.account_id or UUID(int=0),
            signal.instrument_id,
            event.mode or AccountMode.PAPER,
        )
        if key in self._blocked:
            raise RuntimeError("execution_blocked: reconciliation required")
        async with self._lock(key):
            account_id = event.account_id
            mode = event.mode
            if account_id is None or mode is None or event.bot_id is None:
                raise ValueError("risk approval is missing execution identity")
            strategy_key = (
                account_id,
                event.bot_id,
                signal.strategy_version_id,
                signal.instrument_id,
                mode,
            )
            existing = self._virtual.get(strategy_key)
            if signal.direction is SignalDirection.CLOSE:
                self._virtual.pop(strategy_key, None)
            else:
                if existing is not None:
                    raise ValueError("duplicate_active_strategy_exposure")
                self._virtual[strategy_key] = VirtualPosition(
                    account_id,
                    event.bot_id,
                    signal.strategy_version_id,
                    signal.instrument_id,
                    mode,
                    PositionSide.LONG
                    if signal.direction is SignalDirection.BUY
                    else PositionSide.SHORT,
                    event.position_size,
                    signal.candle_timestamp,
                    dict(signal.metadata),
                )
            target = self._net_target(account_id, signal.instrument_id, mode)
            current_position = await self._repository.get_position(
                account_id=account_id, instrument_id=signal.instrument_id, mode=mode
            )
            current = self._signed(current_position)
            orders: list[Order] = []
            if (
                current != ZERO
                and target != ZERO
                and current * target < ZERO
            ):
                close = await self._submit_leg(event, current_position, -current, True, submit)
                orders.append(close)
                if close.status is not OrderStatus.FILLED:
                    self._blocked.add(key)
                    return tuple(orders)
                current = ZERO
            delta = target - current
            if delta != ZERO:
                reduce_only = current != ZERO and current * delta < ZERO
                orders.append(
                    await self._submit_leg(event, current_position, delta, reduce_only, submit)
                )
            return tuple(orders)

    def _net_target(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> Decimal:
        total = ZERO
        for exposure in self._virtual.values():
            if (exposure.account_id, exposure.instrument_id, exposure.mode) == (
                account_id,
                instrument_id,
                mode,
            ):
                total += (
                    exposure.quantity if exposure.side is PositionSide.LONG else -exposure.quantity
                )
        return total

    def allocate_reduction(
        self,
        account_id: UUID,
        instrument_id: UUID,
        mode: AccountMode,
        side: PositionSide,
        quantity: Decimal,
    ) -> tuple[tuple[VirtualPosition, Decimal], ...]:
        """Attribute a net reduction to opposing virtual positions FIFO."""
        remaining = quantity
        allocations: list[tuple[VirtualPosition, Decimal]] = []
        candidates = sorted(
            (
                exposure
                for exposure in self._virtual.values()
                if exposure.account_id == account_id
                and exposure.instrument_id == instrument_id
                and exposure.mode == mode
                and exposure.side is side
            ),
            key=lambda exposure: (exposure.opened_at, exposure.strategy_version_id),
        )
        for exposure in candidates:
            if remaining <= ZERO:
                break
            amount = min(remaining, exposure.quantity)
            allocations.append((exposure, amount))
            remaining -= amount
        if remaining > ZERO:
            raise ValueError("reduction exceeds virtual exposure")
        return tuple(allocations)

    @staticmethod
    def _signed(position: Position | None) -> Decimal:
        if position is None or position.status is PositionStatus.CLOSED:
            return ZERO
        return position.quantity if position.side is PositionSide.LONG else -position.quantity

    async def _submit_leg(
        self,
        event: RiskApproved,
        position: Position | None,
        signed_quantity: Decimal,
        reduce_only: bool,
        submit: SubmitOrder,
    ) -> Order:
        signal = event.signal
        side = OrderSide.BUY if signed_quantity > ZERO else OrderSide.SELL
        quantity = signed_quantity.copy_abs()
        order = Order(
            account_id=event.account_id or UUID(int=0),
            instrument_id=signal.instrument_id,
            bot_id=event.bot_id,
            strategy_version_id=signal.strategy_version_id,
            mode=event.mode,
            side=side,
            quantity=quantity,
            client_order_id=str(uuid4()),
            reduce_only=reduce_only,
            stop_loss=event.stop_loss,
            take_profit=event.take_profit,
            signal=signal,
        )
        return await submit(order, event, position)

    def block(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> None:
        self._blocked.add((account_id, instrument_id, mode))

    def clear_block(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> None:
        """Allow new orders only after a successful authoritative reconciliation."""
        self._blocked.discard((account_id, instrument_id, mode))

    def is_blocked(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> bool:
        return (account_id, instrument_id, mode) in self._blocked


class SubmitOrder(Protocol):
    async def __call__(
        self, order: Order, event: RiskApproved, prior: Position | None
    ) -> Order: ...


class ExecutionEngine:
    """Consume only RiskApproved events and persist every fact before publishing it."""

    def __init__(
        self,
        event_bus: EventBus,
        broker: Broker,
        repository: ExecutionRepository,
        *,
        bot_id: UUID | None = None,
        coordinator: AccountExposureCoordinator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._broker = broker
        self._repository = repository
        self._bot_id = bot_id
        self._coordinator = coordinator or AccountExposureCoordinator(repository)
        self._execution_enabled = True
        self._subscription: Subscription = event_bus.subscribe(
            RiskApproved, cast("EventHandler", self._on_approved)
        )

    @property
    def coordinator(self) -> AccountExposureCoordinator:
        """Return the account coordinator used by this isolated execution engine."""
        return self._coordinator

    async def _on_approved(self, event: RiskApproved) -> None:
        if self._bot_id is not None and event.bot_id != self._bot_id:
            return
        if not self._execution_enabled:
            return
        await self._coordinator.apply_approval(event, self._submit)

    def set_execution_enabled(self, enabled: bool) -> None:
        """Gate new broker submissions while retaining event subscriptions."""
        self._execution_enabled = enabled

    @property
    def execution_enabled(self) -> bool:
        """Whether RiskApproved events may submit orders."""
        return self._execution_enabled

    async def _submit(self, order: Order, event: RiskApproved, prior: Position | None) -> Order:
        # create_order is the durable idempotency fence and deliberately precedes I/O.
        order = await self._repository.create_order(order)
        result = await self._broker.submit_order(order, order.client_order_id)
        if result.unknown:
            await self._save_order(replace(order, status=OrderStatus.UNKNOWN))
            self._coordinator.block(
                order.account_id, order.instrument_id, order.mode or AccountMode.PAPER
            )
            await self._event_bus.publish(
                OrderFailed(
                    order_id=order.id,
                    error="unknown_broker_result",
                    account_id=order.account_id,
                    bot_id=order.bot_id,
                    mode=order.mode,
                    occurred_at=event.occurred_at,
                    correlation_id=event.correlation_id,
                )
            )
            return replace(order, status=OrderStatus.UNKNOWN)
        if not result.success:
            rejected = (
                OrderStatus.REJECTED if result.status is OrderStatus.REJECTED else result.status
            )
            await self._save_order(replace(order, status=rejected))
            await self._event_bus.publish(
                OrderRejected(
                    order_id=order.id,
                    reason=result.error or "broker_rejected",
                    account_id=order.account_id,
                    bot_id=order.bot_id,
                    mode=order.mode,
                    occurred_at=event.occurred_at,
                    correlation_id=event.correlation_id,
                )
            )
            return replace(order, status=rejected)
        submitted = replace(order, broker_order_id=result.order_id, status=OrderStatus.SUBMITTED)
        await self._save_order(submitted)
        await self._event_bus.publish(
            OrderSubmitted(
                order=submitted,
                broker_order_id=result.order_id or "",
                account_id=order.account_id,
                bot_id=order.bot_id,
                mode=order.mode,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
            )
        )
        for fill in result.fills:
            await self._process_fill(submitted, fill, prior, event)
        status = (
            OrderStatus.FILLED
            if result.status is OrderStatus.FILLED
            else OrderStatus.PARTIALLY_FILLED
        )
        final = replace(
            submitted, status=status, filled_quantity=sum((f.quantity for f in result.fills), ZERO)
        )
        await self._save_order(final)
        return final

    async def _save_order(self, order: Order) -> None:
        await self._repository.update_order(order)

    async def _process_fill(
        self, order: Order, fill: Fill, prior: Position | None, event: RiskApproved
    ) -> None:
        if fill.broker_fill_id is not None:
            existing_fill = await self._repository.get_fill_by_broker_id(fill.broker_fill_id)
            if existing_fill is not None:
                return
        persisted_fill = await self._repository.append_fill(fill)
        position = await self._broker.get_positions()
        current = next((p for p in position if p.instrument_id == order.instrument_id), None)
        if current is None and prior is not None:
            current = replace(
                prior,
                status=PositionStatus.CLOSED,
                quantity=prior.quantity,
                current_price=fill.price,
                closed_at=fill.filled_at,
                unrealized_pnl=ZERO,
            )
        if current is not None:
            current = replace(
                current, bot_id=order.bot_id, strategy_version_id=order.strategy_version_id
            )
            await self._repository.save_position(current)
        await self._event_bus.publish(
            OrderFilled(
                order=order,
                fill=persisted_fill,
                account_id=order.account_id,
                bot_id=order.bot_id,
                    mode=order.mode,
                    occurred_at=event.occurred_at,
                    correlation_id=event.correlation_id,
            )
        )
        if current is None or current.status is PositionStatus.CLOSED:
            if current is not None:
                trade = await self._repository.get_trade_by_position(current.id)
                if trade is None:
                    trade = Trade(
                        account_id=order.account_id,
                        instrument_id=order.instrument_id,
                        position_id=current.id,
                        direction=current.side,
                        entry_price=current.entry_price,
                        quantity=current.quantity,
                        total_fees=ZERO,
                        entry_time=current.opened_at,
                        bot_id=order.bot_id,
                        strategy_version_id=order.strategy_version_id,
                    )
                gross = (
                    (fill.price - trade.entry_price) * fill.quantity
                    if trade.direction is PositionSide.LONG
                    else (trade.entry_price - fill.price) * fill.quantity
                )
                trade = replace(
                    trade,
                    total_fees=trade.total_fees + fill.fee,
                    gross_pnl=(trade.gross_pnl or ZERO) + gross,
                    net_pnl=(trade.net_pnl or ZERO) + gross - fill.fee,
                    exit_price=fill.price,
                    status=TradeStatus.EXITED,
                    exit_time=fill.filled_at,
                )
                trade = await self._repository.save_trade(trade)
                await self._event_bus.publish(
                    PositionClosed(
                        position=current,
                        account_id=order.account_id,
                        bot_id=order.bot_id,
                        mode=order.mode,
                        occurred_at=event.occurred_at,
                        correlation_id=event.correlation_id,
                    )
                )
                await self._event_bus.publish(
                    TradeClosed(
                        trade=trade,
                        account_id=order.account_id,
                        bot_id=order.bot_id,
                        mode=order.mode,
                        occurred_at=event.occurred_at,
                        correlation_id=event.correlation_id,
                    )
                )
        else:
            trade = await self._repository.get_trade_by_position(current.id)
            if trade is None:
                trade = Trade(
                    account_id=order.account_id,
                    instrument_id=order.instrument_id,
                    position_id=current.id,
                    direction=current.side,
                    entry_price=current.entry_price,
                    quantity=current.quantity,
                    total_fees=ZERO,
                    entry_time=current.opened_at,
                    bot_id=order.bot_id,
                    strategy_version_id=order.strategy_version_id,
                )
            gross = ZERO
            if order.reduce_only:
                gross = (
                    (fill.price - trade.entry_price) * fill.quantity
                    if trade.direction is PositionSide.LONG
                    else (trade.entry_price - fill.price) * fill.quantity
                )
            trade = replace(
                trade,
                total_fees=trade.total_fees + fill.fee,
                gross_pnl=(trade.gross_pnl or ZERO) + gross,
                net_pnl=(trade.net_pnl or ZERO) + gross - fill.fee,
            )
            await self._repository.save_trade(trade)
            event_type = PositionOpened if prior is None else PositionUpdated
            await self._event_bus.publish(
                event_type(
                    position=current,
                    account_id=order.account_id,
                    bot_id=order.bot_id,
                    mode=order.mode,
                    occurred_at=event.occurred_at,
                    correlation_id=event.correlation_id,
                )
            )

    def close(self) -> None:
        self._subscription.unsubscribe()
