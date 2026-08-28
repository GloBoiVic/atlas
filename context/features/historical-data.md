# Historical Data

## Purpose

Trustworthy market data for deterministic Experiments. Initial: OANDA EUR/USD, provider-native M15 MID for analysis, and provider-native M1 BID/ASK for sparse execution. Historical data must be reproducible, inspectable, and free from silent data repair. Canonical semantics: [Market Data Model](../architecture/market-data-model.md).

## Initial Source / Instrument Mapping

OANDA as initial Forex data provider. OANDA-specific (symbols, requests, pagination, responses, limitations) inside OANDA adapter. Core Atlas operates on canonical types. EUR/USD → OANDA EUR_USD mapping via VenueInstrument.

## Base Resolution / Price Components / Candle Model

Persist provider-native M15 MID and M1 BID/ASK products separately. Do not derive M15 analytical candles from M1 in the authoritative Experiment path. M1 BID/ASK observations may be sparse, but a missing execution observation is explicit and never fabricated. Preserve price components and provenance; MID is for analysis, ASK for buys, and BID for sells. Only completed observations enter canonical data.

## UTC / Ingestion / Idempotency

All timestamps UTC. Normalize before persistence. Ingestion: request range → fetch OANDA → normalize → validate → persist idempotently → coverage/integrity. No distributed pipeline. Same period repeatedly must not create duplicates — enforce via DB uniqueness. Incremental: determine existing coverage before requesting; do not redownload complete datasets unnecessarily.

## Provider Pagination / Coverage / Warm-Up

Adapter responsible for provider request limits, pagination, rate limits, response behavior. Not in generic market-data logic. Coverage answers: enough valid data for this Experiment? Considers requested period + warm-up + resolution + price components + gaps. Warm-up: prior completed bars for indicator initialization; not producing Trades before requested period. Warm-up requirements declared by StrategyVersion.

## Gap Detection / Policy / No Forward Filling

Detect missing observations. Distinguish expected closure vs unexpected gap. Material unexpected gaps → block Experiment unless policy explicitly permits. UI explains what's missing. Never synthesize candles by forward-filling. Expected closed-market periods via market-session semantics, not fabricated candles.

## Derived Timeframes / Incomplete / Deterministic

Any future derived timeframe follows [Market Data Model](../architecture/market-data-model.md): half-open intervals and completed constituents only. This is not the current authoritative M15 acquisition path; native M15 MID remains strict and cannot be replaced by M1 aggregation.

## DatasetSnapshot / Fingerprint / Provider Corrections

DatasetSnapshot identifies exact data view. Provenance: [Domain Model](../architecture/domain-model.md). Fingerprint changes when relevant data changes. Purpose: answer if Experiments used same data. May use deterministic hashing. Provider corrections → new fingerprint; old Experiment retains original provenance.

## Data Screen / Load Data Flow / Experiment Integration

Simple Data page: EUR/USD, OANDA, native M15 MID plus sparse native M1 BID/ASK, Coverage, Integrity, Last Updated. Actions: Load Data, Update Data, Inspect Coverage. User chooses date range → inspect coverage → identify missing → fetch OANDA → validate → persist → refresh. Before Experiment: validate StrategyVersion requirements + dates + warm-up + coverage + price components + integrity. Validation failure blocks Experiment.

## Bounded Load Command / Lifecycle

Experiment setup exposes one narrow "Load missing historical data" action for EUR/USD OANDA Practice native M15 MID plus sparse native M1 BID/ASK. A POST commits a durable `historical_data_load_requests` row in `PENDING`, then an in-process coordinator runs `PENDING -> RUNNING -> COMPLETED|FAILED`. It is a bounded command, not a generic Job/worker/queue. Only one request is active at a time (enforced by a DB partial unique index). An interrupted `PENDING`/`RUNNING` request remains inspectable and may be explicitly resumed only after durable successful acquisition-window coverage and canonical rows are recomputed; successful windows are not reissued merely for sparse or empty results, and no second active request is created. Retry/resume is an explicit coordinator action, not automatic startup recovery.

**Server-only OANDA boundary:** the Practice credential is composed server-side only; it is never in a client bundle, HTTP payload, URL, log, or durable diagnostic. If no server token is configured the app still starts but `POST` returns `503` and creates no row; an invalid configured credential yields a terminal `MARKET_DATA / OANDA_AUTHORIZATION_FAILED` without provider text.

**Retry interpretation:** "no automatic retry" means Atlas never reissues, resumes, or loops a failed load command. The OANDA adapter's existing bounded transport behavior (at most three attempts for connection failures and 429/5xx, finite timeouts, `Retry-After` capped at 30 seconds) stays inside one request window. One accepted command is therefore at most 40 provider windows and 120 HTTP attempts. Retry after a terminal failure is an explicit user command that creates a new request.

## Errors / Performance / Data Retention

Actionable errors: "EUR/USD history missing between dates. Load or repair." Avoid "Dataset invalid." Batch inserts, appropriate indexes, bounded requests, efficient range queries. No TimescaleDB, ClickHouse, Redis cache, data lake, distributed ingestion without measured need. Retain historical data for reproducibility and future Experiments.

## Non-Goals

No multiple providers, crypto history, tick/order-book history, alternate data, data marketplace, CSV import, charting-terminal tools, provider failover, separate persistence for every derived timeframe.

## Required Tests

OANDA→canonical normalization, UTC handling, completed-observation filtering, MID/BID/ASK preservation, duplicate/incremental ingestion, independent native-product coverage, warm-up coverage, expected closure handling, unexpected gap detection, no forward filling, strict native M15 validation, sparse M1 handling, DatasetSnapshot creation, fingerprint stability and change after correction, Experiment blocked on insufficient data.

## Acceptance Flow

Open Data → EUR/USD coverage displayed → request period → Atlas determines missing native M15 MID and sparse native M1 BID/ASK coverage → OANDA loaded → canonical products persisted → integrity validated → immutable DatasetSnapshot available → Experiment data validation passes.

Durable setup flow: Experiment setup → enter labelled UTC 15-minute bounds → "Load missing historical data" → durable `PENDING` → RUNNING → independently planned bounded native M15 MID and M1 BID/ASK loads → coverage recomputed → immutable DatasetSnapshot created/reused → Experiment coverage validated → COMPLETED → snapshot auto-selected and coverage auto-validated → Experiment creation enabled. A partial/failed/interrupted load stays inspectable and never enables creation.

## Success Criteria

Reliably: request EUR/USD period → determine missing native M15 MID and sparse native M1 BID/ASK coverage → load only required OANDA products → store without duplicates → detect integrity problems → identify exact data used by Experiment — without a generalized market-data platform.
