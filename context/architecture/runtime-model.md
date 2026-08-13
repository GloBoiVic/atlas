# Runtime Model

## Purpose

The Runtime Model defines how Atlas executes active PAPER and LIVE Deployments. Atlas uses atlas-api, atlas-runtime, and PostgreSQL. The runtime is a long-running process responsible for active trading; it is not a collection of microservices.

## Core Principle

The runtime owns ongoing trading execution. The API owns user-facing commands and queries. The database provides persistent state and coordination. Do not make the browser responsible for keeping trading alive.

## Process Roles / Not Separate Services

Architecture boundaries: [Architecture](architecture.md). Inside atlas-runtime, components (MarketDataService, StrategyEngine, RiskEngine, ExecutionEngine, ReconciliationService) are ordinary Python modules/classes. Do not create separate containers, network APIs, message queues, service discovery, or independent deployment units for these components.

## Deployment Ownership

A Deployment is persistent configuration; the runtime process is not the Deployment. Runtime state recoverable from: persistent Deployment config + broker truth + persisted Strategy state + market-data state.

## Desired vs Actual State

Atlas distinguishes desired Deployment state from actual runtime state. User request → API records desired state → runtime performs validation/reconciliation/warm-up → actual state becomes RUNNING. The UI must not report successful activation before the runtime safely performs it.

## Initial Command Model

User commands: START, PAUSE, RESUME, STOP, ARCHIVE. Persistence may use desired state rather than a separate command queue.

## Database Coordination

PostgreSQL with lightweight polling. Commands idempotent. Canonical state definitions and operator flows: [Deployment feature](../features/deployment.md).

## Runtime Loop

Critical path: receive/finalize completed bar → load Strategy state → strategy.evaluate() → persist updated state → if actionable: create TradeIntent → Risk PRE_FLIGHT → obtain executable context → Risk PRE_SUBMISSION → submit Order → process broker response/Fill. Do not require an internal event bus to understand this flow.

## Strategy Evaluation Scheduling

Runtime evaluates Strategy only when its required primary bar completes (for EMA Sweep Engulfing: completed 15m bar → one evaluation). Do not evaluate repeatedly against the same completed bar.

## Duplicate Evaluation Protection

Runtime must determine whether a completed bar has already been processed. A restart must not cause: same completed bar → duplicate TradeIntent → duplicate Order. Persist sufficient evaluation/state info for idempotent processing.

## Market Data Ownership

Runtime receives data through Atlas market-data services. Strategies do not subscribe directly to providers. Runtime ensures: required bars completed, data fresh, duplicate completed bars do not trigger duplicate evaluation. See: [Market Data Model](market-data-model.md).

## Strategy State Persistence

Meaningful state persisted after each deterministic transition/evaluation. A restart should restore pending setup, confirmation count, reference levels for the reference Strategy. Do not rely solely on process memory.

## Runtime Restart

On restart: find Deployments requiring ownership → load persisted state → connect broker → reconcile → restore Strategy state → recover market-data frontier → resume only if safe. Do not assume previous process ended cleanly.

## Market-Data Catch-Up / Stale Entries

After downtime, retrieve missed completed bars chronologically. Do not skip to newest bar if skipped bars could change Strategy state. Historical catch-up may reconstruct Strategy state but must not blindly execute stale entry intents. Initial behavior: prevent stale exposure creation.

## Broker Connection / Authority

Runtime owns active broker connectivity for trading. API may do independent validation but not trading execution. After uncertainty, broker truth is authoritative: [Reconciliation](../features/reconciliation.md). Only the runtime/execution workflow submits automated trading Orders.

## Manual Commands / Runtime Health

User-triggered risk-reducing actions must still pass through canonical execution and safety boundaries. No hidden direct-broker shortcut. Runtime health: persist HEALTHY/DEGRADED/UNAVAILABLE with heartbeat, broker connectivity, market-data freshness, reconciliation status.

## Single Runtime Assumption / Ownership Lock

Atlas v1 assumes one active atlas-runtime instance owns automated Deployments. Prevent two instances controlling the same Deployment with simple PostgreSQL-backed ownership/locking. Do not build distributed coordination.

## Experiment Execution

Historical Experiments do not require the long-running runtime process. They execute through application code using SimulationClock, HistoricalMarketData, SimulatedExecutionAdapter, SimulatedAccount. Do not force Experiment through live Deployment loop if unnecessarily complex.

## Shutdown / Unexpected Death

Graceful shutdown: stop new exposure → persist state → avoid new submissions → leave broker-hosted protection intact. Must not cancel protective Orders. Assume runtime can die without cleanup. Safety depends on: persisted state, idempotent execution, broker-hosted protection, startup reconciliation.

## No Supervisor Platform

Do not introduce BotSupervisor, WorkerSupervisor, ProcessManager, ActorSystem into the domain. If internal coordination needed, use a narrowly scoped runtime coordinator.

## Required Tests

At minimum: desired vs actual state, idempotent START, PAUSE blocks new exposure, PAUSE allows risk-reducing actions, STOP blocked with open Position, startup reconciliation before RUNNING, Strategy state restored after restart, same bar not evaluated twice, catch-up bars processed chronologically, stale catch-up TradeIntent not blindly executed, runtime heartbeat, second runtime cannot own same Deployment, broker unavailable at startup, FAILED blocks exposure, shutdown preserves broker protection.

## Success Criteria

Proven when Atlas can: receive START → runtime safely activates → process completed bars → evaluate Strategy once per bar → execute approved PAPER trade → persist state → survive runtime restart → reconcile broker truth → resume safely — without Redis, message broker, microservices, or generalized supervisor system.
