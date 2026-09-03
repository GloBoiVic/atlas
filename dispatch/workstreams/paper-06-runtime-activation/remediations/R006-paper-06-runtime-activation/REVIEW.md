# R006 — Exact `risk_per_trade` persistence

- **Status:** `PASS`
- **Role:** `REVIEW`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin:** Original `REVIEW.md` `IMPORTANT-03`
- **Review mode:** Independent review of the complete corrected workstream after the approved R004–R006 batch.

## Decision

`PASS`. The corrected R004–R006 batch closes all three original IMPORTANT
product findings. No unresolved CRITICAL, IMPORTANT, or MINOR product finding
remains in the reviewed scope.

## Review scope

- Inspect the original finding, PLAN/ARCHITECTURE, R004–R006 BUILD and validation evidence, implementation diff, model, migration, repository, Risk, and activation identity seams.
- Specifically judge exact Decimal request → persistence → load → `RiskConfig` → same-ID replay, changed-risk conflict, PostgreSQL unconstrained NUMERIC schema, migration history, and no binary float/arbitrary workaround.
- Also inspect the R004 unsafe truth/flatness separation, R005 non-MT4 proof before `RUNNING`, complete authority boundaries, and all combined validation limitations.
- No application/test/evidence edits beyond this assigned review artifact; no credentials, activation, real OANDA request, broker mutation, PAPER, or LIVE operation.

## Findings

### CRITICAL

None.

### IMPORTANT

None.

## Remediation closure

### R004 — Terminal P05 outcome safety

`is_unsafe_paper_attempt` is now the shared safety classification used by
activation eligibility, runtime account-observation gating, outstanding
reconciliation detection, and interrupted-cycle recovery. Definite
`REJECTED`, `CANCELLED`, and `FILLED_PROTECTED` outcomes with `NOT_RUN` are
allowed to reach fresh account truth; UNKNOWN, protection-incomplete,
unresolved/conflicted, missing, and malformed truth remains unsafe. A
`FILLED_PROTECTED` result is not treated as current flatness: fresh normalized
account facts still control read-only Strategy input and the later FLAT/
zero-pending entry gate.

### R005 — Non-MT4 startup capability

Startup delegates to the normalized, read-only
`OandaPracticeAccountPropertiesReader` while the activation is `STARTING`,
before full Account Details/bootstrap checks and before `RUNNING`. The reader
requires exactly the configured account and `mt4AccountID is None`; invalid,
mismatched, MT4-associated, or unavailable facts remain bounded fail-closed
outcomes. Production composition shares this reader with PAPER 05 and the
runtime has no direct OANDA mutation seam.

### R006 — Exact Risk identity and persistence

The HTTP/domain boundary accepts only finite Decimal values in `(0, 1)` and
rejects JSON numbers before they can become activation authority. The runtime
model and unmerged `0023` migration use unconstrained PostgreSQL `NUMERIC`
with Decimal result handling. Repository identity canonicalizes the loaded
Decimal, so exact ordinary, >10-fractional-digit, near-boundary, same-ID
replay, and changed-risk conflict behavior is preserved. Migration history is
linear and the upgrade/downgrade/upgrade cycle is reversible.

The broader boundary review also found the required owner-generation guards,
STOP/ENTRY row-lock ordering, caller-owned cycle/attempt/claim transaction,
PAPER 05-only opening authority, read-only restart recovery, and no direct
runtime-to-broker mutation path intact.

## Review receipt

- **Verdict:** `PASS`
- **CRITICAL findings:** None
- **IMPORTANT findings:** None; original `IMPORTANT-01`, `IMPORTANT-02`, and `IMPORTANT-03` are closed by R004, R005, and R006.
- **MINOR findings:** None.
- **Evidence:** Independent source review plus focused deterministic checks (`101 passed`) and the dedicated serial PostgreSQL runtime/migration/repository/completion/ownership suite (`17 passed`). Fresh R005/R006 validation also records the focused cross-remediation regressions, dedicated migration cycle, Alembic head/check, and exact Decimal round trips.
- **Limitations:** Repository-wide Pyright and all-changed-file Pyright retain the documented pre-existing baseline diagnostics; R006 changed implementation/migration Pyright is clean. Full repository suites were not rerun by this review and are not claimed here.
- **Capital safety:** No credentials, activation, real OANDA request, broker mutation, PAPER/LIVE operation, or capital-capable action was performed.
- **Files changed by this review:** this `REVIEW.md` only.
