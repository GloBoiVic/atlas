# Memory — Atlas Feature 03 Session

Last updated: 2026-08-02

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

- **Feature 02 (Core Infrastructure) is complete**, including the supervisor slice and
  the lease/worker-ownership removal (commit `8b735ec`). 47/47 targeted tests pass.
  Health monitor and Docker/Compose/PostgreSQL validation remain deferred.
- **Feature 03 (Data Layer) branch `feature/03-data-layer` created** from `main`
  (2026-08-02). `CURRENT.md` updated to Feature 03. No implementation yet.
- **Dispatch folder consolidated**: `.dispatch/ledger.md` renamed to
  `.dispatch/COMPLETED.md` and updated; 32 one-off task brief/report files deleted
  (recoverable from git). `.dispatch/` is gitignored for future artifacts.
- **Environment workflow locked in**: develop locally with `.venv` (no Docker, no local
  PostgreSQL). One Codespace on `main`; validate pushed feature branches by checking
  them out inside that Codespace and running the Compose workflow, then return to `main`.
- All earlier codespaces work (from the previous session) is committed and pushed to
  `main`; the Codespace runs all 4 containers and the API health check returns ok.
- Alembic migration had not yet been re-verified after the psycopg2 fix in the
  previous session — covered by the Codespace validation workflow above.

## Next session starts with

1. Confirm `.dispatch/COMPLETED.md` and `CURRENT.md` are committed on
   `feature/03-data-layer` (branch setup commit).
2. Start Feature 03 implementation: DataProvider interface, Candle/Tick/Instrument
   models, `005` migration for `candles` and `instruments`, CSV provider, historical
   loader, storage pipeline, Binance provider (ccxt), provider registry.
3. Local checks: `.venv/bin/python -m ruff check .`, `mypy backend`, bounded pytest.
4. When the slice is pushed, validate in the single Codespace: checkout the branch,
   `docker compose up --build -d`, `alembic upgrade head`, health check, then return
   to `main`.

## Open questions

- Whether the old `feature/02-*` and `chore/*` branches should be deleted after their
  work is fully merged/verified (the previous session asked the same about
  `feature/01-codespaces-hardening`).
