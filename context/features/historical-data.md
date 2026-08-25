# Historical Data

## Purpose

Trustworthy market data for deterministic Experiments. Initial: OANDA, EUR/USD, 1m stored base resolution, 15m Strategy resolution, MID analysis price. Historical data must be reproducible, inspectable, free from silent data repair. Canonical semantics: [Market Data Model](../architecture/market-data-model.md).

## Initial Source / Instrument Mapping

OANDA as initial Forex data provider. OANDA-specific (symbols, requests, pagination, responses, limitations) inside OANDA adapter. Core Atlas operates on canonical types. EUR/USD → OANDA EUR_USD mapping via VenueInstrument.

## Base Resolution / Price Components / Candle Model

Persist at 1m; higher timeframes derived deterministically. Do not download separate 15m history. Preserve MID, BID, ASK. MID for analysis; ASK for buys, BID for sells for simulated execution. Do not approximate spread from constant when actual BID/ASK available. Canonical bars: Instrument, provider, resolution, timestamp, OHLC, price components, completion/provenance. Provider response objects not in Strategy code. Only completed candles enter canonical data.

## UTC / Ingestion / Idempotency

All timestamps UTC. Normalize before persistence. Ingestion: request range → fetch OANDA → normalize → validate → persist idempotently → coverage/integrity. No distributed pipeline. Same period repeatedly must not create duplicates — enforce via DB uniqueness. Incremental: determine existing coverage before requesting; do not redownload complete datasets unnecessarily.

## Provider Pagination / Coverage / Warm-Up

Adapter responsible for provider request limits, pagination, rate limits, response behavior. Not in generic market-data logic. Coverage answers: enough valid data for this Experiment? Considers requested period + warm-up + resolution + price components + gaps. Warm-up: prior completed bars for indicator initialization; not producing Trades before requested period. Warm-up requirements declared by StrategyVersion.

## Gap Detection / Policy / No Forward Filling

Detect missing observations. Distinguish expected closure vs unexpected gap. Material unexpected gaps → block Experiment unless policy explicitly permits. UI explains what's missing. Never synthesize candles by forward-filling. Expected closed-market periods via market-session semantics, not fabricated candles.

## 15-Minute Aggregation / Incomplete / Deterministic

1m→15m follows [Market Data Model](../architecture/market-data-model.md): half-open [start, end) intervals. Open = first open, high = max high, low = min low, close = last close. Never cross boundaries. Do not create completed 15m bar when constituent data unexpectedly incomplete. Same canonical 1m → same 15m always. Same aggregation for historic and live — no separate Experiment vs PAPER definitions.

## DatasetSnapshot / Fingerprint / Provider Corrections

DatasetSnapshot identifies exact data view. Provenance: [Domain Model](../architecture/domain-model.md). Fingerprint changes when relevant data changes. Purpose: answer if Experiments used same data. May use deterministic hashing. Provider corrections → new fingerprint; old Experiment retains original provenance.

## Data Screen / Load Data Flow / Experiment Integration

Simple Data page: EUR/USD, OANDA, 1m, MID/BID/ASK, Coverage, Integrity, Last Updated. Actions: Load Data, Update Data, Inspect Coverage. User chooses date range → inspect coverage → identify missing → fetch OANDA → validate → persist → refresh. Before Experiment: validate StrategyVersion requirements + dates + warm-up + coverage + price components + integrity. Validation failure blocks Experiment.

## Bounded Load Command / Lifecycle

Experiment setup exposes one narrow "Load missing historical data" action for EUR/USD OANDA Practice M1 MID/BID/ASK. A POST commits a durable `historical_data_load_requests` row in `PENDING`, then an in-process coordinator runs `PENDING -> RUNNING -> COMPLETED|FAILED`. It is a bounded command, not a generic Job/worker/queue. Only one request is active at a time (enforced by a DB partial unique index). An interrupted request left by a prior process is failed at startup (`LOAD_INTERRUPTED_BEFORE_START` for `PENDING`, `LOAD_INTERRUPTED` for `RUNNING`); it is never resumed or auto-reissued. Retry is an explicit user action that creates a new row.

**Server-only OANDA boundary:** the Practice credential is composed server-side only; it is never in a client bundle, HTTP payload, URL, log, or durable diagnostic. If no server token is configured the app still starts but `POST` returns `503` and creates no row; an invalid configured credential yields a terminal `MARKET_DATA / OANDA_AUTHORIZATION_FAILED` without provider text.

**Retry interpretation:** "no automatic retry" means Atlas never reissues, resumes, or loops a failed load command. The OANDA adapter's existing bounded transport behavior (at most three attempts for connection failures and 429/5xx, finite timeouts, `Retry-After` capped at 30 seconds) stays inside one request window. One accepted command is therefore at most 40 provider windows and 120 HTTP attempts. Retry after a terminal failure is an explicit user command that creates a new request.

## Errors / Performance / Data Retention

Actionable errors: "EUR/USD history missing between dates. Load or repair." Avoid "Dataset invalid." Batch inserts, appropriate indexes, bounded requests, efficient range queries. No TimescaleDB, ClickHouse, Redis cache, data lake, distributed ingestion without measured need. Retain historical data for reproducibility and future Experiments.

## Non-Goals

No multiple providers, crypto history, tick/order-book history, alternate data, data marketplace, CSV import, charting-terminal tools, provider failover, separate persistence for every derived timeframe.

## Required Tests

OANDA→canonical normalization, UTC handling, completed-candle filtering, MID/BID/ASK preservation, duplicate/incremental ingestion, coverage calculation, warm-up coverage, expected closure handling, unexpected gap detection, no forward filling, 1m→15m alignment and OHLC aggregation, incomplete aggregation rejection, deterministic aggregation, DatasetSnapshot creation, fingerprint stability and change after correction, Experiment blocked on insufficient data.

## Acceptance Flow

Open Data → EUR/USD coverage displayed → request period → Atlas determines missing → OANDA loaded → canonical 1m MID/BID/ASK persisted → integrity validated → 15m bars derive deterministically → DatasetSnapshot available → Experiment data validation passes.

Durable setup flow: Experiment setup → enter labelled UTC 15-minute bounds → "Load missing historical data" → durable `PENDING` → RUNNING → bounded M1 load → coverage recomputed → immutable DatasetSnapshot created/reused → M15 MID derived from snapshot membership → Experiment coverage validated → COMPLETED → snapshot auto-selected and coverage auto-validated → Experiment creation enabled. A partial/failed/interrupted load stays inspectable and never enables creation.

## Success Criteria

Reliably: request EUR/USD period → determine missing → load only required OANDA → store without duplicates → detect integrity problems → derive deterministic 15m bars → identify exact data used by Experiment — without a generalized market-data platform.
