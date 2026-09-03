# R004 — PAPER 05 Terminal-History Conflict Remediation

- **Remediation ID:** `R004`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Origin finding:** `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R003-paper-05-attribution-frontier-provenance/VALIDATION.md`, finding `IMPORTANT — PRODUCT — later attributable Fill after reject/cancel is not marked as conflict`
- **Finding severity:** `IMPORTANT` / `PRODUCT`, approved-scope post-cap correction
- **Related original task(s):** `T003-paper-05-reconciliation`; prior remediation `R003-paper-05-attribution-frontier-provenance`
- **Approved requirement or invariant violated:** Frozen `ARCHITECTURE.md` §7.1, §7.2, §8.1, and §10 require prior durable `REJECTED`/`CANCELLED` history plus later attributable Fill to preserve the terminal evidence, persist the Fill, advance to a filled execution outcome, and retain `ReconciliationStatus.CONFLICT` with a `CONFLICT` finding. The frozen persistence transition permitting this outcome advancement must remain unchanged.

## Authorization

The developer explicitly authorized exactly this one narrow post-cap R004
correction in the current request. It is an approved-scope PRODUCT defect, not new
scope and not an architecture reopening. If R004 VALIDATE or REVIEW finds another
Critical or Important PRODUCT defect, stop and report that exact finding; do not
create R005 automatically.

## Exact remediation outcome

Centralize historical entry resolution so both exact Order → Transaction discovery
and bounded Transaction-range discovery determine conflict from the prior durable
execution outcome when a newly attributable Fill is proven. The rule is:

```text
prior REJECTED or CANCELLED + newly attributable Fill
    → filled execution truth
    + ReconciliationStatus.CONFLICT
    + CONFLICT finding
```

The conflict must survive the subsequent Trade/protection read and must not be
overwritten by `UNRESOLVED`, `CONSISTENT`, or `LIFECYCLE_ADVANCED`. Preserve the
existing transition contract and all prior terminal observations/evidence; do not
derive conflict merely from simultaneous facts in the current provider read.

Add permanent deterministic coverage in
`backend/tests/paper/test_reconciliation.py` for:

- prior `REJECTED` + exact later Fill;
- prior `CANCELLED` + exact later Fill;
- prior `REJECTED` + bounded range later Fill;
- prior `CANCELLED` + bounded range later Fill;
- each with missing Trade → `FILLED_PROTECTION_INCOMPLETE` + `CONFLICT`;
- exact protected Trade → `FILLED_PROTECTED` + `CONFLICT`, where practical;
- Fill persistence, filled outcome advancement, retained `CONFLICT` finding/status,
  and non-erasure of prior durable terminal evidence;
- controls for prior `UNKNOWN` and prior `NULL` + later Fill that do not become
  conflicts solely because a Fill was discovered;
- adjacent no-Fill historical terminal controls: attributable prior
  `REJECTED` + later same `REJECTED` and prior `CANCELLED` + later same
  `CANCELLED` remain consistent, while unsupported contradictory no-Fill terminal
  combinations fail closed;
- existing simultaneous Fill + reject/cancel range coverage remains green.

## Affected implementation seams

- `backend/paper/reconciliation.py`
- `backend/tests/paper/test_reconciliation.py`

Change `backend/paper/persistence_contracts.py` or persistence/provider code only
if a demonstrated invariant requires a narrow direct adjustment. Do not change
the allowed `REJECTED`/`CANCELLED` → filled outcome transition rule.

## Explicit out-of-scope items

- No PLAN or ARCHITECTURE reopening or redesign.
- No R005 automatic remediation.
- No migration/schema, Strategy, Risk, PAPER 04 broker mutation semantics,
  runtime, activation, OANDA write behavior, broker credentials, real broker calls,
  or capital-capable action.
- No broker mutation, resubmission, cancellation, close/reduce operation,
  protection repair, lifecycle/accounting redesign, or unrelated reconciliation
  contract changes.
- Do not overwrite R003 or any prior task/validation/review/remediation artifact.

