# Task 4 — Example Strategies and Behavioral Tests Report

## Status

DONE_WITH_CONCERNS

## Implementation

- Added `backend.strategy.examples` exports for `SMACrossoverStrategy` and
  `BollingerBandsStrategy`.
- SMA crossover validates positive, ordered periods; keeps per-instance candle state;
  calculates moving averages with `Decimal`; and emits only actual BUY/SELL crossovers.
- Bollinger Bands validates a positive period and finite positive `Decimal` multiplier;
  uses population standard deviation with Decimal arithmetic; and emits mean-reversion
  decisions only when the close crosses the lower or upper band.
- Both strategies expose the configured timeframe through `DataRequirement`, defaulting
  to `1m`, and inherit the computation-only no-op `on_tick` contract.
- Extended metadata validation to preserve finite Decimal indicator values at the strategy
  domain boundary while retaining immutable metadata and rejecting unsupported values.

## Tests

`tests/test_strategy_examples.py` covers:

- insufficient history;
- SMA BUY and SELL crossovers;
- Bollinger lower/upper band behavior;
- suppression of repeated outside-band signals;
- Decimal strength and indicator metadata;
- invalid periods, ordering, multipliers, and timeframe declaration; and
- state isolation between strategy instances.

## Verification

- `python3 -m compileall -q backend/strategy tests/test_strategy_examples.py` — passed.
- `python3` strategy smoke check for SMA BUY/SELL and Bollinger BUY/repeat behavior — passed.
- `git diff --check` — passed.
- Focused pytest, full pytest, Ruff, and mypy could not run because those executables
  are not installed in this environment (`pytest`, `ruff`, `mypy`, and `uv` unavailable).

## Concerns

The required Python verification toolchain is unavailable locally. Run the focused tests,
full backend suite, Ruff, and mypy in the project development environment before merge.

## Commit

`feat: add strategy examples` (final commit; see git history for the hash)
