# Phase 4 Historical Execution — Exploration

## Boundary and recommendation

The smallest safe Phase 4 outcome is a deterministic, persisted Experiment runner that can replay the selected EUR/USD DatasetSnapshot across the requested period, evaluate the immutable StrategyVersion only on completed 15m bars, and simulate all post-decision 1m execution until the Position is closed or the Experiment ends. It should produce canonical TradeIntent, RiskDecision, Order, Fill, Position, Trade, account/equity facts, and explicit assumptions/results provenance.

This is the narrowest step from the current `PHASE3_OPEN_CHECKPOINT_V1`: generalize the existing one-trade/single-target path into a chronological historical execution model, without building a new domain or operational platform. The implementation blueprint should keep the current EUR/USD, OANDA-source, USD, EMA Sweep Engulfing, 15m/1m slice fixed. Do not add optimization, parallelism, analytics infrastructure, or a generic execution framework.

## In-scope candidate behavior

- Validate Experiment inputs and DatasetSnapshot coverage, then run the requested period with Strategy warm-up before exposure; a zero-Trade Experiment is valid.
- Preserve the decision/execution frontier: a completed 15m MID bar drives evaluation, and only subsequent 1m BID/ASK observations can execute the decision. Never reuse signal-bar data.
- Process chronological 1m observations after entry, including executable-side semantics: long entry/exit on ASK/BID respectively and short entry/exit on BID/ASK respectively.
- Simulate deterministic spread through BID/ASK, separately model configured slippage (including no favorable improvement), and apply only explicitly configured costs. Disclose excluded financing rather than silently treating it as zero.
- Create the canonical protective STOP_LOSS and TAKE_PROFIT behavior from actual executable entry, including gap-through stops at the first eligible worse price.
- Resolve an OHLC bar touching both stop and target conservatively as stop/adverse-first, and persist/report the ambiguity and policy.
- Enforce actual frontier ordering when entry and protection occur in the same subsequent 1m observation; protection cannot precede the entry Fill.
- Continue evaluating later completed bars after a closed Trade, while preserving v1 restrictions: one Position, no pyramiding, no intentional partial exits, and no instant reversal.
- Close an open Position at the final eligible executable price with `END_OF_EXPERIMENT`; update Fill-driven Position/Trade/account state and retain equity history sufficient for drawdown and metrics.
- Complete or fail explicitly, retaining immutable input configuration, engine/model version, assumptions, failure category/detail, and deterministic output provenance. Identical inputs must reproduce intents, decisions, orders, fills, trades, equity history, and metrics.

## Explicit exclusions / no-scope-creep boundary

- No PAPER or LIVE trading, OANDA order submission, broker connectivity, broker reconciliation, credential handling, or external API integration. Historical OANDA data may remain the DatasetSnapshot source; it is not an execution venue in this slice.
- No API endpoints, UI, charts, result screens, notifications, or user workflow. Result persistence can be shaped for later inspection but must not expand into Phase 5.
- No `atlas-runtime`, scheduling, long-running process, deployment lifecycle, restart ownership, polling, command queue, worker pool, Redis, message bus, distributed execution, or supervisor.
- No optimization, parameter sweeps, experiment comparison, ranking, parallel workers, generic analytics framework, report export, research notebooks, or generalized multi-broker/multi-instrument/multi-strategy support.
- No manual close, RISK_EXIT, daily-loss engine, drawdown blocking, margin complexity, financing implementation unless explicitly chosen as a documented simulation assumption, partial exits, pyramiding, trailing stops, or instant reversal.
- No separate Backtest/Execution/Trade/Order/Fill models. Reuse canonical Experiment and trading types; `Execution` remains a workflow boundary, not a persisted entity.
- Phase 3 OBS-1/OBS-3 are optional planning inputs summarized by `dispatch/workstreams/phase-4-historical-execution/PLAN.md`, not authorized remediation or requirements; historical reports are intentionally not consulted.

## Governing invariants

- StrategyVersion, DatasetSnapshot, and completed Experiment inputs/results are immutable; rerun means a new Experiment.
- Strategy sees only completed canonical bars available at the simulation frontier, uses UTC boundaries, and cannot access execution resolution, storage, broker/API, account balance, or Risk sizing. Strategy remains environment-independent.
- 1m is the historical base/execution resolution and 15m is the reference evaluation resolution; aggregation is deterministic and missing data is never fabricated.
- A completed signal bar is not post-decision execution data; the same completed bar is evaluated at most once.
- Fill facts, not Order submission, change exposure and accounting. Position derives from Fills; Trade is the flat-to-flat episode.
- Risk remains centralized: PRE_FLIGHT checks structural eligibility, PRE_SUBMISSION checks actual executable quote/stop geometry and sizes quantity. Unknown or invalid state rejects rather than guessing.
- Decimal-safe authoritative financial values; P&L uses actual Fill prices, executable liquidation sides, and explicit costs without double-counting spread.
- Intrabar uncertainty is recorded and resolved adverse-first. No invented exit sequence or favorable price improvement.
- End-of-Experiment handling is deterministic and explicit. Failed Experiments preserve diagnostics; an open Position is never silently abandoned.

Governing sources: `AGENTS.md`; `context/roadmap/roadmap.md` (Phase 4 goal/exit); `context/features/experiments.md`; `context/architecture/domain-model.md`; `context/architecture/strategy-contract.md`; `context/architecture/market-data-model.md`; `context/architecture/accounting-model.md`; `context/architecture/runtime-model.md`; `context/architecture/safety-model.md`.

