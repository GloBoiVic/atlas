# Task 2 — Typed EventBus

Implement the EventBus in `backend/core/events.py` according to Feature 02 and the
architecture docs. Replace the old string-keyed queue/drain contract with exact
event-class subscriptions and sequential awaited delivery.

DomainEvent metadata: auto-generated `event_id` and `correlation_id`, UTC-aware
`occurred_at`, optional `account_id` and `bot_id`, and shared core `AccountMode`.
Define CandleClosed, TickReceived, SignalGenerated, RiskApproved, RiskRejected,
OrderSubmitted, OrderFilled, PositionOpened, PositionUpdated, PositionClosed,
TradeClosed, ApiError, DataFeedError, OrderRejected, OrderFailed, StrategyError,
ConnectionLost, ConnectionRestored, CircuitBreakerOpen, and CircuitBreakerClosed.
Events carry metadata only. `subscribe()` returns an unsubscribe handle. Exact
class matching only. Handler failures are logged with structlog, recorded through an
in-memory default/injected recorder, invoke an injected bot pause callback when a bot
ID exists, and do not stop later handlers. No deduplication. Preserve public typing.

Update tests/test_events.py for the new contract and comprehensive failure/order tests.
Commit the task and report to `.dispatch/task-2-report.md`.
