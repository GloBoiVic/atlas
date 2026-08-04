# Feature 04 Documentation Reconciliation — Report

**Date:** 2026-08-04
**Branch:** feature/04-strategy-engine
**Task:** dispatch/feature04-doc-reconciliation.md

---

## Files Modified

### 1. `context/features/04-strategy-engine.md`

| Change | Description |
|--------|-------------|
| `candle_id` removed from `SignalGenerated` | SignalGenerated payload now carries only `signal: Signal`; no duplicate candle identity |
| `instrument: str` → `instrument_id: UUID` | Signal uses UUID instrument identity consistently |
| `strength: float` → `strength: Decimal` | Signal strength uses Decimal domain convention |
| Canonical `strategy_version_id: UUID` added to Signal | Single source of truth for strategy version; replaces scattered `strategy_name`/`strategy_version`/`strategy_commit_sha` |
| Engine rewritten to assemble immutable Signal | Engine owns provenance assembly from lightweight `StrategyDecision` returned by strategy; no mutation of frozen Signal |
| `DataRequirement` made timeframe-aware | `DataRequirement.data_type` + `timeframe`; Feature 04 validates one candle series |
| SMA Crossover example updated | Returns `StrategyDecision` with Decimal strength and Decimal metadata values; uses no empty identity strings |
| Warm-up/replay ownership added | Engine owns warm-up lifecycle and signal gating; replay layer sources candles |
| Registry trust section added | Registry resolves only deployed, version-pinned packages; fails closed on mismatch |
| Parameter ownership section added | Package owns schema/defaults; bot/backtest owns YAML values; validated, frozen, and recorded |
| Safety/validation sections added | Completed-candle validation, duplicate rejection, fail-closed strategy errors, no I/O |
| Acceptance criteria updated | 13 criteria matching agreed contracts |

### 2. `context/architecture.md`

| Change | Description |
|--------|-------------|
| Strategy Engine section expanded | Signal provenance (engine assembles from decision), UUID/Decimal contracts, timeframe-aware DataRequirement, warm-up gating, fail-closed behavior |
| Deployment trust added | Registry trust, parameter ownership, fail-closed on mismatch |
| `SignalGenerated` event contract updated | `strategy_version_id: UUID` removed from event level (canonical on Signal) |

### 3. `CURRENT.md`

| Change | Description |
|--------|-------------|
| Feature number/name updated | 04 — Strategy Engine — documentation reconciliation |
| Branch updated | feature/04-strategy-engine |
| Status set to In progress | Documentation reconciliation checked; implementation deliverables not claimed |
| Previous Feature 03 content replaced | Preserved nothing from Feature 03 (separate branch/feature) |

---

## Verification Results

### Stale contract search

| Pattern | Feature 04 docs | Unrelated files | Verdict |
|---------|----------------|-----------------|---------|
| `candle_id` (as field on SignalGenerated or Signal) | ✅ Not present (composite key `_seen_candle_keys` for dedup + explicit "no candle_id" statement) | Present in feature 08 (unrelated) | **Clean** |
| `instrument: str` | ✅ Not present (uses `instrument_id: UUID`) | Present in feature 08 and coding-standards (unrelated) | **Clean** |
| `strength: float` | ✅ Not present (uses `strength: Decimal`) | Not present anywhere | **Clean** |

### Consistency checks

- ✅ Signal is immutable (frozen dataclass) — engine assembles it, never mutates
- ✅ `strategy_version_id` is canonical on Signal, not duplicated on SignalGenerated
- ✅ Registry resolves only deployed/pinned packages — no API-supplied imports
- ✅ Parameters owned by package schema + bot YAML values — recorded together
- ✅ Warm-up owned by engine; replay sourcing owned by feed layer
- ✅ Engine validates candle instrument, timeframe, completeness; rejects duplicates using canonical composite key
- ✅ Strategy exceptions fail closed (no signal, StrategyError, bot paused)
- ✅ Tick observation deferred — no tick-signal generation
- ✅ Decimal/UUID conventions consistent with Atlas standards
- ✅ No speculative implementation detail or scope creep

---

## Fix Verification (2026-08-04)

Reviewer finding: `Candle` domain model has no `.id` attribute. The documented deduplication used
`event.candle.id` with `set[UUID]`, which does not exist on the `Candle` dataclass.

**Fix applied:**

| Before | After |
|--------|-------|
| `self._seen_candle_ids: set[UUID]` | `self._seen_candle_keys: set[tuple]` |
| `event.candle.id` lookup | `self._candle_key(candle)` returning `(instrument_id, provider, timeframe, open_time, price_basis)` |
| No `is_complete` validation before strategy evaluation | Explicit `if not candle.is_complete: return` guard |
| No `timeframe` validation before strategy evaluation | Explicit `if candle.timeframe != self._data_requirement.timeframe: return` guard |
| Inline dedup key scattered across guards | `_candle_key()` static method matches the database `UNIQUE(instrument_id, provider, timeframe, open_time, price_basis)` constraint |

The composite key `(instrument_id, provider, timeframe, open_time, price_basis)` is the
canonical uniqueness constraint already used by Feature 08 and the Feature 03 candle
repository — consistent with the database schema and the domain `Candle` model.

The timeframe and `is_complete` guards now match the stated contract before strategy
evaluation: "The engine accepts only completed candles matching the bot's instrument
and timeframe."

---

## Summary

All required changes from `dispatch/feature04-doc-reconciliation.md` and the subsequent
reviewer findings have been applied:

1. ✅ `context/features/04-strategy-engine.md` reconciled — stale contracts removed, agreed contracts documented
2. ✅ `context/architecture.md` updated — strategy engine boundary and Signal provenance authoritative
3. ✅ `CURRENT.md` updated — Feature 04 planning/document reconciliation in progress
4. ✅ No application source, dependencies, migrations, or `.env` modified
5. ✅ All stale contracts (`candle_id`, `instrument: str`, `strength: float`) verified absent
6. ✅ `Candle` deduplication corrected to composite key `(instrument_id, provider, timeframe, open_time, price_basis)`
7. ✅ `timeframe` and `is_complete` validation explicitly documented before strategy evaluation
8. ✅ Documentation aligned with single-user, paper-first, broker-agnostic, Decimal/UUID, fail-closed goals
