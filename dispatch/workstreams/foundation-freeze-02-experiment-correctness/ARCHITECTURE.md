# Foundation Freeze 02 — Architecture Audit

Status: `ARCHITECTURE AUDIT COMPLETE — IMPLEMENTATION UNAUTHORIZED`

## Authority and audit basis

The Foundation Freeze 02 contract and corrected `ema_sweep_confirmation_break.v2`
are authoritative. The relevant product/architecture contract is
`context/features/experiments.md` (especially §§32–98), with domain rules in
`context/architecture/{domain-model,accounting-model,market-data-model,strategy-contract}.md`.
This is a first-pass audit, not an approval to change code.

## Authoritative V2 flow (current reachable path)

`ExperimentRunService.run` (`backend/experiments/lifecycle.py:152`) claims the
row under lock and commits the RUNNING claim before execution. It invokes
`ExperimentRunner.run` (`backend/experiments/runner.py:429`), which accepts only
`ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2` and otherwise fails closed. `_run_v2`
(`runner.py:449`) loads immutable persisted native M15 MID analytical bars and
sparse provider M1 BID/ASK members, then constructs `SimulationClock` with
historical context and the requested UTC period.

The sequence is: initial equity at `trading_start`; warm-up completed M15 bars
with exposure disabled; each decision frontier exactly once; strategy evaluation
through `evaluate_strategy` and the corrected `EmaSweepConfirmationBreakStrategy`
(`backend/strategies/ema_sweep_confirmation_break.py:113`). A confirmation creates
a PRICE_TRIGGERED `TradeIntent` via `_create_intent` (`runner.py:1444`), retaining
setup facts, source IDs and landmarks. The pending trigger is consumed only by
subsequent eligible M1 observations; the strategy state watch count controls the
five-bar window, W5 remains eligible, and W6 expires it (`runner.py:573–763`).

On executable entry, `_attempt_entry` (`runner.py:1517`) performs PRE_FLIGHT Risk,
then PRE_SUBMISSION Risk against the adverse-slipped executable BID/ASK, creates
an ENTRY Order, obtains a canonical Fill from `SimulatedExecutionAdapter`, and
applies it through `apply_fill`. It derives target from the actual fill, creates
STOP_LOSS and TAKE_PROFIT child Orders, submits both, and resolves protection.
`_apply_protection`/`_apply_pair` (`runner.py:1725–1779`) use the adapter's
adverse-first dual-touch policy. Fill application derives Position and Trade
(`backend/execution/fill_application.py:apply_fill`); open exposure is valued on
LONG BID/SHORT ASK. Protection is applied before each eligible M1-close equity
sample; the initial boundary sample precedes all observations. An open Position
is closed at the final eligible M1 close by `_close_at_end` (END_OF_EXPERIMENT),
then a terminal equity point is written.

`_complete_v2` (`runner.py:891`) persists gap decisions and quality, then currently
delegates to `_complete_phase4` (`runner.py:1903`). That function reads terminal
Trade/equity facts, calculates metrics, hashes `_semantic_payload` (which includes
strategy/dataset fingerprints, inputs, intents, risk, orders, fills, trades and
equity), creates `ExperimentResultModel`, and marks the Experiment completed.
The lifecycle flushes/commits atomically; committed partial RUNNING facts are
classified `INCOMPLETE_RUN_STATE` on a subsequent command.

### One complete Trade (canonical expected trace)

For a LONG confirmation at frontier T: M15 confirmation is persisted as an intent
with ASK trigger and stop; first eligible M1 after T supplies ASK entry/BID
execution context. PRE_FLIGHT and PRE_SUBMISSION approve quantity and stop
geometry. ENTRY Order → submitted/fill at adverse ASK → Position LONG and OPEN
Trade; STOP and LIMIT target are persisted and protected. A later M1 BID/ASK
touch either fills target at requested price or stop at requested/gap price (stop
wins an unknowable dual touch), recording price basis, source bar, slippage,
commission and ambiguity. `apply_fill` closes the Position and Trade, computes
gross/net P&L and R multiple; account realized P&L and equity are updated. If
neither protection fires, END_OF_EXPERIMENT uses final eligible close and the same
accounting path. Short is the symmetric BID-entry/ASK-liquidation case.

