# PAPER 06 — Original Workstream Review

- **Status:** `FAIL`
- **Role:** `REVIEW`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Scope:** Independent review of the approved PLAN/ARCHITECTURE, T001–T008 BUILD evidence, original validation, R001–R003 remediation chains, current implementation diff, and deterministic/PostgreSQL checks.

## Decision

`FAIL`. R001–R003 are independently verified as bounded remediations, and the
original `CRITICAL-01`, `CRITICAL-02`, and nested JSON/static findings are
closed. The current implementation still has three unresolved `IMPORTANT`
findings affecting repeated runtime operation, exact account capability, and
exact Risk approval identity.

## Evidence

- Verified repository root `/Users/vike/Desktop/atlas`, branch
  `solo/paper-06-runtime-activation`, and the complete active workstream and
  remediation evidence. No branch or Git history changes were made.
- Inspected runtime composition/orchestration, ownership and persistence
  contracts/repository/migration, activation/API boundaries, current frontier
  and Strategy seam, PAPER 05 durable execution/reconciliation, OANDA account
  readers, and focused tests.
- Full deterministic suite: `1052 passed, 4 skipped, 112 deselected` with
  four existing warnings.
- Full integration suite on dedicated `atlas_freeze07_test`: `111 passed,
  1057 deselected` with four existing warnings.
- `alembic current`: `0023_paper_runtime_activation (head)`; `alembic check`:
  no new upgrade operations.
- All 35 changed Python files passed Ruff format/check. R003's exact changed
  slice passed Pyright with zero diagnostics; repository-wide Ruff/Pyright
  remain non-clean because of unrelated baseline violations.
- A read-only PostgreSQL probe confirmed `numeric(30,10)` rounds
  `0.12345678901` to `0.1234567890` and `0.00000000001` to zero.
- No credentials, activation, real OANDA request, broker mutation, PAPER/LIVE
  operation, or capital-capable action was used.

## Findings

### CRITICAL

None.

### IMPORTANT-01 — Normal terminal P05 outcomes remain falsely unsafe while reconciliation is `NOT_RUN`

`PaperRuntimeRepository.has_unsafe_attempt` treats any attempt with
`reconciliation_status IN ('NOT_RUN', 'UNRESOLVED', 'CONFLICT')` as unsafe
(`backend/persistence/runtime_repository.py:560-580`). A normal P05 result
persists `execution_outcome` through `apply_result`
(`backend/paper/durable_execution.py:378-390`; `backend/persistence/paper_execution_repository.py:570-608`) but does not change the default
`reconciliation_status = 'NOT_RUN'` (`backend/persistence/models.py:957-963`).
The next runtime observation checks `has_unsafe_attempt` before reading the
fresh account (`backend/runtime/orchestration.py:1094-1101`).

Consequently, after a normal `FILLED_PROTECTED`, `REJECTED`, or `CANCELLED`
attempt, the runtime cannot reach the next fresh account observation and
repeated frontier processing. It blocks instead of continuing read-only
Strategy progression while known exposure is open; the activation service also
rejects a new activation for terminal attempts left at `NOT_RUN`.

**Required disposition:** distinguish terminal P05 outcomes from unresolved or
protection-incomplete outcomes in both unsafe-attempt predicates, and add
regression coverage for normal terminal results with `NOT_RUN` status followed
by fresh runtime observation/activation behavior.

### IMPORTANT-02 — Non-MT4 account capability is not proven before `RUNNING`

The only non-MT4 proof is `OandaPracticeAccountPropertiesReader`, whose
normalizer rejects a non-null `mt4AccountID` (`backend/integrations/oanda/execution_account.py:184-228`). The production composition creates that reader only inside
PAPER 05 durable execution (`backend/runtime/main.py:109-142`), while runtime
startup reads only full Account Details and transitions to `RUNNING`
(`backend/runtime/orchestration.py:847-910`). The capability and activation
service only validate the syntactic account ID (`backend/runtime/activation.py:462-477`).

An MT4-associated configured account can therefore be advertised as available
and reach `RUNNING`; an opening later reaches P05 and is refused rather than
mutated. That remains capital-safe but violates the frozen exact capability and
the requirement that provider capability/account facts be proven before
`RUNNING`.

**Required disposition:** perform a bounded read-only non-MT4 capability proof
before `RUNNING` (or make an equivalent explicit startup gate), with tests for
MT4-associated and non-MT4 account facts.

### IMPORTANT-03 — `risk_per_trade` is not an exact durable activation snapshot

The HTTP/domain activation request accepts any finite `Decimal` strictly
between zero and one (`backend/api/schemas.py:40-57`; `backend/runtime/activation.py:99-118`), but the migration stores it as `NUMERIC(30,10)`
(`backend/persistence/migrations/versions/0023_paper_runtime_activation.py:15-18,37`). PostgreSQL therefore rounds values with more than ten fractional digits. The exact replay identity compares the original canonical Decimal with the rounded row (`backend/persistence/runtime_repository.py:187-227`).

For example, `0.12345678901` is persisted as `0.1234567890`, so the runtime
Risk snapshot is changed and the same activation request can return
`ACTIVATION_IDENTITY_CONFLICT` on replay. Values near `1e-11` can round to zero
and fail persistence. This violates the exact trader-approved
`RiskConfig.risk_per_trade` snapshot requirement.

**Required disposition:** preserve the accepted Risk precision exactly, or
reject/normalize it before activation identity is created, and add round-trip
and same-ID replay coverage at the precision boundary.

### MINOR

None beyond the recorded repository-wide static baseline limitations.

## Limitations

- Repository-wide `ruff format --check backend`, `ruff check backend`, and
  `pyright backend` are not clean because they include unrelated pre-existing
  violations; the changed Python slice is clean under Ruff.
- Frontend checks were not run: `npm` is unavailable, and no frontend code is
  in this workstream scope.

## Review receipt

- **Verdict:** `FAIL`
- **CRITICAL findings:** None
- **IMPORTANT findings:** `IMPORTANT-01`, `IMPORTANT-02`, `IMPORTANT-03`
- **MINOR findings:** None
- **Capital safety:** No credentials, activation, PAPER/LIVE operation, or real OANDA mutation was performed.
- **Files changed by this review:** this `REVIEW.md` only.
