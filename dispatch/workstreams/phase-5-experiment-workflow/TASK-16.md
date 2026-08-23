# TASK-16 — Isolated E2E restore, diagnosis, and bounded correction

## Outcome

The isolated E2E PostgreSQL environment was restored and verified. The approved
diagnostics identified one narrow Phase 5/API composition mismatch. Exactly one
corrective source change was made: the application session factory now uses
autoflush, matching the direct lifecycle path used by the Phase 4 runner.

The primary and zero-Trade browser workflows now both complete on the backend.
The browser commands still fail on pre-existing status selectors: the primary
assertion matches two visible `Completed` texts, and the zero-Trade header
selector does not match the rendered status badge. No second correction was
made because this task's one-fix limit was reached.

## Database safety, provisioning, and targeting

- The only database used was `atlas_test`; the configured and server-reported
  database names were compared before migration, seed, or truncation.
- The safety check required the URL database name to end in `_test`, required
  the exact local test database name, and verified `current_database()` before
  any destructive setup operation.
- Existing `backend.tests.e2e_seed` was used unchanged as the provisioning
  mechanism. Its existing Alembic upgrade, deterministic fixture seed, and
  test-only truncate path were used only after the safety check.
- Post-seed verification passed: PostgreSQL session timezone was `UTC`, the
  Alembic revision was `0007_phase_5_metric_contract`, and the expected seeded
  StrategyVersion, primary/zero DatasetSnapshots, and immutable membership were
  present.
- API composition was verified against the same `atlas_test` database and the
  production `ExperimentRunner` composition. No OANDA credential or network
  access was used.

## Diagnostic receipts and closed outcomes

Safe lifecycle diagnostics were enabled only through the guarded test factory.
Runner comparison diagnostics emitted only their closed allow-listed fields;
no exception text, SQL, credentials, paths, UUIDs, or raw payloads were used in
this report.

- Before the correction, the direct Phase 5 integration comparison passed for
  both primary and zero-Trade inputs, while the API-composed primary returned a
  sanitized persistence failure during the entry attempt. The zero-Trade API
  path completed.
- UTC, Alembic revision, and lifecycle commit/final-read diagnostics were
  healthy in both browser cases. No SQLSTATE or exception class was emitted.
- The runner comparison showed equivalent Strategy, snapshot, membership,
  parameters, Risk, simulation, period, capital, financial projection, and
  effective execution inputs. The first divergence was therefore the
  application session-factory behavior at the entry-fact read boundary, not a
  dataset, clock, session-policy, or Phase 4 semantic mismatch.
- This narrowed the fix to `backend/persistence/database.py`: the API-created
  session factory had `autoflush=False`, unlike the direct integration
  lifecycle session. Pending entry facts were consequently unavailable to the
  runner's dependent reads in the API composition; zero-Trade never exercised
  that boundary.

## Corrective fix and regression

Changed exactly one application file for the correction:

- `backend/persistence/database.py` — `create_session_factory` now creates
  sessions with `autoflush=True`; the existing UTC connection policy remains
  unchanged.

This is local to application session composition. It does not alter Strategy,
Risk, aggregation, clock/frontier, execution pricing, Fill/Position/Trade
accounting, result methodology, session policy, or Phase 4 facts/fingerprints.
The focused API-process smoke regression reproduced the primary create/run path
with the production app and completed successfully after the change.

Focused receipt:

```text
TZ=America/Los_Angeles pytest -q \
  backend/tests/integration/test_phase5_valid_run.py \
  backend/tests/integration/test_api_experiments.py
6 passed, 1 pre-existing warning
```

## E2E receipts after correction

Both scenarios were rerun serially against the restored isolated database with
the approved lifecycle and runner diagnostics enabled:

- Primary: API created the Experiment, coverage validation returned success,
  the runner returned `COMPLETED`, lifecycle flush/commit/final-read were
  successful, and result/equity/Trade reads returned successfully. The test
  failed only because its broad `getByText('Completed')` assertion matched two
  elements.
- Zero-Trade: API created the Experiment, coverage validation returned success,
  the runner returned `COMPLETED`, lifecycle flush/commit/final-read were
  successful, and result/equity/Trade-list reads returned successfully. The
  test failed only because its existing exact header status selector did not
  match the rendered badge.

No backend `FAILED` result, diagnostic exception, SQLSTATE, or persistence
failure remained in either affected scenario after the correction.

## Remaining blockers and Phase 5 readiness

Phase 5 is not ready for validation/review. The two focused browser assertions
remain red and require a separately bounded selector alignment pass. Full E2E,
full Phase 5 validation, and review were not started.

## Forbidden-operation confirmation

No non-test database was migrated, seeded, truncated, or otherwise modified.
No server/database/role default was changed. No Git operation, dependency or
browser installation, schema/migration change, Phase 4 semantic change,
PAPER/LIVE or Phase 6 work, full validation, or review operation was performed.
Only the isolated test database and the assigned `TASK-16.md` report were
written for this task; known pre-existing working-tree changes were preserved.
