# Foundation Freeze 04 — Experiment Engine Simplification

## Outcome

Make Atlas have one clear authoritative historical Experiment execution path before
further product capability is built. The cleanup must make the current V2 path
obvious in source, remove executable superseded runner behavior, and preserve the
accepted Freeze 01–03 semantics and deterministic Experiment results.

## Classification

`Critical`

## Status and approval gate

- Status: `READY_FOR_USER — awaiting explicit merge approval`
- Developer approval received for this frozen PLAN/ARCHITECTURE.
- GIT START completed; implementation is authorized only within the approved task
  sequence and scope.

## Current repository state

- Inspected/base branch: `main`
- Execution branch: `solo/foundation-freeze-04-experiment-engine-simplification`
- Base SHA: `3521274d1f3f492176eec8be9434bc76c6e4341b`
- Pre-existing untracked files: `.codegraph/`, `frontend/.env.local`; preserve and
  exclude from all workstream changes.
- `dispatch/ACTIVE.md` is open for this workstream. GIT START is complete.

## Exploration findings

1. `backend/experiments/lifecycle.py` calls `ExperimentRunner.run`; the production
   application constructs that runner in `backend/api/app.py`.
2. `ExperimentRunner.run` routes only V2 simulation snapshots to `_run_v2` and
   rejects unsupported models. This is the intended entry point, but the same file
   still contains a complete private `_run_phase4` implementation that loads the
   snapshot's M1 members, calls `aggregate_m1_to_m15`, constructs a non-sparse clock,
   and is directly callable despite having no production caller.
3. The old `_run_phase4` implementation carries a second execution loop, separate
   diagnostics/comparison seam, and legacy Phase 4 model assumptions. It is the
   clearest superseded executable Experiment path and is a primary cleanup target.
4. `backend/experiments/results.py` has a V1 read branch that calls
   `MarketDataService.derive_m15`, while V2 reads persisted native M15 membership.
   This is a legacy result/chart compatibility branch, not the V2 runner, but it is
   still executable through result inspection and must either be removed for the
   undeployed product or isolated behind an explicitly non-authoritative legacy-read
   boundary. The architecture decision must preserve no accidental new-Experiment
   use of it.
5. `backend/market_data/ingestion.py` still exposes legacy `load_missing`,
   `create_snapshot`, `load_v2_incremental`, and `derive_m15` surfaces. Freeze 03
   already declares V2 `load_v2` and native M15/M1 products authoritative; cleanup
   must distinguish read-only CLI/migration diagnostics from code reachable from new
   Experiment creation/result execution before removing anything. The unreferenced
   `current_m15` helper also derives M15 from current M1 and is not used by the
   current historical-load coordinator.
6. `backend/domain/strategy.py` still supports the old state shape: schema 1,
   `Phase.AWAITING_CONFIRMATION`, and `window_bars`. The current production
   `EMA Sweep Confirmation Break v2` uses schema 2, `REFERENCE_IDENTIFIED` →
   `ARMED`, `watch_bars`, and immediate same-bar sweep/confirmation. The old
   `ema_sweep_engulfing.py` and `ema_sweep_engulfing_v2.py` implementations are not
   registered by production and are only test-referenced in the inspected tree.
7. The current Strategy contract also still permits `EntryPolicy.IMMEDIATE` and
   legacy `expiry_time`/`expiry_bars` persistence fields. The current reference
   Strategy uses `PRICE_TRIGGERED` with received-bar expiry. Any removal must be
   proven not to move Strategy, Risk, execution, accounting, or persistence
   ownership and must account for immutable historical facts rather than silently
   rewriting them.
8. Current V2 runner code already uses native M15 MID analytical members, sparse M1
   BID/ASK execution observations, `SimulationClock`, canonical Risk, simulated
   execution, Fill application, Position/Trade accounting, and V2 result completion.
   Those boundaries are accepted and are not redesign targets.

