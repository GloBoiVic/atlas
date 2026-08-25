# R1 Review — Experiment Foundation Recovery

## Verdict

**BLOCKED — not acceptance-ready.** The focused deterministic checks and frontend
build checks are useful evidence, and the current public runner is V2-only, but
the implementation still has a material terminal-accounting safety defect. The
required database-backed lifecycle and real OANDA Practice UI acceptance are
also absent, so the core vertical slice has not been proven.

## Scope and evidence reviewed

Reviewed `AGENTS.md`, the relevant experiment, result, database, market-data,
accounting, runtime, strategy, and safety contracts, plus `PLAN.md`,
`EXPLORATION.md`, `ARCHITECTURE.md`, `READY.md`, `TASK-01` through `TASK-05`,
`VALIDATION-R2.md`, and the current changed-path source/tests.

Reused evidence:

- R2 targeted suite: 94 passed, 1 skipped; backend Ruff and compileall passed.
- R2 full suite: 259 passed, 37 skipped, **15 integration setup errors** because
  `ATLAS_TEST_DATABASE_URL` is unset.
- R2 frontend tests/typecheck/lint/build passed; format check failed in 14 files.
- R2 reports 2,036 existing pyright errors and a blocked `alembic check`.
- R2 explicitly records that the required real OANDA Practice UI run was not
  attempted and has no run identifier or broker/database evidence.
- Independent rerun: `python -m pytest -q backend/tests/experiments/test_clock.py
  backend/tests/experiments/test_runner_diagnostics.py` — **12 passed**.

Receipts are treated as evidence, not as a substitute for the missing external
acceptance gates.

## Findings

### R1-001 — Critical: end-of-experiment close can fabricate a terminal outcome

**Severity: BLOCKER / P0**

In `backend/experiments/runner.py:471-477`, an open position is considered
terminally knowable when *any* observation with `start_time >= entry_time`
exists. The code then closes at `terminal[-1]`. Thus an entry observation can
also be the sole observation and be used as the END_OF_EXPERIMENT close, even
when no executable observation exists at or near `trading_end`; a sparse quote
before the experiment end can likewise be treated as the final quote. This
violates the approved policy in `ARCHITECTURE.md:20-22` and the experiment
contract's explicit end close requirement: unknown terminal financial state
must fail closed, never become an invented exit.

The current tests cover exact entry lookup and incomplete buckets, but do not
cover “entry exists, no later executable observation” or “last quote precedes
experiment end”. This is a production correctness blocker for both long and
short results and must be fixed before acceptance.

### R1-002 — High: native analytical gaps are not independently validated as a
material completeness condition

**Severity: BLOCKER / P1**

`backend/experiments/configuration.py:363-370` only checks that at least one
native analytical bar exists in the requested range. It does not verify the
expected M15 frontier sequence or otherwise classify missing native M15 bars
inside the requested window. `backend/experiments/clock.py:247-261` emits
frames only for bars that exist, so an absent internal native frontier can be
silently omitted rather than becoming an explicit evaluation/gap outcome.

This conflicts with `ARCHITECTURE.md:35-38,46-47` and the no-silent-omission
requirement. The implementation may therefore produce an apparently complete
zero-trade or under-traded result from an incomplete analytical snapshot.

### R1-003 — High: result quality semantics do not match the approved contract

**Severity: BLOCKER / P1**

`backend/experiments/runner.py:519-532` marks quality
`DETERMINED_WITH_GAPS` whenever *any* snapshot gap exists (including gaps
outside the requested period or non-material sparse intervals). The approved
blueprint (`ARCHITECTURE.md:28`) requires quality to be derived from whether a
gap affects possible decisions: `DETERMINED` only with no material gap and
`DEGRADED` when execution availability affects possible decisions while facts
remain determinable. The persisted check in `backend/persistence/models.py:616`
also has no `DEGRADED` value. Consequently the UI/API can neither express the
approved result state nor distinguish harmless sparse absence from a material
execution-data limitation.

### R1-004 — High: required database and broker acceptance evidence is missing

**Severity: BLOCKER / P1 (acceptance gate)**

Per `VALIDATION-R2.md:23-51,90-117`, the full backend lifecycle cannot run
without a dedicated `_test` PostgreSQL URL, `alembic check` is blocked by the
database state, and the real OANDA Practice UI flow was not attempted. There
is no evidence for load → immutable snapshot → create → run → completed result
against PostgreSQL, nor for the required UI disclosures using a credentialed
OANDA Practice session. This is exactly the database/OANDA evidence blocker
required by the review instructions; no run or result should be inferred from
unit tests.

### R1-005 — Medium: normal experiment identity still exposes a UUID fragment

**Severity: P2**

`backend/api/experiments.py:145-147` sets the normal API label to
`Experiment {str(row.id)[:8]}`. This is still a raw UUID fragment, contrary to
`AGENTS.md:21`, `ARCHITECTURE.md:48`, and the stated UI requirement that normal
labels not be raw UUID identities. It is not the primary trading-safety block,
but it contradicts the claimed TASK-03 disclosure completion and should be
replaced with a human-readable strategy/period label (while retaining the UUID
as a technical identifier).

### R1-006 — Medium: formatting gate remains red

**Severity: P2**

`VALIDATION-R2.md:63-67` records 14 frontend Prettier failures, including the
changed experiment workflow, strategy history, generated API code, and tests.
This is not a domain-safety defect, but it is an unresolved completion gate for
the changed UI path.

## Alignment assessment

- **Plan/V2-only path:** substantially aligned. The public runner dispatch now
  rejects unsupported models, and R2 found no legacy Phase-4 labels under the
  current experiment path. Retained `load_missing` surfaces remain a stated
  scope concern, though they are not shown to route current V2 Experiments.
- **Bounded execution:** exact `start_time == frontier` selection and no later
  fallback are implemented and independently tested. The terminal consequence
  of sparse absence is not safe, as described in R1-001.
- **Context requirement:** canonical field propagation is present in the
  current focused path; the compatibility alias remains and should stay only at
  a clearly bounded legacy boundary.
- **Snapshot/fingerprint:** native analytical rows and execution memberships
  carry fingerprints and the market-bar append-only trigger supports captured
  identity. Database-backed immutability and fingerprint replay remain
  unverified because the required PostgreSQL run is unavailable.
- **Canonical accounting:** the runner retains the intended
  TradeIntent → RiskDecision → Order → Fill → Position → Trade structure and
  executable-side valuation in the inspected path, but the terminal-close bug
  prevents production-readiness.
- **Result/UI:** completed-only and V2 provenance plumbing is present, but
  quality taxonomy, UUID labeling, formatting, and the real UI flow remain
  unresolved.

## Required disposition

Do not approve or claim completion. First correct the terminal observation
criterion and analytical-gap/quality semantics, add deterministic regression
tests for those cases, then provision a dedicated `_test` PostgreSQL database,
run migrations and the database-backed golden lifecycle, resolve or explicitly
baseline the stated tooling gates, and perform the real OANDA Practice UI
acceptance run with durable load/run/result evidence. No speculative
generalization or new provider work is requested.
