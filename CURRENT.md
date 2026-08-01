# Current Feature

Last updated: 2026-07-31

## Status

- [ ] Not started
- [ ] In progress
- [x] Complete

## Feature

- **Number:** 01
- **Name:** Project Foundation — Codespaces hardening
- **File:** context/features/01-project-foundation.md

## Branch

- **Name:** feature/01-codespaces-hardening
- **Created:** 2026-07-31

## What was built

- Backend directory structure with FastAPI app, health check, config, EventBus, error types, structured logging, SQLAlchemy + PostgreSQL, and Alembic migrations
- Worker entrypoint with graceful shutdown
- Frontend Next.js app with landing page, dashboard placeholder, Tailwind CSS, and API client
- Docker Compose: PostgreSQL, API, worker, and frontend services
- pyproject.toml with all Python dependencies (FastAPI, SQLAlchemy, ccxt, pandas, structlog, ruff, mypy)
- package.json with frontend dependencies (Next.js, React, TanStack Query, Axios, Sonner, Tailwind)
- 19 passing tests (API health, config, errors, events, models)
- ruff check and mypy pass clean
- Deployment documentation, .env.example, .gitignore, .dockerignore
- GitHub Codespaces devcontainer with Python, Node.js, Docker, forwarded ports, and setup commands
- Container package discovery and Alembic configuration fixed for Compose service networking
- Frontend API URL made configurable at image build time for Codespaces/browser access

## What comes next

Feature 02 — Core Infrastructure: EventBus persistence, config validation, structured logging verification.

## Notes

Codespaces hardening is complete on `feature/01-codespaces-hardening`. Docker/Compose
verification must run inside the Codespace because Docker is unavailable on the Mac host.
