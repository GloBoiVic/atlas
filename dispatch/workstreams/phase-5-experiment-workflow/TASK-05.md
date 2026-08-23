# TASK-05 — Result read composition

- **Task:** Implement approved blueprint task 5 only: bounded result, equity, and Trade reads; legacy metric derivation; provenance/assumption mapping seams; equity envelope sampling; and immutable Trade chart context.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/experiments/results.py`
- `backend/persistence/result_repository.py`
- `backend/tests/experiments/test_results.py`

## Outcome

Implemented a focused read-only result composition boundary. Completed-only result subresources fail closed with explicit `RESULT_NOT_READY` or `EXPERIMENT_FAILED` states; failed Experiments expose no partial metrics. Metric reads use the existing pure metrics component over immutable Trade/equity facts, so compatible legacy projections are derived without mutation. Equity reads are bounded with `EQUITY_ENVELOPE_V1` representatives while preserving full-series source counts. Trade reads are sequence ordered and use `Trade N` labels, with rationale, both Risk phases, Orders/events, Fills, ambiguity, approved stop/target facts, and costs/lineage. Trade chart context aggregates canonical M15 MID candles from immutable DatasetSnapshot membership, computes EMA before window selection, and returns bounded annotations plus omitted-range disclosure.

No FastAPI routes, frontend, lifecycle, or simulation behavior was changed. No current market-bar projection is used for result inspection.

## Exact validation receipts

- `.venv/bin/pytest -q backend/tests/experiments/test_results.py backend/tests/experiments/test_metrics.py` → **15 passed** (8 focused result-read tests and 7 deterministic metrics tests).
- `.venv/bin/ruff check backend/experiments/results.py backend/persistence/result_repository.py backend/tests/experiments/test_results.py` → **All checks passed**.
- `.venv/bin/python -m py_compile backend/experiments/results.py backend/persistence/result_repository.py` → **passed**.

## Evidence scope

Receipts cover the result read service's completed-only gates for PENDING/RUNNING/FAILED, zero-Trade and legacy metric derivation without mutation, bounded equity envelope sampling, sequence pagination, Trade lineage and approved protection facts, immutable snapshot chart reads, M15/EMA context, annotations, and omitted-range disclosure. The repository queries are read-only and bounded; chart reads use snapshot membership, not mutable current bars.

## Blocker/conflict

None. No Git mutations were performed. Existing dispatch artifacts and preceding task changes remain untouched.

## R1 remediation

Added focused service-level coverage to repair the Important validation gap. Tests now exercise every result subresource's fail-closed status gate, zero-Trade unavailable metric states, legacy read derivation without persistence mutation, envelope source/count/edge/cap behavior, sequence pagination, rationale/Risk/Order/Fill lineage, approved PRE_SUBMISSION stop/target selection, ambiguity, missing-intent fail-closed behavior, and immutable snapshot-backed M15/EMA chart annotations with an omitted-range marker.

### Exact remediation validation receipts

- `.venv/bin/pytest -q backend/tests/experiments/test_results.py` → **8 passed**.
- `.venv/bin/pytest -q backend/tests/experiments/test_results.py backend/tests/experiments/test_metrics.py` → **15 passed**.
- `.venv/bin/ruff check backend/tests/experiments/test_results.py backend/experiments/results.py backend/persistence/result_repository.py` → **All checks passed**.
- `.venv/bin/python -m py_compile backend/experiments/results.py backend/persistence/result_repository.py backend/tests/experiments/test_results.py` → **passed**.
