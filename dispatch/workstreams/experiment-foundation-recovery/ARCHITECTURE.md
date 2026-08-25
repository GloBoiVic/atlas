# Implementation Blueprint — Experiment Foundation Recovery

## Outcome

Recover the V2-only Experiment vertical slice for EUR/USD/OANDA Practice: one authoritative Strategy market-data requirement, deterministic native M15 analysis plus sparse M1 BID/ASK execution, explicit execution-gap outcomes, and result provenance that matches the execution model. A completed result must never imply that missing executable observations were a valid no-trade outcome.

Out of scope: new brokers/instruments, LIVE trading, a generalized data/event framework, and UI analytics beyond V2 provenance and state disclosures. V1 creation, running, persistence/table compatibility, and legacy UI semantics are not retained where disposable; completed V1 data is not a supported input to this slice.

## Agreed language

- **V2 snapshot**: the sole current immutable native M15 MID analytical membership plus immutable sparse M1 BID/ASK execution membership.
- **Execution gap**: an absent required executable observation, distinct from an expected sparse feed interval and from a missing native analytical bar.
- **Decision frontier**: completed M15 `end_time`; the bounded entry window is the immediately following complete 1-minute interval `[frontier, frontier + 1 minute)`.
- **Gap outcome**: an explicit persisted diagnostic/decision, never a silently omitted decision or fabricated fill.

## Decisions

- **Authoritative requirements — confirmed direction, implementation decision**: `requirement_for_version()` is the single source for analytical instrument/timeframe/component, `required_historical_context_bars`, and execution requirements. Loader planning, V2 coverage, clock construction, and `StrategyContext` validation consume it; retain EUR/USD/OANDA boundary validation at the edges. Remove `warm_up_bars` as a canonical persisted concept; if a transitional read is unavoidable during the clean migration/reset, map it once at the boundary and never persist or propagate it as a domain field.

- **Bounded sparse execution policy — recommended smallest current policy**: every eligible native M15 frontier is evaluated independently exactly once. For each frontier, entry may use only the complete BID+ASK observation whose `start_time == frontier` in the immediately following 1-minute bucket `[frontier, frontier + 1 minute)`; there is no search or eventual execution in later minutes, and an observation cannot satisfy two frontiers. If that bucket lacks a complete executable observation, persist `EXECUTION_DATA_UNAVAILABLE` for that frontier and mark the completed result `DEGRADED` when terminal facts remain determinable (never a normal clean zero-trade conclusion). Protection is a separate chronological safety process: once a position exists, inspect each available complete executable observation after entry through the experiment end; if sparse data cannot establish the terminal protected outcome, fail with a persisted execution-data failure rather than inventing an exit. Sparse intervals while flat that cannot affect any frontier remain non-blocking diagnostics. This is the narrowest deterministic policy consistent with the current 1m execution model.

- **Protection across sparse gaps — recommended**: protection is checked on every available executable observation after entry, in chronological order. A missing observation cannot trigger a fill. If the remaining sparse membership cannot establish a terminal protected outcome, terminal validation fails closed. Entry and protection on the same available observation retain the current ordering: entry Fill first, then protection.

- **V1 removal boundary — confirmed task amendment**: V2 is the sole current historical Experiment architecture. Remove V1 creation, run dispatch, V1-only persistence/table models and compatibility where disposable; preserve only reusable V2/shared code and tests. A clean migration baseline/database reset is acceptable, so do not spend scope on reading or translating V1 rows. If an artifact is genuinely shared, retain it only after V2 tests demonstrate that it has no V1 semantic branch.

- **Model/result alignment — recommended**: assign V2 a distinct immutable model version (for example `PHASE5_HISTORICAL_EXECUTION_V2`) and result schema version 2; keep metric schema version unchanged unless metric semantics change. Persist the same V2 model label from configuration through runner and result provenance.

- **Result quality — recommended**: expose a persisted quality/state derived from gap decisions (`DETERMINED` only when no material gap affects outcome; `DEGRADED` when execution availability affects possible decisions while terminal facts remain determinable; failed/unfinished Experiments have no trustworthy result). The UI must display quality and affected gap counts next to assumptions.

- **No hidden broker semantics — confirmed**: this is historical simulation only. OANDA source models remain behind the adapter; no credentials or provider selector enters Experiment configuration.

## Constraints and risks

