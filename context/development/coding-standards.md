# Coding Standards

## Purpose

Define Atlas implementation standards. Goal: simple, explicit, testable code preserving trading correctness. Prefer clear over clever, explicit over hidden magic, small correct implementations over speculative frameworks.

The current implemented path is historical Experiments and their persisted evidence. PAPER/LIVE execution, monitoring, and broker-confirmed Trade behavior described by these standards are future target contracts unless current status explicitly says otherwise. See [Current status](../../CURRENT.md).

## General Principles

Code should be: readable, typed, deterministic where required, easy to test/audit, explicit about failure, scoped to active roadmap slice. Avoid unnecessary abstraction.

## Context First / Naming

Before implementing, follow [agent-workflow.md](agent-workflow.md). Use active feature spec and relevant architecture files as source of truth. Do not invent product behavior in code. Use domain language from [domain-model.md](../architecture/domain-model.md). Prefer descriptive names (simulation_clock.py, risk_engine.py, oanda_execution.py). Avoid vague names (manager.py, helper.py, utils.py) unless responsibility is explicit.

## Python

Python 3.13. Modern features. Type annotations for public functions, domain/persistence boundaries, Strategy contracts, Risk/execution interfaces. Avoid untyped trading-critical code. Prefer concrete domain types over loosely structured dictionaries.

## Decimal Precision / Time

Decimal for authoritative prices, quantities, account values, fees, P&L, risk amounts. No binary floating-point for financial state. NumPy float OK for analytical computations but values crossing into financial state must be converted safely. Timezone-aware UTC values. No wall-clock time inside Strategy/deterministic simulation/Risk without explicit injection.

## Determinism / Functions / Classes

Trading-critical code: no hidden inputs. Strategy/simulation not dependent on global mutable state, random unseeded values, wall-clock time, external I/O, unordered iteration. Identical inputs → identical outputs. Small functions, one clear responsibility. Classes for meaningful state/lifecycle/interface/identity. Plain typed functions acceptable where simpler. Composition over inheritance.

## Interfaces / Repository Pattern / Domain Independence

Explicit interfaces at external boundaries (execution adapter, market-data provider, clock, account-state source). Direct typed calls for internal collaboration. Focused repositories (ExperimentRepository, DeploymentRepository). No BaseRepository[T]/GenericCRUDRepository/RepositoryFactory. Core domain code must not import FastAPI, SQLAlchemy, OANDA SDK/DTOs, frontend types, HTTP clients. Infrastructure depends on domain concepts, not reverse.

## API Schemas / SQLAlchemy / Transactions / Async

Pydantic v2 for API boundaries — separate from SQLAlchemy models and domain objects. SQLAlchemy 2: explicit sessions, transactions, typed models, focused queries, async DB I/O where appropriate. Transactions for real consistency boundaries. Never hold DB transaction open during network calls. Async primarily for I/O (DB, HTTP, WebSockets, provider connections); not for pure domain calculations.

## External APIs / Error Handling / Exceptions / Logging

Provider adapters normalize inputs/outputs, translate errors, preserve identifiers, avoid leaking DTOs. Errors: handle locally with known safe behavior OR propagate as typed/application error. Specific exceptions, not one giant generic type. Log meaningful context (Deployment, StrategyVersion, Experiment, Instrument, Order IDs). Never log API tokens, secrets, credentials. Use SystemEvent for operational facts; logs for diagnostics. No persisting every debug log as SystemEvent.

## Configuration / Environment Branching

Explicit config. Secrets from secure environment config — never hardcoded tokens, account IDs, URLs, credentials. No commits of secrets. Strategy code must not branch on EXPERIMENT/PAPER/LIVE. Environment behavior belongs in adapters, clocks, account sources, runtime/simulation boundaries.

## Strategy / Risk / Execution / Simulation Code

Strategy: obey [strategy-contract.md](../architecture/strategy-contract.md); deterministic, side-effect free, no IO, independent of account sizing. Risk: explicit inputs; decisions reproducible from persisted inputs; no unrelated state queries. Execution: idempotent under uncertainty; stable identifiers + reconciliation required; no timeout→unconditional retry. Simulation: reuse canonical domain logic; no BacktestTrade, BacktestOrder, BacktestRiskEngine.

## Market Data / DataFrames / Comments / Docstrings / TODOs

Follow [market-data-model.md](../architecture/market-data-model.md): UTC, completed bars, deterministic aggregation, no lookahead, BID/ASK/MID semantics, no silent forward-filling. Polars/NumPy OK for efficient calculations; not the primary domain API. Comments explain why, non-obvious semantics, safety rationale. Docstrings for public interfaces and non-obvious behavior. TODOs must be specific and reference phase.

## Dead Code / Feature Flags / Dependencies

Remove obsolete code. No large commented-out implementations. No feature-flag framework initially. Before adding dependency: verify slice requires it, check existing stack, verify tech-stack.md, prefer mature focused libraries, avoid implicit architecture changes.

## Frontend TypeScript / React / Next.js / State

Strict TypeScript; avoid any in product code. Prefer generated API types. Small composable components, feature-local behavior, explicit props, accessible interactions. App Router. Route files focused on composition, not trading logic. Prefer: backend-authoritative state, server data where appropriate, local state, focused hooks. No Redux/Zustand/global stores without need. Tailwind CSS v4 and shared design conventions. Lightweight Charts for charts — no Recharts unless unsupported requirement.

## Accessibility / Testing Principles / Unit / Integration / Regression

Semantic HTML, keyboard support, visible focus, meaningful labels, appropriate contrast. Tests prove behavior, not trivia. Prioritize: domain correctness, determinism, integration, failure paths, restart/recovery, critical workflows. Unit tests for isolated deterministic behavior. Integration tests for important boundaries (bar→Strategy→TradeIntent→Risk→Order→Fill→Trade). Every meaningful bug fix adds regression test. External credential tests separate from deterministic suite. Name tests by behavior (test_long_trade_uses_ask_for_entry).

## Test Data / Formatting / Security / Performance

Small, explicit, deterministic fixtures. Crafted candles preferred over giant datasets for unit tests. Standard formatting/linting tooling. Never commit secrets. Validate input. Avoid exposing internal errors to users. Least privilege for broker credentials. Single-user Atlas does not require sandboxing Strategy code initially. Correctness first. Measure before optimizing. No caching, workers, specialized DBs, concurrency based on expected future scale.

## Refactoring / Review / Definition of Good Code

Refactor only when improving correctness, clarity, testability, or architecture compliance. Code review: correctness, deterministic semantics, safe failure, no duplication, no unnecessary abstraction, stays in active slice, testable end-to-end. Good Atlas code makes the trading path easy to follow: market data → Strategy → Risk → Order → Fill → Position/Trade — without navigating unnecessary frameworks or hidden control flow.

## Success Criteria

These standards are working when Atlas code remains simple enough to audit + strict enough to trust + organized enough for agents to extend + small enough to avoid premature architecture — while advancing the Golden Path one vertical slice at a time.
