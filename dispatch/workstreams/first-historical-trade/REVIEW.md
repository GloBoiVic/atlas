# REVIEW — First Historical Trade (Atlas Phase 3)

Gate: **R1** (independent final review)
Spec compliance: **PASS** (scope, invariants, acceptance evidence verified against the blueprint)
Task quality: **PASS** (Important OBS-2 resolved in TASK-10 recheck; two Minor follow-ups)
Layer 1 (plan alignment): **PASS**
Layer 2 (system integrity): **PASS**
Layer 3 (production readiness): **PASS** (after TASK-10 recheck — see below)
Decision: **PASS** (OBS-2 resolved by TASK-10; final R1 — see recheck below)

> **Recheck (TASK-10) — final R1 decision appended below.** The earlier BLOCKED
> verdict was solely due to Important OBS-2; it is now resolved with independent
> evidence. OBS-1/OBS-3 remain non-blocking Minor follow-ups.

---

## Basis and scope

- Blueprint (authoritative): `dispatch/PHASE-3-BLUEPRINT.md`.
- Control plane: `dispatch/ACTIVE.md`, `dispatch/PLAN.md`, `dispatch/TASKS.md`.
- Receipts: `READY.md` (branch `feature/first-historical-trade`, HEAD `4fd3c5b094dccefa2c479e274e94841af0f966aa`, cwd `/Users/vike/Desktop/atlas`), `TASK-01` … `TASK-09`, `TASK-08A`, `VALIDATION.md`.
- Reviewed cwd matches the READY receipt: branch `feature/first-historical-trade`, HEAD `4fd3c5b…`. All Phase 3 files are uncommitted task context in this same checkout, consistent with `READY.md` feature-branch mode.
- Inspection method: CodeGraph-first (runner, clock, risk, execution, fill application, strategy, registry, aggregation, session calendar), then direct reads of the reviewed modules, migrations, golden-flow test, and snapshot repository. Evidence checks reproduced independently where the finding affects the check (full suite, fill-application isolation, migration cycle, non-integration suite, runner pyright).

## Layer 1 — Plan alignment

Scope is exactly the blueprint's Phase 3 outcome and excludes Phase 4 work:

- No API/UI/CLI/runtime/OANDA/PAPER/LIVE/reconciliation changes (`git status` clean for `backend/api`, `backend/runtime`).
- No full M1 replay, intrabar ordering, gaps/slippage/costs/equity-history/metrics/forced-end-close/multiple-Trades, partial Fills, or protective-Order lifecycle.
- Migration `0004` adds exactly the eight approved tables (`experiments`, `experiment_accounts`, `trade_intents`, `risk_decisions`, `orders`, `fills`, `positions`, `trades`); no `TradingAccount`, `Deployment`, `RiskProfile`, `OrderEvent`, equity-history, or `SystemEvent`. `0005` is a forward-only chained revision (`0005_phase_3_failure_persistence` ← `0004_phase_3_first_trade`), matching the bounded-revision head asserted by `test_migration_revision.py`.
- `PHASE3_OPEN_CHECKPOINT_V1` model version is persisted and disclosed; `PHASE3_TRADE_NOT_COMPLETED` is never returned as success.

## Layer 2 — System integrity

