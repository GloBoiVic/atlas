# Memory — Feature 06 Risk Engine

Last updated: 2026-08-04

## What was built

### Feature 06 — Risk Engine (this session)

- Implemented the deterministic Risk Engine on branch `feature/06-risk-engine`.
- Created `backend/risk/engine.py` (398 lines) — `RiskEngine`, `RiskContext`, `PositionInfo`, `PositionStatus`, `RiskContextProvider` protocol, configuration-driven stop resolution, conservative tick/step rounding, equity-constrained sizing, max-open positions with transient reservations, per-bot isolation via bot_id filtering, CLOSE zero-quantity approval, and direction-conflict rejection (no scaling/reversal).
- Added `RiskApproved`/`RiskRejected` typed event payloads to `backend/core/events.py` — `signal`, `position_size`, `stop_loss`, `take_profit` for approval; `signal`, `reason` for rejection.
- Extended `RiskConfig` in `backend/config.py` with `stop_loss_multiplier`, `take_profit_multiplier`, `stop_source_config`, `take_profit_risk_reward`, `max_risk_per_trade`, and YAML-friendly source discriminator.
- Updated `config/default.yaml` with full risk section: `max_open_positions: 5`, `per_trade_risk: 0.01`, `stop_source`, `stop_loss_multiplier`, `take_profit_risk_reward`.
- Populated `backend/risk/__init__.py` with public exports.
- Updated `tests/test_events.py` — `RiskApproved`/`RiskRejected` new-style payload assertions.
- Updated `tests/test_config.py` — `RiskConfig` extended-field validation.
- Created `tests/test_risk_engine.py` (22 KB, 38 tests) — every rejection path, identity/timestamp/entry mismatches, max-positions boundary with pending reservations, reserved-bot isolation, CLOSE approval, lifecycle hooks, constraint validation variants, post-rounding geometry guards.
- **294 backend tests passing**, **Ruff clean**, **Feature 06 mypy clean** (21 pre-existing errors in unrelated test files), **98% risk-module coverage** (4 missed lines: defensive guard + fail-closed handler).

### Context Documentation Reconciliation (preserved from previous session)

- Reconciled all 17+ context documentation files to form a single authoritative source of truth.
- Established singular ownership boundaries, approved MVP execution model, metric policy, and 9 approved defaults.
- Final review: **PASS** with 0 Critical, 0 Important, 0 Minor findings.
- Resolved 6 findings from the first review cycle.

### Feature 04 — Strategy Engine (preserved from previous session)

- Strategy contracts with UUID/Decimal, immutable Signal, provenance, warm-up, registry, parameter, validation, and fail-closed contracts.
- StrategyEngine validates completed candles, deduplicates by composite key, gates signals until warm-up completes.
- 256 tests, Ruff clean, mypy clean.

### Feature 03 — Data Layer (preserved from previous session)

- Historical CSV and Binance Spot providers, normalized contracts, provider-aware persistence, dataset fingerprints, UUID migrations 005/006, repositories, and provider registry.

## Decisions made

### From this session (Feature 06 Risk Engine)

- **No ATR for the MVP.** Stop sources are configuration-driven: `percentage_of_entry`, `absolute_price_distance`, or `explicit_stop_price`. No ATR indicator, no ATR import, no ATR field.
- **1% default / 2% hard cap** on per-trade equity risk. Enforced at config level (Pydantic `gt=0, le=0.02`) and at runtime (guard raises if > 2% even if config somehow exceeds it).
- **Three stop sources, not just strategy proposals.** The risk engine resolves stops from config — strategy stop proposals may be supported later but are always subject to Risk approval.
- **Conservative rounding:** BUY → `ROUND_FLOOR` for stop distance and quantity; SELL → `ROUND_CEILING`. This prevents under-sizing long stops and over-sizing short stops when precision must truncate.
- **Sizing from rounded stop distance.** Position size = risk_amount / rounded stop_distance, not raw stop_distance. This ensures the math uses the exact distance that will be enforced.
- **Optional R:R take-profit.** No universal target ratio. When `take_profit_risk_reward` is configured, TP = entry ± (stop_distance × ratio); when absent, no TP is set.
- **No scaling or reversal.** Direction conflict (BUY signal while existing long) rejects the signal. CLOSE is approved as a zero-quantity close intent.
- **Transient reservations + per-bot isolation.** Each RiskEngine maintains its own `set[ReservationKey]` scoped by `(account_id, mode, instrument_id)`. Pending entries occupy a slot without needing a persisted position.
- **Foreign bot filtering.** RiskEngine silently ignores signals where `event.bot_id != self._bot_id` — critical since EventBus is per-process, not per-bot-pipeline.
- **Fail-closed:** exceptions in `_handler` log the error and re-raise; no misleading approvals are published.
- **No Feature 07/05 scope leakage.** The risk engine has zero dependencies on orders, fills, positions, P&L, broker interfaces, database, API, or UI.

