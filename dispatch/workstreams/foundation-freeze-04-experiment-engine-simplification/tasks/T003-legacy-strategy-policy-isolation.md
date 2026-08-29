# T003 — Legacy Strategy and Policy Isolation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE`

## Goal

Remove unregistered legacy EMA Sweep Engulfing execution modules and tests, while
isolating shared compatibility fields that still lack a complete persisted-state
inventory.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 2.4 and Strategy ownership/invariants
- `backend/domain/strategy.py`
- `backend/strategies/production.py`, current reference Strategy, registry, and
  strategy requirements
- strategy, domain, persistence, and API contract tests

## Implement

- Remove only the unregistered `ema_sweep_engulfing.py` and
  `ema_sweep_engulfing_v2.py` execution modules and tests whose sole purpose is
  those modules.
- Mark/prove retained schema-1/old-phase fields as non-authoritative compatibility
  surfaces; do not guess away persisted immutable fields or migrations.
- Preserve the existing V2 `EntryPolicy.IMMEDIATE` path and tests; do not narrow
  the existing Strategy/runner contract. Prove production registration contains
  only `ema_sweep_confirmation_break.v2`, and new V2 execution cannot use old
  schema-1/phase state. Any future IMMEDIATE removal requires a separate explicit
  contract decision.

## Do not implement

- Do not redesign or edit current EMA Sweep Confirmation Break v2 methodology,
  indicators, state transitions, rationale, source fingerprint, or parameters.
- Do not remove persisted columns, migrate rows, change API result shapes, or move
  Strategy/Risk ownership.

## Acceptance/checks

- Current reference Strategy tests and golden behavior pass unchanged in meaning.
- Legacy modules are not importable through production registration; retained
  schema-1/phase compatibility is read-only/non-authoritative and tested, while
  existing IMMEDIATE behavior remains supported and covered.
- Receipt lists every removed symbol and confirms no persisted compatibility data was
  changed.

## Completion receipt

### Implementation

- Removed the unregistered legacy modules:
  - `backend.strategies.ema_sweep_engulfing` — `DEFINITION`,
    `EmaSweepEngulfingStrategy`, and `EMASweepEngulfingStrategy`.
  - `backend.strategies.ema_sweep_engulfing_v2` — `DEFINITION` and
    `EmaSweepEngulfingV2Strategy`.
- Removed their sole-purpose test modules:
  - `backend.tests.strategies.test_ema_sweep_engulfing`.
  - `backend.tests.strategies.test_ema_sweep_engulfing_v2`.
- Marked retained schema-1/old-phase state, warm-up fallback, proposal expiry
  fields, and compatibility reads as read-only/non-authoritative in source. No
  state fields, API fields, persistence columns, or migrations were removed or
  changed.
- Added focused isolation coverage proving the production catalog contains only
  `ema_sweep_confirmation_break.v2`, schema-1 `AWAITING_CONFIRMATION` state is
  rejected before registered V2 evaluation, and the V2 runner initializes state
  from the persisted StrategyVersion schema. Added a contract guard proving
  `EntryPolicy.IMMEDIATE` remains valid.
- `backend/strategies/ema_sweep_confirmation_break.py` was not changed.

### Files changed

- `backend/domain/strategy.py`
- `backend/domain/strategy_requirements.py`
- `backend/persistence/models.py`
- `backend/strategies/contract.py`
- `backend/tests/strategies/test_legacy_strategy_isolation.py`
- Deleted `backend/strategies/ema_sweep_engulfing.py`
- Deleted `backend/strategies/ema_sweep_engulfing_v2.py`
- Deleted `backend/tests/strategies/test_ema_sweep_engulfing.py`
- Deleted `backend/tests/strategies/test_ema_sweep_engulfing_v2.py`

### Checks / evidence

- `pytest -q backend/tests/strategies backend/tests/domain` — **77 passed**.
- Focused regression set including the new isolation test and current V2 tests —
  **53 passed**.
- `ruff check` on all T003-modified Python files — **passed**.
- `pyright backend/tests/strategies/test_legacy_strategy_isolation.py` — **0
  errors, 0 warnings**.
- `python -m compileall -q` on all T003-modified Python files — **passed**.
- `git diff --check` — **passed**.
- Python import probe confirmed both removed legacy module names resolve to no
  importable module.
- `pytest -q backend/tests --ignore=backend/tests/integration` — **310 passed,
  6 skipped** (one existing dependency deprecation warning).
- No diff in the current V2 implementation or `backend/persistence/migrations`.

### Concerns

- Existing non-strategy fixtures still contain historical
  `ema_sweep_engulfing` identifiers; they are persisted compatibility fixtures,
  not imports or production registrations, and were intentionally preserved.
- No persisted compatibility rows were changed, migrated, deleted, or rewritten.
- Integration tests were not run because they require the dedicated PostgreSQL
  test database; the broad non-integration suite passed completely.
