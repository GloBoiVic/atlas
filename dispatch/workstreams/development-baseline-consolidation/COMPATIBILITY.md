# Compatibility Inventory

- **Workstream:** `development-baseline-consolidation`
- **Task:** `T003`
- **Captured:** `2026-09-10`
- **Repository baseline:** `611fe10b9b596f9e48339f305b99023d402c4514`

## Decision Rule

This inventory classifies compatibility by the responsibility it has in the current
checkout, not by its age or by whether Atlas is deployed.

- **CURRENT** means current Atlas behavior, a current persisted contract, or a current
  API/import surface depends on the seam.
- **EVIDENCE** means the seam is needed to inspect deliberately retained historical
  DatasetSnapshot, Experiment, result, or execution evidence without rewriting it.
- **PROTOTYPE** means the seam serves only disposable development-era state and has no
  current production, evidence, API, or persistence responsibility.
- **DEFERRED** means the seam is likely removable, but removal belongs to a later
  Strategy SDK, market-capability, persistence, or explicit compatibility decision.

Historical identifiers are not automatically current semantics. A migration revision,
persisted schema/version string, old benchmark name, or database constraint name may
describe when or how a contract was introduced while the behavior it protects remains
current or deliberately readable. This record therefore does not rename identifiers to
make their labels look newer.

No seam below is removed merely because Atlas is undeployed. No seam is retained merely
because an old test mentions it. The evidence includes current callers, persistence,
evidence, API/generated surfaces, and the blocker to retirement.

## Inventory

### Strategy State Schema 1

- **Classification:** `PROTOTYPE` for the standalone `StrategyState.schema_version == 1`
  contract. The `StrategyState` type itself remains because the current EMA adaptor uses
  its schema-2 internal representation.
- **Current caller:** `backend/domain/strategy.py:862-1075` validates and serializes both
  versions. `backend/strategies/production.py:_legacy_state` constructs the internal
  `StrategyState` for the registered `ema_sweep_confirmation_break.v2` adaptor, but that
  path receives the Strategy definition's schema 2. The current public entry point in
  `backend/strategies/contract.py:evaluate_strategy` requires a
  `StrategyStateEnvelope`, and `backend/paper/strategy_evaluation.py` rejects a bare
  `StrategyState` at its boundary.
- **Persisted dependency:** Current runtime activation and cycle persistence stores and
  restores `StrategyStateEnvelope` JSON through `backend/runtime/activation.py` and
  `backend/persistence/runtime_repository.py`. It does not deserialize a bare schema-1
  `StrategyState` from the current persisted runtime state. A
  `StrategyVersionModel.state_schema_version == 1` value is the envelope/Strategy
  version contract and must not be conflated with `StrategyState.schema_version == 1`.
- **Evidence dependency:** No current retained Experiment or PAPER evidence was found
  that stores a bare schema-1 `StrategyState`. The schema-1 object is exercised by
  `backend/tests/domain/test_primitives.py` and the intentional legacy-isolation tests,
  not by a current persisted evidence reader.
- **API/test/generated responsibility:** The PAPER activation API exposes
  `strategy_state` as an opaque JSON object (`backend/api/schemas.py:115-116`); it does
  not publish a schema-1 typed contract. Tests verify schema-1 rejection at the current
  public Strategy boundary.
- **Natural retirement point:** An explicit Strategy SDK or EMA vNext transition that
  removes the underlying legacy internal state adapter and its test fixtures, after a
  repository and retained-data scan confirms that no bare schema-1 state is persisted.
  That transition would be a methodology/compatibility decision, so T003 retains it.

### `window_bars` and `AWAITING_CONFIRMATION`

- **Classification:** `PROTOTYPE` for the old schema-1 confirmation-window semantics.
  `Phase.AWAITING_CONFIRMATION` is not emitted or consumed by the registered V2
  Strategy. `window_bars` is not current methodology.
- **Current caller:** The old validation and JSON codec remain in
  `backend/domain/strategy.py`. The legacy-isolation tests construct the old state and
  assert that the V2 public boundary rejects it. The current EMA adaptor's payload codec
  still includes a zero-valued `window_bars` key in its ordered compatibility field set
  (`backend/strategies/production.py:40-85` and `190-216`); it round-trips the key but
  does not use it to decide eligibility.
- **Persisted dependency:** Bare schema-1 window state has no current persistence path.
  The zero-valued key is part of the current EMA envelope payload, and envelope state is
  persisted in runtime activation/cycle evidence. Removing that key would therefore be
  a state-codec/version decision, not a comment cleanup.
