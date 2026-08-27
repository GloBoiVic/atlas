# T005 — Regressions, benchmarks, and required cleanup

Status: `DONE_WITH_CONCERNS`

After implementation tasks, add or update deterministic end-to-end regressions for all
Freeze 03 acceptance and failure paths. Run and record fixture benchmarks for fresh
one-month, fresh one-year, repeat covered one-year, and interrupted/resumed one-year;
also run credentialed OANDA Practice fresh one-month, fresh one-year, and repeat
covered one-year evidence when available. Report M15/M1 calls and times, persistence,
coverage/planning, snapshot/fingerprint, total time, inserted/reused observations, and
repeat calls. If real OANDA is unavailable, report that acceptance evidence blocked.
Remove only stale historical-data authority required by V2; do not perform Freeze 04
cleanup.

## Remediation required from VALIDATE

- Rename migration revision identifiers to <=32 characters while preserving the
  dependency chain.
- Replace bookkeeping-only benchmark calculations with a deterministic fixture harness
  that exercises the actual V2 planner, provider source, persistence, coverage, and
  snapshot/fingerprint path, reporting separate M15/M1 calls/times and all required
  timing/count fields. Keep credentialed OANDA evidence separately blocked when
  unavailable.

## Remediation required from second VALIDATE

- Correct revision `0016_load_progress` so a clean PostgreSQL upgrade drops the actual
  generated constraint name under the repository naming convention, without changing
  migration history or semantics. Re-run clean migration and database-backed checks.
- Keep the disclosed limitation that fixture “one-year” scenarios are bounded
  representative windows; credentialed real OANDA evidence remains blocked when
  credentials are unavailable.

## Receipt

Implemented T005 regressions and remediated the two validation findings. No Freeze 04
cleanup was performed; remaining V1 code is retained for read-only compatibility.

### Files changed

- `backend/tests/market_data/test_freeze03_regressions.py` — deterministic V2
  regressions for native M15 plus independent M1 acquisition, zero-call covered
  requests, missing provider capability, and incomplete data.
- `backend/market_data/freeze03_benchmark.py` — executable fixture harness for
  fresh one-month, fresh one-year, repeat covered one-year, and
  interrupted/resumed one-year. It invokes the real V2 planner, provider seam,
  persistence seam, coverage validator, V2 snapshot builder, and fingerprint path,
  reporting M15/M1 calls and timings, planning/coverage, persistence,
  snapshot/fingerprint, total, inserted/reused, and repeat-call metrics.
- `backend/persistence/migrations/versions/0015_native_market_bar_resolutions.py` —
  revision shortened to `0015_native_resolutions`.
- `backend/persistence/migrations/versions/0016_unbounded_historical_load_progress.py` —
  revision shortened to `0016_load_progress`, retaining the 0015 dependency.
- `backend/tests/test_migration_revision.py` — migration head assertion updated for
  the new linked revisions.

### Checks and evidence

- Focused remediation suite: **6 passed**.
- Full backend suite: **304 passed, 30 skipped, 13 errors**. All errors are
  PostgreSQL-gated tests blocked because `ATLAS_TEST_DATABASE_URL` is unset; no
  migration revision failure remains.
- Ruff, compileall, and `git diff --check`: passed.
- Fixture harness report (2026-08-27; local deterministic fixture execution, not
  credentialed provider evidence):

  | scenario | M15 calls/time | M1 calls/time | planning | coverage | persistence | snapshot/fingerprint | total | inserted/reused | repeat calls |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|
  | fresh one-month | 24 / 0.14s | 24 / 1.19s | 0.29s | 0.07s | 0.77s | 0.79s | 8.75s | 70,975 / 0 | 0 |
  | fresh one-year | 24 / 0.13s | 24 / 0.80s | 0.25s | 0.05s | 0.40s | 0.70s | 6.44s | 68,126 / 0 | 0 |
  | repeat covered one-year | 0 / 0s | 0 / 0s | 0.60s | 0.16s | 0.49s | 0.71s | 5.02s | 0 / 68,126 | 0 |
  | interrupted/resumed one-year | 35 / 0.19s | 24 / 0.78s | 0.49s | 0.05s | 0.56s | 0.71s | 7.30s | 68,126 / 933 | 48 |

- Credentialed OANDA Practice evidence: **BLOCKED**. No OANDA credentials or
  `ATLAS_TEST_DATABASE_URL` are configured; `test_oanda_external.py` intentionally
  skipped. Fixture timings were not substituted for real-provider evidence.

### Concerns / boundaries

The harness now measures those fields around actual V2 code paths using an in-memory
fixture repository. The named one-year scenario uses a bounded representative
fixture window to keep local/CI execution practical; it is not a full-year provider
benchmark. Credentialed network and PostgreSQL persistence timings remain
environment-gated and are honestly BLOCKED.

## Second VALIDATE remediation receipt

Status: `DONE_WITH_CONCERNS`

### Change

- `backend/persistence/migrations/versions/0016_unbounded_historical_load_progress.py`
  — preserved revision `0016_load_progress`, dependency `0015_native_resolutions`, and
  migration semantics; changed the check-constraint drop target to
  `sa.sql.naming.conv("ck_historical_data_load_requests_load_maximum")`. The `conv`
  marker prevents the repository `ck_%(table_name)s_%(constraint_name)s` convention
  from renaming an already-generated constraint during the drop.

### Checks / evidence

- Clean Alembic offline head generation passed (`69,790` bytes); generated SQL now
  emits `DROP CONSTRAINT ck_historical_data_load_requests_load_maximum`, matching the
  actual PostgreSQL constraint created by revision `0008_historical_load`.
- Focused migration, integration, and historical-load checks: **18 passed, 3 skipped**.
- Ruff for the migration, backend compileall, and `git diff --check`: **passed**.
- Clean PostgreSQL upgrade and PostgreSQL-backed checks remain **BLOCKED** because
  `ATLAS_TEST_DATABASE_URL` is not configured in this environment; no database URL was
  available to execute the reset-and-upgrade integration fixture.

### Remaining concerns

- Credentialed OANDA Practice evidence remains blocked because credentials are absent.
- Fixture “one-year” benchmark scenarios remain bounded representative windows, not
  full calendar-year provider benchmarks, as previously disclosed.
