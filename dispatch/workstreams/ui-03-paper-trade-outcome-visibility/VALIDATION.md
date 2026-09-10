# VALIDATION - UI 03 PAPER Trade Outcome Visibility

## Result

- **Status:** `FAIL`
- Independent validation found two `PRODUCT / DEFECT` findings. The implementation is otherwise within the approved scope, and no capital-capable behavior was activated.

- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Role:** `VALIDATE`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`

## Findings

### F-001 — Bounded query can omit completed Trades

- **Classification:** `PRODUCT / DEFECT`
- **Location:** `backend/paper/trade_history.py:96-137`
- The SQL query joins every schema-V2 `TRADE_DETAIL` observation and applies `.limit(limit)` before Python validates `state == CLOSED`, required closure facts, and matching Fill/Trade identity.
- The SQL query has no CLOSED-state predicate. PostgreSQL descending ordering places a missing `close_time` before non-null values, so an open observation can consume the requested limit before a valid completed Trade is composed.
- The final Python sort cannot recover completed rows that were excluded by the SQL limit. Raw JSON timestamp ordering can also differ from chronological ordering when persisted timestamps use different offsets.
- This violates the recent-history contract for newest-close-first bounded results. The focused unit tests do not catch it because their fake session ignores SQL ordering and limiting.

### F-002 — Initial risk is presented as a price

- **Classification:** `PRODUCT / DEFECT`
- **Location:** `frontend/components/paper-trade-history.tsx:194-197`
- Durable `actual_initial_risk` is the filled quantity multiplied by the entry/Stop distance and is an account-risk amount (`backend/integrations/oanda/execution.py:778-786`, `backend/paper/execution.py:326-352`).
- The full history card passes it through `priceLabel`, which uses `formatPrice` and five decimal places, instead of `formatMoney` used for realized P/L and financing.
- A value such as `98.1150` is therefore shown as `98.11500`, without currency or money rounding, while labeled `Initial risk`. This is misleading in the fuller PAPER history view.

## Scope Review

- The working tree contains the expected UI 03 implementation and tests. `HEAD` is still the recorded base; the workstream is represented by working-tree changes and untracked workstream files.
- No changes were found under `backend/runtime`, `backend/risk`, `backend/integrations/oanda`, `backend/persistence`, `backend/strategies`, or migrations.
- No migration was introduced. `uv run alembic check` returned `No new upgrade operations detected`.
- The new route is GET-only, bounded to `limit=1..50`, defaults to `10`, and is wired through the read service rather than reconstructing evidence in the route.
- The read service uses durable Fill facts, `LIFECYCLE_ADVANCED`, schema-V2 `TRADE_DETAIL`, CLOSED state, durable Strategy catalog names, confirmed protection, and CLOSED Trade economics. Exact exit causes require one closing transaction ID and matching schema-V2 transaction evidence; multiple or unresolved causes remain unavailable.
- No `Net P/L` is calculated. Realized P/L, financing, and dividend adjustment remain separate.
- The new history UI does not render UUIDs, provider IDs, provider reasons, or internal history evidence vocabulary as primary content. Existing current PAPER status fields remain unchanged.

## Verification

### Focused backend

```text
uv run pytest backend/tests/paper/test_trade_history.py backend/tests/test_api_paper.py
28 passed; one existing Starlette/httpx deprecation warning
```

The focused coverage includes eligibility, Fill and closure sourcing, Strategy identity, malformed evidence, exact Stop/Target causes, missing/mismatched transaction evidence, multiple closing IDs, Dogfood-02-style unavailable cause, bounds, endpoint response, and provider/runtime/mutation seam isolation.

Changed-slice Ruff format/check passed. Changed-slice Pyright reported `0 errors`.

### Focused frontend

```text
npx vitest run --config frontend/vitest.config.ts frontend/tests/api_client.test.ts frontend/tests/overview.test.tsx frontend/tests/paper_status.test.tsx
29 passed
```

The focused coverage includes Overview/PAPER limits, LONG/SHORT, positive/negative P/L, separate financing, exact/unresolved/multi-close causes, protection, timezone formatting, empty/error states, and absence of raw identifiers in history presentation.

### Broad safe checks

- `uv run pytest -m "not integration and not external"`: `1294 passed`, `4 skipped`.
- `npm run check:web`: Prettier, ESLint with existing warnings only, TypeScript, `94` frontend tests, and production build passed.
- `git diff --check`: passed.
- Generated OpenAPI was rebuilt from `create_app().openapi()`, converted with `openapi-typescript 7.13.0`, formatted with repository Prettier, and byte-compared successfully against `frontend/lib/api.generated.ts`.
- Full backend Ruff format reports `68` existing files requiring formatting; full Ruff reports `28` existing errors; full backend Pyright reports `3011` existing errors. Changed-slice checks pass, and these baseline failures are outside UI 03.

### Database and browser evidence

- A read-only development-database query found `7` persisted observations, including a schema-V2 CLOSED Trade with durable closure economics and one recorded closing transaction ID. An older schema-V1 CLOSED observation was not eligible.
- `uv run pytest -m integration` was attempted, but the dedicated `ATLAS_TEST_DATABASE_URL` was unavailable. No valid PostgreSQL integration result is available; this is a non-product environment limitation, not an acceptance pass.
- Safari Technology Preview evidence covered the populated Overview and PAPER history with local in-page fixtures, desktop `1440x900`, and mobile `390x844` viewports. It showed direction, Strategy/version, entry/exit, separate economics, close time in `America/New_York`, exact and unavailable exit-cause states, loading/error/empty handling, and preserved current-state sections.
- The existing local browser server was loaded before fetch interception and is not the UI 03 branch server. After interception, history data came from local read-only fixtures. No Atlas mutation request, runtime start, activation, or broker mutation was performed. A Next development stack-frame POST caused by the interception harness is tooling noise, not an application request.
- The initial existing-server page load did request current broker-state data before interception; therefore the browser run cannot be claimed as a zero-provider-read run. The UI 03 history endpoint itself was validated by source, focused tests, and the database-only service design.

## Acceptance Summary

- API existence, GET-only contract, bounds/default, generated client freshness, no migration, no execution/reconciliation changes, durable fact sourcing, fail-closed parsing, exact-cause rules, no invented net P/L, and read-only UI states: verified by focused tests, source review, OpenAPI comparison, and safe checks.
- New Overview and PAPER history surfaces, limits, trader-facing labels, separate current/history sections, timezone handling, and preserved existing sections: verified by focused tests and browser fixture evidence.
- Newest-close-first bounded history: **not accepted** because of F-001.
- Initial-risk presentation: **not accepted** because of F-002.

## Validation Limits

- No credentialed external tests were run.
- No `atlas-runtime` process was started.
- PAPER was not activated and no broker mutation was performed.
- The unavailable dedicated PostgreSQL integration environment leaves ORM/database behavior less covered than the focused fake-session tests.
