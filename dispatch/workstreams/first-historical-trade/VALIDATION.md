# VALIDATION — First Historical Trade (Phase 3)

Status: **PASS** (implementation validated against the authoritative blueprint; three non-blocking observations)

Role: Independent tester. Owns only this artifact. No dispatch artifact or application code was modified, no branch was changed, and no Git-changing command was run.

## Scope basis

- Blueprint: `dispatch/PHASE-3-BLUEPRINT.md` (authoritative, per `READY.md` and `ACTIVE.md`).
- Control plane: `dispatch/ACTIVE.md` (READY → validation in progress), `dispatch/PLAN.md`, `dispatch/TASKS.md`.
- Read receipts: `READY.md`, `TASK-01` … `TASK-09`, `TASK-08A`.
- Environment: branch `feature/first-historical-trade`, HEAD `4fd3c5b094dccefa2c479e274e94841af0f966aa`, cwd `/Users/vike/Desktop/atlas`. Matches `READY.md`.
- Inspection: CodeGraph-first (clock, runner, fill application, strategy, risk), then targeted file reads of the reviewed modules.
- Independent execution: golden flows, migration cycle, fill application, failure persistence, market-data repositories, full non-integration suite, single full-suite invocation, ruff, pyright on the receipt-cited files.

## Validation performed (independent commands)

Every receipt below was re-run independently. A pre-existing PostgreSQL environment permission gap (`atlas` role lacked schema/database privileges on the shared `atlas_test` DB) was fixed with local-only GRANT statements; this is not a repository change and did not alter any source.

| Command | Result | Reuses / rerun reason |
|---|---|---|
| `pytest -q backend/tests/integration/test_golden_flows.py` | **2 passed** (LONG + SHORT) | Rerun — end-to-end acceptance evidence; required PostgreSQL grant fix |
| `pytest -q backend/tests/integration/test_migrations.py` | **2 passed** (upgrade→downgrade base→upgrade, exact table set, failure columns, unique indexes) | Rerun — migration cycle gate |
| `pytest -q backend/tests/integration/test_fill_application.py` | **2 passed** (clean DB) | Rerun — atomic Fill boundary |
| `pytest -q backend/tests/integration/test_runner_failure_persistence.py` | **1 passed** (clean DB) | Rerun — persisted sanitized failure |
| `pytest -q backend/tests/integration/test_market_data_repositories.py` | **3 passed** (clean DB) | Rerun — snapshot-only reads |
| `pytest -q backend/tests/integration/test_market_data_ingestion.py backend/tests/integration/test_strategy_persistence.py backend/tests/integration/test_database.py` | **8 passed** (clean DB) | Rerun — supporting integration coverage |
| `pytest -q -m "not integration"` | **151 passed, 1 skipped** | Rerun — non-integration suite (matches receipt "168 passed, 1 skipped" when added to the 17 clean-DB integration tests) |
| `pytest -q` (single invocation, shared DB) | **2 failed, 168 passed, 1 skipped** | Diagnostic — see OBS-2 |
| `ruff check` on changed implementation/test/migration files | **passed** | Rerun |
| `pyright` on receipt-cited files (clock, golden flows, risk, execution contract/simulated, trading domain, experiment/trading repositories, fill_application) | **0 errors, 0 warnings** each | Rerun |
| `python -m compileall -q` on changed modules | **passed** | Rerun |

Reused receipts: `TASK-05`/`TASK-06`/`TASK-07`/`TASK-08` pyright/ruff receipts are consistent with the clean re-runs above; `TASK-08A` full-suite claim is consistent only when integration tests run in isolation (see OBS-2).

## Criterion-by-criterion findings

### 1. Migrations / head and PostgreSQL migration cycle — PASS
Alembic head is `0005_phase_3_failure_persistence`, chained forward from `0004_phase_3_first_trade`; `test_migration_revision.py` asserts the head and a bounded revision ID. `test_migrations.py` passed the full cycle (drop schema → upgrade head → check → downgrade base → re-upgrade head), verified the **exact 16-table set** (the 8 approved Phase 3 tables + existing Phase 0/1/2 tables, plus `alembic_version`), the `experiments.failure_category/failure_code/failure_detail` columns, and the intent-frontier / Risk-phase / Fill-sequence / Position uniqueness indexes. `0004` defines restrictive FKs, UTC timestamps, positive-financial checks, immutability triggers, terminal projection guards, and `model_version` (`PHASE3_OPEN_CHECKPOINT_V1`). **No** TradingAccount, Deployment, RiskProfile, OrderEvent, equity-history, or SystemEvent table exists.

