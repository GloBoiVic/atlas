# T001 - Compact Trader State Presentation

- **Workstream:** `ui-02-trader-shell-overview-product-cleanup`
- **Status:** `DONE_WITH_CONCERNS`
- **Role:** `BUILD`
- **Branch:** `solo/ui-02-trader-shell-overview-product-cleanup`
- **Base:** `9c31774f499c2e21a34b7f80fbfa190bf3be1fdb`

## Outcome

Implement the approved compact broker and runtime presentation without changing API request semantics or full PAPER evidence behavior.

## Scope

Primary files:

- `frontend/components/paper-broker-state.tsx`
- `frontend/components/paper-status.tsx`
- `frontend/tests/paper_broker_state.test.tsx`
- `frontend/tests/paper_status.test.tsx`

Required behavior:

- Make compact broker mode materially trader-facing.
- Prioritize instrument, state, direction, absolute quantity, and unrealized P/L.
- Make unrealized P/L visually stronger than entry, opened time, and provider metadata while preserving semantic colors and exact API decimal strings.
- Hide provider Trade ID in compact Overview mode only; preserve full PAPER evidence.
- Render every open Trade independently, including multiple Trades.
- Keep successful empty inventory distinct from broker failure, with concise states and explicit GET-only Refresh.
- Render active and no-active runtime states concisely in compact mode without exposing `PAPER_ACTIVATION_NOT_ACTIVE`.
- Preserve the full PAPER page's detailed broker/runtime truth boundary.

## Constraints

- Frontend-only; no backend files, API contracts, generated clients, or broker behavior.
- No automatic polling or mutation controls.
- Do not broaden into shell or Overview hierarchy work assigned to T002.

## Checks

Run the focused broker/runtime tests from the PLAN and record the exact result in this task file. Do not mark this task done without implementation, tests, and a concise completion receipt.

## Worker Evidence

- BUILD execution completed.

## Immutable BUILD Receipt

- **Status:** `DONE_WITH_CONCERNS`
- **Files changed:**
  - `frontend/components/paper-broker-state.tsx`
  - `frontend/components/paper-status.tsx`
  - `frontend/tests/paper_broker_state.test.tsx`
  - `frontend/tests/paper_status.test.tsx`
  - `dispatch/workstreams/ui-02-trader-shell-overview-product-cleanup/tasks/T001-compact-trader-state-presentation.md`
- **Checks/evidence:**
  - `npm run test:web -- tests/paper_broker_state.test.tsx tests/paper_status.test.tsx` - passed, 25 tests.
  - `npm run format:check:web` - passed.
  - `npm run lint:web` - passed with 242 existing warnings and no errors.
  - `npm run typecheck:web` - passed.
  - `npm run build:web` - passed.
  - `git diff --check` - passed.
  - Broker evidence covers LONG, SHORT, multiple Trades, empty inventory, unavailable state, positive/negative/neutral P/L, exact displayed entry values, GET-only Refresh, and no mutation controls.
  - Runtime evidence covers active/phase, no active runtime without `PAPER_ACTIVATION_NOT_ACTIVE`, concise unavailable/retry, and preserved full PAPER detail behavior.
  - The PLAN focused command was run: `32` tests passed and `5` failed in the pending T002-owned `tests/overview.test.tsx`; failures assert old compact labels/states (`PAPER broker state`, `Loading PAPER broker state...`, `No open broker trades.`, and `PAPER_ACTIVATION_NOT_ACTIVE`).
- **Findings/concerns:**
  - The five PLAN-command failures are expected until T002 updates Overview tests for the new compact broker/runtime contract. No T002 files were changed.
  - No backend files, generated clients, API request semantics, automatic polling, or mutation controls were changed.
