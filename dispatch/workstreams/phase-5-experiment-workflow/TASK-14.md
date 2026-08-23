# TASK-14 — E2E lifecycle persistence diagnostic

## Outcome

**Stopped after diagnosis; no corrective change was made.** The default-off
lifecycle diagnostic was added and the direct PostgreSQL comparison passed for
both cases. The serial primary E2E case still failed, while the serial
zero-Trade E2E case reached a durable completed result but failed its existing
selector assertion.

## Diagnostic contract and implementation

- Added the closed six-key `ExperimentLifecycleDiagnostic` record with exactly:
  `stage`, `exception_class`, `sqlstate`, `show_time_zone`, `backend_pid`, and
  `alembic_revision`.
- Added exactly the seven approved stages and allow-listed exception/SQLSTATE
  extraction. Unknown classes become `UNCLASSIFIED_EXCEPTION`; malformed
  SQLSTATE, timezone, PID, or revision values become the specified null/
  `UNAVAILABLE` values.
- Metadata is read from the same connection using a diagnostic savepoint. Sink
  and metadata failures are swallowed without changing lifecycle behavior.
- Production `create_app` has no sink by default. `backend.tests.e2e_app` is
  the guarded adapter and emits only compact `ATLAS_E2E_LIFECYCLE` JSON when
  `ATLAS_E2E_LIFECYCLE_DIAGNOSTIC=1` and the effective database is `*_test`.
- Task 12's runner diagnostic remains separate and unchanged. No runner,
  repository, model, migration, schema, route, or frontend semantic change
  was made.

## Exact receipts

### Unit, lifecycle, lint, and default-off checks

```text
pytest -q backend/tests/experiments/test_lifecycle_diagnostics.py backend/tests/experiments/test_runner_diagnostics.py
5 passed in 0.85s

pytest -q backend/tests/experiments/test_lifecycle_diagnostics.py backend/tests/integration/test_experiment_lifecycle.py
7 passed in 97.59s

ruff check backend/experiments/lifecycle.py backend/api/app.py backend/tests/e2e_app.py backend/tests/integration/test_phase5_valid_run.py backend/tests/experiments/test_lifecycle_diagnostics.py
All checks passed!

ATLAS_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' python -c 'from backend.api.app import create_app; app=create_app(); assert app.state.experiment_lifecycle._diagnostic_sink is None; print("default-off: no sink")'
default-off: no sink
```

The hostile unit case included marker SQL, credentials, a source path, and a
traceback-like message. The exact six-key serialization contained none of it;
the hostile exception's message was not formatted. Existing lifecycle tests
continued to pass with sanitized durable/API outcomes. No diagnostic data is
persisted or returned.

### Direct comparison under non-UTC host TZ

```text
TZ=America/Los_Angeles ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' pytest -s -q backend/tests/integration/test_phase5_valid_run.py
2 passed in 34.89s
```

Both the primary (`START + 1500` through `START + 1590`) and zero-Trade
(`START + 1500` through `START + 1515`) candidates completed and retained the
existing direct-vs-baseline semantic assertions. The in-memory lifecycle
collector recorded these exact sequences:

```text
Primary:   RUNNER_RETURN(null) → FLUSH(null) → COMMIT(null) → FINAL_READ(null)
Zero-Trade: RUNNER_RETURN(null) → FLUSH(null) → COMMIT(null) → FINAL_READ(null)
```

Every direct event reported `show_time_zone=UTC` and
`alembic_revision=0007_phase_5_metric_contract`. Primary candidate PID was
`45598`; zero-Trade candidate PID was `45606`; each PID was continuous across
its four events. No SQLSTATE or exception class was present.

### Serial primary E2E diagnostic

```text
TZ=America/Los_Angeles ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' ATLAS_E2E_FIXTURE_FILE='/tmp/atlas-e2e-primary.json' ATLAS_E2E_LIFECYCLE_DIAGNOSTIC=1 npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'configures, runs' --workers=1
1 failed: expected Completed, received FAILED; timeout after 120000ms
```

