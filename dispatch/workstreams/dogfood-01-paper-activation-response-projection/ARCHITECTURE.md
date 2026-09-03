# ARCHITECTURE — Dogfood 01 PAPER Activation Response Projection Remediation

## Dispatch

- **Role:** `ARCHITECT`
- **Workstream:** `dogfood-01-paper-activation-response-projection`
- **Branch:** `main` (pre-GIT START; no branch operation performed)
- **CWD:** `/Users/vike/Desktop/atlas`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-paper-activation-response-projection/ARCHITECTURE.md`
- **Status:** `FROZEN FOR DEVELOPER APPROVAL`

## 1. Defect and affected path

The committed activation path is:

```text
POST /api/v1/paper/activations
  -> PaperRuntimeService.activate()
  -> PaperRuntimeRepository.create_activation()
  -> durable activation transaction commits
  -> _activation_from_row() [restores row.requested_at]
  -> PaperRuntimeActivationResult.to_json()
  -> PaperRuntimeActivation.to_json()
  -> FastAPI PaperRuntimeActivationResultResponse validation
```

`PaperRuntimeActivationResponse.requested_at` is required and emitted on the HTTP wire as `requestedAt`.

`PaperRuntimeActivation.to_json()` currently omits that required field.

The result is an operational-truth defect at the PAPER control boundary: activation can commit successfully while the client receives HTTP 500.

The active, detail/status, and stop routes reuse the same activation projection and therefore depend on the same repair.

This is a Dogfood 01 remediation against the existing PAPER runtime capability. It is not a new PAPER milestone or new runtime capability.

## 2. Narrow architecture decision

Make one outbound production projection repair in:

```text
backend/runtime/persistence_contracts.py
PaperRuntimeActivation.to_json()
```

Add the activation's existing requested timestamp:

```python
"requested_at": self.requested_at.isoformat().replace("+00:00", "Z"),
```

The value is the already validated and UTC-normalized `self.requested_at` restored from durable persistence or assigned when the activation was originally constructed.

Use the same timestamp wire convention already used by:

- `state_changed_at`;
- `last_operational_at`;
- `last_frontier_end`;
- `updated_at`.

No schema, route, repository, model, migration, activation transaction, lifecycle, idempotency, Risk, Strategy, execution, runtime, reconciliation, or provider behavior changes are part of this repair.

`PaperRuntimeActivationResponse` remains strict and required. `requestedAt` must not be made optional to hide the projection defect.

### Identity guardrail

`requested_at` remains excluded from `PaperRuntimeActivation.immutable_json()`.

`immutable_json()` participates in the activation's durable immutable identity. Adding `requested_at` there would incorrectly couple replay identity to a newly constructed request timestamp and could turn an exact same-ID replay into an identity conflict.

The repair is therefore strictly outbound:

```text
durable requested_at
        ↓
PaperRuntimeActivation.requested_at
        ↓
PaperRuntimeActivation.to_json()
        ↓
PaperRuntimeActivationResponse
        ↓
