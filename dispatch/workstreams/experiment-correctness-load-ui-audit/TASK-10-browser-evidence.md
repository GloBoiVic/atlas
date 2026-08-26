# TASK-10 Browser evidence — Experiment setup load UI

## Scope and result

Inspected `http://localhost:3000/experiments/new` as a trader. No application
frontend change was made: the two reported symptoms are not safe frontend-only
regressions to fix in this workstream.

Required inputs were reviewed: the current workstream artifacts and approved
`ARCHITECTURE.md`, `frontend/app/globals.css`, `context/design/design.md`,
`visual-guide.md`, `ui-tokens.md`, and all ten approved design screengrabs.
The observed surface was compared against the dark-first, restrained Atlas
tokens and trader-facing hierarchy; no theme semantic change was warranted.

- The duplicate mount traffic is two identical request groups issued within
  4 ms during the Next development mount. This is consistent with the
  development Strict Mode remount, not a second load command. The component
  does not POST a load during mount.
- `/api/v1/historical-data/load-requests/active` returned 404 twice. The page
  treats this initial optional-status failure as unavailable/idle and does not
  show a red error. The missing route is a server/API deployment mismatch;
  changing the client to hide or synthesize status would weaken server
  authority and fail-closed creation.

## Mount network evidence

Browser network capture (`tab-18`, `http://localhost:3000/experiments/new`):

| Timestamp (browser epoch ms) | Method | Endpoint | Status |
|---:|---|---|---:|
| 1787712171057 | GET | `/atlas-api/health/ready` | 200 |
| 1787712171059 | GET | `/atlas-api/api/v1/experiments/configuration-options` | 200 |
| 1787712171059 | GET | `/atlas-api/api/v1/historical-data/capability` | 200 |
| 1787712171059 | GET | `/atlas-api/api/v1/historical-data/load-requests/active` | **404** |
| 1787712171062 | GET | `/atlas-api/health/ready` | 200 |
| 1787712171063 | GET | `/atlas-api/api/v1/experiments/configuration-options` | 200 |
| 1787712171063 | GET | `/atlas-api/api/v1/historical-data/capability` | 200 |
| 1787712171063 | GET | `/atlas-api/api/v1/historical-data/load-requests/active` | **404** |

The page rendered trader-facing copy (`Trading start (UTC)`, `Trading end
(UTC)`, `Data available`, and `Loading market data and validating strategy
coverage.`). Console diagnostics were empty. The extra font request was a
successful 200 and is unrelated to the duplicate API group.

## Interaction evidence and limits

The local API returned an empty configuration (`Choose a StrategyVersion` and
`Choose available data` remained displayed). Consequently the form had no
strategy or snapshot selected, date controls remained unset, and the load
button was disabled.

- **One edit:** attempted the `1W` preset and a calendar date selection. The
  preset was disabled because no strategy was ready; selecting day `25` did not
  produce a valid form period. No coverage request was emitted.
- **Four rapid edits:** not executable. The browser interaction surface could
  not resolve the nested date/time and form inputs as fillable labelled
  controls, and the form had no loaded StrategyVersion/data to enable the
  workflow. No edit request trace is claimed.
- **Polling:** not started. There was no active load ID/status and the initial
  `/active` request was 404. No polling interval or status request was
  observed.
- **Terminal completion:** not reachable. Starting a load was disabled and no
  POST was made. No completion or failure transition is claimed from this
  session.
- **Stale-response protection:** not exercised. No overlapping coverage
  validations could be generated in the available local state.

Static review confirms the automatic inventory effect uses a local request
generation guard (`current`) before applying its response. The explicit
`Validate coverage` handler currently awaits directly and has no equivalent
request-generation check; this could not be reproduced or safely remediated
without changing the owned frontend component, so it is recorded as an
unverified follow-up rather than claimed protected.

These are exact local-environment limitations, not inferred success. Existing
fail-closed behavior remained intact: `Run Experiment` stayed unavailable
without valid coverage and a completed historical load.

## Validation commands

| Command | Result |
|---|---|
| `npm run test:web` | **23 passed** across 9 files |
| `npm run typecheck:web` | **Passed** |
| `npm run lint:web` | **Passed** |
| `npm run build:web` | **Passed** |
| `npx prettier --check frontend/components/experiment-workflow.tsx frontend/components/utc-date-time-picker.tsx frontend/app/globals.css` | **Failed only for existing `frontend/app/globals.css` formatting divergence** |

No frontend files, `globals.css`, backend/Strategy/PAPER paths, dependencies,
or other dispatch artifacts were changed. Theme tokens and server authority
were preserved. The required `globals.css` formatter issue remains a separate
pre-existing gate and was not altered outside this artifact.
