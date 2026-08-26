# TASK-14 Receipt — Atlas theme UI audit

## Outcome

**PARTIAL / HANDOFF REQUIRED.** The shared UI and chart palette were audited and
the direct non-Atlas colors found in shared controls and Lightweight Charts were
replaced with Atlas semantic tokens. No behavior, backend, Strategy, PAPER/LIVE,
dependency, or navigation changes were made.

The audit also confirmed that `experiment-workflow.tsx` still contains legacy
Tailwind utility names in its JSX. Those classes are currently covered by the
existing `globals.css` compatibility layer and therefore render with Atlas
colors, but they were not all migrated to source-level `atlas-*` classes in this
bounded pass. This is an explicit remaining P1 cleanup rather than an invented
token or architecture decision.

## Changed files

- `frontend/app/globals.css` — added the chart-local `--atlas-color-sweep`
  alias and its Tailwind theme alias; existing core Atlas values were retained.
- `frontend/components/experiment-workflow.tsx` — replaced direct chart hex
  values for canvas, axes, grid, equity/drawdown, candles, trade markers,
  landmarks, and levels with Atlas CSS variable references.
- `frontend/components/app-shell.tsx` — replaced the legacy blue focus-ring
  utility with `atlas-focus-ring`.
- `frontend/components/utc-date-time-picker.tsx` — replaced the legacy slate
  icon color with `atlas-foreground-muted`.
- `frontend/components/ui/calendar.tsx` — replaced legacy slate/blue calendar
  states with Atlas surface, primary, and primary-foreground utilities.
- `frontend/components/ui/popover.tsx` — replaced legacy slate/white surface
  utilities with Atlas border and surface utilities.

## References and visual review

Reviewed `dispatch/ACTIVE.md`, `PLAN.md`, `ARCHITECTURE.md`, `EXPLORATION.md`,
`READY.md`, `VALIDATION.md`, prior UI receipts TASK-03, TASK-06, TASK-07,
TASK-08, and TASK-12, all required design guidance, and `globals.css`.

Approved visual references reviewed: `atlas-experiment-run-page.png`,
`atlas-experiments-detail-page.png`, and `atlas-experiments-page.png`.

Local Host routes inspected:

- `http://localhost:3000/experiments/new` — setup hierarchy, dark canvas,
  bordered form panels, semantic warning treatment, horizontal shell, and
  PAPER/connected context.
- `http://localhost:3000/experiments` — list header, empty state, action
  placement, table/empty-state surface, and shell alignment.
- `http://localhost:3000/strategies` — shared shell and non-Experiment surface
  check.

Screenshots matched the approved dark-first Atlas direction: deep blue-black
canvas, navy surfaces, cool-neutral text/borders, restrained primary blue, and
semantic amber/green treatment. Local Host console diagnostics were empty on
all inspected routes. No positioning or layout change was required.

## Validation evidence

| Command | Result |
|---|---|
| `npm run test:web` | **23 passed** across 9 files (second full-suite run) |
| Focused `experiment_results.test.tsx` | **5 passed** |
| `npm run typecheck:web` | **Passed** |
| `npm run lint:web` | **Passed** |
| `npm run build:web` | **Passed** |
| Focused Prettier check for all changed frontend files | **Passed** |
| Frontend TSX hard-coded hex scan | **No matches** |

One initial full-suite run reproduced the previously known asynchronous
truncation-test flake; the focused test and subsequent full suite passed without
weakening assertions.

No Git operations were run. Only the listed frontend files and this owned receipt
were changed.

## Remaining action

Migrate the remaining legacy utility names in `experiment-workflow.tsx` to the
already-established Atlas utilities, then rerun the same full validation and
browser screenshot checks. Do not remove the compatibility layer until all
frontend consumers are migrated and verified.