## Current Phase 3 contracts/modules

- `backend/experiments/clock.py`: `SimulationClock` already separates warm-up, completed M15 decision bars, and post-frontier BID/ASK opens; it currently exposes only a narrow frame and does not replay the full 1m execution stream.
- `backend/experiments/runner.py`: `ExperimentRunner` composes snapshot aggregation, Strategy, Risk, simulated execution, persistence, and Fill application, but explicitly runs until its first completed Trade (`MODEL_VERSION = PHASE3_OPEN_CHECKPOINT_V1`). It currently hardcodes flat Strategy position context, opens one entry, watches one target, and fails on unsupported intrabar/stop cases.
- `backend/execution/simulated.py` and `backend/execution/contract.py`: pure adapter and observation/order contract; Phase 3 assumes full fills, has no deterministic slippage/cost model, and rejects intrabar triggers and stop gaps.
- `backend/execution/fill_application.py`: sole Fill-to-financial-projection boundary; currently requires one full sequence-one Fill, zero fee, and updates Position/Trade/account for entry and exit.
- `backend/risk/service.py`: explicit two-stage, fail-closed EUR/USD/USD risk and actual BID/ASK sizing; it already resolves target from executable entry.
- `backend/persistence/experiment_repository.py` and `backend/persistence/models.py`: Experiment configuration/status/failure, simulated account, canonical intents/risk/orders/fills/positions/trades. Existing constraints include immutable-style terminal lifecycle, one intent per experiment frontier, one risk decision per phase, and one Position per experiment/instrument.
- `backend/market_data/aggregation.py` and `backend/persistence/market_data_repository.py`: existing 1m snapshot inputs and deterministic 1m→15m derivation boundary used by the runner.
- Existing behavioral evidence is limited to the current source/tests, notably `backend/tests/experiments/test_clock.py`, `backend/tests/execution/test_simulated.py`, `backend/tests/integration/test_fill_application.py`, and `backend/tests/integration/test_golden_flows.py`. These are current contracts, not authorization to preserve Phase 3 limitations.

## Risks and unresolved product decisions

1. **Execution observation shape:** Decide whether the clock yields every eligible 1m observation (including BID/ASK OHLC) or a narrower execution frame. The latter must still retain enough data for gap-through and ambiguity without leaking future information.
2. **Intrabar precedence:** The feature/architecture sources require adverse-first, but the persisted result shape and exact ambiguity count/affected-Trade representation need an authoritative schema decision.
3. **Stop/target order lifecycle:** Decide how protective Orders are represented and transitioned when one triggers, and how the untriggered sibling is canceled/closed in simulation without implying broker behavior.
4. **Multiple Trade persistence:** Existing constraints support sequence-numbered Trades, but the runner and current Fill application are written around one open Trade; the blueprint must define chronological state transitions and unique/idempotent keys.
5. **End pricing:** Define the final eligible BID/ASK observation when the requested end is inside a gap/session break or lacks a complete executable quote; reject rather than invent a price.
6. **Cost configuration:** Decide the minimal immutable simulation-config schema for slippage, commission, and financing exclusion/disclosure. Do not silently default unavailable costs to zero.
7. **Equity history and metrics:** Specify the minimum persisted sampling frontier and derived metrics needed for Phase 4 acceptance, while deferring the Phase 5 presentation contract.
8. **Failure and partial state:** A mid-run failure must remain FAILED with inspectable diagnostics and must not be mistaken for a completed result. Transaction boundaries must avoid duplicate facts if a run is retried; a rerun should be a new Experiment.
9. **Phase 3 observations:** PLAN permits OBS-1/OBS-3 as optional planning inputs only. The architect should confirm whether the proposed narrow slice addresses either observation; neither should enlarge the acceptance boundary.

## Validation implications

The blueprint should require deterministic unit and integration fixtures, not live credentials. Minimum gates are: warm-up/no exposure; exact UTC/frontier/no-lookahead and signal-bar separation; duplicate decision prevention; long/short ASK/BID entry and liquidation; spread without double-count; explicit slippage; actual-entry target; stop and target fills; gap-through stop; adverse-first ambiguity recording; same-bar entry/protection ordering; multiple sequential Trades; no-pyramiding/no-reversal; end close; zero-trade; costs/financing disclosure; equity/drawdown history; failure persistence; and identical-input replay of all canonical facts. These expectations are stated in `context/features/experiments.md` and reinforced by `context/architecture/market-data-model.md` and `context/architecture/accounting-model.md`.

Validation must also prove no forbidden boundary was crossed: Strategy has no external I/O or environment branch; the Experiment does not use `atlas-runtime`, API, UI, broker execution, or PAPER/LIVE state; and no separate historical trading nouns are introduced.

## Architect handoff

Produce an authoritative blueprint for one narrow, persisted, deterministic multi-Trade historical Experiment slice: extend the existing clock/runner/simulated execution/fill-accounting path to consume post-decision 1m BID/ASK observations, model conservative protection/costs/ambiguity/end handling, and preserve canonical facts. Resolve the nine decisions above before task breakdown. Make every PAPER/LIVE, broker/API/UI/runtime, optimization, and generalized-infrastructure item an explicit non-goal. No READY receipt, Git operation, or implementation is authorized until a human approves that blueprint, per `dispatch/ACTIVE.md` and `dispatch/workstreams/phase-4-historical-execution/PLAN.md`.
