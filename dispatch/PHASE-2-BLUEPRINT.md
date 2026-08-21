# Implementation Blueprint — Phase 2 Historical Data to DatasetSnapshot

**Blueprint ready.** This document is the authoritative implementation contract for Phase 2. Builders must not change a boundary or material decision below without stopping and returning the conflict to the orchestrator.

## Outcome

Build the narrow backend capability that proves the Phase 2 roadmap exit criterion:

1. map canonical EUR/USD to OANDA `EUR_USD`;
2. retrieve bounded OANDA Practice M1 candles with MID, BID, and ASK;
3. normalize only completed observations into UTC, decimal-safe canonical bars;
4. persist them idempotently in PostgreSQL while preserving corrected values and old snapshot inputs;
5. report expected closures and unexpected gaps without fabricating data;
6. derive deterministic UTC-aligned 15-minute bars from pinned 1-minute data; and
7. atomically create an immutable, content-fingerprinted `DatasetSnapshot` that identifies the exact bar variants used.

The operational entry point is a small synchronous `atlas-data` CLI over typed application services. This makes the backend slice executable without prematurely adding a Data API or frontend.

### Explicitly out of scope

- Experiment creation/execution, simulation, Risk, Orders, Fills, Trades, and account state.
- Live pricing/streaming, scheduling, background workers, runtime coordination, or automatic correction polling.
- Data API routes, Data UI, WebSockets, or frontend changes. The documented Data screen remains a later delivery over these contracts.
- OANDA account/trading endpoints, OANDA Live, additional providers, instruments, or resolutions.
- Persisted 15-minute bars; they are derived from snapshot members on demand.
- CSV import, provider failover, forward filling, synthetic candles, holiday guessing, generalized calendar/timeframe/plugin frameworks, caches, or a specialized time-series store.
- NumPy/Polars; neither is required for this slice.

## Agreed language

- **Instrument**: canonical Atlas market identity. Phase 2 supports only `EUR/USD`.
- **VenueInstrument**: mapping from `EUR/USD` + provider `OANDA` to provider symbol `EUR_USD`.
- **Canonical Bar**: one completed `[start_time, end_time)` OHLC observation for one Instrument, provider, resolution, and price component. Provider DTOs are not canonical bars.
- **Base resolution**: persisted `1m` bars. `15m` is derived and never downloaded or persisted in Phase 2.
- **Price component**: one of `MID`, `BID`, or `ASK`. A required minute is complete only when all three current components exist and validate.
- **Current bar variant**: the provider value Atlas presently selects for a logical `(VenueInstrument, resolution, component, start_time)` identity. Historical variants remain immutable.
- **Expected closure**: a minute excluded by the versioned OANDA EUR/USD session policy. It is not a gap and no candle is fabricated for it.
- **Unexpected gap**: a session-open minute missing one or more required components. It blocks snapshot creation and later Experiment use.
- **DatasetSnapshot**: an immediately finalized, immutable descriptor plus immutable membership rows pointing to exact persisted bar variants. It is not merely a query over mutable “current” rows.
- **Coverage range**: a UTC, minute-aligned, half-open `[coverage_start, coverage_end)` interval.
- **Decision frontier**: time supplied by Atlas; only bars with `end_time <= frontier` can be Strategy-visible.

## Decisions

### Confirmed

