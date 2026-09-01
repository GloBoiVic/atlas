# T001 — OANDA Read-only Observation Infrastructure Refactor

## Task state

- **Task:** `T001`
- **Status:** `DONE`
- **Workstream:** `oanda-read-only-observation-infrastructure-refactor`
- **Role:** `BUILD`
- **Approval:** developer approved; GIT START complete

## Assignment

Implement the behavior-preserving refactor frozen in `PLAN.md` and
`ARCHITECTURE.md`. Extract the demonstrated common request mechanics from the
Practice account, open-Trade, and open-Position readers into the internal
OANDA-local requester. Extract only the identical transaction-ID, finite
provider-decimal, and provider-instrument parsers into the internal primitive
module. Preserve every PAPER 01A–01D public contract, domain error, semantic
rule, request path, retry behavior, injected-client seam, and fail-closed
boundary.

## Owned files

- `backend/integrations/oanda/request.py`
- `backend/integrations/oanda/primitives.py`
- `backend/integrations/oanda/account.py`
- `backend/integrations/oanda/trades.py`
- `backend/integrations/oanda/positions.py`
- `backend/tests/integrations/test_oanda_request.py`
- `backend/tests/integrations/test_oanda_primitives.py`
- `backend/tests/integrations/test_oanda_account.py`
- `backend/tests/integrations/test_oanda_trades.py`
- `backend/tests/integrations/test_oanda_positions.py`
- this task receipt

## Required evidence

- Exact frozen `OandaObservationRequester` contract, token preflight,
  bounded timeout construction, owned/injected client behavior, headers, GET
  URL construction, JSON decoding, status classification, retry counts,
  `Retry-After` timing/capping, and sanitized errors.
- Exact frozen primitive parser acceptance and rejection, including leading-zero
  transaction IDs and provider instrument boundaries, with internal primitive
  failures wrapped by each existing domain-specific normalization error.
- Account, Trade, and Position settings helpers still perform `/summary` first
  and then their independent existing observation; endpoint paths and query
  behavior remain unchanged.
- Existing immutable provider contracts and all local account, Trade, and
  Position semantic validation remain unchanged, including Position long/short
  independence and Trade ordering.
- `source.py` remains untouched and does not use the observation requester.
- No new package exports, provider endpoints, fields, capabilities, Atlas
  financial objects, persistence, Risk, runtime, execution, reconciliation,
  mutation, activation, LIVE, or PAPER 01E behavior.

## Explicit boundaries

Do not modify `source.py`, `backend/integrations/oanda/__init__.py`, persistence,
migrations, Risk, runtime, execution, API/UI, domain trading state, or any
provider-domain semantics. Do not introduce a broker adapter/client/gateway,
provider factory, generic provider hierarchy, plugin infrastructure, or
environment switching. If any boundary is necessary, mark this task `BLOCKED`
and return for developer re-scoping approval.

## Required checks

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_request.py \
  backend/tests/integrations/test_oanda_primitives.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_positions.py \
  backend/tests/integrations/test_oanda_source.py

uv run pytest -m "not integration and not external"
uv run ruff format --check <changed OANDA files and tests>
uv run ruff check <changed OANDA files and tests>
uv run pyright <changed OANDA files and tests>
git diff --check
```

## Worker Evidence

### Implementation files

- Added `backend/integrations/oanda/request.py` with the frozen token,
  timeout, client-ownership, authenticated GET, JSON, status, retry, and
  `Retry-After` mechanics.
- Added `backend/integrations/oanda/primitives.py` with the frozen transaction
  ID, finite decimal, and provider-instrument parsers.
- Updated `account.py`, `trades.py`, and `positions.py` to retain local paths,
  response-shape checks, semantic validation, domain-specific errors, account
  binding, ordering, and duplicate rules while using the shared seams.
- Added request and primitive seam tests; updated only the existing OANDA
  observation tests' retry patch points and added non-object/domain regression
  coverage. The repeated-instrument Trade regression remains covered.

### Checks

- Focused OANDA regression command (including `test_oanda_source.py`): **253
  passed**.
- `uv run pytest -m "not integration and not external"`: **640 passed, 4
  skipped, 88 deselected** (4 pre-existing warnings).
- Targeted Ruff format check: **10 files already formatted**.
- Targeted Ruff lint: **passed**.
- Targeted Pyright: **0 errors, 0 warnings, 0 informations**.
- `git diff --check`: **passed**.
- Confirmed no diff in `backend/integrations/oanda/source.py` or
  `backend/integrations/oanda/__init__.py`.

### Acceptance coverage

- Request tests cover exact Practice URL, GET-only headers/no params, decoded
  object and non-object JSON, invalid JSON sanitization, all status classes,
  attempt/status metadata, transport retry, fallback and capped numeric/date
  `Retry-After`, bounded sleeps, token preflight, and owned/injected client
  behavior.
- Primitive tests cover exact type strictness, regex boundaries, leading-zero
  transaction IDs, finite decimals, non-finite rejection, instrument shape,
  and sanitized internal errors.
- Existing account/Trade/Position tests continue to cover account binding
  sequencing, immutable provider contracts, local semantic failure-closed
  rules, deterministic ordering, exact duplicate rules, and repeated
  provider-instrument validity for distinct Trade IDs.

### Concerns

None. No source historical request path, package export, provider capability,
financial state, persistence, runtime, Risk, execution, mutation, PAPER 01E,
or LIVE behavior was added. Pre-existing `dispatch/ACTIVE.md` and workstream
bookkeeping remain outside this BUILD change.