### Preserved from previous sessions

- Feature IDs are stable domain identifiers, not implementation sequence; the roadmap owns delivery order.
- BotSupervisor ownership: Feature 02 (core lifecycle), Feature 09 (paper/testnet pipeline), Feature 12 (API/UI).
- Paper Broker: shared algorithm with mode-specific price sources (next-candle open for backtests, current market for live paper).
- Event payload ownership: Feature 04 owns SignalGenerated/StrategyError; Feature 06 owns RiskApproved/RiskRejected; Feature 07 owns execution events.
- Execution realism defaults approved: 0.10% taker fee, 0.05% fixed adverse slippage, stop-loss-first candle ambiguity, complete fills by default, no synthetic candles, indefinite data retention, immutable strategy pins.
- Metric formulas canonical in Feature 10; Feature 05 persists raw snapshots.
- Atlas remains single-user, paper-first, broker-agnostic, single-worker for the MVP.
- Backend identifiers use UUID; prices, quantities, fees, P&L, and signal strength use Decimal; timestamps are UTC.
- Local Docker: 2 CPUs/~3 GiB normal, 3 CPUs/~4 GiB for heavier iteration.

## Problems solved

### From this session

- **Event payload lockstep:** Adding `RiskApproved`/`RiskRejected` payload fields required simultaneous update of `tests/test_events.py` `EVENT_TYPES` parametrized assertion. The exploration phase flagged this blocker; the update was done in lockstep.
- **`_optional_constraint` edge cases:** Missing `min_qty`/`min_notional` in per-instrument constraints defaults to `ZERO`, which could pass `>=` validation incorrectly. Handled with explicit `ZERO if name != "max_qty" else None` — correct for current constraint set, flagged as a cosmetic Minor observation.
- **Mode filtering gap in position conflict check:** Initial implementation didn't scope reservation keys by `mode` (backtest vs paper). Fixed so mode is part of the key — different modes for the same account/instrument are independent.
- **Post-rounding stop geometry:** After conservative rounding (e.g., BUY `ROUND_FLOOR` on stop), a rounded stop at entry is possible (zero distance). Added a post-rounding guard that rejects `invalid_stop` if the rounded distance isn't positive.
- **295 → 294 test count:** One `pytest-asyncio` fixture running on non-async test was consuming the event loop without yielding — removed the unused async from that fixture.

### Preserved from previous sessions

- Resolved stale Feature 04 contracts using `instrument: str`, `strength: float`, `candle_id`, and mutation of frozen Signals.
- Documentation drift root cause addressed — ownership boundaries and approved defaults now explicit.
- Transport timeouts vs domain-clock deadlines distinguished.

## Eureka moments

- Choosing explicit stop sources over ATR eliminates indicator state, warm-up latency, and candle-sync complexity from the risk gate — the risk engine stays purely configuration-driven and deterministic.
- Conservative tick/step rounding on both stop distance and quantity means the risk engine is always pessimistic about how much risk it's taking, which is the correct safety posture.
- The `RiskContextProvider` protocol (callable or `RiskContext`-returning awaitable) decouples the risk engine from any DB/broker dependency without needing abstract base classes or dependency injection frameworks.
- Documentation drift was the root cause of most architectural ambiguity — explicit ownership boundaries prevent entire classes of implementation errors.

