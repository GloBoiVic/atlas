# Feature: 09 — Live Trading (Paper + Testnet)

## Description

Execute trades through broker adapters. Paper trading comes first and reuses the same
Strategy, Risk, and Execution contracts as backtesting. Binance USDⓈ-M Futures testnet
(Phase 11) follows after paper trading is stable. Production live trading is deferred.

## Dependencies

- 02 — Core Infrastructure (BotSupervisor contract, lifecycle state machine)
- 07 — Execution Layer (shared Paper Broker, execution state)
- 08 — Live Data Streaming (completed-candle feed)
- 12 — Bot Management (API/UI for lifecycle controls; Feature 09 constructs pipelines)

## Deliverables

### Paper Trading (MVP)
- [x] Bot lifecycle: Start, stop, pause, resume persisted bots
- [x] BotSupervisor with isolated per-bot pipelines
- [x] Paper account with balance, positions, P&L tracking
- [x] Startup restoration: Reconcile broker state before enabling execution
- [x] Real-time bot status events via EventBus

### Binance USDⓈ-M Futures Testnet (Phase 11 — after paper execution is stable)
- [ ] Binance USDⓈ-M Futures testnet broker adapter: Place, cancel, reconcile orders
- [ ] Broker authentication: Read credentials from server environment secrets
- [ ] Testnet order execution: Submit, fill, cancel, and reconcile orders
- [ ] Position tracking: Sync net positions with the broker before resuming bots
- [ ] Explicit mode boundary: Paper and testnet use separate account/configuration records

### Production (Deferred)
Production mode is reserved. See "Production Mode" below.

## Technical Details

### Ownership Boundaries

Feature 09 owns **mode-specific pipeline assembly and broker adapters only**. It does not
redefine:

- **BotSupervisor lifecycle** (Feature 02) — supervising start/stop/pause/resume.
- **Execution state and Paper Broker algorithm** (Feature 07) — order/fill/position/trade
  state machines, idempotency, fee/slippage defaults.
- **Live streaming feed** (Feature 08) — completed-candle emission, deduplication.
- **Bot API/UI** (Feature 12) — lifecycle endpoints, status presentation.

See Feature 07 for authoritative execution event payload status. The "Event Payload Gap"
sections that previously appeared in this file were duplicates and have been removed.

### Strategy-Version Startup Policy

A running bot keeps its pinned strategy version and does not hot-reload from a new commit.
On startup, the supervisor verifies that the installed strategy package matches the
persisted `strategy_version_id`. If the identity mismatches or the package is missing,
the bot fails closed with `last_error` set and does not start. Adopting a new strategy
commit requires an explicit stop/recreate cycle.

### Paper Trading (Phase 8)

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

### Authenticated Binance USDⓈ-M Futures Adapter (Phase 11)

The authenticated broker adapter for Binance USDⓈ-M Futures is deferred to Phase 11.
Its canonical identity is `binance_usdm`. When implemented, it will:

- Use the `binance_usdm` provider identity for instrument resolution and order routing.
- Connect to Binance USDⓈ-M Futures testnet (and later production) REST and WebSocket
  endpoints — never a Spot endpoint or `defaultType: spot`.
- Read credentials from server environment secrets only (never the browser or database).
- Implement the `Broker` protocol with market orders for entries and protective exits.
- Defer limit, stop-limit, OCO, and iceberg order types.
- Use the Broker interface defined in Feature 07; no provider-specific contract is required.

The Broker interface contract (Feature 07) remains the sole adapter contract. The Phase 11
adapter will implement `submit_order`, `cancel_order`, `get_account`, `get_positions`,
and `reconcile`. Unknown-order responses trigger Feature 07 reconciliation before retry.

```python
# Phase 11 stub — identity only, no implementation.
# broker_identity = "binance_usdm"
# mode = "testnet"
# Adapter connects to USDⓈ-M Futures testnet endpoints.
# No Spot endpoints, no defaultType: spot.
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
  name: "binance_usdm"
  mode: "paper"          # or "testnet" (Phase 11)

  binance_usdm:
    api_key: "${BINANCE_USDM_API_KEY}"
    api_secret: "${BINANCE_USDM_API_SECRET}"
```

Paper mode (`mode: paper`) requires no API credentials. Testnet mode (`mode: testnet`,
Phase 11) reads credentials from environment variables. Credentials never reach the
browser or PostgreSQL. The authenticated Futures adapter is deferred; in Phase 8 the
`binance_usdm` identity resolves only to the public-stream live provider (Feature 08).

## Acceptance Criteria

- [x] Paper trading pipeline runs against live streaming data
- [x] Paper broker fills are deterministic with Decimal values, fees, and slippage
- [x] Bot lifecycle (start, stop, pause, resume) works through BotSupervisor
- [x] Startup restoration reconciles before enabling execution
- [ ] Binance USDⓈ-M Futures testnet orders can be submitted, filled, cancelled, and reconciled
- [ ] Broker authentication uses server environment secrets
- [ ] Testnet mode cannot accidentally use production endpoints
- [ ] Unknown order responses trigger reconciliation before retry
- [ ] Paper and testnet accounts cannot share orders or positions
- [x] Trade entity is created and finalized through the trade lifecycle
- [x] Production mode is rejected until a safety gate exists

## Done when

All acceptance criteria are met.
