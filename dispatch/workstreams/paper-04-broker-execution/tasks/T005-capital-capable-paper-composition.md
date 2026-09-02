# T005 — Capital-capable PAPER execution composition

- **Status:** DONE
- **Role:** BUILD
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Depends on:** T004

## Assignment

Implement one public PAPER execution operation that owns the complete frozen
sequence from StrategyDecision through read-only eligibility, coherent account
state, GSLO/instrument/pricing observations, exactly-once fresh PAPER 03 Risk,
entry mutation/readback, and actual-Fill protection completion. Make stale
PAPER 03 approvals unable to mutate and avoid runtime activation. Add end-to-end
deterministic composition tests covering all final outcomes and isolation
regressions requested by the canonical artifacts.

## Acceptance

- Callers cannot bypass fresh observations and fresh Risk with a stale approval.
- All pre-entry gates fail before POST and exactly one Risk evaluation occurs for a permitted invocation.
- The complete entry/protection state machine returns only the five frozen outcomes with bounded diagnostics/evidence.
- No real OANDA mutation, credentials, persistence, runtime, API/UI, migrations, or LIVE behavior is introduced.

## Worker evidence

Implemented the single public capital-capable PAPER composition seam without
changing historical execution, Risk/PAPER 03 semantics, persistence, runtime,
API/UI, migrations, or LIVE behavior:

- Added `PaperExecutionApplication` / `execute_paper_execution`, accepting only
  the immutable `StrategyDecision` and `RiskConfig`; stale `PaperRiskEvaluation`
  values are rejected before any read or mutation.
- Owned the serial fresh-read sequence for AccountProperties, the coherent full
  Account Details snapshot, EUR/USD execution capability, current pricing, and
  exactly one `evaluate_paper_risk(...)` call before exact entry serialization.
- Composed the existing non-retrying entry mutation and actual-Fill protection
  completion seams, preserving all five frozen outcomes and bounded evidence.
- Added deterministic public-seam composition tests for
  `FILLED_PROTECTED`, `FILLED_PROTECTION_INCOMPLETE`, `REJECTED`, `CANCELLED`,
  and `UNKNOWN`, including fresh-read ordering, exactly-once Risk, stale
  approval rejection, and historical/Risk isolation regressions.

## Checks

- `uv run pytest backend/tests/paper/test_execution_composition.py backend/tests/paper/test_execution_contracts.py backend/tests/paper/test_risk_evaluation.py backend/tests/integrations/test_oanda_entry_mutation.py backend/tests/integrations/test_oanda_protection_completion.py backend/tests/integrations/test_oanda_execution_capability.py -q` — **69 passed**.
- `uv run pytest -m "not integration and not external" -q` — **919 passed, 4 skipped, 88 deselected**; existing warnings only.
- Focused `ruff check`, `ruff format --check`, `pyright`, and `git diff --check` — **passed** for T005 application/export/test files.
- No real OANDA requests, credentials, broker mutation, persistence, runtime
  activation, API/UI, migration, or Git history operation performed.

## Concerns

- The frozen snapshot-to-mutation race, durable attempt ownership, and unknown
  outcome/protection reconciliation remain explicit PAPER 05 boundaries.
- Existing T001–T004 working-tree changes and SoloFlow operational changes were
  preserved and not edited by T005.
