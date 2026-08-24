# Phase 6 — Strategy Iteration: Exploration

_Read-only evidence for the Architect blueprint. Bounded to Phase 5 implementation, StrategyVersion
persistence/provenance, API contracts, UI routes/components, and relevant context. No architecture
decisions made; labeled recommendations only. Material conflicts reported plainly._

- **Classification:** Architecture (R1) · **Status:** Exploring
- **Read inputs:** `dispatch/workstreams/phase-6-strategy-iteration/PLAN.md`, relevant `context/`, indexed code.
- **Note:** `ACTIVE.md` (listed as a required input) does **not** exist at the workstream root. Only `PLAN.md` was available under the allowed dispatch read scope.

---

## 1. Material conflicts (blockers to resolve first)

These are the highest-priority findings. The Architect must stop and report, not silently resolve.

### C1 — Manual parameter iteration is currently impossible for the reference Strategy
Every EMA Sweep Engulfing parameter is hard-locked to its default by the **implementation source**, not just by the UI:
- `backend/strategies/ema_sweep_engulfing.py:33-85` — `_schema()` declares every `ParameterSchema` with `min == max == default` (`ema_period` 100/100/100, `atr_period` 14/14/14, `stop_buffer` 0.5, `target_r` 1.7, `expiry_window` 5/5/5).
- `backend/strategies/ema_sweep_engulfing.py:152-160` — `EmaSweepEngulfingStrategy._validate_parameters` raises `ParameterError("EMA Sweep Engulfing Phase 1 parameters are fixed")` unless **all** values equal the defaults.
- `backend/experiments/configuration.py:112-154` (`_validate_parameters`) enforces the persisted schema `min`/`max` **and** then calls the registered `implementation._validate_parameters(params)` (`:149`), which rejects any non-default value → `ConfigurationError("PARAMETERS_INVALID")` (`:153`).

**Consequence:** Phase 6's core goal — "manual hypothesis testing via parameter variation" (roadmap Phase 6, `context/roadmap/roadmap.md:33-35`) and PLAN acceptance criterion #2 ("typed supported-parameter iteration") — **cannot be satisfied** without changing the Strategy source (widening `min`/`max` and relaxing `_validate_parameters`).

**Conflict with immutability/provenance:** `StrategyVersionModel.source_fingerprint` is a SHA-256 of the source files
(`backend/strategies/fingerprint.py`; `source_files` in `ema_sweep_engulfing.py:96-99`) and
`implementation_key="ema_sweep_engulfing.v1"` (`:100`). Widening the schema/validation **changes the source** →
new fingerprint → **new StrategyVersion** (`backend/persistence/strategy_repository.py:98-133` dedupes on fingerprint and
auto-increments `version_number`; registry matching in `backend/strategies/registry.py:96-109`).

This is the central tension: the strategy-contract says parameters are "runtime configuration; changing them does not create a new
StrategyVersion" (`context/architecture/strategy-contract.md:41`), but today the reference Strategy's parameters are **baked into
the executable source** such that permitting variation is itself a source/behavior change. The Architect must decide how to reconcile
"supported-parameter iteration without a new StrategyVersion" with the fingerprint-derived immutability, and must not silently reopen
Phase 1's fixed-parameter decision.

### C2 — `expiry_window` is structurally a methodology constant, not an iterable parameter
- `backend/domain/strategy.py:98-99` — `StrategyParameters.__post_init__` hard-requires `expiry_window == 5`.
- `backend/domain/strategy.py:357` — `StrategyState.__post_init__` requires `0 <= window_bars <= 5`.
- `backend/strategies/ema_sweep_engulfing.py:232` — expiry is hard-coded as `if window >= 5` (and schema locks it at 5).

**Consequence:** `expiry_window` cannot be varied at all without a methodology/state-machine/source change, which per
`strategy-contract.md:43-45` is precisely the trigger for a **new StrategyVersion**. Including it in the "iterable parameters without
a new version" set (PLAN #2) is contradictory.
**Recommendation (labeled):** treat `expiry_window` as a fixed methodology constant of the StrategyVersion and exclude it from the
manually-iterable parameter set (or remove it from the iterable schema). Do not silently change its semantics.

