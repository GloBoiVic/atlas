# T002 — Align pending-trigger handoff

## Status

`DONE_WITH_CONCERNS`

## Ownership

BUILD owns this task.

## Scope

Make the runner consume the Strategy-owned analytical frontier for pending
trigger eligibility, process execution observations before each bar closes,
remove wall-clock expiry from eligibility, and preserve existing ASK/BID,
gap-through, Risk, Fill, and evidence ownership boundaries.

## Acceptance

- No independent runner expiry clock can disagree with Strategy state.
- W1–W5 execution observations remain eligible, including W5.
- Missing analytical intervals do not consume pending slots.
- Expiry clears the pending proposal after W5 without a fill.
- Actual-fill target resolution and execution evidence remain unchanged.
- Relevant runner/golden-flow tests cover the handoff and persisted evidence.

## Required receipt

Record files changed, checks run, and concerns here when complete.

## Completion receipt

- Files changed: `backend/experiments/runner.py`.
- Checks: `pytest -q backend/tests/experiments/test_runner_diagnostics.py`
  (10 passed); authoritative strategy, contract, provenance, and configuration
  checks (29 passed); compileall, Ruff, and diff checks passed.
- Evidence: pending execution eligibility is calculated from completed
  analytical frontiers, not `expiry_time`; persisted ARMED watch count is the
  sole eligibility authority, W5 remains eligible, and Strategy SEARCHING at
  W6 clears the pending proposal. Existing ASK/BID, gap-through, Risk, Fill,
  target, and evidence paths remain unchanged.
- Findings: sparse/session gaps do not add analytical frontiers and therefore
  do not consume watch slots.
- Concerns: database-backed integration checks require
  `ATLAS_TEST_DATABASE_URL` and were unavailable in this checkout. The
  existing persisted trigger schema still carries nullable `expiry_time` as a
  shape field; corrected decisions leave it null and runner eligibility never
  reads it, using ARMED state instead.

## Corrective receipt — 2026-08-26

- Files changed: `backend/persistence/models.py`,
  `backend/persistence/migrations/versions/0007_proposal_watch.py`,
  `backend/persistence/migrations/versions/0008_proposal_constraints.py`,
  plus the corrected v2 integration seed in
  `backend/tests/integration/test_golden_flows.py`.
- Checks: runner diagnostics and configuration tests passed; Ruff,
  compileall, and `git diff --check` passed. Database integration remains
  blocked because `ATLAS_TEST_DATABASE_URL` is unset.
- Evidence: PRICE_TRIGGERED persistence constraints now require trigger and
  expiry bars while accepting nullable `expiry_time`; no wall-clock eligibility
  path was added.

## Final corrective receipt — 2026-08-26

- Files changed: `backend/experiments/runner.py` (handoff), with the corrected
  domain/strategy contract and authoritative integration seed recorded by T001.
- Checks: targeted runner, configuration, strategy, domain, and legacy
  compatibility pytest (95 passed); compileall, targeted Ruff, and
  `git diff --check` passed. Full Ruff has unrelated pre-existing findings.
- Evidence: runner eligibility remains analytical-frontier/state based;
  nullable `expiry_time` is not used as an eligibility clock, and legacy
  schema-1 implementations are quarantined from the authoritative schema-2
  registration.
