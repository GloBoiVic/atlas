# PLAN - PAPER Visibility 01 Current Broker Trade Read

## Workstream state

- **Workstream:** `paper-visibility-01-current-broker-trade-read`
- **Classification:** `Feature`
- **Base:** `main` at `25ebc4182d5a409a9ceaa2b9aa354a51dd5e9c47` (original approved base `09323c76eac25ca32bc27bbc98b092db153328cb` plus `chore: ignore .DS_Store` `25ebc41` to clean worktree)
- **Branch:** `solo/paper-visibility-01-current-broker-trade-read`
- **Phase:** `READY_FOR_USER` (R001 remediation)
- **Approval:** Developer approved PLAN on 2026-09-08; GIT START completed; VALIDATE `PASS` 2026-09-08; REVIEW `PASS` 2026-09-08; R001 approved via trader request 2026-09-08; R001 validation/review completed locally after worker capacity failure
- **Architecture:** not required; this is a narrow HTTP projection and frontend composition over an existing read-only observation contract
- **Task state:** T001 `DONE` — VALIDATE `PASS` — REVIEW `PASS` — R001 `DONE_WITH_CONCERNS` — VALIDATE `PASS` — REVIEW `PASS_WITH_CONCERNS`
- **Next action:** Await explicit merge approval
- **Worktree concern:** Resolved 2026-09-08 — `.gitignore` `.DS_Store` committed as `25ebc41` on `main` before branch creation; tracked worktree is clean at GIT START

`dispatch/ACTIVE.md` remains `# No active workstream` during this pre-approval planning phase. This PLAN is the only new workstream artifact.

## Outcome

Make current OANDA Practice open broker Trades visible on Overview and PAPER without using runtime activation state as a proxy for broker exposure.

The surface must distinguish:

```text
Runtime: active or not active
Broker: open Trades, no open Trades, or unavailable
```

The workstream is read-only. It adds no activation, runtime, execution, reconciliation, Risk, persistence, migration, or broker mutation behavior.

## Current findings

- `backend/integrations/oanda/trades.py` already owns the validated, immutable `OandaPracticeOpenTradeInventory` and `OandaPracticeOpenTrade` facts.
- `read_oanda_practice_open_trade_inventory(settings)` validates the configured Practice account and uses the existing authenticated GET-only observation path. It must be reused unchanged.
- The inventory's validated account identity already contains provider, Practice environment, and base account currency. The current supported base currency is USD.
- The HTTP projection may expose the base currency but must not expose the provider account ID.
- `create_app()` owns `settings` and currently composes `create_paper_router()` with only the runtime service.
- The smallest composition change is to inject a no-argument broker observation callable into that router; the callable invokes the existing reader per GET.
- `backend/api/paper.py` already provides the PAPER route prefix and safe local-authority handling, but no current broker inventory route.
- The existing PAPER runtime exception mapping must not be reused in a way that converts broker-observation failure into a misleading runtime error code.
- `frontend/lib/api-client.ts` has typed PAPER GET wrappers and preserves non-empty API errors.
- The new broker read must not use the active-activation `404` to represent an empty broker inventory.
- UI 01 already provides `Overview`, `/paper`, `useReadResource`, display-timezone formatting, and read-only error/empty/unavailable components. Preserve those patterns.

## Proposed API

### Route

Add one explicit read-only product route:

```text
GET /api/v1/paper/broker-state
```

The route is product-level under PAPER rather than exposing an OANDA provider reader directly to the frontend.

It performs one invocation of the injected observation callable for each request.

There is no:

- cache;
- polling;
- background work;
- mutation method.

### Successful response

Use a strict response envelope with only safe normalized facts needed by the UI:

```json
{
  "provider": "OANDA",
  "environment": "PRACTICE",
  "accountCurrency": "USD",
  "openTrades": [
    {
      "tradeId": "20",
      "instrument": "EUR_USD",
      "openTime": "2026-01-05T08:00:00.123456Z",
      "openPrice": "1.16188",
      "currentUnits": "-390663",
      "state": "OPEN",
      "unrealizedPl": "-410.20"
    }
  ]
}
```

Contract rules:

