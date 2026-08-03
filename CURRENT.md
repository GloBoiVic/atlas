# Current Feature

Last updated: 2026-08-02

## Status

- [ ] Not started
- [ ] In progress
- [x] Complete

## Feature

- **Number:** 03
- **Name:** Data Layer
- **File:** context/features/03-data-layer.md

## Branch

- **Name:** feature/03-data-layer
- **Created:** 2026-08-02

## What was built

### CSV historical slice (2026-08-02)

- [x] Added `CSVDataProvider` with the explicit `<data_dir>/<symbol>.csv` contract:
  UTF-8 CSV, required `timestamp,open,high,low,close,base_volume` columns, and
  optional close/volume detail columns.
- [x] CSV parsing runs in the executor, closes its file on success/error, propagates
  cancellation, normalizes aware timestamps to UTC, preserves Decimal values, validates
  OHLC/volume bounds, accepts unsorted rows, and collapses only identical duplicates.
- [x] Added `HistoricalDataLoader` with repository-owned CSV instrument resolution and
  metadata-preserving idempotent candle persistence; explicit upsert remains for
  metadata-bearing provider flows. No provider database access or `CandleClosed` emission.
- [x] Added canonical SHA-256 dataset identity over normalized Decimal/timestamp candle
  values and `HistoricalLoadResult(dataset, inserted_count)`.
- [x] Added UTF-8 BOM support, robust SQLAlchemy inserted-count handling via `RETURNING`,
  regression coverage for preserved instrument metadata, and documented `tick_volume`
  exclusion from the CSV contract.
- [x] Added focused fixture-style tests for valid, malformed, naive, duplicate, unsorted,
      range-filtered, Decimal, fingerprint, and repeat-import behavior.

### Binance historical slice (2026-08-02)

- [x] Added `BinanceHistoricalProvider` using resolved Binance Spot instruments, async ccxt
      `fetch_ohlcv`, bounded pagination, UTC/Decimal normalization, strict OHLCV validation,
      deterministic ordering, and identical-duplicate collapse.
- [x] Mapped normalized `BTCUSDT`-style instrument identities to ccxt `BTC/USDT` symbols;
      rejected provider and base/quote mismatches without network calls.
- [x] Closed async exchange resources on success, provider errors, and cancellation. ccxt-only
      candles leave quote/trade/taker fields absent because those values are not in OHLCV.
- [x] Added mocked exchange coverage for pagination, normalization, bounds, duplicates,
       symbol mapping, invalid rows, no-network validation, and cleanup paths.

### Provider composition slice (2026-08-02)

- [x] Added `HistoricalProviderRegistry` with strict lookup and duplicate-registration errors.
- [x] Added side-effect-free CSV/Binance composition with configured data directory and
      injectable Binance exchange factory; no secrets or database access are owned by the registry.
- [x] Exported registry, factory, and error types from `backend.data`.
- [x] Added registration, lookup, default construction, dependency injection, and no-network
      composition tests.
- [x] Tests: 218 passing after provider registry checks; ruff and mypy are clean.

### Foundation slice (2026-08-02)

- [x] Contract/safety prerequisites:
  - Converted all ORM models to native `Uuid` type with Python `UUID` annotations
    (accounts, strategies, strategy_versions, bots, reconciliation_runs —
    migrated via 005; new Instrument/Candle use Uuid from the start)
  - Removed auto-commit from `get_async_session()` — sessions yielded by the
    generic dependency are now read-only by default
  - Added production-mode rejection guard via `@model_validator` on
    `BrokerConfig` — `PRODUCTION` mode raises `ValidationError`
  - Added typed payload fields to `CandleClosed(candle: Candle)` and
    `TickReceived(tick: Tick)` — both use `field(kw_only=True)` to prevent
    dataclass inheritance ordering issues
  - EventBus delivery behavior preserved; CandleClosed payload verified
    through the bus end-to-end
- [x] Migrations:
  - **005 `convert_string36_to_uuid`** — drops/recreates all FK constraints,
    converts String(36)→UUID using `ALTER ... TYPE UUID USING col::UUID`
    across 5 tables (accounts, strategies, strategy_versions, bots,
    reconciliation_runs), downgrade reverses to VARCHAR(36)
  - **006 `create_instruments_and_candles`** — creates instruments table with
    `(symbol, provider)` uniqueness, creates candles table with
    `(instrument_id, provider, timeframe, open_time, price_basis)` uniqueness,
     explicit volume columns (base_volume, quote_volume, trade_count,
     tick_volume), `is_complete` boolean, and `idx_candles_lookup` index
   - Review fixes: 006 now uses PostgreSQL `gen_random_uuid()` server defaults
     for both primary keys; ORM metadata declares the matching candle lookup
     index.
- [x] Data domain models:
  - `Candle` — provider-domain OHLC, no DB row id, Decimal prices/volumes
  - `Tick` — single price update
  - `Instrument` — provider-aware with JSONB constraints metadata
  - `DatasetIdentity` — fingerprint for reproducible backtests
  - `HistoricalLoadResult` — wraps DatasetIdentity + inserted_count