---

## 2. Existing facts and extension points (Phase 5 baseline)

### 2.1 Experiment configuration and immutability
- Config inputs are validated and snapshotted atomically as an immutable `ExperimentModel`:
  `backend/experiments/configuration.py:298-365` (`ExperimentConfigurationService.create`) persists `strategy_version_id`,
  `dataset_snapshot_id`, `venue_instrument_id`, `trading_start/end`, `starting_capital`, `risk_per_trade`,
  `parameter_snapshot`, `risk_config`, `simulation_config`, `model_version`.
- Persisted columns: `backend/persistence/models.py:227-258` (`ExperimentModel`). **Extension point:** each Experiment already stores
  the full typed `parameter_snapshot` (JSONB, `:250`), `risk_config` (`:251`), `simulation_config` (`:252`), and `model_version` (`:253`).
- Schema version constants: `backend/experiments/configuration.py:33-35` (`RISK_SCHEMA_VERSION`, `SIMULATION_SCHEMA_VERSION`,
  `MODEL_VERSION = "PHASE4_HISTORICAL_EXECUTION_V1"`). `simulation_config()` (`:38-69`) and `risk_config()` (`:72-76`) are the canonical
  assumption builders — reusable as the comparison "simulation-assumption" inputs.

### 2.2 Metric authority and result schema
- Authoritative metrics are computed **from immutable Experiment facts**, never current defaults:
  `backend/experiments/metrics.py:83-155` (`calculate_metrics`) driven by `experiment.starting_capital`
  (`backend/experiments/results.py:102-111`), reading persisted Trades + equity.
- Versioned metric vocabulary: `backend/experiments/metric_contract.py` (`PHASE5_RESULT_SCHEMA_VERSION`,
  `PHASE5_METRIC_SCHEMA_VERSION`, `METRIC_STATE_KEYS`, `MetricState` `VALUE/INFINITE/UNAVAILABLE/LEGACY_UNCOMPUTED`).
- Result table with output fingerprint and finite/infinite state constraints: `backend/persistence/models.py:471-513`
  (`ExperimentResultModel`), migration `0007_phase_5_metric_contract.py`.
- **Extension point:** the canonical `ExperimentMetrics` dataclass (`metrics.py:27-36`) — Net Return, Max Drawdown (amount/percent),
  Sharpe, Profit Factor, Win Rate, Expectancy, Trade Count — is exactly the "existing authoritative core metric" set the comparison
  must reuse (`context/features/experiment-comparison.md:25`). No comparison-specific formulas exist or are needed.

### 2.3 StrategyVersion persistence / provenance / parameter schema
- Domain: `backend/domain/strategy.py:506-573` (`StrategyVersion`); parameter schema descriptors `:118-162` (`ParameterSchema`).
- Persistence: `backend/persistence/models.py:50-96` (`StrategyVersionModel`) — stores `version_number`, `source_fingerprint`,
  `implementation_key`, `parameter_schema` (JSONB), `context_timeframes`, `capabilities`, `source_manifest`, `exact_source_snapshot`,
  `primary_timeframe`, `warm_up_bars`, `state_schema_version`, optional `git_sha`, `created_at`.
- Repository: `backend/persistence/strategy_repository.py:59-137` (`create_version`, dedupe by fingerprint, auto-increment version),
  `:140-177` (`version_to_domain`). No update/delete methods (`:18-19`) — immutability enforced by omission.
- Registry/provenance matching: `backend/strategies/registry.py:96-109` (`implementation_for_version`); source archive/fingerprint:
  `backend/strategies/fingerprint.py`.
- **Extension points for StrategyVersion history/provenance UI:** all identity/provenance fields listed above are already persisted
  and exposed via `GET /api/v1/experiments/configuration-options`
  (`backend/api/experiments.py:183-201`, includes `id`, `strategyKey`, `name`, `version`, `implementationKey`, `sourceFingerprint`,
  `parameterSchema`, `warmUpBars`). **Gap:** there is no dedicated `strategy_versions`/strategies read endpoint and no Strategy
  list/detail UI route (see 2.5).