requestedAt
```

No identity input changes.

## 3. Frozen response contract

The response models and route envelopes remain unchanged:

| Route                                                 | Declared response model                | Activation projection                            |
| ----------------------------------------------------- | -------------------------------------- | ------------------------------------------------ |
| `POST /api/v1/paper/activations`                      | `PaperRuntimeActivationResultResponse` | `activation` plus `replayed`                     |
| `GET /api/v1/paper/activations/active`                | `PaperRuntimeStatusResponse`           | nested `activation` plus current status evidence |
| `GET /api/v1/paper/activations/{activation_id}`       | `PaperRuntimeStatusResponse`           | nested `activation` plus current status evidence |
| `POST /api/v1/paper/activations/{activation_id}/stop` | `PaperRuntimeActivationResponse`       | direct activation projection                     |

The repaired field remains:

| Domain projection key | HTTP key      | HTTP wire type | Required source and format                                              |
| --------------------- | ------------- | -------------- | ----------------------------------------------------------------------- |
| `requested_at`        | `requestedAt` | JSON string    | original durable `self.requested_at`, ISO-8601 UTC with `Z`, never null |

For example, an aware value of:

```text
2026-09-03T08:00:00-04:00
```

is normalized by the domain contract before projection and emitted as:

```text
2026-09-03T12:00:00Z
```

A value with microseconds retains them:

```text
2026-09-03T12:00:00.123456Z
```

The projection must not use:

- a new clock value;
- response-generation time;
- epoch seconds;
- a space-separated datetime;
- `state_changed_at`;
- `updated_at`;
- any reconstructed approximation.

`requestedAt` is evidence of the original explicit activation request.

It is not evidence that:

- the runtime started;
- runtime ownership was acquired;
- OANDA was queried;
- Risk approved an entry;
- an execution attempt occurred;
- broker exposure exists.

The response model remains the FastAPI validation authority. `model_validate()` accepts the domain's snake-case projection, while the HTTP response emits the model's camel-case aliases.

## 4. Decimal-string contract

`riskPerTrade` remains a decimal string at both HTTP boundaries.

### Request

`PaperActivationRequest`:

- accepts a JSON string;
- permits a direct typed `Decimal` caller;
- rejects JSON numeric values before binary-float conversion;
- requires a finite Decimal;
- requires:

```text
0 < risk_per_trade < 1
```

### Runtime projection

The existing activation projection continues to pass `risk_per_trade` through `canonical_decimal_text()` inside `immutable_json()`.

This established canonical representation is unchanged.

For example:

```text
request:   "0.0100"
projection: "0.01"
```

The Decimal value is preserved even though redundant textual scale is canonicalized.

### Response

`PaperRuntimeActivationResponse` continues to parse the projected value as `Decimal`, and its existing field serializer emits a JSON string.

No float, numeric JSON value, rounding rule, or new normalization is introduced.

Tests must assert:

- JSON string type;
- Decimal/value preservation;
- existing canonicalization behavior.

A hand-written fake payload with a manually added `requested_at` is not sufficient evidence of the repaired domain projection.

## 5. Invariants that must remain true

- A successful create response is still produced only from the existing activation transaction and projection flow.
- This repair does not move, split, duplicate, retry, or otherwise alter the activation transaction.
- An exact same-ID replay still returns:

  - the original durable activation;
  - `replayed: true`;
  - the original `requestedAt`.

- A same-ID request with changed immutable facts still follows the existing identity-conflict contract.
- A different activation request while the non-terminal PAPER slot is occupied still follows the existing active-slot conflict contract.
- The existing Dogfood 01 durable activation remains untouched.
- The existing activation continues to represent:

```text
lifecycle_state: REQUESTED
operational_phase: IDLE
state_origin: FRESH_BOOTSTRAP
risk_per_trade: 0.001
```

- `GET active` continues to treat the existing non-terminal `REQUESTED` activation according to current runtime semantics.
- Status continues to distinguish runtime lifecycle from execution and reconciliation evidence.
- STOP continues to use its existing guarded lifecycle transition and retains the original activation timestamp.
- No runtime process is started.
- No new activation is created.
- No OANDA request is made.
- No broker mutation occurs.
- No new capital-capable behavior is introduced.

## 6. Valid, invalid, and boundary examples

### Valid

```json
{
  "activationRequestId": "11111111-1111-1111-1111-111111111111",
  "strategyVersionId": "22222222-2222-2222-2222-222222222222",
  "parameters": {},
  "riskPerTrade": "0.0100",
  "confirmation": "ACTIVATE_PAPER"
}
```

A corresponding activation response contains:

```json
{
  "requestedAt": "2026-09-03T12:00:00Z",
  "riskPerTrade": "0.01",
  "lifecycleState": "REQUESTED",
  "operationalPhase": "IDLE",
  "stateOrigin": "FRESH_BOOTSTRAP"
}
```

The same activation body remains valid:

- nested under create;
- nested under active/status;
- nested under detail/status;
- returned directly by stop.

### Invalid

Removing `requested_at` from a real activation domain projection must make `PaperRuntimeActivationResponse.model_validate()` fail.

The field remains required. An HTTP 500 caused by the application omitting it is the regression being removed, not a reason to weaken the contract.

The following request values remain invalid:

```text
riskPerTrade: 0.01
riskPerTrade: "0"
riskPerTrade: "1"
riskPerTrade: "NaN"
riskPerTrade: "Infinity"
```

Unknown request fields remain invalid.

Any confirmation other than:

```text
ACTIVATE_PAPER
```

remains invalid.

A same-ID request with changed immutable Strategy, parameters, configured account identity, or risk facts remains governed by the existing identity-conflict behavior. This remediation must not create a second activation or alter the original timestamp.

### Boundary

The following remain valid finite decimal-string values under the current open interval:

```text
"0.00000000001"
"0.99999999999"
```

Exact `0` and exact `1` remain rejected.

An aware non-UTC `requested_at` is normalized to UTC before projection.

An unaware datetime remains invalid at the domain/persistence boundary and is not silently treated as local time or UTC.

STOP from a `REQUESTED` activation continues to follow the existing guarded lifecycle semantics and retains the original `requestedAt`. Exercising that response in deterministic tests does not authorize a runtime start.

## 7. Required deterministic validation evidence

The BUILD regression must use fixed UUIDs, a fixed timezone-aware datetime, exact `Decimal` values, and fakes/`TestClient` only.

### 7.1 Domain projection

Construct a real `PaperRuntimeActivation`.

Assert:

```text
activation.to_json()["requested_at"]
```

equals the exact normalized timestamp expected from the domain object.

Also assert the existing `risk_per_trade` projection remains canonical Decimal text.

Validate that projection with `PaperRuntimeActivationResponse`.

Serialize in alias mode and assert:

```text
requestedAt
riskPerTrade
```

are present, with `riskPerTrade` remaining a JSON string.

### 7.2 HTTP projection

Drive these four success paths through the FastAPI router:

1. create activation;
2. active activation;
3. detail/status;
4. stop.

The fake service must return a real `PaperRuntimeActivation` or `PaperRuntimeStatus` projection through the existing `.to_json()` methods.

It must not manually pre-populate `requested_at`.

Each route must:

```text
HTTP 200
requestedAt present
requestedAt exact
riskPerTrade string
```

### 7.3 Existing behavioral guards

Retain or extend deterministic coverage for:

- numeric `riskPerTrade` rejection;
- unknown-field rejection;
- open interval boundaries;
- high-precision Decimal strings;
- exact same-ID replay;
- immutable identity conflict;
- unchanged `REQUESTED`;
- unchanged `IDLE`;
- unchanged `FRESH_BOOTSTRAP`.

The test suite must not operate on the real Dogfood 01 activation.

### 7.4 Focused validation command

At minimum:

```text
uv run pytest \
  backend/tests/test_api_paper.py \
  backend/tests/runtime/test_runtime_activation.py \
  backend/tests/runtime/test_runtime_persistence.py \
  backend/tests/runtime/test_runtime_risk_precision.py
```

Use additional focused tests only if the changed code's real dependency surface requires them.

No:

- `atlas-runtime`;
- live database activation;
- mutation of the existing Dogfood activation;
- credentialed OANDA check;
- broker mutation;
- external provider integration test

is required for this projection-only repair.

## 8. Evidence and concerns for approval

Baseline deterministic tests covering the nearby PAPER API/runtime surface completed with:

```text
59 passed
1 warning
```

before this architecture artifact was frozen.

That green baseline does not catch the production defect because the existing API test fixture manually supplies `requested_at` instead of exercising the real `PaperRuntimeActivation.to_json()` projection.

The required regression must close that exact blind spot.

The only production behavior authorized to change is:

```text
PaperRuntimeActivation.to_json()
    before: missing requested_at
    after:  requested_at from existing durable activation timestamp
```

Everything else remains frozen.

The existing Dogfood 01 activation remains durable, non-running, and untouched until this remediation closes and the trader explicitly resumes Dogfood 01.
