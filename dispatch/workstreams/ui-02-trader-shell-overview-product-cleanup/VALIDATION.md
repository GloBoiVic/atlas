# VALIDATION - UI 02 Trader Shell and Overview Product Cleanup

## Result

**PASS**

- **Workstream:** `ui-02-trader-shell-overview-product-cleanup`
- **Role:** `VALIDATE`
- **Branch:** `solo/ui-02-trader-shell-overview-product-cleanup`
- **Base:** `main` at `9c31774f499c2e21a34b7f80fbfa190bf3be1fdb`
- **Validated:** 2026-09-09

The approved frontend-only acceptance slice is implemented and passes the focused and full frontend gates. The two BUILD receipt concerns were independently rechecked: the stale T001/T002 focused-test failures are resolved, and the 242-warning lint baseline remains warning-only with no errors.

## Commands and Evidence

- `npm run test:web -- tests/app_shell.test.tsx tests/overview.test.tsx tests/paper_broker_state.test.tsx tests/paper_status.test.tsx` — passed, 4 files and 34 tests.
- `npm run check:web` — passed formatting, lint, typecheck, 18 files and 91 tests, and production build.
- `npm run lint:web` within the full gate — 242 existing `@typescript-eslint/no-unused-vars` warnings, 0 errors; no warnings were reported in the changed shell, Overview, broker-state, or PAPER-status files.
- `git diff --check 9c31774f499c2e21a34b7f80fbfa190bf3be1fdb -- frontend backend` — passed.
- `git diff --name-only 9c31774f499c2e21a34b7f80fbfa190bf3be1fdb -- backend` — empty; no backend files changed.
- Current scope contains the approved frontend components/tests, the narrow `home_page.test.tsx` stale-copy adjustment recorded by T002, and workstream operational records. No generated client, API helper, shared formatter, or backend file changed.

## Browser Evidence

Safari Technology Preview was used against the safe local frontend at `http://127.0.0.1:3000/`. Only existing read-only surfaces were exercised. `atlas-runtime` was not started; PAPER was not activated or stopped; reconciliation, OANDA mutation, Trade mutation, and seed-based E2E setup were not run.

- Desktop at 1440px: Overview rendered with Paper Trading first, followed by Runtime, Strategies, Experiments, and System; no page horizontal overflow.
- Mobile at 390px CSS width: page `scrollWidth` equaled `clientWidth` at 390; the primary nav had `overflow-x: auto` with content scroll width 570, so navigation remained accessible without page overflow.
- The normal configured read state rendered `OANDA Practice USD`, `No open trades`, `No active runtime`, trader-facing Strategy and Experiment rows, and compact System `Ready`/API/Database facts.
- The shell retained Atlas, Overview, Strategies, Experiments, PAPER, Data, disabled LIVE, API status, and the labelled Display timezone selector.
- Changing the Display timezone from Chicago to UTC and New York updated rendered Experiment dates and persisted the preference; `Times shown in ...` was absent.
- Browser network evidence contained only GET requests to `/health/ready`, `/api/v1/strategies`, `/api/v1/experiments?limit=8`, `/api/v1/paper/broker-state`, and `/api/v1/paper/activations/active`. No capability, historical-data, configuration-options, POST, PUT, PATCH, or DELETE request occurred.
- The expected no-active runtime endpoint returned HTTP 404 with `PAPER_ACTIVATION_NOT_ACTIVE`; the rendered Overview showed only `No active runtime`. No raw code, UUID, provider Trade ID, snapshot metadata, Next Steps section, or mutation control appeared in the rendered Overview.
- After the initial reads settled, a three-second network observation recorded zero additional requests, consistent with no automatic polling.
- Focus-visible styling remains defined by the existing global `:focus-visible` rule, shell links remain semantic links, the timezone control is labelled, and the focused shell test passed.

## Acceptance Coverage

- 1. PASS — Overview has no recurring Atlas explanation paragraph.
- 2. PASS — Shell lifecycle explainer strip is removed.
- 3. PASS — Standalone `Times shown in <timezone>` body text is removed.
- 4. PASS — Timezone selector remains functional and updates persisted display context.
- 5. PASS — Primary navigation remains responsive, horizontally usable on mobile, semantic, and focus-styled.
- 6. PASS — API status remains available in the shell.
- 7. PASS — Current broker exposure is the first substantive Overview section.
- 8. PASS — All returned open Trades are mapped and independently rendered.
- 9. PASS — Signed units still derive LONG/SHORT and absolute quantity without float conversion.
- 10. PASS — Compact unrealized P/L uses the stronger `text-2xl font-semibold` hierarchy and existing positive/negative/neutral colors.
- 11. PASS — Compact Overview does not render provider Trade IDs.
- 12. PASS — Successful empty broker inventory renders `No open trades`, never `Flat`.
- 13. PASS — Broker read failure renders `Broker unavailable` with retry and not an empty/flat state.
- 14. PASS — Refresh retries the existing broker GET only; focused tests verify the read is retried.
- 15. PASS — Runtime is visually and structurally secondary to the broker exposure surface.
- 16. PASS — No-active runtime renders `No active runtime` without `PAPER_ACTIVATION_NOT_ACTIVE` on Overview.
- 17. PASS — Runtime presentation does not claim broker flatness or substitute for broker exposure.
- 18. PASS — Strategies summary uses Strategy names, latest display names, and concise secondary facts with contextual links.
- 19. PASS — Experiments summary uses returned identity, status, strategy, period, and existing headline metric helpers instead of status-count diagnostics.
- 20. PASS — System summary is compact when healthy and explicit for degraded facts and read errors.
- 21. PASS — PAPER capability is removed from Overview.
- 22. PASS — Historical-data capability is removed from Overview.
- 23. PASS — DatasetSnapshot fingerprints, schemas, and integrity metadata are absent from Overview.
- 24. PASS — Overview does not invoke `paperCapability()`, `historicalCapability()`, or `configurationOptions()`; browser network evidence confirms no corresponding reads.
- 25. PASS — Global Next Steps section and duplicate navigation actions are removed.
- 26. PASS — Contextual Strategy and Experiment links remain usable.
- 27. PASS — Independent loading, empty, and error states are covered by focused tests and separate `useReadResource` instances.
- 28. PASS — Safari mobile observation shows readable stacked content with no page horizontal overflow; nav overflow is intentional and contained.
- 29. PASS — No trading or mutation controls were introduced; Overview controls are read-only Refresh/Retry plus navigation links.
- 30. PASS — No backend files changed.

## Baseline Limitations

- The configured local read API had no open broker Trades and no active PAPER runtime, so browser-visible active, multiple-Trade, positive/negative/neutral P/L, and unavailable variants were validated through the focused component/Overview tests and source inspection rather than by changing live or persisted state.
- The normal no-active runtime response is an HTTP 404 and produced two browser console 404 messages during React development-mode duplicate reads. This is the existing `PAPER_ACTIVATION_NOT_ACTIVE` read contract, is translated to the concise empty state by the existing API client, and was not changed by this workstream.
- `npm run test:e2e` was not run because its global setup seeds a database and the requested validation boundary requires browser checks to remain read-only. It is not part of the approved frontend focused/full gate.
- Existing lint baseline contains 242 unused-variable warnings in unrelated files; no changed-surface lint errors or new warnings were observed.

## Findings

No findings. No `PRODUCT`, `REGRESSION`, or `TOOLING` defects and no `NEW SCOPE` findings were identified.
