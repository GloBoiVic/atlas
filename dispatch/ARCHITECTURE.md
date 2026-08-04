# Feature 04 — Agreed Architecture

## Signal provenance

`strategy_version_id` is canonical data on the immutable `Signal`, alongside
strategy name, pinned commit SHA, instrument UUID, completed-candle timestamp,
direction, Decimal strength, and strategy metadata. `SignalGenerated` carries
the signal and event-scoping metadata without duplicating the version identity.

The engine assembles the final Signal from a strategy decision. Strategies own
trading logic (direction, strength, and indicator metadata); the engine owns
bot/account scope, instrument and candle provenance, strategy identity,
validation, and deduplication.

## Data requirements

Strategies declare a typed `DataRequirement` containing a data type and
timeframe. Feature 04 supports one candle requirement and validates it against
the bot configuration. Multi-timeframe orchestration is deferred.

## Warm-up and replay

The replay/data-feed layer owns sourcing and ordering historical candles. The
Strategy Engine owns warm-up lifecycle and signal gating. Warm-up candles rebuild
strategy state but cannot emit trading signals. Signal generation begins only
after warm-up completes.

## Registry and deployment trust

The runtime registry resolves only already-deployed and explicitly registered
strategy packages. A bot selects a persisted strategy version; the registry
requires the installed package identity to match the expected strategy and
pinned commit SHA. Missing packages or mismatches fail closed. Runtime registry
code does not clone repositories, install dependencies, or execute API-supplied
import paths.

## Parameters

The deployed package owns the parameter schema and safe defaults. A bot or
backtest owns the selected YAML parameter values. Atlas validates and freezes
the configuration, and records the selected parameter snapshot with the
strategy-version identity.

## Safety behavior

The engine accepts only completed candles matching the bot's instrument and
timeframe. It rejects duplicate candle events and invalid signal output. A
strategy exception produces no signal, publishes/logs `StrategyError`, and
pauses the affected bot under the existing EventBus safety contract. Strategy
hooks are synchronous and computation-focused; they perform no I/O.
