# REVIEW - UI 02 Trader Shell and Overview Product Cleanup

- **Status:** `PASS`
- **Role:** `REVIEW`
- **Workstream:** `ui-02-trader-shell-overview-product-cleanup`
- **Branch:** `solo/ui-02-trader-shell-overview-product-cleanup`
- **Base:** `main` at `9c31774f499c2e21a34b7f80fbfa190bf3be1fdb`
- **Reviewer:** independent REVIEW
- **Inputs reviewed:** approved `PLAN.md`, immutable BUILD receipts for T001 and T002, `VALIDATION.md`, complete branch diff including untracked workstream records, repository constraints, affected frontend sources/tests, and relevant API/domain contracts

## Verdict

**PASS.** The implementation matches the approved frontend-only slice. No unresolved `CRITICAL` or `IMPORTANT` finding remains. The branch preserves broker/runtime separation, exact string-based broker facts, independent Overview reads, read-only request behavior, and the approved progressive disclosure boundary.

## Evidence

- Branch and base match the workstream authority. The complete pre-review diff contains only `dispatch/ACTIVE.md`, the four approved component files, their focused tests, the narrow approved `home_page.test.tsx` stale-copy adjustment, and the four expected workstream records. This review adds only this `REVIEW.md`. No backend file, generated client, shared formatter, API client, fixture, or design-token file changed.
- T001 and T002 receipts were reviewed. Their expected focused-test concern and lint-baseline concern are resolved in `VALIDATION.md`.
- Independent focused execution passed: 4 files, 34 tests.
- Independent `npm run check:web` passed formatting, lint with 242 existing warnings and 0 errors, typecheck, 18 files and 91 tests, and production build.
- Independent `git diff --check` passed. The backend diff from the approved base is empty.
- Safari Technology Preview loaded `/` from the safe local frontend. Desktop rendered Paper Trading first, followed by Runtime, Strategies, Experiments, and System. At 390px, document and body scroll widths remained 390px while the labelled primary navigation contained its 570px horizontal content.
- Browser requests for the Overview were GET-only: readiness, strategies, experiments, broker state, and active runtime. The expected inactive-runtime 404 was translated to `No active runtime`; no raw provider code, UUID, provider Trade ID, snapshot metadata, or mutation control appeared in the Overview. No automatic polling was observed.
- Shell navigation, API status, timezone selector, disabled LIVE affordance, lifecycle-strip removal, and standalone timezone-copy removal are present and usable. The timezone selector remained functional and the display-timezone formatter updated rendered dates.
- The compact broker path maps every returned Trade independently, keeps signed-unit LONG/SHORT semantics and absolute quantities, gives unrealized P/L the stronger visual hierarchy, hides provider Trade IDs, and distinguishes empty from unavailable state. Refresh and Retry remain read-only.
- The compact runtime path distinguishes Active, no active runtime, and unavailable states without using runtime state as broker-flatness evidence. The full `/paper` path retains capability and detailed runtime evidence.
- Strategies and Experiments use existing reads/helpers and trader-facing facts. The Overview removes capability, historical-data, DatasetSnapshot, raw status-count, and global Next Steps sections. System health remains concise when healthy and explicit when degraded or unavailable.

## Acceptance Coverage

- **1-6 PASS:** recurring explanation, lifecycle strip, and timezone body sentence removed; timezone, navigation, API status, focus styling, and disabled LIVE retained.
- **7-17 PASS:** broker exposure is first; all Trades remain visible; direction, quantities, P/L hierarchy, empty/unavailable semantics, GET-only Refresh, and independent runtime presentation are preserved.
- **18-20 PASS:** Strategies, Experiments, and System summaries use supported facts, concise states, existing metric formatting, contextual actions, and explicit degraded health.
- **21-26 PASS:** Overview capability, historical, snapshot, raw metadata, and global Next Steps content and reads are removed; contextual links remain.
- **27-30 PASS:** loading/empty/error reads remain independent; mobile layout is contained; no trading or mutation controls were introduced; no backend files changed.

## Findings

### CRITICAL

None.

### IMPORTANT

None.

### MINOR

