# Implementation Blueprint — Strategy / Experiment Workstation

## Outcome

Replace the current EMA Sweep Engulfing reference slice with **EMA Sweep
Confirmation Break**, and make the smallest generic Strategy/Experiment
boundary needed to run it deterministically and explain every trade. The
result is a historical Experiment workstation for EUR/USD, OANDA Practice
data, USD, M15 analysis, and M1 execution. PAPER and LIVE order lifecycles,
new providers, timeframe configuration, and plugin/DSL infrastructure are out
of scope.

## Agreed language

- **StrategyVersion**: immutable executable methodology and provenance; parameter
  values are an Experiment/Deployment snapshot, not a new version.
- **Proposal**: the Strategy's pure request for an exposure change. It contains
  direction, stop proposal, target methodology, entry policy, expiry policy,
  setup facts, and deterministic rationale. Risk still owns quantity and
  approval; the runner owns observation and execution.
- **Immediate entry**: fill at the first eligible post-decision executable
  observation.
- **Price-triggered entry**: wait for a directional executable-side trigger in
  post-decision observations; it expires at an explicit M1/M15 frontier and is
  never silently carried beyond it.
- **Setup facts**: immutable, machine-readable reference/sweep/confirmation
  candle facts emitted by Strategy at decision time. They are evidence for
  persistence and chart markers, not UI pattern detection.
- **Experiment**: one immutable historical replay using canonical
  TradeIntent/RiskDecision/Order/Fill/Position/Trade facts.

## Status and confidence

- **Confirmed (high confidence)**: scope and acceptance criteria in `PLAN.md`;
  Strategy purity, completed-bar/no-lookahead rules, M15/M1 split, BID/ASK
  execution, actual-fill target geometry, one Position/no pyramiding, immutable
  Experiment evidence, and adverse-first ambiguity are governed by the supplied
  architecture and feature documents.
- **Confirmed (high confidence)**: the existing V2 runner is snapshot-only,
  evaluates native M15 once per frontier, and currently assumes an entry
  observation rather than a reusable pending proposal. Existing persistence
  has JSON rationale, `target_multiple`, and no entry-policy columns.
- **Confirmed (high confidence)**: “Confirmation Break” has no W1–W5 formation
  window. After selecting a bearish/bullish reference, only the **very next**
  completed M15 candle may be its valid directional sweep/close confirmation;
  otherwise the setup resets immediately. Only a valid next-candle confirmation
  arms a price-triggered proposal, watched for five subsequent completed M15
  bars.
- **Deferred**: PAPER invocation, live watch/restart behavior, MANUAL_CLOSE and
  RISK_EXIT in Experiments, partial exits, trailing protection, M5/M1 Strategy
  evaluation, multi-timeframe context, and generalized broker/provider support.

## Decisions

### 1. Strategy contract and proposal shape

Extend the existing immutable domain decision rather than introducing a second
Signal model. Keep `Strategy.evaluate(context, parameters, state)` pure and
environment-independent. The opening decision must carry an immutable proposal
with:

1. `direction`, `stop`, and `TargetProposal` (R-multiple remains the only
   initial target methodology);
2. `entry_policy`: `IMMEDIATE` or `PRICE_TRIGGERED`;
3. for the latter, a positive Decimal `trigger_price`, a directional executable
   price basis (`ASK` for LONG, `BID` for SHORT), and an explicit expiry
   frontier (UTC timestamp, plus a bar-count/policy version for audit);
4. immutable structured strategy evidence/landmarks, including reference,
   sweep, and confirmation timestamps and OHLC values, plus any strategy-owned
   trend/ATR/stop inputs required to explain the setup;
5. deterministic rationale suitable for JSON persistence.

The public type must reject malformed combinations: immediate proposals have no
trigger/expiry; triggered proposals have all trigger fields; LONG/SHORT sides
match action; all prices are finite Decimals; expiry is after decision time.
Existing callers that construct immediate decisions remain compatible through
an explicit default. Do not make Strategy know simulation resolution or account
state.

