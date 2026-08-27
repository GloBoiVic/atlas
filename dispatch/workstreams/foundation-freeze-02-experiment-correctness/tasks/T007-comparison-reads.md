# T007 — Persisted comparison reads

Status: `BUILD COMPLETE`

## Receipt

- Updated comparison metric projection to accept persisted metric dictionaries
  returned by `ExperimentResultReadService.detail`, without recalculating from
  Trades or equity. Legacy in-memory metric objects remain compatible.
- Added a completed-comparison regression proving persisted metric values and
  reasons are preserved unchanged.

Files changed: `backend/experiments/comparison.py`,
`backend/tests/experiments/test_comparison.py`.

Checks:

- `pytest -q backend/tests/experiments/test_comparison.py backend/tests/experiments/test_results.py` — 17 passed.
- `python -m compileall -q backend` — passed.
- `git diff --check` — passed.

Concerns: PostgreSQL-backed integration remains dependent on the environment
configuration documented by VALIDATION.md.
