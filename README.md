# Atlas Phase 2 — Historical Data

Atlas currently provides the historical EUR/USD data slice: OANDA Practice M1
candles, immutable dataset snapshots, and deterministic M15 derivation. There
are no trading, live, or API routes in this slice.

## Prerequisites

- Python 3.13 (see `.python-version`) and `uv`
- Node.js 22 LTS and npm
- PostgreSQL running locally on `127.0.0.1:5432`

## 1. Environment setup

Copy `.env.example` to `.env` and edit values for your machine. `.env` is
gitignored. The OANDA token is optional for coverage, snapshot, and derivation;
load and refresh fail clearly when it is absent.

```bash
cp .env.example .env
```

`.env.example` contains only a placeholder token. Put a real OANDA Practice
token only in your untracked `.env`; it is sent only as an Authorization header
to the fixed HTTPS Practice endpoint and is never a CLI argument or output.

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

## 4. Historical data commands

All ranges must be explicit UTC, minute-aligned, positive, half-open ranges.
Commands print stable summaries; `--json` produces compact sorted-key JSON.

```bash
uv run atlas-data load-missing --start 2025-01-06T00:00:00Z --end 2025-01-07T00:00:00Z
uv run atlas-data refresh --start 2025-01-06T00:00:00Z --end 2025-01-07T00:00:00Z
uv run atlas-data coverage --start 2025-01-06T00:00:00Z --end 2025-01-07T00:00:00Z --warm-up-bars 50
uv run atlas-data snapshot --start 2025-01-06T00:00:00Z --end 2025-01-07T00:00:00Z
uv run atlas-data derive-m15 --snapshot-fingerprint <sha256> --component MID
```

Failures have a nonzero exit status. No raw database UUIDs or credentials are
normal output. OANDA failures are bounded and sanitized; a timeout or partial
provider failure never means that coverage is valid. Unknown holidays and
unexpected observations fail closed. M15 is derived only from immutable
snapshot membership; no forward fill, interpolation, or synthetic bars are
created. OANDA Practice historical candles are the only external capability.

## 5. Run the stack

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

## 6. Validation

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration and not external"
ATLAS_TEST_DATABASE_URL=<dedicated *_test DB> uv run pytest -m integration
npx playwright install chromium
npm run check:web
npm run test:e2e
```

Integration tests require `ATLAS_TEST_DATABASE_URL` exported in your shell, pointing at a dedicated PostgreSQL database whose name ends in `_test` (e.g. `atlas_test`). Keep it out of `.env` — Atlas settings reject unknown `ATLAS_*` variables. Playwright e2e tests start their own web server (`npm run dev:web`) unless one is already running on port 3000.

The credentialed OANDA check is separately marked `external`, is opt-in, uses a
small closed historical range, and never calls account or trading endpoints.
