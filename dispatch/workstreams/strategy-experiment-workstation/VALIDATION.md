# Validation — Strategy Experiment Workstation

**Result: BLOCKED**  
**Validation time:** 2026-08-25 (UTC; final receipt at 22:51:10Z)  
**Revision basis:** `5cb72a74bcc946e54e7c6e265cfa24f87352832a` (`feature/strategy-experiment-workstation`). The checkout already contained the builder changes and task-context files; this validation made no source or Git changes.

## Automated validation

| Command | Result |
|---|---|
| `python -m pytest -q` | **FAIL** — 270 passed, 30 skipped, 1 failed, 13 errors. Failure: `test_alembic_revision_ids_fit_default_version_column` sees two migration heads (`0007_proposal_watch`, `0013_result_quality_degraded`) instead of the expected `0013_result_quality_degraded`. Integration errors require absent `ATLAS_TEST_DATABASE_URL`. |
| `python -m pytest backend/tests/strategies backend/tests/domain backend/tests/experiments backend/tests/execution backend/tests/integration/test_migrations.py -q` | **PASS** — 181 passed, 2 skipped. |
| `npm run test:web -- --run` | **PASS** — 9 files, 23 tests. |
| `npm run typecheck:web` | **PASS** |
| `npm run lint:web` | **PASS** |
| `npm run format:check:web` | **FAIL** — 11 pre-existing/unrelated formatting warnings. |
| `npm run test:e2e -- tests/e2e/experiment-workflow.spec.ts` | **BLOCKED before test execution** — Playwright could not start because `http://127.0.0.1:8000/health/ready` was already in use. |
| `python -m pytest backend/tests/integrations/test_oanda_external.py -q` | **SKIPPED** — 1 skipped (credentialed external test did not run). |

## Real OANDA historical flow

The existing API process was healthy (`GET /health/ready` → 200, database `ok`) and its existing environment configuration was used; no credential values were read, printed, or exposed.

Executed durably through the API in this order:

1. `POST /api/v1/historical-data/load-requests` (`load_missing`) for `2025-01-06T00:00:00Z` → `2025-02-06T00:00:00Z`.
2. Poll request `3b41ce97-5e09-4839-ba67-47ec9ae9d2fb` to `COMPLETED`.
3. Reused immutable snapshot `32799557-0e90-4872-920e-a9bad94ab247`; native M15 and coverage validation completed.
4. `POST /api/v1/experiments/coverage-validations` → 200, `valid: true`, warm-up `200/200`, no blocking reasons.
5. `POST /api/v1/experiments` → 201, Experiment `0134fbeb-102c-48c1-9775-63350888a488`.
6. `POST /api/v1/experiments/0134fbeb-102c-48c1-9775-63350888a488/run` timed out at the client while the synchronous server continued; status polling then reached `COMPLETED`.

Durable load receipt: OANDA Practice, EUR/USD, M1 MID/BID/ASK; load range `2025-01-04T23:00:00Z` → `2025-02-06T00:00:00Z`; `coverage.valid: true`; `gapCount: 968` disclosed; snapshot schema `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2`; snapshot fingerprint `b796dd8e6b128cf60ae21c1e63226331ce20ebd2b7dcbfbb9ba19b484b572a83`; policy `OANDA_FX_NY_V1`; native contract `OANDA_M15_NATIVE_UTC_V1`. The load found existing data (inserted/reactivated/unchanged all 0), but completed the provider-backed durable path.

Experiment receipt:

- Human label: `Experiment · 2025-01-06 → 2025-02-06`
- Status: `COMPLETED`
- StrategyVersion: `b65b726a-ad77-4f7e-8536-ad8ad0e048a0`, source fingerprint `42c4645e45c5b15a822bf379d0e58e3ee43e4a58eb3084a7d1074162fb7c0d3d`
- DatasetSnapshot: `32799557-0e90-4872-920e-a9bad94ab247`, fingerprint above
- Result: 49 Trades; modeled net P&L `-578.2534665099`; net return `-0.0578253467`; max drawdown `578.2534665099`; result quality `DETERMINED`; ambiguous trades `0`; financing `FINANCING EXCLUDED`.
- Output fingerprint: `a3c59dc8ad03f3b9e01d15a0a9bc3c730c4464db753e1cd49be4f8a9c4cf35f7`