1. **PRODUCT | DEFECT | BASELINE** `frontend/components/api-status.tsx:42-47` suppresses the API-outage Retry button outline with `focus-visible:outline-none` without an explicit replacement ring. The changed shell retains this existing recovery control, but it is not a regression introduced by this workstream. Track with the shared shell accessibility baseline.
2. **PRODUCT | DEFECT | BASELINE** `frontend/components/app-shell.tsx:95-97` has no skip link or focus target for `main`. Keyboard users can reach the new Overview controls, but still must traverse the shared header before content. This is inherited shell debt, not new scope.
3. **PRODUCT | DEFECT** `frontend/components/paper-status.tsx:135-143` renders the newly compact Active runtime result without a `role="status"` or live region after replacing the loading status. A screen reader user may not be notified when the asynchronous runtime read resolves. Add a polite status region in a later accessibility remediation; this does not affect financial truth or merge safety.
4. **TOOLING | DEFECT | BASELINE** `tests/e2e/foundation.spec.ts:56-60` still asserts the removed Overview labels and visible-page prose. The file was already stale at the approved base (`PAPER current status` at line 72), and `npm run test:e2e` was not run because its global setup seeds a database outside this review's read-only boundary. Update the E2E copy assertions in shell-test maintenance; the approved focused/full frontend gates and safe browser checks are unaffected.

No `NEW SCOPE` finding was identified.

## Residual Concerns / Baseline Limitations

- The configured read API exposed no active broker Trades and no active PAPER runtime during browser review. Active, multiple-Trade, signed-short, P/L-tone, and unavailable variants were covered by the focused component/Overview tests and source inspection rather than by changing broker or runtime state.
- The expected inactive-runtime endpoint returns HTTP 404 and emits development-console 404 noise because the existing API client translates `PAPER_ACTIVATION_NOT_ACTIVE` to the normal null read result. This behavior is unchanged and the raw code remains absent from Overview.
- `npm run test:e2e -- --list` discovered all 7 repository E2E tests, but execution was intentionally not performed because the global setup seeds data and would violate the requested read-only review boundary. One existing E2E file also contains the stale assertions listed above.
- The repository retains 242 pre-existing unused-variable lint warnings, all outside the changed shell, Overview, broker-state, and PAPER-status files. No new lint error or changed-surface warning was observed.
- Broker P/L presentation continues to use the pre-existing string-only two-decimal display formatter. Entry and unit values remain exact strings and no float conversion or API contract change was introduced.

## Scope and Boundary Judgment

- The branch is frontend-only and does not activate PAPER, start `atlas-runtime`, reconcile, mutate OANDA, submit broker requests, change Risk, alter persistence, or change backend/API contracts.
- The existing GET read methods remain the only Overview data sources: `ready()`, `listStrategies()`, `listExperiments({ limit: 8 })`, `paperBrokerState()`, and `activePaperStatus()`.
- Full PAPER and Data surfaces retain ownership of their detailed capability, runtime, historical, and evidence facts. Progressive disclosure removes only their prominence from Overview.
- The implementation does not introduce polling, websockets, trading controls, broker controls, a navigation redesign, or new design tokens.

## Merge Recommendation

**MERGE APPROVED.** Merge after the normal explicit developer/trader merge approval. The minor baseline accessibility and stale-E2E concerns are non-blocking and should remain follow-up work rather than trigger application changes in this review.

## Completion Receipt

```text
ROLE: REVIEW
STATUS: PASS
ARTIFACT: dispatch/workstreams/ui-02-trader-shell-overview-product-cleanup/REVIEW.md
FILES CHANGED BY REVIEW: dispatch/workstreams/ui-02-trader-shell-overview-product-cleanup/REVIEW.md only
CHECKS / EVIDENCE: Independent focused Vitest 4 files / 34 tests PASS; npm run check:web PASS with 242 baseline warnings and 0 errors, 18 files / 91 tests, typecheck, and production build; git diff --check PASS; backend diff empty; Safari desktop and 390px Overview, hierarchy, overflow, timezone, focusability, and GET-only checks PASS; Playwright discovery listed 7 tests without execution because seeded E2E setup is outside the read-only review boundary.
FINDINGS / CONCERNS: No CRITICAL or IMPORTANT findings. Four MINOR findings remain: two inherited shell accessibility defects, one compact-runtime async announcement defect, and one baseline/stale E2E assertion defect. No NEW SCOPE finding. Merge approved.
```
