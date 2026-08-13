# Skills

## Purpose

Skills provide reusable implementation guidance for Atlas coding agents. They improve technical correctness, use of current library documentation, testing quality, debugging discipline, code review quality, and implementation consistency. Skills do not define Atlas product behavior. Atlas context decides what to build. Skills help build it correctly.

## Skill Categories

Atlas uses two categories: workflows/ and technical/.

Workflow Skills: define how an agent approaches a task (vertical-slice, implementation-plan, debugging, code-review, architecture-review, testing, documentation-review). Technology-agnostic where practical.

Technical Skills: focused implementation guidance for technologies or external systems (python, fastapi, pydantic, sqlalchemy, alembic, postgresql, oanda, numpy, polars, pytest, nextjs, react, typescript, tailwind, shadcn, lightweight-charts, playwright). Create only skills that materially improve Atlas work. Do not build large library for technologies Atlas does not use.

## Authority Order

When guidance conflicts: Atlas product context → Atlas architecture context → active feature specification → Atlas coding standards → Atlas agent workflow → workflow skill → technical skill → library/framework convention → agent preference. A skill must never silently override a documented Atlas decision.

Examples:
- Generic trading-system skill recommends "distributed event-driven microservices" but Atlas architecture requires "modular monolith + single long-running atlas-runtime" → Atlas wins.
- Generic SQLAlchemy skill might recommend repository abstraction for every entity but Atlas coding standards say focused repositories only, no generic CRUD → Atlas wins.

## Skill Selection

Use smallest relevant skill set for each task. Do not load every installed skill. Example: historical-data ingestion needs workflows/vertical-slice + workflows/testing + technical/python + technical/oanda + technical/sqlalchemy + technical/postgresql + technical/pytest. No React or Playwright unless UI work included.

## Skill Declaration

Task packets should identify relevant skills explicitly (e.g., Skills: workflows/vertical-slice, workflows/testing, technical/oanda, technical/sqlalchemy). This makes agent behavior reproducible and reduces irrelevant context.

## Up-to-Date Documentation

Technical skills should prefer authoritative current documentation for APIs/libraries that may change (OANDA, FastAPI, SQLAlchemy, PostgreSQL, Next.js, React, Tailwind, Lightweight Charts, Playwright). Do not encode large copies of upstream documentation into Atlas context. Where agent has documentation tools/MCP servers: retrieve current authoritative docs → apply only relevant portion.

## Version Awareness

Technical guidance should match Atlas's selected versions (Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Next.js 16, React 19, Tailwind CSS v4). Do not apply obsolete patterns from earlier major versions.

## Skill Content

A good technical skill focuses on: current API patterns, common correctness pitfalls, Atlas-relevant best practices, testing approach, links/retrieval instructions for authoritative docs. Not a textbook.

## Skill Boundaries

Skills must not decide: Atlas scope, roadmap priority, domain terminology, Strategy behavior, Risk policy, execution semantics, database entities, or UI product requirements. Those belong to project context.

Broker Skills: may teach OANDA authentication, endpoints, candle/order APIs, transaction/fill behavior, client identifiers, error handling, practice vs live differences. Must not decide Atlas Strategy rules, Risk limits, whether Atlas supports spot crypto, Deployment lifecycle, or canonical Order semantics.

Database Skills: may teach modern SQLAlchemy 2 patterns, async sessions, transactions, constraints, indexing, Alembic migrations, PostgreSQL numeric handling. Must not invent Atlas tables beyond documented requirements.

Frontend Skills: may teach App Router conventions, server/client boundaries, forms, accessibility, component composition, Tailwind v4. Must not redesign Atlas into generic SaaS. Shared UX authority: [design.md](../design/design.md).

TradingView Lightweight Charts Skill: focus on candlestick series, markers, lines/overlays, equity curves, drawdown time series, lifecycle/performance. No other chart library unless active feature demonstrates real unsupported requirement.

## Workflow Skills

Vertical-slice reinforces one user capability → minimum domain → persistence → integration → UI where needed → tests → exit criterion. Implementation Plan produces concise plans: goal, context, files, sequence, tests, non-goals. Debugging: reproduce → observe → isolate → root cause → smallest fix → regression. Code Review prioritizes: correctness, safety, architecture compliance, deterministic behavior, failure handling, unnecessary complexity, maintainability. Architecture Review asks: new service? new domain concept? duplicated model? infrastructure without need? weakened parity? violated fail-closed? expanded beyond slice? Testing: deterministic domain tests, integration, failure-path, restart/reconciliation, E2E. Not coverage percentage alone.

## Skill Maintenance

Technical skills may evolve as libraries change. Atlas product/architecture context should remain stable unless an actual decision changes. Library changes → update skill. Atlas product unchanged → no architecture rewrite.

## Local vs Shared Skills

Atlas-specific workflow guidance may live in repo. Generic technical skills may be shared across projects if project-neutral. Do not duplicate the same generic library guidance in multiple context files.

## Skills and Context Size

Skills loaded on demand. A task should not receive all context + all workflow skills + all technical skills by default. Goal is focused context, not maximum context.

## Missing Skill / New Technology

If implementation requires technology without a skill: use authoritative docs, perform task with Atlas context, create reusable skill only if future repeated work justifies it. Do not pause for skill library. A coding agent must not add new dependency/technology merely because a skill exists for it. Technology choices governed by: [tech-stack.md](../architecture/tech-stack.md).

## Skill Quality / Success Criteria

A skill is useful when it reduces errors or unnecessary research. Delete/simplify skills that duplicate Atlas context, restate obvious syntax, encourage unnecessary patterns, are outdated, or consume context without improving implementation. Skills system is working when agent can: identify active task → load governing context → select only relevant skills → retrieve current technical guidance → implement within Atlas boundaries — without generic best practices overriding deliberate Atlas decisions.
