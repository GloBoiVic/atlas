# T003 — Align Reference Strategy Wording

Status: `DONE`

## Assignment

Correct only the remaining IMPORTANT contradiction identified by validation: `context/features/reference-strategy.md` currently requires a confirmation close through the reference extreme, while the current EMA Sweep Confirmation Break v2 implementation treats the next completed bar's direction-specific strict sweep as the immediate decision condition and carries the price-triggered ARMED state for later sparse M1 execution observations.

Make the smallest documentation-only correction. Do not modify application code, tests, migrations, North Star, dispatch history, or out-of-scope docs. Do not commit.

## Required checks

- Re-read the current Strategy implementation before editing.
- Run `git diff --check` and the required terminology/contradiction searches.
- Verify scope and preserve all prior fixes.

## Completion receipt

### Changed paths

- `context/features/reference-strategy.md`
- `dispatch/workstreams/context-authority-cleanup-pass-1/tasks/T003-context-authority-strategy-wording.md`

### Checks / Evidence

- Re-read current `backend/strategies/ema_sweep_confirmation_break.py`; confirmed the next completed bar uses a strict direction-specific sweep and immediately emits the price-triggered decision, then ARMED tracks W1–W5.
- Removed unsupported close-through-reference-extreme requirements from long/short wording and acceptance examples.
- Required terminology search confirms strict sweep, same-bar decision, ARMED, W1–W5, and sparse native M1 wording remain present.
- Contradiction search finds no obsolete close-through requirement in `context/features/reference-strategy.md`.
- `git diff --check` passes.
- No commit made.

### Findings / Concerns

- None. Prior fixes and pending-trigger behavior were preserved.