### 2. Full test suite — PASS (with OBS-2)
All receipts verified. See note under OBS-2 about single-invocation integration isolation.

### 3. LONG/SHORT golden flows — PASS
Both parameterized PostgreSQL flows completed. Persisted facts prove: COMPLETED Experiment with correct `model_version` and provenance (dataset_snapshot_id / strategy_version_id), PRE_FLIGHT and PRE_SUBMISSION both APPROVED, decision frontier `START+1530`, executable quote sides, target from actual entry, Fill-driven closed Trade with `exit_reason=TAKE_PROFIT`, correct long/short P&L and R=1.7, FLAT final Position, updated account, and source M1 identities resolving to immutable snapshot members. No stubbed decision path: the real EMA Sweep Engulfing StrategyVersion is registered from its archive with real reference/sweep/confirmation/post-decision inputs.

### 4. Deterministic rerun equivalence — PASS
The golden test creates a second identical Experiment from the same StrategyVersion + DatasetSnapshot and asserts semantic equality of all facts excluding generated IDs/timestamps. Passed for both directions.

### 5. Strategy purity — PASS
`ExperimentRunner` calls `evaluate_strategy` with `StrategyContext(frontier, instrument, history_bars, PositionState.FLAT, exposure_allowed)` and parameters only. The Strategy receives no account state, no balance, no sizing, no broker, no DB, and cannot submit Orders. EMA Sweep Engulfing is a real, deterministic implementation with fixed Phase 1 parameters.

### 6. Snapshot-only membership — PASS
`DatasetSnapshotRepository.ordered_members_with_sources` reads `dataset_snapshot_bars` directly and does **not** filter `market_bars.is_current`; `by_fingerprint` loads without consulting mutable heads. `test_market_data_repositories.py` proves ordering, source identities, correction provenance, and that a reread equals the originally captured bars after the mutable current projection changes — so mutable current bars cannot enter a run.

### 7. Decision/execution frontier and no lookahead — PASS
`SimulationClock.frames()` emits, per M15 frontier `T`: the completed M1 interval ending at `T` (decision context) first, exactly one completed MID M15 bar ending at `T`, then only BID/ASK M1 opens beginning at `T` for execution. `test_signal_bar_is_not_reused_as_post_decision_execution_data` proves signal-bar data is never returned as executable data. The runner builds the executable `ExecutionObservation` from the post-decision BID/ASK opens; entry uses ASK for LONG / BID for SHORT. No earlier-price or new-M1-high/low reuse in the entry/target path.

### 8. EUR/USD and USD-only Risk — PASS
`RiskService._common` rejects any instrument other than `EUR_USD` and any account base currency other than `USD` with `UNSUPPORTED_INSTRUMENT_ECONOMICS`. All six required rejections are present as typed codes. PRE_SUBMISSION uses executable ASK (LONG) / BID (SHORT), validates stop geometry, floors whole-unit EUR sizing, and asserts actual risk ≤ budget. Target derives from actual entry (long `entry + multiple×(entry−stop)`; short `entry − multiple×(stop−entry)`).

### 9. Fill-only exposure — PASS
`apply_fill` is the sole boundary at which financial state changes, inside a savepoint that rolls back the Fill and all projections on failure. Entry Fill opens Position/Trade; supported exit Fill closes them and realizes long/short Decimal P&L with zero fee. `test_entry_fill_is_the_only_exposure_transition` and `test_failed_fill_rolls_back_all_projections` passed (clean DB). `SimulatedExecutionAdapter` is pure — creating an Order and producing a Fill never apply exposure.

### 10. Persisted sanitized fail-closed results — PASS
Migration `0005` adds immutable terminal `failure_category`/`failure_code`/`failure_detail` with DB checks (approved categories, uppercase codes, control-character-free detail, FAILED/non-FAILED consistency) and a revised immutability trigger permitting failure facts only on the RUNNING→FAILED transition. `ExperimentRunner._fail` sanitizes detail (whitespace-collapse, ≤500 chars), stops new exposure, preserves any open Position without invented closure, and `PHASE3_TRADE_NOT_COMPLETED` is never returned as success. `test_runner_failure_persistence.py` passed.