## Reconciled architecture decisions

The ARCHITECTURE.md role artifact freezes the following decisions:

- Keep `ExperimentRunner.run → _run_v2` as the sole new-Experiment execution path.
- Remove the unreachable `_run_phase4` execution loop, `_open_and_close`, and only
  the diagnostics, imports, and composition seams made dead by that removal. Rename
  the shared terminal method to a V2-neutral name without changing ordering.
- Keep immutable V1 result/chart reads only behind an explicit private read-only
  boundary. V2 reads use persisted native M15 membership and never call the V1
  helper. No new V1 snapshot creation or acquisition/write command remains.
- Remove obsolete V1 acquisition/write methods, the uncalled `current_m15` helper,
  the public `derive_m15` aggregation alias, and their old CLI commands/tests as
  specified by the architecture. Retain `aggregate_m1_to_m15` only for the private
  immutable V1 read boundary.
- Replace the V2 runner's pending-entry tuple with a private frozen/slotted
  `_PendingPriceTrigger` handoff. Strategy state remains authoritative for the
  five W1–W5 post-confirmation execution windows and the W6 SEARCHING/reset
  transition; the structure owns no clock or second watch counter. Preserve the
  existing V2 `EntryPolicy.IMMEDIATE` behavior and tests; any future removal
  requires a separate explicit contract decision.
- Remove unregistered legacy EMA Sweep Engulfing implementation modules/tests.
  Isolate, rather than guess away, shared schema-1/old-phase fields whose persisted
  compatibility inventory is incomplete. Preserve the existing V2
  `EntryPolicy.IMMEDIATE` path and tests; its future removal requires a separate
  explicit contract decision.
- Keep Strategy evaluation, Risk decisions/sizing, execution pricing/slippage,
  Fill application, Position/Trade accounting, market-data validation, snapshot
  membership, result facts, and persistence repositories in their current owning
  boundaries.

These decisions were approved by the developer before GIT START. They remain the
implementation and closure authority for this workstream.

## Non-goals

- No new Experiment features, UI/API capabilities, broker support, Strategy,
  timeframe, or generalized engine abstraction.
- No Experiment engine redesign, performance optimization, persistence redesign,
  migration, schema change, or historical-data acquisition change.
- No changes to Strategy methodology, Risk policy, execution model, accounting,
  market-data semantics, DatasetSnapshot identity, result methodology, or immutable
  fact rules.
- No backward-compatibility preservation for obsolete runtime paths merely because
  Atlas is undeployed. Existing immutable facts may remain readable only where the
  approved architecture explicitly requires a read-only boundary.

## Required acceptance

- Exactly one executable authoritative Experiment runner path is documented and
  enforced: lifecycle/application entry → `ExperimentRunner.run` → V2 native
  Experiment loop.
- Superseded Experiment execution code is removed or isolated, with a source/call
  graph test proving no second path is callable as an authoritative new Experiment
  runner.
- No executable authoritative Experiment path aggregates M1 into analytical M15.
  Native M15 MID plus sparse M1 BID/ASK semantics remain unchanged.
- Obsolete phase/compatibility policy code is removed only when no current contract,
  immutable fact, migration, or approved read-only boundary requires it.
- Pending price-trigger state is explicit and its behavior is byte/result equivalent
  for current inputs.
- Same canonical Experiment inputs produce the same authoritative outputs before and
  after cleanup, excluding only explicitly operational identity/timestamp fields.
- EMA Sweep Confirmation Break v2 golden behavior is unchanged, including native
  M15 decision frontiers, same-bar confirmation, strict `observation.start_time >
  decision_time` execution eligibility, post-decision sparse M1 trigger fills,
  W1–W5 eligible execution windows, W6-frontier Strategy reset, stop/target
  geometry, rationale facts, and the existing IMMEDIATE path.
- Risk/accounting/equity/result immutability and failure-without-trustworthy-result
  behavior remain unchanged.
