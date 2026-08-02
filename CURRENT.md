# Current Feature

Last updated: 2026-08-02

## Status

- [ ] Not started
- [x] In progress
- [ ] Complete

## Feature

- **Number:** 03
- **Name:** Data Layer
- **File:** context/features/03-data-layer.md

## Branch

- **Name:** feature/03-data-layer
- **Created:** 2026-08-02

## What was built

- Feature 03 branch created from `main`. No implementation yet.

## What comes next

- [ ] DataProvider interface defined
- [ ] Data models: Candle, Tick, Instrument
- [ ] CSV DataProvider: Load historical OHLC data from CSV files
- [ ] Historical data loader: Bulk import candles to PostgreSQL
- [ ] Candle storage pipeline: Fetch → Store → Emit CandleClosed event
- [ ] Binance DataProvider: Fetch historical Spot candles via ccxt
- [ ] Provider registry: Keep broker-specific data access behind the common interface

## Notes

- Development happens locally with the `.venv` (no Docker, no local PostgreSQL).
  Source-level checks: `ruff`, `mypy`, bounded `pytest`.
- Docker/Compose/PostgreSQL validation runs in the **single** Codespace on `main`
  (no per-branch Codespaces). Validate the pushed branch by checking it out in the
  existing Codespace, then return to `main`.
- `candles` and `instruments` tables are specified in `context/database.md`; a new
  Alembic migration (`005`) will be needed. Candles require Decimal precision,
  provider-scoped uniqueness, and the `idx_candles_lookup` index.
- Providers must normalize timestamps to UTC, return Decimal domain values, sort and
  deduplicate candles, and emit `CandleClosed` only for completed candles
  (`context/architecture.md`, Market Data section).
