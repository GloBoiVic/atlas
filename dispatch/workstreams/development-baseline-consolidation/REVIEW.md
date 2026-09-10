# REVIEW - Development Baseline Consolidation

- **Status:** `BLOCKED`
- **Role:** `REVIEW`
- **Workstream:** `development-baseline-consolidation`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `main` at `611fe10b9b596f9e48339f305b99023d402c4514`
- **Reviewer:** independent REVIEW
- **Files changed by REVIEW:** this file only

## Assignment

Independently review the approved PLAN, complete branch diff, all BUILD receipts, PYRIGHT.md,
COMPATIBILITY.md, and VALIDATION.md. Judge whether the implementation is limited to approved
scope, whether removals meet the evidence standard, whether the Pyright contradiction is
truthfully documented, and whether any trading, evidence, persistence, authority, or safety
boundary was weakened.

The reviewer must diagnose and judge only. Do not edit application, test, fixture, selector,
harness, workflow, or other implementation code. Complete this artifact with the verdict,
severity-classified findings, acceptance/boundary evidence, residual debt, merge recommendation,
and the required concise REVIEW receipt. Do not merge or change Git history.

## Decision

`BLOCKED`. The implementation diff has no identified trading, financial, persistence, API,
frontend behavior, or runtime safety regression. However, two `IMPORTANT / PRODUCT / DEFECT`
findings violate approved documentation and compatibility-inventory requirements. They must be
remediated by Solo and independently re-reviewed. REVIEW did not repair either finding.

There are no `CRITICAL` findings.

## Scope And Identity

- `HEAD` is the approved base commit `611fe10b9b596f9e48339f305b99023d402c4514`; there is no
  committed branch delta.
- The worktree contains the 15 tracked paths and 72 insertions / 55 deletions recorded in
  `VALIDATION.md:33-53`. Untracked application or test source was not found; untracked files
  are the workstream artifacts.
- The tracked implementation changes are limited to repository guidance, current-source phase
  wording, one local-variable rename, removal of one unreferenced private forwarder, and the
  proven frontend duplicate/dead-symbol removals.
- No application, test, fixture, selector, harness, workflow, schema, migration, generated
  client, dependency, persisted-data, or Git-history change was made by REVIEW.

## Findings

### F-001 - IMPORTANT / PRODUCT / DEFECT / approved scope

`README.md:31` states: `A real OANDA Practice token is required only for workflows that call
the external OANDA historical-data API.` The current repository also has guarded OANDA Practice
PAPER workflows that require the token:

- `backend/runtime/activation.py:695-704` rejects PAPER activation without an OANDA token and
  account configuration.
- `backend/runtime/main.py:77-153` wires the token into account, pricing, execution, protection,
  and reconciliation readers for the PAPER runtime.
- `backend/api/app.py:196-203` exposes a broker-state reader backed by an OANDA API call, and
  `backend/integrations/oanda/request.py:34-37` rejects missing or blank tokens.

The runtime still fails closed, so this is not evidence of an authorization bypass. It is an
inaccurate current setup/capability statement and violates the T001/PLAN requirement that
repository guidance describe the current guarded PAPER capability accurately. This blocks the
review until Solo corrects the wording; REVIEW must not edit `README.md`.

### F-002 - IMPORTANT / PRODUCT / DEFECT / approved scope

`COMPATIBILITY.md:165-167` and `190-193` state that the generated client models Experiment
result and metric schema values as strings. The current API/generated boundary does not support
that claim:

- `backend/api/schemas.py:486-490` defines `ExperimentReadResponse` with only `identity` and
  `extra="allow"`.
- `frontend/lib/api.generated.ts:738-743` therefore exposes Experiment detail fields only
  through an index signature of `unknown`; it has no typed `resultSchemaVersion` or
  `metricSchemaVersion` member.
- `frontend/lib/api.generated.ts:524-529` types `ComparisonExperimentResponse.metricContract`
  as a map of `unknown`, not as string-valued fields.
- The runtime payloads do contain these values at `backend/api/experiments.py:296,310` and
  `backend/experiments/results.py:529-532`; the frontend deliberately consumes the detail
  response as `ExperimentPayload = Record<string, unknown>` in `frontend/lib/api-client.ts:5-7`.

The current behavior is not broken, and the generated file itself is unchanged. The required
T003 API/generated-surface inventory is nevertheless factually overbroad, which can mislead a
future result-contract or compatibility retirement decision. This blocks the review until Solo
corrects the inventory claim; REVIEW must not edit `COMPATIBILITY.md` or regenerate the client.

### MINOR / TOOLING / NEW SCOPE

The accepted repository-wide validation debt remains:

- Locked Pyright `1.1.411`: `3,011` errors, `1,845` production and `1,166` test errors,
  `0` warnings, and `0` informations. The structured report is valid and exit `1` means
  diagnostics, not a tool/runtime failure.
- Full Ruff lint reports `28` unrelated diagnostics; full Ruff format reports `68` files that
  would be reformatted and `147` already formatted.
- Changed-surface Ruff checks pass. Before/after focused Pyright reports are identical at
  `37` diagnostics across the nine changed Python files, with no new diagnostic.

This is inherited baseline debt documented in `PYRIGHT.md` and `VALIDATION.md`, not a product
regression or an approved-scope blocker.

### MINOR / TOOLING / NEW SCOPE

`VALIDATION.md:205-206` records two standalone current-worktree `npm run test:web` invocations
that exited `1` after all 146 tests passed because Vitest emitted a late
`ReferenceError: window is not defined` from `home_page.test.tsx`. The focused home-page test,
the base full suite, and the required `npm run check:web` gate passed as recorded. This remains
an intermittent test-harness teardown concern, not a frontend behavior regression.

