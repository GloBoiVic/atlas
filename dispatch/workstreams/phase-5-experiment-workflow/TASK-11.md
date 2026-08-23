# TASK-11 — Narrow post-repair E2E remediation

- **Task:** Resolve only the three browser failures documented by TASK-10.
- **Branch:** `feature/phase-5-experiment-workflow`
- **Outcome:** Blocked; no application or test edits were made.

## Scope checks

Inspected the existing UI/API flow, Playwright harness, fixture seed, and the
three affected assertions before considering edits. The documented failures
are already repaired in the current checkout:

- Coverage validation is enabled after the configuration options load and the
  requested period is filled. Both valid and invalid coverage requests reached
  the API; the valid request returned `200` with `"valid":true`.
- The failed-Experiment page rendered `Failed` and
  `No trustworthy full result was created.`.
- The foundation test expects the current approved title and `Experiments`
  heading.

No smallest additional change could be justified within the approved scope.

## Exact E2E receipt

Command:

```text
ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' \
npx playwright test --workers=1
```

Result: **2 failed, 3 passed** in approximately 4.6 minutes.

Passing scenarios:

- invalid coverage and creation prevention
- failed Experiment without partial results
- foundation page

The two valid-run scenarios both reached coverage validation successfully but
the run returned durable `FAILED` state with API failure
`MARKET_DATA / INVALID_INPUT / Experiment could not be run`. The browser then
timed out waiting for `Completed` at the existing assertions in
`tests/e2e/experiment-workflow.spec.ts` (120 seconds each). This is a runner/
fixture execution failure, not one of the three TASK-10 browser assertion
failures, and changing it would exceed Task 11 scope.

The documented `npm run test:e2e` command was also attempted. Its first run
was terminated by the command timeout after the same durable failure state was
observed; a subsequent attempt was blocked by the prior server process still
occupying port 8000. The serial rerun above completed the relevant diagnostic
receipt without reinstalling anything.

## Changed files

- None.

## Remaining blocker

The valid primary and zero-Trade Experiments fail in the existing backend run
path with `MARKET_DATA/INVALID_INPUT`. No workaround or out-of-scope runner,
fixture, or Phase 1–4 semantic change was introduced. Validation should remain
blocked pending an approved task addressing that execution failure.

## Operations confirmation

- No Git mutations were performed: no commit, reset, checkout, clean, push, or
  merge.
- No dependency or browser installation was performed.
- No dispatch artifact other than this `TASK-11.md` was altered.