- **Backend-only Phase 2 boundary — confirmed, high confidence.** The roadmap exit criterion can be proven without UI/API work, and the exploration recommends the smallest backend vertical slice. A narrow CLI supplies the executable acceptance flow. This resolves the feature document's broader Data-screen description without deleting or redefining that later product flow.
- **Single synchronous modular-monolith flow — confirmed, high confidence.** Direct typed calls, PostgreSQL, and a synchronous OANDA adapter; no queue, worker, event bus, Redis, or additional process.
- **Canonical scope constants — confirmed, high confidence.** Instrument `EUR/USD`; provider `OANDA`; Practice REST base URL; symbol `EUR_USD`; stored resolution `1m`; components `ASK`, `BID`, `MID`; derived Strategy resolution `15m`; UTC half-open intervals.
- **Completed observations only — confirmed, high confidence.** An OANDA candle with `complete != true`, a future end, missing component data, an off-grid timestamp, invalid Decimal, or invalid OHLC never enters canonical persistence.
- **Snapshot membership pins immutable bar variants — confirmed, high confidence.** A snapshot cannot depend only on a mutable range query. Provider correction selects/inserts a different current variant; old snapshot membership and aggregation remain unchanged.
- **No draft snapshot lifecycle — confirmed, high confidence.** Validation, fingerprinting, snapshot row creation, and membership insertion happen in one DB transaction. Success means finalized; failure creates no snapshot.
- **Correction model — confirmed, high confidence.** `load-missing` fetches only missing expected-open ranges. `refresh` explicitly re-fetches a requested range. Unchanged values are no-ops; changed values become/select a different immutable variant. No automatic correction process is added.
- **Aggregation over snapshot membership — confirmed, high confidence.** Snapshot-based derivation must never query whatever bars happen to be current later.
- **Strategy boundary remains 15m MID — confirmed, high confidence.** Generalizing `Bar` to represent M1 and BID/ASK requires strengthening `StrategyContext` to reject anything except completed, same-Instrument, UTC-aligned M15 MID bars.
- **HTTP client dependency — confirmed, medium confidence.** Promote the already locked/test-used `httpx` package into runtime dependencies for TLS, persistent connections, explicit timeouts, and injectable test transport. Do not add an OANDA SDK.

### Assumed for this slice

- **Session policy `OANDA_FX_NY_V1` — assumed, medium confidence.** Use `zoneinfo.ZoneInfo("America/New_York")`. For EUR/USD, expected closure is the daily `[16:59, 17:05)` New York interval, the weekly interval from Friday 16:59 through Sunday 17:05, and all of Saturday. DST is therefore handled by timezone conversion, not fixed UTC offsets. This matches OANDA's published US FX hours as reviewed on 2026-08-14.
- **Holiday behavior — assumed, high safety confidence.** No public-holiday exception is guessed. A holiday-related absent minute outside `OANDA_FX_NY_V1` is an unexpected gap and blocks a snapshot. This is intentionally conservative.
- **OANDA candle window size — assumed, high confidence.** Use deterministic request windows of at most 4,000 M1 intervals, below OANDA's commonly documented candle limit. Filter normalized results back to the exact requested half-open window so endpoint boundary behavior cannot expand membership.
- **Price storage — assumed, high confidence.** PostgreSQL `NUMERIC(20,10)` and Python `Decimal` are sufficient for the initial EUR/USD source while remaining exact.

### Deferred

- **Holiday/session exception source — deferred, medium confidence.** Before Atlas accepts periods affected by special OANDA holiday hours, introduce a reviewed, versioned policy update; never edit `OANDA_FX_NY_V1` semantics in place.
- **Generalized calendars, resolutions, providers, and instruments — deferred, high confidence.** Add only when a roadmap slice requires them.
- **Data API/UI and persisted load-attempt history — deferred, high confidence.** Phase 2 exposes actionable typed/CLI results and durable coverage facts; it does not add an ingestion-job domain model.
- **Performance partitioning/caching — deferred, high confidence.** Add only after measurement.

No unresolved product decision blocks implementation. Developer approval of this blueprint explicitly ratifies the backend-plus-CLI boundary and conservative holiday behavior.

## Authoritative provider contract

The adapter is based on OANDA v20's published contract reviewed on 2026-08-14:

- `GET /v3/instruments/{instrument}/candles` with Bearer authentication;
- `granularity=M1`, `price=MBA`, `smooth=false`, RFC3339 times;
- Practice base URL `https://api-fxpractice.oanda.com`;
- OANDA candle time is the interval start; `complete` identifies elapsed candles; OHLC values are decimal strings;
- use a persistent client and bounded requests; 429 and transient server/network failures are retryable.

Implementation references: OANDA v20 Instrument OpenAPI (`oanda/v20-openapi`, `v20_instrument.yaml`), OANDA Authentication, Development Guide, Best Practices, and OANDA FX Hours of Operation. If live behavior materially contradicts these semantics, stop and return evidence rather than silently adapting canonical behavior.

## Architecture boundaries and interfaces

### Domain (`backend/domain/market_data.py`, `backend/domain/strategy.py`)

Extend, do not duplicate, the existing canonical types:

- `Instrument`: retain only `EUR_USD = "EUR/USD"`.
- Add canonical provider enum/value `OANDA`.
- `Timeframe`: `M1`, `M15` only.
- `PriceComponent`: `MID`, `BID`, `ASK` only.
- `VenueInstrument`: frozen value containing canonical Instrument, provider, and provider symbol; reject every mapping except the current slice.
- `Bar`: frozen completed canonical value containing Instrument, provider, timeframe, component, UTC start/end, Decimal OHLC, optional non-negative provider volume, and `complete=True`. Validate exact interval length/alignment, positive finite prices, and `low <= open/close <= high`. Preserve explicit JSON serialization with Decimal strings and UTC `Z` timestamps.
- `DatasetSnapshot`: frozen finalized value containing durable ID, VenueInstrument, base resolution, ordered component tuple, coverage range, alignment convention, session-policy version, fingerprint schema/value, integrity summary, and creation time.
- Strengthen `StrategyContext`: every bar must match the context Instrument and must be completed M15 MID; retain strict ordering, uniqueness, and `bar.end_time <= evaluation_time` checks.

Do not introduce provider response models into `backend.domain` and do not add Strategy access to repositories or OANDA.

### Market-data application layer (`backend/market_data/`)

Create only focused modules:

- `session_calendar.py`: versioned `OANDA_FX_NY_V1` minute classification and eligible M15-window logic.
- `coverage.py`: pure coverage and warm-up requirement calculation.
- `aggregation.py`: pure M1→M15 derivation.
- `fingerprint.py`: versioned canonical byte encoding and streaming SHA-256.
- `ingestion.py`: orchestration across source, repositories, coverage, and snapshot creation; no HTTP DTO knowledge.
- `cli.py`: `argparse` composition root and sanitized JSON/text output.

Required typed contracts:

- `HistoricalBarSource.fetch(start, end) -> fetched canonical M1 candle groups + request diagnostics`.
- `MarketDataRepository.ensure_initial_venue_instrument(...)`.
- `MarketDataRepository.current_bars(range, components)` and `missing_ranges(...)`.
- `MarketDataRepository.apply_bar_batch(...) -> inserted/reactivated/unchanged counts`.
- `CoverageValidator.validate(range, required_components) -> CoverageReport`.
- `CoverageValidator.required_range(requested_start, requested_end, warm_up_m15_bars) -> range + report`; count preceding eligible M15 windows, not calendar minutes.
- `DatasetSnapshotRepository.create_validated(...) -> existing-or-new DatasetSnapshot` and `members(snapshot)`.
- `aggregate_snapshot(snapshot, component) -> tuple[Bar, ...]`.

The application service must expose `load_missing`, `refresh_range`, `inspect_coverage`, `create_snapshot`, and `derive_m15`. Each accepts an injected UTC clock/frontier where current time matters. It returns structured reports rather than relying on logs.

### OANDA integration (`backend/integrations/oanda/`)

- Provider DTO parsing, query names, status mapping, and pagination remain inside this package.
- Use one injected/configured synchronous `httpx.Client` per operation, Bearer header, HTTPS Practice allowlist, explicit connect/read timeouts, and persistent connections.
- Request exact deterministic windows with `from`, `to`, `price=MBA`, `granularity=M1`, `smooth=false`, and RFC3339 response format. Do not request OANDA M15.
- Normalize timestamps to UTC, filter to `[requested_start, requested_end)`, sort out-of-order candles, collapse byte/value-identical overlap duplicates, and fail the operation on conflicting duplicates.
- A provider candle is atomic for normalization: all MID/BID/ASK structures must exist and validate. Incomplete candles are not persisted and are reported; malformed complete candles fail the affected fetch rather than being skipped silently.
- Retry this read-only GET on connection errors, timeouts, HTTP 429, and HTTP 5xx with at most three total attempts and bounded deterministic backoff, honoring a sane `Retry-After` cap. Do not retry 400/401/403/404. Exhaustion returns an actionable transient failure.
- A request failure after earlier chunks were committed may leave safe partial coverage. Report the committed range/counts; subsequent coverage remains invalid until repaired. Never hold a DB transaction during an HTTP request.

### CLI boundary

Add the `atlas-data` project script with commands:

- `load-missing --start <UTC> --end <UTC>`
- `refresh --start <UTC> --end <UTC>`
- `coverage --start <UTC> --end <UTC> [--warm-up-bars N]`
- `snapshot --start <UTC> --end <UTC>`
- `derive-m15 --snapshot-fingerprint <sha256> --component <MID|BID|ASK>`

Reject local/naive timestamps and non-minute-aligned or non-positive ranges. Commands emit a stable summary (Instrument/provider/range/counts/gaps/fingerprint), use nonzero exit status for failure, and never print a credential. Raw UUIDs are not normal output labels.

## Migrations and persistence contracts

Add one Alembic revision, `0003_phase_2_market_data`, with `down_revision = "0002_phase_1_strategy"`; update migration-head and schema-cycle tests.

### `instruments`

- UUID PK, canonical `code`, `base_currency`, `quote_currency`, UTC `created_at`.
- Unique canonical code; checks constrain the Phase 2 values to EUR/USD.
- Referenced rows use `ON DELETE RESTRICT`.

### `venue_instruments`

- UUID PK, FK to Instrument, provider, provider symbol, UTC `created_at`.
- Unique `(provider, provider_symbol)` and `(instrument_id, provider)`.
- Checks constrain current values to OANDA/`EUR_USD`.

### `market_bars`

- UUID PK; VenueInstrument FK; resolution; price component; UTC start/end; exact OHLC; nullable non-negative volume; `complete`; lowercase SHA-256 `content_fingerprint`; nullable sanitized `source_request_id`; UTC `retrieved_at`; `is_current` projection flag.
- Checks enforce M1 only, exact one-minute aligned interval, `complete = true`, valid component, finite/positive representable prices, OHLC containment, non-negative volume, and fingerprint shape.
- Unique `(venue_instrument_id, resolution, price_component, start_time, content_fingerprint)` prevents duplicate value variants.
- Partial unique index on `(venue_instrument_id, resolution, price_component, start_time) WHERE is_current` guarantees one logical current value.
- Index current range queries by VenueInstrument/resolution/component/start.
- Content/provenance columns and deletion are immutable by trigger. The trigger permits only `is_current` projection changes. A correction atomically deselects the old current variant and inserts or reactivates the exact fetched variant while holding a row lock on VenueInstrument.
- A repeated identical fetch is a no-op. A change inserts a new immutable variant. A later reversion may reactivate an existing identical variant. Old rows remain available to snapshots.

### `dataset_snapshots`

- UUID PK; VenueInstrument FK; base resolution; ordered JSONB components fixed to `["ASK","BID","MID"]`; UTC coverage start/end; alignment convention `UTC_HALF_OPEN_V1`; session policy `OANDA_FX_NY_V1`; fingerprint schema `ATLAS_DATASET_SHA256_V1`; unique lowercase SHA-256 fingerprint; JSONB integrity summary; UTC `created_at`.
- Checks enforce supported constants, aligned positive range, valid fingerprint, and an integrity status of `VALID`.
- Entire row is UPDATE/DELETE protected by trigger.

### `dataset_snapshot_bars`

- Composite PK `(dataset_snapshot_id, market_bar_id)` with both FKs `ON DELETE RESTRICT`.
- Membership rows are UPDATE/DELETE protected by trigger.
- Snapshot creation locks the VenueInstrument row shared with ingestion, selects exactly one current required component per expected-open minute, validates integrity, computes the fingerprint, inserts/gets the snapshot by fingerprint, and inserts all memberships in the same transaction.

### Integrity summary shape

Persist a small explicit JSON object containing at least: `status`, `expected_open_minutes`, `expected_closure_minutes`, `member_minutes`, `bar_count`, `unexpected_gap_count`, `unexpected_observation_count`, and `session_policy`. Invalid reports are returned to callers but do not create snapshot rows.

## Dataset fingerprint contract

`ATLAS_DATASET_SHA256_V1` is SHA-256 over a streaming sequence of UTF-8 canonical JSON lines, each terminated by `\n`:

1. one header line containing schema, canonical Instrument, provider, provider symbol, base resolution, ordered components, exact UTC coverage start/end, alignment convention, and session-policy version;
2. one line per member ordered by `(start_time ASC, price_component ASC)`, containing component, start/end, normalized Decimal OHLC strings, volume (`null` if absent), and `complete=true`.

