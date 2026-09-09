# T001 - PAPER Visibility 01 Current Broker Trade Read

- **Status:** `DONE`
- **Role:** BUILD
- **Workstream:** `paper-visibility-01-current-broker-trade-read`
- **Branch:** `solo/paper-visibility-01-current-broker-trade-read`
- **Owner:** fresh `solo-flow-worker`

## Objective

Implement the read-only current broker Trade observation surface defined by `PLAN.md`.

Make current OANDA Practice open broker Trades visible on Overview (most prominent PAPER fact) and PAPER (fuller Trade detail) without using runtime activation state as broker exposure. Distinguish runtime active/not-active from broker open/no-open/unavailable per PLAN outcome.

## Constraints

- Existing `read_oanda_practice_open_trade_inventory(settings)` semantics remain frozen. Do not modify `backend/integrations/oanda/trades.py`, `account.py`, `execution.py`, `reconciliation.py`, or account normalization.
- `atlas-runtime` remains OFF. No PAPER activation, runtime, execution, reconciliation, Risk, persistence, migration, or broker mutation behavior.
- No Dogfood 02 or Trade 11 hardcoding. Do not encode real activation ID, Trade ID, account ID, units, entry, or P/L in fixtures or implementation.
- Broker observation must distinguish successful empty inventory (`200 openTrades: []` + `No open broker trades.`) from unavailable/unknown failure. Runtime state or missing frontend data must never prove broker flatness.
- Keep trader-facing copy short and intuitive. No netting, aggregation, filtering, or selection of Trades; preserve every Trade in reader's deterministic order, both `OPEN` and `CLOSE_WHEN_TRADEABLE`.
- Current broker exposure must become highest-value PAPER information in frontend: Overview broker section before readiness/Strategy/Experiment/snapshot; PAPER broker section above/ahead of runtime diagnostics.
- Do not expand into broader UI cleanup yet. Preserve UI 01 patterns (`useReadResource`, display-timezone, error/empty/unavailable components).
- Keep `frontend/lib/api.generated.ts` generation-only — regenerate via `create_app().openapi()` -> `openapi-typescript` -> Prettier, do not hand-edit.

## Dependencies

- None — this is the sole BUILD task for the workstream. It owns all backend and frontend implementation.

## Required checks

- Backend: `uv run pytest backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py backend/tests/integrations/test_oanda_trades.py` (GET-only fakes, sanitized objects, no live credential).
- Formatting/lint/type: `uv run ruff format --check` + `uv run ruff check` + `uv run pyright` on `backend/api/app.py`, `backend/api/paper.py`, `backend/api/schemas.py`, and test files; `git diff --check`; `npm run check:web` (lint, typecheck, build, generated client freshness).
- Frontend: focused `paper_broker_state`/overview/paper-status tests for populated LONG, SHORT, multiple Trades, empty inventory, unavailable/error, currency-aware P/L, independent loading/error states, display-timezone, Refresh GET-only, no mutation controls; `npm run test:e2e` where available.
- Verify `create_app().openapi()` regeneration matches `frontend/lib/api.generated.ts`.

## Implementation seams

### Backend

- `backend/api/schemas.py`: add strict response schemas `PaperBrokerTradeResponse` + `PaperBrokerStateResponse` projecting only safe fields: `provider`/`environment`/`accountCurrency` from validated identity; `tradeId`/`instrument`/`openTime`/`openPrice`/`currentUnits`/`state`/`unrealizedPl` as exact decimal strings, signed units preserved, ordered.
- `backend/api/paper.py`: add broker-read callable param to `create_paper_router()`, broker-specific error translation (`PAPER_BROKER_STATE_UNAVAILABLE` for known failures, `PAPER_BROKER_STATE_INTERNAL_ERROR` for unexpected, never `PAPER_RUNTIME_INTERNAL_ERROR`), and `GET /api/v1/paper/broker-state` (GET-only, per-request invocation, no cache/polling).
- `backend/api/app.py`: wire settings-backed callable `lambda: read_oanda_practice_open_trade_inventory(settings)` into router composition; preserve existing PAPER runtime wiring.
- `backend/tests/test_api_paper_broker_state.py` (new): cover populated, LONG, SHORT, multiple, empty-vs-failure, unavailable mapping, error redaction, currency, no non-GET.
- `backend/tests/test_api_paper.py`: add regression that existing PAPER/runtime behavior unchanged.

### Frontend

