# Current Feature

Last updated: 2026-08-04

## Status

- [ ] Not started
- [x] In progress
- [ ] Complete

## Feature

- **Number:** 07
- **Name:** Execution Layer
- **File:** context/features/07-execution-layer.md

## Branch

- **Name:** feature/07-execution-layer
- **Created:** 2026-08-04

## Current session

### Context reconciliation (2026-08-04)

- [x] Applied approved Atlas context reconciliation per `dispatch/ARCHITECTURE.md`
- [x] Added Feature ID → roadmap phase table to `context/features/README.md`
- [x] Updated `context/architecture.md`: fee/slippage scope, order-type scope,
      partial-fill semantics, trigger ambiguity, unknown-order fail-closed policy,
      ratio-vs-money numeric rule
- [x] Updated `context/roadmap.md`: feature IDs on all phase headings, cross-links
      for split phases (03/08, 08/09/12), Phase 7 dependency on 06/07, Phase 10
      dependency on 09 data
- [x] Updated `context/project-brief.md`: added MVP realism scope (completed candles,
      no same-candle fills, fee/slippage defaults, no synthetic gaps)
- [x] Updated `context/database.md`: NUMERIC vs FLOAT metric column policy,
      data-retention policy
- [x] Updated `context/features/02-core-infrastructure.md`: reconciled checkbox status;
      health monitoring deferred to 13
- [x] Updated `context/features/04-strategy-engine.md`: added repeated-signal
      responsibility, no-future-data expectation, strategy version immutability
- [x] Updated `context/features/05-backtesting.md`: marked Phase 7, deferred metric
      formulas to 10, added lookahead/data-integrity gate, recorded execution
      assumptions
- [x] Updated `context/features/06-risk-engine.md`: removed stale SignalGenerated
      payload claim (already implemented by 04), clarified risk-only payload ownership,
      added reuse-by-backtesting section
- [x] Updated `context/features/07-execution-layer.md`: authoritative execution event
      payload status table, added approved fee/slippage/order-type/partial-fill/
      trigger-ambiguity/unknown-order policy
- [x] Updated `context/features/08-live-data-streaming.md`: changed examples to
      `Instrument`, distinguished feed health contract from 13 hardening,
      documented no synthetic gap candles
- [x] Updated `context/features/09-live-trading.md`: removed duplicate payload-gap
      section, added ownership boundaries, separated Phase 8 paper from Phase 11
      testnet, added strategy-version startup policy
- [x] Updated `context/features/10-journal-analytics.md`: canonical metric formulas
      with annualization, drawdown basis, undefined cases, open-trade policy
- [x] Updated `context/features/11-ui-dashboard.md`: added Feature 09 dependency,
      documented UI boundary (displays facts only)
- [x] Updated `context/features/12-bot-management.md`: added Feature 09 dependency,
      ownership boundaries (supervisor core in 02, pipeline construction in 09),
      migration policy
- [x] Updated `context/features/13-polish-testing.md`: health-monitor boundary,
      lookahead gate, reconciliation tests, endpoint safety gates
- [x] Updated `CURRENT.md`: corrected stale next-feature from "Feature 05 — Bot
      Supervisor" to "Feature 06 — Risk Engine"
- [x] No application source code, dependencies, migrations, or `.env` modified

### Documentation reconciliation (2026-08-04)

- [x] Reconciled `context/features/04-strategy-engine.md`:
  - Removed `candle_id` from `SignalGenerated` payload
  - Replaced `instrument: str` with `instrument_id: UUID` on Signal
  - Replaced `strength: float` with `strength: Decimal` on Signal
  - Added canonical `strategy_version_id: UUID` to Signal
  - Removed individual `strategy_name`/`strategy_version`/`strategy_commit_sha` duplication
  - Made `DataRequirement` timeframe-aware (Feature 04 supports one candle series)
  - Rewrote Strategy Engine to assemble immutable Signal from strategy decision,
    with engine-owned provenance, validation, deduplication, warm-up gating, and
    fail-closed error handling
  - Updated SMA Crossover example to use `StrategyDecision`, `Decimal`, UUID
  - Added warm-up/replay ownership, registry trust, parameter ownership,
    safety/validation semantics sections
  - Updated acceptance criteria to reflect agreed contracts
- [x] Updated `context/architecture.md`: expanded Strategy Engine section with
    Signal provenance, engine responsibilities, deployment trust, and fail-closed
    semantics; removed `strategy_version_id: UUID` from `SignalGenerated` event
    contract (canonical on Signal)
- [x] Updated `CURRENT.md` for Feature 04 planning/document reconciliation
- [x] No application source code, dependencies, migrations, or `.env` modified

### Task 2 — Strategy contracts and trusted registry (2026-08-04)

- [x] Implemented immutable strategy contracts with UUID, Decimal, UTC, and metadata validation
- [x] Implemented synchronous Strategy base contract and timeframe-aware data requirements
- [x] Implemented fail-closed trusted registry for explicitly deployed factories
- [x] Added focused contract and registry tests
- [x] Implemented per-bot StrategyEngine, warm-up gating, event payloads, and focused tests

### Task 4 — Example strategies (2026-08-04)

- [x] Implemented Decimal SMA crossover and Bollinger Bands examples with isolated state
- [x] Added focused behavior and configuration tests
- [x] Wrote `dispatch/feature04-examples-report.md`
- [x] Ruff, mypy, and pytest coverage clean (256 tests passed, Ruff clean, mypy clean)

### Contracts and registry quality fix (2026-08-04)

