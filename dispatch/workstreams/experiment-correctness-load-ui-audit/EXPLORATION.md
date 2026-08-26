# Exploration — Experiment correctness, historical load, and UI audit

## Scope and governing contracts

- `AGENTS.md:19-21,47-53` — completed Experiments/results are immutable; no lookahead; only completed bars; equity history must remain reproducible; raw IDs are not normal UI labels.
- `context/features/experiments.md:15-26,32-46,80-98` — setup lifecycle is load → snapshot → M15 → validation; warm-up is prior history with no exposure; equity history and deterministic metrics are required.
- `context/features/experiment-results.md:7-25,35-57,67-73` — results hierarchy is identity/status → headline metrics → equity/drawdown → Trades → assumptions/provenance; max drawdown uses canonical equity history and Sharpe needs one disclosed return/sampling/annualization methodology.
- `context/features/historical-data.md:15-25,39-49,55-63` — incremental missing-only loading, bounded durable lifecycle, actual warm-up coverage, no silent repair, and bounded provider behavior are the contract.
- `context/design/design.md:7-9,27-33,43-47,75-89` — one primary question per screen, restrained cards/tables, and Experiment results should be simple and scanable.

## Relevant files and behavioral evidence

### V2 equity sampling and metrics

- `backend/experiments/runner.py:413-461,500-540` — V2 runs native M15 decision frames and sparse M1 execution observations, but the V2 path calls `_complete_v2()` after the loop; unlike the Phase 4 path, this excerpt contains no per-observation/per-frontier `_sample_equity` call. This strongly indicates V2 persists only the initial and terminal equity points (subject to `_complete_v2`).
- `backend/experiments/runner.py:577-603` — `_complete_v2` calls `_sample_equity(..., None, 0)` once, then finalizes metrics. This cannot capture an intra-run peak or trough, making V2 max drawdown and daily-return Sharpe materially incomplete when equity changes between endpoints.
- `backend/experiments/runner.py:1006-1028` — `_sample_equity` values open positions on BID for LONG/ASK for SHORT, tracks running peak/drawdown, de-duplicates equal timestamps, and persists `ExperimentEquityPointModel`. The primitive is suitable for correct sampling, but V2 must invoke it at a defined canonical cadence/frontier.
- `backend/experiments/metrics.py:60-80,83-155` — `calculate_metrics` currently uses the last supplied equity row for net return, computes max drawdown from supplied equity points, and computes Sharpe from the last equity point per UTC date with sample variance and `sqrt(252)` annualization. It returns `UNAVAILABLE` for fewer than two daily returns or zero variance. The daily policy is implicit in code and not encoded in the V2 result contract.
- `backend/experiments/metric_contract.py:5-30` — V2 result/metric schema constants exist (`PHASE5_EXPERIMENT_RESULT_V2`, `PHASE5_METRICS_V1`), but only state fixtures for Sharpe/profit factor/win rate/expectancy are defined; no sampling interval, annualization, risk-free rate, or equity sampling policy is represented here.
- `backend/experiments/runner.py:1030-1050` — finalization derives metrics from persisted equity facts and stores scalar metric fields plus metric states. If the V2 equity series is sparse, persisted result scalars/fingerprint are deterministically wrong rather than merely a display issue.
- `backend/api/experiments.py:198-221,470-516` — API exposes both drawdown amount and percent, and returns the equity endpoint's source/returned counts and sampling policy. The list/detail path does not expose a metric methodology object.
- `backend/experiments/results.py:163-200` — equity read loads all rows, then for >2,000 rows emits up to four envelope representatives per bucket (up to 6,000 points), preserving source count and marking `EQUITY_ENVELOPE_V1`. This is presentation-only and does not feed metrics; the implementation is a reasonable bounded chart policy once the canonical source series is correct.
- `backend/tests/experiments/test_results.py:136-179` — tests cover metric state payloads and envelope bounds/edges, but not V2 sampling cadence, drawdown peak/trough capture, daily-return construction, annualization, or methodology disclosure.

### Historical load warm-up/refetch/windowing/status/progress

