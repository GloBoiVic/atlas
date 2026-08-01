# Memory — Atlas Codespaces Development Setup

Last updated: 2026-08-01

## What was built

- Added `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile` for GitHub Codespaces with Python 3.12, Node 20, Docker-outside-of-Docker, forwarded ports, and VS Code extensions.
- Removed the Codespaces `postCreateCommand` that installed the full Python and frontend dependency trees.
- Updated `Dockerfile.api` and `Dockerfile.worker` so the `backend` package is copied before editable installation.
- Added setuptools package discovery to `pyproject.toml`.
- Updated Alembic to read the configured synchronous database URL instead of relying on `localhost` in `alembic.ini`.
- Made `NEXT_PUBLIC_API_URL` configurable for Codespaces/browser access.
- Added `docs/codespaces.md` and updated `AGENTS.md`, `CURRENT.md`, `context/tech-stack.md`, `context/features/01-project-foundation.md`, and `docs/deployment.md` to document Codespaces as the supported development environment.

## Decisions made

- GitHub Codespaces is the supported development environment; Docker Desktop on the Mac is not required.
- Docker Compose remains the runtime topology for API, worker, frontend, and PostgreSQL in Codespaces and Linux VPS deployment.
- Codespace creation must stay lightweight. Heavy packages such as Pandas and NumPy are installed during application image builds, not automatically in `postCreateCommand`.
- The Codespaces devcontainer uses a custom base Dockerfile to remove a stale Yarn apt source before Docker feature installation.
- Use `docker-outside-of-docker` instead of `docker-in-docker` for Codespaces — mounts host Docker socket instead of running a nested daemon.
- FastAPI remains the canonical trading API and the existing Atlas architecture boundaries remain unchanged.
- Alembic runs synchronous migrations requiring `psycopg2-binary` alongside the async `asyncpg` driver.

## Problems solved

- Fixed `ModuleNotFoundError: No module named 'backend'` during Alembic execution by correcting Python package installation order and package discovery.
- Fixed the container database hostname problem by making Alembic use settings instead of the `localhost` URL in `alembic.ini`.
- Fixed the initial Codespaces creation failure caused by the Docker feature encountering an invalid Yarn repository signing key.
- Fixed Codespaces post-create failure with exit code 137 by removing automatic installation of the full dependency tree.
- Fixed Codespaces recovery mode by replacing `docker-in-docker` with `docker-outside-of-docker`.
- Fixed Codespace recovery mode caused by `overrideCommand: false` — container exited because no long-running command was specified; default `overrideCommand: true` lets Codespaces inject a keep-alive command.
- Fixed `ModuleNotFoundError: No module named 'psycopg2'` by adding `psycopg2-binary` to `pyproject.toml` dependencies for Alembic sync migrations.

## Current state

- All changes committed and pushed to `main` at commit `3517dfc`.
- Local backend validation passes: Ruff, mypy, and 19 tests.
- Codespace is operational: all 4 containers (API, worker, frontend, postgres) run successfully.
- API health check returns `{"status":"ok"}`.
- Alembic migration has not yet been verified after the psycopg2 fix — user needs to run `docker compose build api && docker compose exec api alembic upgrade head` in the Codespace.

## Next session starts with

1. Verify Alembic migration works: `docker compose build api && docker compose exec api alembic upgrade head`
2. Check `https://github.com/codespaces` and determine whether the Atlas Codespace is Running, Stopped, or Unavailable.
3. If unavailable, rebuild the container using the VS Code command palette "Rebuild Container".

## Open questions

- Whether `feature/01-codespaces-hardening` branch should be deleted after Codespaces is verified; `main` already contains the same commit.
