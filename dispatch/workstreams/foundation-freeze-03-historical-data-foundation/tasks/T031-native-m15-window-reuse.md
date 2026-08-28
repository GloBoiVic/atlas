# T031 — Native M15 acquisition-window reuse

Status: `COMPLETE`

## Assignment

Fix REVIEW finding 2 only. Reuse the successful acquisition-window union for native
M15 as well as M1, including successful empty/sparse M15 responses, while preserving
strict native-M15 observation validation and no-fabrication semantics. Add a focused
repeat test proving no needless provider re-request.

Do not change provider chunking, atomic commit boundary, progress phases, Experiment
validation, completion handling, terminal metrics, or unrelated architecture.

## Required checks

- focused empty/sparse native-M15 repeat regression;
- affected planning/repository tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: COMPLETE
FILES CHANGED:
- `backend/market_data/ingestion.py`
- `backend/persistence/market_data_repository.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T031-native-m15-window-reuse.md`
CHECKS / EVIDENCE:
- Focused native-M15 empty/sparse repeat coverage: 2 passed.
- Planning, historical-load, repository, and V2 coverage tests: 44 passed, 7 skipped (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed for changed application/test files.
IMPLEMENTATION:
- Successful acquisition-window union reuse now applies to native M15 as well as M1.
- M15 successful empty/sparse windows remain reusable without weakening provider-native
  alignment/completeness validation or fabricating observations.
- M15 uncovered remainders retain 15-minute planning semantics.
CONCERNS:
- Database-backed repository tests were skipped because `ATLAS_TEST_DATABASE_URL` was not configured.
