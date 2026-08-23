# Exploration — Phase 5: Experiment Workflow

## Scope and method

Read-only exploration of the repository against the root `AGENTS.md`, context
index, roadmap, Experiments and Experiment Results specifications, design
specification, and this workstream's `PLAN.md`. No CodeGraph index is present
at the repository root, so source inspection used direct repository search and
reads. No application code was changed.

## Existing Experiment flow

### Domain and persistence

- `backend/persistence/models.py` contains the Phase 3/4 Experiment graph:
  `ExperimentModel`, `ExperimentAccountModel`, `TradeIntentModel`,
  `RiskDecisionModel`, `OrderModel`, `FillModel`, `PositionModel`,
  `TradeModel`, `ExperimentEquityPointModel`, and `ExperimentResultModel`.
- `ExperimentModel` persists immutable inputs: StrategyVersion, DatasetSnapshot,
  venue instrument, UTC range, capital, risk, parameter snapshot, simulation
  config, and model version. Statuses are `PENDING`, `RUNNING`, `COMPLETED`,
  and `FAILED`; terminal failure category/code/detail are persisted.
- Migration `0006_phase_4_persistence_contract.py` adds result/equity facts and
  database guards for immutable terminal configuration, append-only historical
  facts, and terminal projections. This is important protection for the Phase
  5 read workflow; completed results must not be recomputed from current
  defaults.
- `backend/persistence/experiment_repository.py` can create an Experiment,
  seed its simulated account and flat Position, load one Experiment, transition
  status, append equity points, and create a result. It has no list/query
  methods for workflow screens and no result/trade/equity read methods.
- Dataset snapshots are immutable and fingerprinted. `DatasetSnapshotRepository`
  reads snapshot membership without `is_current`, preserving historical facts
  even after market-data corrections. `backend/market_data/coverage.py` offers
  a pure M1 coverage report with missing components, gaps, closures, and
  unexpected observations, but it is not connected to an Experiment workflow.

### Execution and runner

- `backend/experiments/runner.py` is the application orchestration boundary.
  It loads the persisted StrategyVersion and DatasetSnapshot, derives M15 MID
  bars from snapshot M1 data, uses `SimulationClock`, evaluates the registered
  Strategy, applies canonical Risk, simulated execution, fills, protection,
  Position/Trade accounting, equity history, and result persistence.
- The Phase 4 path (`PHASE4_HISTORICAL_EXECUTION_V1`) is the relevant current
  path. It validates the fixed M1/MID/BID-ASK, slippage, commission, financing,
  intrabar, end-of-Experiment, and equity-sampling configuration. It records
  output fingerprints, ambiguous Trade counts, financing disclosure, and basic
  result values.
- `SimulationClock` explicitly separates completed signal-bar data from
  post-decision executable observations. Existing tests cover no lookahead,
  warm-up ordering, M15 alignment, complete observations, and half-open ranges.
- Integration tests in `backend/tests/integration/test_golden_flows.py` cover
  long/short golden flows, semantic reproducibility, slippage, equity, failure
  without a result, and end-of-Experiment closure. These are the principal
  Phase 4 contracts that Phase 5 must expose rather than alter.

## Existing API and UI flow

- `backend/api/app.py` only creates the FastAPI app, database engine, and the
  `/health/live` and `/health/ready` routes from `backend/api/health.py`.
  There are no Experiment, StrategyVersion, DatasetSnapshot, Trade, result,
  coverage, or run-action API routes, schemas, dependency wiring, or error
  responses.
- `frontend/app/page.tsx` is only the foundation page (“The project foundation
  is running.”). There is no horizontal navigation, Experiments list/config
  page, Experiment detail/results page, Trade detail view, status polling, data
  coverage presentation, or API client. `frontend/app/globals.css` contains
  only minimal global styling. Existing frontend coverage is a foundation-page
  test only. No chart dependency or chart implementation is present.
- The repository has backend dependencies for FastAPI, SQLAlchemy, and
  PostgreSQL, but no existing Phase 5 API/UI integration layer. The frontend
  package manifest was not found in the inspected tree, so the actual frontend
  dependency/install conventions need confirmation before implementation.

## Phase 5 gaps

### Configuration and run lifecycle

1. No bounded request/response contract for creating an Experiment from a
   StrategyVersion, requested period, snapshot, capital, Risk, and simulation
   configuration.
2. No pre-run coverage validation against the requested period plus required
   warm-up/history and M1 BID/ASK/MID observations. Invalid snapshots currently
   surface only when the runner reaches them and are persisted as a generic
   failure path.
3. No API action to create/seed/start an Experiment, no status retrieval, and
   no list ordering/filtering for PENDING/RUNNING/COMPLETED/FAILED records.
4. The runner is a synchronous application call and the current API has no
   execution service or lifecycle integration. The implementation must preserve
   durable status and failure behavior without introducing a speculative worker
   architecture.

