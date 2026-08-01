# Supervisor Task 4 — BotSupervisor

Implement `backend/worker/supervisor.py` using only the repository and runtime protocols.
The supervisor owns multiple isolated bot pipelines, one per bot, with per-bot
`asyncio.Lock` instances. Generate one UUID worker_id per supervisor. Use heartbeat
interval 10 seconds and lease timeout 30 seconds, with an injected Clock.

Required behavior:
- Idempotent concurrent start/stop/pause/restore operations per bot.
- Claim the durable lease before creating a pipeline.
- Start and restore with execution disabled; reconcile before enabling execution.
- Explicit pause keeps feed/strategy tasks alive and only disables execution.
- Successful reconciliation is the only path to RUNNING and execution enabled.
- MISMATCHED/FAILED reconciliation and pipeline failures persist ERROR, keep execution
  disabled, and require explicit human action; no automatic retry loop.
- PAUSED is resumable by explicit start/restore and is not auto-restored.
- On startup, auto-restore only persisted RUNNING/STARTING bots.
- Heartbeat renews every 10 seconds; ownership failure disables execution and persists
  ERROR. Graceful stop/shutdown stops pipelines, persists STOPPED, and releases leases.
- Publish BotStatusChanged after each persisted lifecycle transition and log transition
  context with structlog.
- Keep different bots independent.

Write comprehensive supervisor tests using in-memory repository and fake pipeline,
factory, reconciler, clock, and EventBus. Cover concurrency, restore filtering,
execution gating, reconciliation failures, ownership/heartbeat failure, and shutdown.
Run pytest, Ruff, mypy, and diff checks. Commit and report to
`.dispatch/supervisor-task-4-report.md`.
