# Product Principles

## Strategy First

The Strategy lifecycle is the organizing principle of Atlas. Features should make it easier to Build → Test → Deploy → Monitor → Improve. Do not allow secondary infrastructure or tooling to become the product.

## Same Methodology Everywhere

One StrategyVersion moves through Experiment → PAPER → LIVE without changing methodology. Environment-specific behavior belongs outside Strategy logic.

## Reliability Over Features

Small correct feature set > broad untrustworthy platform. Prioritize correct execution, deterministic simulation, reliable recovery, clear failure states.

## Simplicity Over Complexity

Simplest architecture that safely satisfies current requirements. No infrastructure for hypothetical scale. Prefer direct calls, PostgreSQL, one runtime, focused adapters over distributed systems unless demonstrated need.

## Build Proof, Not Infrastructure

Each roadmap phase proves a real user capability. No speculative implementation. Future needs may influence boundaries but must not create premature code.

## Deterministic and Explainable

Trading behavior reproducible and inspectable. The trader should understand why the Strategy acted, why Risk approved/rejected, how execution occurred, what assumptions affected an Experiment, why a Deployment stopped/failed. Avoid hidden behavior.

## Explicit Failure

Surface uncertainty rather than pretending everything is healthy. State untrusted → new exposure blocked. Do not hide failures behind silent retries or generic error messages.

## Human Oversight

Trader remains responsible for activating/supervising automated trading. Strong automation without obscuring current exposure, account environment, Risk status, Deployment state, critical failures.

## Broker Agnostic

Core concepts independent of OANDA-specific models. OANDA is first integration. Future providers through explicit adapter boundaries. Do not build generic plugin platform before a second real integration exists.

## Market Agnostic, Market Aware

Reuse common concepts where safe. But Forex, crypto, and future markets differ in calendars, fees, financing, margin, execution, data structure. Do not force market-specific economics into false universal abstraction.

## Canonical Domain Language

One set of domain concepts consistently: StrategyVersion, Experiment, Deployment, TradeIntent, RiskDecision, Order, Fill, Position, Trade. No parallel models for different environments.

## Risk Is Centralized

Strategy defines trade structure; Atlas Risk decides capital commitment. Strategy must never bypass Risk.

## Broker Truth Wins

For PAPER/LIVE: broker truth > stale Atlas projection. Reconcile after uncertainty before increasing exposure.

## Protect Existing Exposure

When degraded: preserve protection → prevent unintended new exposure → establish authoritative state → resume safely. Risk-reducing actions remain possible where safe.

## Completed Data Only

Strategies act on completed market information. No future or partially formed data. Historical and live candle semantics aligned.

## Immutable Evidence

Important research/trading provenance historically trustworthy: StrategyVersion, DatasetSnapshot, completed Experiment, Fill, Trade history. Do not silently rewrite history.

## Opinionated Constraints

v1 intentionally restricts: one Instrument per Deployment, one Position per Deployment, one active Deployment per TradingAccount+Instrument, no pyramiding, no partial exits, no instant reversal. Constraints relaxed only when real requirements justify complexity.

## Workstation, Not Generic SaaS

Interface optimizes for trading decisions: compact tables, clear statuses, useful charts, strong hierarchy. Avoid oversized cards, excessive whitespace, infrastructure terminology, generic SaaS visuals.

## PAPER Must Resemble LIVE

PAPER proves LIVE behavior. No simplified paper-only execution that bypasses production trading path.

## Measure Before Optimizing

Implement correctly → measure → identify bottleneck → optimize. No caching, specialized storage, concurrency, or workers based on future expectations only.

## Documentation Should Reduce Ambiguity

Define meaningful decisions once, link to authoritative source. Do not duplicate rules across every feature file. Documentation exists to prevent agents from improvising architecture — not to maximize document volume.

## Final Principle

Between more architecture and a smaller trustworthy path from Strategy to protected Trade: choose the trustworthy path.