The EMA Sweep Confirmation Break implementation uses its declared analytical
M15 MID bars for EMA, ATR, candle classification, and evidence. Trend is checked
only when selecting the reference. A bearish reference above EMA qualifies
LONG; a bullish reference below EMA qualifies SHORT. The **very next** received
completed M15 candle must be a strict valid sweep with the required directional
close; otherwise the reference resets immediately. There is no formation
window, same-candle reconsideration, later-candle confirmation, or W1–W5
expiry. Once valid sweep-confirmation arms the proposal, exactly one armed
opening setup exists. No new reference may be identified, replaced, queued,
merged, or taken from the opposite direction while armed. The armed proposal is
watched for five subsequent received completed M15 bars; on fill or expiry the
state returns to SEARCHING, and armed candles are never retroactively
reconsidered. Position non-FLAT or exposure disallowed clears pending setup and
cannot create an opening proposal.

Trigger calculation is exact and mirrored: LONG
`max(reference_high, confirmation_high)`; SHORT
`min(reference_low, confirmation_low)`. The reference and confirmation values
are the persisted setup facts, and the resulting trigger is immutable for the
armed proposal. “Break” is evaluated on executable prices, not MID analysis:
LONG watches ASK and triggers when the complete post-decision M1 ASK range
reaches or exceeds the LONG trigger; SHORT watches BID and triggers when the
complete post-decision M1 BID range reaches or falls below the SHORT trigger.
The first eligible post-decision M1 observation that touches/breaks the level
is the trigger observation and supplies the executable quote for Risk and
entry. The signal M15 bar and its already-consumed data are never reused.

Stop is 0.5 ATR beyond confirmation low/high. Target is `1.7R`, but must be
resolved only after the actual executable Fill: LONG `entry + 1.7*(entry-stop)`;
SHORT `entry - 1.7*(stop-entry)`. Strategy may carry methodology, never a
fabricated entry price or quantity.

### 2. Analytical data requirements

Add declarative metadata to `StrategyDefinition` for only the generic analytical
requirements: instrument, resolution, price component, completed-only semantics,
and required historical context. Do not add OANDA, EMA, ATR, or OHLC as generic
requirement fields, and do not create a general query language. OHLC is supplied
by the declared canonical bar data; EMA and ATR remain Strategy-owned
parameters/implementation details. OANDA belongs to historical-data acquisition
and Experiment configuration, not the Strategy boundary. Keep the current
fixed Experiment validation scope separately: EUR/USD, OANDA, M15 analysis, and
M1 execution.

The analytical series is the immutable snapshot membership at the declared
instrument, resolution, and price component. Requirements contain only:
instrument, resolution, price component, completed-only semantics, and required
historical context. They do not contain OANDA/provider semantics. EMA/ATR
periods and indicator details remain Strategy parameters/implementation
details. Execution observations remain sparse complete M1 BID+ASK.
Missing analytical or execution data is a durable validation/gap result, never
fabricated or forward-filled data. The Strategy receives only bars whose
`end_time <= evaluation_time`.

### 3. Generic runner watch semantics

Refactor the V2 runner into generic proposal handling:

1. process protection observations strictly before each M15 decision frontier;
2. evaluate once with the completed M15 bar and persist the returned Strategy
   state and TradeIntent/proposal facts;
3. for `IMMEDIATE`, choose the first complete M1 observation strictly after the
   decision frontier;
4. for `PRICE_TRIGGERED`, inspect complete post-decision M1 observations in
   chronological order until the proposal's **armed trigger-watch expiry**.
   For this Strategy the proposal is armed on sweep-confirmation and its
   expiry is the fifth subsequent received completed M15 bar. LONG triggers when
   ASK breaks
   `max(reference_high, confirmation_high)`; SHORT triggers when BID low
   reaches/falls below `min(reference_low, confirmation_low)`. The trigger
   observation is the first eligible observation and is never the signal M1/M15
   data. For LONG, if ASK open is already greater than the trigger, fill at
   executable ASK open; otherwise an ASK high touch fills at the trigger. Mirror
   this for SHORT with BID: if BID open is below the trigger, fill at executable
   BID open; otherwise a BID low touch fills at the trigger. Apply configured
   adverse slippage after this executable price selection.
