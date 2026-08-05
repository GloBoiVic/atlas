# Feature: 04 — Strategy Engine

## Description

Strategies generate signals from market data. Same code works in backtesting and live trading.

## Dependencies

- 02 — Core Infrastructure
- 03 — Data Layer

## Deliverables

- [x] Strategy base class: `on_candle()`, optional `on_tick()`, `required_data()`
- [x] Signal model: includes strategy version, commit SHA, and completed-candle timestamp
- [x] Strategy engine: Subscribes to `CandleClosed`, calls strategy, emits `SignalGenerated`
- [x] Example strategy: SMA crossover (trend following)
- [x] Example strategy: Bollinger Bands (mean reversion)
- [~] Strategy configuration: Versioned YAML-based parameters (YAML validation boundary exists in `backend/config.py`; end-to-end wiring from YAML → registry → engine constructor is deferred to the Bot Supervisor feature)
- [x] Strategy registration: Load only from the deployed strategy registry, never from API-supplied paths
- [x] Per-bot strategy state isolation and reset

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
```

The `DomainEvent` base class correctly uses `UUID` typed fields for `event_id`,
`correlation_id`, `account_id`, and `bot_id`.

## Technical Details

### Strategy Base Class

Strategies return a trading decision (`StrategyDecision`) containing direction, Decimal
strength, and indicator metadata. The engine assembles the canonical `Signal` with full
provenance. Strategies never construct `Signal` objects themselves.

```python
@dataclass(frozen=True, slots=True)
class DataRequirement:
    data_type: DataType        # CANDLE, TICK, etc.
    timeframe: str             # "1m", "5m", "1h" — validated against bot config
    warmup_candles: int = 0    # deterministic historical prefix consumed before replay

class Strategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        """Evaluate a completed candle and optionally return a trading decision."""
        pass

    def on_tick(self, tick: Tick) -> None:
        """Observe a tick for state/monitoring; candle signals remain canonical.
        The default is a no-op — strategies that need tick state override this."""
        return None

    def required_data(self) -> DataRequirement:
        """Declare the data requirement for this strategy.
        Feature 04 supports one candle requirement only."""
        return DataRequirement(data_type=DataType.CANDLE, timeframe="1m")
```

`warmup_candles` is part of the validated strategy/data contract. Backtests use this
declared count rather than an optional strategy attribute, and warm-up evaluation never emits
trading signals.

### Signal Model

```python
@dataclass(frozen=True, slots=True)
class Signal:
    instrument_id: UUID
    direction: SignalDirection          # BUY, SELL, CLOSE
    strength: Decimal                   # 0.0 to 1.0 (Decimal domain)
    metadata: dict                      # Strategy-specific data (indicator values, etc.)
    candle_timestamp: datetime          # Completed candle that triggered this signal
    strategy_version_id: UUID           # Canonical strategy version identity
    strategy_name: str
    strategy_commit_sha: str

