# Implementation Blueprint — Atlas Phase 6: Strategy Iteration

## Authority and status

- This document is the authoritative implementation blueprint for Phase 6.
- **Conflict outcome:** no unresolved product decision blocks implementation. The two tensions are reconciled by preserving the fixed Phase 1 implementation as immutable v1 and introducing a separately fingerprinted, immutable parameter-enabled v2. `expiry_window` remains fixed at five and is not iterable.
- Implementation still requires explicit developer approval of this blueprint and a separate worktree readiness receipt. This document authorizes neither Git mutation nor implementation.
- Assigned cwd: `/Users/vike/Desktop/atlas`. Isolation scope: the approved Phase 6 feature branch/worktree only.

## Outcome

Build the smallest manual Strategy iteration workflow that lets one trader:

1. inspect Atlas-owned StrategyVersion history and provenance;
2. create immutable Experiments with manually entered, schema-validated values for supported v2 parameters;
3. select two to four COMPLETED Experiments and compare immutable configuration facts and existing authoritative core metrics; and
4. see deterministic, explainable comparability warnings before interpreting performance.

Phase 5 Experiment creation, execution, result immutability, metrics, Risk, accounting, simulation, no-lookahead, and execution semantics remain authoritative and unchanged.

## Scope

### Included

- An immutable EMA Sweep Engulfing v2 implementation under the existing Strategy identity.
- Manual variation of `ema_period`, `atr_period`, `stop_buffer`, and `target_r` within a persisted typed schema.
- Fixed, visible `expiry_window = 5`, excluded from iteration.
- Exact local execution matching for both v1 and v2 StrategyVersions.
- Idempotent persistence of registered local StrategyVersions through the existing append-only model.
- Strategy list/detail reads with version history, provenance, use counts, and local execution availability.
- A stateless Experiment comparison read for two to four COMPLETED Experiments.
- Experiment-list selection and a dedicated comparison workspace.
- Generated OpenAPI/client refresh and focused tests.

### Explicitly out of scope

- Automated sweeps, optimization, ranking, winners, scores, recommendations, or “best” labels.
- Persisted comparison entities, tables, saved selections, or comparison IDs.
- Mutation of any existing StrategyVersion or completed Experiment.
- Varying `expiry_window`, timeframe, Instrument, state-machine behavior, setup rules, Risk rules, or simulation assumptions.
- Prefill/clone-from-Experiment convenience, custom Experiment names, equity overlays, normalized equity, metric deltas, and trade-level cross-comparison.
- PAPER/LIVE/Deployment work, dynamic loading of archived source, plugin systems, dependency-graph provenance, or Git as required identity.

## Agreed language

- **Strategy:** the long-lived `ema_sweep_engulfing` methodology identity.
- **StrategyVersion:** an immutable executable methodology snapshot identified in Atlas by Strategy identity plus persisted version number, with exact source fingerprint provenance.
- **v1:** the existing Phase 1 fixed EMA-100/ATR-14/0.5/1.7R/five-bar implementation. Its source and behavior remain unchanged.
- **v2:** a new immutable source implementation that preserves the v1 setup/state-machine methodology while allowing four bounded runtime parameters. Its implementation key is `ema_sweep_engulfing.v2`; its persisted Atlas version number remains database authority.
- **Iterable parameter:** a parameter whose value may differ between Experiments referencing the same StrategyVersion.
- **Methodology constant:** a value fixed by executable/state-machine semantics. `expiry_window = 5` is one.
- **Comparison:** a transient read/composition of existing immutable Experiments, not a domain entity and not persisted.
- **Strong parameter isolation:** all listed comparability dimensions match and exactly one typed parameter value differs. This is a factual classification, not a score or recommendation.

## Architecture boundaries

### Strategy boundary

