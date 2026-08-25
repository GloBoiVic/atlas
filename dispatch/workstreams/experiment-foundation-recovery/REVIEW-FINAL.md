# Final Independent R1 Review — Experiment Foundation Recovery

## Gate result

**BLOCKED — not acceptance-ready.** The deterministic V2 implementation and the
frontend quality gates reported by validation are substantively green, and the
TASK-07 configuration-boundary and TASK-08 migration-test findings are resolved.
The required PostgreSQL-backed lifecycle/migration proof and the required real
OANDA Practice UI acceptance remain absent. These are Critical acceptance
blockers; no acceptance is inferred from unit tests or receipts.

## Review scope and evidence

Reviewed the objective/amendments and governing context, `PLAN.md`,
`EXPLORATION.md`, `ARCHITECTURE.md`, `READY.md`, `TASK-01.md` through
`TASK-08.md`, `VALIDATION.md`, `VALIDATION-R1.md`, `VALIDATION-R2.md`,
`VALIDATION-FINAL.md`, `REVIEW.md`, `REVIEW-R1.md`, current relevant source,
tests, and migration revision `0013_result_quality_degraded`.

The current source was inspected with CodeGraph first, including the V2 clock,
runner, configuration boundary, result-quality path, persistence result model,
and API result path. A conceptual changed-scope review was performed from the
task file manifests and validation evidence; no Git commands were run.

## Prior findings after TASK-07/08

- **R1-001 terminal close fabrication — resolved.**
  `backend/experiments/runner.py:91-102` requires an executable observation at
  or after entry whose `end_time` is exactly `trading_end`; `_run_v2()` fails
  closed at `:493-500` when that proof is unavailable. The focused regression
  coverage passes.
- **R1-002 native analytical omission/V1 configuration route — resolved for
  current requests.** `backend/experiments/configuration.py:264-276` rejects
  non-V2 snapshots, and `:300-349` validates native M15 coverage and internal
  analytical frontiers. The TASK-07 direct-create regression is present and
  the focused configuration tests pass.
- **R1-003 result quality — resolved in deterministic code.**
  `backend/experiments/runner.py:105-110` classifies only material blocked
  intervals as `DEGRADED`; result persistence accepts it in
  `backend/persistence/models.py:616` and migration `0013`. Database proof is
  still unavailable.
- **R1-005 UUID normal label — resolved in the inspected API path.** The normal
  label uses the requested period; technical UUIDs remain separate fields.
- **R1-006 formatting — changed files resolved.** TASK-07 reports all changed
  frontend files pass Prettier. The full configured formatter still reports
  unrelated pre-existing files; this is not treated as a changed-path blocker.
- **TASK-08 stale migration assertion — resolved.**
  `backend/tests/test_migration_revision.py` now asserts head
  `0013_result_quality_degraded`.

No remaining code-level Important/Critical defect was reproduced in the current
V2 request/routing path. Retained historical migration identifiers and dormant
legacy acquisition/model surfaces are documented compatibility/history concerns,
not evidence that new requests route through V1. In particular, the runner
rejects unsupported snapshot schemas at `backend/experiments/runner.py:395-409`
and configuration rejects them before persistence at
`backend/experiments/configuration.py:264-276`.

## Evidence reused and checks rerun

Reused `VALIDATION-FINAL.md`: focused V2 suite **99 passed, 1 skipped**;
backend Ruff/compileall passed; frontend tests (**23**), typecheck, lint, build,
and changed-file Prettier checks passed; migration graph is linear with head
`0013_result_quality_degraded`.

Reran focused checks:

- `python -m pytest -q backend/tests/test_migration_revision.py` — **1 passed**.
- `python -m pytest -q backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_clock.py` — **16 passed**.
- `python -m pytest -q backend/tests/experiments/test_configuration.py` — **3 passed**.

A combined broader focused command exceeded the 120-second tool limit; its
separately rerun affected suites above passed, and the complete 99/1 result is
retained from `VALIDATION-FINAL.md`.

## Critical acceptance blockers

1. **Dedicated PostgreSQL test database is missing.** `ATLAS_TEST_DATABASE_URL`
   is unavailable. Consequently the load → immutable snapshot → create → run →
   completed-result lifecycle, migration application/state, persistence
   constraints, and database-backed golden flow remain unproven. `alembic check`
   remains blocked by database state. No database mutation was attempted.
2. **Real OANDA Practice UI evidence is missing.** The required credentialed
   browser flow was not performed; there is no durable load/run identifier,
   completed UI result, broker/account evidence, or UI confirmation of the
   disclosed V2 assumptions and quality/gaps. No OANDA outcome is inferred or
   fabricated.

## Terminal eligibility

**Not eligible for terminal acceptance or approval.** Provision only a dedicated
`_test` PostgreSQL database, apply/verify the linear migration head safely, run
the database-backed golden lifecycle, and complete the real OANDA Practice UI
flow with durable evidence. Re-review those artifacts before changing this
gate result.
