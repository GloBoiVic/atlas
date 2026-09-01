# PAPER 01 — C004 V-C004-01a Independent Rereview

ROLE: REVIEW  
WORKSTREAM: paper-01  
BRANCH: solo/paper-01  
CWD: /Users/vike/Desktop/atlas  
TASK: NONE  
OWNED_ARTIFACT: dispatch/workstreams/paper-01/REVIEW.md  
SPECIALIST_SKILLS: tdd, supabase-postgres-best-practices

**Status:** `FAIL — NEW CRITICAL C004 FINDINGS — NOT READY_TO_ACTIVATE`

## Verdict and scope

This is a fresh, targeted rereview of the approved `V-C004-01a` boundary against
the frozen PLAN, ARCHITECTURE, IMPLEMENTATION-CLOSURE C004/H-I contract, C004 task
receipt, prior review findings, current remediation source/tests, and fresh
validation evidence. No application, test, fixture, migration, credential,
provider, or Git-history change was made.

The cursorless local canonical-state remediation is present and passes its
enumerated PostgreSQL cases. C004 as a whole is not closed: the existing-cursor
Account Changes path and the durable lifecycle-gate seam still have fail-open
defects. A new CRITICAL C004 invariant was found; this review stops here and does
not request or trigger another remediation.

## Findings

### V-C004-02 — CRITICAL — successful repair can forge the durable gate

**Contract breached:** C004/I and the approved V-C004-01 requirement that
`_ensure_running` accept only a reconciliation result carrying a proven durable
baseline or Account Changes catch-up gate.

**Evidence:**

- `backend/runtime/coordinator.py:330-343` and `:355-373` accept a repair result
  whose outcome is `MATCHED`/`REPAIRED`, but reconstruct the returned result with
  `durable_gate_proven=True` instead of preserving and requiring
  `repaired.durable_gate_proven`.
- `_reconciliation_allows_runtime` at `backend/runtime/coordinator.py:1078-1083`
  therefore sees a forged proof and permits the coordinator's later
  `RUNNING` transition.
- An independent seam probe using the current `ReadOnlyReconciler` produced
  `REPAIRED, durable_gate_proven=True` when the injected repair returned
  `REPAIRED, durable_gate_proven=False`.

The concrete current store sets the flag on its intended successful paths, but
the lifecycle enforcement seam does not enforce that fact. This violates the
frozen gate contract and leaves a fail-open route to `RUNNING` whenever a repair
implementation returns success without durable proof.

### V-C004-03 — CRITICAL — Account Changes Order resolution advances the cursor without applying the Order projection

**Contract breached:** C004/D, C004/F, C004/G, and C004/I. A transaction that
changes a canonical broker-linked ENTRY Order must be durably applied or block;
the cursor may not advance while the local Order remains unresolved.

**Evidence:**

- In `backend/runtime/store.py:2216-2234`, matching `ORDER_CREATE`,
  `ORDER_CANCEL`, `ORDER_REJECT`, `STOP_LOSS_ORDER`, and `TAKE_PROFIT_ORDER`
  transactions only set `canonical_order` and increment an observation count.
  They do not update `OrderModel.current_status` or append the corresponding
  Order event.
- The receipt is then written as `OBSERVED_NO_PROJECTION` at
  `backend/runtime/store.py:2236-2255`, followed by the successful cursor
  update at `:2277-2283`.
- For a local `PENDING_SUBMISSION`/`UNKNOWN` ENTRY Order that OANDA has
  canceled or rejected, the current-account read can show no pending broker
  Order, causing reconciliation to invoke this repair. The method can return
  `REPAIRED` with a durable gate while the local ENTRY Order remains unresolved;
  the coordinator can then reach `RUNNING`.

This is not an acceptable `OBSERVED_NO_PROJECTION` transaction: the matching
provider Order change requires a canonical Order lifecycle mutation. It also
leaves subsequent cursor reuse unable to recover the already-consumed change.

### V-C004-04 — IMPORTANT — known full-fill recovery for an UNKNOWN Order is not implemented

The frozen reconciliation matrix permits an UNKNOWN Order with one clear full
Fill to be repaired after current Trade/Position/protection proof. The public
`SqlAlchemyRuntimeStore.repair_reconciliation` ORDER_FILL branch does not first
resolve an `UNKNOWN` Order to a fill-eligible state. It calls `apply_fill` at
`backend/runtime/store.py:2205`; `apply_fill` explicitly rejects `UNKNOWN` at
`backend/execution/fill_application.py:120-123`. The path therefore blocks and
retains the old cursor even when the Account Changes evidence is otherwise
unambiguous. This is fail-closed, but it is an incomplete C004 UNKNOWN recovery
contract and is not covered by the PostgreSQL success test (which seeds
`PENDING_SUBMISSION`).

## Approved V-C004-01a matrix

