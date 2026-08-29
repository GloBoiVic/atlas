# T004 — Determinism and Boundary Regressions

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Lock the cleanup with deterministic before/after evidence and source-level proof that
no second authoritative Experiment execution path remains.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, sections 4, 5, 7, and 8
- Freeze 01–03 validation/golden receipts and relevant current tests

## Implement

- Add or update focused tests for runner call-graph exclusivity, V2 native product
  selection, legacy-read isolation, explicit pending-trigger boundaries, and
  retained compatibility non-use.
- Add deterministic replay/equivalence evidence over fixed canonical Experiment
  inputs: ordered intents, Risk decisions, Orders, Fills, Trades, equity, result
  metrics/quality, and output fingerprint.
- Include EMA v2 long/short, W1/W5/W6, exact trigger, no-lookahead, sparse absence,
  one-sided absence, terminal quote, result immutability, and failure-safety checks.
- Write a complete BUILD receipt; independent VALIDATE remains a later gate.

## Do not implement

- Do not update expected outputs merely because cleanup changed behavior.
- Do not add benchmarks, performance work, product features, migrations, or a second
  runner abstraction.

## Acceptance/checks

- Required deterministic and Freeze 01–03 regression tests pass.
- Before/after comparison differs only in permitted operational identity/timestamps
  and removed diagnostic plumbing.
- Source/import audit proves no executable alternate Experiment authority.

## Completion receipt

### Implementation

- Added source-graph guards proving `ExperimentRunService.run` reaches exactly one
  runner call, application composition constructs one `ExperimentRunner`, and
  `ExperimentRunner.run` dispatches only to `_run_v2` for the V2 schema.
- Added fail-closed regressions for V1, unknown, and absent snapshot schemas; the
  legacy runner is not entered.
- Added runner source guards for native M15 MID plus sparse BID/ASK products,
  strict `observation.start_time > decision_time`, equality/gap-through trigger
  operators, Strategy-owned W1-W5/W6 boundaries, retained IMMEDIATE handling, and
  absence of runner aggregation or expiry-clock reads.
- Added native/sparse clock boundary coverage, deterministic sequential W1-W5 and
  W6 reset coverage, explicit V1 aggregation-reader isolation, and persisted result
  metric projection coverage without read-time recalculation.
- Expanded the fixed PostgreSQL golden replay fixture to compare ordered intents,
  Risk decisions, Orders, Fills, Trades, all equity points, result metric states,
  quality, and output fingerprint; it also verifies the original completed facts
  remain unchanged after a semantic rerun.

### Files changed

- `backend/tests/experiments/test_runner_diagnostics.py`
- `backend/tests/experiments/test_clock.py`
- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_results.py`
- `backend/tests/strategies/test_ema_sweep_confirmation_break.py`
- `backend/tests/integration/test_golden_flows.py`
- `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T004-determinism-and-boundary-regressions.md`

### Checks / evidence

- `pytest -q backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_results.py` — **30 passed**.
- `pytest -q backend/tests/experiments/test_clock.py backend/tests/strategies/test_ema_sweep_confirmation_break.py backend/tests/experiments/test_price_analysis_results.py` — **40 passed**.
- `pytest -q backend/tests/market_data/test_freeze03_regressions.py backend/tests/market_data/test_task3.py backend/tests/risk/test_service.py backend/tests/execution/test_simulated.py` — **61 passed**.
- `pytest -q backend/tests/integration/test_golden_flows.py` — **2 skipped** because `ATLAS_TEST_DATABASE_URL` is unavailable; the fixed deterministic PostgreSQL replay test is present and will execute when the required database is configured.
- Focused Ruff checks and `git diff --check` — **passed**.

### Concerns

- The required database-backed golden replay/equivalence and persistence immutability execution evidence could not run in this environment because `ATLAS_TEST_DATABASE_URL` is unset. No expected outputs were changed.
- Repository status contains the pre-existing T001-T003 workstream changes, `.codegraph/`, and `frontend/.env.local`; T004 did not alter or remove them. No application source, migration, schema, or Git history was changed by T004.