- `provider`, `environment`, and `accountCurrency` are direct projections of the existing validated account identity.
- The provider account ID and credentials must not be exposed.
- `tradeId`, `instrument`, `openTime`, `openPrice`, `currentUnits`, `state`, and `unrealizedPl` are direct projections of the existing normalized Trade facts.
- Decimal fields remain exact decimal strings on the HTTP wire.
- `currentUnits` remains signed.
- The API must not convert signed units to an absolute quantity or add a derived direction that could replace the authoritative sign.
- `accountCurrency` is used only to label monetary broker facts accurately.
- Do not assume or hardcode a currency independently of the normalized identity.
- Preserve every returned Trade independently, in the reader's deterministic order.
- Do not net, aggregate, select, filter, or discard unexpected instruments or exposure.
- Preserve the existing `OPEN` and `CLOSE_WHEN_TRADEABLE` state values.
- Both states represent current Trade exposure.
- Do not expose credentials, raw provider payloads, account identifiers, Strategy or activation attribution, Risk, stop/target, realized P/L, realized R, or exit cause.
- A successful empty reader result is HTTP 200 with `openTrades: []`.
- A successful empty result is the only response that may support the UI copy `No open broker trades.`
- The response does not add a freshness, reconciliation, flatness, or runtime-authority claim.
- The existing provider transaction cursor need not be displayed or exposed by this minimal UI contract.

### Failure response

The route must fail closed for:

- missing or invalid OANDA configuration;
- account binding failure;
- request/authentication failure;
- provider transport failure;
- provider response failure;
- existing OANDA normalization failure.

Known broker observation failures must use the existing structured error envelope with:

```text
PAPER_BROKER_STATE_UNAVAILABLE
```

and a safe trader-readable message such as:

```text
Current broker state is unavailable.
```

Do not include:

- exception text;
- provider response bodies;
- credentials;
- tokens;
- account IDs.

Unexpected implementation failures must remain distinct:

```text
PAPER_BROKER_STATE_INTERNAL_ERROR
```

They must not reuse `PAPER_RUNTIME_INTERNAL_ERROR`, because this GET reports broker observation rather than runtime control.

Use an unavailable/error HTTP response rather than HTTP 200 with an empty list.

Unexpected implementation exceptions must never become a successful empty inventory.

The frontend must preserve every failure as an unavailable or unknown broker state.

The route must be covered by GET-only tests using injected fakes and sanitized normalized objects.

No credentialed live read is required for implementation validation.

## Exact reader reuse and composition

The endpoint will call:

```python
read_oanda_practice_open_trade_inventory(settings)
```

through the API composition boundary.

That existing function remains responsible for:

- account validation;
- configured Practice-account identity;
- OANDA authentication;
- `/openTrades` GET behavior;
- retries/timeouts;
- normalization;
- immutable ordering;
- existing sanitized exception types.

Expected API composition changes are limited to:

- safe HTTP response schemas in `backend/api/schemas.py`;
- a broker-read callable parameter in `backend/api/paper.py`;
- broker-specific safe error translation in `backend/api/paper.py`;
- a GET route in `backend/api/paper.py`;
- wiring the settings-backed callable in `backend/api/app.py`;
- focused API tests.

Do not modify `backend/integrations/oanda/trades.py` or account normalization to make the UI easier.

If this endpoint cannot be composed from the existing normalized reader and identity facts without changing a frozen integration seam, stop and return `BLOCKED` for re-scope.

## Frontend presentation

### Overview

Add current broker exposure as the first high-level PAPER fact on `/`, before:

- readiness;
- Strategy summary;
- Experiment summary;
- DatasetSnapshot metadata.

Keep the remaining Overview structure broadly intact in this workstream.

The larger product-hierarchy cleanup remains a later slice.

The compact broker section will:

- perform an initial `atlasApi.paperBrokerState()` GET;
- show provider/environment in trader-facing form such as `OANDA Practice`;
- show each returned Trade independently;
- derive trader-facing direction from signed units:
  - positive units -> `LONG`
  - negative units -> `SHORT`
- show absolute display quantity while retaining the signed API value in the typed contract;
- show instrument;
- show provider Trade state;
- show entry;
- show unrealized P/L;
- show opened time;
- format unrealized P/L using the returned `accountCurrency`;
- avoid unsafe floating-point conversion;
- show `No open broker trades.` only for successful `openTrades: []`;
- show `Broker unavailable` or equivalent unknown state with retry when the GET fails.

The compact view must not:

- collapse multiple Trades into a net position;
- hide any returned Trade;
- infer broker flatness.

Do not make technical IDs prominent in the compact Overview.

The Trade ID may remain available only where useful as secondary or evidence detail.