- **Evidence dependency:** Old window state is not reconstructed for current Experiment
  or PAPER results. Current EMA evidence uses the armed state, pending-entry handoff,
  and `watch_bars`; `AWAITING_CONFIRMATION` and nonzero `window_bars` are not current
  execution semantics.
- **API/test/generated responsibility:** The runtime API returns state JSON opaquely and
  the generated client has no typed `window_bars` or `AWAITING_CONFIRMATION` member.
  `backend/tests/domain/test_primitives.py` and
  `backend/tests/strategies/test_legacy_strategy_isolation.py` are intentional
  compatibility/rejection coverage, not evidence that the old methodology is current.
- **Natural retirement point:** The first replacement EMA/Strategy state codec with a
  deliberate immutable state-schema transition and a decision about any stored envelope
  payloads. Until then, retain the zero-valued field and old rejection coverage; do not
  reinterpret it or silently delete it.

### `warm_up_bars`

- **Classification:** `DEFERRED` for the deprecated alias/fallback. The current
  semantic owner is `required_historical_context_bars` and
  `RequiredHistoricalContext`, not the old global-sounding name.
- **Current caller:** `StrategyDefinition.warm_up_bars` and
  `StrategyVersion.warm_up_bars` are read-only properties. The current contract still
  calls the definition alias from `backend/strategies/contract.py:validate_context`.
  `backend/domain/strategy_requirements.py:76-100` accepts `warm_up_bars` only as a
  boundary fallback for pre-canonical objects. `StrategyVersionModel.warm_up_bars` is a
  SQLAlchemy synonym for the canonical column.
- **Persisted dependency:** Migration
  `backend/persistence/migrations/versions/0012_required_historical_context.py` renamed
  the database column to `required_historical_context_bars`. The current model maps the
  old attribute as a read alias; it does not recreate an old database column. Removing
  the alias or fallback now would change old-row/test-double compatibility and could
  require a persistence baseline decision.
- **Evidence dependency:** Historical-load planning, SimulationClock construction, and
  result reads consume the canonical required-context value. The fallback exists for
  pre-canonical objects, not to change the number of bars or reinterpret historical
  Experiment methodology.
- **API/test/generated responsibility:** Current API and generated contracts expose
  `requiredHistoricalContextBars`, not `warm_up_bars`. Existing historical-load tests
  deliberately use lightweight pre-canonical objects with `warm_up_bars`, while current
  production Strategy definitions expose the canonical field.
- **Natural retirement point:** A later persistence/data-baseline workstream that proves
  all supported rows and callers are canonical and explicitly decides whether development
  data is migrated, reset, or retired. No migration or database reset belongs in T003.

### Dataset Snapshot V1

- **Classification:** `EVIDENCE`. V1 is not the current acquisition target, but it is a
  deliberately readable immutable snapshot format.
- **Current caller:** `backend/experiments/results.py:_legacy_v1_m15` reads V1 snapshot
  membership and aggregates immutable M1 members for legacy chart/price views;
  `ExperimentResultReadService.price_analysis` and `_chart` select that reader when the
  persisted snapshot schema is V1. Current ingestion creates V2 snapshots only
  (`MarketDataService.create_snapshot_v2`).
- **Persisted dependency:** `DatasetSnapshotModel.snapshot_schema` and its conditional
  resolution/component/fingerprint/integrity checks retain V1 rows. The V1 constants and
  constraints are established by the snapshot migrations, including
  `0009_historical_snapshot_v2`; those identifiers and old rows are not rewritten.
- **Evidence dependency:** Existing V1 dataset membership and Experiment lineage are the
  direct reason the reader remains. The V1 path preserves `DERIVED_M15_FROM_V1_M1` and
  fixed `ema_100` chart behavior rather than substituting V2 calculations.
- **API/test/generated responsibility:** Configuration options currently filter to V2
  snapshots for new work, while Experiment result provenance still reports the stored
  `snapshotSchema`. The API and generated client treat the schema as a string, and V1
  behavior is covered by result, migration, and integration tests.
- **Natural retirement point:** A later evidence/persistence decision that archives or
  deletes all intentionally retained V1 lineage and removes the V1 read surface with an
  explicit contract change. Until then, do not rename `ATLAS_HISTORICAL_SNAPSHOT_V1`,
  alter its constraints, migrate rows, or reset the database.