- v1 and v2 are explicit local implementations of the same Strategy. Neither accesses persistence, Risk, broker state, account values, or environment mode.
- v1 source files must not be edited to enable v2. They remain locally registered so historical v1 Experiments remain reproducible.
- v2 uses separately archived source files and generalized deterministic EMA/Wilder ATR functions receiving an explicit period.
- The five-bar state machine, completed-bar behavior, duplicate frontier, reference/sweep/confirmation rules, stop/target methodology, rationale, and environment independence are unchanged.

### Experiment boundary

- Parameter values remain runtime configuration captured in `Experiment.parameter_snapshot`; varying a supported v2 value does not create a StrategyVersion.
- A schema/range, indicator algorithm, state-machine, or other executable behavior change changes source and must append a new StrategyVersion.
- Comparison consumes completed Experiment snapshots and authoritative result reads only. It never reads current defaults to reinterpret history and never recalculates metrics in the frontend.

### Persistence boundary

- PostgreSQL remains durable truth.
- Existing `strategies`, append-only `strategy_versions`, `experiments`, and result/fact tables are sufficient. No new table or column is authorized.
- Exact source snapshots remain persisted but are not returned by normal API reads.

## Decisions

### 1. Reconcile fixed v1 with parameter iteration by adding immutable v2

Widening the current source is itself an executable behavior/provenance change, so it must not be represented as a value-only change to v1. Preserve v1 byte-for-byte and add v2 as new source with a new fingerprint and implementation key. Once v2 exists, changing any supported value inside its persisted schema creates only a new Experiment.

This preserves both governing rules: executable change creates a StrategyVersion; runtime parameter change within that version does not.

### 2. Keep `expiry_window` fixed

`expiry_window` remains in the parameter snapshot/schema with `min = max = default = 5` so historical configuration is explicit. The Experiment form renders it as read-only with “Fixed by methodology.” v1 and v2 validation both require five. Any future change requires a new state-machine methodology, state compatibility review, and new StrategyVersion.

### 3. Use bounded v2 parameter support

The v2 persisted schema is:

| Key | Type | Default | Minimum | Maximum | Iterable |
| --- | --- | ---: | ---: | ---: | --- |
| `ema_period` | integer | 100 | 20 | 200 | Yes |
| `atr_period` | integer | 14 | 5 | 50 | Yes |
| `stop_buffer` | decimal | `0.5` | `0.1` | `3.0` | Yes |
| `target_r` | decimal | `1.7` | `0.5` | `5.0` | Yes |
| `expiry_window` | integer | 5 | 5 | 5 | No |

v2 declares `warm_up_bars = 200`, the maximum required by its supported EMA range and sufficient for ATR up to 50. Coverage remains conservative and version-owned; parameter-dependent warm-up infrastructure is not introduced. Inputs must contain exactly the schema keys. Integers reject booleans/non-integers; decimals must be finite and within inclusive bounds. Server validation remains authoritative.

### 4. Preserve exact v1 and v2 execution locally

The Strategy registry must support multiple explicit local implementations under one `strategy_key`, keyed for execution by exact `(strategy_key, implementation_key, source_fingerprint)`. Registration rejects duplicate implementation keys within a Strategy. Execution never falls back to “latest,” fingerprint-only, or Strategy-key-only selection.

Archived source is provenance, not executable input: Atlas must not dynamically execute `exact_source_snapshot`. A persisted version without an exact local registration is visible in history as unavailable and is not selectable for a new Experiment.

### 5. Persist the local catalog idempotently

At API startup, before requests are served, an explicit catalog synchronization transaction persists registered implementations in deterministic v1-then-v2 order through `StrategyRepository.create_version`. Existing fingerprint rows deduplicate; missing fingerprints append. Failure to synchronize is an explicit startup failure, not a partially available catalog.

The persisted version number is Atlas authority. In the expected current catalog, v1 remains version 1 and parameter-enabled source becomes version 2; UI/API must display the persisted number rather than infer it from `implementation_key`.

### 6. Make Atlas provenance primary and Git optional