## Current state

- Feature 06 Risk Engine is **complete and reviewed** — 294 tests, Ruff clean, Feature 06 mypy clean, 98% coverage, final review PASS. Branch `feature/06-risk-engine` has uncommitted implementation files.
- Context documentation reconciliation is complete and verified; `main` contains Feature 04 + reconciliation (locally ahead of `origin/main`).
- Docker Compose is stopped; PostgreSQL volume preserved.
- All dispatch files present with Feature 06 records in PLAN.md, TASKS.md, DECISIONS.md, EXPLORATION.md, REVIEW.md, COMPLETED.md, MODEL-LOG.md.
- Next implementation slice: **Feature 07 — Execution Layer** (Phase 6), then Feature 05 (Backtesting).

## Next session starts with

1. Restore memory and confirm this state.
2. Commit and push the Feature 06 implementation on `feature/06-risk-engine` (or merge to `main`).
3. Read Feature 07 (Execution Layer) acceptance criteria — `context/features/07-execution-layer.md`.
4. Feature 07 requires: Order, Fill, Position, Trade domain models; migration 007; repository protocols; Broker interface; PaperBroker; execution events; paper-trade pipeline. Plan the implementation order (data models first, then broker, then execution engine).

## Open questions

- Exact Feature 05/07 replay mechanism for supplying warm-up candles while preserving deterministic timing.
- Whether to push local `main` to remote before beginning Feature 07.
- No remaining Feature 06 open questions — all edge cases from the initial exploration (ATR dependency, direction-conflict policy, CLOSE handling, bot_id filtering) were decided and implemented.

---

## Session: Feature 06 Risk Engine — 2026-08-04

This session completed Feature 06 Risk Engine per the approved no-ATR blueprint.

### What was done

- Revised the ARCHITECTURE.md blueprint to incorporate the approved no-ATR stop policy and take-profit boundary.
- Implemented RiskApproved/RiskRejected event payloads in `backend/core/events.py` and extended RiskConfig in `backend/config.py`.
- Implemented the pure Risk Engine evaluator in `backend/risk/engine.py` — RiskContext, position sizing, stop resolution, constraint validation, conservative rounding, reservation tracking, CLOSE approval, direction-conflict rejection, fail-closed handler.
- Implemented the EventBus adapter and complete test suite in `tests/test_risk_engine.py` (38 tests).
- First review (GPT-5.6 Luna): **needs-retry** — 7 Important findings (coverage gaps, mode filtering, type suppressions).
- Fix loop resolved all 7 findings: added missing rejection-path tests, fixed mode filtering in position conflict, removed `# type: ignore` from fixtures.
- Re-review (GPT-5.6 Luna): **PASS** — 0 Critical, 0 Important, 3 Minor cosmetic observations.

### Review summary

| Review cycle | Model | Outcome |
|---|---|---|
| Initial Feature 06 review | GPT-5.6 Luna | needs-retry (7 Important findings) |
| Post-fix re-review | GPT-5.6 Luna | success — PASS |

### Key outcomes

- The no-ATR stop design was validated through implementation and review — no indicator state or warm-up needed for the risk gate.
- Every rejection path has a direct test (25 `_Reject` paths all covered).
- Conservative rounding direction is confirmed safe for both BUY and SELL.
- Risk engine is broker-agnostic, DB-independent, and ready to feed RiskApproved events to Feature 07.

### Files created or modified

**Created:**
- `backend/risk/engine.py` — RiskEngine, RiskContext, PositionInfo, PositionStatus, RiskContextProvider
- `backend/risk/__init__.py` — public exports
- `tests/test_risk_engine.py` — 38 tests covering all rejection paths and lifecycle

**Modified:**
- `backend/core/events.py` — RiskApproved/RiskRejected payload fields
- `backend/config.py` — RiskConfig extended with stop/tp/constraint fields
- `config/default.yaml` — full risk section
- `tests/test_events.py` — updated EVENT_TYPES assertions
- `tests/test_config.py` — extended RiskConfig validation tests
