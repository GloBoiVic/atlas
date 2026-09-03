# R004 — Terminal P05 outcome safety classification

- **Status:** `FAIL`
- **Role:** `VALIDATE`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin:** Original `REVIEW.md` `IMPORTANT-01`
- **Validation mode:** Fresh independent validation of the combined current HEAD after BUILD R004, R005, and R006.

## Decision

`FAIL`. The deterministic functional evidence for all three remediations passed,
but the mandatory dedicated PostgreSQL evidence could not run because
`ATLAS_TEST_DATABASE_URL` is unset, and the requested all-changed-file Pyright
gate fails with 123 diagnostics. The implementation-only R004–R006 Pyright
slice is clean; that narrower result does not convert the required changed-file
gate to PASS.

## Scope and safety

- Verified repository root `/Users/vike/Desktop/atlas`, branch
  `solo/paper-06-runtime-activation`, and the combined dirty BUILD state before
  validation. No branch or Git history operation was performed.
- Read the approved `PLAN.md`, `ARCHITECTURE.md`, original `REVIEW.md`, and
  R004/R005/R006 BUILD receipts plus the directly affected runtime, OANDA,
  persistence, migration, and test seams.
- Tests used local fakes and `httpx.MockTransport` only. No credentials,
  activation, real OANDA request, broker mutation, PAPER, or LIVE operation
  was performed.

## Original findings reproduced

### IMPORTANT-01 / R004 — P05 terminal-attempt safety

The current implementation centralizes the predicate in
`backend/persistence/runtime_repository.py:is_unsafe_paper_attempt` and uses
the equivalent SQL predicate in `has_unsafe_attempt`, which is consumed by
activation eligibility and runtime account-observation gating. The unit matrix
was independently exercised through `test_paper_attempt_safety_truth_table`,
`test_activation_eligibility_uses_the_terminal_safety_matrix`, and
`test_unsafe_outcome_fences_account_observation`:

| Execution outcome | Reconciliation status | Expected safety | Result |
| --- | --- | --- | --- |
| `REJECTED` | `NOT_RUN` | safe | PASS |
| `CANCELLED` | `NOT_RUN` | safe | PASS |
| `FILLED_PROTECTED` | `NOT_RUN` | safe for a fresh observation | PASS |
| `UNKNOWN` | `NOT_RUN` | unsafe | PASS |
| `FILLED_PROTECTION_INCOMPLETE` | `NOT_RUN` | unsafe | PASS |
| definite outcome | `UNRESOLVED` | unsafe | PASS |
| definite outcome | `CONFLICT` | unsafe | PASS |
| missing outcome/status | any | unsafe | PASS |
| invalid/malformed outcome/status | any | unsafe | PASS |

`test_terminal_not_run_outcome_reaches_fresh_account_observation` proves all
three normal terminal outcomes reach a fresh account read. The repeated-runtime
regression `test_repeated_runtime_keeps_filled_history_separate_from_fresh_entry_gate`
proves: a historical `FILLED_PROTECTED` result does not substitute for current
account truth; a known attributable open `LONG` state advances Strategy
read-only with no new entry/P05 preparation; a later fresh `FLAT`, zero-pending
observation permits the later opening path. The restart matrix also proves
`FILLED_PROTECTED` recovery requires its dependent Take Profit claim, while
unknown, incomplete, unresolved, conflicted, missing, and malformed truth
blocks recovery.

The SQL predicate itself was inspected, but its PostgreSQL execution was not
independently exercised because the dedicated database suite was unavailable.

### IMPORTANT-02 / R005 — non-MT4 capability before `RUNNING`

`OandaPracticeAccountPropertiesReader` remains the provider-specific,
read-only normalization seam. `test_startup_proves_non_mt4_capability_before_running`
proves the successful exact configured non-MT4 AccountProperties read occurs
before Account Details and before `RUNNING`. MT4-associated, empty/missing,
mismatched, malformed-ID, and malformed-MT4 facts block with bounded
`STARTUP_CAPABILITY_INVALID`; repeated HTTP 503 failure remains `STARTING` with
`WAITING_PROVIDER` / `STARTUP_READ_UNAVAILABLE` and never reads Account Details.
The OANDA capability regression additionally covers invalid AccountProperties
shape/type cases. Production-composition coverage proves the same normalized
reader instance is shared with PAPER 05 preparation; runtime orchestration only
treats successful provider normalization as proof and has no direct mutation
seam.

### IMPORTANT-03 / R006 — exact `risk_per_trade` persistence

The static/model and deterministic request tests pass for exact Decimal values
`0.01`, `0.12345678901`, and `0.00000000001`; the runtime model and unmerged
0023 migration now use unconstrained PostgreSQL `NUMERIC` rather than
`NUMERIC(30,10)`. A read-only probe against the existing non-dedicated local
database reproduced the original loss:

```text
NUMERIC(30,10): 0.1234567890, 0E-10
NUMERIC:        0.12345678901, 1E-11
```