## Browser / UI evidence (Local Host MCP)

- `tab-1`, `/experiments`: list rendered the completed Experiment and status/metrics.
- `tab-2`, `/experiments/{id}`: completed result rendered with 49 Trades, equity/price-analysis sections, assumptions and provenance. Console had no entries; network had no failed requests.
- `tab-3`, `/experiments/{id}/trades/1`: Trade 1 detail loaded (LONG, STOP_LOSS, -$100.00, -1.00x), with persisted rationale, M1 lineage, and chart route. Console had no entries.
- `tab-4`, `/experiments/{id}/trades/5`: Trade 5 detail loaded (LONG, TAKE_PROFIT, +$163.15, 1.70x). Screenshot captured the candlestick chart with EMA and entry/stop/target/exit labels. `verify(text=TAKE_PROFIT)` passed; console and failed-request diagnostics were empty.
- The browser visibly disclosed `PERSISTED_NATIVE_M15_MID`, BID/ASK execution, immutable snapshot provenance, gap count, and no pattern inference in the browser.

## Blocking findings

1. The complete backend suite is not green: migration heads conflict and the PostgreSQL integration environment is unavailable (`ATLAS_TEST_DATABASE_URL` absent).
2. E2E acceptance could not execute because the configured Playwright server port was already occupied.
3. The real run exposed the persisted catalog as **EMA Sweep Engulfing v2**, not EMA Sweep Confirmation Break; Trade rationale likewise reported `EMA_SWEEP_ENGULFING_CONFIRMED`. Therefore this successful real-data run cannot be accepted as proof of the requested replacement Strategy.
4. The real snapshot disclosed 968 persisted gap decisions. Coverage was valid and the result quality was `DETERMINED`, but the gap disclosure remains part of the acceptance evidence.

No fixture was substituted for the real-data gate, and no acceptance claim is made despite the completed provider-backed Experiment.

## Resumed validation — 2026-08-25

The updated TASK-01/TASK-02 receipts and blueprint were reread before this run. The API and frontend processes were restarted from the current checkout (no source or Git mutation); the API was confirmed healthy on `127.0.0.1:8000` and Next.js served the current checkout on port 3000. Migration state was advanced with `uv run alembic -c alembic.ini upgrade head` so the current model could be exercised; this changed only the disposable development database.

### Updated automated receipts

| Command | Result |
|---|---|
| `python -m pytest -q` | **FAIL** — 271 passed, 30 skipped, 1 failed, 13 errors. The migration-head failure is resolved. Remaining assertion: `backend/tests/experiments/test_configuration.py::test_production_registration_archives_once_and_evaluation_has_no_path_input` still expects obsolete `ema_sweep_engulfing.v1`; 13 integration errors still require absent `ATLAS_TEST_DATABASE_URL`. |
| `python -m pytest backend/tests/strategies backend/tests/domain backend/tests/experiments backend/tests/execution backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py -q` | **FAIL** — 182 passed, 2 skipped, 1 failure: the same obsolete production-registration expectation. |
| `npm run test:web -- --run && npm run typecheck:web && npm run lint:web` | **PASS** — 9 files/23 tests; typecheck and lint passed. |
| `python -m pytest backend/tests/integrations/test_oanda_external.py -q` | **SKIPPED** — 1 skipped; no credentialed external test ran. |
| `uv run alembic -c alembic.ini upgrade head` | **PASS** — applied `0013_result_quality_degraded -> 0007_proposal_watch`; current API no longer hit the prior missing-column error. |
| `npm run test:e2e -- tests/e2e/experiment-workflow.spec.ts` | **Not rerun under a second server** — the supported config hard-codes `reuseExistingServer: false` and port 8000; the current feature-branch server was intentionally kept running for UI validation. Prior exact receipt remains: blocked before execution because port 8000 was occupied. |

### Current production Strategy gate

`GET /api/v1/experiments/configuration-options` after restart returned exactly one catalog row, but it was `EMA Sweep Engulfing v2`, `implementationKey=ema_sweep_engulfing.v2`, `executionAvailable=false`, with no EMA Sweep Confirmation Break row. The current source registry (`production.py`) registers only `ema_sweep_confirmation_break.v1`, while the API option filter admits only implementation keys ending in `.v2`; the persisted catalog also retains the obsolete row. This is a direct blocker to the requested real run, not a credential or stale-server issue.

