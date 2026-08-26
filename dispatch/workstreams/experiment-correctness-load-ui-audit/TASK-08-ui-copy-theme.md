# TASK-08 Receipt — Experiment UI copy and theme remediation

## Outcome

**RESOLVED.** The live setup page had the reported technical copy in primary
content. This was current application output, not a stale server artifact: the
browser at `http://localhost:3000/experiments/new` showed `UTC wall-clock
entry`, `Technical load range`, `OANDA M1 bars + ... snapshot`, and `Native M15
MID analysis · sparse M1 BID/ASK execution` before this change. Those strings
matched the source at the corresponding `experiment-workflow.tsx` and
`utc-date-time-picker.tsx` call sites.

## Changes

- Kept the blueprint’s trader-facing labels and loading sentence unchanged:
  `Trading start (UTC)`, `Trading end (UTC)`, `Data available`, and
  `Loading market data and validating strategy coverage.`
- Removed technical mechanics from primary setup copy. The UTC wall-clock
  explanation, load-range bounds/context, provider/snapshot onboarding detail,
  and M15/M1 BID/ASK execution detail now appear under native HTML
  `<details><summary>Technical details</summary>` disclosures.
- Kept truthful progress and status messaging visible; only implementation
  facts were progressively disclosed.
- Used the existing Atlas compatibility/theme classes and variables already
  provided by `frontend/app/globals.css`; no one-off color, token, dependency,
  backend, Strategy, or PAPER/LIVE change was introduced.

## Browser evidence

- Route: `http://localhost:3000/experiments/new`
- Before remediation: primary page text exposed all four technical-copy
  examples above.
- After remediation: visible page text retains the trader-facing setup flow,
  dates, `Data available`, `Loading market data and validating strategy
  coverage.`, and `Run Experiment`; technical mechanics are represented by
  collapsed `Technical details` disclosures and are not in the primary copy.
- Console: no errors.
- Failed network diagnostics: two document `ERR_ABORTED` entries from the
  development reload; no application API failure was observed.

## Validation

| Command | Result |
|---|---|
| `npm run test:web` | **23 passed** across 9 files |
| `npm run typecheck:web` | **Passed** |
| `npm run lint:web` | **Passed** |
| `npx prettier --write frontend/components/experiment-workflow.tsx frontend/components/utc-date-time-picker.tsx` | **Passed** |
| `npx prettier --check frontend/components/experiment-workflow.tsx frontend/components/utc-date-time-picker.tsx frontend/tests/experiment_results.test.tsx frontend/tests/experiment_list.test.tsx frontend/tests/price_analysis.test.tsx` | **Passed** |

No Git operations were run. Only the two frontend component files and this
receipt were changed for this remediation; no backend or trading-domain path
was touched.
