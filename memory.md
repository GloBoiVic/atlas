# Memory — Atlas Feature 03 Session

Last updated: 2026-08-02

## What was built

*This session (Feature 03 implementation):*

- **Data domain models & protocols** (`backend/data/models.py`, `backend/data/interfaces.py`):
  - `Instrument`, `Candle`, `Tick`, `DatasetIdentity`, `HistoricalLoadResult` domain models
  - `HistoricalDataProvider` and `LiveDataProvider` (stub) provider interfaces
  - `CandleClosed` and `TickReceived` typed event payloads with `kw_only=True` convention

- **CSV historical provider** (`backend/data/csv_provider.py`):
  - Strict column contract, Decimal normalization, UTC timestamps, BOM support
  - Validated, sorted, deduplicated OHLC from CSV files
  - Range filtering and proper error handling for malformed rows

- **Binance Spot historical provider** (`backend/data/binance_provider.py`):
  - Normalized kline data via async ccxt with bounded pagination
  - UTC/Decimal normalization, strict OHLCV validation
  - Cleanup on all exit paths (normal, cancellation, error)

- **Historical data loader** (`backend/data/loader.py`):
  - Repository-owned CSV instrument resolution with idempotent candle persistence
  - No provider database access or CandleClosed emission
  - `DatasetIdentity` fingerprint for reproducible backtests

- **Provider registry** (`backend/data/registry.py`):
  - `HistoricalProviderRegistry`: strict lookup, duplicate-registration errors
  - Side-effect-free CSV/Binance composition with configured data dir and injectable exchange factory

- **In-memory & SQLAlchemy repositories** (`backend/persistence/repositories/`):
  - `InstrumentRepository` and `CandleRepository` protocols, in-memory and SQLAlchemy implementations
  - Bulk save with `ON CONFLICT DO NOTHING` and correct inserted-count return
  - Updated `BotRepository` to use SQLAlchemy `select()` style for UUID compatibility

- **Migrations 005 and 006** (`alembic/versions/`):
  - 005: Convert existing `String(36)` PK/FK columns to native UUID across accounts, strategies, strategy_versions, bots, reconciliation_runs
  - 006: Create provider-aware `instruments` and `candles` tables with native UUID FKs, JSONB provider metadata, explicit `price_basis`, and split volume columns
  - Migration upgrade/downgrade round-trip validated on live Codespace PostgreSQL

- **Tests (218 passing, ruff/mypy clean):**
  - `test_data_models.py` (191 lines) — UTC, candle bounds, ordering, duplicates, Decimal values, completion, price basis
  - `test_csv_data_layer.py` (397 lines) — CSV malformed rows, naive timestamps, duplicates, unsorted, range filtering, Decimal preservation
  - `test_binance_provider.py` (140 lines) — pagination, mocked ccxt normalization, symbol mapping, cleanup on cancellation
  - `test_instrument_candle_repos.py` (453 lines) — SQLAlchemy repository CRUD, conflict idempotency, bulk count
  - `test_repository_contracts.py` (281 lines) — in-memory/SQLAlchemy parity contract enforcement
  - `test_provider_registry.py` (81 lines) — strict lookup, duplicate registration, composition
  - `test_migrations.py` (138 lines, updated) — migration SQL rendering, upgrade/downgrade round-trip
  - `test_models.py` (87 lines, updated) — UUID/model updates, events type/event_type consistency
  - Other amended tests: `test_repositories.py`, `test_sql_repositories.py`, `test_supervisor.py`, `test_worker_protocols.py`, `test_events.py`, `test_config.py`

*Previous session (preserved — context normalization):*