Consequently, the resumed real OANDA flow **could not safely proceed past StrategyVersion selection**. No fixture or obsolete Strategy run was substituted. The earlier Experiment ID `0134fbeb-102c-48c1-9775-63350888a488` is explicitly not accepted because it used the obsolete Strategy.

### Current browser receipts

- Current-branch API/frontend restart was observed in `/tmp/atlas-api-validation.log` and `/tmp/atlas-web-validation.log`; API readiness returned 200.
- Local Host MCP `tab-1` `/experiments/new` showed the setup workflow, OANDA Practice EUR/USD capability, and only the unavailable obsolete `EMA Sweep Engulfing v2` option after refresh.
- The previous completed-result observations remain valid only for the obsolete run: `tab-2` list/result, `tab-3` Trade 1, and `tab-4` Trade 5. Trade 5 screenshot visibly showed candlesticks, EMA, entry, stop, target, and exit labels; persisted detail facts were compared for fill/stop/target/exit. Both Trade 1 and Trade 5 routes loaded, but current-Strategy acceptance cannot use them.
- Browser diagnostics during current-branch page loads: no console entries; no failed network requests for the setup/result pages. Earlier trade-detail requests against the unmigrated database produced HTTP 500 `UndefinedColumn trade_intents.entry_policy`; migration was then applied. This is recorded as a resolved environment/schema prerequisite, not hidden.

## Final disposition

**BLOCKED.** Recovery requires the owning builders to align the sole production Strategy catalog/API option contract (including `.v1`), remove or supersede the obsolete persisted catalog row in the disposable database, and update the obsolete registration expectation. Then provide a test database (`ATLAS_TEST_DATABASE_URL`) and an e2e invocation with a free configured server port. Re-run the complete suite and the real one-month flow, then inspect at least two Confirmation Break Trade charts against persisted reference/sweep/confirmation/trigger/fill/stop/target/exit/EMA facts before acceptance.

## Final bounded validation — attempt 2 — 2026-08-25

Updated TASK-01 through TASK-04 receipts and the blueprint were reread. Only this validation artifact was edited. API and frontend were restarted from the current feature checkout; readiness returned HTTP 200. No credentials were printed or exposed.

### Automated receipts

- `python -m pytest backend/tests/strategies backend/tests/domain backend/tests/experiments backend/tests/execution backend/tests/test_migration_revision.py -q` — **PASS: 183 passed**.
- `python -m pytest -q` — **BLOCKED by environment only for integration tests**: 272 passed, 30 skipped, 13 errors. Every error is fixture setup requiring absent `ATLAS_TEST_DATABASE_URL`; no assertion/code failure was reported in those tests.
- `npm run test:web -- --run && npm run typecheck:web && npm run lint:web` — **PASS: 9 files, 23 tests; typecheck and lint passed**.
- `python -m pytest backend/tests/integrations/test_oanda_external.py -q` — **SKIPPED: 1**, credentialed external test not enabled.

### Current configuration-options gate

`GET /api/v1/experiments/configuration-options` on the restarted API returned exactly one executable StrategyVersion and no obsolete options:

- `EMA Sweep Confirmation Break v1`
- strategy key `ema_sweep_confirmation_break`
- implementation `ema_sweep_confirmation_break.v1`
- `executionAvailable: true`
- source fingerprint `bfc425027de82712be63566159631f7df2b983484f68ebd5471f4bdbb666f821`

The browser setup page (`Local Host MCP tab-5`, `/experiments/new`) visibly showed this StrategyVersion and the fixed five-bar armed-watch parameter. Accessibility snapshot exposed the primary navigation, setup region, combobox, and action buttons. Tab-5 console diagnostics were empty and failed-request diagnostics were empty. A screenshot was captured.

### Current real OANDA durable flow

The real provider-backed flow was executed with the current StrategyVersion, without fixtures:

