# ARCHITECTURE — PAPER Control 01 — Trader Activation & Supervision

**Role:** `ARCHITECT`
**Workstream:** `paper-control-01-trader-activation-supervision`
**Classification:** `Critical`
**Status:** proposed; pending PLAN/ARCHITECTURE intake and explicit developer approval
**Base:** `main` at `e2ad47c5cbfbca89d58f915745f81180c4864db9`

## Purpose

Give the local trader a deliberate UI path to authorize, observe, and stop a PAPER trading session without weakening the existing Atlas capital, Risk, execution, runtime, or broker boundaries.

This workstream does not create new trading authority.

It exposes the existing PAPER activation and stop contracts through a guarded trader-facing workflow.

---

## Architectural decision

PAPER Control 01 is a frontend control surface over the existing PAPER runtime API.

No new backend trading endpoint, persistence model, migration, Risk rule, execution rule, broker mutation, or runtime process-management mechanism is introduced.

The existing authority chain remains:

```text
Trader
  ↓ explicit PAPER approval
Local Atlas UI
  ↓ existing activation contract
PaperRuntimeService
  ↓ durable activation
atlas-runtime
  ↓ fresh startup/account/provider checks
Strategy
  ↓ intent
Atlas Risk
  ↓ RiskDecision
PAPER durable execution
  ↓
OANDA Practice
```

The UI is not a capital authority by itself.

The persisted activation remains the durable authorization boundary.

---

## Runtime process boundary

`POST /api/v1/paper/activations` does not launch `atlas-runtime`.

It records an explicitly approved activation.

The existing separate `atlas-runtime` process owns:

- singleton runtime ownership;
- startup recovery;
- provider capability reads;
- fresh account-state reads;
- analytical-frontier reads;
- Strategy evaluation;
- Risk evaluation;
- PAPER execution;
- reconciliation;
- STOP finalization.

Therefore:

- `atlas-runtime` must already be running for an approved activation to progress;
- the UI must not claim that a `REQUESTED` activation is already trading;
- the UI must distinguish `REQUESTED`, `STARTING`, and `RUNNING`;
- this workstream must not use subprocesses or make the API server responsible for runtime process lifecycle.

A future product-process composition slice may remove this operational prerequisite.

That is explicitly out of scope here.

---

## Approval semantics

PAPER activation is session-scoped capital authorization.

The final review must tell the trader that approval authorizes Atlas to create PAPER exposure automatically when the selected Strategy produces an eligible signal, subject to:

- the selected immutable StrategyVersion;
- the reviewed parameter snapshot;
- the reviewed Risk-per-trade rate;
- the configured OANDA Practice account;
- Atlas Risk;
- existing PAPER execution contracts;
- existing runtime safety/reconciliation rules.

Approval does not mean a broker Order will be submitted immediately.

It authorizes the runtime to create exposure later when all Strategy, Risk, account, market, and execution conditions permit it.

No per-Trade human prompt is added.

Any change to StrategyVersion, parameters, or Risk-per-trade requires a new activation and new explicit approval.

---

## Activation review boundary

Before a capital-authorizing POST is enabled, the UI must show one frozen review snapshot containing:

- Strategy name;
- immutable StrategyVersion;
- methodology summary;
- parameter values;
- instrument;
- provider/environment;
- Risk per trade;
- explicit PAPER environment labeling.

The full provider account ID must not be presented in the primary UI.

Use trader-facing language such as:

`Configured OANDA Practice account`

The UI must never display credentials.

---

## Explicit confirmation

The final activation action requires the trader to type exactly:

`ACTIVATE PAPER`

The browser then sends the existing API value:

`ACTIVATE_PAPER`

Typing the phrase is a UI accidental-action guard.

The backend's existing approval validation remains authoritative.

The final control should use unambiguous language such as:

`Activate PAPER trading`

It must not be presented as a generic Save, Run, Continue, or Start button.

---

## Activation identity and retries

Each reviewed activation snapshot receives one `activationRequestId`.

Rules:

1. Generate the UUID once for the frozen review snapshot.
2. Do not regenerate it while retrying the same snapshot.
3. If StrategyVersion, parameters, or Risk changes, invalidate the review and generate a new activation identity.
4. Permit only one activation POST in flight.
5. Never automatically retry a failed or timed-out activation POST with a new identity.

This preserves the existing idempotency contract.

### Ambiguous transport outcome

If the activation POST has an ambiguous client/transport failure:

1. perform a read-only active-status check;
2. if the returned activation ID equals the submitted ID, treat the activation as accepted;
3. if no active activation exists, offer an explicit trader retry using the same ID;
4. if a different activation exists, surface a conflict and do not retry automatically.

The frontend must not guess whether activation succeeded.

---

## Strategy authority

Use the existing Strategy catalog APIs:

- list Strategies;
- inspect Strategy detail/version history.

Only locally available StrategyVersions should be selectable in the UI.

