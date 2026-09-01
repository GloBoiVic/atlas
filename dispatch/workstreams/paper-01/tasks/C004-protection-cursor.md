# C004 — Protection truth and OANDA transaction-cursor authority

**State:** `DONE`
**Dependency:** C003 `DONE`
**Owner:** BUILD
**Authority:** `IMPLEMENTATION-CLOSURE.md` C004; preserve PLAN, ARCHITECTURE, and
the frozen T004 reconciliation without reinterpretation.

## Objective

Implement exactly the frozen C004 capital boundary: strict Trade-scoped
protection identity and exposure proof, preservation of authoritative immediate
Fills when later protection confirmation fails, and Account Changes as the sole
durable OANDA cursor-advancement authority with minimal durable transaction
receipts.

## Required behavior

- Enforce every frozen protection identity, distinct provider ID, exact Trade
  linkage, stop/actual-Fill-derived target price, OPEN/direction/full-unit,
  Position-side, and freshness rule without inventing protection quantities.
- On immediate authoritative Fill, persist/deduplicate Fill and canonical
  exposure before confirming protection. Protection failure preserves financial
  truth, blocks all new exposure, and persists FAILED or
  RECONCILIATION_REQUIRED; missed-Fill repair retains the stricter T004 proof.
- Never advance the durable cursor from submission responses. Use GET Account
  Changes from the durable cursor, validate explicit account binding, normalize
  and classify every unfiltered transaction, durably receipt each one, apply/
  deduplicate canonical facts, and advance only to the response fence after the
  complete response succeeds.
- Add the minimal account-scoped OandaTransactionReceipt and exact uniqueness,
  digest, disposition, replay/conflict, sanitization, and transactionality
  semantics frozen in C004. Unknown or exposure-relevant ambiguous facts block.
- Keep receipt insert/deduplication, projections, reconciliation evidence, and
  final cursor update in one transaction; rollback all on failure and persist the
  safety failure separately. Cursor update is the final successful write.
- Implement only the frozen flat initial baseline and startup/resume/reconnect/
  ownership/UNKNOWN cursor gate; do not import full account history or broaden
  recovery.

## Required tests

Implement and run every protection and cursor test listed under frozen C004,
including distinct IDs/linkage/prices/current units/freshness, Fill preservation
on protection failure, no submission cursor movement, complete Account Changes
receipts/classification, idempotent/conflicting replay, atomic rollback,
cursor-last ordering, restart replay, flat baseline, and exposed baseline block.
All provider calls must be mocked/recorded GET shapes. PostgreSQL persistence and
ordering checks must use only the configured `_test` database.

## Hard boundaries

Do not touch C005, F-07/F-09, PAPER 02, credentials, Risk policy, activation, or
any mutating/capital-capable OANDA request. Stop and report any contradiction with
PLAN, ARCHITECTURE, or T004 rather than redesigning.

## Completion receipt

BUILD must record changed files, focused checks, PostgreSQL evidence or explicit
environment blocker, no-mutation/no-activation evidence, and concerns here before
marking the task `DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`.

## Approved remediation packet — V-C004-01

- **Classification:** `PRODUCT` (production safety/readiness gate and regression).
- **Issue:** A cursorless Deployment can return `MATCHED` on START, RESUME,
  reconnect, or ownership reacquisition without a current Account Changes fence,
  allowing `_ensure_running` to reach actual `RUNNING`.
- **Owning task:** this existing C004 task; do not reopen T004 or touch C001-C003.
- **Affected seams:** `OandaReadOnlyBrokerReader`, `ReadOnlyReconciler`, the
  `RuntimeStore` reconciliation persistence seam, and the coordinator's shared
  readiness result; preserve the frozen C004/H baseline and Account Changes
  transaction rules.
- **Required fix:** every lifecycle reconciliation must prove either a durable
  cursorless flat baseline (selected Practice account, current clean EUR/USD
  account facts, no unresolved local broker-linked execution fact, valid current
  provider `lastTransactionID`) or complete Account Changes catch-up from the
  exact durable cursor. Unknown/stale/contradictory/non-flat baseline facts and
  failed Account Changes application return `RECONCILIATION_REQUIRED`, retain
  the old cursor, and block exposure. No synthetic Account Changes request may
  be made without a cursor. `_ensure_running` must accept only a reconciliation
  result carrying the proven durable gate.