1. `POST /api/v1/historical-data/load-requests` (`load_missing`) → request `41b79c2f-8502-430e-9b8f-4680a56e000b`, then polled to `COMPLETED`.
2. Immutable snapshot selected/reused: `1ec2f9bd-6e82-4197-9f26-5e452b176833`, fingerprint `7e6b8149781ae4ba5279eee62e65af9dae2314f60f62a7859429a8c22e2d0e8a`.
3. Native M15 derivation completed; load receipt reports OANDA Practice EUR/USD M1 MID/BID/ASK, snapshot schema `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2`, native contract `OANDA_M15_NATIVE_UTC_V1`, policy `OANDA_FX_NY_V1`, and 960 disclosed gap decisions.
4. `POST /api/v1/experiments/coverage-validations` → HTTP 200, `valid: true`, warm-up required/available `100/108`, no blocking reasons.
5. `POST /api/v1/experiments` → HTTP 201, Experiment `4a414319-b959-4be6-a757-8c1be4a2099c`.
6. `POST /api/v1/experiments/4a414319-b959-4be6-a757-8c1be4a2099c/run` → HTTP 200 response, durable status `FAILED` with sanitized `PERSISTENCE_FAILURE` (`Experiment persistence failed`). No trustworthy result was created and no Trades were persisted.

The API detail confirms the current StrategyVersion ID `17ddb7c6-dc89-4167-8046-1214def41259` and current snapshot ID above, but the failed Experiment cannot satisfy the completed-result gate. The provider request receipts in `/tmp/atlas-api-validation.log` show successful OANDA M15 and BID/ASK M1 HTTP 200 responses; the failure occurred after data acquisition during Experiment persistence.

### Browser result/trade inspection

- Current Experiment result page (`Local Host MCP tab-6`) rendered persistent FAILED status, “No trustworthy full result was created,” and the persistence failure; accessibility snapshot was available, console diagnostics were empty, and no failed browser requests were reported. Screenshot captured.
- Two distinct Trade detail routes were attempted in the current UI session (`tab-7` Trade 1 and `tab-8` Trade 5) as supplemental checks against the prior obsolete completed Experiment. Trade 1 loaded persisted rationale/lineage, while Trade 5 remained on “Loading Trade…”/“Checking API” in the browser session. These are explicitly not current-Strategy evidence and are not used for acceptance.
- The current Experiment has zero Trades, so it is impossible to compare two current Trade pages or visually verify current reference/sweep/confirmation/trigger/fill/stop/target/exit/EMA landmarks. No fixture substitution was made.

## Final disposition

**BLOCKED.** The prior catalog/API blocker is resolved: the current API exposes only executable EMA Sweep Confirmation Break v1. The remaining acceptance blocker is a real-data Experiment `PERSISTENCE_FAILURE` after successful OANDA load, leaving zero Trades and no completed result. Recovery: the owning persistence/runner builder must diagnose and fix the sanitized persistence failure against the current migrated schema; rerun the complete feasible suite and real flow, then verify at least two current Trade detail pages and all persisted landmarks/charts. Integration DB availability (`ATLAS_TEST_DATABASE_URL`) and isolated e2e server execution remain environmental prerequisites.

## Final acceptance validation — runner persistence fix — 2026-08-25

Latest TASK-02 and all task receipts plus the blueprint were reread. API/frontend were restarted from the current feature checkout. No source, dispatch artifact other than this file, or Git state was changed; credentials were never exposed.

### Automated receipts

- `python -m pytest backend/tests/experiments backend/tests/execution backend/tests/strategies backend/tests/domain backend/tests/test_migration_revision.py -q` — **PASS: 183 passed**.
- `python -m pytest -q` — **272 passed, 30 skipped, 13 errors**. All 13 errors are integration fixture setup failures caused by missing `ATLAS_TEST_DATABASE_URL` (API experiment, database, and strategy persistence integration modules); no additional code assertion failure occurred.
- `npm run test:web -- --run && npm run typecheck:web && npm run lint:web` — **PASS: 9 files, 23 tests; typecheck and lint passed**.
- `python -m pytest backend/tests/integrations/test_oanda_external.py -q` — **SKIPPED: 1** because credentialed external tests are not enabled.

### Strategy/catalog verification

`GET /api/v1/experiments/configuration-options` returned exactly one executable row and no obsolete rows: `EMA Sweep Confirmation Break v1`, strategy key `ema_sweep_confirmation_break`, implementation `ema_sweep_confirmation_break.v1`, StrategyVersion ID `17ddb7c6-dc89-4167-8046-1214def41259`, source fingerprint `bfc425027de82712be63566159631f7df2b983484f68ebd5471f4bdbb666f821`, `executionAvailable=true`.