The UI may use existing Strategy metadata for:

- display name;
- methodology summary;
- parameter schema;
- market requirements;
- execution availability.

However, frontend filtering is not PAPER authorization.

`PaperRuntimeService` remains authoritative for:

- exact StrategyVersion provenance;
- registered implementation identity;
- parameter validity;
- current supported PAPER market contract.

A server-side rejection must remain visible rather than being converted into frontend success.

---

## Parameter semantics

The activation UI edits only the parameter values for the selected immutable StrategyVersion.

Changing a parameter:

- does not mutate the StrategyVersion;
- invalidates any previously frozen activation review;
- invalidates the existing activation request identity.

Parameter inputs must follow the existing Strategy parameter schema.

The backend remains the final parameter validator.

---

## Risk authority

The trader enters Risk per trade as a percentage.

Example:

```text
UI:   1%
Wire: "0.01"
```

The activation request must continue sending `riskPerTrade` as an exact decimal string.

The frontend must not derive the authoritative wire value using binary floating-point arithmetic.

Use deterministic string-based percentage-to-ratio conversion.

Requirements:

- greater than 0%;
- less than 100%;
- no default Risk value;
- trader must deliberately enter a value.

The UI may display the reviewed percentage.

It must not calculate or promise a dollar Risk budget during activation.

Actual Risk budget and quantity remain based on fresh account facts when Atlas Risk evaluates a real Trade.

---

## Capability and broker-state reads

The activation screen may use existing read-only:

- PAPER capability;
- PAPER broker-state;
- active runtime status.

`PaperCapabilityResponse.available` must be true before activation can be submitted.

If an open broker Trade is visibly present, the activation control should be blocked because fresh PAPER bootstrap cannot safely begin with known exposure.

However:

- zero visible open Trades is not broad flatness proof;
- the UI must not label that result `Safe`, `Flat`, or `Approved`;
- pending Orders and other startup facts remain the runtime's responsibility.

If the broker-state read is unavailable, surface that uncertainty.

Do not convert it into broker-flat proof.

The runtime's mandatory fresh startup checks remain authoritative.

---

## Runtime supervision

The PAPER page becomes the operational home for the current PAPER session.

The Overview remains primarily observational and must not gain capital controls.

The full PAPER page must show trader-facing lifecycle labels.

| Durable lifecycle | Trader-facing meaning                |
| ----------------- | ------------------------------------ |
| `REQUESTED`       | Approved — waiting for Atlas runtime |
| `STARTING`        | Starting                             |
| `RUNNING`         | Running                              |
| `STOP_REQUESTED`  | Stopping                             |
| `STOPPED`         | Stopped                              |
| `BLOCKED`         | Blocked                              |
| `FAILED`          | Failed                               |

Operational phase may be translated into readable secondary status:

| Phase              | Trader-facing meaning            |
| ------------------ | -------------------------------- |
| `IDLE`             | Waiting                          |
| `STARTING`         | Starting                         |
| `WAITING_FRONTIER` | Waiting for next market frontier |
| `WAITING_DATA`     | Waiting for market data          |
| `WAITING_PROVIDER` | Waiting for broker               |
| `EVALUATING`       | Evaluating Strategy              |
| `EXECUTING`        | Executing approved Trade         |
| `RECOVERING`       | Recovering broker evidence       |
| `STOPPING`         | Stopping                         |
| `BLOCKED`          | Blocked                          |
| `FAILED`           | Failed                           |

Do not display `Active` for every non-null activation.

In particular, `REQUESTED` is not equivalent to `RUNNING`.

---

## Status polling

Runtime status is database-backed and may be polled while a session is non-terminal.

Use bounded frontend polling.

Target cadence:

`3 seconds`

Do not poll the broker-state endpoint at the same cadence.

Broker state performs provider reads and should retain its explicit/manual refresh behavior unless separately justified.

After an activation ID is known, prefer:

`GET /api/v1/paper/activations/{activation_id}`

for supervision.

This permits the UI to observe the session through terminal `STOPPED`, `BLOCKED`, or `FAILED` state even when it no longer qualifies as the active activation.

On a fresh page load, use the existing active-activation endpoint to discover a current session.

---

## Stop semantics

Stopping PAPER is not closing a Trade.

The UI must state:

`Stopping PAPER does not close or modify broker positions or orders.`

A stop action means the trader requests the PAPER runtime session to stop.

The existing backend remains authoritative for STOP/ENTRY linearization.

The UI must not promise that a stop click retroactively cancels work that already crossed an authoritative execution boundary.

### Stop interaction

Stopping requires a deliberate two-step interaction:

1. trader selects `Stop PAPER`;
2. confirmation surface explains the consequences;
3. trader selects `Confirm stop`.

No typed phrase is required because STOP does not increase capital authority.

Send the existing stop contract with a bounded reason such as:

`Trader requested stop from Atlas UI.`

After POST success, continue observing the activation until terminal state.

