# Documentation and Context Reset

## Outcome

Replace the current permanent documentation/context hierarchy with a small,
implementation-grounded surface:

```text
AGENTS.md
README.md
DOMAIN.md
dispatch/
  ACTIVE.md
  COMPLETED.md
  MODEL-LOG.md
  workstreams/
```

The reset is repository maintenance only. It must not change Atlas application
behavior, tests, schemas, migrations, generated contracts, frontend behavior,
runtime behavior, or any PAPER workstream state.

## Classification and authority

- **Classification:** `Feature` — permanent documentation/context migration;
  no application implementation.
- **Baseline:** `main` at `e671190ae4a77282367f2cecfa27ef45a375add1`.
- **Current branch:** `solo/documentation-context-reset` in the separate clean
  worktree `/Users/vike/Desktop/atlas-documentation-context-reset`.
- **GIT START:** completed from `main` at the recorded baseline after explicit
  developer approval. The original dirty PAPER worktree was not altered.
- **Current phase:** `READY_FOR_USER — BUILD, VALIDATE, and REVIEW complete`.
- **Approval:** explicit developer approval was received to proceed with this
  PLAN and to create the separate clean worktree/branch.
- **Tasks:** `T001` is `DONE`; its canonical receipt is
  `dispatch/workstreams/documentation-context-reset/tasks/T001-documentation-migration.md`.
- **Validation:** `PASS`; canonical receipt is
  `dispatch/workstreams/documentation-context-reset/VALIDATION.md`.
- **Review:** `PASS`; canonical receipt is
  `dispatch/workstreams/documentation-context-reset/REVIEW.md`.
- **Active-workstream exception:** the developer explicitly authorized this
  separate maintenance workstream while `dispatch/ACTIVE.md` continues to own
  `paper-01`. This plan must not modify, resume, close, remediate, or derive
  permanent context from `paper-01`.
- **Source rule:** permanent docs are derived from committed `main` at the
  recorded baseline, executable code/tests/schema/migrations at that baseline,
  and durable domain language. Uncommitted PAPER paths are excluded evidence.

## Current Git state (verified before implementation)

- **Branch:** `main`.
- **HEAD:** `e671190ae4a77282367f2cecfa27ef45a375add1`.
- **Uncommitted PAPER changes physically present:** yes. Tracked PAPER-related
  edits, untracked PAPER source/tests/migrations, and untracked PAPER dispatch
  artifacts are present in this worktree.
- **Other uncommitted paths:** `.codegraph/.gitignore` and
  `frontend/.env.local` are also present and must not be altered.
- **Required implementation baseline:** a clean checkout of committed `main`
  at the approved baseline. No reset, stash, commit, clean, merge, branch
  switch, or other operation has been performed by this workstream.

The clean BUILD worktree was then verified as:

```text
path   /Users/vike/Desktop/atlas-documentation-context-reset
branch solo/documentation-context-reset
HEAD   e671190ae4a77282367f2cecfa27ef45a375add1
status clean
```

The exact porcelain receipt at planning time was:

```text
 M backend/api/app.py
 M backend/api/schemas.py
 M backend/config.py
 M backend/domain/__init__.py
 M backend/domain/strategy.py
 M backend/execution/__init__.py
 M backend/execution/contract.py
 M backend/execution/fill_application.py
 M backend/integrations/oanda/__init__.py
 M backend/integrations/oanda/source.py
 M backend/persistence/__init__.py
 M backend/persistence/lifecycle_locks.py
 M backend/persistence/models.py
 M backend/persistence/trading_repository.py
 M backend/risk/__init__.py
 M backend/risk/service.py
 M backend/runtime/__init__.py
 M backend/runtime/main.py
 M backend/strategies/production.py
 M backend/tests/integration/test_migrations.py
 M backend/tests/test_migration_revision.py
 M dispatch/ACTIVE.md
?? .codegraph/.gitignore
?? backend/api/paper.py
?? backend/domain/broker.py
?? backend/integrations/oanda/execution.py
?? backend/integrations/oanda/normalization.py
?? backend/integrations/oanda/readonly.py
?? backend/market_data/live.py
?? backend/persistence/migrations/versions/0022_paper_persistence_lifecycle.py
?? backend/persistence/migrations/versions/0023_analytical_frontier.py
?? backend/persistence/migrations/versions/0024_authorization_fence.py
?? backend/persistence/migrations/versions/0025_restart_continuity.py
?? backend/persistence/migrations/versions/0026_oanda_transaction_receipts.py
?? backend/persistence/paper_repository.py
?? backend/persistence/timestamps.py
?? backend/runtime/coordinator.py
?? backend/runtime/production.py
?? backend/runtime/reconciliation.py
?? backend/runtime/store.py
?? backend/tests/integration/test_analytical_frontier_persistence.py
?? backend/tests/integration/test_authorization_fence.py
?? backend/tests/integration/test_runtime_store_reconciliation.py
?? backend/tests/integrations/test_oanda_execution.py
?? backend/tests/integrations/test_oanda_paper_contracts.py
?? backend/tests/market_data/test_live_frontier.py
?? backend/tests/persistence/test_paper_persistence.py
?? backend/tests/risk/test_paper_service.py
?? backend/tests/runtime/test_analytical_frontier.py
?? backend/tests/runtime/test_coordinator.py
?? backend/tests/runtime/test_paper_account_authorization.py
?? backend/tests/runtime/test_paper_api.py
?? backend/tests/runtime/test_production_runtime.py
?? dispatch/workstreams/paper-01/ARCHITECTURE.md
?? dispatch/workstreams/paper-01/IMPLEMENTATION-CLOSURE.md
?? dispatch/workstreams/paper-01/PLAN.md
?? dispatch/workstreams/paper-01/REVIEW.md
?? dispatch/workstreams/paper-01/VALIDATION.md
?? dispatch/workstreams/paper-01/tasks/C001-analytical-frontier.md
?? dispatch/workstreams/paper-01/tasks/C002-authorization-fence.md
?? dispatch/workstreams/paper-01/tasks/C003-restart-continuity.md
?? dispatch/workstreams/paper-01/tasks/C004-protection-cursor.md
?? dispatch/workstreams/paper-01/tasks/T001-contracts-data.md
?? dispatch/workstreams/paper-01/tasks/T002-persistence-lifecycle.md
?? dispatch/workstreams/paper-01/tasks/T003-risk-execution.md
?? dispatch/workstreams/paper-01/tasks/T004-runtime-reconciliation.md
?? dispatch/workstreams/pre-paper-audit/AUDIT.md
?? frontend/.env.local
```

## Scope

### In scope

1. Write a compact `AGENTS.md` that routes work to the correct authority and
   gives only current repository operating guidance.
2. Write a compact `README.md` that describes the current supported workflow,
   setup, migrations, runtime commands, and validation commands.
3. Add `DOMAIN.md` containing implementation-independent, cross-cutting Atlas
   trading laws.
4. Remove stale, duplicated, speculative, or superseded permanent context and
   status files listed in the exact inventory below.
5. Verify that current active/root authority docs do not point readers at the
   deleted context hierarchy.

### Out of scope

- All paths in the current dirty PAPER set.
- `dispatch/ACTIVE.md` content or status.
- `dispatch/workstreams/paper-01/**` and `dispatch/workstreams/pre-paper-audit/**`.
- Any completed workstream artifact rewrite merely because it names an old
  context path.
- Application code, tests, fixtures, migrations, generated API clients,
  frontend code, configuration, dependencies, secrets, or Git history.
- New ADRs, a replacement `docs/` tree, `legacy/` or `archive/` trees, or
  speculative architecture/framework documentation.

## Exact permanent-file inventory

### Retain and rewrite

