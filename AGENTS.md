# Atlas

Atlas is a single-user algorithmic trading platform for taking a trading methodology through controlled, reproducible research and eventually PAPER and LIVE operation.

Atlas prioritizes correctness, reproducibility, capital safety, simplicity, auditability, and trader control over speculative abstraction or scale.

## Sources of truth

Use each source only for the question it owns.

- **Desired change:** the approved active task/workstream.
- **Current implementation behavior:** code, nearby tests, schemas/migrations, and generated contracts.
- **Durable trading semantics:** `DOMAIN.md`.
- **Setup, operation, and supported user workflow:** `README.md`.
- **Historical reasoning:** closed `dispatch/` workstreams and Git history, only when explicitly needed.

Historical workstreams describe what happened at that time. They are not current specifications.

If prose conflicts with current implementation, do not silently make code match stale prose. Determine which source owns the question and surface genuine contradictions.

## Progressive context loading

For implementation work:

1. Read this file.
2. Read the approved active workstream/task.
3. Inspect the affected implementation and nearby tests.
4. Inspect relevant schemas and migrations when persistence is involved.
5. Consult only applicable sections of `DOMAIN.md`.
6. Consult `README.md` when setup, runtime, or supported workflow matters.
7. Load closed workstreams or Git history only for explicit regression, provenance, or rationale investigation.

Do not bulk-load historical documentation.

Do not create a parallel prose representation of the application.

## Repository map

- `backend/domain/` — core typed domain values and contracts.
- `backend/strategies/` — Strategy contracts, registration, provenance, and implementations.
- `backend/experiments/` — deterministic historical Experiment execution.
- `backend/market_data/` — historical market-data acquisition, validation, and provenance.
- `backend/risk/` — centralized Risk decisions.
- `backend/execution/` — execution-domain behavior and Fill application.
- `backend/integrations/` — external provider boundaries, currently including OANDA historical data.
- `backend/persistence/` — SQLAlchemy persistence and Alembic migrations.
- `backend/api/` — FastAPI application and HTTP contracts.
- `backend/runtime/` — runtime process boundary.
- `frontend/` — Next.js trader interface.
- `backend/tests/` and `tests/e2e/` — executable behavior and workflow evidence.
- `dispatch/` — active and historical SoloFlow workstreams.

## Current boundary

Committed `main` supports historical EUR/USD research using OANDA Practice historical data, immutable DatasetSnapshots, deterministic Experiments, centralized Risk, simulated execution, and inspectable Trade/results evidence.

PAPER/LIVE broker execution, broker reconciliation, and capital-capable runtime behavior are not committed-main capabilities unless current code and tests explicitly show otherwise.

Do not infer a future capability from historical workstreams.

## Engineering rules

- Implement the narrowest complete slice required by the approved task.
- Prefer explicit, typed, local abstractions over speculative frameworks.
- Do not generalize for future brokers, instruments, Strategies, users, workers, or deployment models unless the current task requires it.
- Preserve existing domain meaning unless the task explicitly changes it.
- Add or change dependencies only when the current stack cannot reasonably satisfy the requirement.
- Keep external provider payloads behind normalization boundaries.
- Keep credentials in ignored environment files. Never persist or log secrets.
- Treat unknown, stale, contradictory, partial, or failed financial state explicitly. Do not convert uncertainty into success.

## Trading boundaries

`DOMAIN.md` contains the permanent Atlas trading laws.

In particular, do not bypass:

- Strategy/Risk separation;
- immutable StrategyVersion methodology;
- completed-data and no-lookahead requirements;
- Fill-derived exposure;
- explicit market-data provenance;
- fail-closed financial uncertainty;
- broker authority and reconciliation requirements when broker execution exists.

## Validation

Run the smallest relevant checks during development, then the appropriate completion gates for the changed slice.

```bash
uv sync --all-groups
npm ci

uv run alembic upgrade head
uv run alembic current
uv run alembic check

uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend

uv run pytest -m "not integration and not external"
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> uv run pytest -m integration

npm run check:web
npm run test:e2e
```

Integration tests must use a dedicated PostgreSQL test database.

External credentialed checks are separate and must not be treated as ordinary test-suite prerequisites.

## Capital boundary

Code inspection, planning, deterministic tests, mocks, recorded provider-shape tests, migrations, and read-only checks do not authorize capital exposure.

Creating or changing broker credentials, activating PAPER/LIVE, changing Risk policy, submitting capital-capable broker requests, or otherwise changing exposure requires explicit trader authorization.
