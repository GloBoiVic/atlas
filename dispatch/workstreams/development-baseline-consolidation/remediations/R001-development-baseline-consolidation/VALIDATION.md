# R001 - Development Baseline Consolidation Remediation VALIDATION

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `development-baseline-consolidation`
- **Remediation:** `R001`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `main` at `611fe10b9b596f9e48339f305b99023d402c4514`
- **Validator:** independent VALIDATE
- **Validated:** `2026-09-10`
- **Origin:** `dispatch/workstreams/development-baseline-consolidation/REVIEW.md` findings F-001 and F-002

## Decision

`PASS`. Both originating IMPORTANT / PRODUCT / DEFECT findings are resolved in the
assigned documentation seams. No R001 PRODUCT, REGRESSION, or TOOLING defect remains.
The corrected claims were checked against current runtime/provider setup, API schema and
projection code, the unchanged generated client, and frontend payload typing. No application,
schema, generated-client, migration, database, persisted-data, evidence, trading, credential,
broker, runtime, or PAPER operation was performed or changed by R001 VALIDATE.

## Originating Findings

### F-001 - README OANDA prerequisite

**Result: PASS.** `README.md:31` now requires an OANDA Practice token for both external
historical-data calls and guarded PAPER runtime or broker reads that call OANDA. The claim is
supported by `backend/runtime/main.py:69-169`, which composes the OANDA historical source,
account, pricing, execution, protection, and reconciliation readers with the configured token;
`backend/api/app.py:99-130,192-204`, which wires the historical coordinator, reconciliation
reader, and OANDA-backed broker-state reader; and
`backend/integrations/oanda/request.py:34-37,100-124`, which rejects a missing/blank token and
sends authenticated observation requests. The historical source also rejects a missing token
at `backend/integrations/oanda/source.py:287-295`.

The non-authorization and separate-guard wording remains explicit at `README.md:9` and
`README.md:135`: startup, runtime startup, broker inspection, and configured credentials do
not authorize or activate trading, while PAPER activation requires explicit trader
authorization and runtime/reconciliation controls. The capital boundary remains explicit at
`README.md:227-241`. Current code corroborates the separate guard: activation requires token
and account configuration at `backend/runtime/activation.py:486-504,695-704`, the request
requires `ACTIVATE_PAPER` at `backend/runtime/activation.py:92-121`, local authority is
enforced by `backend/api/local_authority.py:134-167`, and the approval constants are fixed in
`backend/runtime/persistence_contracts.py:39-40,390-393`.

### F-002 - Compatibility generated-client claim

**Result: PASS.** `COMPATIBILITY.md:165-168` preserves that result and metric schema values
may be present in Experiment detail/provenance payloads while correctly describing them as
opaque generated-client payload data rather than typed string members. Its
`COMPATIBILITY.md:191-196` comparison entry likewise distinguishes the explicitly typed
`modelVersion` from the unknown-key `metricContract` and untyped additional Experiment detail
values.

The current boundary supports that description:

- `backend/api/schemas.py:486-490` defines `ExperimentReadResponse` with only typed `identity`
  and `extra="allow"`; `backend/api/schemas.py:583-597` defines comparison `metric_contract`
  as `dict[str, Any]`.
- `backend/api/experiments.py:247-310` projects `resultSchemaVersion`, and
  `backend/experiments/results.py:527-548` projects `resultSchemaVersion` and
  `metricSchemaVersion` in provenance. `backend/experiments/comparison.py:273-320` projects
  the result/metrics contract values into `metricContract`.
- `frontend/lib/api.generated.ts:481-529` types `metricContract` as an unknown-key map, and
  `frontend/lib/api.generated.ts:738-743` types `ExperimentReadResponse` through an unknown
  index signature. No typed `resultSchemaVersion` or `metricSchemaVersion` string members are
  present in the generated client.
- `frontend/lib/api-client.ts:5-7,230-231` deliberately types Experiment detail as
  `ExperimentPayload = Record<string, unknown>`; the result view consumes the opaque values
  through the existing helpers at `frontend/components/experiments/experiment-results.tsx:80-90,154-158`.

## Scope And Boundary Audit

