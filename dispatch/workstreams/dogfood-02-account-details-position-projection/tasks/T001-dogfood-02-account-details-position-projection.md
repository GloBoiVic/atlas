# T001 — Dogfood 02 Account Details Position Projection

- **Workstream:** `dogfood-02-account-details-position-projection`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/dogfood-02-account-details-position-projection`
- **Base:** `main` at `b75930f2276f93938e250ea8498ad8affb4f97c5`

## Assignment

Implement only the frozen `PLAN.md` and `ARCHITECTURE.md` contract for repairing the
interpretation of OANDA full Account Details `account.positions`.

Add a separate pure Account Details Position projection/helper. Keep
`normalize_oanda_practice_open_position_inventory()` strict and unchanged in meaning for
the separate `/openPositions` contract. The new helper must parse and validate every raw
Position's instrument, long/short side objects, and both finite provider Decimal units;
enforce nonnegative long and nonpositive short signs; exclude exactly zero/zero historical
records; retain every nonzero Position and both nonzero sides; and apply the existing
open-position invariants to retained records. Duplicate instruments fail closed across the
raw collection, including excluded records. Do not net, discard, or select sides, and do not
add a new `hedgingEnabled`-dependent classification rule.

Update full Account Details normalization to use only the derived open inventory and compare
`openPositionCount` with its exact length, while preserving the one Account Details GET,
validated common `lastTransactionID`, existing Trade/Order semantics, exposure projection,
runtime/P05/reconciliation safety, and all out-of-scope boundaries in the frozen artifacts.
Do not change schema or migrations.

Add sanitized deterministic tests covering the complete A–O matrix and required boundary
cases in the directly affected normalization, exposure, runtime/P05, and reconciliation
seams. Prove no extra Position endpoint read, no provider mutation, no input payload
mutation, and no raw-provider leakage. Do not use credentials, start atlas-runtime, create
or reuse an activation, or manually repair an account.

## Required checks

Run focused provider-normalization tests first, then affected exposure/runtime/P05/
reconciliation regressions, then changed-slice Ruff, Pyright, `git diff --check`, and the
appropriate Critical safe backend suite. Record exact commands and results in this task
receipt. Stop and report if satisfying the frozen contract would require provider-read
topology, exposure, Risk/runtime/execution, persistence/schema, or new `hedgingEnabled`
authority changes.

## Worker Evidence

- **Status:** COMPLETE
- **Implementation:** Added the pure
  `normalize_oanda_practice_account_position_inventory` seam in
  `backend/integrations/oanda/positions.py`, preserving strict `/openPositions`
  normalization; full Account Details normalization now uses the derived open
  inventory and existing exact count/frontier checks.
- **Tests:** Added sanitized coverage for the A–O matrix and boundary cases across
  `backend/tests/integrations/test_oanda_positions.py`,
  `test_oanda_execution_capability.py`, `test_oanda_exposure_projection.py`,
  `test_oanda_reconciliation.py`, `backend/tests/runtime/test_runtime_orchestration.py`,
  and `backend/tests/paper/test_execution_composition.py`.
- **Checks:**
  - `uv run pytest backend/tests/integrations/test_oanda_positions.py -q` — 75 passed.
  - `uv run pytest backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_exposure_projection.py -q` — 51 passed.
  - `uv run pytest backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/runtime/test_runtime_cycles.py backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_reconciliation.py -q` — 138 passed.
  - `uv run pytest -m "not integration and not external"` — 1221 passed, 4 skipped,
    115 deselected.
  - `uv run ruff format --check backend/integrations/oanda/positions.py backend/integrations/oanda/execution_account.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_reconciliation.py && uv run ruff check backend/integrations/oanda/positions.py backend/integrations/oanda/execution_account.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_reconciliation.py` — passed.
  - `uv run pyright backend/integrations/oanda/positions.py backend/integrations/oanda/execution_account.py backend/integrations/oanda/__init__.py backend/tests/integrations/test_oanda_positions.py backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_reconciliation.py` — 0 errors, 0 warnings, 0 informations.
  - `git diff --check` — passed.
- **Safety:** No credentials, runtime, activation, provider call, or provider mutation
  was used; tests use sanitized local fixtures and MockTransport only.
- **Concerns:** No task-specific concerns. Repository-wide Pyright still reports
  unrelated existing errors outside the changed slice; changed-slice Pyright passes.
