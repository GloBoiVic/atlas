# PLAN - UI 03 — PAPER Trade Outcome Visibility

## Workstream state

- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Classification:** `Feature`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Phase:** `READY_FOR_USER`
- **Approval:** approved by developer on 2026-09-09
- **Architecture:** not required
- **Task state:** T001 DONE; T002 DONE; R001 DONE; R001 VALIDATE PASS; R001 REVIEW PASS; R002 DONE; R002 VALIDATE PASS; R002 REVIEW PASS; final REVIEW PASS
- **Next action:** explicit developer merge approval; do not merge before approval
- **Concerns:** none recorded; F-001 and F-002 resolved through the completed remediation chains.

## Outcome

Give the trader a clear read-only view of completed PAPER Trades using durable Atlas evidence already persisted by PAPER execution and reconciliation.

The slice should answer:

- What PAPER Trades have completed?
- Which Strategy produced each Trade?
- Was it LONG or SHORT?
- Where did it enter and exit?
- Where were the actual Stop and Take Profit?
- What realized P/L did the broker report?
- What financing or dividend adjustment was recorded?
- When did the Trade close?
- If Atlas durably proved one exact exit cause, what was it?

The Overview receives a compact recent-PAPER-trades summary.

The PAPER page receives a fuller bounded trade-history view.

This workstream does not create trading controls or new broker activity.

---

## Current-main facts

Current `main` already has:

- durable PAPER execution attempts;
- immutable Strategy/version identity on each attempt;
- durable Fill facts including:
  - actual Fill price;
  - signed units;
  - Fill time;
  - actual initial risk;
- confirmed Stop and Take Profit prices;
- append-only broker observations;
- PAPER broker facts schema V2;
- CLOSED Trade observations containing:
  - close time;
  - average close price;
  - realized P/L;
  - financing;
  - dividend adjustment;
  - closing transaction IDs;
  - aggregate exit-cause state;
- optional exact closing-transaction observations containing:
  - exact closing transaction ID;
  - matching Trade ID;
  - exact close price;
  - provider reason;
  - normalized exit cause;
- `LIFECYCLE_ADVANCED` reconciliation state;
- Strategy catalog names through `StrategyModel`;
- generated OpenAPI frontend types;
- current-state PAPER broker and runtime UI.

Current `main` does not expose a read API for completed PAPER Trades.

The PAPER page explicitly remains a current-state surface today.

---

## Product rules

### 1. Durable evidence only

A completed PAPER Trade shown by this feature must come entirely from Atlas persistence.

The history read must not:

- call OANDA;
- inspect current broker inventory;
- trigger reconciliation;
- start runtime;
- reconstruct facts from mutable Strategy code;
- infer missing facts from prices.

### 2. Completion eligibility

A PAPER attempt is eligible for this history projection only when all of the following are true:

- a durable Fill exists;
- the attempt has reached `LIFECYCLE_ADVANCED`;
- Atlas has a schema-V2 `TRADE_DETAIL` observation for that Fill Trade;
- that observation identifies the Trade as `CLOSED`;
- required closure economics are present and valid.

A filled Trade without durable CLOSED Trade evidence is not presented as completed.

### 3. Entry facts

Use actual durable Fill facts, not approved/pre-trade estimates:

- entry price = durable Fill price;
- entered time = durable Fill execution time;
- units = actual durable Fill units;
- initial risk = durable actual initial risk.

Direction remains the attempt's durable `LONG` / `SHORT` identity.

The trader-facing units value may be presented as an absolute quantity because direction is shown separately.

### 4. Protection facts

Use actual durable protection facts:

- Stop = confirmed broker Stop price when available;
- Target = confirmed Take Profit price when available.

Do not substitute the originally proposed Stop or Target when confirmed protection evidence differs.

Unavailable protection facts remain unavailable.

### 5. Closure economics

Use the CLOSED Trade observation as authority for lifetime Trade closure economics:

- close time;
- average close price;
- realized P/L;
- financing;
- dividend adjustment.

Do not substitute closing-transaction-level financing for Trade-level lifetime financing.

### 6. No invented net P/L

This workstream does not define a new Atlas net-P/L metric.

Expose separately:

- realized P/L;
- financing;
- dividend adjustment.

The UI must not add them together and label the result `Net P/L`.

### 7. Exit cause requires exact durable evidence

Exact exit-cause attribution is permitted only when the CLOSED Trade has exactly one recorded closing transaction ID.

That single ID must have durable schema-V2 `TRANSACTION_DETAIL` evidence attributable to:

