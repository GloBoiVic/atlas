# TASK-13 — PostgreSQL UTC session policy enforcement

## Outcome

**Explicitly blocked.** The central UTC session policy and direct-path adoption
were implemented and the focused PostgreSQL/integration receipts passed, but the
canonical E2E receipt still fails both valid browser scenarios with durable
`PERSISTENCE/PERSISTENCE_FAILURE` results. No workaround or further correction was
attempted.

## Canonical context update

Updated only `context/architecture/database.md`, under `## Time`, immediately
after the existing “Store timestamps in UTC…” paragraph. The exact approved text
was added:

> **PostgreSQL session policy:** Every Atlas PostgreSQL session operates with `TimeZone = 'UTC'`. UTC is canonical for persisted trading, market-data, Experiment, runtime, and audit timestamps. Atlas establishes this setting for every new and pooled connection; it must not depend on PostgreSQL server, database, or role defaults, or on host, developer, or deployment locale. Application input, domain, and persistence boundaries require timezone-aware UTC datetimes; naive datetimes must be rejected rather than interpreted through a machine-local timezone. This policy does not change canonical UTC bar alignment or timestamp semantics.

No other context file was changed by this task.

## Implementation mechanism and path inventory

- `backend/persistence/database.py` now owns
  `configure_utc_session_timezone(engine: Engine) -> Engine`.
- PostgreSQL/psycopg engines receive SQLAlchemy `connect` and `checkout` hooks.
  Both use the constant `SET SESSION TIME ZONE 'UTC'` through the DBAPI
  connection with temporary autocommit, closing the cursor and restoring the
  prior mode. This avoids touching an application transaction.
- Registration is marked on the Engine and is idempotent when called by both
  engine and session-factory composition.
- New physical connections, pooled checkouts, invalidation/reconnects, and
  `NullPool` migration connections are governed. Setup exceptions propagate and
  prevent handoff.
- `create_database_engine` and `create_session_factory` install the policy.
- Online Alembic migration composition calls the helper before `.connect()`.
- E2E seed and all direct application-semantic integration engines use the
  helper: `integration/conftest.py`, `test_database.py`,
  `test_phase5_valid_run.py`, `test_golden_flows.py`,
  `test_experiment_configuration.py`, `test_experiment_lifecycle.py`,
  `test_runner_failure_persistence.py`, `test_api_experiments.py`,
  `test_market_data_ingestion.py`, `test_market_data_repositories.py`,
  `test_fill_application.py`, `test_strategy_persistence.py`, and
  `test_migrations.py`.
- API/workflow (`backend/api/app.py`), historical CLI
  (`backend/market_data/cli.py`), and runtime (`backend/runtime/main.py`)
  inherit the shared engine/session path; no command-local timezone SQL was
  added.
- Inventory of backend `create_engine`, `engine_from_config`, `Session(engine)`,
  and `sessionmaker(bind=engine)` paths found no remaining ungoverned
  application-semantic engine construction.

## UTC policy proof

`backend/tests/integration/test_database.py` covers:

- fresh Session `SHOW TIME ZONE == UTC`;
- aware zero-offset `timestamptz` read;
- clean `session.begin()` handoff;
- committed pooled drift to `America/Chicago`, followed by checkout reset to
  UTC;
- repeated helper registration and dispose/reconnect behavior.

The hook executes before SQLAlchemy exposes the connection and uses no
application SQLAlchemy transaction. No naive datetime interpretation,
`replace(tzinfo=UTC)`, local-time reinterpretation, environment timezone,
server/database/role default, schema migration, or historical data mutation was
introduced. Task 12's inline test-only `SET TIME ZONE 'UTC'` statements were
removed from `test_phase5_valid_run.py` and `test_golden_flows.py`.

The requested isolated failure-injection receipt for setup failure was not
completed before the E2E blocker; the implementation intentionally propagates
setup failure rather than handing out an unknown session.

## Phase 5 and regression results

- Phase 5 primary and zero-Trade integration regression, with no inline
  timezone override: **2 passed in 46.23s**.
- Focused database policy regression: **2 passed in 1.39s**.
- Phase 1–4/golden regression (`test_golden_flows.py`), run serially after an
  earlier parallel attempt was discarded: **8 passed in 120.58s**.
- Lifecycle, API, runner-failure, market-data ingestion/repositories, Fill,
  Strategy, configuration, and migration integrations: **26 passed, 1 warning
  in 192.09s**. Warning was the pre-existing Starlette/httpx deprecation.
- Targeted Ruff receipt for all changed backend/context integration paths:
  **passed**.

## E2E blocker

Command:

```text
TZ=America/Los_Angeles ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' ATLAS_E2E_FIXTURE_FILE='/tmp/atlas-e2e-fixtures.json' npm run test:e2e
```

Result: **3 passed, 2 failed in 2.6m** with two workers. The invalid-coverage,
failed-Experiment, and foundation scenarios passed. The primary valid scenario
and zero-Trade scenario failed: the API durably returned
`PERSISTENCE/PERSISTENCE_FAILURE`; primary never reached Completed and the
zero-Trade assertion failed. The E2E host process used `TZ=America/Los_Angeles`.
This is not a passing timezone-independent receipt. No focused serial E2E
receipt, unmodified canonical passing E2E receipt, or full Phase 5 quality
matrix receipt exists.

Because the valid browser paths still fail after the governed integration path
was installed, this task stops without a runner-specific workaround, inline SQL,
fixture relaxation, or public failure-sanitization change. Validation and review
were not started.

## Files changed

- `context/architecture/database.md`
- `backend/persistence/database.py`
- `backend/persistence/migrations/env.py`
- `backend/tests/e2e_seed.py`
- `backend/tests/integration/conftest.py`
- `backend/tests/integration/test_database.py`
- `backend/tests/integration/test_phase5_valid_run.py`
- `backend/tests/integration/test_golden_flows.py`
- `backend/tests/integration/test_experiment_lifecycle.py`
- `backend/tests/integration/test_api_experiments.py`
- `backend/tests/integration/test_experiment_configuration.py`
- `backend/tests/integration/test_market_data_ingestion.py`
- `backend/tests/integration/test_market_data_repositories.py`
- `backend/tests/integration/test_runner_failure_persistence.py`
- `backend/tests/integration/test_fill_application.py`
- `backend/tests/integration/test_strategy_persistence.py`
- `backend/tests/integration/test_migrations.py`
- this `TASK-13.md`

## Forbidden-operations confirmation

No Git mutation, dependency or browser installation, server/database/role
default change, non-test data migration, historical data mutation, Phase 6
work, worktree operation, validation artifact, review artifact, prior task
artifact, PLAN, ARCHITECTURE, READY, ACTIVE, or COMPLETED artifact was altered
by this task. The known pre-existing working-tree changes were preserved.
