# Local Docker & GitHub Codespaces Development

Atlas supports two development environments:

- **Local Docker Desktop (macOS)** — preferred when available.
- **GitHub Codespaces** — fallback for machines without a local Docker daemon.

Docker Compose is the runtime topology for the API, worker, frontend, and PostgreSQL
services on either platform.

---

## Local Docker Workflow (macOS)

### Prerequisites

- Docker Desktop 4.x+ with one of the resource profiles below (2 CPUs / ~3 GiB minimum).
- macOS 13+ recommended.
- Node.js 20.9+ (for frontend local checks outside the container).

### Resource Profiles

Benchmarked on macOS 13.7.8, Intel i5-7267U, 8 GB RAM:

| Profile | CPUs | Memory | Recommendation |
|---------|------|--------|----------------|
| **A** | 2 | ~2.9 GiB | Safe / conservative default. Sequential builds succeeded; cold API ~286s, cold frontend ~153s. Full stack, PostgreSQL, migrations, repository smoke test, `/health`, and frontend HTTP 200 all passed. A no-cache frontend rebuild while the stack ran also succeeded. |
| **B** | 3 | ~4.06 GiB | Higher headroom, viable for iteration after a clean startup. Cold API ~281s, cold frontend ~177s. Existing containers are recreated after changing Docker Desktop resources — this is expected. |

Do not claim parallel builds are safe on this machine. Docker stats measure post-start
container memory (~245 MiB steady-state for all services), not BuildKit peak memory or
macOS host responsiveness.

### Start Atlas

Run these commands from the repository root:

```bash
test -f .env || cp .env.example .env   # Preserve existing .env — only copy if absent
docker compose build api                # Build one service at a time
docker compose build worker
docker compose build frontend
docker compose up -d                    # Start all services after builds are complete
docker compose exec api alembic upgrade head
docker compose ps
curl http://localhost:8000/health
```

**Do not** use `docker compose up --build` for all services at once. Build `api`, `worker`,
and `frontend` one at a time; then `docker compose up -d`. Use service-specific rebuilds
(`docker compose build api`) instead of blanket builds.

For a no-cache rebuild of a single service while the stack runs:

```bash
docker compose build --no-cache frontend
```

The API and worker images install backend dependencies. The frontend image installs
frontend dependencies. This keeps the local workflow consistent with deployment.

### Logs and Shutdown

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
docker compose down
```

### Local Validation Checks

For source-level checks without Docker, create a repository-local virtual environment:

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

Next.js 16 requires Node.js 20.9 or newer. Confirm the runtime before frontend checks
with `node --version`; the frontend Docker image uses the same minimum runtime. The
frontend lint check invokes ESLint directly because Next.js 16 removed `next lint`.

These local checks validate source code and do not replace service validation. API,
worker, and PostgreSQL integration validation must use the Docker Compose workflow
above.

---

## Codespaces Workflow (Fallback)

### Create a Codespace

1. Open the Atlas repository on GitHub.
2. Select the branch to work on.
3. Choose **Code → Codespaces → Create codespace**.
4. Use the repository's `.devcontainer/devcontainer.json` configuration.

The devcontainer installs the development tools needed to run the environment, but does not
install Atlas's full Python trading stack during creation. That stack includes heavy data
packages such as Pandas and NumPy and is installed inside the API and worker images when
Compose builds them. A new Codespace may take several minutes to build its Docker feature
the first time.

### Start Atlas

```bash
test -f .env || cp .env.example .env   # Safe for first-time setup — does not overwrite
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose ps
curl http://localhost:8000/health
```

Codespaces forwards port `3000` for the frontend and port `8000` for the API. Open the
forwarded frontend port from the **Ports** panel. Keep PostgreSQL port `5432` private.

Atlas defaults to paper mode. Broker credentials are not required for the foundation or
paper development workflow. Never commit `.env` or any credential values.

### Logs and Shutdown

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
docker compose down
```

Stopping the Compose services before stopping the Codespace reduces resource usage. The
PostgreSQL volume belongs to the Codespace and should be treated as disposable development
data. Do not use a Codespace as the production trading runtime.

### Validation Checks

The same source-level checks apply. Create the virtual environment and install
dependencies as shown in the local section above.

### Common Across Both Environments

- The production deployment remains a Docker Compose application on a Linux VPS behind
  Cloudflare Access. Neither local Docker nor Codespaces changes the deployment topology.
- The dependency installs are intentionally manual. They are not part of environment
  creation.