- The R001 README correction is limited to the prerequisite sentence identified by immutable
  REVIEW F-001. Existing T001 capability, undeployed, non-authorization, and safety wording is
  preserved; no LIVE capability is introduced.
- The R001 compatibility correction replaces the false typed-string generated-client claim with
  the observed API-payload/unknown-surface distinction. The T003 classifications, retirement
  points, historical identifiers, and evidence/persistence cautions remain intact.
- The current worktree contains pre-existing T001-T004 implementation changes. The relevant
  API, provider, runtime-composition, generated-client, migration, and model paths were audited
  with the command below and produced no diff. The separate pre-existing
  `backend/persistence/database.py` diff is a T003 comment-only terminology change, and the
  pre-existing `backend/runtime/activation.py` diff is the T004 dead-forwarder removal; neither
  is an R001 change.
- No migration, database reset, persisted-data rewrite, evidence rewrite, API schema change,
  generated-client regeneration, OANDA request, credential read/change, runtime start, PAPER
  activation/reconciliation, broker mutation, or capital-capable operation occurred.

## Checks And Evidence

| Command                                                                                                                                                                                                                                                                                                                                                    | Result                                                                                                                   |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `npx prettier --check README.md dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/BUILD.md dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/VALIDATION.md` | PASS; all files use Prettier style                                                                                       |
| `npm run typecheck:web`                                                                                                                                                                                                                                                                                                                                    | PASS; TypeScript generated-client and frontend payload typing check completed with no diagnostics                        |
| `uv run --frozen ruff check backend/runtime/main.py backend/runtime/activation.py backend/api/app.py backend/api/paper.py backend/api/schemas.py backend/api/experiments.py backend/integrations/oanda/request.py backend/integrations/oanda/trades.py backend/experiments/results.py`                                                                     | PASS                                                                                                                     |
| `git diff --check`                                                                                                                                                                                                                                                                                                                                         | PASS; no tracked-worktree whitespace diagnostics                                                                         |
| `git diff --name-status 611fe10b9b596f9e48339f305b99023d402c4514 -- backend/api backend/integrations/oanda backend/runtime/main.py frontend/lib backend/persistence/migrations backend/persistence/models.py`                                                                                                                                              | No output; no R001 change in API, provider, runtime-composition, generated-client, migration, or persistence-model paths |
| `git diff --no-index --check -- /dev/null dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md`                                                                                                                                                                                                                                        | No whitespace diagnostics; normal non-zero no-index status for an untracked non-empty file                               |
| `git diff --no-index --check -- /dev/null dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/BUILD.md`                                                                                                                                                                                           | No whitespace diagnostics; normal non-zero no-index status for an untracked non-empty file                               |
| `git diff --no-index --check -- /dev/null dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/VALIDATION.md`                                                                                                                                                                                      | No whitespace diagnostics; normal non-zero no-index status for an untracked non-empty file                               |

## Findings

| Classification           | Result                                                                                                    |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| `PRODUCT / DEFECT`       | None; F-001 and F-002 are resolved.                                                                       |
| `REGRESSION / DEFECT`    | None identified.                                                                                          |
| `TOOLING / DEFECT`       | None identified by the R001 checks.                                                                       |
| `PRODUCT / NEW SCOPE`    | None.                                                                                                     |
| `REGRESSION / NEW SCOPE` | None.                                                                                                     |
| `TOOLING / NEW SCOPE`    | None from this remediation; inherited repository-wide baseline debt is outside R001 and was not reopened. |

## VALIDATE Receipt

```text
ROLE: VALIDATE
STATUS: PASS
ARTIFACT: dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/VALIDATION.md
FILES CHANGED: dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/VALIDATION.md only
CHECKS / EVIDENCE: F-001 and F-002 independently verified against current README, runtime/provider setup, API schema/projection, unchanged generated client, and frontend payload typing; Prettier, frontend typecheck, focused Ruff, tracked diff check, and untracked-document no-index checks passed with no whitespace diagnostics.
FINDINGS / CONCERNS: None. No PRODUCT, REGRESSION, or TOOLING defect; no NEW SCOPE finding; no application, persistence, credential, OANDA, runtime, PAPER, broker, or capital-capable operation occurred.
```
