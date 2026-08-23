# TASK-17 — Selector-only E2E alignment

## Outcome

Updated the two affected completion assertions to use the existing rendered
status badge class, scoped to the Experiment page header. No UI markup, copy,
roles, test IDs, or product behavior was changed.

## Selector rationale

`StatusBadge` renders the approved completion state as a `span.status` inside
the page `header`. The prior primary `getByText('Completed')` was ambiguous
because the completed result surface contains two visible `Completed` text
matches. The prior zero-Trade assertion relied on a stale header text locator.
Both now use:

```ts
page.locator('header .status').filter({ hasText: 'Completed' })
```

This targets the existing rendered status badge rather than introducing a new
test-only contract.

## Changed files

- `tests/e2e/experiment-workflow.spec.ts` — replaced the primary broad
  completion locator and the zero-Trade stale locator.
- `dispatch/workstreams/phase-5-experiment-workflow/TASK-17.md` — this report.

## E2E receipts

The affected primary scenario was run serially against the isolated
`atlas_test` database:

```text
TZ=America/Los_Angeles \
ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' \
ATLAS_E2E_FIXTURE_FILE='/tmp/atlas-e2e-primary-task17.json' \
npx playwright test tests/e2e/experiment-workflow.spec.ts \
  --grep 'configures, runs' --workers=1
```

Result: **blocked**. The new completion locator passed, and the scenario
reached the Trade navigation. It then exposed a pre-existing backend failure
while loading Trade detail: `backend/experiments/results.py:_chart` raises
`ValueError: too many values to unpack (expected 2)`. The scenario failed at
the `Trade 1` heading assertion because the detail response was not rendered.

Per task instruction, execution stopped at this backend defect. The zero-Trade
affected scenario and canonical full Phase 5 E2E suite were not run.

## Blockers

- Backend Trade-detail chart composition failure in
  `backend/experiments/results.py` surfaced by the primary E2E scenario.
- No green primary receipt; therefore no claim is made for zero-Trade or the
  full Phase 5 E2E suite.

## Forbidden-operation confirmation

No backend source, product copy or UI behavior, Phase 4 semantics, database
outside the isolated `*_test` environment, dependency, browser installation,
Git state, or Phase 6 capability was changed. Backend code was only exercised
by the required E2E command. Full validation and review were not run, and no
dispatch artifact other than this `TASK-17.md` report was written.