Trader-facing identity is `Strategy name + v{persisted version_number}`. History exposes Atlas creation time, source fingerprint, implementation key, source manifest, parameter schema, timeframe, warm-up, state schema, capabilities, Experiment usage, and local execution availability. `git_sha` is optional secondary provenance and must never be required or substituted for Atlas identity. Exact source contents stay server-side.

### 7. Comparison is a stateless read

Use one bounded read service and one GET endpoint. Request order defines stable A–D slots. The response is generated from immutable Experiment/config/result facts and is never stored. No migration, comparison model, cache, worker, or background job is introduced.

### 8. Compare configuration before metrics

The comparison response and UI order are:

1. human-readable Experiment identities;
2. comparability summary and warnings;
3. changed configuration with unchanged configuration de-emphasized;
4. canonical metrics side by side; and
5. links to each Experiment and its Trades.

No winner, rank, recommendation, aggregate score, inferred causality, or metric delta is produced.

## Detailed behavior

### StrategyVersion migration and provenance behavior

- Existing v1 rows, source snapshots, fingerprints, Experiments, and results are untouched.
- v1 remains selectable and produces only its fixed defaults.
- v2 gets a distinct source fingerprint because its executable source and schema differ.
- All v2 Experiments reference the same v2 StrategyVersion regardless of supported parameter values.
- A later change to v2 bounds/defaults, indicator math, warm-up declaration, or validation is a source change and must become a new immutable StrategyVersion; no row is updated in place.
- Strategy history shows v1 and v2 separately. Comparisons crossing them always say “Methodology differs (StrategyVersion changed),” even when visible parameter values happen to match.

### Experiment creation

- Configuration options return every persisted version plus derived `executionAvailable` and `unavailableReason`; only exact locally available versions are selectable.
- The default selection is the highest persisted, locally available version.
- Selecting a version rebuilds parameter controls from that version's persisted schema and resets them to that schema's defaults. Values do not leak between versions.
- Integer and decimal controls accept manually typed values. Decimal values remain strings at the UI/API boundary to avoid binary floating-point conversion.
- A `min == max` descriptor is visible but read-only. The request still sends its fixed value.
- Coverage validation is rerun when StrategyVersion or period changes because v2 warm-up differs.
- Client checks improve feedback only. Existing server schema validation plus exact registered implementation validation remains final authority.
- Creation still snapshots parameters, Risk, simulation config, DatasetSnapshot, period, capital, and model version atomically into a new PENDING Experiment.

### Human-readable Experiment identity

No label column is added. API composition derives labels from immutable facts, for example: `EMA Sweep Engulfing v2 · 23 Aug 2026 14:30 UTC`; within comparison this is prefixed `Experiment A` through `Experiment D`. UUIDs remain links/transport identifiers, not displayed labels.

### Selection and eligibility

- Experiment list rows expose a selection checkbox only for COMPLETED status.
- Compare is enabled only for two to four distinct selections.
- PENDING, RUNNING, and FAILED rows explain why they cannot participate; they are never silently omitted.
- The comparison endpoint independently enforces all limits and statuses.
- A missing ID returns not found. Duplicates, fewer than two, more than four, or any non-COMPLETED status reject the whole request with structured details. No partial comparison is returned.
- A COMPLETED zero-Trade Experiment is valid. Trade-dependent metrics retain their authoritative `UNAVAILABLE` state, never zero.

## Comparison semantics

### Dimensions

For each requested Experiment, compose and display:

- Strategy and StrategyVersion identity, implementation key, and source fingerprint;
- canonical Instrument;
- DatasetSnapshot identity/fingerprint;
- exact UTC trading start/end;
- union of parameter keys with descriptor type and persisted value;
- starting capital and base currency;
- Risk snapshot, including risk per trade;
- simulation snapshot;
- Experiment model/engine version;
- result/metric contract versions where present; and
- existing canonical metric envelopes.

### Equality rules

