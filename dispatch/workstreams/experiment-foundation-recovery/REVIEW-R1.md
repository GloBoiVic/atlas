# Independent R1 Re-review — Experiment Foundation Recovery

## Review

Gate: R1

Spec compliance: ISSUES

Task quality: ISSUES

Layer 1: ISSUES

Layer 2: ISSUES

Layer 3: ISSUES

## Scope and evidence

This independent re-review covers R1-001 through R1-006 after TASK-06, using the
objective/amendments, required context, PLAN, EXPLORATION, ARCHITECTURE, READY,
TASK-01 through TASK-06, VALIDATION-R2, the prior REVIEW, and the current
changed-path source and tests. No application code or other dispatch artifact was
modified.

Evidence reused:

- TASK-06 receipt: remediation claims for R1-001, R1-002, R1-003, R1-005 and
  workflow formatting; targeted tests, Ruff, compileall, and changed-workflow
  checks reported passing.
- VALIDATION-R2: deterministic suite 94 passed/1 skipped, frontend tests,
  typecheck, lint and build passed; full backend integration setup was blocked by
  missing `ATLAS_TEST_DATABASE_URL`; real OANDA Practice UI acceptance was not
  attempted; full frontend formatting and pyright remained red.
- Current inspection confirms exact terminal-end criterion in
  `backend/experiments/runner.py:91-102`, native frontier detection in
  `backend/experiments/configuration.py:113-124,337-413`, quality propagation in
  `backend/experiments/runner.py:105-110,539-565`, and non-UUID date-period API
  labels in `backend/api/experiments.py:146-149`.

Checks rerun:

- `python -m pytest -q backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_clock.py backend/tests/experiments/test_configuration.py` — **19 passed**; rerun because these tests cover all five deterministic TASK-06 remediation areas.
- `python -m pytest -q backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py` — **36 passed**; rerun because result quality/API read paths were changed.
- `python -m ruff check backend/experiments/runner.py backend/experiments/configuration.py backend/persistence/models.py backend/api/experiments.py backend/tests/experiments/test_runner_diagnostics.py` — **passed**.
- `alembic heads && alembic history --verbose` — **passed** with current head `0013_result_quality_degraded`; this supersedes the stale R2 statement that the head was `0012`.
- `npm run format:check:web -- --check frontend/components/experiment-workflow.tsx` — **failed as a project gate**: the script checks the whole configured frontend set and reports 13 files, including changed `frontend/components/strategy-history.tsx` and `frontend/lib/api.generated.ts`. The workflow file itself is clean.

## Findings and R1 disposition

### R1-001 — Terminal close fabrication

**Resolved for the inspected path.** `terminal_protection_observation()` now
requires an observation beginning at/after entry and ending exactly at
`trading_end`; entry-only and pre-end observations return no terminal proof.
The two regression tests pass. This addresses the prior production safety defect,
though the database-backed golden lifecycle remains unproven.

### R1-002 — Native analytical gap omission

**Partially resolved; remains BLOCKED (Important).** V2 coverage now computes the
complete expected M15 frontier sequence and returns `MISSING_ANALYTICAL_FRONTIERS`.
The internal-gap regression passes. However,
`backend/experiments/configuration.py:273-316` still contains the non-V2
coverage/aggregation branch, and `create()` accepts any snapshot that passes that
branch. The approved blueprint makes V2 the sole current historical Experiment
architecture and requires that new requests cannot route through V1. Public
options being V2-only and the runner rejecting unsupported schemas do not prove
that direct create/coverage requests cannot enter this retained branch. Remove or
explicitly reject the non-V2 Experiment configuration path, with a regression
guard. This is a production/spec blocker, not merely a historical migration
concern.

### R1-003 — Result quality semantics

**Resolved in deterministic code; acceptance evidence still blocked.** Material
blocked gaps overlapping the requested period classify as `DEGRADED`, while
non-material/sparse diagnostics classify as `DETERMINED`; failed API detail exposes
`FAILED`. The model constraint and migration `0013_result_quality_degraded`
accept `DEGRADED`, and the focused quality/result tests pass. PostgreSQL
persistence, migration application, and a completed degraded result have not been
verified because the dedicated test database is unavailable.

### R1-004 — Required database and broker acceptance evidence

**Unresolved BLOCKER (Critical acceptance gate).** No evidence exists for the
required PostgreSQL load → immutable snapshot → create → run → completed-result
flow. `ATLAS_TEST_DATABASE_URL` is still unavailable, so integration setup and
database migration checks cannot establish persistence, immutability, or the
golden lifecycle. The required credentialed OANDA Practice browser run was not
attempted and has no durable load/run/result identifier. Per instruction, unit
tests cannot substitute for either database or OANDA evidence. Do not approve.

### R1-005 — UUID fragment in normal identity labels

**Resolved for the inspected API detail path.** `backend/api/experiments.py:148`
now uses the requested date period as the normal label; UUIDs remain technical
fields. No contrary normal Experiment label was found in the inspected current UI
path. This still needs confirmation through the real UI acceptance run.

### R1-006 — Formatting gate

**Unresolved BLOCKED (Important completion gate).** TASK-06 formatted
`experiment-workflow.tsx`, but the configured frontend formatting gate remains
red. The current rerun reports 13 files, including changed
`strategy-history.tsx` and `api.generated.ts` (and other repository frontend
files). The changed-path formatting gate must be made green or explicitly
accepted as an environment/project baseline before completion.

## Additional observations

- V2 runner dispatch is schema-first and rejects unsupported models; this is good
  evidence against the former runner fallback, but it does not remove the
  configuration V1 branch identified under R1-002.
- `required_historical_context_bars` is used in the current focused V2 path. The
  deprecated `warm_up_bars` alias remains at the stated compatibility boundary;
  no V2 experiment-path propagation was found in the inspected source.
- Terminal safety, chronological protection, canonical accounting flow, and
  sparse exact-entry semantics are supported by focused tests, but unverified
  database facts remain a separate production-readiness blocker.
- No credentials, environment files, databases, OANDA account state, or Git
  commands were accessed or changed. No terminal operation requiring elevated
  approval was performed.

## Decision

**BLOCKED — not acceptance-ready.** R1-001, R1-003, and R1-005 are addressed in
the deterministic inspected paths. R1-002 remains an Important V2-only boundary
issue, R1-004 is an unresolved Critical database/OANDA acceptance gate, and
R1-006 remains an unresolved formatting gate. Provision only a dedicated `_test`
database, apply the current linear migration head safely, prove the database
golden flow, close the V2 configuration boundary, resolve/accept formatting, and
then perform the real OANDA Practice UI acceptance run with durable evidence.
