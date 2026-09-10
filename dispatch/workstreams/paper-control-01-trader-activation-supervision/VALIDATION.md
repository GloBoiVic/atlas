# VALIDATION — PAPER Control 01 — Trader Activation & Supervision

- **Workstream:** `paper-control-01-trader-activation-supervision`
- **Role:** `VALIDATE`
- **Status:** IN_PROGRESS
- **Branch:** `solo/paper-control-01-trader-activation-supervision`
- **Base:** `e2ad47c5cbfbca89d58f915745f81180c4864db9`

## Validation scope

Independently verify the approved PLAN and ARCHITECTURE, all T001/T002/T003 receipts, the implementation diff, focused frontend behavior, acceptance criteria, and safety constraints.

## Required evidence

- T001 focused API-client and pure-helper tests, including exact decimal-string Risk conversion and lifecycle labels.
- T002 focused activation workflow tests, including preflight, frozen review, typed confirmation, one-shot submission, stable identity, and ambiguous outcome handling.
- T003 focused supervision tests, including recurring bounded detail polling, terminal polling stop, broker-state cadence separation, runtime-only STOP, ambiguous STOP readback, and preserved history.
- `npm run check:web` and `git diff --check`.
- Relevant backend authority regression checks without starting `atlas-runtime`, activating PAPER, reading OANDA, mutating a broker, or using credentials.
- Manual/mock visual validation where supported, including desktop and narrow viewport states.

## Worker Evidence

The independent VALIDATE worker records the immutable conclusion, commands, evidence, findings classified under SoloFlow, and any required remediation reference here. This artifact must not be overwritten after completion.

## Findings

### F-001 - Important - PRODUCT / approved-scope DEFECT

`frontend/components/paper-status.tsx:296-323` schedules one detail request with `setTimeout`, then depends on `detailRetry`, `observedLifecycle`, and `retainedActivationId`. When a detail response reports the same non-terminal lifecycle as the prior response, `observedLifecycle` is unchanged, so the effect does not run again. The supervision surface therefore stops polling after the first unchanged `RUNNING`, `STARTING`, `REQUESTED`, or `STOP_REQUESTED` response. This violates acceptance criterion 27 and the T003 requirement for recurring approximately 3-second detail polling until terminal state or unmount. The focused T003 test only returns `STOPPED` after its first poll and does not cover an unchanged non-terminal response.

Remediation path after Solo reconciliation: return to BUILD for a recurring timer independent of lifecycle transitions, with a regression test for an unchanged non-terminal detail response.

### F-002 - Important - PRODUCT / approved-scope DEFECT

`frontend/components/paper-status.tsx:192-197` always assigns `status-success` to the compact Overview lifecycle indicator. `status-success` is the positive color in `frontend/app/globals.css:136-138`, so `BLOCKED` and `FAILED` are rendered as green success states in Overview even though their text remains visible. This conflicts with acceptance criterion 35 and the requirement that blocked/failed state not be presented as generic success.

Remediation path after Solo reconciliation: return to BUILD to use non-success styling for blocked/failed compact lifecycle states and add assertions for the status class or equivalent semantic styling.

### F-003 - Minor - PRODUCT / approved-scope DEFECT

The activation form controls at `frontend/components/paper-activation.tsx:149-188`, `:812-826`, and `:943-950` do not provide meaningful `name`/`autocomplete` attributes. The Risk placeholder at `:820` is also `Enter a percentage`, rather than an example ending in an ellipsis. These are Web Interface Guidelines issues, not capital-contract failures, and are non-blocking residual UI concerns.

## Scope And Receipts

- `main`, `HEAD`, and the approved base all resolve to `e2ad47c5cbfbca89d58f915745f81180c4864db9`.
- The inspected implementation diff is frontend-only: the expected T001/T002/T003 client, helper, page, component, and test files plus `dispatch/ACTIVE.md` and workstream artifacts. No backend, generated API type, migration, or runtime file changed.
- Immutable T001, T002, and T003 BUILD receipts were inspected. Each records the expected owned files and no backend, provider, broker, credential, or runtime operation.
- Direct source review confirmed exact string Risk conversion, frozen review identity, `ACTIVATE_PAPER`, explicit same-ID retry, immutable version/schema use, preflight uncertainty blocking, runtime-only STOP, the required STOP warning/reason, no Close Trade or reconciliation controls, broker/runtime separation, history preservation, and no account ID or credential rendering in the primary activation UI.

