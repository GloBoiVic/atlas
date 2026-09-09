# REVIEW - PAPER Visibility 01 Current Broker Trade Read - T001

- **Workstream:** `paper-visibility-01-current-broker-trade-read`
- **Branch:** `solo/paper-visibility-01-current-broker-trade-read`
- **Task:** `T001-paper-visibility-01-current-broker-trade-read`
- **Role:** `REVIEW`
- **Reviewer:** `Muse Spark (REVIEW)`
- **Date:** `2026-09-08`
- **Base:** `main` at `25ebc41` (PLAN approved base `09323c7` + `.DS_Store` ignore `25ebc41`)
- **Inputs reviewed:** `PLAN.md`, `tasks/T001-paper-visibility-01-current-broker-trade-read.md`, `VALIDATION.md`, `git diff main` (unstaged + untracked), `git status`, focused re-execution of `pytest` and `npm run check:web`, OpenAPI inspection

## Verdict: PASS

Workstream satisfies all 23 PLAN acceptance criteria, respects frozen seams and approval gates, preserves error semantics and trader copy, and is supported by executable validation evidence. No code changes required before merge. Minor non-blocking observations noted.

## Classification

**PASS** - `Feature` is correct. Workstream adds a new read-only product route `GET /api/v1/paper/broker-state` `backend/api/paper.py:176` and typed frontend broker sections. No bug-fix or chore misclassification. Lifecycle `BUILD -> VALIDATE PASS -> REVIEW` followed per `PLAN.md:6` and `dispatch/ACTIVE.md:3-7` (`REVIEW` stage, developer approval recorded 2026-09-08).

## Scope

**PASS**

- Implements exactly the PLAN Outcome `PLAN.md:18-29`: make current OANDA Practice open Trades visible on Overview and PAPER without using runtime activation as broker proxy; distinguishes `Runtime: active/not-active` vs `Broker: open/no-open/unavailable`.
- Backend seams match `PLAN.md:66` and `T001:42-44`: `backend/api/schemas.py:522-536` strict projection, `backend/api/paper.py:116-246` GET-only route with injected `broker_state_reader`, `backend/api/app.py:189-200` wiring `lambda: read_oanda_practice_open_trade_inventory(settings)`, `backend/tests/test_api_paper_broker_state.py` (9 tests) + existing `backend/tests/test_api_paper.py` regression.
- Frontend seams match `PLAN.md:55-64`: `frontend/lib/api-client.ts:145-148` typed GET, `frontend/lib/api.generated.ts:434-450,905-932` regenerated, `frontend/components/paper-broker-state.tsx` and integration in `frontend/components/overview.tsx:219-221` and `frontend/components/paper-status.tsx:189-191`, plus `frontend/tests/paper_broker_state.test.tsx` / `overview.test.tsx` / `paper_status.test.tsx` / `api_client.test.ts`.
- No scope required by PLAN is missing. Deferrals respected: no history, attribution, RiskDecision, stop/target, realized P/L/R, exit cause, reconciliation, freshness, netting, polling, websocket, scheduler, persistence, migration, runtime, execution, activation/trading/close controls, or LIVE behavior introduced.
- Extra diff beyond expected file list is limited to formatting-only prettier changes in `frontend/app/providers.tsx`, `frontend/lib/time.ts`, `frontend/components/ui/select.tsx`, `tests/e2e/.fixtures.json` - see MINOR finding M01. No functional scope creep.

## Approval and Frozen Seams

**PASS**

