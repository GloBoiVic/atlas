# Atlas Roadmap

## Purpose

Atlas is built through narrow vertical slices. Each phase must prove one real capability before the next phase begins. The roadmap is governed by one rule: do not build future infrastructure before the current workflow works end to end.

The Golden Path: Historical EUR/USD → deterministic 15m bars → EMA Sweep Engulfing → deterministic Experiment → trustworthy results → OANDA Practice → same StrategyVersion → PAPER TradeIntent → Risk → Order → Fill → protected Position → restart → reconciliation → safe resume.

## Phase 0 — Project Foundation

**Goal**: Smallest correct Atlas application skeleton. **Build**: Next.js, FastAPI, PostgreSQL, SQLAlchemy/Alembic, atlas-runtime entry point, config, testing foundations, repository structure. **Do Not Build**: Strategy engine, OANDA trading, Experiment engine, reconciliation, WebSocket infra unless required, Redis/Celery/Docker orchestration. **Exit**: frontend starts, API starts, runtime starts, migration works, tests run, repo boundaries match context.

## Phase 1 — Reference Strategy

**Goal**: Prove Atlas can load and deterministically evaluate one real Python Strategy. **Build**: Strategy, immutable StrategyVersion, contract, parameter schema, state, source fingerprinting, EMA Sweep Engulfing. **Do Not Build**: broker execution, account Risk sizing, Experiment UI, plugin framework, multiple Strategies. **Exit**: Reference Strategy deterministically produces correct long/short/no-action/state-transition/expiry behavior from crafted completed bars.

## Phase 2 — Historical EUR/USD Data

**Goal**: Trustworthy historical data for reference Strategy. **Build**: Instrument, VenueInstrument, OANDA adapter, EUR/USD 1m ingestion, MID/BID/ASK normalization, PostgreSQL persistence, coverage/gap detection, DatasetSnapshot, deterministic 1m→15m aggregation. **Do Not Build**: live streaming, multiple providers, crypto, derived timeframe persistence, specialized time-series DB. **Exit**: Load EUR/USD 1m data without duplicates, validate coverage, detect gaps, derive identical 15m bars, create DatasetSnapshot.

## Phase 3 — First Historical Trade

**Goal**: Prove canonical trading pipeline with one deterministic simulated Trade. **Build**: Experiment, SimulationClock, simulated account, TradeIntent, RiskDecision, SimulatedExecutionAdapter, Order, Fill, Position, Trade. Risk: risk-per-trade sizing, valid stop geometry, no existing Position, valid quantity. **Do Not Build**: daily-loss engine, drawdown blocking, complex margin, OrderEvent UI, reconciliation, PAPER trading. **Exit**: Deterministic long + short Trade through complete pipeline (15m Bar → Strategy → TradeIntent → RiskDecision → Order → Fill → Position → Trade).

## Phase 4 — Trustworthy Experiments

**Goal**: Turn working simulation into credible Experiment engine. **Build**: requested period, warm-up, 1m simulation frontier, no-lookahead, BID/ASK execution, spread, slippage, stop/target execution, gap-through stops, adverse-first intrabar ambiguity, equity history, costs, end-of-Experiment handling, reproducibility tests. **Do Not Build**: optimization, parallel workers, analytics framework, distributed job queue. **Exit**: Identical inputs produce identical Trades, Fills, P&L, equity, metrics. No signal bar data reused as post-decision execution data.

## Phase 5 — Experiment Workflow

**Goal**: Run and inspect trustworthy Experiment from UI. **Build**: Experiment config, coverage validation, run action, status, detail/headline metrics, equity/drawdown chart, Trade list/detail, assumptions/provenance. **Do Not Build**: dozens of secondary metrics, report exports, optimization, research notebooks, generic charting terminal. **Exit**: Trader answers: Did it work? How risky? What Trades? Why specific Trade? What data/assumptions?

## Phase 6 — Strategy Iteration

**Goal**: Manual hypothesis testing via parameter variation. **Build**: Experiments with different parameter values, StrategyVersion history, simple Experiment comparison (parameters, core metrics). **Do Not Build**: automated/grid/Bayesian/genetic optimization, walk-forward, ranking, recommendations. **Exit**: Compare multiple immutable Experiments' config and risk/performance.

## Phase 7 — OANDA Practice Account

**Goal**: Connect Atlas safely to external PAPER account. **Build**: TradingAccount, OANDA Practice config, credential handling, connection validation, account state normalization, EUR/USD venue mapping, capability checks. **Do Not Build**: OANDA Live, multiple brokers, account switching, institutional management, crypto. **Exit**: Connect to OANDA Practice, read normalized account/EUR/USD/Order/Position state. No automated Strategy Order submitted.

