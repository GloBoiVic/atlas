# Atlas Phase 6 — Strategy Iteration: Plan

## Control

- **Classification:** Architecture (R1)
- **Status:** Implementing sequentially on READY feature branch
- **Workstream root:** `dispatch/workstreams/phase-6-strategy-iteration/`
- **Requested outcome:** An authoritative, implementation-ready architecture blueprint for manual parameter iteration, StrategyVersion history/provenance, and comparison of immutable Experiment results. No code changes.
- **Constraints:** Preserve Phase 5 Experiment behavior, immutability, metric authority, simulation/no-lookahead/Risk/execution/accounting semantics, canonical domain language, local-first deployment, and existing API/UI boundaries. Do not introduce optimization, ranking, recommendations, persisted comparison state absent demonstrated need, SDK, or PAPER/LIVE changes.

## Acceptance criteria for the blueprint

1. Defines StrategyVersion history and Atlas-owned trader-facing identity/provenance, with Git optional only.
2. Defines typed supported-parameter iteration without a new StrategyVersion; methodology/source behavior changes produce a new immutable StrategyVersion.
3. Defines a read/composition comparison workflow for multiple immutable Experiments with configuration, parameter, Risk, DatasetSnapshot/date-range, simulation-assumption, and existing authoritative core metric differences.
4. Defines deterministic, explainable comparability warnings without ranking or recommendations.
5. Specifies API contracts, persistence changes only when necessary, UI routes/views, ordered implementation tasks, validation matrix, rollback implications, assumptions, exclusions, and final acceptance criteria.
6. Identifies any material conflict with current Atlas context rather than silently changing architecture.

## Ordered tasks and assignments

| Order | Status | Assignment | Exact artifact | Required inputs | Forbidden dispatch paths | Model |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Completed | Explore agent: inspected Phase 5 implementation/contracts and relevant context; reported extension points and two material conflicts. Read-only. | `dispatch/workstreams/phase-6-strategy-iteration/EXPLORATION.md` | `ACTIVE.md`, this `PLAN.md`, relevant `context/` docs, indexed code | All other `dispatch/` paths, especially prior-workstream artifacts | standard |
| 2 | Completed | Architect agent: produced the authoritative blueprint. It reconciles the reported tensions without reopening v1 or Phase 5: append a separately fingerprinted parameter-enabled v2; keep `expiry_window` fixed. | `dispatch/workstreams/phase-6-strategy-iteration/ARCHITECTURE.md` | `ACTIVE.md`, this `PLAN.md`, `EXPLORATION.md`, cited relevant context and code | All other `dispatch/` paths | standard architecture agent |
| 3 | Completed | Orchestrator presented the blueprint; user explicitly approved the Phase 6 scope and workflow on 2026-08-23. This approval does not authorize Git mutation. | N/A | `ARCHITECTURE.md` | N/A | gpt-5.6-terra |
| 4 | Completed | Worktrees agent created the approved local feature branch after separate user confirmation and issued a valid READY receipt. | `dispatch/workstreams/phase-6-strategy-iteration/READY.md` | Approved `ARCHITECTURE.md`, this plan, selected checkout context | All other `dispatch/` paths | standard |
| 5 | Completed | Backend builder added v2 source/indicators/tests; v1 remains byte-identical; focused validation passed. | `TASK-01-strategy-v2.md` | `ARCHITECTURE.md` §§57–67, 78–100, 136–154, 331–334, 343–368; `READY.md` | All other `dispatch/` paths | backend |
| 6 | Completed | Backend builder completed exact multi-version registration/catalog synchronization. Narrow test-config repair was approved after research classified the hardcoded `u` role as stale test config; API health 4 passed, Task 02 strategy/persistence 49 passed, Ruff passed. | `TASK-02-registry-catalog.md`, `TASK-02-TEST-CONFIG-REPAIR.md` | `ARCHITECTURE.md` §§102–116, 277–285, 331–341, 343–368; `READY.md`, Task 01 report | All other `dispatch/` paths | backend |
| 7 | Completed | Backend builder added Strategy catalog/history reads and typed routes; focused checks passed. Integration validation is blocked by the local `atlas_test` database missing `instruments`, to be handled in final validation. | `TASK-03-strategy-history-api.md` | `ARCHITECTURE.md` §§114–116, 231–257, 271–285, 331–341; `READY.md`, Tasks 01–02 reports | All other `dispatch/` paths | backend |
| 8 | Completed | Full-stack builder implemented typed schema-derived parameter controls and additive option metadata; focused backend/frontend validations passed. | `TASK-04-experiment-parameters.md` | `ARCHITECTURE.md` §§145–154, 254–257, 295–300, 331–341; `READY.md`, Tasks 01–03 reports | All other `dispatch/` paths | frontend |
| 9 | Completed | Backend builder implemented the stateless comparison service/route with immutable typed diffs and canonical metric envelopes; 196 passed, 1 skipped, Ruff/compile passed. | `TASK-05-comparison-api.md` | `ARCHITECTURE.md` §§118–132, 160–285, 331–341, 343–368; `READY.md`, Tasks 01–04 reports | All other `dispatch/` paths | backend |
| 10 | Completed | Frontend builder implemented Strategy history and comparison UI/client integration; focused tests 7 passed; lint/typecheck passed; format drift is pre-existing. | `TASK-06-strategy-comparison-ui.md` | `ARCHITECTURE.md` §§287–309, 331–341, 343–368; `READY.md`, Tasks 01–05 reports | All other `dispatch/` paths | frontend |
| 11 | Blocked | Tester completed validation and recorded B1 generated-client freshness, B2 comparison query mismatch, and B3 build Suspense failures. User approved narrow remediation. | `VALIDATION.md` | Full `ARCHITECTURE.md`, `READY.md`, all completed task reports | All other `dispatch/` paths | tester |
| 11a | In progress | Frontend builder: narrowly remediate B1–B3, then record task receipts. | `TASK-07-validation-remediation.md` | `VALIDATION.md`, `ARCHITECTURE.md`, `READY.md`, Task 05–06 reports | All other `dispatch/` paths | frontend |
| 12 | Pending | Reviewer: evaluate implementation and validation against the authoritative blueprint (R1). | `REVIEW.md` | Full `ARCHITECTURE.md`, `VALIDATION.md`, all task reports | All other `dispatch/` paths | reviewer |
| 13 | Pending | Documenter: close only after all gates pass; update root completion index and successful remember receipt, then clear ACTIVE. | root `dispatch/COMPLETED.md` and `dispatch/ACTIVE.md` | `REVIEW.md`, `VALIDATION.md`, approved blueprint, task reports | All other workstream artifacts | documenter |

## Model decision log

- 2026-08-23: No premium-model work authorized or needed for bounded read-only exploration.
- 2026-08-23: Architecture has substantial downstream product risk due to immutable StrategyVersion provenance and parameter-iteration conflicts, but a premium model is not required: the standard architecture agent has the complete user brief, governing context, and explicit exploration evidence. Use it; require it to surface, not silently resolve, material conflicts.
- 2026-08-23: User explicitly requested reviewer-premium after tester failures. Premium verification is justified by downstream-risk to Experiment immutability, metric authority, and API/UI contract correctness; a cheaper tester repeatedly failed to produce terminal validation evidence. The reviewer-premium agent will run the full validation matrix and record its evidence in its owned `REVIEW.md`.

## Scope lock

The Architect must stop and report a material conflict. It may not silently reopen Phase 5 simulation semantics, no-lookahead, Risk, execution, accounting, metric definitions, or Experiment immutability.
