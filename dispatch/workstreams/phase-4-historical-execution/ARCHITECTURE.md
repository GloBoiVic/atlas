# Phase 4 Historical Execution — Authoritative Blueprint

**Blueprint ready.**

This blueprint is authoritative for this workstream. Builders must stop and return any material conflict rather than silently changing it. Human approval is required before a `READY` receipt, any Git-changing operation, or implementation.

## Implementation Blueprint — Trustworthy Historical Experiments

### Outcome

Build one synchronous, deterministic, persisted Experiment runner for the fixed slice: **EMA Sweep Engulfing / EUR/USD / OANDA-source DatasetSnapshot / USD simulated account / M1 execution / M15 Strategy evaluation**. It replays the requested half-open period, permits multiple sequential Trades, models executable BID/ASK entry and protection, persists canonical facts plus equity/results provenance, and terminates as `COMPLETED` or inspectably `FAILED`.

The outcome is complete when identical semantic inputs produce identical semantic TradeIntents, RiskDecisions, Orders, OrderEvents, Fills, Trades, equity points, metrics, ambiguity facts, and output fingerprint. Database UUIDs and wall-clock audit timestamps are identities/metadata and are excluded from semantic equality.

### Agreed language

- **Experiment:** immutable historical simulation; never Backtest/BacktestRun/BacktestResult.
- **Simulation frontier:** the UTC instant at which completed data becomes available. A decision at `T` sees only bars ending at or before `T`; execution starts with the M1 interval beginning at `T`.
- **Execution observation:** an in-memory M1 BID/ASK OHLC input to the simulator, not a persisted `Execution` entity.
- **Executable reference price:** raw DatasetSnapshot BID/ASK price before configured slippage.
- **Protection pair:** the STOP_LOSS and TAKE_PROFIT Orders related to one filled entry. This is a workflow relationship, not a new OCO domain entity.
- **Ambiguous Trade:** a Trade whose same M1 observation touched both stop and target without knowable tick order; STOP_LOSS wins.
- **Modeled net P&L:** gross P&L from actual Fill prices less modeled commission. Financing is excluded and prominently disclosed, so the value is not represented as financing-inclusive.
- **Semantic output fingerprint:** SHA-256 over versioned, canonicalized input references and ordered financial/output facts, excluding UUIDs and wall-clock audit fields.

### Decisions

