# R004 Review — PAPER 05 Terminal-History Conflict

- **Remediation ID:** `R004`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `REVIEW`
- **Status:** `PASS`
- **Origin:** R003 `IMPORTANT` / `PRODUCT` finding that a later attributable Fill after durable `REJECTED`/`CANCELLED` history lacks retained reconciliation conflict status

## Review mandate

Independently review the request, frozen `PLAN.md` and `ARCHITECTURE.md`, the
immutable R003 finding, R004 BUILD and VALIDATION receipts, current diff, affected
reconciliation call paths, and scope constraints. Confirm that R004 is an
approved-scope correction, that exact and bounded-range resolution share the
historical prior-outcome rule, that conflict survives downstream Trade/protection
reads, that no-Fill terminal controls fail closed, and that the persistence
transition contract and unrelated PAPER 05/PAPER 04 behavior remain unchanged.

Review validation evidence and relevant focused/static checks. Do not modify
application, tests, fixtures, migrations, or prior evidence. No real OANDA call,
credential, activation, runtime, broker mutation, or capital-capable action is
permitted.

If another Critical or Important PRODUCT defect is found, STOP: record the exact
finding and do not create R005 automatically.

## Worker Evidence

Populate this artifact once with the independent review judgment, evidence,
findings, and completion receipt.

## Independent judgment

R004 passes the approved narrow remediation scope. The R003 IMPORTANT PRODUCT
finding is resolved without changing the frozen outcome-transition contract.

- `_terminal_history_conflicts()` compares the prior durable execution outcome
  with the newly proven terminal result, and is used by both exact
  Order → Transaction and bounded range resolution.
- Prior `REJECTED` or `CANCELLED` plus an attributable Fill produces filled
  execution truth and a `CONFLICT` finding. The coordinator retains the
  conflict flag when downstream Trade/protection handling would otherwise
  return `UNRESOLVED`, `CONSISTENT`, or `LIFECYCLE_ADVANCED`.
- The Fill is still passed through the existing attributable-Fill persistence
  path, and the existing `REJECTED`/`CANCELLED` → filled transition validator
  is unchanged. Prior terminal evidence remains retained by the repository
  projection and append-only observations.
- Same-terminal replays remain consistent; contradictory no-Fill terminal
  replays remain conflicted and preserve the prior execution outcome. `NULL`
  and `UNKNOWN` later-Fill controls do not become historical conflicts merely
  because a Fill is discovered.
- The diff is limited to the provider-neutral coordinator and deterministic
  reconciliation tests. No schema, migration, provider write behavior,
  runtime, activation, LIVE, repair, or capital-capable behavior was added.

## Findings

No unresolved CRITICAL or IMPORTANT PRODUCT/REGRESSION finding was found in
R004. No R005 is warranted or authorized.

### MINOR — tooling/environment limitation

The dedicated PostgreSQL repository suite skipped 9 tests because
`ATLAS_TEST_DATABASE_URL` was not configured. The configured Alembic database
is at `0020_fix_snapshot_guard`, so `alembic check` reports that the target is
not up to date. Repository-wide Ruff/Pyright baseline failures remain those
documented by R004 VALIDATION; the changed slice passes its scoped checks.
These are validation-environment/repository concerns, not R004 defects.

## Review Evidence

- Repository root/CWD and branch verified as
  `/Users/vike/Desktop/atlas` and `solo/paper-05-persistence-reconciliation`.
- Reviewed the frozen PLAN/ARCHITECTURE, immutable R003 finding, R004
  BUILD/VALIDATION receipts, current implementation/test diff, persistence
  transition validator, and affected reconciliation call paths.
- R004 acceptance matrix: **12 passed, 17 deselected**.
- Focused PAPER/reconciliation/OANDA suite:
  `uv run pytest -q backend/tests/paper backend/tests/integrations/test_oanda_reconciliation.py`
  — **107 passed**.
- Broad safe backend suite:
  `uv run pytest -q -m "not integration and not external"` — **975 passed,
  4 skipped, 97 deselected, 4 warnings**.
- Changed-slice Ruff format/check and Pyright passed; Pyright reported **0
  errors, 0 warnings, 0 informations**. `git diff --check` passed.
- Direct PostgreSQL integration rerun skipped **9** tests without a dedicated
  test URL; `alembic current` reported `0020_fix_snapshot_guard` and
  `alembic check` failed because the configured database is stale.
- No real OANDA request, credential, activation, runtime operation, broker
  mutation, or capital-capable action occurred. REVIEW changed only this
  artifact.

## Completion Receipt

ROLE: REVIEW
STATUS: PASS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R004-paper-05-terminal-history-conflict/REVIEW.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Independent source/diff review; exact/range terminal-history matrix 12 passed; focused PAPER/OANDA suite 107 passed; broad safe backend 975 passed, 4 skipped, 97 deselected; scoped Ruff/Pyright and `git diff --check` passed; PostgreSQL/Alembic environment limitations documented; deterministic fake-only evidence with no broker mutation or capital-capable action.
FINDINGS / CONCERNS: PASS — no unresolved CRITICAL or IMPORTANT PRODUCT/REGRESSION finding. Dedicated PostgreSQL tests were skipped without `ATLAS_TEST_DATABASE_URL`; configured Alembic target is stale; repository-wide static baseline concerns remain documented. No R005 is warranted or authorized.