## Acceptance Coverage

| Acceptance area | Result | Independent evidence |
| --- | --- | --- |
| Current capability and non-authorization documentation | **BLOCKED** | `AGENTS.md` and the new README top/runtime text correctly describe undeployed guarded EUR/USD PAPER and deny authorization from startup, broker inspection, or credentials; F-001 remains in the unchanged README prerequisite sentence. |
| Provider-first and complexity-ratchet guidance | **PASS** | `AGENTS.md:72-86` contains the approved provider-first rule and the generated-file/400/600/800/1,200-line ratchet. |
| Pyright contradiction and changed-surface policy | **PASS** | `PYRIGHT.md` gives the exact historical command, current locked version/counts, production/test split, bounded causes, and no-new-diagnostics policy; `VALIDATION.md:149-176` records identical before/after focused reports. |
| Compatibility classifications and retirement points | **BLOCKED** | All required seams are classified in `COMPATIBILITY.md:34-310`, but F-002 makes the required generated-surface evidence inaccurate. |
| Phase terminology | **PASS** | Current comments/docstrings and one local/test identifier were mechanically reworded; historical migration IDs, persisted identifiers, benchmark names, constraints, triggers, functions, compatibility enum values, and API-facing error text remain unchanged. |
| Removed duplicate/dead symbols | **PASS** | T004 proof and current searches cover `WorkflowFeatureBoundaries`, `chartTime`, `chartTick`, duplicate chart types/order helpers, and `_unsafe_attempt_exists`; canonical chart helpers and runtime aliases remain. |
| Persistence/API/generated and evidence boundaries | **PASS** | The diff has no migration, schema, model, generated-client, persisted-data, or evidence change; the generated-surface documentation issue is separately recorded as F-002. |
| Strategy/Risk/execution/reconciliation/protection/activation/broker authority | **PASS** | `fill_application.py` only renames a local; `activation.py` only removes an unreferenced private forwarder. Existing safety predicates, model-version values, state codecs, and authority boundaries remain. |
| Frontend behavior and scope | **PASS** | Only duplicate/dead exports and wrappers were removed; focused Prettier/ESLint/typecheck/tests and the production build passed. No rendered behavior or data flow changed. |

## Validation And Safety Evidence

- `git diff --check` passed for the tracked diff; the workstream Markdown receipts also passed
  their no-index whitespace checks according to `VALIDATION.md:60-68`.
- `uv lock --check` passed with 41 resolved packages.
- The safe backend suite passed with `1,296 passed, 4 skipped, 115 deselected`; the focused
  backend receipt passed with `213 passed, 1 warning`.
- Frontend typecheck, focused changed-file Prettier/ESLint, and `npm run check:web` passed as
  recorded in `VALIDATION.md:70-89`; the Vitest teardown concern remains explicitly recorded
  above rather than hidden.
- Direct Pydantic schema inspection confirmed `ExperimentReadResponse` has only the typed
  `identity` field plus arbitrary additional properties, corroborating F-002.
- No database reset, migration execution, credential creation/change, runtime start, API server
  start, external OANDA request, PAPER activation/reconciliation, broker mutation, or
  capital-capable operation was performed by REVIEW or the recorded validator.

The following were intentionally not run because this Feature changes no migration, database
contract, external-provider behavior, or browser-visible behavior:

```text
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> uv run pytest -m integration
uv run pytest -m external
npm run test:e2e
```

## Residual Debt And Readiness

The repository-wide Pyright/Ruff baselines and intermittent Vitest teardown issue are accepted
nonblocking tooling debt and must remain reported truthfully. They do not justify a repository-
wide cleanup in this workstream.

The branch is **not currently ready** to begin Market Capability 01 - GBP/JPY on OANDA Practice,
because F-001 and F-002 are approved-scope defects. No GBP/JPY or multi-instrument implementation
was introduced; the current runtime remains explicitly EUR/USD-only (`PAPER_RUNTIME_INSTRUMENT =
"EUR_USD"`). After Solo remediates both documentation findings and the remediation chain passes
independent validation/review, the implementation evidence supports beginning the next Critical
workstream. Beginning that workstream is distinct from implementing GBP/JPY, which remains
deferred and absent here.

## Merge Recommendation

Do not merge this workstream and do not begin GBP/JPY until F-001 and F-002 are corrected through
the normal Solo remediation chain and independently re-reviewed. REVIEW made no repair and did
not change Git history.

## REVIEW Receipt

```text
ROLE: REVIEW
STATUS: BLOCKED
ARTIFACT: dispatch/workstreams/development-baseline-consolidation/REVIEW.md
FILES CHANGED BY REVIEW: dispatch/workstreams/development-baseline-consolidation/REVIEW.md only
CHECKS / EVIDENCE: Independent PLAN, T001-T004, PYRIGHT, COMPATIBILITY, VALIDATION, complete diff, source, API/generated-schema, persistence, safety, and frontend-boundary review; git diff --check PASS; locked Pyright baseline and focused before/after evidence corroborated.
FINDINGS / CONCERNS: F-001 and F-002 are IMPORTANT / PRODUCT / approved-scope DEFECT findings covering the README OANDA-token prerequisite and the COMPATIBILITY generated-client typing claim; two MINOR / TOOLING / NEW SCOPE baseline concerns are recorded; no CRITICAL finding and no runtime/trading/safety regression identified. No credentialed or capital-capable operation occurred.
```