### Legacy Result Metric States

- **Classification:** `EVIDENCE` for `LEGACY_UNCOMPUTED`, `LEGACY_RESULT`, and the
  legacy metric-state normalization path.
- **Current caller:** `backend/persistence/experiment_repository.py:create_result` fills
  missing metric state and schema values with the legacy vocabulary. The read service's
  `_persisted_metrics` projects stored values and states without reopening or recalculating
  mutable facts. `backend/tests/experiments/test_results.py` verifies that a legacy result
  remains untouched and is not recalculated.
- **Persisted dependency:** `ExperimentResultModel.metric_states`,
  `metric_schema_version`, defaults, and consistency checks retain these values. The
  metric-state migrations `0007_phase_5_metric_contract` and
  `0014_result_metric_state_details` describe the durable shape. These are immutable
  result facts, not cleanup markers.
- **Evidence dependency:** Historical result rows may have no trustworthy recomputed
  metric value. `LEGACY_UNCOMPUTED` must remain distinguishable from `UNAVAILABLE` or a
  newly calculated `VALUE`; changing it would reinterpret evidence.
- **API/test/generated responsibility:** The API includes persisted result and metric
  schema versions in Experiment detail/provenance. The current generated client exposes these
  additional values through opaque `unknown` payload surfaces rather than typed string
  members, and the frontend renders the schema/version and metric states.
- **Natural retirement point:** A later result-contract workstream that inventories all
  retained rows and explicitly migrates, archives, or replaces their metric evidence.
  T003 does not calculate, rewrite, or delete any result state.

### Historical and Current Result Schema Identifiers

- **Classification:** `CURRENT` for the identifiers used by the current historical
  Experiment writer, with `EVIDENCE` responsibility for older values.
- **Current caller:** `backend/experiments/configuration.py` and
  `backend/experiments/runner.py` write the current `PHASE5_*` model/config/result
  identifiers. `backend/api/experiments.py` reads and returns the stored model and
  result schema values. `backend/execution/fill_application.py` recognizes both the
  older `PHASE4_HISTORICAL_EXECUTION_V1` and current
  `PHASE5_HISTORICAL_EXECUTION_V2` to preserve historical exit-reason semantics.
- **Persisted dependency:** `experiments.model_version`,
  `experiment_results.result_schema_version`, metric checks, migration trigger logic,
  and result provenance depend on exact strings. The `PHASE4_*` and `PHASE5_*` labels are
  identifiers, not instructions to rename current domain concepts.
- **Evidence dependency:** Older Experiment/result rows and frontend/API fixtures use
  earlier identifiers to exercise the read contract. The identifier is part of lineage;
  replacing it with a newer label would make the evidence appear to have been produced by
  a different contract.
- **API/test/generated responsibility:** Experiment detail and comparison responses can
  contain `modelVersion`, `resultSchemaVersion`, and metric contract values. The generated
  client types `modelVersion` explicitly, but exposes the additional Experiment detail
  values through its `unknown` index signature and `metricContract` through an unknown-key
  object, not as typed string members. Backend and frontend tests assert representative old
  identifiers and their display.
- **Natural retirement point:** A new immutable result/model contract with an explicit
  reader for all prior identifiers and a deliberate persistence/evidence migration
  decision. Do not rename current or historical persisted version strings in T003.

### `indicators.py` and `indicators_v2.py`

#### Fixed-period `indicators.py`

- **Classification:** `EVIDENCE`.
- **Current caller:** `backend/experiments/results.py:_chart` imports `ema_100` and uses
  it on the V1-compatible chart path. `backend/tests/strategies/test_indicators.py`
  covers the fixed EMA-100/ATR-14 arithmetic, while result tests protect the V1 chart
  behavior.
- **Persisted dependency:** The module name is not a database column, but the V1 result
  reader's calculation is part of the interpretation of retained V1 chart evidence.
  Removing it or switching the function would alter displayed historical analysis.
- **Evidence dependency:** V1 snapshot membership plus the legacy chart path is the
  concrete non-test responsibility. The old module is not kept only because its unit test
  exists.
- **API/test/generated responsibility:** The API returns chart values without exposing a
  Python module name; frontend tests only observe the result surface. The module remains
  behind the read boundary and is not a generated contract.
- **Natural retirement point:** Retirement of the V1 snapshot/result chart read path, or
  an approved EMA vNext methodology/evidence transition that preserves old chart output
  separately. No indicator rewrite is safe in T003.

