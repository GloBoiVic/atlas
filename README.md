# Atlas

Atlas is currently a historical-research application for EUR/USD. The supported
path is OANDA Practice historical candles → immutable `DatasetSnapshot` →
deterministic historical `Experiment` → inspectable results and `Trade` records.
PAPER/LIVE broker execution is not a committed-main capability.

## Prerequisites

- Python 3.13 (see `.python-version`) and `uv`
- Node.js 22 LTS and npm
- PostgreSQL on `127.0.0.1:5432`

## Setup

Copy `.env.example` to the ignored `.env`, then set local database values. A real
OANDA Practice token is required only when loading historical data; keep it in
`.env`, never in a command, source file, or log.

```bash
cp .env.example .env
uv sync --all-groups
npm ci
```

The frontend reads its local API URL from an ignored `frontend/.env.local`:

```text
ATLAS_API_BASE_URL=http://127.0.0.1:8000
```

Create separate development and test databases, for example:

```bash
createdb atlas
createdb atlas_test
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Alembic uses `ATLAS_DATABASE_URL`; migration files are in
`backend/persistence/migrations`.

## Historical Experiment workflow

All requested periods are positive, minute-aligned, UTC half-open ranges. The
Experiments setup page is <http://localhost:3000/experiments/new>.

1. Check `GET /api/v1/historical-data/capability`.
2. Start a load with `POST /api/v1/historical-data/load-requests`, passing the
   selected `strategyVersionId`, `tradingStart`, and `tradingEnd`.
3. Poll `GET /api/v1/historical-data/load-requests/{id}`. Resume only explicitly
   with `POST /api/v1/historical-data/load-requests/{id}/resume` when recovery is
   required; uncertain loads are not resent automatically.
4. Choose the completed V2 `DatasetSnapshot`, validate coverage with
   `POST /api/v1/experiments/coverage-validations`, and create an `Experiment`
   with `POST /api/v1/experiments`.
5. Run it with `POST /api/v1/experiments/{id}/run`, then inspect the result,
   equity, price-analysis, and Trade endpoints or the corresponding UI pages.

The current Strategy is **EMA Sweep Confirmation Break v2**. Its analysis uses
native M15 MID candles; sparse native M1 BID/ASK observations are used only for
historical execution simulation. The Strategy requires its declared historical
context, and the Experiment period must remain inside validated snapshot
coverage. Results, inputs, StrategyVersion identity, and snapshot provenance are
immutable evidence while the Experiment exists. Completed Experiments can be
compared read-only; Atlas does not rank or recommend parameters.

Historical loading and simulation fail closed on invalid, incomplete, or
unexpected data. No forward fill, interpolation, synthetic price, or M1
substitution for native M15 is created. Provider failures are bounded and
sanitized; credentials and raw database UUIDs are not normal display labels.

## Run the applications

Run each command in its own terminal:

```bash
# API: http://127.0.0.1:8000; docs at /docs; health at /health/live and /health/ready
uv run uvicorn backend.api.app:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --reload

# Frontend: http://localhost:3000
npm run dev:web
```

The API is restricted to loopback peers and local host authority. The optional
`atlas-runtime` process only checks PostgreSQL readiness and waits for shutdown;
it does not execute historical Experiments:

```bash
uv run atlas-runtime --check
uv run atlas-runtime
```

## Validation

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration and not external"
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> uv run pytest -m integration
npx playwright install chromium
npm run check:web
npm run test:e2e
```

Integration tests must use a dedicated PostgreSQL database whose name ends in
`_test`. The credentialed OANDA check is separately marked `external` and is
opt-in: `uv run pytest -m external`.
