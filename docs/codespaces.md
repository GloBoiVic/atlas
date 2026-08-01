# GitHub Codespaces Development

GitHub Codespaces is Atlas's supported development environment. It provides a Linux
container, Python, Node.js, and Docker so the Mac host does not need Docker Desktop,
Colima, or a local Docker daemon.

## Create a Codespace

1. Open the Atlas repository on GitHub.
2. Select the branch to work on.
3. Choose **Code → Codespaces → Create codespace**.
4. Use the repository's `.devcontainer/devcontainer.json` configuration.

The devcontainer installs Python development dependencies and frontend dependencies after
the Codespace is created. A new Codespace may take several minutes to build its Docker
feature the first time.

## Start Atlas

Run these commands from the repository root in the Codespace terminal:

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose ps
curl http://localhost:8000/health
```

Codespaces forwards port `3000` for the frontend and port `8000` for the API. Open the
forwarded frontend port from the **Ports** panel. Keep PostgreSQL port `5432` private.

Atlas defaults to paper mode. Broker credentials are not required for the foundation or
paper development workflow. Never commit `.env` or any credential values.

## Logs and Shutdown

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
docker compose down
```

Stopping the Compose services before stopping the Codespace reduces resource usage. The
PostgreSQL volume belongs to the Codespace and should be treated as disposable development
data. Do not use a Codespace as the production trading runtime.

## Validation

```bash
python -m ruff check .
python -m mypy backend/
python -m pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
```

The production deployment remains a Docker Compose application on a Linux VPS behind
Cloudflare Access. Codespaces changes development setup only.