- **Required regressions:** cursorless START, RESUME, reconnect, ownership
  reacquisition, non-flat/unknown baseline, durable baseline before MATCHED,
  stale cursor catch-up, failed application with old cursor retained, successful
  catch-up with new cursor durable before MATCHED, and restart reusing the
  persisted cursor.
- **Invalidated evidence:** prior C004 cursorless lifecycle/readiness evidence
  and the closure validation/review conclusions for this gate only. F-07/F-09
  remain independent gates; no activation or mutating provider request is allowed.

## Approved remediation packet — V-C004-01a

- **Classification:** `PRODUCT` (critical cursor-baseline safety invariant).
- **Issue:** The cursorless baseline rejects local Order/Fill/Trade rows but can
  ignore a non-flat or contradictory local `PositionModel`, allowing a broker-
  flat Deployment to persist an initial cursor and become ready.
- **Owning task:** this existing C004 task; do not reopen T004 or touch C001-C003.
- **Affected seams:** the cursorless branch of
  `SqlAlchemyRuntimeStore.repair_reconciliation`, its local canonical-state
  query/validation, and the PostgreSQL baseline regression. The check must live
  in the authoritative baseline operation, not only in the coordinator.
- **Required fix:** inside the baseline transaction, prove local EUR/USD state
  is flat and clean: reject any non-flat/open/contradictory `PositionModel`, open
  `TradeModel`, unresolved broker-relevant ENTRY Order (including
  `PENDING_SUBMISSION`, `UNKNOWN`, or equivalent unresolved state), unresolved
  broker-linked Fill/Order/Trade fact, or unresolved pending opening
  handoff/TradeIntent. Preserve the null cursor and durable safety block on
  rejection. Keep broker flat/clean proof, current selected-account Details
  fence, and no-synthetic-Account-Changes behavior unchanged.
- **Required regressions:** flat broker plus open local PositionModel; open local
  Trade; unresolved PENDING_SUBMISSION Order; UNKNOWN Order; unresolved
  broker-linked execution fact; both broker/local flat baseline succeeds once;
  repeated startup reuses the persisted cursor.
- **Invalidated evidence:** the prior remediation's cursorless baseline success
  and validation claims for local canonical state; existing-cursor catch-up and
  clean flat lifecycle evidence remain separately valid unless the fix changes
  those seams.
- **Smallest revalidation:** rerun the affected cursorless baseline/lifecycle
  matrix, targeted C004 runtime/OANDA checks, and PostgreSQL baseline/cursor
  cases when an isolated `_test` database is available; then obtain fresh
  independent C004 rereview.

## BUILD receipt

**Final state:** `DONE_WITH_CONCERNS`

### Changed files — V-C004-01 remediation

- `backend/runtime/reconciliation.py` — exposes the current Account Details
  `lastTransactionID` as the cursorless baseline fence while never issuing an
  Account Changes request without a durable cursor.
- `backend/runtime/coordinator.py` — requires local reconciliation facts and a
  successful durable baseline/catch-up result for every reconciliation before
  runtime readiness or actual `RUNNING`; reconnect and reacquisition cannot keep
  an unproven runtime active.
- `backend/runtime/store.py` — persists account evidence and the cursorless flat
  baseline atomically before the cursor, validates the current fence, rejects
  local execution facts during baselining, and marks successful Account Changes
  application as a durable readiness proof.
- `backend/tests/runtime/test_coordinator.py` and
  `backend/tests/runtime/test_production_runtime.py` — regressions for
  cursorless START/RESUME/reconnect/ownership reacquisition, flat-baseline
  ordering, non-flat/unknown facts, stale and failed catch-up, durable cursor
  advancement, restart cursor reuse, and the no-synthetic-Account-Changes
  provider shape.
- `backend/tests/integration/test_runtime_store_reconciliation.py` — verifies
  durable baseline evidence and rejection of non-flat Position, open Trade,
  unresolved Order/Fill, and pending opening handoff/TradeIntent facts when
  PostgreSQL integration is available.

### Checks and evidence

