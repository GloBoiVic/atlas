# T030 — Atomic acquisition commit boundary

Status: `COMPLETE WITH CONCERNS`

## Assignment

Fix REVIEW finding 1 only. Canonical observation persistence and the successful
acquisition-window outcome must commit in one short transaction. Provider I/O remains
outside the transaction. Preserve idempotency and failure semantics. Add focused
interruption/crash-boundary coverage for both commit orderings or the narrowest
deterministic equivalent that proves neither partial durable outcome can be reported.

Do not change provider chunking, sparse semantics, native M15 semantics, progress phase
semantics, Experiment validation, completion handling, terminal metrics, or unrelated
architecture. Use existing repository/session boundaries; no new abstraction framework.

## Required checks

- focused atomicity/interruption regressions;
- affected historical-load and repository tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: COMPLETE WITH CONCERNS
FILES CHANGED:
- `backend/market_data/ingestion.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T030-atomic-acquisition-commit.md`
CHECKS / EVIDENCE:
- Focused V2 atomicity/interruption tests: 3 passed.
- Full Freeze 03 regression module: 17 passed.
- Historical-load and repository tests: 22 passed, 7 skipped (database-gated).
- Historical ingestion integration tests: 5 skipped (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed for changed application/test files.
IMPLEMENTATION:
- Provider I/O remains outside the database transaction.
- Canonical observation application and successful acquisition-window recording now
  share one short `session.begin()` boundary; completion/progress follows commit.
- Persistence and acquisition-record interruptions are deterministically tested to
  leave no partial durable outcome; existing failure recording and idempotent
  repository methods remain unchanged.
CONCERNS:
- Full `ruff check backend` still reports 46 pre-existing E501 violations in
  unrelated files; no unrelated formatting changes were made.
- Database-backed integration tests were skipped because the test database URL was
  not configured.
