# Feature: 07 — Execution Layer

## Description

Place orders through broker adapters. Paper trading and live trading use same interface.

## Dependencies

- 02 — Core Infrastructure
- 06 — Risk Engine
- 03 — Data Layer

## Deliverables

- [ ] Execution engine: Subscribes to RiskApproved, manages orders, fills, positions, and trades
- [ ] Broker interface: submit_order, cancel_order, get_positions, get_account, reconcile
- [ ] Order model with client-order-id idempotency
- [ ] Position model: one net position per account and instrument
- [ ] Trade model: Explicit Trade entity connecting fills to journaling/analytics
- [ ] Fill model: Append-only fill records
- [ ] Paper Broker: Simulates deterministic fills locally — price source is the current executable market price in live mode, or the next candle open in backtest replay mode. The fill algorithm is identical in both modes.
- [ ] Order management: Track open orders, fills, cancellations, state transitions
- [ ] Position tracking: Update positions on fills, calculate unrealized P&L
- [ ] Trade lifecycle: Create Trade on position open, finalize on position close
- [ ] Broker reconciliation on startup and unknown states

### Event Payload Status

This feature owns the payload definitions for all execution-related events. The event
classes in `backend/core/events.py` currently have the following status:

| Event class | Payload status |
|---|---|
| `RiskApproved` | `pass` — owned by Feature 06; must carry `signal`, `position_size`, `stop_loss`, `take_profit` |
| `RiskRejected` | `pass` — owned by Feature 06; must carry `signal`, `reason` |
| `SignalGenerated` | **Implemented** — carries `signal: Signal` (owned by Feature 04) |
| `OrderSubmitted` | `pass` — must carry `order: Order`, `broker_order_id: str` |
| `OrderFilled` | `pass` — must carry `order: Order`, `fill: Fill` |
| `PositionOpened` | `pass` — must carry `position: Position` |
| `PositionUpdated` | `pass` — must carry `position: Position` |
| `PositionClosed` | `pass` — must carry `position: Position` |
| `TradeClosed` | `pass` — must carry `trade: Trade` |
| `OrderFailed` | `pass` — must carry `order_id: UUID`, `error: str` |

All payload fields must follow the `kw_only=True` dataclass convention. This feature
is the authoritative source for execution event payload contracts; duplicate "Event
Payload Gap" sections in other feature files are stale and have been removed.

## Technical Details

### Execution Engine

```python
class ExecutionEngine:
    def __init__(self, event_bus: EventBus, broker: Broker, bot_id: UUID,
                 trade_service: TradeService):
        self.event_bus = event_bus
        self.broker = broker
        self.bot_id = bot_id
        self.trade_service = trade_service
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

        result = await self.broker.submit_order(order, client_order_id=str(uuid4()))

        if result.success:
            await self.event_bus.publish(OrderSubmitted(
                order=order, broker_order_id=result.order_id,
            ))
        else:
            await self.event_bus.publish(OrderFailed(
                order=order, error=result.error,
            ))
```

### Broker Interface

```python
class Broker(ABC):
    @abstractmethod
    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        """Place an order with the broker. client_order_id ensures idempotency."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        pass

    @abstractmethod
    async def get_positions(self) -> list[Position]:
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

### Order, Fill, Position, and Trade Models

The canonical schema is defined in `context/database.md`. Key principles:

- **Orders** have unique `client_order_id` for idempotent submission.
- **Fills** are append-only. Positions and trades are derived from fills.
- **One net position** per account and instrument (enforced by partial unique index on
  `positions`).
- **Trade lifecycle:** A `Trade` record is created when a position opens (aggregating entry
  fills) and finalized when the position closes (aggregating all fills). Trades carry
  gross/net P&L and fees, and are the canonical source of truth for journaling and analytics.

```python
@dataclass
class Trade:
    id: UUID
    account_id: UUID
    bot_id: UUID | None
    strategy_version_id: UUID | None
    position_id: UUID
    instrument_id: UUID
    direction: str          # "long", "short"
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    gross_pnl: Decimal | None
    net_pnl: Decimal | None
    total_fees: Decimal
    status: str             # "entered", "exited"
    signal_metadata: dict
    market_context: dict
    entry_time: datetime
    exit_time: datetime | None
```

### Paper Broker

```python
class PaperBroker(Broker):
    def __init__(self, initial_balance: Decimal = Decimal(10000)):
        self.balance = initial_balance
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []

    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        # The execution context supplies the deterministic fill price:
        # current executable market price in live mode,
        # next candle open in backtest replay mode.
        # Paper fills apply configured fees and slippage and are idempotent.
        # Rejected client_order_ids return the previous result (idempotency).
        ...
```

### Execution Policy (Approved Defaults)

The following defaults apply to both backtesting and paper trading, and are documented
in the accepted blueprint (Section 9):

- **Order types:** Market entries and execution-managed protective exits only. Limit,
  stop-limit, OCO, iceberg, and order-book-aware fill models are deferred.
- **Fee default:** Configurable taker fee, default **0.10% per fill**. Recorded in
  `execution_config` on every run.
- **Slippage default:** Configurable fixed adverse percentage per fill, default **0.05%**.
  No OHLC-based spread/volume inference.
- **Precision:** Provider/instrument tick and step constraints are applied before
  submission. All money, prices, quantities, fees, and P&L remain `Decimal`.
- **Partial fills:** The state contract supports partial fills, but the default Paper
  Broker fills complete. When partial fills are enabled, fill-quantity-weighted average
  entry/exit prices apply, with one net position per account/instrument.
- **Protective-trigger ambiguity:** When both stop-loss and take-profit levels could be
  touched in one candle, apply stop-loss first (conservative deterministic rule).
  Record the rule in `execution_config`.
- **Unknown order state:** A broker timeout or non-deterministic response produces
  `unknown`. The system fails closed — unknown orders are never retried until
  reconciliation resolves the state. Reconciliation decides whether retry is safe.

### Trade Lifecycle

The trade lifecycle connects execution to journaling:

1. **Position opens** → Create `Trade(account_id, bot_id, ..., status="entered")`.
2. **Position updates** → Update trade `exit_price`, `gross_pnl`, `net_pnl` with partial
   close values (if partial fills close part of a position).
3. **Position closes** → Set `exit_price`, `exit_time`, finalize `gross_pnl`/`net_pnl`,
   set `status="exited"`, emit `TradeClosed`.
4. **Journal subscribes to `TradeClosed`** → Create `JournalEntry` from the completed trade.

### Execution Order of Operations

The MVP uses one net position per account and instrument. Orders and fills are persisted
before a bot reports the transition as complete. A broker timeout produces an `unknown`
order state and triggers reconciliation before any retry. Protective exits are represented
as execution-managed orders and are evaluated from incoming completed candles/ticks according
to the configured market model.

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
- [ ] Trade entity is created on position open and finalized on position close
- [ ] Closed trades emit TradeClosed event for journaling

## Done when

All acceptance criteria are met.
