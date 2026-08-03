# Feature: 09 — Live Trading (Paper + Testnet)

## Description

Execute trades through broker adapters. Paper trading comes first and reuses the same
Strategy, Risk, and Execution contracts as backtesting. Binance Spot testnet follows
after paper trading is stable. Production live trading is deferred.

## Dependencies

- 07 — Execution Layer
- 08 — Live Data Streaming

## Deliverables

### Paper Trading (MVP)
- [ ] Bot lifecycle: Start, stop, pause, resume persisted bots
- [ ] BotSupervisor with isolated per-bot pipelines
- [ ] Paper account with balance, positions, P&L tracking
- [ ] Startup restoration: Reconcile broker state before enabling execution
- [ ] Real-time bot status events via EventBus

### Binance Spot Testnet (MVP+)
- [ ] Binance Spot testnet broker adapter: Place, cancel, reconcile orders via ccxt
- [ ] Broker authentication: Read credentials from server environment secrets
- [ ] Testnet order execution: Submit, fill, cancel, and reconcile orders
- [ ] Position tracking: Sync net positions with the broker before resuming bots
- [ ] Explicit mode boundary: Paper and testnet use separate account/configuration records

### Production (Deferred)
Production mode is reserved. See "Production Mode" below.

## Technical Details

### Event Payload Gap

All execution-related event classes (`RiskApproved`, `OrderSubmitted`, `OrderFilled`,
`PositionOpened`, `PositionUpdated`, `PositionClosed`, `TradeClosed`, `OrderFailed`) are
currently defined with `pass`. The payload fields shown in Feature 07 must be added before
live trading can emit valid events.

### Paper Trading

Paper trading runs the same bot pipeline as backtesting but receives live data from the
streaming feed (Feature 08). The paper broker simulates fills deterministically using the
current market price.

```python
class PaperBroker(Broker):
    def __init__(self, initial_balance: Decimal = Decimal(10000)):
        self.balance = initial_balance
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.fill_counter = 0

    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        # Check idempotency: if client_order_id was already submitted,
        # return the previous result without creating a new order.
        # Determine fill price from current market context.
        # Apply configured fees and slippage.
        ...
```

### Binance Broker Adapter

```python
class BinanceBroker(Broker):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.exchange = ccxt.async_support.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "options": {"defaultType": "spot"},
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        symbol = self._to_binance_symbol(order.instrument)
        side = "buy" if order.side == SignalDirection.BUY else "sell"
        try:
            result = await self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=self._format_quantity(order.quantity),
                params={"newClientOrderId": client_order_id},
            )
            return OrderResult(success=True, order_id=result["id"])
        except ccxt.NetworkError as e:
            return OrderResult(success=False, error=f"network_error: {e}")
        except ccxt.ExchangeError as e:
            return OrderResult(success=False, error=f"exchange_error: {e}")
        except Exception as e:
            return OrderResult(success=False, error=str(e))
```

### Trade Lifecycle (Paper + Testnet)

The same `Trade` entity (defined in Feature 07) applies to both paper and testnet trading.
Trades are created when a position opens and finalized when the position closes. They carry:

- Entry/exit prices and times
- Gross/net P&L and total fees
- Strategy version and signal metadata
- Market context at entry

Completed trades emit `TradeClosed`, which triggers journaling (Feature 10).

### Production Mode

**Production mode (`AccountMode.PRODUCTION`) is reserved, not implemented.** The enum value
exists but must be rejected by configuration validation until both of these exist:

1. A **production broker adapter** that connects to real exchange endpoints (not testnet).
2. A **safety gate** — either a deployment-specific manifest, a physical confirmation step,
   or a documented operational procedure that prevents accidental production execution.

Until those mechanisms exist, any bot or configuration specifying `mode: production` should
fail at startup with a clear error.

### Configuration

```yaml
broker:
  name: "binance"
  mode: "paper"          # or "testnet"

  binance:
    api_key: "${BINANCE_API_KEY}"
    api_secret: "${BINANCE_API_SECRET}"
```

Paper mode requires no API credentials. Testnet mode reads credentials from environment
variables. Credentials never reach the browser or PostgreSQL.

## Acceptance Criteria

- [ ] Paper trading pipeline runs against live streaming data
- [ ] Paper broker fills are deterministic with Decimal values, fees, and slippage
- [ ] Bot lifecycle (start, stop, pause, resume) works through BotSupervisor
- [ ] Startup restoration reconciles before enabling execution
- [ ] Binance Spot testnet orders can be submitted, filled, cancelled, and reconciled
- [ ] Broker authentication uses server environment secrets
- [ ] Testnet mode cannot accidentally use production endpoints
- [ ] Unknown order responses trigger reconciliation before retry
- [ ] Paper and testnet accounts cannot share orders or positions
- [ ] Trade entity is created and finalized through the trade lifecycle
- [ ] Production mode is rejected until a safety gate exists

## Done when

All acceptance criteria are met.
