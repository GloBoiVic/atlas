# Feature: 07 — Execution Layer

## Description

Place orders through broker adapters. Paper trading and live trading use same interface.

## Dependencies

- 02 — Core Infrastructure
- 06 — Risk Engine
- 03 — Data Layer

## Deliverables

- [ ] Execution engine: Subscribes to RiskApproved, manages orders
- [ ] Broker interface: submit_order, cancel_order, get_positions, get_account
- [ ] Order model: Order(instrument, side, quantity, order_type, stop_loss, take_profit)
- [ ] Position model: Position(instrument, side, entry_price, quantity, unrealized_pnl)
- [ ] Paper Broker: Simulates deterministic fills locally from the current market-data context
- [ ] Order management: Track open orders, fills, cancellations
- [ ] Position tracking: Update positions on fills, calculate unrealized P&L

## Technical Details

### Execution Engine

```python
class ExecutionEngine:
    def __init__(self, event_bus: EventBus, broker: Broker, bot_id: UUID):
        self.event_bus = event_bus
        self.broker = broker
        self.bot_id = bot_id
        self.event_bus.subscribe(RiskApproved, self._on_risk_approved)

    async def _on_risk_approved(self, event: RiskApproved):
        order = Order(
            instrument=event.signal.instrument,
            side=event.signal.direction,
            quantity=event.position_size,
            order_type=OrderType.MARKET,
            stop_loss=event.stop_loss,
            take_profit=event.take_profit,
        )

        result = await self.broker.submit_order(order, client_order_id=event.correlation_id)

        if result.success:
            await self.event_bus.publish(OrderSubmitted(
                order=order, broker_order_id=result.order_id
            ))
        else:
            await self.event_bus.publish(OrderFailed(
                order=order, error=result.error
            ))
```

### Broker Interface

```python
class Broker(ABC):
    @abstractmethod
    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        """Place an order with the broker."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        pass

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Get account information (balance, equity, etc.)."""
        pass

    @abstractmethod
    async def reconcile(self) -> BrokerSnapshot:
        """Return broker orders and positions for startup recovery."""
        pass
```

### Order and Position Models

Order, fill, position, trade, and status fields are defined canonically in `context/database.md`. This feature owns their state transitions and broker behavior, not a second schema definition.

### Paper Broker

```python
class PaperBroker(Broker):
    def __init__(self, initial_balance: Decimal = Decimal(10000)):
        self.balance = initial_balance
        self.positions = {}
        self.orders = []

    async def submit_order(self, order: Order) -> OrderResult:
        # The execution context supplies the deterministic current/next-open price.
        # Paper fills apply configured fees and slippage and are idempotent.
        ...
```

The MVP uses one net position per account and instrument. Orders and fills are persisted before a bot reports the transition as complete. A broker timeout produces an `unknown` order state and triggers reconciliation before any retry. Protective exits are represented as execution-managed orders and are evaluated from incoming completed candles/ticks according to the configured market model.

## Acceptance Criteria

- [ ] Paper broker fills orders and updates positions
- [ ] Execution engine emits OrderSubmitted, OrderFilled, PositionOpened, PositionClosed events
- [ ] Stop-loss and take-profit orders trigger correctly
- [ ] Same execution code works in backtester and live trading
- [ ] Position tracking updates unrealized P&L
- [ ] Order history is persisted
- [ ] Paper fills are deterministic and use Decimal values, fees, slippage, and instrument precision
- [ ] Duplicate client order IDs do not create duplicate orders
- [ ] Broker reconciliation handles unknown orders and startup recovery
- [ ] One net position per account and instrument is enforced

## Done when

All acceptance criteria are met.
