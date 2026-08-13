# Agent Workflow

## Purpose

Atlas is implemented through small, testable vertical slices. The agent's job is to complete the active roadmap slice with the smallest correct implementation — not to "complete the architecture."

## Core Rule

Before writing code: 1) What exact roadmap slice is active? 2) What user-visible behavior must work? 3) Which context files govern? 4) Which skills are relevant? 5) What must not be built yet? If unclear, inspect context before implementing. Do not fill gaps with speculative architecture.

## Context Precedence

See [skills.md#authority-order](skills.md#authority-order). Skills provide guidance; they do not override Atlas decisions.

## Context Loading

Do not load every context file for every task. Always start with: AGENTS.md, context/roadmap/roadmap.md. Then: active feature spec, only governing architecture files, relevant coding standards, relevant technical skills.

## Example Contexts

- **Historical Data**: AGENTS.md + roadmap Phase 2 + historical-data.md + market-data-model.md + database.md + domain-model.md + relevant skills (OANDA, SQLAlchemy, PostgreSQL, pytest). Not Dashboard, Journal, Reconciliation.
- **Experiments**: AGENTS.md + roadmap + experiments.md + reference-strategy.md + strategy-contract.md + market-data-model.md + accounting-model.md + domain-model.md. Not live broker docs unless crossing that boundary.
- **PAPER Execution**: AGENTS.md + roadmap + deployment.md + risk-management.md + execution.md + trading-accounts.md + runtime-model.md + safety-model.md + domain-model.md + relevant skills.

## Task Packet

Every implementation task should have: Task ID, Goal, Active roadmap phase, Read, Skills, Implement, Do not implement, Acceptance criteria, Tests. The packet should reduce scope, not restate the entire feature file.

## Plan Before Code / Inspect Before Creating

For nontrivial work: concise plan identifying files to change, code to reuse, data model changes, test strategy, edge cases, explicit non-goals. Before creating a class/abstraction/directory/service/repository/adapter/utility/table: inspect existing codebase for established home or equivalent concept. Prefer extending boundaries over parallel architecture.

## Vertical Slice Rule / Golden Path

Move a real workflow forward end-to-end. Bad: every repository → every engine → every API → every UI shell → eventually connect. Good: minimum domain behavior → persistence → application flow → API/UI where required → integration test → usable workflow. All implementation should ultimately advance: Load EUR/USD data → deterministic 15m bars → EMA Sweep Engulfing → long/short Trades → reproduce Experiment → inspect results → OANDA Practice → live bars → same StrategyVersion → TradeIntent → Risk → Order → Fill → Position → protection → restart → reconcile.

## Build Proof, Not Infrastructure

No Redis, Kafka, Celery, generic event bus, plugin system, distributed workers, container-per-module, repository framework, global state library without measured or explicit roadmap requirement.

## Abstraction Rule / External Boundaries

Create abstraction when: multiple real implementations exist, boundary explicitly required by architecture, or testing requires clean external dependency seam. Interfaces valuable at real external boundaries (market-data providers, execution brokers, clocks, account-state sources). Internal modules do not automatically require interfaces.

## Skills / Up-to-Date Documentation

Skills teach implementation practices (see [skills.md](skills.md)). For libraries/external APIs: use appropriate skill or authoritative current documentation. Do not rely on stale remembered APIs. Atlas context defines what to build; technical docs define how the dependency works today.

## Code Simplicity / Determinism / Failure-First

Explicit names, typed functions, small classes, straightforward control flow, clear transactions, visible error paths. Avoid metaprogramming, unnecessary inheritance, excessive generics, framework magic, giant managers, architecture ceremony. Deterministic behavior is a correctness requirement for Strategy/Risk/simulation. Implement happy path + material failure path together (valid data + missing data; Order accepted + rejected + timeout; normal start + broker unavailable).

## Safety Review / Database Changes

Any task affecting PAPER/LIVE exposure must check: can this create new exposure? what if broker state unknown? what on retry/restart? is protection preserved? can it run twice accidentally? Authority: [safety-model.md](../architecture/safety-model.md). Before adding table/column: identify domain concept, verify feature requires persistence, check overlap, define constraints, create Alembic migration, test invariant.

## Persistence Boundaries / Frontend Workflow / UI Reuse

Persist source-of-truth facts and required durable state. Not every intermediate calculation. Frontend work starts from user question screen must answer. Reuse established layout, typography, status patterns, badges, tables, charts, feedback patterns. No new design language per feature.

## UUID Rule / Test Strategy / Integration / E2E

Internal IDs may exist in URLs/technical diagnostics; no raw UUIDs as user-facing labels. Prioritize: domain correctness, deterministic simulation, integration boundaries, failure/restart, user workflow, unit coverage for isolated calculations. Important trading paths have integration tests. Use Playwright for important UI workflows once UI exists. No large brittle E2E suites for every component.

## Definition of Done / Slice Completion

Task done when: required behavior exists, tests pass, material failure behavior exists, architecture boundaries intact, no unrelated scope added, documentation accurate, user-facing workflow works. A roadmap slice is not complete because code compiles or tests pass — the slice-specific success criterion must work end to end.

## Documentation Updates / Contradiction Handling

Update context only when implementation reveals a real product/architecture boundary change, resolved ambiguity, or changed requirement. If context conflicts: stop → identify files → determine authoritative file → follow it → flag genuine unresolved contradictions. Do not silently choose whichever rule is easiest.

## Scope Expansion / Refactoring / Performance

If task requires work outside active slice: is it necessary for acceptance criteria? If no → defer. If yes → smallest required supporting behavior, document why, do not expand further. Refactor when required: remove duplication from active work, preserve boundary, fix correctness, make testable. No unrelated cleanup. Do not optimize based on assumption: implement correctly → measure → identify bottleneck → optimize.

## Agent Completion Report

Report: Implemented (what behavior changed), Files Changed, Tests, Acceptance Criteria (state whether each passed), Deferred, Risks/Blockers. Do not claim slice complete if end-to-end success criterion not demonstrated.

## Final Principle

Between a broad elegant framework and the smallest correct implementation advancing the Golden Path: choose the smallest correct implementation.
