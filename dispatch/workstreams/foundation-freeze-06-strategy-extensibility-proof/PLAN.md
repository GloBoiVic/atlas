# Foundation Freeze 06 — Strategy Extensibility Proof

## Outcome

Prove genuine Strategy methodology extensibility through constrained Atlas
contracts. A second Strategy must be able to own different parameters,
methodology state, evidence, and pip-based stop derivation while using the
existing historical capability:

`EUR/USD native M15 MID analysis → sparse native M1 BID/ASK execution`.

The proof must cover:

`Strategy registration → immutable StrategyVersion → Strategy-owned parameter
configuration → Experiment creation → shared V2 runner → TradeIntent/Risk/
Order/Fill → result and Trade evidence inspection`.

The validated EMA Sweep Confirmation Break v2 Strategy must remain unchanged in
methodology and persisted historical meaning.

## Classification and approval status

- **Classification:** `Critical` — the requested boundary changes cross Strategy
  contracts, configuration, state/evidence persistence, UI metadata, and the
  Experiment handoff while protecting financial semantics.
- **Status:** `IMPLEMENTATION IN PROGRESS — developer-approved design; GIT START
  completed at the requested base SHA.`
- **Developer directive reconciled:** the prior EMA-specific compatibility
  candidate is rejected. The architecture must establish constrained generic
  plumbing rather than force a second Strategy into EMA parameter/state/evidence
  shapes.
- **Implementation:** authorized on the execution branch after GIT START. No
  migrations or generated-client changes are authorized unless directly required
  by the frozen boundary.
- **Architecture status:** `FROZEN / DEVELOPER-APPROVED DESIGN`; implementation
  remains not started. See `ARCHITECTURE.md` for the constrained generic seams,
  candidate, invariants, failure behavior, examples, and test matrix.

## Repository state

- **Inspected branch:** `main`
- **Base SHA:** `50c5e18b27d2d652c807f4ca3068ca66cd664687`
- **Current checkout:** `solo/foundation-freeze-06-strategy-extensibility-proof`
  at the requested base SHA
- **Pre-existing untracked files:** `.codegraph/`, `frontend/.env.local`; preserve
  and exclude from this workstream
- **Execution branch:** create only after approval as
  `solo/foundation-freeze-06-strategy-extensibility-proof`

## Existing path explored and frozen

1. `backend/strategies/production.py` explicitly registers the current
   `EmaSweepConfirmationBreakStrategy` in `StrategyRegistry`.
2. Registry registration validates metadata, archives declared source files, and
   matches implementations by `(strategy_key, implementation_key,
source_fingerprint)`.
3. `backend/persistence/strategy_catalog.py` and
   `StrategyRepository.create_version` persist immutable StrategyVersion
   identity, schema, requirements, state schema, source manifest, exact source,
   and fingerprint.
4. Configuration options expose persisted versions only when exact local
   provenance is available. `ExperimentConfigurationService` validates the
   version's market-data requirement and immutable V2 DatasetSnapshot coverage,
   then creates a PENDING Experiment graph with an immutable parameter snapshot.
5. `ExperimentRunService` claims the Experiment and calls the sole
   `ExperimentRunner.run` entry point. `_run_v2` loads persisted native M15 MID
   and sparse M1 BID/ASK members, advances `SimulationClock`, and calls the
   checked Strategy contract at warm-up and completed M15 frontiers.
6. The runner owns scheduling, no-lookahead, TradeIntent persistence, Risk,
   simulated execution, protection, Fill-derived accounting, and result
   finalization. Strategy code never sizes, submits, or performs I/O.
7. Result readers and frontend components consume immutable persisted identity,
   parameters, rationale/evidence, Risk, Order/Fill, Trade, and bounded market
   context. They must not rediscover methodology from candles.

## Hardcoded assumption inventory

### Strategy-owned current reference facts — preserve unchanged

- `backend/strategies/ema_sweep_confirmation_break.py` owns the EMA/ATR
  parameters and bounds, sweep/confirmation state machine, `Phase.ARMED` and
  W1–W5 semantics, trigger/stop/target proposals, rationale codes, and
  `SetupFacts` evidence.
- The current `StrategyParameters`, `StrategyState`, and `SetupFacts` in
  `backend/domain/strategy.py` are incorrectly shaped as shared abstractions but
  remain read-only EMA compatibility DTOs/adaptor payloads. Their reference
  behavior and serialized facts cannot change; they are not the new generic
  Strategy boundary.