## Executed Checks

| Check | Result |
| --- | --- |
| T001 focused Vitest | PASS - 2 files, 25 tests |
| T002 focused Vitest | PASS - 1 file, 12 tests |
| T003 focused Vitest | PASS - 2 files, 41 tests; source audit still finds F-001 and F-002 |
| `npm run check:web` | PASS - 20 files, 143 tests, typecheck, format, and production build; lint reported 242 existing warnings and zero errors |
| `git diff --check` | PASS |
| `uv run pytest backend/tests/test_api_paper.py backend/tests/runtime` | PASS - 200 tests, 1 deprecation warning |
| `uv run pyright backend` | PASS - no type errors; tool update notice only |
| `uv run alembic check` | PASS - no new upgrade operations detected |
| `uv run ruff format --check backend` | TOOLING / NEW SCOPE - 68 unrelated backend files would be reformatted |
| `uv run ruff check backend` | TOOLING / NEW SCOPE - 28 unrelated baseline backend errors; no changed backend files |

## Acceptance Matrix

| Criteria | Result | Evidence |
| --- | --- | --- |
| 1-4 | PASS | `/paper/activate` exists; capability, active-session, and broker preflight block unsafe preparation/submission. |
| 5-9 | PASS | Strategy and immutable version selection use existing catalog/detail responses; unavailable versions are disabled; schema defaults and review invalidation are implemented. |
| 10-15 | PASS | Risk starts blank, validates `0% < p < 100%`, converts by string arithmetic, remains a decimal string, and review shows the selected PAPER boundary without the provider account ID. |
| 16-22 | PASS | Exact `ACTIVATE PAPER` UI phrase maps to `ACTIVATE_PAPER`; one UUID is generated per frozen review, same-review retry reuses it, and successful submission navigates to `/paper`. |
| 23 | PASS | Ambiguous non-API transport failures perform read-only active-status resolution; matching ID accepts, no active offers same-ID retry, and a different active ID becomes a conflict. |
| 24-26 | PASS | Lifecycle helpers distinguish `REQUESTED`, `STARTING`, and `RUNNING`; current Strategy key/version and Risk are displayed. |
| 27 | FAIL - F-001 | A status detail request is scheduled at 3000 ms, but unchanged non-terminal responses do not schedule the next request. |
| 28 | PASS | Broker state has explicit/manual refresh only; the detail timer calls `paperStatus`, not `paperBrokerState`. |
| 29-34 | PASS | STOP has deliberate confirmation, exact warning/reason, existing stop route, ambiguous detail readback, and no flatness claim after terminal runtime state. |
| 35 | FAIL - F-002 | Full PAPER status uses `Blocked`/`Failed`, but compact Overview applies positive success styling to all lifecycle values. |
| 36-38 | PASS | Broker exposure remains first, completed PAPER history remains rendered, and Overview exposes no activation or STOP control. |
| 39-45 | PASS | Backend Risk/Strategy/execution/provider authority is unchanged; no migration, process spawning, or credentialed/provider operation was used. |

## Visual Validation Limitation

Mocked visual validation was not performed. No safe mocked visual harness/state was available, and starting Atlas services, using live browser/API state, reading OANDA, or activating/mutating broker state was explicitly prohibited. Desktop and narrow-viewport appearance therefore remain unverified beyond source inspection and the successful production build.

## Worker Evidence Conclusion

- **Status:** FAIL
- **Conclusion:** T001/T002/T003 focused behavior and safe authority checks pass, but unresolved Important approved-scope PRODUCT defects F-001 and F-002 block acceptance. The primary failure is stale PAPER supervision after an unchanged lifecycle response; Overview also presents blocked/failed runtime states with positive-success styling.
- **Classification:** F-001 and F-002 are `PRODUCT / approved-scope DEFECT / Important`; F-003 is `PRODUCT / approved-scope DEFECT / Minor`; backend Ruff failures are `TOOLING / NEW SCOPE` and unrelated to the frontend slice.
- **Safety:** No `atlas-runtime` process was started, no PAPER activation was submitted, no OANDA/provider read was performed, no broker mutation or credentialed operation occurred, and no remediation artifact was created.
- **Required next step:** After Solo reconciliation, use the remediation paths recorded under F-001 and F-002 before re-validation.
