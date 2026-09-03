# PLAN — Dogfood 01 PAPER Activation Response Projection Remediation

## Workstream state

- **Workstream:** `dogfood-01-paper-activation-response-projection`
- **Outcome:** Restore the missing `requestedAt` field at the PAPER activation response boundary so committed activation projections validate successfully without changing activation, idempotency, lifecycle, Risk, execution, or broker semantics.
- **Classification:** `Critical`. This is a narrow Dogfood 01 remediation at the capital-capable PAPER control boundary: the response may fail after durable activation commit, while the durable activation must remain untouched.
- **Base:** `main` at `4a737af780526f06e2c60ffeb63a9a901f0284b9` (`Close PAPER 06 workstream`)
- **Base SHA:** `4a737af780526f06e2c60ffeb63a9a901f0284b9`
- **Branch:** `solo/dogfood-01-paper-activation-response-projection`
- **Phase:** `READY_FOR_USER`
- **Approval:** approved for implementation by developer
- **Architecture:** `FROZEN` and reconciled with this PLAN
- **Task state:** `T001` DONE
- **Next action:** await explicit developer merge approval; do not merge without it
- **Concerns:** Non-blocking pre-existing TestClient deprecation warning and historical
  validation metadata note; do not start `atlas-runtime`, contact OANDA, create another
  PAPER activation, modify the existing durable activation, change Risk or execution
  behavior, or add runtime/scheduling/recovery/broker scope.

## 1. Proven defect

The current `PaperRuntimeActivationResponse` declares required `requested_at` / wire alias `requestedAt`, while `PaperRuntimeActivation.to_json()` omits `requested_at`.

The Dogfood 01 activation request therefore reached durable persistence successfully, but FastAPI response validation failed afterward with HTTP 500.

The reported durable Dogfood 01 activation remains the source of truth and must not be edited:

```text
StrategyVersion: 86b405a3-cb11-47f0-81f1-84c4e5501094
risk_per_trade: 0.001
lifecycle_state: REQUESTED
operational_phase: IDLE
state_origin: FRESH_BOOTSTRAP
```

No runtime owner has been started and no broker mutation is part of this remediation.

## 2. Scope

In scope:

- Restore `requested_at` in the existing activation JSON projection using its durable value and existing timestamp wire convention.
- Verify the declared FastAPI response projections for:

  - create activation;
  - active activation;
  - activation detail/status;
  - stop.

- Add focused regression coverage proving a real activation domain projection serializes successfully with `requestedAt`.
- Preserve exact decimal-string handling for `riskPerTrade`.
- Preserve activation idempotency, immutable identity, and existing durable `REQUESTED` semantics.

Explicitly out of scope:

- Any change to activation transaction semantics.
- Any change to lifecycle transitions.
- Any change to activation idempotency identity.
- Persistence schema or migration changes.
- Modification, deletion, replay, or replacement of the existing Dogfood 01 activation.
- Starting `atlas-runtime`.
- Creating another PAPER activation.
- Credentialed OANDA requests.
- Broker mutations.
- Scheduling, recovery, reconciliation behavior, Risk policy, Strategy methodology, or PAPER execution behavior.
- Any new PAPER capability or new numbered PAPER milestone.

## 3. Acceptance criteria

1. `PaperRuntimeActivation.to_json()` supplies the required `requested_at` value from the activation's existing durable/requested timestamp.
2. The projected timestamp uses the existing UTC ISO-8601 `Z` convention.
3. Create activation, get active activation, get activation status, and stop response projections validate against their declared FastAPI response models.
4. Regression coverage exercises the real activation domain projection and asserts the HTTP representation contains valid `requestedAt`.
5. `riskPerTrade` remains a JSON string on the request/response boundary with no float conversion or semantic normalization change.
6. Same-ID activation replay/idempotency behavior remains unchanged.
7. Existing durable `REQUESTED` / `IDLE` / `FRESH_BOOTSTRAP` semantics remain unchanged.
8. `requested_at` remains outside immutable activation identity so replay identity is not changed by this repair.
9. Safe deterministic validation uses fakes/fixtures only; no runtime start, PAPER activation, credentialed OANDA request, broker mutation, or external capital-capable action occurs.

## 4. Reconciled architecture contract

- The only authorized production-code repair is `PaperRuntimeActivation.to_json()` emitting the already validated and UTC-normalized `requested_at` using the existing ISO-8601 `Z` convention.
- `PaperRuntimeActivationResponse` remains strict and required; the fix must not make `requested_at` optional or alter response envelopes.
- `requested_at` remains excluded from `immutable_json()` so same-ID replay identity and durable activation semantics remain unchanged.
- The unchanged activation projection must validate through create, active, detail/status, and stop responses.
- Regression coverage must construct/use a real `PaperRuntimeActivation` projection rather than a fake payload that manually supplies `requested_at`.
- `riskPerTrade` remains a JSON string using the existing exact Decimal ingestion and canonical runtime projection.
- No repository/model/migration/transaction/lifecycle/Risk/execution/runtime/provider seam is authorized to change.
- Required checks are deterministic API/runtime tests using fixed UUIDs, fixed time, and fakes only.

## 5. Lifecycle gate

```text
PLAN
→ ARCHITECTURE
→ reconcile PLAN + ARCHITECTURE
→ DEVELOPER_APPROVAL
→ GIT START
→ BUILD
→ VALIDATE
→ REVIEW
→ READY_FOR_USER   ← CURRENT; merge approval pending
→ GIT END
```

Implementation and independent validation/review are complete. The next action
requires explicit developer merge approval; no merge or Git history operation has
been performed.