5. run PRE_SUBMISSION Risk against the actual executable quote at that
   observation, resolve the target from the actual fill price, then submit the
   canonical simulated entry and protection orders;
6. if no observation reaches the trigger before expiry, persist an expired/no-
   fill diagnostic and continue M15 evaluation; never submit a stale intent.

The proposal watcher must be a generic policy interpreter, not an
`if ema_sweep...` branch. At most one pending opening proposal may exist for
the one Position invariant. A filled proposal cancels/clears pending state;
an expired or Risk-rejected proposal is terminal and cannot be retried from a
later price observation. A later Strategy decision may create a new proposal
only while FLAT and only according to its returned state.

The post-decision boundary is strict: observations at the decision frontier
are excluded. Use the observation's executable side for trigger, entry,
protection, and valuation; use MID only for analysis. Preserve source bar IDs,
price basis, trigger/expiry timestamps, and actual entry in the lineage.

### 4. Persistence and API compatibility

Extend the canonical `TradeIntent` persistence representation, not the domain
vocabulary. Persist proposal policy and trigger/expiry data in a clean model
field (versioned JSON or explicit columns), along with structured evidence and
landmarks. Do not derive facts later by rerunning Strategy or by UI candle
inspection. Add constraints for valid action/policy combinations and UTC/finite
values. This development database is disposable: do not add compatibility
machinery solely to read obsolete rows or implementations; reset/rebuild when
that is cleaner.

Persist the actual target only in the approved PRE_SUBMISSION RiskDecision and
protection Order lineage after the fill context is known. Do not overwrite
immutable Strategy rationale or mutate completed Experiment facts. If a schema
migration is needed, prefer a clean model migration and documented development
reset/rebuild over legacy adapters. Do not weaken immutability of results
produced by the new model.

API response schemas should expose a stable optional `entryPolicy` object,
`setupFacts`, and proposal status/expiry diagnostics in result/trade detail.
Keep existing endpoint paths, pagination, status gating, and camel-case
conventions. Unknown or incomplete lineage returns the existing explicit
`INCOMPLETE_RESULT`; FAILED Experiments never expose partial results as
trustworthy. Do not expose raw UUIDs as ordinary labels.

### 5. Results, formatting, and chart readability

Result payloads must format authoritative financial values as decimal strings
and retain timestamps as UTC instants. UI formatters should display prices with
instrument-appropriate precision, P&L with `$` and sign, R with a consistent
`x` suffix, and explicitly show unavailable metrics as `—`, not zero. Preserve
the existing metric definitions and assumptions/provenance hierarchy.

Price analysis returns analytical M15 candles, strategy-declared indicator
series, and a generic structured-evidence/landmark collection. The EMA Sweep
Confirmation Break supplies the seven requested display categories: **EMA**,
**reference**, **sweep**, **confirmation**, **entry**, **stop/target**, and
**exit**. The price-trigger level is included in the entry evidence/marker (and
is not a new Strategy-specific renderer category). Marker timestamps/prices
come from persisted evidence and execution lineage; the generic renderer does
not detect patterns. The server selects a bounded context window around all
landmarks; truncation is explicit. Use distinct subtle marker styles, a legend
or accessible labels, and avoid stacking labels over candles; the chart must
remain readable at normal workstation width and on narrow scrolling layouts.
Keep Lightweight Charts and current routes.

### 6. OANDA one-month validation

After automated validation, run one real one-month historical Experiment using
the OANDA Practice historical source, EUR/USD, exact UTC 15-minute-aligned
bounds, and the required warm-up preceding the trading start. The durable flow
must be `load_missing → immutable snapshot → native M15 derivation → coverage
validation → create → run`; verify the snapshot records MID/BID/ASK provenance,
fingerprint, and no blocking gaps. Record the Experiment's human-readable
label, period, StrategyVersion/source fingerprint, snapshot fingerprint,
status, trade count, quality/ambiguity disclosures, and a browser capture of
list, run/status, completed results, and at least one Trade detail chart.

