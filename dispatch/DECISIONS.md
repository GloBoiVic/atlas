# Feature 04 — Decisions

- Final signals use UUID instrument identity and Decimal strength.
- `strategy_version_id` is canonical on immutable `Signal`; it is not duplicated
  as competing data on `SignalGenerated`.
- Strategies return a trading decision; the engine assembles the canonical
  provenance-bearing Signal.
- `DataRequirement` is timeframe-aware, while Feature 04 executes one candle
  series only.
- The feed/replay layer sources warm-up candles; the Strategy Engine rebuilds
  state and gates signals until warm-up completes.
- The registry loads only trusted, already-deployed packages and verifies the
  expected pinned commit. It does not accept arbitrary API import paths.
- Packages define parameter schemas/defaults; bots and backtests select validated
  YAML values. Code identity and configuration identity are recorded together.
- Only completed, matching, non-duplicate candles are evaluated. Strategy
  failures fail closed and pause the affected bot.
