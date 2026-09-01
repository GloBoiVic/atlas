# T001 — PAPER contracts, normalization, and live data frontier

**State:** `DONE`
**Dependency:** none
**Owner:** BUILD

## Objective

Implement the pure, provider-neutral PAPER 01 seams needed before persistence:
normalized OANDA account/instrument/quote facts, read-only account/pricing/data
transport contracts, canonical live completed-M15 and sparse M1 execution
eligibility, and a durable-state-compatible strategy handoff value boundary.

## Required behavior

- Keep OANDA DTOs inside `backend/integrations/oanda`; expose small typed Atlas
  values only.
- Require an explicit Practice account ID; never infer the first authorized
  account. Reject MT4-associated or unknown MT4 association accounts.
- Normalize USD account facts, EUR/USD instrument precision/limits/capabilities,
  and complete BID/ASK executable quotes. Missing, stale, non-tradeable, or
  malformed facts are not executable.
- Reuse the existing immutable EMA Sweep Confirmation Break v2 StrategyVersion
  and Strategy boundary. Do not add broker/account/database/clock I/O to Strategy.
- Accept only completed, UTC-aligned native M15 MID bars. M1 BID/ASK is execution
  data only; no aggregation, interpolation, forward-fill, or fabricated price.
- Enforce `observation.start_time > decision_time` (equality is ineligible) and
  the exact predicates: LONG `ASK open > trigger OR ASK high >= trigger`; SHORT
  `BID open < trigger OR BID low <= trigger`.
- Add pure serialization/validation helpers for the versioned state envelope and
  pending handoff if the existing domain types do not already provide the full
  PAPER shape. Invalid/incompatible state must fail closed.
- This task is read-only at the provider boundary. Tests must use mocked HTTP or
  recorded shapes and assert no mutating endpoint is called.

## Owned implementation surface

Primarily `backend/integrations/oanda/`, `backend/market_data/`, and narrowly
scoped domain/contract modules plus their tests. Do not edit migrations or role
artifacts. Do not alter historical Experiment semantics.

## Task-level checks

- Targeted OANDA normalization and frontier tests.
- Strict equality/no-lookahead and long/short trigger predicate tests.
- Existing Strategy and historical market-data tests remain green.
- Ruff and pyright on changed modules where practical.

## Completion receipt requirements

At completion, update this file with `DONE` or `DONE_WITH_CONCERNS`, changed files,
checks/evidence, and concerns. Do not edit `PLAN.md`, `ACTIVE.md`, or another
worker's artifact.

## Completion receipt

**Final state:** `DONE`

### Changed files

- `backend/domain/broker.py` — provider-neutral account, instrument, quote, and
  broker-side position/order/trade facts.
- `backend/domain/__init__.py` — exports the broker fact values.
- `backend/integrations/oanda/normalization.py` — strict recorded-shape
  normalization for explicit Practice account selection, MT4 rejection, USD
  account summaries, EUR/USD venue constraints, and executable BID/ASK quotes.
- `backend/integrations/oanda/readonly.py` — GET-only Practice account/pricing/
  instrument/candle transport protocol and mocked-transport client.
- `backend/integrations/oanda/source.py` — elapsed-UTC completed native M15 and
  sparse M1 read-only fetch helpers; historical fetch semantics remain unchanged.
- `backend/integrations/oanda/__init__.py` — exports the read-only contracts and
  normalizers.
- `backend/market_data/live.py` — immutable completed-M15 frontier, sparse BID/
  ASK pairing, strict post-decision eligibility, and exact long/short predicates.
- `backend/tests/integrations/test_oanda_paper_contracts.py` — normalization,
  MT4/account selection, quote freshness, and GET-only transport tests.
- `backend/tests/market_data/test_live_frontier.py` — completion, deduplication,
  sparse-data, frontier, and trigger tests.

### Checks and evidence

