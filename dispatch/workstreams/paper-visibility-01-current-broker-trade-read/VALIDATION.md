# VALIDATION - PAPER Visibility 01 Current Broker Trade Read - T001

- **Workstream:** `paper-visibility-01-current-broker-trade-read`
- **Branch:** `solo/paper-visibility-01-current-broker-trade-read`
- **Task:** `T001`
- **Role:** `VALIDATE`
- **Date:** `2026-09-08`
- **Validator:** `Muse Spark (VALIDATE)`
- **Base:** `main` at `25ebc41` (PLAN base `09323c7` + `.DS_Store` ignore)

## Verdict: PASS

T001 implements the read-only current broker Trade observation surface as specified in `PLAN.md` and `T001-paper-visibility-01-current-broker-trade-read.md`. All 23 acceptance criteria are satisfied. Backend GET-only contract, safe projection, decimal/sign behavior, error-code distinction, prominence, and Refresh semantics are evidenced. No runtime, mutation, reconciliation, persistence, migration, or live broker workflow was introduced or executed.

## Scope Checked

- `backend/api/app.py:189-200` - wires `lambda: read_oanda_practice_open_trade_inventory(settings)` into `create_paper_router`
- `backend/api/paper.py:116-246` - `GET /api/v1/paper/broker-state`, `broker_state_reader` callable, broker-specific error translation, safe projection
- `backend/api/schemas.py:522-536` - strict `PaperBrokerTradeResponse` / `PaperBrokerStateResponse` (camelCase, `extra="forbid"`, decimal strings)
- `backend/tests/test_api_paper_broker_state.py:1-283` - 9 focused broker-state tests
- `backend/tests/test_api_paper.py` - unchanged PAPER/runtime regression
- `backend/integrations/oanda/trades.py` - unchanged (frozen reader)
- `frontend/lib/api-client.ts:145-148` - typed `paperBrokerState()` GET wrapper
- `frontend/lib/api.generated.ts:434-450,905-932` - regenerated OpenAPI contract
- `frontend/components/paper-broker-state.tsx:1-173` - broker section, LONG/SHORT derivation, currency-aware P/L, absolute quantity, Refresh, empty/unavailable handling
- `frontend/components/overview.tsx:17,219-221` - broker as first PAPER fact, `lg:col-span-2` before readiness
- `frontend/components/paper-status.tsx:7,145,189-191` - broker above runtime, runtime section explicitly `Runtime status`
- `frontend/tests/paper_broker_state.test.tsx`, `frontend/tests/overview.test.tsx`, `frontend/tests/paper_status.test.tsx`, `frontend/tests/api_client.test.ts`

## Evidence Executed

| Check | Command | Result |
|-------|---------|--------|
| uv sync | `uv sync --all-groups` | PASS - 38 packages checked |
| ruff format (scoped) | `uv run ruff format --check backend/api/app.py backend/api/paper.py backend/api/schemas.py backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py` | PASS - 5 files already formatted |
| ruff check (scoped) | `uv run ruff check backend/api backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py` | PASS - All checks passed |
| ruff check (full backend) | `uv run ruff check backend` | 28 pre-existing errors in unrelated modules (not in `backend/api` scope); not a T001 regression |
| ruff format (full backend) | `uv run ruff format --check backend` | 68 files would be reformatted (pre-existing drift outside T001 scope); scoped check passes |
| pyright (target files) | `uv run pyright backend/api/paper.py backend/api/schemas.py` | PASS - 0 errors |
| pyright (app.py) | `uv run pyright backend/api/app.py` | 25 errors (pre-existing `Any`/`None` optional-access in `create_app` factory; identical on `main`) |
| pyright (full backend/api) | `uv run pyright backend/api` | 145 pre-existing errors (historical_data, strategies, etc.); 0 new in T001 files |
| pytest (focused) | `uv run pytest backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py backend/tests/integrations/test_oanda_trades.py -v` | PASS - 62 passed (7 paper + 9 broker-state + 46 trades) |
| pytest (non-integration) | `uv run pytest -m "not integration and not external" -q` | PASS - 1230 passed, 4 skipped |
| npm check:web | `npm run check:web` (format:check, lint, typecheck, test:web, build:web) | PASS - lint 0 errors/242 warnings, typecheck 0 errors, test:web 78 passed (17 files), build compiled successfully |
| frontend tests | `vitest run --config frontend/vitest.config.ts` | 78 passed including 8 paper_broker_state, 11 overview, 10 paper_status |
| e2e | `npm run test:e2e` | Not executed - `http://127.0.0.1:8000/health/ready is already used` (pre-existing harness port conflict, not T001-related); exit 0 |
| git diff --check | `git diff --check` | PASS - clean (no whitespace errors) |
| openapi regeneration | `create_app().openapi() -> openapi-typescript -> prettier --config .prettierrc.json` | PASS - byte-identical to `frontend/lib/api.generated.ts` when using repo prettier config (`singleQuote:true`); raw `openapi-typescript` uses double quotes, prettier normalizes to single quotes matching committed file |
| broker-state method | `spec['paths']['/api/v1/paper/broker-state']` | `['get']` only |
| accountId leakage | `grep -r accountId` in spec + `assert "accountId" not in resp.text` tests | PASS - not exposed in schemas, responses, or error redaction tests |
| no-runtime | `grep -r "atlas-runtime" dispatch` / `git diff main -- backend/runtime` | PASS - no activation/start, `backend/runtime` unchanged, `atlas-runtime` OFF preserved |
| no-mutation | `grep` for polling/websocket/Buy/Sell/Close controls in `paper-broker-state.tsx` | PASS - none, only `Refresh` GET-only button |

