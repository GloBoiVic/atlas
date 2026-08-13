# Tech Stack

## Purpose

This document defines the approved Atlas technology stack. Do not substitute major technologies during implementation without first changing Atlas architecture context. Use current official documentation and relevant technical skills for version-specific implementation details.

## Frontend

**Stack**: Next.js 16, React 19, TypeScript strict, Tailwind CSS v4, shadcn/ui, Lucide React, Sonner, TradingView Lightweight Charts, npm.

**Responsibilities**: Next.js/React — application UI, App Router, server/client composition, API consumption, user commands/queries. Tailwind/shadcn — shared design system, accessible UI primitives, workstation layout. TradingView Lightweight Charts — candlesticks, trade visualization, equity curves, drawdown/time-series. Sonner — transient user feedback only; persistent safety failures belong in normal UI.

**Testing**: Vitest, React Testing Library, Playwright (E2E).

## Backend

**Stack**: Python 3.13, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2, Alembic, psycopg 3, PostgreSQL, NumPy, Polars, uv.

**FastAPI**: REST/JSON APIs, WebSocket endpoints where justified, request validation, OpenAPI generation. Trading execution belongs to atlas-runtime, not FastAPI handlers.
**Pydantic v2**: API schemas, external/config validation, typed boundaries. Not universal domain/persistence representation.
**SQLAlchemy 2**: PostgreSQL persistence. Modern typed patterns, async I/O where appropriate. Do not use SQLModel or generic ORM framework.
**Alembic**: All schema migrations. No runtime auto-create as production strategy.
**PostgreSQL**: Sole initial operational persistence layer.
**NumPy**: Efficient numerical operations where helpful. Not merely to avoid straightforward Python.
**Polars**: Tabular market-data/research operations. Do not make Strategy depend on large mutable DataFrames as persistent state.
**uv**: Python dependency/environment management. Explicit and reproducible declarations.

**Testing**: pytest, pytest-asyncio. Prioritize deterministic domain tests, integration, failure-path, restart/reconciliation. Not primarily coverage percentage.

## Broker / Market Data

Initial: OANDA, Forex, EUR/USD. Use official/current OANDA API documentation. OANDA-specific code inside integration adapters.

## API Contract

Python/Pydantic owns the API contract. Where practical: FastAPI OpenAPI → generated TypeScript types. Avoid maintaining duplicate handwritten API contracts.

## Real-Time Communication

REST/JSON for normal commands/queries. WebSockets only when genuinely useful for live state. Polling acceptable where simpler. No additional messaging infrastructure for frontend updates.

## Runtime

Long-running Python process `atlas-runtime` in same backend codebase as API, separate process role. Do not introduce Celery, Dramatiq, Redis workers, Kafka consumers, or actor frameworks for the initial runtime.

## Development Environment

Docker optional. Atlas development must not require Docker. Expected local processes: Next.js, FastAPI, atlas-runtime, PostgreSQL. Docker may later package for deployment convenience.

## Explicitly Not Selected

SQLModel, Prisma, Redis, Celery, Dramatiq, Kafka, RabbitMQ, TimescaleDB, ClickHouse, InfluxDB, Kubernetes, Redux, Zustand, Recharts, CQRS, event sourcing, microservices. A future roadmap requirement may change this, but implementation agents must not add them opportunistically.

## Dependency Rule

Before adding: 1) active slice needs it, 2) existing stack cannot solve it, 3) no duplication, 4) no accidental new architectural pattern. Prefer standard library or existing dependencies.

## Version Guidance

Versions define intended major-version family. Technical skills and official docs determine current minor-version APIs. Do not copy outdated patterns from Pydantic v1, SQLAlchemy 1.x, older Next.js routing, older Tailwind config, obsolete React patterns.

## Technology Authority

Technology choices: this document. Implementation details: [coding-standards.md](../development/coding-standards.md). Skill guidance: [skills.md](../development/skills.md). Product behavior: feature and architecture context. Sources are not interchangeable.

## Success Criteria

Stack is working when Atlas can reach the Golden Path using these technologies without adding infrastructure merely to compensate for poor scope discipline.
