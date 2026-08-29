# Atlas

Atlas currently supports the historical EUR/USD workflow: load OANDA Practice
native M15 MID and sparse M1 BID/ASK observations, create immutable
DatasetSnapshots, configure and
run deterministic historical Experiments, inspect results and Trades, compare
completed Experiments, and inspect immutable StrategyVersion history. This is
historical simulation only: PAPER/LIVE broker execution is not implemented.

## Prerequisites

- Python 3.13 (see `.python-version`) and `uv`
- Node.js 22 LTS and npm
- PostgreSQL running locally on `127.0.0.1:5432`

## 1. Environment setup

Copy `.env.example` to `.env` and edit values for your machine. `.env` is
gitignored. The OANDA token is required for the historical-data load workflow.

```bash
cp .env.example .env
```

`.env.example` contains only a placeholder token. Put a real OANDA Practice
token only in your untracked `.env`; it is sent only as an Authorization header
to the fixed HTTPS Practice endpoint and is never a CLI argument or output.

The frontend requires its own local API URL because Next.js runs from
`frontend/`. Create an untracked `frontend/.env.local`:

```bash
cat > frontend/.env.local <<'EOF'
ATLAS_API_BASE_URL=http://127.0.0.1:8000
EOF
```

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

## 4. Prepare historical data (current V2 UI/API workflow)

All ranges must be explicit UTC, minute-aligned, positive, half-open ranges.
The authoritative V2 setup flow is the Experiments UI at
<http://localhost:3000/experiments/new>, backed by these API calls:

1. Check `GET /api/v1/historical-data/capability`.
2. Submit `POST /api/v1/historical-data/load-requests` with the selected
   `strategyVersionId`, `tradingStart`, and `tradingEnd` in UTC.
3. Poll `GET /api/v1/historical-data/load-requests/{id}` until the load is
   terminal. If the status requires recovery, explicitly resume with
   `POST /api/v1/historical-data/load-requests/{id}/resume`, then continue
   polling; an uncertain status is never resent automatically.
4. Select the completed V2 `DatasetSnapshot`, validate its coverage for the
   trading period (`POST /api/v1/experiments/coverage-validations`), then
   create the historical `Experiment` (`POST /api/v1/experiments`) with that
   immutable `StrategyVersion` and snapshot.

Failures are persisted with a nonzero terminal status. No raw database UUIDs or
credentials are normal output. OANDA failures are bounded and sanitized; a
timeout or partial provider failure never means that coverage is valid. Unknown
holidays and unexpected observations fail closed. Native M15 is validated from
immutable snapshot membership; M1 never substitutes for M15. No forward fill,
interpolation, or synthetic observations are created. OANDA Practice historical
candles are the only external capability.

To run an Experiment, Atlas needs a completed DatasetSnapshot with native M15 MID
coverage and sparse M1 BID/ASK membership for the selected period. The UI lists eligible data. If it has no
eligible DatasetSnapshot, load a sufficiently long range and create a snapshot.
Keep all Experiment periods
inside the snapshot's validated coverage.

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

**Runtime (optional for historical Experiments)** — use `uv run atlas-runtime --check` for a one-shot readiness check, or `uv run atlas-runtime` to run until stopped:

```bash
uv run atlas-runtime
```

Liveness is process-only; readiness checks PostgreSQL and returns sanitized 503 when unavailable.

**Stopping:** press Ctrl+C in each terminal. The runtime also exits cleanly on SIGTERM.

## 6. Use the current Strategy workflow

The current reference Strategy is **EMA Sweep Confirmation Break v2**. Use its immutable StrategyVersion with an eligible DatasetSnapshot to create and run a historical Experiment. Strategy analysis uses native M15 MID; sparse M1 BID/ASK observations are used only for execution simulation. Compare completed Experiments from the read-only comparison view; Atlas does not rank or recommend parameters.

1. Start PostgreSQL, apply migrations, then start the API and frontend as above.
2. Confirm the API is ready at <http://127.0.0.1:8000/health/ready> and open
   <http://localhost:3000/experiments/new>.
3. Select the parameter-enabled **EMA Sweep Confirmation Break v2** StrategyVersion and
   an eligible DatasetSnapshot. Choose a period within the snapshot coverage.
4. Run a baseline Experiment, then run 5–10 more while changing one supported
   parameter at a time (for example EMA period, ATR period, stop buffer, or
   target R). Record the exact parameter set, date range, snapshot, starting
   capital, and risk per Trade for each run.
5. Open the completed Experiment result. Inspect its metrics, equity curve,
   drawdown, and Trade list. Select an individual Trade to open its detail page.

The Trade detail page includes a charted execution context: canonical M15 MID
candles, EMA 100, setup markers, and entry, exit, initial-stop, and target
levels. Experiment results also expose equity and drawdown charts. These views
are historical Experiment evidence, not broker/PAPER/LIVE execution.

Parameter changes may alter signals, Trade count, exits, and metrics, but Atlas
does not promise that every valid parameter combination will produce a different
outcome for the same DatasetSnapshot and period. Use the Experiment comparison
view to compare completed runs; it is read-only and does not rank or recommend
parameters.

## 7. Engineering validation

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
