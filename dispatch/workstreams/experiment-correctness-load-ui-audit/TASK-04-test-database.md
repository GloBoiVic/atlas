# TASK-04 — Test database environment diagnosis

## Receipt

- **Role:** Environment diagnosis specialist
- **Artifact:** `dispatch/workstreams/experiment-correctness-load-ui-audit/TASK-04-test-database.md`
- **Scope:** Read-only diagnosis of why pytest does not receive `ATLAS_TEST_DATABASE_URL`, plus a non-mutating connectivity probe.
- **Inputs reviewed:** `dispatch/ACTIVE.md`, `PLAN.md`, `ARCHITECTURE.md`, `EXPLORATION.md`, `READY.md`, `VALIDATION.md`, backend pytest/conftest/configuration, `frontend/app/globals.css`, and the PLAN UI reference manifest.
- **Not present:** There is no workstream-local `ACTIVE.md`; the repository-level `dispatch/ACTIVE.md` was reviewed instead.
- **Safety:** No application code, database setup, `.env` file, or Git state was changed. No migration, truncation, DDL, DML, or other destructive database command was run. Secrets and credential values were not printed or recorded.

## Finding

The dedicated test URL is present in the root `.env` and is loadable by Pydantic Settings, but it is **not exported in the pytest process environment**.

Evidence from the read-only environment probe:

- Root `.env` contains the keys `ATLAS_DATABASE_URL` and `ATLAS_TEST_DATABASE_URL`.
- `ATLAS_TEST_DATABASE_URL` is absent from `os.environ` in a normal shell-launched Python process.
- `Settings()` successfully loads `.env`; its `test_database_url` is configured for loopback PostgreSQL database `atlas_test` (credential value omitted).
- `frontend/.env.local` only contains the frontend API-base key and is unrelated to pytest.

The precedence/configuration mismatch is the direct cause:

1. `backend/config.py` declares `SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="forbid")`. Thus `Settings()` can read `ATLAS_TEST_DATABASE_URL` from `.env`; an actual process environment variable would take precedence over the dotenv value.
2. `backend/tests/integration/conftest.py::_test_database_url()` reads **only** `os.environ.get("ATLAS_TEST_DATABASE_URL")`; it does not call `Settings()` and therefore does not see Pydantic's dotenv-loaded value.
3. The integration tests likewise read `os.environ` directly. With the key absent, the fixture returns `None`, migration/isolation fixtures no-op, and individual integration tests skip or fail with the reported “ATLAS_TEST_DATABASE_URL is required” condition.
4. `pyproject.toml` only registers the `integration` marker; it does not load dotenv files or inject environment variables. `.env.example` documents the intended key but is not an injection mechanism.
5. The integration session fixture deliberately copies the test URL into `ATLAS_DATABASE_URL` only **after** `_test_database_url()` has obtained it from `os.environ` (before migrations). That fallback cannot help when the initial test key is absent.

This matches `VALIDATION.md`: the non-integration suite passes, while the full pytest run reports PostgreSQL integration setup errors due to missing `ATLAS_TEST_DATABASE_URL`.

## Database availability

A non-mutating connection probe using the dotenv-loaded test URL and `SELECT 1, current_database()` succeeded:

```text
dedicated test database: reachable=True probe=1 database=atlas_test
```

The local PostgreSQL readiness probe also reported accepting connections. Reachability is therefore **YES** for the configured dedicated database. This does not imply that the schema is at Alembic head or that integration tests are safe to run concurrently; the integration fixture performs migrations and truncation when enabled.

## Exact safe checks/commands

These checks do not print secret values. They inspect key presence and URL metadata only:

```bash
python - <<'PY'
import os
from pathlib import Path
from urllib.parse import urlsplit
from backend.config import Settings

for key in ("ATLAS_DATABASE_URL", "ATLAS_TEST_DATABASE_URL"):
    print(f"process {key}: present={key in os.environ}")
print("dotenv keys:", [
    line.split("=", 1)[0].strip()
    for line in Path(".env").read_text().splitlines()
    if line.strip() and not line.lstrip().startswith("#") and "=" in line
])
settings = Settings()
value = settings.test_database_url.get_secret_value() if settings.test_database_url else None
parsed = urlsplit(value) if value else None
print("Settings test URL:", {
    "configured": value is not None,
    "host": parsed.hostname if parsed else None,
    "port": parsed.port if parsed else None,
    "database": parsed.path.lstrip("/") if parsed else None,
})
PY
pg_isready
```

This is a non-mutating connectivity check for the configured dedicated URL (the
driver URL is normalized only in memory; the password is never printed):

```bash
python - <<'PY'
from backend.config import Settings
from sqlalchemy.engine import make_url
import psycopg

settings = Settings()
assert settings.test_database_url is not None, "test URL is not configured"
url = make_url(settings.test_database_url.get_secret_value())
connect_url = url.set(drivername="postgresql").render_as_string(hide_password=False)
with psycopg.connect(connect_url, connect_timeout=3) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1, current_database()")
        probe, database = cur.fetchone()
print(f"reachable={probe == 1} database={database}")
PY
```

To run the integration suite, the operator must inject the test URL into the
pytest process environment from an approved local secret source; do not copy a
credential into this artifact and do not use a production database. A safe
pattern is to export the already-approved value in the invoking shell, verify
only presence, then run pytest:

```bash
export ATLAS_TEST_DATABASE_URL='postgresql+psycopg://<approved-test-credential>@127.0.0.1:5432/atlas_test'
test -n "${ATLAS_TEST_DATABASE_URL:-}" && echo 'ATLAS_TEST_DATABASE_URL is set'
pytest -q
```

The export value is intentionally a placeholder here. Because the integration
fixtures migrate and truncate the dedicated test database, `pytest -q` is not a
diagnostic-only command and was **not** run as part of this task.

## Handoff

- **Diagnosis:** dotenv configuration exists, but pytest fixtures require an OS environment variable and do not consume `Settings.test_database_url`.
- **Dedicated DB reachable:** YES (`atlas_test`, loopback PostgreSQL, `SELECT 1` succeeded).
- **Required next action:** inject `ATLAS_TEST_DATABASE_URL` into the pytest process using an approved secret source, then rerun the backend integration/full suite under the existing fixture isolation rules.
- **No application/config fix made:** per task scope, this artifact records diagnosis only.