- Existing EMA indicator arithmetic, source fingerprint/version, golden flows,
  result/chart facts, and reference tests are regression authorities.

### Shared EMA-specific plumbing that must be removed or isolated

- `backend/experiments/configuration.py:_validate_parameters` constructs
  `StrategyParameters` using `ema_period`, `atr_period`, `stop_buffer`,
  `target_r`, and `expiry_window` instead of delegating parsing/defaults/bounds
  and validation to the registered Strategy. It must use a constrained exact-
  schema primitive envelope and the Strategy-owned parser.
- `backend/experiments/runner.py:_parameters` reconstructs those same fields
  before execution. It must resolve the implementation and call the same
  Strategy-owned parser against the immutable snapshot.
- `backend/experiments/runner.py` reads `Phase.ARMED`, `watch_bars`, and the
  literal five-bar limit for the pending price-trigger handoff. This must become
  a generic Atlas-owned `PendingEntryHandoff`; the EMA adaptor maps its legacy
  state to that handoff and preserves W1–W5/W6 behavior exactly.
- `backend/experiments/runner.py:_create_intent` assumes `SetupFacts` contains
  exactly `reference`, `sweep`, and `confirmation`, dropping non-reference
  structured evidence. It must pass a bounded generic `StrategyEvidence`
  payload opaquely while preserving the existing EMA path.
- `backend/experiments/results.py`, `backend/api/schemas.py`, and related UI
  currently require/report EMA series and EMA diagnostics and project
  reference-shaped facts. EMA-specific chart output may remain an optional
  compatibility projection, but generic rationale/evidence must pass through
  without EMA or `SetupFacts` inference.
- Strategy context currently exposes only `Instrument`; a bounded validated,
  capability-neutral `MarketSpecification` containing `instrument` and
  `pip_size` is needed for Strategy stop derivation. The current capability
  resolver may supply only EUR/USD with `pip_size=0.0001`; unsupported
  instruments still fail closed through capability validation.
- Setup UI must not construct controls from an EMA-known list or display fixed
  market/timeframe facts as if they were global. It must render the selected
  StrategyVersion parameter schema and market requirements metadata.

### Already generic and not to be regressed

Registry/provenance matching, StrategyVersion persistence, immutable Experiment
snapshots, DatasetSnapshot membership/fingerprint/coverage, native M15 and
sparse M1 acquisition, Risk, Order/Fill/Position/Trade/accounting, OANDA
normalization, and completed-result fail-closed reads are not to be redesigned.
Legacy `ema_sweep_engulfing` and V1 aggregation references remain historical
compatibility only and are not the candidate.

## Revised candidate

The second proof Strategy is **Candle Confirmation Break v1**, a non-EMA,
immediate-entry Strategy using the same fixed market capability.

Candidate identity and methodology are frozen by the revised ARCHITECTURE:

- `strategy_key=candle_confirmation_break`,
  `implementation_key=candle_confirmation_break.v1`;
- one completed M15 bar of warm-up and capabilities
  `LONG`, `SHORT`, `STOP_LOSS`, `TAKE_PROFIT`;
- a bullish signal breaks strictly above the prior high and a bearish signal
  breaks strictly below the prior low; consecutive same-direction breaks reach
  the configured confirmation count and emit an immediate opening decision.

- Parameters are Strategy-owned: `confirmation_bars` (integer `1..3`, default
  `2`), `stop_buffer_pips` (finite decimal `1..100`, default `20`), and
  `target_r` (finite decimal `0.5..5.0`, default `1.5`). No EMA parameter is
  accepted.
- Doji, equality, no-break, and direction changes that do not satisfy the
  candidate's deterministic confirmation rule cannot confirm. No EMA,
  reference/sweep/confirmation `SetupFacts`, or price-triggered pending window
  is used.
- Stops are absolute normalized prices derived inside the Strategy: LONG
  `signal.low - stop_buffer_pips × context.market.pip_size`, inverse SHORT
  geometry. Risk receives no pip rule.
- Freeze 06 supports Strategy-derived absolute `StopProposal` prices from
  decision-time facts, including pip offsets from candle prices. Fill-relative,
  trailing, break-even, and dynamically managed stops remain outside this freeze.
- Emit an R-multiple `TargetProposal` resolved by existing Risk/execution from
  the actual executable entry.
- Persist candidate-owned rationale/evidence describing its candle signal,
  confirmation count, pip buffer, pip size, proposed stop, and target multiple.
