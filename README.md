# Atlas

Atlas is a local-first, single-user algorithmic trading platform.

The committed `main` branch currently supports historical EUR/USD research: historical OANDA Practice market data is loaded into immutable DatasetSnapshots, registered immutable StrategyVersions are evaluated through deterministic Experiments, centralized Risk and simulated execution produce auditable trading facts, and results and Trades can be inspected through the application.

PAPER/LIVE broker execution is not a committed-main capability unless the current implementation and tests explicitly show otherwise.

## Prerequisites

- Python 3.13
- `uv`
- Node.js
- npm
- PostgreSQL on `127.0.0.1:5432`

See `.python-version` and the committed package manifests for exact dependency requirements.

## Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Set local database configuration in `.env`.

A real OANDA Practice token is required only for workflows that call the external OANDA historical-data API. Keep credentials only in ignored environment files. Do not place credentials in commands, source files, committed fixtures, or logs.

Install dependencies:

```bash
uv sync --all-groups
npm ci
```

The frontend reads its local API base URL from an ignored `frontend/.env.local`:

```text
ATLAS_API_BASE_URL=http://127.0.0.1:8000
```

## Database

Use separate development and test databases.

For example:

```bash
createdb atlas
createdb atlas_test
```

Apply and verify migrations:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Alembic uses `ATLAS_DATABASE_URL`.

Migration history lives under:

```text
backend/persistence/migrations/
```

Integration tests must use a dedicated PostgreSQL database whose name ends in `_test`.

## Run Atlas

Run the API:

```bash
uv run uvicorn backend.api.app:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8000 \
  --no-proxy-headers \
  --reload
```

API:

```text
http://127.0.0.1:8000
```

OpenAPI documentation:

```text
http://127.0.0.1:8000/docs
```

Health endpoints:

```text
/health/live
/health/ready
```

Run the frontend:

```bash
npm run dev:web
```

Frontend:

```text
http://localhost:3000
```

## Runtime process

The committed runtime process currently provides database readiness and process lifecycle behavior.

Check readiness:

```bash
uv run atlas-runtime --check
```

Run the process:

```bash
uv run atlas-runtime
```

Do not assume that starting `atlas-runtime` activates PAPER or LIVE trading. Capital-capable runtime behavior must be demonstrated by current implementation and requires explicit trader authorization.

## Historical Experiment workflow

The supported historical workflow is:

```text
Historical OANDA Practice data
→ immutable DatasetSnapshot
→ immutable StrategyVersion
→ deterministic Experiment
→ Risk / simulated execution
→ Trade and result evidence
```

The current historical market-data path includes provider-native analytical and execution observations required by registered Strategy contracts. Atlas preserves provenance and fails closed when required observations are invalid, incomplete, missing, or inconsistent.

The Experiments setup page is:

```text
http://localhost:3000/experiments/new
```

The API exposes historical-data, Strategy, Experiment, result, and Trade contracts under `/api/v1/`.

Use the generated OpenAPI contract and current application code as authority for exact endpoint shapes.

## Validation

Backend formatting:

```bash
uv run ruff format --check backend
```

Backend lint:

```bash
uv run ruff check backend
```

Backend typing:

```bash
uv run pyright backend
```

Non-integration backend tests:

```bash
uv run pytest -m "not integration and not external"
```

PostgreSQL integration tests:

```bash
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> \
uv run pytest -m integration
```

External credentialed checks are opt-in:

```bash
uv run pytest -m external
```

Frontend checks:

```bash
npm run check:web
```

End-to-end tests:

```bash
npx playwright install chromium
npm run test:e2e
```

## Repository guidance

Permanent repository guidance is intentionally small:

- `AGENTS.md` — how coding agents should locate authoritative context.
- `DOMAIN.md` — durable cross-cutting Atlas trading laws.
- `README.md` — setup, operation, and supported workflow.
- `dispatch/` — active and historical SoloFlow workstreams.

Current implementation behavior belongs primarily to code, tests, migrations, schemas, and generated contracts rather than long-form feature or architecture documentation.

Closed workstreams are historical evidence, not current specifications.

## Safety

Atlas is designed to fail closed around financial uncertainty.

Do not:

- fabricate missing market data;
- infer a Fill from an Order request;
- assume an uncertain broker submission failed or succeeded;
- blindly retry an outcome-unknown Order;
- treat stale or contradictory financial state as safe;
- resume exposure-creating operation before required reconciliation;
- expose credentials through logs, source code, or committed files.

PAPER/LIVE activation, broker credential changes, Risk-policy changes, and capital-capable broker actions require explicit trader approval.
