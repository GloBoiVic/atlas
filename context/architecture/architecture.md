# Architecture

## Purpose

This document defines the high-level architecture of Atlas — a strategy-first algorithmic trading workstation for independent systematic traders. The architecture exists to support one core lifecycle: Build → Test → Deploy → Monitor → Improve. The same StrategyVersion should move through Experiment → PAPER → LIVE without changing its trading methodology.

## Architectural Style

Atlas is a modular monolith with a separate long-running trading runtime. Primary components: Next.js frontend, FastAPI API, atlas-runtime, PostgreSQL, external integrations. Do not introduce distributed architecture unless measured requirements justify it.

## Process Model

Two persistent Python process roles: **atlas-api** (REST/JSON API, WebSocket endpoints where justified, command validation, application queries, user-facing config) and **atlas-runtime** (active Deployment execution, market-data consumption, Strategy evaluation, Risk evaluation, Order coordination, Fill processing, Strategy-state persistence, broker reconciliation, runtime health). See: [Runtime Model](runtime-model.md).

## Frontend

Stack: Next.js 16, React 19, TypeScript strict, Tailwind CSS v4, shadcn/ui, Lucide React, Sonner, TradingView Lightweight Charts. The frontend is a trading workstation, not a trading engine. It may query state, issue commands, display live updates, inspect Experiments/Deployments/Trades/accounts. It must not: call brokers directly, execute Strategy logic, own trading lifecycle state. UX rules: [Design](../design/design.md).

## Backend

Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3, PostgreSQL, NumPy, Polars, pytest, pytest-asyncio. Backend code organized by responsibility, not by deployable service. Repository organization: [Repository Structure](repository-structure.md).

## Core Trading Pipeline

StrategyVersion → TradeIntent → RiskDecision → Order → Fill → Position → Trade. Canonical terminology and domain ownership: [Domain Model](domain-model.md). Do not create environment-specific parallel domain models.

## Strategy Boundary

Strategies are deterministic Python trading logic consuming Atlas-controlled context. They do not know whether running in Experiment, PAPER, or LIVE. Must not access: broker APIs, database, HTTP, filesystem, account equity, wall-clock time. Contract: [Strategy Contract](strategy-contract.md).

## Market Data Boundary

Providers normalized before Strategy evaluation. Initial: OANDA → EUR/USD → 1m base → deterministic 15m bars. Historical and live must preserve same completed-bar semantics. Rules: [Market Data Model](market-data-model.md).

## Risk Boundary

Strategy defines trade structure (direction, stop, target, exit methodology). Atlas Risk controls capital exposure (eligibility, risk budget, position size, account constraints, drawdown/loss limits). Shared conceptually across Experiment, PAPER, LIVE. Feature behavior: [Risk Management](../features/risk-management.md).

## Execution Boundary

Strategies never submit Orders directly. Approved trading intent flows through canonical Atlas execution. Adapters translate Atlas Orders into venue-specific requests. Initial: SimulatedExecutionAdapter, OandaExecutionAdapter. OANDA types inside integration boundary. Behavior: [Execution](../features/execution.md).

## Simulation

Historical Experiments use the canonical simulation pipeline: HistoricalMarketData, SimulationClock, SimulatedAccount, SimulatedExecutionAdapter — reusing the same Strategy/Risk/Order/Fill/Position/Trade pipeline as PAPER/LIVE. Do not create a parallel Experiment architecture. See: [Experiments](../features/experiments.md).

## Account State

Experiments use simulated account state; PAPER/LIVE use normalized broker account state. Risk consumes economic information without depending on source environment. Financial semantics: [Accounting Model](accounting-model.md).

## Broker Integration

OANDA is initial reference broker/provider for Forex. Atlas core must not become OANDA-specific. Broker adapters own: authentication, provider-native DTOs, symbol mapping, account normalization, market-data requests, Order translation, broker error translation. Canonical Atlas domain objects remain broker-independent.

## Instrument Model

Atlas distinguishes **Instrument** (e.g., EUR/USD) from **VenueInstrument** (e.g., OANDA EUR_USD). Canonical Instrument identity must not depend on provider-specific symbols.

## Broker Authority

For PAPER/LIVE the broker is authoritative for actual state. Canonical behavior: [Reconciliation](../features/reconciliation.md).

