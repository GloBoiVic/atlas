# Foundation Freeze 01 — Reference Strategy Correctness

## Status and authority

This is an audit/design artifact, not an implementation. The user-provided
**EMA Sweep Confirmation Break** contract is authoritative. The current
`context/features/reference-strategy.md` and the older
`ema_sweep_engulfing` implementation are reference material only where they do
not contradict that contract.

The smallest correction is to preserve the existing public Strategy seam and
make the current `ema_sweep_confirmation_break` implementation, its persisted
state, and its pending-trigger handoff agree on one deterministic completed-bar
state machine. No Experiment, Risk, execution, historical-data, PAPER/LIVE,
or UI architecture changes are proposed.

## Authoritative public seam

The only Strategy entry point is:

```text
Strategy.evaluate(
    StrategyContext,
    StrategyParameters,
    StrategyState,
) -> StrategyEvaluation(decision, next_state)
```

The Strategy consumes only canonical, completed analytical M15 MID bars in
strict completion order. It does not submit Orders, inspect broker/account
state, size risk, resolve final protection, or infer fills/exits. The caller
owns persistence of `next_state` and must provide the same state after a
restart. `last_evaluated_bar_end` is the consumed-bar frontier: every bar with
an end time at or before it is already consumed and must never be reconsidered.
An evaluation with no new bars may advance no setup state and must be
idempotent.

Exposure disallowed or a non-FLAT Position returns `NO_ACTION`, clears setup
continuation to SEARCHING, and advances only the duplicate-detection frontier.
It must not select a reference or emit an OPEN. This is a safety gate, not a
window-expiry event.

## Exact state machine

The persisted conceptual phases are `SEARCHING`, `REFERENCE_IDENTIFIED`, and
`ARMED`; `OPEN_*` is a transient decision. There is at most one opening setup
while FLAT: no replacement by a later/opposite reference, no competing setup,
and no pyramiding. The state must carry only deterministic continuation data:

- direction and fixed reference high/low/time;
- sweep/confirmation time (the immediate confirmation bar);
- the count/frontier of received completed analytical bars after the OPEN
  decision (W1–W5 pending-trigger window);
- for ARMED, confirmation time and trigger price;
- `last_evaluated_bar_end`.

The existing legacy `AWAITING_CONFIRMATION`, `window_bars`, and `watch_bars`
shape must not remain semantically ambiguous. A narrow schema adjustment or a
versioned migration is permitted only if needed to represent the above
invariants without aliases. If retained for compatibility, old fields must be
quarantined and mapped deterministically, never used to create a second
confirmation window.

### Reference and immediate confirmation

While SEARCHING, calculate the canonical EMA/ATR from completed analytical
bars. A qualifying reference is bearish and above EMA for LONG, or bullish and
below EMA for SHORT. The trend predicate applies only at reference selection;
later EMA movement does not invalidate or replace the fixed setup.

After reference selection, process each subsequent received completed
analytical bar exactly once. The confirmation opportunity is **immediate-only**:

- LONG: the immediate next bar must be bullish (`close > open`) and sweep the
  reference low strictly (`low < reference_low`).
- SHORT: the immediate next bar must be bearish (`close < open`) and sweep the
  reference high strictly (`high > reference_high`).

Do not add `close > reference_high` to LONG confirmation or
`close < reference_low` to SHORT confirmation. Equality is not a sweep. Doji,
direction-without-sweep, and sweep-without-direction all fail. A failed
immediate confirmation resets to SEARCHING after consuming that bar; it does
not defer confirmation to a later bar and does not reuse that bar as a new
reference.

The immediate next bar is the bar immediately after reference selection. It is
the single sweep/confirmation bar; there is no delayed sweep state and no
second confirmation opportunity.

### Five-bar analytical window

The OPEN decision starts an exact pending-trigger window of the next five
*received* completed analytical bars after the confirmation decision: W1, W2,
W3, W4, W5. The reference and confirmation bars are not pending-window bars.
A received analytical bar advances this pending count even when no executable
M1 observation is available; missing intervals, weekends, sessions, and
elapsed wall-clock time do not advance it and must not fabricate bars. W5 is
the final eligible bar for the pending trigger. If no trigger has filled by
W5, the pending proposal expires and the armed state resets; W5 is consumed
and cannot be reconsidered as a new reference.

