# Strategy Contract

## Purpose

The Strategy Contract defines how trading strategies interact with Atlas. A Strategy describes trading methodology; it must remain independent of broker, account environment, database, API, runtime implementation, and Experiment/PAPER/LIVE mode. The same immutable StrategyVersion must be usable across Experiment → PAPER → LIVE without changing its trading logic.

## Core Principle

A Strategy answers: *Given the completed market information and my current state, what trading action do I want?* A Strategy does not answer: *How much capital should Atlas risk?* Capital allocation belongs to Risk.

## Canonical Evaluation

Conceptually: `evaluate(context: StrategyContext, state: StrategyState) -> StrategyDecision`. Exact syntax may vary; the boundary must preserve these semantics.

## StrategyContext

Contains only information the Strategy is allowed to know: evaluation time, Instrument, parameter values, required completed market data, current Position state, persisted Strategy state. Keep intentionally small.

## Evaluation Time

Time must be supplied by Atlas. A Strategy must never call wall-clock time directly. All internal trading time is UTC.

## Market Data

Strategies receive completed canonical Atlas market data. They must never: call OANDA, query historical storage, subscribe to market feeds, construct provider-specific requests. Atlas supplies the required completed bars.

## Completed Bars Only

Strategy evaluation must never receive a partially formed candle as a completed bar. For the reference Strategy (15m), evaluation occurs only after a 15-minute bar is finalized.

## Multi-Timeframe Data

A StrategyVersion may declare one primary evaluation timeframe and zero or more context timeframes. At evaluation, Atlas supplies only bars completed by the evaluation frontier. A Strategy must never access future context bars.

## Warm-Up

StrategyVersion declares its required warm-up history for indicator initialization and state establishment. During warm-up: Strategy may evaluate/update internal state, but new trading exposure is disabled. Must be validated by Atlas before execution.

## Parameters

Each Strategy defines a typed parameter schema (integer, decimal, boolean, enum/string where justified). Parameter values are runtime configuration; changing them does not create a new StrategyVersion.

## StrategyVersion

An immutable executable methodology. A new version required when executable behavior changes (entry/exit methodology, indicator logic, state-machine changes, source code changes affecting behavior). Historical versions must remain reproducible.

## Source Provenance

StrategyVersion should preserve: source fingerprint, creation timestamp, optional git commit SHA, Strategy identity, parameter schema, capability/timeframe/warm-up requirements. Do not build complex dependency-graph analysis initially.

## Strategy State

Strategies may maintain small persisted state that must be serializable, deterministic, version-compatible, Atlas-persisted. State must survive runtime restart. Examples: pending direction, reference candle levels, sweep timestamp, confirmation count, cooldown state.

## Invalid Strategy State

If persisted state cannot be loaded safely for the active StrategyVersion: new exposure → blocked. Do not silently reset meaningful trading state while a Deployment is active. The Deployment should fail or require explicit recovery.

## Forbidden Strategy State

Must not contain: database sessions, network clients, sockets, broker objects, open file handles, large DataFrames, runtime process references. Persist only what is necessary to reproduce decision state.

## Current Position / Account Information

StrategyContext may expose current Position (FLAT/LONG/SHORT). Strategy must not infer state from broker APIs. Must not receive account balance, equity, margin, risk settings, or portfolio exposure — these belong to Risk.

## StrategyDecision

Initial decisions: NO_ACTION, OPEN_LONG, OPEN_SHORT, CLOSE_POSITION, UPDATE_PROTECTION. Only implement behaviors required by active roadmap slices.

## Trade Intent

A trading StrategyDecision that changes exposure becomes a canonical TradeIntent containing action, Instrument, decision timestamp, proposed stop, target methodology/value, rationale, strategy context metadata. The Strategy does not submit Orders.

## Stop and Target

Strategies may define trade structure (stop price, target price/methodology). Atlas Risk validates safety and calculates quantity. Execution translates approved protection into venue-native instructions.

## Rationale

Strategies should provide concise deterministic rationale for actionable decisions captured at decision time rather than reconstructed later.

## Determinism

Given identical StrategyVersion + parameters + completed market data + evaluation time + Position + state, the Strategy must return the same result. Do not use arbitrary randomness. If randomness is introduced for research, it must be explicitly seeded outside the normal contract.

## External I/O

Strategy evaluation must not perform external I/O: HTTP, broker calls, database queries, filesystem reads/writes, subprocess execution, external service calls. This keeps behavior reproducible and testable.

## Environment Independence

Strategy code must not branch on BACKTEST/PAPER/LIVE. The environment should be invisible to Strategy methodology. Differences between historical and live execution belong to market-data, clock, account-state, and execution adapters.

## Strategy Registration

Atlas should support a documented registration/discovery mechanism. Keep registration explicit and understandable. Do not create a complex plugin framework.

## Validation

Before a StrategyVersion becomes usable, validate: metadata, parameter schema, timeframes, warm-up, state schema, contract conformance, source fingerprint. Invalid strategies should produce actionable validation errors without crashing unrelated workflows.

## Capabilities

A StrategyVersion may declare requirements (LONG, SHORT, STOP_LOSS, TAKE_PROFIT) used to validate Instrument, TradingAccount, broker capabilities, and Deployment compatibility.

## Reference Strategy

Current Strategy: EMA Sweep Confirmation Break v2, EUR/USD, native M15 MID. Exact methodology: [Reference Strategy](../features/reference-strategy.md). Generic infrastructure must not contain special cases for this Strategy.

## Required Tests

At minimum test: deterministic evaluation, parameter validation, completed-bar enforcement, no future data access, warm-up behavior, source fingerprint stability, new version after source change, parameter change without new version, serializable state, state restoration, invalid state handling, environment independence, rationale persistence, reference Strategy contract conformance.

## Success Criteria

Proven when same StrategyVersion can consume historical completed bars → generate deterministic TradeIntent AND consume live completed bars → generate the same methodology-driven TradeIntent — without Strategy code knowing Experiment vs PAPER vs LIVE.
