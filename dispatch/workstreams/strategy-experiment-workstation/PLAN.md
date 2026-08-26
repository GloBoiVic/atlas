# Plan — Strategy Experiment Workstation

## Classification
Architecture + Feature

## Scope
Replace the reference Strategy with EMA Sweep Confirmation Break (LONG/SHORT),
generalize the Strategy/Experiment boundary only as required for reusable private
state, analytical requirements, rationale, and immediate or expiring price-triggered
proposals, and make Experiment results auditable in the UI. Do not implement PAPER.

## Status
Closed — approved by user; implementation completed; validation and final R1 review passed; terminal closure recorded 2026-08-25.

## Acceptance criteria
- Exact LONG and mirrored SHORT rules, 5 M15-bar expiry, one position, M1 BID/ASK execution.
- Stop is 0.5 ATR beyond confirmation low/high; target is 1.7R from actual fill.
- Strategy owns parameters/state/data requirements/setup facts/proposal; not Risk or fills.
- Experiment runner watches price-triggered proposals without Strategy-specific branches.
- Results format prices/P&L/metrics clearly and visually identifies all requested trade landmarks.
- A real one-month OANDA Experiment is run and browser evidence is captured; no PAPER lifecycle.

## Ordered phases
1. Explore current contracts, runner, persistence, result API/UI, OANDA path, tests, and risks.
2. Architect authoritative blueprint; pause for explicit human confirmation.
3. Worktrees READY receipt for dedicated feature branch.
4. Sequential implementation: contract/strategy; runner/persistence; results UX; tests and integration.
5. Validation: automated tests, real one-month OANDA Experiment, browser/accessibility/request/console checks.
6. R1 review, bounded fixes, R2 review if elevated findings.

## Assignments
- Explore: solo-worker, owns `EXPLORATION.md`.
- Architect: solo-worker, owns `ARCHITECTURE.md`.
- Worktrees: solo-worker, owns `READY.md`.
- Builders/tester/reviewers: assigned after approval; sequential writers only.

## Constraints
- Do not edit context architecture docs or build a DSL/plugin framework.
- Do not add PAPER or LIVE behavior.
- Do not dispatch implementation-capable work before explicit confirmation.
- No Git mutation is authorized by this plan.
