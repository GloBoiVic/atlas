# PLAN — Phase 4 Historical Execution

## Status

**Phase:** Remediation — Task 06
**Implementation authorization:** Approved blueprint and valid `READY.md`; sequential implementation may begin.
**Workstream root:** `dispatch/workstreams/phase-4-historical-execution/`

## Scope

Discover and bound the next Atlas feature following Phase 3: historical execution realism beyond `PHASE3_OPEN_CHECKPOINT_V1`. The workstream must determine the smallest safe Phase 4 outcome from current product and architecture sources. It must not assume an implementation shape or expand into PAPER, LIVE, broker integration, API, UI, runtime, scheduling, reconciliation, or generalized infrastructure.

## Acceptance criteria

1. Exploration identifies the governing product, roadmap, feature, and architecture sources for Phase 4.
2. Exploration distinguishes existing Phase 3 behavior and known observations from candidate Phase 4 requirements.
3. The architect can produce an explicit, bounded blueprint with invariants, exclusions, risks, validation gates, ordered tasks, and a no-scope-creep boundary.
4. A human explicitly approves the architecture before a READY receipt, any Git-changing operation, or implementation dispatch.

## Ordered tasks and assignments

1. **Explore — complete:** `EXPLORATION.md` identifies the candidate historical-execution boundary, governing invariants, exclusions, current contracts, risks, and architect handoff.
2. **Architect — complete:** `ARCHITECTURE.md` contains the authoritative bounded implementation blueprint.
3. **Human approval — complete:** the Phase 4 blueprint and boundary were explicitly approved.
4. **Worktrees — complete:** `READY.md` verifies the approved feature branch, assigned cwd, SHA, scope, and required context.
5. **Task 01 — complete, persistence builder:** migration, models, protections, and focused repository support; receipt passed focused checks.
6. **Task 02 — complete, simulation builder:** chronological M1/M15 frontier contract; receipt passed focused checks.
7. **Task 03 — complete, execution builder:** pure deterministic execution behavior; receipt passed focused checks.
8. **Task 04 — complete, accounting builder:** atomic Fill/order-event/protection/accounting transitions; receipt passed focused checks.
9. **Task 05 — complete, experiment builder:** runner orchestration, results, and output fingerprint; receipt passed focused checks.
10. **Validation — failed:** HIGH reproducibility defect and required automated coverage gap; review is blocked.
11. **Task 06 remediation — complete, backend:** receipt passed focused and full-suite checks.
12. **Re-validation — complete, tester:** PASS; all remediation findings resolved.
13. **Review — blocked:** two Important findings require narrow remediation; closure is prohibited.
14. **Task 07 remediation — in progress:** wire approved slippage end-to-end and reconcile END_OF_EXPERIMENT terminal accounting only; own `TASK-07-review-remediation.md`.
11. **Review — pending, reviewer:** own `REVIEW.md` after validation passes.
12. **Closure — pending, documenter:** append root `COMPLETED.md`, clear `ACTIVE.md`, and preserve this workstream only after review passes and `/remember save` succeeds.

## Constraints

- Preserve all legacy dispatch history, including root Phase 1–3 artifacts and `first-historical-trade`.
- Do not modify application code, context documents, tests, branches, commits, Git history, or `.codegraph/` during exploration and architecture.
- Read only this workstream’s control artifacts plus required product/context/source files; do not scan unrelated dispatch history.
- Phase 3’s non-blocking OBS-1 and OBS-3 are inputs for planning, not implicit authorized remediation.
- Builders, testers, reviewers, and documenters must be sequential and only start after the required approval and READY receipt.

## Model metadata

| Task | Assigned role | Artifact | Model | Status |
| --- | --- | --- | --- | --- |
| Explore Phase 4 boundary | explore | `EXPLORATION.md` | openai/gpt-5.6-terra | complete |
| Architect Phase 4 blueprint | architect | `ARCHITECTURE.md` | openai/gpt-5.6-terra | complete |
| Worktrees readiness | worktrees | `READY.md` | openai/gpt-5.6-terra | complete |
| Task 01 persistence | backend | `TASK-01-persistence.md` | openai/gpt-5.6-terra | complete |
| Task 02 clock | backend | `TASK-02-clock.md` | openai/gpt-5.6-terra | complete |
| Task 03 simulated execution | backend | `TASK-03-simulated-execution.md` | openai/gpt-5.6-terra | complete |
| Task 04 Fill accounting | backend | `TASK-04-fill-accounting.md` | openai/gpt-5.6-terra | complete |
| Task 05 runner/results | backend | `TASK-05-runner-results.md` | openai/gpt-5.6-terra | complete |
| Validation | tester | `VALIDATION.md` | openai/gpt-5.6-terra | pass after remediation |
| Task 06 remediation | backend | `TASK-06-remediation.md` | openai/gpt-5.6-luna | complete |
| Review | reviewer | `REVIEW.md` | openai/gpt-5.6-terra | pending |
