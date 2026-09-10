# T003 - Compatibility and Phase Inventory

- **Workstream:** `development-baseline-consolidation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `611fe10b9b596f9e48339f305b99023d402c4514`
- **Dependency:** T002

## Outcome

Classify known development compatibility seams and distinguish historical identifiers from
current domain semantics before any cleanup is attempted.

## Scope

Primary artifact:

- `dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md`

Inventory at least:

- StrategyState schema 1;
- `window_bars` and `AWAITING_CONFIRMATION` compatibility;
- `warm_up_bars`;
- snapshot V1;
- legacy result metric states and old result schema identifiers;
- `indicators.py` versus `indicators_v2.py`;
- `EmaSweepConfirmationBreakCompatibilityAdaptor`;
- historical-load compatibility fields;
- runtime service aliases.

For every seam record:

- CURRENT, EVIDENCE, PROTOTYPE, or DEFERRED classification;
- current caller;
- persisted dependency;
- evidence dependency;
- API/test/generated-surface responsibility where applicable;
- natural retirement point.

Apply only mechanical phase-terminology cleanup that does not rename historical migration
revision IDs, closed workstreams, persisted schema/version identifiers, old benchmark names,
or existing database constraint names. Current application concepts, new contracts, comments
describing current behavior, and future code must use domain/capability terminology.

## Constraints

- Do not remove a seam because Atlas is undeployed, and do not preserve one only because old
  tests exist.
- Do not reinterpret methodology, rewrite evidence, migrate or reset data, or change schema.
- If classification or retirement requires a semantic, persistence, methodology, authority,
  or trading decision, retain it, mark the decision DEFERRED, and report the blocker.

## Checks

Verify repository imports, callers, tests, API exposure, generated surfaces, and persistence
or evidence responsibilities for each candidate. Run relevant focused checks and
`git diff --check`. Record the evidence and completion receipt in this task file.

## Worker Evidence

BUILD execution completed. The primary compatibility inventory is
`dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md`.

## Immutable BUILD Receipt

- **Status:** `DONE`
- **Files changed:**
  - `dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md`
  - `backend/domain/market_data.py`
  - `backend/domain/trading.py`
  - `backend/execution/contract.py`
  - `backend/execution/fill_application.py`
  - `backend/persistence/database.py`
  - `backend/risk/service.py`
  - `backend/tests/e2e_seed.py`
  - `backend/tests/experiments/test_configuration.py`
  - `dispatch/workstreams/development-baseline-consolidation/tasks/T003-compatibility-and-phase-inventory.md`
- **Inventory/evidence:**
  - `COMPATIBILITY.md` inventories StrategyState schema 1, `window_bars`/
    `AWAITING_CONFIRMATION`, `warm_up_bars`, DatasetSnapshot V1, legacy result metric
    states, historical/current result identifiers, both indicator modules, the EMA
    compatibility adaptor, historical-load fields, and runtime aliases.
  - Each seam has a `CURRENT`, `EVIDENCE`, `PROTOTYPE`, or `DEFERRED` classification,
    current caller, persistence dependency, evidence dependency, API/test/generated
    responsibility where applicable, and natural retirement point.
  - `PROTOTYPE` and `DEFERRED` seams were retained where retirement requires a later
    Strategy SDK, state-codec, persistence, evidence, or import-surface decision.
  - Historical migration revisions, persisted schema/version strings, benchmark names,
    database constraint/function/trigger names, compatibility enum values, and retained
    evidence identifiers were not renamed or rewritten.
- **Mechanical cleanup:**
  - Reworded only current comments/docstrings and one test identifier away from milestone
    terminology; renamed the local `phase4` boolean to
    `uses_historical_end_close_reason` without changing its persisted model-version values.
  - Observable validation/error text containing historical Phase labels was left unchanged
    because it is an API/test-facing contract with no functional cleanup benefit.
  - No Strategy methodology, Risk decision, execution accounting, reconciliation,
    protection, activation, broker-authority, API shape, schema, migration, generated file,
    persisted data, or evidence changed.
- **Checks/evidence:**
  - `uv run --frozen ruff check backend/risk/service.py backend/domain/market_data.py backend/domain/strategy.py backend/domain/trading.py backend/strategies/contract.py backend/persistence/database.py backend/execution/contract.py backend/execution/fill_application.py backend/tests/e2e_seed.py backend/tests/experiments/test_configuration.py` - passed.
  - Focused pytest command covering domain primitives, legacy Strategy isolation, EMA
    confirmation-break behavior, historical loading, Experiment configuration/results,
    Freeze03 regressions, and simulated execution - `143 passed, 1 skipped` in `19.43s`.
  - Focused structured Pyright over the eight reviewed production files and two touched test
    files - before and after both reported `37 errors, 0 warnings, 0 informations` across
    `backend/execution/fill_application.py` (13),
    `backend/tests/e2e_seed.py` (1), and
    `backend/tests/experiments/test_configuration.py` (23); normalized file/rule/message
    diagnostics were identical, with only line shifts from comment edits.
  - `git diff --check` - passed with no whitespace errors. The untracked inventory also
    produced no whitespace diagnostics under `git diff --no-index --check`.
  - `uv run --frozen ruff format --check backend` remains non-clean baseline debt: `68`
    files would be reformatted and `147` are already formatted. No broad formatter rewrite
    was applied in this narrow task.
- **Findings/concerns:**
  - The repository-wide Pyright baseline remains `3,011` errors as recorded by T002; T003
    introduced no changed-surface diagnostics.
  - No migration, database reset, data rewrite, evidence rewrite, credential change, broker
    request, or capital-capable operation was performed.
