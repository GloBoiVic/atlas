# Validation

Status: `PASS WITH BLOCKED ENVIRONMENT EVIDENCE`
Role: `VALIDATE`
Workstream: `foundation-freeze-03-historical-data-foundation`
Branch: `solo/foundation-freeze-03-historical-data-foundation`

Fresh independent validation completed 2026-08-27 from `/Users/vike/Desktop/atlas`.
No implementation files, branches, or Git history were changed. This artifact is
the only file changed by this validation.

## Contract checks

CodeGraph and current-source review, corroborated by focused regressions, confirm:

- `_warmup_plan` has no 40-window or 90-day ceiling; only malformed/invariant inputs
  fail. Readiness is based on observed eligible completed native M15 bars, including
  closure/gap behavior, not wall-clock estimates.
- `HistoricalDataLoadCoordinator.prepare()` does not invoke the legacy shared
  `plan_missing` planner. V2 preparation derives the semantic analytical context and
  leaves independent native-product planning to the V2 path.
- Public metadata describes independent native M15/MID analytical and native M1/
  BID+ASK execution products.
- Native M15 MID is not derived from M1 in the authoritative V2 Experiment path;
  M1 BID/ASK execution observations remain independently planned and reusable.
- Missing-only planning, zero provider calls for fully covered products, completed
  filtering, UTC half-open boundaries/frontier checks, bounded arbitrary-size chunks,
  immutable deterministic snapshot membership, and durable resume/failure semantics
  are covered by source and tests.

## Checks and evidence

- Focused historical-load, V2, storage, OANDA, migration, and configuration suite:
  **61 passed, 1 skipped**.
- Full backend suite: **307 passed, 30 skipped, 13 errors**. The 13 setup errors
  are PostgreSQL-gated tests failing because `ATLAS_TEST_DATABASE_URL` is unset;
  no implementation assertion failure was observed.
- Changed-scope Ruff: **passed**.
- `python -m compileall -q backend`: **passed**.
- `git diff --check`: **passed**.
- Alembic offline generation from repository root: **passed**, 69,775 bytes; head
  includes `0016_load_progress` and emits `DROP CONSTRAINT
  ck_historical_data_load_requests_load_maximum`.

## Actual fixture benchmark

`python -m backend.market_data.freeze03_benchmark` completed successfully and
exercised the actual V2 planner, native provider seam, persistence seam, coverage
validator, snapshot, and fingerprint path. Timings are local deterministic fixture
evidence; the one-year labels are bounded representative windows, not full-year
provider measurements.

| Scenario | M15 calls | M1 calls | Planning | Coverage | Persistence | Snapshot/fingerprint | Total | Inserted / reused | Repeat calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fresh one-month | 24 | 24 | 0.422s | 0.075s | 1.208s | 0.000s / 1.021s | 10.224s | 70,975 / 0 | 0 |
| fresh one-year (representative) | 24 | 24 | 0.351s | 0.074s | 0.895s | 0.000s / 0.956s | 9.203s | 68,126 / 0 | 0 |
| repeat covered one-year | 0 | 0 | 0.854s | 0.217s | 0.934s | 0.000s / 0.983s | 7.048s | 68,126 / 68,126 | 0 |
| interrupted/resumed one-year (representative) | 35 | 24 | 0.671s | 0.077s | 1.003s | 0.000s / 0.947s | 9.733s | 68,126 / 933 | 48 |

Provider timing was separately recorded by the harness: fresh month M15/M1
`0.214s/1.374s`; fresh representative year `0.177s/1.120s`; repeat `0s/0s`;
interrupted/resumed `0.261s/1.029s`.

## Environment-gated evidence

- PostgreSQL-backed migration execution, immutable triggers, repository,
  transaction/resume, and Experiment integration evidence: **BLOCKED**.
  `ATLAS_TEST_DATABASE_URL` is absent. `psql` is installed but no database endpoint
  is configured; `docker info` also fails because the Docker daemon is unavailable.
  Offline SQL generation is evidence of script validity, not actual execution.
- Credentialed OANDA Practice fresh month/year/repeat evidence: **BLOCKED**.
  OANDA credentials are absent; `backend/tests/integrations/test_oanda_external.py`
  results: **1 skipped**. Fixture timings were not substituted for real-provider
  evidence.
- Full-backend Ruff remains outside this validation's clean changed-scope result due
  to unrelated pre-existing findings documented by prior receipts.

## Findings and verdict

No unresolved implementation finding was identified in the T006 remediation scope.
The required warm-up, planner-quarantine, and public-metadata regressions pass.
The overall verdict is **PASS WITH BLOCKED ENVIRONMENT EVIDENCE**: PostgreSQL-backed
and credentialed OANDA acceptance gates remain open until those environments are
available. The disclosed bounded representative fixture limitation also remains.
