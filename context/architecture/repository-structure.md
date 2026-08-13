# Repository Structure

## Purpose

Atlas uses a deliberate repository structure so developers and coding agents know where code belongs. Provide clear boundaries without forcing unnecessary abstraction. Organize by responsibility. Do not build architecture for architecture's sake.

## Top-Level Structure

```
atlas/
  AGENTS.md
  README.md
  context/          # product, architecture, design, roadmap, development, features
  skills/           # aspirational — not yet created; current authority: context/development/skills.md
  backend/          # Python import package: backend.*
    __init__.py
    config.py
    logging.py
    api/            # FastAPI HTTP/WebSocket boundaries
      __init__.py
      app.py
      health.py
    persistence/    # PostgreSQL/SQLAlchemy models, repositories, migrations
      __init__.py
      base.py
      database.py
      migrations/
        env.py
        script.py.mako
        versions/
          0001_phase_0_baseline.py
    runtime/        # long-running Deployment coordination, health
      __init__.py
      main.py
    tests/          # Python backend tests; remain in place within the backend/ package
      conftest.py
      test_api_health.py
      test_config.py
      test_runtime.py
      integration/
        test_database.py
        test_migrations.py
  frontend/
  tests/
    e2e/            # cross-application/browser tests
  pyproject.toml
  package.json
  configuration files
```

Do not create new top-level directories without a clear repository-level responsibility.

## Context

All product/architecture context under `context/` with subdirectories: product/, architecture/, design/, development/, roadmap/, features/. Do not create duplicate context documents for concepts that already have an authoritative home.

## Backend Structure

`backend/` with modules:
- **api/** — FastAPI HTTP/WebSocket boundaries. No trading logic in route handlers.
- **domain/** — canonical Atlas domain concepts and invariants. Independent of FastAPI/SQLAlchemy/OANDA/Next.js.
- **strategies/** — Strategy contract implementation, registered implementations, validation, source handling.
- **market_data/** — bars, completed-bar handling, timeframe aggregation, historical/live interfaces, validation.
- **risk/** — centralized Risk Engine (eligibility, budgets, sizing, constraints, RiskDecision creation).
- **execution/** — Order/Fill execution workflows (creation, coordination, protection, Fill processing, idempotent submission). Broker-specific APIs under integrations/.
- **simulation/** — SimulationClock, SimulatedAccount, SimulatedExecutionAdapter. Reuses canonical Strategy/Risk/Order/Fill/Position/Trade.
- **runtime/** — long-running Deployment coordination, market-data coordination, Strategy scheduling, restart, health. Application module, not microservices.
- **persistence/** — PostgreSQL/SQLAlchemy models, repositories, migrations, session.
- **integrations/** — external-system adapters (initial: OANDA). OANDA DTOs must not leak into domain.
- **shared/** — narrow shared exceptions, cross-cutting primitives. Use sparingly; not a dumping ground.

The repository root is `/Users/vike/Desktop/atlas/`, its name remains Atlas, and it is not itself a Python package. The Python import package is `backend/`; the package file is `/Users/vike/Desktop/atlas/backend/__init__.py`. Application imports use the canonical `backend.*` namespace; neither root `atlas.*` nor `backend.atlas.*` is valid.

Backend dependency direction: API → application/domain behavior → Domain; Infrastructure/integrations implement boundaries required by core behavior. Core domain must not import OANDA or FastAPI.

## Frontend Structure

`frontend/` with: **app/** (Next.js App Router, routes, layout), **components/ui/** (shadcn/ui primitives), **components/shared/** (reusable Atlas components), **features/** (feature-specific UI), **lib/api/** (API client), **hooks/**, **tests/**. Use smallest structure appropriate to current implementation. Prefer server/backend-authoritative state, route/server data loading, component-local state, focused hooks. Do not create global state library (Redux, Zustand) without demonstrated need.

## Tests

Backend source is directly under the `backend/` package; backend tests remain under `backend/tests/`. Root `tests/e2e/` remains the cross-application/browser boundary. Tests close to implementation for discoverability: `backend/tests/`, `frontend/tests/` or colocated. E2E under `tests/e2e/`. Do not organize solely around unit/integration labels if feature-oriented grouping is clearer.

## Migrations

Alembic migrations live with persistence under `backend/persistence/migrations/`. One migration history. See [Database](database.md).

## Skills

Current authoritative skills guidance: [context/development/skills.md](../development/skills.md). The aspirational `skills/` directory structure (not yet created) would contain workflows/ and technical/ subdirectories. Skills must not redefine Atlas product or architecture decisions; Atlas context always takes precedence.

## No Premature Directories

Do not create empty/speculative directories for future capabilities (crypto, optimization, ai, notifications, billing, portfolio, microservices, workers). Create when their roadmap slice begins. Structure should reflect software that exists, not software that may exist years later.

## File Naming / Abstraction Rule

Prefer descriptive domain names (risk_engine.py, simulation_clock.py, experiment_results.tsx). Avoid vague names (manager.py, service.py, utils.py) unless responsibility is explicit. Folder boundaries do not justify abstractions by themselves. Do not create AbstractBaseRepository, BaseManager, GenericEngine, AdapterFactoryRegistry unless multiple real implementations demonstrate the need.

## Agent Rule

Before creating a new directory/architectural layer: 1) why existing structure cannot contain the responsibility, 2) whether active roadmap slice requires it, 3) whether change introduces a new architectural concept. If it materially alters this structure, update this document.

## Success Criteria

Working when developer/agent can answer: Where does this code belong? What layer owns this behavior? Is this Atlas domain or external integration logic? Is this directory required by the current slice? — without inventing new organizational patterns during each task.