- Completed Experiment inputs, facts, and results are immutable. New model/schema labels must not mutate old rows; migrations are additive and backward-readable.
- Native M15 membership is the only analytical source. Never re-aggregate current M1 rows or consult mutable bar heads after snapshot creation.
- BID/ASK execution is sparse by design; do not apply legacy full-component wall-clock validation to V2. Validate native analytical completeness and explicit executable availability at each affected decision/protection frontier.
- No lookahead: signal-bar data is never reused as execution data; all timestamps are UTC and all fills use executable sides.
- A missing executable observation must not become a rejected order, assumed fill, invented exit, or silent no-trade. Unknown terminal financial state blocks completion.
- Scope is the current checkout `/Users/vike/Desktop/atlas`; implementation cwd/branch/isolation is not established by this blueprint. Builders may start only after the orchestrator records the required READY receipt and human workflow approval. The exact owned blueprint path is `dispatch/workstreams/experiment-foundation-recovery/ARCHITECTURE.md`.
- Real OANDA verification is external-credential work. Keep it separate from deterministic tests, never log secrets, and use an OANDA Practice account only.

## Ordered implementation

1. **Requirement contract (backend/domain; owner: domain/market-data implementation)** — extend the existing `StrategyMarketDataRequirement` value object only as needed to represent analytical and executable requirements, `required_historical_context_bars`, and gap policy. Thread it through `backend/domain/strategy.py`, `backend/domain/strategy_requirements.py`, loader planning (`backend/market_data/historical_load.py`), `backend/market_data/ingestion.py`, and `backend/experiments/configuration.py`. Remove `warm_up_bars` from the persisted/domain contract and preserve Strategy state immutability.
2. **V2-only acquisition and persistence (backend/market_data + persistence; owner: market-data/persistence)** — keep `load_v2()` native-M15 plus sparse-M1 acquisition; make persisted execution membership/gap facts sufficient to diagnose per-minute BID/ASK completeness without requiring a current-row query. Remove disposable V1 snapshot/Experiment tables, mappings, migration branches, and compatibility paths; retain only reusable V2/shared persistence. A clean migration baseline/reset may replace legacy migration history in the test/development database. Ensure fingerprints include ordered analytical members, execution members, and gap diagnostics.
3. **Coverage and clock semantics (backend/experiments/clock.py, backend/experiments/configuration.py; owner: experiments)** — define the exact bounded entry lookup as the single immediately following 1-minute bucket `[frontier, frontier + 1 minute)`, with no later fallback and no cross-frontier reuse. Reject malformed/duplicate members, distinguish expected sparse absence from a material gap, and expose diagnostics to the caller. Every native analytical frontier must still produce one independent evaluation record, including when its entry bucket is unavailable.
4. **Runner and terminal accounting (backend/experiments/runner.py; owner: experiments/execution)** — update `_run_v2()` to evaluate each native frontier once, use only its bounded entry bucket, persist explicit gap decisions, and check protection chronologically on observations after an actual entry. Keep canonical TradeIntent → RiskDecision → Order → Fill → Position → Trade flow, BID/ASK valuation, adverse-first ambiguity, and end-of-Experiment close. Make terminal validation fail closed for an open position whose protection outcome is unknowable; set result quality and gap counts from persisted facts.
5. **Lifecycle/version provenance (backend/experiments/lifecycle.py, persistence experiment/result repositories/models; owner: experiments/persistence)** — carry V2 model and result versions through create/run/complete paths. Preserve durable RUNNING claims, sanitized failure diagnostics, idempotent commands, and completed-only result publication. Add repository reads for quality/gap diagnostics without exposing raw UUIDs as normal labels.
6. **API contract (backend/api/experiments.py and relevant schemas/services; owner: API)** — configuration/coverage/create/run endpoints must use V2 semantics, return explicit gap diagnostics and model/version provenance, and refuse creation when analytical validation or required terminal prerequisites fail. Keep failed results unavailable as trustworthy output.
7. **Frontend disclosure (frontend/components/experiment-workflow.tsx and result views; owner: frontend)** — render only V2 proof/coverage copy: “native M15 MID + sparse M1 BID/ASK”, the one-minute bounded post-frontier policy, durable load status, execution-gap quality, affected count, and financing/execution assumptions. Do not reimplement Strategy detection or recalculate immutable results from current defaults.
8. **Remove V1 surface (backend/experiments, market-data, persistence, API, tests; owner: experiments/API/persistence)** — delete disposable V1 creation/run/persistence/table compatibility and stale branches after V2 parity tests pass. Preserve only reusable V2/shared code and tests; add guards proving new work cannot route through V1.

