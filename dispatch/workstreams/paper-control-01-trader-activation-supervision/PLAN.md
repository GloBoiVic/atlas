# PLAN — PAPER Control 01 — Trader Activation & Supervision

## Workstream state

- **Workstream:** `paper-control-01-trader-activation-supervision`
- **Title:** `PAPER Control 01 — Trader Activation & Supervision`
- **Classification:** `Critical`
- **Base:** `main` at `e2ad47c5cbfbca89d58f915745f81180c4864db9`
- **Base SHA:** `e2ad47c5cbfbca89d58f915745f81180c4864db9`
- **Branch:** `solo/paper-control-01-trader-activation-supervision`
- **Phase:** `READY_FOR_USER`
- **Approval:** explicit developer approval recorded; current PLAN/ARCHITECTURE approved
- **Architecture:** `ARCHITECTURE.md` required and authoritative
- **Task state:** T001, T002, and T003 DONE; R001 BUILD/VALIDATE/REVIEW PASS
- **Next action:** explicit developer merge approval; stop before GIT END
- **Concerns:** `atlas-runtime` remains a separately launched local process by design; F-003 Minor activation-form UI guideline concern and mocked visual validation limitation remain documented

## Outcome

Allow the trader to activate, supervise, and stop a PAPER session from Atlas UI using the existing capital-control contracts.

Successful product path:

```text
Open Atlas
→ PAPER
→ Activate PAPER
→ choose StrategyVersion
→ review parameters
→ enter Risk per trade
→ review exact authorization
→ type ACTIVATE PAPER
→ submit one activation request
→ observe REQUESTED / STARTING / RUNNING
→ Strategy trades only through existing runtime + Risk
→ request Stop PAPER when desired
→ observe terminal status
→ completed broker Trades remain visible through UI 03
```

No curl is required for activation or stop.

The separate `atlas-runtime` process remains an operational prerequisite.

---

## Architecture authority

Implementation must follow `ARCHITECTURE.md`.

In particular:

- frontend only unless intake proves otherwise;
- no new capital authority;
- no process spawning;
- no backend semantic changes;
- no migrations;
- no broker mutation from frontend;
- stable activation request identity;
- no automatic activation retry;
- exact decimal-string Risk wire value;
- explicit typed activation confirmation;
- STOP does not mean Close Trade.

---

## Scope

### A. PAPER control API client

Extend:

`frontend/lib/api-client.ts`

Add typed methods using existing generated OpenAPI contracts for:

- create PAPER activation;
- get PAPER activation by ID;
- stop PAPER activation.

Existing active-status, capability, and broker-state reads remain.

Suggested methods:

```text
activatePaper(...)
paperStatus(activationId)
stopPaper(activationId, ...)
```

Use existing generated request/response types.

Do not hand-create a conflicting backend contract.

Do not modify generated API types unless intake proves they are stale.

### B. Exact Risk conversion helper

Add a small pure frontend helper module.

Expected file:

`frontend/lib/paper-control.ts`

Own:

- percentage input validation;
- exact percentage-string → decimal-ratio-string conversion;
- trader-facing lifecycle labels;
- trader-facing operational-phase labels if useful;
- other pure control formatting needed by both activation and supervision.

Example:

```text
"1"    → "0.01"
"0.5"  → "0.005"
"12.5" → "0.125"
```

Do not use binary floating-point arithmetic to construct the authority-bearing wire value.

Risk input:

- blank by default;
- required;
- > 0%;
- < 100%.

### C. Dedicated activation page

Add:

`frontend/app/paper/activate/page.tsx`

Expected presentation component:

`frontend/components/paper-activation.tsx`

The page must be a deliberate capital-approval workflow rather than a single button.

Stages:

1. Strategy selection
2. StrategyVersion selection
3. parameter configuration
4. Risk-per-trade entry
5. review
6. typed confirmation
7. activation submission

Use existing:

- Strategy catalog API;
- Strategy detail API;
- PAPER capability API;
- active PAPER status API;
- PAPER broker-state API;
- existing parameter schema.

No new backend Strategy-options endpoint is planned.

### D. Strategy selection

Load existing Strategy catalog.

After Strategy selection, load Strategy detail and offer its available immutable versions.

Only versions with current local execution availability should be selectable.

Display:

- Strategy name;
- version;
- methodology summary;
- supported market facts;
- parameter schema.

Do not imply frontend availability is final PAPER approval.

Backend activation validation remains authoritative.

### E. Parameter editor

Initialize Strategy parameters from the selected immutable version's defaults.