| Path | Proposed action |
| --- | --- |
| `AGENTS.md` | Rewrite to routing, authority, progressive context loading, current scope, essential invariants, and commands; target ≤100 lines. |
| `README.md` | Rewrite to current capability boundary, prerequisites, setup, migrations, supported historical workflow, stack commands, and validation. |

### Add

| Path | Proposed action |
| --- | --- |
| `DOMAIN.md` | Add only durable cross-cutting trading laws supported by committed `main` or explicitly labeled as a future safety boundary; target ≤120 lines. |

### Delete

```text
CURRENT.md
memory.md

context/index.md

context/architecture/accounting-model.md
context/architecture/architecture.md
context/architecture/database.md
context/architecture/domain-model.md
context/architecture/market-data-model.md
context/architecture/repository-structure.md
context/architecture/runtime-model.md
context/architecture/safety-model.md
context/architecture/strategy-contract.md
context/architecture/strategy-setup.png
context/architecture/tech-stack.md

context/product/north-star.md
context/product/product-principles.md
context/product/vision.md

context/roadmap/roadmap.md

context/features/dashboard.md
context/features/deployment.md
context/features/execution.md
context/features/experiment-comparison.md
context/features/experiment-results.md
context/features/experiments.md
context/features/historical-data.md
context/features/journal.md
context/features/reconciliation.md
context/features/reference-strategy.md
context/features/risk-management.md
context/features/strategy-management.md
context/features/trading-accounts.md

context/design/design.md
context/design/ui-tokens.md
context/design/visual-guide.md
context/design/atlas-compare-experiments-page.png
context/design/atlas-deployments-page.png
context/design/atlas-experiment-run-page.png
context/design/atlas-experiments-detail-page.png
context/design/atlas-experiments-page.png
context/design/atlas-journal-detail-page.png
context/design/atlas-journal-page.png
context/design/atlas-overview-page.png
context/design/atlas-strategies-details-page.png
context/design/atlas-strategies-page.png

context/development/agent-workflow.md
context/development/coding-standards.md
context/development/skills.md

dispatch/ARCHITECTURE.md
dispatch/DECISIONS.md
dispatch/EXPLORATION.md
dispatch/PLAN.md
dispatch/REVIEW.md
dispatch/TASKS.md
```

The `context/` deletion is complete: the list above covers every currently
indexed `context/` file, including the architecture PNG and all design PNGs.

### Keep unchanged as dispatch records

| Path/group | Treatment |
| --- | --- |
| `dispatch/ACTIVE.md` | Keep byte-for-byte unchanged. It remains the canonical `paper-01` status and must not be redirected to this workstream. |
| `dispatch/COMPLETED.md` | Keep completion history unchanged. It is bookkeeping, not current authority; historical references to deleted context paths are permitted here. |
| `dispatch/MODEL-LOG.md` | Keep append-only model history unchanged. |
| `dispatch/PHASE-1-BLUEPRINT.md` | Keep unchanged historical record. |
| `dispatch/PHASE-1-READY.md` | Keep unchanged historical record. |
| `dispatch/PHASE-2-BLUEPRINT.md` | Keep unchanged historical record. |
| `dispatch/PHASE-2-EXPLORATION.md` | Keep unchanged historical record. |
| `dispatch/PHASE-2-READY.md` | Keep unchanged historical record. |
| `dispatch/PHASE-3-BLUEPRINT.md` | Keep unchanged historical record. |
| `dispatch/PHASE-3-EXPLORATION.md` | Keep unchanged historical record. |
| `dispatch/workstreams/**` | Keep all existing historical and active artifacts unchanged. Git history preserves their original context. |

## Exact merge map

### `AGENTS.md` receives

- Atlas identity and canonical terminology.
- Current repository map based on committed `main`.
- Authority order: product direction, domain laws, executable implementation,
  tests, schema/migrations, generated contracts, then historical dispatch.
- Progressive loading rule: read only the relevant implementation and domain
  material; do not bulk-load historical context.
- Current supported scope: historical EUR/USD Experiment workflow; PAPER/LIVE
  are not current supported capabilities at the committed baseline.
