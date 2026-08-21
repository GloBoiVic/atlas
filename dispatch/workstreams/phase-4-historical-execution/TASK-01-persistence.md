# Task 01 — Persistence receipt

## Changed paths

- `backend/persistence/migrations/versions/0006_phase_4_persistence_contract.py`
- `backend/persistence/models.py`
- `backend/persistence/experiment_repository.py`
- `backend/persistence/trading_repository.py`
- `backend/tests/test_migration_revision.py`
- `backend/tests/integration/test_migrations.py`

Added the Phase 4 additive schema contract: `PENDING` Experiment lifecycle support,
Order protection parent linkage, OrderEvents, Phase 4 Fill provenance/cost fields,
Trade cost/result/ambiguity fields, equity points, and one-to-one Experiment results.
Added append-only and terminal graph guards, lifecycle compatibility handling, and
flush-only repository support for running Experiments, order events, fills, equity,
and results.

## Migration and legacy compatibility

Migration `0006_phase_4_persistence` follows `0005_phase_3_failure_persistence`.
Phase 3 columns and rows remain nullable/unchanged; no legacy values are fabricated
or backfilled. Legacy Phase 3 inserts that omit status remain `RUNNING`; Phase 4
Experiments created through the repository start `PENDING`. Phase 4-only protection
parent validation is enforced by trigger based on the Phase 4 model version, so the
existing Phase 3 runner remains compatible. Downgrade restores the prior experiment
guard and removes only the additive Phase 4 schema.

## Focused checks

- `uv run ruff check ...` (Task 01 persistence, migration, and focused test paths): **passed**
- `uv run pytest backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py`: **passed**
- `uv run pytest backend/tests/integration/test_golden_flows.py`: **passed**
- `python -m compileall -q backend/persistence`: **passed**

## Scope exclusions

No clock, execution adapter, Fill application, runner loop, validation/review,
API/UI/runtime, broker, PAPER/LIVE behavior, or speculative infrastructure was
implemented.

## Blockers

None. No Git-changing command was performed.
