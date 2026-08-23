# Implementation Blueprint — Phase 5 Experiment Workflow

## Authority and outcome

This blueprint is the implementation authority for the Phase 5 workstream. Builders must follow it sequentially. A material conflict with source, context, or a preceding task stops implementation and returns the issue for blueprint revision; builders must not silently choose a different architecture.

Deliver one trustworthy UI path:

1. choose an existing runnable StrategyVersion and immutable DatasetSnapshot;
2. configure the requested period, capital, Risk, parameters, and the supported simulation controls;
3. validate immutable snapshot coverage including Strategy warm-up;
4. create and run one Experiment with durable status;
5. inspect completed, zero-Trade, or failed state;
6. inspect headline metrics, equity/drawdown, Trades, one Trade's rationale and execution lineage, assumptions, and provenance.

The Phase 4 simulation pipeline remains authoritative. This workstream exposes it; it does not change candle frontiers, execution pricing, Risk, Fill/Position/Trade accounting, stop/target behavior, or reproducibility semantics.

Explicitly out of scope: Experiment comparison, optimization, cancellation, progress percentages, parallel execution, exports, notebooks, report generation, generic charting, PAPER/LIVE behavior, custom Experiment names, arbitrary Strategy loading, WebSockets, Redis, queues, workers, and new analytics beyond the specified primary metrics.

## Agreed language

- **Experiment**: the canonical immutable historical simulation. Never call it a backtest, run, or BacktestResult domain object.
- **Configuration**: the immutable StrategyVersion, DatasetSnapshot, requested period, capital, parameter snapshot, Risk snapshot, simulation snapshot, and engine provenance persisted on an Experiment.
- **Coverage validation**: a read-only eligibility check against exact DatasetSnapshot membership, including all required MID/BID/ASK M1 observations and the StrategyVersion's completed M15 warm-up bars.
- **Result facts**: immutable Fills, completed Trades, costs, and equity history. These remain the authority for derived metrics.
- **Result projection**: the immutable `experiment_results` summary created only when an Experiment completes.
- **Metric state**: an explicit `VALUE`, `INFINITE`, or unavailable reason. The API/UI never substitutes zero for an undefined metric.
- **Trade count**: completed Trade episodes, not intents, Risk decisions, Orders, or Fills.
- **R multiple**: a Trade's net P&L divided by its persisted initial monetary risk.
- **Terminal time**: wall-clock UTC time when Atlas persisted `COMPLETED` or `FAILED`. `completed_market_time` remains the final simulation frontier and is a different value.
- **Opaque identifier**: a UUID used in API links, never rendered as a normal user-facing label.

## Architecture boundaries

- FastAPI owns Pydantic request/response contracts and HTTP translation. Route handlers perform no simulation, metric, or SQL composition logic.
- `backend/experiments/` owns coverage orchestration, create/run lifecycle, deterministic metric calculation, result composition, and immutable chart-context construction.
- Focused persistence repositories own SQL, row locking, bounded list queries, and immutable-fact reads. Do not introduce a generic repository or CRUD framework.
- `ExperimentRunner` remains the simulation orchestration boundary. Phase 5 may call it through a workflow service and may move result-metric calculation to a pure collaborator, but must not fork or duplicate the runner.
- The frontend consumes the FastAPI contract, renders backend-authoritative state, and never recalculates Strategy patterns, trading P&L, metrics, EMA setup identity, or data coverage.
- Next.js uses a same-origin `/atlas-api/*` rewrite to the configured FastAPI base URL. This avoids a second BFF contract and avoids broad CORS. Python/Pydantic remains the only API contract owner.
- PostgreSQL remains the sole durable store. No background job store, cache, broker, or additional database is introduced.

## Decisions

### Configuration and coverage

- The UI accepts only supported controls: StrategyVersion, DatasetSnapshot, UTC period, starting capital, risk per trade, schema-defined Strategy parameters, adverse slippage ticks, and commission per Fill per unit in USD.
- The application, not the browser, constructs the full `PHASE4_RISK_CONFIG_V1` and `PHASE4_SIMULATION_CONFIG_V1` documents. Fixed values remain fixed: M1 execution, MID analysis, BID/ASK execution, embedded spread, EUR/USD tick size `0.00001`, adverse fixed-tick slippage, financing excluded, adverse-first ambiguity, no target improvement, final-eligible-M1 close, and current equity sampling.
- Arbitrary Risk/simulation JSON is not accepted. This prevents unsupported assumptions from entering immutable configuration.
- Strategy parameters are validated against the selected persisted parameter schema and then against the registered implementation. The current fixed EMA Sweep Engulfing values render read-only, but the contract remains schema-driven.
- A StrategyVersion is runnable only when its persisted strategy key, implementation key, and source fingerprint match the explicitly registered local implementation. Unavailable historical versions remain inspectable but cannot start a new Experiment. Do not build dynamic execution from stored source snapshots.
- Coverage validation uses DatasetSnapshot membership without `is_current`; mutable current market-bar heads are forbidden. It validates UTC and 15-minute period alignment, snapshot/venue compatibility, containment of the requested period, complete MID/BID/ASK M1 observations, and at least `warm_up_bars` completed canonical M15 MID bars ending at or before `trading_start`.
- The required coverage start is the start of the earliest selected warm-up M15 bar. The required coverage end is `trading_end`; the interval is half-open. Weekend/session closures are valid absences under the stored session policy. Missing observations are never fabricated.
- Coverage reports return counts and at most the first 100 coalesced gaps/anomalies plus `truncated: true` when needed. Invalid coverage is a normal `200` validation result; Experiment creation repeats validation and rejects invalid input with `409 COVERAGE_INVALID`.
- A valid snapshot and period containing no session-open trading observations may complete with zero Trades. Zero-Trade is not a failure.

### Create and run lifecycle

- Creation and execution are separate backend operations. Creation atomically persists a `PENDING` Experiment plus its USD simulated account and flat Position. A rerun always creates a new Experiment.
- The UI's **Run Experiment** form submits configuration, creates the Experiment, redirects to its detail route with a one-time start instruction, and invokes the run command there. A refresh on a still-`PENDING` Experiment also offers an explicit Run action.
- `POST .../run` is retry-safe and intentionally executes synchronously in the request process; the browser polls status concurrently. Do not introduce FastAPI background tasks or a worker. Polling is the only Phase 5 live-state mechanism.
- Run transaction protocol:
  1. lock the Experiment row; transition `PENDING` to `RUNNING`; commit so status readers can observe it;
  2. open a new transaction, lock the same row `FOR UPDATE`, and hold that transaction through the existing runner;
  3. commit the complete terminal graph atomically.
- The row lock serializes duplicate run commands. A concurrent duplicate waits, then returns the terminal resource without rerunning. A process crash releases the lock and rolls back all uncommitted result facts while leaving durable `RUNNING`; a retry may safely resume only when no run facts exist.
- If a recovered `RUNNING` Experiment already has any committed intent/order/fill/trade/equity/result facts, Atlas does not guess or append. It marks the Experiment `FAILED` with `PERSISTENCE/INCOMPLETE_RUN_STATE` and explains that a new Experiment is required.
- If the runner returns a domain failure, commit its durable `FAILED` state and return the resource normally. If a database/infrastructure exception leaves the transaction unusable, roll back, use a fresh transaction to persist sanitized `PERSISTENCE_FAILURE` when the row is still non-terminal, and return a sanitized HTTP 500 error.
- `completed_at` for new Phase 5 completions is wall-clock UTC and is excluded from reproducibility fingerprints. `completed_market_time` remains `trading_end`. Legacy Phase 4 completed rows whose `completed_at` used market time expose operational terminal time as unavailable rather than relabeling it.
- No progress estimate is invented. UI state is only `PENDING`, `RUNNING`, `COMPLETED`, or `FAILED`.

### Metrics

- One pure deterministic metrics component is used both at completion and to read compatible legacy Phase 4 results. It consumes only the Experiment's immutable Trades and equity points.
- Net return and maximum drawdown retain Phase 4 definitions. Maximum drawdown uses the full canonical equity history, not chart-downsampled data or closed-Trade P&L.
- Profit Factor uses positive and negative **net** Trade outcomes: `sum(net_pnl > 0) / abs(sum(net_pnl < 0))`. If profit is positive and losses are zero, state is `INFINITE`; if both sums are zero, it is unavailable; zero Trades is unavailable.
- Win Rate is winning completed Trades (`net_pnl > 0`) divided by all completed Trades. Break-even Trades remain in the denominator and are not wins. Zero Trades is unavailable.
- Expectancy is average net P&L per completed Trade in USD. Zero Trades is unavailable.
- Sharpe uses UTC daily equity returns: last canonical equity point per UTC date, with the first return measured from starting equity to the first date's final point. Risk-free rate is 0%, annualization is `sqrt(252)`, and sample standard deviation is used. Fewer than two daily returns or zero variance produces an explicit unavailable state, not zero.
- Ratios and money are calculated with Decimal-safe inputs and persisted as PostgreSQL NUMERIC where finite. No `NaN` or numeric infinity crosses persistence or JSON.
- Every metric response is `{state, value, unit, reason}`. Decimal values are canonical decimal strings in JSON. Trade Count is always a value. Failed Experiments expose no result metrics. Zero-Trade results show valid return/drawdown/count and explicit unavailable states for Trade-dependent metrics.

### Result and Trade inspection

- Full result, equity, and Trade endpoints are available only for `COMPLETED`. `PENDING`/`RUNNING` return `409 RESULT_NOT_READY`; `FAILED` returns `409 EXPERIMENT_FAILED`. Partial facts are never presented as trustworthy output.
- Assumptions are mapped from the persisted simulation snapshot, never current defaults. Provenance includes Strategy/StrategyVersion label and source fingerprint, exact parameter snapshot, DatasetSnapshot fingerprint/integrity/coverage, requested period, Risk snapshot, starting capital/base currency, simulation snapshot, engine/model version, result/metric schema versions, output fingerprint, and available timestamps. Exact source files and raw UUID labels are not returned for normal display.
- Equity API data is bounded. If there are at most 2,000 points, return all. Otherwise bucket chronologically and preserve each bucket's first, last, minimum-equity, and maximum-drawdown points (deduplicated and time ordered), capped at 6,000 returned points. Return source count, returned count, and sampling policy `EQUITY_ENVELOPE_V1`. Metrics always use the full series.
- Trade list order is sequence number ascending. URLs and visible labels use the per-Experiment Trade sequence (`Trade 1`), not the Trade UUID.
- Trade detail composes the immutable TradeIntent rationale, both Risk phases, Orders, OrderEvents, Fills, and final Trade. Initial stop/target come from approved PRE_SUBMISSION/protection facts, not the signal close.
- Trade chart context is derived server-side from the Experiment's DatasetSnapshot: canonical M15 MID candles, EMA using the persisted parameter snapshot, rationale timestamps identifying reference/sweep/confirmation candles, and entry/stop/target/exit annotations from execution facts. The browser does no pattern detection.
- Chart context returns at most 500 M15 candles. It preserves setup context (at least EMA period plus 20 preceding bars where available) and the exit neighborhood. For a longer Trade, return bounded setup and exit windows with an explicit omitted-range marker; compute EMA before window selection so displayed values remain canonical.
- Costs show commission and slippage when supported. Spread is disclosed as embedded in BID/ASK and not separately double-counted. Financing is explicitly `FINANCING EXCLUDED`.

## Assumptions

- **Confirmed — high confidence:** Phase 4 behavior and persistence are accepted as complete for this workstream; existing no-lookahead and reproducibility tests are regression gates.
- **Confirmed — high confidence:** Atlas is single-user and initially runs one FastAPI process, one Next.js process, and PostgreSQL. The row-lock protocol remains correct if duplicate HTTP requests occur.
- **Confirmed — high confidence:** EUR/USD, OANDA historical data, M1 base resolution, M15 Strategy resolution, USD base currency, and EMA Sweep Engulfing are the only supported vertical slice.
- **Assumed — medium confidence:** Initial form defaults are USD 10,000 starting capital, 1% risk per Trade, zero adverse slippage ticks, and zero modeled commission. They are editable supported inputs and are always disclosed; they are not hidden engine defaults.
- **Assumed — high confidence:** API and web are deployed behind a trusted single-user boundary; authentication is not added in Phase 5. The API still validates every input, emits no secrets, and the web proxy target is server-side configuration.
- **Deferred — high confidence:** cancellation, durable detached execution, multi-process run ownership, and progress reporting require a later measured requirement. The synchronous row-locked command is the narrow Phase 5 solution.
- **Deferred — high confidence:** legacy metric materialization. Compatible Phase 4 rows are deterministically derived on read without mutating terminal facts; optimize only after measured need.

