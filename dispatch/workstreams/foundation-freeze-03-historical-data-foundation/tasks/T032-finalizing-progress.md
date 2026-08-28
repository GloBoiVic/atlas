# T032 — Durable FINALIZING progress phase

Status: `DONE`

## Assignment

Fix REVIEW finding 3 only. Emit and durably record the frozen `FINALIZING` progress
phase at the existing finalization boundary, preserving bounded payloads and the
existing phase order. Add a focused lifecycle/progress regression.

Do not change acquisition semantics, persistence atomicity, Experiment validation,
completion handling, terminal metrics, or unrelated architecture.

## Required checks

- focused FINALIZING emission/persistence regression;
- affected historical-load tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: DONE
FILES CHANGED:
- `backend/market_data/ingestion.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T032-finalizing-progress.md`
CHECKS / EVIDENCE:
- Focused FINALIZING emission/persistence regression: 1 passed.
- Focused adjacent progress regression: 1 passed.
- Affected Freeze 03 and historical-load tests: 41 passed, 1 skipped (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed.
IMPLEMENTATION:
- Added the bounded `FINALIZING` progress record between `FINGERPRINTING` and
  `COMPLETED` at the existing V2 finalization boundary.
- Regression drives the real V2 progress emission through the existing durable
  progress repository writer and verifies the complete ordered lifecycle.
CONCERNS:
- Database-gated test remained skipped because `ATLAS_TEST_DATABASE_URL` is not
  configured. No genuine OANDA run was performed.