- Approval gate satisfied per `PLAN.md:556-575`: PLAN approved 2026-09-08 before `GIT START`; `dispatch/ACTIVE.md` correctly tracks `REVIEW` stage; branch `solo/paper-visibility-01-current-broker-trade-read` created from clean tracked worktree at `25ebc41`.
- Frozen integration seam untouched: `git diff main -- backend/integrations/oanda/trades.py` is 0 lines (re-executed `uv run python` inspection confirms `read_oanda_practice_open_trade_inventory` reused unchanged via composition). Likewise `backend/integrations/oanda/account.py`, `execution.py`, `reconciliation.py` unchanged. Frozen product seams unchanged: `git diff main -- backend/runtime backend/risk backend/persistence/migrations` is 0.
- If endpoint could not be composed without changing frozen reader, PLAN required `BLOCKED`. Composition succeeded via existing `OandaPracticeOpenTradeInventory` and `OandaPracticeOpenTrade` facts, so no BLOCKED condition triggered.

## Error Semantics

**PASS**

- Known broker observation failures (missing/invalid config, account binding, auth, transport, provider response, normalization) correctly map to `503 PAPER_BROKER_STATE_UNAVAILABLE` with safe message `Current broker state is unavailable.` `backend/api/paper.py:191-208` + per-branch `logger.warning`. Not reused via runtime `_invoke` path.
- Unexpected implementation failures map to `500 PAPER_BROKER_STATE_INTERNAL_ERROR` with `Current broker state could not be read.` `backend/api/paper.py:209-219` via `logger.error`. Distinct from `PAPER_RUNTIME_INTERNAL_ERROR` `backend/api/paper.py:108`. Test `test_broker_state_internal_error_distinct_from_runtime` asserts distinction.
- Null reader (mis-wired composition) also fails closed to `503 PAPER_BROKER_STATE_UNAVAILABLE` `backend/api/paper.py:178-188`.
- All failure paths redact: `OandaError` and generic paths discard exception text, provider body, credentials, tokens, account IDs. Backend tests `test_broker_state_unavailable_for_known_failures_and_redacts` and `test_broker_state_internal_error_distinct_from_runtime` assert `secret not in resp.text`, `provider body not in resp.text.lower()`, `top-secret-token not in resp.text`.
- HTTP 200 with `openTrades: []` is the only path rendering `No open broker trades.`; failure paths never render that or `Flat`. Frontend `paper-broker-state.tsx:150-151` renders `EmptyState` only in `ready && length===0`, error branch renders `ReadError` + `UnavailableState: Broker unavailable` `paper-broker-state.tsx:136-140`.
- Active-activation `404 PAPER_ACTIVATION_NOT_ACTIVE` never represents empty broker inventory. Frontend `atom` does not map `paperBrokerState` 404 to null `frontend/lib/api-client.ts:145-148` vs `activePaperStatus` catch `frontend/lib/api-client.ts:152-160`; test `does not map paper broker 404 to empty` asserts rejection. Backend `GET-only` verified: OpenAPI `['get']` only, test `test_broker_state_is_get_only` asserts 405 for POST/PUT/DELETE/PATCH, per-request invocation verified (2 GETs -> 2 calls).

## Frontend Prominence and Trader Copy

**PASS**