Allow-listed lifecycle lines only:

```text
RUNNER_RETURN: exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45052 alembic_revision=0007_phase_5_metric_contract
FLUSH:         exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45052 alembic_revision=0007_phase_5_metric_contract
COMMIT:        exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45052 alembic_revision=0007_phase_5_metric_contract
FINAL_READ:    exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45052 alembic_revision=0007_phase_5_metric_contract
```

Final durable/API outcome: `FAILED`, category `PERSISTENCE`, code
`PERSISTENCE_FAILURE`, sanitized detail `Experiment persistence failed`, with
no result. There were no fallback events. The lifecycle therefore observed a
runner return without a thrown exception, then a successful flush, commit, and
fresh final read; the record contract does not and must not expose the
runner-return status.

### Serial zero-Trade E2E diagnostic

```text
TZ=America/Los_Angeles ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' ATLAS_E2E_FIXTURE_FILE='/tmp/atlas-e2e-zero.json' ATLAS_E2E_LIFECYCLE_DIAGNOSTIC=1 npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'valid zero-Trade' --workers=1
1 failed: existing locator strict-mode assertion; backend result completed
```

Allow-listed lifecycle lines only:

```text
RUNNER_RETURN: exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45305 alembic_revision=0007_phase_5_metric_contract
FLUSH:         exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45305 alembic_revision=0007_phase_5_metric_contract
COMMIT:        exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45305 alembic_revision=0007_phase_5_metric_contract
FINAL_READ:    exception_class=null sqlstate=null show_time_zone=UTC backend_pid=45305 alembic_revision=0007_phase_5_metric_contract
```

Final durable/API outcome: `COMPLETED`, result/equity present, Trade Count 0.
The test failed because `getByText('Completed')` resolved both the status and
the explanatory text, not because of persistence. There were no exception
classes or SQLSTATEs. The bounded two-worker reproduction was **not run**:
the blueprint permits it only when both serial E2E cases pass.

## Comparison and diagnosis

- **Proven facts:** direct primary and zero-Trade lifecycle paths pass under
  `TZ=America/Los_Angeles`; both report UTC, live revision `0007_phase_5_metric_contract`,
  and continuous per-run PIDs. The primary E2E path reaches and durably commits
  a failed result through a normal lifecycle event sequence, with no thrown
  lifecycle exception. The zero-Trade E2E backend path completes in isolation.
- **Inference:** the primary E2E divergence occurs inside the runner's returned
  terminal result or its E2E composition inputs, rather than at lifecycle
  flush, primary commit, fallback, connection timezone, or live migration
  revision. Confidence: medium; the closed lifecycle record intentionally
  cannot identify a runner-internal caught exception.
- **Not proven:** exact runner operation, SQL statement, SQLSTATE, fixture
  mismatch, or concurrency cause. No two-worker evidence exists.
- **Root cause:** not proven. The smallest next corrective scope, if separately
  approved, is the runner-return/E2E composition boundary with the existing
  Task 12 runner diagnostic kept out of public and durable surfaces; no
  correction is authorized by this task.

## Changed files

- `backend/experiments/lifecycle.py`
- `backend/api/app.py` (sink injection only; pre-existing Phase 5 changes preserved)
- `backend/tests/e2e_app.py`
- `playwright.config.ts` (explicit diagnostic factory/stdout selection)
- `backend/tests/experiments/test_lifecycle_diagnostics.py`
- `backend/tests/integration/test_phase5_valid_run.py`

## Forbidden-operation confirmation

No Git mutation, dependency installation, browser installation, migration
generation/execution outside the existing E2E seed, schema/model/database
change, central UTC policy change, server/database/role-default change,
runner correction, Phase 6/PAPER/LIVE work, production logging change, API
response change, frontend change, or validation/review artifact change was
performed. Known uncommitted work was preserved. The task terminates here as
required; no corrective fix or full validation/review was started.