This is a validation operation, not a fixture or application-code dependency.
Credentials stay in environment configuration and browser evidence must not
contain tokens. If OANDA is unavailable, report the durable failure and do not
claim acceptance; fixture tests cannot substitute for the real-data gate.

## Constraints and risks

- **No lookahead / duplicate bars**: contract validation and runner tests must
  reject future, incomplete, or repeated frontiers; state frontier remains
  persisted across restart.
- **Two distinct phases, one armed window**: there is no W1–W5 formation
  window. The very next completed M15 candle either validates the reference via
  sweep/directional close or resets it immediately. A valid confirmation starts
  exactly one armed setup with a five-subsequent-completed-M15-bar watch.
  Missing intervals do not consume bars. While armed, no setup identification,
  replacement, queueing, merging, opposite setup, or expiry restart is allowed;
  fill/expiry returns directly to SEARCHING and armed candles are not reused.
- **Trigger-level integrity**: the armed trigger must be calculated as LONG
  `max(reference_high, confirmation_high)` or SHORT
  `min(reference_low, confirmation_low)` from immutable setup facts. Never
  substitute confirmation high/low alone or a requested/fill price.
- **Trigger crossing in OHLC**: M1 BID/ASK high/low indicates touch but not tick
  sequence. For entry, use executable open when LONG ASK opens beyond / SHORT
  BID opens below the trigger; otherwise fill a first eligible high/low touch at
  the trigger, then apply existing adverse slippage. Protection retains the
  existing adverse-first policy and records ambiguity.
- **Actual-fill target**: never calculate target from confirmation close,
  trigger price, or requested price. If Risk rejects geometry after movement,
  persist rejection and no exposure.
- **Unknown/incomplete state**: malformed setup facts, missing lineage,
  missing executable quote, persistence failure, or ambiguous terminal
  protection fails closed, preserves diagnostics, and cannot be represented as
  a successful trade.
- **Disposable development persistence**: this workstation uses a clean,
  rebuildable development database. Prefer a clean model and remove obsolete
  compatibility machinery for old rows/implementations rather than preserving
  V1 migration/read paths solely for legacy data. Reset/rebuild the disposable
  database when that is the simpler correct transition; completed results in the
  rebuilt model remain immutable thereafter.
- **Concurrency**: preserve current synchronous lifecycle and row locking;
  no queues, Redis, workers, or supervisor abstractions.
- **Security**: no credentials in logs/results/browser payloads; sanitize
  failure details and preserve external IDs only where lineage requires them.

## Ordered implementation

Builders work sequentially in the assigned cwd `/Users/vike/Desktop/atlas` and
must touch only their listed groups. They must not edit context docs, this
blueprint, PLAN, ACTIVE, or EXPLORATION.

1. **Contract and Strategy builder** — owns
   `backend/domain/strategy.py`, `backend/strategies/contract.py`, the new
   EMA Sweep Confirmation Break implementation and its registration/production
   wiring, plus `backend/tests/strategies/*` and relevant domain tests.
    Implement proposal policy, analytical requirements, setup facts, exact
    LONG/SHORT state machine with immediate-next-candle validation followed by
    one armed-watch counter,
   `max(reference_high, confirmation_high)` / `min(reference_low,
   confirmation_low)` trigger calculation, serialization, validation, and
   backward-compatible immediate defaults. Do not change runner or persistence
   in this step.
2. **Runner/persistence builder** — owns
   `backend/experiments/runner.py`, simulation/clock helpers only if required,
   `backend/persistence/models.py`, experiment repository/migrations, and
   `backend/tests/experiments/*`, execution tests, and persistence tests.
    Implement generic watch/expiry using the proposal's armed expiry (with no
    formation-window coupling), executable ASK/BID crossing and open-versus-
    touch gap-through rules, actual-fill target resolution, durable intent
    facts/diagnostics, constraints, and all failure paths. Do not add
   Strategy-name branches.
