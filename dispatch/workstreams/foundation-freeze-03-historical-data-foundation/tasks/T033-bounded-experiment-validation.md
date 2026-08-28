# T033 — Bounded V2 Experiment coverage validation

Status: `DONE_WITH_CONCERNS`

## Assignment

Fix REVIEW finding 4 only. Remove request-sized ORM `.all()`/tuple/set materialization
from authoritative V2 Experiment coverage validation. Use bounded streaming or
set-based reads consistent with Freeze 03, preserving all coverage and fail-closed
semantics. Add focused bounded-read/behavior regression coverage.

Do not change ingestion, provider chunking, snapshot determinism, progress phases,
completion handling, terminal metrics, or unrelated architecture.

## Required checks

- focused V2 Experiment validation behavior and bounded-read regression;
- affected Experiment tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T033-bounded-experiment-validation.md`
FILES CHANGED:
- `backend/experiments/configuration.py`
- `backend/tests/experiments/test_configuration.py`
- `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T033-bounded-experiment-validation.md`
CHECKS / EVIDENCE:
- Focused Experiment configuration tests: 7 passed.
- Backend Experiment tests: 88 passed.
- Freeze 03 V2 regression and snapshot-contract tests: 28 passed.
- Relevant database repository/ingestion tests: 11 skipped because `ATLAS_TEST_DATABASE_URL` is not configured.
- Ruff passed for changed application/test files; `python -m compileall -q backend` passed; `git diff --check` passed.
IMPLEMENTATION:
- Replaced analytical ORM collection reads with SQL count/existence/nth-row reads and an ordered analytical frontier stream.
- Replaced execution and successful-window ORM collections with one ordered, `yield_per(1000)` event stream retaining only bounded minute/report previews.
- Preserved strict native-M15 membership, sparse M1 only for successful acquisition coverage, snapshot-pinned execution membership, and fail-closed one-sided/unacquired/blocked-gap behavior.
- Added behavior coverage for sparse, unacquired, and one-sided execution data plus AST/source guards against `.all()` and request-sized materialization in the authoritative path.
CONCERNS:
- PostgreSQL-backed validation of the changed Experiment path remains database-gated; no genuine OANDA run was performed.