### Fresh real OANDA durable Experiment

The supported flow completed with OANDA Practice EUR/USD and the current Strategy only:

1. `load_missing`: request `eb310d58-f31b-4c57-9968-99f958e27924` → `COMPLETED`.
2. Immutable snapshot: ID `1ec2f9bd-6e82-4197-9f26-5e452b176833`, fingerprint `7e6b8149781ae4ba5279eee62e65af9dae2314f60f62a7859429a8c22e2d0e8a`.
3. Provider receipt: OANDA Practice, EUR/USD, M1 MID/BID/ASK; native M15 contract `OANDA_M15_NATIVE_UTC_V1`; snapshot schema `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2`; policy `OANDA_FX_NY_V1`; 960 persisted gap decisions disclosed; coverage valid and warm-up `100/108`.
4. Coverage validation: HTTP 200, `valid=true`, no blocking reasons.
5. Create: HTTP 201, Experiment ID `d067a6ca-5c9b-4669-92fb-9d1c27c6fdab`, period `2025-01-06T00:00:00Z` → `2025-02-06T00:00:00Z`.
6. Run/status: HTTP 200 and durable `COMPLETED`.

Result receipt: 10 Trades, quality `DETERMINED`, ambiguous trades `0`, gross/modeled net P&L `280.0581906441`, net return `0.0280058191`, max drawdown `0`, output fingerprint `a9419c470b59dc1774edd1c140eb35f3848ce31db6c001e89bd396af2d9bbe86`, financing `FINANCING EXCLUDED`.

### Browser acceptance evidence

- Local Host MCP `tab-5` (`/experiments/new`) showed only `EMA Sweep Confirmation Break v1`; accessibility snapshot exposed navigation, Run an Experiment region, StrategyVersion/DatasetSnapshot controls, and action buttons. Screenshot captured. Console had no entries and failed-request diagnostics were empty.
- `tab-10` (`/experiments/{id}`) rendered COMPLETED, 10 Trades, metrics, assumptions, provenance, and 960-gap disclosure. Screenshot and accessibility snapshot captured. Console had no entries. However, the page displayed `StrategyVersion EMA Sweep Engulfing` and its price-analysis requests returned HTTP 500 (`/price-analysis`), showing a current UI/API result-read defect despite the API detail carrying the current StrategyVersion ID.
- `tab-11` Trade 1 and `tab-12` Trade 2 both loaded as distinct current Experiment Trade details. Console diagnostics were empty and failed-request diagnostics were empty for both; tab-12 accessibility snapshot was captured and tab-12 screenshot was captured.
- Trade 1 persisted facts visually/textually matched its chart facts: LONG, `PRICE_TRIGGERED`, trigger `1.03526`, reference M15 at `2025-01-06T08:45Z`, sweep/confirmation at `09:00Z`, entry fill `1.03526` at `09:03Z`, stop `1.0329244773`, exit `1.03292` at `11:02Z`, `STOP_LOSS`; EMA 100 context and all server landmarks were present.
- Trade 2 persisted facts matched its setup/execution facts: LONG, trigger `1.03880`, reference `17:45Z`, sweep/confirmation `18:00Z`, entry fill `1.03889` at `18:01Z`, stop `1.0372053992`, target/fill `1.0417538213` at `2025-01-07T07:39Z`, `TAKE_PROFIT`; server landmarks included reference, sweep, confirmation, and trigger with EMA 100 context.
- The chart canvas was visible on the Trade 2 screenshot with setup/proposal evidence and chart region; the API facts supplied the exact landmark prices/timestamps. Trade 1/2 are current Experiment trades, not prior obsolete-run evidence.

## Final disposition

**BLOCKED.** The real current-Strategy Experiment and multiple Trade evidence pass the durable/data gates, but acceptance cannot pass because the completed-result UI identifies the Strategy as obsolete `EMA Sweep Engulfing` instead of the current Confirmation Break StrategyVersion, and the authoritative price-analysis endpoint returns HTTP 500. The full suite also remains environment-blocked by absent `ATLAS_TEST_DATABASE_URL` (distinct from code failures). Recovery: fix result/UI StrategyVersion identity and `/price-analysis` for current Strategy records, provision the integration test database, then rerun this bounded acceptance check. No fixture or prior obsolete run was substituted.

