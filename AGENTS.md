# Atlas

Atlas is a single-user algorithmic trading platform. The committed baseline supports
historical EUR/USD research with an emphasis on correctness, reproducibility, capital
safety, simplicity, and auditability.

## Permanent surface and authority

## Permanent surface and authority

- `AGENTS.md` routes work; `README.md` owns setup, usage, and validation commands.
- `DOMAIN.md` owns durable, cross-cutting trading laws.
- Desired change → approved current task/workstream.
- Current implementation behavior → code, nearby tests, schemas/migrations, and
  generated contracts.
- Cross-cutting trading semantics → `DOMAIN.md`.
- Setup/run/current supported workflow → `README.md`.
- Historical reasoning → closed dispatch workstreams/Git only when explicitly
  needed.
- Dispatch history records what happened. Do not treat historical records as
  current capability or silently broaden an approved task when sources disagree.

## Progressive loading

Read only the implementation, tests, schema/migrations, and domain rules relevant to
the slice being changed. Follow active workstream artifacts under `dispatch/` when a
task requires them; do not bulk-load historical records or invent a replacement
documentation hierarchy.

## Current repository

- `backend/` is the Python package: FastAPI API, domain values, market-data loading,
  historical Experiments, simulated execution, Risk, persistence, and runtime check.
- `frontend/` is the Next.js application. `tests/e2e/` contains Playwright coverage.
- `backend/persistence/migrations/` contains Alembic history; PostgreSQL is durable
  application state.
- `backend/integrations/oanda/` is the read-only OANDA Practice historical adapter.

## Supported boundary

The current workflow is OANDA Practice historical data → immutable DatasetSnapshot →
deterministic historical Experiment → inspectable results and Trades. The primary
Strategy is EMA Sweep Confirmation Break v2, using native M15 MID analysis and sparse
native M1 BID/ASK execution observations. PAPER/LIVE broker execution, reconciliation,
and live protection are not committed-main capabilities.

## Boundaries and safety

- Use Strategy, StrategyVersion, Experiment, DatasetSnapshot, TradeIntent, RiskDecision,
  Order, Fill, Position, and Trade. A historical backtest is an Experiment.
- Strategy is pure: it proposes setup, direction, stop, target methodology, and
  rationale; it does not access persistence, accounts, brokers, Risk, or UI.
- Risk is centralized; financial exposure is represented by Fill-derived Position
  state. Immutable StrategyVersion and completed Experiment facts remain immutable.
- Use UTC, completed candles, half-open periods, no lookahead, and one evaluation per
  completed frontier. Never fabricate, interpolate, aggregate in place of, or silently
  substitute a required market observation.
- Unknown, stale, contradictory, or failed state must remain visible and fail closed;
  never turn uncertainty into a successful order, fill, or result.

## Engineering workflow

Choose the narrowest complete slice, inspect affected callers and contracts, implement
explicitly, test success and failure paths, and report evidence. Avoid speculative
brokers, workers, messaging, plugins, or generalization. Keep credentials in ignored
environment files and never log them.

## Commands

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

Run the API with `uv run uvicorn backend.api.app:create_app --factory --host
127.0.0.1 --port 8000 --no-proxy-headers --reload`; run the frontend with
`npm run dev:web`. `uv run atlas-runtime --check` is the optional database readiness
check; it is not a historical Experiment worker.
