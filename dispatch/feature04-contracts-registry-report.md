# Task 2 — Strategy Contracts and Trusted Registry Report

## Status

Implemented Task 2 only. StrategyEngine and EventBus integration were intentionally
not implemented.

## Implementation

- Added `backend/strategy/contracts.py` with `SignalDirection`, `DataType`,
  timeframe-aware `DataRequirement`, immutable `StrategyDecision`, and immutable
  provenance-bearing `Signal`.
- Enforced UUID identity, Decimal-only finite strength in `[0, 1]`, UTC candle
  timestamps, non-empty strategy identity, and JSON-compatible immutable metadata.
- Added `backend/strategy/base.py` with synchronous `Strategy.on_candle`, no-op
  `on_tick`, and default one-minute candle requirement.
- Added `backend/strategy/registry.py` with explicit factory registration,
  duplicate protection, expected name/SHA verification, missing version rejection,
  and factory-result validation. It performs no imports, repository cloning, or
  package installation.
- Updated `backend/strategy/__init__.py` exports.
- Preserved `Candle` unchanged, including its lack of a row ID. No events,
  migrations, persistence schema, API routes, or live-feed code were changed.

## Tests

`tests/test_strategy_contracts_registry.py` covers frozen contracts, metadata and
strength validation, UUID/UTC boundaries, data requirements, default hooks,
registry lookup, duplicate registration, missing versions, and commit mismatch.

## Verification

- Focused tests: `python3 -m pytest -q tests/test_strategy_contracts_registry.py` — 13 passed.
- Ruff and mypy executables were not installed in the environment; both commands
  were attempted and could not run (`command not found`).
- Full backend tests: `python3 -m pytest -q` — 234 passed.

## Concerns

The environment lacks standalone `ruff`, `mypy`, and `uv` on PATH. Python's
installed pytest module provided focused and full test runs; Ruff and mypy require
the project's development toolchain to be installed.
