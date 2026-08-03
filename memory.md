# Memory — Atlas Feature 03 Session

Last updated: 2026-08-02

## What was built

*This session:*

- **Context normalization complete** — reconciled 13 context files with the actual single-user, paper-first, single-worker MVP:
  - `context/project-brief.md` — clarified Binance Spot as first integration, OANDA deferred with specific format differences, production mode gated behind safety adapter
  - `context/architecture.md` — UUID identity convention, separate historical/live provider interfaces, provider-aware instruments with JSONB constraints, Trade entity lifecycle, session auto-commit as temporary gap, typed event payload contracts documented
  - `context/database.md` — full rewrite: target UUID schema, service-owned transaction boundary, current `String(36)` gap, planned schema for Feature 03+ tables (instruments, candles, orders, fills, positions, trades, journal_entries) with explicit uniqueness and column semantics
  - `context/coding-standards.md` — updated module tree to reflect actual `backend/` layout with `data/`, `execution/`, `worker/`, `persistence/repositories/` packages; UUID identity rule with gap note
  - `context/library-docs.md` — aligned FastAPI/SQLAlchemy patterns with documented gaps
  - `context/roadmap.md` — all feature deliverables updated to match separated responsibilities
  - `context/features/03-data-layer.md` through `10-journal-analytics.md` — each feature file updated with clarified scope, separate historical vs live data interfaces, Trade entity, dataset identity
- `.dispatch/COMPLETED.md` updated with context normalization completion record.
- No application code was written or changed.

*Previous session (preserved):*

- Added `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile` for GitHub Codespaces.
- Removed Codespaces `postCreateCommand` for full dependency installation.
- Updated `Dockerfile.api` and `Dockerfile.worker` for correct `backend` package copy.
- Added setuptools package discovery to `pyproject.toml`.
- Updated Alembic to read synchronous database URL from settings.
- Made `NEXT_PUBLIC_API_URL` configurable for Codespaces.
- Added `docs/codespaces.md` and updated `AGENTS.md`, `CURRENT.md`, `context/tech-stack.md`, etc.
- Consolidated `.dispatch/ledger.md` → `COMPLETED.md`; deleted 32 one-off task files.

## Decisions made

*This session:*

- **UUID identity convention is the confirmed target.** Python domain types use `UUID`, ORM models use `Uuid` column type, repository protocols accept/return `UUID`. Current `String(36)` implementation is a documented transitional gap — all new code must use native UUIDs.
- **Historical and live data provider interfaces are separate.** `HistoricalDataProvider` returns bounded candle lists; `LiveDataProvider` is an async generator. Feature 03 covers historical only; live streaming is Feature 08.
- **Instruments are provider-aware.** Candles reference `instrument_id` FK, not fragile symbol strings. Provider-specific constraints are JSONB metadata, not flattened shared columns.
- **Candle semantics are explicit:** `open_time` (interval start, UTC), `price_basis` (`"trade"` for Binance, `"bid"/"ask"/"mid"` for OANDA), `is_complete`, volume fields split into `base_volume`, `quote_volume`, `trade_count`, `tick_volume`. Binance `tick_volume` is not OANDA `tick_volume` — different semantics require different fields.
- **CandleClosed emission belongs to Feature 08** (live streaming / replay), not Feature 03 (historical loader).
- **Trade is a first-class entity.** Created when a position opens, finalized when the position closes. Anchors journaling and analytics. All fills, P&L, fees, and market context aggregate on the Trade.
- **Session auto-commit is a temporary gap.** The `get_async_session()` FastAPI dependency currently auto-commits. Target is read-only default; write services own commit/rollback explicitly via `async with session_factory.begin()`.
- **Typed event payload contracts are documented but not yet populated.** All event subclasses still carry `pass` — payload fields must be added before event emission integration.
- **OANDA is deferred** with documented candle format differences (RFC3339 timestamps, bid/ask/mid prices, tick-count volume) so abstractions are designed correctly now, not retrofitted later.
- **Production live trading requires a safety gate and production adapter** before it can be enabled. This is consistently documented across all context files.
- **Risk configuration lives in YAML**, not a separate database table.

*Previous session (preserved and still relevant):*

- GitHub Codespaces is the supported dev environment; Docker Desktop not required.
- Docker Compose is the runtime topology (API, worker, frontend, PostgreSQL).
- Codespace creation must stay lightweight — no automatic heavy dependency installs.
- `docker-outside-of-docker` for Codespaces (mounts host socket).
- Alembic sync migrations require `psycopg2-binary` alongside `asyncpg`.

## Problems solved

*This session:*

- Recontextualized the entire documentation set from a speculative multi-user database design to the actual single-user, paper-first, single-worker platform. The `database.md` had the most substantial rewrite (695 lines changed).
- Separated historical data ingestion responsibility from live streaming across Feature 03 and Feature 08 — avoiding a design that conflates both in one deliverable.
- Documented the UUID identity gap explicitly rather than silently continuing with `String(36)`. New code now has a clear target.
- Established provider-specific volume semantics so Binance `base_volume` and OANDA `tick_volume` are not conflated in a single `volume` field.
- Addressed the open question from the first session in COMPLETED.md: "whether we should continue refining pre-implementation decisions or proceed with Feature 03 implementation" — decision was to normalize context first, then plan.

*Previous session (preserved):*

- Fixed `ModuleNotFoundError: No module named 'backend'` during Alembic execution.
- Fixed container database hostname problem in Alembic configuration.
- Fixed Codespaces creation failure from stale Yarn repository signing key.
- Fixed Codespaces post-create exit code 137 by removing full dependency installation.
- Fixed Codespaces recovery mode with `docker-outside-of-docker` and `overrideCommand`.

## Current state

- **Context normalization is complete and internally consistent.** All 13 modified context files are uncommitted (`git diff --stat` shows +1356/−709 lines across 15 files including `.dispatch/COMPLETED.md`). No application code was modified.
- **Branch:** `feature/03-data-layer` (from `main`, 2026-08-02).
- **Feature 02** complete and committed on `main` (lease removal in `8b735ec`). Health monitor and Docker/Compose/PostgreSQL validation remain deferred.
- **Dispatch state:** `.dispatch/PLAN.md` still holds the obsolete context normalization plan (tasks all marked done in `TASKS.md`). `.dispatch/COMPLETED.md` updated with the normalization record. `MODEL-LOG.md` records the documenter/explore agent task history.
- **Environment workflow locked in:** local `.venv` development; one Codespace on `main`; validate feature branches by checking them out inside the existing Codespace.
- **Alembic migration** not yet re-verified after the psycopg2 fix.

## Next session starts with

**Revisit and finalize the pre-Feature-03 implementation plan.** The context normalization resolved what the architecture and data contracts should be. Before writing code (DataProvider interfaces, domain models, CSV/Binance providers, migration `005`, storage pipeline), produce a concrete implementation plan that answers:

1. Which files to create and in what order (vertical slice sequence for Feature 03).
2. Which existing patterns to follow (UUID on new models, `async with session_factory.begin()` for writes).
3. Whether the `String(36)` → `UUID` migration for existing models should be its own follow-up or bundled with Feature 03.
4. Test strategy for provider-agnostic data access (mocked Binance, fixture-based CSV).
5. How the historical loader integrates with the existing `async_session` factory without auto-commit.
6. Confirmation that the `CandleClosed` omission from Feature 03 is deliberately preserved.

## Open questions

- Whether old `feature/02-*` and `chore/*` branches should be deleted after their work is fully merged/verified.
- Whether the `String(36)` → native `UUID` migration for existing ORM models should be a separate pre-Feature-03 task or included in Feature 03.