## Acceptance Criteria (23) - All PASS

### 1. GET-only, existing read-only OANDA path
**PASS** - `backend/api/paper.py:176` declares `@router.get("/broker-state")`; `backend/api/app.py:196` injects `lambda: read_oanda_practice_open_trade_inventory(settings)` per-request invocation. Test `test_broker_state_is_get_only` asserts 405 for POST/PUT/DELETE/PATCH. Test `test_broker_state_invoked_per_request_and_no_account_id_exposed` asserts per-request call count `2` for `2` GETs. OpenAPI shows only `get` operation.

### 2. Provider/environment/currency from validated identity
**PASS** - `backend/api/paper.py:234-243` projects `provider`/`environment`/`account_currency` solely from `inventory.identity`. Identity is `OandaPracticeAccountIdentity` validated by frozen `read_oanda_practice_open_trade_inventory`. No hardcoded currency: `str(inventory.identity.base_currency)` is used. Successful response example matches `USD` from identity.

### 3. Provider account ID not exposed
**PASS** - No `provider_account_id` in `PaperBrokerStateResponse` / `PaperBrokerTradeResponse` schemas (`backend/api/schemas.py:522-536`, OpenAPI verification shows `accountId` absent). `backend/api/paper.py:220-244` never maps `provider_account_id`. Tests assert `"accountId" not in resp.text`, `"providerAccountId" not in data`, `"providerAccountId" not in str(body)`, `"001-011" not in r.text`.

### 4. One normalized Trade projects exact facts without raw payload
**PASS** - `backend/api/paper.py:221-233` maps `trade_id`/`instrument`/`open_time`/`open_price`/`current_units`/`state`/`unrealized_pl` as `str(...)` and ISO8601 `Z` conversion. No raw keys (`closingTransactionIDs`, `takeProfitOrder`) - test `test_broker_state_invoked_per_request...` asserts absence. `test_broker_state_projects_long...` verifies `tradeId`, `instrument`, `openPrice`, `currentUnits`, `state`, `unrealizedPl` exact.

### 5. Positive units render LONG with absolute quantity
**PASS** - `frontend/components/paper-broker-state.tsx:29-31` derives `LONG` for non-negative, `frontend/components/paper-broker-state.tsx:19-27` strips sign and groups `390663 -> 390,663`. Test `renders LONG for positive units` and `overview.test.tsx: shows broker exposure first with LONG` both assert `LONG` + `390,663 units` / `5,000 units`.

### 6. Negative units render SHORT with absolute quantity
**PASS** - Same derivation with `startsWith('-') -> SHORT`, absolute via `slice(1)`. Test `renders SHORT for negative units` asserts `SHORT` + `390,663 units` + `-$410.20`; integration test `test_broker_state_projects_short_negative_units` verifies `-390663` and `CLOSE_WHEN_TRADEABLE`.

### 7. Signed quantity authoritative in API contract
**PASS** - API preserves signed string: `str(trade.current_units)` yields `"-390663"` for SHORT. Tests `test_broker_state_projects_long...` (`390663`) and `test_broker_state_projects_short...` (`-390663`) assert signed strings remain; `typeof currentUnits === 'string'` checked. Frontend derives direction but never replaces API sign.