- Persist only bounded serializable methodology payload and the generic Atlas
  frontier/safety envelope; no `Phase.ARMED`, reference fields, or watch-bar
  assumptions. Candidate evidence is generic pass-through, not a fabricated
  reference evidence object.

The candidate must be genuinely different in parameters, methodology state, and
evidence. It must not be a renamed EMA implementation or a test-only fake.

## Exact invariant boundary

### May change for generic contract plumbing and the candidate

- Replace the concrete shared parameter construction with constrained immutable
  `ValidatedParameterPayload`. `StrategyDefinition`/`ParameterSchema` declares
  each parameter's primitive type, default, min/max, allowed values, and
  nullability; Atlas validates the payload exactly against that declaration. The
  Strategy parser converts the validated payload into its typed object and owns
  only cross-field/methodology-specific semantic validation. Shared code must
  not name EMA fields, duplicate bounds, or independently own parameter rules.
- Separate an Atlas-owned immutable `StrategyStateEnvelope` (state schema
  version, consumed completed-bar frontier, safety/entry-handoff metadata) from
  a bounded Strategy-owned serializable payload. The envelope validates type,
  size, schema/version, UTC/frontier, pending-entry consistency, and deterministic
  round-trip. It must not require `Phase.ARMED`, `reference_*`, or `watch_bars`
  for a Strategy with no pending entry. During a historical Experiment the
  envelope may remain in memory for the run; Freeze 06 adds no durable
  mid-Experiment checkpoint persistence and no migration. If implementation
  discovers that durable checkpoint state is required, stop for developer review.
- `PendingEntryHandoff` is the single normalized execution-eligibility clock.
  ExperimentRunner consumes it mechanically and may only advance the declared
  count at the declared analytical frontiers; it must not invent, extend,
  shorten, reset, or reinterpret the Strategy-declared window. EMA's adaptor
  derives and synchronizes that handoff from the unchanged EMA transition;
  legacy `watch_bars` and generic `consumed_count` are never competing
  authorities.
- Add bounded immutable `StrategyEvidence` to the decision and intent
  persistence seam. Existing EMA `SetupFacts` serialization and
  reference/sweep/confirmation landmarks remain byte-for-byte equivalent; other
  Strategies pass through their own evidence without runner/result/browser
  interpretation.
- Add the smallest validated EUR/USD market specification needed by Strategies,
  including fixed `pip_size=0.0001`, to Strategy context while keeping the generic
  type capability-neutral. Do not add instruments, brokers, resolutions,
  providers, or a generalized market SDK.
- Add the candidate module, explicit production registration, source provenance,
  candidate tests, and generic catalog/options/UI schema consumption.
- Update setup/result/Trade inspection presentation so it renders persisted
  StrategyVersion schema, market requirements, rationale, and evidence generically
  while retaining current EMA compatibility projections.

### Must remain behaviorally and semantically untouched

- EMA Sweep Confirmation Break v2 methodology, parameter meanings/defaults/bounds,
  state/evidence JSON, W1–W5 pending behavior, golden outputs, and historical
  StrategyVersion/result interpretation.
- Runner scheduling, completed-frontier/no-lookahead ordering, warm-up gating,
  immediate-entry execution, existing EMA pending-entry eligibility, Risk
  PRE_FLIGHT/PRE_SUBMISSION, quantity/protection resolution, Order/Fill handling,
  Position/Trade/accounting, result finalization, and failure authority.
- Native EUR/USD M15 MID analytical acquisition, sparse native M1 BID/ASK
  execution acquisition, DatasetSnapshot semantics/fingerprints/coverage,
  OANDA integration/normalization, and immutable completed Experiment facts.
- No candidate-specific conditionals in ExperimentRunner, Risk, execution,
  accounting, market-data acquisition, snapshots, OANDA, or result interpretation.
  Generic contract plumbing must dispatch through Strategy-owned hooks/data only.
- No dynamic discovery, arbitrary unrestricted JSON runtime, plugin framework,
  additional capability, speculative SDK, migration, or PAPER/LIVE behavior.

## Acceptance criteria

- Candidate registration/catalog/version persistence uses explicit exact
  provenance and leaves the reference registration/fingerprint unchanged.
- Candidate options expose only its own parameter schema/defaults/requirements;
  shared configuration and runner contain no EMA parameter construction.
- Candidate valid/boundary/invalid parameters are accepted/rejected by the
  Strategy-owned contract and an immutable Experiment captures the exact parsed
  snapshot; changing parameters creates a new Experiment, not a version.
