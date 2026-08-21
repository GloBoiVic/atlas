# Exploration — Phase 2 Historical Data to DatasetSnapshot

## Relevant files
- `AGENTS.md` — initial vertical slice, safety invariants, scope, and testing expectations.
- `context/roadmap/roadmap.md` — Phase 2 goal and exit criterion.
- `context/features/historical-data.md` — ingestion, normalization, coverage, gaps, aggregation, DatasetSnapshot, and stated non-goals.
- `context/architecture/market-data-model.md` — canonical bar semantics, UTC intervals, completion, aggregation, components, gaps, and fingerprints.
- `context/architecture/domain-model.md` — Instrument, VenueInstrument, DatasetSnapshot, Market Bar, and immutability language.
- `context/architecture/database.md` — PostgreSQL, Decimal/UTC, immutable facts, uniqueness, and correction policy.
- `context/architecture/repository-structure.md` — intended `market_data/`, `integrations/`, and persistence boundaries.
- `context/architecture/architecture.md` and `context/architecture/strategy-contract.md` — OANDA normalization parity and Strategy’s completed-canonical-bar boundary.
- `backend/domain/market_data.py` — current Phase 1 15m MID-only Bar contract.
- `backend/persistence/models.py` and `backend/persistence/migrations/versions/0002_phase_1_strategy_persistence.py` — current persistence and immutability-trigger patterns.

## Existing patterns
- Flat `backend.*` package; synchronous SQLAlchemy 2 with PostgreSQL/Alembic and focused repositories.
- Frozen dataclasses, strict runtime validation, UTC-aware timestamps, `Decimal`, and explicit JSON serialization.
- `StrategyVersion` immutability is enforced by a PostgreSQL trigger.
- There is currently no market-data/provider/snapshot implementation, API, or UI workflow.

## Dependencies
- Python 3.13; FastAPI, Pydantic v2, SQLAlchemy 2, Alembic 1, psycopg 3 are available.
- NumPy and Polars are architecture-approved but not declared; no need was established for either.
- No OANDA-specific configuration or technical skill exists in the repository.

## Context gaps
- DatasetSnapshot fields, finalization lifecycle, identity, and fingerprint byte format are conceptual only.
- OANDA component/completeness semantics, pagination/rate limits, correction behavior, and retry/timeout classification require authoritative decisions/documentation.
- Forex closure/session-calendar semantics are required but unspecified.
- Feature document mentions a Data UI flow, while the roadmap and prior phase suggest a backend-focused slice.
- Snapshot membership must be immutable even if provider data later changes; the required persistence shape is not stated.

## Risks
- The current Bar contract rejects 1m/BID/ASK data; Phase 2 must extend data modeling without weakening the Phase 1 Strategy’s 15m MID guarantee.
- A snapshot that only references mutable bar rows can silently change a completed Experiment input.
- Gaps, incomplete observations, and provider corrections must fail visibly and never be fabricated or silently repaired.
- OANDA integration must isolate credentials and classify timeout/unknown outcomes safely.

## Recommendations
- Implement a narrow backend-only vertical slice: EUR/USD, OANDA historical retrieval, completed 1m MID/BID/ASK canonical bars, deterministic 1m-to-15m aggregation, coverage/gap validation, and immutable DatasetSnapshot creation.
- Persist Instrument, VenueInstrument, canonical MarketBar, and DatasetSnapshot facts through a focused Alembic migration/repositories.
- Use standard library plus existing dependencies unless the approved blueprint proves an additional package is necessary.
- Exclude Experiment execution, Risk, Orders, streaming, scheduling, correction automation, UI/API flows, additional markets/providers/resolutions, and generalized timeframe frameworks.