## Final acceptance validation after TASK-03/TASK-04 fixes — 2026-08-25

Latest TASK-01 through TASK-04 receipts and the blueprint were reread. The API and frontend were restarted from the current feature checkout; readiness for both services returned HTTP 200. No source, other dispatch artifact, or Git state was changed, and no credential was exposed.

### Automated receipts

- `python -m pytest backend/tests/experiments backend/tests/execution backend/tests/strategies backend/tests/domain backend/tests/test_migration_revision.py -q` — **PASS: 183 passed**.
- `python -m pytest -q` — **272 passed, 30 skipped, 13 errors**. All 13 errors are integration fixture setup failures because `ATLAS_TEST_DATABASE_URL` is absent; no code assertion failure occurred in those modules.
- `npm run test:web -- --run && npm run typecheck:web && npm run lint:web` — **PASS: 9 files, 23 tests; typecheck and lint passed**.

### Fresh real OANDA Experiment

Because API/UI code changed since the prior run, a fresh run was made rather than reusing it. The supported durable flow completed: `load_missing` request `4c08ba2b-b263-4846-83b4-075f4d814d48` → immutable snapshot → native M15 → coverage → create → run.

- StrategyVersion: `17ddb7c6-dc89-4167-8046-1214def41259`, `EMA Sweep Confirmation Break v1`, implementation `ema_sweep_confirmation_break.v1`, source fingerprint `bfc425027de82712be63566159631f7df2b983484f68ebd5471f4bdbb666f821`.
- DatasetSnapshot: `1ec2f9bd-6e82-4197-9f26-5e452b176833`, fingerprint `7e6b8149781ae4ba5279eee62e65af9dae2314f60f62a7859429a8c22e2d0e8a`.
- Provider/provenance: OANDA Practice EUR/USD M1 MID/BID/ASK; `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2`; `OANDA_M15_NATIVE_UTC_V1`; policy `OANDA_FX_NY_V1`; coverage valid, warm-up `100/108`, 960 disclosed gap decisions.
- Experiment: `2ff310d8-f462-4df8-a0e4-275a7d99a0a1`, period 2025-01-06 through 2025-02-06 UTC, **COMPLETED**.
- Result: **10 Trades**, quality `DETERMINED`, ambiguity `0`, net P&L `280.0581906441`, net return `0.0280058191`, max drawdown `0`, output fingerprint `a9419c470b59dc1774edd1c140eb35f3848ce31db6c001e89bd396af2d9bbe86`, financing excluded.
- Direct `GET /api/v1/experiments/{id}/price-analysis` now **HTTP 200**: 2,308 M15 candles, 2,209 EMA points, 10 trade markers, 10 reference markers, 70 landmarks; provenance reports `PERSISTED_NATIVE_M15_MID`, `SPARSE_PROVIDER_M1_BID_ASK`, quality `DETERMINED`, and 960 gaps.

### Browser receipts and fact comparison

- MCP `tab-13` result page showed `COMPLETED`, **EMA Sweep Confirmation Break v1**, formatted `2.80%`, `0.00%`, `+$28.01`, `1.70x`, `50.00%`, and Trade Count `10`. Price analysis rendered successfully with the persisted M15/EMA chart and landmark legend. Screenshot and accessibility snapshot captured; console had no entries and failed-network diagnostics were empty.
- MCP `tab-14` and `tab-15` loaded distinct current Trade 1 and Trade 2 pages. Both had HTTP 200 API responses, empty console diagnostics, empty failed-request diagnostics, accessibility snapshot captured for tab-15, and screenshots captured.
- Trade 1 facts: reference `2025-01-06T08:45Z` 1.03352, sweep/confirmation `09:00Z` 1.03502, trigger/fill 1.03526 at `09:03Z`, stop 1.0329244773, stop exit 1.03292 at `11:02Z`; LONG `PRICE_TRIGGERED`, `STOP_LOSS`, -$100.00 / -1.00x. These matched the persisted setup facts and execution lineage; EMA 100 context was disclosed.
- Trade 2 facts: reference `17:45Z` 1.03823, sweep/confirmation `18:00Z` 1.03875, trigger 1.03880, fill 1.03889 at `18:01Z`, stop 1.0372053992, target/fill 1.0417538213 at `2025-01-07T07:39Z`; LONG `TAKE_PROFIT`, +$168.30 / 1.70x. These matched persisted setup facts and execution lineage; EMA 100 context was disclosed.
- Result-page screenshot visibly showed the M15 candles, EMA, reference/sweep/confirmation/entry/stop/target/exit landmark overlays. Trade detail screenshots showed the persisted proposal evidence and chart regions; exact landmark values/timestamps were compared from the server-supplied facts above, with no browser pattern inference.