- StrategyVersion: persisted ID equality; labels/fingerprints explain the difference.
- Instrument: canonical Instrument identity, not provider symbol text.
- DatasetSnapshot: persisted snapshot identity/fingerprint.
- Period: exact UTC start and end instants.
- Parameters: compare by each version's persisted descriptor type. Integers compare as integers; decimals compare as exact Decimal values, so `0.5` and `0.50` are semantically equal. Missing keys or type changes are explicit differences.
- Starting capital: exact Decimal value plus currency.
- Risk and simulation snapshots: recursively compare immutable canonical structures, independent of object key order; no current defaults are consulted.
- Model/result/metric versions: exact version string equality.
- Metrics: retain Phase 5 metric state/value/unit/reason envelopes. `INFINITE`, `UNAVAILABLE`, and legacy states are not coerced.

### Warning contract

Warnings are deterministic, non-blocking, deduplicated set-level facts returned in this fixed precedence:

1. `STRATEGY_VERSION_DIFFERS` — methodology differs.
2. `INSTRUMENT_DIFFERS` — market identity differs.
3. `DATASET_SNAPSHOT_DIFFERS` — historical data provenance differs.
4. `TRADING_PERIOD_DIFFERS` — start and/or end differs.
5. `RISK_CONFIG_DIFFERS` — Risk assumptions differ.
6. `STARTING_CAPITAL_DIFFERS` — account starting state differs.
7. `SIMULATION_CONFIG_DIFFERS` — execution assumptions differ.
8. `MODEL_VERSION_DIFFERS` — Experiment execution model differs.
9. `METRIC_CONTRACT_DIFFERS` — displayed metric contracts differ.

Each warning contains `code`, neutral severity `CAUTION`, a fixed plain-language explanation, and the affected field paths. Values remain in the differences section rather than being embedded into free-form messages.

Parameter differences are configuration facts, not warnings. The response includes `strongParameterIsolation: true` only when no warning dimension differs and exactly one typed parameter key differs. It also returns `changedParameterKeys`; no quality judgment follows from this flag.

### Core metrics

Reuse only Phase 5 authority:

- Net Return
- Maximum Drawdown amount and percent
- Sharpe Ratio
- Profit Factor
- Win Rate
- Expectancy
- Trade Count

The comparison read service delegates metric production to the canonical completed-Experiment result service/calculator over immutable facts. The frontend only formats returned envelopes. No comparison-specific formula is allowed.

## API contracts

### Strategy reads

#### `GET /api/v1/strategies`

Returns the small Strategy catalog with `strategyKey`, name, description, persisted latest version summary, version count, total Experiment count, and last Experiment time. Ordering is stable by Strategy name/key.

#### `GET /api/v1/strategies/{strategyKey}`

Returns Strategy identity and versions newest-first. Each version includes:

- internal ID for links/requests;
- `displayName` (`EMA Sweep Engulfing v2` style) and persisted version number;
- implementation key and full source fingerprint;
- creation time and optional Git SHA;
- source manifest paths/byte lengths, but not source contents;
- parameter schema, timeframe, warm-up, state schema, and capabilities;
- Experiment count and last-used time; and
- `executionAvailable` with a stable unavailable reason when no exact local implementation exists.

Unknown Strategy key returns 404.

### Configuration options extension

`GET /api/v1/experiments/configuration-options` keeps all Phase 5 fields and adds `displayName`, `createdAt`, `executionAvailable`, and nullable `unavailableReason` to each StrategyVersion option. This is additive. Unavailable versions remain visible for provenance but disabled for creation.

### Comparison read

#### `GET /api/v1/experiments/comparison?experimentId=…&experimentId=…`

- Accepts two to four ordered, distinct UUID query values.
- Returns `experiments` in request order with A–D slots, derived labels, immutable identity/config, and canonical metrics.
- Returns ordered `differences`, `warnings`, `changedParameterKeys`, and `strongParameterIsolation`.
- Does not return or create a comparison ID.
- Error codes: `COMPARISON_SELECTION_INVALID` (count/duplicates), `EXPERIMENT_NOT_FOUND`, `EXPERIMENT_NOT_COMPLETED`, and `COMPARISON_RESULT_UNAVAILABLE` for inconsistent completed-result facts.
- Responses are bounded; no trade/equity series or source contents are included.