### 11. No Phase 4 scope creep — PASS
No API/UI/CLI/runtime/OANDA/PAPER/LIVE/reconciliation added; no full M1 replay, intrabar ordering, gaps/slippage/costs/equity-history/metrics/forced-end-close/multiple Trades; no partial Fills or protective Order lifecycle. Stop closure is intentionally unsupported (fails `UNSUPPORTED_PHASE3_STOP_GAP` / `UNSUPPORTED_PHASE3_INTRABAR_TRIGGER`) rather than fabricated; target-only closure is used and disclosed. Exclusions are documented in each task report.

## Findings by severity

- **BLOCKER**: none.
- **HIGH**: none.
- **MEDIUM**: none.
- **LOW — OBS-1 (flagged Task-09 NY daily-break behavior):** `SimulationClock.frames()` (clock.py:156-166) couples decision-frontier gating to the real-world NY session calendar via `is_session_open_minute`, skipping a frontier when no completed M1 ends at it during the daily break and staying fail-closed for unexpected gaps during an open session. **This does not violate the approved Phase 3 scope or core data semantics for the golden flows:** the skip fires only at break-adjacent frontiers (≈22:00 UTC), never in the 01:00–02:00 UTC trading window, so no legitimate decision is suppressed; decisions remain guarded by `exposure_allowed`, so no exposure can be created from incomplete data; and it is fail-closed for genuine gaps. Two genuine deviations remain worth documenting: (a) gating is driven by a wall-clock calendar rather than purely snapshot membership — a scope-adjacent coupling the blueprint's "snapshot-only" language does not authorize, though it reuses existing Phase 2 session-policy infrastructure consistent with the data model; and (b) an M15 bar spanning the break (missing the break minutes) is still emitted as a **WARMUP** frame, so its partial prices feed the strategy's EMA warmup history, slightly departing from "warm up completed bars" (impact is nil for the golden outcome since exposure is disabled during warmup). Recommended: keep, but document, and if stricter data-driven purity is desired derive break-adjacent gating from membership gaps instead of the calendar.
- **LOW — OBS-2 (integration test isolation):** The integration test files share one PostgreSQL `_test` database and are not mutually isolated; a single `pytest -q` yields **2 failed, 168 passed** from cross-file residue (duplicate `instruments`/`strategies` seeds), while every file passes in isolation. Not an implementation defect — the "168 passed, 1 skipped" receipt reflects clean-state/per-file runs — but the "full suite" receipt is not reproducible as one command. Recommend truncating/resetting between integration files or per-file cleanup before the final gate.
- **INFO — OBS-3 (pyright on runner.py):** `pyright backend/experiments/runner.py` reports 128 errors (primarily `reportUnknownArgumentType` in `_fail` and dynamic-dispatch paths). No receipt claimed pyright for runner (TASK-08 cited ruff/compileall/pytest only), so this is not a receipt violation, but the runner is not pyright-clean while its collaborators are.

## Reusable evidence (exact receipts)

- `pytest -q backend/tests/integration/test_golden_flows.py` → **2 passed**
- `pytest -q backend/tests/integration/test_migrations.py` → **2 passed**
- `pytest -q backend/tests/integration/test_fill_application.py` → **2 passed** (clean DB)
- `pytest -q backend/tests/integration/test_runner_failure_persistence.py` → **1 passed** (clean DB)
- `pytest -q backend/tests/integration/test_market_data_repositories.py` → **3 passed** (clean DB)
- `pytest -q -m "not integration"` → **151 passed, 1 skipped**
- `pytest -q` (single invocation) → **2 failed, 168 passed, 1 skipped** (OBS-2 diagnostic; do not treat as a suite failure)
- `ruff check` (changed files) → passed
- `pyright` (clock, golden_flows, risk/service, execution/contract, execution/simulated, domain/trading, experiment_repository, trading_repository, fill_application) → 0 errors each

Reusable receipts remain valid only when: (1) the branch is `feature/first-historical-trade` at HEAD `4fd3c5b…`; (2) integration tests run against a clean/isolated PostgreSQL test DB; (3) environment grants remain as configured here.

## Recommended next gate

**Independent final review (`REVIEW.md`), with OBS-2 test isolation addressed or explicitly accepted first.** After the review clears, dispatch the documenter (`RECORD.md` / `COMPLETED.md`). No further implementation is required for Phase 3 acceptance; do not expand into Phase 4. Preserve all uncommitted task context and the branch per `READY.md` cleanup ownership.