- Candidate state contains a valid Atlas envelope plus bounded custom payload,
  round-trips deterministically, rejects invalid/future/duplicate frontiers, and
  never requires EMA phases or watch bars. No durable mid-Experiment state
  checkpoint table, persistence path, or migration is introduced.
- Candidate rationale/evidence and pip-based absolute StopProposal survive
  Strategy → TradeIntent → result/Trade inspection. EMA evidence remains
  unchanged; no reader or browser infers candidate facts.
- Candidate Experiment creation and execution use the existing V2 clock and
  immediate-entry path and produce canonical Risk, Order, Fill, Position/Trade,
  accounting, and result facts. The runner has no candidate identity branch.
- Setup UI is driven by selected StrategyVersion parameter schema and market
  requirements, not an EMA-known parameter list or global EUR/USD/M15 literals.
- Existing EMA unit, provenance, golden execution, result, API, and UI regression
  tests remain green, with source/AST guards for forbidden candidate-specific
  branches and unchanged financial seams.
- Failure paths remain fail-closed: invalid registration/parameters/state,
  unavailable provenance, insufficient native coverage, invalid stop geometry,
  Risk rejection, missing execution, and incomplete/failed results never invent
  exposure, fills, protection, metrics, or evidence.
- Strategy-derived absolute proposed stops are proven from decision-time candle
  facts and pip offsets; fill-relative, trailing, break-even, and dynamically
  managed stops are explicitly excluded.

## BUILD tasks

1. `T001-generic-strategy-contract`: implement the constrained parameter/state/
   evidence/market-spec contract plumbing and preserve EMA compatibility. See
   `tasks/T001-generic-strategy-contract.md`.
2. `T002-candle-confirmation-strategy`: implement the explicit candidate,
   registration, provenance, methodology, pip stops, custom state, and focused
   public contract tests. See `tasks/T002-candle-confirmation-strategy.md`.
3. `T003-experiment-and-inspection-proof`: prove configuration, Experiment
   creation/execution, persistence, result/Trade inspection, and schema-driven
   setup UI without candidate branches. See
   `tasks/T003-experiment-and-inspection-proof.md`.
4. `T004-reference-regression-and-validation`: prove original behavior and
   forbidden-seam guards, run quality gates, and prepare independent validation.
   See `tasks/T004-reference-regression-and-validation.md`.

Task files were created after the revised architecture was frozen and the
developer explicitly approved PLAN + ARCHITECTURE.

## Phase and next action

- **Phase:** `READY_FOR_USER`
- **Tasks:** T001 DONE; T002 DONE; T003 DONE; T004 DONE
- **Validation:** PASS (fresh targeted remediation validation; non-blocking baseline
  formatting concern documented)
- **Review:** PASS — targeted review resolved original R-001 through R-004; no
  unresolved CRITICAL or IMPORTANT findings.
- **Concerns:** Pre-existing repository-wide web-formatting baseline and
  unavailable Local Host browser validation remain documented as non-blocking.
- **Next action:** report `READY_FOR_USER`; await explicit merge approval before
  GIT END.

## Developer approval — narrow remediation cycle

The developer approved one manual remediation cycle for R-001 through R-004.
Only the existing owning tasks T001, T002, and T003 may be reopened; no new
T### is authorized. The required sequence is BUILD remediation → fresh targeted
VALIDATE of the four findings and directly affected evidence → fresh targeted
REVIEW of only the original findings, remediation diff, task receipts, and
targeted validation. Full validation is not to be rerun, and any new targeted
review blocker returns directly to the developer.

## Approval-required disposition after two remediation returns

- `R-001` — `PRODUCT BLOCKER`; T001; add generic blocked/non-FLAT opening guard.
- `R-002` — `PRODUCT BLOCKER`; T001; normalize canonical EMA timestamps in the
  compatibility codec and prove active-state round-trip.
- `R-003` — `PRODUCT BLOCKER`; T002; reject future candidate methodology
  timestamps and prove boundary equality.
- `R-004` — `PRODUCT BLOCKER`; T003; commit the deterministic candidate
  PostgreSQL V2 vertical regression test and run it in isolation.

Further work is paused pending explicit developer approval of these smallest
remediations and their targeted validation/re-review sequence.

## Final gate

The approved remediation cycle completed. Fresh targeted VALIDATE and targeted
REVIEW both PASS, and no new blocker was found. This workstream is
`READY_FOR_USER`; do not commit, switch to `main`, merge, or clean up until the
developer explicitly approves GIT END.
