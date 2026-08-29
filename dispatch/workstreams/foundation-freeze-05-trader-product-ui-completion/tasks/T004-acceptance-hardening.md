# T004 — Acceptance Hardening

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `foundation-freeze-05-trader-product-ui-completion`
- **Branch:** `solo/foundation-freeze-05-trader-product-ui-completion`
- **Owner:** fresh `solo-flow-worker`

## Objective

Close focused regressions for the complete historical-research workstation:
states, navigation, hidden technical details, immutable evidence, and bounded
query behavior. Run the quality gates and perform the required Local Host
structured browser acceptance for the end-to-end flow.

## Dependencies

- T001, T002, and T003 must each be `DONE` before this task starts.

## Required checks

- Existing plus new/changed frontend tests and changed API contract/query tests.
- Fresh generated OpenAPI client if the public contract was touched.
- `npm run check:web` and relevant backend quality gates.
- Local Host discover → accessibility snapshot → one interaction at a time →
  bounded verification for StrategyVersion handoff, setup readiness,
  Experiment list/detail, result, Trade evidence/lineage, comparison, console
  errors, and failed requests. Use screenshots only as supplemental evidence.
- Preserve automated coverage for failed and zero-Trade states.
- Remediation: add bounded browser assertions for Trade Strategy evidence, Risk
  decision, Orders/Fills, execution lineage, and comparison `Inspect Trades`
  navigation, then rerun the equivalent browser acceptance.
- Remediation continuation: add the minimal root `npm start` alias to the
  existing `start:web` command so the required Local Host MCP harness can launch
  the built web app; do not change application behavior or dependencies.
- Validation remediation: align invalid-snapshot E2E assertions with explicit
  ambiguity blocking and make handoff/comparison fixture expectations
  deterministic for the available completed rows.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/foundation-freeze-05-trader-product-ui-completion/tasks/T004-acceptance-hardening.md
FILES CHANGED: package.json; backend/tests/e2e_seed.py; tests/e2e/experiment-workflow.spec.ts; frontend/tests/experiment_results.test.tsx
CHECKS / EVIDENCE: Added the minimal root package script alias `"start":"npm run start:web"`; no dependencies or application behavior changed. Updated stale StrategyVersion/DatasetSnapshot E2E locators, made the stateful workflow serial, and added bounded browser assertions for visible Strategy evidence, TradeIntent rationale/setup facts, Risk decision approval, opened execution lineage, Orders/events, Fills, and non-empty execution facts. The comparison flow now clicks `Inspect Trades` and verifies the destination URL's `#trades-heading` anchor and visible Trades heading. Validation remediation now keeps the invalid fixture's authoritative coverage facts distinct from the valid zero-Trade fixture so its sparse execution is selectable and fails coverage as intended. The seed also runs two canonical completed Experiments against the same authoritative snapshot, while the E2E assertion enforces the existing 2–4 completed comparison rule. The complete workflow passed 6/6 with a dedicated PostgreSQL test database, loopback API/web ports 8011/3011, and two workers; no unexpected console errors, failed responses, or request failures were observed. `npm run test:web` passed 30 tests across 12 files; frontend typecheck and production build passed; targeted ESLint, Prettier, Ruff, Python compileall, and `git diff --check` passed. Generated fixture output was restored after the run.
FINDINGS / CONCERNS: DONE_WITH_CONCERNS — existing repository-wide format/Ruff/pyright diagnostics documented by VALIDATION remain outside this remediation; T002's separate integration-test remediation was not changed.
```
