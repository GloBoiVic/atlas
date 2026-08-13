# AGENTS.md

## Atlas

Atlas is a single-user algorithmic trading platform for moving a trading hypothesis through Strategy → Experiment → PAPER → LIVE. Prioritizes: trading correctness, reproducibility, capital safety, simplicity, auditability. Do not optimize for hypothetical scale.

## Current Scope

**Initial vertical slice:** Instrument: EUR/USD | Broker: OANDA | Account: OANDA Practice | Base Currency: USD | Strategy Timeframe: 15m | Historical Base Resolution: 1m | Strategy: EMA Sweep Engulfing. Build this correctly before generalizing.

## Architecture Principle

Atlas is intentionally simple. Primary applications: Next.js web, FastAPI API, atlas-runtime, PostgreSQL. Avoid: microservices, Redis, message brokers, distributed workers, Bot/Supervisor abstractions, container-per-process, speculative plugin frameworks. Docker is not an architectural requirement.

## Domain Language

Use canonical Atlas terminology. Prefer: Strategy, StrategyVersion, Experiment, DatasetSnapshot, TradingAccount, Deployment, TradeIntent, RiskDecision, Order, Fill, Position, Trade. Do not introduce: Bot, BacktestRun, BacktestResult, PaperBot, LiveBot, StrategyInstance. A historical backtest is an Experiment. Domain definitions: `context/architecture/domain-model.md`.

## Core Invariants

Never violate: StrategyVersion is immutable. Completed Experiment inputs/results are immutable. Strategy does not own Risk; Risk is centralized. Position state derives from Fills. Broker truth wins in PAPER/LIVE. Unknown financial state blocks new exposure. Only completed candles trigger decisions. No lookahead. Same completed bar never evaluated twice. Order submission must be retry-safe. Open PAPER/LIVE exposure must use broker-hosted protection. Reconciliation before resuming after uncertain state. PAPER/LIVE share Strategy/Risk/domain boundaries. Raw UUIDs are not normal UI labels.

## Context Hierarchy

Read only relevant files. **Product:** `context/product/`, `context/roadmap/`. **Architecture:** `context/architecture/` — owners: `domain-model.md` (language/invariants), `strategy-contract.md` (Strategy boundary), `market-data-model.md` (candle semantics), `accounting-model.md` (financial rules), `runtime-model.md` (runtime execution), `safety-model.md` (fail-closed rules). Architecture documents govern cross-feature semantics. **Features:** `context/features/` — load only the feature being implemented (reference-strategy, historical-data, experiments, experiment-results, experiment-comparison, trading-accounts, deployment, risk-management, execution, reconciliation, dashboard, journal). **Design:** `context/design/design.md` then screenshots. Written specs govern; screenshots are visual references. **Engineering:** `context/development/`.

## Source Precedence

1. explicit current task | 2. architecture invariants | 3. feature specification | 4. product/roadmap scope | 5. design specification | 6. screenshot/mockup | 7. existing implementation. Existing code is not automatically correct. Surface contradictions; do not invent resolutions.

## Implementation Workflow

Identify slice → read AGENTS.md → load relevant context → inspect existing code → identify affected contracts → smallest plan → implement → test behavior + failure paths → report changes. Prefer complete vertical slices over horizontal infrastructure. Bad: generic event/broker/Strategy/worker frameworks before a Trade exists. Good: historical EUR/USD → Strategy → TradeIntent → RiskDecision → Order → Fill → Trade → result.

## Simplicity Rule

Narrowest correct abstraction for current requirements. Do not generalize for future brokers, Instruments, Strategies, users, or distributed execution. Ask: does the current slice require this? If not, do not add it.

## Trading Safety

Correctness over convenience. Unknown financial state → block new exposure. Never silently: fabricate market data, assume Order outcome, invent exit price, retry uncertain entry, repair ambiguous state, resume before reconciliation, leave exposure unprotected. Safety failures must be persistent and inspectable.

## Strategy Boundary

`context/architecture/strategy-contract.md`. Strategy determines setup/direction/stop proposal/target methodology/rationale. Must not: access broker APIs, account balance, size Risk, submit Orders, query databases, contain UI. Reference Strategy gets no special infrastructure.

## Experiments / PAPER / LIVE

Use Experiment (not Backtest). Experiments must be deterministic, reproducible, no-lookahead, based on immutable StrategyVersion + DatasetSnapshot. OANDA Practice = PAPER. Do not implement LIVE until PAPER lifecycle is proven. PAPER proves real broker interaction, execution, protection, restart, reconciliation, operational safety — not fake execution.

## UI

Horizontal navigation (no sidebar). Design: quiet, focused, spacious, trader-oriented. Use: shadcn/ui, Sonner (transient feedback only), TradingView Lightweight Charts. Persistent safety conditions belong in persistent UI, not toasts.

## Dependencies / External APIs / Database

Before adding a dependency: confirm stack cannot solve it, verify maintenance, consult current docs, add only what feature requires. For OANDA: isolate behind adapter, normalize to Atlas types, preserve external IDs for reconciliation, never leak credentials, handle timeout/unknown explicitly. PostgreSQL is durable truth; use constraints for invariants; avoid additional persistence without measured need.

## Testing

Prioritize: domain invariants, Strategy behavior, no-lookahead, Risk calculations, execution semantics, idempotency, restart/reconciliation, failure paths, critical workflows. Small deterministic fixtures. External credential tests separate. Do not chase coverage percentage.

## Failure Handling

Failures must answer: What happened? What did Atlas do? Is new exposure blocked? Is existing exposure protected? What should happen next? Never hide failures behind logs alone. Do not convert unknown state into false certainty.

## Code Quality / Scope / Completion

Prefer: explicit, typed, small modules, deterministic, boring infrastructure. Avoid: premature abstraction, deep inheritance, speculative factories, hidden side effects, cleverness obscuring trading logic. Do not implement adjacent features unless required. Before declaring done: behavior works, tests pass, failure paths handled, invariants intact, UI matches scope, no unnecessary architecture, docs updated.

## Guiding Question

What is the simplest implementation that moves Atlas toward a trustworthy Strategy → Experiment → PAPER → LIVE lifecycle without compromising trading correctness? Build that.