- [x] Replaced string-mixin enums with Python 3.12 `StrEnum` while preserving values
- [x] Typed metadata freezing/validation without weakening Decimal support or immutability
- [x] Updated registry `Callable` import to `collections.abc`

### Task 5 — Final documentation status (2026-08-04)

- [x] Fixed stale "same candle ID" wording → canonical composite key
- [x] Marked all implemented deliverables and acceptance criteria with [x]
- [x] Marked YAML config boundary as partially complete ([~]) — end-to-end wiring deferred
- [x] Updated "Done when" to reference orchestrator final validation gate
- [x] Updated `CURRENT.md` with completed slices and remaining validation state
- [x] No application source code, dependencies, migrations, or `.env` modified
- [x] Feature 04 final validation gate passed: 256 tests, Ruff clean, mypy clean

## What comes next

- **Next scheduled feature:** Feature 05 — Backtesting.

### Feature 07 — Contracts slice (2026-08-04)

- [x] Added immutable Order, Fill, Position, and Trade domain contracts with UUID,
      instrument_id, Decimal, UTC, and one-way Futures semantics.
- [x] Added broker-facing OrderResult, AccountInfo, BrokerSnapshot, and Broker protocols.
- [x] Added typed frozen keyword-only execution event payloads and focused tests.
- [x] No persistence, Binance connectivity, or execution engine implemented.

### Feature 07 — Persistence and paper broker slice (2026-08-04)

- [x] Started implementation of the PostgreSQL execution persistence boundary and
      Futures-aware Paper Broker.

### Feature 07 — Persistence and paper broker slice complete (2026-08-04)

- [x] Added migration 007 and SQLAlchemy execution models for orders, append-only fills,
      active one-way positions, and trade lifecycle aggregates.
- [x] Added UUID/NUMERIC repository protocols, SQLAlchemy implementation, and in-memory
      deterministic implementation with client, broker-order, and broker-execution idempotency.
- [x] Added isolated-margin Futures Paper Broker with 1x default/2x hard maximum leverage,
      configurable 0.05% taker fee, separate funding, executable bid/ask and backtest prices,
      mark-price P&L, protective triggers, maintenance margin, and non-negative liquidation.
- [x] Added focused Paper Broker tests.
- [x] Execution Engine and account-level net exposure coordinator remain deferred to the next
      Feature 07 slice.
- [x] Backend pytest: 300 passed
- [x] Ruff: clean
- [x] mypy: clean

### Feature 07 — Net exposure coordinator and RiskApproved integration (2026-08-04)

- [x] Added account/instrument serialization, strategy-keyed virtual exposures, deterministic
      net target/delta calculation, explicit close-before-reversal, and FIFO allocation helper.
- [x] Added ExecutionEngine RiskApproved subscription with durable client IDs before broker I/O,
      persistence-before-event ordering, provenance propagation, duplicate-fill handling,
      partial-fill handling, and unknown-state blocking.
- [x] Reconciled Feature 06's former instrument-wide conflict rule to the approved
      cross-strategy policy while retaining same-strategy no-scaling behavior.
- [x] Added multi-strategy netting and reversal integration coverage.
- [x] Added strategy-aware reservation tests, typed execution fixtures, coordinator idempotency/
      FIFO/event coverage, and cumulative trade fee/P&L updates for partial fills.
- [x] Focused validation: 57 passed; full backend suite: 308 passed; slice Ruff/mypy clean.

### Slice 2 review fixes (2026-08-04)

- [x] Fully annotated Paper Broker test helpers and async test signatures.
- [x] Reconciled execution schema documentation with migration 007/ORM, including
      NUMERIC(28, 12) precision and idempotency indexes.
- [x] Added accumulation, weighted-average, partial/full close, protective trigger,
      liquidation, re-marking, and repository-backed persistence/idempotency coverage.
- [x] Validation: 304 pytest passed; Ruff and mypy clean.

### Feature 06 final validation (2026-08-04)

- [x] Implemented typed risk events, YAML risk configuration, and the pure RiskEngine plus
      EventBus adapter with isolated transient reservations.
- [x] Added event, configuration, and comprehensive risk-engine behavior tests.
- [x] Backend pytest: 266 passed
- [x] Ruff: clean
- [x] mypy: clean

### Feature 07 — Reconciliation and recovery slice (2026-08-04)

- [x] Implemented broker-snapshot reconciliation behind broker/repository/coordinator protocols
- [x] Added authoritative order, fill, and position comparison with provenance preservation,
      unknown-order recovery, fill idempotency, durable reconciliation records, and fail-closed
      coordinator blocking/unblocking
- [x] Added startup, reconnect, periodic invocation methods and matching, missing-state,
      mismatch, duplicate-execution, unblock, and restart-recovery tests

### Feature 07 — Reconciliation review fixes (2026-08-04)

- [x] Paper Broker reconciliation now returns its complete order/fill ledger plus positions
- [x] Added real Paper Broker regression coverage, missing-local-fill recovery, orphan-position
      closure, mode-scoped fills, lifecycle entry points, bot/account scope, and coordinator
      blocking tests
- [x] Reconciliation test helpers are fully typed; changed-slice mypy is clean
- [x] Validation: 322 pytest passed; Ruff clean; mypy clean

### Feature 07 — Final validation gate (2026-08-04)

- [x] Whole-feature review passed with zero Critical or Important findings
- [x] Backend pytest: 322 passed
- [x] Ruff: clean
- [x] Feature 07 source, tests, and migration mypy: clean
- [x] Feature 07 complete; next scheduled feature is Feature 05 — Backtesting
