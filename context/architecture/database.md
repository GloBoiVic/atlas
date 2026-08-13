# Database

## Purpose

This document defines Atlas persistence rules. PostgreSQL is the sole initial persistence layer for application/domain state, historical market data, runtime state, Strategy provenance, Experiments, and Orders/Fills/Trades. Domain meanings: [Domain Model](domain-model.md).

## Database Choice

PostgreSQL, SQLAlchemy 2, Alembic, psycopg 3. Do not introduce initially: TimescaleDB, ClickHouse, InfluxDB, Redis as primary state, object-storage-first market data, multiple operational databases. Add only after measured need.

## Persistence Principles

Persist: source-of-truth facts, durable configuration, immutable provenance, current projections for recovery, Strategy/runtime state across restart. Do not persist every temporary calculation.

## Logical Schema

Initial tables: strategies, strategy_versions, instruments, venue_instruments, market_bars, dataset_snapshots, experiments, trading_accounts, risk_profiles, deployments, strategy_states, trade_intents, risk_decisions, orders, order_events, fills, positions, trades, system_events, runtime_state. Exact names may differ. Do not create tables merely because a domain class exists.

## Domain vs Persistence Models

Keep separate: Domain objects, SQLAlchemy persistence models, Pydantic API schemas. Do not make SQLAlchemy models the universal application model. Keep mapping code straightforward.

## Primary Keys / Human Identity

Internal records: UUIDs. External broker IDs stored separately (orders.external_order_id). Never use broker IDs as Atlas primary identity. Normal UI uses human-readable labels, not raw UUIDs.

## Financial Precision

Persist exact financial values using PostgreSQL NUMERIC. Use Python Decimal where exact arithmetic matters. No binary floating-point for prices, quantities, monetary values, fees, P&L, risk amounts.

## Time

Store timestamps in UTC. Use timezone-aware values. Do not persist machine-local timestamps as canonical trading time.

## Immutable Historical Facts / Mutable Projections

Immutable: StrategyVersion, DatasetSnapshot, completed Experiment config, TradeIntent, RiskDecision, OrderEvent, Fill, SystemEvent. Correction appends or creates new provenance. Mutable: Order.current_status, Position, Deployment.actual_status, runtime heartbeat/state.

## StrategyVersion / DatasetSnapshot / Experiments

StrategyVersion preserves: Strategy identity, version identity, source fingerprint, parameter schema, timeframe/warm-up/capability requirements, creation timestamp. Do not overwrite old versions. DatasetSnapshot identifies immutable data view. Experiment persists immutable configuration; rerun creates new Experiment.

## Risk Snapshots / Deployment Configuration

Experiments and Deployments persist exact Risk configuration used — not just FK to mutable RiskProfile. Once a Deployment has traded, trading-relevant config must not silently mutate.

## Deployment / Position Uniqueness

At most one active Deployment per TradingAccount+Instrument — enforce at DB level. At most one current Position per Deployment — enforce transactionally.

## Order Idempotency / Fill Deduplication

Persist stable Atlas/client correlation IDs for broker submission. Broker execution identifiers unique where guaranteed. Repeated reconciliation must not create duplicate Fills.

## Order Events / Fill-Driven State Updates

OrderEvents append-only. Fill → atomically update Order status + Position + Trade + simulated account in one transaction.

## Network Calls and Transactions

Never hold DB transaction open during network calls. Pattern: persist intent/submission state → commit → external call → persist resulting facts.

## Market Bars / Identity

Market bars preserve: Instrument, provider, resolution, timestamps, OHLC, required price components, completion/provenance. Logical uniqueness prevents duplicates (Instrument+Provider+Resolution+PriceComponent+Timestamp). Index for actual query patterns.

## Missing Data / Historical Corrections

No fabricated bars. Distinguish expected closure vs unexpected gap. Provider corrections → new DatasetSnapshot/fingerprint. Completed Experiment provenance unchanged.

## Strategy State / Runtime State

Minimum state to survive restart: serializable, linked to StrategyVersion+Deployment, version-compatible. Do not store arbitrary Python objects. Persist only runtime info needed for ownership, heartbeat, desired/actual state, restart recovery, last processed frontier.

## Equity History / Metrics

Experiments persist account/equity history for equity curve, drawdown, metrics. Metrics are derived summaries; canonical inputs remain Fills, Trades, costs, equity history.

## Notes and Tags / Foreign Keys / Deletion Policy

Journal notes/tags are mutable user metadata separate from immutable execution facts. Use foreign keys for ownership/provenance. Prefer archival over destructive deletion for historical provenance.

## Migrations / Transactions / Concurrency

All schema changes via Alembic. One migration history. Test migrations. Use transactions around consistency boundaries. Assume concurrent API/runtime access; protect against duplicate activation, submission, Fill ingestion, stale overwrite.

## Repository Pattern

Focused repositories where needed (ExperimentRepository, MarketBarRepository, DeploymentRepository). Do not create BaseRepository[T], GenericCRUDRepository, RepositoryFactory as default infrastructure.

## Query Performance / Backups

Correctness first. Sensible indexes, bounded queries, batch insertion, pagination. Only add caching, partitioning, specialized storage after profiling. Backup/restore needed before meaningful LIVE usage but not blocking early development.

## Required Tests

Schema migrations, financial NUMERIC/Decimal round-trip, UTC timestamp round-trip, active Deployment uniqueness, Position uniqueness, market-bar duplicate prevention, Fill deduplication, immutable Experiment config, Risk snapshot independence, Fill/Position/Trade atomic update, historical deletion protection, repeated ingestion idempotency, concurrent duplicate-submission protection.

## Success Criteria

Working when Atlas can store canonical facts → enforce critical invariants → reproduce Experiment provenance → survive runtime restart → reconcile broker state without duplicates → query market data efficiently — using PostgreSQL alone without unnecessary persistence infrastructure.
