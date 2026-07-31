# Feature: 04 — Strategy Engine

## Description

Strategies generate signals from market data. Same code works in backtesting and live trading.

## Dependencies

- 02 — Core Infrastructure
- 03 — Data Layer

## Deliverables

- [ ] Strategy base class: on_candle(), optional on_tick(), required_data()
- [ ] Signal model: Signal(instrument, direction, strength, metadata)
- [ ] Strategy engine: Subscribes to CandleClosed, calls strategy, emits SignalGenerated
- [ ] Example strategy: SMA crossover (trend following)
- [ ] Example strategy: Bollinger Bands (mean reversion)
- [ ] Strategy configuration: Versioned YAML-based parameters
- [ ] Strategy registration: Load only from the deployed strategy registry

## Technical Details

### Strategy Base Class

```python
class Strategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def on_candle(self, candle: Candle) -> Optional[Signal]:
        """Evaluate a completed candle and optionally generate a signal."""
        pass

    @abstractmethod
    def on_tick(self, tick: Tick) -> None:
        """Observe a tick for state/monitoring; candle signals remain canonical."""
        return None

    def required_data(self) -> List[DataType]:
        """Declare what data types this strategy requires."""
        return [DataType.CANDLE]
```

### Signal Model

```python
class Signal:
    instrument: str
    direction: SignalDirection  # BUY, SELL, CLOSE
    strength: float  # 0.0 to 1.0
    metadata: dict  # Strategy-specific data
    timestamp: datetime

class SignalDirection(Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
```

### Strategy Engine

```python
class StrategyEngine:
    def __init__(self, event_bus: EventBus, bot_id: UUID, strategies: List[Strategy]):
        self.event_bus = event_bus
        self.bot_id = bot_id
        self.strategies = strategies
        self.event_bus.subscribe(CandleClosed, self._on_candle)

    async def _on_candle(self, event: CandleClosed):
        for strategy in self.strategies:
            signal = strategy.on_candle(event.candle)
            if signal:
                await self.event_bus.publish(
                    SignalGenerated(bot_id=self.bot_id, signal=signal)
                )
```

### SMA Crossover Strategy

```python
class SMACrossoverStrategy(Strategy):
    def __init__(self, config: dict):
        super().__init__(config)
        self.fast_period = config["fast_period"]
        self.slow_period = config["slow_period"]
        self.candles = []

    def on_candle(self, candle: Candle) -> Optional[Signal]:
        self.candles.append(candle)
        if len(self.candles) < self.slow_period:
            return None

        fast_ma = np.mean([c.close for c in self.candles[-self.fast_period:]])
        slow_ma = np.mean([c.close for c in self.candles[-self.slow_period:]])

        if fast_ma > slow_ma and self._prev_fast <= self._prev_slow:
            return Signal(
                instrument=candle.instrument,
                direction=SignalDirection.BUY,
                strength=0.8,
                metadata={"fast_ma": fast_ma, "slow_ma": slow_ma},
                timestamp=candle.timestamp,
            )
        # ... sell logic
```

### Strategy Configuration (YAML)

```yaml
strategies:
  - name: "sma_crossover"
    entrypoint: "sma_crossover"
    repository: "git@github.com:private/atlas-strategies.git"
    commit_sha: "<pinned-commit>"
    instrument: "BTCUSDT"
    timeframe: "1h"
    parameters:
      fast_period: 10
      slow_period: 50
```

## Acceptance Criteria

- [ ] Strategy receives CandleClosed event and produces Signal
- [ ] Strategy engine emits SignalGenerated event
- [ ] Strategies are configurable via YAML and pinned to a deployed commit
- [ ] Example strategies produce reasonable signals on historical data
- [ ] Strategy interface supports completed candles and optional tick observation without generating tick signals
- [ ] Strategies declare required data types
- [ ] Strategy state is isolated per bot and reset between runs
- [ ] Signals include the strategy version and completed-candle timestamp

## Done when

All acceptance criteria are met.