Canonical JSON uses sorted keys, separators `(",", ":")`, ASCII-safe encoding, and no floats. UTC is second-precision RFC3339 with `Z`. Decimal canonicalization removes insignificant trailing zeros without exponent notation and normalizes signed zero to `0`. Exclude UUIDs, DB row order, `is_current`, retrieval time, request ID, and content-variant identity. Therefore equal economic data/descriptors produce the same fingerprint; a relevant OHLC/volume/component/range/policy change produces a different fingerprint. Hashing must stream ordered rows rather than materializing the entire dataset.

## Coverage, aggregation, and warm-up rules

- Coverage and requests are minute-aligned UTC half-open ranges whose end does not exceed the injected latest completed-minute frontier.
- For each session-open minute, exactly one current M1 bar for each of ASK/BID/MID is required. Coalesce absent minutes into actionable ranges with missing-component details.
- Expected-closed minutes need no bar. A current observation during a policy-declared closure is an integrity anomaly and blocks snapshot creation; do not silently include or discard it.
- No forward fill, interpolation, constant spread, or synthetic zero-volume bar is permitted.
- A 15-minute interval is aligned on UTC minute `00/15/30/45` and is emitted only when it lies wholly inside snapshot coverage, contains at least one session-open minute, and has every expected-open M1 constituent for the requested component. Scheduled closed minutes require no constituent. Any unexpected missing minute rejects that interval.
- Aggregate open=first, high=max, low=min, close=last, volume=sum when all source volumes are present (otherwise `None`). Output interval remains the full aligned 15 minutes and is completed only after its end frontier.
- Ordering and arithmetic are deterministic Decimal operations. The same snapshot/component must serialize identically on repeated derivation.
- Warm-up range calculation walks backward over eligible aligned M15 windows until the StrategyVersion's declared count is satisfied; closure-only windows do not count. Warm-up data initializes Strategy state only; exposure behavior remains a later phase.

## Safety and failure handling

Every failure report/CLI error must answer: what failed, what Atlas persisted, whether coverage/snapshot is valid, and the next action.

- Missing/incomplete/malformed/conflicting data: persist no malformed canonical row; coverage remains invalid; snapshot creation is blocked with exact ranges/components.
- Provider timeout/429/5xx: bounded retry because the operation is read-only; after exhaustion, report partial committed coverage and instruct retry. Never convert timeout into “no data.”
- 400/404: classify request/mapping error; do not retry. 401/403: classify credential/authorization error; do not retry or reveal provider body/token.
- DB constraint/transaction failure: roll back the current batch/snapshot transaction. Previously committed batches remain valid facts and coverage exposes what is missing.
- Correction during snapshot creation: prevented by the shared VenueInstrument row lock. Snapshot membership and fingerprint reflect one atomic current view.
- Fingerprint collision/descriptor mismatch on an existing fingerprint: treat as integrity failure and stop; never reuse a mismatched snapshot.
- Unknown session/holiday state: fail closed as unexpected gap. Never mark it expected merely to make coverage pass.
- Aggregation gap/anomaly: emit no affected M15 bar and return an actionable integrity error.
- Logging is supplementary. Persistent bars/snapshot membership and returned coverage reports are authoritative; no failure is hidden only in logs.

## Security boundaries

- Add optional `ATLAS_OANDA_API_TOKEN: SecretStr`; absence must not break API/runtime/tests that do not instantiate OANDA. The CLI fails clearly if an OANDA command needs it.
- Add only bounded timeout settings if needed. Keep the base URL an internal HTTPS Practice allowlist constant; do not accept arbitrary CLI/config URLs (SSRF boundary). Tests inject transport instead.
- Token appears only in the Authorization header inside the OANDA integration. Never place it in URLs, DTOs, domain objects, persistence, logs, exception strings, CLI output, fixtures, or snapshots.
- Sanitize/truncate provider error bodies. Request IDs may be persisted/logged only after length/content validation and must not be treated as secrets.
- `.env.example` contains a placeholder, never a real token. `.env` remains untracked and must not be read/copied by agents.
- OANDA DTOs and `httpx` objects do not cross the integration boundary. Core services receive canonical values or sanitized typed failures.
- This slice calls only historical candle endpoints; no account ID, trading endpoint, or order capability is introduced.

## Strict ordered implementation

