# Task 06 Remediation — receipt

## Task / outcome

- **Task:** Approved Phase 4 remediation
- **Agent:** Backend remediation builder
- **Model:** openai/gpt-5.6-luna
- **Outcome:** DONE

## Root cause

Phase 4 selected an Order risk decision by descending random UUID. This could
link entry and protection Orders to PRE_FLIGHT instead of PRE_SUBMISSION, making
`Trade.initial_risk` intermittently null. The fingerprint omitted both that
linkage fact and initial risk, so it could report equality while semantic facts
differed. Equity sampling also used the first M1 close as the nominal starting
point instead of the exact `trading_start` boundary.

## Changed paths

- `backend/experiments/runner.py`
  - Carries the persisted PRE_SUBMISSION row ID directly to every Phase 4 Order.
  - Samples the initial equity point at exactly `experiment.trading_start`.
  - Includes each Order’s linked risk phase/actual risk and each Trade’s
    `initial_risk` in the semantic fingerprint payload.
  - Uses deterministic intent-frontier/purpose ordering for semantic Orders.
- `backend/tests/integration/test_golden_flows.py`
  - Added permanent Phase 4 end-to-end coverage for fresh-ID fingerprint
    equality, explicit PRE_SUBMISSION linkage, stable initial risk, sequential
    Trades, long and short execution, adverse-first ambiguity, equity/results,
    exact starting equity timing, and FAILED experiments without results.
  - Added deterministic Phase 4 fixtures with two sequential Trades.

No Git-changing command was performed. Existing changes and `.codegraph/` were
preserved. No other dispatch artifact was modified.

## Reproducibility proof

The new integration test runs the same semantic Phase 4 input as two fresh
Experiments with different database IDs, for both LONG and SHORT fixtures. It
asserts byte-identical semantic payloads and output fingerprints, while also
asserting every Order links to a PRE_SUBMISSION RiskDecision and every Trade has
non-null initial risk.

## Validation

- `uv run ruff check backend/experiments/runner.py backend/tests/integration/test_golden_flows.py` — **PASS**
- `uv run pytest backend/tests/integration/test_golden_flows.py backend/tests/integration/test_runner_failure_persistence.py backend/tests/execution/test_simulated.py -q` — **PASS** (15 passed)
- `uv run pytest -q` — **PASS** (177 passed, 1 skipped)

## Remaining deviations / blockers

None known within the approved Task 06 scope. Review remains prohibited until
independent re-validation passes, per `ACTIVE.md`.
