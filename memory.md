# Memory — Atlas Documentation Alignment

Last updated: 2026-07-31

## What was built

- Initialized the Git repository and created branch `feature/01-project-foundation`.
- Updated `context/project-brief.md` to define Atlas as a single-user, remotely deployed trading operations platform.
- Reworked `context/architecture.md` into a focused source of truth for runtime topology, component boundaries, EventBus semantics, bot supervision, trading state contracts, backtesting invariants, and safety rules.
- Updated `context/roadmap.md` with the corrected delivery order: foundation, infrastructure, data, strategy, risk, execution, backtesting, bot runtime/paper trading, journal/analytics, UI, Binance testnet, and hardening.
- Expanded and aligned `context/database.md` with accounts, strategy versions, fills, bot runs, reconciliation runs, scoped orders/positions/journal entries, idempotency fields, and paper/testnet modes.
- Updated feature files `01` through `13` to match the agreed MVP scope and removed duplicated schema/UI/code examples where appropriate.
- Updated `context/design.md`, `context/tech-stack.md`, `context/coding-standards.md`, `context/library-docs.md`, `context/features/README.md`, `AGENTS.md`, and `CURRENT.md` for consistent ownership and terminology.

## Decisions made

- MVP is single-user but remotely deployed on one VPS using Docker Compose with frontend, API, worker, and PostgreSQL.
- Cloudflare provides HTTPS and Access with Google authentication; Atlas does not implement passwords.
- Broker interfaces remain broker-agnostic, but Binance Spot is the first concrete integration.
- First complete trading slice is Binance public market data plus paper execution; Binance Spot testnet execution follows later.
- Strategies are version-pinned Python packages from a private Git repository. Bots record the selected commit SHA.
- Multiple bots run as isolated pipelines in one worker process.
- MVP supports one net position per account and instrument.
- Backtest signals confirmed at candle close fill at the next candle open.
- Initial risk controls are position sizing, stop-loss/take-profit, and maximum open net positions. Daily loss, drawdown, and session controls are deferred.
- PostgreSQL is the durable source of truth. The EventBus is in-process coordination only.
- Unknown broker order state requires reconciliation before retrying.

## Problems solved

- Corrected the roadmap dependency error where backtesting preceded risk and execution.
- Defined EventBus delivery ordering, failure handling, bot scoping, idempotency, and event metadata.
- Added durable runtime recovery and broker reconciliation requirements.
- Resolved schema gaps around accounts, fills, strategy commits, bot runs, and journal identity.
- Removed stale Oanda implementation examples and old frontend/file-tree examples from MVP documentation.
- Resolved circular feature dependencies and made `roadmap.md` the canonical delivery sequence.
- Removed duplicate architecture diagrams, schema definitions, UI route/code examples, feature-order tables, and agent documentation.
- Clarified Decimal boundaries for backend money and controlled numeric conversion for Pandas/frontend display.

## Current state

- Documentation cleanup and consistency verification are complete.
- No application code, Docker setup, migrations, or tests have been implemented yet.
- `CURRENT.md` identifies Feature 01 as in progress.
- The working tree is uncommitted and contains the initialized repository plus existing project files.

## Next session starts with

Implement Feature 01 from `context/features/01-project-foundation.md`:

1. Create the backend, frontend, worker, and persistence structure.
2. Add Docker Compose for the four services and PostgreSQL volume.
3. Configure FastAPI health, worker liveness, Next.js app, Alembic, and environment settings.
4. Add tests and run backend/frontend linting and type checks.

## Open questions

- Exact VPS provider and Cloudflare deployment mechanism remain implementation details for Feature 01.
- The private strategy repository location and deployment procedure need to be configured without committing credentials.
- The final Binance Spot data/testnet adapter details should be verified against the selected library versions during implementation.