#### Period-driven `indicators_v2.py`

- **Classification:** `CURRENT`.
- **Current caller:** The registered EMA Strategy imports `ema` and `atr`; current V2
  price analysis also calculates the persisted `ema_period` with this module. Its path is
  used by Experiment and PAPER Strategy evaluation through the production registry.
- **Persisted dependency:** The EMA Strategy definition's source manifest includes
  `backend/strategies/indicators_v2.py`; StrategyVersion provenance and runtime/PAPER
  receipts therefore bind the implementation and its source fingerprint.
- **Evidence dependency:** Current V2 Experiment result analysis and Strategy evidence
  depend on period-driven, completed-bar calculations. It must not be collapsed into the
  fixed-period legacy module.
- **API/test/generated responsibility:** No generated API imports this module. Backend
  Strategy and price-analysis tests explicitly compare results to `indicators_v2.ema`.
- **Natural retirement point:** A deliberately versioned EMA/Strategy SDK replacement
  with new immutable provenance and a read path for existing versions. Keep the module
  and current import split now.

### `EmaSweepConfirmationBreakCompatibilityAdaptor`

- **Classification:** `CURRENT`.
- **Current caller:** `create_production_strategy_registry` registers the adaptor under
  `ema_sweep_confirmation_break.v2`. The API application, runtime process, Experiment
  runner, and PAPER evaluation all use that registry and resolve persisted StrategyVersion
  provenance through it. The adaptor normalizes the internal legacy state machine into
  `StrategyStateEnvelope` and `PendingEntryHandoff`.
- **Persisted dependency:** StrategyVersion stores `implementation_key` and source
  fingerprint; runtime activations/cycles and PAPER/Experiment receipts persist the
  resulting state/evaluation evidence. The adaptor's codec key and payload fields are part
  of that current state handoff.
- **Evidence dependency:** Current historical Experiments and guarded PAPER evaluation
  require exact Strategy provenance and the current W1-W5/W6 pending-entry behavior.
  Removing the adaptor or changing its state mapping would be a methodology and restart
  semantics change, not dead-code cleanup.
- **API/test/generated responsibility:** Strategy listing/detail responses expose the
  implementation key and source fingerprint. Registry, isolation, Strategy, Experiment,
  PAPER, and integration tests assert the adaptor registration, state round-trip, and
  normalized pending handoff. No generated file names the Python adaptor directly.
- **Natural retirement point:** Strategy SDK or EMA vNext work that registers a replacement
  implementation under a new immutable implementation/provenance contract and defines
  how existing EMA versions/evidence remain readable. T003 leaves this current seam
  unchanged.

### Historical-load Compatibility Fields

- **Classification:** `CURRENT` for the compatibility-shaped progress fields and their
  current HTTP projection.
- **Current caller:** `HistoricalDataLoadRepository.record_progress` maintains the legacy
  columns while also writing the bounded progress payload. `backend/api/historical_data.py`
  returns `fetchedRanges`, `committedRanges`, `inserted`, `reactivated`, `unchanged`, and
  `incompleteMinuteCount`; `frontend/components/experiments/experiment-setup.tsx` reads
  the range counts and counters during the current load workflow.
- **Persisted dependency:** `HistoricalDataLoadRequestModel` still has the non-null
  columns and database checks for those fields. Migrations `0008_historical_load`,
  `0016_unbounded_historical_load_progress`, and `0018_acquisition_windows` establish
  the durable request/progress shape. The repository intentionally clears request-sized
  range history and keeps bounded progress because acquisition windows are the resume
  authority; that is current behavior, not proof that the fields are removable.
- **Evidence dependency:** Load request status and final coverage are operational audit
  evidence. Removing or changing the fields would affect inspection of active, failed,
  and completed load requests, even though they are not Experiment financial facts.
- **API/test/generated responsibility:** The HTTP response model exposes a generic
  `progress` object and the generated client preserves that shape as an unknown-key
  object. Backend load/repository/migration tests assert the columns, checks, and bounded
  progress; the frontend consumes the response.
- **Natural retirement point:** A later historical-load API/persistence contract that
  replaces the response fields, updates clients, and explicitly handles existing request
  rows and resume semantics. No schema change or field removal belongs in T003.

### Runtime Service Aliases

