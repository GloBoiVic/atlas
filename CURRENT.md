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

## What comes next

- Implementation of strategy contracts, base class, engine, registry, and examples