- the same PAPER attempt;
- the same provider Trade;
- that exact closing transaction ID.

Multiple closing IDs preserve `MULTIPLE` semantics and do not prove one trader-facing exit cause.

Do not infer exit cause from:

- close price equaling Stop;
- close price equaling Target;
- realized P/L sign;
- current broker flatness;
- Strategy intent.

When exact single-closing-transaction evidence is absent, the API returns no proved exit cause and the UI says:

`Exit cause unavailable`

### 8. Dogfood 02 remains historically truthful

Do not special-case Dogfood 02.

Its persisted lifecycle run contains valid CLOSED Trade economics but no persisted transaction-19 observation.

Therefore this feature may show its:

- entry;
- exit;
- Stop;
- Target;
- realized P/L;
- financing;
- close time;

but must not display `Stopped out` from knowledge obtained outside its durable Atlas record.

Future Trades reconciled through the fixed adapter can expose exact persisted exit causes when the closure has exactly one closing transaction.

### 9. Trader-facing language

Primary UI should favor trading concepts over Atlas implementation terms.

Do not display as primary content:

- attempt UUIDs;
- activation UUIDs;
- reconciliation run IDs;
- provider transaction IDs;
- client IDs;
- provider Trade IDs;
- observation schema names;
- `FILLED_PROTECTED`;
- `LIFECYCLE_ADVANCED`;
- raw provider reasons.

These may remain internal API/evidence facts where needed.

### 10. Bounded read

This slice is recent-history visibility, not a full analytics engine.

Use a bounded `limit` query:

- default: `10`;
- minimum: `1`;
- maximum: `50`.

Sort newest closed Trade first by close time.

No pagination/cursor contract is required in UI 03.

---

## Scope

### A. PAPER Trade history read model

Add a dedicated read-only PAPER Trade-history composition service.

Expected file:

`backend/paper/trade_history.py`

Suggested contract:

`PaperTradeHistoryReadService`

The service may query the existing durable tables required to compose the projection, including:

- `PaperExecutionAttemptModel`;
- `PaperBrokerObservationModel`;
- `StrategyVersionModel`;
- `StrategyModel`.

Do not add a new persistence table.

Do not call provider code from this service.

For each eligible completed Trade, compose a bounded trader-facing projection containing at least:

- Strategy key;
- Strategy name;
- Strategy version number;
- instrument;
- direction;
- units;
- entry price;
- entered time;
- Stop price if available;
- Target price if available;
- initial risk if available;
- close time;
- average close price;
- realized P/L;
- financing;
- dividend adjustment;
- proved exit cause or `None`.

An opaque attempt identity may remain in the API if useful for stable item identity or future drill-down, but it is not shown in the primary UI.

### B. Closure evidence selection

The read service must select closure facts only from:

- `ATLAS_PAPER_BROKER_FACTS_V2`;
- `TRADE_DETAIL`;
- the durable Fill Trade;
- state `CLOSED`.

The projection must not reinterpret arbitrary JSON observations as completed Trades.

The service should use existing typed/bounded parsing conventions where practical and fail closed on malformed required closure facts rather than manufacturing a partial financial result.

### C. Exact exit-cause evidence

For the selected CLOSED Trade:

1. read its recorded `closing_transaction_ids`;
2. only continue exact-cause attribution when the collection contains exactly one ID;
3. inspect durable schema-V2 `TRANSACTION_DETAIL` observations for the same attempt and Trade;
4. require that observation to match the single recorded closing transaction ID;
5. use the normalized exact transaction `exit_cause` only when attribution is valid.

Do not fan out across multiple closing transaction IDs.

Do not promote one transaction's cause when a Trade has multiple closing IDs.

Multiple-ID closures return no proved trader-facing exit cause.

`UNRESOLVED` and `MULTIPLE` are not promoted to one proved trader-facing cause.

No provider reason needs to be exposed in this first public history response.

### D. PAPER history API

Add:

`GET /api/v1/paper/trades`

Query:

`limit`

Expected response shape:

```text
{
  items: [
    {
      strategyKey
      strategyName
      strategyVersionNumber
      instrument
      direction
      units
      entryPrice
      enteredAt
      stopPrice
      targetPrice
      initialRisk
      closedAt
      averageClosePrice
      realizedPl
      financing
      dividendAdjustment
      exitCause
    }
  ]
}
```

Exact field naming follows existing FastAPI/Pydantic and generated-client conventions.

The endpoint must be:

- GET-only;
- database-only;
- bounded;
- deterministic;
- free of credentials/provider calls;
- free of broker mutation authority.