## Safety Model

Atlas fails closed for new exposure when state is unknown, stale, contradictory, unreconciled, or unsafe. Canonical: [Safety Model](safety-model.md).

## Persistence

PostgreSQL is the sole initial persistence layer: domain state, runtime state, Strategy provenance, Experiments, historical market data, Orders/Fills/Trades, account snapshots. Do not introduce separate time-series DB or object-storage initially. Rules: [Database](database.md).

## API Contract

REST/JSON for normal commands and queries (create Experiment, inspect StrategyVersion, configure Deployment, query Trades, update notes). WebSockets only for genuinely live state (Position changes, Fill events, Deployment status, runtime health). Polling acceptable where simpler.

## Type Ownership

Python/Pydantic owns the API contract. Generate TypeScript types from FastAPI OpenAPI where practical. Do not maintain duplicate manually authored API schemas.

## Internal Communication

Prefer direct typed method calls for the core trading path: completed bar → Strategy → Risk → Execution. Internal events may support UI updates, SystemEvents, analytics, notifications, observability — but an event bus is not required to understand the basic trading flow.

## No Distributed Event Architecture

Do not introduce by default: Kafka, RabbitMQ, Redis Streams, distributed event buses, event sourcing, CQRS. Internal events remain ordinary in-process/application concerns unless future measured requirements demand otherwise. API and runtime coordinate Deployment desired/actual state through PostgreSQL (see [Runtime Model](runtime-model.md)). Atlas v1 assumes one active runtime owns automated Deployments.

## Broker-Hosted Protection

Where supported, protective stops/targets should exist at the broker. Trading safety must not depend solely on Atlas process uptime. A runtime crash should not leave an open Position unprotected.

## Failure Recovery

Atlas must assume: process crashes, network timeouts, broker disconnects, missed Fills, stale local state. Recovery relies on persistent state + stable execution identifiers + broker-hosted protection + reconciliation — not on perfect process uptime.

## No Mandatory Docker

Docker is not required for development or architecture. Local dev may run Next.js, FastAPI, atlas-runtime, PostgreSQL as normal processes. Docker may later package for deployment convenience; do not turn Docker boundaries into application architecture boundaries.

## Deferred Infrastructure

Do not introduce initially: Redis, Celery, Dramatiq, Kafka, RabbitMQ, Kubernetes, TimescaleDB, ClickHouse, CQRS, event sourcing, microservices, generic plugin platform, distributed workers. A measured requirement must exist before adding them.

## Experiment Workers

Experiments may initially run through normal Python application execution. If heavy simulations later interfere with live runtime performance: measure → introduce dedicated Experiment worker if needed. Do not create job infrastructure before that problem exists.

## Market Scope

Initial: Forex. Reference: OANDA. Future: crypto derivatives. Out of scope: crypto spot, U.S. exchange-traded futures, equities, options, HFT/tick-level trading. Market-specific economics should extend the architecture through explicit boundaries.

## UI Navigation

Primary: Dashboard, Strategies, Experiments, Deployments, Journal, Data, Settings. Do not expose implementation architecture (Workers, Engines, Supervisors, Event Bus) as user-facing concepts unless a genuine operator workflow later requires it.

## Testing Architecture

Prioritize: deterministic Strategy tests, market-data aggregation tests, Risk tests, simulation integration tests, execution idempotency, broker adapter tests, restart/reconciliation tests, critical UI workflows. Do not treat raw coverage percentage as correctness.

## Architecture Evolution

Future requirements (additional brokers, crypto derivatives, heavier Experiment workloads, richer analytics) should extend existing boundaries before creating new architectural systems. A future need should not create speculative code today.

## Architecture Change Rule

If implementation requires a new persistent process, infrastructure, domain concept, persistence technology, communication layer, or environment-specific engine: the change must first be checked against Atlas context. Do not introduce architectural changes silently during feature implementation.

## Architectural Success

The architecture is working when Atlas can prove: historical EUR/USD → completed 15m bars → EMA Sweep Engulfing → deterministic Experiment → trustworthy Trades → OANDA Practice → same StrategyVersion → live completed bars → Risk → Order → Fill → protected Position → restart → reconciliation → safe resume — with a codebase understandable without distributed infrastructure.
