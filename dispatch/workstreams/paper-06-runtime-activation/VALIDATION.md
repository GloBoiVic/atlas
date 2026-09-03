# PAPER 06 — Original Validation

- **Status:** `FAIL`
- **Role:** `VALIDATE`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Scope:** Independent validation of the approved PLAN, ARCHITECTURE, T001–T008 receipts, implementation diff, deterministic behavior, PostgreSQL migration/concurrency evidence, API boundary, and safe completion gates.

## Decision

`FAIL`. The focused deterministic and PostgreSQL evidence is substantially green,
but the implementation does not yet satisfy the frozen runtime and ownership
boundaries. Two critical findings can permit either a non-operating runtime or a
dependent broker mutation after runtime ownership has been lost.

## Evidence

### Artifacts and implementation reviewed

- Read the approved `PLAN.md`, frozen `ARCHITECTURE.md`, `ACTIVE.md`,
  `VALIDATION.md`, and T001–T008 BUILD receipts.
- Inspected the implementation diff and the relevant untracked PAPER 06
  runtime/API, migration, repository, and test files.
- Reviewed `backend/runtime/main.py`, runtime activation/orchestration/ownership/
  cycle contracts, runtime persistence and migration, API wiring, PAPER 05
  durable execution, OANDA protection completion, and focused tests.
- Branch and repository were verified as `solo/paper-06-runtime-activation` at
  `/Users/vike/Desktop/atlas`. No branch or Git history changes were made.

### Checks run

| Check | Result |
| --- | --- |
| Focused deterministic runtime/API/PAPER tests | `89 passed`, 1 existing Starlette/httpx deprecation warning |
| Dedicated PostgreSQL runtime completion/repository/migration/ownership tests | `14 passed` |
| `alembic current` against dedicated test DB | `0023_paper_runtime_activation (head)` |
| `alembic check` against dedicated test DB | `No new upgrade operations detected` |
| Changed runtime/PAPER source Pyright | `0 errors, 0 warnings, 0 informations` |
| `git diff --check` | Passed |
| Nested secret-key boundary probe | Failed: a secret-key sentinel nested inside a list within a list was accepted |
| Changed runtime/PAPER Ruff check | Failed: 3 `E501` errors in `backend/persistence/runtime_repository.py` |
| Changed runtime/PAPER Ruff format check | Failed: `backend/persistence/runtime_repository.py` would be reformatted |

The full integration suite timed out at both 120 seconds and 300 seconds. The
full non-integration suite also timed out; those runs are limitations, not
failures attributed to individual tests. No real OANDA request, credentialed
operation, activation, or broker mutation was performed.

## Findings

### CRITICAL-01 — Owner loss is not fenced between the Take Profit claim and PUT

**Evidence:**

- `backend/paper/durable_execution.py:330-350` invokes `mutation_guard()` and
  commits the Take Profit claim, then invokes the callback.
- `backend/integrations/oanda/execution.py:1448-1463` invokes the callback and
  then immediately calls `put_trade_orders(...)`.
- `backend/runtime/orchestration.py:1320-1349` uses the callback to persist
  `TAKE_PROFIT_CLAIMED`, but there is no owner assertion after that transaction
  and immediately before the PUT.

This violates ARCHITECTURE §4 ownership-loss fencing, which explicitly includes
“post-claim network dispatch not already protected by a valid owner.” A lock or
durable-generation loss after the claim commit can therefore leave the current
process able to issue the dependent PUT. Existing cross-seam coverage proves
read-only restart behavior after a process-loss callback, but does not prove
the owner-loss race after a successful claim commit and before PUT dispatch.

**Required disposition:** Block PAPER 06 until the dependent mutation boundary
has an immediately preceding valid-owner fence and a deterministic owner-loss
test covers the claim-commit-to-PUT window.

### CRITICAL-02 — The executable `atlas-runtime` process never runs the orchestrator

**Evidence:**

- `pyproject.toml:20-21` exposes `atlas-runtime = "backend.runtime.main:main"`.
- `backend/runtime/main.py:17-39` creates Settings, checks the database, logs
  readiness, and then waits for the stop event. It never constructs
  `PaperRuntimeOwner`, `PaperRuntimeOrchestrator`, provider readers, or the
  fixed-cadence runtime loop.
- `backend/api/app.py:110-129` wires `PaperRuntimeService` for API activation,
  but does not wire that activation service to a running orchestrator process.

The orchestration class and unit tests exist, but the supported executable
runtime remains readiness-only. An explicit activation can become durable while
no process performs startup recovery, frontier polling, Strategy evaluation, or
PAPER execution. This leaves the primary approved outcome unavailable in the
actual process boundary.

**Required disposition:** Block completion until the runtime entrypoint has a
safe production construction/wiring path for the already-approved orchestrator
and loop, while preserving idle-without-activation behavior.

### IMPORTANT-01 — Nested JSON secret rejection is incomplete

**Evidence:**

- `backend/runtime/persistence_contracts.py:209-221` recursively checks mapping
  values and dictionaries directly inside lists, but does not recurse when a
  list contains another list.
- A direct probe of `validate_runtime_json_object` with a secret-key sentinel
  at that nested depth returned the object instead of raising
  `PaperRuntimePersistenceError`.

The activation/cycle JSONB boundary is required to be secret-free by
ARCHITECTURE §3.1 and §4.1. A nested parameter/evidence payload can therefore
carry a credential-bearing field past validation and into durable JSONB.

**Required disposition:** Reject forbidden keys recursively through arbitrary
bounded list/object nesting, with regression coverage that does not print or
persist real secret material.

### MINOR-01 — Runtime repository changed slice fails formatting/lint gates

`backend/persistence/runtime_repository.py:525`, `:529`, and `:530` exceed the
configured 88-character Ruff line length. Ruff format also reports that this
file would be reformatted. This is not the reason for the safety verdict, but
the changed-slice static gate is not clean.

### MINOR-02 — Domain cycle object does not enforce attempt identity by status

`PaperRuntimeCycle.__post_init__` validates the type of `attempt_id` and rejects
an attempt on non-opening terminal statuses, but it permits
`ENTRY_CLAIMED`/`ENTRY_RESOLVED`/`TAKE_PROFIT_CLAIMED` without an attempt ID.
The normal orchestration path supplies the attempt ID atomically, and the
focused tests passed; this is a defense-in-depth contract gap because the
durable cycle status matrix binds opening/protection statuses to P05 claim
identity.

## Positive evidence and limitations

- Local API capability/activation/control paths, exact Strategy identity checks,
  fixed-scope persistence, ownership-generation tests, migration constraints,
  no-catch-up behavior, read-only restart recovery, and focused PAPER 05
  composition tests passed in the executed selections.
- The dedicated PostgreSQL database was reachable and at the expected migration
  head; no schema drift was detected.
- Repository-wide Ruff and Pyright were not used as PASS gates because they
  include unrelated existing violations; however, strict Pyright including the
  changed `backend/api/app.py` separately reported existing-style `Any | None`
  typing errors, so the repository-wide static baseline is not clean.
- Full integration and full non-integration runs did not complete within the
  available timeouts. The focused results above are the completed evidence.

## Validation receipt

- **Verdict:** `FAIL`
- **Critical findings:** `CRITICAL-01`, `CRITICAL-02`
- **Additional findings:** `IMPORTANT-01`, `MINOR-01`, `MINOR-02`
- **Capital safety:** No capital-capable operation was authorized or performed.
- **Files changed by this validation:** this `VALIDATION.md` only.
