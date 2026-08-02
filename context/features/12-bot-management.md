# Feature: 12 — Bot Management

## Description

Start, stop, pause, resume, and monitor multiple isolated paper/testnet bots from the UI. Bots run in one worker process under a durable supervisor and recover only after reconciliation.

The MVP runs a single worker process. `BotSupervisor` uses in-process per-bot locks and durable lifecycle state; there are no cross-worker leases, heartbeats, or worker ownership protocols. Startup restores active bots and reconciles before execution. Health-monitor and orphan-state handling remain deferred.

## Dependencies

- 04 — Strategy Engine
- 07 — Execution Layer
- 08 — Live Data Streaming

## Deliverables

- [ ] Bot model: Bot(strategy, broker, status, instrument, timeframe)
- [ ] Bot pins a strategy repository, commit SHA, account, and execution mode
- [ ] Bot lifecycle: Start, stop, pause, resume
- [ ] BotSupervisor: Owns one isolated pipeline per bot
- [ ] Bot status: Real-time status updates
- [ ] Startup restoration and broker reconciliation
- [ ] Bot API endpoints: POST /bots, GET /bots, POST /bots/{id}/stop
- [ ] Bot UI: Start/stop buttons, status indicators
- [ ] Confirmation dialogs: Destructive actions require confirmation

## Technical Details

### Bot Model

The canonical bot schema and lifecycle statuses are defined in `context/database.md`. This feature owns runtime supervision and lifecycle behavior.

### Bot Service

```python
class BotService:
    def __init__(self, event_bus: EventBus, supervisor: BotSupervisor, repository: BotRepository, clock: Clock):
        self.supervisor = supervisor
        self.event_bus = event_bus
        self.repository = repository
        self.clock = clock

    async def start_bot(self, bot_id: UUID):
        bot = await self.repository.get(bot_id)
        strategy = self._load_strategy(bot.strategy_version_id)
        broker = self._load_broker(bot.broker_name)

        # Create and start the trading pipeline
        engine = TradingPipeline(
            bot_id=bot.id,
            strategy=strategy,
            broker=broker,
            event_bus=self.event_bus,
        )
        await self.supervisor.start(bot.id, engine)

        bot.status = BotStatus.RUNNING
        bot.started_at = self.clock.now()
        await self.repository.update(bot)

    async def stop_bot(self, bot_id: UUID):
        await self.supervisor.stop(bot_id)

        bot = await self.repository.get(bot_id)
        bot.status = BotStatus.STOPPED
        bot.stopped_at = self.clock.now()
        await self.repository.update(bot)
```

### Bot API Endpoints

```python
@router.post("/bots")
async def create_bot(config: BotConfig) -> Bot:
    ...

@router.get("/bots")
async def list_bots() -> List[Bot]:
    ...

@router.get("/bots/{bot_id}")
async def get_bot(bot_id: UUID) -> Bot:
    ...

@router.post("/bots/{bot_id}/start")
async def start_bot(bot_id: UUID):
    ...

@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: UUID):
    ...

@router.post("/bots/{bot_id}/pause")
async def pause_bot(bot_id: UUID):
    ...
```

### Bot UI

The UI uses the canonical Shadcn dialog, TanStack Query, WebSocket, and Sonner patterns from `context/library-docs.md`. Destructive lifecycle actions require confirmation.

## Acceptance Criteria

- [ ] Bots can be started, stopped, paused, and resumed from the UI
- [ ] Bot status is displayed in real time
- [ ] Confirmation dialogs appear for destructive actions
- [ ] Bot P&L is tracked and displayed
- [ ] Multiple bots can run simultaneously
- [ ] Multiple bots do not receive one another's events or share strategy/risk state
- [ ] Active bots are restored only after successful reconciliation
- [ ] Failed reconciliation leaves the bot paused or errored with no new orders

## Done when

All acceptance criteria are met.