## Regression evidence required

1. First reproduce the R003 validator probe using deterministic in-process fakes.
2. Run the complete R004 exact/range transition matrix above, including both
   downstream Trade/protection cases and NULL/UNKNOWN controls.
3. Run the existing focused reconciliation/PAPER/OANDA regression suite.
4. Run appropriate broad safe backend and changed-slice static gates already
   required by PAPER 05, including Ruff, Pyright, Alembic checks where applicable,
   and `git diff --check`.
5. Use no real OANDA requests, credentials, migrations/schema changes, or
   capital-capable operation.

## Worker Instructions

To be completed by the BUILD worker. The worker must inspect the frozen PLAN and
ARCHITECTURE, immutable R003 finding, current reconciliation implementation, and
adjacent terminal tests before editing, then record the exact files, checks, and
any concerns here without editing prior evidence.

## Worker Evidence

### Implementation receipt

R004 is implemented in the provider-neutral reconciliation coordinator. Exact
Order → Transaction resolution and bounded Transaction-range resolution now use
the prior durable execution outcome when accepting a newly attributable Fill.
Prior `REJECTED`/`CANCELLED` history therefore advances execution truth to a
filled outcome while retaining `CONFLICT` status and finding codes. The conflict
is preserved through missing or exact protected Trade reads. Attributable
same-terminal replays remain consistent, contradictory no-Fill terminal
replays fail closed, and `NULL`/`UNKNOWN` Fill discovery does not become a
history conflict solely because a Fill was found. Existing filled-versus-terminal
range conflict behavior remains covered.

Changed files:

- `backend/paper/reconciliation.py`
- `backend/tests/paper/test_reconciliation.py`
- this BUILD artifact

### Checks and evidence

- Red reproduction before implementation: the new exact/range terminal-history
  matrix failed with `UNRESOLVED` status, and contradictory no-Fill terminal
  controls incorrectly advanced to the later terminal outcome.
- Focused R004 matrix and downstream read-failure coverage: **12 passed**, including prior `REJECTED`/`CANCELLED`
  exact and bounded-range later Fills, missing/exact Trade paths, `NULL`/`UNKNOWN`
  controls, same-terminal replays, and contradictory terminal controls.
- Focused reconciliation/PAPER/OANDA suite: **114 passed**.
- Broad safe backend suite:
  `uv run pytest -q -m "not integration and not external"` — **975 passed,
  4 skipped, 97 deselected, 4 existing warnings**.
- Changed-slice Ruff format/check and Pyright — passed; Pyright reported **0
  errors, 0 warnings, 0 informations**.
- `git diff --check` — passed.
- Repository-wide static gates were also probed but remain blocked by unrelated
  pre-existing findings: Ruff format reports 68 unformatted files (so Ruff
  check was not reached), and Pyright reports 2887 errors outside this changed
  slice.
- Alembic checks were not changed by R004. The configured database reported
  `0020_fix_snapshot_guard` from `alembic current`, and `alembic check` failed
  because the target database is not up to date; no migration or schema action
  was taken.
- No real OANDA request, credential use, broker mutation, PAPER activation,
  runtime operation, or capital-capable action occurred.

## Completion Receipt

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R004-paper-05-terminal-history-conflict/BUILD.md`
FILES CHANGED: `backend/paper/reconciliation.py`, `backend/tests/paper/test_reconciliation.py`, and this BUILD artifact
CHECKS / EVIDENCE: R004 matrix and downstream read-failure coverage 12 passed; focused 114 passed; final broad safe backend 975 passed, 4 skipped, 97 deselected; changed-slice Ruff/Pyright and git diff --check passed; repository-wide static failures and stale Alembic target documented above; fake-only deterministic evidence with no broker mutation or capital-capable action.
CONCERNS: Repository-wide Ruff/Pyright remain blocked by unrelated pre-existing findings, and the configured Alembic database is at 0020 rather than the current target. Fresh R004 VALIDATE and REVIEW contexts remain required.
