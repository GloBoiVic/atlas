# R001 — PAPER 05 Persistence Attribution Remediation

- **Remediation ID:** `R001`
- **Status:** `DONE_WITH_CONCERNS`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Origin finding:** `dispatch/workstreams/paper-05-persistence-reconciliation/VALIDATION.md`, findings 1 and 2
- **Finding severity:** two `IMPORTANT` / `PRODUCT` defects
- **Related original task:** `T001-paper-05-persistence-foundation`
- **Approved requirement/invariant violated:** same-ID immutable result identity; strict protection attribution; `FILLED_PROTECTED` requires exact protections for the durable attempt

## Exact remediation outcome

Harden the provider-neutral persistence repository so that:

1. Applying a result for an existing attempt verifies the result's immutable
   instruction identity against the durable attempt before any projection
   change. Same `attempt_id` with changed quantity, prices, direction,
   account/instrument, correlation, Strategy/Risk/provenance, or other frozen
   instruction facts must raise `PaperIdentityConflict` and leave the row
   unchanged.
2. Applying protection verifies every Stop Loss and Take Profit fact against the
   durable attempt and, where applicable, the immutable actual Fill and derived
   target geometry. Unrelated client IDs, broker IDs, prices, Trade identity,
   account/instrument, units, or provider states must not be accepted. Invalid
   protection must remain incomplete/blocked and must never produce
   `FILLED_PROTECTED`.
3. Add public-seam regression tests reproducing both validation probes and prove
   valid protection still reaches `FILLED_PROTECTED`, while invalid same-ID
   results/protection cannot alter durable facts or falsely advance the outcome.

## Affected implementation seams

- `backend/persistence/paper_execution_repository.py`
- `backend/paper/persistence_contracts.py` only if a narrow contract helper is
  required
- `backend/persistence/models.py` only if required to preserve the existing
  durable guards
- focused repository tests under `backend/tests/integration/` and/or
  `backend/tests/paper/`

## Explicit out-of-scope items

- No schema redesign or unrelated migration changes.
- No OANDA adapter changes, broker calls, mutation retries, reconciliation
  coordinator, repair, close/reduce, activation, runtime, scheduling, LIVE,
  or historical Experiment semantics.
- Do not weaken the existing state machine or Fill non-erasure guarantees.

## Regression evidence required

- Focused deterministic persistence tests, including both reproduced findings.
- Dedicated PostgreSQL checks for unchanged state after identity/protection
  rejection where applicable.
- Relevant formatting, lint, type, and migration safety checks.
- No real provider call or credential use.

## Worker Evidence

### Implementation receipt

R001 is implemented at the provider-neutral persistence boundary without
schema, adapter, runtime, or broker changes.

- `apply_result()` now validates the complete immutable instruction identity
  (including quantity, prices, direction, account/instrument, correlation,
  Strategy/Risk/provenance, precision, and timing facts) before changing the
  durable projection. Conflicts raise `PaperIdentityConflict`.
- `apply_protection()`, `apply_execution_outcome()`, and the take-profit claim
  path now attribute Stop Loss and Take Profit client IDs, broker IDs, prices,
  provider states, durable Fill identity, and Fill-derived target geometry to
  the durable attempt. Invalid or incomplete protection cannot produce
  `FILLED_PROTECTED`.
- Added public-seam PostgreSQL regressions for same-ID conflict with unchanged
  state, unattributed protection with unchanged outcome, and exact valid
  protection reaching `FILLED_PROTECTED`.
- Updated the existing take-profit claim fixture to use the durable Fill-derived
  Stop Loss (`1.0950`) and Take Profit target (`1.1085`) prices.

### Checks and evidence

Passed:

- `uv run pytest -q backend/tests/paper/test_persistence_contracts.py backend/tests/paper/test_strategy_evaluation.py` — 25 passed.
- `ATLAS_TEST_DATABASE_URL=<configured test URL> PGOPTIONS='-c search_path=paper05_validation' uv run pytest -q backend/tests/integration/test_paper_execution_repository.py` — 9 passed.
- `uv run pytest -q backend/tests/integrations/test_oanda_protection_completion.py backend/tests/paper/test_execution_composition.py backend/tests/paper/test_execution_contracts.py` — 22 passed.
- `uv run pytest -m "not integration and not external" -q` — 927 passed, 4 skipped, 97 deselected; 4 existing warnings.
- Scoped Ruff check and format check for the repository and integration test — passed.
- Scoped Pyright for the repository and integration test — 0 errors.
- With the dedicated `paper05_validation` schema selected, `alembic current` reported `0022_paper_persistence (head)` and `alembic check` reported no new upgrade operations.
- `git diff --check` — passed.

### Concerns

- Unscoped repository gates remain non-clean outside this R001 slice:
  `ruff format --check backend` reports 68 files needing formatting,
  `ruff check backend` reports 28 errors, and `pyright backend` reports 2887
  errors. No unrelated cleanup was made.
- Running Alembic without the dedicated test URL/schema reports the configured
  database is not at head; the dedicated validation schema is at head and
  passes `alembic check`.
- No real provider calls, credentials, activation, or capital-capable actions
  were used.