Each numbered task is a gate. The next task starts only after its tests pass. One implementation writer operates at a time in the approved worktree.

1. **Establish isolation receipt (Worktrees owner).** Create the approved linked worktree/branch described below and record `READY` with root, path, branch, full base SHA, clean status, scope, and recovery. No builder starts without it.
2. **Generalize canonical market-data values without weakening Strategy input (domain owner).** Update `backend/domain/market_data.py`, `backend/domain/strategy.py`, exports, and domain tests. Add M1/M15, all components, provider/VenueInstrument/DatasetSnapshot, generalized Bar validation, and explicit M15 MID `StrategyContext` checks. Gate: existing Strategy suite plus new wrong-component/timeframe/provider/instrument/frontier tests pass.
3. **Implement pure session, coverage, fingerprint, and aggregation rules (market-data owner).** Add the focused `backend/market_data/` modules and deterministic fixtures. Gate: UTC/DST daily break/weekend classification, warm-up calculation, gap coalescing, canonical hash vectors, boundaries, partial scheduled-closure windows, no-forward-fill, and repeatability tests pass without DB/network.
4. **Implement the OANDA historical source boundary (integration owner).** Promote `httpx` in `pyproject.toml`/`uv.lock`; add optional secret/timeouts in config; add `backend/integrations/oanda/` with injectable transport, pagination, normalization, retries, and sanitized failures. Gate: fixture-driven tests cover exact request parameters, >4,000-minute pagination, boundary filtering, all components, incomplete/malformed/out-of-order/duplicate data, status classes, retries, and token non-disclosure.
5. **Add persistence schema and models (persistence owner).** Add Alembic `0003`, SQLAlchemy models, constraints/indexes/triggers, and migration expectations. Gate: upgrade/check/downgrade/upgrade succeeds against the dedicated test DB; all check/unique/FK/immutability/current-row constraints are integration-tested.
6. **Add focused repositories and correction semantics (persistence owner).** Implement initial mapping creation, current-range reads, missing-range support, atomic batch apply under VenueInstrument lock, snapshot create/read, and membership reads. Gate: first load, exact replay no-op, changed correction, reversion, current uniqueness, and concurrent serialization tests pass.
7. **Compose ingestion and snapshot application services (market-data owner).** Ensure network calls occur outside transactions; implement `load_missing`, `refresh_range`, coverage-after reports, atomic snapshot validation/fingerprinting/membership, and idempotent snapshot lookup. Gate: partial provider failure remains inspectable; gap/incomplete/anomaly blocks snapshot; correction changes a new snapshot while the old snapshot remains byte-identical.
8. **Bind snapshot-only M15 derivation (market-data owner).** Read membership, never current heads, and expose deterministic component derivation. Gate: old snapshot derivation remains unchanged after correction; new snapshot changes where source content changed; MID output is accepted by StrategyContext and M1/BID/ASK input is rejected there.
9. **Add the narrow CLI and operator documentation (application owner).** Add `atlas-data`, command parsing/output/exit status, `.env.example` placeholder, and update README from stale Phase 0 wording with Phase 2 setup, safe credential handling, commands, limitations, and validation. Do not add API/frontend routes. Gate: CLI tests use fake source/test DB and never print secrets/raw UUID labels.
10. **Run complete validation and record evidence (validation owner).** Run all gates below, then the opt-in credentialed smoke test. Document exact commands/results for review. Do not commit, push, merge, or clean up unless separately requested and confirmed.

## Validation gates

### Automated gates

- `uv run ruff format --check backend`
- `uv run ruff check backend`
- `uv run pyright backend`
- `uv run pytest -m "not integration and not external"`
- `ATLAS_TEST_DATABASE_URL=<dedicated *_test DB> uv run pytest -m integration`
- `uv run alembic check`
- Existing frontend checks need run only as regression confirmation if dependency/README work changes root tooling; no frontend behavior is in scope.

Register a separate `external` pytest marker. The credentialed OANDA test must be opt-in, use a small operator-supplied closed historical range away from known holiday exceptions, make no account/trading calls, and never be required for normal CI.

### Required behavioral evidence

