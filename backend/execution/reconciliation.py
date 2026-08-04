"""Broker-authoritative recovery for durable execution state."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from backend.execution.models import OrderStatus, PositionStatus
from backend.persistence.repositories.protocols import (
    ReconciliationRecord,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.core.account_mode import AccountMode
    from backend.execution.broker import Broker, BrokerSnapshot
    from backend.execution.models import Fill, Order, Position
    from backend.persistence.repositories.protocols import (
        ExecutionRepository,
        ReconciliationRepository,
    )


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Outcome of one authoritative broker snapshot comparison."""

    reconciliation_id: UUID
    status: str
    differences: tuple[str, ...]

    @property
    def safe_to_execute(self) -> bool:
        """Whether new execution may safely be admitted."""
        return self.status == "matched"


class ReconciliationBlock(Protocol):
    def block(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> None: ...

    def clear_block(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> None: ...


def _json_value(value: object) -> object:
    if isinstance(value, (UUID, datetime)):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {
            item.name: _json_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


class Reconciler:
    """Compare durable state with a broker snapshot and fail closed on differences."""

    def __init__(
        self,
        broker: Broker,
        execution_repository: ExecutionRepository,
        reconciliation_repository: ReconciliationRepository | None = None,
        *,
        coordinator: ReconciliationBlock | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._broker = broker
        self._execution = execution_repository
        self._runs = reconciliation_repository or cast(
            "ReconciliationRepository", execution_repository
        )
        self._coordinator = coordinator
        self._clock = clock or (lambda: datetime.now(UTC))

    async def reconcile(
        self,
        *,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None = None,
        bot_id: UUID | None = None,
    ) -> ReconciliationResult:
        """Fetch and persist one startup, reconnect, or periodic reconciliation."""
        started_at = self._clock()
        snapshot = await self._broker.reconcile()
        differences: list[str] = []
        if snapshot.account.account_id != account_id:
            differences.append("account_scope_mismatch")

        local_orders = await self._execution.get_non_terminal_orders(
            account_id=account_id, mode=mode
        )
        local_positions = await self._execution.get_positions(account_id=account_id, mode=mode)
        local_fills = await self._execution.get_fills(account_id=account_id, mode=mode)
        broker_orders = self._scoped_orders(snapshot, account_id, mode, instrument_id)
        broker_positions = self._scoped_positions(snapshot, account_id, mode, instrument_id)
        broker_fills = self._scoped_fills(snapshot, account_id, mode, instrument_id)

        local_by_broker = {
            order.broker_order_id: order
            for order in local_orders
            if order.broker_order_id is not None
        }
        local_by_client = {order.client_order_id: order for order in local_orders}
        for broker_order in broker_orders:
            local = local_by_client.get(broker_order.client_order_id)
            if broker_order.broker_order_id is not None:
                local = local_by_broker.get(broker_order.broker_order_id) or local
                if local is None:
                    local = await self._execution.get_order_by_broker_id(
                        broker_order.broker_order_id
                    )
            if local is None:
                local = await self._execution.get_order_by_client_id(broker_order.client_order_id)
            if local is None:
                differences.append(f"missing_local_order:{broker_order.client_order_id}")
                continue
            merged = replace(
                broker_order,
                id=local.id,
                bot_id=local.bot_id,
                strategy_version_id=local.strategy_version_id,
                signal=local.signal,
                client_order_id=local.client_order_id,
            )
            await self._execution.update_order(merged)

        broker_ids = {
            order.broker_order_id for order in broker_orders if order.broker_order_id is not None
        }
        for local in local_orders:
            if local.broker_order_id is not None and local.broker_order_id in broker_ids:
                continue
            if local.status is OrderStatus.UNKNOWN:
                # An authoritative absence means the request did not execute; it is safe
                # to terminate the UNKNOWN record, but never to resubmit it automatically.
                await self._execution.update_order(replace(local, status=OrderStatus.CANCELED))
            else:
                differences.append(f"missing_broker_order:{local.client_order_id}")

        local_fill_ids = {fill.broker_fill_id for fill in local_fills}
        for fill in broker_fills:
            if fill.broker_fill_id in local_fill_ids:
                continue
            if await self._execution.get_order_by_broker_id(self._order_id(fill, broker_orders)):
                await self._execution.append_fill(fill)
            else:
                differences.append(f"missing_local_fill:{fill.broker_fill_id}")

        await self._reconcile_positions(
            local_positions, broker_positions, differences, account_id, mode
        )
        status = "matched" if not differences else "blocked"
        if self._coordinator is not None:
            instruments = {
                position.instrument_id for position in (*local_positions, *broker_positions)
            }
            for scope_instrument_id in instruments:
                if instrument_id is None or scope_instrument_id == instrument_id:
                    if status == "matched":
                        self._coordinator.clear_block(account_id, scope_instrument_id, mode)
                    else:
                        self._coordinator.block(account_id, scope_instrument_id, mode)
            if instrument_id is not None and not local_positions and not broker_positions:
                if status == "matched":
                    self._coordinator.clear_block(account_id, instrument_id, mode)
                else:
                    self._coordinator.block(account_id, instrument_id, mode)
        completed_at = self._clock()
        record = ReconciliationRecord(
            account_id=account_id,
            bot_id=bot_id,
            status=status,
            broker_snapshot=cast("dict[str, object]", _json_value(snapshot)),
            differences={"items": differences},
            started_at=started_at,
            completed_at=completed_at,
        )
        saved = await self._runs.record(record)
        return ReconciliationResult(saved.id, status, tuple(differences))

    async def startup(
        self,
        *,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None = None,
        bot_id: UUID | None = None,
    ) -> ReconciliationResult:
        return await self.reconcile(
            account_id=account_id, mode=mode, instrument_id=instrument_id, bot_id=bot_id
        )

    async def reconnect(
        self,
        *,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None = None,
        bot_id: UUID | None = None,
    ) -> ReconciliationResult:
        return await self.reconcile(
            account_id=account_id, mode=mode, instrument_id=instrument_id, bot_id=bot_id
        )

    async def periodic(
        self,
        *,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None = None,
        bot_id: UUID | None = None,
    ) -> ReconciliationResult:
        return await self.reconcile(
            account_id=account_id, mode=mode, instrument_id=instrument_id, bot_id=bot_id
        )

    @staticmethod
    def _scoped_orders(
        snapshot: BrokerSnapshot,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None,
    ) -> tuple[Order, ...]:
        return tuple(
            order
            for order in snapshot.orders
            if order.account_id == account_id
            and (order.mode or mode) == mode
            and (instrument_id is None or order.instrument_id == instrument_id)
        )

    @staticmethod
    def _scoped_positions(
        snapshot: BrokerSnapshot,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None,
    ) -> tuple[Position, ...]:
        return tuple(
            position
            for position in snapshot.positions
            if position.account_id == account_id
            and position.mode == mode
            and (instrument_id is None or position.instrument_id == instrument_id)
        )

    @staticmethod
    def _scoped_fills(
        snapshot: BrokerSnapshot,
        account_id: UUID,
        mode: AccountMode,
        instrument_id: UUID | None,
    ) -> tuple[Fill, ...]:
        order_modes = {
            order.id: order.mode or mode
            for order in snapshot.orders
            if order.account_id == account_id
        }
        return tuple(
            fill
            for fill in snapshot.fills
            if fill.account_id == account_id
            and order_modes.get(fill.order_id) == mode
            and (instrument_id is None or fill.instrument_id == instrument_id)
        )

    @staticmethod
    def _order_id(fill: Fill, orders: tuple[Order, ...]) -> str:
        order_id = fill.order_id
        for order in orders:
            if order.id == order_id and order.broker_order_id is not None:
                return order.broker_order_id
        return str(order_id)

    async def _reconcile_positions(
        self,
        local: list[Position],
        broker: tuple[Position, ...],
        differences: list[str],
        account_id: UUID,
        mode: AccountMode,
    ) -> None:
        local_by_key = {(p.account_id, p.instrument_id, p.mode): p for p in local}
        broker_by_key = {(p.account_id, p.instrument_id, p.mode): p for p in broker}
        for key, broker_position in broker_by_key.items():
            local_position = local_by_key.get(key)
            if local_position is None:
                differences.append(f"missing_local_position:{broker_position.instrument_id}")
                await self._execution.save_position(broker_position)
                continue
            if (
                local_position.side != broker_position.side
                or local_position.quantity != broker_position.quantity
                or local_position.entry_price != broker_position.entry_price
            ):
                differences.append(f"position_mismatch:{broker_position.instrument_id}")
            await self._execution.save_position(
                replace(
                    broker_position,
                    id=local_position.id,
                    bot_id=local_position.bot_id,
                    strategy_version_id=local_position.strategy_version_id,
                )
            )
        for key, local_position in local_by_key.items():
            if key not in broker_by_key:
                differences.append(f"missing_broker_position:{local_position.instrument_id}")
                await self._execution.save_position(
                    replace(local_position, status=PositionStatus.CLOSED, closed_at=self._clock())
                )