| Label | Decision | Rationale |
| --- | --- | --- |
| **Confirmed — high confidence** | Keep the existing canonical Strategy → Experiment → TradeIntent → RiskDecision → Order/OrderEvent → Fill → Position → Trade boundaries. No persisted `Execution` or historical-only trading nouns. | Governing domain and Experiment specifications require parity with later PAPER/LIVE concepts. |
| **Confirmed — high confidence** | The clock exposes every eligible M1 MID/BID/ASK observation chronologically; M15 MID bars remain derived through the existing deterministic aggregator. | Full OHLC is required for stops, targets, gaps, valuation, and ambiguity without future leakage. A reduced “open-only” frame is insufficient. |
| **Confirmed — high confidence** | Requested period is `[trading_start, trading_end)`. Bars ending at `trading_start` are warm-up only; decision frontiers satisfy `trading_start < T < trading_end`. | This preserves the existing warm-up boundary and prevents pre-period information from creating period exposure. |
| **Confirmed — high confidence** | At a frontier, first finalize protection/valuation from the M1 interval that just ended, then evaluate a newly completed M15 bar once, then allow entry at the current M1 open. | Position and Strategy state reflect all economically prior events, while signal-bar data is never reused for execution. |
| **Confirmed — high confidence** | Entry is full-fill market execution at the first complete BID/ASK open after an approved decision. Long buys ASK; short sells BID. PRE_SUBMISSION sizes from the slippage-adjusted actual entry, and the target resolves from that entry. | Risk must validate actual executable economics, not confirmation close or an unslipped quote. |
| **Confirmed — high confidence** | Both protective Orders are created only after the entry Fill. STOP is stop-market; target is limit-style. The triggered Order fills and its sibling becomes `CANCELED` atomically. | Fill authority is preserved and no simulator behavior is misrepresented as broker-hosted OCO behavior. |
| **Confirmed — high confidence** | Same-bar entry and protection are allowed only after the entry Fill event. Open-gap stop is evaluated first; otherwise dual intrabar touch resolves STOP_LOSS/adverse-first and records ambiguity on the affected Trade. | This is the conservative policy required by the Experiment and market-data contracts. |
| **Confirmed — high confidence** | One Position projection is reused across sequential Trades. Trade sequence is allocated under the Position lock as `max(sequence)+1`; deterministic correlation keys include Experiment, Trade sequence, and purpose. | Existing persistence already models one Position and sequence-numbered Trades; no new aggregate is needed. |
| **Confirmed — high confidence** | Risk rejection caused by setup/geometry/quantity is a persisted non-fatal outcome; evaluation continues. Unknown account/Position state, invalid configuration, or internal inconsistency fails the Experiment. | A rejected opportunity is normal; unknown financial state must fail closed. Zero-Trade completion remains valid. |
| **Assumed — high confidence** | Slippage model is fixed adverse ticks, applied to entry, stop-market, and END_OF_EXPERIMENT market Fills; target limit Fills receive neither adverse slippage nor favorable improvement. | It is the smallest deterministic model satisfying explicit slippage and conservative execution. Human approval confirms this product choice. |
| **Assumed — high confidence** | Commission is configurable as USD per unit per Fill, including explicit zero. Financing is not implemented and is stored/disclosed as `FINANCING EXCLUDED`, never as zero. | Supports explicit costs without inventing unavailable financing data or broadening into Phase 13 economics. Human approval confirms this product choice. |
| **Assumed — high confidence** | Equity is persisted at `trading_start` and after every complete eligible M1 close. Open exposure is valued long at BID close and short at ASK close. | This is the minimum reproducible M1 curve needed for equity and drawdown without fabricating ticks. |
| **Assumed — high confidence** | An open Position at the end closes at the latest complete BID/ASK M1 close with `end_time <= trading_end`, provided any interval between that quote and `trading_end` is only a classified expected session closure. | This defines “final eligible price” without inventing data. An unexpected gap, missing side, or absence of a quote fails the Experiment. |
| **Confirmed — high confidence** | A Phase 4 Experiment is single-attempt and terminal. Failed/completed inputs and results cannot be edited; a deliberate rerun creates a new Experiment. | Required reproducibility and auditability invariant. |
| **Deferred — high confidence** | Cancellation, partial Fills, intentional partial exits, manual/risk exits, trailing protection, margin/financing engines, daily-loss/drawdown blocking, instant reversal, and restart/resume checkpoints. | None is required by the Phase 4 exit criterion. |

### Exact simulation configuration and provenance

For `model_version = PHASE4_HISTORICAL_EXECUTION_V1`, `simulation_config` is an immutable JSON object validated before any trading fact is written:

- `schema_version`: `PHASE4_SIMULATION_CONFIG_V1`
- `execution_resolution`: `M1`
- `analysis_component`: `MID`
- `execution_components`: exactly `['BID', 'ASK']`
- `spread_model`: `DATASET_BID_ASK_EMBEDDED`; never subtract spread again
- `slippage_model`: `{type: ADVERSE_FIXED_TICKS, ticks: non-negative integer, tick_size: '0.00001'}`
- `commission_model`: `{type: PER_FILL_PER_UNIT_USD, amount: non-negative finite decimal string}`; zero must be explicit
- `financing_model`: `{type: EXCLUDED, disclosure: 'FINANCING EXCLUDED'}`
- `intrabar_policy`: `STOP_LOSS_ADVERSE_FIRST_V1`
- `target_fill_policy`: `REQUESTED_PRICE_NO_IMPROVEMENT_V1`
- `end_policy`: `FINAL_ELIGIBLE_M1_CLOSE_V1`
- `equity_sampling`: `TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1`