Add response schemas to:

`backend/api/schemas.py`

Wire the read service through the existing PAPER router/application composition without teaching the HTTP route how to reconstruct evidence.

Expected files:

- `backend/api/paper.py`
- `backend/api/app.py`

### E. Generated client contract

Regenerate:

`frontend/lib/api.generated.ts`

using the repository's canonical OpenAPI generation workflow.

The generated file must be byte-current with the backend schema.

Do not hand-edit generated types.

### F. Frontend API client

Extend:

`frontend/lib/api-client.ts`

with a typed read method for:

`GET /api/v1/paper/trades`

The Overview may request a small limit such as `3`.

The PAPER page may request a larger bounded limit such as `20`.

### G. Shared PAPER Trade-history component

Add a reusable presentation component.

Expected file:

`frontend/components/paper-trade-history.tsx`

Support at least:

- compact Overview mode;
- fuller PAPER-page mode;
- loading;
- empty;
- unavailable/error;
- completed Trade rows/cards.

Use existing Atlas components, spacing, typography, status treatment, timezone handling, instrument formatting, and design tokens.

Do not introduce a parallel design system.

### H. Compact Overview presentation

Update:

`frontend/components/overview.tsx`

Add a trader-facing section for recent PAPER outcomes.

Suggested heading:

`Recent PAPER trades`

Compact presentation should prioritize:

1. instrument + direction;
2. Strategy name/version;
3. exit description;
4. realized P/L;
5. entry → exit;
6. closed time.

Examples of permitted exit copy when exact evidence exists:

- `Target hit`
- `Stopped out`
- `Market close`
- `Margin closeout`
- `Other broker close`

Without exact durable single-close cause:

`Exit cause unavailable`

Do not show raw Atlas state-machine values.

### I. PAPER page trade history

Update:

`frontend/components/paper-status.tsx`

Retain the existing current broker/runtime sections.

Add a separate historical section so the distinction remains clear:

```text
Current PAPER state
vs.
Completed PAPER trades
```

The fuller history view should make useful Trade facts inspectable without overwhelming the page.

Show at least:

- instrument/direction;
- Strategy;
- entry;
- exit;
- Stop;
- Target;
- realized P/L;
- financing;
- close time;
- exit cause when proved.

Show dividend adjustment only when useful/non-zero.

Initial risk may be shown in the fuller view.

Do not add activation controls, reconciliation buttons, or broker actions.

---

## Out of scope

This workstream does not authorize:

- PAPER activation;
- runtime start/stop controls;
- reconciliation controls;
- OANDA reads from the history endpoint;
- broker mutation;
- LIVE trading;
- Risk-policy changes;
- Strategy methodology changes;
- new execution semantics;
- historical reconciliation/backfill;
- Dogfood-02-specific data repair;
- provider transaction browsing;
- trade-detail routes;
- pagination/cursors;
- realized-R calculation;
- aggregate win rate;
- cumulative PAPER P/L;
- equity curves;
- performance analytics;
- new persistence tables;
- database migrations;
- changes to PAPER execution or reconciliation semantics.

If implementation proves a migration or new durable financial definition is required, stop and return for re-planning.

---

## Suggested task boundaries

### T001 — PAPER completed-Trade read contract and API

Own:

- `backend/paper/trade_history.py`
- `backend/api/schemas.py`
- `backend/api/paper.py`
- `backend/api/app.py`
- `backend/tests/paper/test_trade_history.py`
- `backend/tests/test_api_paper.py`
- `frontend/lib/api.generated.ts` generated output only

Deliver:

- bounded database-only history projection;
- strict CLOSED Trade eligibility;
- Strategy name/version composition;
- closure economics;
- exact durable single-closing-transaction exit-cause attribution;
- `GET /api/v1/paper/trades`;
- generated API contract.

T001 must not change frontend presentation code.

### T002 — Trader-facing PAPER history UI

Depends on T001.

Own:

- `frontend/lib/api-client.ts`
- `frontend/components/paper-trade-history.tsx`
- `frontend/components/overview.tsx`
- `frontend/components/paper-status.tsx`
- `frontend/tests/api_client.test.ts`
- `frontend/tests/overview.test.tsx`
- `frontend/tests/paper_status.test.tsx`

Deliver:

- typed history read;
- compact Overview presentation;
- fuller PAPER-page history;
- trader-facing exit labels;
- loading/empty/error handling;
- no raw implementation identifiers in primary UI.

T001 and T002 are sequential.

---

## Acceptance criteria