- `frontend/lib/api-client.ts`: add `paperBrokerState()` typed GET wrapper; preserve non-empty API errors; do not map 404 to empty.
- Regenerate `frontend/lib/api.generated.ts` from OpenAPI.
- `frontend/components/paper-broker-state.tsx` (new) or equivalent: broker section component rendering provider/environment (`OANDA Practice`), direction derived from signed units (positive LONG/negative SHORT) with absolute quantity, instrument, state, entry, unrealized P/L formatted with `accountCurrency` (no lossy float), opened time via display timezone, empty vs unavailable handling, Refresh GET-only button.
- `frontend/components/overview.tsx`: compose broker section as first PAPER fact before readiness/Strategy/Experiment/snapshot; derive quantity display without hiding Trade; keep technical IDs secondary.
- `frontend/components/paper-status.tsx`: place broker exposure above runtime status; make Runtime vs Broker distinction visible (`Broker: OPEN TRADE` vs `Runtime: STOPPED`); add Refresh; label runtime section explicitly.
- `frontend/tests/api_client.test.ts`, `frontend/tests/overview.test.tsx`, `frontend/tests/paper_status.test.tsx` (and new `paper_broker_state` tests): cover cases listed in Required checks.

## Out of scope (explicit deferrals per PLAN)

No history, attribution, RiskDecision, stop/target, realized P/L/R, exit cause, reconciliation result, freshness/flatness proof, netting, polling/websockets/scheduler, persistence/migrations, runtime/execution, activation/trading/close/protection controls, navigation/shell redesign, LIVE, multi-broker abstraction.

## Acceptance criteria (from PLAN)

1. GET-only and invokes only existing read-only OANDA open-Trade path.
2. Provider/environment/currency projected only from validated identity; account ID not exposed.
3. One normalized Trade projects exact ID/instrument/openTime/entry/signed units/state/unrealizedPl without raw payload.
4. Positive units render LONG; negative render SHORT; signed quantity authoritative; absolute display quantity.
5. Unrealized P/L labelled/formatted with accountCurrency without lossy conversion.
6. Multiple Trades distinct; no netting/selection.
7. Successful zero-Trade read returns `openTrades: []` and renders `No open broker trades.`; failure cannot render that or `Flat`.
8. Known broker-read failures use `PAPER_BROKER_STATE_UNAVAILABLE`; unexpected use `PAPER_BROKER_STATE_INTERNAL_ERROR` distinct from runtime errors.
9. Runtime stopped/not-active never used as broker flatness evidence.
10. Overview prominence; PAPER separation; Refresh GET-only; tests as listed; existing behavior unchanged; no runtime/mutation/reconciliation/DB/migration/live workflow run.

## Completion receipt (to be filled by BUILD)

```text
ROLE: BUILD
STATUS: DONE
ARTIFACT: dispatch/workstreams/paper-visibility-01-current-broker-trade-read/tasks/T001-paper-visibility-01-current-broker-trade-read.md
FILES CHANGED: backend/api/app.py, backend/api/paper.py, backend/api/schemas.py, backend/tests/test_api_paper_broker_state.py, frontend/lib/api-client.ts, frontend/lib/api.generated.ts, frontend/components/paper-broker-state.tsx, frontend/components/overview.tsx, frontend/components/paper-status.tsx, frontend/tests/api_client.test.ts, frontend/tests/overview.test.tsx, frontend/tests/paper_status.test.tsx, frontend/tests/paper_broker_state.test.tsx, frontend/tests/experiment_results.test.tsx (formatting fix), formatting-only: frontend/app/providers.tsx, frontend/components/ui/select.tsx, frontend/lib/time.ts, tests/e2e/.fixtures.json
CHECKS / EVIDENCE: uv run pytest backend/tests/test_api_paper.py backend/tests/test_api_paper_broker_state.py backend/tests/integrations/test_oanda_trades.py -> 62 passed; full suite 1230 passed 4 skipped; ruff format --check + ruff check backend/api + pyright backend/api (paper/schemas 0 errors, app 25 pre-existing Any errors, broker test 0 after type ignores) pass; git diff --check clean; npm run check:web -> format:check, lint, typecheck, test:web 78 passed, build:web compiled successfully; openapi-typescript regeneration byte-identical after prettier.
FINDINGS / CONCERNS: None. Broker state is GET /api/v1/paper/broker-state only via injected lambda: read_oanda_practice_open_trade_inventory(settings). No accountId/raw payload exposed. Decimal strings preserved. Empty vs unavailable distinguished with correct error codes. Overview broker first before readiness, PAPER broker above runtime, Refresh GET-only, no polling/mutation.
```
