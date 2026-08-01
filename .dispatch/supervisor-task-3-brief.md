# Supervisor Task 3 — Runtime Protocols

Define the injected runtime contracts used by BotSupervisor. Add a `BotPipeline` protocol
with `start()`, `stop()`, `set_execution_enabled(bool)`, and `execution_enabled`.
Add a `PipelineFactory` protocol that creates one pipeline per owned bot, and a
`Reconciler` protocol returning a typed result with status, broker snapshot, differences,
and optional error.

Only MATCHED reconciliation is safe to execute. MISMATCHED and FAILED both prevent
execution. Keep protocols independent of persistence implementations and concrete
strategy/feed/execution components. Add protocol/result tests or contract fixtures as
useful. Run checks, commit, and report to `.dispatch/supervisor-task-3-report.md`.