### Results and inspection

1. No result read model/API. `ExperimentResultModel` currently stores net
   return, maximum drawdown, gross/commission/net P&L, ending values, Trade
   count, ambiguity count, and financing disclosure, but not the specified
   Sharpe, Profit Factor, Win Rate, Expectancy, or a persisted/derived primary
   R summary.
2. No equity/drawdown endpoint or serialization. Equity points are persisted
   with valuation BID/ASK and source bar IDs, suitable for a chart payload.
3. No Trade list/detail query. Trade facts, intent rationale, Risk decisions,
   Orders, Fills, ambiguity, and source market-bar identities exist in the
   database, but there is no read composition that exposes the required
   lineage or focused trade context.
4. No assumptions/provenance presentation. The required inputs are already
   captured across Experiment fields, StrategyVersion identity/fingerprint and
   source snapshot, DatasetSnapshot fingerprint/integrity, result schema, and
   simulation config, but they are not assembled for a consumer.
5. No explicit failed/zero-Trade result presentation. Runner failure persists
   a terminal reason and deliberately does not create a result; zero Trades
   can be a valid completed result but the UI/API has no distinction or metric
   availability semantics.

## Dependencies and bounded implementation seams

The narrowest seams suggested by the existing boundaries are:

- **Backend read/write application boundary:** add an Experiment workflow
  service around `ExperimentRepository`, `DatasetSnapshotRepository`,
  `StrategyRepository`, and `ExperimentRunner`; keep repository sessions and
  transaction ownership explicit. Reuse existing canonical domain facts rather
  than adding Backtest-specific types or a second result domain.
- **Coverage seam:** compose the existing snapshot integrity metadata and
  `validate_coverage`/snapshot membership reads into a pre-run validation
  response. Required output should explain range, warm-up availability, missing
  components/gaps, and whether the run may start.
- **API seam:** add typed request/response contracts and narrowly scoped routes
  for Experiment list/create, coverage validation, run/status, result/equity,
  Trade list, and Trade detail. Keep internal UUIDs out of normal display
  labels while retaining IDs as opaque API linkage.
- **Metrics seam:** define one result read/computation boundary over immutable
  Experiment facts and equity points. Any missing primary metrics need a
  deliberate persistence/read-model treatment; do not fabricate unavailable
  values or recalculate from current Strategy/Risk defaults.
- **Frontend workflow seam:** replace the foundation-only page with the
  Experiments workspace and separate result/trade-detail views. Use the design
  hierarchy: identity/status, restrained headline metrics, equity then drawdown,
  Trades, assumptions, provenance. The existing frontend has no reusable
  components or API client to preserve.
- **Chart seam:** use the repository's intended Lightweight Charts direction
  only if the dependency is confirmed and added within approved scope. Equity
  and drawdown need simple series; Trade detail needs the focused EUR/USD
  candle context and annotations without duplicating Strategy detection in UI.

## Risks and attention points

- **Correctness boundary:** coverage must be validated before starting, and the
  run must continue to use the immutable DatasetSnapshot membership, not mutable
  current market-bar heads. Signal-bar separation, warm-up, and no-lookahead
  tests are existing contracts, not UI conveniences.
- **Immutability:** completed Experiment inputs/results and the provenance shown
  by the UI must come from the stored Experiment graph. A rerun is a new
  Experiment, not a mutation or refresh of an old one.
- **Metric semantics:** max drawdown must come from equity history; Trade Count
  means completed Trade episodes; failed results must not appear as zeroes;
  zero-Trade completion is valid. Sharpe methodology and unavailable states
  need explicit treatment before exposing cards.
- **Run concurrency/idempotency:** duplicate start requests, terminal reruns,
  session failure, and a status observed during execution need safe, persistent
  behavior. Existing database guards help, but no API-level lifecycle contract
  exists yet.
- **Synchronous execution/UI status:** the current runner performs the full
  simulation in one call. A UI status flow must not imply progress or durable
  background execution that does not exist. Avoid silently converting runner
  failure into a successful response.
- **Trade context provenance:** rationale contains decision-time data and source
  M1 IDs, while chart context requires immutable snapshot reads. Do not infer
  setup candles in the browser or query mutable market data.
- **Scope creep:** exclude comparison, optimization, exports, research
  notebooks, secondary analytics, generic terminal charting, and future PAPER/
  LIVE concerns. Phase 5 should expose the Phase 4 simulation, not change its
  execution semantics.

## Recommended bounded outcome

Implement only the vertical path: choose an existing immutable StrategyVersion
and valid DatasetSnapshot → validate requested coverage → create and start one
Phase 5 Experiment → observe durable status/failure → inspect a completed or
zero-Trade result → inspect equity/drawdown and a Trade's rationale plus
lineage → disclose assumptions/provenance. Preserve the existing runner and
database invariants, and make the next blueprint resolve metric storage versus
derived read-model details before builders begin.