- **Strategy purity — PASS.** `ExperimentRunner.run` (runner.py:191-195) calls `evaluate_strategy(implementation, StrategyContext(frontier, instrument, tuple(history), PositionState.FLAT, frame.exposure_allowed), params, state)`. The Strategy receives no account, balance, sizing, broker, or DB. StrategyVersion is resolved only through the verified registry (`StrategyRegistry.implementation_for_version` matches source fingerprint + implementation_key and never reads the filesystem at resolution time).
- **Snapshot-only / no mutable-current-bar — PASS.** `DatasetSnapshotRepository.ordered_members_with_sources` joins `dataset_snapshot_bars` directly with no `is_current` predicate and is bounded to snapshot coverage (market_data_repository.py:498-560); `by_fingerprint` and the runner use immutable membership. Mutable current heads cannot enter a run.
- **No-lookahead frontier — PASS.** `SimulationClock.frames()` yields, per M15 frontier `T`: the completed M1 ending at `T` (decision context) first, exactly one completed MID M15 ending at `T`, then only BID/ASK M1 opens beginning at `T`. `_observation` uses the post-decision BID/ASK opens for entry; entry side is ASK (LONG) / BID (SHORT). The completed M1 ending at `T` is used only for unsupported-intrabar detection, not for an invented fill. Test `test_signal_bar_is_not_reused_as_post_decision_execution_data` proves signal-bar M1 data is never returned as executable data.
- **Risk ownership / EUR/USD economics — PASS.** `RiskService._common` rejects any instrument other than `EUR_USD` and any base currency other than `USD` (`UNSUPPORTED_INSTRUMENT_ECONOMICS`). PRE_FLIGHT and PRE_SUBMISSION implement all six required typed rejections; PRE_SUBMISSION floors whole-unit EUR sizing with `equity × risk_per_trade` budget and asserts actual risk ≤ budget. Target derives from the actual entry (`entry ± multiple × (entry−stop)`); long liquidation is BID, short is ASK.
- **Fill-only exposure — PASS.** `apply_fill` (fill_application.py) is the sole financial-state boundary inside a savepoint that rolls back the Fill and all projections on failure. Entry opens Position/Trade; supported exit closes them with Decimal P&L (`(exit−entry)×qty` long, `(entry−exit)×qty` short) and zero fee. `SimulatedExecutionAdapter` is pure — creating an Order and producing a Fill never mutate exposure.
- **Migration safety — PASS.** `test_migrations.py` passed the full upgrade→downgrade→upgrade cycle, exact 16-table set, failure columns, and the intent-frontier/Risk-phase/Fill-sequence/Position uniqueness indexes. The immutability trigger in `0005` permits failure facts only on the RUNNING→FAILED transition and blocks post-terminal mutation.
- **Persistence of sanitized failures — PASS.** `0005` adds immutable terminal `failure_category`/`failure_code`/`failure_detail` with DB checks (approved categories, uppercase codes, control-character-free ≤500-char detail, FAILED/non-FAILED consistency). `ExperimentRunner._fail` sanitizes detail (whitespace-collapse, ≤500), stops new exposure, preserves any open Position without invented closure. `test_runner_failure_persistence.py` passed (persisted + terminal-mutation rejection).
- **Determinism — PASS.** Decimal/NUMERIC only, no RNG, immutable state; the golden test re-runs an identical second Experiment and asserts semantic equality of all facts excluding generated IDs/timestamps for both LONG and SHORT.

## Layer 3 — Production readiness

- **Golden LONG/SHORT flows — PASS.** Both parameterized PostgreSQL flows pass; persisted facts prove COMPLETED Experiment, provenance, PRE_FLIGHT + PRE_SUBMISSION APPROVED, decision frontier `START+1530`, executable quote sides, actual-entry target, Fill-driven closed Trade with `exit_reason=TAKE_PROFIT`, R=1.7, FLAT Position, updated account, and source M1 identities resolving to immutable snapshot members. Real EMA Sweep Engulfing StrategyVersion registered from its source archive — no stub decision path.
- **Migration cycle / non-integration suite — PASS (independent re-runs).** `pytest -q backend/tests/integration/test_migrations.py` → 2 passed. `pytest -q -m "not integration"` → 151 passed, 1 skipped (matches receipt).
- **Full suite as a single command — ISSUES (OBS-2, Important).** See findings.

## Findings

### Important — OBS-2: full suite does not pass as a single command

- **Location:** `backend/tests/integration/*.py` (isolation model), most concretely `test_fill_application.py:59-62` (hardcoded `InstrumentModel(code="EUR/USD")` with no truncation/cleanup/conflict handling).
- **Evidence (independently reproduced):** `pytest -q` → **2 failed, 168 passed, 1 skipped**, both failures `UniqueViolation … "uq_instruments_code"` `Key (code)=(EUR/USD) already exists` in `test_fill_application.py`. The file passes **2/2 on a truncated clean DB**. The failure is deterministic given the shared `atlas_test` DB already containing an `EUR/USD` instrument seeded by an earlier integration file (e.g. `test_golden_flows`, which truncates, or other files that do not). Every integration file passes in isolation on a clean DB, but the suite is order/state-dependent.
- **Impact:** The blueprint's "full-suite" completion gate is not reproducible as one command. The `TASK-08A` receipt claiming `pytest -q` → 168 passed is not reproducible single-command (it reflects clean-state/per-file runs). This directly contradicts the requirement that an implementation pass its full suite as a single command. It is a test-harness defect, not an application-code defect: no Phase 3 product behavior is broken, and all acceptance evidence is intact.
- **Remedy (test-only):** Make integration test files mutually isolated — truncate/reset the `_test` DB between files (or use unique per-test instrument codes / an autouse reset), then re-run `pytest -q` to green as a single invocation.

