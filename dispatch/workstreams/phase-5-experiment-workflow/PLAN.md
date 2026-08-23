# Plan — Phase 5: Experiment Workflow

## Scope
Deliver the roadmap Phase 5 workflow for configuring, running, and inspecting trustworthy Experiments from the UI. Phase 4 completion is accepted based on the user's attestation; this workstream must preserve its reproducibility and no-lookahead guarantees.

## Acceptance criteria
- A trader can configure an Experiment, validate data coverage, start it, observe status, and inspect the completed result.
- The result exposes headline metrics, equity/drawdown, Trade list/detail, and assumptions/provenance.
- The work stays within roadmap Phase 5 exclusions.

## Ordered tasks
1. Explore the existing Experiment, API, and UI surfaces and identify Phase 5 context and gaps.
2. Produce an architecture blueprint and implementation task breakdown.
3. Obtain explicit human approval of the blueprint.
4. Obtain a READY receipt for a dedicated local feature branch.
5. Implement approved tasks sequentially; validate and review; close the workstream.

## Assignments and status
| Task | Owner | Artifact | Status | Model |
| --- | --- | --- | --- | --- |
| Explore existing surfaces | explore agent | `EXPLORATION.md` | completed | default |
| Architecture blueprint | architect agent | `ARCHITECTURE.md` | completed — approved | default |
| Worktree readiness | worktrees agent | `READY.md` | completed — READY on `feature/phase-5-experiment-workflow` | default |
| Implementation task 1: contract fixtures and migration | backend builder | `TASK-01.md` | completed — R1 passed | default |
| Implementation task 2: deterministic metrics boundary | backend builder | `TASK-02.md` | completed — R1 passed after repair | default |
| Implementation task 3: coverage and configuration workflow | backend builder | `TASK-03.md` | completed — R1 passed after repair | default |
| Implementation task 4: run lifecycle and recovery | backend builder | `TASK-04.md` | completed — R1 passed | default |
| Implementation task 5: result read composition | backend builder | `TASK-05.md` | completed — R1 passed after repair | default |
| Implementation task 6: FastAPI contract and composition | backend builder | `TASK-06.md`, `VALIDATION.md`, `REVIEW.md` | completed — independent validation and R1 passed after repair | default |
| Implementation task 7: frontend foundation and generated client | frontend builder | `TASK-07.md` | completed — R1 passed after repair | default |
| Task 8 backend list-metrics repair | backend builder | `TASK-08-BACKEND-REPAIR.md` | completed — independent validation passed | default |
| Implementation task 8: Experiment list/config/run UI | frontend builder | `TASK-08.md` | completed — independent validation and R1 passed after repair | default |
| Implementation task 9: completed result and Trade detail UI | frontend builder | `TASK-09.md` | completed — R1 passed after repair | default |
| Task 10 E2E failure diagnosis | research agent | `RESEARCH.md` | completed — remediation approval required | default |
| Implementation task 10: end-to-end regression and documentation alignment | backend builder | `TASK-10.md` | completed — harness and initial repairs delivered; remaining failures documented without a false coverage claim | default |
| Implementation task 11: narrow post-repair E2E remediation | backend builder | `TASK-11.md` | completed — prior browser failures were already repaired; E2E receipt exposed an out-of-scope valid-run backend failure | default |
| Read-only valid-run root-cause investigation | research agent | `RESEARCH.md` (append-only investigation section) | completed — deterministic Phase 5 create/orchestration failure classified; remediation scope awaiting approval | default |
| Remediation blueprint update | architect agent | `ARCHITECTURE.md` (append-only remediation blueprint) | completed — explicitly approved | default |
| Implementation task 12: evidence-led valid-run remediation | backend builder | `TASK-12.md` | completed — safe diagnostics/regressions delivered; evidence found a session-timezone policy conflict and correctly stopped before corrective change | default |
| PostgreSQL UTC policy blueprint update | architect agent | `ARCHITECTURE.md` (append-only policy remediation blueprint) | completed — explicitly confirmed | default |
| Implementation task 13: PostgreSQL UTC session policy enforcement | backend builder | `TASK-13.md` | completed — policy and focused regressions passed; E2E-only persistence failure correctly blocked further correction | default |
| Read-only E2E persistence-failure investigation | research agent | `RESEARCH.md` (append-only investigation section) | completed — exact operation unproven; safe lifecycle diagnostic recommended and awaiting approval | default |
| E2E lifecycle-diagnostic blueprint update | architect agent | `ARCHITECTURE.md` (append-only diagnostic blueprint) | completed — explicitly confirmed | default |
| Implementation task 14: E2E lifecycle persistence diagnostic | backend builder | `TASK-14.md` | in progress — approved closed diagnostic; mandatory stop after evidence, no corrective fix | default |
| Implementation task 14: E2E lifecycle persistence diagnostic | backend builder | `TASK-14.md` | completed — lifecycle/UTC/commit path proven healthy; primary divergence narrowed to runner-return/E2E composition; no correction made | default |
| Runner-return/E2E composition diagnostic blueprint update | architect agent | `ARCHITECTURE.md` (append-only diagnostic blueprint) | completed — explicitly confirmed | default |
| Implementation task 15: primary runner-return/E2E composition diagnostic | backend builder | `TASK-15.md` | in progress — approved closed comparison diagnostic and zero-Trade selector-only repair; mandatory stop after evidence | default |
| Implementation task 15: primary runner-return/E2E composition diagnostic | backend builder | `TASK-15.md` | completed — safe diagnostic and direct comparison delivered; E2E evidence blocked because isolated database environment was unavailable | default |
| Implementation task 16: isolated E2E restore, diagnosis, and bounded correction | backend builder | `TASK-16.md` | in progress — explicitly authorized for test DB restore/seed, approved diagnostics, and one evidence-proven narrow Phase 5/E2E correction only | default |
| Implementation task 16: isolated E2E restore, diagnosis, and bounded correction | backend builder | `TASK-16.md` | completed — API autoflush mismatch corrected; valid backend E2E paths complete; two browser completion selectors remain stale | default |
| Implementation task 17: selector-only E2E alignment | frontend builder | `TASK-17.md` | in progress — approved test-locator alignment only; affected E2E then canonical E2E required | default |
| Implementation task 17: selector-only E2E alignment | frontend builder | `TASK-17.md` | completed — selector repair passed; primary E2E exposed an out-of-scope Trade-detail chart composition failure | default |
| Implementation task 18: Trade-detail chart diagnosis and bounded repair | backend builder | `TASK-18.md` | in progress — approved local diagnosis/fix/regression plus affected/canonical E2E receipts | default |
| Implementation task 18: Trade-detail chart diagnosis and bounded repair | backend builder | `TASK-18.md` | completed — chart mapping contract corrected; E2E now blocked solely by Trade-detail financing-copy assertion | default |
| Implementation task 19: financing-disclosure diagnosis and bounded repair | frontend builder | `TASK-19.md` | in progress — approved contract trace, smallest repair/test adjustment, affected and canonical E2E receipts | default |
| Implementation task 19: financing-disclosure diagnosis and bounded repair | frontend builder | `TASK-19.md` | completed — disclosure/API/UI regressions pass; E2E blocked by invalid isolated database URL scheme | default |
| Implementation task 20: E2E URL restoration and receipts | backend builder | `TASK-20.md` | in progress — authorized isolated URL correction and affected/canonical E2E execution only | default |
| Implementation task 20: E2E URL restoration and receipts | backend builder | `TASK-20.md` | completed — URL corrected; migration setup blocked by missing PostgreSQL schema selection | default |
| Implementation task 21: isolated E2E PostgreSQL schema repair | backend builder | `TASK-21.md` | in progress — authorized local `atlas_test` environment diagnosis/repair, migrations, seed, E2E, then validation readiness | default |
| Implementation task 21: isolated E2E PostgreSQL schema repair | backend builder | `TASK-21.md` | completed — isolated `atlas_test` repaired; migration/seed and canonical E2E 5/5 passed | default |
| Independent full Phase 5 validation | tester | `VALIDATION.md` | in progress — required before review | default |
| Independent full Phase 5 validation | tester | `VALIDATION.md` | completed — pass; two Minor non-blocking findings | default |
| Independent Phase 5 review | reviewer | `REVIEW.md` | in progress — required terminal gate | default |
| Independent Phase 5 review | reviewer | `REVIEW.md` | completed — PASS (R1), no Critical/Important findings; four Minor non-blocking findings | default |
| Closure receipt recovery | documenter | root `COMPLETED.md`, root `ACTIVE.md` | in progress — separate recovery task after prior documenter result was empty; must verify rather than infer memory/closure state | default |
| Validation | tester | `VALIDATION.md` | blocked — valid primary and zero-Trade E2E runs durably fail with `MARKET_DATA/INVALID_INPUT`; no passing E2E receipt exists | default |
| Review | reviewer | `REVIEW.md` | blocked on validation | default |
| Closure | documenter | root `COMPLETED.md`, root `ACTIVE.md` | blocked on review | default |