Render supported parameter-schema types consistently with current Experiment configuration patterns.

Support current schema types required by registered Strategies.

Frontend validation improves UX only.

The exact submitted object is still validated by `PaperRuntimeService`.

Changing Strategy/version/parameters after entering review must:

- exit the reviewed state;
- clear typed confirmation;
- invalidate the activation request ID.

### F. Risk entry

Trader-facing field:

`Risk per trade (%)`

Do not prefill it.

Provide concise explanation:

`Atlas Risk applies this percentage to fresh account equity when an eligible Trade is evaluated.`

Do not show estimated dollars.

Review must show the exact percentage being authorized.

### G. Pre-activation read state

Before final activation submission, inspect:

- PAPER capability;
- active activation;
- supported broker-state read.

Rules:

- capability unavailable → activation disabled;
- another active activation → activation form disabled with link to `/paper`;
- visible open broker Trade → activation disabled with explanation;
- zero visible open Trades must not be described as full flatness proof;
- unavailable broker-state read remains uncertainty and must be visibly disclosed.

The runtime still owns authoritative fresh startup checks.

### H. Frozen review

Entering Review captures the authority-bearing snapshot:

- Strategy key/name;
- StrategyVersion ID/version;
- parameter object;
- Risk decimal ratio;
- Risk display percentage;
- provider/environment/instrument.

Generate one activation UUID for this snapshot.

Review must prominently state that activation authorizes Atlas to create PAPER Trades automatically when the Strategy signals and Atlas Risk approves them until the session stops or blocks.

Show:

- `PAPER / OANDA Practice`;
- Strategy + version;
- methodology;
- parameters;
- Risk per trade;
- EUR/USD current supported market boundary.

Do not show full provider account ID.

### I. Typed approval

Require exact UI phrase:

`ACTIVATE PAPER`

Only then enable:

`Activate PAPER trading`

POST exactly one request for a submit attempt:

```text
activationRequestId = frozen review ID
strategyVersionId   = reviewed version
parameters          = reviewed parameters
riskPerTrade        = reviewed decimal ratio string
confirmation        = ACTIVATE_PAPER
```

Disable duplicate submit while in flight.

### J. Activation uncertainty handling

If POST succeeds:

- treat returned durable activation as authority;
- navigate to `/paper`;
- begin supervision.

If POST returns known validation/conflict:

- show the bounded API failure;
- do not claim activation.

If transport outcome is ambiguous:

- GET active PAPER status;
- same activation ID → activation succeeded;
- no active activation → offer explicit Retry using same ID;
- different active activation → conflict.

Never auto-generate a new UUID and retry.

### K. PAPER page supervision

Update:

`frontend/components/paper-status.tsx`

The page is no longer described as read-only.

Preserve:

- current broker exposure first;
- completed PAPER Trades;
- capability facts.

Add current-session control.

When no active activation:

- show `No active PAPER session`;
- show `Activate PAPER`.

When an activation exists, show trader-facing:

- Strategy key/name where resolvable;
- version;
- Risk per trade;
- lifecycle;
- operational phase;
- state/reason when blocked;
- last state-change time.

Do not primarily show raw UUIDs, fingerprints, implementation keys, or provider account IDs.

### L. Status polling

On fresh PAPER-page load:

1. read active activation;
2. if present, retain its ID.

While current session is non-terminal, poll:

`GET /api/v1/paper/activations/{id}`

approximately every 3 seconds.

Stop polling on:

- `STOPPED`;
- `BLOCKED`;
- `FAILED`;
- component unmount.

Do not poll broker-state every 3 seconds.

Retain broker-state's explicit refresh model.

### M. Trader-facing status copy

Replace the existing assumption that any current activation is simply `Active`.

Required lifecycle meanings:

```text
REQUESTED      Approved — waiting for Atlas runtime
STARTING       Starting
RUNNING        Running
STOP_REQUESTED Stopping
STOPPED        Stopped
BLOCKED        Blocked
FAILED         Failed
```

Translate operational phases into readable secondary labels without changing their semantics.

Technical raw codes may live under progressive disclosure where useful.

### N. Stop PAPER

For non-terminal current activation, expose:

`Stop PAPER`

The button opens a deliberate confirmation surface.

Required warning:

`Stopping PAPER does not close or modify broker positions or orders.`

Confirm action sends existing stop request with bounded reason:

`Trader requested stop from Atlas UI.`

Do not add:

- Close Trade;
- Cancel Order;
- SL/TP modification;
- reconciliation.

### O. Stop outcome handling

