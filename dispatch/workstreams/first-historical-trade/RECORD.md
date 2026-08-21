# RECORD — First Historical Trade (Atlas Phase 3)

**Date:** 2026-08-21
**Status:** **CLOSED** — implementation and final review complete; memory-save receipt verified.

## Durable scope

Phase 3 proves two persisted, deterministic historical Experiments for EUR/USD/OANDA M1 data: one LONG and one SHORT, each completing exactly one `FLAT → exposed → FLAT` episode through the Strategy → TradeIntent → RiskDecision → Order → Fill → Position → Trade path. The implementation remains bounded by `PHASE3_OPEN_CHECKPOINT_V1`: snapshot-only inputs, completed-candle/no-lookahead ordering, centralized Risk, pure simulated execution, Fill-authoritative exposure, whole-unit EUR sizing, sanitized fail-closed failures, and no Phase 4/API/UI/broker/runtime behavior.

## Implementation boundary

- Strategy state was separated from financial exposure (`PositionState` versus canonical financial `Position`).
- The Phase 3 model boundary adds the eight approved tables: `experiments`, `experiment_accounts`, `trade_intents`, `risk_decisions`, `orders`, `fills`, `positions`, and `trades`. Migration `0004_phase_3_first_trade` establishes them; forward-only `0005_phase_3_failure_persistence` adds immutable terminal failure facts. Restrictive relationships, financial checks, uniqueness protections, immutability, and terminal projection guards are persisted in PostgreSQL.
- Snapshot membership reads carry immutable source identities and do not consult mutable current-bar projections. `SimulationClock` separates the completed decision frontier from post-decision BID/ASK opens. Repositories, central Risk, pure simulated execution, atomic `apply_fill`, and the Experiment runner compose the vertical slice.
- No `TradingAccount`, Deployment, RiskProfile, OrderEvent, equity-history, SystemEvent, or generalized execution infrastructure was introduced; the account used by Experiments is `SimulatedAccount`.

## Validation and golden evidence

Independent validation and final R1 review are PASS. LONG and SHORT PostgreSQL golden flows both pass and prove real EMA Sweep Engulfing decisions, immutable StrategyVersion/DatasetSnapshot provenance, frontier/no-lookahead behavior, approved PRE_FLIGHT and PRE_SUBMISSION Risk, direction-correct executable quotes, actual-entry targets, source M1 identities, Fill-driven closed Trades with correct P&L and R=1.7, updated simulated accounts, FLAT Positions, COMPLETED Experiments, and semantic rerun equivalence excluding generated IDs/timestamps.

Migration upgrade/downgrade/re-upgrade, failure persistence, Fill application, snapshot repository, supporting integration tests, non-integration tests, Ruff, Pyright on receipt-cited modules, and compileall passed. The final isolation recheck makes the full suite reproducible: sequential `pytest -q` runs from residue-present and base-schema states each yielded `170 passed, 1 skipped`; integration-only yielded 18 passed.

## Resolved and outstanding observations

- **OBS-2 (Important): resolved.** Test-only integration fixtures now ensure the head schema and truncate the shared `_test` database per integration test. Final review found no remaining Critical or Important issue.
- **OBS-1 (Minor, non-blocking):** clock decision gating retains NY-calendar coupling and can admit a partial-break warmup bar; consider membership-gap-derived gating if stricter snapshot purity is later required.
- **OBS-3 (Minor, non-blocking):** `backend/experiments/runner.py` remains outside the strict Pyright-clean set (128 reported errors); annotate in a future hardening pass if desired.

## Material report inventory

Authoritative scope/acceptance: `dispatch/PHASE-3-BLUEPRINT.md`; readiness/control: workstream `READY.md` and `dispatch/ACTIVE.md`; implementation evidence: `TASK-01` through `TASK-10` (including `TASK-08A`); independent validation: `VALIDATION.md`; final gate: workstream `REVIEW.md`. Existing reports and task context remain preserved. No Phase 4 expansion, Git operation, branch cleanup, or reset was performed.

## Closure state

The workstream is terminally closed after R1 PASS and explicit user confirmation of `/remember save`. `memory.md` was durably updated with a secret-safe Phase 3 state summary; no secrets were recorded. No active-control reset or deletion was performed or authorized.