## HTTP interfaces

All routes are under `/api/v1`. Timestamps are RFC 3339 UTC. Financial values are decimal strings. UUIDs are opaque strings used for linkage only. Errors use `{ "error": { "code", "message", "details" } }`; messages are sanitized and actionable.

### Configuration and lifecycle

- `GET /experiments/configuration-options`
  - Returns runnable/inspectable StrategyVersion summaries, parameter schemas/defaults, snapshot summaries and coverage, fixed simulation assumptions, and form defaults.
- `POST /experiments/coverage-validations`
  - Input: `strategyVersionId`, `datasetSnapshotId`, `tradingStart`, `tradingEnd`.
  - Output: `valid`, requested and required ranges, warm-up requirement/available count, snapshot identity, counts, bounded gaps/anomalies, warnings, and blocking reason codes.
- `POST /experiments`
  - Input: IDs, requested range, starting capital, risk per Trade, parameter values, slippage ticks, and commission amount.
  - Revalidates coverage and compatibility; returns `201` `ExperimentDetail` in `PENDING`.
- `POST /experiments/{experimentId}/run`
  - Retry-safe command. Returns the current/terminal `ExperimentDetail`; domain failures are represented by terminal `FAILED`. Infrastructure failure returns sanitized 500 after best-effort durable failure persistence.
- `GET /experiments?limit=50&cursor=...`
  - Bounded newest-first list, deterministic by `(created_at, id)`, maximum 100. Returns opaque next cursor.
- `GET /experiments/{experimentId}`
  - Returns identity, human label, status/failure, immutable config, assumptions/provenance, and completed headline metrics when available. This is the polling endpoint.

### Results

- `GET /experiments/{experimentId}/equity`
  - Completed only. Returns bounded equity/drawdown points and sampling metadata.
- `GET /experiments/{experimentId}/trades?limit=100&afterSequence=...`
  - Completed only. Returns compact Trade summaries and the next sequence cursor; maximum 250.
- `GET /experiments/{experimentId}/trades/{sequenceNumber}`
  - Completed only. Returns Trade summary, rationale, ambiguity disclosure, costs, progressive execution lineage, and bounded immutable chart context.

### Response rules

- `404`: unknown Experiment or Trade.
- `409 COVERAGE_INVALID`: create attempted with invalid coverage.
- `409 RESULT_NOT_READY`: result subresource requested before completion.
- `409 EXPERIMENT_FAILED`: result subresource requested for failed Experiment; failure detail remains available on Experiment detail.
- `422`: malformed schema/type/range input.
- `500`: sanitized unexpected infrastructure failure. No SQL, path, source, credential, or stack detail crosses the API.

FastAPI OpenAPI generates the frontend TypeScript contract. Do not maintain a parallel handwritten response model. Frontend formatters may wrap generated types but may not redefine their data semantics.

## Persistence and migration

Create one additive Alembic revision after `0006_phase_4_persistence`:

- Add nullable NUMERIC columns to `experiment_results`: `sharpe_ratio`, `profit_factor`, `win_rate`, `expectancy_net_pnl`.
- Add non-null JSONB `metric_states` and a string `metric_schema_version`. Existing rows receive a `LEGACY_UNCOMPUTED` state; they are not updated after migration and are derived on read.
- Add checks: finite NUMERIC values; `profit_factor >= 0`; `0 <= win_rate <= 1`; required metric-state keys; Phase 5 result rows may not use `LEGACY_UNCOMPUTED`; infinity is represented only by metric state with null numeric value.
- Add a deterministic list index on `experiments (created_at DESC, id DESC)`. Existing Trade/equity keys already support sequence/range reads; add no speculative indexes.
- Update SQLAlchemy models and the result creation boundary. A new result schema/metric schema version identifies the methodology. Preserve the Phase 4 output fingerprint over primary semantic facts; metric schema/version is separate provenance.
- Do not add a coverage table, job table, progress table, chart table, custom-name column, or copied market-data table.
- Do not update terminal Experiment graphs in application code. Compatible legacy metrics are calculated transiently from their immutable facts.

Migration rollback may drop only the derived metric cache columns and list index; canonical Trades/equity/results remain. Rolling application code back while the additive migration remains must still permit old result inserts through safe server defaults. Never roll back by deleting Experiments or historical facts.

## Failure handling and security

- Every persistent failure view states: what happened, that no trustworthy full result exists, whether Atlas created exposure (historical only; no broker exposure), and the next action (fix configuration/data or create a new Experiment).
- Coverage failures remain inspectable before creation. Runner failures persist category/code/bounded detail. No failure exists only in a log or toast.
- Failed Experiment configuration/provenance remains readable; partial result cards, charts, and Trades remain hidden.
- Polling/network failure does not change Experiment status. The page shows a persistent “status unavailable” state and retry action; it does not claim failure or completion.
- Run-command timeout is treated as unknown client transport outcome. The client polls the Experiment and may retry the idempotent command; it never creates a replacement automatically.
- Inputs are bounded: list limits, gap detail, date ordering/alignment, decimal precision/ranges, parameter keys, and chart points. Unknown JSON fields are rejected.
- API logs may include Experiment ID and failure code but never exact source snapshots, database credentials, or stack details in responses.
- The Next.js rewrite target is server-side environment configuration, rejects an absent/invalid value at startup/build, and is not rendered in browser configuration.

## UI routes and views

### Application shell

- `/` redirects to `/experiments`.
- Establish the horizontal Atlas navigation and restrained workstation shell. Experiments is active. Future-section labels may be present as clearly disabled navigation, but no fake Dashboard/Deployment/Journal feature pages are created.
- Desktop-first, light neutral theme, visible focus, semantic tables/forms, compact status badges, no sidebar, gradients, tile wall, raw UUID labels, or excessive red/green.

### `/experiments`

- Header: “Experiments”, concise purpose, primary **Run Experiment** action.
- Newest-first compact table: human identity, StrategyVersion, period, status, Net Return, Max Drawdown, Sharpe, Trade Count, created time.
- Non-completed metric cells show `—`, not zero. Failed rows clearly show failure status. Empty state leads to Run Experiment.

### `/experiments/new`

- Focused form groups: methodology/data, requested period, account/Risk, simulation costs/assumptions.
- Coverage panel shows valid range, warm-up, missing data, and blocking actions. Any relevant field edit invalidates the prior validation display.
- Primary **Run Experiment** is enabled only after a successful client-visible validation, but the server always revalidates. Successful create redirects to detail and initiates the retry-safe run command.

### `/experiments/[experimentId]`

- Always show human identity and durable status.
- `PENDING`: configuration summary and Run action.
- `RUNNING`: calm persistent status, no fake percentage; poll every two seconds and stop at terminal state.
- `FAILED`: persistent failure panel with category, safe explanation, configuration, and next action; no metric cards.
- `COMPLETED`: identity/status → seven headline metrics → equity chart → subordinate drawdown chart → Trade table → assumptions → provenance.
- Zero-Trade: explicit “No Trades — Strategy produced no executed Trades during this period,” valid return/drawdown/count, unavailable Trade metrics, empty Trade table without implying failure.
- Ambiguous count is visible near Trades and affected rows are marked “Ambiguous intrabar resolution — Stop-first policy applied.”

### `/experiments/[experimentId]/trades/[sequenceNumber]`

- Header `Trade N` with Experiment/Strategy/Instrument context.
- Summary: direction, times/prices, initial stop, target, exit reason, net P&L, R, costs, ambiguity.
- Lightweight Charts candlestick view with EMA 100, subtle reference/sweep/confirmation emphasis, and entry/stop/target/exit annotations. A disclosed omitted range is visible when bounded windows are used.
- Deterministic Strategy rationale appears as captured at decision time.
- Progressive execution lineage expands TradeIntent → PRE_FLIGHT/PRE_SUBMISSION RiskDecision → Orders/events → Fills → Trade. No internal IDs are normal labels.

Use TradingView Lightweight Charts, minimal shadcn/ui primitives, Lucide icons, and Sonner only for transient request feedback. Persistent status/failure/coverage belongs in the page. Add only the approved stack dependencies needed for these views; do not add a charting or state-management alternative.

## Ordered sequential implementation

1. **Contract fixtures and migration**
   - Add the Alembic revision, SQLAlchemy result fields/checks/index, result/metric schema constants, and migration tests.
   - Define deterministic metric-state vocabulary and pure metric fixtures before wiring UI/API.
   - Validation: upgrade from `0006`, downgrade/upgrade, existing Phase 4 row compatibility, NUMERIC/state constraints, no terminal-fact mutation.

2. **Deterministic metrics boundary**
   - Add the pure Experiment metrics component and use it at completion; persist finite values/states in the result projection.
   - Correct new completion timestamp semantics without placing wall-clock data in the output fingerprint.
   - Validation: net return, full-series max drawdown regression, daily Sharpe/value/insufficient/zero-variance, Profit Factor finite/infinite/empty, Win Rate with break-even, expectancy, zero-Trade, identical inputs/outputs, unchanged Phase 4 trading facts/fingerprint.

3. **Coverage and configuration workflow**
   - Add focused repository reads for StrategyVersion/snapshot options and immutable membership.
   - Add coverage validation and create orchestration that derives fixed Risk/simulation snapshots and atomically seeds account/Position.
   - Add explicit production registration of EMA Sweep Engulfing at application composition; no filesystem access occurs during Strategy evaluation.
   - Validation: warm-up across session closures, gaps/components, range/alignment, incompatible IDs, unavailable source fingerprint, parameter validation, invalid create rejected, valid create is exactly one `PENDING` graph.

4. **Run lifecycle and recovery**
   - Add row-locking/retry-safe run orchestration around the existing runner and fresh-transaction persistence fallback.
   - Keep all simulation facts and terminal result in one run transaction after the visible `RUNNING` claim.
   - Validation: PENDING→RUNNING→COMPLETED/FAILED, status visible during execution, duplicate commands serialize, terminal retry is a no-op, crash-equivalent clean RUNNING retry succeeds, committed partial RUNNING fails closed, infrastructure failure is durable/sanitized.

5. **Result read composition**
   - Add bounded list/detail/equity/Trade queries, compatible legacy metric derivation, provenance/assumption mapping, equity envelope sampling, and immutable Trade chart context.
   - Validation: completed/failed/zero-Trade semantics, immutable snapshots despite corrected current bars, pagination/order, metric values/states, ambiguity, rationale, stop/target, lineage, M15/EMA/annotation correctness, point limits and omitted-range disclosure.

6. **FastAPI contract and composition**
   - Add Pydantic v2 schemas, Experiment router, request-scoped sessions, error mapping, session factory/registry/service wiring, and OpenAPI contract generation.
   - Keep health routes unchanged and app factory dependencies injectable for tests.
   - Validation: every route/status/error listed above, decimal-string and UTC serialization, unknown fields rejected, failure sanitization, no raw source/secret leakage, OpenAPI generation stable.

7. **Frontend foundation and generated client**
   - Add the same-origin API rewrite/config validation, generated TypeScript API types, typed client, minimal shadcn primitives, Sonner host, Lightweight Charts/Lucide dependencies, tokens, and horizontal application shell.
   - Replace the foundation page with the root redirect; do not create adjacent feature pages.
   - Validation: strict typecheck, inaccessible API produces an explicit persistent state, keyboard/focus/contrast checks, no UUID labels, no duplicate handwritten API model.

8. **Experiment list/config/run UI**
   - Build `/experiments` and `/experiments/new`; implement coverage invalidation, create/redirect/start flow, retry-safe command handling, and two-second terminal polling.
   - Validation: list states and metrics, invalid/valid coverage, field-change invalidation, duplicate start effect safety, refresh at PENDING/RUNNING, transport timeout resolved by poll/retry, failed state persistent.

9. **Completed result and Trade detail UI**
   - Build the completed/failed/zero-Trade detail hierarchy, equity/drawdown charts, Trades, assumptions/provenance, and focused Trade detail/chart/lineage.
   - Validation: all acceptance questions can be answered; unavailable/infinite states are accurate; charts resize/clean up; ambiguity and financing disclosures are visible; narrow screens preserve safety/status and scroll tables.