`risk_config` is `{schema_version: PHASE4_RISK_CONFIG_V1, risk_per_trade: decimal string}` and must equal the existing scalar `risk_per_trade`. Parameter values remain in `parameter_snapshot`. Provenance also includes StrategyVersion/source fingerprint, DatasetSnapshot/fingerprint and immutable member IDs, requested range, starting USD capital, venue/instrument, engine model version, result schema version, and semantic output fingerprint.

All authoritative arithmetic uses `Decimal`/PostgreSQL `NUMERIC`. Apply no intermediate binary floating-point conversion. Quantize persisted USD amounts once to the existing 10-decimal storage scale using round-half-even; quantity remains whole units under current Risk rules. Slippage cost is analytic because it is already embedded in Fill price; it is not subtracted again. Commission is the Fill `fee` and is subtracted once. Spread remains embedded in BID/ASK references and is not separately charged.

### Historical execution behavior and safety invariants

1. Validate that StrategyVersion is immutable and locally provenance-matched; DatasetSnapshot belongs to OANDA EUR/USD, contains M1 MID/BID/ASK, has valid integrity, and covers warm-up plus requested period.
2. Derive M15 MID bars only with the existing canonical aggregator. Missing expected M1 data is never filled. Expected OANDA FX closures are skipped according to the existing session policy; unexpected gaps fail validation/market data.
3. Warm-up supplies exactly the required prior M15 bars, updates Strategy state, and forbids exposure. Strategy sees no execution resolution, account, Risk, persistence, environment, or future data.
4. Evaluate each completed M15 frontier at most once with actual current `FLAT`/`LONG`/`SHORT` Position context. Persist TradeIntent only for actionable Strategy decisions.
5. PRE_FLIGHT runs against known account/Position state. If approved, the first complete post-decision M1 BID/ASK open supplies PRE_SUBMISSION. No later quote is substituted for a missing first quote.
6. Apply adverse slippage to the relevant executable side before sizing. If stop geometry becomes invalid, persist rejection and continue; do not create an Order.
7. Persist entry Order lifecycle `PENDING_SUBMISSION → SUBMITTED → FILLED`; the Fill atomically updates Position, opens a Trade, debits commission, and updates account state.
8. Create STOP_LOSS and TAKE_PROFIT Orders after entry Fill, each `PENDING_SUBMISSION → SUBMITTED`, related by `parent_entry_order_id`. There is no broker submission or claim of broker-hosted protection.
9. For each later M1 observation, use long BID or short ASK: (a) gap-through stop at open fills from that worse open plus adverse slippage; (b) target at/open or intrabar fills exactly at target; (c) ordinary intrabar stop fills at stop plus adverse slippage; (d) dual touch records ambiguity and executes stop first.
10. A Fill, never Order status, changes exposure/accounting. Trigger Fill, Trade close, Position flattening, account/cost update, and sibling cancellation occur atomically.
11. Continue chronological Strategy evaluation after a Trade closes. Never pyramid. An opposite direction can open only from `FLAT` at a later M15 decision frontier; no direct or same-decision reversal.
12. At each eligible M1 close, value open exposure on its liquidation side and append one equity point. Drawdown derives from the persisted running peak; primary facts remain Fills, Trades, costs, and equity points.
13. At `trading_end`, do not evaluate a bar ending exactly there. If exposed, create/fill a market `EXIT` at the final eligible side close with adverse slippage and Trade exit reason `END_OF_EXPERIMENT`, then cancel both protection Orders atomically.
14. Complete only while Position is `FLAT`, every Order is terminal, one immutable result row exists, counts reconcile to primary facts, and the semantic output fingerprint has been recomputed from persisted facts.

### State and order/protection lifecycle

