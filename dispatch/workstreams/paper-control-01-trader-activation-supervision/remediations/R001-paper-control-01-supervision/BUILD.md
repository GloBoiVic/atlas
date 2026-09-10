# R001 — PAPER Control 01 supervision remediation

- **Remediation ID:** `R001`
- **Workstream:** `paper-control-01-trader-activation-supervision`
- **Status:** DONE
- **Role:** BUILD
- **Origin finding:** `dispatch/workstreams/paper-control-01-trader-activation-supervision/VALIDATION.md` findings F-001 and F-002
- **Finding severity:** Important
- **Related original tasks:** T003

## Approved requirement or invariant violated

- Acceptance criterion 27 and T003 require recurring approximately three-second activation-detail polling for every non-terminal session until terminal state or component unmount.
- Acceptance criterion 35 and the T003 lifecycle requirements require `BLOCKED` and `FAILED` to remain visible without generic success styling.

## Exact remediation outcome

- Make activation-detail polling recur at approximately three seconds after every successful non-terminal detail response, including unchanged lifecycle responses, and stop at `STOPPED`, `BLOCKED`, `FAILED`, or unmount.
- Render compact Overview lifecycle states with non-success styling for `BLOCKED` and `FAILED` while preserving approved trader-facing labels and observation-only Overview behavior.
- Add focused regression coverage for unchanged non-terminal polling and blocked/failed compact status styling.

## Affected implementation seams

- `frontend/components/paper-status.tsx`
- `frontend/tests/paper_status.test.tsx`
- `frontend/tests/overview.test.tsx`

## Explicit out-of-scope items

- No changes to T001/T002 behavior, API client contracts, generated types, backend, Risk, runtime, execution, broker semantics, persistence, migrations, or routes.
- No new capital authority, automatic activation/retry, broker mutation, Close Trade, reconciliation, runtime process spawning, `atlas-runtime` startup, OANDA/provider operation, or credentials.
- Do not expand the remediation to F-003 Minor UI guideline concerns.

## Regression evidence required

- T003 focused PAPER status and Overview tests, including repeated unchanged non-terminal detail responses, terminal stop, broker-state cadence separation, and compact `BLOCKED`/`FAILED` styling.
- Changed-surface typecheck, formatting, lint, and `git diff --check`.

## Worker Evidence

The R001 BUILD worker records the bounded implementation, regression checks, files changed, and concerns here when complete. This packet and its completed receipt are immutable after completion.

- **Status:** DONE
- **Implementation:** Activation-detail polling now advances a dedicated poll attempt after each successful non-terminal response, including unchanged lifecycle responses, while existing terminal-state and unmount cleanup remains in place. Compact `BLOCKED` and `FAILED` lifecycle states now use `status-danger` rather than `status-success`.
- **Files changed:** `frontend/components/paper-status.tsx`, `frontend/tests/paper_status.test.tsx`, `frontend/tests/overview.test.tsx`, `dispatch/workstreams/paper-control-01-trader-activation-supervision/remediations/R001-paper-control-01-supervision/BUILD.md`
- **Checks/evidence:** `npx vitest run --config frontend/vitest.config.ts frontend/tests/paper_status.test.tsx frontend/tests/overview.test.tsx` passed: 2 files, 44 tests. `npm run typecheck:web` passed. `npx prettier --check frontend/components/paper-status.tsx frontend/tests/paper_status.test.tsx frontend/tests/overview.test.tsx dispatch/workstreams/paper-control-01-trader-activation-supervision/remediations/R001-paper-control-01-supervision/BUILD.md` passed. `npx eslint frontend/components/paper-status.tsx frontend/tests/paper_status.test.tsx frontend/tests/overview.test.tsx` passed. `git diff --check` passed.
- **Concerns:** F-003 was intentionally not addressed. No backend, generated contract, API route, Risk, runtime, execution, broker, persistence, migration, credentialed/provider, or capital-capable operation was performed; `atlas-runtime` was not started and PAPER was not activated.
