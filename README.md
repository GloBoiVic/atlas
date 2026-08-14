# Atlas Phase 0

Foundation only: Next.js, FastAPI, synchronous SQLAlchemy/PostgreSQL, Alembic baseline, and `atlas-runtime`; no trading functionality.

## Prerequisites

- Python 3.13 (see `.python-version`) and `uv`
- Node.js 22 LTS and npm
- PostgreSQL running locally on `127.0.0.1:5432`

## 1. Environment setup

Copy `.env.example` to `.env` and edit values for your machine. `.env` is gitignored; never commit it or copy real credentials from anywhere else into it.

```bash
cp .env.example .env
```

`.env.example` ships with local development defaults; adjust `ATLAS_DATABASE_URL` in `.env` to your own PostgreSQL credentials and database names.

## 2. Install dependencies

```bash
uv sync --all-groups
npm ci
```

`uv sync` creates the project virtualenv and installs runtime plus dev groups. `npm ci` installs frontend dependencies from the committed lockfile.

## 3. Database and migrations

Create the two databases with your local PostgreSQL setup, for example:

```bash
createdb atlas
createdb atlas_test
```

Apply the baseline and verify migration state:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Migrations live in `backend/persistence/migrations` and read `ATLAS_DATABASE_URL` from `.env`.

## 4. Run the stack

Run each command in its own terminal. Python application source and backend tests live directly under the `backend/` Python package.

**Frontend** — browser at http://localhost:3000

```bash
npm run dev:web
```

**API** — base at http://127.0.0.1:8000, interactive docs at `/docs`, health at `/health/live` and `/health/ready`

```bash
uv run uvicorn backend.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

**Runtime** — use `uv run atlas-runtime --check` for a one-shot readiness check, or `uv run atlas-runtime` to run until stopped:

```bash
uv run atlas-runtime
```

Liveness is process-only; readiness checks PostgreSQL and returns sanitized 503 when unavailable.

**Stopping:** press Ctrl+C in each terminal. The runtime also exits cleanly on SIGTERM.

## 5. Validation

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration"
uv run pytest -m integration
npm run check:web
npx playwright install chromium
npm run test:e2e
```

Integration tests require `ATLAS_TEST_DATABASE_URL` exported in your shell, pointing at a dedicated PostgreSQL database whose name ends in `_test` (e.g. `atlas_test`). Keep it out of `.env` — Atlas settings reject unknown `ATLAS_*` variables. Playwright e2e tests start their own web server (`npm run dev:web`) unless one is already running on port 3000.
