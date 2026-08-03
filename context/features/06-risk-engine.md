# Feature: 06 — Risk Engine

## Description

Centralized risk control. Every signal passes through risk rules before execution.

## Dependencies

- 02 — Core Infrastructure
- 04 — Strategy Engine
- 03 — Data Layer

## Deliverables

- [ ] Risk engine: Subscribes to SignalGenerated, emits RiskApproved/RiskRejected
- [ ] Position sizing: Calculate position size based on risk parameters
- [ ] Maximum open positions: Limit concurrent net positions
- [ ] Per-trade risk limits: Risk per trade as % of account equity
- [ ] Stop-loss/take-profit enforcement: Calculate and enforce SL/TP levels
- [ ] Decimal quantity and instrument constraint validation
- [ ] Risk configuration: YAML-based in bot config, overridable via UI
- [ ] Risk engine integrated into backtester: Same risk rules in backtesting
- [ ] Per-bot risk state isolation

### Event Payload Gap

`SignalGenerated`, `RiskApproved`, and `RiskRejected` event classes in
`backend/core/events.py` are currently defined with `pass`. `SignalGenerated` must carry
a `signal` payload; `RiskApproved` must carry `signal`, `position_size`, `stop_loss`,
and `take_profit`; `RiskRejected` must carry `signal` and `reason`. These payload fields
must be added before Feature 04/06 integration.

## Technical Details

### Risk Engine

```python
class RiskEngine:
    def __init__(self, event_bus: EventBus, account: AccountContext,
                 config: RiskConfig):
        self.event_bus = event_bus
        self.account = account
        self.config = config
        self.event_bus.subscribe(SignalGenerated, self._on_signal)
        self.event_bus.subscribe(OrderFilled, self._on_fill)
        self._open_positions: set[str] = set()
        self._bot_pnl = Decimal("0")

    async def _on_signal(self, event: SignalGenerated):
        signal = event.signal

        # Check risk rules
        if not self._check_max_positions():
            await self.event_bus.publish(RiskRejected(
                signal=signal, reason="Max open positions reached",
                account_id=event.account_id, bot_id=event.bot_id,
                mode=event.mode, correlation_id=event.correlation_id,
            ))
            return

        # Calculate position size
        context = self._build_risk_context(signal)
        position_size = self._calculate_position_size(signal, context)

        # Calculate stop-loss and take-profit
        stop_loss = self._calculate_stop_loss(signal)
        take_profit = self._calculate_take_profit(signal)

        await self.event_bus.publish(RiskApproved(
            signal=signal,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            account_id=event.account_id, bot_id=event.bot_id,
            mode=event.mode, correlation_id=event.correlation_id,
        ))
```

### Risk Configuration (YAML)

Risk configuration lives in the bot's YAML config file, not a separate database table.

```yaml
risk:
  per_trade_risk: 0.01           # Risk per trade as % of equity
  max_open_positions: 5          # Max concurrent net positions
  stop_loss_multiplier: 2.0      # SL as multiple of ATR
  take_profit_multiplier: 3.0    # TP as multiple of ATR
```

### Risk Context

The risk engine receives an explicit `RiskContext` containing account equity, available balance, open net positions, current price, intended entry price, stop-loss distance, instrument constraints (resolved from the `Instrument.constraints` JSONB metadata for the specific provider), bot ID, and the clock timestamp. Risk calculations never query database tables directly — the caller provides context.

**Instrument constraints are provider-specific.** For Binance, constraints include
`tick_size` and `step_size` (from `LOT_SIZE`/`PRICE_FILTER`). For OANDA, constraints
include `margin_rate` and `pip_location`. The risk engine reads these from a common
`constraints: dict` interface rather than hardcoded field names.

### Position Sizing

```python
def _calculate_position_size(self, signal: Signal, context: RiskContext) -> Decimal:
    risk_amount = context.equity * Decimal(str(self.config.per_trade_risk))
    stop_distance = abs(context.entry_price - context.stop_loss)
    if stop_distance <= 0:
        raise InvalidRiskConfiguration("stop distance must be positive")
    position_size = risk_amount / stop_distance
    # Apply instrument constraint (round to step size)
    return self._round_to_step(position_size, context.tick_size, context.step_size)
```

### Initial Risk Controls (MVP Slice)

The initial risk implementation includes:

1. **Position sizing** — From account equity, risk-per-trade ratio, and stop-loss distance.
2. **Maximum open net positions** — Hard limit per bot.
3. **Stop-loss and take-profit** — Calculated from entry price, ATR or configurable multiplier.
4. **Decimal quantity validation** — Enforce instrument tick size and step size.

**Deferred follow-up controls** (not required for the first backtest-to-paper slice):

- Daily loss limits
- Maximum drawdown halts
- Trading session restrictions
- Per-strategy risk configuration inheritance
- Risk aggregation across bots

## Acceptance Criteria

- [ ] Risk engine rejects signals that violate risk rules
- [ ] Position sizing is calculated correctly using Decimal values
- [ ] Max open positions limit is enforced per bot
- [ ] Stop-loss and take-profit are calculated correctly
- [ ] Same risk rules apply in backtesting and live trading
- [ ] Risk calculations use explicit account/market context (no direct DB queries)
- [ ] Invalid stops, quantities, and instrument constraints reject the signal safely
- [ ] Risk configuration is loaded from YAML (no separate risk_configurations table)
- [ ] Per-bot risk state is isolated

## Done when

All acceptance criteria are met.
