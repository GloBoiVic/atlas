# T001 - Repository Truth and Engineering Rules

- **Workstream:** `development-baseline-consolidation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `611fe10b9b596f9e48339f305b99023d402c4514`

## Outcome

Make repository guidance accurately describe the current undeployed Atlas baseline and
encode the approved provider-first and complexity-ratchet rules.

## Scope

Primary files:

- `README.md`
- `AGENTS.md`

Required behavior:

- State that current Atlas includes historical Experiment capability and guarded OANDA
  Practice PAPER execution, runtime, activation, and reconciliation capability.
- Do not claim LIVE support.
- Do not imply that starting Atlas, starting the runtime, inspecting broker state, or
  possessing configured credentials authorizes trading.
- State that Atlas is currently undeployed and that prototype compatibility is not
  automatically permanent.
- Add the approved provider-first principle without implementing new OANDA behavior or
  generalized provider infrastructure.
- Add the approved complexity ratchet, including generated-file exemption, approximate
  module thresholds, the existing-large-file growth rule, and the requirement that future
  Feature/Critical plans identify expected files and any growth exception.
- Preserve all existing trading safety, authority, evidence, and capital-boundary guidance.

## Constraints

- Documentation and repository guidance only; no application, schema, migration, or
  persisted-data changes.
- Do not rewrite current domain concepts or introduce development-phase terminology into
  them.
- Keep the wording concise and consistent with the approved PLAN and current code.

## Checks

Inspect the resulting diff for truthful capability claims, explicit non-authorization, and
preservation of the existing capital boundary. Run `git diff --check` for the changed files.
Record exact checks and a completion receipt in this task file. Do not mark this task done
without implementation, checks, and evidence.

## Worker Evidence

- BUILD execution completed.

## Immutable BUILD Receipt

- **Status:** `DONE`
- **Files changed:**
  - `README.md`
  - `AGENTS.md`
  - `dispatch/workstreams/development-baseline-consolidation/tasks/T001-repository-truth-and-engineering-rules.md`
- **Checks/evidence:**
  - `git diff --check` - passed with no whitespace errors.
  - `git diff -- README.md AGENTS.md` - inspected; both documents state historical EUR/USD Experiment capability and guarded OANDA Practice PAPER execution/runtime/activation/reconciliation capability, deny LIVE capability, and explicitly deny authorization from starting Atlas/runtime, inspecting broker state, or possessing configured credentials.
  - `backend/api/app.py`, `backend/runtime/main.py`, `backend/api/paper.py`, and `backend/runtime/activation.py` plus related tests were inspected to verify the documented PAPER capability and its explicit activation/reconciliation safeguards; no application files were changed.
  - `AGENTS.md` now contains the approved provider-first principle and complete complexity ratchet, including the generated-file exemption, approximately 400/600-line module thresholds, 800-line existing-file rules, 1,200-line extraction guidance, and future Feature/Critical PLAN file/growth-exception requirement.
  - Existing safety, authority, evidence, and capital-boundary guidance was preserved.
- **Findings/concerns:**
  - None for T001. The pre-existing unowned `dispatch/ACTIVE.md` worktree modification was left untouched.
  - No application, schema, migration, persisted-data, trading-semantic, or Git-history changes were made.