10. **End-to-end regression and documentation alignment**
    - Extend the test harness to start FastAPI and Next.js against a dedicated PostgreSQL test database and deterministic seeded StrategyVersion/DatasetSnapshot. Do not require OANDA credentials or Docker.
    - Prove configure → validate → create/run → observe status → completed result → Trade detail, plus failed coverage, failed Experiment, zero-Trade, and duplicate-run paths.
    - Run all Phase 1–4 deterministic/golden tests unchanged in meaning. Update only implementation-facing documentation/configuration required by this feature; do not rewrite product architecture or this workstream's exploration.

Tasks are sequential. A later task may not compensate for a failed validation gate in an earlier task.

## Final validation and acceptance

- Backend quality: Ruff, Pyright strict, complete pytest suite, PostgreSQL integration suite, Alembic upgrade/downgrade/upgrade.
- Frontend quality: generated contract freshness, Prettier, ESLint, strict TypeScript, Vitest/React Testing Library, production Next.js build.
- End to end: Playwright against real FastAPI/PostgreSQL with deterministic fixtures.
- Regression: exact signal frontier, warm-up, no lookahead, no signal-bar reuse, BID/ASK execution, slippage, ambiguity, end close, equity, failure-without-result, and semantic reproducibility remain proven.
- Acceptance: the trader can answer “Did it work?”, “How risky?”, “What Trades?”, “Why this Trade?”, and “What data and assumptions?” without source code or database access.
- Scope review: no comparison/optimization/export/background worker/WebSocket/global state library/generic chart terminal/PAPER/LIVE capability entered the change.

## Constraints, risks, and rollback

- A full Experiment remains one database transaction after the RUNNING claim. This intentionally favors atomic trustworthy facts over throughput. Measure before changing it; no external network call occurs inside it.
- Status polling can observe `RUNNING` but no percentage. This is honest and sufficient for the single-user slice.
- Legacy completed results may require on-read metric derivation; bounded list size limits cost. Do not cache or mutate terminal rows in this phase.
- Chart downsampling is presentation-only and must be labeled; it never feeds metrics.
- The same local Strategy fingerprint requirement can make an old StrategyVersion non-runnable. Surface that explicitly; do not weaken provenance matching.
- Additive migration rollback loses only derived metric cache fields/index. Primary facts permit deterministic reconstruction. Application rollback must tolerate the migrated schema and server defaults.
- No automatic commit, push, merge, migration execution against non-test data, or cleanup is authorized by this blueprint.

## Branch and readiness requirement

- Assigned implementation cwd/root: `/Users/vike/Desktop/atlas`.
- Isolation scope: one dedicated local feature branch for `phase-5-experiment-workflow` in the current checkout by default; use a linked worktree only if separately requested and approved.
- No implementation begins until the developer explicitly approves this blueprint and the workflow, then the worktrees process obtains operation-specific confirmation and writes a valid `READY` receipt.
- The `READY` receipt must record mode, root, cwd/path, branch, full starting SHA, exact workstream scope, clean/known status, context, and recovery instructions.
- Blueprint approval is not authorization for Git mutations. Commit, push, merge, and cleanup each require separate explicit requests/confirmations under the repository workflow.

## Implementation Blueprint — Phase 5 valid-run remediation

**Date:** 2026-08-23

### Authority, outcome, and out of scope

This append-only section is the authority for the approved valid-run remediation. Where it is more specific than the Phase 5 blueprint above, this section governs. A material conflict or evidence that requires changing Phase 4 trading semantics stops implementation and returns the issue for blueprint revision.

The outcome is a deterministic, passing Phase 5 create/orchestrate/execute path for both:

1. the valid primary configuration (`START + 1500 minutes` through `START + 1590 minutes`); and
2. the valid zero-Trade configuration (`START + 1500 minutes` through `START + 1515 minutes`).

Both must be created through `ExperimentConfigurationService`, executed through `ExperimentRunService` and the existing `ExperimentRunner` Phase 4 path, and shown equivalent to directly persisted Phase-4-shaped inputs using the same immutable StrategyVersion, DatasetSnapshot membership, values, and model version.

Explicitly out of scope: Phase 6; PAPER/LIVE; OANDA calls or credentials; wall-clock/current-candle/current-session eligibility; changes to candle aggregation, no-lookahead frontiers, Strategy, Risk, execution pricing, Fill/Position/Trade accounting, session policy, result methodology, API/user failure detail, UI behavior, schema/migrations, generic diagnostics/telemetry, broad exception handling, workers, retries beyond the existing lifecycle, and unrelated fixture cleanup.

### Agreed language

- **Valid-run regression:** the PostgreSQL integration test that creates an Experiment through the Phase 5 configuration boundary and executes it through the Phase 5 lifecycle into the existing Phase 4 runner.
- **Known-good baseline:** a directly persisted `PHASE4_HISTORICAL_EXECUTION_V1` Experiment using the existing golden StrategyVersion/data shape and the exact candidate configuration values; it must complete before its Phase 5-created counterpart is compared.
- **Primary case:** the deterministic fixture period expected to produce completed Trades.
- **Zero-Trade case:** a valid deterministic period that completes with a result, canonical equity history, and Trade Count `0`; it is not a failure.
- **Diagnostic evidence:** a structured, test-only record identifying the Phase 4 runner stage and an allow-listed reason code for the caught underlying `ValueError`, together with the baseline/candidate input comparison and failing assertion.
- **First concrete mismatch:** the earliest differing runner-consumed input or orchestration state that explains why the Phase 5 candidate fails while the matching direct Phase 4 baseline succeeds. A guess based only on `MARKET_DATA/INVALID_INPUT` is not a mismatch.
- **Corrective change:** any behavior or fixture change intended to make the valid run pass. Diagnostic instrumentation and the failing regression may precede evidence; a corrective change may not.

### Confirmed facts and decisions

- **Confirmed — high confidence:** both browser cases reach valid coverage and durably fail in the Phase 4 runner's `ValueError` handler as `MARKET_DATA / INVALID_INPUT / Experiment could not be run`; the underlying text is currently discarded.
- **Confirmed — high confidence:** the fixture and runner read immutable DatasetSnapshot membership and use timestamp-based session policy. They do not query OANDA, mutable current bars, wall-clock market state, or current Forex-open state.
- **Confirmed — high confidence:** the existing Phase 4 primary golden path completes with the same Strategy/data shape. Existing tests do not cover Phase 5 service creation followed by the real runner or a real zero-Trade completion through `_complete_phase4`.
- **Decision — preserve public sanitization:** persisted failure category/code/detail, HTTP responses, frontend state, and OpenAPI remain unchanged. Diagnostic data never enters an Experiment row, API response, browser payload, normal production log, or UI.
- **Decision — narrow runner seam:** add only an optional, default-off `ValueError` diagnostic sink to `ExperimentRunner`, used at the existing `_run_phase4` `except ValueError` boundary. Do not alter exception ordering, category selection, `_fail`, transaction behavior, or the broad infrastructure handler.
- **Decision — closed diagnostic vocabulary:** the sink receives an immutable structured record, not the exception, traceback, arbitrary `str(error)`, configuration, SQL, or source location. The record contains only `event`, `experiment_id`, `model_version`, fixed run path `PHASE4`, a fixed stage, an allow-listed reason code, and an optional UTC timestamp parsed and re-serialized from a recognized market-data message. Unknown text becomes `UNCLASSIFIED_VALUE_ERROR`; it is never emitted verbatim.
- **Decision — bounded stage markers:** assign a local stage immediately before existing Phase 4 operations: preconditions, config validation, snapshot/member load, M15 aggregation, clock construction, clock materialization, initial equity, Strategy/observation loop, end close, and result finalization. This is diagnostic labeling only, not a decomposition or exception refactor.
- **Decision — test/E2E lifecycle:** integration tests inject an in-memory collector. A test-only FastAPI factory under `backend/tests/` may inject a sink that emits one compact JSON diagnostic line to the E2E server stream; `playwright.config.ts` may point only the E2E server at that factory. Production `backend.api.app:create_app` remains default-off and emits nothing. The seam may remain as a test diagnostic after remediation because it is inert in production and protects future E2E receipts.
- **Decision — evidence-first correction:** no configuration, orchestration, fixture, clock, aggregation, or runner behavior is corrected until the diagnostic regression has produced the evidence tuple defined below. Fix exactly one first mismatch. Prefer `configuration.py`, lifecycle composition, or the test/E2E fixture. A Phase 4 semantic change requires a stop and new approval.
- **Decision — no new abstraction:** keep the diagnostic record/catalog beside the runner unless source constraints require one small focused module. Do not create a logging framework, event model, diagnostic table, generic callback bus, or environment-wide debug mode.

### Safe diagnostic contract and lifecycle

The diagnostic record is test infrastructure, not domain state. Its required shape is:

- `event`: fixed `experiment_runner_value_error`;
- `experiment_id`: the opaque Experiment UUID for test correlation;
- `model_version`: fixed from the persisted Experiment;
- `run_path`: fixed `PHASE4`;
- `stage`: one closed stage value from the bounded list above;
- `reason_code`: one closed code mapped from exact known runner/clock/aggregation validation messages or recognized safe prefixes;
- `at`: optional RFC 3339 UTC timestamp only when a recognized message contains a parseable timestamp.

Security and lifecycle rules:

1. The production default is no sink and no emission.
2. The mapper must fail closed. Unrecognized messages emit only `UNCLASSIFIED_VALUE_ERROR`; no message fragment, hash input, exception representation, chained exception, traceback, SQL, credential, URL, filesystem path, source path, or configuration value is emitted.
3. Sink failure must not alter Experiment status, transaction outcome, persisted failure, or API response. The existing sanitized failure remains authoritative.
4. The E2E sink exists only in a test module and emits the allow-listed JSON object. Do not enable it through a production debug endpoint or return it to Playwright through HTTP.
5. Add a regression proving a hostile/unrecognized `ValueError` cannot cross the sink, persistence, or API boundaries, and that known reasons produce only allowed fields.
6. After the mismatch is fixed, retain no temporary raw prints, response listeners exposing internal detail, tracebacks, ad hoc files, or expanded logging. The default-off structured seam and its safety tests are the only permitted lasting diagnostic change.

### Evidence gate before corrective code

Only the diagnostic seam, its security tests, and the failing valid-run regressions may be changed before diagnosis. Before any corrective code or fixture edit, the builder must provide all of:

1. the primary and zero-Trade diagnostic records (`stage`, `reason_code`, optional safe `at`);
2. a field-by-field comparison of runner-consumed baseline and Phase 5 candidate inputs: StrategyVersion/fingerprint, DatasetSnapshot/fingerprint and member identities/counts, venue, period, capital, parameter snapshot, Risk value/config, simulation config, model version, account, Position, and status at runner entry;
3. proof that the direct primary baseline completes in the same database setup;
4. the first failing assertion or operation and whether the failure reproduces with direct runner invocation, lifecycle invocation, or only E2E composition; and
5. a named first mismatch and the single smallest file/interface proposed for correction.

If the backend regression does not reproduce, do not change the runner. Compare the E2E test factory, production composition, persisted seed membership, selected snapshot, submitted defaults, and lifecycle entry state. If baseline and candidate fail identically, the evidence does not establish a Phase 5 mismatch; stop rather than changing Phase 4 behavior. If the first mismatch is in Phase 4 semantics, session policy, historical access, or financial methodology, stop for explicit scope approval.

### Ordered implementation

1. **Install the safe diagnostic seam.**
   - Likely files: `backend/experiments/runner.py`; focused diagnostic unit tests under `backend/tests/experiments/`.
   - Add the closed record/stage/reason vocabulary and optional constructor-injected sink. Invoke it only in `_run_phase4`'s existing `ValueError` handler, before the unchanged sanitized `_fail` call.
   - If browser-process evidence is required, add one test-only app factory such as `backend/tests/e2e_app.py` and point the API entry in `playwright.config.ts` to it. Do not change `backend/api/experiments.py` responses or production app defaults.
   - Gate: known and unknown diagnostic safety tests pass; existing failed-Experiment sanitization remains byte-for-byte equivalent at the persistence/API boundary.

