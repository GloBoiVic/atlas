# Validation

Status: `PASS`
Role: `VALIDATE`
Workstream: `foundation-freeze-03-historical-data-foundation`
Branch: `solo/foundation-freeze-03-historical-data-foundation`

Validation ran 2026-08-28 from `/Users/vike/Desktop/atlas`. CWD, repository root,
branch, and CodeGraph were verified. This validation covered only T036-T037; T030-T035
were not reopened. Only this artifact was edited by VALIDATE. No branch or Git history
operation was performed, and `.codegraph/` plus `frontend/.env.local` remain untouched.

## Source and focused evidence

- **T036:** `MarketDataService.load_v2` obtains each next planning window and all
  planning reads inside a short `session.begin()` scope, closes the session, and only
  then yields the window. `acquire` calls the provider after that yield and opens its
  persistence transaction only after provider return. The focused regression
  `test_v2_provider_fetch_runs_after_planning_transaction_closes` passed and asserts
  the provider sees no active planning transaction. Planning totals are computed for
  both products before provider I/O and the totals/progress regression passed.
- **T037:** authoritative repository `missing_ranges` advances a streamed ordered-row
  frontier and emits one bounded `BarRange` at a time; application coalescing retains
  only its current span and provider bound. V2 planning replans from the frontier and
  replays the bounded generator for per-product totals rather than retaining a
  request-sized missing-range collection. The focused large/disjoint regression
  `test_missing_range_planning_streams_large_disjoint_ranges` passed: the first
  window was produced after fewer than 100 of 20,000 candidate minutes were read.
- Closure bridging, acquisition-union subtraction, strict native-M15 behavior,
  provider bounds, and per-product totals remained green in the affected suites.

## Checks and evidence

- T036/T037 focused regressions: **2 passed**.
- Affected Freeze 03 and historical-load unit tests: **46 passed**.
- Fresh isolated PostgreSQL repository/ingestion integration checks: **11 passed**.
- Full backend suite on the isolated validation schema: **383 passed, 1 skipped,
  4 warnings**. The migration cycle and drift checks passed; the skipped test is the
  opt-in external-provider check with credentials unset.
- Isolated database checks used the fresh schema
  `validation_t036_t037_20260828` in disposable database
  `atlas_validation_20260828_final3_test`. `atlas_test` was never targeted, reset, or
  deleted; its pre-existing idle/server connections were left untouched.
- Ruff on all T036/T037 changed application/test files: **PASS**. Full `ruff check
  backend` still reports **45 pre-existing issues**, all outside those changed files.
- `python -m compileall -q backend`: **PASS**.
- `git diff --check`: **PASS**.
- Post-check process inspection: **no validation or OANDA processes remain**. No
  OANDA request or genuine full-year benchmark was run.

## Existing evidence and incident context

The previously accepted live-year, covered-repeat, and interrupted/recovery evidence
remains accepted. T036/T037 change planning transaction lifetime and missing-range
memory behavior only; these checks found no material invalidation, so the approved
no-rerun exception applies.

The previously accepted validation-process incident remains non-blocking context: an
earlier validator used a malformed derived migration URL that targeted `atlas_test`
and its fixture dropped that schema. This validation did not repeat that invocation;
all database checks above used the explicitly constructed isolated database/schema.

## Receipt

ROLE: VALIDATE
STATUS: PASS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md`
FILES CHANGED: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md`
CHECKS / EVIDENCE: CodeGraph-first T036/T037 source audit; focused 2-test regression; affected unit 46 passed; isolated PostgreSQL integration 11 passed; full backend suite 383 passed/1 skipped/4 warnings; scoped Ruff, compileall, and diff checks passed; no validation/OANDA processes remain.
FINDINGS / CONCERNS: T036/T037 resolved with no new implementation blockers. Full Ruff retains 45 unrelated pre-existing issues. No full-year OANDA benchmark was required or run.
