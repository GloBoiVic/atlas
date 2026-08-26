# TASK-16 Receipt — Experiment frontend decomposition

## Verdict

**BLOCKED — implementation not applied.** This worker was constrained to write
only this receipt artifact. The approved decomposition therefore remains
unimplemented: `frontend/components/experiment-workflow.tsx` is still the
monolithic public entry point, and the approved feature modules and centralized
formatter/chart-support modules do not yet exist.

The repository also remains in the workstream's pre-existing state. No frontend
application file, test, CSS file, backend path, dependency, API contract, or
Git state was changed by this task.

## Required inputs reviewed

- Root `AGENTS.md` and `dispatch/ACTIVE.md`.
- Workstream `PLAN.md`, `ARCHITECTURE.md` including §Approved Refactor Extension,
  `TASK-15-ui-refactor-exploration.md`, `READY.md`, and current `VALIDATION.md`.
- Prior UI/theme receipts TASK-06, TASK-07, TASK-08, and TASK-14.
- Experiment and Experiment Results feature contracts.
- Design guidance: `design.md`, `visual-guide.md`, `ui-tokens.md`, and the
  approved Experiments list/detail/run screenshots.
- `frontend/app/globals.css` and the current workflow source via CodeGraph.

## Current boundary assessment

The current source still contains list, setup/load status, lifecycle status,
completed results, metric presentation, equity/drawdown charts, price analysis,
Trades, trade detail, lineage, and local formatting in
`frontend/components/experiment-workflow.tsx`. No approved decomposition seams
were changed, so compatibility exports, props, requests, polling, guards,
routes, links, chart lifecycle, accessibility behavior, and result semantics
were not put at risk.

The following approved work remains outstanding:

- Extract cohesive list, setup, load-status, lifecycle-status, results,
  metric-summary, equity-charts, Trades, trade-detail, price-chart, and lineage
  modules while retaining the four public workflow exports.
- Add shared `frontend/lib/experiment-formatters.ts` without client metric
  recalculation and reuse `frontend/lib/time.ts` for time semantics.
- Add one runtime Atlas chart-role map and complete source-level Atlas theme
  migration without hard-coded chart colors or a second palette.
- Add or preserve focused decomposition/formatter/support regressions.

## Validation performed against unchanged code

| Command | Result |
|---|---|
| `npm run test:web` | **23 passed** across 9 files |
| `npm run typecheck:web` | **Passed** |
| `npm run lint:web` | **Passed** |
| `npm run build:web` | **Passed** |
| `npx prettier --check frontend/components/experiment-workflow.tsx frontend/app/globals.css` | **Passed** |

These are baseline results, not evidence that TASK-16 acceptance criteria are
met. No focused new formatter/support or decomposition test was added.

## Local Host and visual evidence

The Local Host browser discovery reported **“Local Host is not running.”** As a
result, post-refactor comparison of `/experiments`, `/experiments/new`, a
completed Experiment result, and Trade detail could not be performed. No new
screenshots, keyboard traversal evidence, chart text-alternative evidence,
console inspection, or failed-network inspection is claimed. A completed result
and trade-detail route were consequently unavailable for honest verification.

The three approved screenshots and written design guides were reviewed as
references only; prior TASK-14 evidence is not substituted for post-refactor
evidence.

## Remaining limitations / next action

An authorized frontend builder must apply the approved decomposition in the
listed frontend files, then run focused regressions plus the complete frontend
test, typecheck, lint, build, and per-file Prettier gates. Afterward, Local Host
must be started and all four routes verified, with console and failed-network
diagnostics recorded. If a split produces uncertain lifecycle or request
behavior, restore the prior boundary rather than adding duplicate requests or
client-side facts.

No Git command was run.
