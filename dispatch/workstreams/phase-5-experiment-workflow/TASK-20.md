# TASK-20 — Isolated E2E database URL and Phase 5 receipts

## Scope

Only the isolated E2E database URL was restored for execution; no application
code, dependencies, Git state, validation artifacts, or review artifacts were
changed.

## Database URL verification

- Command-scoped `ATLAS_E2E_DATABASE_URL`:
  `postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test`
- Verified scheme: `postgresql+psycopg`
- Verified database: `atlas_test`
- Verified `*_test` target: `True`
- Connectivity receipt: `connected_database=atlas_test`

## E2E receipts

- Affected Trade-detail E2E:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'configures, runs' --workers=1`
  — **BLOCKED** during global setup before browser test execution.
- Canonical Phase 5 E2E:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' npm run test:e2e -- --workers=1`
  — **BLOCKED** during global setup before browser test execution.

## Blocker

Both runs reached `backend.tests.e2e_seed`, but Alembic failed while creating
`alembic_version` with:

`psycopg.errors.InvalidSchemaName: no schema has been selected to create in`

The PostgreSQL connection itself succeeded against `atlas_test`; the blocker is
the database schema/search-path state during E2E migration setup. No E2E test
passed or ran, so validation readiness cannot be stated.
