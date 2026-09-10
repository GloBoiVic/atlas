# T003 — PAPER supervision and STOP

- **Workstream:** `paper-control-01-trader-activation-supervision`
- **Status:** DONE
- **Role:** BUILD
- **Depends on:** T001; build after T002 to minimize overlapping control-state assumptions

## Owned files

- `frontend/components/paper-status.tsx`
- `frontend/tests/paper_status.test.tsx`
- `frontend/components/overview.tsx` only if compact lifecycle copy requires adjustment
- `frontend/tests/overview.test.tsx` only if Overview changes

## Deliver

- Make `/paper` the current-session supervision surface while preserving current broker exposure first, capability facts, and completed PAPER Trade history.
- Show `No active PAPER session` and an `Activate PAPER` CTA when idle.
- Show current Strategy/version, Risk, lifecycle, operational phase, state/reason when blocked, and last state-change time for an activation.
- Add bounded detail polling at approximately three seconds while the current session is non-terminal.
- Stop polling on `STOPPED`, `BLOCKED`, `FAILED`, or component unmount.
- Do not poll broker-state at runtime-status cadence; preserve explicit broker-state refresh.
- Translate lifecycle and operational phase to approved trader-facing labels, including distinct `REQUESTED`, `STARTING`, and `RUNNING` states.
- Add deliberate `Stop PAPER` confirmation with the exact warning that stopping does not close or modify broker positions or orders.
- Send the existing stop contract with reason `Trader requested stop from Atlas UI.`.
- Preserve activation ID and continue detail polling through durable terminal state after STOP.
- Resolve ambiguous STOP transport outcomes by reading activation detail; surface uncertainty and allow explicit retry when not accepted.
- Do not expose Close Trade, Cancel Order, SL/TP modification, reconciliation, or broker-flatness claims.

## Constraints

- Depends on T001 and builds after T002.
- No backend, Risk, runtime, execution, broker, persistence, migration, or generated-contract changes.
- STOP is runtime-session control only and never broker-position control.
- Do not spawn or start `atlas-runtime`.
- Do not perform broker reads or mutations during automated validation.

## Required checks

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/paper_status.test.tsx \
  frontend/tests/overview.test.tsx
```

Cover idle CTA, lifecycle/phase copy, current Strategy/version/Risk, bounded polling and terminal stop, no broker-state polling, STOP confirmation/warning/body/one-shot behavior, ambiguous STOP readback, no Close Trade control, non-flatness distinction, and preserved completed Trade history.

## Worker Evidence

Record implementation, task-level checks, files changed, and any concerns here when complete. Do not edit this completed receipt after marking the task DONE.

- **Status:** DONE
- **Files changed:** `frontend/components/paper-status.tsx`, `frontend/tests/paper_status.test.tsx`, `frontend/tests/overview.test.tsx`, this task artifact.
- **Checks/evidence:** Required focused Vitest command passed: 2 files, 41 tests. `npm run check:web` passed: 20 files, 143 tests, typecheck, format, and production build. Changed-surface ESLint, Prettier, and `git diff --check` passed.
- **Concerns:** Full lint retains 242 existing unrelated warnings with zero errors. No backend/generated contracts, migrations, runtime process, PAPER activation, OANDA, broker operation, credentials, or capital-capable request was used.
