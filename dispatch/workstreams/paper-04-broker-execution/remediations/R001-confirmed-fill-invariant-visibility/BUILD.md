# R001 — Confirmed Fill invariant visibility

- **Remediation ID:** `R001`
- **Status:** DONE
- **Role:** BUILD
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Origin finding:** `CRITICAL C-001` in `dispatch/workstreams/paper-04-broker-execution/REVIEW.md`
- **Related original tasks:** T003, T005

## Approved requirement or invariant violated

Once `orderFillTransaction.tradeOpened` has been validated as a matching full
Fill, bound, Stop geometry, or actual-risk-budget violations must not erase the
known exposure or return entry `UNKNOWN`. Fill facts and bounded transaction
provenance must remain visible, and no retry, repair, target mutation, or
resubmission may be introduced.

## Exact remediation outcome

Preserve the validated `BrokerFillFacts` and `TransactionProvenance` for
confirmed-exposure invariant failures and return the frozen non-UNKNOWN
`FILLED_PROTECTION_INCOMPLETE` outcome with a bounded diagnostic. Ensure the
composition does not proceed to Stop/target protection completion for those
entry invariant failures. Add composition-level deterministic tests for
worse-than-bound, wrong-side Stop geometry, and actual-risk-budget violations.

## Affected implementation seams

- `backend/integrations/oanda/execution.py` entry response normalization.
- `backend/paper/execution_application.py` entry-result handling.
- Focused OANDA entry and PAPER composition tests.

## Explicitly out of scope

- Any architecture or PLAN revision.
- New operational outcomes.
- Automatic retry, resubmission, cancellation, or Stop repair.
- Changes to Risk/Strategy methodology, persistence, runtime, API/UI,
  migrations, historical Experiment semantics, PAPER activation, or LIVE.
- Real OANDA requests or credentials.

## Regression evidence required

- Existing focused T001–T005 and historical/Risk/PAPER 03 suites remain green.
- New composition coverage proves confirmed Fill identifiers, actual price,
  actual risk, and transaction provenance survive each invariant violation;
  outcome is not `UNKNOWN`; protection mutation is not attempted.
- Changed-file format, lint, type, and `git diff --check` pass.
- No real broker mutation occurs.

## Worker evidence

Remediated only C-001 without changing the frozen outcome set, mutation retry
policy, Risk/Strategy semantics, persistence, runtime, API/UI, historical
execution, or completed evidence:

- Extended `OandaPracticeEntryMutationNormalizationError` with bounded,
  validated `BrokerFillFacts`, `TransactionProvenance`, and invariant diagnostic
  context. `_filled_result` constructs the confirmed Fill before checking bound,
  Stop geometry, and actual-risk-budget invariants.
- Updated the PAPER application entry-result seam to convert those carried
  facts into `FILLED_PROTECTION_INCOMPLETE` with `NOT_ATTEMPTED` protection,
  preserving broker IDs, actual Fill price/risk, and transaction provenance.
  The application returns before invoking protection/target completion.
- Added composition-level deterministic coverage for worse-than-bound,
  wrong-side Stop geometry, and actual-risk-budget failures, including retained
  Fill/provenance assertions and zero protection mutation calls.

## Checks

- `uv run pytest backend/tests/paper/test_execution_composition.py -q` — **10 passed**.
- Focused OANDA entry/protection and PAPER composition suite — **34 passed**.
- Focused T001–T005 integration/PAPER/Risk/historical execution suite — **557 passed, 1 skipped**.
- `uv run pytest -m "not integration and not external" -q` — **922 passed, 4 skipped, 88 deselected**; only existing warning output.
- Changed-file `ruff format --check`, `ruff check`, `pyright`, and `git diff --check` — **passed**.
- No real OANDA requests, credentials, broker mutations, persistence, or runtime activation performed.

## Concerns

- Inherited workstream application changes and operational state remain in the
  worktree and were not otherwise altered by R001.
- Durable reconciliation of confirmed invariant violations remains outside this
  remediation and belongs to the frozen PAPER 05 boundary.
