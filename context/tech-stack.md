# Atlas — Tech Stack

## Overview

Atlas uses Python for the backend trading system and TypeScript/React for the frontend dashboard. The stack is chosen for simplicity, maintainability, and strong ecosystem support for both trading and web development.

---

## Backend

### Core Language: Python

Python is the standard language for algorithmic trading. The trading, data analysis, and backtesting ecosystem is centered on Python.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Python | 3.12+ | Latest stable, modern async support, performance improvements, type hint maturity |

### API Framework: FastAPI

FastAPI provides async API endpoints, WebSocket support, automatic OpenAPI docs, and Pydantic integration for data validation.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| FastAPI | `>=0.115,<1` (manifest range) | Async-first, WebSocket support, Pydantic v2 integration |
| Uvicorn | `>=0.34,<1` (manifest range) | ASGI server for FastAPI |

**Alternatives considered:**
- Flask — no native async or WebSocket support
- Django — heavier, more opinionated, slower iteration

### Database: PostgreSQL + SQLAlchemy

PostgreSQL for persistent storage. SQLAlchemy as the ORM for type-safe database access. Alembic for schema migrations.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| PostgreSQL | 15+ | Reliable, concurrent access, production-ready |
| SQLAlchemy | `>=2.0,<3` (manifest range) | Modern async support, type-safe queries, ORM + Core |
| Alembic | `>=1.14,<2` (manifest range) | Schema versioning and migrations |
| asyncpg | `>=0.30,<1` (manifest range) | Async PostgreSQL driver for SQLAlchemy |

**Alternatives considered:**
- SQLite — no concurrent access, not production-ready
- MongoDB — we use PostgreSQL for trades; MongoDB can be added later for scraped data if needed

### Data Analysis: Pandas + NumPy

Pandas is the standard for time-series data manipulation in Python. NumPy for numerical computations. Used in both research (Jupyter) and production (Strategy Engine).

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Pandas | `>=2.2,<4` (manifest range) | Time-series data, OHLC manipulation, rolling calculations |
| NumPy | `>=1.26,<3` (manifest range) | Numerical operations, array computations |

### Crypto Exchange API: ccxt

Unified interface to 100+ cryptocurrency exchanges. Handles authentication, rate limits, order placement, and data fetching.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| ccxt | `>=4,<5` (manifest range) | Unified API for Binance, Coinbase, and 100+ exchanges |

### Deferred Forex API: Oanda v20 API

Oanda's REST API for future forex data and trading. It is not an MVP integration.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| httpx | `>=0.28,<1` (manifest range) | Async HTTP client for future HTTP-based adapters |

**Alternatives considered:**
- oandapyV20 — unmaintained, we can wrap the API directly with more control

### WebSocket: websockets

For live data feeds (Binance Spot WebSocket first; Oanda deferred).

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| websockets | `>=14,<18` (manifest range) | Async WebSocket client for live data feeds |

### Configuration: Pydantic Settings + dotenv

Pydantic for typed configuration. dotenv for environment variables (API keys, database URLs).

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| pydantic-settings | `>=2.6,<3` (manifest range) | Typed settings with validation |
| python-dotenv | `>=1,<2` (manifest range) | Load environment variables from .env files |

### Logging: structlog

Structured logging for debugging and error tracking. Better than stdlib logging for production systems.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| structlog | `>=24,<27` (manifest range) | Structured logging, better than stdlib for production |

**Alternatives considered:**
- stdlib logging — works but unstructured, harder to query

### Testing

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| pytest | `>=8,<9` (manifest range) | Standard Python test framework |
| pytest-asyncio | `>=0.24,<0.27` (manifest range) | Async test support |
| pytest-cov | `>=6,<8` (manifest range) | Coverage reporting |

### Linting / Type Checking

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| ruff | `>=0.8,<1` (manifest range) | Fast Python linter and formatter (replaces flake8, isort, black) |
| mypy | `>=1.13,<2` (manifest range) | Static type checking |

---

## Frontend

### Framework: Next.js + React

Next.js for server-side rendering, file-based routing, and API routes. React for component-based UI.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Next.js | `^15.0.0` (manifest range) | React framework with SSR, routing, API routes |
| React | `^19.0.0` (manifest range) | Component-based UI |
| Node.js | 20+ | Runtime for Next.js |

### Language: TypeScript

Type safety for frontend code. Catches errors at compile time, improves maintainability.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| TypeScript | `^5.7.0` (manifest range) | Type safety, better DX, fewer runtime errors |

### UI Components: Shadcn/ui

Copy-paste React components built with Radix UI and Tailwind CSS. No dependency lock-in — components live in your codebase.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| shadcn/ui | latest | Accessible, customizable, no dependency lock-in |
| Radix UI | Managed by selected Shadcn components | Headless UI primitives (used by shadcn/ui) |

**Alternatives considered:**
- Material UI — heavier, more opinionated styling
- Chakra UI — less control over styling
- Headless UI — fewer pre-built components

### Styling: Tailwind CSS

Utility-first CSS framework. Pairs with Shadcn/ui.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Tailwind CSS | `^4.0.0` (manifest range) | Utility-first CSS, pairs with shadcn/ui |