- Experiment: `PENDING → RUNNING → COMPLETED | FAILED`; no other transition and no terminal mutation.
- Position: `FLAT → LONG|SHORT → FLAT`; only Fill application may transition it.
- Trade: created `OPEN` by entry Fill, then `COMPLETED` by exactly one exit Fill with `TAKE_PROFIT`, `STOP_LOSS`, or `END_OF_EXPERIMENT`.
- Entry Order: `PENDING_SUBMISSION → SUBMITTED → FILLED`.
- Protective winner: `PENDING_SUBMISSION → SUBMITTED → FILLED`; sibling: `PENDING_SUBMISSION → SUBMITTED → CANCELED`.
- End exit: `PENDING_SUBMISSION → SUBMITTED → FILLED`; both submitted protection siblings then become `CANCELED` in the same atomic transition.
- Every status transition has an immutable OrderEvent (`ORDER_CREATED`, `ORDER_SUBMITTED`, `ORDER_FILLED`, `ORDER_CANCELED`) with per-Order sequence. Phase 4 never emits `UNKNOWN`, `PARTIALLY_FILLED`, `REJECTED`, or `EXPIRED` Orders.

### Immutable persistence and migration shape

Add one forward Alembic migration after `0005_phase_3_failure_persistence`; update SQLAlchemy models and focused repositories in lockstep.

1. **Experiments:** permit `PENDING`; new Phase 4 rows default to `PENDING`. Existing Phase 3 rows and model versions are retained unchanged. Strengthen the immutability trigger so only the legal lifecycle fields can change and terminal rows are wholly immutable.
2. **Orders:** add nullable self-FK `parent_entry_order_id`; Phase 4 protection Orders require it and `(parent_entry_order_id, purpose)` is unique. Entry/end-exit Orders leave it null.
3. **OrderEvents (new append-only table):** `id`, `order_id`, positive `sequence_number`, event type, UTC `occurred_at`, optional source MarketBar ID, bounded JSON details; unique `(order_id, sequence_number)`.
4. **RiskDecisions:** add nullable `actual_risk`; required for approved Phase 4 PRE_SUBMISSION decisions.
5. **Fills:** add nullable-for-legacy, required-for-Phase-4 `source_market_bar_id`, `price_basis` (`OPEN`, `OPEN_GAP`, `INTRABAR_STOP`, `INTRABAR_TARGET`, `END_CLOSE`), executable reference price, slippage per unit, and slippage cost. Existing `execution_price` is the economic price and existing `fee` is USD commission. Fill/order sequence uniqueness remains the idempotency boundary.
6. **Trades:** add nullable-for-legacy, required-on-Phase-4 completion `initial_risk`, `commission_cost`, nullable `financing_cost`, `net_pnl`, `r_multiple`, `intrabar_ambiguous`, ambiguity policy, ambiguity observation time, and ambiguity source MarketBar ID. Constrain Phase 4 exit reasons to the three in-scope values. A numeric financing value is forbidden when financing mode is excluded.
7. **ExperimentEquityPoints (new append-only table):** composite key `(experiment_id, sequence_number)`; UTC observation time; balance, realized/unrealized P&L, equity, running peak, drawdown amount/percent; optional valuation BID/ASK and source BID/ASK MarketBar IDs (null only for the starting point); unique `(experiment_id, observed_at)`.
8. **ExperimentResults (new append-only one-to-one table):** Experiment FK/PK; result schema version; Trade and ambiguity counts; gross P&L, commission, nullable financing, modeled net P&L; ending balance/equity, net return, max drawdown amount/percent; financing disclosure; completed market time; 64-character output fingerprint.
9. **Terminal guards:** append-only triggers protect OrderEvents, Fills, equity points, results, TradeIntents, and RiskDecisions. Parent-aware guards reject inserts/updates/deletes against a terminal Experiment and freeze terminal Orders, Position, ExperimentAccount, and Trades. Completion inserts the result and freezes the graph in one transaction.
10. **Legacy compatibility:** no Phase 3 result/cost/provenance value is fabricated or backfilled. New fields remain nullable for legacy rows; Phase 4 completion validation enforces their presence only for `PHASE4_HISTORICAL_EXECUTION_V1`.

The run is one caller-owned database unit of work with nested savepoints around each financial transition. A handled domain/strategy/risk/execution failure rolls back only the current transition, persists categorized diagnostics, retains prior facts, and commits `FAILED`. A database outage that prevents durable diagnostics must roll back the whole run and propagate; Atlas must not report false completion or false persisted failure.

