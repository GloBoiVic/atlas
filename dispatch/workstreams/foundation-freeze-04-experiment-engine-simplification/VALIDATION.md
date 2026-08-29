# Foundation Freeze 04 — Validation

Status: `PASS`

## Receipt

- ROLE: `VALIDATE`
- WORKSTREAM: `foundation-freeze-04-experiment-engine-simplification`
- BRANCH: `solo/foundation-freeze-04-experiment-engine-simplification`
- CWD/repository root: `/Users/vike/Desktop/atlas`
- BASE SHA: `3521274d1f3f492176eec8be9434bc76c6e4341b`
- ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/VALIDATION.md`
- FILES CHANGED: this artifact only

Fresh independent validation was run after T011. PLAN.md, ARCHITECTURE.md, all
T001–T011 receipts, the prior VALIDATION.md and REVIEW.md, Freeze 01–03
receipts, and the complete tracked base-to-current diff were inspected. The
tracked diff is 32 files, 1,167 insertions, and 3,819 deletions; all paths are
within the approved Freeze 04 cleanup, test, documentation, and E2E harness
scope. T011 introduced no scope drift. HEAD/history was not changed.

## T011 remediation evidence

- AST audit: `_run_v2` contains exactly one `RiskConfig(...)` construction at
  line 431, after the warm-up frame loop (line 415), before the decision loop
  (line 528), and outside every frame-loop ancestor.
- `test_v2_malformed_risk_config_fails_before_empty_frame_completion` passed;
  malformed risk input on an empty-frame path returns sanitized `FAILED` /
  `INVALID_INPUT`, records the failure, and cannot complete.
- Focused runner/Risk/source-graph suite passed: 23 tests.

## Section-8 validation matrix

| Concern | Evidence | Result |
|---|---|---|
| One runner / source graph | Runner diagnostics and legacy-isolation tests pass. `run` dispatches only V2; removed Phase 4 symbols, runner aggregation, and obsolete production seams are absent. Remaining `aggregate_m1_to_m15` is confined to the named V1 read boundary/tests. | PASS |
| Before/after determinism | Base-SHA golden replay: 2 passed. Current golden replay: 2 passed. Replay compares ordered intents, RiskDecisions, Orders, Fills, Trades, equity, metrics, quality, fingerprint, and completed facts. | PASS |
| EMA v2 golden behavior | Current reference Strategy long/short, same-bar confirmation, evidence/rationale, geometry, source identity, and retained `IMMEDIATE` coverage passed. Protected EMA v2 implementation has no diff. | PASS |
| Pending W1–W6 / no lookahead | Focused clock/runner/Strategy tests pass for W1/W5, sparse/no-trigger, W6 reset/ineligibility, restart equivalence, exact/gap-through triggers, strict post-decision observations, duplicate frontiers, and one evaluation per frontier. | PASS |
| Native market data / sparse execution | Native M15 MID and sparse M1 BID/ASK membership, no aggregation substitution, acquired/unacquired absence, one-sided quotes, terminal quote, source provenance, and executable-side tests pass. | PASS |
| Risk / execution / accounting | PRE_FLIGHT/PRE_SUBMISSION, adverse slippage once, actual-fill target, protection, ambiguity, Fill-driven accounting, BID/ASK liquidation, costs, equity, and end-close tests pass. | PASS |
| Result immutability / failure safety | Persisted result/fact reads, completed/failed/V1 fixtures, unsupported schema/model, unavailable StrategyVersion, invalid data, missing protection/quote, Risk rejection, persistence failure, and no-trustworthy-result tests pass. | PASS |
| V1 / legacy isolation | Explicit immutable V1 reader, unknown-schema rejection, V2 bypass, no current-bar query/mutation, removed V1 write surfaces, production-only EMA v2 registration, and non-authoritative compatibility guards pass. | PASS |
| Ownership / Freeze 01–03 | Full backend and Freeze 01–03 regression suites pass without migration, schema, Strategy v2, Risk ownership, or accounting ownership changes. | PASS |

## Executed acceptance gates

Database-backed commands used only:
`ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`.
E2E used only the same dedicated database through `ATLAS_E2E_DATABASE_URL`.

| Gate | Evidence | Result |
|---|---|---|
| Migrations / head | Migration tests: 2 passed. Alembic head: `0020_fix_snapshot_guard (head)`. | PASS |
| Full integration backend | `pytest -q backend/tests/integration`: 33 passed, 4 warnings. | PASS |
| Full non-integration backend | `pytest -q backend/tests --ignore=backend/tests/integration`: 317 passed, 6 skipped, 1 warning. | PASS |
| Focused backend/source regressions | Focused Freeze 04, Strategy, domain, clock, Risk, execution, market-data, result, historical-load, runtime, API-health, and migration suites: 301 passed, 6 skipped, 1 warning; dedicated source-graph/T011 subset: 23 passed. | PASS |
| Golden replay | Base SHA: 2 passed. Current: 2 passed. | PASS |
| Compile / diff | `python -m compileall -q backend`; `git diff --check`: passed. | PASS |
| Ruff differential | Full raw diagnostics base/current: 44/44. Changed-path raw diagnostics: 14/14. Exact path/code/message comparison: 0 current-only diagnostics. | PASS |
| Strict Pyright differential | Base/current raw diagnostics: 3,333/2,673; exact path/severity/rule/message comparison, ignoring line movement: 0 current-only and 299 resolved. Changed Freeze 04 paths: 0 current-only. | PASS |
| Web | Vitest: 23 passed. ESLint: 0 errors, 365 warnings. Typecheck and production build: passed. | PASS |
| Web format | Current/base-equivalent check reports the same 5 pre-existing files; no changed Freeze 04 format regression. | PASS |
| Playwright E2E | `ATLAS_E2E_API_PORT=18080 ATLAS_E2E_WEB_PORT=13000 npm run test:e2e`: 5 passed. | PASS |

## Preservation and disposition

- PID `72514` remained listening on `127.0.0.1:8000`; alternate E2E
  listeners on `18080`/`13000` were cleaned up.
- Generated files were restored: `tests/e2e/.fixtures.json` git hash
  `a7d6d72d1e7decd08aab166793657573d5ec20c4`; `frontend/next-env.d.ts` git
  hash `ce4e94a6b10f160ee021fe18939af160d2927dcf`.
- `.codegraph/`, `frontend/.env.local`, and other pre-existing/unowned files
  were preserved. No migration path, current EMA v2 implementation, or Git
  history changed.
- Remaining Ruff, Pyright, and web-format nonzero output is exact baseline
  debt only; there are zero current-only diagnostics.
- No Critical or Important findings remain. The stale PLAN status metadata is
  a minor closure-metadata concern and was not changed by VALIDATE.

`PASS` — all required section-8 behaviors, failure paths, immutability,
ownership regressions, source graph, determinism, migration, quality, and E2E
gates passed. This receipt makes no review or READY_FOR_USER claim.

ROLE: `VALIDATE`  
STATUS: `PASS`  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/VALIDATION.md`  
FILES CHANGED: this artifact only  
CHECKS / EVIDENCE: Complete section-8 matrix; T011 RiskConfig ordering and empty-frame fail-closed regression; base/current golden replay; full backend, migration, Ruff, strict Pyright, web, and 5-test Playwright gates.  
FINDINGS / CONCERNS: Exact baseline-only lint/type/format debt and stale PLAN closure metadata; zero current-only diagnostics and no Critical/Important findings. No review or READY_FOR_USER claim.