All new/changed routes receive explicit response schemas. Regenerate and verify `frontend/lib/api.generated.ts`, then keep the handwritten API client as a thin typed wrapper.

## Persistence

### Schema changes

None. Do not add a comparison table, saved-selection column, Experiment label, ranking data, or StrategyVersion changelog column.

### Writes

The only new durable write is append-only creation of the v2 StrategyVersion during idempotent catalog synchronization using existing constraints and immutable triggers. Existing version rows are never updated or deleted.

### Reads

- Extend repository reads/aggregates for Strategy history and Experiment usage.
- Comparison reads existing Experiment, StrategyVersion/Strategy, VenueInstrument/Instrument, DatasetSnapshot, result, Trade, and equity facts through focused services.
- Four Experiments is the hard bound; simple per-Experiment canonical result composition is acceptable. Do not add caching or bulk infrastructure absent measurement.

## UI architecture

### Navigation and Strategy history

- Enable the existing horizontal `Strategies` navigation item.
- `/strategies`: quiet table/list answering “What StrategyVersions do I have?”
- `/strategies/[strategyKey]`: Strategy overview followed by version history. Show v2 as a methodology version, its four variable parameters, fixed five-bar window, provenance, availability, and Experiment usage. Git SHA is secondary and omitted when absent.

### Experiment form

- Keep the existing form and derive controls entirely from selected persisted schema.
- Make the four v2 fields manually editable and `expiry_window` visible/read-only.
- Show inline type/range errors; server errors remain authoritative and actionable.
- Do not add optimization language, presets, sliders implying recommended values, or automatic Experiment generation.

### Experiment list and comparison route

- Add bounded selection to `/experiments` and one `Compare selected` action.
- Add `/experiments/compare` with ordered repeated `experimentId` query parameters. URL state is transient/shareable navigation state, not persisted comparison state.
- Page hierarchy: title/identities → warnings → configuration differences → core metric table → links to individual results/Trades.
- Changed values receive restrained emphasis; unchanged values are available but de-emphasized.
- Do not use leaderboard styling, green/red winner semantics, sorting by performance, or “better/worse” copy.
- Responsive behavior may horizontally scroll compact tables and stack secondary sections; preserve warning visibility.

## Failure handling and security

- Catalog fingerprint mismatch or sync failure is explicit and prevents serving an execution-selectable version; never substitute another implementation.
- Persisted but locally unavailable versions remain inspectable and are blocked from new Experiment creation with an actionable reason.
- Comparison never silently drops an invalid selection or fabricates missing results.
- Backend errors identify what failed and that no immutable Experiment was changed.
- All query cardinality is bounded at four and UUIDs are strictly validated.
- Source snapshots and filesystem contents are not exposed by these APIs. Git metadata is optional, read-only provenance.
- No credentials, broker state, account connection, or PAPER/LIVE surface is touched.

## Constraints and risks

- **v1 reproducibility:** editing existing v1 source would invalidate exact matching. Handle by adding separate v2 files and registering both.
- **Warm-up:** a variable EMA period cannot rely on v1's 100-bar declaration. Handle with conservative v2 maximum warm-up of 200; no dynamic warm-up framework.
- **Version identity:** implementation-key text is not the displayed Atlas version. Always use persisted version number.
- **Cross-version interpretation:** equal visible values do not make v1 and v2 the same methodology. Always warn on StrategyVersion difference.
- **Decimal representation:** persisted historical strings may differ in scale. Compare by typed Decimal value while displaying the immutable snapshot value.
- **Metric authority:** service reuse is mandatory; UI-side or comparison-specific calculations are forbidden.
- **API drift:** generated OpenAPI freshness is a completion gate.

## Ordered implementation

