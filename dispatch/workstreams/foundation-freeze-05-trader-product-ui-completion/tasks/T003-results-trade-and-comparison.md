# T003 — Results, Trade Evidence, and Comparison

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `foundation-freeze-05-trader-product-ui-completion`
- **Branch:** `solo/foundation-freeze-05-trader-product-ui-completion`
- **Owner:** fresh `solo-flow-worker`

## Objective

Implement the trader-facing result hierarchy, evidence/diagnostics placement,
progressive Trade lineage, and comparison workspace refinement using only
authoritative existing payloads. Make outcome/identity and canonical metrics
prominent, then equity/Trades, Strategy evidence/diagnostics, and secondary
technical provenance. Make Trade detail explain rationale/setup, Risk,
Order/Fill, protection, and outcome in that order. Improve comparison identity,
changed-fact emphasis, and navigation without ranking or recommending a winner.

## Constraints

- Depends on T001 and T002 shared presentation/navigation work.
- Preserve failed and zero-Trade states, unavailable/infinite metric states,
  bounded chart context, immutable evidence, and comparison limits/warnings.
- Do not infer Strategy patterns or recompute financial facts in the browser.
- Do not expose raw JSON, internal field names, or UUIDs in the normal path.
- No new comparison semantics, exports, rankings, or API redesign.

## Required checks

- Focused frontend tests for completed, failed, zero-Trade, Trade evidence/
  lineage, and comparison warning/no-winner states.
- Relevant frontend type/lint/test checks.
- Remediation: Strategy evidence and diagnostics must be visible in the normal
  result hierarchy; only technical provenance may remain collapsed. Add a
  regression asserting evidence is visible without opening Technical details.
- Review remediation: reorder Trade detail to rationale/setup → Risk decision →
  Order/Fill → protection → outcome, and add structural/browser sequence
  coverage while preserving authoritative facts.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/foundation-freeze-05-trader-product-ui-completion/tasks/T003-results-trade-and-comparison.md
FILES CHANGED: frontend/components/experiment-comparison.tsx; frontend/components/experiments/experiment-results.tsx; frontend/components/experiments/experiment-status.tsx; frontend/components/experiments/lineage.tsx; frontend/components/experiments/price-chart.tsx; frontend/components/experiments/trade-detail.tsx; frontend/components/experiments/trades-table.tsx; frontend/tests/experiment_results.test.tsx; frontend/tests/strategy_comparison.test.tsx; tests/e2e/experiment-workflow.spec.ts
CHECKS / EVIDENCE: Trade-detail remediation is complete: Strategy rationale/setup and chart context now precede Risk decision, visible Order and Fill hierarchy, collapsed execution-event lineage, Protection, and Outcome. Added structural Vitest and Playwright heading-order assertions. `npm run test:web` passed (12 files, 30 tests); focused Trade-detail Vitest passed (5 tests); frontend typecheck passed; targeted ESLint passed with 0 errors; targeted Prettier and `git diff --check` passed. Existing completed/failed/zero-Trade, metric-state, chart, Trade, and comparison coverage remains in the focused suite.
FINDINGS / CONCERNS: Focused Playwright execution was attempted but could not start in this environment: port 8000 was already in use, and an alternate-port attempt stopped because the configured database URL was absent/invalid (`database_url must use postgresql+psycopg`). No implementation or API concern found; rerun browser acceptance after the E2E database/server environment is available.
```
