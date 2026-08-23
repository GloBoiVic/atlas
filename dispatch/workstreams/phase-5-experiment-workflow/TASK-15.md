# TASK-15 — Primary runner-return/E2E composition diagnostic

## Outcome

Implemented the default-off, test-only runner comparison diagnostic and the
approved zero-Trade selector repair. No primary corrective change was made.
The required primary E2E receipt could not be captured because the isolated
E2E database environment was unavailable in this checkout; diagnosis therefore
stops without a root-cause claim.

## Closed implementation

- Added `Phase4RunnerComparisonDiagnostic` with the exact closed comparison
  fields, checkpoints, bounded runner stages, domain-separated SHA-256 digests,
  and sink-failure isolation.
- Added pre-execution and terminal-return records to the existing optional
  runner diagnostic channel. Existing public/durable failure sanitization and
  the legacy ValueError diagnostic remain unchanged.
- Added only the guarded `_test` E2E stdout adapter and explicit Playwright
  runner-diagnostic flag. Production composition remains default-off.
- Removed temporary browser console/request/response-body logging.
- Repaired only the zero-Trade status assertion to the approved header-scoped
  exact selector.

## Receipts

```text
ruff check (changed Python files): PASS
pytest -q backend/tests/experiments/test_runner_diagnostics.py: 4 passed
primary/zero integration comparison under non-UTC host TZ: 2 passed
prettier check (changed TypeScript files): PASS
serial zero-Trade E2E diagnostics off: NOT RUN — isolated E2E database environment unavailable
serial primary E2E runner diagnostic: NOT RUN — isolated E2E database environment unavailable
```

The integration comparison produced matching `PRE_EXECUTION` and
`TERMINAL_RETURN` records for both direct and service-created paths. Terminal
status was `COMPLETED`; failure category and code were null. Primary and
zero-Trade result/Trade assertions passed. No E2E record, terminal stage, or
browser outcome is claimed because the E2E commands were not executable.

## Closed comparison verdicts

| Field | Verdict |
| --- | --- |
| Strategy identity/contract | MATCH |
| Dataset identity/contract | MATCH |
| Ordered immutable membership/count | MATCH |
| Parameters | MATCH |
| Risk configuration | MATCH |
| Simulation configuration | MATCH |
| Requested period | MATCH |
| Starting capital | MATCH |
| Financial projection/account/Position | MATCH |
| Effective execution inputs | MATCH |
| Seed profile | MATCH |
| Aggregate runner inputs | MATCH |
| Terminal semantic result | MATCH |
| Direct PENDING-to-run versus candidate RUNNING entry | EXPECTED_ORCHESTRATION_DIFFERENCE |
| Primary E2E versus passing direct primary integration | UNAVAILABLE |

Integration terminal stage: `mark_completed`; status `COMPLETED`; category
null; code null. E2E terminal stage/status/category/code: `UNAVAILABLE`.

## Diagnosis and corrective scope

Root cause: `UNAVAILABLE` (no primary E2E execution receipt). Confidence:
`UNAVAILABLE`. The passing direct comparison establishes no mismatch between
the tested direct baseline and service-created candidate. It does not establish
the E2E composition result. Smallest corrective scope, if a future E2E receipt
identifies one: the single first-mismatching runner-return/E2E composition
boundary or file only; no producer was changed by this task.

## Selector result and changed files

The zero-Trade selector was changed to the approved exact header status scope.
Changed files:

- `backend/experiments/runner.py`
- `backend/api/app.py`
- `backend/tests/e2e_app.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- `backend/tests/integration/test_phase5_valid_run.py`
- `playwright.config.ts`
- `tests/e2e/experiment-workflow.spec.ts`

## Forbidden-operation confirmation

No Git, dependency, migration, schema/model, database-policy, production
logging, API, frontend semantic, lifecycle, runner semantic, fixture, Phase 6,
PAPER/LIVE, full validation, or review operation was performed. No raw values,
messages, SQL, credentials, URLs, paths, traces, payloads, UUIDs, digest
values, or durable diagnostic output are included here. Mandatory stop reached;
no corrective fix was started.