class SignalDirection(Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
```

### Strategy Engine

The engine owns bot/account scope, instrument and candle provenance, strategy identity,
validation, and deduplication. Strategies return a lightweight decision; the engine
assembles the canonical provenance-bearing Signal and owns the `strategy_version_id`.

```python
class StrategyEngine:
    def __init__(self, event_bus: EventBus, bot_id: UUID, account_id: UUID,
                 instrument_id: UUID, strategy: Strategy,
                 strategy_version_id: UUID, strategy_name: str,
                 commit_sha: str, data_requirement: DataRequirement):
        self._event_bus = event_bus
        self._bot_id = bot_id
        self._account_id = account_id
        self._instrument_id = instrument_id
        self._strategy = strategy
        self._strategy_version_id = strategy_version_id
        self._strategy_name = strategy_name
        self._commit_sha = commit_sha
        self._data_requirement = data_requirement
        self._warmed_up = False
        self._seen_candle_keys: set[tuple] = set()
        self._event_bus.subscribe(CandleClosed, self._on_candle)

    @staticmethod
    def _candle_key(candle: Candle) -> tuple:
        """Canonical composite key matching the database uniqueness constraint."""
        return (candle.instrument_id, candle.provider,
                candle.timeframe, candle.open_time, candle.price_basis)

    async def warm_up(self, candles: list[Candle]) -> None:
        """Feed historical candles to rebuild strategy state.
        No trading signals are emitted during warm-up."""
        for candle in candles:
            self._strategy.on_candle(candle)
        self._warmed_up = True

    async def _on_candle(self, event: CandleClosed) -> None:
        if not self._warmed_up:
            return

        candle = event.candle
        key = self._candle_key(candle)

        if key in self._seen_candle_keys:
            return  # Duplicate protection

        # Validation before strategy evaluation
        if candle.instrument_id != self._instrument_id:
            return  # Instrument mismatch
        if candle.timeframe != self._data_requirement.timeframe:
            return  # Timeframe mismatch
        if not candle.is_complete:
            return  # Incomplete candle — not eligible for signal generation

        self._seen_candle_keys.add(key)

        try:
            decision = self._strategy.on_candle(candle)
        except Exception:
            await self._event_bus.publish(
                StrategyError(bot_id=self._bot_id,
                              error="strategy on_candle failed")
            )
            return  # Fail closed — no signal, bot paused by supervisor

        if decision is not None:
            signal = Signal(
                instrument_id=self._instrument_id,
                direction=decision.direction,
                strength=decision.strength,
                metadata=decision.metadata,
                candle_timestamp=candle.open_time,
                strategy_version_id=self._strategy_version_id,
                strategy_name=self._strategy_name,
                strategy_commit_sha=self._commit_sha,
            )
            await self._event_bus.publish(
                SignalGenerated(
                    bot_id=self._bot_id, signal=signal,
                    account_id=self._account_id, mode=event.mode,
                    correlation_id=event.correlation_id
                )
            )
```

### Example Strategy: SMA Crossover

Strategies return a lightweight decision (direction, strength, metadata). The engine
assembles the canonical Signal with instrument identity, strategy version, and provenance.

```python
@dataclass(frozen=True, slots=True)
class StrategyDecision:
    direction: SignalDirection
    strength: Decimal
    metadata: dict

class SMACrossoverStrategy(Strategy):
    def __init__(self, config: dict):
        super().__init__(config)
        self.fast_period = config["fast_period"]
        self.slow_period = config["slow_period"]
        self.candles: list[Candle] = []

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        self.candles.append(candle)
        if len(self.candles) < self.slow_period:
            return None

        close_prices = [c.close for c in self.candles]
        fast_ma = sum(close_prices[-self.fast_period:]) / Decimal(str(self.fast_period))
        slow_ma = sum(close_prices[-self.slow_period:]) / Decimal(str(self.slow_period))

        prev_fast = sum(close_prices[-self.fast_period-1:-1]) / Decimal(str(self.fast_period))
        prev_slow = sum(close_prices[-self.slow_period-1:-1]) / Decimal(str(self.slow_period))

        if fast_ma > slow_ma and prev_fast <= prev_slow:
            return StrategyDecision(
                direction=SignalDirection.BUY,
                strength=Decimal("0.8"),
                metadata={"fast_ma": fast_ma, "slow_ma": slow_ma},
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

### No-Future-Data Expectation

The strategy engine operates on completed candles only. A signal confirmed at candle `T`
close is eligible at the `T+1` candle open — never at `T` itself. The engine never receives
incomplete candles for signal evaluation. Strategy authors must not reference future data
(e.g., using `T+1` close within `on_candle` at `T`). A lookahead validation gate should
be applied before trusting any backtest result (Feature 05, Feature 13).

### Repeated-Signal Responsibility

The engine deduplicates candle events by the canonical composite key
`(instrument_id, provider, timeframe, open_time, price_basis)`. A strategy that emits the
same direction as a previously filled signal for the same market direction is permitted —
repeated signals are handled by the Risk Engine (position-size limits, max open positions).
The strategy engine does not suppress consecutive signals of the same direction; Risk
decides whether a new position is warranted.

### Strategy Version Immutability

A running bot keeps its pinned strategy version — it never hot-reloads from a new commit.
Adopting a new strategy commit requires an explicit stop/recreate cycle. The deployed
strategy package's parameter schema and safe defaults are authoritative; bot configurations
supply validated YAML values that are frozen and recorded alongside the
`strategy_version_id`.

### Warm-up and Replay Ownership

The replay/data-feed layer (Feature 05, Feature 08) owns sourcing and ordering historical candles.
The Strategy Engine owns the warm-up lifecycle and signal gating:

- The engine's `warm_up()` method accepts ordered historical candles and feeds them to the
  strategy to rebuild internal state (moving averages, buffers, etc.).
- Warm-up candles are evaluated by `on_candle()` but **never** emit a trading signal.
- Signal generation begins only after `warmed_up` transitions to `True`.
- The engine does not source, fetch, or order historical data — it receives pre-sourced
  candles from the caller.

### Registry and Deployment Trust

The runtime registry resolves only already-deployed and explicitly registered strategy
packages:

1. A `StrategyVersion` record (persisted in the database) contains the repository URL
   and pinned commit SHA.
2. The registry verifies that the installed package identity matches the expected strategy
   and pinned commit SHA at startup.
3. Missing packages, version mismatches, or SHA mismatches fail closed — the bot does
   not start.
4. Registry code does **not** clone repositories, install dependencies, or execute
   API-supplied import paths.

### Parameter Ownership

- The deployed strategy package owns the parameter schema and safe defaults.
- The bot or backtest configuration owns the selected YAML parameter values.
- Atlas validates parameter values against the schema, freezes the configuration, and
  records the selected parameter snapshot alongside the `strategy_version_id`.
- Parameter changes require a new bot configuration; they are not hot-reloaded.

### Safety and Validation

- The engine accepts only completed candles matching the bot's instrument and timeframe.
- Duplicate candle events (same composite key `(instrument_id, provider, timeframe, open_time, price_basis)`) are silently rejected.
- A strategy exception produces no signal, publishes a `StrategyError` event, and pauses
  the affected bot under the existing EventBus failure contract.
- Strategy hooks (`on_candle`, `on_tick`) are synchronous and computation-focused; they
  perform no I/O (database, network, or broker access).
- The engine validates that the candle's `instrument_id`, `timeframe`, and `is_complete`
  flag match the bot's data requirement before calling `on_candle()`.

### Strategy State Isolation

Each bot pipeline creates its own strategy instance. Strategy state is not shared between
bots. Between runs (e.g., after a restart), the strategy is re-initialized with its
configuration — no persistent strategy state survives across bot restarts.

## Acceptance Criteria

- [x] Strategy receives CandleClosed event and produces a trading decision
- [x] Strategy engine assembles immutable Signal with `strategy_version_id`, `instrument_id`,
      `candle_timestamp`, and Decimal `strength`
- [x] Strategy engine emits `SignalGenerated` with the assembled Signal (no `candle_id`)
- [x] Strategy engine validates completed-candle instrument, timeframe, and completeness
- [x] Strategy engine rejects duplicate candle events silently via the canonical composite
      key `(instrument_id, provider, timeframe, open_time, price_basis)`
- [x] Strategy exception publishes `StrategyError` and pauses bot (fail-closed)
- [x] Strategies are configurable via YAML (validated by `backend/config.py` `StrategyConfig`)
      and registry resolution verifies pinned commit SHA
- [x] Strategy engine owns warm-up lifecycle; warm-up candles never emit signals
- [x] Registry resolves only deployed, version-pinned packages and fails closed on mismatch
- [x] Example strategies produce reasonable signals on historical data
- [x] Strategy interface supports completed candles and optional tick observation without
      generating tick signals
- [x] Strategies declare a timeframe-aware `DataRequirement`
- [x] Strategy state is isolated per bot and reset between runs

## Done when

All acceptance criteria are implemented at the component level and validated in the
development environment (Ruff, mypy, full `pytest` suite). End-to-end integration
from YAML configuration → registry → engine constructor is deferred to the Bot
Supervisor feature. Feature 04 is not complete until the orchestrator's final
validation gate passes.
