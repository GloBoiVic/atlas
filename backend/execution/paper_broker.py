"""Deterministic, provider-neutral isolated Futures paper broker."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode
from backend.execution.broker import AccountInfo, Broker, BrokerSnapshot, OrderResult
from backend.execution.models import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    PositionSide,
    PositionStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.persistence.repositories.protocols import ExecutionRepository


class PaperFillMode(StrEnum):
    """Price source used by the shared paper execution algorithm."""

    LIVE = "live"
    BACKTEST = "backtest"


@dataclass(frozen=True, slots=True)
class ExecutableMarket:
    """Fresh executable bid/ask and risk mark context."""

    instrument_id: UUID
    bid: Decimal
    ask: Decimal
    mark_price: Decimal
    as_of: datetime
    stale_after: timedelta = timedelta(seconds=5)
    next_candle_open: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("bid", "ask", "mark_price"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be a positive finite Decimal")
        if self.bid > self.ask:
            raise ValueError("bid cannot exceed ask")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() != UTC.utcoffset(self.as_of):
            raise ValueError("as_of must be UTC")
        if self.next_candle_open is not None and self.next_candle_open <= 0:
            raise ValueError("next_candle_open must be positive")


@dataclass(frozen=True, slots=True)
class FundingAdjustment:
    """A cash-only funding adjustment, separate from trading fees and P&L."""

    account_id: UUID
    amount: Decimal
    applied_at: datetime
    id: UUID


class PaperBroker(Broker):
    """A deterministic one-way isolated-margin Futures simulator.

    The broker has no provider connectivity.  Callers supply executable prices and
    mark prices explicitly, making backtest and live-paper behavior reproducible.
    """

    def __init__(
        self,
        *,
        account_id: UUID | None = None,
        initial_balance: Decimal = Decimal("10000"),
        fee_rate: Decimal = Decimal("0.0005"),
        slippage_rate: Decimal = Decimal("0.0005"),
        maintenance_margin_rate: Decimal = Decimal("0.005"),
        leverage: Decimal = Decimal("1"),
        fill_mode: PaperFillMode = PaperFillMode.LIVE,
        clock: Callable[[], datetime] | None = None,
        repository: ExecutionRepository | None = None,
    ) -> None:
        self.account_id = account_id or uuid4()
        self.balance = self._non_negative(initial_balance, "initial_balance")
        self.fee_rate = self._rate(fee_rate, "fee_rate")
        self.slippage_rate = self._rate(slippage_rate, "slippage_rate")
        self.maintenance_margin_rate = self._rate(
            maintenance_margin_rate, "maintenance_margin_rate"
        )
        if not Decimal("1") <= leverage <= Decimal("2"):
            raise ValueError("leverage must be between 1x and 2x")
        self.leverage = leverage
        self.fill_mode = PaperFillMode(fill_mode)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._repository = repository
        self._contexts: dict[UUID, ExecutableMarket] = {}
        self._positions: dict[tuple[UUID, AccountMode], Position] = {}
        self._orders: dict[str, Order] = {}
        self._fills: dict[str, Fill] = {}
        self._results: dict[str, OrderResult] = {}
        self._funding: list[FundingAdjustment] = []

    @staticmethod
    def _non_negative(value: Decimal, name: str) -> Decimal:
        if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
            raise ValueError(f"{name} must be a finite non-negative Decimal")
        return value

    @classmethod
    def _rate(cls, value: Decimal, name: str) -> Decimal:
        result = cls._non_negative(value, name)
        if result >= Decimal("1"):
            raise ValueError(f"{name} must be below 1")
        return result

    def set_market(self, market: ExecutableMarket) -> None:
        """Set the explicit market context used by subsequent paper fills."""
        self._contexts[market.instrument_id] = market
        for (instrument_id, mode), position in list(self._positions.items()):
            if instrument_id == market.instrument_id:
                self._positions[(instrument_id, mode)] = self._marked(position, market)

    def _fresh_market(self, instrument_id: UUID) -> ExecutableMarket | None:
        market = self._contexts.get(instrument_id)
        if market is None:
            return None
        if self._clock() - market.as_of > market.stale_after:
            return None
        return market

    def _price(self, order: Order, market: ExecutableMarket) -> Decimal:
        if self.fill_mode is PaperFillMode.BACKTEST:
            if market.next_candle_open is None:
                raise ValueError("missing next-candle-open price")
            raw = market.next_candle_open
        elif order.side is OrderSide.BUY:
            raw = market.ask
        else:
            raw = market.bid
        return raw * (
            Decimal("1") + self.slippage_rate
            if order.side is OrderSide.BUY
            else Decimal("1") - self.slippage_rate
        )

    def _available(self, instrument_id: UUID | None = None) -> Decimal:
        used = sum(
            position.isolated_margin
            for (position_instrument, _), position in self._positions.items()
            if instrument_id is None or position_instrument == instrument_id
        )
        unrealized = sum(position.unrealized_pnl for position in self._positions.values())
        return max(Decimal("0"), self.balance + unrealized - used)

    @staticmethod
    def _position_side(side: OrderSide) -> PositionSide:
        return PositionSide.LONG if side is OrderSide.BUY else PositionSide.SHORT

    def _marked(self, position: Position, market: ExecutableMarket) -> Position:
        pnl = (
            market.mark_price - position.entry_price
            if position.side is PositionSide.LONG
            else position.entry_price - market.mark_price
        ) * position.quantity
        maintenance = market.mark_price * position.quantity * self.maintenance_margin_rate
        liquidation_price = (
            position.entry_price
            * (Decimal("1") - Decimal("1") / position.leverage + self.maintenance_margin_rate)
            if position.side is PositionSide.LONG
            else position.entry_price
            * (Decimal("1") + Decimal("1") / position.leverage - self.maintenance_margin_rate)
        )
        return replace(
            position,
            current_price=market.mark_price,
            unrealized_pnl=pnl,
            maintenance_margin=maintenance,
            liquidation_price=liquidation_price,
        )

    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        """Submit a market order, returning the same result for repeated client IDs."""
        previous = self._results.get(client_order_id)
        if previous is not None:
            return previous
        if order.account_id != self.account_id:
            return self._reject(client_order_id, "account_scope_mismatch")
        if order.leverage != self.leverage:
            return self._reject(client_order_id, "unsupported_leverage")
        if self._repository is not None:
            await self._repository.create_order(order)
        self._orders[client_order_id] = order
        market = self._fresh_market(order.instrument_id)
        if market is None:
            return self._reject(client_order_id, "missing_or_stale_executable_context")
        try:
            price = self._price(order, market)
        except ValueError as exc:
            return self._reject(client_order_id, str(exc))
        mode = order.mode or AccountMode.PAPER
        key = (order.instrument_id, mode)
        position = self._positions.get(key)
        side = self._position_side(order.side)
        if (
            position is not None
            and position.side is not side
            and (order.quantity > position.quantity or not order.reduce_only)
        ):
            return self._reject(client_order_id, "explicit_close_required_for_reversal")
        notional = order.quantity * price
        fee = notional * self.fee_rate
        if position is None or position.side is side:
            required_margin = notional / self.leverage
            if required_margin + fee > self._available():
                return self._reject(client_order_id, "insufficient_isolated_margin")
        fill = Fill(
            order_id=order.id,
            account_id=self.account_id,
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=price,
            fee=fee,
            filled_at=self._clock(),
            broker_fill_id=f"paper-{order.id}",
        )
        if self._repository is not None:
            fill = await self._repository.append_fill(fill)
        if fill.broker_fill_id is not None:
            self._fills[fill.broker_fill_id] = fill
        self.balance = max(Decimal("0"), self.balance - fee)
        self._apply_fill(position, fill, order, market, mode)
        if self._repository is not None:
            persisted_position = self._positions.get(key)
            if persisted_position is None and position is not None:
                persisted_position = replace(
                    position,
                    status=PositionStatus.CLOSED,
                    current_price=fill.price,
                    unrealized_pnl=Decimal("0"),
                    closed_at=fill.filled_at,
                )
            if persisted_position is not None:
                await self._repository.save_position(persisted_position)
        result = OrderResult(
            success=True,
            status=OrderStatus.FILLED,
            order_id=f"paper-{order.id}",
            fills=(fill,),
        )
        self._orders[client_order_id] = replace(
            order,
            broker_order_id=result.order_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_fill_price=fill.price,
            updated_at=fill.filled_at,
        )
        self._results[client_order_id] = result
        return result

    def _apply_fill(
        self,
        position: Position | None,
        fill: Fill,
        order: Order,
        market: ExecutableMarket,
        mode: AccountMode,
    ) -> None:
        key = (order.instrument_id, mode)
        side = self._position_side(order.side)
        if position is None:
            created = Position(
                account_id=self.account_id,
                instrument_id=order.instrument_id,
                side=side,
                quantity=fill.quantity,
                entry_price=fill.price,
                mode=mode,
                bot_id=order.bot_id,
                strategy_version_id=order.strategy_version_id,
                stop_loss=order.stop_loss or None,
                take_profit=order.take_profit or None,
                leverage=self.leverage,
                isolated_margin=fill.quantity * fill.price / self.leverage,
                opened_at=fill.filled_at,
            )
            self._positions[key] = self._marked(created, market)
            return
        if position.side is side:
            quantity = position.quantity + fill.quantity
            entry = (
                position.entry_price * position.quantity + fill.price * fill.quantity
            ) / quantity
            updated = replace(
                position,
                quantity=quantity,
                entry_price=entry,
                isolated_margin=(
                    position.isolated_margin + fill.quantity * fill.price / self.leverage
                ),
            )
            self._positions[key] = self._marked(updated, market)
            return
        pnl = (
            fill.price - position.entry_price
            if position.side is PositionSide.LONG
            else position.entry_price - fill.price
        ) * fill.quantity
        self.balance = max(Decimal("0"), self.balance + pnl)
        remaining = position.quantity - fill.quantity
        if remaining == 0:
            self._positions.pop(key)
        else:
            updated = replace(
                position,
                quantity=remaining,
                realized_pnl=position.realized_pnl + pnl,
                isolated_margin=position.isolated_margin * remaining / position.quantity,
                status=PositionStatus.REDUCING,
            )
            self._positions[key] = self._marked(updated, market)

    def _reject(self, client_order_id: str, reason: str) -> OrderResult:
        result = OrderResult(success=False, status=OrderStatus.REJECTED, error=reason)
        order = self._orders.get(client_order_id)
        if order is not None:
            self._orders[client_order_id] = replace(
                order,
                status=OrderStatus.REJECTED,
                updated_at=self._clock(),
            )
        self._results[client_order_id] = result
        return result

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel only an order that has not been filled."""
        return order_id not in {result.order_id for result in self._results.values()}

    async def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    async def get_account(self) -> AccountInfo:
        unrealized = sum(position.unrealized_pnl for position in self._positions.values())
        return AccountInfo(
            account_id=self.account_id,
            balance=self.balance,
            equity=max(Decimal("0"), self.balance + unrealized),
            available_balance=self._available(),
            as_of=self._clock(),
        )

    async def reconcile(self) -> BrokerSnapshot:
        """Return the complete in-memory broker ledger and authoritative positions."""
        return BrokerSnapshot(
            account=await self.get_account(),
            orders=tuple(self._orders.values()),
            positions=tuple(await self.get_positions()),
            fills=tuple(self._fills.values()),
        )

    async def apply_funding(
        self, amount: Decimal, *, applied_at: datetime | None = None
    ) -> FundingAdjustment:
        """Apply funding separately from fees and realized trading P&L."""
        if not isinstance(amount, Decimal) or not amount.is_finite():
            raise ValueError("funding amount must be a finite Decimal")
        self.balance = max(Decimal("0"), self.balance + amount)
        adjustment = FundingAdjustment(
            self.account_id, amount, applied_at or self._clock(), uuid4()
        )
        self._funding.append(adjustment)
        return adjustment

    async def check_liquidation(
        self, instrument_id: UUID, mode: AccountMode = AccountMode.PAPER
    ) -> OrderResult | None:
        """Liquidate deterministically when equity reaches maintenance margin."""
        position = self._positions.get((instrument_id, mode))
        if position is None:
            return None
        market = self._fresh_market(instrument_id)
        if market is None:
            return None
        position = self._marked(position, market)
        self._positions[(instrument_id, mode)] = position
        if position.isolated_margin + position.unrealized_pnl > position.maintenance_margin:
            return None
        order = Order(
            account_id=self.account_id,
            instrument_id=instrument_id,
            side=OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY,
            quantity=position.quantity,
            client_order_id=f"liquidation-{position.id}",
            mode=mode,
            reduce_only=True,
            leverage=self.leverage,
        )
        return await self.submit_order(order, order.client_order_id)

    async def check_protective_triggers(
        self, instrument_id: UUID, mode: AccountMode = AccountMode.PAPER
    ) -> OrderResult | None:
        """Use mark price for triggers, with stop loss winning ambiguous touches."""
        position = self._positions.get((instrument_id, mode))
        market = self._fresh_market(instrument_id)
        if position is None or market is None:
            return None
        triggered = (
            position.side is PositionSide.LONG
            and position.stop_loss is not None
            and market.mark_price <= position.stop_loss
        ) or (
            position.side is PositionSide.SHORT
            and position.stop_loss is not None
            and market.mark_price >= position.stop_loss
        )
        if not triggered:
            triggered = (
                position.side is PositionSide.LONG
                and position.take_profit is not None
                and market.mark_price >= position.take_profit
            ) or (
                position.side is PositionSide.SHORT
                and position.take_profit is not None
                and market.mark_price <= position.take_profit
            )
        if not triggered:
            return None
        order = Order(
            account_id=self.account_id,
            instrument_id=instrument_id,
            side=OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY,
            quantity=position.quantity,
            client_order_id=f"protective-{position.id}-{market.as_of.isoformat()}",
            mode=mode,
            reduce_only=True,
            leverage=self.leverage,
        )
        return await self.submit_order(order, order.client_order_id)