## Constraints
- Follow `AGENTS.md` invariants and canonical terminology.
- Do not add Phase 6+ capabilities or alter Phase 4 semantics without an approved blueprint change.
- No implementation before explicit human approval and a valid READY receipt.
- Writers, validation, review, and closure are sequential.
- Implementation cwd: `/Users/vike/Desktop/atlas` on `feature/phase-5-experiment-workflow`, per `READY.md`.
- Task 11 is limited to the failures recorded in `TASK-10.md`: disabled coverage validation controls, the failed-Experiment result assertion, and the foundation heading assertion. Reuse the existing harness and do not reinstall browsers, recreate seed/server infrastructure, or repeat already-passing checks unless needed to validate a changed file.
- Task 11 receipt established that its three documented browser failures are repaired. Any investigation or correction of the valid-run `MARKET_DATA/INVALID_INPUT` failure requires separately approved scope and must not be folded into Task 11.
- The approved investigation must trace the E2E seeded StrategyVersion/DatasetSnapshot through coverage, persisted Experiment inputs, repository reads, session policy, M15 derivation, and Phase 4 runner invocation; compare it to a known-good Phase 4 fixture; prove historical determinism independent of wall-clock/session/OANDA availability; and stop with a recommended smallest corrective scope.
- Task 12 must follow the append-only remediation blueprint in `ARCHITECTURE.md` exactly. It may not correct any behavior before meeting the evidence gate, and it must stop for a blueprint update if evidence indicates a Phase 4 semantic or broader architectural conflict.
- Task 12 evidence identified PostgreSQL session timezone (`America/Chicago` versus runner-required UTC alignment) as the first mismatch. This is a broader policy conflict; no E2E/full validation/review may begin until a separately approved blueprint update resolves it.
- Task 13 established governed UTC sessions across the approved direct paths, but the two valid E2E browser paths now durably fail with `PERSISTENCE/PERSISTENCE_FAILURE` under a non-UTC host `TZ`. No workaround was applied; a separately approved read-only diagnosis is required before any further change.
- Task 14 showed UTC, revision, PID continuity, flush, commit, and final read all succeed in the primary E2E case, but the runner returns a durable failed result; the zero-Trade backend completes and only its locator is stale. Root cause is not yet proven; a new bounded runner-return/E2E composition diagnostic requires approval.
- Task 15 implemented the approved runner-return comparison diagnostic and repaired the zero-Trade selector, but could not execute either required E2E receipt because the isolated E2E database environment was unavailable. No E2E cause is claimed; rerun authorization is required after the environment is restored.
- Task 16 may restore only the isolated `*_test` E2E PostgreSQL environment with the existing project migration/seed setup, execute the approved diagnostics, and apply exactly one local evidence-proven Phase 5/E2E correction plus its regression. It must stop for a destructive/non-test operation, material architecture/Phase 4 conflict, or broader fix.
- Task 16 proved and corrected the API session-factory autoflush mismatch. Both valid E2E backend paths now complete, but primary and zero-Trade browser assertions use stale/non-matching completion selectors. A separate selector-only task is required before full E2E validation.
- Task 17 repaired completion selectors without UI changes. The primary E2E then reached Trade detail and exposed `backend/experiments/results.py:_chart` `ValueError: too many values to unpack`; zero-Trade/full E2E/validation/review remain blocked pending a separately approved diagnosis.

## Task metadata
- Workstream: `phase-5-experiment-workflow`
- Classification: Feature
- Risk level: R1
- Premium model decision: not needed; existing UI/API integration is bounded and a cheaper/default model is sufficient.