### 8. Unrealized P/L labelled/formatted with accountCurrency without lossy conversion
**PASS** - `frontend/components/paper-broker-state.tsx:33-44` formats via string operations (no `Number()`/`parseFloat`), prefixing `$` for `USD` else `value currency`. Keeps exact `0.00001`. Test `formats unrealized P/L with currency without lossy float` asserts `$0.00001`; test `renders LONG...` asserts `$10.00`; `overview` asserts `-$410.20`.

### 9. Multiple Trades distinct and all rendered
**PASS** - Backend preserves `inventory.trades` order, appending each independently (`backend/api/paper.py:220-233`). Test `test_broker_state_preserves_multiple_trades...` verifies 3 IDs `["3","20","100"]` and units `["-20","30","10"]`. Frontend maps `openTrades.map(...)` with `key={trade.tradeId}`; tests `renders multiple trades distinct` and `shows multiple Trades distinct without netting` assert both `LONG`/`SHORT` and both quantities present.

### 10. No netting or arbitrary selection
**PASS** - No aggregation, netting, or filtering in `backend/api/paper.py` (simple loop, no reduce). Tests assert `len(ids)==3`, `units == ["-20","30","10"]` (no net sum), and frontend tests assert both `100 units` and `200 units` coexist. PLAN prohibition `Do not net, aggregate, select, filter` satisfied.

### 11. Successful zero-Trade read returns explicit empty inventory and renders `No open broker trades.`
**PASS** - `backend/tests/test_api_paper_broker_state.py:206-213` asserts `200` with `openTrades == []` and `accountCurrency`. Frontend `paper-broker-state.tsx:150-151` renders `<EmptyState>No open broker trades.</EmptyState>` only when `status==='ready' && length===0`. Tests `shows empty inventory only for successful empty` (broker_state, overview, paper_status) all assert text present and `Broker unavailable` absent on success.

### 12. Configuration/provider/transport/auth/normalization failure renders unavailable/unknown
**PASS** - `backend/api/paper.py:191-208` catches `OandaError` -> 503 `PAPER_BROKER_STATE_UNAVAILABLE` with safe message. Test `test_broker_state_unavailable_for_known_failures_and_redacts` covers `OandaConfigurationError`, `OandaRequestError`, `OandaNormalizationError` all mapping to 503. Frontend `paper-broker-state.tsx:136-140` renders `<UnavailableState>Broker unavailable</UnavailableState>` + `ReadError` on `state.status==='error'`.

### 13. Failure cannot render `No open broker trades.`, `Flat`, or equivalent
**PASS** - Frontend `paper-broker-state.tsx` renders empty state only in `ready` branch, never in `error` branch. Tests `shows unavailable on error` / `shows Broker unavailable on failure not flat` assert `queryByText('No open broker trades.')` is null and `queryByText('Flat')` is null when rejected.

### 14. Known broker-read failures use `PAPER_BROKER_STATE_UNAVAILABLE`
**PASS** - `backend/api/paper.py:183-208` uses code `PAPER_BROKER_STATE_UNAVAILABLE` for `broker_state_reader is None` and for `isinstance(error, OandaError)`. Test `test_broker_state_unavailable...` asserts `error.code == "PAPER_BROKER_STATE_UNAVAILABLE"` and message `Current broker state is unavailable.`.

### 15. Unexpected internal failures distinct from runtime errors
**PASS** - `backend/api/paper.py:209-219` maps non-Oanda exceptions to `PAPER_BROKER_STATE_INTERNAL_ERROR` (500, message `Current broker state could not be read.`), not `PAPER_RUNTIME_INTERNAL_ERROR`. Test `test_broker_state_internal_error_distinct_from_runtime` asserts code `PAPER_BROKER_STATE_INTERNAL_ERROR` and `!= "PAPER_RUNTIME_INTERNAL_ERROR"`. Existing `_invoke` for runtime still uses `PAPER_RUNTIME_INTERNAL_ERROR` (`backend/api/paper.py:108`), keeping distinction.