## Migrations / reset / rollback

- Use a clean V2 migration baseline/reset where disposable V1 tables and migration compatibility would otherwise remain. Add a migration only when needed for V2 model/result version or result quality. Do not backfill or reinterpret V1 rows; no V1 compatibility schema is a requirement. Preserve the V2 snapshot trigger and constraints in the resulting head.
- Add constraints only for facts guaranteed for both old and new rows; enforce per-frontier execution policy in application/domain validation where sparse membership is intentionally incomplete.
- For development/test recovery, reset the `_test` database, run migrations from a clean head, and seed V2 native/sparse fixtures. Do not reset a credentialed/shared database.
- Rollback is code rollback plus forward-compatible V2 migration handling; do not downgrade by deleting immutable V2 rows. A V2 run must fail safely if its version is unsupported rather than being interpreted as another architecture.

## Validation

- Unit tests: requirement propagation with `required_historical_context_bars`; rejection/absence of persisted `warm_up_bars`; UTC/frontier ordering; native M15 completeness; sparse BID+ASK grouping; exact one-minute entry-window selection; later observation is not selected; missing bounded post-decision observation produces an explicit gap; every analytical frontier is independently evaluated; no cross-frontier reuse; open-position protection through sparse gaps; same-observation entry then protection; no duplicate evaluation; no lookahead; immutable membership/fingerprint.
- Integration tests: load → snapshot → M15 validation → V2-only create gating; V2 create/run lifecycle and durable failure; deterministic replay; long/short executable-side fills; ambiguity and end close; zero-trade versus degraded execution-gap result; disposable V1 tables/creation/run paths are absent and new requests cannot route through V1; clean baseline/reset migration succeeds.
- Result/API/UI tests: completed-only result retrieval; quality and gap disclosure; immutable parameters/provenance; failed and zero-trade states; V2 assumptions and bounded-window copy; no raw UUID identity labels.
- Golden deterministic acceptance: historical EUR/USD 1m MID/BID/ASK → native 15m decision → first post-frontier executable quote → Risk → Order/Fill → protected Position → stop/target → closed Trade → equity/result, for long and short, with identical inputs producing identical facts.
- **Real OANDA UI run (required acceptance gate)**: in the browser UI, select the seeded EMA Sweep Engulfing StrategyVersion, request a valid UTC-aligned range, use “Load missing historical data,” wait for durable `COMPLETED`, confirm V2 native/sparse coverage and assumptions, create and run the Experiment, then inspect the completed result, equity/trades, execution lineage, quality, gap disclosure, and provenance. This run uses OANDA Practice only; capture the run identifier/status and confirm no credential/provider selector is exposed. If historical availability causes a documented gap, the UI must show the explicit degraded/failure outcome rather than a false clean result.
- Run the backend suite with `ATLAS_TEST_DATABASE_URL` ending in `_test`, migration checks, frontend tests, and lint/type checks before review. No implementation is complete until the deterministic golden flow and the real OANDA UI gate both pass or the latter is explicitly recorded as blocked by credentials/environment.

## Assumptions and deferred items

- **Confirmed**: initial scope is EUR/USD, OANDA, OANDA Practice/PAPER, 15m Strategy, 1m base, MID analysis, BID/ASK execution, financing excluded disclosure.
- **Assumed (high confidence)**: an explicit degraded completed result is preferable to silently under-traded output when terminal facts remain determinable; an unknowable open-position outcome is FAILED.
- **Confirmed task amendment**: V2 is the sole current historical Experiment architecture; disposable V1 persistence/table compatibility may be removed and a clean migration baseline/reset is acceptable.
- **Recommended policy (high confidence)**: the immediate following 1-minute bucket is the smallest bounded post-frontier entry window compatible with the current 1m execution model; later quotes are not eventual entry substitutes.
- **Deferred**: generalized broker/instrument requirements, richer gap taxonomies, tick-level ambiguity resolution, financing inclusion, cancellation/resume semantics beyond current lifecycle, and LIVE deployment.