### Minor — OBS-1: clock couples decision-gating to the NY wall-clock calendar; partial-break warmup bars

- **Location:** `backend/experiments/clock.py:156-166` (`is_session_open_minute` gate) and `frames()` warmup handling.
- **Evidence:** A missing completed M1 at a frontier is classified as "legitimate break" (skip) via the NY calendar rather than derived from snapshot membership gaps; an M15 window spanning the daily break is aggregated from only the present open minutes and still emitted as a WARMUP frame, so its partial prices enter the EMA warmup history.
- **Impact:** Deviation from the blueprint's "snapshot-only" language, but fail-closed and scoped: the skip fires only at break-adjacent frontiers (≈22:00 UTC), never in the 01:00–02:00 UTC golden trading window; decisions remain guarded by `exposure_allowed`, and warmup has exposure disabled, so no exposure can be created from incomplete data and the golden outcome is unaffected. The coupling reuses existing Phase 2 session-policy infrastructure consistent with the data model.
- **Remedy:** Document the coupling; if stricter data-driven purity is desired, derive break-adjacent gating from membership gaps instead of the calendar. Non-blocking.

### Minor — OBS-3: runner.py is not pyright-clean while collaborators are

- **Location:** `backend/experiments/runner.py` (e.g. `_fail`, `_open_and_close`, untyped SQLAlchemy model access).
- **Evidence (independently reproduced):** `pyright backend/experiments/runner.py` → **128 errors** (predominantly `reportUnknownArgumentType`/`reportUnknownMemberType`); pre-existing Phase 2 modules (`backend/persistence/strategy_repository.py`, `backend/market_data/fingerprint.py`) report 0 errors. No task receipt claimed pyright for runner.py (TASK-08 cited ruff/compileall/pytest only), so this is not a receipt violation.
- **Impact:** Type-hygiene deviation from the repo's strict-typing convention in the safety-critical orchestrator; no runtime or behavioral impact (tests and integration receipts cover the behavior).
- **Remedy:** Annotate the runner so a strict `pyright backend` is green. Non-blocking.

## Checks run (evidence reuse and rerun reasons)

Reruns (reason: OBS-2/3 affect or gate the check; fresh reproduction of receipt claims):
- `pytest -q` (full) → **2 failed, 168 passed, 1 skipped** — reproduce OBS-2 single-command gate.
- `pytest -q backend/tests/integration/test_fill_application.py` on truncated clean DB → **2 passed** — isolate OBS-2 root cause (test isolation, not implementation).
- `pytest -q backend/tests/integration/test_migrations.py` → **2 passed** — reconfirm migration-cycle gate.
- `pytest -q -m "not integration"` → **151 passed, 1 skipped** — reconfirm non-integration receipt.
- `pyright backend/experiments/runner.py` → **128 errors**; `pyright backend/persistence/strategy_repository.py` and `backend/market_data/fingerprint.py` → **0 errors** — confirm OBS-3 and its deviation from baseline.

Reused receipts (not rerun; scope/env unchanged, receipt basis verified): `VALIDATION.md` golden flows (2 passed, LONG + SHORT) — corroborated in the full-suite run (golden flows not among the two failures); runner-failure persistence (1 passed); market-data repositories (3 passed); fill-application clean-DB (2 passed) reconfirmed above; `TASK-05`/`TASK-06`/`TASK-07` pyright/ruff receipts consistent with clean re-runs.

## Required remediation / next gate

