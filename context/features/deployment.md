# Deployments

## Purpose

A Deployment runs one immutable StrategyVersion against one Instrument and one TradingAccount in PAPER or LIVE. Initial: EMA Sweep Engulfing, EUR/USD, OANDA Practice, PAPER. A Deployment is persistent trading configuration — not a Bot, Worker, or runtime process.

## Core Model

References: StrategyVersion, Instrument, TradingAccount, parameter snapshot, Risk snapshot, desired state, actual state, persisted Strategy state. Canonical: [Domain Model](../architecture/domain-model.md). Runtime: [Runtime Model](../architecture/runtime-model.md).

## One Instrument / Ownership Invariant

v1: 1 Deployment → 1 Instrument. Multi-instrument deferred. At most one active Deployment per TradingAccount+Instrument. Enforce transactionally.

## Configuration / Compatibility Checks

Creating requires: StrategyVersion, TradingAccount, Instrument, parameter values, Risk config. Validate before START: StrategyVersion usable, Instrument mapped, account reachable, mode known, broker capabilities exist, parameters valid, Risk config valid, no conflicting active Deployment, compatible Strategy state. Failure blocks activation.

## Configuration Immutability / Desired vs Actual

DRAFT editable. Once traded: no silent changes to StrategyVersion, Instrument, TradingAccount, parameters, Risk config — clone instead. Desired state ≠ actual runtime state. User presses Start → desired=RUNNING → runtime validates/reconciles/warms → actual=RUNNING. UI must not report success before safe transition.

## Canonical States

Actual states: DRAFT (configured, never activated, editable, no runtime ownership), STOPPED, STARTING (runtime-facing transitional if useful), RUNNING (data received, bar evaluated once per completed bar, state persisted, TradeIntents→Risk→Orders→Fills), PAUSED (block new entries, preserve protection/market data/risk-reducing), RESUME (fresh broker check + reconciliation + data freshness + state validation before RUNNING), STOP (allowed only when FLAT — blocked if exposure exists), FAILED (exposure blocked, reason persisted, broker protection intact), RECONCILIATION_REQUIRED (cannot prove local state against broker truth — exposure blocked), ARCHIVED (for historical provenance; cannot activate). Prefer archival over deletion once trading history exists.

## Runtime Ownership / Single Runtime

atlas-runtime owns active execution. Browser/Next.js do not — closing browser must not stop trading. API records commands; runtime performs transitions. v1: one atlas-runtime instance. Prevent multiple instances controlling same Deployment via simple PostgreSQL lock. No distributed leader election.

## Market Data / Duplicate Evaluation Protection

RUNNING Deployment receives canonical data: OANDA EUR/USD → 1m → 15m MID → Strategy. Only completed bars trigger evaluation. Duplicate evaluation protection: persist enough state (last processed/evaluated bar) to prevent same bar from causing duplicate TradeIntent after restart. Trading correctness invariant.

## Warm-Up / Strategy State / Catch-Up

Before new exposure: required history loaded, indicators initialized (100 EMA, 14 ATR for reference). No exposure created during warm-up; with exposure disallowed the Strategy returns NO_ACTION, remains SEARCHING with all pending setup fields cleared, and neither selects a reference nor creates or advances a setup. Persist Strategy state (direction, reference levels, sweep_time, window-candle count since reference selection, last evaluated bar end). State must survive restart — no reliance on process memory. After downtime: process missed bars chronologically to reconstruct state. Replaying bars ≠ submitting stale entries. Catch-up may update state but must not blindly execute stale entry opportunities.

## Position Rule / PAPER vs LIVE / LIVE Activation

0 or 1 Position. No pyramiding, partial exits, simultaneous long+short, instant reversal. Deployment mode from TradingAccount. PAPER/LIVE share same Strategy contract, Risk logic, trading model, runtime flow. No PaperDeploymentEngine/LiveDeploymentEngine. LIVE deferred until PAPER proven; when implemented requires explicit confirmation — no auto-promotion.

## Commands / Runtime Health / UI

START, PAUSE, RESUME, STOP, ARCHIVE. Idempotent where reasonable. Deployment Detail: StrategyVersion, Instrument, TradingAccount, PAPER/LIVE, parameters, Risk config, actual state, desired state (pending), Position, recent meaningful activity, persistent failure/safety state. Healthy infrastructure understated; unsafe prominent. Simple UI for initial scope: name, PAPER, status, EUR/USD, OANDA Practice, Risk, Position, [Pause] [Stop]. No institutional grid.

## Activity / Error UX

Meaningful events: started, setup activated, TradeIntent created, Risk approved, Order filled, Position closed, paused, Reconciliation required. No heartbeats or polling cycles. Failed state explains: what happened, what Atlas did, exposure blocked? exposure protected? action required? Follow [Safety Model](../architecture/safety-model.md).

## Non-Goals

No Bot model, BotSupervisor, worker-per-Deployment, container-per-Deployment, multiple runtimes, distributed coordination, Redis command bus, multiple Instruments per Deployment, scheduling calendar, automatic failover, LIVE before PAPER proven.

## Required Tests

Valid creation, invalid rejection, TradingAccount+Instrument uniqueness, desired vs actual, idempotent START, runtime ownership, duplicate ownership blocked, warm-up before exposure, one evaluation per bar, last-evaluated bar persisted, Strategy state persistence, restart restoration, PAUSE blocks new entries/preserves safe management, RESUME requires reconciliation/freshness, STOP while flat, STOP blocked with Position, FAILED blocks exposure, RECONCILIATION_REQUIRED blocks exposure, catch-up does not execute stale entry, PAPER uses same StrategyVersion as Experiment.

## Acceptance Flow

Create deployment (EMA v1, OANDA Practice, EUR/USD, Risk config) → START → runtime validates → broker reconciled → warm-up loaded → data healthy → RUNNING → bars processed → Strategy evaluated once per bar → state persisted → PAUSE/RESUME safely → restart → state restored without duplicate evaluation.

## Success Criteria

Trader safely runs same StrategyVersion as Experiments against live OANDA Practice market data, with persistent state, correct completed-bar evaluation, clear START/PAUSE/RESUME/STOP behavior — without Bot or supervisor architecture.