- Full required tests and an independent validation/review receipt pass before any
  READY_FOR_USER claim.

## BUILD task breakdown and remediation sequence

Tasks were ordered, approved, and each has a completion receipt in its own file.
T005–T011 are narrow validation/review remediations recorded on the same branch.

1. `T001-authoritative-runner-cleanup`: remove the dead Phase 4 runner loop and
   runner-only diagnostics/composition, neutralize terminal completion naming, and
   introduce the explicit pending-trigger handoff. Preserve valid V2 output and
   failure semantics.
2. `T002-legacy-read-and-ingestion-isolation`: isolate V1 immutable result/chart
   reads; remove obsolete V1 ingestion/write methods, uncalled M1-derived helper,
   aggregation alias, and CLI compatibility commands without touching V2 load or
   existing V1 rows.
3. `T003-legacy-strategy-policy-isolation`: remove unregistered legacy Strategy
   modules/tests and mark/prove retained shared state/entry-policy compatibility is
   not used by production registration or new V2 execution. Do not change the
   current EMA Sweep Confirmation Break v2 implementation.
4. `T004-determinism-and-boundary-regressions`: add/update focused source-graph and
   deterministic integration regressions for one runner, native products,
   pending-trigger boundaries, immutability, and Freeze 01–03 behavior; run the
   required pre/post-equivalence evidence after T001–T003.
5. `T005-validation-remediation`: correct the newly introduced changed-file Ruff
   import-order finding, reconcile the T002 receipt metadata, and establish whether
   strict Pyright findings are pre-existing baseline debt or Freeze 04 regressions.
6. `T006-quality-and-e2e-remediation`: resolve remaining Freeze 04-only strict
   Pyright diagnostics without changing runtime behavior and make the E2E harness
   runnable on an explicitly supplied alternate local port when the default port is
   occupied, so the required E2E gate can execute without stopping another process.
7. `T007-e2e-selector-remediation`: align stale E2E accessibility selectors with
   the current Strategy/Data form labels, without changing product behavior or test
   assertions, then prove the complete E2E workflow.
8. `T008-e2e-date-and-fixture-remediation`: align the existing workflow spec with
   the current composite UTC date/time picker and diagnose/fix only stale E2E fixture
   setup that prevents the already-specified failed-Experiment flow from reaching
   its existing assertion.
9. `T009-changed-test-lint-remediation`: remove the exact Freeze 04-only Ruff
   diagnostics from changed test seams without broad baseline cleanup or behavioral
   test changes.
10. `T010-final-test-typing-remediation`: remove the three exact current-only strict
   Pyright diagnostics from changed test seams without weakening the type gate or
   changing runtime behavior.
11. `T011-risk-config-loop-remediation`: restore `RiskConfig` construction to the
   pre-loop V2 setup boundary identified by independent review, preserving fail-closed
   ordering and behavior.

## Planned role artifacts

- `ARCHITECTURE.md`: ARCHITECT-owned contract, invariants, valid/invalid/boundary
  examples, exact cleanup scope, and required validation.
- `tasks/T###-*.md`: approved BUILD assignments and completion receipts for this
  workstream's implementation and remediation sequence.
- `VALIDATION.md`: independent validation after every approved BUILD task is DONE.
- `REVIEW.md`: independent review after validation PASS.

## Task state

- ARCHITECT: `DONE — ARCHITECTURE.md frozen and approved`
- BUILD: `T001 DONE; T002 DONE; T003 DONE; T004 DONE; T005 DONE; T006 DONE; T007 DONE; T008 DONE; T009 DONE; T010 DONE; T011 DONE`
- VALIDATE: `PASS`
- REVIEW: `PASS`

## Next action

All BUILD tasks are complete; VALIDATION and REVIEW both PASS with no unresolved
Critical or Important findings. Await explicit developer approval before GIT END and
merge. Do not alter or discard the uncommitted branch state without approval.