### Failure and unknown-state handling

- Failure categories remain `VALIDATION`, `MARKET_DATA`, `STRATEGY`, `RISK`, `EXECUTION`, `PERSISTENCE`; codes are stable, sanitized, and specific. Never infer category from error-message substrings.
- Invalid config/provenance/coverage fails before any Order. Missing/contradictory M1 sides, nonpositive prices after slippage, impossible lifecycle, duplicate frontier, or absent end quote fails rather than guessing.
- Expected Risk rejection is not an Experiment failure. Unknown account/Position/equity or projection disagreement is a `RISK` failure and blocks new exposure.
- Historical simulation has no broker uncertainty, so Order `UNKNOWN`, reconciliation, and blind retry do not apply and must not be introduced.
- If failure occurs while a simulated Position is open and no truthful close price exists, retain the open Position/Orders as partial FAILED facts, persist that exposure was not closed and why, and omit ExperimentResults. Never invent a Fill or mark `COMPLETED`.
- A FAILED Experiment is not resumable or retryable. A new deliberate run requires a new Experiment. A process/database abort that committed nothing leaves `PENDING`, not an ambiguously `RUNNING` result.
- Failure reporting must answer: what failed, the last durable market frontier, whether simulated exposure remains open, what Atlas did, and that no real broker exposure exists.

### Explicit exclusions

- No PAPER/LIVE mode, TradingAccount, Deployment, OANDA order submission, broker adapter/connectivity, credentials, external API call, broker-hosted protection, reconciliation, or broker `UNKNOWN` handling. OANDA is historical DatasetSnapshot provenance only.
- No FastAPI endpoint, Next.js/UI/chart/result screen, notification, or user workflow.
- No `atlas-runtime`, scheduler, polling loop, worker, restart ownership, command queue, Redis, message broker, distributed execution, supervisor, or container architecture.
- No optimization, parameter sweep, comparison/ranking, parallelism, generalized analytics framework, export, or notebook.
- No multi-instrument/provider/strategy/account generalization; no Strategy special-case infrastructure despite the fixed reference slice.
- No financing calculation, margin engine, daily-loss/drawdown blocking, partial Fill behavior, partial exit, pyramiding, manual close, RISK_EXIT, trailing stop, protection update, instant reversal, or cancellation workflow.
- No performance optimization beyond ordinary deterministic queries/batching proven necessary by tests.

### Ordered sequential implementation

Implementation remains blocked pending human approval and `READY`. Recommended assignments are sequential, with one writer at a time:

1. **Persistence owner — migration and model contract:** add the Phase 4 migration, model fields/tables, constraints/triggers, and repository methods under `backend/persistence/`. Preserve all Phase 3 rows. Validate upgrade/downgrade on an isolated database before handoff.
2. **Simulation owner — frontier contract:** reshape `backend/experiments/clock.py` and market-data reads to yield chronological M1 observations and M15 decision frontiers with exact warm-up/end/session semantics. Do not create a second aggregator.
3. **Execution owner — pure deterministic adapter:** revise `backend/execution/contract.py` and `simulated.py` for adverse slippage, entry, stop, target, gap, ambiguity, end close, and explicit source/price provenance. Keep it free of sessions, I/O, Strategy, and Risk.
4. **Accounting owner — Fill application:** extend `fill_application.py` so Fill + OrderEvent + Position + Trade + account/cost changes are atomic, sequence-safe, multi-Trade capable, and protection siblings terminate correctly.
5. **Experiment owner — orchestration:** refactor `runner.py` and focused repositories into the exact loop above; use actual Position/equity, persist expected Risk rejections, generate deterministic keys/sequences, append equity, compute results/fingerprint, and enforce legal terminal transitions.
6. **Validation owner — deterministic tests:** add/adjust unit and PostgreSQL integration fixtures only after implementation handoff. No live credentials. Compare ordered semantic projections and fingerprints across fresh Experiment IDs.
7. **Review owner — production gate:** review against this blueprint, governing invariants, migration safety, exclusions, and full validation matrix. Any material deviation returns to the architect/human; it is not silently accepted.

