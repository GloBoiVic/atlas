# T034 — Fail-closed completion transition

Status: `DONE`

## Assignment

Fix REVIEW finding 5 only. Check the completion transition result in the coordinator.
If completion cannot be committed, produce an inspectable fail-closed terminal outcome
instead of leaving the request apparently `RUNNING`; preserve existing safety semantics
and avoid inventing a snapshot or financial state. Add focused race/linkage regression
coverage.

Do not change ingestion, provider chunking, progress phases, Experiment validation,
terminal metrics, or unrelated architecture.

## Required checks

- focused failed-completion transition regression;
- affected coordinator/repository tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T034-fail-closed-completion.md`
FILES CHANGED:
- `backend/market_data/historical_load.py`
- `backend/tests/test_historical_data_load.py`
- this receipt
CHECKS / EVIDENCE:
- Focused failed-completion coordinator regression: 1 passed.
- Coordinator/repository and relevant historical-load tests: 42 passed, 1 skipped
  (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed.
IMPLEMENTATION:
- The coordinator now checks the repository completion result.
- A failed completion/linkage transition is converted through the existing
  `fail_if_active` path to a durable `PERSISTENCE` / `COMPLETION_TRANSITION_FAILED`
  terminal outcome, without linking or inventing a snapshot.
CONCERNS:
- Database-gated checks remain dependent on `ATLAS_TEST_DATABASE_URL`; no genuine
  OANDA run or database reset was performed.
