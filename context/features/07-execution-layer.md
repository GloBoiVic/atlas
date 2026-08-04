# Feature: 07 — Execution Layer

## Description

Place orders through broker adapters. Paper trading and live trading use same interface.

## Dependencies

- 02 — Core Infrastructure
- 06 — Risk Engine
- 03 — Data Layer

## Deliverables

- [x] Execution engine: Subscribes to RiskApproved, manages orders, fills, positions, and trades
- [x] Broker interface: submit_order, cancel_order, get_positions, get_account, reconcile
- [x] Order model with client-order-id idempotency
- [x] Position model: one net position per account, instrument, and execution mode
- [x] Trade model: Explicit Trade entity connecting fills to journaling/analytics
- [x] Fill model: Append-only fill records with broker-execution idempotency
- [x] Paper Broker: Futures-aware deterministic fills using executable bid/ask in live paper
      mode and next-candle open in backtest mode
- [x] Persistence boundary: PostgreSQL SQLAlchemy models, migration 007, repository protocols,
      SQLAlchemy implementation, and deterministic in-memory test implementation
- [x] Order management: Track open orders, fills, cancellations, state transitions
- [x] Position tracking: Update positions on fills, calculate mark-price unrealized P&L
- [x] Trade lifecycle: Create Trade on position open, finalize on position close
- [x] Broker reconciliation on startup, reconnect, periodic, and unknown states

### Event Payload Status

This feature owns the payload definitions for all execution-related events. The event
classes in `backend/core/events.py` currently have the following status:

| Event class | Payload status |
|---|---|
| `RiskApproved` | **Implemented** — owned by Feature 06; carries `signal`, `position_size`, `stop_loss`, `take_profit` |
| `RiskRejected` | **Implemented** — owned by Feature 06; carries `signal`, `reason` |
| `SignalGenerated` | **Implemented** — carries `signal: Signal` (owned by Feature 04) |
| `OrderSubmitted` | **Implemented** — carries `order: Order`, `broker_order_id: str` |
| `OrderFilled` | **Implemented** — carries `order: Order`, `fill: Fill` |
| `PositionOpened` | **Implemented** — carries `position: Position` |
| `PositionUpdated` | **Implemented** — carries `position: Position` |
| `PositionClosed` | **Implemented** — carries `position: Position` |
| `TradeClosed` | **Implemented** — carries `trade: Trade` |
| `OrderRejected` | **Implemented** — carries `order_id: UUID`, `reason: str` |
| `OrderFailed` | **Implemented** — carries `order_id: UUID`, `error: str` |

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
- **Fee default:** Configurable taker fee, default **0.05% per fill**. Recorded in
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

- [x] Paper broker fills orders and updates positions
- [x] Execution engine emits OrderSubmitted, OrderFilled, PositionOpened, PositionClosed events
- [x] Stop-loss and take-profit orders trigger correctly
- [x] Same execution code works in backtester and live trading
- [x] Position tracking updates mark-price unrealized P&L
- [x] Order history persistence boundary is implemented (engine integration deferred)
- [x] Paper fills are deterministic and use Decimal values, configurable 0.05% taker fees,
      executable bid/ask or next-candle prices, isolated margin, funding, and liquidation
- [x] Duplicate client order IDs and broker execution IDs do not create duplicate records
- [x] Broker reconciliation handles unknown orders and startup recovery
- [x] One active net position per account, instrument, and execution mode is enforced
- [x] Trade entity is created on position open and finalized on position close
- [x] Closed trades emit TradeClosed event for journaling
- [x] Reconciliation compares broker-authoritative orders, fills, and positions, records every
      run through repositories, deduplicates execution reports, and preserves local strategy
      provenance when broker records do not carry it
- [x] Unresolved discrepancies fail closed; a successful explicit reconciliation clears the
      account/instrument coordinator block, including after worker restart

## Done when

All acceptance criteria are met.