### 2.4 API contracts (Phase 5)
`backend/api/experiments.py` (router prefix `/api/v1/experiments`):
- `GET /configuration-options` (`:183-201`)
- `POST /coverage-validations` (`:202-215`, `PeriodRequest`)
- `POST /` create (`:217-237`, `ExperimentCreateRequest`)
- `GET /` list w/ cursor (`:239-265`)
- `GET /{experiment_id}` detail (`:273-280`)
- `POST /{experiment_id}/run` (`:282-290`)
- `GET /{experiment_id}/equity` (`:300-307`)
- `GET /{experiment_id}/trades` + `/{sequence_number}` (`:309-323`)

Request schemas: `backend/api/schemas.py:31-47` (`PeriodRequest`, `ExperimentCreateRequest`). Note
`parameters: dict[str, Any]` (`:41`) — already free-form at the transport boundary; validation is server-side.
**Extension point:** a comparison endpoint can be added as a new read/composition route; no request-schema change is required for
parameter variation itself.

### 2.5 UI routes/components
- Routes: `frontend/app/experiments/page.tsx` (list), `new/page.tsx` (create form), `[experimentId]/page.tsx` (status + results),
  `[experimentId]/trades/`.
- Components: `frontend/components/experiment-workflow.tsx` (`ExperimentsList`, `ExperimentForm`, `ExperimentStatusPage`,
  `EquityResults`, `StateDisclosure`, `TradeDetailPage`, chart components).
- **Gap — no manual parameter inputs:** `ExperimentForm` builds `parameters` purely from `parameterSchema` descriptors' **defaults**
  (`experiment-workflow.tsx:693-701`), with no per-parameter edit controls. Even once the backend permits variation, the UI has no
  input affordances for `ema_period`/`atr_period`/`stop_buffer`/`target_r`.
- **Gap — no StrategyVersion history / comparison route:** nav "Strategies" is `disabled` (`frontend/components/app-shell.tsx:14`);
  only `/experiments` is active (`:15`). Design describes a Strategies/Strategy Detail workspace
  (`context/design/design.md:41`) and one comparison workspace (`experiment-comparison.md:45`), neither built.
- API client: `frontend/lib/api-client.ts:49-88` (`atlasApi`) — only Experiment methods; no comparison/strategy-history methods.

### 2.6 Existing comparison references
Cross-Experiment comparison does **not** exist. All backend `compar*` matches are runner **diagnostics**
(`Phase4RunnerComparisonDiagnostic`, `comparison_diagnostic_sink`, `backend/experiments/runner.py:248-630`) used for
determinism/reproducibility checks (see `backend/tests/integration/test_phase5_valid_run.py:191-236`), not cross-Experiment
performance comparison. Frontend has zero comparison code.

---

## 3. Affected contracts / dependencies / risks

### 3.1 Affected contracts (if Phase 6 proceeds)
- **Strategy parameter schema** (`ema_sweep_engulfing.py` + persisted `strategy_versions.parameter_schema`) — C1 requires widening;
  this changes source → new fingerprint → new StrategyVersion.
- **Strategy source immutability/provenance** (`strategy-repository.py`, `registry.py`, `fingerprint.py`) — any change to widen params
  must preserve existing completed Experiments' provenance (immutable `ExperimentModel`/`ExperimentResultModel` are untouched).
- **Generated OpenAPI contract** — Phase 5 exit required byte-identical `frontend/lib/api.generated.ts`
  (`CURRENT.md:8`). Any new comparison/strategy-history endpoint requires regenerating `api.generated.ts` and `api-client.ts`.
- **API router/schemas** (`backend/api/experiments.py`, `schemas.py`) — comparison is read-only composition; consistent with
  `experiment-comparison.md:31-33` (only COMPLETED Experiments participate; FAILED excluded; Zero-Trade valid with unavailable metrics).
- **UI nav/routes** (`app-shell.tsx`, `app/`) — adding Strategies and Comparison workspaces.
- **No persistence change strictly required** for comparison: all comparability inputs (strategy_version_id, dataset_snapshot_id,
  period, parameters, risk_config, simulation_config, model_version, starting_capital) are already immutable columns on
  `ExperimentModel` (`models.py:242-253`). Roadmap explicitly avoids persisted comparison state absent demonstrated need
  (`roadmap.md:35`, `experiment-comparison.md:47-49`). **Recommendation (labeled):** comparison should be a read/composition workflow,
  not new tables.

