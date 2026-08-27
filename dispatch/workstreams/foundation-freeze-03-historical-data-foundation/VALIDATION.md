# Validation

Status: `BLOCKED`
Role: `VALIDATE`
Workstream: `foundation-freeze-03-historical-data-foundation`
Branch: `solo/foundation-freeze-03-historical-data-foundation`

Validation ran 2026-08-27 from `/Users/vike/Desktop/atlas`. Repository root,
CWD, and branch were verified. CodeGraph was queried first. No credentials or
provider response bodies were exposed. Only this artifact was changed.

## Migration and durable database

- Alembic declared and applied head: `0017_session_policy_v2` (`alembic heads`,
  `alembic current`).
- `alembic check`: passed (`No new upgrade operations detected`).
- The authorized disposable database was not reset. It contained durable partial
  T012 coverage, but no `historical_data_load_requests`, no StrategyVersion rows,
  and no snapshots. Consequently the coordinator/API lifecycle could not create a
  request; the unchanged V2 ingestion service was resumed directly from persisted
  observations, without changing implementation or data.

## Genuine OANDA V2 full-year attempt

Exact half-open range: `[2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z)`.

The direct V2 load resumed existing native M15 coverage, then acquired native
M15/MID and M1/BID+ASK missing ranges from OANDA Practice. Provider calls were
counted by a wrapper around the unchanged source; no credentials were printed.

| attempt | elapsed | M15 calls | M1 calls | result |
|---|---:|---:|---:|---|
| resumed full-year load | 740.957 s | 181 | 259 | invalid, no snapshot |
| exact unchanged repeat | 415.393 s | 0 | 927 | invalid, no snapshot |

The repeat was attempted after the first load. It did **not** prove zero calls:
the request was not covered and the remaining execution gaps caused 927 M1
provider calls. No M15 calls were needed on the repeat.

## Persisted coverage and classification

Final canonical current rows:

| native product | rows | earliest | latest |
|---|---:|---|---|
| M15/MID | 24,605 | 2025-01-01T22:15Z | 2025-12-31T21:45Z |
| M1/BID | 370,113 | 2025-01-01T22:05Z | 2025-12-31T21:58Z |
| M1/ASK | 370,113 | 2025-01-01T22:05Z | 2025-12-31T21:58Z |

The V2 execution coverage report after the attempt reported 371,406 expected
open minutes, 154,194 expected closure minutes, 370,113 complete member
minutes, and 1,293 missing minutes. Closure anomalies: 0. Unexpected
observations: 0. The 1,293 gaps are scattered expected-session acquisition
incompleteness, not provider/session closures; no bars were fabricated,
forward-filled, or derived from M1.

Snapshot/fingerprint: **none / none**. Snapshot creation correctly remained
blocked by incomplete execution coverage. The database has 0 snapshots and 0
load-request rows after the run.

## Tests and benchmark

- Focused historical-data, migration, OANDA, ingestion, and market-data suite:
  **90 passed, 9 skipped** in 70.68s.
- Full backend suite excluding external credentials:
  **309 passed, 29 skipped, 1 deselected, 2 failed, 13 errors** in 149.29s.
  Failures were the stale expected migration-head assertion (`0016` versus the
  applied `0017`) and the native analytical-frontier diagnostic assertion.
  Errors were integration fixtures requiring the absent exported
  `ATLAS_TEST_DATABASE_URL`. No test reset the authorized database.
- Fixture benchmark completed successfully. Required unchanged fixture repeat:
  0 M15 calls, 0 M1 calls, 0 repeat calls, 68,126 reused, fingerprint
  `67e7eaf974274ac97e4d8f221d683e9c474426dfb338fd5196f7651ed8142f6f`, total
  10.093s. This is deterministic fixture evidence, not live full-year proof.
- `git diff --check`: passed.

## Verdict

`BLOCKED`: OANDA returned/persisted 1,293 scattered execution gaps, so the
full-year native products are not valid, no immutable snapshot/fingerprint was
created, and the unchanged live repeat made 927 calls rather than zero. The
authorized database also lacks a durable load request/StrategyVersion needed to
record the coordinator lifecycle. No implementation or branch/history changes
were made.

ROLE: VALIDATE
STATUS: BLOCKED
ARTIFACT: dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md
FILES CHANGED: dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md
CHECKS / EVIDENCE: CodeGraph-first; migration head/current/check; genuine OANDA attempts; persisted row counts and coverage; 90-pass focused suite; full backend results; fixture benchmark; diff check
FINDINGS / CONCERNS: 1,293 acquisition gaps remain; snapshot and zero-call live repeat are unproven; durable request and StrategyVersion rows are absent
