# Task 07 Review Remediation — receipt

## Outcome

**DONE** — approved review remediation only. No Git operation was performed.

## Root cause

- The Phase 4 runner constructed the simulated adapter with zero slippage and
  passed raw BID/ASK prices into PRE_SUBMISSION Risk. Consequently sizing,
  actual risk, target resolution, and persisted execution provenance could
  disagree when configuration requested nonzero adverse slippage.
- The loop sampled the final M1 equity point before END_OF_EXPERIMENT close;
  the deduplication guard then rejected the post-close sample. The terminal
  curve could therefore differ from persisted result equity.

## Changed paths

- `backend/experiments/runner.py`
  - Validates the complete Phase 4 simulation/risk configuration, including
    explicit zero/nonzero slippage and commission models.
  - Builds `SimulatedExecutionAdapter` from configured slippage ticks/tick
    size and passes the adverse-slipped executable side into PRE_SUBMISSION
    sizing. The resulting Risk entry/target/actual-risk facts now match Fill
    economics and provenance.
  - Defers the final equity sample while exposed, closes END_OF_EXPERIMENT,
    then persists the realized terminal point before result creation.
  - Preserves explicitly supplied execution adapters for deterministic test
    control while default Phase 4 execution remains config-driven.
- `backend/tests/integration/test_golden_flows.py`
  - Expanded permanent Phase 4 coverage for zero and nonzero slippage in both
    directions, asserting slipped entry, Risk actual risk, and provenance
    agreement.
  - Added an end-open integration flow asserting END_OF_EXPERIMENT Fill,
    commission/accounting, flat Position, atomic protection cancellation,
    and final equity/result reconciliation.

## Evidence

- `uv run pytest backend/tests/integration/test_golden_flows.py -q` — **8 passed**
- `uv run pytest -q` — **180 passed, 1 skipped**, 1 existing dependency warning
- `uv run ruff check backend/experiments/runner.py backend/tests/integration/test_golden_flows.py` — **passed**

## Remaining findings

The two Important review findings are remediated and covered. Minor review
observations regarding explicit dataset coverage/integrity validation and
session-closed frontier/gap handling were not broadened into this task; they
remain follow-up findings.
