# TASK-02 — Deterministic metrics boundary

- **Task:** Implement approved blueprint task 2 only: pure deterministic Experiment metrics, completion persistence, finite metric states, and wall-clock terminal timestamp semantics without timestamp fingerprint input.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/experiments/metrics.py`
- `backend/experiments/runner.py`
- `backend/tests/experiments/test_metrics.py`
- `backend/tests/integration/test_golden_flows.py`

Task-01 files were pre-existing working-tree changes and were not rewritten.

## Outcome

Implemented one pure metrics boundary over immutable completed Trades and the full canonical equity series. It computes Phase 4 net return and maximum drawdown, plus daily UTC Sharpe, net-P&L Profit Factor, break-even-inclusive Win Rate, and net-P&L Expectancy with explicit unavailable/infinite states. Decimal-safe finite values are persisted through the Phase 5 result projection; no NaN or infinity value is persisted.

Completion now uses the Phase 5 result/metric schema, persists all metric values and states, keeps `completed_market_time` at the simulation frontier, and records new `completed_at` from wall-clock UTC. The semantic output fingerprint remains built only from reproducibility facts and excludes `completed_at`. Phase 4 trading facts and semantic rerun fingerprints remain unchanged.

Focused tests cover full-series drawdown, daily Sharpe value/insufficient/zero-variance behavior, final point per UTC day, finite/infinite/empty Profit Factor, Win Rate break-even denominator, Expectancy, zero-Trade state semantics, deterministic repeat calculation, timestamp separation, persisted metric schema, and Phase 4 golden-flow regression.

## Exact validation receipts

- `pytest -q backend/tests/experiments/test_metrics.py` → **6 passed**. Pure metric edge cases and deterministic output evidence.
- `pytest -q backend/tests/integration/test_golden_flows.py` → **8 passed in 115.31s**. Phase 4 long/short, slippage, reproducibility/fingerprint, failure-without-result, end-close, and new wall-clock `completed_at` versus market frontier assertions.
- `pytest -q backend/tests/integration/test_migrations.py backend/tests/test_migration_revision.py` → **3 passed**. Task-01 migration/model compatibility regression after completion wiring.
- `ruff check backend/experiments/metrics.py backend/experiments/runner.py backend/tests/experiments/test_metrics.py backend/tests/integration/test_golden_flows.py` → **All checks passed**.
- `python -m py_compile backend/experiments/metrics.py backend/experiments/runner.py` → **passed**.

## Evidence scope

Evidence covers pure metric calculations and state semantics, full-resolution equity drawdown, UTC daily return selection, finite persistence inputs, completion timestamp/fingerprint separation, Phase 4 financial facts, semantic reproducibility, failure behavior, end-of-Experiment closure, and migration compatibility. No API, UI, coverage, run lifecycle, worker, or tasks 3+ work was added.

## Blocker/conflict

None. No Git mutations were performed. Known pre-existing dispatch and Task-01 working-tree changes remain untouched.

## R1 remediation

Repaired the single Important finding: maximum drawdown percentage now tracks
each trough's applicable running peak rather than dividing the maximum dollar
drawdown by the final global peak. Added the focused `[100, 110, 90, 120]`
regression proving `20 / 110`. No other scope or dispatch artifact changed.

### Remediation validation receipts

- `pytest -q backend/tests/experiments/test_metrics.py` → **7 passed**. Includes the running-peak regression and all prior metric edge cases.
- `ruff check backend/experiments/metrics.py backend/tests/experiments/test_metrics.py` → **All checks passed**.
- `python -m py_compile backend/experiments/metrics.py` → **passed**.