- [x] Provider interfaces (stubs):
  - `HistoricalDataProvider` — abstract `get_historical_candles(instrument, timeframe, start, end)`
  - `LiveDataProvider` — abstract subscribe stubs (implementation in Feature 08)
  - Both receive resolved `Instrument`, not raw symbol strings
- [x] Repositories:
  - `InstrumentRepository` protocol — `resolve(symbol, provider)` and `upsert(...)`
  - `CandleRepository` protocol — `save_many(candles)` returns inserted count
    via `ON CONFLICT DO NOTHING` (no-op dedup, not upsert)
  - `SqlAlchemyInstrumentRepository` — `postgres_insert(...).on_conflict_do_update()`
   - `SqlAlchemyCandleRepository` — bulk insert with dedup
   - Candle inserts select the PostgreSQL or SQLite dialect from the bound engine;
     in-memory deduplication retains exact `datetime` timestamps.
  - All existing `BotRecord`, `ReconciliationRecord`, `BotSnapshot` types
    updated to use `UUID` (not `str`) end-to-end through repository protocols,
    implementations, worker protocols, and supervisor
- [x] Tests: 218 passing after the Binance historical slice (including focused
  migration server-default, ORM index, exact timestamp deduplication, SQL
  dialect-selection, CSV provider, and Binance provider tests)
- [x] Lint + type: ruff clean; mypy clean on backend code (14 pre-existing
  test-only annotations remain unchanged)

## PostgreSQL / Codespace validation (2026-08-02)

- [x] Live PostgreSQL upgrade/downgrade/re-upgrade cycle passed:
  - Migration 005 (`convert_string36_to_uuid`) — upgrade: applied cleanly on
    the Codespace PostgreSQL instance, converted all `String(36)` PK/FK columns
    to native `UUID` across `accounts`, `strategies`, `strategy_versions`,
    `bots`, and `reconciliation_runs`.
  - Migration 005 — downgrade: reverted all columns back to `VARCHAR(36)`
    without data loss or truncation.
  - Migration 006 (`create_instruments_and_candles`) — upgrade: applied cleanly,
    created `instruments` and `candles` tables with correct schema, index,
    and uniqueness constraints.
  - Re-upgrade (005 → 006): clean re-application after downgrade confirmed
    idempotent round-trip.
  - `alembic current` reports `006` (head).
- [x] Repository smoke test passed: `InstrumentRepository.resolve()` and
  `CandleRepository.save_many()` executed against the live PostgreSQL database
  with correct upsert, dedup, and inserted-count semantics.
- [x] Health check: `/health` endpoint accessible via Docker Compose API service.
- [x] Migration SQL rendering tests continue to pass (local and CI).
- [x] Full test suite: 218 tests passing; ruff and mypy remain clean.
- [x] Commit: `ec70874` — validated on the shared Codespace.

## What comes next

- [x] HistoricalDataProvider CSV implementation and historical loader — this slice
- [x] HistoricalDataProvider Binance implementation — this slice
- [x] LiveDataProvider interface stub — defined; Feature 08 wires the implementation
- [x] CSV historical provider: Load validated, sorted, deduplicated OHLC data
- [x] Binance historical provider: Fetch normalized Spot klines via async ccxt, including
      bounded pagination, Decimal normalization, duplicate validation, and cleanup on all exits
- [x] Provider registry: Keep broker-specific data access behind the common interface
- [x] DatasetIdentity fingerprint for reproducible backtests
- [ ] CandleClosed emission owned by replay/live feed (Features 07/08 — deferred, not a Feature 03 deliverable)

## Migration notes

- Migrations 005 and 006 require PostgreSQL. SQLite cannot execute the
  `ALTER COLUMN ... TYPE UUID USING` or `sa.Uuid()` column types.
- Migration 005 downgrade converts UUID columns back to VARCHAR(36) —
  verify the data fits back into 36 characters (UUID strings always do).
- Both migrations have been validated against live PostgreSQL in the shared
  Codespace — upgrade, downgrade, and re-upgrade round-trip confirmed.

## Notes

- Development happens locally with the `.venv` (no Docker, no local PostgreSQL).
  Source-level checks: `ruff`, `mypy`, bounded `pytest`.
- Docker/Compose/PostgreSQL validation validated in the **single** Codespace on
  `main` (no per-branch Codespaces).
- `candles` and `instruments` tables are live in the ORM and migrations
  (006). Candles require Decimal precision, provider-scoped uniqueness,
  and `idx_candles_lookup`.
- `CandleClosed` and `TickReceived` now carry typed payloads with
  `kw_only=True` — new payload-bearing events must follow this pattern.
- `get_async_session()` no longer auto-commits; write operations must own
  their transaction boundaries via `session_factory.begin()`.
