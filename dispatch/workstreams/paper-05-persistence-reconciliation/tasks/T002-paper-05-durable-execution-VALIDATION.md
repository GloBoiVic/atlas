# T002 Validation — PAPER 05 Durable Execution Integration

- **Task:** `T002`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `VALIDATE`
- **Status:** `PASS`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`

## Validation mandate

Independently validate T002 against the frozen PLAN, ARCHITECTURE, T002 BUILD
receipt, and actual diff. Verify exact Strategy receipt binding, exactly one
fresh Risk evaluation, attempt/ENTRY commit ordering before entry POST,
normalized observations before outcome projection, Fill retention, actual-fill
target derivation, TAKE_PROFIT commit ordering before dependent PUT, and
restart/duplicate/uncertain no-resubmit behavior. Confirm that existing PAPER 04
semantics and provider boundaries remain unchanged.

Use deterministic fakes or `httpx.MockTransport` only. Run focused tests first,
then the broad safe non-integration/non-external backend suite if focused tests
pass. Use the dedicated PostgreSQL test database/schema for persistence evidence
when available and distinguish environment limitations from product defects.

VALIDATE must write only this artifact and must not modify application, tests,
fixtures, migrations, or BUILD/review artifacts.

## Worker Evidence

Independent validation found no CRITICAL, IMPORTANT PRODUCT, or REGRESSION
finding. The canonical receipt-producing Strategy boundary returns the verified
version/parameter/evaluation bundle, and the durable coordinator structurally
accepts that receipt rather than an independently supplied decision/provenance
pair.

## Acceptance evidence

- `PaperDurableExecutionApplication.execute()` accepts only a
  `PaperStrategyEvaluationReceipt` and executes
  `receipt.evaluation.decision`; it does not accept a separate decision or
  provenance sidecar.
- `PaperExecutionAttempt` checks that its instruction decision equals the
  receipt decision and that Risk facts match the instruction. The repository
  commits the attempt and permanent `ENTRY` claim before calling the injected
  entry mutation, and the permanent `TAKE_PROFIT` claim is committed by the
  `before_take_profit` callback before the dependent PUT.
- `PaperExecutionApplication.prepare()` calls `evaluate_paper_risk(...)` once.
  `PaperRiskAuthoritySnapshot.from_evaluation()` serializes the already-created
  evaluation; it does not evaluate Risk again.
- `_persist_result()` appends the normalized observation before applying the
  result projection. The repository records the complete Fill before its
  filled projection, and R001's identity/protection checks remain in the
  provider-neutral repository boundary.
- `resolve_oanda_practice_actual_target()` uses the actual Fill price and the
  frozen Stop/Strategy target geometry without rounding before the target
  payload is serialized.
- Deterministic source review plus probes verified that restart/duplicate paths
  return durable state without resubmitting, uncertain TAKE_PROFIT does not
  resubmit after restart, and a TAKE_PROFIT pre-mutation commit failure does
  not reach the PUT boundary.
- Existing PAPER 04 composition and OANDA deterministic tests remained green.
  No reconciliation coordinator, transaction-range polling, runtime,
  activation, repair, close/reduce, LIVE, credential use, or real broker call
  was introduced by T002.

## Checks / evidence

- Focused durable/PAPER/OANDA checks:
  `uv run pytest -q backend/tests/paper/test_durable_execution.py
  backend/tests/paper/test_execution_composition.py
  backend/tests/paper/test_execution_contracts.py
  backend/tests/paper/test_persistence_contracts.py
  backend/tests/paper/test_strategy_evaluation.py
  backend/tests/integrations/test_oanda_entry_mutation.py
  backend/tests/integrations/test_oanda_protection_completion.py` — **66
  passed**.
- Broad safe backend suite:
  `uv run pytest -m "not integration and not external" -q` — **931 passed, 4
  skipped, 97 deselected**; four existing warnings.
- Dedicated PostgreSQL repository evidence was initially **9 skipped** because
  the shell did not export `ATLAS_TEST_DATABASE_URL`. The URL in ignored
  `.env` was checked without printing credentials; it names `atlas_test` and
  was run with the owned `paper05_validation` schema:
  `uv run pytest -q backend/tests/integration/test_paper_execution_repository.py`
  — **9 passed**.
- Dedicated schema migration state:
  `alembic current` — `0022_paper_persistence (head)`;
  `alembic check` — **No new upgrade operations detected**.
- The migration integration fixture was attempted with the same dedicated
  `atlas_test` URL and schema. One migration test passed; two failed at the
  fixture's `DROP SCHEMA public CASCADE` because the configured role is not the
  owner of `public` (`must be owner of schema public`). This is the existing
  T001/R001 environment limitation, not a T002 application failure.
- Changed-slice Ruff format — **7 files already formatted**; Ruff check —
  **all checks passed**; changed-slice Pyright — **0 errors**; `git diff
  --check` — **passed**.
- In-process deterministic probes passed for uncertain TAKE_PROFIT restart
  no-resubmit and TAKE_PROFIT commit failure blocking PUT. Source review also
  confirmed the receipt-producing helper, durable receipt decision handoff, and
  repository StrategyVersion/parameter verification path.
- All provider-facing checks used deterministic fakes/MockTransport only. No
  OANDA request, credential, activation, or capital-capable action was used.

## Findings

### MINOR — TOOLING — migration reset cannot own the configured `public` schema

The dedicated repository evidence is available and passed, but the migration
integration fixture hard-codes `DROP SCHEMA public CASCADE`. The configured
`atlas` role does not own that schema, so the dedicated migration test run
reported two setup failures (`must be owner of schema public`). The owned
`paper05_validation` schema still reports migration head/check success. This is
the same environment limitation recorded by T001/R001 and is not a T002
application defect, but it means the migration fixture's full cycle is not
independently executable under the current role.

No CRITICAL, IMPORTANT PRODUCT, IMPORTANT REGRESSION, or MINOR PRODUCT finding
was found. The MINOR TOOLING limitation does not block the durable execution
validation because the dedicated repository checks passed and T001/R001 provide
the dedicated migration-cycle evidence.

## Worker Evidence Receipt

ROLE: VALIDATE
STATUS: PASS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T002-paper-05-durable-execution-VALIDATION.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Focused 66 passed; broad safe backend 931 passed, 4 skipped, 97 deselected; dedicated PostgreSQL repository 9 passed in `atlas_test` / `paper05_validation`; Alembic head/check passed; scoped Ruff/Pyright and `git diff --check` passed; deterministic failure/restart probes passed.
FINDINGS / CONCERNS: PASS with MINOR TOOLING concern: migration reset is blocked by `public` schema ownership; dedicated repository and schema checks passed. No real OANDA call, credential, activation, runtime, or capital-capable action occurred.
