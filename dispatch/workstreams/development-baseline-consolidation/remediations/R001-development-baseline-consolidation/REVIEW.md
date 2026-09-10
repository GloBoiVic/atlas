# R001 - Development Baseline Consolidation Remediation REVIEW

- **Status:** `PASS`
- **Role:** `REVIEW`
- **Workstream:** `development-baseline-consolidation`
- **Remediation:** `R001`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `main` at `611fe10b9b596f9e48339f305b99023d402c4514`
- **Reviewer:** independent REVIEW
- **Origin:** `dispatch/workstreams/development-baseline-consolidation/REVIEW.md` findings F-001 and F-002
- **Files changed by REVIEW:** this file only

## Assignment

Independently review the immutable originating REVIEW findings, the approved PLAN, the
original T001 and T003 receipts, R001 BUILD and VALIDATE artifacts, and the final README.md
and COMPATIBILITY.md state. Confirm that only the two approved documentation/inventory
corrections were made, both findings are resolved, and no application, API, generated-client,
persistence, evidence, trading, authority, or safety boundary changed.

The reviewer diagnoses and judges only. No implementation code, completed artifact, Git
history, credential, runtime, broker, or capital-capable operation was changed or performed.

## Decision

`PASS`. Originating findings F-001 and F-002 are closed. R001 is limited to the approved
README prerequisite correction and compatibility-inventory correction. There are no unresolved
`CRITICAL` or `IMPORTANT` findings, and no R001 `PRODUCT`, `REGRESSION`, or `TOOLING` defect.

## Exact Remediation Diff

- `HEAD` remains the approved base commit; there is no committed branch delta.
- The immutable pre-remediation VALIDATION recorded 15 tracked paths with 72 insertions and
  55 deletions. The current base-relative tracked diff is 15 paths with 73 insertions and
  56 deletions. The one-line net increase is the R001 README replacement.
- The README base-relative diff also contains the pre-existing T001 capability, undeployed,
  safety, runtime, and repository-guidance edits. The exact R001 change is the prerequisite
  sentence at `README.md:31`, replacing the obsolete `only` claim with the guarded PAPER
  runtime/broker-read OANDA requirement.
- `COMPATIBILITY.md` is an untracked T003 artifact and is absent from the base commit, so
  Git cannot render a base blob diff for that file. The immutable originating F-002 identifies
  the two pre-remediation passages. The final corresponding passages are the legacy-metric
  block at `COMPATIBILITY.md:165-168` and the result-identifier block at
  `COMPATIBILITY.md:191-196`. They replace the false typed-string generated-client
  description with the API-payload/opaque-`unknown` distinction and leave the inventory
  classifications, retirement points, and historical cautions intact.
- Current status shows no untracked application or test source. The other tracked paths are
  pre-remediation T001-T004 worktree changes, not R001 changes. In particular, the existing
  `backend/persistence/database.py` comment edit and `backend/runtime/activation.py` dead
  forwarder removal predate R001 and were left untouched.

## Finding Closure

### F-001 - README OANDA prerequisite

**Closed.** `README.md:31` now requires a real OANDA Practice token for external historical
data calls and for guarded PAPER runtime or broker reads that call OANDA. This matches the
current composition and provider boundaries:

- `backend/runtime/main.py:69-169` composes the historical source, account, pricing,
  execution, protection, and reconciliation readers with the configured token.
- `backend/api/app.py:99-130,192-204` wires the historical coordinator, reconciliation
  reader, and OANDA-backed broker-state reader.
- `backend/integrations/oanda/request.py:34-37,100-124` and
  `backend/integrations/oanda/source.py:287-295` reject missing token configuration before
  authenticated OANDA observation requests.

The non-authorization and capital-boundary wording remains explicit. `README.md:9,135`
states that startup, runtime startup, broker inspection, and configured credentials do not
authorize or activate trading; PAPER activation remains separately guarded by explicit trader
authorization and runtime/reconciliation controls. `README.md:227-241` retains the capital
boundary and credential-safety rules. `backend/runtime/activation.py:486-504,695-704` keeps
the separate activation configuration and explicit-request checks. No LIVE capability is
claimed.

### F-002 - Compatibility generated-client claim

**Closed.** `COMPATIBILITY.md:165-168` preserves that result and metric schema values can be
present in API detail/provenance payloads while describing the generated client as exposing
opaque additional `unknown` data, not typed string members. `COMPATIBILITY.md:191-196`
correctly distinguishes explicitly typed `modelVersion` from the unknown-key
`metricContract` and untyped additional Experiment detail values.

The current boundaries corroborate the inventory:

- `backend/api/schemas.py:486-490` defines `ExperimentReadResponse` with typed `identity`
  plus `extra="allow"`; `:583-597` defines comparison contract values as `dict[str, Any]`.
- `backend/api/experiments.py:262-310` projects `resultSchemaVersion` in Experiment detail
  and provenance. `backend/experiments/results.py:527-548` projects result and metric schema
  versions in provenance, and `backend/experiments/comparison.py:273-320` projects the
  values into `metricContract`.