---

## Stop transport uncertainty

If the STOP request has an ambiguous transport outcome:

1. GET the activation detail;
2. if lifecycle is `STOP_REQUESTED` or `STOPPED`, treat the request as accepted;
3. otherwise surface uncertainty and permit an explicit retry.

Do not automatically claim that PAPER stopped.

---

## Current broker exposure

Broker exposure remains visually separate from runtime state.

The PAPER UI must preserve the distinction:

```text
Broker exposure
≠
Runtime lifecycle
```

A stopped or blocked runtime does not prove a flat broker account.

The existing broker-state surface remains the authority for the supported current broker exposure projection.

No `Close trade` control is introduced.

---

## Failure behavior

Activation failures must remain explicit.

Examples include:

- PAPER capability unavailable;
- StrategyVersion unavailable;
- parameter validation failure;
- activation already present;
- unresolved historical PAPER attempt;
- startup broker/provider failure;
- bootstrap account not safe;
- runtime block/failure;
- transport uncertainty.

Do not transform a rejected or blocked activation into a generic success state.

Blocked and failed runtime reason information should remain inspectable in trader-facing language, with technical codes available only as secondary detail when useful.

---

## Local authority and secrets

This workstream preserves the existing loopback-only HTTP boundary.

It must not:

- widen API network admission;
- accept proxy/header-derived remote authority;
- expose OANDA tokens;
- log credential material;
- render full provider account IDs as primary UI;
- persist new credential material in browser storage.

Activation state may remain in React state.

No localStorage/sessionStorage persistence is required.

---

## Persistence and migrations

No new persistence is required.

Existing durable activation records already preserve:

- StrategyVersion identity;
- validated parameter snapshot;
- parameter fingerprint;
- Risk per trade;
- provider/environment/account identity;
- approval kind/code;
- lifecycle state;
- operational phase.

No database migration is permitted for this workstream.

If implementation proves a new durable authority fact is necessary, stop and return for architecture review.

---

## API boundary

Use existing routes unchanged:

```text
GET  /api/v1/paper/capability
GET  /api/v1/paper/broker-state
GET  /api/v1/paper/activations/active
GET  /api/v1/paper/activations/{activation_id}

POST /api/v1/paper/activations
POST /api/v1/paper/activations/{activation_id}/stop
```

Do not expose reconciliation as a routine trader control in this slice.

No new backend endpoint is planned.

No OpenAPI regeneration should be necessary unless intake finds current generated types stale.

---

## UI placement

### `/paper`

The PAPER page becomes:

```text
PAPER

Current broker exposure

Current PAPER session
  Strategy
  Risk
  lifecycle
  operational phase
  Stop PAPER

Completed PAPER trades

Capability / technical evidence
```

When no active activation exists, show a clear:

`Activate PAPER`

link to the dedicated activation workflow.

### `/paper/activate`

Dedicated deliberate capital-approval flow:

```text
1. Strategy
2. Parameters
3. Risk
4. Review
5. Type ACTIVATE PAPER
6. Activate PAPER trading
```

Do not place the final capital-authorizing control on the Overview dashboard.

---

## Non-goals

PAPER Control 01 does not add:

- runtime subprocess spawning;
- daemon/service installation;
- scheduler;
- automatic activation;
- automatic reactivation after terminal state;
- LIVE controls;
- broker credential editing;
- account switching;
- Risk-policy editing beyond choosing the existing activation risk rate;
- per-Trade manual approval;
- manual Buy/Sell;
- Close Trade;
- SL/TP editing;
- reconciliation button;
- retrying unknown broker mutations;
- PAPER history redesign;
- Strategy methodology editing;
- new provider support;
- new instrument/timeframe support.

---

## Safety invariants

Implementation must preserve all of the following:

1. Starting Atlas does not authorize trading.
2. A PAPER activation requires a deliberate trader action.
3. The reviewed StrategyVersion is immutable.
4. Reviewed parameters are exactly the parameters sent.
5. Reviewed Risk is exactly the Risk value sent.
6. Changing authority-bearing configuration invalidates approval/review identity.
7. One frozen review uses one stable activation request ID.
8. Automatic capital-authorizing POST retries are forbidden.
9. Backend activation validation remains authoritative.
10. Runtime startup checks remain authoritative.
11. Atlas Risk remains authoritative for each Trade.
12. UI never sends broker mutations directly.
13. Stop is not represented as Close Trade.
14. Runtime terminal state is not represented as broker flatness.
15. Unknown state remains visible.
16. Credentials remain outside UI state and logs.
17. Existing local-only API authority is not widened.
18. No migration or new durable capital authority is introduced.

---

## Architecture approval gate

Before implementation:

1. Solo validates this architecture against current repository facts.
2. PLAN is validated against this architecture.
3. Any material discrepancy returns to developer review.
4. Developer explicitly approves both artifacts.
5. Only then may GIT START occur.