2. **Add the two narrow failing regressions and matching baselines.**
   - Preferred file: new focused `backend/tests/integration/test_phase5_valid_run.py`; reuse `START`, `PARAMETERS`, `_registry`, and the established golden market-data shape without moving unrelated fixtures.
   - For each case, persist a direct Phase-4-shaped baseline and create a candidate with `ExperimentConfigurationService`. Use exact equal values, including commission/slippage, and assert runner-consumed input equivalence before execution.
   - Execute the baseline directly with `ExperimentRunner`; execute the candidate with `ExperimentRunService` using the same real runner and session factory. Do not substitute `GatedRunner` or mock Strategy/market data.
   - Primary expectations: both `COMPLETED`, at least one completed Trade, result present, equal semantic payload/output fingerprint and canonical trading facts apart from operational identity/timestamps.
   - Zero-Trade expectations: both `COMPLETED`, result present, Trade Count `0`, no Trade facts, valid equity/return/drawdown states, unavailable Trade-dependent metrics for `ZERO_TRADES`, and equal semantic payload/output fingerprint apart from operational identity/timestamps.
   - Fixture changes to `backend/tests/e2e_seed.py` or the golden helper are forbidden at this step unless required solely to express equal candidate/baseline inputs; defaults and existing golden expectations must remain unchanged.

3. **Capture and classify the evidence.**
   - Run the focused integration tests serially against the isolated PostgreSQL test database and, if needed, the two valid E2E scenarios serially.
   - Record the evidence-gate tuple. Select the first mismatch, not the last observed failed status.
   - No corrective change is permitted in this task step. An unmapped reason may add one closed safe mapping after its raise site is identified, but must never enable raw exception output.

4. **Correct only the proven first mismatch.**
   - Preferred locations, in order: `backend/experiments/configuration.py` for malformed persisted input; `backend/experiments/lifecycle.py` or `backend/api/app.py` for a proven orchestration/composition mismatch; `backend/tests/e2e_seed.py` for a proven snapshot/fixture mismatch.
   - `backend/experiments/runner.py`, `backend/experiments/clock.py`, `backend/market_data/aggregation.py`, Strategy, Risk, execution, and accounting are not corrective targets unless evidence proves the existing Phase 4 contract is violated and the blueprint is re-approved.
   - Preserve immutable Experiment configuration, DatasetSnapshot membership, retry-safe lifecycle, transaction boundaries, failure sanitization, no-lookahead, completed-bar-only decisions, and zero-Trade completion.
   - Do not “fix” the issue by broadening coverage, fabricating missing bars, using `is_current`, changing session classification, accepting malformed config, catching more exception classes, or relabeling failure as completion.

5. **Lock the correction and remove investigation residue.**
   - Make both regressions green and assert the exact corrected boundary so the mismatch cannot recur silently.
   - Keep only the closed default-off diagnostic seam/test factory if used. Remove temporary prints, raw exception assertions, ad hoc files, and one-off instrumentation.
   - Rerun unchanged Phase 4 golden/failure tests before E2E. A changed Phase 4 semantic payload or fingerprint is a blocker, not an expected update.

6. **Run full Phase 5 validation and independent gates.**
   - Run the matrix below with isolated test database configuration only.
   - Validation and review remain sequential and independently owned. No closure or success claim is permitted until both valid browser scenarios and the complete Phase 5 suite pass.

### Validation matrix

| Layer | Required proof | Pass condition |
| --- | --- | --- |
| Diagnostic unit | Known reason, recognized timestamp prefix, unknown/hostile message, absent sink, raising sink | Closed fields only; unknown text absent; sink behavior cannot alter sanitized result |
| Runner failure security | Existing invalid Phase 4 config through runner and API | Durable/API detail remains `Experiment could not be run`; no diagnostic fields or sensitive tokens in response/OpenAPI |
| Primary integration | Direct baseline plus service-created/lifecycle-executed candidate | Both complete; result and Trades exist; runner inputs and semantic outputs are equivalent |
| Zero-Trade integration | Direct baseline plus service-created/lifecycle-executed candidate | Both complete; result/equity exist; Trade Count `0`; Trade-dependent metrics explicitly unavailable |
| Lifecycle regression | Existing claim, duplicate, recovery, partial-state, infrastructure tests | No transaction, idempotency, recovery, or sanitized fallback regression |
| Phase 4 regression | `backend/tests/integration/test_golden_flows.py` and deterministic Strategy/Risk/execution/domain/Experiment suites | Existing facts, no-lookahead behavior, fingerprints, and failure-without-result semantics pass unchanged |
| API regression | Experiment create/run/detail integration tests | Phase 5 contract unchanged; no diagnostic leakage; terminal retry remains safe |
| Focused E2E | Primary and zero-Trade scenarios, serial during diagnosis | Primary reaches Completed/Trade detail; zero case reaches Completed/No Trades; safe server diagnostic only on failure |
| Full E2E | Canonical `npm run test:e2e` against real FastAPI/PostgreSQL/Next.js | All five current scenarios pass, including invalid coverage, failed Experiment, and foundation |
| Full Phase 5 | Ruff, strict Python typing, complete pytest/PostgreSQL suite, frontend format/lint/typecheck/unit tests, production Next build, generated contract freshness | Every command completes successfully; no partial or timeout-based success inference |
| Scope/security review | Diff and independent review | One evidence-backed mismatch fixed; no SQL/credential/path/traceback leakage, external dependency, Phase 6, schema, or semantic drift |

All historical inputs must be fixed timestamps and immutable fixture data. Tests must run without OANDA credentials, network market data, current time, current market session, or `is_current`. Database URLs must target the isolated test database; never run fixture truncation or E2E setup against non-test data.

### Constraints, rollback, and failure handling

- A diagnostic failure is not permission to expose raw exceptions. Use `UNCLASSIFIED_VALUE_ERROR`, refine the closed mapping from source, and rerun.
- A failing candidate remains durably `FAILED` with the existing sanitized detail and no trustworthy result. Tests must inspect diagnostics out of band; they must not weaken fail-closed behavior.
- No migration or data repair is expected. The correction must be application/configuration/orchestration or isolated fixture code only.
- Rollback is file-level: revert the single mismatch correction if it changes Phase 4 facts or breaks lifecycle gates. The additive default-off diagnostic seam may be reverted independently only after preserving equivalent safe test evidence.
- Test-created Experiments and diagnostic output are disposable only in the isolated test database/process. Never mutate, delete, or “repair” a completed Experiment in place.
- If the run transaction becomes unusable, existing rollback and fresh-session sanitized fallback remain authoritative. Do not route diagnostic sink failures through persistence fallback.
- A browser timeout after a durable terminal state is diagnosed from the persisted status and safe sink record; do not auto-create a replacement Experiment.
- No automatic Git operation, dependency installation, service cleanup outside the harness, commit, push, merge, reset, or worktree cleanup is authorized.

### Acceptance criteria

- The primary and zero-Trade Phase 5 configurations are created by `ExperimentConfigurationService` and complete through `ExperimentRunService` plus the existing Phase 4 runner.
- Each candidate is proven input- and output-equivalent to a matching direct Phase-4-shaped baseline, with only operational identity/terminal timestamps excluded.
- Primary completion contains trustworthy result, equity, completed Trade facts, and inspectable Trade detail; zero-Trade completion contains a trustworthy result/equity history and explicit zero-Trade metric states.
- The first concrete mismatch is evidenced before its correction, and the final diff corrects only that mismatch.
- Public and durable failure sanitization is unchanged. SQL, credentials, URLs, filesystem/source paths, stack traces, arbitrary exception text, and sensitive internals never appear in API/UI or diagnostic output.
- Existing Phase 1–4 deterministic, no-lookahead, financial, reproducibility, and failure-without-result semantics pass unchanged.
- All five Playwright scenarios and the full Phase 5 validation matrix pass without OANDA, current-time/session, live data, or Phase 6 behavior.
- Independent validation and review report no blocker; no success is inferred from partial runs or command timeouts.

### Assignment and model metadata

- Workstream: `phase-5-experiment-workflow`; classification: Feature; risk: R1.
- Blueprint owner: architect agent; model: `gpt-5.6-sol` (`opencode/gpt-5.6-sol`).
- Corrective implementation owner: backend builder, sequential single writer; model class: default/standard per `PLAN.md` (premium model not required).
- Validation owner: independent tester after implementation; review owner: independent reviewer after validation. A builder may not self-close either gate.
- Scope status: valid-run remediation scope approved; implementation of the appended blueprint still requires the workstream's explicit final confirmation before the corrective writer starts.

### Known valid READY checkout

- READY receipt: `dispatch/workstreams/phase-5-experiment-workflow/READY.md`.
- Mode: `feature-branch`.
- Root/cwd/path: `/Users/vike/Desktop/atlas`.
- Branch: `feature/phase-5-experiment-workflow`.
- Full starting SHA: `67c24b714f3c128cfefab0581118638194063de8`.
- Recorded status: READY, with known pre-existing modified `dispatch/ACTIVE.md`, `dispatch/MODEL-LOG.md`, and `dispatch/PLAN.md`, plus untracked `.codegraph/` and this workstream directory. Preserve them; do not clean, reset, stage, or rewrite them.
- Recovery: verify branch and full SHA/current contents before resuming, preserve the recorded working tree, and use only `/Users/vike/Desktop/atlas` as cwd. The READY receipt authorizes no Git mutation.

## Implementation Blueprint — PostgreSQL UTC session policy

**Date:** 2026-08-23

### Authority, outcome, and out of scope

This append-only section is the authority for the approved PostgreSQL session-timezone remediation. Where it is more specific than either Phase 5 section above, this section governs. A material conflict stops implementation and returns it for blueprint revision.

The outcome is one non-configurable Atlas persistence rule: every PostgreSQL connection used by Atlas is handed to application or migration code with session `TimeZone = 'UTC'`, including a reused pooled connection. Persisted trading, market-data, Experiment, runtime, and audit timestamps remain canonical UTC instants. The Phase 5 primary and zero-Trade paths must then complete through the production database composition without an inline `SET TIME ZONE`, runner override, or altered market-data rule.

Explicitly out of scope: changing PostgreSQL server/database/role defaults; adding an environment setting or deployment-specific timezone; adding a schema revision or rewriting historical rows; changing timestamp columns, API timestamp shapes, fingerprints, DatasetSnapshot membership, session calendars, M1/M15 aggregation, UTC bar boundaries, `SimulationClock`, Strategy, Risk, execution, accounting, result methodology, UI behavior, or Phase 6/PAPER/LIVE capabilities. This policy fixes session interpretation only; it does not redefine a historical fact.

### Canonical context owner and mandatory update order

`context/architecture/database.md` is the one canonical owner of the persistence/session-timezone rule. Before corrective source or test changes, append the following paragraph under `## Time`, immediately after the existing “Store timestamps in UTC…” paragraph:

> **PostgreSQL session policy:** Every Atlas PostgreSQL session operates with `TimeZone = 'UTC'`. UTC is canonical for persisted trading, market-data, Experiment, runtime, and audit timestamps. Atlas establishes this setting for every new and pooled connection; it must not depend on PostgreSQL server, database, or role defaults, or on host, developer, or deployment locale. Application input, domain, and persistence boundaries require timezone-aware UTC datetimes; naive datetimes must be rejected rather than interpreted through a machine-local timezone. This policy does not change canonical UTC bar alignment or timestamp semantics.

Do not duplicate this policy in product vision or another architecture owner. Implementation-facing comments may point to it but may not create alternate rules. Required order is: canonical context update → central engine policy and regression → composition-path adoption → removal of test workarounds → focused/full validation. The context change records the already-approved decision; it is not permission to alter unrelated context.

### Agreed language and confirmed facts

- **PostgreSQL session timezone:** PostgreSQL's per-connection `TimeZone` setting, which controls presentation and interpretation of `timestamptz`; it is not the host process timezone and does not change the stored instant.
- **New connection:** a newly opened psycopg physical connection.
- **Newly acquired session:** a SQLAlchemy `Session` or `Connection` that has just checked out a physical connection, whether new or reused from the pool.
- **Timezone drift:** a pooled physical connection whose session timezone was changed after initial connection. Atlas must reset it before the next borrower receives it.
- **Confirmed — high confidence:** SQLAlchemy mappings use timezone-aware `DateTime(timezone=True)` for the affected persisted timestamps; no schema migration is needed.
- **Confirmed — high confidence:** production API, historical-data CLI, and current runtime startup use `backend.persistence.database.create_database_engine`; API/workflow sessions use `create_session_factory`; Alembic, E2E seed, and several integration tests construct engines directly.
- **Confirmed — high confidence:** Task 12 isolated the first mismatch at `clock_construction`: PostgreSQL returned persisted instants in the database session's `America/Chicago` offset while the canonical clock requires zero-offset UTC/M15-aligned values.