- `frontend/lib/api.generated.ts:524-529` types `metricContract` as an unknown-key map and
  `:738-743` types Experiment detail additional fields through an unknown index signature.
  No typed `resultSchemaVersion` or `metricSchemaVersion` string members are present.
- `frontend/lib/api-client.ts:5-7,230-231` deliberately uses
  `ExperimentPayload = Record<string, unknown>` for Experiment detail.

The separate `snapshotSchema: string` generated configuration field in
`frontend/lib/api.generated.ts:609-627` is a typed snapshot-option contract and is not the
false Experiment result/metric claim from F-002.

## Findings

| Classification                    | Result                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------- |
| `CRITICAL / PRODUCT / DEFECT`     | None.                                                                                 |
| `IMPORTANT / PRODUCT / DEFECT`    | None. F-001 and F-002 are closed.                                                     |
| `MINOR / REGRESSION / DEFECT`     | None identified.                                                                      |
| `MINOR / TOOLING / DEFECT`        | None identified in R001.                                                              |
| `CRITICAL / PRODUCT / NEW SCOPE`  | None.                                                                                 |
| `IMPORTANT / PRODUCT / NEW SCOPE` | None.                                                                                 |
| `MINOR / REGRESSION / NEW SCOPE`  | None.                                                                                 |
| `MINOR / TOOLING / NEW SCOPE`     | Only inherited baseline debt below; it is accepted outside R001 and is not a blocker. |

## Scope And Boundary Audit

- The R001 changes are documentation and inventory text only. The base-relative path audit
  produced no change in `backend/api`, `backend/integrations/oanda`, `backend/runtime/main.py`,
  `frontend/lib/api.generated.ts`, `backend/persistence/migrations`, or
  `backend/persistence/models.py` attributable to R001.
- No API schema, generated client, persistence model, migration, persisted data, historical
  evidence, fixture, or generated contract was edited by R001. No result, metric, Strategy,
  Risk, execution, reconciliation, protection, activation, broker-authority, or trading
  semantic changed.
- No credential was read or changed, no OANDA or broker request was made, no API or runtime
  process was started, no PAPER activation/reconciliation/mutation occurred, and no
  capital-capable operation occurred during this review or the R001 validation chain.
- `git diff --check` and the relevant untracked-document no-index checks reported no
  whitespace diagnostics. `npx prettier --check` passed for the final README, compatibility,
  and R001 artifacts. `npm run typecheck:web` passed.

## Residual Accepted Baseline Debt

The following remain `MINOR / TOOLING / NEW SCOPE` baseline debt accepted by the approved PLAN
and the original workstream evidence. They are not R001 defects and do not block closure:

- Locked Pyright `1.1.411` reports 3,011 errors: 1,845 production and 1,166 test errors,
  with zero warnings and zero informations. The structured report is valid; exit status 1 is
  the diagnostic result, not a tool failure.
- Repository-wide Ruff reports 28 unrelated lint diagnostics. Ruff format reports 68 files
  that would be reformatted and 147 already formatted. Focused changed-surface checks pass.
- Two standalone current-worktree `npm run test:web` invocations exited 1 after all 146 tests
  passed because of a late Vitest `ReferenceError: window is not defined` in
  `home_page.test.tsx`. The focused test and required `npm run check:web` passed; this remains
  an intermittent harness-teardown concern.

## Closure And Readiness

- **Originating findings:** F-001 CLOSED; F-002 CLOSED. No remediation return is required.
- **Overall workstream:** **READY FOR EXPLICIT MERGE APPROVAL: YES.** Original T001-T004 are
  complete, the original validation is PASS, R001 validation is PASS, this review is PASS,
  and no unresolved Critical or Important finding remains. This is a recommendation at the
  approval gate; REVIEW did not commit, merge, or authorize Git history changes.
- **Market Capability 01 - GBP/JPY on OANDA Practice:** **READY TO BEGIN THE NEXT WORKSTREAM:
  YES**, after normal explicit merge approval and workstream closure. This means beginning
  that separately approved Critical workstream, not implementing GBP/JPY here. The current
  Atlas implementation remains the supported EUR/USD baseline, and R001 adds no GBP/JPY,
  multi-instrument, credential, runtime, or capital capability.

## REVIEW Receipt

```text
ROLE: REVIEW
STATUS: PASS
ARTIFACT: dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/REVIEW.md
FILES CHANGED: dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/REVIEW.md only
CHECKS / EVIDENCE: Independent review of originating F-001/F-002, PLAN, T001/T003 receipts, R001 BUILD/VALIDATE artifacts, current source/API/generated boundaries, exact base-relative diff, git diff checks, Prettier, and frontend typecheck; both originating findings closed and no R001 boundary change found.
FINDINGS / CONCERNS: No unresolved CRITICAL or IMPORTANT finding. Inherited Pyright/Ruff/Vitest baseline debt remains MINOR / TOOLING / NEW SCOPE and accepted; no credentialed, OANDA, runtime, PAPER, broker, or capital-capable operation occurred.
```
