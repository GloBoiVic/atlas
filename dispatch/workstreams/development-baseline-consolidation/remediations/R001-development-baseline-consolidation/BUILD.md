# R001 - Development Baseline Consolidation Remediation BUILD

- **Remediation ID:** `R001`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `development-baseline-consolidation`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `611fe10b9b596f9e48339f305b99023d402c4514`
- **Origin:** `dispatch/workstreams/development-baseline-consolidation/REVIEW.md`
- **Origin findings:** F-001 and F-002
- **Finding severity:** `IMPORTANT / PRODUCT / DEFECT`
- **Related original tasks:** T001, T003

## Approved Requirement Or Invariant Violated

- Repository guidance must accurately describe guarded OANDA Practice PAPER capability and
  its setup prerequisites without weakening non-authorization or capital-boundary guidance.
- The compatibility inventory must accurately record API/generated-surface responsibility for
  each seam so later compatibility decisions are not based on false contract facts.

## Exact Remediation Outcome

- Correct the README prerequisite wording so it states that an OANDA Practice token is needed
  for external historical-data calls and guarded PAPER runtime/broker reads that use OANDA;
  retain explicit language that credentials and startup do not authorize trading and that
  PAPER activation remains separately guarded.
- Correct the generated-client/API description in `COMPATIBILITY.md`: the current generated
  client does not provide typed string members for Experiment result/metric schema values;
  those fields are exposed through opaque `unknown` additional payload data. Preserve the
  fact that the API payload can contain the values and do not change or regenerate the client.

## Affected Implementation Seams

- `README.md` prerequisites and adjacent PAPER/runtime setup guidance.
- `dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md` Experiment
  result and metric schema API/generated-surface entries.

No application implementation, API schema, generated client, persistence, or trading seam is
authorized by this remediation.

## Explicit Out Of Scope

- No Strategy, Risk, execution, reconciliation, protection, activation, broker-authority, or
  financial semantic changes.
- No API contract change, generated-client regeneration, migration, database reset, persisted
  data/evidence rewrite, credential operation, OANDA/broker request, runtime start, or PAPER
  activation/reconciliation/mutation.
- No broad documentation rewrite, Pyright cleanup, frontend cleanup, or GBP/JPY work.

## Regression Evidence Required

- Verify the corrected README claims against current runtime/API/provider code and existing
  non-authorization/capital-boundary guidance.
- Verify the corrected compatibility statements against `backend/api/schemas.py`, the current
  generated client, API projection, and frontend payload typing.
- Run relevant documentation/source checks and `git diff --check`; confirm no application,
  schema, migration, generated, or persisted files changed.

## Worker Evidence

- R001 BUILD execution completed.
- `README.md:31` now requires an OANDA Practice token for both external historical-data API
  calls and guarded PAPER runtime or broker reads that call OANDA. Existing non-authorization,
  explicit PAPER activation, credential-handling, fail-closed, and capital-boundary wording
  remains in place at `README.md:9`, `README.md:135`, and `README.md:227-241`.
- `COMPATIBILITY.md:165-168` and `COMPATIBILITY.md:191-196` now preserve that Experiment
  result/metric values can be present in API payloads while describing the generated client’s
  `unknown` additional-payload/index surfaces rather than typed string members.
- Source verification covered `backend/runtime/activation.py:695-704`,
  `backend/runtime/main.py:77-153`, `backend/api/app.py:196-203`,
  `backend/integrations/oanda/request.py:34-37`, `backend/api/schemas.py:486-490`,
  `frontend/lib/api.generated.ts:524-529,738-743`, `backend/api/experiments.py:294-310`,
  `backend/experiments/results.py:527-532`, and `frontend/lib/api-client.ts:5-7`.

### Immutable Completion Receipt

```text
ROLE: BUILD
STATUS: DONE
ARTIFACT: dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/BUILD.md
FILES CHANGED: README.md; dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md; this BUILD artifact only.
CHECKS / EVIDENCE: Obsolete README and generated-client string-claim searches returned no matches; corrected-claim searches matched. `npx prettier --check README.md dispatch/workstreams/development-baseline-consolidation/COMPATIBILITY.md dispatch/workstreams/development-baseline-consolidation/remediations/R001-development-baseline-consolidation/BUILD.md` PASS. `git diff --check` PASS. `git diff --no-index --check -- /dev/null` checks PASS for both untracked workstream documents. Final status/name audit confirms no R001 edit to application, API schema, generated client, provider/runtime, frontend, migration, or persistence files; pre-existing workstream changes were left untouched.
FINDINGS / CONCERNS: None. No migration, database reset, persisted/evidence rewrite, credential or OANDA/broker request, runtime start, PAPER operation, or capital-capable action occurred.
```