1. **Preserve v1 and add v2 Strategy source.** Owners: Strategy/domain. Leave v1 implementation and indicators unchanged; add v2 definition/implementation and period-driven deterministic indicators with the exact schema and warm-up above. Validate unchanged five-bar state behavior and parameter-driven EMA/ATR/stop/target behavior.
2. **Support exact multi-version local registration.** Owners: Strategy registry/composition. Replace ambiguous Strategy-key execution lookup with exact provenance lookup, register v1 and v2 explicitly, expose stable catalog iteration, and retain clear unavailable errors. Do not load archived source dynamically.
3. **Synchronize immutable StrategyVersion catalog.** Owners: persistence/API composition. Add idempotent startup synchronization through the existing repository, deterministic registration order, transactional failure behavior, and derived execution availability. No database schema migration.
4. **Add Strategy history read contracts.** Owners: repositories/API. Implement catalog/detail aggregation and explicit response schemas without returning source contents; include optional Git SHA only as secondary provenance.
5. **Enable typed manual Experiment parameters.** Owners: Experiment API/frontend. Extend configuration options with availability/identity, render schema-driven editable/fixed fields, reset on version change, rerun coverage validation, and preserve the existing immutable create transaction.
6. **Add comparison read service.** Owners: Experiment results. Validate ordered eligibility, compose immutable facts, reuse canonical metric authority, perform typed deterministic differences, and emit warnings in fixed precedence.
7. **Add comparison API contract.** Owners: API. Add the bounded GET route and typed success/error responses before dynamic Experiment-ID route matching; test order, limits, statuses, zero-Trade, and unavailable metric states.
8. **Build Strategy and comparison UI.** Owners: frontend. Enable Strategies navigation/routes, add completed-only selection and `/experiments/compare`, place config/warnings before metrics, and preserve neutral non-ranking language.
9. **Regenerate contracts and run gates.** Owners: integration. Regenerate the OpenAPI client, update thin client methods/types, run backend/frontend quality suites, and execute the acceptance flow using v2 Experiments that differ by one parameter.

## Validation matrix

| Area | Required validation | Expected result |
| --- | --- | --- |
| v1 provenance | Fingerprint golden test before/after Phase 6 | Byte-identical v1 fingerprint and exact source snapshot |
| Registry | Exact lookup for persisted v1 and v2; wrong fingerprint/key | Correct implementation returned; mismatches fail closed |
| Catalog sync | Empty DB, existing v1, repeated startup, concurrent attempt | v1 then v2 appended once; no updates/duplicates |
| v2 schema | Boundary/default/out-of-range/wrong-type/non-finite cases | Four iterable values accepted only in bounds; expiry only five |
| Version semantics | Create several Experiments with different supported v2 values | All reference one v2 StrategyVersion with distinct immutable parameter snapshots |
| Methodology change | v1 vs v2 history/comparison | Separate fingerprints/versions and methodology warning |
| Indicators | Multiple supported EMA/ATR periods on deterministic fixtures | Exact repeatable values; no future bars used |
| Strategy behavior | Existing reference state-machine suite against v1; equivalent setup suite against v2 defaults | v1 unchanged; v2 defaults preserve setup/expiry decisions |
| Warm-up | v2 at EMA 200 and coverage boundary | 200 bars required; no exposure during warm-up |
| Stop/target | Supported buffer/R values long and short | Proposal changes deterministically; actual-entry/R semantics unchanged |
| Experiment create | Manual values, version switch, fixed field, server rejection | Correct typed snapshot; no cross-version value leakage or mutation |
| History API/UI | v1/v2, optional/no Git SHA, unavailable local version | Atlas identity always present; Git optional; unavailable clearly blocked |
| Comparison selection | 1, 2, 4, 5, duplicate, missing, PENDING/RUNNING/FAILED | Only 2–4 distinct COMPLETED accepted; whole invalid request rejected |
| Difference rules | Each dimension changed independently | Exact stable field difference and warning code/precedence |
| Parameter equality | Decimal `0.5` vs `0.50`; missing/type-changed key | Equivalent decimal not changed; schema differences explicit |
| Strong isolation | Same assumptions with one vs multiple parameter changes | Flag true only for exactly one parameter and no warning dimensions |
| Metrics | Normal, zero-Trade, infinite, unavailable, legacy contract | Phase 5 envelopes preserved; no fabricated zeros or coercion |
| Immutability | Compare/read and repeat requests | No database writes; identical facts produce identical response ordering |
| UI language | Visual/content review | No UUID labels, ranking, winner, recommendation, or optimization affordance |
| Contract freshness | OpenAPI generation check | Generated client is current and byte-stable |
| Regression | Phase 5 integration/golden/no-lookahead/accounting tests | Existing behavior remains green |