- Targeted PAPER/OANDA/frontier plus existing OANDA source, domain primitive, and
  EMA Strategy tests: **85 passed**.
- All `backend/tests/market_data` and `backend/tests/integrations`: **93 passed,
  1 skipped**.
- All `backend/tests/domain` and `backend/tests/strategies`: **115 passed**.
- Full non-capital suite excluding the repository's DB-required integration
  directory, with external tests excluded: **415 passed, 5 skipped, 1 deselected**
  in 180.61s.
- Ruff on changed implementation/tests: **passed**.
- Pyright on changed implementation modules: **0 errors, 0 warnings**.
- `git diff --check`: **passed**.
- Read-only client test recorded four `GET` requests and no mutating endpoint;
  no credentialed or capital-capable OANDA request was made.

### Concerns

- The full non-external command completed in 211.57s with **416 passed, 74
  skipped, 1 deselected, and 16 setup errors** because `ATLAS_TEST_DATABASE_URL`
  is not configured for DB-required integration tests. No T001 test or code
  failure was observed; the DB suite remains unverified in this environment.
- Existing untracked dispatch/audit paths, `.codegraph/`, `frontend/.env.local`,
  and the pre-existing `dispatch/ACTIVE.md` modification were left untouched.

## Validation remediation packet — F-04

- **Classification:** PRODUCT; **severity:** BLOCKER.
- **Issue:** `normalize_account_snapshot` defaults missing account `orders`,
  `trades`, and `positions` collections to empty, allowing incomplete broker
  state to appear flat and pass Risk.
- **Affected seam:** `backend/integrations/oanda/normalization.py`, broker facts,
  reconciler/Risk exposure gate.
- **Required fix:** Require all broker-state collections or represent each as
  explicitly unknown; unknown collections must reject/block new exposure and
  cannot reconcile as `MATCHED`/flat.
- **Invalidated evidence:** T001 malformed-shape and non-executable claims.
- **Smallest revalidation:** missing `orders`, `trades`, and `positions` cases,
  reconciler blocking, and Risk rejection using recorded provider shapes.

## F-04 remediation receipt

**Final state:** `DONE`

### Remediation details

- `normalize_account_snapshot` now requires `orders`, `trades`, and `positions`
  object arrays; a missing or malformed collection raises `BrokerFactsError`
  instead of producing an apparently flat account.
- `AccountSnapshot` explicitly tracks `orders_known`, `trades_known`, and
  `positions_known`, conservatively defaulting each to unknown. Normalized OANDA
  snapshots mark all three known only after successful collection parsing.
- Read-only reconciliation returns `RECONCILIATION_REQUIRED` for any unknown
  broker-state collection, and `PaperRiskService` rejects it as
  `ACCOUNT_STATE_UNKNOWN`. Unknown snapshots cannot be treated as flat.

### Changed files for remediation

- `backend/domain/broker.py`
- `backend/integrations/oanda/normalization.py`
- `backend/runtime/coordinator.py`
- `backend/risk/service.py`
- `backend/tests/integrations/test_oanda_paper_contracts.py`
- `backend/tests/risk/test_paper_service.py`
- `backend/tests/runtime/test_coordinator.py`

### Remediation checks and evidence

- Recorded-shape normalization, Risk, and reconciliation tests: **21 passed**.
- All `backend/tests/integrations` and `backend/tests/market_data`, plus the
  focused Risk/runtime suites: **117 passed, 1 skipped**.
- Ruff on remediation implementation/tests: **passed**.
- Pyright on remediation implementation modules: **0 errors, 0 warnings**.
- `git diff --check` on remediation files: **passed**.
- No credentials, PAPER activation, or mutating/capital-capable OANDA request
  was used; provider tests remain mocked/recorded and GET-only.

### Remaining concerns

- F-04 is remediated and its focused evidence is restored. The existing
  database-environment validation limitation and other validation findings are
  outside this T001 remediation packet and remain unresolved.
