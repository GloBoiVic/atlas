# R001 Validation — PAPER 05 Persistence Attribution

- **Remediation ID:** `R001`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `VALIDATE`
- **Status:** `PASS`
- **Origin:** root `VALIDATION.md`, same-ID result identity and protection attribution findings

## Validation mandate

Independently verified the R001 implementation against the frozen PLAN,
ARCHITECTURE, completed T001 task, root validation, R001 BUILD receipt, and the
working-tree implementation/test diff. Validation used public repository seams
and a dedicated PostgreSQL test schema only; no provider mutation or credential
was used.

## Acceptance evidence

- `apply_result()` with the existing attempt ID and changed immutable quantity
  raised `PaperIdentityConflict`. A subsequent read showed the original
  quantity (`20000`) and no execution outcome; the durable projection was
  unchanged.
- `apply_protection()` with unrelated Stop/Take Profit client IDs, broker IDs,
  and prices raised `PaperIdentityConflict`. The proven Fill, incomplete
  outcome, leg statuses, and absent target remained unchanged.
- Exact attempt-attributed Stop/Take Profit facts derived from the durable Fill
  reached `FILLED_PROTECTED`. A later mismatched broker ID was rejected and the
  original protection IDs, target, outcome, and Fill remained unchanged.
- A later invalid outcome could not erase the durable Fill; the permanent claim
  and Fill non-erasure regression passed.

## Checks / evidence

- `uv run pytest -q backend/tests/paper/test_persistence_contracts.py backend/tests/paper/test_strategy_evaluation.py` — **25 passed**.
- Dedicated PostgreSQL schema `paper05_validation`, with `PGOPTIONS='-c search_path=paper05_validation'`: `uv run pytest -q backend/tests/integration/test_paper_execution_repository.py` — **9 passed**.
- The four direct remediation probes (`same_id_result_conflict`,
  `unattributed_protection`, `exact_protection`, `fill_is_not_erased`) — **4
  passed**.
- Related PAPER/OANDA deterministic regressions — **22 passed**:
  `backend/tests/integrations/test_oanda_protection_completion.py`,
  `backend/tests/paper/test_execution_composition.py`, and
  `backend/tests/paper/test_execution_contracts.py`.
- `uv run ruff format --check` and `uv run ruff check` on the repository and
  integration test — passed; `uv run pyright` on both — **0 errors**.
- Dedicated test schema `alembic current` — `0022_paper_persistence (head)`;
  `uv run alembic check` — **No new upgrade operations detected**.
- Optional broad safe rerun: `uv run pytest -m "not integration and not
  external" -q` — **927 passed, 4 skipped, 97 deselected**, 4 pre-existing
  warnings.
- `git diff --check` — passed. Validation changed only this assigned artifact.

## Findings

No CRITICAL, IMPORTANT, or MINOR PRODUCT/REGRESSION findings remain for R001.

### MINOR — TOOLING / environment limitation

The local `.env` test URL requires the dedicated `paper05_validation` schema to
be selected explicitly. An initial integration invocation without
`PGOPTIONS` failed during Alembic setup with `no schema has been selected`; the
required schema-qualified rerun passed all 9 PostgreSQL tests. This is an
environment invocation issue, not a remediation defect. Unscoped repository
static-gate debt documented by BUILD remains outside this slice.

## Worker Evidence

ROLE: VALIDATE
STATUS: PASS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R001-paper-05-persistence-attribution/VALIDATION.md`
FILES CHANGED: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R001-paper-05-persistence-attribution/VALIDATION.md` only
CHECKS / EVIDENCE: Focused unit 25 passed; dedicated PostgreSQL repository 9 passed; direct R001 probes 4 passed; related PAPER/OANDA regressions 22 passed; broad safe backend 927 passed, 4 skipped, 97 deselected; scoped Ruff/Pyright passed; Alembic head/check passed; `git diff --check` passed.
FINDINGS / CONCERNS: R001 findings are resolved. One schema-selection environment limitation is recorded above; no real OANDA call, credential, activation, runtime, or capital-capable action occurred.
