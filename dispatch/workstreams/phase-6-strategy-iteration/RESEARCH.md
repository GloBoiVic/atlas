# Phase 6 Task 02 validation research

## Classification

**Stale/incorrect test database configuration.** The API health tests do not
derive their database URL from an Atlas test-database convention. They
explicitly inject `postgresql+psycopg://u:p@localhost/atlas` in
`backend/tests/test_api_health.py:11-17`; therefore PostgreSQL quite correctly
reports `FATAL: role "u" does not exist` when that locally invented role has
not been provisioned. There is no evidence that role `u` is an Atlas default
or intended local provisioning target.

This is not an application configuration defect: `backend/config.py:23-50`
accepts a validated PostgreSQL URL supplied through `ATLAS_DATABASE_URL` and
does not select or require role `u`. The repository example uses
`atlas:atlas@127.0.0.1:5432/atlas` (`.env.example:1`), while the health test
uses a different role, password, host form, and database name.

## Why the failure appears during health tests

`create_app()` creates the configured engine (`backend/api/app.py:37-44`). Its
lifespan now synchronizes the Strategy catalog before serving requests
(`backend/api/app.py:48-54`). Consequently, mocking
`backend.api.health.check_database` in the readiness tests only mocks the
readiness endpoint check; it cannot prevent the lifespan catalog transaction
from opening the configured PostgreSQL connection. The liveness assertion is
still correct as an endpoint contract, but app startup must complete first.
Task 02 records the same unambiguous startup failure and says no health
assertion was reached (`dispatch/workstreams/phase-6-strategy-iteration/TASK-02-registry-catalog.md:36-39`).

## Established Atlas test-database convention

- Create/use a dedicated `atlas_test` database; the setup example creates both
  `atlas` and `atlas_test` (`README.md:36-43`).
- Integration tests receive the URL through `ATLAS_TEST_DATABASE_URL`, and the
  database name must end in `_test` (`README.md:101-114`).
- `backend/tests/integration/conftest.py:66-74` rejects URLs that are absent or
  whose database name does not end in `_test`; its session fixture migrates the
  configured URL (`:77-94`) and its function fixture truncates it in isolation
  (`:96-106`).
- The general pytest configuration labels integration tests as requiring a
  dedicated PostgreSQL test database (`pyproject.toml:34-39`).

The health test's `/atlas` target and hard-coded `u` role follow neither this
test convention nor the repository's documented local credentials.

## Minimum safe repair

No application configuration change, migration, credential change, or role
provisioning for `u` is warranted. Do not make `u` a new local convention.

The smallest safe validation repair is test-only: either (a) make the health
tests use a deliberately provisioned dedicated `_test` URL supplied by
`ATLAS_TEST_DATABASE_URL` and ensure its schema/catalog is migrated, if these
tests are intended to exercise real startup synchronization; or (b) keep them
unit-level by injecting/mocking the catalog synchronization (while retaining
the existing health-check mocks), so endpoint tests do not require PostgreSQL.
If the goal is specifically to validate Task 02 startup synchronization, use
option (a), not the production `atlas` database and not an arbitrary `u` role.
