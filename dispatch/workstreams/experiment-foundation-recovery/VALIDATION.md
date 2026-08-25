# Validation — Experiment Foundation Recovery

## Verdict

**NOT READY / BLOCKED.** The deterministic V2-focused tests pass, and the
frontend checks (apart from formatting) pass. However, the full backend suite
has three implementation-facing historical-load failures and one migration
revision assertion failure. PostgreSQL integration validation and real OANDA
UI acceptance were blocked because `ATLAS_TEST_DATABASE_URL` is unset.

No environment files or credentials were read or modified. No application
code was changed by this validation task.

## Commands and evidence

### Backend deterministic validation

- `python -m pytest -q`
  - **FAIL:** 255 passed, 37 skipped, 4 failed, 15 errors.
  - Three failures are in `backend/tests/test_historical_data_load.py`:
    `test_success_order_is_load_snapshot_m15_then_validation`,
    `test_durable_load_prefers_v2_acquisition_when_available`, and
    `test_v2_warmup_extends_on_actual_native_count_with_session_closures`.
    The coordinator reaches `StrategyRepository.get_version()` with a
    `FakeSession` lacking `get()`, then failure handling reaches a
    `FakeRepository` lacking `fail_if_active()`. This is an actionable
    implementation/test-double contract regression, not an environment skip.
  - The fourth failure is
    `backend/tests/test_migration_revision.py::test_alembic_revision_ids_fit_default_version_column`:
    the test expects head `0011_fix_v2_snapshot_trigger`, while the current
    migration graph correctly reports `0012_required_historical_context`.
  - The 15 integration errors all fail setup because
    `ATLAS_TEST_DATABASE_URL` is not set.

- `python -m pytest -q backend/tests/test_historical_data_load.py`
  - **FAIL:** 11 passed, 1 skipped, 3 failed (the three failures listed above).

- `python -m pytest -q backend/tests/experiments backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/market_data/test_task3.py backend/tests/strategies/test_ema_sweep_engulfing_v2.py backend/tests/experiments/test_price_analysis_results.py backend/tests/experiments/test_results.py`
  - **PASS:** 64 passed.
  - Covers the focused clock/runner diagnostics, V2 snapshot contract,
    strategy V2 behavior, configuration/results contracts, and result
    disclosures.

- `python -m compileall -q backend`
  - **PASS** (no output).

- `python -m ruff check backend`
  - **FAIL:** 7 errors in
    `backend/tests/integration/_run_validation_real_data.py` (unused imports,
    import ordering, and two line-length violations).

- `python -m pyright`
  - **FAIL:** 2094 errors, predominantly strict typing errors in existing
    tests and fake session/repository fixtures, including the historical-load
    test fixtures. No fixes were made.

### Migration validation

- `alembic heads && alembic history --verbose`
  - **PASS (graph inspection):** one linear head,
    `0012_required_historical_context`, parent
    `0011_fix_v2_snapshot_trigger`.

- `python -m pytest -q backend/tests/integration/test_migrations.py backend/tests/test_migration_revision.py`
  - **FAIL/BLOCKED:** 1 failed, 2 skipped. The failure is the stale expected
    head assertion described above; migration integration tests are skipped
    without the dedicated test database.

- `alembic check`
  - **BLOCKED/FAIL:** Alembic reports `Target database is not up to date`.
    No database reset, upgrade, downgrade, or other mutation was attempted.

### Frontend validation

- `npm run test:web -- --run`
  - **PASS:** 9 test files, 23 tests passed.

- `npm run typecheck:web`
  - **PASS.**

- `npm run lint:web`
  - **PASS.**

- `npm run build:web`
  - **PASS:** Next.js production build completed; routes were generated.

- `npm run format:check:web`
  - **FAIL:** Prettier reports 14 files with existing formatting issues,
    including `frontend/components/experiment-workflow.tsx`,
    `frontend/components/strategy-history.tsx`, and generated API code.
    No formatting changes were made.

## V2-only and scope assessment

- The focused V2 suite passed and confirms the implemented bounded sparse
  entry and result-disclosure behavior covered by those tests.
- Current runner source still contains an unreachable legacy V1 block after
  the V2-only dispatch guard, and the historical-load implementation retains
  compatibility seams. This conflicts with the approved V1-removal boundary
  if “remove” is interpreted literally; TASK-03 explicitly prohibited core
  runner changes, so this is reported rather than changed here.
- The current migration head is V2 foundation migration `0012`; the failing
  revision test still asserts the former `0011` head and must be reconciled by
  the implementation workstream.
- Scope was checked against `TASK-01.md`, `TASK-02.md`, `TASK-03.md` file
  receipts and the current source via CodeGraph. Per the tester role
  prohibition, no Git command (including `git diff`) was run; therefore a Git
  diff-based scope check remains outstanding for the orchestrator.

## Integration and OANDA acceptance

- Existing integration tests were attempted in the safe environment and are
  blocked by the absent `ATLAS_TEST_DATABASE_URL` (the project requires a
  dedicated URL ending in `_test`). No credentials or environment files were
  inspected.
- The required real OANDA Practice UI flow is **not executable** in this
  environment: there is no available test database and no confirmed
  credentialed OANDA Practice session. It was not attempted, so there is no
  fabricated run identifier, load status, result, or broker evidence.

## Required follow-up before approval

1. Resolve the three historical-load contract failures and update/align the
   migration-head assertion with migration `0012` (or document an intentional
   alternative).
2. Fix the backend lint and investigate the strict typing baseline.
3. Run migrations and the complete integration/golden flow against a dedicated
   `_test` PostgreSQL database.
4. Run the real OANDA Practice UI acceptance flow with approved credentials,
   recording durable load/run status, result quality/gaps, and provenance.
5. Run the prohibited Git diff scope review in the orchestrator/review phase.