After STOP response:

- preserve activation ID;
- continue detail polling;
- show `Stopping` until durable terminal status.

For ambiguous transport failure:

- read activation detail;
- `STOP_REQUESTED` / `STOPPED` means accepted;
- otherwise surface uncertainty and allow explicit retry.

Do not claim broker flatness after STOP.

### P. Overview behavior

Do not place capital controls on Overview.

The existing compact runtime section may receive corrected trader-facing lifecycle labels so `REQUESTED` is not displayed generically as `Active`.

Overview remains observation-first.

---

## Out of scope

Do not add:

- backend activation semantics;
- backend stop semantics;
- migrations;
- new persistence;
- new OpenAPI routes;
- subprocess/runtime spawning;
- automatic runtime launch;
- scheduler/daemon installation;
- LIVE controls;
- credential configuration;
- account selection;
- manual Buy/Sell;
- manual Close;
- protection editing;
- reconciliation button;
- automatic activation;
- automatic retry with new identity;
- per-Trade approval;
- Strategy editing;
- new Risk model;
- dollar Risk estimates;
- new brokers/instruments/timeframes;
- redesign of completed PAPER Trade history.

If implementation discovers that one of these is required, stop for re-planning.

---

## Suggested task boundaries

### T001 — PAPER frontend control protocol

Own:

- `frontend/lib/api-client.ts`
- `frontend/lib/paper-control.ts`
- `frontend/tests/api_client.test.ts`
- new focused pure-helper tests as appropriate

Deliver:

- typed activate/detail/stop methods;
- exact Risk conversion;
- lifecycle/phase presentation helpers;
- stable request-body contract.

No page-level UI.

### T002 — Explicit PAPER activation workflow

Depends on T001.

Own:

- `frontend/app/paper/activate/page.tsx`
- `frontend/components/paper-activation.tsx`
- `frontend/tests/paper_activation.test.tsx`

Deliver:

- Strategy/version selection;
- parameter editor;
- Risk entry;
- capability/active/broker preflight reads;
- frozen review;
- stable activation request ID;
- typed confirmation;
- one-shot submit;
- ambiguous transport readback;
- success navigation.

T002 must not implement STOP.

### T003 — PAPER supervision and STOP

Depends on T001.

Own:

- `frontend/components/paper-status.tsx`
- `frontend/tests/paper_status.test.tsx`
- `frontend/components/overview.tsx` only if compact lifecycle copy requires adjustment
- `frontend/tests/overview.test.tsx` only if Overview changes

Deliver:

- current-session supervision;
- bounded status polling;
- trader-facing lifecycle/phase copy;
- Activate PAPER CTA when idle;
- explicit STOP confirmation;
- STOP uncertainty readback;
- broker/runtime separation;
- preservation of UI 03 history.

T002 and T003 may build sequentially to minimize overlapping control-state assumptions.

---

## Acceptance criteria

1. Trader can open `/paper/activate`.
2. No active session permits activation workflow.
3. Existing active session blocks a second activation workflow.
4. PAPER capability unavailable blocks activation.
5. Strategy and StrategyVersion are explicitly selected.
6. Only locally available versions are selectable.
7. Strategy methodology is visible before approval.
8. Parameters are derived from immutable version schema.
9. Parameter changes invalidate frozen review.
10. Risk field has no default value.
11. Risk is entered as trader-facing percent.
12. Authority-bearing Risk wire value is generated without float arithmetic.
13. Risk wire value remains a decimal string.
14. Review shows exact StrategyVersion, parameters, Risk, environment, and instrument.
15. Full provider account ID is not rendered in primary activation UI.
16. Trader must type `ACTIVATE PAPER`.
17. Browser sends existing `ACTIVATE_PAPER` confirmation code.
18. One frozen review uses one activation request UUID.
19. Same-review explicit retry reuses the same UUID.
20. Configuration change produces a new review identity.
21. No automatic activation retry occurs.
22. Successful activation navigates to PAPER supervision.
23. Ambiguous activation transport outcome performs read-only status resolution.
24. `REQUESTED` is not labeled `Running`.
25. `RUNNING` is clearly visible.
26. PAPER page shows Strategy/version and Risk for current session.
27. Status detail polling is bounded.
28. Broker-state endpoint is not polled at runtime-status cadence.
29. Stop PAPER requires explicit confirmation.
30. STOP warning states that broker positions/orders are not closed or modified.
31. STOP uses existing backend stop contract.
32. STOP does not expose a Close Trade action.
33. Ambiguous STOP outcome is resolved by read before claiming success.
34. STOPPED runtime is not presented as broker flatness.
35. BLOCKED/FAILED remain visible rather than generic success.
36. Existing broker exposure surface remains above runtime state.
37. Existing completed PAPER Trade history remains available.
38. Overview receives no capital-authorizing control.
39. Existing Risk authority is unchanged.
40. Existing Strategy methodology is unchanged.
41. Existing PAPER execution semantics are unchanged.
42. Existing provider semantics are unchanged.
43. No database migration.
44. No runtime process spawning.
45. No external credentialed operation during BUILD/VALIDATE/REVIEW.

