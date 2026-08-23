# READY — Phase 5 Experiment Workflow

mode: feature-branch
root: /Users/vike/Desktop/atlas
path: /Users/vike/Desktop/atlas
branch: feature/phase-5-experiment-workflow
full_sha: 67c24b714f3c128cfefab0581118638194063de8
scope: Implement the approved Phase 5 Experiment workflow: configure and validate immutable StrategyVersion/DatasetSnapshot inputs, create and run Experiments with durable lifecycle state, and inspect completed, zero-Trade, or failed results including metrics, equity/drawdown, Trades, lineage, assumptions, and provenance. Preserve Phase 4 simulation, reproducibility, and no-lookahead semantics; exclude comparison, optimization, exports, workers, WebSockets, and PAPER/LIVE behavior.
status: READY; branch verified at the starting SHA. Working tree has known pre-existing changes: modified dispatch/ACTIVE.md, dispatch/MODEL-LOG.md, dispatch/PLAN.md; untracked .codegraph/ and dispatch/workstreams/phase-5-experiment-workflow/. No files were cleaned, reset, committed, pushed, or merged.

context:
  - source: /Users/vike/Desktop/atlas/AGENTS.md
    destination: /Users/vike/Desktop/atlas/AGENTS.md
    method: current-checkout
    verified: true
  - source: /Users/vike/Desktop/atlas/dispatch/workstreams/phase-5-experiment-workflow/PLAN.md
    destination: /Users/vike/Desktop/atlas/dispatch/workstreams/phase-5-experiment-workflow/PLAN.md
    method: current-checkout
    verified: true
  - source: /Users/vike/Desktop/atlas/dispatch/workstreams/phase-5-experiment-workflow/EXPLORATION.md
    destination: /Users/vike/Desktop/atlas/dispatch/workstreams/phase-5-experiment-workflow/EXPLORATION.md
    method: current-checkout
    verified: true
  - source: /Users/vike/Desktop/atlas/dispatch/workstreams/phase-5-experiment-workflow/ARCHITECTURE.md
    destination: /Users/vike/Desktop/atlas/dispatch/workstreams/phase-5-experiment-workflow/ARCHITECTURE.md
    method: current-checkout
    verified: true

recovery: Writers must use /Users/vike/Desktop/atlas as their cwd on this branch. Preserve the known pre-existing working-tree changes. To abandon this branch without discarding changes, switch to main with `git switch main`; branch deletion, cleanup, commit, push, merge, reset, and clean-up require separate authorization. If interrupted, verify branch and SHA with `git branch --show-current` and `git rev-parse HEAD`, then resume only after confirming the working tree contents.
