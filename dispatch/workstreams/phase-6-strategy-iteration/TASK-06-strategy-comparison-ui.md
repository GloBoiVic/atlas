# Task 06 — Strategy and Comparison UI

## Status

**COMPLETE** — implemented the Phase 6 frontend routes and transient comparison
workspace. No backend, persistence, migration, optimization, ranking, or
PAPER/LIVE changes were made by this task.

## Changes

- Enabled the horizontal Strategies navigation and added:
  - `/strategies` catalog view;
  - `/strategies/[strategyKey]` immutable StrategyVersion history view with
    Atlas version identity, provenance, parameter schema, fixed five-bar
    expiry, usage, warm-up, and local availability.
- Added typed `listStrategies`, `getStrategy`, and `compareExperiments` client
  methods and refreshed the generated contract declarations for the existing
  Strategy and comparison responses/routes.
- Added completed-only selection to `/experiments`, a bounded two-to-four
  `Compare selected` action, and explicit non-completed eligibility messaging.
- Added `/experiments/compare` using repeated ordered `experimentId` query
  parameters. The view presents identities, deterministic warnings,
  configuration differences, canonical metric envelopes, and links to result
  and Trade views in the approved order.
- Preserved neutral language: no ranking, winner semantics, recommendations,
  scores, deltas, or frontend metric calculations. Responsive tables scroll
  horizontally and warning/configuration sections remain visible.
- Added focused UI coverage for Strategy history and comparison ordering,
  warnings, fixed methodology display, and unavailable metric states.

## Validation receipts

- `npm run lint:web` — **passed**.
- `npm run typecheck:web` — **passed**.
- Focused frontend tests (`experiment_list.test.tsx`,
  `experiment_results.test.tsx`, `strategy_comparison.test.tsx`) — **7 passed**.
- `npm run format:check:web` — implementation files passed; the command remains
  **blocked by pre-existing `tests/e2e/.fixtures.json` formatting drift**, which
  is outside this task and was not modified.

## Scope / blockers

No material deviation from ARCHITECTURE §§287–309, 331–341, 343–368. The
format-check receipt has the isolated unrelated fixture failure noted above;
focused lint, typecheck, and tests pass.