- Fresh narrow runtime/OANDA/C004 plus direct migration/lock checks: **67 passed,
  19 skipped**. The 16 C004 persistence cases and 3 migration cases are skipped
  because `ATLAS_TEST_DATABASE_URL` is unset.
- Ruff on the changed implementation and regression-test modules: **passed**.
- Pyright on `backend/runtime/{coordinator,reconciliation,store}.py`:
  **0 errors, 0 warnings, 0 informations**.
- Targeted `compileall` and `git diff --check`: **passed** (the latter covers
  tracked content; the remediation source is untracked on this branch).

### Safety receipt and concerns

- Provider-facing validation used recorded/mock transports and GET-only read
  shapes. The cursorless regression asserts no Account Changes request is made;
  no credentials were read or changed, no PAPER activation or Risk-policy
  change occurred, and no Order submission or mutating/capital-capable OANDA
  request was invoked.
- PostgreSQL-backed proof of baseline evidence, receipt/projection rollback,
  cursor-last ordering, migration state, and advisory-lock behavior remains
  environment-unverified because `ATLAS_TEST_DATABASE_URL` is not configured.
- C005, F-07/F-09, PAPER 02, credentials, activation, and Risk policy remain
  untouched. No `READY_TO_ACTIVATE` claim is made.

## V-C004-01a BUILD receipt

**Final state:** `DONE_WITH_CONCERNS`

### Scope and implementation

The authoritative cursorless baseline transaction now calls
`_local_state_is_safe_for_initial_cursor` while holding the baseline transaction.
It locks and validates local Deployment Position projections, rejects any
non-flat or contradictory Position, rejects non-terminal broker-relevant local
Orders, rejects local Fills and Trades, and rejects pending opening handoffs or
pending opening TradeIntents. Rejections raise the existing
`INITIAL_CURSOR_BASELINE_UNSAFE` path, roll back the baseline transaction, retain
the null cursor, persist the existing safety block, and return no durable gate.
The selected Practice-account Details fence and no-synthetic-Account-Changes
path are unchanged.

### V-C004-01a changed files

- `backend/runtime/store.py` — added the transaction-local canonical EUR/USD
  flat/clean proof before cursorless baseline persistence.
- `backend/tests/integration/test_runtime_store_reconciliation.py` — added
  PostgreSQL regressions for open Position, open Trade, PENDING_SUBMISSION and
  UNKNOWN Orders, unresolved broker-linked Fill, and pending opening
  handoff/TradeIntent. Existing flat-baseline and repeated-startup cursor tests
  remain in the focused suite.

No model, migration, provider, credential, Risk, C001-C003, C005, F-07, F-09,
activation, or mutating OANDA path was changed.

### V-C004-01a checks

```text
pytest -q -rs -p no:cacheprovider \
  backend/tests/runtime/test_coordinator.py \
  backend/tests/runtime/test_production_runtime.py \
  backend/tests/integrations/test_oanda_execution.py \
  backend/tests/integrations/test_oanda_paper_contracts.py \
  backend/tests/integration/test_runtime_store_reconciliation.py \
  backend/tests/integration/test_migrations.py \
  backend/tests/test_migration_revision.py \
  backend/tests/persistence/test_paper_persistence.py
```

Result: **67 passed, 19 skipped**. `ATLAS_TEST_DATABASE_URL` was not configured;
therefore all 16 cases in `test_runtime_store_reconciliation.py` and all 3
cases in `test_migrations.py` skipped with their module guard message
`ATLAS_TEST_DATABASE_URL is not configured`. No prior BUILD result substitutes
for those cases. No PostgreSQL-backed baseline, rollback, receipt, migration,
or advisory-lock evidence is claimed. The deterministic advisory-lock-key unit
case passed; live PostgreSQL advisory-lock behavior remains unverified.

Additional fresh checks: Ruff passed; Pyright on the affected runtime modules
reported **0 errors, 0 warnings, 0 informations**; targeted compileall passed;
tracked `git diff --check` passed.

### Safety receipt

All provider-facing checks used recorded/mock GET-only transports. No
credentials were read or changed, no Order submission or other mutating or
capital-capable OANDA request was invoked, and PAPER was not activated. The
worktree was already dirty; this BUILD change is limited to the two files above
and this owned task receipt. C005, F-07/F-09, PAPER 02, credentials, activation,
and Risk policy remain untouched.
