"""SQLAlchemy implementation of the execution persistence boundary."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.account_mode import AccountMode
from backend.execution.models import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    PositionStatus,
    Trade,
    TradeStatus,
)
from backend.execution.paper_broker import FundingAdjustment
from backend.persistence.models import (
    ExecutionFill,
    ExecutionOrder,
    ExecutionPosition,
    ExecutionTrade,
)
from backend.persistence.models import FundingAdjustment as FundingAdjustmentRow


def _order(row: ExecutionOrder) -> Order:
    return Order(
        id=row.id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        bot_id=row.bot_id,
        strategy_version_id=row.strategy_version_id,
        mode=AccountMode(row.mode),
        side=OrderSide(row.side),
        quantity=row.quantity,
        client_order_id=row.client_order_id,
        order_type=OrderType(row.order_type),
        stop_loss=row.stop_loss,
        take_profit=row.take_profit,
        reduce_only=row.reduce_only,
        leverage=row.leverage,
        status=OrderStatus(row.status),
        broker_order_id=row.broker_order_id,
        filled_quantity=row.filled_quantity,
        average_fill_price=row.average_fill_price,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _fill(row: ExecutionFill) -> Fill:
    return Fill(
        id=row.id,
        order_id=row.order_id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        side=OrderSide(row.side),
        quantity=row.quantity,
        price=row.price,
        fee=row.fee,
        filled_at=row.filled_at,
        broker_fill_id=row.broker_fill_id,
    )


def _position(row: ExecutionPosition) -> Position:
    return Position(
        id=row.id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        bot_id=row.bot_id,
        strategy_version_id=row.strategy_version_id,
        mode=AccountMode(row.mode),
        side=PositionSide(row.side),
        quantity=row.quantity,
        entry_price=row.entry_price,
        current_price=row.current_price,
        stop_loss=row.stop_loss,
        take_profit=row.take_profit,
        unrealized_pnl=row.unrealized_pnl,
        realized_pnl=row.realized_pnl,
        leverage=row.leverage,
        isolated_margin=row.isolated_margin,
        maintenance_margin=row.maintenance_margin,
        liquidation_price=row.liquidation_price,
        status=PositionStatus(row.status),
        opened_at=row.opened_at,
        closed_at=row.closed_at,
    )


def _trade(row: ExecutionTrade) -> Trade:
    return Trade(
        id=row.id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        position_id=row.position_id,
        bot_id=row.bot_id,
        strategy_version_id=row.strategy_version_id,
        direction=PositionSide(row.direction),
        entry_price=row.entry_price,
        quantity=row.quantity,
        total_fees=row.total_fees,
        entry_time=row.entry_time,
        exit_price=row.exit_price,
        gross_pnl=row.gross_pnl,
        net_pnl=row.net_pnl,
        status=TradeStatus(row.status),
        signal_metadata=row.signal_metadata,
        market_context=row.market_context,
        exit_time=row.exit_time,
    )


def _funding(row: FundingAdjustmentRow) -> FundingAdjustment:
    return FundingAdjustment(
        account_id=row.account_id,
        amount=row.amount,
        applied_at=row.applied_at,
        id=row.id,
        instrument_id=row.instrument_id,
        mode=AccountMode(row.mode),
        funding_timestamp=row.funding_timestamp,
    )


class SqlAlchemyExecutionRepository:
    """Execution repository with explicit transaction ownership per operation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_order(self, order: Order) -> Order:
        async with self._session_factory.begin() as session:
            result = await session.execute(
                select(ExecutionOrder).where(
                    ExecutionOrder.client_order_id == order.client_order_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return _order(existing)
            row = ExecutionOrder(
                id=order.id,
                account_id=order.account_id,
                instrument_id=order.instrument_id,
                bot_id=order.bot_id,
                strategy_version_id=order.strategy_version_id,
                client_order_id=order.client_order_id,
                broker_order_id=order.broker_order_id,
                side=order.side.value,
                quantity=order.quantity,
                order_type=order.order_type.value,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                reduce_only=order.reduce_only,
                leverage=order.leverage,
                status=order.status.value,
                filled_quantity=order.filled_quantity,
                average_fill_price=order.average_fill_price,
                mode=(order.mode or AccountMode.PAPER).value,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
            session.add(row)
            await session.flush()
            return _order(row)

    async def get_order_by_client_id(self, client_order_id: str) -> Order | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionOrder).where(ExecutionOrder.client_order_id == client_order_id)
            )
            row = result.scalar_one_or_none()
            return _order(row) if row else None

    async def get_order_by_broker_id(self, broker_order_id: str) -> Order | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionOrder).where(ExecutionOrder.broker_order_id == broker_order_id)
            )
            row = result.scalar_one_or_none()
            return _order(row) if row else None

    async def get_non_terminal_orders(
        self, *, account_id: UUID, mode: AccountMode
    ) -> list[Order]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionOrder).where(
                    ExecutionOrder.account_id == account_id,
                    ExecutionOrder.mode == mode.value,
                    ExecutionOrder.status.notin_((
                        OrderStatus.FILLED.value,
                        OrderStatus.CANCELED.value,
                        OrderStatus.REJECTED.value,
                        OrderStatus.EXPIRED.value,
                    )),
                )
            )
            return [_order(row) for row in result.scalars().all()]

    async def get_orders(self, *, account_id: UUID, mode: AccountMode) -> list[Order]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionOrder).where(
                    ExecutionOrder.account_id == account_id,
                    ExecutionOrder.mode == mode.value,
                )
            )
            return [_order(row) for row in result.scalars().all()]

    async def update_order(self, order: Order) -> Order:
        async with self._session_factory.begin() as session:
            row = await session.get(ExecutionOrder, order.id)
            if row is None:
                result = await session.execute(
                    select(ExecutionOrder).where(
                        ExecutionOrder.client_order_id == order.client_order_id
                    )
                )
                row = result.scalar_one_or_none()
            if row is None:
                raise LookupError("order does not exist")
            row.broker_order_id = order.broker_order_id
            row.status = order.status.value
            row.filled_quantity = order.filled_quantity
            row.average_fill_price = order.average_fill_price
            row.updated_at = order.updated_at
            await session.flush()
            return _order(row)

    async def append_fill(self, fill: Fill) -> Fill:
        async with self._session_factory.begin() as session:
            if fill.broker_fill_id is not None:
                result = await session.execute(
                    select(ExecutionFill).where(ExecutionFill.broker_fill_id == fill.broker_fill_id)
                )
                existing = result.scalar_one_or_none()
                if existing is not None:
                    return _fill(existing)
            row = ExecutionFill(
                id=fill.id,
                order_id=fill.order_id,
                account_id=fill.account_id,
                instrument_id=fill.instrument_id,
                broker_fill_id=fill.broker_fill_id,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                fee=fill.fee,
                filled_at=fill.filled_at,
            )
            session.add(row)
            await session.flush()
            return _fill(row)

    async def get_fill_by_broker_id(self, broker_fill_id: str) -> Fill | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionFill).where(ExecutionFill.broker_fill_id == broker_fill_id)
            )
            row = result.scalar_one_or_none()
            return _fill(row) if row else None

    async def get_fills(self, *, account_id: UUID, mode: AccountMode) -> list[Fill]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionFill)
                .join(ExecutionOrder, ExecutionOrder.id == ExecutionFill.order_id)
                .where(
                    ExecutionFill.account_id == account_id,
                    ExecutionOrder.mode == mode.value,
                )
            )
            return [_fill(row) for row in result.scalars().all()]

    async def save_funding_adjustment(self, adjustment: FundingAdjustment) -> FundingAdjustment:
        if adjustment.instrument_id is None:
            raise ValueError("funding adjustment requires an instrument")
        timestamp = adjustment.funding_timestamp or adjustment.applied_at
        async with self._session_factory.begin() as session:
            result = await session.execute(
                select(FundingAdjustmentRow).where(
                    FundingAdjustmentRow.account_id == adjustment.account_id,
                    FundingAdjustmentRow.instrument_id == adjustment.instrument_id,
                    FundingAdjustmentRow.mode == adjustment.mode.value,
                    FundingAdjustmentRow.funding_timestamp == timestamp,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return _funding(existing)
            row = FundingAdjustmentRow(
                id=adjustment.id,
                account_id=adjustment.account_id,
                instrument_id=adjustment.instrument_id,
                mode=adjustment.mode.value,
                amount=adjustment.amount,
                funding_timestamp=timestamp,
                applied_at=adjustment.applied_at,
            )
            session.add(row)
            await session.flush()
            return _funding(row)

    async def get_funding_adjustments(
        self, *, account_id: UUID, instrument_id: UUID | None, mode: AccountMode
    ) -> list[FundingAdjustment]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FundingAdjustmentRow)
                .where(
                    FundingAdjustmentRow.account_id == account_id,
                    FundingAdjustmentRow.mode == mode.value,
                )
                .where(
                    FundingAdjustmentRow.instrument_id == instrument_id
                    if instrument_id is not None
                    else FundingAdjustmentRow.instrument_id.is_not(None)
                )
                .order_by(FundingAdjustmentRow.funding_timestamp)
            )
            return [_funding(row) for row in result.scalars().all()]

    async def get_positions(self, *, account_id: UUID, mode: AccountMode) -> list[Position]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionPosition).where(
                    ExecutionPosition.account_id == account_id,
                    ExecutionPosition.mode == mode.value,
                    ExecutionPosition.status.in_(('open', 'reducing')),
                )
            )
            return [_position(row) for row in result.scalars().all()]

    async def get_position(
        self, *, account_id: UUID, instrument_id: UUID, mode: AccountMode
    ) -> Position | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionPosition).where(
                    ExecutionPosition.account_id == account_id,
                    ExecutionPosition.instrument_id == instrument_id,
                    ExecutionPosition.mode == mode.value,
                    ExecutionPosition.status.in_(("open", "reducing")),
                )
            )
            row = result.scalar_one_or_none()
            return _position(row) if row else None

    async def save_position(self, position: Position) -> Position:
        async with self._session_factory.begin() as session:
            row = await session.get(ExecutionPosition, position.id)
            if row is None:
                row = ExecutionPosition(id=position.id)
                session.add(row)
            for key, value in {
                "account_id": position.account_id,
                "instrument_id": position.instrument_id,
                "bot_id": position.bot_id,
                "strategy_version_id": position.strategy_version_id,
                "mode": position.mode.value,
                "side": position.side.value,
                "quantity": position.quantity,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
                "leverage": position.leverage,
                "isolated_margin": position.isolated_margin,
                "maintenance_margin": position.maintenance_margin,
                "liquidation_price": position.liquidation_price,
                "status": position.status.value,
                "opened_at": position.opened_at,
                "closed_at": position.closed_at,
            }.items():
                setattr(row, key, value)
            await session.flush()
            return _position(row)

    async def save_trade(self, trade: Trade) -> Trade:
        async with self._session_factory.begin() as session:
            row = await session.get(ExecutionTrade, trade.id)
            if row is None:
                row = ExecutionTrade(id=trade.id)
                session.add(row)
            for key, value in {
                "account_id": trade.account_id,
                "instrument_id": trade.instrument_id,
                "position_id": trade.position_id,
                "bot_id": trade.bot_id,
                "strategy_version_id": trade.strategy_version_id,
                "direction": trade.direction.value,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "quantity": trade.quantity,
                "gross_pnl": trade.gross_pnl,
                "net_pnl": trade.net_pnl,
                "total_fees": trade.total_fees,
                "status": trade.status.value,
                "signal_metadata": trade.signal_metadata,
                "market_context": trade.market_context,
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
            }.items():
                setattr(row, key, value)
            await session.flush()
            return _trade(row)

    async def get_trade_by_position(self, position_id: UUID) -> Trade | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionTrade).where(
                    ExecutionTrade.position_id == position_id,
                    ExecutionTrade.status == TradeStatus.ENTERED.value,
                )
            )
            row = result.scalar_one_or_none()
            return _trade(row) if row else None