### 16. Runtime stopped/not-active never used as broker flatness evidence
**PASS** - `frontend/components/paper-broker-state.tsx` never reads `activePaperStatus`; `frontend/components/paper-status.tsx` keeps broker and runtime in independent `useReadResource` sections with separate loading/error states. Tests `keeps a failed section visible while known sections remain populated` and `places broker exposure above runtime` confirm independence. Empty runtime result (` null` -> `PAPER_ACTIVATION_NOT_ACTIVE`) is tested as distinct from broker empty.

### 17. No account ID, credential, raw payload, attribution, Risk, protection, realized-result, or exit-cause claim exposed
**PASS** - Schemas and route expose only safe fields (see AC3/4). Error branches redact `secret not in resp.text`, `"provider body" not in resp.text.lower()`, and sanitize via `_http_error` / broker-specific catch that discards exception text. Tests verify redaction. No Risk/strategy/exit fields in response.

### 18. Overview prominence without broad UI redesign
**PASS** - `frontend/components/overview.tsx:219-221` renders `<PaperBrokerStateSection compact />` as first grid item `lg:col-span-2` before readiness/strategy/experiment. Test `shows broker exposure first with LONG derived...` computes heading indices and asserts `brokerIdx < readinessIdx`. Remaining Overview structure (readiness, strategy, experiment, capability sections) preserved per T001 constraints.

### 19. PAPER clearly separates broker observation from Atlas runtime status
**PASS** - `frontend/components/paper-status.tsx:189-198` places broker in standalone `rounded-lg` above the existing two-column runtime/capability grid. Headings are distinct: `PAPER broker state` (`paper-broker-state.tsx:114`) vs `Runtime status` (`paper-status.tsx:145`) with subtext `Runtime is Atlas activation state, not broker exposure`. Tests `places broker exposure above runtime and broker before readiness` assert `brokerIdx < runtimeIdx`.

### 20. PAPER has explicit GET-only Refresh action
**PASS** - `frontend/components/paper-broker-state.tsx:121-129` renders `Refresh` button (`onClick={retry}`) only when `status !== 'loading'`, invoking `useReadResource` retry which re-calls `atlasApi.paperBrokerState()` (GET only, `frontend/lib/api-client.ts:145-148`). Tests `refresh triggers GET-only retry` / `refresh retries broker state GET only` assert mock called `1 -> 2` after click, and `screen.queryByText(/Buy|Sell|Close|Activate|Stop|Reconcile/)` not present. No polling/websocket/scheduler introduced.

### 21. Focused backend and frontend tests cover required cases
**PASS** - Backend: populated LONG (`projects_long`), SHORT (`projects_short_negative`), multiple distinct (`preserves_multiple`), empty-vs-failure (`empty_is_explicit`), unavailable mapping + redaction (`unavailable_for_known_failures`), internal error distinction (`internal_error_distinct`), GET-only (`is_get_only`), per-request + no accountId (`invoked_per_request`), decimal exactness (`decimal_strings_exact`). Frontend: `paper_broker_state.test.tsx` covers all 8 cases (LONG, SHORT, multiple, empty, unavailable, timezone, Refresh GET-only, no mutation); `overview.test.tsx` 11 tests; `paper_status.test.tsx` 10 tests; `api_client.test.ts` includes `paperBrokerState` GET.

### 22. Existing PAPER/runtime/execution behavior unchanged
**PASS** - `backend/tests/test_api_paper.py` (7 tests) all pass, including `test_paper_routes_project_all_control_and_status_seams` and `test_paper_active_and_detail_routes_use_safe_not_found_contracts`. No changes to activation/stop/reconcile routes or runtime service wiring except additive `broker_state_reader` param (default `None`). `git diff main -- backend/runtime backend/risk backend/persistence/migrations` shows no changes.

### 23. No runtime, mutation, reconciliation, database, migration, or live broker mutation workflow run
**PASS** - No new migrations (`backend/persistence/migrations` unchanged), no `docker-compose` changes, `atlas-runtime` not started (only referenced in `backend/runtime/main.py` logs, not invoked). Integration tests use injected fakes with sanitized `OandaPracticeOpenTrade` / `OandaPracticeOpenTradeInventory`; no credentialed live read. Frozen file `backend/integrations/oanda/trades.py` untouched (`git diff main -- backend/integrations` empty).

## Additional PLAN Requirements

### Backend GET-only contract, safe projection, decimal/sign
**PASS** - See AC1/4/7/8. Wire types are `str` for `openPrice`/`currentUnits`/`unrealizedPl` (Pydantic `StrictModel` + `str(Decimal)`). `openTime` is `isoformat Z` without exposing raw provider payload.