| INVARIANT | AUTHORITY | ENFORCEMENT LOCATION | DB ENFORCEMENT | TEST | STATUS |
|---|---|---|---|---|---|
| Cursorless broker-flat/current selected-account Details fence | C004/H | `OandaReadOnlyBrokerReader.read`; `repair_reconciliation` | Numeric cursor and account FK | Reader no-Account-Changes regression; flat PostgreSQL baseline | **PASS for covered path** |
| Cursorless local EUR/USD Position is flat/clean | C004/H, V-C004-01a | `_local_state_is_safe_for_initial_cursor` in the authoritative baseline transaction | Position constraints; row lock | Open/contradictory-shape guard and PostgreSQL open Position case | **PASS for covered cases** |
| Open Trade, unresolved Fill/Order, and pending opening handoff/Intent block baseline | V-C004-01a | Same transaction-local local-state proof | Canonical root FKs/constraints | PostgreSQL open Trade, Fill, unresolved Order, handoff/Intent cases | **PASS for covered cases** |
| Baseline rejection retains NULL cursor and durable safety block | C004/G/H | Rollback then `_record_account_changes_failure` | Cursor row remains absent | PostgreSQL rejection cases | **PASS for covered cases** |
| No synthetic Account Changes request without a cursor | V-C004-01 | Reader calls Account Changes only when durable cursor is non-NULL | Cursor persistence | Recorded GET shape and cursorless reader regression | **PASS** |
| Existing cursor uses exact Account Changes response and selected account | C004/D | Reader normalization and `repair_reconciliation` | Account-scoped receipt uniqueness | One successful ORDER_FILL path only | **PARTIAL — V-C004-03** |
| Every returned canonical Order/Fill change is applied before cursor update | C004/F/G | Receipt/projection/cursor transaction | Receipt uniqueness and FKs | No multi-transaction or Order-cancel/reject projection case | **FAIL — V-C004-03** |
| Failure rolls back receipts/projections/cursor and durably blocks | C004/G | Single application transaction plus separate safety transaction | PostgreSQL rollback | Fill collision and conflicting receipt replay | **PASS for covered cases** |
| Cursor update is the final successful write | C004/G | `advance_cursor` after receipt/projection/evidence writes | Cursor monotonicity | Source ordering and covered PostgreSQL checks | **PASS for covered cases; Order projection gap remains** |
| Restart reuses persisted cursor | C004/I | Reader callback to durable account cursor | Account cursor PK | Runtime restart cursor regression | **PASS** |
| START/RESUME/reconnect/ownership reacquisition/UNKNOWN require durable proof before RUNNING | C004/I, V-C004-01 | Reconciler result and coordinator gate | Durable cursor/baseline | Four cursorless lifecycle cases; no false-proof propagation case | **FAIL — V-C004-02** |

## Validation evidence review

I independently reran the exact targeted command using only the supplied
isolated database:

```text
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@127.0.0.1:5432/atlas_test' pytest -q -rs -p no:cacheprovider \
  backend/tests/runtime/test_coordinator.py \
  backend/tests/runtime/test_production_runtime.py \
  backend/tests/integrations/test_oanda_execution.py \
  backend/tests/integrations/test_oanda_paper_contracts.py \
  backend/tests/integration/test_runtime_store_reconciliation.py \
  backend/tests/integration/test_migrations.py \
  backend/tests/test_migration_revision.py \
  backend/tests/persistence/test_paper_persistence.py
```

Result: **86 passed in 35.22s; 0 skipped**.

I also ran the supplied-database drift check:

```text
ATLAS_DATABASE_URL='postgresql+psycopg://vike@127.0.0.1:5432/atlas_test' \
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@127.0.0.1:5432/atlas_test' alembic check
```

Result: **PASS — No new upgrade operations detected**. Ruff and Pyright on the
affected runtime/review-test modules also passed. The 86-pass/0-skip result is
credible as PostgreSQL-backed execution of the listed tests. It does not prove
the missing Order projection, UNKNOWN full-fill recovery, or false durable-gate
regression; the integration fixture contains only `ORDER_FILL` transaction
coverage for the Account Changes application path.

## Scope and carried gates

- No C001-C003, C005, Risk-policy, credential, activation, or mutating OANDA
  change was attributed to this rereview. The pre-existing dirty worktree was
  preserved; the only file changed by this role is this `REVIEW.md`.
- Provider-facing validation used recorded/mock GET-only transports. No OANDA
  credentials were read, no POST/PUT/PATCH/DELETE/cancel/close/transfer request
  was made, and no Order was submitted.
- **F-07 remains carried:** PRODUCT BLOCKER for missing official OANDA
  session-policy provenance. Actual `RUNNING`/activation and
  `READY_TO_ACTIVATE` remain unauthorized.
- The supplied PostgreSQL environment resolves the prior availability portion of
  F-09 for the executed checks, but this review does not claim the complete
  workstream finish line while C004 has unresolved findings.

## Safety disposition

`C004 = FAIL`. Do not close C004, begin C005, claim `READY_TO_ACTIVATE`, activate
PAPER, or invoke a capital-capable OANDA path. Because new CRITICAL C004
invariants were found, this review stops without proposing or triggering another
remediation.

ROLE: REVIEW  
STATUS: FAIL  
ARTIFACT: dispatch/workstreams/paper-01/REVIEW.md  
FILES CHANGED: dispatch/workstreams/paper-01/REVIEW.md only  
CHECKS / EVIDENCE: 86 PostgreSQL-backed tests passed, 0 skipped; `alembic check`, Ruff, and Pyright passed; source and seam review found V-C004-02/V-C004-03 CRITICAL findings.  
FINDINGS / CONCERNS: C004 remains open; F-07 is carried; no remediation or activation is authorized.
