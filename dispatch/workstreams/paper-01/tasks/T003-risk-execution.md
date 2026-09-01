# T003 — PAPER Risk, OANDA execution, and broker-hosted protection

**State:** `DONE`
**Dependency:** T002 `DONE`
**Owner:** BUILD

## Objective

Implement the centralized PAPER Risk composition and one narrow OANDA Practice
adapter for canonical Order/Fill facts, including safe full-fill-only entry,
stable correlation, and broker-hosted protection.

## Required behavior

- Compose exactly PRE_FLIGHT followed immediately by PRE_SUBMISSION. Only an
  approved PRE_SUBMISSION may authorize an entry Order.
- Use broker-authoritative equity, margin, precision/min/max, tradeability,
  exposure, and current executable BID/ASK facts. Size conservatively with
  Decimal and floor to provider-valid units; reject unknown or unsafe facts.
- PAPER PRE_SUBMISSION `target_price` is NULL/not-final. Persist approved stop,
  target methodology/multiple, quote evidence, and priceBound. Calculate 1.7R
  target only from the authoritative Fill.
- Map canonical entry to OANDA MARKET/FOK with stable clientExtensions
  correlation and conservative `priceBound`; reject IOC/unsupported orders before
  any network request.
- Commit `PENDING_SUBMISSION` before network I/O. Normalize create/fill/reject/
  cancel/reissue/related transactions and external IDs. Timeout or malformed /
  uncertain outcome becomes UNKNOWN; never blind retry.
- PAPER 01 accepts only an unambiguous full Fill. Partial/reissue/ambiguous state
  fails closed and is never represented as a full Position.
- Submit/confirm broker-hosted stop-on-fill protection and then attach/confirm the
  actual-Fill-derived TAKE_PROFIT. Missing, wrong, orphan, or ambiguous
  protection persists a safety event and blocks new exposure.
- Apply confirmed Fill transactionally through canonical Order → Fill → Position →
  Trade. Fill alone changes exposure.
- All tests use mocked HTTP/recorded provider shapes and assert no POST/PUT/PATCH/
  DELETE/cancel/close/transfer endpoint is called during non-capital validation.

## Owned implementation surface

`backend/risk/`, `backend/execution/`, `backend/integrations/oanda/`, and focused
tests, using T002 persistence seams. Do not change historical Experiment risk or
execution semantics except for explicitly backward-compatible shared contracts.

## Task-level checks

- Risk ordering, rounding, margin, priceBound, null target, and rejection tests.
- Mocked OANDA response normalization, timeout→UNKNOWN, no-retry, FOK/IOC,
  full-fill-only, protection, and actual-Fill target tests.
- Existing risk/execution/fill-application tests remain green.

## Completion receipt

At completion, update this file with `DONE` or `DONE_WITH_CONCERNS`, changed files,
checks/evidence, and concerns. Do not edit role artifacts.

## Completion receipt

**Final state:** `DONE`

### Changed files

- `backend/risk/service.py` — added the normalized-fact PAPER Risk composition,
  exact PRE_FLIGHT → PRE_SUBMISSION ordering, conservative Decimal sizing,
  margin/venue/quote gates, safe priceBound, and null/not-final PAPER target.
- `backend/risk/__init__.py` — exported the PAPER Risk composition contracts.
- `backend/execution/contract.py` — added backward-compatible instrument,
  correlation, FOK/IOC, bound/protection, and broker identity fields to canonical
  in-memory Order/Fill contracts; historical defaults remain unchanged.
- `backend/execution/__init__.py` — exported canonical execution contracts and
  Fill application.
- `backend/execution/fill_application.py` — extended the Fill-only atomic bridge
  to Deployment-owned PAPER Orders/Positions/Trades while preserving historical
  Experiment accounting and full-fill behavior.
- `backend/persistence/trading_repository.py` — added immutable PAPER
  RiskDecision persistence with null PRE_SUBMISSION target enforcement.
- `backend/integrations/oanda/execution.py` — added transport-injected MARKET/FOK
  request mapping, stable clientExtensions, stop-on-fill and target protection
  requests, compound response normalization, UNKNOWN/partial/reissue fail-closed
  handling, authoritative-Fill target calculation, protection confirmation, and
  canonical Fill bridge.
- `backend/integrations/oanda/__init__.py` — exported the OANDA execution seam.
- `backend/tests/risk/test_paper_service.py` — PAPER ordering, sizing, margin,
  quote freshness, and safety-gate tests.
- `backend/tests/integrations/test_oanda_execution.py` — recorded response,
  FOK/IOC, protection, timeout/no-retry, target, and GET-only provider tests.

### Checks and evidence

- Targeted Risk, execution, OANDA, persistence, and Fill-application tests:
  **68 passed, 5 skipped**. Skips are DB integration tests because
  `ATLAS_TEST_DATABASE_URL` is not configured.
- Existing historical Experiment tests: **96 passed**.
- Ruff on all changed T003 modules/tests: **passed**.
- Pyright on all changed implementation modules: **0 errors, 0 warnings**.
- `git diff --check`: **passed**.
- Provider validation used recorded/mocked shapes and one mocked `GET` trade
  confirmation; no credentialed request and no POST/PUT/PATCH/DELETE,
  cancel/close/transfer, or Order-submission request was made.
- No credentials, activation, Risk-policy change, branch change, commit, or
  Git-history operation was performed.

### Concerns

- A dedicated PostgreSQL test database remains required to verify the new
  Deployment-owned Fill transaction, persistence trigger behavior, and actual
  canonical ownership constraints; those tests were skipped in this environment.
- The authenticated POST/PUT transport methods are implementation-only seams;
  the first capital-capable request remains approval-gated and was not invoked.
- Runtime orchestration, startup/reconciliation, and lifecycle control remain
  T004 scope and are intentionally not implemented here.