### Validation and acceptance matrix

| Area | Required proof |
| --- | --- |
| Input/provenance | Reject wrong StrategyVersion, instrument/provider/components, invalid config, insufficient warm-up, out-of-range snapshot, unexpected gap; preserve exact immutable references and config. |
| Frontier | UTC half-open boundaries; warm-up cannot expose; one evaluation per M15 bar; no future bars; signal M1s never execute their decision; end bar not evaluated. |
| Entry/Risk | Long ASK and short BID; actual adverse-slipped entry drives stop geometry, quantity, target, actual risk; PRE_FLIGHT/PRE_SUBMISSION rejections persist and continue. |
| Protection | Long BID/short ASK liquidation; stop and target; gap-through worse open; no target improvement; same-bar entry ordering; dual touch stop-first with affected Trade recorded. |
| Lifecycle | Complete OrderEvent sequences; both protection Orders after entry; winner filled/sibling canceled; Fill-only exposure; one Position; no pyramid/reversal/partial exit. |
| Multi-Trade | At least two sequential long/short Trades, deterministic Trade sequences/correlation IDs, later M15 evaluation after flat, no uniqueness collisions. |
| Costs/accounting | Spread embedded once; explicit zero and nonzero adverse slippage; explicit zero and nonzero commission; financing null plus exact disclosure; long/short gross/net P&L and R multiple from actual Fills. |
| Equity/results | Starting point plus every eligible M1 close; long BID/short ASK unrealized P&L; balance/equity distinction; running peak/max drawdown; zero-Trade valid result; counts reconcile. |
| End handling | Open Trade closes at final eligible side close with adverse slippage and `END_OF_EXPERIMENT`; expected closure lookup works; missing/incomplete/unexpected-gap quote fails without fabricated Fill. |
| Failure/immutability | Strategy, market-data, Risk unknown, execution invariant, and persistence failure paths; partial FAILED facts inspectable; no result row on failure; terminal graph rejects mutation/deletion/late insert. |
| Reproducibility | Two new Experiments with identical semantic inputs produce byte-identical canonicalized semantic facts, equity/metrics, ambiguity set, and output fingerprint despite different UUIDs/audit times. |
| Boundary | Automated checks/review confirm Strategy has no I/O/environment branch and implementation imports no API/UI/runtime/broker/PAPER/LIVE/optimization infrastructure. |

Acceptance requires all existing unaffected tests plus the matrix above to pass. No live OANDA credential test is permitted or needed.

### Rollback implications

- The migration downgrade is destructive to Phase 4-only tables/columns and is permitted only before any Phase 4 Experiment exists. Once Phase 4 facts exist, use a forward-fix migration; do not delete or rewrite immutable results to enable downgrade.
- Rolling application code back while retaining the additive schema is acceptable only if old code is prevented from creating/running Phase 4 model versions. Existing Phase 3 records remain readable and untouched.
- A simulation-policy change requires a new engine/model/config schema version and new Experiments. A Strategy methodology change separately requires a new StrategyVersion. Neither permits mutation of completed results.
- No automatic commit, push, merge, branch deletion, worktree cleanup, or data cleanup belongs to this blueprint.

### Worktree and approval requirements

- Assigned repository root/cwd: `/Users/vike/Desktop/atlas`.
- Isolation scope: only the approved Phase 4 application/migration/test files; dispatch artifacts remain controlled by Orchestrate. A dedicated local feature branch in the current checkout is the default. A linked worktree is opt-in only if the human explicitly requests it.
- After blueprint approval, the `worktrees` workflow must obtain exact confirmation immediately before every Git-changing command. This blueprint grants no Git authorization.
- Builders may start only after `READY` records mode, repository root, assigned path, branch, full base SHA, scope, status, context, and recovery instructions.
- Human approval of this blueprint and workflow is required before `READY` or implementation. Approval does not authorize commit, push, merge, or cleanup.