- **Classification:** `DEFERRED`.
- **Current caller:** `backend/api/app.py` uses canonical `PaperRuntimeService`; the
  runtime process and tests use canonical `PaperRuntimeOrchestrator`. The aliases
  `PaperRuntimeActivationService`, `PaperRuntimeControlService`, and
  `PaperRuntimeReconciliationService` point to `PaperRuntimeService`; `PaperRuntime`,
  `PaperRuntimeRunner`, and `PaperRuntimeLoop` point to `PaperRuntimeOrchestrator`.
  Repository search found no current internal caller of those alias names beyond their
  definitions, lazy package exports, and `__all__` declarations.
- **Persisted dependency:** None. The aliases do not appear in runtime JSON, database
  rows, broker requests, or evidence fingerprints; the underlying service/orchestrator
  responsibilities do.
- **Evidence dependency:** None identified. Existing runtime tests exercise the canonical
  classes and guarded behavior rather than an alias-specific contract.
- **API/test/generated responsibility:** These are Python import-surface names exposed by
  `backend/runtime/__init__.py` through lazy exports. They are not HTTP endpoints and do
  not appear in `frontend/lib/api.generated.ts`.
- **Natural retirement point:** An explicit internal Python API freeze or later runtime
  cleanup that checks package imports and any supported external callers. Because removing
  public import names is a compatibility decision, T003 does not delete them; T004 may
  only revisit them with the required import/export evidence.

## Phase Terminology

### Historical Identifiers Retained

The following occurrences were inspected and intentionally left unchanged because they
are historical or persisted identifiers rather than current domain semantics:

- Alembic revision IDs and migration filenames/descriptions such as
  `0001_phase_0_baseline`, `0003_phase_2_market_data`,
  `0006_phase_4_persistence`, and `0007_phase_5_metric_contract`.
- Migration-created functions, triggers, and database constraint names containing
  `phase_2`, `phase_3`, `phase_4`, or `phase5`.
- Persisted model/result/config identifiers including
  `PHASE4_HISTORICAL_EXECUTION_V1`, `PHASE5_HISTORICAL_EXECUTION_V2`,
  `PHASE5_RISK_CONFIG_V1`, `PHASE5_SIMULATION_CONFIG_V1`,
  `PHASE5_EXPERIMENT_RESULT_V2`, and `PHASE5_METRICS_V1`.
- The existing `freeze03_benchmark.py` benchmark name and its regression/test references.
- Negative tests that assert superseded private names such as `_run_phase4` are absent;
  those strings are historical test evidence, not current application concepts.
- Compatibility enum values such as `UNSUPPORTED_PHASE3_STOP_GAP` and
  `UNSUPPORTED_PHASE3_INTRABAR_TRIGGER`; renaming public values would provide no
  mechanical benefit and could break old callers.

No migration was created to rename a historical revision, persisted schema/version,
benchmark, trigger, function, or constraint name.

### Mechanical Current-source Cleanup Applied

Only source-safe terminology changes were made:

- Reworded current Risk, market-data, trading, database-session, and simulated-execution
  comments/docstrings that described current behavior as `Phase 1`, `Phase 3`, or `Phase 4`.
- Renamed the local `phase4` boolean in `backend/execution/fill_application.py` to
  `uses_historical_end_close_reason`; the persisted model-version values it checks are
  unchanged.
- Renamed the current test identifier
  `test_configuration_derives_only_supported_phase4_assumptions` to
  `test_configuration_uses_supported_historical_execution_assumptions`; no test
  behavior or persisted fixture value changed.
- Left observable validation/error text containing historical Phase labels unchanged in
  `backend/domain/strategy.py`, `backend/strategies/contract.py`,
  `backend/execution/contract.py`, and `backend/execution/fill_application.py`; changing
  those messages could alter an API/test-facing contract without functional benefit.

No Strategy methodology, Risk decision, execution accounting, reconciliation, protection,
activation, broker-authority, API shape, schema, migration, generated file, persisted
data, or evidence was changed.

## T003 Boundary

The inventory supports the following decisions for this workstream:

- Retain all `CURRENT` and `EVIDENCE` seams exactly as classified.
- Retain `PROTOTYPE` and `DEFERRED` seams when retirement would require a semantic,
  methodology, import-surface, persistence, or evidence decision.
- Do not migrate/reset data, rewrite historical evidence, rename persisted identifiers,
  or change the Strategy/Risk/execution/reconciliation/protection/activation boundary.
- Any later retirement must start from the natural retirement point recorded beside the
  seam, with focused import, API, persistence, and evidence checks.
