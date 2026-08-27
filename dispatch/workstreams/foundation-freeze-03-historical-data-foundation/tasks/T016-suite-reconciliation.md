# T016 — Suite reconciliation after sparse semantics

Status: `DONE`

Reconcile the remaining full-suite failures with the approved current contracts:
update stale migration-head/table expectations for head `0018_acquisition_windows`,
update the native analytical-frontier diagnostic assertion, and make migration-cycle
teardown safely remove disposable V2 snapshot state before downgrade without weakening
immutable-facts protections. Preserve the successful live sparse snapshot/repeat
semantics. Run the full backend suite and relevant live evidence again; do not expose
secrets or change migration semantics merely for stale fixtures.

## Implementation

- Reconciled migration-cycle table expectations and revision-head assertion with
  `0018_acquisition_windows`.
- Updated the native analytical-frontier diagnostic to treat the 2026-01-01
  closed-session frontier as non-missing under the approved session semantics.
- Migration-cycle teardown now truncates disposable test snapshot state through
  the established `TRUNCATE ... CASCADE` fixture path; the V2-policy downgrade
  guard rejects durable `OANDA_FX_NY_V2` snapshots. Immutable-facts triggers
  remain unchanged.

## Checks / evidence

- Ruff check on the three changed Python implementation/test files: passed.
- Focused migration/diagnostic tests: **19 passed**.
- Full backend suite with configured root `.env`: **354 passed, 1 skipped, 4 warnings** in 215.69s. No credentials or provider response bodies were printed.
- Fixture benchmark: fresh month **24 M15 / 24 M1 calls**, 70,975 inserts; representative year **24 M15 / 24 M1 calls**, 68,126 inserts; covered repeat **0 / 0 provider calls**, 68,126 reused, identical fingerprint; interrupted-resumed year **48 repeat calls**, 933 reused.
- Preserved genuine full-calendar-year V2 evidence from `VALIDATION.md`: exact half-open `[2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z)` snapshot `8bc3149e-94bc-49b6-a5d2-3f409cf87088`, fingerprint `b0f7c522b390af988a3a33169fc853871a282d4c93804c452f018a4078491c90`; unchanged repeat made **0 OANDA calls** and reused **24,605 analytical + 740,226 execution memberships**.

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T016-suite-reconciliation.md`
FILES CHANGED: `backend/tests/integration/test_migrations.py`, `backend/tests/experiments/test_runner_diagnostics.py`, `backend/tests/test_migration_revision.py`, `backend/persistence/migrations/versions/0017_session_policy_v2.py`, this receipt
CHECKS / EVIDENCE: CodeGraph-first; root/CWD/branch verified; focused tests; full backend suite; Ruff; fixture benchmark; preserved genuine full-year snapshot and zero-call repeat evidence
FINDINGS / CONCERNS: Four existing non-fatal pytest warnings (Starlette httpx deprecation and unknown `price_analysis` mark); no functional failures
