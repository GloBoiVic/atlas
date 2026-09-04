# VALIDATION — Dogfood 01 Lifecycle-Advanced Activation Fence

ROLE: VALIDATE  
WORKSTREAM: dogfood-01-lifecycle-advanced-activation-fence  
BRANCH: solo/dogfood-01-lifecycle-advanced-activation-fence  
CWD: /Users/vike/Desktop/atlas  
TASK: T001  
OWNED_ARTIFACT: dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/VALIDATION.md  
SPECIALIST_SKILLS: tdd

## Verdict

**PASS — no blocking PRODUCT or REGRESSION defect found.** The implementation matches the
frozen semantic split and remains provider-mutation-free. Concerns below are LOW-severity
validation/tooling limitations and are recorded separately from product findings.

## Independent scope and safety checks

- CWD, repository root, and branch were verified as `/Users/vike/Desktop/atlas` and
  `solo/dogfood-01-lifecycle-advanced-activation-fence`.
- No credentialed OANDA request, runtime start, activation, Dogfood 02 action, historical-data
  change, or broker mutation was performed. `ATLAS_TEST_DATABASE_URL` was not set.
- The diff contains only the expected implementation/tests plus `dispatch/ACTIVE.md`; it
  contains no migration, schema, `backend/paper/reconciliation.py`, or provider-neutral
  reconciliation change.
- Production search found the Dogfood UUID only in the regression fixture
  `backend/tests/runtime/test_runtime_activation.py`.

## Required semantic proof

`runtime_repository.py:106-123` is byte-for-byte unchanged from base `bc53f70`; the strict
predicate still classifies `FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` as unsafe.
The independent enumerated check exercised 64 combinations, plus missing Fill evidence.

| Durable outcome | Reconciliation status/evidence | New session creation | Same-attempt recovery | Startup / entry |
|---|---|---|---|---|
| `REJECTED`, `CANCELLED`, or `FILLED_PROTECTED` | `NOT_RUN`, `CONSISTENT`, or `LIFECYCLE_ADVANCED` | `ALLOW -> REQUESTED` | strict safe behavior | fresh current-account/Risk gates still required |
| Same terminal outcomes | `UNRESOLVED`, `CONFLICT`, null, malformed, or unsupported | `BLOCK` | strict block | block |
| `FILLED_PROTECTION_INCOMPLETE` | `NOT_RUN`, `CONSISTENT`, `UNRESOLVED`, or `CONFLICT` | `BLOCK` | strict block | block |
| `FILLED_PROTECTION_INCOMPLETE` | `LIFECYCLE_ADVANCED` with missing/contradictory qualifier | `BLOCK` | strict block | block |
| `FILLED_PROTECTION_INCOMPLETE` | `LIFECYCLE_ADVANCED` plus complete Fill and linked applied coherent run | `ALLOW -> REQUESTED` | **strict block** | fresh current-account/Risk gates still required |
| `UNKNOWN` | any status, including `LIFECYCLE_ADVANCED` | `BLOCK` | strict block | block |

The classifier requires provider/environment/currency/instrument scope, all durable Fill
identity and value facts, matching attempt/run IDs, applied projection-version continuity,
matching completion timestamps, lifecycle-advanced run status, unchanged incomplete outcome on
both sides, and no reconciliation block code (`runtime_repository.py:126-240`). The account-wide
query joins the attempt's existing applied-run pointer and returns a blocker if **any** row is
unsafe (`runtime_repository.py:738-765`). The Dogfood and synthetic future UUID fixtures have
identical classification without a production UUID exception.

The remaining authority boundaries are preserved:

- Activation POST performs local configuration/history/Strategy validation only and creates a
  new `FRESH_BOOTSTRAP` activation in `REQUESTED`; it does not read the provider or reconcile
  (`activation.py:480-520`, `692-771`). Exact replay/conflict behavior remains unchanged.
- `BLOCKED` is excluded from active activation selection and its transition set is terminal;
  reconciliation does not revive it (`runtime_repository.py:470-490`, `243-280`).
