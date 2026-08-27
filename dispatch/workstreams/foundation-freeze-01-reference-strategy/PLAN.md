# Foundation Freeze 01 — Reference Strategy Correctness

## Status

`APPROVED — implementation authorized with the developer's five-bar semantic frontier, ATR timing, and pre-freeze versioning decisions.`

Branch: `solo/foundation-freeze-01-reference-strategy`
Base SHA: `aef7187433a6f2c3366220378f5e5dcf133714ff`
Current phase: `REVIEW PASSED — full suite verified; awaiting explicit developer merge approval`

## Authority and scope

The user-provided EMA Sweep Confirmation Break contract is authoritative. This is a Critical workstream because it changes Strategy decision semantics, temporal expiry, and evidence used to explain trading decisions.

In scope:

- The authoritative `ema_sweep_confirmation_break` Strategy state machine.
- Its public Strategy decision/evidence seam.
- The narrow Strategy-to-pending-trigger handoff required to make the five completed-bar window authoritative.
- Persistence of authoritative Strategy evidence/landmarks, without moving execution/Risk ownership of fill, final stop, target, or exit evidence.
- Regression coverage through public Strategy behavior and the existing persisted golden-flow seam.
- Stale reference-strategy docs/tests/comments that encode the old engulfing/multi-bar semantics, only where needed to remove contradiction.

Out of scope:

- Experiment architecture, Risk architecture, execution model, historical-data architecture, PAPER/LIVE, and unrelated UI.
- Generic Strategy engines, new broker abstractions, or frontend pattern discovery.
- Implementation before approval.

## Current implementation audit

### Authoritative Strategy

`backend/strategies/ema_sweep_confirmation_break.py` currently:

- Correctly qualifies bearish-above-EMA100 LONG references and bullish-below-EMA100 SHORT references while searching.
- Correctly requires strict sweep inequalities and candle direction for the immediate next bar.
- Incorrectly adds LONG `close > reference_high` and SHORT `close < reference_low` to confirmation, rejecting valid confirmations that need only sweep plus direction.
- Produces `SetupFacts` with the reference and immediate confirmation duplicated as sweep/confirmation, which is structurally compatible with the immediate-confirmation contract but needs authoritative naming/evidence verification.
- Calculates trigger as `max(reference_high, confirmation_high)` for LONG and `min(reference_low, confirmation_low)` for SHORT.
- Calculates the proposed stop from confirmation low/high and ATR, and emits `TargetProposal(R_MULTIPLE)` so Risk can resolve 1.7R from executable fill.
- Emits ASK/BID trigger basis and `expiry_bars=5`, but also emits a wall-clock `expiry_time=confirmation_end + 75 minutes`.
- Transitions to `ARMED` after OPEN output; subsequent Strategy bars only count `watch_bars` and reset at the fifth bar. This is the correct conceptual armed-state shape, but the boundary/order and pending-trigger consumer must be made consistent with exactly W1–W5.

### Public seam and state

The public seam is `Strategy.evaluate(StrategyContext, StrategyParameters, StrategyState) -> StrategyEvaluation`. `StrategyState` is serialized and validated in `backend/domain/strategy.py`; it currently retains legacy `AWAITING_CONFIRMATION`, `window_bars`, and `watch_bars` fields to support older Strategy implementations. The corrected Strategy must not use a multi-bar confirmation window or reconsider consumed bars. Any state schema change must preserve immutable restart behavior and be explicitly justified in the architecture artifact.

### Pending trigger / Risk / Fill interaction

`backend/experiments/runner.py` creates and persists a TradeIntent on the Strategy OPEN decision, then independently watches sparse executable BID/ASK observations. LONG uses ASK and SHORT uses BID; gap-through uses executable open, otherwise the high/low reaches the trigger. Risk sizes and resolves target from the executable quote/fill path, and fill accounting owns final execution evidence. The runner currently expires pending entries by `decision.expiry_time`, which is wall-clock based and therefore can consume the window across weekend/session gaps. This is the narrow interaction that must be corrected without changing Risk or execution responsibilities.

### Persisted Strategy evidence

`ExperimentRunner._create_intent` persists `setup_facts`, `evidence`, and three candle landmarks from `StrategyDecision.setup_facts`. Current `SetupFacts` persists reference/sweep/confirmation candle facts, trend relation, ATR, proposed stop price, and trigger price, but no numeric EMA, explicit entry-window semantics, or proposed-stop methodology field. Rationale currently includes trigger/stop strings only. `ExperimentResultReadService` reads persisted evidence/landmarks and separately reads approved Risk/fill/exit data; frontend result code must remain a consumer, not a pattern detector.

## Mismatches to correct