- Overview: broker is first high-level PAPER fact `frontend/components/overview.tsx:219-221` as `lg:col-span-2` before readiness, Strategy, Experiment, snapshot. Test `shows broker exposure first with LONG ...` asserts `brokerIdx < readinessIdx`.
- PAPER: fuller broker section in standalone card above capability/runtime grid `frontend/components/paper-status.tsx:189-191`; headings distinct `PAPER broker state` `paper-broker-state.tsx:114` vs `Runtime status` `paper-status.tsx:145` with subtext `Runtime is Atlas activation state, not broker exposure.` and `Broker exposure, not runtime.` `paper-broker-state.tsx:117-119`. Tests `places broker exposure above runtime ...` assert `brokerIdx < runtimeIdx`.
- Copy is short/trader-facing per `PLAN.md:164`: `OANDA Practice` provider/environment, `LONG`/`SHORT` derived from signed units `paper-broker-state.tsx:29-31`, absolute quantity `formatUnitsAbsolute` `paper-broker-state.tsx:19-27` (`390,663 units`), `OPEN`/`CLOSE_WHEN_TRADEABLE` state preserved, `Instrument`, `Entry`, `Unrealized P/L` with `accountCurrency` labeling `paper-broker-state.tsx:80-85`, `Opened` via display timezone `formatInstant(trade.openTime, timeZone)` `paper-broker-state.tsx:90`.
- Technical IDs not prominent: `Trade {tradeId}` rendered as muted `text-xs font-mono` secondary detail `paper-broker-state.tsx:94-96`.
- Decimal/sign behavior correct without lossy conversion: API preserves `str(trade.current_units/open_price/unrealized_pl)` `backend/api/paper.py:228-232`; frontend `formatUnitsAbsolute` and `formatUnrealized` `paper-broker-state.tsx:19-44` use string ops, no `Number()`/`parseFloat`, groups integers and keeps exact `0.00001`. Tests `decimal_strings_exact`, `formats unrealized P/L with currency without lossy float` assert `0.00001`/`$0.00001` exact.
- Multiple Trades preserved distinct, ordered, no netting: backend loop preserves `inventory.trades` order, test `preserves_multiple_trades...` verifies `["3","20","100"]` and `["-20","30","10"]`; frontend `map` with `key={trade.tradeId}` renders all, tests `renders multiple trades distinct` / `shows multiple Trades distinct without netting` assert both `LONG`/`SHORT` and both quantities present.
- Refresh is explicit GET-only user action: `Refresh` button `paper-broker-state.tsx:121-129` calls `retry` -> `useReadResource` -> `atlasApi.paperBrokerState()` GET; tests `refresh triggers GET-only retry` assert `1 -> 2` calls, `queryByText(/Buy|Sell|Close|Activate|Stop|Reconcile/)` not present. No polling, websockets, schedulers, or mutation controls added.
- No overreach in copy: no fresh/reconciliation/flatness proof, no realized P/L/R, no Risk, no attribution, no account ID/credential/raw payload/Strategy linkage.

## No Overreach

**PASS**

- Workstream is read-only observation: one `lambda: read_oanda_practice_open_trade_inventory(settings)` per GET `backend/api/app.py:196`, no cache/polling/background work/mutation. `git diff main --stat` shows no files in `backend/paper`, `backend/runtime`, `backend/risk`, `backend/persistence`, `Dockerfile`/`docker-compose`. `atlas-runtime` OFF preserved, no activation/stop/reconcile/execution operation performed.
- Frozen Dogfood path respected `PLAN.md:100-113`: no activation restart/reuse/reconcile/reconstruction, no broker Trade modified/closed, no real Dogfood activation/Trade/account/units/entry/P/L encoded. Fixtures use synthetic IDs `7`/`20`/`3`/`100` with USD and EUR_USD; sanitized test account `001-011-5838423-001` is the reusable test identity from existing `test_api_paper_broker_state.py` (see MINOR M02), not a Dogfood Trade 11 value.

## Validation Evidence Supports Merge

**PASS** - independently re-executed:

- `uv run ruff format --check backend/api/app.py backend/api/paper.py backend/api/schemas.py backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py` -> PASS (5 files already formatted). Full-backend drift (68 files would be reformatted, 28 ruff check errors) acknowledged as pre-existing `main` drift outside T001 scope; scoped `backend/api` passes `uv run ruff check backend/api` -> All checks passed.
- `uv run pyright backend/api/paper.py backend/api/schemas.py` -> 0 errors. `backend/api/app.py` 25 Any errors are pre-existing `main` identical; full `backend/api` 145 errors pre-existing, 0 new in T001 files.
- `uv run pytest backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py -v` -> 16 passed (9 broker-state + 7 paper). Focused `backend/tests/integrations/test_oanda_trades.py` is 46 passed per VALIDATION (not re-run credential-free). Full `uv run pytest -m "not integration and not external" -q` -> 1230 passed, 4 skipped (re-confirmed).
- `npm run check:web` -> PASS: `lint` 0 errors / 242 warnings (pre-existing), `typecheck` 0 errors, `test:web` 78 passed (17 files) including 8 `paper_broker_state`, 11 `overview`, 10 `paper_status`; `build:web` compiled successfully (Next.js 16.3.0 TSS).
- `git diff --check` -> clean (no whitespace errors).
- OpenAPI regeneration: `create_app().openapi()` -> broker-state path contains only `get`; committed `frontend/lib/api.generated.ts` `broker_state_api_v1_paper_broker_state_get` and schemas `PaperBrokerStateResponse`/`PaperBrokerTradeResponse` match fresh generation after `openapi-typescript` + `prettier --config .prettierrc.json` (byte-identical). Verified via `uv run python` inspection: `accountId` absent from broker-state schemas/responses; `PaperBrokerTradeResponse` exposes only `tradeId/instrument/openTime/openPrice/currentUnits/state/unrealizedPl` as strings.
- Frontend generation: `frontend/lib/api.generated.ts` not hand-edited (only via toolchain).