### Session enforcement mechanism and pool behavior

1. `backend/persistence/database.py` owns an exact shared interface named `configure_utc_session_timezone(engine: Engine) -> Engine`. It is PostgreSQL/psycopg-specific, idempotent per Engine, and is called by both `create_database_engine` and `create_session_factory`. The session-factory call is the backstop for an engine injected into `create_app`.
2. The helper installs SQLAlchemy engine/pool event handling before first use. A new physical connection is initialized with the constant statement `SET SESSION TIME ZONE 'UTC'`; every pool checkout repeats that reset before SQLAlchemy exposes the connection. New-connection initialization establishes the default, and checkout reset prevents a committed `SET TIME ZONE` from leaking to the next borrower.
3. The hook uses the DBAPI connection directly and leaves it transaction-neutral before handoff. It closes its cursor and completes only its own setup transaction; it must never commit, roll back, or otherwise touch an application transaction. Registration must not duplicate when engine creation and session-factory composition both call the helper.
4. `pool_pre_ping=True`, existing pool sizing/reset behavior, connect timeout, Session `autoflush=False`, and `expire_on_commit=False` remain unchanged. Reconnect/invalidation creates a physical connection that goes through the same initialization and checkout policy.
5. Failure to establish UTC fails the connection/checkout. Atlas must not continue with an unknown or non-UTC session. No application query, migration, Experiment, or runtime readiness claim may proceed on that connection.

The builder must prove, not assume, the SQLAlchemy 2/psycopg 3 event ordering, transaction neutrality, idempotent registration, pool-reuse reset, and reconnect behavior in the focused PostgreSQL regression. If the proposed DBAPI hook cannot satisfy those properties, stop and return the mechanism for blueprint revision; do not fall back to a runner-local statement or server-default assumption.

### Application and migration paths

- **API and Experiment workflow:** `backend/api/app.py:create_app` continues to compose the engine and session factory. A supplied engine is configured through `create_session_factory` before request sessions or `ExperimentRunService` claim/run/fallback sessions use it. Production must not inject an ungoverned alternate session factory; tests that inject one own the same UTC contract.
- **Historical-data operator path:** `backend/market_data/cli.py:_service` inherits the policy from the shared engine/session factories. No command-local timezone SQL is allowed.
- **Runtime:** `backend/runtime/main.py:run` inherits the policy from the shared engine, including `check_database` and all future Sessions on that engine. If UTC setup fails, the existing startup failure path returns not-ready; it must not log a database URL or raw SQL error.
- **Alembic:** `backend/persistence/migrations/env.py:run_migrations_online` applies `configure_utc_session_timezone` to the `NullPool` engine before `.connect()`. Offline migration generation has no PostgreSQL session and requires no artificial timezone operation. No migration revision is created for this remediation.
- **E2E seed:** `backend/tests/e2e_seed.py` configures its direct engine through the shared helper. The API server already uses production `create_app`; `playwright.config.ts` must not point to a diagnostic or timezone-specific app factory.
- **Integration tests:** direct engines that execute application/persistence semantics must use the shared helper. At minimum this includes `backend/tests/integration/conftest.py`, `test_database.py`, `test_phase5_valid_run.py`, `test_golden_flows.py`, `test_experiment_configuration.py`, `test_experiment_lifecycle.py`, `test_runner_failure_persistence.py`, `test_api_experiments.py`, `test_market_data_ingestion.py`, `test_market_data_repositories.py`, `test_fill_application.py`, `test_strategy_persistence.py`, and migration-test engines in `test_migrations.py`. Do not create a competing test-only engine policy.

Before finishing, inventory all `create_engine`, `engine_from_config`, `Session(engine)`, and `sessionmaker(bind=engine)` sites under `backend/`. Every application-semantic PostgreSQL site must either use `create_database_engine`/`create_session_factory` or explicitly apply `configure_utc_session_timezone` before first checkout. Pure fake/non-PostgreSQL unit-test objects are outside this rule. Any newly discovered production bypass is part of this remediation; a different database abstraction is not.

### Naive timestamp, normalization, and historical-fact policy

- New external, domain, and persistence inputs remain timezone-aware UTC. Naive values are rejected at those boundaries; code must never call local-time conversion on a naive value or infer UTC from host/developer locale.
- PostgreSQL `timestamptz` reads on governed sessions must produce aware zero-offset datetimes. The regression must prove this. If they do not, treat that as a driver/session-policy failure rather than adding `replace(tzinfo=UTC)` in runner, repository, aggregation, or clock code.
- Existing explicit UTC API serialization/normalization remains unchanged for this narrow correction, including response shape and RFC 3339 `Z` output. Prove the PostgreSQL path reaches it with aware values; do not broaden or silently reinterpret naive values to make a test pass.
- `context/architecture/market-data-model.md` remains authoritative for UTC half-open bars and 00/15/30/45 M15 boundaries. Do not weaken `_utc_aligned`, M1/M15 validation, no-lookahead, completed-bar-only decisions, signal/frontier separation, or DatasetSnapshot immutability.
- Existing rows are instants and are not updated, rebucketed, re-fingerprinted, deleted, or “repaired.” There is no data migration, backfill, or terminal Experiment mutation.

### Diagnostics, failure handling, and security

- Preserve the Task 12 `Phase4ValueErrorDiagnostic` seam and its sanitization tests unchanged in behavior. It remains optional, closed-vocabulary, sink-failure-isolated, and default-off. Production `create_app` injects no sink; E2E uses no special diagnostic factory.
- The timezone statement is a source constant with no interpolation, request data, environment-controlled timezone name, or credential content. Never emit database URLs, SQL details, connection parameters, raw driver exceptions, paths, or credentials to API/UI output.
- A UTC setup failure is infrastructure failure, not `MARKET_DATA/INVALID_INPUT`. API readiness fails and requests use existing sanitized infrastructure handling; runtime does not become ready. Historical Experiments create no broker exposure. For future PAPER/LIVE use, inability to establish canonical session state blocks new exposure under the existing fail-closed safety rule.
- Do not catch setup failure and continue, retry a runner under a different timezone, mutate immutable facts, or convert unknown financial/time state into a successful result.

### Ordered implementation

1. **Record the canonical rule first.** Update only the `## Time` section of `context/architecture/database.md` with the exact paragraph above. Gate: wording and placement are exact; no product or other context file changes.
2. **Implement the central, pooled-session policy.** In `backend/persistence/database.py`, add `configure_utc_session_timezone`, wire it into `create_database_engine` and `create_session_factory`, and retain existing engine/Session options. Add the newly-acquired-session regression to `backend/tests/integration/test_database.py`. Gate: fresh connection, reused/poisoned pooled connection, aware UTC `timestamptz` read, transaction-neutral handoff, and failed setup behavior are proven against PostgreSQL.
3. **Close direct composition paths.** Apply the shared helper in `backend/persistence/migrations/env.py`, `backend/tests/e2e_seed.py`, and every direct application-semantic integration engine identified above. Confirm API, workflow claim/run/fallback, CLI, runtime health, online Alembic, E2E seed, and injected-engine tests all acquire governed connections. Do not add settings, dependencies, or a migration.
4. **Remove runner-specific workarounds.** Delete inline `SET TIME ZONE 'UTC'` statements from `backend/tests/integration/test_phase5_valid_run.py` and `backend/tests/integration/test_golden_flows.py`; do not replace them with per-test SQL. Keep fixture timestamps, M1/M15 validation, expectations, and diagnostic seam unchanged.
5. **Prove the original correction.** Run the primary (`START + 1500` → `START + 1590`) and zero-Trade (`START + 1500` → `START + 1515`) regressions through `ExperimentConfigurationService`, `ExperimentRunService`, and the real `ExperimentRunner`, using only the governed engine/session path. Primary must contain result/equity/completed Trade facts; zero-Trade must contain result/equity and no Trade facts. No test-only timezone override is permitted.
6. **Run regression, E2E, validation, and review gates sequentially.** Remove no diagnostics, fixtures, or assertions merely to obtain green output. A changed Phase 1–4 semantic fact/fingerprint or any M1/M15 acceptance broadening is a blocker.

### Validation and acceptance

- **Focused database policy:** with the isolated `*_test` URL, prove `SHOW TIME ZONE`/`current_setting('TimeZone')` is `UTC` for a fresh Session. Change one borrowed connection to a non-UTC timezone and commit, return it to the pool, then prove a newly acquired Session is reset to UTC. Also prove a known `timestamptz` is returned aware with zero offset and that a normal `with session.begin()` starts cleanly after checkout setup.
- **Connection lifecycle:** prove repeated helper registration is idempotent; engine disposal/reconnect still yields UTC; forced setup failure does not hand out a connection or report readiness. Tests may induce pool drift/failure to test enforcement, but Phase 5 valid-run tests themselves may not issue timezone SQL or override the runner.
- **Migration:** run Alembic upgrade → downgrade → upgrade against the isolated test database and prove online migration execution uses the governed engine. Schema and data remain otherwise unchanged; no new revision appears.
- **Phase 5 integration:** run `backend/tests/integration/test_phase5_valid_run.py` serially with no inline timezone statement. Both parameterized cases pass with the exact Task 12 semantic assertions and safe diagnostic collector behavior.
- **Phase 1–4 regression:** run `backend/tests/integration/test_golden_flows.py`, runner-failure persistence, market-data repository/ingestion, Strategy, Risk, execution, domain, clock/aggregation, lifecycle, and API suites. Existing no-lookahead, completed-bar, M1/M15 alignment, BID/ASK, accounting, ambiguity, failure-without-result, and reproducibility/fingerprint expectations pass unchanged.
- **Timezone-independent E2E:** run the focused primary and zero-Trade Playwright scenarios with a deliberately non-UTC host process `TZ` while PostgreSQL retains a non-UTC/default-unknown database setting. Keep browser display timezone configuration separate; it is not database-session evidence. Primary reaches Completed and Trade detail; zero-Trade reaches Completed and No Trades. Neither seed, API, browser test, nor runner issues a timezone override.
- **Canonical E2E:** run the unmodified `npm run test:e2e`; all five current scenarios pass against real FastAPI/PostgreSQL/Next.js without OANDA, network market data, current time/session, or a special app factory.
- **Full Phase 5:** Ruff, strict Pyright, complete pytest plus PostgreSQL integration suite, `npm run check:web`, production build, and generated OpenAPI contract freshness all complete successfully. A timeout or partial command is not a pass receipt.
- **Independent gates:** tester appends the complete receipts to `VALIDATION.md`; only after validation passes does the independent reviewer assess scope, pool/transaction safety, failure sanitization, timestamp semantics, and Phase 1–5 regressions in `REVIEW.md`. Closure remains blocked until both pass.

Acceptance requires all application and online-migration PostgreSQL paths to acquire UTC sessions independent of host/server/developer/deployment locale; the primary and zero-Trade paths to pass without test-only overrides; canonical UTC/bar semantics and historical facts to remain unchanged; diagnostics to remain safe and default-off; and full Phase 5 validation/review to pass.

### Rollback and proof-required decisions

- There is no schema or data rollback. Deploying the policy requires process restart/engine disposal so old pooled connections cannot survive. Existing historical rows remain untouched.
- If the hook causes connection or transaction regressions, stop Atlas, revert the engine-hook source wiring as one unit, and keep Experiments/runtimes blocked rather than resume under locale-dependent sessions. The approved UTC context policy remains authoritative while the mechanism is revised.
- Reverting only checkout reset while retaining connect-only initialization is not an acceptable steady state unless pool-drift immunity is proven by another approved mechanism. Altering PostgreSQL defaults is defense in depth at most, never the Atlas enforcement boundary.
- Must be proven rather than guessed: psycopg returns aware zero-offset values under the hook; checkout setup is transaction-neutral; a pooled timezone change cannot leak; migration `NullPool` connections are governed; injected API engines are governed; non-UTC host `TZ` cannot alter E2E results; and no application-semantic direct engine bypass remains.
- No Git operation, dependency installation, server/database/role alteration, migration execution against non-test data, or dispatch-artifact change beyond the eventual assigned task receipts is authorized by this blueprint.

### Summary

