# T002 — Shell, Strategy, and Experiment Setup

- **Status:** `DONE`
- **Role:** BUILD
- **Workstream:** `foundation-freeze-05-trader-product-ui-completion`
- **Branch:** `solo/foundation-freeze-05-trader-product-ui-completion`
- **Owner:** fresh `solo-flow-worker`

## Objective

Refine the shared workstation shell and the Strategy catalog/detail and
Experiment setup flow. Make historical research/Experiments clearly available
now while PAPER/LIVE remain future-only. Provide readable immutable
StrategyVersion context and a direct selected-version handoff. Reorder setup
around StrategyVersion → requested period/data readiness → configuration →
review/Run Experiment.

## Constraints

- Depends on T001 helpers/read shape; do not undo its response-equivalence work.
- Preserve durable historical-load status, coverage validation, immutable input
  capture, timeout/unknown handling, and all fail-closed run gates.
- No new Strategy methodology, current-default substitution, broker workflow, or
  API semantic changes.
- Technical keys, fingerprints, Git refs, schema names, and raw IDs remain
  progressively disclosed, not normal workflow labels.
- Use existing tokens/components; no dependency additions.

## Required checks

- Focused frontend tests for shell capability boundary, version handoff, setup
  stage order, readiness gates, and failed/unknown states.
- Relevant frontend type/lint/test checks.
- Review remediation: preserve authoritative StrategyVersion market, analysis,
  and price-component requirements in the configuration handoff; add regression
  coverage. Make DatasetSnapshot choices distinct using existing facts, or make
  ambiguity explicit and blocking; add multi-snapshot coverage.
- Validation remediation: correct the changed integration regression's use of
  `_complete_experiment()` so the requirement assertion executes, without
  weakening its API contract coverage.
- Validation remediation: regenerate `frontend/lib/api.generated.ts` from the
  current OpenAPI output using the repository generation path and prove the
  committed client is fresh.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE
ARTIFACT: dispatch/workstreams/foundation-freeze-05-trader-product-ui-completion/tasks/T002-shell-strategy-and-setup.md
FILES CHANGED: frontend/lib/api.generated.ts; dispatch/workstreams/foundation-freeze-05-trader-product-ui-completion/tasks/T002-shell-strategy-and-setup.md
CHECKS / EVIDENCE: Existing documented OpenAPI pipeline rerun with the validation PostgreSQL URL: create_app().openapi() → openapi-typescript 7.13.0 → Prettier. Byte comparison (`cmp -s frontend/lib/api.generated.ts /tmp/atlas-api-generated-freeze05.pretty.ts`) passed. `npm run typecheck:web` passed.
FINDINGS / CONCERNS: None. Generated client is byte-identical to fresh current OpenAPI output; no application semantics, tests, dependencies, or unrelated files changed.
```
