# Worktrees READY

- **Mode:** `feature-branch`
- **Workstream root:** `/Users/vike/Desktop/atlas/dispatch/workstreams/strategy-experiment-workstation/`
- **Assigned checkout:** `/Users/vike/Desktop/atlas`
- **Branch:** `feature/strategy-experiment-workstation`
- **Starting/current full SHA after branch creation:** `5cb72a74bcc946e54e7c6e265cfa24f87352832a`
- **Status:** `READY`

## Scope

Replace the reference Strategy with EMA Sweep Confirmation Break (LONG/SHORT),
generalize only the Strategy/Experiment boundary needed for private state,
analytical requirements, rationale, and immediate/expiring price-triggered
proposals, and make Experiment results auditable in the UI. PAPER is out of
scope.

## Context manifest

All required files were readable from the assigned checkout:

### Committed baseline (at the SHA above)

- `AGENTS.md`
- `context/index.md`
- `context/architecture/strategy-contract.md`
- `context/architecture/domain-model.md`
- `context/architecture/runtime-model.md`
- `context/architecture/market-data-model.md`
- `context/features/reference-strategy.md`
- `context/features/experiments.md`
- `context/features/experiment-results.md`
- `context/design/design.md`

### Uncommitted task context (present and readable in the assigned checkout)

- `dispatch/workstreams/strategy-experiment-workstation/PLAN.md`
- `dispatch/workstreams/strategy-experiment-workstation/EXPLORATION.md`
- `dispatch/workstreams/strategy-experiment-workstation/ARCHITECTURE.md`
- `context/architecture/strategy-setup.png`

The committed/uncommitted classification is based on the observed checkout at
the recorded SHA. Planning files and the supplied setup image are task context,
not part of the committed baseline.

## Cleanup and recovery

- **Cleanup:** No automatic cleanup. The workstream/orchestrator owner is
  responsible for manual cleanup at workstream close; preserve task-context
  files until then.
- **Recovery:** Re-check out `feature/strategy-experiment-workstation` at
  `5cb72a74bcc946e54e7c6e265cfa24f87352832a`, preserve or restore the listed
  uncommitted task context, and rerun this READY gate before any writer starts.

No Git mutations were performed by this gate. No application code was written.