1. **Resolve OBS-2 (Important, required before closure):** make the integration test suite mutually isolated so `pytest -q` passes as a single command; re-run the full suite to green.
2. Optionally resolve OBS-1 (document or membership-gap gating) and OBS-3 (runner annotations) — non-blocking, for follow-up.
3. Re-review Layer 3 (full-suite gate) after the OBS-2 fix; then dispatch the Documenter (`RECORD.md` / `COMPLETED.md`) per the terminal-eligibility flow in the review skill.

No Phase 4 implementation is authorized by this review; do not expand scope.

---

## Recheck after TASK-10 — final R1 decision

Gate: R1 (recheck)
Spec compliance: PASS
Task quality: PASS
Layer 1: PASS | Layer 2: PASS | Layer 3: PASS
Decision: **PASS**

### TASK-10 basis and scope

`TASK-10-integration-isolation.md` adds a single test-infrastructure file,
`backend/tests/integration/conftest.py`, to resolve Important **OBS-2**. `git
status` confirms the sole change from this task is that new untracked conftest;
no tracked implementation, migration, or test-assertion file was modified. Scope
is test-only — appropriate and within the required remediation.

### New conftest — scope/safety review (independent)

- **Test-only:** no application code, production schema, migration, or assertion
  changed. The file only adds autouse fixtures for the shared `*_test` DB.
- **Safety guard:** `_test_database_url()` returns `None` unless
  `ATLAS_TEST_DATABASE_URL` is set AND the database name ends in `_test`, so the
  fixtures can never act on a non-test database (conftest.py:64-72).
- **Session schema fixture:** `_ensure_integration_schema` runs `alembic upgrade
  head` once per integration session against the test URL, making a full run
  self-sufficient regardless of a prior invocation's schema state.
- **Per-test isolation:** `_isolate_integration_database` truncates every data
  table (via `TRUNCATE ... CASCADE`) before each integration test, so no test
  observes another test's rows. `TRUNCATE` correctly bypasses the row-level
  immutability triggers that only guard DML row transitions — the same mechanism
  the existing integration files already use for cleanup. Appropriate for a test
  DB.
- **Unaffected test:** the 19th integration-marked test
  (`test_cli_load_uses_fake_source_and_dedicated_database`) uses its own
  dedicated DB and is not touched by the conftest's shared-DB truncation.
- `ruff check backend/tests/integration/conftest.py` → **passed**; `pyright
  backend/tests/integration/conftest.py` → **0 errors, 0 warnings** (independent
  re-runs).

### Independent recheck evidence (run sequentially in READY cwd)

All runs used `.venv/bin/python -m pytest -q` with the shared `atlas_test` DB.
An initial parallel double-run produced transient failures that were an artifact
of two commands racing against the same DB (one downgrading while the other
ran); results below are clean sequential runs.

| State | Result |
|---|---|
| Residue present (OBS-2 reproduction; `EUR/USD` already in DB) | **170 passed, 1 skipped** |
| Consecutive full suite (cross-run isolation, head) | **170 passed, 1 skipped** |
| Downgraded to base schema (worst-case prior-state leak) | **170 passed, 1 skipped** |
| Integration directory in isolation | **18 passed** |

The `2 failed, 168 passed, 1 skipped` failure mode from the prior review is
gone: the suite now passes as a single command from both the residue-present and
base-schema states and is stable across consecutive sequential invocations.

### Finding dispositions

- **Important — OBS-2: RESOLVED.** Full `pytest -q` now passes as one command
  (170 passed, 1 skipped) from both residue-present and base-schema states,
  stable across consecutive runs. No new Critical/Important finding surfaced.
- **Minor — OBS-1** (clock NY-calendar coupling / partial-break warmup): no new
  evidence changed severity; retained as a non-blocking follow-up.
- **Minor — OBS-3** (runner.py not pyright-clean): no new evidence changed
  severity; retained as a non-blocking follow-up.

### Final decision

**PASS.** No Critical or Important finding remains; OBS-2 is resolved with
independent evidence, and the review gate is terminal-eligible. Hand the
terminal evidence to the Documenter (`RECORD.md` / `COMPLETED.md`) per the
review-skill terminal-eligibility flow. Non-blocking follow-ups (OBS-1, OBS-3)
may be tracked for future hardening. Do not expand into Phase 4.
