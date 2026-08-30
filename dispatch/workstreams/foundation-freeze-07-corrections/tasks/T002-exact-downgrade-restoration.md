# T002 — Exact 0021 downgrade restoration

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-corrections`
- Depends on: none
- Owns: migration downgrade body and focused migration-cycle tests

## Required implementation

Correct migration `0021` downgrade so `snapshot_v2_append_only_guard()` is
restored to the exact revision-0020 canonical function body. At revision 0020,
the row trigger handles UPDATE/DELETE and INSERT validation belongs to the
`snapshot_v2_insert_guard` statement trigger. Preserve all other downgrade and
upgrade semantics exactly.

## Required proof

Strengthen the migration-cycle test to compare the relevant restored function
definition and trigger contract, including operation timing/coverage, rather
than merely function existence or generic immutability behavior. Run focused
upgrade/downgrade tests and preserve ordinary guarded DML behavior.

## Completion instructions

BUILD must update this file with final status, changed paths, checks/evidence, and
concerns. Do not edit PLAN.md, ARCHITECTURE.md, ACTIVE.md, VALIDATION.md, REVIEW.md,
or T001. Do not start pre-PAPER/PAPER work.

## Completion receipt

- Status: `DONE`
- Files changed:
  - `backend/persistence/migrations/versions/0021_experiment_deletion_lifecycle.py`
  - `backend/tests/integration/test_migrations.py`
- Checks/evidence:
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test pytest -q backend/tests/integration/test_migrations.py::test_downgrade_to_0020_restores_guarded_trigger_dependencies` — passed.
  - Focused migration cycle and revision checks — 4 passed.
  - `ruff check` on changed Python files — passed.
  - `compileall` and `git diff --check` — passed.
  - Downgrade proof compares the exact restored 0020 function definition, all row/statement trigger definitions, valid V2 insert, rejected non-V2 insert, and rejected UPDATE/DELETE.
- Concerns: none. Pre-existing unrelated worktree changes were left untouched.
