# T001 — OANDA Observation Query Parameter Support

## Assignment

- **Workstream:** `oanda-observation-query-parameter-support`
- **Task:** `T001`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/oanda-observation-query-parameter-support`
- **Base:** `190282f07246f7603cdfe14d297186c304afc24c`
- **Owned artifact:** `dispatch/workstreams/oanda-observation-query-parameter-support/tasks/T001-oanda-observation-query-parameter-support.md`

## Approved outcome

Extend only `OandaObservationRequester.get_json(...)` and its focused requester tests so the requester accepts:

```python
params: Mapping[str, str] | None = None
```

The argument is keyword-only and must use `Mapping` from `collections.abc`. Existing account, Trade, Position, and pending Order consumers remain unchanged.

## Required implementation behavior

- Snapshot a non-`None` caller mapping exactly once at the beginning of each `get_json()` call into local request state, equivalent to `None if params is None else dict(params)`.
- Reuse the same local snapshot for every retry; do not reread or mutate the caller mapping.
- Do not store the mapping or snapshot on `self` or retain query state after the call.
- Pass only the local snapshot through `client.get(..., params=request_params, ...)`.
- Never append a query string to `path`, manually encode values, or add query validation/coercion.
- Preserve fixed OANDA Practice routing, authenticated GET-only behavior, timeout construction and per-request timeout, client ownership, bounded retry and `Retry-After` behavior, statuses, JSON handling, attempt/status metadata, exception classes, and exact sanitized messages.
- Do not include query keys/values, response bodies, tokens, or transport exception text in request-level errors.

## Files

Application/test edits are limited to:

```text
backend/integrations/oanda/request.py
backend/tests/integrations/test_oanda_request.py
```

Do not edit the four current consumers or any other application area. If any behavioral application change outside `request.py` is required, stop `BLOCKED` and report the concrete reason rather than broadening scope.

## Required focused test evidence

Retain existing requester coverage and add behavior-level evidence for:

- omitted/`None` params: exact existing no-query Practice GET and headers;
- one provider-neutral query: `{"example": "value"}`;
- multiple distinct string keys, without repeated-key/list semantics;
- HTTPX-owned escaping using a provider-neutral string value if needed;
- unchanged caller mapping after success and failure;
- transient failure then success with identical query/path/headers on both attempts;
- mutation of the original mapping after the first attempt proving retries use the original snapshot;
- sanitized deterministic failure with distinctive query markers absent from the error text.

Do not add pricing, `/pricing`, `instruments`, or any new provider endpoint semantics to tests.

## Required task-level checks

Run only the focused commands from PLAN/ARCHITECTURE as appropriate during BUILD; do not run the full backend suite, database/Alembic, frontend/browser, or credentialed external checks.

## Worker Evidence

- **Status:** `DONE`
- **Implementation:** Added the keyword-only `Mapping[str, str] | None` `params` seam to `OandaObservationRequester.get_json`, snapshotting caller values once locally and passing that snapshot through HTTPX `params=` for every attempt. Existing request routing, headers, timeout, retry, ownership, JSON, error, and sanitization behavior remains unchanged.
- **Focused tests:** Added coverage for omitted/`None` and empty query behavior, single and multiple string values, HTTPX escaping, caller ownership on success/failure, retry identity, retry snapshot stability after caller mutation, and sanitized failure messages.
- **Files changed:**
  - `backend/integrations/oanda/request.py`
  - `backend/tests/integrations/test_oanda_request.py`
  - `dispatch/workstreams/oanda-observation-query-parameter-support/tasks/T001-oanda-observation-query-parameter-support.md`
- **Checks:**
  - `uv run pytest backend/tests/integrations/test_oanda_request.py` — 47 passed.
  - Required focused requester plus account/Trade/Position/pending-Order tests — 250 passed.
  - Targeted Ruff format, Ruff check, Pyright, and `git diff --check` — passed.
- **Findings/concerns:** None. The four existing OANDA consumers were not edited; no new endpoint or provider semantics were added.