### 3.2 Dependencies
- Comparison/metric reuse: `backend/experiments/results.py` (`ExperimentResultReadService`) and `metrics.py` are the canonical
  read/metric authority — comparison must consume these, not recompute from mutable defaults (`experiment-results.md:55-57`).
- Label/identity: Experiment labels are currently derived (`"Experiment {id[:8]}"`, `api/experiments.py:106`; UI `"Experiment {index+1}"`,
  `experiment-workflow.tsx:564`). Comparison requires meaningful labels ("Experiment A: EMA Sweep Engulfing v1, ATR Buffer 0.5",
  `experiment-comparison.md:21`); `ExperimentModel` has **no name/label column**, so meaningful labels depend either on existing
  identity/provenance fields (no migration) or a new label column (persistence change — needs justification).
- Equity overlay: comparison may overlay equity curves via TradingView Lightweight Charts only where periods are meaningfully
  comparable (`experiment-comparison.md:29`); `results.equity` already supports envelope sampling (`results.py:113-150`).

### 3.3 Risks
- **R1 — Widening parameters bifurcates versions:** existing completed Experiments reference v1 with locked params. Enabling variation
  creates v2 (new fingerprint). Comparison must clearly surface StrategyVersion differences as methodology change, not parameter
  adjustment (`experiment-comparison.md:41`). Risk of silently implying v1 vs v2 are same-methodology comparisons.
- **R2 — Comparability warnings correctness:** strongest comparison is "same StrategyVersion + Instrument + DatasetSnapshot/period +
  Risk + simulation assumptions + one intentional parameter change" (`experiment-comparison.md:17`). All these are diffable today from
  `ExperimentModel`, but the diff logic must be deterministic and explainable, with FAILED excluded and Zero-Trade metrics
  `UNAVAILABLE` (not zero) (`experiment-comparison.md:33`).
- **R3 — UI/API drift:** adding endpoints without regenerating the typed API client (byte-identical guard) breaks the established
  contract-freshness discipline.
- **R4 — Metric misuse:** comparison must not introduce composite/ranking scores (`experiment-comparison.md:37`); must reuse canonical
  metrics only.
- **R5 — `expiry_window`/state coupling:** any attempt to vary `expiry_window` without a methodology change will fail at
  `StrategyState`/`StrategyParameters` validation (C2) — a runtime surface that must not be silently reopened.

### 3.4 Context gaps (to note for the blueprint)
- No StrategyVersion history/detail read path or UI (design describes it; nothing built).
- No manual parameter input UI.
- No comparison endpoint/UI.
- No explicit "prefill new Experiment from existing" convenience (mentioned as future in `experiment-comparison.md:41`); if Phase 6
  scope includes it, it is a new affordance, not existing code.

---

## 4. Plain-language summary

- Phase 5 left a clean, immutable foundation: per-Experiment typed `parameter_snapshot`/`risk_config`/`simulation_config`/period/
  capital, versioned canonical metrics, and a fully-provenanced immutable StrategyVersion. All comparison inputs already exist as
  persisted columns, so comparison can be a **read/composition** workflow with no new tables.
- **The dominant blocker is C1:** the reference Strategy's parameters are locked to defaults *in the executable source*, so the Phase 6
  "manual parameter variation" goal cannot work until the schema/validation are widened — which is a source change that produces a new
  StrategyVersion. The blueprint must reconcile PLAN criterion #2 with StrategyVersion fingerprint immutability and must not silently
  reopen Phase 1's fixed-parameter decision.
- **Secondary conflict is C2:** `expiry_window` is a methodology/state constant, not an iterable parameter.
- No comparison or StrategyVersion-history UI/API exists; the API client must be regenerated for any new endpoint (byte-identical
  contract discipline).
- No decisions were made here; recommendations are labeled. The above conflicts are reported for the Architect to resolve explicitly.

_Artifact complete._