- Reconciled all 13 context files (project-brief, architecture, database, coding-standards, library-docs, roadmap, features 03–10) with the actual single-user, paper-first, single-worker MVP
- UUID identity convention, separate historical/live provider interfaces, provider-aware instruments with JSONB metadata, Trade entity lifecycle, typed event payload contracts
- OANDA deferred with documented format differences
- `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile` for GitHub Codespaces
- Updated Dockerfiles, pyproject.toml, Alembic config, Codespaces docs, AGENTS.md, CURRENT.md
- Consolidated `.dispatch/` → COMPLETED.md; deleted 32 one-off task files

## Decisions made

*This session (Feature 03 implementation):*

- **ccxt for Binance Spot historical** — async ccxt wraps Binance REST klines endpoint; no direct REST calls. Six-value OHLCV from ccxt includes only `base_volume`; optional quote/trade/taker fields not enriched without separate approval.
- **Repository-owned instrument resolution** — CSV provider resolves instruments via `InstrumentRepository` (get-or-create upsert), not by accepting pre-resolved IDs. Binance provider does the same with provider `Base` + quote symbol mapping.
- **ON CONFLICT DO NOTHING** — candles are deduplicated at the database level on `(instrument_id, provider, timeframe, open_time, price_basis)`. `save_many()` returns actual inserted count, not requested count.
- **DatasetIdentity fingerprint** — SHA-256 of canonical serialized canonical JSON of sorted candles. Deterministic: same inputs always produce same fingerprint.
- **kw_only=True for event payloads** — avoids inherited-default dataclass ordering failures. Applied to `CandleClosed` and `TickReceived` payload subclasses.
- **Storage pipeline is not a standalone class** — the `HistoricalDataLoader` orchestrates provider → resolve → persist in one service; no separate "storage" abstraction layer beyond repositories.
- **Migration 005 targets 7 tables** — accounts, strategies, strategy_versions, bots, reconciliation_runs (and their String(36) FK columns), plus migration 006 references new tables with native UUID.
- **Migration 006 instrument uniqueness** — `(provider, symbol)` unique constraint on instruments; candles unique on `(instrument_id, provider, timeframe, open_time, price_basis)`.
- **18 pre-existing test-only mypy annotations are excluded** from strict mode, not fixed. Verified clean run.

*Previous session (preserved and still relevant):*

- **UUID identity convention is the confirmed target** — Python domain types use `UUID`, ORM models use `Uuid` column type, repository protocols accept/return `UUID`. Migration 005 now converts existing `String(36)` to native UUID.
- **Historical and live data provider interfaces are separate** — Feature 03 covers historical only; live streaming is Feature 08.
- **Instruments are provider-aware** — Candles reference `instrument_id` FK, not fragile symbol strings. Provider-specific constraints are JSONB metadata.
- **Candle semantics are explicit** — `open_time` (interval start, UTC), `price_basis` (`"trade"` for Binance), `is_complete`, split volume fields.
- **CandleClosed emission belongs to Feature 08** — not Feature 03.
- **Trade is a first-class entity** — planned for Feature 05/07 when positions and fills are introduced.
- **Session auto-commit is being migrated** — service-owned `async with session_factory.begin()` now in use for repositories; the old FastAPI dependency auto-commit is a documented gap.
- **OANDA is deferred** — candle format differences documented (RFC3339, bid/ask/mid, tick-count volume).
- **Production live trading requires a safety gate** — consistently documented.
- **Risk configuration lives in YAML** — not a database table.
- **GitHub Codespaces is the supported dev environment** — Docker Desktop not required.
- **Docker Compose is the runtime topology** (API, worker, frontend, PostgreSQL).
- **Single-worker deployment invariant** — lease removal was Feature 02.

## Problems solved

*This session:*

