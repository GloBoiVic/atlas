# Market Data Model

## Purpose

The Market Data Model defines how Atlas represents, stores, aggregates, and exposes market data. Primary goals: deterministic Strategy evaluation, consistent historical/live candle semantics, no lookahead, explicit execution pricing, reliable data provenance. Same rules must support Experiment, PAPER, and LIVE.

## Core Principle

Atlas separates: market observation from trading decision from execution price. Providers are normalized into canonical Atlas market data before Strategy evaluation.

## Canonical Instrument / Bar

Market data identified using canonical Atlas Instrument (e.g., EUR/USD). Provider-native symbols belong to VenueInstrument. A Bar contains: Instrument, provider, resolution, price component, start/end time, OHLC, completion state. All timestamps are UTC.

## Timestamp Semantics

Distinguish explicitly between bar start time and bar end time. For a 15-minute bar: interval [10:00:00, 10:15:00). Use one canonical convention consistently.

## Completed Bar Rule

A bar becomes completed only when its full interval has elapsed and Atlas has sufficient data to finalize it. A Strategy may only receive completed bars. Strategy evaluates only at or after bar completion according to the Atlas-controlled frontier.

## No-Lookahead Frontier

At evaluation time T, Strategy-visible market info must satisfy bar.end_time <= T. No Strategy code may access future bars, partially formed future context, or provider responses beyond the current frontier. Applies equally to historical simulation, paper trading, and live trading.

## Base Resolution / Deterministic Aggregation

Initial Forex base: 1m. Reference Strategy: 15m. Higher timeframes derived deterministically from base resolution. Aggregation rules identical across historical and live workflows. Do not implement separate builders for Experiment vs live.

## OHLC Aggregation

For derived interval: open = first base-bar open, high = max base-bar high, low = min base-bar low, close = final base-bar close. Only completed constituent bars contribute. Missing data must not be silently fabricated. Timeframe boundaries deterministic and UTC-based (00/15/30/45 for 15m unless provider convention requires otherwise).

## Decision / Execution Separation

If Strategy evaluates a completed bar ending at 10:15:00, that decision may not execute using market data already consumed to construct that bar. First execution observation must occur at or after the decision frontier. Must be tested explicitly.

## Price Components

MID, BID, ASK are separate price components with different purposes. MID used for Strategy analysis/indicator calculation (EMA, ATR, candlestick patterns). MID is not automatically executable. Execution simulation uses executable sides: Long entry BUY→ASK, Long exit SELL→BID, Short entry SELL→BID, Short exit BUY→ASK. Spread emerges from price components, not hidden in Strategy logic.

## Provider Normalization

Each provider adapter translates data into canonical Atlas bars. Initial: OANDA. Provider-specific models inside integration layer.

## Historical / Live Data

Historical: deterministic replay, coverage inspection, gap detection, DatasetSnapshot creation, warm-up validation, timeframe aggregation. Idempotent ingestion. Live: provider connection, normalized updates, bar formation, completed-bar emission, reconnect recovery, stale-data detection. Do not allow live-provider quirks to alter canonical completed-bar semantics.

## Live / Historical Parity

A 15m candle built during live PAPER must have same semantic boundaries as the equivalent candle reconstructed from historical base data. If a provider's live and historical data differ, surface the discrepancy rather than pretending they are identical.

## Market Data Freshness / Missing Data

Active Deployments distinguish healthy/stale/disconnected. Stale/uncertain data → new exposure blocked. Existing broker-hosted protection remains authoritative. Safety: [Safety Model](safety-model.md). Never forward-fill missing OHLC bars. Classify gaps as expected market closure vs unexpected data gap. Forex weekend closure ≠ data failure.

## Gap / Out-of-Order / Duplicate / Correction Behavior

Material unexpected gap → Experiment reject or explicitly warn. Out-of-order data: normalize timestamps, handle duplicates idempotently, reconcile safely before bar is canonical. Same provider observation must not create duplicate canonical records or duplicate evaluations. Provider data corrections after completed Experiment → new DatasetSnapshot/fingerprint; completed Experiment provenance must not silently change.

## DatasetSnapshot Relationship

Identifies exact historical market-data view for an Experiment. Captures: Instrument, provider, base resolution, price components, coverage, alignment, data fingerprint, integrity metadata. See: [Domain Model](domain-model.md), [Historical Data](../features/historical-data.md).

## Warm-Up

Market-data validation must account for Strategy warm-up requirements. Warm-up bars may initialize indicators/state but must not create trading exposure.

## Execution Simulation Resolution

Strategy resolution and simulation resolution are separate. Reference: Strategy 15m, execution simulation 1m. The Strategy should not be aware of the simulation resolution.

## Intrabar Uncertainty

OHLC data does not provide exact tick sequence. If simulation cannot determine whether stop or target occurred first: adverse outcome first for Atlas v1. Experiment must record the ambiguity. See: [Experiments](../features/experiments.md).

## Volume / Numeric Precision

Provider volume persisted where supplied; not required for initial Strategy. Prices use decimal-safe representations; no binary floating-point for authoritative financial values. Storage rules: [Database](database.md).

## Performance

Correctness before optimization. Do not add Redis cache, specialized time-series DB, distributed streaming, persisted copies of every derived timeframe without measured need. Initial Forex data manageable in PostgreSQL.

## Required Tests

At minimum test: UTC normalization, start/end timestamp semantics, 1m bar completion, deterministic 1m→15m aggregation, exact 15m boundary alignment, no incomplete bar reaches Strategy, no future bar reaches Strategy, signal interval not reused as post-decision data, MID/BID/ASK normalization, duplicate ingestion, out-of-order input handling, missing-data detection, weekend closure classification, warm-up coverage, live/historical aggregation parity, DatasetSnapshot fingerprint change on data change.

## Success Criteria

Proven when Atlas can: load EUR/USD 1m data → normalize MID/BID/ASK → construct deterministic completed 15m bars → expose only info available at time frontier → run Strategy evaluation → use only post-decision executable data for fills — with same candle semantics for historical and live trading.