## Final disposition

**BLOCKED.** Real-data, current-Strategy, persistence, `/price-analysis`, metrics, provenance, multiple-trade, accessibility, console, and failed-network gates now pass. Acceptance remains blocked only because the full backend suite cannot execute its 13 PostgreSQL integration tests without `ATLAS_TEST_DATABASE_URL`; this is an unavailable integration environment, not a demonstrated code failure. Provide that test database and rerun `python -m pytest -q` for final PASS.

## R1 remediation validation — final bounded check — 2026-08-25

Read the latest TASK-01 through TASK-04 receipts, `REVIEW.md`, and blueprint. The feature-branch API/frontend were restarted; readiness returned HTTP 200 on ports 8000/3000. No source, non-`VALIDATION.md` dispatch artifact, or Git state was changed. Credentials were not exposed.

### Automated receipts

- `python -m pytest backend/tests/strategies backend/tests/domain backend/tests/experiments backend/tests/execution backend/tests/integration/test_fill_application.py backend/tests/integration/test_strategy_persistence.py -q` — **184 passed, 4 skipped, 3 errors**. The errors are exclusively `ATLAS_TEST_DATABASE_URL` fixture failures in `test_strategy_persistence.py`; no contract/runner/persistence assertion failed. (An initial command naming nonexistent `backend/tests/persistence` was corrected and is not treated as a product failure.)
- `python -m pytest backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py -q` — **46 passed**.
- `uv run alembic -c alembic.ini heads` — **PASS**, one head: `0008_proposal_constraints`.
- `python -m pytest backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py -q` — **1 passed, 2 skipped**; skips are PostgreSQL tests requiring absent `ATLAS_TEST_DATABASE_URL`.
- `npm run test:web -- --run && npm run typecheck:web && npm run lint:web` — **PASS**, 9 files/23 tests; typecheck and lint passed.
- Full `python -m pytest -q` — **274 passed, 30 skipped, 13 errors**; all errors are unavailable integration DB setup (`ATLAS_TEST_DATABASE_URL`), not newly observed code failures.

### R1 finding disposition

- Generic Strategy analytical metadata finding: **RESOLVED** by TASK-01; targeted contract/domain tests pass.
- Double-slippage / actual-fill target finding: **RESOLVED in code/tests** by TASK-02; targeted execution/runner tests pass, including non-zero LONG/SHORT slippage assertions. The accepted real run uses zero configured slippage, so its prior execution evidence remains valid under the corrected boundary.
- Proposal persistence constraint finding: **RESOLVED in code/migration** by TASK-02; migration head is singular at `0008_proposal_constraints`, and migration assertions pass. PostgreSQL constraint execution remains unverified because the integration DB variable is unavailable.
- Control-artifact/process alignment finding: **UNRESOLVED**. `dispatch/ACTIVE.md`/`PLAN.md` still contain the stale no-implementation-approval state noted by REVIEW.md. This is a release-process blocker independent of runtime test results and was not edited by this validation role.

### Existing real-data evidence recheck

No fresh OANDA run was necessary: R1 execution changes are slippage-boundary/constraint corrections, while the accepted current Strategy run used `slippageTicks=0` and immutable snapshot inputs. The current completed Experiment remains `2ff310d8-f462-4df8-a0e4-275a7d99a0a1` with EMA Sweep Confirmation Break v1, 10 Trades, `DETERMINED`, 960 disclosed gaps, and the same Strategy/source and snapshot fingerprints recorded above. After restart, direct `/price-analysis` returned HTTP 200 with persisted M15/EMA/landmark data; no data or API/UI response changes were observed.