The dedicated integration tests contain the required exact loaded
`RiskConfig`, same-ID replay, changed-risk identity conflict, and
upgrade→downgrade→upgrade assertions, but all were skipped because no
dedicated `*_test` database was available. Therefore exact PostgreSQL
round-trip closure is not independently validated in this pass.

## Checks and results

| Check | Command/result |
| --- | --- |
| Focused PAPER 06 runtime/activation | `uv run pytest -q backend/tests/runtime backend/tests/test_runtime.py` — **127 passed** |
| PAPER 05 execution/reconciliation | `uv run pytest -q backend/tests/paper/test_execution_contracts.py backend/tests/paper/test_execution_composition.py backend/tests/paper/test_durable_execution.py backend/tests/paper/test_reconciliation.py backend/tests/paper/test_persistence_contracts.py` — **54 passed** |
| OANDA AccountProperties/execution regressions | `uv run pytest -q backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_execution_translation.py backend/tests/integrations/test_oanda_reconciliation.py` — **36 passed** |
| Risk/activation identity | `uv run pytest -q backend/tests/runtime/test_runtime_risk_precision.py backend/tests/risk/test_service.py backend/tests/test_api_paper.py backend/tests/test_migration_revision.py` — **29 passed**, 1 existing warning |
| Deterministic backend suite | `uv run pytest -m 'not integration and not external' -q` — **1108 passed, 4 skipped, 115 deselected**, 4 existing warnings |
| Runtime concurrency/ownership/STOP unit regressions | `uv run pytest -q backend/tests/runtime -k 'stop or owner or ownership or concurrency'` — **10 passed**, 109 deselected |
| Runtime persistence/cycle regressions | `uv run pytest -q backend/tests/runtime/test_runtime_persistence.py backend/tests/runtime/test_runtime_cycles.py` — **20 passed** |
| PAPER 05/OANDA integration regressions | `uv run pytest -q backend/tests/integration/test_paper_execution_repository.py backend/tests/integrations/test_oanda_reconciliation.py` — **11 passed, 10 skipped** |
| Dedicated PAPER 06 PostgreSQL suite | `uv run pytest -q backend/tests/integration/test_runtime_migration.py backend/tests/integration/test_runtime_repository.py backend/tests/integration/test_runtime_completion.py backend/tests/integration/test_runtime_ownership.py` — **17 skipped**; `ATLAS_TEST_DATABASE_URL` was confirmed **UNSET** |
| Alembic current | `uv run alembic current` — exit 0, local non-dedicated DB at `0020_fix_snapshot_guard` |
| Alembic check | `uv run alembic check` — **exit 255**, `Target database is not up to date` |
| Changed-file Ruff format | `uv run ruff format --check` over all 36 changed Python files — **passed** |
| Changed-file Ruff lint | `uv run ruff check` over all 36 changed Python files — **passed** |
| Required all-changed-file Pyright | `uv run pyright` over all changed Python files — **FAIL**, 123 errors, 0 warnings/informations: `backend/api/app.py` 25, `backend/tests/runtime/test_runtime_activation.py` 96, `backend/tests/test_api_paper.py` 2 |
| R004–R006 changed implementation Pyright | `uv run pyright` over the affected implementation/migration files — **0 errors, 0 warnings, 0 informations** |
| Git whitespace | `git diff --check` and no-index checks for untracked changed files — **passed** |

## Findings and limitations

1. **Validation blocker — dedicated PostgreSQL evidence unavailable.** The
   required R006 exact round-trip, activation replay/conflict, migration
   upgrade→downgrade→upgrade, PostgreSQL ownership/concurrency, and STOP race
   checks did not execute; they are not reported as PASS. The local Alembic
   database was only inspected and was not migrated or otherwise changed.
2. **Validation gate failure — all-changed-file Pyright.** The required
   changed-file invocation reports 123 diagnostics, including 96 in the R004
   runtime activation regression test and 25 in the pre-existing changed
   `backend/api/app.py` slice. The narrower R004–R006 implementation slice is
   clean, but this does not satisfy the explicitly requested all-changed-file
   gate.
3. No deterministic functional regression was observed in the available
   local suite. The unavailable PostgreSQL evidence and failed required static
   gate prevent an overall PASS.

## Validation receipt

- **Verdict:** `FAIL`
- **R004 functional evidence:** deterministic matrix, fresh observation,
  attributable-open read-only progression, no-entry gate, later fresh-flat
  entry gate, and recovery matrix passed; PostgreSQL predicate execution not
  run.
- **R005 functional evidence:** startup AccountProperties proof ordering,
  non-MT4/invalid/unavailable cases, bounded reasons, shared read-only
  composition, and OANDA regressions passed.
- **R006 functional evidence:** deterministic exact Decimal/model/migration
  assertions passed and the old scale-loss was reproduced read-only; actual
  PostgreSQL round-trip/replay/migration integration was unavailable.
- **Mandatory gate failures:** dedicated PostgreSQL suite unavailable;
  all-changed-file Pyright failed; Alembic check failed on the non-dedicated
  stale local database.
- **Files changed by this validation:** this `VALIDATION.md` only.