- `backend/market_data/historical_load.py:25-71,145-162` — first range is fixed at `trading_start - 25h`; hard limits are 90 elapsed days and 40 provider windows. The frontend computes `required_context_bars * 15m`, but server `prepare` does not use that value for its first range.
- `backend/market_data/historical_load.py:164-245` — each warm-up extension loops back through `self.ingestion.load_v2(load_start, row.load_end)`, creates a new snapshot, counts actual native M15 bars, and may extend by another fixed 25h. Thus a 99-bar first result causes a second acquisition of the entire enlarged range, including already fetched trading-period data, rather than a bounded missing-only extension.
- `backend/market_data/ingestion.py:335-359` — missing-only planning exists for the legacy `load_missing` path, but the durable coordinator calls `load_v2` instead. This is the key architectural seam to reconcile; do not infer missing-only behavior from the existence of `plan_missing`.
- `backend/market_data/ingestion.py:590-601` — `load_v2` always fetches native M15 and execution M1 for the complete passed range, then applies execution and creates a V2 snapshot. There is no progress callback passed from the coordinator.
- `backend/integrations/oanda/source.py:232-256,258-299` — one V2 acquisition makes two product fetches (native M15 MID and execution M1 BID/ASK); each `_fetch` divides ranges into 4,000-minute windows. `context/features/historical-data.md:43-45` documents up to 40 windows and up to three transport attempts per window, so repeated warm-up acquisition multiplies HTTP work.
- `backend/market_data/historical_load.py:250-263` — `_progress` can persist fetched/committed ranges and counts, but no call site in `run` invokes it. Therefore the durable API status cannot show meaningful incremental progress during the V2 load.
- `backend/api/historical_data.py:44-95,143-230` — status payload exposes progress arrays/counts, coverage, snapshot, validation, and terminal failure; creation is durable `202` plus background task and active-load conflict is attachable. Status semantics are sound, but currently under-populated by the coordinator.
- `frontend/components/experiment-workflow.tsx:1358-1450,1528-1558` — mount performs configuration options plus capability/active-load requests; coverage validation is an effect triggered whenever strategy, snapshot, start, or end changes. There is no abort/debounce guard, so rapid edits can issue overlapping validations and stale responses can win.
- `frontend/components/experiment-workflow.tsx:1623-1705` — completion refetches options and then validates; load polling is once per second, pauses after three unavailable responses, and correctly does not resend the load. The completion effect is keyed by status/request ID but calls `refreshOptions` and `validate` again even if the user already has equivalent state.
- `frontend/components/experiment-workflow.tsx:2204-2247,2256-2297` — UI displays fetched/committed range counts, member minutes, inserted/reactivated/unchanged, and status-unknown behavior, but not a provider-window/HTTP-attempt estimate or a progress fraction. It promises approximately 30–60 seconds and ~1 poll/sec.
- `backend/tests/test_historical_data_load.py:25-68,290-397` — tests cover deterministic warm-up planning, hard bounds, ordered load-before-validation, V2 preference, and one extension. They do not assert request counts, no-refetch behavior, progress persistence, or coordinator progress callback usage.

### Experiment UI information architecture and formatting

- `frontend/components/experiment-workflow.tsx:513-692,2506-2697` — completed results place seven headline metrics, price analysis, zero-trade messaging, equity, drawdown, Trades, and assumptions/provenance in one long status page; failed/running states correctly suppress trustworthy result facts. This broadly matches the written hierarchy but duplicates analytical context (price analysis before equity and a second chart/detail layer) and makes the primary result scan longer than necessary.
- `frontend/components/experiment-workflow.tsx:283-324` — `MetricCard` formats percent/money/R values and shows unavailable reasons. `frontend/components/experiment-workflow.tsx:106-110` — list-cell `metric` returns raw string values, so list net return/drawdown/Sharpe are not consistently formatted (e.g. ratio `0.125` rather than `12.50%`).
- `frontend/components/experiment-workflow.tsx:535-563,573-598` — detail shows Max Drawdown percent but omits the available Max Drawdown amount; the drawdown chart is amount-based. The result contract calls for both amount and percent, so labeling/formatting should make the relationship explicit rather than silently hiding one.
- `frontend/components/experiment-workflow.tsx:1168-1189,1217-1324` — list has selection, status, period, three headline metrics, trade count, and created date; it uses `Experiment {index + 1}` rather than an intrinsic human-readable identity. This avoids UUIDs but is unstable across pagination/order and should be treated as a display fallback, not durable identity.
- `frontend/tests/experiment_results.test.tsx:158-195,255-288` and `frontend/tests/experiment_list.test.tsx:28-77` — tests verify state rendering, zero-trade/failure behavior, charts, and one raw drawdown value, but do not lock down ratio formatting, amount-vs-percent labels, request counts, or the intended result section order.

## Dependencies and blast radius

- Backend: `ExperimentRunner._run_v2`, `_complete_v2`, `_sample_equity`, `calculate_metrics`, result finalization/API payloads, and their deterministic runner/result tests.
- Historical load: `HistoricalDataLoadCoordinator.run`, `MarketDataService.load_v2`/source acquisition, durable repository progress fields, historical API status schema, and experiment form polling/coverage effects.
- Frontend: the shared `frontend/components/experiment-workflow.tsx` owns list, form, status, result, charts, and trade detail; UI changes have broad test impact. `lightweight-charts` is already the chart dependency; no new dependency is indicated.

