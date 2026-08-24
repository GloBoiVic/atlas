# Task 02 — Registry Catalog

## Status

**COMPLETE** — implemented exact multi-version local Strategy registration and
idempotent startup catalog synchronization without migrations or API/history/UI
changes.

## Changes

- Updated `StrategyRegistry` to retain multiple implementations for one
  `strategy_key`, reject duplicate implementation keys, expose deterministic
  catalog iteration, and resolve execution only by exact
  `(strategy_key, implementation_key, source_fingerprint)` provenance.
- Registered the preserved v1 implementation before the parameter-enabled v2
  implementation in `create_production_strategy_registry`.
- Added transactional `synchronize_strategy_catalog`, which persists explicit
  local registrations through `StrategyRepository.create_version`; existing
  fingerprints deduplicate and missing versions append in stable order.
- Wired synchronization into the FastAPI lifespan before requests are served.
  Any synchronization exception propagates as startup failure and the engine is
  disposed; no partially available catalog is served.
- No database migration, new table/column, API route, history, UI, comparison,
  broker, or runtime execution surface was added.

## Validation receipts

- `ruff check` on changed backend files: **passed**.
- `python -m compileall -q backend/strategies backend/persistence backend/api`:
  **passed**.
- Focused Strategy provenance/v1/v2 tests: **35 passed**.
- Existing Strategy persistence integration tests: **3 passed**.
- Production catalog receipt: **2 registrations**, ordered
  `ema_sweep_engulfing.v1` then `ema_sweep_engulfing.v2`; fingerprints match
  Task 01 (`20c2bf...8e3a3` and `56b236...9754`).
- API health tests were attempted but could not start the configured local
  database (`FATAL: role "u" does not exist`). This is consistent with the
  fail-closed startup synchronization path; no application assertion was
  reached.

## Blockers

None within Task 02 scope.
