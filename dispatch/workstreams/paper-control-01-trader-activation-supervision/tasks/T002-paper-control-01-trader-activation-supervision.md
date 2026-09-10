# T002 — Explicit PAPER activation workflow

- **Workstream:** `paper-control-01-trader-activation-supervision`
- **Status:** DONE
- **Role:** BUILD
- **Depends on:** T001

## Owned files

- `frontend/app/paper/activate/page.tsx`
- `frontend/components/paper-activation.tsx`
- `frontend/tests/paper_activation.test.tsx`

## Deliver

- Add Strategy and immutable StrategyVersion selection using existing catalog/detail APIs.
- Add the existing parameter-schema editor with version defaults and frontend validation.
- Add blank-by-default Risk-per-trade percentage entry and exact reviewed Risk display.
- Add capability, active-session, and supported broker-state preflight reads.
- Block unavailable capability, an existing active session, visible open broker Trades, and unavailable broker-state uncertainty according to the approved PLAN.
- Add frozen review with Strategy/version, methodology, parameters, Risk, provider/environment/instrument, and one stable activation request UUID.
- Invalidate review, typed confirmation, and request identity when authority-bearing configuration changes.
- Require exact `ACTIVATE PAPER` UI confirmation and send `ACTIVATE_PAPER`.
- Disable duplicate submission while in flight; perform no automatic retry.
- Resolve ambiguous activation transport outcomes through read-only active-status lookup, reusing the same request ID for explicit retry.
- Navigate to `/paper` after the returned durable activation is accepted.

## Constraints

- Depends on T001 and must not implement STOP.
- No backend, Risk, runtime, execution, broker, persistence, migration, or generated-contract changes.
- Do not spawn or start `atlas-runtime`.
- Do not perform broker reads or mutations during automated validation.
- Do not expose credentials or the full provider account ID in primary activation UI.

## Required checks

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/paper_activation.test.tsx
```

Cover no default Risk, Strategy/version loading and unavailable versions, parameter defaults/validation, capability/active-session/broker preflight, frozen review and invalidation, typed confirmation, one-shot submission, stable UUID retry, ambiguous POST readback, conflict, success navigation, and no credential/account-ID presentation.

## Worker Evidence

Record implementation, task-level checks, files changed, and any concerns here when complete. Do not edit this completed receipt after marking the task DONE.

- **Status:** DONE
- **Files changed:** `frontend/app/paper/activate/page.tsx`, `frontend/components/paper-activation.tsx`, `frontend/tests/paper_activation.test.tsx`, this task artifact.
- **Checks/evidence:** Required focused Vitest command passed: 1 file, 12 tests. `npm run typecheck:web`, changed-surface ESLint, Prettier check, and `git diff --check` passed.
- **Concerns:** None. No backend/generated contracts, runtime process, PAPER activation, OANDA, broker mutation, credential, or provider account-ID presentation was used or changed.
