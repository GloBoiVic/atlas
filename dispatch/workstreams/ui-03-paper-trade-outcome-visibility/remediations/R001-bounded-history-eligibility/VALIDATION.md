# VALIDATION - R001 Bounded History Eligibility

## Result

- **Status:** `PASS`
- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Remediation:** `R001`
- **Role:** `VALIDATE`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`
- **Finding disposition:** F-001 is resolved within the approved R001 scope.
- **R001 findings:** None.

## Scope Review

- Reviewed the R001 BUILD packet, origin finding F-001 in the workstream VALIDATION, the approved PLAN, T001's contract/task receipt, and the complete visible working-tree diff.
- R001-owned implementation and regression seams are `backend/paper/trade_history.py` and `backend/tests/paper/test_trade_history.py`, as approved by BUILD. The working tree also contains the separate T001/T002 backend, frontend, generated-contract, and dispatch artifacts; no R001 scope drift was identified.
- No R001 change was made to frontend presentation, API shape, limit bounds, persistence schema, migrations, PAPER execution, reconciliation, runtime, risk, or provider integrations.
- The history service contains no OANDA/provider or runtime call. The route supplies a database session and delegates composition to the read service; it has no broker mutation path.

## Acceptance Coverage

### F-001 bounded eligibility

- The candidate SQL statement has no `.limit()` or SQL ordering/limiting. It loads all candidate schema-V2 `TRADE_DETAIL` rows for filled, `LIFECYCLE_ADVANCED` attempts.
- The service groups observations, validates durable Fill facts, selects matching schema-V2 `CLOSED` Trade evidence, rejects malformed or contradictory closure evidence, composes eligible items, and only then applies `composed[:limit]`.
- `test_history_keeps_eligible_trade_when_ineligible_observation_fills_sql_limit` places an OPEN observation with no close time before a valid CLOSED observation and requests `limit=1`; the valid completed Trade is returned. The SQL-limit-aware fake would have truncated the old pre-validation query, so this regression passes only with the limit applied after composition.

### Chronology

- `_timestamp` requires a timezone-aware ISO timestamp and converts it to UTC. Sorting uses the parsed `closure.closed_at` and the string form of the attempt UUID in reverse order, providing newest-first chronology and deterministic tie-breaking.
- `test_history_orders_by_parsed_close_time_then_attempt_id` verifies offset-normalized timestamps and high-before-low attempt-ID ordering for equal instants.

### T001 contract and behavior

- The service and route retain the approved `limit` contract: default `10`, inclusive bounds `1..50`, and final response slicing. The API test verifies default and explicit limits, rejects `0` and `51`, and confirms POST returns `405`.
- Focused T001 history/API coverage remains green for durable Fill sourcing, strict lifecycle and schema-V2 CLOSED eligibility, fail-closed malformed evidence, Strategy identity, closure economics, exact-cause attribution, missing/mismatched transaction evidence, multiple close IDs, unavailable exact cause, response shape, and read-only route behavior.
- Fresh OpenAPI generation is byte-identical to `frontend/lib/api.generated.ts`; no T001 API contract drift was found.

## Checks

```text
uv run pytest backend/tests/paper/test_trade_history.py backend/tests/test_api_paper.py
30 passed; one existing Starlette/httpx deprecation warning

uv run ruff format --check backend/paper/trade_history.py backend/tests/paper/test_trade_history.py
uv run ruff check backend/paper/trade_history.py backend/tests/paper/test_trade_history.py
2 files already formatted; all checks passed

uv run pyright backend/paper/trade_history.py backend/tests/paper/test_trade_history.py
0 errors, 0 warnings, 0 informations

uv run ruff format --check backend/paper/trade_history.py backend/tests/paper/test_trade_history.py backend/api/app.py backend/api/paper.py backend/api/schemas.py backend/tests/test_api_paper.py
6 files already formatted

uv run ruff check backend/paper/trade_history.py backend/tests/paper/test_trade_history.py backend/api/app.py backend/api/paper.py backend/api/schemas.py backend/tests/test_api_paper.py
All checks passed!

uv run pyright backend/api/app.py backend/api/paper.py backend/api/schemas.py backend/tests/test_api_paper.py backend/paper/trade_history.py backend/tests/paper/test_trade_history.py
25 errors in backend/api/app.py only. These are the known pre-existing app.py Any/optional typing errors; the R001-only Pyright command above passed.

uv run alembic check
No new upgrade operations detected.

git diff --check
Passed with no output.

git diff --no-index --check /dev/null backend/paper/trade_history.py || test $? -eq 1
git diff --no-index --check /dev/null backend/tests/paper/test_trade_history.py || test $? -eq 1
Passed with no whitespace diagnostics; the expected no-index difference exit was accepted.

ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run python -c "from backend.api.app import create_app; import json; print(json.dumps(create_app().openapi(), indent=2))" > /tmp/atlas-r001-validation-openapi.json
npx openapi-typescript /tmp/atlas-r001-validation-openapi.json -o /tmp/atlas-r001-validation-generated.ts
npx prettier --config .prettierrc.json /tmp/atlas-r001-validation-generated.ts > /tmp/atlas-r001-validation-generated.pretty.ts
cmp -s frontend/lib/api.generated.ts /tmp/atlas-r001-validation-generated.pretty.ts
openapi-typescript 7.13.0 completed and cmp passed with no differences.
```

## Findings

- None for R001. No `PRODUCT / REGRESSION / TOOLING` plus `DEFECT / NEW SCOPE` finding was identified in the approved remediation.
- F-002 remains intentionally unaddressed: `frontend/components/paper-trade-history.tsx:194-197` still renders `initialRisk` through `priceLabel`, as confirmed by source review. Its existing classification is `PRODUCT / DEFECT`; changing it in R001 would be `NEW SCOPE` and is reserved for R002. It is not a regression from R001.
- The broader six-file Pyright result is classified `TOOLING / NEW SCOPE`, not an R001 defect, because all 25 errors are in the known pre-existing `backend/api/app.py` typing baseline and the R001 files pass strict Pyright.

## Limitations

- No PostgreSQL integration test run was performed; the validation evidence is focused fake-session/API coverage plus static/source review.
- No OANDA call, credentialed external check, `atlas-runtime` startup, PAPER activation, or broker mutation was performed.
- Browser/frontend validation was not repeated because R001 owns backend bounded eligibility and chronology only; the existing T002 frontend changes were inspected only to confirm F-002 remains separate.