1. `GET /api/v1/paper/trades` exists.
2. Endpoint is GET-only.
3. Endpoint performs no OANDA/provider request.
4. Endpoint performs no mutation.
5. `limit` is bounded from 1 through 50.
6. Default limit is 10.
7. Results are newest-close-first.
8. Only durable filled attempts are eligible.
9. Only `LIFECYCLE_ADVANCED` completed attempts are eligible.
10. A schema-V2 CLOSED `TRADE_DETAIL` observation is required.
11. Entry price comes from durable Fill.
12. Entry time comes from durable Fill.
13. Units come from durable Fill.
14. Stop comes from durable confirmed protection when available.
15. Target comes from durable confirmed protection when available.
16. Close time comes from CLOSED Trade evidence.
17. Average close price comes from CLOSED Trade evidence.
18. Realized P/L comes from CLOSED Trade evidence.
19. Financing comes from CLOSED Trade evidence.
20. Dividend adjustment comes from CLOSED Trade evidence.
21. No `Net P/L` is calculated.
22. Exit cause is returned only when the CLOSED Trade has exactly one recorded closing transaction ID and matching attributable durable exact-transaction evidence.
23. Multiple closing IDs do not produce one proved trader-facing exit cause.
24. Price proximity never determines exit cause.
25. Missing exact exit evidence remains unavailable.
26. Dogfood 02 is not special-cased.
27. Strategy name comes from durable Strategy catalog identity.
28. No migration is introduced.
29. No new PAPER execution/reconciliation semantics are introduced.
30. Generated OpenAPI client is current.
31. Overview shows recent PAPER Trade outcomes.
32. PAPER page shows fuller completed PAPER Trade history.
33. Empty history has a clear empty state.
34. Read failure has a clear non-destructive error state.
35. Trader UI does not primarily expose UUIDs or provider transaction identifiers.
36. Trader UI does not primarily expose internal PAPER state-machine vocabulary.
37. Existing current broker/runtime visibility remains intact.
38. Existing Overview Strategies/Experiments/System behavior remains intact.
39. Existing PAPER page current-state semantics remain intact.

---

## Validation plan

### T001 focused backend

Run focused tests covering:

- no eligible Trades;
- one completed Trade;
- multiple Trades ordered by close time;
- limit validation;
- missing Fill;
- missing CLOSED Trade evidence;
- non-V2 observation ignored;
- malformed closure evidence fails closed;
- Strategy name/version projection;
- exact Take Profit cause;
- exact Stop Loss cause;
- absent exact transaction cause;
- mismatched transaction/Trade ignored;
- multiple closing transaction IDs produce no single proved exit cause;
- Dogfood-02-style aggregate closure with no exact transaction remains cause-unavailable;
- endpoint response;
- endpoint limit behavior;
- endpoint does not invoke provider/runtime mutation seams.

Expected focused files:

```bash
uv run pytest \
  backend/tests/paper/test_trade_history.py \
  backend/tests/test_api_paper.py
```

Then:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run alembic check
git diff --check
```

Verify generated OpenAPI client freshness using the repository's canonical generation/byte-comparison workflow.

### T002 focused frontend

Run:

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/api_client.test.ts \
  frontend/tests/overview.test.tsx \
  frontend/tests/paper_status.test.tsx
```

Cover:

- recent PAPER Trades render on Overview;
- Overview uses compact limit;
- PAPER page uses fuller bounded limit;
- LONG/SHORT rendering;
- positive and negative realized P/L;
- financing displayed separately;
- exact exit-cause labels;
- unresolved exit cause;
- multi-close exit cause remains unavailable;
- Stop/Target display;
- local display timezone;
- empty history;
- failed read;
- no raw IDs/internal state labels in primary UI.

Then:

```bash
npm run check:web
git diff --check
```

### Broad safe regression

Before REVIEW:

```bash
uv run pytest -m "not integration and not external"
npm run check:web
uv run alembic check
git diff --check
```

Run PostgreSQL integration tests if the changed read/API seams are covered by existing integration markers and the dedicated `atlas_test` database is available.

Do not run external credentialed tests.

Do not start `atlas-runtime`.

Do not activate PAPER.

Do not perform broker mutation.

---

## Approval gate

This PLAN does not authorize implementation.

Before GIT START:

1. Confirm the two intake corrections are incorporated.
2. Confirm the recorded base still matches current `main`.
3. Developer explicitly approves this corrected PLAN.

Only then may Solo:

`GIT START → create T001/T002 → BUILD → VALIDATE → REVIEW`
