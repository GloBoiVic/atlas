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
- [ ] Maximum drawdown: Stop trading if drawdown exceeds threshold
- [ ] Maximum open positions: Limit concurrent positions
- [ ] Per-trade risk limits: Risk per trade as % of account
- [ ] Stop-loss/take-profit enforcement: Calculate and enforce SL/TP levels
- [ ] Daily loss limits: Stop trading if daily loss exceeds threshold
- [ ] Trading session restrictions: Only trade during specific hours
- [ ] Risk configuration: YAML-based, overridable via UI
- [ ] Risk engine integrated into backtester: Same risk rules in backtesting

## Technical Details

### Risk Engine

```python
class RiskEngine:
    def __init__(self, event_bus: EventBus, account: AccountContext, config: RiskConfig):
        self.event_bus = event_bus
        self.account = account
        self.config = config
        self.event_bus.subscribe(SignalGenerated, self._on_signal)
        self.event_bus.subscribe(OrderFilled, self._on_fill)
        self.open_positions = 0
        self.daily_pnl = Decimal(0)

    async def _on_signal(self, event: SignalGenerated):
        signal = event.signal

        # Check risk rules
        if not self._check_max_positions():
            await self.event_bus.publish(RiskRejected(
                signal=signal, reason="Max open positions reached"
            ))
            return

        # Calculate position size
        context = await self._build_risk_context(signal)
        position_size = self._calculate_position_size(signal, context)

        # Calculate stop-loss and take-profit
        stop_loss = self._calculate_stop_loss(signal)
        take_profit = self._calculate_take_profit(signal)

        await self.event_bus.publish(RiskApproved(
            signal=signal,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ))
```

### Risk Configuration (YAML)

```yaml
risk:
  per_trade_risk: 0.01           # Risk per trade as % of equity
  max_open_positions: 5          # Max concurrent net positions
  stop_loss_multiplier: 2.0      # SL as multiple of ATR
  take_profit_multiplier: 3.0    # TP as multiple of ATR
```

### Position Sizing

```python
def _calculate_position_size(self, signal: Signal, context: RiskContext) -> Decimal:
    risk_amount = context.equity * self.config.per_trade_risk
    # Calculate position size based on stop-loss distance
    stop_distance = abs(context.entry_price - context.stop_loss)
    if stop_distance <= 0:
        raise InvalidRiskConfiguration("stop distance must be positive")
    position_size = risk_amount / stop_distance
    return position_size
```

The risk engine receives an explicit `RiskContext` containing account equity, available balance, open net positions, current price, intended entry price, stop-loss distance, instrument constraints, bot ID, and the clock timestamp. Risk calculations never query database tables directly.

## Acceptance Criteria

- [ ] Risk engine rejects signals that violate risk rules
- [ ] Position sizing is calculated correctly
- [ ] Max open positions limit is enforced
- [ ] Stop-loss and take-profit are calculated correctly
- [ ] Same risk rules apply in backtesting and live trading
- [ ] Risk calculations use Decimal values and explicit account/market context
- [ ] Invalid stops, quantities, and instrument constraints reject the signal safely

Drawdown halts, daily loss limits, and trading session restrictions are deferred follow-up controls, not requirements for the first backtest-to-paper slice.

## Done when

All acceptance criteria are met.
