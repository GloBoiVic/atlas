# Experiment Correctness, Historical Load, and UI Audit

## Control
- Classification: Architecture / Feature (R1)
- Status: Closed
- Workstream root: `dispatch/workstreams/experiment-correctness-load-ui-audit/`
- Requested outcome: Rebuild the Experiments frontend into real responsibility-based modules, remove the rejected legacy implementation, preserve behavior/API contracts, and validate against Atlas design and Local Host.
- Constraints: Preserve canonical domain language, immutable Experiment inputs/results, no-lookahead, Risk/execution/accounting semantics, and current architecture. No speculative caching or infrastructure. No Strategy rule changes.

## Context pointers
- `context/features/experiments.md`
- `context/features/experiment-results.md`
- `context/design/design.md`
- `context/design/visual-guide.md`
- `context/design/ui-tokens.md`
- `frontend/app/globals.css`
- `dispatch/workstreams/experiment-correctness-load-ui-audit/TASK-18-real-extraction.md`

## Ordered tasks
1. Explore existing routes, API orchestration, focused modules, tests, and design authority. **Completed**.
2. Produce authoritative frontend rebuild blueprint. **Completed**.
3. Obtain explicit human confirmation of blueprint and execution scope. **Completed**.
4. Implement stateful ownership in list, setup/load, status/results, metrics/charts, trades, detail/lineage, and shared formatter modules; delete `experiment-workflow-legacy.tsx`. **Completed**.
5. Update only frontend tests needed to preserve behavior and module ownership; do not change backend, API contracts, Strategy, or PAPER/LIVE. **Completed**.
6. Run tests, typecheck, lint, format/build checks; fix failures. **Completed**, with five pre-existing unrelated format warnings.
7. Start Local Host and validate discover → snapshot/read → interact → verify for list, setup/loading, results, and trade detail; inspect computed Atlas token styles, console, and network; fix observed issues and repeat. **Completed**.
8. Write one canonical validation receipt and review completion gates. **Completed** — `TASK-19-rebuild.md` is canonical; `REVIEW.md` is R1 PASS.

## Next action
Closed; completion indexed in `dispatch/COMPLETED.md` and memory saved.

## Definition of done
- Legacy file deleted; no responsibility module imports it.
- Each listed responsibility owns real implementation, not a re-export wrapper.
- Atlas semantic tokens and shadcn controls are used; no arbitrary palette classes or chart hex colors.
- Existing behavior/API/routes preserved; no Strategy/backend/PAPER/LIVE changes.
- Tests, typecheck, lint, and build pass.
- Local Host confirms real flows, token styles, readable charts, and no console/network errors.
- Canonical receipt records evidence without duplicating receipt details elsewhere.

## UI reference manifest

UI workers must inspect the written design guidance and these current screengrabs
before changing the Experiment setup/results UI. They are visual references, not a
replacement for the approved architecture or domain contracts:

- `context/design/design.md`
- `context/design/visual-guide.md`
- `context/design/ui-tokens.md`
- `context/design/atlas-experiment-run-page.png`
- `context/design/atlas-experiments-detail-page.png`
- `context/design/atlas-experiments-page.png`
- `frontend/app/globals.css` — required Atlas theme tokens and compatibility layer;
  UI changes must use these theme variables/classes rather than introducing new
  one-off colors.

## Approved refactor extension

The workstream remains open for the behavior-preserving Experiment frontend
decomposition requested by the user. This extension does not alter Strategy,
Experiment semantics, API contracts, backend behavior, or PAPER. It requires a
focused Explore → Architect → confirmation gate before implementation.
