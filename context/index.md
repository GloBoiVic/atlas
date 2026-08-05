# Context Index

> Source of truth for project knowledge. Read this first, then load only the docs relevant to your task.
> Last updated: 2026-08-04

## How to use

- Read `AGENTS.md` at the project root first, then this index.
- Load only the docs your task needs — do not bulk-read `context/`.
- Existing docs are authoritative; edits happen through normal project workflows, not initialization.

## Core

- **project-brief.md** — product scope, MVP boundary, goals and non-goals
- **tech-stack.md** — languages, frameworks, key libraries, supported versions
- **architecture.md** — component boundaries, runtime topology, bot lifecycle, trading invariants
- **coding-standards.md** — Python and TypeScript conventions, testing, error handling, commits

## Optional

- **database.md** — PostgreSQL schema, SQLAlchemy ORM patterns, Alembic migrations, data retention
- **design.md** — visual language, interaction patterns, UX principles for the trading dashboard
- **library-docs.md** — project-specific usage patterns for every third-party library
- **roadmap.md** — delivery sequence with feature IDs, phase dependencies
- **ui-registry.md** — component pattern registry for UI consistency
- **ui-tokens.md** — Tailwind utility tokens with `atlas-` prefix
- **vision.md** — product purpose, target audience, long-term direction
- **features/** — 13 vertical-slice feature specifications plus README index

## Missing (reported, not scaffolded)

- **security.md** — trust boundaries, secrets handling, Cloudflare Access auth (recommended for a trading platform with auth and secrets)
- **api-contracts.md** — client/server API boundaries, external broker API interactions (recommended for a full-stack app with client/server and external API boundaries)
- **domain-specific.md** — trading/finance domain knowledge that changes design decisions (recommended given the algorithmic trading domain)