3. **API/results builder** — owns
   `backend/experiments/results.py`, `backend/api/schemas.py`,
   `backend/api/experiments.py`, result/API tests, and only directly related
   backend read-service tests. Preserve endpoint compatibility and explicit
   incomplete/failed behavior.
4. **Frontend workstation builder** — owns the existing Experiment workflow
   component, experiment route wrappers, frontend API types/client, and
   directly related frontend tests/e2e tests. Render durable status, assumptions,
   formatted values, and server-supplied landmark markers; do not detect
   patterns in the browser or add new chart libraries.
5. **Integration/validation tester** — owns only test/support fixtures and
   validation evidence locations explicitly assigned by the orchestrator.
   Run the complete suite, browser accessibility/request/console checks, and
   the real one-month OANDA procedure. It may not alter application behavior;
   failures return to the owning sequential builder.

## Validation

- Contract: deterministic identical-input output; strict completed-bar and
  no-future enforcement; state serialization/restart; warm-up; reference
  followed by the very next completed M15 candle only, immediate reset on an
  invalid candle, and no later reconsideration; exactly one armed setup; five
  subsequent completed M15 trigger-watch bars; fill/expiry to SEARCHING with no
  armed-candle reuse; exact LONG `max(reference_high, confirmation_high)` and
  SHORT `min(reference_low, confirmation_low)` triggers; EMA reversal behavior;
  position/exposure gating; LONG/SHORT mirrored stop and setup facts; immediate
  and triggered proposal validation without EMA/ATR requirements in the generic
  contract.
- Runner: exactly-once M15 evaluation; signal frontier excluded from watch;
  correct ASK/BID trigger and entry sides; exact max/min trigger levels;
  invalid-next-candle reset; one armed proposal with no replacement/queue/
  merge/opposite setup; five-bar armed expiry with gaps; LONG open-above versus
  high-touch-at-trigger and mirrored SHORT open-below versus low-touch-at-
  trigger; slippage after executable selection; Risk PRE_FLIGHT and
  PRE_SUBMISSION rejection; target from actual fill; protection after Fill only;
  stop/target, gap-through, adverse-first ambiguity, end close, zero trades,
  deterministic replay, and terminal sparse-data failure.
- Persistence/API: clean-model constraints; disposable database reset/rebuild;
  rerun immutability; setup facts, generic evidence/landmarks, proposal policy,
  and lineage survive retrieval; pagination/status gates; sanitized failures;
  FAILED and incomplete results never masquerade as valid output.
- Results/UI: all seven requested display categories render from server data,
  including trigger data in entry evidence; chart bounds/readability and
  accessible labels; decimal price/P&L/R formatting;
  unavailable metrics as `—`; immutable assumptions/provenance; no raw UUIDs,
  console errors, failed unexpected requests, or pattern-detection code in UI.
- Acceptance gate: automated tests pass, then a real one-month OANDA Practice
  Experiment completes with evidence of deterministic snapshot provenance,
  post-decision M1 BID/ASK execution, auditable setup markers, and result
  inspection. No PAPER lifecycle is implemented or claimed.
- **Extensibility gate**: do not generalize beyond the stated Strategy boundary
  and the two entry policies until a second concrete Strategy requirement
  cannot be represented by them; that requirement must first be captured as a
  failing contract/runner test, then justify the smallest new generic field or
  policy. No Strategy-name branch is an acceptable extension.

## Remaining generic-engine coupling

The runner still necessarily couples to the canonical Strategy boundary,
RiskService, simulation clock, M1 observation shape, and Experiment persistence;
that is intended domain coupling, not Strategy-specific coupling. The initial
engine remains constrained to EUR/USD/OANDA/M15/M1 and to the current native-M15
 snapshot schema. Analytical requirements remain only instrument, resolution,
 price component, completed-only semantics, and required historical context;
 provider semantics and EMA/ATR details stay outside the generic contract.
 There is no legacy V1 compatibility path solely for obsolete rows or
 implementations in the disposable development database. New execution must
 use one generic proposal interpreter (IMMEDIATE or PRICE_TRIGGERED) and one
 canonical Trade/Fill accounting path.
