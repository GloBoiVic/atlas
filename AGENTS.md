# Atlas — Coding Agent Guide

Atlas is an opinionated, strategy-first algorithmic trading platform. Python backend (FastAPI, PostgreSQL), TypeScript frontend (Next.js, Shadcn/ui). The same strategy and risk contracts run across backtesting and paper trading.

## Before Writing Code

Read these files in order:

1. `context/project-brief.md` — product scope and MVP boundary
2. `context/architecture.md` — component boundaries and runtime invariants
3. `context/tech-stack.md` — exact dependency versions
4. `context/coding-standards.md` — Python and TypeScript conventions
5. `context/library-docs.md` — project-specific library patterns
6. `context/features/<current-feature>.md` — deliverables and acceptance criteria

When the work touches a covered library, also read the relevant local skill under
`.agents/skills/`:

| Area | Skill |
|------|-------|
| FastAPI, Pydantic, streaming, routing | `.agents/skills/fastapi/SKILL.md` |
| FastAPI dependency injection | `.agents/skills/fastapi-dependency-injection/SKILL.md` |
| SQLAlchemy and Alembic | `.agents/skills/sqlalchemy-orm/SKILL.md` |
| Async I/O and worker tasks | `.agents/skills/asyncio/SKILL.md` |
| Next.js App Router | `.agents/skills/nextjs-core/SKILL.md` |
| Tailwind CSS | `.agents/skills/tailwind-css/SKILL.md` |

The authority order is:

1. Security, product, and architecture invariants.
2. Feature acceptance criteria.
3. Actual dependency manifests and lockfiles.
4. Official documentation for the resolved dependency versions.
5. Project-specific guidance in `context/library-docs.md` and `context/coding-standards.md`.
6. Local agent skills under `.agents/skills/`.
7. General training knowledge.

Local skills are reference material, not an authority over Atlas architecture or verified
library documentation. If a skill conflicts with Atlas context or the resolved library
version, follow the higher authority and update the project guidance when the decision is
intentional.

For version-sensitive API work:

1. Identify the declared and resolved dependency version.
2. Read the relevant local skill and its referenced material.
3. Verify the pattern against the official documentation or changelog for that version.
4. Check that it preserves Atlas boundaries, especially repository ownership, bot isolation,
   deterministic backtesting, and the FastAPI-to-frontend API boundary.
5. Run the relevant lint, type, test, and build commands.

These context files are the source of truth for project decisions. Do not rely on general
knowledge when a project-specific document covers the decision.

## Development Rules

1. Create a branch named `feature/XX-feature-name` before implementation.
2. Update `CURRENT.md` at the start and end of each session.
3. Implement one vertical slice at a time; do not build ahead.
4. Plan before coding and surface major architectural choices for approval.
5. Write tests with every feature. Risk and execution require comprehensive coverage.
6. Run backend `ruff check`, `mypy`, and tests. Run frontend linting, type checking, and tests.
7. Mark completed deliverables in the current feature file.
8. Update affected context documentation when a library pattern or architectural decision changes.

## Product Constraints

- Single-user remote deployment; not multi-tenant SaaS for the MVP.
- One Docker Compose deployment with frontend, API, worker, and PostgreSQL.
- Cloudflare Access with Google authentication; Atlas does not implement passwords.
- Binance Spot is the first concrete integration. Keep interfaces broker-agnostic.
- Paper trading on Binance public data comes before Binance testnet execution.
- Strategy packages are version-pinned private Git deployments.
- Multiple bots run as isolated pipelines in one worker process.
- One net position per account and instrument in the MVP.
- No AI features, social features, distributed messaging, or advanced optimization in the MVP.
- No hardcoded secrets. Broker credentials stay in server environment secrets.
- No `float` for backend money, prices, quantities, fees, or P&L. Use `Decimal`.
- No blocking I/O in async code.
- No custom toast libraries. Use `sonner`.

## Architecture Reference

`context/architecture.md` owns component boundaries, runtime topology, EventBus semantics, bot lifecycle, trading invariants, and safety rules.

Other source-of-truth files:

- `context/project-brief.md` — product purpose and scope
- `context/roadmap.md` — delivery sequence
- `context/database.md` — persistence schema and relationships
- `context/tech-stack.md` — dependencies and infrastructure
- `context/coding-standards.md` — code structure and conventions
- `context/library-docs.md` — library-specific integration patterns
- `context/design.md` — UI navigation and behavior
- `context/features/` — slice deliverables and acceptance criteria
- `CURRENT.md` — current feature and session state