## Rollback implications

- StrategyVersion and Experiment data are append-only. Do not delete v2 rows or completed v2 Experiments as rollback.
- UI comparison/Strategies pages can be withdrawn without data changes.
- Once v2 is persisted or used, retain v2 local registration and availability filtering during rollback so exact execution/reproducibility remains possible. Reverting wholesale to a pre-Phase 6 backend is not the preferred rollback: it would safely fail exact v2 execution but could expose an unavailable v2 in the old configuration-options UI.
- Safe rollback is forward-compatible: disable new Phase 6 UI/API entry points while retaining multi-version registry/catalog support and immutable result reads, then issue a corrective release.
- No schema downgrade is needed because no table/column migration is introduced.

## Assumptions

- **Confirmed — high confidence:** Phase 1 v1 source-locked values are intentional historical semantics and must remain reproducible.
- **Confirmed — high confidence:** completed Experiment inputs/results and StrategyVersion rows are immutable.
- **Confirmed — high confidence:** all comparison inputs and canonical metrics already exist in durable Phase 5 facts; comparison persistence is unnecessary.
- **Confirmed — high confidence:** `expiry_window` is coupled to the five-bar state machine and is not a v2 iterable parameter.
- **Assumed — high confidence:** the bounded ranges in this blueprint are sufficient for deliberate initial manual research and intentionally avoid a generic parameter framework. Changing them after approval requires a new fingerprint/version.
- **Assumed — high confidence:** conservative fixed v2 warm-up of 200 bars is acceptable for the current single Strategy/Dataset workflow.
- **Deferred:** parameter-dependent warm-up, custom Experiment labels, comparison equity overlay, cloning/prefill, and richer version release notes.

## Acceptance criteria

Phase 6 is accepted only when all are true:

1. Existing v1 source fingerprint and behavior remain unchanged and v1 stays exactly executable.
2. A distinct immutable v2 is persisted with Atlas-owned version identity/provenance and Git remains optional.
3. The trader can manually enter all four supported typed v2 parameters; `expiry_window` is visible, fixed at five, and cannot be varied.
4. Two Experiments with different supported values reference the same v2 StrategyVersion and retain distinct immutable snapshots.
5. Strategy history clearly shows versions, fingerprints, schemas, creation/use provenance, and local availability without raw UUID labels.
6. The trader can select two to four COMPLETED Experiments and see configuration differences before canonical metrics.
7. StrategyVersion, Instrument, DatasetSnapshot, period, Risk, starting capital, simulation, model, and metric-contract differences produce deterministic explainable warnings.
8. Zero-Trade and unavailable/infinite metric states remain authoritative; FAILED/non-completed Experiments are rejected, not dropped.
9. Comparison performs no writes and creates no persisted comparison state.
10. No ranking, winner, recommendation, score, optimizer, sweep, or PAPER/LIVE behavior is introduced.
11. OpenAPI/client freshness and all Phase 5 regression, no-lookahead, Risk, execution, accounting, and immutability tests pass.

## Approval gate

No implementation begins until the developer explicitly approves this blueprint and the orchestrated workflow. Any implementation discovery that would require changing Phase 1 setup/expiry semantics, Phase 5 Experiment/metric semantics, the parameter ranges above, or persistence boundaries must stop and return to architecture rather than silently deviating.