- Essential safety and Strategy-boundary routing, without duplicating the full
  domain model.
- Exact backend/frontend/database validation commands.

### `DOMAIN.md` receives

Only compact laws that survive implementation changes:

- canonical Atlas nouns and immutable `StrategyVersion` identity;
- deterministic Experiment inputs/results and reproducibility;
- UTC, completed-candle, no-lookahead, and duplicate-frontier semantics;
- native M15 analysis versus sparse M1 execution provenance;
- no fabricated, interpolated, or substituted market observations;
- pure Strategy boundary and centralized Risk boundary;
- Fill-derived exposure and broker authority when broker execution exists;
- unknown, stale, contradictory, or unreconciled financial state fails closed;
- no blind retry after uncertain order submission;
- protection and reconciliation prerequisites before resuming exposure.

The implementation must not present future PAPER/LIVE guarantees as current
capabilities. Any law not evidenced by committed `main` must be labeled as a
boundary/invariant rather than an implemented feature.

### `README.md` receives

- Prerequisites and environment setup from the existing working commands.
- PostgreSQL/Alembic lifecycle commands.
- Historical OANDA data → DatasetSnapshot → Experiment workflow.
- API, frontend, and optional runtime commands that exist on committed `main`.
- Current Strategy and historical execution semantics.
- Engineering validation commands from `pyproject.toml` and `package.json`.
- Explicit statement that PAPER/LIVE execution is not a supported committed-main
  workflow.

The README must not copy product vision, roadmap, design guidance, historical
phase narratives, or unfinished PAPER implementation details.

## Committed-main evidence boundary

The following candidates may be retained only after checking them against the
clean committed baseline, not against the dirty PAPER paths:

| Candidate law/capability | Required evidence source | Permanent-doc treatment |
| --- | --- | --- |
| Strategy purity and deterministic evaluation | committed `backend/domain/`, `backend/strategies/`, and Strategy tests | Keep as domain law and routing rule |
| StrategyVersion immutability/provenance | committed persistence models, migrations, and tests | Keep as domain law |
| Experiment reproducibility/result immutability | committed `backend/experiments/`, persistence, and tests | Keep as domain law and README boundary |
| Native M15 plus sparse M1 semantics | committed market-data/Experiment code and tests | Keep as domain/data law |
| No-lookahead/completed-bar frontier | committed Experiment clock/runner and tests | Keep as domain law |
| Historical OANDA capability | committed source/API/README/tests | Keep in README current workflow |
| PAPER/LIVE execution/reconciliation/protection | no dirty PAPER evidence may be used | Keep only as a clearly marked future safety boundary, never current capability |
| Product vision, roadmap, screenshots, and design tokens | no executable authority | Delete from permanent context; preserve historical dispatch records |

## Acceptance criteria for the planning phase (satisfied before BUILD)

- This PLAN records the exact inventory and proposed file actions.
- The plan explicitly treats `AGENTS.md`, `README.md`, `CURRENT.md`,
  `memory.md`, every `context/` category/file, `dispatch/ACTIVE.md`, and
  `dispatch/COMPLETED.md`.
- No permanent documentation has been edited.
- No PAPER path or PAPER status has been edited by this workstream.
- The current branch, HEAD, physical dirty PAPER state, and dirty paths are
  recorded.
- GIT START is recorded as complete only for the separate clean worktree; the
  original dirty PAPER worktree remains untouched.

## Lifecycle after BUILD

1. VALIDATE line limits, links, stale-path references in active/current docs,
   README command accuracy, and exact diff scope.
2. REVIEW independently checks the plan, inventory, diff, and preservation of
   PAPER and historical dispatch records.
3. Stop at `READY_FOR_USER`; no merge or cleanup without separate approval.

## Current phase / next action

`READY_FOR_USER — independent review passed.` The documentation migration is
complete on the clean worktree. Do not alter the original dirty PAPER worktree.
Merge, commit, push, or cleanup requires separate developer approval.
