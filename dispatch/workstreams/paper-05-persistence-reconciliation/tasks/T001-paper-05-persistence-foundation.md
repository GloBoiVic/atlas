# T001 — PAPER 05 Persistence Foundation

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`
- **Owned artifact:** this file
- **Depends on:** frozen `PLAN.md` and `ARCHITECTURE.md`; completed GIT START

## Objective

Implement the provider-neutral PAPER persistence foundation required to make one
PAPER 04 attempt durable without reusing historical Experiment persistence.

## In scope

- Add immutable/provider-neutral PAPER value contracts and strict bounded
  serialization for StrategyVersion provenance, Risk evidence, broker
  observations, Fill facts, and reconciliation findings.
- Bind the durable handoff to the exact verified StrategyVersion and validated
  parameter snapshot without changing Strategy methodology or `StrategyDecision`.
- Add the five-outcome state-transition validator and fail-closed conflict rules.
- Add PAPER-specific SQLAlchemy models for attempts, permanent mutation claims,
  normalized broker observations, reconciliation runs, and findings.
- Add the child Alembic migration from `0021_experiment_deletion` with required
  indexes, foreign keys, append-only guards, immutable-fact guards, outcome
  checks, and unique attempt/phase/correlation constraints.
- Add `PaperExecutionRepository` with pre-mutation commit boundaries, exact
  attempt identity comparison, row locking/optimistic projection protection,
  permanent no-expiry claims, append-only observations/findings, and guarded
  projection application.
- Add deterministic unit and dedicated PostgreSQL-facing tests for the public
  persistence seams, including migration shape, constraints, concurrent claims,
  rollback, Fill non-erasure, and valid/invalid outcome transitions where
  feasible in this foundation slice.

## Explicit non-goals

- No OANDA POST/PUT call, runtime loop, scheduler, activation, recovery
  mutation, protection repair, close/reduce, LIVE, or real credential use.
- Do not alter historical Experiment `Order`/`Fill`/`Trade` semantics.
- Do not change Strategy methodology, Risk authority, or PAPER 04 provider
  semantics.

## Completion requirements

1. All new persistence code is PAPER-specific and provider-neutral at the
   repository boundary.
2. A durable attempt can retain the exact instruction/Risk/provenance evidence
   and cannot be replaced by a same-ID conflicting instruction.
3. A committed `ENTRY` or `TAKE_PROFIT` claim is unique, permanent, and never
   treated as proof that HTTP was dispatched.
4. Proven Fill facts are write-once and cannot be erased by later `UNKNOWN` or
   protection updates.
5. Provider observations remain append-only and distinct from Atlas outcome
   projections.
6. The database enforces the last-line safety invariants from
   `ARCHITECTURE.md`; repository validation remains the semantic authority.
7. Focused deterministic tests pass, and the task receipt below is complete.

## Worker Evidence

Populate on completion with:

```text
ROLE: BUILD
STATUS: DONE | BLOCKED | DONE_WITH_CONCERNS
ARTIFACT: this file
FILES CHANGED: <paths>
CHECKS / EVIDENCE: <commands and results>
FINDINGS / CONCERNS: <brief result>
```

## Completion Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T001-paper-05-persistence-foundation.md`
FILES CHANGED: `backend/paper/__init__.py`, `backend/paper/persistence_contracts.py`, `backend/paper/strategy_evaluation.py`, `backend/persistence/__init__.py`, `backend/persistence/models.py`, `backend/persistence/paper_execution_repository.py`, `backend/persistence/migrations/versions/0022_paper_persistence_foundation.py`, `backend/tests/paper/test_persistence_contracts.py`, `backend/tests/paper/test_strategy_evaluation.py`, `backend/tests/integration/test_paper_execution_repository.py`, `backend/tests/integration/test_migrations.py`, `backend/tests/test_migration_revision.py`
CHECKS / EVIDENCE:

- Targeted Ruff check: passed.
- Targeted Ruff format check: 12 files already formatted.
- Targeted Pyright for changed PAPER/persistence code and tests: `0 errors`.
- `python -m compileall -q backend/paper backend/persistence`: passed.
- `uv run pytest -m "not integration and not external" -q`: `927 passed, 4 skipped, 90 deselected`.
- Focused PAPER/migration tests: `63 passed`.
- Dedicated PostgreSQL repository tests: `6 passed`, covering commit-before-claim, same-ID conflict, concurrent claims, Fill non-erasure, Take Profit prerequisites, observation replay, stale reconciliation, and database append-only/immutable guards.
- Dedicated PostgreSQL schema `paper05_validation`: `uv run alembic check` reported no new operations; downgrade to `0020_fix_snapshot_guard` and upgrade to `0022_paper_persistence` completed; current revision is `0022_paper_persistence`.

FINDINGS / CONCERNS: The repository's migration integration test could not run against the configured `atlas_test` public schema because the `atlas` role does not own `public` (`must be owner of schema public`). The migration cycle was instead verified in the dedicated owned `paper05_validation` schema. Full-repository Pyright still reports pre-existing errors outside this slice; changed-slice Pyright is clean. No broker calls, credentials, runtime activation, or capital-capable execution were introduced.