### Currency
**PASS** - `accountCurrency` projected from `inventory.identity.base_currency` (PLAN: `only to label monetary broker facts accurately`), not hardcoded. Frontend uses it to format P/L without `float`.

### Empty vs unavailable
**PASS** - Empty: `200 openTrades: []` + `No open broker trades.`; Failure: `503 PAPER_BROKER_STATE_UNAVAILABLE` or `500 PAPER_BROKER_STATE_INTERNAL_ERROR` + `Broker unavailable`, never empty.

### Error codes
**PASS** - `PAPER_BROKER_STATE_UNAVAILABLE` for known OandaError, `PAPER_BROKER_STATE_INTERNAL_ERROR` for unexpected, never `PAPER_RUNTIME_INTERNAL_ERROR` for broker path.

### No accountId, no netting, ordering
**PASS** - No account ID in schemas/responses/logs; no netting/selection; preserves reader's deterministic order (inventory sorts by tradeId; API preserves iteration order; tests verify `["3","20","100"]`).

### Runtime vs broker distinction
**PASS** - Headings, copy, and independent `useReadResource` states make `Broker: OPEN TRADE` vs `Runtime: STOPPED / No active runtime` visible; broker section subtext `Broker exposure, not runtime.`

### Prominence
**PASS** - Overview broker `lg:col-span-2` first; PAPER broker standalone card before capability/runtime grid.

### Refresh GET-only, no mutation
**PASS** - `Refresh` button calls only `retry` -> `atlasApi.paperBrokerState()` GET; no POST/PATCH/DELETE to broker-state; tests assert no mutation controls `Buy|Sell|Close|Activate|Stop|Reconcile`.

### Frozen reader semantics
**PASS** - `read_oanda_practice_open_trade_inventory(settings)` reused unchanged; no modification to `backend/integrations/oanda/trades.py`, `account.py`, `execution.py`, `reconciliation.py`.

### Docker/RISK/persistence unchanged
**PASS** - `git diff main --stat` shows 0 files in `backend/persistence`, `backend/risk`, `backend/runtime`, `Dockerfile`/`docker-compose.yml`.

### Frontend/browser checks
**PASS with note** - `npm run check:web` passes (format, lint 242 warnings, typecheck, 78 tests, build). Browser checks not executed in headless validation; component uses responsive `grid gap-x-6 gap-y-3 sm:grid-cols-2`, `text-sm`/`text-xs` readable sizes, independent loading/error states verified via tests.

### No atlas-runtime, no PAPER activation, no broker mutation
**PASS** - No `atlas-runtime` process started, no `activate`/`stop`/`reconcile` invoked, endpoint is observation-only GET.

## Gaps / Findings / Remediation Required

**None blocking.** The following are noted for transparency, not remediation:

1. **Pre-existing backend formatting drift** - `uv run ruff format --check backend` reports 68 files would be reformatted; `uv run ruff check backend` reports 28 errors. Both are outside T001 scope (`backend/api` scoped checks pass) and identical to `main` drift. No action required for this workstream.

2. **Pre-existing pyright strictness** - `uv run pyright backend/api` reports 145 errors, `backend/api/app.py` reports 25 `Any` errors; all pre-existing (`main` has same). Target files `backend/api/paper.py` + `backend/api/schemas.py` are 0 errors. Not a regression.

3. **Full-width formatting-only files** - `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`, `tests/e2e/.fixtures.json` are formatting-only changes unrelated to broker logic but included in branch; their ruff/prettier changes are clean and do not affect behavior.

4. **E2E not executed** - `npm run test:e2e` aborted due to `http://127.0.0.1:8000/health/ready is already used` (harness port conflict); web build succeeded as proxy. No T001-specific E2E was required by PLAN beyond `npm run check:web`.

5. **Dogfood boundary preserved** - No fixture or implementation encodes real Dogfood activation/Trade/account IDs. Test fixtures use synthetic IDs (`7`, `20`, `001-011-5838423-001` is a reusable sanitized test account in `test_api_paper_broker_state.py` distinct from Dogfood Trade 11).

## Recommendation

**MERGE APPROVED** after independent REVIEW. No code changes required before merge. Ensure `dispatch/ACTIVE.md` reverts to `# No active workstream` if required by SoloFlow post-merge housekeeping (current branch has workstream ACTIVE entry, which is expected pre-merge).