VALIDATION.md verdict `PASS` is substantiated by evidenced checks above. E2E not executed due to harness port conflict `http://127.0.0.1:8000/health/ready is already used` (see MINOR M03) does not invalidate this read-only workstream; web build is the proxy per VALIDATION.

## Findings

### CRITICAL
None.

### IMPORTANT
None.

### MINOR

- **M01 - Formatting-only files outside expected list but within no-risk scope.** `frontend/app/providers.tsx`, `frontend/lib/time.ts`, `frontend/components/ui/select.tsx`, `tests/e2e/.fixtures.json` appear in `git status` / `git diff main --stat` (17 files) as pure `prettier`/`ruff` line-break expansions. They do not change behavior (`time.ts` logic identical, `providers.tsx` same semantics, `select.tsx` whitespace). Included in branch without being in PLAN Expected files `PLAN.md:116-123`. Not blocking; keep as is, no production seam impact. Recommend squash note on merge.

- **M02 - Sanitized test account ID reuse.** `backend/tests/test_api_paper_broker_state.py:33` uses `001-011-5838423-001` as `OandaPracticeAccountIdentity` fixture. This is a reusable sanitized test identity (also present in historical tests), distinct from Dogfood Trade 11 and not encoding real entry/units/P/L. Meets PLAN Dogfood constraint `PLAN.md:102-108` but worth flagging for provenance clarity. No remediation required.

- **M03 - E2E not executed in validation.** `npm run test:e2e` was not executed (harness port conflict) per VALIDATION.md Gaps. `npm run check:web` including `build:web` passed as the safe proxy per PLAN Validation plan `PLAN.md:100-102`. No T001-specific E2E was required. Not blocking for this GET-only projection workstream; re-run E2E in next pipeline if harness available.

- **M04 - Full-backend `ruff`/`pyright` drift.** `uv run ruff format --check backend` (68 files) and `uv run ruff check backend` (28 errors) and `uv run pyright backend/api` (145 errors) report pre-existing drift on `main` identical to branch. Scoped `backend/api` + target files pass. Not a T001 regression.

- **M05 - `dispatch/ACTIVE.md` housekeeping.** Branch leaves `dispatch/ACTIVE.md:3-7` at `REVIEW` stage, which is expected pre-merge. Post-merge SoloFlow housekeeping should revert to `# No active workstream` per `VALIDATION.md:177`.

## Constraints Verification

- `Do not edit application code.` - This REVIEW performed no edits; only reading and re-execution.
- All numerical verification via executed commands, not mental math.
- Prose vs implementation: no stale-prose silent fix applied; PLAN ownership verified, implementation matches durable PLAN contract.

## Recommendation

**MERGE APPROVED.** No remediation required. Proceed to merge after explicit trader merge approval per `PLAN.md:567-575`. Ensure new files `backend/tests/test_api_paper_broker_state.py`, `frontend/components/paper-broker-state.tsx`, `frontend/tests/paper_broker_state.test.tsx`, and workstream docs are included in the merge commit (currently untracked/unstaged in this worktree snapshot).
