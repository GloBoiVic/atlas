# T037 — Bounded V2 missing-range planning

Status: `DONE`

## Assignment

Fix the remaining REVIEW finding only: remove request-sized list/tuple accumulation
from the authoritative V2 planning path. Stream/coalesce missing spans incrementally,
retaining only bounded current frontier/state and bounded diagnostics. Preserve closure
handling, acquisition-window union subtraction, strict native M15 semantics, and OANDA
provider chunk bounds.

Do not reopen T030–T036. Do not change transaction boundaries, snapshot behavior,
sparse M1 semantics, progress totals, or unrelated code. Add a focused regression proving
large/disjoint missing-range planning does not materialize request-sized collections.

## Required checks

- focused bounded planning regression;
- affected planning/load/repository tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: DONE
FILES CHANGED:
- `backend/persistence/market_data_repository.py`
- `backend/market_data/ingestion.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- `backend/tests/integration/test_market_data_repositories.py`
- this receipt
CHECKS / EVIDENCE:
- Focused large/disjoint missing-range regression: 1 passed.
- Affected planning/load tests: 45 passed, 1 skipped (database-gated).
- Repository/ingestion integration tests: 11 skipped (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed for changed application/test files.
IMPLEMENTATION:
- Repository missing-range planning now yields one-minute spans from the ordered row
  frontier; application coalescing retains only its current span and provider bound.
- V2 planning consumes one next window inside each short planning transaction and
  replans from the frontier, so no database-backed range iterator survives closure and
  no request-sized missing-range collection is retained.
- Closure filtering, acquisition-window union subtraction, native M15 semantics,
  provider bounds, progress totals, and snapshot behavior remain unchanged.
CONCERNS:
- PostgreSQL-backed checks remain skipped because `ATLAS_TEST_DATABASE_URL` is not
  configured; no database reset/delete, timeout change, benchmark, OANDA call, branch,
  or Git history operation was performed.