An OPEN decision transitions its returned state to the one-armed setup state
required by pending executable entry, not to a second setup. The Strategy emits
no further opening decision while that setup is pending. The five-bar counter
must advance from analytical frames that follow the decision, including frames
for which execution data is sparse. If the pending entry expires or is filled,
the caller clears the pending setup; a later Strategy evaluation can search
only when the supplied Position is FLAT.

## Decision, trigger, and ownership split

An OPEN decision contains direction, decision time, proposed stop, target
methodology (`R_MULTIPLE`, parameterized by target R), and immutable Strategy
evidence. For a LONG trigger use `max(reference_high, confirmation_high)` on
ASK; for a SHORT trigger use `min(reference_low, confirmation_low)` on BID.
Trigger detection is executable-price behavior, not analytical MID behavior:
the runner accepts the first eligible post-decision M1 observation whose ASK
(LONG) or BID (SHORT) reaches the trigger, including gap-through at executable
open. The pending consumer must retain raw observation/provenance and apply
slippage exactly once through the existing execution adapter.

The pending entry window is exactly five subsequent completed analytical bars,
and must be carried from the Strategy decision to the runner as a bar-based
frontier/eligibility contract. `expiry_time = confirmation_end + 75 minutes`
must not be authoritative: it incorrectly expires across data/session gaps.
The existing persistence columns may remain for compatibility, but a
wall-clock value must be null, diagnostic-only, or explicitly derived rather
than used to decide eligibility. The exact representation (bar sequence ID,
analytical end-time frontier, or equivalent persisted snapshot position) is an
unresolved implementation decision and requires approval; whichever is chosen
must be restart-safe and must count only received analytical bars.

Strategy owns the proposed stop geometry, trigger, target methodology, rationale,
and analytical evidence. Risk owns final stop/target from the actual executable
entry/fill, quantity, approvals, and rejection evidence. Execution owns Order
submission/fill evidence, executable BID/ASK provenance, and slippage. Position
and Trade evidence derives from Fills and owns terminal exit evidence. No result
reader or frontend may rediscover EMA/sweep/confirmation patterns from candles.

## Evidence contract

`SetupFacts` and the persisted `evidence`/`landmarks` payload must explain the
Strategy decision without claiming fill truth. At minimum, authoritative
Strategy evidence contains:

- reference and the immediate sweep/confirmation bar,
  and their complete candle facts and timestamps;
- direction and trend relation, including the numeric EMA used at reference
  selection;
- ATR value and proposed-stop methodology/inputs (not final protection);
- trigger price and ASK/BID basis;
- explicit entry-window semantics: W1–W5, reference excluded, received
  completed analytical bars only, no wall-clock expiry;
- the Strategy implementation/contract version sufficient to interpret the
  evidence.

Landmarks should be stable typed kinds (reference, sweep/confirmation as
applicable, and decision/trigger), with analytical timestamps/prices. Entry,
final stop, final target, fill, and exit landmarks remain separately sourced
from Risk/execution/Fill. `ExperimentRunner._create_intent` may serialize the
Strategy payload, but must not calculate missing pattern facts. The existing
`ExperimentResultReadService` should project persisted evidence and keep its
separate Risk/fill/exit projections; it must not reconstruct corrected facts
from mutable defaults.

## Exact seams expected to change

1. `backend/strategies/ema_sweep_confirmation_break.py`: immediate-only
   transition, strict sweep/direction rules, five-slot counting, consumed-bar
   frontier, one-armed invariant, reset behavior, trigger/stop calculation, and
   complete evidence.
2. `backend/domain/strategy.py`: only if typed evidence or state validation,
   JSON schema, and compatibility/versioning require it. Keep the public
   `evaluate` seam and immutable dataclasses.
3. `backend/experiments/runner.py`: replace wall-clock pending expiry with the
   approved analytical-bar eligibility handoff; preserve ASK/BID trigger
   behavior and existing Risk/execution path; serialize new Strategy evidence.