### Charts: TradingView Lightweight Charts

Free, open-source financial charting library. Lightweight (35KB), fast, and purpose-built for financial data.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| lightweight-charts | Not yet declared | Free, open-source financial charting library when added |

**Alternatives considered:**
- Plotly.js — heavier (3MB+), not financial-specific
- Highcharts Stock — commercial license required
- TradingView Advanced Charts — proprietary, not available for personal use

### State Management: React Query (TanStack Query)

Server state management for API data fetching, caching, and real-time updates.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| @tanstack/react-query | `^5.60.0` (manifest range) | Server state management, caching, WebSocket integration |

### HTTP Client: Axios

For REST API calls from the frontend.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| axios | `^1.7.0` (manifest range) | HTTP client with interceptors, error handling |

### Toast Notifications: Sonner

Lightweight, accessible toast notifications.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| sonner | latest | Simple API, accessible, no config needed |

### WebSocket Client

Native browser WebSocket API — no library needed for basic WebSocket communication.

---

## Infrastructure

### Containerization: Docker Compose

For GitHub Codespaces development and the single-user remote deployment. The frontend, API,
worker, and PostgreSQL run as separate containers. Codespaces supplies the Linux container
runtime; Docker Desktop is not required for Atlas development.

Codespace creation intentionally avoids installing the full application dependency trees.
Compose image builds install each service's runtime dependencies so development and remote
deployment use the same packaging path.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Docker Engine | 24+ | Container runtime supplied by Codespaces or Linux VPS |
| Docker Compose | 2.24+ | Multi-container orchestration |

Development setup is documented in `docs/codespaces.md`. Local macOS Docker Desktop is not
required and may be unavailable on older macOS versions.

### Remote Access: Cloudflare

The remote deployment uses Cloudflare DNS, HTTPS, and Access with Google authentication. Atlas does not implement password authentication for the MVP. Broker credentials remain server-side environment secrets.

### Database Migrations: Alembic

Schema versioning and migrations for PostgreSQL.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Alembic | `>=1.14,<2` (manifest range) | SQLAlchemy migration tool |

---

## Research

### Jupyter Notebooks

For strategy exploration, data analysis, and indicator development. Uses the same Pandas library as production code — seamless transition from research to production.

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Jupyter | 1.1.1 | Interactive notebooks for research |
| ipykernel | 6.29+ | Jupyter kernel for Python |

### Visualization (Research)

| Requirement | Version | Rationale |
|-------------|---------|-----------|
| Plotly | 6.9.0 | Interactive charts in Jupyter notebooks |
| matplotlib | 3.11.1 | Static charts (optional, Plotly preferred) |

---

## Summary

### Backend Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| API | FastAPI `>=0.115,<1` + Uvicorn `>=0.34,<1` |
| Database | PostgreSQL 15+ |
| ORM | SQLAlchemy `>=2.0,<3` |
| Migrations | Alembic `>=1.14,<2` |
| Data Analysis | Pandas `>=2.2,<4` + NumPy `>=1.26,<3` |
| Crypto API | ccxt `>=4,<5` |
| Forex API | httpx `>=0.28,<1` (Oanda deferred) |
| WebSocket | websockets `>=14,<18` |
| Configuration | pydantic-settings `>=2.6,<3` + python-dotenv `>=1,<2` |
| Logging | structlog `>=24,<27` |
| Testing | pytest `>=8,<9` + pytest-asyncio `>=0.24,<0.27` |
| Linting | ruff `>=0.8,<1` + mypy `>=1.13,<2` |

### Frontend Stack

| Layer | Technology |
|-------|------------|
| Framework | Next.js `^15.0.0` |
| Language | TypeScript `^5.7.0` |
| UI Components | Shadcn/ui + selected Radix components |
| Styling | Tailwind CSS `^4.0.0` |
| Charts | Not yet declared |
| State Management | TanStack React Query `^5.60.0` |
| HTTP Client | Axios `^1.7.0` |

### Infrastructure

| Layer | Technology |
|-------|------------|
| Containers | Docker + Docker Compose |
| Database Migrations | Alembic |

### Research

| Layer | Technology |
|-------|------------|
| Notebooks | Jupyter |
| Visualization | Plotly |

---

## Principles

Version values in this document are declaration ranges from the project manifests, not
installed versions. Atlas currently has no committed Python or frontend lockfile. When a
dependency is added or upgraded, update the manifest, generate the appropriate lockfile,
and verify version-sensitive API guidance against the official documentation for the
resolved version.

1. **No dependency lock-in.** Prefer libraries that are open-source, well-maintained, and don't lock you into a specific ecosystem.
2. **Minimal dependencies.** Don't add a library if the standard library or existing dependency already solves the problem.
3. **Same libraries in research and production.** Pandas is used in Jupyter notebooks and in the Strategy Engine. No translation layer needed.
4. **Simple infrastructure.** Docker Compose on one VPS. No Kubernetes or managed application infrastructure for MVP; Cloudflare is used only for DNS, HTTPS, and Access.
5. **Type safety everywhere.** Python type hints + mypy on backend. TypeScript on frontend.