## Risks

- Sampling a point after every sparse execution observation can make the series huge; sampling must be defined as canonical facts (for metrics) versus bounded envelope (for presentation), never silently replace canonical equity history with chart samples.
- A daily Sharpe series with only one point per UTC date is not valid unless the policy is explicitly chosen and disclosed; changing cadence or annualization changes immutable result meaning and likely requires a result/metric schema version bump.
- Reusing existing snapshot membership while extending warm-up must preserve DatasetSnapshot immutability/fingerprint provenance; never mutate a completed snapshot in place.
- Removing validation or polling requests can re-enable creation from stale coverage/load state. Any coalescing must preserve durable load status as authority and fail closed.
- Changing list labels or metric formatting can affect comparison/readability, but must not expose raw UUIDs or recalculate from current defaults.

## Unknowns / context gaps

- The intended V2 equity sampling policy is not stated in code/contracts: per completed M1 observation, per decision frontier, per day, or another canonical interval. Human confirmation is required before implementation.
- It is not established whether OANDA native M15 and execution M1 can be independently missing-planned under the current V2 snapshot schema without changing snapshot acquisition semantics.
- No browser/network timing baseline or provider fixture timing is checked into the workstream. Current claims (~30–60s, 1 poll/sec) are UI copy, not measured evidence.
- Result API schema generation may need regeneration after any payload/schema change; current tests use hand-built payloads and do not prove the generated contract.

## Measured timing/request-count methodology

1. Use deterministic fake OANDA transport (no credentials) and a fixed UTC range (for example 30 days) with controlled 4,000-minute window boundaries and a controlled warm-up shortfall (e.g. 99 then 100 eligible M15 bars).
2. Instrument the fake transport to record each HTTP request's product, window start/end, attempt number, and elapsed monotonic time. Instrument `load_v2`/coordinator calls and repository progress writes separately.
3. Compare baseline and proposed behavior on identical seeded DB state in three cases: fully covered range, missing trading-period data, and warm-up extension. Report coordinator acquisitions, native/execution fetch calls, provider windows, HTTP attempts, DB progress writes, wall time, inserted/reactivated/unchanged counts, and final snapshot count.
4. For browser waste, use a fresh page and scripted field changes (initial mount, one date edit, four rapid edits, load completion). Record Network requests by endpoint/method/status and timestamps, plus request overlap/stale-response outcomes. Count expected polling separately from validation/configuration requests.
5. Baseline request expectations from current code: initial options `1`, capability + active-load `2`, coverage validation after each valid dependency change (potentially overlapping), completion options refresh + validation `2`, and active-load polling roughly one GET/sec until terminal or three unavailable polls. A V2 acquisition is at least two provider product fetches, each multiplied by `ceil(range_minutes / 4000)` windows and up to three attempts per window; each warm-up extension repeats the enlarged-range acquisition.
6. For metrics, seed equity facts with an intra-day peak/trough and multiple UTC dates, then assert persisted points, max amount/percent, net return, daily return count, Sharpe state/value, and disclosed policy. Repeat with zero/one/two daily returns and zero variance.

## Recommendations

- Define and version a canonical V2 equity sampling policy first; persist enough facts at that policy's frontier to make drawdown reproducible, and make Sharpe's UTC daily sampling/252 annualization/risk-free assumptions explicit in result provenance. Add runner and metrics regression tests before changing UI.
- Separate canonical equity persistence from the existing `EQUITY_ENVELOPE_V1` chart envelope. Preserve source count and edges/extrema, but never calculate metrics from the envelope.
- Make warm-up extension incremental and measured: reuse existing canonical observations through missing-only planning where safe, fetch only the newly required prefix, and create a new immutable snapshot from the complete final membership. Wire coordinator progress callbacks after each committed provider range; retain durable terminal/unknown semantics.
- Add request instrumentation tests and a repeatable fake-transport benchmark before claiming waste reduction. Debounce/abort coverage validation and guard completion refreshes against equivalent state, while preserving fail-closed creation rules.
- Simplify result IA around the written hierarchy: identity/status and headline metrics first, then equity + drawdown, then compact Trades; move price analysis and lineage into progressive detail. Standardize list/detail formatting (percent, money, ratio, count), explicitly label drawdown amount versus percent, disclose Sharpe methodology, and add UI tests for order and formatted values.
