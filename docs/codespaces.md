# GitHub Codespaces Development

GitHub Codespaces is Atlas's supported development environment. It provides a Linux
container, Python, Node.js, and Docker so the Mac host does not need Docker Desktop,
Colima, or a local Docker daemon.

## Create a Codespace

1. Open the Atlas repository on GitHub.
2. Select the branch to work on.
3. Choose **Code → Codespaces → Create codespace**.
4. Use the repository's `.devcontainer/devcontainer.json` configuration.

The devcontainer installs the development tools needed to run the environment, but does not
install Atlas's full Python trading stack during creation. That stack includes heavy data
packages such as Pandas and NumPy and is installed inside the API and worker images when
Compose builds them. A new Codespace may take several minutes to build its Docker feature
the first time.

## Start Atlas

Run these commands from the repository root in the Codespace terminal:

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose ps
curl http://localhost:8000/health
```

The API and worker images install backend dependencies. The frontend image installs
frontend dependencies. This keeps Codespace creation within the memory limit and ensures
the runtime uses the same dependency setup as deployment.

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

## Local Validation Checks

The application dependency trees are not installed during Codespace creation. For local
backend checks, create and activate a repository-local virtual environment, then install the
development extras:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Install the frontend from the committed lockfile:

```bash
npm --prefix frontend ci
```

Run the non-Docker checks:

```bash
python -m ruff check .
python -m mypy backend/
python -m pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
```

These local checks validate source code and do not replace service validation. API, worker, and
PostgreSQL integration validation must use the Docker Compose workflow above:

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose ps
curl http://localhost:8000/health
```

The dependency installs are intentionally manual. They are not part of Codespace creation.

The production deployment remains a Docker Compose application on a Linux VPS behind
Cloudflare Access. Codespaces changes development setup only.