One canonical database rule, one shared SQLAlchemy enforcement interface, explicit online-migration/test adoption, no historical or trading-semantic change, and complete regression/E2E proof.

Blueprint ready.

## Implementation Blueprint — E2E lifecycle persistence diagnostic

**Date:** 2026-08-23

### Authority, outcome, and stop boundary

This append-only section is the authority for the approved narrow diagnostic. Where it is more specific than an earlier Phase 5 section, this section governs. A material conflict stops the task and returns it for blueprint revision.

The outcome is evidence identifying the lifecycle operation at which the primary and zero-Trade E2E requests diverge from the passing PostgreSQL integration path. The diagnostic is default-off, test/E2E-only, out of band, and non-durable. After capturing and comparing the evidence, the task **must stop before any corrective fix**, even if the root cause appears obvious.

Explicitly out of scope: correcting the failure; changing the central UTC policy; changing Experiment, runner, transaction, fallback, session-calendar, aggregation, Strategy, Risk, execution, accounting, result, API, or UI semantics; migrations or schema changes; dependency/configuration frameworks; production telemetry; raw exception logging; and Phase 6/PAPER/LIVE work.

### Agreed language and confirmed facts

- **Lifecycle diagnostic:** a closed six-field observation of one approved lifecycle checkpoint. It is test evidence, not domain state, audit state, or an API contract.
- **Operation event:** one record emitted after an operation succeeds or throws. Its database metadata is captured immediately before that operation from the same SQLAlchemy Session/connection.
- **Final read:** a diagnostic-only fresh-Session read of the Experiment after the primary commit or fallback attempt. It proves what a newly acquired API-process connection can read; it does not replace or alter the normal API response composition.
- **Passing comparison:** `backend/tests/integration/test_phase5_valid_run.py` using the real `ExperimentConfigurationService`, `ExperimentRunService`, `ExperimentRunner`, PostgreSQL, and governed session factory—not a mock runner.
- **Confirmed — high confidence:** Task 13 proves the direct primary and zero-Trade integration cases pass, while the same two browser cases fail under non-UTC host `TZ` with durable `PERSISTENCE/PERSISTENCE_FAILURE`.
- **Confirmed — high confidence:** production failure sanitization is intentional and must remain unchanged; diagnostic data may not enter an Experiment row, result, normal response, OpenAPI schema, frontend payload, or UI.
- **Assumed — medium confidence:** the original failure occurs at or after the runner transaction reaches the runner-return boundary. If no primary-stage event can be captured, report that bounded result and stop rather than broadening instrumentation during the task.

### Closed data contract

Define one immutable `ExperimentLifecycleDiagnostic` record beside `ExperimentRunService` in `backend/experiments/lifecycle.py`. `as_dict()` must always return exactly these keys and no others:

```text
stage:                RUNNER_RETURN | FLUSH | COMMIT | FALLBACK_BEGIN |
                      FALLBACK_FLUSH | FALLBACK_COMMIT | FINAL_READ
exception_class:      approved class name | UNCLASSIFIED_EXCEPTION | null
sqlstate:             five uppercase ASCII alphanumeric characters | null
show_time_zone:       validated PostgreSQL SHOW TIME ZONE value | UNAVAILABLE
backend_pid:          positive integer | null
alembic_revision:     validated revision token | UNAVAILABLE
```

There is deliberately no Experiment ID, request ID, timestamp, message, operation text, SQL, URL, configuration, payload, hostname, database name, role, filesystem/source path, traceback, or arbitrary metadata. Because correlation fields are forbidden, diagnostic E2E cases run in separate serial invocations.

- Successful events have `exception_class = null` and `sqlstate = null`.
- Exception classes use an explicit allow-list for expected built-in, SQLAlchemy, and psycopg persistence classes. Any other type is `UNCLASSIFIED_EXCEPTION`; never serialize module names, `repr`, `str`, arguments, or chained-exception text.
- SQLSTATE extraction inspects only known structured attributes on the caught exception and, for SQLAlchemy DBAPI wrappers, their `.orig` object (`sqlstate`, then `diag.sqlstate`). It never calls `str`/`repr`, walks arbitrary causes, or emits malformed values. A value not matching exactly five uppercase ASCII letters/digits becomes `null`.
- `show_time_zone` is accepted only as a non-empty bounded PostgreSQL timezone token; `alembic_revision` only as a bounded ASCII revision token (`[A-Za-z0-9_]+`). Invalid, absent, multiple, or unreadable values become `UNAVAILABLE`; they are never emitted verbatim.
- Sink or serialization failure is swallowed at the diagnostic boundary and cannot change status, commit/rollback, fallback, or HTTP behavior.

### Same-connection metadata and Alembic retrieval

For each primary, fallback, or final-read Session, capture one immutable metadata snapshot from `session.connection()` before its first observed operation and reuse it only for events on that Session. Execute the constant statements independently on that same connection:

1. `SHOW TIME ZONE`;
2. `SELECT pg_backend_pid()`;
3. a bounded, scalar read of `alembic_version.version_num`.

The Alembic value comes from the live database, never from migration files, `alembic.ini`, a filesystem path, or an environment-derived expected value. Exactly one validated revision is accepted; the expected current receipt is `0007_phase_5_metric_contract`, but the diagnostic records the live value rather than substituting it.

Metadata reads use a nested transaction/savepoint so an absent/unreadable revision cannot poison the Experiment transaction. Roll back only that diagnostic savepoint on metadata failure. Never commit, roll back, flush, or mutate the owning application transaction. A connection-level failure yields the closed unavailable/null fields and is then allowed to affect the real operation normally; diagnostics must not make a failing connection look healthy.

For `COMMIT` and `FALLBACK_COMMIT`, cache metadata before commit on the committing connection and emit after the commit attempt. Do not acquire a replacement connection to label a commit event. `FINAL_READ` captures its own metadata from its fresh read Session.

### Injection and emission boundary

Add an optional constructor-injected lifecycle diagnostic sink to `ExperimentRunService`; its default is `None`. No environment lookup, global logger, SQLAlchemy engine listener, repository callback, or runner change may enable it. The existing `Phase4ValueErrorDiagnostic` remains separate and unchanged.

`backend/api/app.py:create_app` may accept one optional lifecycle diagnostic sink solely to pass into `ExperimentRunService`. The production factory supplies none. Do not expose the sink through FastAPI dependencies, request data, settings, an endpoint, or OpenAPI.

When the sink is present only, make primary/fallback transaction checkpoints explicit without changing their boundaries:

1. invoke the existing runner in the existing row-locked transaction; emit `RUNNER_RETURN` for its return or thrown exception;
2. call the existing Session flush boundary explicitly and emit `FLUSH` for success/failure;
3. let the same transaction commit and emit `COMMIT` for success/failure;
4. on the unchanged outer exception path, use the existing fresh fallback Session; emit `FALLBACK_BEGIN` after fresh transaction acquisition, row lock, and eligibility read, or for an exception there;
5. retain `ExperimentRepository.mark_failed` as the fallback mutation/flush and emit `FALLBACK_FLUSH` for its success/failure;
6. commit that same fallback transaction and emit `FALLBACK_COMMIT` for success/failure;
7. after normal commit or fallback attempt, and only when diagnostics are enabled, open a fresh Session, read the Experiment without mutation, and emit `FINAL_READ` for success/failure.

The explicit primary `session.flush()` is an idempotent checkpoint after the runner's existing repository flushes; it must not move, split, or partially commit facts. Transaction ownership, row-lock duration, rollback, sanitized fallback, and returned/raised values remain identical. The diagnostic-only final read is best-effort and may not suppress or replace the original result/error.

### Required event ordering

Each attempted stage emits at most once. Later primary stages are absent after an earlier primary failure; later fallback stages are absent after an earlier fallback failure.

- Normal terminal path: `RUNNER_RETURN → FLUSH → COMMIT → FINAL_READ`.
- Runner/primary-operation exception: `RUNNER_RETURN(error) → FALLBACK_BEGIN → FALLBACK_FLUSH → FALLBACK_COMMIT → FINAL_READ`.
- Primary flush exception: `RUNNER_RETURN → FLUSH(error) → FALLBACK_BEGIN → FALLBACK_FLUSH → FALLBACK_COMMIT → FINAL_READ`.
- Primary commit exception: `RUNNER_RETURN → FLUSH → COMMIT(error) → FALLBACK_BEGIN → FALLBACK_FLUSH → FALLBACK_COMMIT → FINAL_READ`.
- Fallback begin, flush, or commit failure: emit the successful prefix, the failing fallback event with its exception, then attempt `FINAL_READ` once.
- Final-read failure: emit `FINAL_READ(error)` and preserve the already-determined lifecycle/API outcome.

The durable `RUNNING` claim remains outside this diagnostic because the failing receipts already prove it committed. Do not add CLAIM or repository-level stage vocabulary in this task.

### E2E server and log transport

Add `backend/tests/e2e_app.py` as the only emitting adapter. It creates the normal app with a lifecycle sink only when `ATLAS_E2E_LIFECYCLE_DIAGNOSTIC` equals exactly `1`, and it must refuse diagnostic startup unless `ATLAS_E2E_DATABASE_URL`/the effective database URL names a database ending in `_test`.

The sink writes one compact, sorted JSON object per line to the API server stdout with one fixed non-sensitive prefix, for example `ATLAS_E2E_LIFECYCLE `. The JSON body is exactly `ExperimentLifecycleDiagnostic.as_dict()`. Use immediate flushing; never write a diagnostic file, browser response, response header, fixture JSON, database row, or frontend console message.

In `playwright.config.ts`, select `backend.tests.e2e_app:create_app` only when the same explicit diagnostic flag is `1`; otherwise retain `backend.api.app:create_app`. Forward the flag only to the API subprocess and explicitly pipe its stdout for the diagnostic receipt. Keep `reuseExistingServer: false`, the existing API target, and production-like factory as the default. Do not add a general debug setting.

No change is required in `tests/e2e/experiment-workflow.spec.ts`: existing browser response logging is not diagnostic transport and must not be expanded to expose internals.

### Test safety, cleanup, and isolation

- Strengthen the diagnostic startup/seed guard before any truncate: both integration and E2E diagnostic URLs must identify a `*_test` database. Never run migration, seed, truncate, or E2E setup against non-test data.
- Run the primary and zero-Trade E2E cases in separate Playwright invocations with `--workers=1`; each invocation gets global seed setup, fresh API/Next processes, `reuseExistingServer: false`, and one unambiguous lifecycle sequence.
- Preserve the deliberately non-UTC host process setting used by Task 13. Browser `timezoneId: UTC` is display configuration and is not database evidence.
- The diagnostic environment flag is scoped to those child commands. After process exit there is no sink, listener, persistent file, or cleanup service. Existing engine disposal and Playwright process teardown remain authoritative.
- Test-created rows and `.fixtures.json` remain ordinary disposable E2E fixtures. Do not manually clean, repair, or mutate historical/non-test data after the receipt.
- Do not run OANDA, network market-data, current-session, server/database/role-setting, dependency-installation, Git, or migration-generation operations.

### Exact likely files and ownership

Implementation is limited to the smallest subset proven necessary:

- `backend/experiments/lifecycle.py` — closed record, extraction/metadata helpers, optional sink, seven lifecycle emissions.
- `backend/api/app.py` — default-off sink injection only.
- `backend/tests/e2e_app.py` — guarded E2E stdout adapter.
- `playwright.config.ts` — explicit-flag conditional factory and API stdout transport.
- `backend/tests/experiments/test_lifecycle_diagnostics.py` — new pure contract/extraction/no-leak tests.
- `backend/tests/integration/test_experiment_lifecycle.py` — stage ordering and injected runner/flush/commit/fallback failures.
- `backend/tests/integration/test_phase5_valid_run.py` — passing real-run comparison with an in-memory lifecycle collector.
- `backend/tests/integration/test_api_experiments.py` — default-off/public/durable no-leak and final-read behavior.
- `backend/tests/e2e_seed.py` — only if required to place the `_test` guard before its existing truncate.

Do not modify `backend/experiments/runner.py`, repositories, models, migrations, normal API schemas/routes, frontend code, E2E scenario assertions, context documents, dependencies, or production logging configuration. If the diagnostic cannot be implemented within these boundaries, stop for blueprint revision.

### Ordered implementation

