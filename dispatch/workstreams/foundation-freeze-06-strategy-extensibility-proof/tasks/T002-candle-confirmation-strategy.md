# T002 — Candle Confirmation Break Strategy

## Assignment

- **Status:** `DONE` — developer-approved narrow remediation for R-003
  completed.
- **Owner:** BUILD
- **Workstream:** `foundation-freeze-06-strategy-extensibility-proof`
- **Branch:** `solo/foundation-freeze-06-strategy-extensibility-proof`
- **Dependencies:** T001 DONE

Implement the real second Strategy frozen in `ARCHITECTURE.md`: Candle
Confirmation Break v1. It must use the generic contract from T001 and the same
production registry/provenance seams as EMA.

## Required scope

- Add `strategy_key=candle_confirmation_break` and
  `implementation_key=candle_confirmation_break.v1`, explicit production
  registration, stable source archive/fingerprint, catalog/version metadata,
  requirements, capabilities, and state/evidence schema.
- Own exactly `confirmation_bars` integer `1..3` default `2`,
  `stop_buffer_pips` finite decimal `1..100` default `20`, and `target_r`
  finite decimal `0.5..5.0` default `1.5`; reject EMA keys and all malformed
  payloads through the shared declaration plus Strategy parser.
- Implement one-bar warm-up, strict bullish/bearish break rules, consecutive
  same-direction confirmation, direction restart, no-break/doji/equality clear,
  immediate opening decisions, and no pending handoff.
- Implement the bounded candidate payload exactly as frozen, deterministic
  envelope round-trip/continuation, and safe clearing when exposure is blocked
  or Position is non-FLAT.
- Derive absolute LONG/SHORT stops from signal candle facts and resolver-supplied
  `pip_size`; emit existing R-multiple target; never size, use broker/I/O, or
  assume signal-close execution.
- Emit bounded candidate evidence with the frozen schema and fields; it must
  survive the generic persistence seam without SetupFacts fabrication.
- Add focused candidate contract, boundary, determinism, strictness, stop,
  evidence, and registration/provenance tests.

## Frozen constraints

No EMA/ATR/Phase/SetupFacts fields, no PRICE_TRIGGERED handoff, no candidate
branch in ExperimentRunner/Risk/execution, no new market capability, and no
durable checkpoint persistence. Read the candidate and state/evidence sections
of `ARCHITECTURE.md` before editing.

## Completion receipt

Before returning, update this file with `DONE`, files changed, checks/evidence,
and findings/concerns. Do not edit PLAN, ACTIVE, ARCHITECTURE, VALIDATION, or
REVIEW.

## Completion receipt

- **Status:** `DONE`
- **Files changed:**
  - `backend/strategies/candle_confirmation_break.py`
  - `backend/strategies/production.py`
  - `backend/tests/strategies/test_candle_confirmation_break.py`
  - `backend/tests/strategies/test_ema_sweep_confirmation_break.py`
  - `backend/tests/strategies/test_legacy_strategy_isolation.py`
  - `backend/tests/experiments/test_configuration.py`
- **Checks/evidence:** Candidate contract tests passed (`7 passed`); focused
  Strategy/configuration regression tests passed (`21 passed`); broader
  non-integration backend suite passed (`331 passed, 6 skipped`). Ruff,
  candidate Pyright, compileall, and `git diff --check` passed. Tests cover
  explicit registration/provenance, exact three-parameter schema and bounds,
  strict breaks, confirmation/restart/clear transitions, deterministic state
  round-trip, immediate LONG/SHORT decisions, pip-based absolute stops,
  generic evidence, and exposure safety.
- **Findings/concerns:** No candidate-specific branch was added to the shared
  runner, Risk, or execution path; no checkpoint persistence or migration was
  added. Existing EMA tests that assumed the production registry contained only
  EMA were updated to select EMA by its explicit identity while preserving its
  assertions. Pre-existing unrelated working-tree changes and untracked files
  were preserved.

## Remediation packet — VALIDATE return 1 (F-001, F-005)

- **Classification:** `PRODUCT` as recorded by validation.
- **Exact issues:** Direct typed `CandleConfirmationParameters` values bypass
  the registered schema bounds because `evaluate_strategy` accepts a typed
  parameter set without generic schema validation/reparse. Focused strict
  Pyright also reports the candidate's narrowed `evaluate` signature and
  restored JSON typing errors.