## Phase 8 — Live Market Data + PAPER Deployment

**Goal**: Run same StrategyVersion against live completed EUR/USD candles. **Build**: Deployment, desired/actual state, runtime ownership, OANDA live pricing, 1m normalization, deterministic 15m bars, warm-up, Strategy-state persistence, duplicate-evaluation protection, START/PAUSE/RESUME/STOP basics. **Do Not Build**: automated Order submission, complex supervisor, multiple runtimes, Redis command bus, full WebSocket, LIVE account. **Exit**: Same StrategyVersion runs under atlas-runtime, evaluates each live 15m bar exactly once.

## Phase 9 — First PAPER Trade

**Goal**: First real automated OANDA Practice Trade (primary MVP milestone). **Build**: PRE_FLIGHT/PRE_SUBMISSION Risk, position sizing, OANDA execution adapter, canonical Order, stable client correlation, idempotent submission, broker response normalization, Fill processing, Position/Trade lifecycle, broker-hosted stop + target. **Do Not Build**: OANDA Live, multiple Instruments, pyramiding, partial exits, trailing stops, generalized framework, distributed workers. **Exit**: Completed live bar → Strategy → TradeIntent → Risk → OANDA Order → Fill → Position → broker-hosted stop + target → closed Trade — same StrategyVersion as Experiments.

## Phase 10 — Recovery and Reconciliation

**Goal**: Fail and recover safely. **Build**: startup reconciliation, submission-timeout recovery, UNKNOWN Order handling, missed Fill recovery, Position mismatch detection, unexpected broker exposure, protection verification, runtime heartbeat/ownership, restart recovery, stale market-data handling. Required scenarios: runtime restart, broker disconnect, request timeout, unknown Order, missed Fill, Position mismatch, missing protection, Strategy exception, stale data. **Do Not Build**: generalized incident management, distributed failover, complex supervisor, auto-remediation for ambiguous exposure. **Exit**: Restart after PAPER activity, establish broker truth, avoid duplicate exposure, resume only when state known and safe.

## Phase 11 — Daily Trading Workstation

**Goal**: Routine monitoring and review. **Build**: Dashboard (account equity, today's P&L, Position, Deployment, health, recent activity/Trades). Journal (Trade list/detail/chart, rationale, execution lineage, notes/tags). **Do Not Build**: institutional portfolio dashboard, system health widgets, unrelated analytics, social features, export/reporting. **Exit**: Trader quickly answers: What is Atlas doing? Exposure? Safe? Recent Trades? Why specific Trade?

## Phase 12 — OANDA Live

**Goal**: Move proven PAPER lifecycle to real capital. **Build**: OANDA Live TradingAccount, LIVE config/activation/LIVE visual/LIVE reconciliation. **Do Not Build**: separate LiveStrategy/Risk/Execution. Exit: Same StrategyVersion moves Experiment → OANDA Practice → OANDA Live without methodology code changes.

## Phase 13+ — Forex Hardening / Crypto Derivatives

**Phase 13**: Forex hardening — additional Instruments, currency conversion, financing, broader calendars, stability, larger datasets, performance. One requirement at a time. **Phase 14**: Design for crypto derivatives — define venue/API/margin/leverage/funding/etc. before implementation. **Phase 15**: Proof with existing Atlas concepts. Reuse Strategy, Experiment, Risk, Order, Fill, Position, Trade, Journal, runtime.

## Deferred (not part of initial build)

crypto spot, futures, equities, options, multi-instrument Strategies, pyramiding, partial exits, instant reversal, portfolio netting, automated optimization, AI strategy generation, social/copy trading, multi-user SaaS, mobile-first, HFT, tick replay, distributed runtime, Kubernetes, plugin framework.

## Golden Path Checklist

Project boots → EMA Sweep Engulfing evaluates bars → EUR/USD loads without duplicates → 15m bars produced → long + short historical Trades → identical Experiment reproduces → results inspectable → OANDA Practice connects → live bars produced → same StrategyVersion evaluates → PAPER TradeIntent → Risk approves → OANDA Order → Fill → Position → stop+target confirmed → Trade closes → Journal shows it → runtime restarts → broker reconciles → Deployment resumes safely.

## Advancement Rule / Completion Rule

Do not begin later phase because supporting interfaces exist. Advance only when current phase exit criterion works end to end. The question is never "How much code exists?" but "How much of the Golden Path can Atlas prove and trust?"
