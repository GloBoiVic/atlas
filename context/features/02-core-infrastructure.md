# Feature: 02 — Core Infrastructure

## Description

EventBus, Clock abstraction, error handling, configuration system, and structured logging. The foundation that all other components build on.

## Dependencies

- 01 — Project Foundation

## Deliverables

- [x] EventBus: In-process pub/sub with typed, bot-scoped domain events
- [x] Event types defined: CandleClosed, TickReceived, SignalGenerated, RiskApproved, RiskRejected, OrderSubmitted, OrderFilled, PositionOpened, PositionUpdated, PositionClosed, TradeClosed
- [x] Error events defined: ApiError, DataFeedError, OrderRejected, OrderFailed, StrategyError, ConnectionLost, ConnectionRestored, CircuitBreakerOpen, CircuitBreakerClosed
- [x] Clock abstraction: LiveClock, SimulationClock
- [x] Configuration system: Pydantic Settings, YAML strategy config, deployment mode validation
- [x] Structured logging: structlog setup
- [ ] Error handling: Retry logic and circuit breaker are complete; health monitor remains deferred

## Technical Details

### EventBus

```python
class EventBus:
    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> Subscription

    async def publish(self, event: DomainEvent) -> None
```

Handlers run in deterministic registration order. `publish()` awaits each handler. Events include `event_id`, `occurred_at`, `correlation_id`, `account_id`, `bot_id`, and `mode` where applicable. Handlers must be idempotent. A trading-critical handler failure pauses the affected bot and is recorded; it is never silently swallowed.

### Clock Abstraction

```python
class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime

class LiveClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

class SimulationClock(Clock):
    def __init__(self, start_time: datetime):
        self._current_time = start_time

    def now(self) -> datetime:
        return self._current_time

    def advance(self, new_time: datetime):
        self._current_time = new_time
```

### Configuration (YAML)

```yaml
# config/default.yaml
strategy:
  name: "sma_crossover"
  parameters:
    fast_period: 10
    slow_period: 50

risk:
  max_open_positions: 5
  per_trade_risk: 0.01

broker:
  name: "paper"
  mode: "paper"
  # name: "binance"
  # mode: "testnet"
```

### Runtime Supervisor

`BotSupervisor` is responsible for starting, stopping, pausing, restoring, and reconciling multiple independent bot pipelines inside one worker process. It persists lifecycle state and guarantees that only one runtime instance controls a bot.

### Error Handling

```python
class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    async def call(self, func: Callable, *args, **kwargs):
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

### Structured Logging

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
```

## Acceptance Criteria

- [x] EventBus publishes and subscribes to typed events
- [x] SimulationClock advances through timestamps deterministically
- [x] Configuration loads from YAML and environment variables
- [x] Errors are logged with structured context
- [x] Circuit breaker opens/closes based on failure counts
- [x] Retry logic retries transient failures with exponential backoff
- [x] Event delivery order, failure handling, bot scoping, and idempotency are tested
- [x] Bot supervisor starts and stops isolated pipelines idempotently

## Done when

All acceptance criteria are met.
