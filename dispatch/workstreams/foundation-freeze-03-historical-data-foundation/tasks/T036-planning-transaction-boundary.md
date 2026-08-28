# T036 — V2 planning transaction boundary

Status: `DONE`

## Assignment

Fix the remaining REVIEW finding only: complete all V2 planning database reads and
coverage planning before closing the database transaction, then yield provider work.
No generator may yield provider work while holding an open database transaction, and
provider I/O must occur outside all database transactions. Preserve current planning
semantics and progress totals.

Do not reopen T030–T035. Do not change missing-range boundedness, provider chunking,
closure handling, sparse M1, strict native M15, snapshot behavior, or unrelated code.
Add a focused regression proving provider fetch observes no active planning transaction.

## Required checks

- focused transaction-boundary regression;
- affected planning/load unit tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: DONE
FILES CHANGED:
- `backend/market_data/ingestion.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- this receipt
CHECKS / EVIDENCE:
- Focused transaction-boundary regression and related V2 planning regressions: 4 passed.
- Affected historical-load and Freeze 03 regression tests: 44 passed, 1 skipped
  (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed for changed application/test files.
IMPLEMENTATION:
- V2 planning now performs each database planning read inside a short transaction,
  closes the session before exposing the next provider window, and retains only the
  unconsumed pure coalescing iterator between windows.
- Both provider products retain pre-acquisition total planning and existing coverage,
  chunking, closure, and progress semantics.
- Regression source observes the planning session and asserts provider fetch occurs
  with no active planning transaction on the authoritative acquired-window path.
CONCERNS:
- PostgreSQL-backed checks remain skipped because `ATLAS_TEST_DATABASE_URL` is not
  configured; no database reset/delete, timeout change, benchmark, or OANDA call was
  performed.
