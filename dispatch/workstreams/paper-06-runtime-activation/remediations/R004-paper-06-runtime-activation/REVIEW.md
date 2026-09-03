# R004 — Terminal P05 outcome safety classification

- **Status:** `PASS`
- **Role:** `REVIEW`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin:** Original `REVIEW.md` `IMPORTANT-01`
- **Review mode:** Independent review of the complete corrected workstream after the approved R004–R006 batch.

## Decision

`PASS`. The corrected R004–R006 batch closes the three unresolved IMPORTANT
product blockers from the original workstream review. R001–R003 remain
independently passed, so the original CRITICAL ownership-loss and executable
runtime findings are also closed. No CRITICAL, IMPORTANT, or MINOR product
finding remains within the approved PAPER 06 boundary.

## Review scope

- Inspect the original finding, PLAN/ARCHITECTURE, R004–R006 BUILD and validation evidence, implementation diff, and relevant PAPER 05 contracts.
- Specifically judge the unsafe-attempt truth table across activation and runtime observation, `FILLED_PROTECTED` versus current flatness, read-only progression with open attributable exposure, later fresh-flat entry gating, and no weakening of UNKNOWN/reconciliation/claim semantics.
- Also inspect the R005 startup capability proof, R006 exact Decimal round trip/schema/replay, authority boundaries, migration history, and all combined validation limitations.
- No application/test/evidence edits beyond this assigned review artifact; no credentials, activation, real OANDA request, broker mutation, PAPER, or LIVE operation.

## Findings

### CRITICAL

None. R001's owner/generation fence is checked again after the committed Take
Profit claim and runtime callback and immediately before the dependent PUT.
R002 wires the executable `atlas-runtime` entrypoint to the composed
`PaperRuntimeOrchestrator` while preserving idle-without-activation behavior.

### IMPORTANT

None.

**IMPORTANT-01 / R004 — P05 terminal safety:** Closed. The Python predicate
`is_unsafe_paper_attempt` and the equivalent repository SQL predicate accept
only definite `REJECTED`, `CANCELLED`, or `FILLED_PROTECTED` outcomes with
`NOT_RUN`, `CONSISTENT`, or `LIFECYCLE_ADVANCED` reconciliation. UNKNOWN,
protection-incomplete, unresolved, conflicted, missing, malformed, and invalid
truth remains unsafe. The predicate is used by activation eligibility,
reconciliation outstanding detection, runtime account-observation gating, and
interrupted-cycle recovery. `FILLED_PROTECTED` is treated as historical
execution resolution only: current account truth is still freshly read, known
attributable open LONG/SHORT exposure advances Strategy read-only, and a later
fresh FLAT/zero-pending observation is required before a new opening.

**IMPORTANT-02 / R005 — non-MT4 startup capability:** Closed. Production
composition creates one read-only
`OandaPracticeAccountPropertiesReader` and shares it with PAPER 05. Startup
requires its successful normalized exact-configured-account, non-MT4 read
before full Account Details/bootstrap checks and before `RUNNING`. MT4,
missing, mismatched, malformed, and temporarily unavailable capability facts
fail closed or remain bounded `STARTING`; runtime does not reinterpret raw
provider fields or gain a direct mutation seam.

**IMPORTANT-03 / R006 — exact Risk identity:** Closed. The runtime activation
model and the unmerged 0023 migration use unconstrained PostgreSQL `NUMERIC`
with Decimal handling. Dedicated evidence preserves `0.01`,
`0.12345678901`, and `0.00000000001` through persistence, restores the exact
`RiskConfig`, accepts exact same-ID replay, rejects changed-risk replay, and
passes the migration cycle/schema assertion.

### MINOR

None.

## Evidence

- Reviewed the approved `ACTIVE.md`, PLAN, ARCHITECTURE, original workstream
  REVIEW/VALIDATION, T001–T008 receipts, R001–R006 BUILD/VALIDATION/REVIEW
  packets, PAPER 05 contracts/evidence, DOMAIN.md, README.md, current dirty
  implementation diff, migration, and focused tests.
- Inspected the durable truth and all call sites in
  `backend/persistence/runtime_repository.py`, including both the Python and
  SQL unsafe-attempt predicates; `backend/runtime/activation.py` and
  `backend/runtime/orchestration.py`; the caller-owned P05 seam in
  `backend/paper/durable_execution.py`; startup composition in
  `backend/runtime/main.py`; ownership in `backend/runtime/ownership.py`; and
  the account/capability normalizer in
  `backend/integrations/oanda/execution_account.py`.
- Inspected `PaperRuntimeAccountObservation` and cycle authority. The runtime
  separates Strategy evaluation from entry eligibility, binds account
  observation/frontier/state evidence to the cycle, blocks unattributed or
  contradictory exposure, and requires a fresh flat zero-pending gate before
  an opening.
- R001, R002, and R003 immutable review receipts are PASS with no remaining
  findings in their scopes. R005 and R006 independent validation receipts are
  PASS and retain the R004 regression evidence.
- No credential, provider mutation, activation, PAPER/LIVE operation, or real
  OANDA request was performed.

## Checks and results

| Check | Result |
| --- | --- |
| R004 terminal-safety/fresh-observation regression selection | **29 passed, 53 deselected** |
| R005 startup capability/OANDA selection | **76 passed** |
| R006 precision/model/migration deterministic selection | **6 passed** |
| Full deterministic backend suite | **1108 passed, 4 skipped, 115 deselected**, 4 existing warnings |
| Dedicated runtime/PAPER 05 PostgreSQL suite, serial and explicitly dedicated | **38 passed** using `atlas_freeze07_test`; migration test printed head/check success |
| Dedicated Alembic current/check | **0023_paper_runtime_activation (head)**; **No new upgrade operations detected** |
| Affected implementation/test Ruff format and lint | **Passed** |
| Affected implementation/migration Pyright slice | **0 errors, 0 warnings, 0 informations** |
| Git whitespace | **Passed** with `git diff --check` |

## Validation limitations

- The immutable canonical R004 `VALIDATION.md` remains marked `FAIL` for its
  then-unavailable dedicated database and required all-changed-file Pyright
  gate. Later independent R005/R006 validation supplied serial dedicated
  PostgreSQL evidence, and the current review reran the relevant dedicated
  suite successfully. The old artifact was not changed.
- Repository-wide and all-changed-file Pyright remain non-clean at the
  documented baseline (`2987` and `123` diagnostics respectively), concentrated
  in pre-existing app/test typing. The affected implementation/migration slice
  is clean; no diagnostic is attributed to R004–R006.
- An initial multi-file integration invocation without the explicit integration
  isolation plugin encountered fixture residue/duplicate test seed rows. It was
  not used as evidence; the dedicated suite was rerun serially with the
  repository's integration isolation conftest explicitly loaded and passed.

## Review receipt

- **Verdict:** `PASS`
- **CRITICAL findings:** None
- **IMPORTANT findings:** None
- **MINOR findings:** None
- **Capital safety:** No credentials, activation, PAPER/LIVE operation, or
  real OANDA mutation was performed.
- **Files changed by this review:** this `REVIEW.md` only.
