# Feature: 12 — Bot Management

## Description

Start, stop, pause, resume, and monitor multiple isolated paper/testnet bots from the UI. Bots run in one worker process under a durable supervisor and recover only after reconciliation.

The MVP runs a single worker process. `BotSupervisor` uses in-process per-bot locks and durable lifecycle state; there are no cross-worker leases, heartbeats, or worker ownership protocols. Startup restores active bots and reconciles before execution. Health-monitor and orphan-state handling remain deferred.

## Dependencies

- 02 — Core Infrastructure (BotSupervisor lifecycle contract, state machine)
- 04 — Strategy Engine
- 07 — Execution Layer
- 08 — Live Data Streaming
- 09 — Live Trading (pipeline construction, broker adapters)

## Deliverables

- [x] Bot model: Bot(strategy, broker, status, instrument, timeframe)
- [x] Bot pins a strategy repository, commit SHA, account, and execution mode
- [x] Bot lifecycle: Start, stop, pause, resume
- [ ] BotSupervisor: Owns one isolated pipeline per bot
- [ ] Bot status: Real-time status updates
- [ ] Startup restoration and broker reconciliation
- [x] Bot API endpoints: POST /bots, GET /bots, GET /bots/{id}, PATCH /bots/{id}, and
      idempotent start/stop/pause/resume commands
- [x] Bot UI: Start/stop/pause/resume controls, status indicators, and configuration forms
- [x] Confirmation dialogs: Destructive/trading-affecting actions require confirmation

## Technical Details

### Ownership Boundaries

Feature 12 owns the **persisted Bot-facing application service, CRUD/lifecycle API
endpoints, bot configuration UX, and lifecycle controls/status presentation**. It does not
implement a second supervisor:

- **Supervisor core:** Feature 02 owns the `BotSupervisor` contract and state machine.
  Feature 12 requests operations (start, stop, pause, resume) from the supervisor.
- **Pipeline construction:** Feature 09 owns mode-specific pipeline assembly and broker
  adapters. Feature 12 calls Feature 09 to construct pipelines.
- **Live feed:** Feature 08 provides the completed-candle stream that pipelines consume.
- **Startup restoration and reconciliation mechanics** remain Feature 02/09; Feature 12
  exposes their durable status and controls.

### Migration Policy

Bot configuration migration (schema changes across strategy versions) is deferred. The MVP
requires explicit stop/recreate to adopt a new strategy version or configuration. No
automated migration of running bot state across configuration changes exists.

### Create idempotency and duplicate semantics

`POST /bots` is idempotent by the canonical stopped-bot configuration identity:
`(account_id, mode, name, strategy_version_id, broker, instrument, timeframe, config_identity)`.
`config_identity` is a separate internal JSON projection: strings remain strings, while every
JSON number or Decimal is encoded as the reserved `{"__atlas_numeric__": "<canonical Decimal>"}`
object. This preserves runtime config types and Decimal precision while making `1`, `1.0`, and
Decimal `"1.00"` equivalent without conflating an intentional string value. A repeated valid
request with the same identity returns the existing bot and does not create another UUID. The
identity includes account and mode, so it cannot collapse bots across scopes. Changing any
identity component creates a new stopped record. The database constraint is authoritative for
concurrent requests; memory repositories implement the same equality semantics.

Migration 012 fails before creating its constraint if pre-existing duplicate bot identities are
detected, with an actionable operator error. It never deletes or silently changes trading records.
Migration 013 adds the canonical identity column; legacy rows remain nullable so migration does
not invent identities for historical configuration.

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