- **ccxt v2+ pagination** — ccxt `fetch_ohlcv` pagination uses `since` param with millisecond timestamps. Limit must be <= 1000 (Binance cap). The loop fetches until `since >= until` or empty response.
- **Instrument resolution before candle fetch** — Binance provider must resolve/create instruments before fetching candles because candles reference `instrument_id`. The provider returns both identity and resolved instrument mapping.
- **UUID migration for existing String(36) tables** — converting PK/FK columns in 7 tables required careful handling of existing row data (no data loss), Alembic `batch` mode for SQLite compatibility, and proper FK dependency ordering.
- **Migration test dead code** — an obsolete test specifically for the old migration had to be removed after the real migration was implemented.
- **Repository contract parity** — in-memory and SQLAlchemy implementations must match behavior exactly. Enforced via parametrized contract tests in `test_repository_contracts.py`.
- **Event payload kw_only convention** — discovered during implementation that inherited default ordering in dataclass subclasses causes ValueError. `kw_only=True` resolves this.
- **Live PostgreSQL validation in Codespaces** — migrations 005→006 upgrade→downgrade→re-upgrade round-trip confirmed working against a real PostgreSQL instance in the shared Codespace via Docker Compose.

*Previous session (preserved):*

- Recontextualized entire doc set from speculative multi-user to actual single-user, paper-first, single-worker platform
- Separated historical (Feature 03) from live streaming (Feature 08) responsibilities
- Documented UUID identity gap before implementing the migration
- Established provider-specific volume semantics to avoid conflating Binance and OANDA fields
- Fixed Codespaces creation failures, Docker hostname issues, Alembic module resolution, and stale signing keys

## Eureka moments

*Preserved from previous session (still relevant):*

- Separating historical from live data interfaces was the key insight that made the data layer design clean. Without this distinction, every provider would need to implement both bounded-batch and async-generator patterns simultaneously.
- Provider-specific volume semantics (Binance `base_volume` vs OANDA `tick_volume`) are fundamentally different data — forcing them into a single `volume` field would be a design mistake that compounds across backtesting.

## Current state

- **Feature 03 is complete and validated.** All code committed on branch `feature/03-data-layer`. 218 tests passing, ruff clean, mypy clean (14 pre-existing test-only annotations excluded). Live Codespace PostgreSQL migration and repository smoke validation passed.
- **Commits:** `ec70874` (feat: implement historical data layer), `78cf3bf` (docs: close feature 03 validation).
- **Branch:** `feature/03-data-layer` (from `main`, 2026-08-02).
- **Feature 02** is complete and committed on `main` (lease removal in `8b735ec`). Health monitor and Docker/Compose/PostgreSQL validation remain deferred.
- **Dispatch state:** `.dispatch/PLAN.md` still holds the Feature 03 implementation plan. `.dispatch/TASKS.md` all marked done. `.dispatch/COMPLETED.md` updated with Feature 03 completion. `.dispatch/MODEL-LOG.md` records the full agent task history.
- **Environment:** local `.venv` development; Codespace on `main` with feature branch checked out inside for validation.
- **Migrations 005 and 006** are at head (`alembic current` = 006).

## Next session starts with

**Plan and implement Feature 04 — Strategy Engine.** This is the next vertical slice. The strategy engine owns package deployment, the Strategy runtime protocol, the strategy sandboxed execution context, and strategy lifecycle (start/stop/destroy). Key preparation:

1. Read `context/features/04-strategy-engine.md` for acceptance criteria.
2. Read `context/architecture.md` for strategy-engine component boundaries.
3. Read `context/database.md` for the schema relevant to strategies, strategy_versions.
4. Confirm whether the existing `StrategyRepository` protocols need updating for the strategy engine.
5. Review decision to use version-pinned private Git deployments for strategy packages (from context/project-brief.md).
6. Plan feature branch: `feature/04-strategy-engine` from `main`.
7. Implement one vertical slice at a time; write tests with every slice.
8. Run `ruff check`, `mypy`, and `pytest` after each slice.

## Open questions

- Whether old `feature/02-*` and `chore/*` branches should be deleted after their work is fully merged/verified.
- Whether the health monitor / Docker-Compose-PostgreSQL validation from Feature 02 should be addressed before or during Feature 04.
