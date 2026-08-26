# TASK-04 — Frontend Workstation Builder

- **Task:** Update the existing Experiment workflow, route wrappers, frontend API
  types/client, and directly related frontend tests/e2e coverage for auditable
  Strategy/Experiment results.
- **Outcome:** COMPLETE (e2e environment blocked)

## Implementation

- Added EUR/USD five-decimal price formatting, signed USD P&L, consistent `R`
  multiple `x` formatting, percentage display, and `—` unavailable metrics.
- Rendered server-supplied generic landmarks with accessible text labels and
  legend entries for EMA, setup facts, entry/exit, protection, and trigger.
  The browser does not infer patterns.
- Added bounded chart price-scale margins and preserved strict chronological
  de-duplication for readable Lightweight Charts rendering.
- Added Trade setup/proposal evidence (policy, trigger, status, expiry) and
  retained the existing selected-Trade detail route and lineage disclosure.
- Extended frontend API schema/client types for evidence, landmarks, proposal
  diagnostics, setup facts, Experiment payloads, and Trade detail payloads.

## Changed files

- `dispatch/workstreams/strategy-experiment-workstation/TASK-04.md` — this
  receipt only.
- `frontend/components/experiment-workflow.tsx` — result formatting, generic
  landmark rendering, chart bounds, and Trade proposal evidence.
- `frontend/lib/api-client.ts` — typed Experiment and Trade detail responses.
- `frontend/lib/api.generated.ts` — response types for evidence, landmarks, and
  proposal diagnostics.
- `frontend/tests/experiment_results.test.tsx` — updated assertions for signed/
  human-readable metric presentation.

## Validation receipts

- `npm run test:web -- --run` — **passed**: 9 files, 23 tests.
- `npm run typecheck:web` — **passed**.
- `npm run lint:web` — **passed**.
- `npx prettier --write` on changed frontend/report files — **passed**.
- `npx vitest run --config frontend/vitest.config.ts frontend/tests/price_analysis.test.tsx` — **passed**: 7 tests (targeted rerun after one transient full-suite failure).
- `npm run test:e2e -- tests/e2e/experiment-workflow.spec.ts` — **blocked before
  test execution**: port 8000 is already used; Playwright requires a fresh
  server under the current configuration.

## Concerns / next action

- A rerun of `npm run test:web -- --run` passed cleanly: 9 files, 23 tests.
- `npm run format:check:web` remains globally red because of pre-existing
  formatting warnings in 11 unrelated files; changed files were formatted.
- The existing API process on port 8000 was not stopped or modified.
- Existing unowned backend/task-context modifications were left untouched.

## Follow-up receipt — validation blocker, attempt 2 of 2

- **Outcome:** DONE.
- Replaced obsolete completed-result `EMA Sweep Engulfing` labels with the
  API-supplied StrategyVersion identity, including result assumptions, the
  Experiment list, and Trade detail header. Unknown identity falls back to the
  neutral `StrategyVersion` label; no identity is inferred in the browser.
- Updated `frontend/tests/experiment_results.test.tsx` with an
  `EMA Sweep Confirmation Break v1` API fixture and assertion that the obsolete
  label is absent.
- `npm run test:web -- --run` — **PASS: 9 files, 23 tests**.
- `npx vitest run --config frontend/vitest.config.ts frontend/tests/experiment_results.test.tsx` — **PASS: 5 tests**.
- `npm run typecheck:web` — **PASS**.
- `npm run lint:web` — **PASS**.
- Existing routes, generic evidence/landmark rendering, and no-pattern-detection
  behavior were preserved. No backend, context, or dispatch control artifact
  was edited.
