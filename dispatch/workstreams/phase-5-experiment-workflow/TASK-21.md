# TASK-21 — Repair isolated test database and rerun E2E

## Scope

Local test environment only. No application code, persistence models, UTC
application behavior, production database, or non-test database was changed.

## Destructive-operation safety proof

Before resetting or truncating anything, the command-scoped target was verified
as `postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test` and a connection
reported:

- `current_database=atlas_test`
- `current_user=atlas`
- target database name ends with `_test`: `True`

The only destructive operation was the existing E2E seed's truncation of tables
in `atlas_test`.

## Diagnosis

The database existed and was reachable, but its isolated setup was incomplete:

- Database owner: `vike` (expected test application role: `atlas`)
- `public` schema owner: `vike`
- `public` schema `USAGE`: `False`
- `public` schema `CREATE`: `False`
- Session timezone: `America/Chicago`
- Effective search path/current schema: `"$user", public` / `None`
- Existing `public` tables, including `alembic_version`, were owned by `vike`

This explains the prior `no schema has been selected to create in` failure and,
after schema repair, the subsequent `permission denied for table
alembic_version` failure.

## Test-only repair and migration

Using the existing `atlas` role/database conventions, `atlas_test` was repaired
only:

- Database owner set to `atlas`.
- Database defaults set to `search_path=public` and `timezone=UTC`.
- `public` schema owner set to `atlas`; `USAGE` and `CREATE` granted.
- Existing public tables/sequences were transferred to `atlas` and granted
  full test-role privileges.
- Alembic upgraded to `0007_phase_5_metric_contract`.
- E2E seed completed successfully: 1 strategy, 3 experiments, 4,752 market
  bars, and 2 dataset snapshots.

Post-repair connection verification reported `timezone=UTC`,
`search_path=public`, `current_schema=public`, database/schema owner `atlas`,
and schema `USAGE`/`CREATE` both `True`. `alembic check` reported:
`No new upgrade operations detected.`

## E2E receipts

- Affected test:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'configures, runs' --workers=1`
  — **1 passed**.
- Full E2E:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' npm run test:e2e -- --workers=1`
  — **5 passed**.

The isolated database setup blocker is resolved. The work is ready for
validation; validation/review was not performed as part of this task.