### PAPER page

Add a fuller current broker Trade section with short trader-facing labels:

```text
Open Trade
SHORT
390,663 units

Entry
1.16188

Unrealized P/L
-$410.20

Opened
...

OANDA Practice

Refresh
```

Keep the existing capability section and runtime status section, but make the runtime section explicitly runtime-oriented.

Place current broker exposure above or ahead of runtime diagnostics so current capital state is visually more important than whether an Atlas activation process is active.

The page must visibly preserve the distinction:

```text
Broker
OPEN TRADE

Runtime
STOPPED / No active runtime
```

The existing active route continues to mean only current Atlas runtime activation.

Its empty result must never be used as broker flatness.

Refresh is an explicit user action that retries the same GET.

Do not add:

- polling;
- websockets;
- schedulers;
- activation controls;
- stop controls;
- reconcile controls;
- Buy/Sell controls;
- Close controls;
- protection controls.

Use the existing display-timezone preference for `Opened`.

Format unit and decimal strings without lossy binary-number conversion.

Do not hardcode:

- account;
- currency;
- instrument;
- Trade;
- units;
- entry;
- P/L;
- direction.

## Expected files

Expected backend files:

```text
backend/api/app.py
backend/api/paper.py
backend/api/schemas.py
backend/tests/test_api_paper.py
backend/tests/test_api_paper_broker_state.py
```

Expected frontend files:

```text
frontend/lib/api-client.ts
frontend/lib/api.generated.ts
frontend/components/overview.tsx
frontend/components/paper-status.tsx
frontend/tests/api_client.test.ts
frontend/tests/overview.test.tsx
frontend/tests/paper_status.test.tsx
```

`frontend/lib/api.generated.ts` must not be hand-edited.

Regenerate it from the current FastAPI OpenAPI document with the repository's existing `openapi-typescript` and Prettier workflow if the new schema requires it.

No changes are expected or permitted in:

```text
backend/integrations/oanda/trades.py
backend/integrations/oanda/account.py
backend/integrations/oanda/execution.py
backend/integrations/oanda/reconciliation.py
backend/paper/**
backend/runtime/**
backend/risk/**
backend/persistence/**
backend/strategies/**
backend/persistence/migrations/**
```

## Acceptance criteria

1. The new route is GET-only and invokes only the existing read-only OANDA open-Trade observation path.
2. Provider, Practice environment, and account currency are projected only from the existing validated account identity.
3. Provider account ID is not exposed.
4. One normalized Trade projects exact ID, instrument, open time, entry price, signed units, supported state, and unrealized P/L facts without raw payload fields.
5. Positive units render LONG with absolute display quantity.
6. Negative units render SHORT with absolute display quantity.
7. Signed quantity remains authoritative in the API contract.
8. Unrealized P/L is labelled and formatted using the returned account currency without lossy numeric conversion.
9. Multiple Trades remain distinct and all are rendered.
10. No netting or arbitrary selection occurs.
11. A successful zero-Trade read returns an explicit empty inventory and renders `No open broker trades.`
12. Configuration, provider, transport, authentication, or normalization failure renders unavailable or unknown.
13. Failure cannot render `No open broker trades.`, `Flat`, or equivalent.
14. Known broker-read failures use `PAPER_BROKER_STATE_UNAVAILABLE`.
15. Unexpected internal broker-read failures remain distinct from runtime errors.
16. Runtime stopped/not-active, historical activation state, and missing frontend data are never used as evidence of broker flatness.
17. No account ID, credential, raw provider payload, unsupported attribution, Risk, protection, realized-result, or exit-cause claim is exposed.
18. Overview makes current broker exposure more prominent than readiness and DatasetSnapshot metadata without broad UI redesign.
19. PAPER clearly separates broker observation from Atlas runtime status.
20. PAPER has an explicit GET-only Refresh action.
21. Focused backend and frontend tests cover:
    - populated state;
    - LONG;
    - SHORT;
    - multiple Trades;
    - empty inventory;
    - unavailable state;
    - error redaction;
    - currency presentation;
    - Refresh GET-only behavior.
22. Existing PAPER/runtime/execution behavior remains unchanged.
23. No runtime, mutation, reconciliation, database, migration, or live broker mutation workflow is run.

## Frozen Dogfood path

