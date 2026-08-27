# T009 — Native M15 migration remediation

Status: `DONE_WITH_CONCERNS`

Resolve the T008 live PostgreSQL blocker narrowly. Reconcile revision `0015` with the
actual naming-convention constraint names so native M15 rows can persist while M1
constraints remain correct. Preserve migration history and fail-closed invariants;
prove clean upgrade and downgrade/re-upgrade. Then rerun the genuine full-calendar-year
OANDA durable load and unchanged repeat covered request, recording zero repeat provider
calls. Do not weaken validation or expose credentials.

## Completion receipt

### Migration remediation

- Updated revision `0015_native_resolutions` to drop the PostgreSQL names produced
  by Atlas's naming convention: `ck_market_bars_m1_only`,
  `ck_market_bars_exact_one_minute`, and
  `ck_market_bars_minute_aligned_start`.
- Updated downgrade to drop the corresponding generated names for the native
  constraints. It still recreates the legacy M1-only checks, so M1 validation
  remains fail-closed after downgrade.
- Added integration assertions for generated constraint names, native M15
  persistence, and rejection of an M1 row with a 15-minute interval.

### Evidence

- Direct inspection of the configured PostgreSQL database before the change
  reported Alembic version `0008_proposal_constraints` and generated legacy
  checks including `ck_market_bars_exact_one_minute` and
  `ck_market_bars_m1_only`. Credentials were not printed or persisted.
- `uv run ruff check ...0015_native_market_bar_resolutions.py ...test_migrations.py`:
  **passed**.
- `git diff --check`: **passed**.
- `uv run pytest -q backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py`:
  **1 passed, 2 skipped**; PostgreSQL integration tests were skipped because
  `ATLAS_TEST_DATABASE_URL` is not configured.
- A clean `uv run alembic upgrade head` against the configured database was
  attempted and rolled back transactionally at revision `0014_result_metric_state_details`
  because existing `experiment_results` rows are protected by the immutable-facts
  trigger (`historical facts are immutable`). No trigger, validation, or migration
  history was weakened.

### Durable OANDA rerun

- **Not run.** The configured database could not be advanced to migration head
  without resolving the pre-existing 0014 immutable-data conflict, and the
  configured database role cannot create a dedicated clean test database. No
  post-remediation first-run or unchanged repeat metrics are claimed; zero repeat
  provider calls are not claimed.

Concern: the generated-name fix is implemented and covered by the available
integration regression, but clean upgrade/downgrade/re-upgrade and the genuine
2025 full-calendar-year OANDA durable load remain blocked by the environment's
pre-existing 0014 migration failure and absent dedicated test database URL.
