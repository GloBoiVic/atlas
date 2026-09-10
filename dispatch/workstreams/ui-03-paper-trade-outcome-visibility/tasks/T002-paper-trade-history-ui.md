# T002 - Trader-Facing PAPER Trade History UI

- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `664b19c902656b37271158c55faf7f7d19cfa840`
- **Dependency:** T001 DONE

## Outcome

Implement the compact Overview and fuller PAPER-page completed Trade history presentation from the approved PLAN, using the T001 read contract.

## Scope

Primary files:

- `frontend/lib/api-client.ts`
- `frontend/components/paper-trade-history.tsx`
- `frontend/components/overview.tsx`
- `frontend/components/paper-status.tsx`
- `frontend/tests/api_client.test.ts`
- `frontend/tests/overview.test.tsx`
- `frontend/tests/paper_status.test.tsx`

Required behavior:

- Add the typed completed-PAPER-Trades read and bounded Overview/PAPER page requests.
- Render compact recent outcomes on Overview and fuller bounded history on the PAPER page.
- Show trader-facing entry, exit, protection, economics, close time, direction, and Strategy facts.
- Show exact exit labels only when the API proves an exact cause; render unavailable otherwise, including multiple-close cases.
- Support loading, empty, and non-destructive error states.
- Preserve existing current PAPER broker/runtime sections and read-only semantics.
- Keep raw UUIDs, provider IDs, raw reasons, and internal state vocabulary out of primary UI.

## Constraints

- Frontend presentation and client only; do not modify backend/API or generated contract files.
- No activation controls, reconciliation controls, broker actions, automatic polling, or new design system.
- Do not broaden beyond the approved Overview and PAPER page history surfaces.

## Checks

Run the focused frontend tests and checks from the approved PLAN. Record exact results in this task file before marking the task done.

## Worker Evidence

- BUILD assignment created after explicit approval and GIT START.
- Work begins after T001 is DONE.

## BUILD Receipt

- **Status:** `DONE`
- **Implemented:** Added the typed `GET /api/v1/paper/trades` client read, reusable compact/full completed-trade history presentation, Overview recent history with `limit=3`, and PAPER completed history with `limit=20`. Existing current broker/runtime sections and read-only behavior remain intact.
- **Evidence:** Entry/exit, direction, Strategy/version, protection, separate realized P/L and financing, non-zero dividend adjustment, close times in the selected display timezone, and bounded loading/empty/error states are rendered. Exact exit labels are mapped only for API-proved causes; missing, unresolved, multi-close, and unknown causes remain `Exit cause unavailable`. Raw history/provider identifiers and internal state vocabulary are not rendered by the new history UI.
- **Files:** `frontend/lib/api-client.ts`, `frontend/components/paper-trade-history.tsx`, `frontend/components/overview.tsx`, `frontend/components/paper-status.tsx`, `frontend/tests/api_client.test.ts`, `frontend/tests/overview.test.tsx`, `frontend/tests/paper_status.test.tsx`.
- **Focused tests:** `npx vitest run --config frontend/vitest.config.ts frontend/tests/api_client.test.ts frontend/tests/overview.test.tsx frontend/tests/paper_status.test.tsx` -> `29 passed`.
- **Web checks:** `npm run check:web` -> passed: Prettier, ESLint with existing warnings only, TypeScript, `94` frontend tests, and production build. `git diff --check` passed.
- **Findings/concerns:** None for T002. No broker/provider reads, polling, runtime startup, activation, mutation, or out-of-scope files were added.
