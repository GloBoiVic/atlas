# PAPER 01 — C004 V-C004-01a Validation

**Status:** `PASS — V-C004-01a`
**ROLE:** `VALIDATE`
**WORKSTREAM:** `paper-01`
**BRANCH:** `solo/paper-01`
**CWD:** `/Users/vike/Desktop/atlas`
**TASK:** `NONE`
**OWNED_ARTIFACT:** `dispatch/workstreams/paper-01/VALIDATION.md`
**SPECIALIST_SKILLS:** `tdd, supabase-postgres-best-practices`

## Scope and basis

Fresh independent validation covers only the approved `V-C004-01a` remediation:
the transaction-local canonical local-state proof in the cursorless baseline.
The frozen C004 contract, PLAN, C004 task receipt, and implementation-closure
artifact were used as authority. No implementation or test changes were made.

## Isolated PostgreSQL evidence

Only the approved isolated database was used:

```text
postgresql+psycopg://vike@127.0.0.1:5432/atlas_test
```

Targeted C004/runtime/OANDA command:

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

Result: **86 passed in 36.02s; 0 skipped**.

The previously skipped PostgreSQL cases were rerun independently with:

```text
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@127.0.0.1:5432/atlas_test' pytest -vv -p no:cacheprovider \
  backend/tests/integration/test_runtime_store_reconciliation.py \
  backend/tests/integration/test_migrations.py
```

Result: **19 passed in 32.02s; 0 skipped**.

This included all 16 PostgreSQL reconciliation cases: fill-identity collision
rollback, submission-cursor non-advancement, Fill preservation after protection
failure, three current-protected-exposure repair guards, one durable Fill/cursor
repair with replay idempotency, conflicting receipt replay rollback, flat initial
baseline, existing local execution, open Position, open Trade, both
`PENDING_SUBMISSION` and `UNKNOWN` Order cases, unresolved broker Fill, and
pending opening handoff/TradeIntent. It also included all three migration cases:
`test_migration_cycle`, `test_downgrade_to_0020_restores_guarded_trigger_dependencies`,
and `test_market_data_constraints_and_immutability`.

Standalone migration drift check against the same database:

```text
ATLAS_DATABASE_URL='postgresql+psycopg://vike@127.0.0.1:5432/atlas_test' \
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@127.0.0.1:5432/atlas_test' alembic check
```

Result: **PASS — No new upgrade operations detected**.

Live Deployment advisory-lock probe against the same PostgreSQL database:

```text
deployment advisory lock exclusivity: PASS; first=True, concurrent-second=False, after-release-second=True
```

The deterministic `test_deployment_lock_key_and_client_correlation_are_stable`
also passed. No separate live lock test is present in the targeted repository
suite; the direct probe verified session-level exclusivity and release.

## Approved behavior matrix

| Invariant | Evidence | Result |
|---|---|---|
| Broker-flat plus local-flat/clean baseline succeeds once and persists the current fence | `test_flat_deployment_initializes_cursor_without_importing_history`: durable gate, cursor `10`, source `OANDA_ACCOUNT_DETAILS_BASELINE`, no receipt/history import | **PASS** |
| Non-flat or contradictory local `PositionModel` blocks in the authoritative baseline transaction | `test_cursorless_baseline_rejects_open_local_position` passed in PostgreSQL; source guard rejects wrong venue, non-`FLAT` state, or non-null quantity/entry/opened facts before baseline writes | **PASS** |
| Open local `Trade` blocks with null cursor and safety state | `test_cursorless_baseline_rejects_open_local_trade` passed; no cursor persisted | **PASS** |
| Unresolved `PENDING_SUBMISSION` and `UNKNOWN` ENTRY Orders block | Both parameter cases of `test_cursorless_baseline_rejects_unresolved_entry_order` passed; no cursor persisted | **PASS** |
| Unresolved broker-linked Fill/Order/Trade fact blocks | Existing local execution and unresolved broker Fill PostgreSQL cases passed; baseline remains blocked | **PASS** |
| Pending opening handoff/TradeIntent blocks | `test_cursorless_baseline_rejects_pending_opening_handoff_and_intent` passed; no cursor persisted | **PASS** |
| Broker/local disagreement and unknown/non-flat broker state block | `test_local_flat_projection_cannot_override_broker_exposure` and cursorless unknown/non-flat runtime regressions passed | **PASS** |
| Existing-cursor catch-up applies facts before advancing the cursor | Durable Fill/cursor test passed (`9` → `10`); submission Fill left cursor at `9`; failed/current-protection and receipt-conflict cases retained the old cursor | **PASS** |
| Cursor-last ordering and rollback remain safe | Runtime ordering regressions passed; collision and conflicting-receipt PostgreSQL cases rolled back projections/receipts as required and durably blocked safety | **PASS** |
| Repeated startup reuses the persisted cursor | `test_restart_reuses_persisted_cursor_for_account_changes` passed and requested cursor `10` on restart | **PASS** |
| START/RESUME/reconnect/ownership reacquisition cannot reach `RUNNING` without durable proof | Four cursorless lifecycle cases passed; durable baseline/catch-up precedes `RUNNING` in the gate | **PASS** |
| Migration and persistence constraints remain valid | 3 PostgreSQL migration cases passed; `alembic check` reported no drift; persistence/UTC/monotonicity checks passed | **PASS** |
| Deployment advisory-lock exclusivity | Direct two-session PostgreSQL probe passed; deterministic key test passed | **PASS** |
| OANDA path is read-only/capital-inert | Mock/recorded transport assertions passed, including exactly `GET` methods; no real provider credentials or mutating endpoint was used | **PASS** |

## Scope and safety disposition

No application, tests, fixtures, migrations, harness, selectors, C001-C003,
C005, Risk policy, credentials, activation, or Git history was changed. The
existing dirty worktree was preserved. No OANDA POST/PUT/PATCH/DELETE, cancel,
close, transfer, or Order-submission request was made.

F-07 remains an out-of-scope official session-policy provenance / activation
gate and is not a failure of this approved remediation. The prior F-09
environment-availability blocker is resolved for this validation by the supplied
isolated PostgreSQL run; this result does not claim `READY_TO_ACTIVATE` or permit
PAPER activation.

**Conclusion:** `PASS` for the approved `V-C004-01a` behavior. C004 may proceed
to fresh independent review; no new finding remains in this validation scope.
