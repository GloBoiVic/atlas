# Feature: 06 — Risk Engine

## Description

Centralized risk control. Every signal passes through risk rules before execution.

## Dependencies

- 02 — Core Infrastructure
- 04 — Strategy Engine
- 03 — Data Layer

## Deliverables

- [x] Risk engine: Subscribes to SignalGenerated, emits RiskApproved/RiskRejected
- [x] Position sizing: Calculate position size based on risk parameters
- [x] Maximum open positions: Limit concurrent net positions
- [x] Per-trade risk limits: Risk per trade as % of account equity
- [x] Stop-loss/take-profit enforcement: Calculate and enforce SL/TP levels
- [x] Decimal quantity and instrument constraint validation
- [x] Risk configuration: YAML-based in bot config, overridable via UI
- [x] Risk evaluator is reusable by backtesting and paper pipelines
- [x] Per-bot risk state isolation

### Event Payload Status

`RiskApproved` and `RiskRejected` event classes in `backend/core/events.py` are currently
defined with `pass`. These payloads are owned by this feature and must follow the
`kw_only=True` convention:

```python
@dataclass(frozen=True, slots=True)
class RiskApproved(DomainEvent):
    signal: Signal = field(kw_only=True)
    position_size: Decimal = field(kw_only=True)
    stop_loss: Decimal = field(kw_only=True)
    take_profit: Decimal = field(kw_only=True)

@dataclass(frozen=True, slots=True)
class RiskRejected(DomainEvent):
    signal: Signal = field(kw_only=True)
    reason: str = field(kw_only=True)
```

**Note:** `SignalGenerated` is already implemented by Feature 04 with a typed
`signal: Signal` payload. The risk engine depends on it and must not redefine it.

## Technical Details

### Risk Engine

`RiskEngine.evaluate(signal, context)` is a synchronous, side-effect-free evaluator. The
EventBus adapter filters the engine's bot, asks the pipeline-owned context provider for a fresh
snapshot, evaluates it, and publishes exactly one typed decision. The engine has no repository,
broker, fill, or P&L dependency and retains only transient pending-entry reservations.

### Risk Configuration (YAML)

Risk configuration lives in the bot's YAML config file, not a separate database table.

```yaml
risk:
  per_trade_risk: 0.01           # Risk per trade as % of equity, maximum 0.02
  max_open_positions: 5
  stop_source: percentage_of_entry
  stop_percentage: 0.02
  stop_distance: null
  stop_price: null
  take_profit_risk_reward: null
```

### Risk Context

The risk engine receives an explicit `RiskContext` containing account equity, available balance,
open net positions, intended entry price, the `Instrument` and its provider constraints, bot and
account identity, execution mode, and a UTC clock timestamp. Risk calculations never query
database tables directly — the caller provides context.

### Reuse in Backtesting

The same `RiskEngine` implementation runs in both backtesting and paper trading. The
backtester (Feature 05) provides the `RiskContext` from the current candle's price and
simulated account state. No separate risk implementation exists for backtesting. Because
the backtester's clock is a `SimulationClock`, risk decisions remain deterministic and
reproducible.

**Instrument constraints are provider-specific.** For Binance, constraints include
`tick_size` and `step_size` (from `LOT_SIZE`/`PRICE_FILTER`). For OANDA, constraints
include `margin_rate` and `pip_location`. The risk engine reads these from a common
`constraints: dict` interface rather than hardcoded field names.

### Position Sizing

```python
stop_distance = abs(context.entry_price - rounded_stop)
risk_amount = context.equity * Decimal(str(config.per_trade_risk))
raw_quantity = risk_amount / stop_distance
quantity = floor_to_step(raw_quantity, context.instrument.constraints["step_size"])
```

### Initial Risk Controls (MVP Slice)

The initial risk implementation includes:

1. **Position sizing** — From account equity, risk-per-trade ratio, and stop-loss distance.
2. **Maximum open net positions** — Hard limit per bot.
3. **Stop-loss and take-profit** — Calculated from the selected configuration stop source
   and optional risk/reward multiple; ATR is not consulted.
4. **Decimal quantity validation** — Enforce instrument tick size and step size.

**Deferred follow-up controls** (not required for the first backtest-to-paper slice):

- Daily loss limits
- Maximum drawdown halts
- Trading session restrictions
- Per-strategy risk configuration inheritance
- Risk aggregation across bots

## Acceptance Criteria

- [x] Risk engine rejects signals that violate risk rules
- [x] Position sizing is calculated correctly using Decimal values
- [x] Max open positions limit is enforced per bot
- [x] Stop-loss and take-profit are calculated correctly
- [x] Same evaluator rules are reusable in backtesting and paper trading
- [x] Risk calculations use explicit account/market context (no direct DB queries)
- [x] Invalid stops, quantities, and instrument constraints reject the signal safely
- [x] Risk configuration is loaded from YAML (no separate risk_configurations table)
- [x] Per-bot risk state is isolated

## Done when

All acceptance criteria are met.
