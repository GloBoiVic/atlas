# Feature 04 — Strategy Engine Plan

## What we are building

The deterministic strategy boundary between normalized completed candles and the
centralized Risk Engine. Each bot receives an isolated strategy instance. The
same strategy package and contracts work in backtesting and paper trading.

## Scope

- Strategy base contract for completed candles and optional tick observation.
- Immutable, fully identified signals assembled by the Strategy Engine.
- Per-bot Strategy Engine subscription to `CandleClosed` and publication of
  `SignalGenerated`.
- Timeframe-aware data requirements, validated for one candle series in this
  feature.
- Trusted registry for already-deployed, version-pinned strategy packages.
- YAML parameter validation and immutable per-bot configuration.
- Warm-up lifecycle and signal gating; replay/data sourcing remains outside the
  Strategy Engine.
- SMA crossover and Bollinger Bands examples with focused tests.

## Explicit non-goals

- Intrabar or tick-generated trading signals.
- Multi-timeframe orchestration or candle aggregation.
- Database/network/broker access from strategies.
- Arbitrary API-supplied imports or runtime package installation.
- Persistent strategy state across restarts.
- Backtest orchestration, live feed implementation, Risk Engine, or Execution.

## Implementation order

1. Reconcile the Feature 04 contract and architecture documentation.
2. Define strategy decisions, immutable signals, directions, and data
   requirements using UUID, Decimal, UTC, and frozen-domain conventions.
3. Implement the base strategy contract and trusted registry boundary.
4. Implement the per-bot engine, warm-up gate, validation, deduplication, and
   error/pause behavior.
5. Implement SMA crossover and Bollinger Bands examples.
6. Add contract, isolation, timing, registry, parameter, failure, and example
   strategy tests.
7. Run Ruff, mypy, and the full backend test suite; update CURRENT.md and mark
   the feature deliverables complete only after validation.
