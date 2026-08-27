# Validation

Status: `PASS`
Role: `VALIDATE`
Workstream: `foundation-freeze-03-historical-data-foundation`
Branch: `solo/foundation-freeze-03-historical-data-foundation`

Fresh final validation ran 2026-08-27 from `/Users/vike/Desktop/atlas`. Repository
root, CWD, and branch were verified. CodeGraph was queried before source/artifact
review. Root `.env` was loaded without printing values; no credentials or OANDA
response bodies were exposed. Only this artifact was overwritten.

## Database and migrations

- PostgreSQL was reachable using the configured root `.env`.
- `alembic current`: `0018_acquisition_windows (head)`.
- `alembic heads`: `0018_acquisition_windows (head)`.
- `alembic check`: passed (`No new upgrade operations detected`).
- The full backend suite exercised the migration-cycle teardown and passed.

## Genuine full-calendar-year V2 evidence

Verified the already-produced exact half-open request
`[2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z)` and unchanged covered repeat.

- Snapshot ID: `8bc3149e-94bc-49b6-a5d2-3f409cf87088`
- Fingerprint: `b0f7c522b390af988a3a33169fc853871a282d4c93804c452f018a4078491c90`
- Snapshot bounds, normalized to UTC, are exactly `2025-01-01T00:00:00Z` and
  `2026-01-01T00:00:00Z`.
- Analytical membership: `24,605` native `M15/MID` rows; no M1-derived M15
  membership.
- Execution membership: `740,226` rows, exactly `370,113 BID` and `370,113 ASK`
  observations, with no membership outside the requested range.
- Acquisition provenance: `927` `M1`, `BID+ASK`,
  `SUCCESS_EMPTY_OR_SPARSE` windows; no failure/unknown windows. Sparse M1
  continuity remains explicitly allowed (`1,293` sparse missing minutes), with
  no fabrication or forward fill.
- Integrity summary is `VALID`, analytical contract is
  `OANDA_M15_NATIVE_UTC_V1`, and execution continuity is `SPARSE_ALLOWED`.
- A repeat `MarketDataService.load_v2` run using a counting OANDA source made
  exactly `0` M15 and `0` M1 provider calls and returned the same snapshot ID and
  fingerprint.

## Tests and benchmark

- Full backend suite with configured root `.env`: **354 passed, 1 skipped, 4
  warnings** in 197.04s.
- Focused T016/migration/frontier/regression suite: **27 passed** in 39.21s.
- Fixture benchmark completed: fresh month `24 M15 / 24 M1` calls and `70,975`
  inserts; representative year `24 / 24` calls and `68,126` inserts; covered
  repeat `0 / 0` calls and `68,126` reused with identical fingerprint;
  interrupted/resumed scenario `48` repeat calls and `933` reused.
- `git diff --check`: passed.

## Verdict

`PASS`: full suite is green, migrations are at current head, stale frontier and
migration assertions/teardown are fixed, and genuine full-year native/sparse V2
snapshot and zero-call repeat evidence remain intact.

Environment gates: none for the requested validation. The four existing warnings
(Starlette/httpx deprecation and three unregistered `price_analysis` marks) are
non-functional and non-blocking; no critical or important findings remain.

ROLE: VALIDATE
STATUS: PASS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md`
FILES CHANGED: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md`
CHECKS / EVIDENCE: CodeGraph-first review; PostgreSQL; Alembic current/heads/check; full backend suite; focused reconciliation suite; fixture benchmark; exact full-year snapshot, provenance, membership, fingerprint, and zero-call repeat
FINDINGS / CONCERNS: No critical or important findings; four pre-existing non-functional pytest warnings