4. `backend/experiments/results.py`: only expose the persisted evidence fields
   if the current projection does not already pass them through. No pattern
   detection belongs here.

Likely test seams are
`backend/tests/strategies/test_ema_sweep_confirmation_break.py`,
`backend/tests/integration/test_golden_flows.py`, and, only for projection
shape, `backend/tests/experiments/test_price_analysis_results.py`.

## Compatibility and versioning

`StrategyVersion` remains immutable. Changing decision semantics or serialized
state/evidence interpretation requires a new implementation/version and a new
source fingerprint; completed Experiments retain their original immutable
inputs/results and must not be silently reinterpreted. A state schema change
requires an explicit `state_schema_version` transition and deterministic
read/upgrade policy. Do not make v1 old engulfing results appear to be the new
contract. Registry/docs/test names referring to `EMA Sweep Engulfing` are stale
unless they explicitly target the legacy implementation; the production
registry currently exposes `ema_sweep_confirmation_break.v1` and should be
updated only as part of the approved versioning decision.

## Required public-behavior regression tests

Through `Strategy.evaluate` (not private helpers), add deterministic tests for:

- valid LONG and SHORT references and immediate confirmations;
- bearish LONG rejection, bullish SHORT rejection, doji rejection, strict
  inequality, sweep-without-direction, and direction-without-sweep;
- no opposite-reference close requirement;
- immediate-next-bar-only behavior and failed-bar reset;
- exact pending-trigger W1–W5 accounting after confirmation, W5
  boundary/reset, W5 not reused, and restart from active state;
- missing intervals/weekend/session gaps not consuming slots or expiring by
  wall clock;
- duplicate evaluation not re-consuming a bar; competing/opposite setups
  ignored while armed; reset clears every stale field;
- trigger max/min and ASK/BID basis, post-decision executable trigger behavior,
  gap-through, and no trigger before decision time;
- proposed stop, ATR/EMA evidence, entry-window evidence, and target
  methodology;
- golden-flow persistence agreement, actual-fill-derived final target/stop, and
  separate fill/exit evidence through existing Risk/Fill seams;
- StrategyVersion/state serialization and explicit legacy-version quarantine.

Valid examples include a bearish-above-EMA LONG reference followed by one
bullish strict-low-sweep confirmation, then an ASK trigger reached by the first
eligible executable observation in pending W1; and the inverse bullish-below-
EMA SHORT reference, bearish strict-high-sweep confirmation, and BID trigger
reached in pending W5. Boundary examples include a trigger reached exactly at
the executable trigger price, a gap-through open, and a no-trigger decision
where the fifth received post-confirmation analytical bar expires the proposal
despite an arbitrarily long wall-clock gap.

Invalid examples include a partial candle, duplicate/out-of-order bars,
equality at the sweep boundary, confirmation after a failed immediate bar,
W6 entry for an expired setup, a wall-clock-only expiry across a gap, a second
armed setup, and a Strategy payload containing final fill-derived target data.

## Approval gate

This architecture is approved for implementation by the developer on
2026-08-26, with these binding decisions:

- The persisted ARMED Strategy state and completed-analytical-bar count are the
  single authority for pending-trigger expiry. The runner must not maintain a
  second eligibility clock or use `expiry_time` authoritatively.
- Confirmation arms with zero consumed watch bars. Execution observations for
  each of W1–W5 are processed before that bar's closing analytical frontier is
  consumed. W5 is fully eligible; after it closes without a fill, Strategy
  returns to SEARCHING and the runner clears the proposal. W6 is ineligible.
  Missing intervals, weekends, and session gaps do not consume slots.
- ATR14 is calculated from completed analytical history including the
  sweep-confirmation candle, at confirmation close. The proposed stop is
  `confirmation.low - (0.5 × ATR14)` for LONG and
  `confirmation.high + (0.5 × ATR14)` for SHORT.
- Atlas is undeployed and pre-freeze results using the known-wrong semantics
  may be invalid/disposable. No compatibility layer, state migration, or
  permanent wrong-v1 implementation is required solely to preserve them.

Implementation may now modify only the listed seams and must preserve all
stated Atlas invariants.
