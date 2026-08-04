# Current Feature

Last updated: 2026-08-04

## Status

- [ ] Not started
- [x] In progress
- [ ] Complete

## Feature

- **Number:** 04
- **Name:** Strategy Engine — documentation reconciliation
- **File:** context/features/04-strategy-engine.md

## Branch

- **Name:** feature/04-strategy-engine
- **Created:** 2026-08-04

## Current session

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
- [ ] Feature 04 not complete until orchestrator final validation gate passes

## What comes next

- **Feature 04 final validation:** orchestrator must pass the final validation gate
  (Ruff, mypy, full `pytest` suite pass in the development environment)
- **Feature 05 — Bot Supervisor:** end-to-end wiring of YAML config → registry →
  engine constructor, bot lifecycle, pipeline isolation
