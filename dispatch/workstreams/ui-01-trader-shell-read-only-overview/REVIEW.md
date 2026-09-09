# REVIEW - UI 01 Trader Shell and Read-Only Overview

- **Status:** `PASS`
- **Role:** REVIEW
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Owner:** fresh `solo-flow-worker`

## Findings

### MINOR

1. **PRODUCT | DEFECT** `frontend/app/globals.css:148-163`, used by
   `frontend/components/overview.tsx:253-266`: `.action-primary` and
   `.action-secondary` set `outline: none` without a `:focus-visible` replacement.
   The new Overview next-step links therefore have no visible keyboard focus
   indicator. Required action: remove the outline suppression or add an explicit
   visible focus ring, then assert the Overview action links' focused state.
2. **PRODUCT | DEFECT** `frontend/components/api-status.tsx:42-47`: the
   unavailable-state Retry button uses `focus-visible:outline-none` without a
   focus ring. In an API outage, the shell's recovery control can receive focus
   without a visible indicator. Required action: retain the shared outline or add
   the same explicit visible focus ring used by `ReadError` Retry.
3. **PRODUCT | DEFECT** `frontend/components/app-shell.tsx:123-128`: the shell
   has no skip link or focus target for main content. Keyboard users must traverse
   the wordmark, six primary-surface items, API status, and timezone control before
   reaching a route's content. Required action: add a first-focusable Skip to main
   link and a focusable `main` target on the shared shell.

No unresolved CRITICAL or IMPORTANT finding remains. These three MINOR findings
are approved-scope accessibility defects, not NEW SCOPE, and do not block PASS
under the workstream review gate.

## Judgment

- `/` renders `Overview` directly; source has no redirect and Safari loaded the
  Overview heading at `/`.
- Primary navigation is Overview, Strategies, Experiments, PAPER, and Data, with
  LIVE rendered as a noninteractive disabled future capability. Dashboard,
  Deployments, Journal, `PAPER · connected`, and `PAPER and LIVE are future-only`
  are absent from the final frontend source.
- Overview sections use only health, Strategy catalog, visible Experiment-list,
  PAPER capability/current-status, historical capability, and configuration-options
  reads. Section loading, empty, and error state is independent and qualifiers do
  not imply global totals, performance, account, broker, or historical-session
  evidence.
- PAPER uses capability and active-status GETs only. The active 404 is represented
  as `PAPER_ACTIVATION_NOT_ACTIVE`; the page exposes current facts and the explicit
  evidence boundary, with no activation, stop, reconcile, trade, protection, or
  broker mutation affordance.
- Data uses existing historical capability, DatasetSnapshot options, and active
  load status facts. Returned coverage, load, and PAPER state timestamps use the
  display-timezone formatter.
- Strategies and Experiments remained reachable and usable through the shell;
  Safari navigated both existing workflows and retained their existing route
  content.
- The four blocking findings in the immutable root VALIDATION were independently
  confirmed closed by the current shell geometry, wrapped snapshot values,
  corrected smoke sequencing, and explicit Retry focus-ring source/test coverage.

## Boundary

- Branch is `solo/ui-01-trader-shell-read-only-overview`; the recorded base is
  `459e4a298c80b87b28b2875069fd49795ddef478`.
- Final tracked changes are frontend, `tests/e2e/foundation.spec.ts`, and the
  expected `dispatch/ACTIVE.md` coordination edit. New frontend pages/components/
  tests and workstream evidence are the expected untracked files. No backend,
  runtime, PAPER, Risk, OANDA, persistence, Strategy, or migration path changed.
- `frontend/lib/api.generated.ts` retains the auto-generated header and matched a
  fresh `create_app().openapi()` -> `openapi-typescript 7.13.0` -> Prettier
  regeneration byte-for-byte. The handwritten client additions are GET-only
  wrappers; existing mutation methods remain outside the new read surfaces.
- No credentials, `atlas-runtime`, activation, reconciliation, broker mutation,
  migration, Dogfood 02, or Trade 11 action was run.

## Checks

- Independent focused Vitest: 7 files and 21 tests passed.
- Independent changed-file ESLint, Prettier, TypeScript, Playwright discovery
  (2 tests listed), and `git diff --check` passed.
- R001 full frontend evidence: 16 Vitest files and 57 tests passed, lint passed
  with 242 existing warnings, typecheck passed, and production build passed with
  `/`, `/paper`, and `/data` emitted.
- Fresh generated-client comparison passed exactly.
- Safari Technology Preview independently loaded `/`, `/paper`, and `/data` at
  1440px and 390px. Desktop navigation measured 1016px without overflow. At 390px
  the primary nav measured 342px with 568-570px scroll content, document/body
  widths stayed 390px, and DatasetSnapshot cards and 64-character fingerprints
  stayed within their 300px facts. Actual route clicks reached Data, Overview,
  Strategies, and Experiments.
- Safari found only GET API traffic while traversing the read-only surfaces,
  including the expected PAPER active-status 404; POST, PUT, PATCH, and DELETE
  request filters were empty. The five primary nav links reported `tabIndex: 0`
  and direct focus succeeded.

## Baseline And Environment

- `npm run check:web` remains blocked at the five pre-existing formatter failures:
  `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`,
  `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and
  `tests/e2e/.fixtures.json`.
- The 242 lint warnings are in untouched existing Experiment workflow files.
- Playwright execution was not substituted with another database: the standard
  API port was occupied and `ATLAS_E2E_DATABASE_URL` was unset, so execution
  stopped before browser launch. Discovery passed and Safari supplied independent
  read-only evidence.
- Safari's local keyboard-navigation mode sent a literal Tab from the wordmark to
  the timezone select rather than the first nav link. This is a browser setting
  limitation; direct focus and DOM tab stops were verified and it is not treated
  as a workstream finding.
- Safari console output contained only local HMR suspension and expected inactive
  status 404 noise; no remediation-specific runtime exception was observed.

## Completion Receipt

```text
ROLE: REVIEW
STATUS: PASS
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/REVIEW.md
FILES CHANGED BY REVIEW: dispatch/workstreams/ui-01-trader-shell-read-only-overview/REVIEW.md only
CHECKS / EVIDENCE: Focused Vitest 7 files / 21 tests PASS; changed-file ESLint, Prettier, typecheck, Playwright discovery (2 tests), git diff --check, and fresh generated OpenAPI comparison PASS; R001 full frontend Vitest 16 files / 57 tests, lint, typecheck, and build PASS; Safari desktop and 390px route, overflow, focusability, and GET-only PAPER checks PASS; Playwright execution remained blocked before browser launch by occupied port and unset dedicated ATLAS_E2E_DATABASE_URL without database substitution.
FINDINGS / CONCERNS: Three MINOR PRODUCT DEFECT accessibility findings remain: Overview action-link focus replacement is missing at frontend/app/globals.css:148-163, API Retry focus replacement is missing at frontend/components/api-status.tsx:42-47, and the shared shell lacks a skip link at frontend/components/app-shell.tsx:123-128. No unresolved CRITICAL or IMPORTANT finding; no NEW SCOPE. Five baseline formatter failures, 242 pre-existing lint warnings, occupied API port, missing dedicated E2E database, and Safari keyboard-mode limitation remain separately classified as baseline/environment concerns.
```
