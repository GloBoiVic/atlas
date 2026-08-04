# Task 3 — Per-Bot Strategy Engine and Warm-Up Gate Report

## Status

Implemented on `feature/04-strategy-engine`.

## Scope delivered

- Added frozen, keyword-only `SignalGenerated(signal=...)` and
  `StrategyError(error=...)` payloads while retaining `DomainEvent` metadata.
- Added and exported `backend.strategy.StrategyEngine`.
- Engine owns one bot's strategy identity, account/bot/instrument scope,
  candle requirement, subscription, warm-up state, and deduplication state.
- Warm-up accepts caller-sourced ordered candles, rebuilds strategy state, and
  suppresses all signals. It does not source, order, or persist data.
- Live processing validates Candle type, instrument, timeframe, and completion
  before strategy evaluation.
- Deduplication uses exactly
  `(instrument_id, provider, timeframe, open_time, price_basis)`; `Candle` remains
  row-ID-free.
- Decisions are converted into immutable provenance-bearing `Signal` values and
  emitted with account, bot, mode, and correlation metadata.
- Strategy exceptions publish `StrategyError` and are re-raised. The enclosing
  `EventBus` therefore records the handler failure and invokes the bot-pause
  callback. No signal is emitted on failure.
- Added idempotent unsubscribe/close cleanup.
- Added focused async coverage for subscription, warm-up suppression, live
  emission/provenance, validation rejection, composite-key deduplication,
  failure/pause behavior, and cleanup.

## Verification

- Focused tests: `41 passed`
- Full backend tests: `242 passed`
- Focused Ruff: passed for all changed source and test files.
- Full Ruff: reports three pre-existing issues outside this task:
  `SignalDirection`/`DataType` enum style in `contracts.py`, and the existing
  `Callable` import style in `registry.py`.
- Backend mypy: reports one pre-existing error in `backend/strategy/contracts.py:87`
  (`no-any-return` from `_freeze_json`). Engine and event changes introduce no
  mypy errors.

## Files changed

- `backend/core/events.py`
- `backend/strategy/engine.py`
- `backend/strategy/__init__.py`
- `tests/test_events.py`
- `tests/test_strategy_engine.py`
- `CURRENT.md`

## Concerns

The repository's full Ruff and mypy gates remain non-clean because of the
pre-existing findings documented above. No dependencies, persistence, feeds,
risk/execution code, API routes, tick subscriptions, or replay sourcing were
added.
