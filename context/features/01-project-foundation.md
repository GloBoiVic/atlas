# Feature: 01 — Project Foundation

## Description

Set up the remotely deployable single-user project skeleton: frontend, API, worker, PostgreSQL, tooling, and the Cloudflare-protected access boundary.

## Dependencies

None — this is the first feature.

## Deliverables

- [ ] Project directory structure created
- [ ] Docker Compose: frontend, API, worker, and PostgreSQL services
- [ ] Python backend: FastAPI app with health check endpoint
- [ ] SQLAlchemy: Database connection, base models
- [ ] Alembic: Migration setup, initial migration
- [ ] Next.js frontend: App loads, connects to backend
- [ ] `.env.example` with all required environment variables
- [ ] Deployment documentation for one remote VPS, Cloudflare HTTPS, and Google Access
- [ ] `pyproject.toml` with all Python dependencies
- [ ] `package.json` with all frontend dependencies
- [ ] Linting and type checking configured (ruff, mypy, ESLint, TypeScript)

## Technical Details

The canonical backend and Next.js App Router structure is defined in `context/coding-standards.md`. This feature creates that structure without duplicating it here.

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

- [ ] `docker compose up` starts PostgreSQL, API, worker, and frontend
- [ ] Backend starts and responds to `GET /health`
- [ ] Frontend starts and displays a page
- [ ] `ruff check` passes on backend
- [ ] `mypy` passes on backend
- [ ] `npm run lint` passes on frontend
- [ ] Database migrations run successfully
- [ ] Worker liveness is observable
- [ ] Paper/testnet configuration boundaries are validated

## Done when

All acceptance criteria are met.
