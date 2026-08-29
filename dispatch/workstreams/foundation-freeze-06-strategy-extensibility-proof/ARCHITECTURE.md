# Foundation Freeze 06 — Strategy Extensibility Proof Architecture

## Freeze status

- **Role:** `ARCHITECT`
- **Workstream:** `foundation-freeze-06-strategy-extensibility-proof`
- **Classification:** `Critical`
- **Status:** `FROZEN / DEVELOPER-APPROVED DESIGN — implementation not started;
  GIT START is permitted only in a new session when explicitly instructed.

This revision supersedes the prior EMA-compatible candidate. It freezes a
genuinely methodology-extensible, but deliberately constrained, Strategy
boundary. The proof remains one vertical slice:

`Strategy registration → immutable StrategyVersion → Strategy-owned parameter
configuration → Experiment → shared V2 runner → TradeIntent → Risk → Order →
Fill → Position/Trade → result and Trade evidence inspection`.

The only supplied market capability is EUR/USD, native M15 MID analysis, and
sparse native M1 BID/ASK execution. That slice limitation belongs to capability
validation, not to the generic `MarketSpecification` type. No other instrument,
timeframe, broker, provider, execution model, migration, plugin SDK, or dynamic
discovery is authorized.

## Existing path to preserve

`production.py` explicitly registers local implementations. The registry
validates metadata, archives declared source files, and resolves only the exact
`(strategy_key, implementation_key, source_fingerprint)` tuple. Catalog sync
persists immutable StrategyVersion identity, schemas, requirements, and exact
source. Configuration options expose only persisted versions with locally
available exact provenance. Experiment creation validates V2 snapshot coverage
and persists immutable configuration. `ExperimentRunService` calls the sole
V2 `ExperimentRunner`; the runner owns completed-bar scheduling, warm-up,
no-lookahead, intents, Risk, simulated execution, protection, Fill-derived
accounting, and finalization. Result readers and UI consume persisted facts.

All of those responsibilities remain in place. The changes below replace only
EMA-shaped contract plumbing and add the candidate through the same seams.

## Constrained generic contract

### Strategy-owned parameters

The five-field `StrategyParameters` class is removed from the generic Strategy
boundary. It may remain as a read-only EMA compatibility DTO, but configuration
and the runner must never construct it or name any of its fields.

The boundary consists of these small types and hooks:

1. `ParameterSchema` remains the persisted descriptor format. Supported wire
   values are only integer, finite decimal (canonical persisted string),
   boolean, enum/string, or nullable values where declared. Schemas have
   unique keys and explicit defaults/minimums/maximums/allowed values.
2. `ValidatedParameterPayload` is an immutable, exact-schema envelope of those
   flat primitive values. It rejects unknown/missing keys, wrong primitive
   types, non-finite decimals, out-of-range values, and nested objects/lists.
   It is limited to 32 declared fields, 64-character keys, and a 4096-byte
   canonical encoding. It exposes typed accessors only to the Strategy parser;
   it is never indexed by the runner or UI as an arbitrary dictionary.
3. Each registered Strategy owns a frozen typed parameter value object (for
   example `CandleConfirmationParameters`) implementing the narrow
   `StrategyParameterSet` contract: canonical `to_json()` plus no I/O. The
   Strategy owns `parse_parameters(ValidatedParameterPayload)` and only
   cross-field/methodology-specific semantic validation. Parsing a complete
   payload is required; defaults are declared by `StrategyDefinition`/
   `ParameterSchema` and materialized as a complete setup payload, never as a
   silent server-side partial merge.
4. Configuration performs shared schema/primitive validation, then calls the
   exact registered implementation's parser. It stores the parser's canonical
 JSON snapshot. The runner resolves the exact implementation first and calls
 the same parser on that immutable snapshot. Neither layer knows a parameter
 name.

The shared layer validates the payload against the declared `ParameterSchema`,
including exact keys, primitive types, defaults, min/max bounds, allowed values,
nullability, field/byte limits, and canonical representation. Shared
infrastructure does not know Strategy-specific names or duplicate bounds. The
registered Strategy parser converts that validated payload into its typed value
object and owns only cross-field and methodology-specific semantic validation;
it does not independently re-own the declared per-parameter bounds.

This is a constrained typed value boundary, not unrestricted JSON and not a
general extension framework. No Strategy receives account balance, Risk
configuration, broker state, database sessions, or environment mode.

### Atlas-owned state envelope and Strategy-owned payload

The current shared `StrategyState` is replaced at the public boundary by an
immutable `StrategyStateEnvelope` with exactly these responsibilities:

- `state_schema_version`, matching the immutable StrategyVersion;
- `last_evaluated_bar_end`, an optional UTC completed-bar frontier owned by
  Atlas;
- a bounded `StrategyStatePayloadDocument` identified by an explicit codec key
  and payload version; and
- an optional generic `PendingEntryHandoff` owned by Atlas for a
  `PRICE_TRIGGERED` decision.

`StrategyStatePayloadDocument` is not arbitrary JSON. It is produced and
consumed by the registered Strategy's typed codec and is limited to a flat,
serializable primitive field set, at most 16 fields, 64-character field keys,
256-character string values, a 4096-byte canonical encoding, explicit payload
version, and deterministic canonical serialization. The Strategy validates
its exact field names, types, ranges, and methodology semantics. The runner treats
the payload as opaque and never reads a Strategy field.

The envelope validator owns:

- exact state schema/version and payload codec matching;
- UTC, monotonic completed-bar frontier validation;
- rejection of a repeated or future frontier;
- bounded payload shape/size and deterministic round-trip;
- safe `exposure_allowed` behavior (no new opening decision while blocked or
  Position is non-FLAT); and
- generic pending-entry consistency.

`PendingEntryHandoff` contains only normalized entry handoff facts: policy,
direction, trigger price/basis when applicable, decision frontier/time, and a
positive completed-bar eligibility limit (1..1000) plus consumed count in
0..limit. It does not contain `Phase.ARMED`, `reference_*`, `watch_bars`, or any
Strategy phase name. An immediate Strategy has no pending handoff.

There is one normalized execution-eligibility clock. The Strategy methodology
declares the eligible window; the adaptor/contract translates it into
`PendingEntryHandoff`; and `ExperimentRunner` consumes that handoff mechanically
at the declared analytical frontiers. The runner may increment the normalized
`consumed_count` and complete the handoff only according to its declared limit,
but must not invent, extend, shorten, reset, or reinterpret the window. Legacy
`watch_bars` and normalized `consumed_count` are never competing authorities.
For EMA compatibility, the adaptor derives and synchronizes the handoff from the
unchanged EMA Strategy transition, preserving exact W1–W5 eligibility and W6
expiry semantics. The runner does not inspect Strategy payload fields.

For the historical Experiment proof, the envelope is an in-memory value for the
duration of a run. Freeze 06 proves only bounded canonical serialization,
deserialization/restoration, and deterministic continuation at the Strategy
contract. The runner may encode/decode it in memory for that proof, but must not
write a mid-Experiment checkpoint to PostgreSQL, a file, a checkpoint table, or
another persistence path. No migration is permitted. This is not a new
historical restart/persistence mechanism. If implementation discovers that
durable mid-Experiment state is required, it must stop and request developer
review rather than adding persistence. Existing Deployment/runtime persistence
rules remain outside this historical proof and are not redesigned here.

The existing EMA implementation remains behaviorally unchanged through one
explicit compatibility adaptor at production composition:

- the adaptor decodes the legacy EMA `StrategyParameters` and `StrategyState`
  DTOs into/from the new typed parameter and state envelope in the Strategy
  contract, without creating a historical checkpoint;
- legacy `Phase.ARMED`, reference fields, sweep/confirmation fields, and W1–W5
  count exist only inside that adaptor's EMA compatibility payload;
- the adaptor translates the old decision's trigger fields into
  `PendingEntryHandoff`; and
- the existing EMA source, indicator arithmetic, rationale, SetupFacts JSON,
  state meaning, and registered source fingerprint remain unchanged.

The old DTOs are compatibility-only and are not accepted by the new generic
state validator. The adaptor is contract plumbing, not a new Strategy
implementation or discovery mechanism. Freeze 06 adds no database column,
checkpoint table, checkpoint path, migration, or other durable mid-Experiment
storage for the envelope or payload.

### Generic rationale and evidence

Add an immutable `StrategyEvidence` value with an explicit evidence schema key,
version, and bounded flat typed fields (at most 32 fields, 64-character keys,
256-character strings, and an 8192-byte canonical encoding; values are strings,
finite decimals, integers, booleans, or UTC timestamps). `StrategyDecision`
gains an optional evidence value.
The existing EMA `setup_facts` field remains a legacy compatibility field.

Intent persistence follows this exact rule:

- if legacy `SetupFacts` is present, preserve the current EMA rationale JSON,
  setup-facts JSON, three landmarks, and all existing evidence bytes/meaning;
- otherwise persist `StrategyDecision.evidence` as the generic evidence object,
  with no runner interpretation, candle naming, landmark synthesis, or
  browser inference.

The existing JSONB rationale and generic result `evidence` response fields are
the persistence/read seam. Result readers pass candidate evidence through;
`_rationale_facts` and reference/sweep/confirmation landmarks remain only the
EMA compatibility projection. Candidate evidence is not converted into
`SetupFacts`.

### Validated market specification

Add the smallest immutable `MarketSpecification` to `StrategyContext`:

```text
instrument: Instrument
pip_size: Decimal
```

The type is capability-neutral: it has no EUR/USD default, EUR/USD-only generic
type parameter, or permanent instrument literal. Its contract requires an
`Instrument`, a positive finite `Decimal` `pip_size`, and a pip size matching
the supplied instrument under capability validation. The current validated
capability resolver is the only provider in this proof (the OANDA capability
path, concretely `OANDA_CAPABILITY`); it supplies the one supported pair
`Instrument.EUR_USD` + `Decimal("0.0001")`. Context construction must consume
that resolver output rather than inventing a pip size. Unsupported instruments,
or a supported instrument with a non-matching pip size, fail closed through
capability validation before Strategy evaluation. No additional instrument or
provider is added to make the generic type appear extensible.

`StopProposal.price` remains an absolute normalized Decimal price. Freeze 06
supports a Strategy deriving that price from decision-time facts, including a
pip offset from candle prices, using the resolver-supplied `pip_size`; Risk
continues to validate absolute stop geometry and does not learn about pips.
Fill-relative, trailing, break-even, and dynamically managed stops are outside
this freeze.

## Candidate: Candle Confirmation Break v1

### Definition

The second registration is a real, non-EMA implementation:

| Field | Frozen value |
|---|---|
| `strategy_key` | `candle_confirmation_break` |
| `implementation_key` | `candle_confirmation_break.v1` |
| display name | `Candle Confirmation Break` |
| analysis | EUR/USD native M15 MID, completed only |
| execution | existing sparse native M1 BID/ASK |
| capabilities | `LONG`, `SHORT`, `STOP_LOSS`, `TAKE_PROFIT` |
| warm-up | 1 completed M15 bar |
| state schema | 1, generic envelope plus candidate payload |
| entry policy | `IMMEDIATE` |

### Typed parameters

The candidate owns exactly three parameters:

| Key | Default | Bounds |
|---|---:|---|
| `confirmation_bars` | `2` | integer `1..3` |
| `stop_buffer_pips` | `20` | finite decimal `1..100` |
| `target_r` | `1.5` | finite decimal `0.5..5.0` |

The typed `CandleConfirmationParameters` object is the only place these names
are interpreted. The candidate has no EMA/ATR/expiry parameter and does not
receive the legacy EMA DTO.

### Method and state

For each newly supplied completed M15 MID bar, let `prior` be the immediately
preceding completed bar and `signal` the current bar. A directional break is:

- LONG: `signal.close > signal.open` and `signal.close > prior.high`;
- SHORT: `signal.close < signal.open` and `signal.close < prior.low`;
- doji or equality is not a break.

The typed candidate payload contains only:

```text
candidate_direction: LONG | SHORT | null
confirmation_count: integer 0..3
candidate_started_at: UTC timestamp | null
```

On a break matching the stored direction, increment the count; on a direction
change, restart at one; on no break, clear the payload. When the count reaches
`confirmation_bars`, emit an immediate opening decision and clear the payload.
Thus `confirmation_bars=1` opens on one break, while the default requires two
consecutive same-direction breaks. The next state always retains only the
bounded candidate payload and Atlas frontier.

For a LONG decision:

```text
stop = signal.low - (stop_buffer_pips × context.market.pip_size)
```

For SHORT:

```text
stop = signal.high + (stop_buffer_pips × context.market.pip_size)
```

The decision carries an absolute `StopProposal`, an existing
`TargetProposal(R_MULTIPLE, target_r)`, matching direction, and current UTC
decision time. The target is resolved from the actual executable entry by
Risk/execution. The Strategy never sizes or assumes signal-close entry.

Candidate evidence is schema `CANDLE_CONFIRMATION_BREAK_EVIDENCE_V1` and
records direction, prior/signal timestamps and OHLC, confirmation count and
parameter, `pip_size`, `stop_buffer_pips`, absolute proposed stop, and target
multiple. It is generic persisted evidence, not `SetupFacts`.

When exposure is disallowed or Position is non-FLAT, the candidate emits
`NO_ACTION`, clears its payload, remains safe, and advances only the Atlas
frontier. It never creates a pending handoff.

## Current EMA hardcodes and affected seams

### Strategy-owned reference facts to preserve

- `backend/strategies/ema_sweep_confirmation_break.py` owns EMA/ATR parameter
  meanings and bounds, trend qualification, reference/sweep/confirmation
  state machine, `Phase.ARMED`, W1–W5 received-bar semantics, trigger/stop/
  target proposal, rationale codes, and `SetupFacts`.
- `backend/strategies/indicators_v2.py` owns the current deterministic EMA/ATR
  arithmetic used by the reference. Numerical outputs stay unchanged.
- The old `StrategyParameters`, `StrategyState`, `Phase`, and `SetupFacts`
  shapes in `domain/strategy.py` are preserved as EMA compatibility DTOs and
  legacy serialization compatibility authority, not used as the generic
  boundary.
- Existing EMA StrategyVersion identity/source fingerprint, golden flows,
  result/chart facts, API responses, and reference tests are regression
  authorities. No legacy `ema_sweep_engulfing` behavior is activated.

### Shared seams that must change

| Seam | Necessary change | Why financial/execution semantics do not change |
|---|---|---|
| `strategies/contract.py` and `domain/strategy.py` parameter boundary | Add `ValidatedParameterPayload`; `StrategyDefinition`/`ParameterSchema` declares type/default/bounds/allowed values/nullability, Atlas validates against it, and the Strategy parser owns typed conversion plus cross-field/methodology semantics; keep EMA DTO behind adaptor. | Only representation and validation ownership changes. Parameter snapshot values, Strategy decisions, Risk inputs, and Experiment immutability remain the same. |
| `experiments/configuration.py:_validate_parameters` | Validate persisted schema generically, call the exact implementation parser, persist canonical `to_json`; remove all five EMA names. | Configuration still rejects invalid input before graph creation and stores the exact chosen values; no order, price, quantity, or Risk path changes. |
| `experiments/runner.py:_parameters` and initial state | Resolve implementation, parse the immutable snapshot, and request its typed initial envelope; remove EMA construction. | The same V2 clock and completed M15 evaluation schedule remain authoritative. Only the Strategy value/state supplied at the boundary changes. |
| `experiments/runner.py` pending handoff | Replace `Phase.ARMED`/`watch_bars < 5` reads with the single normalized `PendingEntryHandoff` clock. The EMA adaptor derives/synchronizes it from the unchanged transition with limit 5 and preserves W1–W5/W6 timing exactly; legacy `watch_bars` cannot compete. | Trigger timing, first post-decision M1 observation, ASK/BID selection, expiry, and fills remain identical for EMA; immediate candidate never enters this path. |
| `experiments/runner.py:_create_intent` | Persist optional generic `StrategyEvidence` without inspecting it; preserve the existing SetupFacts branch exactly. | Only evidence transport changes for non-EMA decisions. Intent action, frontier, stop, target, entry policy, source IDs, Risk, and execution are unchanged. |
| `domain/strategy.py:StrategyContext` and requirements projection | Add capability-neutral `MarketSpecification(instrument, pip_size)` and expose the current validated resolver's result to Strategy code; the resolver supplies only EUR/USD + `0.0001` in this slice. | It supplies a validated calculation fact only. A Strategy may derive an absolute decision-time stop, including a pip offset; Risk and Instrument rules remain unchanged. |
| `experiments/results.py` and API result schema | Make EMA series/diagnostic/reference projections optional compatibility data; pass generic rationale/evidence through without requiring `ema_period` or parsing SetupFacts. | M15 snapshot selection, execution facts, metrics, and immutable result authority do not change. Existing EMA rows still receive the same compatibility projection. |
| setup/result UI | Render parameter controls and market requirements from the selected StrategyVersion; render evidence as opaque persisted fields. Show EMA/reference labels only when the compatibility projection is present. | The browser displays server facts and never detects a candle pattern or changes a financial value. |

### Hardcodes that must remain frozen

The EUR/USD/M15/MID completed-only contract, V2 snapshot schema, native M15
membership, sparse native M1 BID/ASK membership, UTC/frontier semantics,
SimulationClock, Risk PRE_FLIGHT/PRE_SUBMISSION, executable-side pricing,
Order/OrderEvent/Fill/Position/Trade/accounting, protection, OANDA adapter,
DatasetSnapshot fingerprints/coverage, and completed-result fail-closed reads
are shared slice contracts, not EMA assumptions. They must not be generalized
or reimplemented for this proof.

## Compatibility and persistence rules

- `StrategyVersion` remains immutable. Its persisted parameter schema is the
  candidate's three-key schema or the reference's existing five-key schema;
  parameters changing creates a new Experiment, never a new version.
- Exact source provenance remains the lookup authority. The EMA compatibility
  adaptor is contract plumbing and must not alter the existing EMA source
  archive/fingerprint or create a new EMA version.
- A completed Experiment retains the exact canonical parameter JSON, generic
  rationale/evidence facts, DatasetSnapshot identity, Risk/simulation
  snapshots, and result graph. The historical `StrategyStateEnvelope` is not a
  new durable Experiment fact: it may remain in memory for the run and its
  canonical serialization is exercised only at the Strategy contract. No
  mid-Experiment checkpoint table/path or migration is permitted.
- The generic API may add optional `pipSize`, optional EMA projection fields,
  and a generic evidence payload. Existing EMA response fields and serialized
  facts remain compatible.
- Setup controls are generated from the selected persisted `parameterSchema`;
  fixed values are read-only from min/max. Market display is generated from
  selected `marketRequirements` (including `pipSize`), not from an EMA-known
  list or browser constants.
- Trade detail renders the persisted reason code, rationale, evidence schema,
  and evidence fields. It does not render candidate facts by recognizing
  `confirmation_bars`, candle shapes, or names. EMA SetupFacts is rendered only
  by its existing explicit compatibility view.

## Invariants and failure behavior

- A Strategy is pure: no broker, database, filesystem, network, wall clock,
  account, Risk, or Experiment/PAPER/LIVE branching.
- Only completed bars with `bar.end_time <= evaluation_time` are visible.
  The same frontier cannot be evaluated twice. Missing/future/out-of-order
  data is rejected; no lookahead or fabricated bar is allowed.
- Atlas owns the frontier and safety envelope. A malformed, incompatible,
  oversized, non-serializable, or future state payload blocks new exposure and
  fails the run; no silent reset is allowed.
- A Strategy-owned parser may reject semantically invalid values after shared
  primitive validation. Invalid/missing/extra parameter keys fail as
  `PARAMETERS_INVALID` before an Experiment graph is created.
- Registration/source/archive/duplicate failures are actionable and do not
  partially catalog a version. Missing exact provenance yields
  `STRATEGY_VERSION_UNAVAILABLE`; no fallback implementation is selected.
- Invalid market specification or a capability mismatch fails closed before
  Strategy evaluation. The generic type does not encode EUR/USD, but the
  current validated capability resolver supplies only EUR/USD + `0.0001` and
  rejects unsupported instruments or non-matching pip sizes; the candidate
  cannot bypass that validation or request another capability.
- If state serialization, restoration, or deterministic continuation fails, the
  historical run fails closed with no new intent, Order, Fill, or invented
  state. The runner must not repair/reset it and must not add durable checkpoint
  persistence; durable state discovery is a developer-review stop condition.
- Opening decisions require matching action/direction/stop direction, absolute
  finite stop price, valid immediate-entry fields, and positive R target. Risk
  still owns geometry at the executable price and final quantity.
- Risk rejection persists the decision where applicable and creates no Order or
  Trade. Execution uncertainty remains UNKNOWN/reconciliation-required; no
  blind retry or invented Fill occurs. Existing protection remains authoritative.
- Missing sparse post-frontier execution data records the existing gap/diagnostic
  and creates no Fill. A no-signal period is a valid zero-Trade Experiment.
- Failed/incomplete results are not presented as trustworthy metrics. Completed
  zero-Trade results explicitly report zero Trades and unavailable trade-based
  metrics.
- Generic evidence is immutable and pass-through. A malformed evidence payload
  fails the Strategy boundary; readers never repair, reinterpret, or infer it.

## Valid, invalid, and boundary examples

### Valid

- Candidate registration persists exact identity, three-key schema, codec/state
  schema, requirements, source archive, and fingerprint; options expose it.
- Candidate defaults and all bounds are accepted: confirmation bars 1/3, pip
  buffer 1/100, target 0.5/5.0.
- The validated capability resolver supplies a valid generic
  `MarketSpecification(instrument=EUR/USD, pip_size=0.0001)`; the type itself
  contains no EUR/USD-only parameterization.
- Two consecutive bullish M15 breaks, where each close is strictly above the
  prior high, produce one immediate LONG decision. Its stop is the second
  signal low minus `20 × 0.0001`; target is the existing R multiple.
- The inverse bearish sequence produces one immediate SHORT decision with stop
  above the signal high. A later sparse M1 ASK/BID observation is used by the
  existing immediate-entry execution path.
- State round-trip preserves candidate direction/count/start time and Atlas
  frontier. Replaying identical version, parameters, bars, state, and time
  produces identical output and evidence.
- A valid period with no qualifying sequence completes as zero Trade with honest
  result metrics and candidate provenance.

### Invalid

- Candidate parameter payload with any EMA key, missing/extra key, count 0/4,
  pip buffer 0.99/100.01, target 0.49/5.01, wrong primitive, non-finite
  decimal, or nested value.
- State payload with unknown codec/version, count outside 0..3, direction/count
  mismatch, naive/future timestamp, duplicate frontier, or encoded size above
  the frozen bound.
- Candidate decision containing EMA `SetupFacts`, `PRICE_TRIGGERED` fields,
  trigger expiry, non-absolute stop, wrong stop side, or environment metadata.
- Context with non-UTC/incomplete/future/non-M15/non-MID bars, or a
  resolver-rejected/unsupported instrument, or a market specification with a
  non-positive, non-finite, or non-matching pip size. Directly supplying a
  different pair cannot bypass capability validation.
- Insufficient native M15 coverage, invalid DatasetSnapshot membership,
  one-sided/unacquired BID/ASK execution, unavailable exact provenance, or a
  failed Risk check. None may invent an exposure or Fill.

### Boundaries and no-lookahead

- A bar ending exactly at the evaluation frontier is eligible; one ending even
  one microsecond later is rejected. A repeated frontier is rejected.
- `close == open`, `close == prior.high`, and `close == prior.low` do not make a
  directional confirmation break; strict inequalities are required.
- A decision at an M15 completion may use only M15 data ending at that frontier.
  Its immediate Fill may use only the first eligible sparse M1 observation
  strictly after the frontier; the signal interval cannot be reused.
- `LONG` stop must be below the actual executable entry and `SHORT` stop above
  it. Equality or market movement invalidating geometry is rejected by Risk at
  PRE_SUBMISSION.
- `pip_size` is positive, finite, and matched to the supplied instrument by the
  capability validation path; zero, negative, NaN, infinity, or an unsupported
  instrument/pip pair is rejected before Strategy evaluation.
- `pip_size` may be used with decision-time candle facts to derive an absolute
  stop (LONG signal low minus the pip buffer, inverse SHORT rule). Fill-relative,
  trailing, break-even, and dynamically managed stops are outside Freeze 06.
- EMA's existing confirmation decision remains price-triggered, with W1–W5
  eligible and expiry observed at W6. The generic envelope reproduces this
  without exposing those names to the candidate or runner.

## Required test matrix

| Area | Required evidence |
|---|---|
| Registration | Explicit candidate registration, metadata/schema validation, duplicate rejection, unsafe source rejection, stable archive/fingerprint, catalog sync idempotence, exact-provenance lookup, unavailable-version omission, original registration/fingerprint unchanged. |
| StrategyVersion | Candidate immutable version stores three-key schema, state schema, requirements, source manifest/snapshot and implementation key; parameter changes do not create versions; source changes require a new version; no migration. |
| Parameter parsing | `StrategyDefinition`/`ParameterSchema` declaration of defaults, min/max, allowed values, nullability, and primitive types; Atlas validation against that declaration; candidate typed parser conversion plus cross-field/methodology semantic validation; every lower/upper boundary; EMA keys rejected for candidate; parser canonical round-trip; configuration and runner call the same parser; original five-key EMA configuration regression. |
| Market context/pips | Capability-neutral `MarketSpecification` shape; positive/finite/matching validation; exact ownership test proving the current validated OANDA capability resolver supplies EUR/USD + `pip_size=0.0001`; unsupported instrument/mismatch rejection; candidate LONG/SHORT absolute stop arithmetic from decision-time candle facts; no pip conversion in Risk/execution. |
| State contract | Atlas envelope schema/frontier validation; bounded payload codec; canonical serialize → restore and deterministic continuation at the Strategy contract; candidate count/direction transitions; invalid/future/duplicate/oversized state; exposure-disallowed/non-FLAT clearing; EMA adaptor W1–W5/W6 and legacy state meaning unchanged. Historical state may stay in memory only: assert no mid-Experiment checkpoint table/path/file/migration or persistence call is added. If durable state is discovered necessary, stop for developer review. |
| Public Strategy seam | Candidate conformance, no I/O/environment dependence, completed bars only, no lookahead, strict candle boundaries, doji/equality behavior, deterministic LONG/SHORT/immediate decisions, no pending handoff; EMA adapter conformance. |
| Evidence/rationale | Candidate evidence schema and fields persist without SetupFacts; intent writer passes evidence opaquely; malformed evidence fails closed; result/Trade reads return exact evidence; EMA rationale, SetupFacts bytes, landmarks, and meaning remain unchanged. |
| Experiment creation | Candidate selected through schema/requirements-driven options; UTC range, warm-up, native M15 and sparse M1 coverage; invalid parameters/provenance/snapshot fail before creation; immutable candidate parameter snapshot and resolver-backed market requirements recorded. Invalid runtime state fails the run before any new intent, not by creating a checkpoint. |
| Experiment execution | Candidate uses the sole V2 runner with no candidate branch; warm-up/no exposure; one evaluation per M15 frontier; immediate post-frontier BID/ASK entry; Risk PRE_FLIGHT/PRE_SUBMISSION; canonical Order/Fill/Position/Trade/account/equity/result graph; deterministic replay and zero-Trade case. |
| Failure/safety | Strategy/parser/state serialization or restoration errors, missing data, invalid absolute stop, Risk rejection, execution gap/uncertainty, intent/result persistence failure, and incomplete result produce typed persisted failure where the existing result seam permits it, with no invented exposure, Fill, protection, metrics, evidence, or checkpoint. |
| Result inspection | Candidate identity/version/fingerprint, exact parameters, market/pip requirement, assumptions, rationale/evidence, Risk and Order/Fill lineage; generic evidence pass-through; no EMA/reference inference; optional EMA compatibility projection still works for historical EMA results; failed/not-ready reads fail closed. |
| UI schema rendering | Setup renders selected schema labels/defaults/types/min/max and fixed fields without EMA list; market requirements/pip size come from selected version; result/Trade detail renders opaque evidence and only displays EMA/reference compatibility UI when supplied. |
| Original EMA regression | Existing EMA contract/provenance/golden long-short/trigger/expiry, state/evidence, result/chart, API, and frontend tests remain green. Add source/AST guards showing no candidate identity branch in runner/Risk/execution/market-data/snapshot/result interpretation and no financial-semantic diff. |

## Implementation gate

**Design approved; implementation not started.** This artifact does not authorize
implementation in the current session. `GIT START` may occur only in a new
session when explicitly instructed. No application/test implementation, branch
switch, task creation, migration, or Git history change is authorized before
that instruction.