- Normalization: UTC start/end, exact Decimal values, MID/BID/ASK preserved, incomplete filtered/reported, provider DTO absent from core.
- Idempotency: repeat the same range and prove no duplicate value variants/current bars.
- Incremental load: existing complete minutes are not fetched by `load-missing`; missing ranges are coalesced and bounded.
- Coverage: daily break/weekend are expected closures; a removed session-open minute is an exact unexpected gap; no synthetic row appears.
- Warm-up: N eligible M15 windows are required before requested start and closure-only windows do not count.
- Aggregation: exact UTC alignment/OHLC, expected-closure edge intervals, incomplete rejection, all components, and identical repeated serialization.
- Immutability: SQL UPDATE/DELETE of bar content, snapshots, and membership fails; only the current projection may switch.
- Correction: explicit refresh changes/selects a variant, old snapshot members/derived bytes remain unchanged, and a new snapshot fingerprint changes when relevant content changes.
- Snapshot: creation is atomic, invalid coverage creates no row/membership, identical valid data returns the same fingerprint/snapshot, and fingerprint hash vectors are stable.
- Security: missing/invalid credential errors are sanitized; token is absent from captured logs, exceptions, output, DB, and snapshots.

### Phase 2 acceptance gate

On a freshly migrated database and with an opt-in OANDA Practice token:

1. `load-missing` a bounded historical EUR/USD period; prove completed M1 MID/BID/ASK persistence and valid coverage.
2. Repeat it; prove no new bar variants and no duplicate logical current bars.
3. Derive M15 MID twice and compare canonical serialized bytes/fingerprint; they must be identical and correctly aligned.
4. Create a DatasetSnapshot and verify member count, `VALID` integrity, immutable membership, and stable fingerprint.
5. Using deterministic provider fixtures, remove a required minute and prove coverage/snapshot failure with an actionable range; restore it without forward fill.
6. Using a correction fixture, refresh one value and prove the new snapshot fingerprint differs while the old snapshot derivation remains unchanged.

Only after all six pass is Phase 2 complete and Phase 3 eligible to begin.

## Worktree isolation requirements

- Proposed linked worktree cwd: `/Users/vike/Desktop/atlas-phase-2-historical-data`.
- Proposed branch: `feature/phase-2-historical-data` from the full SHA recorded at approval time.
- The `worktrees` skill must present exact operations and receive confirmation immediately before every Git-mutating command. This blueprint is not Git authorization.
- The `READY` receipt must record repository root `/Users/vike/Desktop/atlas`, worktree path, branch, full base SHA, clean status, allowed scope, and recovery steps.
- Allowed implementation scope: `backend/domain/`, new `backend/market_data/`, new `backend/integrations/oanda/`, `backend/persistence/`, `backend/tests/`, `backend/config.py`, `pyproject.toml`, `uv.lock`, `.env.example`, and `README.md`.
- Forbidden without blueprint revision: `frontend/`, API/runtime behavior, Experiment/Risk/execution code, unrelated context, infrastructure, dependency families, or dispatch history.
- Sequential writers only. Reviewers may be parallel only when read-only. A material contract conflict stops the build and returns to the orchestrator.
- No automatic commit, push, merge, rebase, worktree cleanup, or branch deletion is authorized.

## Rollback implications

- Application rollback to Phase 1 after schema upgrade is operationally possible because the new tables are additive and the OANDA token is optional; Phase 1 will ignore Phase 2 data.
- Alembic downgrade of `0003` is destructive: it removes all Instruments, mappings, bar variants, snapshots, and membership. Permit it only in disposable development/test databases or after explicit backup and approval.
- Once any later Experiment references a DatasetSnapshot, production downgrade is forbidden; preserve provenance and roll forward instead.
- Never “rollback” a provider correction by updating/deleting a bar. Refresh to the desired provider value (which inserts/reactivates a variant) and create/use the appropriate snapshot.
- Changing fingerprint/session semantics requires new version identifiers (`ATLAS_DATASET_SHA256_V2`, `OANDA_FX_NY_V2`), not in-place reinterpretation. Old snapshots remain readable under V1.

## Approval gate

The developer must explicitly approve this blueprint and the proposed worktree workflow before implementation. Approval must include acceptance of: backend-plus-CLI scope, `OANDA_FX_NY_V1` with unknown holidays failing closed, immutable snapshot membership, append/select correction behavior, and the proposed worktree isolation. Approval still does not authorize any Git mutation.
