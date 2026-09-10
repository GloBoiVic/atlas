# T001 - PAPER Trade History Read Contract and API

- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `664b19c902656b37271158c55faf7f7d19cfa840`

## Outcome

Implement the bounded, database-only completed PAPER Trade history projection and its read-only API contract from the approved PLAN.

## Scope

Primary files:

- `backend/paper/trade_history.py`
- `backend/api/schemas.py`
- `backend/api/paper.py`
- `backend/api/app.py`
- `backend/tests/paper/test_trade_history.py`
- `backend/tests/test_api_paper.py`
- `frontend/lib/api.generated.ts` (generated output only)

Required behavior:

- Compose only durable eligible CLOSED PAPER Trades.
- Use durable Fill facts for entry facts and CLOSED Trade evidence for closure economics.
- Use durable Strategy catalog identity for Strategy name/version.
- Keep protection facts tied to confirmed durable evidence when available.
- Attribute an exit cause only with exactly one recorded closing transaction ID and matching attributable schema-V2 transaction evidence.
- Preserve multiple closing IDs as `MULTIPLE` semantics without producing one trader-facing exit cause.
- Fail closed on malformed required closure facts.
- Add `GET /api/v1/paper/trades` with the bounded `limit` contract and current OpenAPI-generated client output.
- Keep the endpoint database-only, deterministic, GET-only, and free of provider calls or broker mutation.

## Constraints

- Backend/API and generated contract only; do not modify frontend presentation code.
- No persistence table or migration.
- Do not change PAPER execution or reconciliation semantics.
- Do not call OANDA, start runtime, activate PAPER, or perform broker mutation.

## Checks

Run the focused backend tests and checks from the approved PLAN. Record exact results in this task file before marking the task done.

## Worker Evidence

- BUILD assignment created after explicit approval and GIT START.

## BUILD Receipt

- **Status:** `DONE`
- **Implemented:** Added the bounded database-only completed PAPER Trade projection and `GET /api/v1/paper/trades` with `limit` default `10` and bounds `1..50`.
- **Evidence rules:** Only durable filled attempts at `LIFECYCLE_ADVANCED` with schema-V2 CLOSED `TRADE_DETAIL` evidence are projected. Entry facts come from durable Fill evidence, Strategy identity comes from the catalog, closure economics come from CLOSED Trade evidence, malformed required closure facts fail closed, and exact exit cause requires one closing transaction ID plus matching attributable schema-V2 `TRANSACTION_DETAIL` evidence. Multiple closing IDs remain cause-unavailable.
- **Safety:** The endpoint is GET-only, database-only, deterministic, and performs no provider request, runtime action, broker mutation, persistence change, or migration.
- **Files:** `backend/paper/trade_history.py`, `backend/api/schemas.py`, `backend/api/paper.py`, `backend/api/app.py`, `backend/tests/paper/test_trade_history.py`, `backend/tests/test_api_paper.py`, `frontend/lib/api.generated.ts`.
- **Focused tests:** `uv run pytest backend/tests/paper/test_trade_history.py backend/tests/test_api_paper.py` -> `28 passed`, one existing Starlette/httpx deprecation warning.
- **Focused static checks:** Changed-slice Ruff format/check passed. `uv run pyright backend/paper/trade_history.py backend/tests/paper/test_trade_history.py` -> `0 errors`. `uv run alembic check` -> `No new upgrade operations detected`. `git diff --check` passed.
- **Generated contract:** Current `create_app().openapi()` -> `openapi-typescript 7.13.0` -> repository Prettier -> `cmp -s` passed for `frontend/lib/api.generated.ts`.
- **Repository baseline:** Full backend Ruff format reports 68 existing files requiring formatting; full Ruff reports 28 existing errors, primarily in migration/repository and unrelated tests; full backend Pyright reports 3011 existing errors. These are outside the T001 slice and were not modified.
- **Integration:** PostgreSQL integration checks were not run because `ATLAS_TEST_DATABASE_URL` was unavailable. No external/provider, runtime, PAPER activation, or broker-mutation checks were run.