## Contract findings (PASS / MISMATCH / UNVERIFIED)

| Requirement | Finding and exact seam |
|---|---|
| V2 native M15 + sparse M1, no lookahead, completed frontier once | **PASS** — `runner._run_v2`; `SimulationClock`; `strategy.contract.evaluate_strategy`; signal bar is not reused (`observation.start_time > frame.frontier`). |
| Corrected V2 pending trigger and W1–W5/W6 expiry | **PASS** — `ema_sweep_confirmation_break._step` and runner pending handoff. |
| Strategy boundary and immutable StrategyVersion/DatasetSnapshot | **PASS** at boundary — `strategy.contract`, `models.py:52–80,186–213`; **UNVERIFIED** full DB immutability in the deployed revision. |
| PRE_FLIGHT then executable PRE_SUBMISSION Risk | **PASS** — `runner._attempt_entry`; `backend/risk/service.py:RiskService`. |
| Canonical Order/Fill/Position/Trade, protection and conservative ambiguity | **PASS** — `runner`, `simulated.py`, `fill_application.py`, `models.py:484–592`; **UNVERIFIED** every partial-fill boundary (V2 assumes full fill). |
| Accounting, spread/slippage/commission and financing disclosure | **PASS** for implemented model — `runner._sample_equity`, `fill_application`, simulation config validation; financing is explicitly excluded. |
| Equity sampling and ordering | **PASS** runner policy: boundary then each eligible M1 close, protection first, terminal close deferred; `runner._sample_equity` enforces sequence/time uniqueness. **MISMATCH** metric ordering contract is not solely persisted canonical order: `metrics.calculate_metrics` re-sorts by timestamp and uses input order only for equal timestamps. |
| Completion only with persisted ExperimentResult | **MISMATCH** — `_complete_phase4` creates the result, but `mark_completed` follows it in the same transaction and no DB invariant shown requires a result for COMPLETED. |
| Persist all headline metrics and metric states | **MISMATCH** — `ExperimentResultModel` persists Sharpe/profit factor/win rate/expectancy states, but net return and drawdown have no state/reason; API recomputes all metrics. |
| Approved Sharpe methodology | **PASS** as current implementation only: UTC daily last equity per day, sample variance, annualization √252 (`metrics._daily_returns`, `calculate_metrics`). **UNVERIFIED** that this is the contract-approved methodology rather than merely existing behavior. |
| Unavailable/degenerate metrics | **PASS** pure calculator: zero trades, no equity history, insufficient daily returns, zero variance, no profit/loss and infinite profit factor are explicit. **MISMATCH** persisted schema cannot represent reasons for all metrics and rejects infinite numeric values by storing NULL/state separately. |
| Normal detail must not recalculate from Trades/equity | **MISMATCH (critical)** — `ExperimentResultReadService.detail:125–144` loads up to 100,000 Trades/equity and calls `_metrics`; API detail/list call it (`api/experiments.py:483–503,532–545`). Persisted result is not the read authority. |
| Equity/trade list/detail reads bounded and immutable | **PASS** read-only repository queries (`result_repository.py`); **MISMATCH** list performs N+1 detail/trade/equity reads and recalculation; trade detail endpoint does not call `_completed` before `results.trade` (`api/experiments.py:618–627`). |
| Fingerprint/reproducibility | **MISMATCH** input/fact semantic fingerprint exists in `_semantic_payload`, but excludes metric methodology/schema and result quality, and `runner_inputs_digest` is diagnostics only. **PASS** StrategyVersion source and DatasetSnapshot fingerprints are included and immutable inputs are snapshotted. |
| Ambiguity/result quality semantics | **PASS** ambiguity is recorded on Trade and result counts; gap quality is persisted by `_complete_v2`. **MISMATCH** model check allows `DETERMINED_WITH_GAPS` and `CONSERVATIVE_AMBIGUITY_RESOLVED`, but `result_quality_for_gaps` emits only DETERMINED/DEGRADED; ambiguity does not itself drive quality. |
| Failure classification and durable fail-closed state | **MISMATCH** broad `_run_v2` `ValueError` becomes MARKET_DATA/INVALID_INPUT and broad Exception becomes PERSISTENCE, masking Strategy/Risk/Execution distinctions; lifecycle fallback is durable but generic. |
| Result schema can persist state, methodology/schema, quality, fingerprint | **PASS in scope** — `models.ExperimentResultModel` has `metric_states`, `metric_schema_version`, `result_quality`, `output_fingerprint`; no migration is needed for those fields in the current model/revision. **MISMATCH** net-return/drawdown states and per-metric reasons still need representation, and fingerprint payload must own methodology. |

