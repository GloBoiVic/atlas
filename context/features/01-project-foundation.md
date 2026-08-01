# Feature: 01 — Project Foundation

## Description

Set up the remotely deployable single-user project skeleton: frontend, API, worker, PostgreSQL, tooling, and the Cloudflare-protected access boundary.

## Dependencies

None — this is the first feature.

## Deliverables

- [x] Project directory structure created
- [x] Docker Compose: frontend, API, worker, and PostgreSQL services
- [x] Python backend: FastAPI app with health check endpoint
- [x] SQLAlchemy: Database connection, base models
- [x] Alembic: Migration setup, initial migration
- [x] Next.js frontend: App loads, connects to backend
- [x] `.env.example` with all required environment variables
- [x] Deployment documentation for one remote VPS, Cloudflare HTTPS, and Google Access
- [x] `pyproject.toml` with all Python dependencies
- [x] `package.json` with all frontend dependencies
- [x] Linting and type checking configured (ruff, mypy, ESLint, TypeScript)

## Technical Details

The canonical backend and Next.js App Router structure is defined in `context/coding-standards.md`. This feature creates that structure without duplicating it here.

Development runs in GitHub Codespaces using the checked-in `.devcontainer/devcontainer.json`.
Codespace creation does not install the full Python or frontend dependency trees; Compose
installs them inside the API, worker, and frontend images. Production-style deployment runs
the same Compose topology on a Linux VPS. Docker Desktop on the developer's host is not a
project prerequisite.

### Docker Compose

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: atlas
      POSTGRES_USER: atlas
      POSTGRES_PASSWORD: atlas
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    # FastAPI HTTP and WebSocket API
    ...

  worker:
    # BotSupervisor and background trading runtime
    ...

  frontend:
    # Next.js operational UI
    ...
```

### Backend Health Check

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Environment Variables

```
DATABASE_URL=postgresql+asyncpg://atlas:atlas@localhost:5432/atlas
BINANCE_API_KEY=
BINANCE_API_SECRET=
ATLAS_ENVIRONMENT=paper
STRATEGY_REPOSITORY_PATH=/opt/atlas/strategies
```

Cloudflare Access with Google authentication protects the deployed application. Atlas does not implement passwords or store broker credentials in PostgreSQL. Paper mode must reject testnet/production credentials and endpoints.

## Acceptance Criteria

- [x] `docker compose up` starts PostgreSQL, API, worker, and frontend
- [x] Backend starts and responds to `GET /health`
- [x] Frontend starts and displays a page
- [x] `ruff check` passes on backend
- [x] `mypy` passes on backend
- [x] `npm run lint` passes on frontend
- [x] Database migrations run successfully
- [x] Worker liveness is observable
- [x] Paper/testnet configuration boundaries are validated

## Done when

All acceptance criteria are met.
