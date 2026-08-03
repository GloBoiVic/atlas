# Feature: 04 — Strategy Engine

## Description

Strategies generate signals from market data. Same code works in backtesting and live trading.

## Dependencies

- 02 — Core Infrastructure
- 03 — Data Layer

## Deliverables

- [ ] Strategy base class: `on_candle()`, optional `on_tick()`, `required_data()`
- [ ] Signal model: includes strategy version, commit SHA, and completed-candle timestamp
- [ ] Strategy engine: Subscribes to `CandleClosed`, calls strategy, emits `SignalGenerated`
- [ ] Example strategy: SMA crossover (trend following)
- [ ] Example strategy: Bollinger Bands (mean reversion)
- [ ] Strategy configuration: Versioned YAML-based parameters loaded from deployed strategy package
- [ ] Strategy registration: Load only from the deployed strategy registry, never from API-supplied paths
- [ ] Per-bot strategy state isolation and reset

### Event Payload Status

The data event payloads are implemented. `CandleClosed` in `backend/core/events.py` now
carries a typed, keyword-only payload (`candle: Candle = field(kw_only=True)`), and
`TickReceived` follows the same pattern (`tick: Tick = field(kw_only=True)`). Strategy
engine code can depend on `event.candle`.

The downstream `SignalGenerated` payload remains owned by this feature and must follow
the same `kw_only=True` convention when implemented:

```python
@dataclass(frozen=True, slots=True)
class SignalGenerated(DomainEvent):
    signal: Signal = field(kw_only=True)
    strategy_version_id: UUID = field(kw_only=True)
    candle_id: UUID = field(kw_only=True)
```

The `DomainEvent` base class correctly uses `UUID` typed fields for `event_id`,
`correlation_id`, `account_id`, and `bot_id`.

## Technical Details

### Strategy Base Class

```python
class Strategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def on_candle(self, candle: Candle) -> Signal | None:
        """Evaluate a completed candle and optionally generate a signal."""
        pass

    def on_tick(self, tick: Tick) -> None:
        """Observe a tick for state/monitoring; candle signals remain canonical.
        The default is a no-op — strategies that need tick state override this."""
        return None

    def required_data(self) -> list[DataType]:
        """Declare what data types this strategy requires."""
        return [DataType.CANDLE]
```

### Signal Model

```python
@dataclass(frozen=True, slots=True)
class Signal:
    instrument: str
    direction: SignalDirection  # BUY, SELL, CLOSE
    strength: float             # 0.0 to 1.0
    metadata: dict              # Strategy-specific data (indicator values, etc.)
    candle_timestamp: datetime  # The completed candle that triggered this signal
    strategy_name: str
    strategy_version: str
    strategy_commit_sha: str

class SignalDirection(Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
```

### Strategy Engine

```python
class StrategyEngine:
    def __init__(self, event_bus: EventBus, bot_id: UUID, strategy: Strategy,
                 strategy_name: str, strategy_version: str, commit_sha: str):
        self.event_bus = event_bus
        self.bot_id = bot_id
        self.strategy = strategy
        self.strategy_name = strategy_name
        self.strategy_version = strategy_version
        self.commit_sha = commit_sha
        self.event_bus.subscribe(CandleClosed, self._on_candle)

    async def _on_candle(self, event: CandleClosed):
        signal = self.strategy.on_candle(event.candle)
        if signal:
            signal.strategy_name = self.strategy_name
            signal.strategy_version = self.strategy_version
            signal.strategy_commit_sha = self.commit_sha
            signal.candle_timestamp = event.candle.open_time
            await self.event_bus.publish(
                SignalGenerated(bot_id=self.bot_id, signal=signal,
                                account_id=event.account_id, mode=event.mode,
                                correlation_id=event.correlation_id)
            )
```

### Example Strategy: SMA Crossover

```python
class SMACrossoverStrategy(Strategy):
    def __init__(self, config: dict):
        super().__init__(config)
        self.fast_period = config["fast_period"]
        self.slow_period = config["slow_period"]
        self.candles: list[Candle] = []

    def on_candle(self, candle: Candle) -> Signal | None:
        self.candles.append(candle)
        if len(self.candles) < self.slow_period:
            return None

        close_prices = [c.close for c in self.candles]
        fast_ma = sum(close_prices[-self.fast_period:]) / Decimal(str(self.fast_period))
        slow_ma = sum(close_prices[-self.slow_period:]) / Decimal(str(self.slow_period))

        prev_fast = sum(close_prices[-self.fast_period-1:-1]) / Decimal(str(self.fast_period))
        prev_slow = sum(close_prices[-self.slow_period-1:-1]) / Decimal(str(self.slow_period))

        if fast_ma > slow_ma and prev_fast <= prev_slow:
            return Signal(
                instrument=candle.instrument,
                direction=SignalDirection.BUY,
                strength=0.8,
                metadata={"fast_ma": float(fast_ma), "slow_ma": float(slow_ma)},
                candle_timestamp=candle.open_time,
                strategy_name="",
                strategy_version="",
                strategy_commit_sha="",
            )
        # ... sell and close logic
```

### Strategy Configuration (YAML)

```yaml
strategy:
  name: "sma_crossover"
  parameters:
    fast_period: 10
    slow_period: 50
```

The deployed strategy package is specified in the bot's configuration, which references a
`strategy_version` record containing the repository URL and pinned commit SHA. Strategy
parameters are passed from the bot config to the strategy constructor.

### Strategy State Isolation

Each bot pipeline creates its own strategy instance. Strategy state is not shared between
bots. Between runs (e.g., after a restart), the strategy is re-initialized with its
configuration — no persistent strategy state survives across bot restarts.

## Acceptance Criteria

- [ ] Strategy receives CandleClosed event and produces Signal
- [ ] Strategy engine emits SignalGenerated event with strategy version, commit SHA, and
      completed-candle timestamp
- [ ] Strategies are configurable via YAML and pinned to a deployed commit
- [ ] Example strategies produce reasonable signals on historical data
- [ ] Strategy interface supports completed candles and optional tick observation without
      generating tick signals
- [ ] Strategies declare required data types
- [ ] Strategy state is isolated per bot and reset between runs

## Done when

All acceptance criteria are met.