- **Owning task:** `T002-candle-confirmation-strategy`, with the public seam
  correction coordinated through T001 (F-001); T002 owns candidate typing in
  F-005.
- **Affected files/seams:** `backend/strategies/contract.py` public evaluation
  path and `backend/strategies/candle_confirmation_break.py` typed parameters/
  evaluate signature.
- **Required fix:** Every public evaluation path must require the validated
  payload or schema-validate/reparse typed values generically before evaluation;
  do not duplicate candidate/EMA bounds in shared code. Make the candidate
  conform to the public Protocol with typed guards, preserving runtime rejection
  and avoiding `Any`.
- **Invalidated checks:** Direct invalid typed-parameter acceptance, public
  conformance, and dependent candidate tests.
- **Smallest revalidation:** direct typed-invalid/typed-valid contract tests,
  candidate boundaries/invalids, focused Strategy/configuration suite, focused
  Pyright, and guards.

## Remediation completion receipt — F-001 / F-005

- **Status:** `DONE`
- **Files changed:**
  - `backend/strategies/contract.py`
  - `backend/strategies/candle_confirmation_break.py`
  - `backend/tests/strategies/test_contract.py`
  - `backend/tests/strategies/test_candle_confirmation_break.py`
- **Exact evidence:** `evaluate_strategy` now applies the registered
  `ParameterSchema` generically to every typed `StrategyParameterSet` before
  evaluation; it does not name EMA or candidate fields and does not duplicate
  bounds. The candidate's public `evaluate` seam uses the same declaration
  without `Any`, while retaining its Protocol-compatible broad parameter type
  and typed guard. Direct valid typed parameters open normally; direct invalid
  `confirmation_bars`, `stop_buffer_pips`, and `target_r` values fail closed.
- **Checks:** Focused Strategy/candidate/configuration tests passed (`31
  passed`). Focused Ruff, strict Pyright for `contract.py` and the candidate,
  compileall, and `git diff --check` all passed.
- **Findings/concerns:** No EMA source was changed by this remediation; no
  architecture, financial semantics, persistence, branch history, or other role
  artifact was changed. Existing
  generic empty-schema contract fixtures now use an empty typed parameter set,
  so exact-schema validation remains enforced rather than bypassed.

## Review return 2 disposition — automatic cycling stopped

- **Classification:** `PRODUCT BLOCKER`
- **Exact issue:** Candidate `candidate_started_at` is only checked for UTC and
  can be later than the restored Atlas frontier/evaluation time, allowing a
  future methodology state to produce an opening decision (R-003).
- **Owning task:** `T002-candle-confirmation-strategy`.
- **Affected files/seams:** `backend/strategies/candle_confirmation_break.py`
  state decoding/evaluation and its public contract tests.
- **Smallest next action after approval:** reject future candidate timestamps
  relative to both restored frontier and evaluation frontier, add empty/non-empty
  future and equality-boundary tests, then rerun candidate contract/state,
  focused suite, and guards.

## Remediation completion receipt — R-003

- **Status:** `DONE`
- **Files changed:**
  - `backend/strategies/candle_confirmation_break.py` (existing remediation
    preserved and verified)
  - `backend/tests/strategies/test_candle_confirmation_break.py`
- **Exact evidence:** `_state_values` now normalizes and validates
  `candidate_started_at` as UTC, then rejects it when later than either the
  restored Atlas frontier or the supplied evaluation frontier. Public contract
  tests cover future timestamps with no prior frontier and with a prior frontier,
  each in empty and non-empty contexts. Malformed, naive, and non-UTC timestamps
  are rejected in all four context combinations. Equality at the restored
  frontier and equality at the evaluation frontier are accepted and continue to
  an opening decision. Rejection occurs before candidate clearing or decision
  generation; no clamp, reset, or repair path was added.
- **Checks:**
  `uv run pytest backend/tests/strategies/test_candle_confirmation_break.py
  backend/tests/domain/test_primitives.py
  backend/tests/strategies/test_contract.py -q` — `72 passed`;
  the same suite plus `backend/tests/test_foundation_freeze_guards.py` — `77
  passed`; focused Ruff passed; focused Pyright passed with `0 errors, 0
  warnings, 0 informations`; focused `compileall` passed; tracked and
  untracked candidate-file `git diff --check` passed.
- **Findings/concerns:** No candidate-specific shared runner branch, EMA
  changes, architecture changes, or persistence/checkpoint changes were made.