## Legacy and specification classification

* **Authoritative:** V2 snapshot gate and `_run_v2`; corrected strategy file;
  canonical domain/execution/fill models; `ExperimentResultModel` and read-only
  repository are the intended boundaries.
* **Reachable legacy:** `_complete_phase4` is called by V2 and is therefore a
  misleadingly named shared completion seam. `fill_application.py` retains
  `PHASE4_HISTORICAL_EXECUTION_V1` behavior. Migration `0006_phase_4_persistence_contract.py`
  retains compatibility triggers and Phase 4 guards. These affect schema/runtime
  semantics and must not be treated as documentation only.
* **Dead legacy for new runs:** `_run_phase4` (`runner.py:939`) is not selected by
  `ExperimentRunner.run`; non-V2 runs fail `UNSUPPORTED_EXPERIMENT_MODEL`. Its
  diagnostic types, comparison machinery and Phase 4 stages remain importable
  and are used by legacy tests/e2e diagnostics.
* **Stale specification/fixtures:** `backend/tests/experiments/test_runner_diagnostics.py`,
  `test_price_analysis_results.py`, `tests/e2e_seed.py`, and comments/config names
  still encode PHASE4 or `ema_sweep_engulfing.v2`; they are evidence of reachable
  compatibility, not authority. `context/features/experiments.md` is authoritative
  where it states V2 semantics, but its “EMA Sweep Engulfing” label is stale versus
  the corrected confirmation-break implementation.

## Smallest authoritative remediation (implementation design only)

1. Make a single V2 completion function the authority (rename or wrap
   `_complete_phase4` without changing domain behavior) and require the result row
   before marking COMPLETED, preferably with a DB/API invariant.
2. At completion, calculate once from canonical ordered persisted facts and persist
   every metric as `{state,value,unit,reason}` (or equivalent state/reason columns),
   plus the approved Sharpe methodology identifier and metric schema version.
   Extend only `backend/persistence/models.py`,
   `backend/persistence/experiment_repository.py`, runner completion, and the
   minimal Alembic migration required by the existing schema strategy.
3. Define output fingerprint ownership in the completion seam: canonicalize
   ordered inputs/facts + metric methodology/schema + quality; hash that payload.
   Persist the resulting schema/version alongside `output_fingerprint`.
4. Change `ExperimentResultReadService.detail` and API list/detail to read the
   persisted result projection, never recalculate from Trades/equity. Keep equity
   and trade endpoints as bounded fact reads; enforce completed-result existence
   for trade detail. Exact seams: `backend/experiments/results.py:detail`,
   `backend/api/experiments.py:_detail/listing/detail`, and repository result query.
5. Replace broad runner exception mapping with explicit validation/market-data/
   strategy/risk/execution/persistence classification and preserve sanitized,
   inspectable failure codes; leave lifecycle fallback as last-resort persistence
   failure.
6. After approval, quarantine/remove dead Phase 4 paths only if compatibility
   migration/test consumers are explicitly retired; do not silently delete them.

## Invariants and boundary examples