- Dogfood 02 activation remains stopped.
- Dogfood 02 is not restarted.
- Dogfood 02 is not reused.
- Dogfood 02 is not reconciled.
- Dogfood 02 is not reconstructed.
- `atlas-runtime` remains OFF.
- No broker Trade is modified, closed, replaced, or otherwise acted upon.
- The endpoint is observation-only.
- Planning and automated validation use injected/fake broker observations.
- Automated validation requires no live provider mutation.
- No activation operation is performed.
- No stop operation is performed.
- No reconcile operation is performed.
- No execution operation is performed.
- No Risk operation is performed.
- No persistence operation is performed.
- No credential operation is performed.
- No fixture or implementation value may encode the real Dogfood:
  - activation ID;
  - Trade ID;
  - account ID;
  - units;
  - entry;
  - P/L.

A manual read-only visual check against the already configured local OANDA Practice account may be performed only after implementation validation if separately authorized or already permitted by the user.

Any such check must remain GET-only and must not start `atlas-runtime`.

## Validation plan

Before implementation validation, verify that the worktree contains no unrelated tracked changes from the pre-existing `.gitignore` modification.

After explicit approval, clean GIT START, and task creation, run the smallest relevant evidence:

```bash
uv run pytest \
  backend/tests/test_api_paper.py \
  backend/tests/test_api_paper_broker_state.py \
  backend/tests/integrations/test_oanda_trades.py

uv run ruff format --check \
  backend/api/app.py \
  backend/api/paper.py \
  backend/api/schemas.py \
  backend/tests/test_api_paper.py \
  backend/tests/test_api_paper_broker_state.py

uv run ruff check \
  backend/api \
  backend/tests/test_api_paper.py \
  backend/tests/test_api_paper_broker_state.py

uv run pyright \
  backend/api \
  backend/tests/test_api_paper.py \
  backend/tests/test_api_paper_broker_state.py

git diff --check
```

Backend evidence must prove:

- safe projection;
- exact decimal/sign behavior;
- validated currency projection;
- multiple Trade preservation;
- empty-vs-failure semantics;
- stable broker-specific error mapping;
- error redaction;
- absence of non-GET broker methods.

Existing OANDA reader tests remain the normalization evidence.

No reader semantic change is authorized.

Run focused frontend tests for:

- one LONG Trade;
- one SHORT Trade;
- multiple Trades;
- successful empty broker inventory;
- unavailable/error broker state;
- currency-aware P/L presentation;
- independent Overview/PAPER loading states;
- independent Overview/PAPER error states;
- display-timezone formatting;
- Refresh request method/path;
- absence of PAPER mutation controls.

Then run:

```bash
npm run check:web
npm run test:e2e
```

where the repository's existing safe frontend/E2E environment is available.

Verify the generated client matches a fresh:

```text
create_app().openapi()
-> openapi-typescript
-> Prettier
```

regeneration.

Browser checks, if run, must verify:

- desktop readability;
- mobile readability;
- independent broker/runtime states;
- explicit unavailable state;
- explicit empty state;
- GET-only traffic.

Browser checks must not use:

- `atlas-runtime`;
- broker mutation.

## Explicit deferrals

This workstream does not add:

- broker Trade history;
- activation history;
- historical reconstruction;
- completed Trade view;
- Strategy attribution;
- RiskDecision;
- stop/target;
- realized P/L;
- realized R;
- exit cause;
- reconciliation result;
- freshness policy;
- broker flatness proof;
- account-level netting;
- Position-level netting;
- Position projection;
- cross-endpoint reconciliation;
- background polling;
- websocket infrastructure;
- scheduler behavior;
- persistence;
- migrations;
- runtime behavior;
- execution behavior;
- activation controls;
- trading controls;
- DatasetSnapshot cleanup;
- Experiment cleanup;
- navigation redesign;
- shell redesign;
- broad Overview cleanup;
- generalized multi-broker abstraction;
- LIVE behavior.

## Approval gate

Before explicit developer approval of this reconciled PLAN, do not:

```text
GIT START
create a solo/* branch
create tasks/ or T001
modify application code
modify tests
run implementation validation
run atlas-runtime
perform a live broker workflow
```

Additionally, GIT START requires a clean tracked worktree.

The unrelated `.gitignore` modification must be resolved separately before branch creation.

After explicit approval, the Feature lifecycle is:

```text
GIT START
-> create T001 from this approved PLAN
-> BUILD
-> focused VALIDATE
-> independent REVIEW
-> remediation if required
-> explicit merge approval
```