- Startup still requires owner/generation, Strategy provenance, capability, exact configured
  account, full coherent account observation, `FLAT`, zero open Trades, zero open Positions,
  and zero pending Orders before `RUNNING` (`orchestration.py:797-940`; observation coherence
  is enforced in `cycles.py:132-186`). Unsupported capability, identity mismatch, exposure,
  pending Orders, malformed facts, and contradictions fail closed.
- Interrupted claim recovery remains on `is_unsafe_paper_attempt()` (`orchestration.py:942-1022`),
  while fresh account observation uses only the new-session classifier
  (`orchestration.py:1131-1157`). P05 fresh account/instrument/pricing reads, one fresh Risk
  evaluation, owner/generation checks, permanent claims, frontier, STOP, and no-retry barriers
  remain on the existing entry path.
- Existing mutation spies and call-path inspection show no activation/startup/recovery route to
  POST, PUT, cancel, close, reduce, or repair. Cross-seam restart/owner-loss tests prove no
  second POST/PUT and no network call before the durable claim; normal entry mutation remains
  outside this remediation.

## Commands and results

Focused first, as required:

```text
uv run pytest backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/runtime/test_runtime_completion_cross_seam.py
128 passed in 1.82s

uv run pytest backend/tests/paper/test_reconciliation.py
29 passed in 1.26s
```

Independent checks:

```text
uv run python -c '<enumerated classifier/strict-predicate check>'
exhaustive enumerated new-session matrix: 64 rows PASS; strict matrix PASS; missing Fill qualifier PASS

uv run ruff format --check backend/persistence/runtime_repository.py backend/runtime/activation.py backend/runtime/orchestration.py backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_orchestration.py
5 files already formatted

uv run ruff check backend/persistence/runtime_repository.py backend/runtime/activation.py backend/runtime/orchestration.py backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_orchestration.py
All checks passed!

uv run pyright backend/persistence/runtime_repository.py backend/runtime/activation.py backend/runtime/orchestration.py
0 errors, 0 warnings, 0 informations

uv run pytest -m "not integration and not external"
1154 passed, 4 skipped, 115 deselected, 4 warnings in 295.97s

uv run alembic check
No new upgrade operations detected.

git diff --check
passed (no output)
```

The first safe-suite invocation reached the tool's 120-second timeout without a test failure;
the same command was rerun with a 300-second bound and completed with the result above.

## Coverage gaps and concerns

1. **LOW — database integration coverage:** no dedicated `*_test` PostgreSQL URL was available,
   so the new ORM join was not executed against PostgreSQL. `alembic check` passed and no schema
   change is present. This is a validation limitation, not evidence of a product defect.
2. **LOW — explicit scenario granularity:** the focused additions directly test the classifier
   matrix, qualifiers, synthetic UUID, account-wide blocker, strict recovery, and fresh
   observation seam. Old-`BLOCKED` non-revival and an end-to-end accepted lifecycle-ended
   incomplete Fill through activation POST are additionally established by the terminal active
   selection/transition and local activation source paths, but do not have dedicated new
   integration tests in this task. Existing broad runtime/P05/restart/STOP/owner/claim/frontier
   tests passed.
3. **PRE-EXISTING TOOLING:** repository-wide checks remain non-clean outside this slice:
   `uv run ruff format --check backend` reports unrelated unformatted files, `uv run ruff check
   backend` reports `Found 28 errors`, and `uv run pyright backend` reports `2987 errors, 0
   warnings, 0 informations`. Changed-slice format, Ruff, and Pyright checks are clean.

## SoloFlow receipt

ROLE: VALIDATE  
STATUS: PASS  
ARTIFACT: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/VALIDATION.md`  
FILES CHANGED: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/VALIDATION.md` only  
CHECKS / EVIDENCE: focused `157 passed`; safe suite `1154 passed, 4 skipped, 115 deselected`; changed-slice Ruff/Pyright clean; Alembic and diff checks passed; semantic matrix and safety boundaries verified  
FINDINGS / CONCERNS: LOW database integration availability and explicit scenario granularity gaps; repository-wide tooling failures are pre-existing and outside the changed slice