---

## Validation plan

### T001 focused

Run focused frontend tests for:

- activation POST body;
- exact decimal-string Risk;
- 1% → 0.01;
- fractional-percent conversion;
- invalid/zero/100% Risk;
- detail GET;
- stop POST body;
- lifecycle labels.

Expected:

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/api_client.test.ts \
  frontend/tests/paper_control.test.ts
```

If helper test filename differs, intake should correct the exact command.

### T002 focused

Cover:

- no default Risk;
- Strategy/version loading;
- unavailable version;
- parameter defaults;
- parameter validation;
- capability unavailable;
- current active session;
- visible broker exposure;
- frozen review;
- review invalidation after configuration change;
- typed confirmation mismatch;
- typed confirmation match;
- only one POST while submitting;
- stable UUID on explicit retry;
- ambiguous POST + matching active read;
- ambiguous POST + no active read;
- conflicting active activation;
- success navigation;
- no credential/account-ID presentation.

Expected:

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/paper_activation.test.tsx
```

### T003 focused

Update/extend PAPER tests for:

- idle Activate PAPER CTA;
- REQUESTED copy;
- STARTING copy;
- RUNNING copy;
- STOP_REQUESTED copy;
- BLOCKED/FAILED copy;
- Strategy/version/Risk display;
- status polling;
- polling stops at terminal;
- broker state is not status-polled;
- Stop PAPER confirmation;
- stop warning;
- one stop POST;
- ambiguous STOP readback;
- no Close Trade control;
- terminal runtime does not imply flatness;
- completed Trade history remains.

Expected:

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/paper_status.test.tsx \
  frontend/tests/overview.test.tsx
```

### Existing backend authority regression

Because the workstream exposes capital-capable contracts without changing them, preserve focused backend evidence:

```bash
uv run pytest \
  backend/tests/test_api_paper.py \
  backend/tests/runtime
```

PLAN intake should narrow the exact runtime test path if `backend/tests/runtime` is not the canonical focused target.

Do not run external tests.

### Full frontend regression

```bash
npm run check:web
git diff --check
```

### Repository safety

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run alembic check
git diff --check
```

Backend checks should remain no-op evidence unless implementation unexpectedly touches backend code.

No real OANDA credentials are used.

Do not start `atlas-runtime`.

Do not activate PAPER.

Do not perform broker reads or mutations during automated validation.

---

## Manual visual validation

Before REVIEW, visually inspect with mocked/non-capital state:

1. idle PAPER page;
2. activation Strategy/configuration screen;
3. final approval screen;
4. REQUESTED state;
5. RUNNING state;
6. STOP confirmation;
7. BLOCKED state;
8. existing completed PAPER Trade history.

Verify:

- activation cannot be mistaken for an ordinary form submission;
- Risk is prominent;
- environment is unmistakably PAPER;
- final authorization text is readable;
- Stop cannot be mistaken for Close Trade;
- raw implementation IDs do not dominate;
- layout remains usable at desktop and narrow viewport.

No real activation is required for visual validation.

---

## Approval gate

This PLAN does not authorize implementation or PAPER activation.

Before GIT START:

1. Solo performs Critical PLAN/ARCHITECTURE intake.
2. Verify recorded base still matches `main`.
3. Verify all frontend and backend paths referenced here.
4. Verify generated API already exposes activation/detail/stop contracts.
5. Verify no OpenAPI regeneration is required.
6. Verify Strategy APIs expose required version/parameter/methodology data.
7. Verify the existing activation contract remains idempotent by activation request ID.
8. Verify STOP remains non-broker-mutation runtime control.
9. Verify runtime remains a separate process.
10. Verify no migration is required.
11. Verify T001/T002/T003 file ownership is feasible.
12. Apply any required artifact corrections.
13. Developer explicitly approves both corrected artifacts.

Only then:

`GIT START → tasks → BUILD → VALIDATE → REVIEW → merge approval`