1. **Define and lock the safe contract.** Add the exact enum/record, allow-listed exception-class and SQLSTATE extractors, same-connection metadata snapshot, and sink-failure isolation. Unit-test exact keys, allowed values, malformed attributes, and hostile exception content before lifecycle wiring.
2. **Instrument the lifecycle without semantic change.** Inject the optional sink; emit the exact sequences around runner return, explicit flush, commit, fresh fallback begin/flush/commit, and diagnostic final read. Add deterministic failure injection at those boundaries in integration tests. Gate: existing status, sanitized detail, transaction, idempotency, and fallback assertions remain unchanged.
3. **Prove no leakage and default-off behavior.** Use a hostile exception message containing marker SQL, credential, path, traceback-like, and payload text. Assert none appears in the record serialization, captured stdout when disabled, Experiment failure fields, HTTP body/headers, or OpenAPI; only the generic existing failure remains public/durable.
4. **Establish the passing comparison.** Under the same non-UTC host `TZ`, run both parameterizations in `test_phase5_valid_run.py` with the real lifecycle and an in-memory collector. Record their ordered stages and per-Session timezone/PID/revision values. Both cases must still complete with their existing semantic assertions.
5. **Install the guarded E2E adapter.** Add the conditional test factory/stdout sink and conditional Playwright command. Verify a normal E2E configuration still selects production `create_app` and emits no lifecycle line.
6. **Capture failing E2E evidence.** Run the primary and zero-Trade scenarios separately, serially, with the diagnostic flag and the Task 13 non-UTC host `TZ`. Preserve only the allow-listed server lines in the assigned task receipt. If both pass in isolation, run one bounded two-worker reproduction of only those two cases to classify a composition/concurrency distinction; do not change shared-runner ownership.
7. **Compare, classify, and stop.** Identify the first E2E event whose outcome or metadata differs from passing integration; report exception class/SQLSTATE, timezone, PID continuity/change, revision, durable final status, root-cause confidence, and the single smallest likely corrective file/interface. Make no correction and do not proceed to full validation/review.

### Validation and no-leak matrix

| Boundary | Required proof |
| --- | --- |
| Closed record | Exact six keys; exact seven stages; no arbitrary value survives validation. |
| Exception safety | Known structured SQLSTATE is captured; unknown/malformed/hostile exception data yields null or `UNCLASSIFIED_EXCEPTION` without calling message formatting. |
| Metadata | `SHOW TIME ZONE`, PID, and live Alembic revision come from the same connection as each observed operation; primary, fallback, and final-read connection changes are visible by PID. |
| Ordering | Success plus runner/flush/commit and fallback begin/flush/commit failures produce only the specified ordered prefixes and one final read. |
| Semantics | Existing lifecycle claim, duplicate, clean recovery, partial-state, domain failure, and sanitized infrastructure fallback tests pass unchanged in outcome. |
| No leak | Hostile marker absent from diagnostic JSON, stdout when disabled, durable Experiment fields, HTTP body/headers, OpenAPI, frontend payloads, and fixture JSON. |
| Default off | Production `create_app`, canonical Playwright configuration without the flag, and ordinary integration construction install no sink and emit no lifecycle records. |
| Passing comparison | Primary and zero-Trade integration cases complete under non-UTC host `TZ`; their stage/metadata receipt is captured in memory. |
| E2E evidence | Each failing browser case has an isolated server sequence and fresh final read under the same non-UTC host conditions; no OANDA or live/current dependency is used. |

Do not claim the Phase 5 suite passes. This diagnostic task succeeds when safe evidence and a bounded root-cause/smallest-scope recommendation exist, even if both E2E cases remain red.

### Receipt, validation, and mandatory stop

- The implementation writer may update only the approved source/test files above and the future orchestrator-assigned diagnostic task receipt. It must not alter `PLAN.md`, `EXPLORATION.md`, `RESEARCH.md`, `READY.md`, prior/current `TASK-*.md`, `VALIDATION.md`, `REVIEW.md`, `ACTIVE.md`, `COMPLETED.md`, or Git state.
- The receipt must include exact commands/outcomes; the allow-listed event sequences for passing integration and each E2E case; final durable status/API outcome; a side-by-side comparison; proven facts versus inference; confidence; root cause or narrowest remaining unknown; and one smallest corrective scope. It must contain none of the forbidden raw data.
- Independent Phase 5 validation and review remain blocked. This task does not authorize full-suite acceptance, closure, or a correction.
- **Mandatory stop:** after the evidence report, stop all writing and return the proposed corrective scope for a new explicit approval and blueprint update. Do not fix connection composition, shared-runner ownership, SQL/schema behavior, test concurrency, fixtures, or any other discovered cause in the diagnostic task.
- If diagnostics themselves change the failure, produce inconsistent metadata, cannot safely retrieve the live revision, leak a hostile marker, or require a stage/field outside the closed contract, stop and report the diagnostic as invalid; do not broaden it ad hoc.
- No migration, data repair, dependency install, Git operation, commit, push, merge, reset, cleanup, or server/database/role-default change is authorized.

### Branch and readiness

- **Confirmed — high confidence:** assigned root/cwd/path is `/Users/vike/Desktop/atlas`; branch is `feature/phase-5-experiment-workflow`; the recorded starting SHA is `67c24b714f3c128cfefab0581118638194063de8` per `READY.md`.
- Preserve all READY-recorded pre-existing changes and use only this checkout. The receipt authorizes no Git mutation.
- Blueprint approval authorizes only the bounded diagnostic workflow above. A corrective writer requires a new approved scope after the mandatory stop.

Blueprint ready.

## Implementation Blueprint — Primary runner-return/E2E-composition diagnostic

**Date:** 2026-08-23

### Authority, outcome, and mandatory stop

This append-only section is the authority for the approved narrow follow-up to Task 14. Where it is more specific than an earlier Phase 5 section, this section governs. A material conflict stops the task and returns it for blueprint revision.

The outcome is one safe comparison of the failing serial primary E2E run with the passing direct primary integration configuration. It must establish, without exposing raw values, whether the two paths agree on StrategyVersion and DatasetSnapshot identity/semantics, immutable membership, parameters, Risk and simulation configuration, requested period, starting capital, seeded market-data semantics, effective pre-execution runner inputs, and terminal result. If the runner returns `PERSISTENCE/PERSISTENCE_FAILURE`, the receipt must name the last closed internal runner stage entered before that return.

This is diagnosis only. After the comparison and receipt, the writer **must stop before any corrective fix**, even if one file or line is strongly implicated. The only permitted behavioral repair is the already-proven stale zero-Trade Playwright selector, changed to an unambiguous selector for the existing approved status UI.

Explicitly out of scope: correcting the primary failure; changing runner, lifecycle, transaction, Strategy, Risk, execution, accounting, market-data, result, API, UI, seed, or concurrency semantics; changing production logging; migrations/schema/data repair; exposing exception detail; two-worker diagnosis; full validation/review; Phase 6/PAPER/LIVE; dependency installation; and Git operations.

### Agreed language and evidence status

- **Runner comparison record:** an immutable, closed, non-domain observation emitted only through the existing optional runner diagnostic mechanism. It contains closed states, counts, and domain-separated digests—not raw persisted values.
- **Pre-execution checkpoint:** the point after StrategyVersion, DatasetSnapshot membership, M15/clock materialization, account/Position, parameters, Risk, simulation, commission, and effective simulated-execution inputs have been resolved, but before the first warm-up/decision Strategy evaluation or simulated Order/Fill operation. Initial equity persistence may already have occurred under the unchanged runner ordering.
- **Terminal checkpoint:** the existing runner return boundary after a completed/failed `ExperimentRunResult` is constructed. It is not the lifecycle commit or final read.
- **Semantic digest:** full SHA-256 over domain-separated canonical JSON. It is a comparison token only, is never a domain fingerprint, and is never persisted or returned through HTTP.
- **Identity consistency:** a closed verdict proving that the Experiment foreign key resolved to the exact loaded StrategyVersion or DatasetSnapshot row. Raw UUIDs are neither serialized nor printed. Cross-process equality uses semantic digests because isolated reseeding may create different UUIDs.
- **Confirmed — high confidence:** Task 14 proves the primary E2E lifecycle receives a returned `FAILED/PERSISTENCE/PERSISTENCE_FAILURE` result and then flushes, commits, and reads it successfully; the zero-Trade backend completes.
- **Confirmed — high confidence:** the broad `_run_phase4` `except Exception` currently converts an internal exception to that returned persistence failure, while the existing safe diagnostic emits only for `ValueError`.
- **Confirmed — high confidence:** the direct primary integration uses commission `0.10`, while the untouched UI submits its existing default commission `0`. This is a comparison fact to record, not a proven defect and not authorization to align either value.
- **Assumed — medium confidence:** the current closed stage markers will narrow the failure. The approved refinement below adds only labels around existing operations; it may not move, split, retry, or recategorize an operation.
- **Deferred — high confidence:** any correction, shared-runner ownership change, fixture/default alignment, stage-specific implementation change, concurrency reproduction, or broader regression belongs to a separately approved task after this mandatory stop.

### Closed safe comparison contract

Add one sibling immutable record, `Phase4RunnerComparisonDiagnostic`, beside the existing `Phase4ValueErrorDiagnostic` in `backend/experiments/runner.py`. Reuse the same optional, sink-failure-isolated runner diagnostic channel; retain the existing ValueError record and sanitization behavior unchanged. `as_dict()` for the comparison record always returns exactly these keys:

```text
event:                       experiment_runner_comparison
checkpoint:                  PRE_EXECUTION | TERMINAL_RETURN
stage:                       one closed Phase4DiagnosticStage value
strategy_identity:           RESOLVED_SAME_ROW | UNAVAILABLE
strategy_contract_digest:    sha256:<64 lowercase hex> | UNAVAILABLE
snapshot_identity:           RESOLVED_SAME_ROW | UNAVAILABLE
snapshot_contract_digest:    sha256:<64 lowercase hex> | UNAVAILABLE
snapshot_member_count:       nonnegative integer | null
snapshot_membership_digest:  sha256:<64 lowercase hex> | UNAVAILABLE
parameters_digest:           sha256:<64 lowercase hex> | UNAVAILABLE
risk_digest:                 sha256:<64 lowercase hex> | UNAVAILABLE
simulation_digest:           sha256:<64 lowercase hex> | UNAVAILABLE
period_digest:               sha256:<64 lowercase hex> | UNAVAILABLE
capital_digest:              sha256:<64 lowercase hex> | UNAVAILABLE
financial_projection_digest: sha256:<64 lowercase hex> | UNAVAILABLE
effective_execution_digest:  sha256:<64 lowercase hex> | UNAVAILABLE
seed_profile_digest:         sha256:<64 lowercase hex> | UNAVAILABLE
runner_inputs_digest:        sha256:<64 lowercase hex> | UNAVAILABLE
terminal_status:             COMPLETED | FAILED | null
failure_category:            closed FailureCategory value | null
failure_code:                approved existing runner code | null
```

There is deliberately no Experiment/request ID, direct StrategyVersion/DatasetSnapshot ID or fingerprint, member ID, timestamp, market price, parameter/configuration value, account amount, exception class/message/arguments, SQL/SQLSTATE, API payload, URL, credential, environment value, hostname, database/role name, filesystem/source path, traceback, or arbitrary metadata.

Canonicalization rules are fixed:

1. Use sorted-key compact JSON, explicit type tags, UTC RFC 3339 normalization for datetimes, canonical decimal strings, and fixed sequence order. Never use `repr`, `str(exception)`, object hashes, Python's randomized `hash`, or ORM serialization.
2. Every digest uses the domain `ATLAS_PHASE4_RUNNER_COMPARISON_V1` plus its field name. Digests from different fields are not interchangeable.
3. `strategy_contract_digest` covers immutable execution-relevant StrategyVersion semantics, including its persisted source fingerprint, but excludes UUID and source text.
4. `snapshot_contract_digest` covers the immutable snapshot descriptor and persisted fingerprint, excluding UUID. `snapshot_membership_digest` covers the ordered semantic member tuples consumed by the runner—venue/instrument, resolution/component, UTC interval, OHLC/completeness, and safe source revision semantics—excluding database IDs. `snapshot_member_count` proves cardinality separately.
5. `seed_profile_digest` combines the strategy, snapshot, and membership tokens. It does not read a fixture file or accept an expected value from the browser.
6. `parameters_digest`, `risk_digest`, `simulation_digest`, `period_digest`, and `capital_digest` each cover the corresponding runner-consumed value. `financial_projection_digest` covers base currency, starting/equity/P&L state, and Position state. `effective_execution_digest` covers whether execution was supplied or derived plus effective slippage/tick configuration. `runner_inputs_digest` combines all preceding tokens and the model version.
7. The integration test may compare raw ORM values in memory, but assertions must emit only fixed `MATCH`/`MISMATCH` field names and closed record data on failure. Pytest must not print raw dictionaries or UUID/value diffs. The task receipt reports equality verdicts, never digest strings or raw values.

