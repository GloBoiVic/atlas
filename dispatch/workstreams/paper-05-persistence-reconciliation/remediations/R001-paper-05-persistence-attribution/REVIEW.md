# R001 Review — PAPER 05 Persistence Attribution

- **Remediation ID:** `R001`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `REVIEW`
- **Status:** `PASS`
- **Origin:** root `VALIDATION.md`, same-ID result identity and protection attribution findings

## Review mandate

Independently review the R001 finding, remediation packet, implementation diff,
BUILD receipt, and remediation VALIDATION artifact against the frozen PLAN and
ARCHITECTURE. Confirm that the remediation is narrowly scoped, resolves both
approved defects, preserves Fill/non-resubmit/outcome semantics, and has no
unresolved CRITICAL or IMPORTANT findings. No implementation edits are allowed
from the REVIEW role.

## Worker Evidence

Populate this artifact once with the independent review receipt, judgment,
findings, and evidence. Do not modify application, test, fixture, migration, or
other evidence artifacts from the REVIEW role.

## Independent judgment

R001 passes. `apply_result()` locks the existing attempt and calls
`_assert_result_identity()` before delegating to any outcome projection. The
comparison covers the durable instruction's Strategy decision, account and
instrument, direction, quantity, prices, timing, provenance frontiers,
precision, Risk decisions, and all deterministic client correlations. A changed
same-ID result therefore raises `PaperIdentityConflict` without changing the
attempt row.

Protection validation is also before projection writes. It requires a durable
Fill for confirmed protection, derives the expected target from the immutable
Fill, Stop, direction, and durable Risk target geometry, and checks each leg's
client ID, expected price, provider state, and any already durable broker ID.
This preserves exact valid Stop/Take Profit facts while rejecting unrelated
protection and preventing `FILLED_PROTECTED` without exact attribution.

The remediation is within scope: only the PAPER repository seam and focused
repository regressions were added/changed for R001; no schema, migration,
adapter, runtime, broker, historical Experiment, or capital-capable behavior
was changed. Existing permanent claim, Fill write-once/non-erasure, guarded
outcome, and read-only/restart boundaries remain intact.

## Findings

No unresolved CRITICAL or IMPORTANT PRODUCT/REGRESSION findings remain.

### MINOR — TOOLING

The dedicated PostgreSQL evidence requires the configured `paper05_validation`
schema via `PGOPTIONS`; the unscoped repository has pre-existing formatting,
lint, and type-check debt documented by BUILD. These are environment/repository
baseline limitations, not R001 defects.

## Review Evidence

- `uv run pytest -q backend/tests/paper/test_persistence_contracts.py backend/tests/paper/test_strategy_evaluation.py backend/tests/paper/test_execution_contracts.py backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_protection_completion.py` — **47 passed**.
- `ATLAS_TEST_DATABASE_URL` loaded from the ignored local environment with `PGOPTIONS='-c search_path=paper05_validation'`; `uv run pytest -q backend/tests/integration/test_paper_execution_repository.py` — **9 passed**.
- `uv run pytest -m "not integration and not external" -q` — **927 passed, 4 skipped, 97 deselected**; only four pre-existing warnings.
- Scoped Ruff check/format and Pyright for the repository plus integration test — passed; Pyright **0 errors**.
- Dedicated schema `alembic current` — `0022_paper_persistence (head)`; `alembic check` — no new upgrade operations.
- `git diff --check` and `python -m compileall -q backend/paper backend/persistence` — passed.
- R001 PostgreSQL regressions prove same-ID conflict leaves quantity/outcome unchanged, unrelated protection leaves Fill/projection unchanged, exact Fill-derived protection reaches `FILLED_PROTECTED`, later broker-ID mismatch is rejected, and Fill/claim non-erasure remains enforced.
- No provider calls, credentials, activation, runtime, or capital-capable action was used. REVIEW changed only this artifact.

## Worker Evidence Receipt

ROLE: REVIEW
STATUS: PASS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R001-paper-05-persistence-attribution/REVIEW.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Independent source/diff review plus focused unit, dedicated PostgreSQL, broad safe regression, scoped static, migration, diff, and compile checks listed above.
FINDINGS / CONCERNS: No unresolved CRITICAL or IMPORTANT findings. One MINOR TOOLING/environment limitation is recorded; no real OANDA mutation or credential use occurred.