1. LONG/SHORT confirmation incorrectly requires closing beyond the opposite reference extreme.
2. The implementation currently exposes a 75-minute wall-clock expiry and the runner enforces it; expiry must be exactly five subsequent completed analytical M15 bars, with gaps not consuming slots.
3. The armed-state processing must have an unambiguous W1–W5 boundary: trigger observations are eligible only during the five subsequent analytical-bar window; expiry/reset must not allow W5 or any consumed candle to be reconsidered.
4. Strategy evidence does not explicitly persist the EMA value, entry-window meaning, or proposed stop methodology required by the evidence contract.
5. Existing reference-strategy documentation and older `EMA Sweep Engulfing` tests/implementation encode delayed/multi-bar confirmation and engulfing requirements that conflict with this authoritative Strategy definition; they must be classified as legacy or updated only where they describe the authoritative implementation.
6. Current direct Strategy coverage is only a production-registry exposure test; required behavior is not covered at the authoritative public seam.

## Proposed smallest implementation shape (pending architecture review)

1. Keep the existing public `Strategy.evaluate` seam and immutable `StrategyState` model unless the architecture artifact proves a narrow state schema adjustment is necessary.
2. Make confirmation strictly immediate-next-bar: LONG bullish + low below reference low; SHORT bearish + high above reference high; any failure resets to SEARCHING and consumes that bar.
3. Preserve one armed setup and the existing trigger basis/stop/target proposal fields. Ensure the next state and bar frontier enforce one setup, no replacement, no opposite setup, and no duplicate consumption.
4. Represent the five-bar analytical window authoritatively at the Strategy/pending-trigger handoff. Keep executable trigger detection on BID/ASK and actual-fill target resolution in existing Risk/execution seams.
5. Extend only the Strategy evidence payload needed to explain EMA, trigger, entry window, and proposed stop methodology; leave actual fill/final protection/target/exit evidence to Risk/execution.
6. Replace stale behavior tests with public-seam regression tests and add/adjust one persisted evidence/golden-flow assertion set if required.

## Expected files and seams

### Likely application files

- `backend/strategies/ema_sweep_confirmation_break.py` — authoritative decision/state machine.
- `backend/domain/strategy.py` — only if Strategy evidence/state contract needs a typed field or schema correction.
- `backend/experiments/runner.py` — only the pending-trigger expiry/window handoff and Strategy evidence serialization; no Risk/execution redesign.
- `backend/experiments/results.py` — only if its existing persisted-evidence projection must expose the corrected fields without rediscovering the pattern.

### Likely tests

- `backend/tests/strategies/test_ema_sweep_confirmation_break.py` — expand public Strategy seam coverage.
- `backend/tests/integration/test_golden_flows.py` — verify persisted Strategy evidence and actual-fill-derived target where the existing database seam supports it.
- `backend/tests/experiments/test_price_analysis_results.py` — only if projection assertions need corrected evidence fields.
- Relevant domain/runner tests only if the narrow contract change requires them.

### Likely stale context/docs

- `context/features/reference-strategy.md` — currently describes `EMA Sweep Engulfing`, a five-bar confirmation window, and confirmation beyond reference extremes; must be reconciled with the frozen contract.
- `backend/strategies/ema_sweep_engulfing.py` and its tests — legacy implementation; do not alter unless registry/docs/tests prove it is being treated as authoritative for this Strategy. The production registry currently exposes only `ema_sweep_confirmation_break`.
- Any comments or test names found during implementation that call the authoritative Strategy “engulfing” or describe delayed confirmation.

## Required regression evidence

At the public `Strategy.evaluate` seam, tests must prove: valid LONG and SHORT; bearish LONG rejection; bullish SHORT rejection; doji rejection; sweep-without-direction and direction-without-sweep rejection; immediate-next-bar-only confirmation; no LONG close-above-reference-high or SHORT close-below-reference-low requirement; exact W1–W5 trigger window; weekend/session gaps not consuming slots; competing setups ignored while armed; trigger calculation; stop proposal/evidence; actual-fill target resolution through the existing Risk/Fill seam; persisted evidence agreement; and reset clearing stale state.

Validation must include targeted Strategy tests, relevant domain/runner/evidence tests, the existing golden-flow tests when database credentials are available, and a repository-wide stale-assumption search. No browser validation is expected unless a required evidence projection changes browser-visible UI.

### Approved architecture decisions

- The persisted ARMED Strategy state and completed-analytical-bar count are the single authority for the five-bar pending-trigger window. No independent runner expiry clock may decide eligibility.
- Confirmation arms with zero consumed watch bars; execution observations for W1–W5 are eligible before that bar's analytical frontier is consumed. W5 is fully eligible, then expiry returns Strategy to SEARCHING and clears the pending proposal. W6 is never eligible. Gaps do not consume slots.
- Proposed stops use ATR14 at confirmation close, including the confirmation candle: LONG `confirmation.low - (0.5 × ATR14)` and SHORT `confirmation.high + (0.5 × ATR14)`.
- Pre-freeze incorrect behavior is not preserved as a permanent legacy version. Invalid pre-freeze Experiments/StrategyVersion data may be disposable; no compatibility layer or migration is required solely for it.

## Approval gate

Developer approval received on 2026-08-26. Source, application, and test implementation may proceed on the recorded branch and base SHA.