### Exact internal stage labeling and runner injection

Keep the existing `Phase4DiagnosticStage` values and add only the minimum closed markers needed to identify the operation inside the present broad persistence catch:

```text
execution_adapter_configuration
financial_projection_load
pre_execution_inputs
warmup_evaluation
decision_evaluation
entry_attempt
protection_application
equity_sampling
terminal_fact_read
metrics_calculation
semantic_payload
result_create
mark_completed
```

Assign a marker immediately before the existing operation. Repeated loop operations reuse the same marker; do not add sequence numbers, market times, or Trade identifiers. For `_complete_phase4`, pass only a private optional stage cursor/callback needed to update the caller's diagnostic stage; it may neither catch nor transform exceptions. Do not inline/decompose result finalization, change exception ordering, or change any repository call.

When a diagnostic sink is present:

1. Build and emit `PRE_EXECUTION` after all comparison inputs are resolved at the defined checkpoint. Cache only the already-safe closed record fields in local memory for the terminal record.
2. On normal completion, construct the existing result, emit `TERMINAL_RETURN` with `COMPLETED` and null failure fields, then return it unchanged.
3. In each existing handled-failure branch, first obtain the unchanged `_fail` result, then emit `TERMINAL_RETURN` with its closed status/category/code and current stage, then return it unchanged. The existing ValueError diagnostic remains emitted first on its current path.
4. In the broad `except Exception`, never inspect or format the exception. Call the unchanged `_fail(... PERSISTENCE_FAILURE ...)`, emit `TERMINAL_RETURN` with the last stage and `FAILED/PERSISTENCE/PERSISTENCE_FAILURE`, and return the same result. If `_fail` itself raises, do not fabricate a runner return; existing lifecycle evidence remains authoritative.
5. Sink, canonicalization, or serialization failure is swallowed and cannot alter mutation order, terminal state, transaction usability, lifecycle fallback, response, or persisted facts.

Production `create_app` gains at most one optional runner-diagnostic injection argument used only when it constructs its default `ExperimentRunner`. Its default remains `None`; production startup, ordinary tests, and canonical Playwright composition install no sink. Do not add an environment lookup to runner, lifecycle, API routes, settings, or production logging.

### Test/E2E adapter and transport

Extend only `backend/tests/e2e_app.py` as the emitting adapter. A distinct flag, `ATLAS_E2E_RUNNER_DIAGNOSTIC=1`, enables the runner comparison sink only when the effective database name ends in `_test`; otherwise startup fails before migration/seed/run activity. The existing lifecycle flag and record remain independent and default-off.

The E2E adapter accepts the runner comparison type only. It must not serialize the legacy ValueError record because that record contains an Experiment ID. It writes one compact, sorted JSON object per line to API-process stdout with the fixed prefix `ATLAS_E2E_RUNNER_COMPARISON ` and immediate flush. The body is exactly the closed `as_dict()` result. It writes no file and uses no database row, API body/header, browser console, fixture JSON, trace attachment, reporter attachment, or frontend state as transport.

`playwright.config.ts` selects the test factory and pipes API stdout only when the exact runner or lifecycle diagnostic flag is enabled; otherwise it retains `backend.api.app:create_app` and ignored API stdout. Forward only the relevant flag to the API child. Keep the existing database target, process isolation, `reuseExistingServer: false`, browser timezone, and application behavior unchanged.

The existing temporary browser console/request/API-response-body listeners in `tests/e2e/experiment-workflow.spec.ts` are not an approved transport and must not run during this diagnostic. Remove them rather than copying their output into a receipt. This is no-leak cleanup, not a product or assertion repair.

### Primary comparison and zero-Trade selector

`backend/tests/integration/test_phase5_valid_run.py` remains the passing authority. For the primary `START + 1500` through `START + 1590` case:

- retain the direct Phase-4-shaped baseline and the `ExperimentConfigurationService` candidate;
- compare requested/persisted/loaded StrategyVersion and DatasetSnapshot identities in memory;
- strengthen membership comparison from count-only to count plus ordered semantic membership digest;
- compare parameters, Risk/simulation configuration, period, capital, account/Position, model version, effective execution inputs, seed profile, and aggregate runner inputs;
- inject the in-memory runner collector into both the direct runner and lifecycle candidate; and
- require matching `PRE_EXECUTION` records and `COMPLETED` terminal records, with existing result/Trade assertions unchanged.

The direct baseline's `PENDING`-to-run transition versus the lifecycle candidate's already-claimed `RUNNING` state is an expected orchestration distinction and must be recorded as such, not hidden inside a false equality. Operational Experiment identity and wall-clock terminal timestamps remain excluded.

For the serial primary E2E run, compare the emitted record to the passing direct primary receipt field by field. The E2E's actual UI-submitted defaults must be observed, not changed to match the integration test. The side-by-side receipt must show `MATCH`, `MISMATCH`, `EXPECTED_ORCHESTRATION_DIFFERENCE`, or `UNAVAILABLE` for every required field, followed by the exact terminal stage/status/category/code. A mismatch is evidence, not permission to edit its producer.

The zero-Trade backend is already proven complete. Change only its stale assertion at `tests/e2e/experiment-workflow.spec.ts:156` from the ambiguous page-wide text lookup to the existing approved header status badge scope:

```text
page.locator('header').getByText('Completed', { exact: true })
```

Do not add test IDs, ARIA roles, copy, or production markup for this repair. Run the serial zero-Trade case with runner diagnostics off and require the existing `No Trades` and empty-Trade assertions to pass.

### Exact likely files and prohibited changes

Implementation is limited to the smallest subset below:

- `backend/experiments/runner.py` — closed comparison record/digests, bounded stage labels, reuse of the optional safe sink, terminal emission.
- `backend/api/app.py` — default-off runner sink injection only.
- `backend/tests/e2e_app.py` — guarded runner-record stdout adapter; existing lifecycle adapter preserved.
- `playwright.config.ts` — explicit runner-flag factory/stdout selection only.
- `backend/tests/experiments/test_runner_diagnostics.py` — exact-record, canonicalization, hostile-input, broad-failure-stage, absent/raising-sink tests.
- `backend/tests/integration/test_phase5_valid_run.py` — primary direct/candidate safe comparison and in-memory receipts.
- `tests/e2e/experiment-workflow.spec.ts` — remove forbidden temporary raw response logging and repair only the zero-Trade strict selector.
- `backend/tests/e2e_seed.py` and `backend/tests/integration/test_golden_flows.py` — read/reuse only unless a test-only assertion helper is strictly required; no seed values, fixture semantics, bars, defaults, or fingerprints may change.

Do not modify lifecycle behavior/diagnostic records, repositories, models, migrations, configuration service, Strategy/Risk/execution/accounting, frontend components/client/generated contract, API routes/schemas, context, dependencies, other E2E scenarios, other dispatch artifacts, or Git state. If safe evidence requires another field, stage, file, raw value, or transport, stop for blueprint revision.

### Ordered implementation

1. **Lock the safe contract first.** Add the exact record, canonical digest helpers, stage vocabulary, union-compatible runner sink typing, and no-leak unit tests. Preserve existing `Phase4ValueErrorDiagnostic` serialization and tests.
2. **Instrument without semantic change.** Emit pre-execution and terminal records around existing operations and add stage-only updates. Prove identical returned results, durable failures, and sink-failure isolation with diagnostics absent/present/raising.
3. **Strengthen the passing primary comparison.** Replace raw-diff assertions with closed verdicts; prove direct baseline and lifecycle candidate identity, membership, all configuration/input fields, seed profile, terminal result, result presence, and completed Trade presence.
4. **Install the guarded E2E transport.** Wire the optional app injection and test adapter/Playwright flag. Prove production/default Playwright has no sink or prefixed output, non-test database startup is rejected, and lifecycle diagnostics are not implicitly enabled.
5. **Remove unsafe test logging and repair the one stale selector.** Make no other E2E assertion or product change. Run zero-Trade serially with diagnostics off and record its passing browser receipt.
6. **Capture the primary evidence.** Under the same non-UTC host `TZ`, run only the primary E2E case serially with the runner flag. Retain only prefixed closed records; compare them to the passing primary integration record and identify the first differing input or exact persistence-return stage.
7. **Report and stop.** Append no artifact in this task except the orchestrator-assigned future diagnostic receipt. Report facts, comparison verdicts, terminal state, confidence, narrowest remaining unknown, and one smallest proposed corrective file/interface. Do not make that correction or run full validation/review.

### No-leak gates and required receipts

Before E2E, all of these gates must pass:

- Exact comparison serialization has the listed key set, closed enums, validated digest format, and no optional arbitrary field.
- Hostile messages containing a credential, SQL text, URL, source/filesystem path, traceback-like text, UUID, API body, and marker market/configuration values appear nowhere in record JSON or enabled/disabled stdout. Tests must not call message formatting to prove this.
- Raw StrategyVersion/DatasetSnapshot IDs/fingerprints, member IDs/bars, period/capital/configuration/account values, and API payloads appear in neither diagnostic stdout nor failure output. Failed assertions print only field names and verdicts.
- No comparison record enters an Experiment/result row, API response/header, OpenAPI, browser payload/console, fixture file, trace, screenshot metadata, or normal production log.
- Default production app, ordinary integration construction, and canonical Playwright configuration install no sink and emit no prefix. A raising sink leaves the existing result and durable/API sanitization unchanged.
- The E2E adapter refuses a non-`*_test` database before any destructive setup; no OANDA credential/network/current-session dependency is introduced.

The implementation receipt must include exact command names and outcomes, without environment values or raw output:

1. focused Ruff for only changed Python files;
2. `pytest -q backend/tests/experiments/test_runner_diagnostics.py` plus the focused default-off/E2E-adapter safety tests;
3. the primary parameterization of `backend/tests/integration/test_phase5_valid_run.py` under a non-UTC host `TZ`, using the isolated test database, with direct/candidate comparison and completion assertions;
4. the serial zero-Trade Playwright scenario with diagnostics off, proving the selector and existing zero-Trade UI assertions;
5. the serial primary Playwright scenario with `ATLAS_E2E_RUNNER_DIAGNOSTIC=1`, proving the closed pre-execution/terminal sequence and durable terminal API state; and
6. a source/diff no-leak review confirming that no raw logger, alternate transport, correction, or out-of-scope file entered the change.

Do not put database URLs, fixture paths, response bodies, digest values, UUIDs, SQL, exception text, stack output, screenshots, traces, or server logs in the receipt. Report runner records as field-level equality verdicts plus closed checkpoint/stage/status/category/code only. A timeout, missing terminal record, `UNAVAILABLE` required field, hostile-marker leak, diagnostic-dependent behavior change, or unexpected extra record is a failed diagnostic and triggers the mandatory stop.

### Branch, rollback, and mandatory stop

- **Confirmed — high confidence:** root/cwd/path is `/Users/vike/Desktop/atlas`, branch is `feature/phase-5-experiment-workflow`, and recorded starting SHA is `67c24b714f3c128cfefab0581118638194063de8` per `READY.md`. Preserve all recorded pre-existing changes; READY authorizes no Git mutation.
- Diagnostic rollback is file-level: remove the new comparison record/injection/adapter while preserving the pre-existing ValueError and lifecycle diagnostics. The zero-Trade selector repair may remain because it only disambiguates existing approved UI. There is no schema/data rollback.
- No implementation may begin without explicit confirmation of this blueprint. No commit, push, merge, reset, cleanup, dependency install, browser install, migration generation, non-test migration/seed/truncate, or service-default change is authorized.
- **Mandatory stop:** once the primary side-by-side record identifies a mismatch or exact `PERSISTENCE_FAILURE` stage—or fails safely to do so—stop all source/test writing. Do not alter commission/defaults, seeded data, runner ownership, execution adapter state, result persistence, constraints, exception handling, or any implicated operation. Return one narrow recommendation for separate approval.

Blueprint ready.