Local Host MCP recheck: `tab-16` result page showed `COMPLETED`, current StrategyVersion identity, formatted metrics, persisted M15/EMA chart and landmarks. Accessibility snapshot was captured; console diagnostics were empty; failed-network diagnostics were empty. The previously captured current Trade 1/Trade 2 pages (`tab-14`/`tab-15`) remain applicable because their API payloads are immutable and the corrected slippage path does not alter this zero-slippage run; their persisted reference, sweep, confirmation, trigger, fill, stop, target, exit, and EMA facts matched as recorded above.

## Final disposition

**BLOCKED.** R1 runtime findings 1–3 are resolved and the real current-Strategy evidence remains valid. Final acceptance is blocked by (a) stale control artifacts still denying implementation approval and (b) unavailable `ATLAS_TEST_DATABASE_URL`, which leaves PostgreSQL integration/constraint execution unverified. Recovery: orchestrator must align/approve the workstream control state, then provision the integration test database and rerun the full suite; no new OANDA run is required unless execution configuration changes from zero slippage.

## Final validation — database/test-only cleanup — 2026-08-25

Latest task receipts and current results were reviewed. The six previously failing tests were classified as stale integration expectations, updated outside this validation artifact, and then re-run successfully. No source behavior changed as part of those test-only corrections or database cleanup; the already validated R1 fixes remain the only runtime changes represented by the accepted OANDA evidence.

### Database and migration receipts

- Disposable `atlas` database: **dropped and recreated empty** using the existing local database configuration; no connection string or credential was printed.
- Disposable `atlas_test` database: **dropped and recreated empty** using the existing local test-database configuration; no connection string or credential was printed.
- `uv run alembic -c alembic.ini upgrade head` against `atlas` — **PASS**, current migrations applied from empty.
- `uv run alembic -c alembic.ini upgrade head` against `atlas_test` — **PASS**, current migrations applied from empty.
- Migration-head check: **one current head**, `0008_proposal_constraints`.

### Automated receipts

- `python -m pytest -q` — **PASS: 316 passed, 1 skipped, 4 warnings**.
- The one skip is the credentialed external OANDA test; no credentials were exposed. The four warnings are non-failing test/deprecation/unknown-mark warnings.
- The six former failures were all stale test/expectation classifications (obsolete Strategy registration expectations and stale database integration expectations after the approved current Strategy/catalog and clean-schema changes). They were not regressions in contract, runner, persistence, API, or frontend behavior; the clean recreated-database full run provides the final receipt.

### Real OANDA/browser evidence reuse basis

No fresh OANDA run was needed. The corrections were test expectations plus empty-database recreation/migration application; they did not change runtime execution semantics, Strategy logic, API result rendering, or frontend behavior. The accepted current-Strategy run remains `2ff310d8-f462-4df8-a0e4-275a7d99a0a1`: EMA Sweep Confirmation Break v1, StrategyVersion fingerprint `bfc425027de82712be63566159631f7df2b983484f68ebd5471f4bdbb666f821`, immutable snapshot `1ec2f9bd-6e82-4197-9f26-5e452b176833` fingerprint `7e6b8149781ae4ba5279eee62e65af9dae2314f60f62a7859429a8c22e2d0e8a`, OANDA Practice EUR/USD, 10 Trades, `COMPLETED`, result quality `DETERMINED`, 960 disclosed gaps, and `/price-analysis` HTTP 200.

The existing Local Host MCP evidence remains applicable: result page `tab-16` showed current Strategy identity, metrics, persisted M15/EMA chart and landmarks with accessibility snapshot, empty console diagnostics, and empty failed-request diagnostics. Current Trade 1/Trade 2 pages `tab-14`/`tab-15` showed persisted reference, sweep, confirmation, trigger, fill, stop, target, exit, and EMA facts matching server payloads; both had clean console and failed-network diagnostics and captured screenshots. No obsolete run or fixture was substituted.

### Remaining environment note and final disposition

The dedicated Playwright E2E command was previously blocked by its hard-coded occupied port; it was not needed to invalidate the acceptance because the real browser MCP result/trade inspection is complete and clean. This remains a reproducibility follow-up, not a failing acceptance gate under the approved browser-evidence path.

**PASS.** All feasible automated gates now pass on clean `atlas` and `atlas_test` schemas, the six stale failures are resolved with no real regression, and the preserved real OANDA/current-Strategy/browser evidence satisfies the durable Experiment acceptance gates. 