* Same `(StrategyVersion, DatasetSnapshot, parameters, Risk, simulation, capital,
  period, engine, methodology)` yields byte-equivalent canonical facts/result;
  changing any one changes the output fingerprint.
* No decision before a completed M15 bar; M1 at exactly the signal-bar boundary
  is not entry data; first eligible observation is strictly after frontier.
* W5 observation may fill; W6 frontier expires; a missing eligible observation
  creates a disclosed gap and cannot fabricate a fill.
* LONG entry/valuation/liquidation use ASK/BID respectively; SHORT uses BID/ASK.
  Stop geometry is strict (`stop < entry` long, `stop > entry` short).
* Two protection touches in one unknowable M1 bar resolve STOP_LOSS, record
  ambiguity and policy; no protection may execute before entry Fill.
* Zero trades is a valid COMPLETED result: trade-dependent metrics are
  UNAVAILABLE with reasons, while the equity series and net-return state remain
  authoritative. One daily return makes Sharpe UNAVAILABLE; two equal returns
  make it ZERO_VARIANCE.
* Open exposure at end requires a final eligible M1 quote; otherwise the run is
  FAILED with market-data uncertainty, never a fabricated exit.
* Completed/failed configuration and result graph are immutable; rerun creates a
  new Experiment.

## Required ordered implementation and evidence (after approval)

1. Schema/domain result-state contract and migration; prove persistence constraints
   and immutable terminal graph.
2. V2-only completion/fingerprint/quality implementation; unit tests for every
   metric state, Sharpe methodology and canonical ordering.
3. Read-path switch; public API tests prove detail/list do not invoke calculation,
   completed result is returned, and missing result is a deterministic conflict.
4. Failure taxonomy tests for each category, unknown state, missing final quote,
   gap/ambiguity quality, and lifecycle fallback.
5. Golden public/domain replay: long and short complete Trade, trigger W5/W6,
   same-bar protection, gap-through, end close, zero-trade, and identical-input
   fingerprint equality. Validate with migration/integration tests and a final
   repository search showing no new-run Phase 4 selection.

## Approval gate (historical pre-approval state)

Before the developer approval recorded below, implementation was unauthorized.
The approved clarifications now govern the implementation phase.

## Approved implementation clarifications

Developer approval was received on 2026-08-27. These decisions amend and bind
the remediation above:

- **Sharpe methodology:** use canonical persisted equity; select the last
  canonical endpoint per UTC day; calculate the first return from starting
  capital to that endpoint and later returns endpoint-to-endpoint; use no
  interpolation or forward-fill, risk-free rate zero, sample standard
  deviation, and annualization `sqrt(252)`. Fewer than two returns is
  `UNAVAILABLE`; zero variance is `UNAVAILABLE` with reason `ZERO_VARIANCE`.
  Persist a stable methodology/schema identifier.
- **Canonical equity:** metric calculation consumes persisted canonical sequence
  order directly and never re-sorts timestamps to recreate authority. The
  terminal point must be written after end-of-Experiment closure and final
  accounting/commission; a stale pre-close point cannot be result truth.
- **Metric state:** prefer the existing `metric_states` and numeric result fields
  for every headline metric and its state/reason. Add schema only if an actual
  insufficiency is demonstrated; do not add a normalization-only migration.
- **Completion:** enforce `COMPLETED => persisted ExperimentResult exists`
  transactionally in application/repository lifecycle code. Do not add a
  cross-table trigger unless genuinely necessary.
- **Result quality:** derive quality deterministically from persisted uncertainty:
  material data uncertainty => `DEGRADED`; otherwise conservative dual-touch
  ambiguity => `CONSERVATIVE_AMBIGUITY_RESOLVED`; otherwise `DETERMINED`.
  Define any distinct `DETERMINED_WITH_GAPS` meaning before using it; do not
  preserve stale enum vocabulary without semantics.
- **Simulation scope:** retain the deterministic full-fill historical model;
  partial-fill/PAPER behavior remains out of scope.

Implementation may now proceed on the recorded branch, with these decisions
governing BUILD and validation.
