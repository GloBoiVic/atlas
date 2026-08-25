# Final Validation — Experiment Foundation Recovery

## Verdict

**BLOCKED — not acceptance-ready.** The focused V2 deterministic path and all
requested frontend quality gates pass, but the full deterministic backend run
has a stale migration-head assertion failure. Database-backed integration and
PostgreSQL migration-state validation remain unavailable, and the required
credentialed OANDA Practice UI acceptance was not performed.

## Inputs and scope

- Approved context: `PLAN.md`, `ARCHITECTURE.md`, `READY.md`.
- Implementation receipts: `TASK-01` through `TASK-07`.
- Prior validation/reviews: `VALIDATION-R2.md`, `REVIEW.md`, `REVIEW-R1.md`.
- Current source was inspected with CodeGraph, including the V2 runner,
  configuration boundary, terminal protection, and result-quality path.
- No application code, environment files, credentials, databases, or other
  dispatch artifacts were modified. No Git commands were run.

## Exact validation results

### Affected V2/configuration/runner/result and foundation tests

- `python -m pytest -q backend/tests/experiments/test_clock.py backend/tests/experiments/test_configuration.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/market_data/test_task3.py backend/tests/strategies/test_ema_sweep_engulfing_v2.py backend/tests/domain/test_strategy_requirements.py backend/tests/test_historical_data_load.py`
  - **PASS:** 99 passed, 1 skipped in 97.33s.

### Full deterministic backend suite

- `python -m pytest -q -m 'not integration and not external'`
  - **FAIL:** 261 passed, 4 skipped, 49 deselected, 1 failed in 128.54s.
  - Failure: `backend/tests/test_migration_revision.py::test_alembic_revision_ids_fit_default_version_column` expects head
    `0012_required_historical_context`, while the current graph correctly has
    `0013_result_quality_degraded` as its head. This is a validation/test
    contract mismatch and remains an acceptance blocker.

### Backend static checks

- `python -m ruff check backend && python -m compileall -q backend`
  - **PASS:** Ruff and compileall completed without errors.

### Migration graph and database check

- `alembic heads && alembic history --verbose`
  - **PASS (graph):** one linear head, `0013_result_quality_degraded`, parent
    `0012_required_historical_context`; history is linear through `0001`.
- `alembic check`
  - **BLOCKED/FAIL:** `Target database is not up to date`.
  - No upgrade, downgrade, reset, or other database mutation was attempted.
- Database-backed integration tests were not runnable because the required
  dedicated `_test` PostgreSQL environment is unavailable. No database
  credentials or environment files were read.

### Frontend

- `npm run test:web -- --run`
  - **PASS:** 9 files, 23 tests.
- `npm run typecheck:web`
  - **PASS.**
- `npm run lint:web`
  - **PASS.**
- `npm run build:web`
  - **PASS:** Next.js production build completed and routes were generated.
- `npx prettier --check frontend/components/experiment-workflow.tsx frontend/components/strategy-history.tsx frontend/lib/api.generated.ts frontend/tests/experiment_results.test.tsx`
  - **PASS:** all changed frontend files use Prettier code style.

## Acceptance disposition

Deterministic V2 behavior is supported by the focused suite, including the
bounded entry policy, independent frontiers, terminal fail-closed behavior,
configuration V2 boundary, result quality, and provenance paths. This does not
substitute for the blocked persistence acceptance gates.

The PostgreSQL golden lifecycle, migration application against the dedicated
`_test` database, and real OANDA Practice browser UI acceptance are **blocked**
while the required environment remains unavailable. No OANDA run identifier,
database result, or UI outcome is inferred or fabricated. The workstream must
remain blocked until the migration assertion is aligned with head `0013`, a
dedicated `_test` PostgreSQL database proves the lifecycle, and the OANDA
Practice UI flow is completed or explicitly accepted as environment-blocked by
the approving human.
