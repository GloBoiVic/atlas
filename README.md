# Atlas Phase 0

Foundation only: Next.js, FastAPI, synchronous SQLAlchemy/PostgreSQL, Alembic baseline, and `atlas-runtime`; no trading functionality.

Prerequisites: Python 3.13, `uv`, Node.js 22 LTS/npm, and PostgreSQL. Create `atlas` and `atlas_test`, copy `.env.example` to `.env`, and replace credentials.

```bash
uv sync --all-groups
npm install
npm ci
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Python application source and backend tests live directly under the `backend/` Python package. Run `npm run dev:web`, `uv run uvicorn backend.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload`, and `uv run atlas-runtime` separately. Use `uv run atlas-runtime --check` for one-shot readiness. Liveness is process-only; readiness checks PostgreSQL and returns sanitized 503 when unavailable.

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration"
ATLAS_TEST_DATABASE_URL="postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test" uv run pytest -m integration
npm run check:web
npx playwright install chromium
npm run test:e2e
```
