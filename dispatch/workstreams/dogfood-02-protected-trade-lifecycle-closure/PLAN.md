# PLAN — Dogfood 02 Protected Trade Lifecycle Closure

## Workstream state

- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Classification:** `Critical`
- **Base:** `main` at `c0079e7b3f4f8bfbd00754060d37f7fdb925d649` (`Close UI 02 trader shell workstream`)
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Phase:** `COMPLETED`
- **Approval:** developer approved the frozen PLAN + ARCHITECTURE on 2026-09-09 after repo-local intake
- **Architecture:** frozen; `ARCHITECTURE.md` defines the semantic authority for this workstream
- **Task state:** T001 `DONE`; T002 `DONE`; R001 chain `FAIL`; R002 BUILD `DONE`, validation `PASS`, review `PASS`
- **Next action:** none; workstream merged and closed
- **Concerns:** repository-wide static-analysis debt remains outside the affected surface

## Outcome

Close the Dogfood 02 lifecycle gap so an explicitly requested reconciliation can inspect a
healthy previously `FILLED_PROTECTED` PAPER Trade after runtime termination, durably record
its later broker `CLOSED` lifecycle, and return bounded completed-Trade evidence without
weakening Atlas recovery, Risk, execution, mutation, or flatness boundaries.

The target transition is:

```text
FILLED_PROTECTED + NOT_RUN
→ exact GET-only Trade reconciliation
→ FILLED_PROTECTED + LIFECYCLE_ADVANCED
```

when the exact attributable Trade has naturally closed at the broker.

The same reconciliation should preserve the broker-supported closure evidence needed to
understand the completed Trade:

```text
close time
average close price
realized P/L
financing
dividend adjustment
closing transaction IDs
exit cause when exactly attributable
exact close price when one exact closing TradeReduce exists
```

This is a Dogfood remediation workstream, not PAPER 07.

It creates no new capital authority.

## Demonstrated Dogfood finding

Dogfood 02 completed a real OANDA Practice PAPER entry with:

```text
execution_outcome = FILLED_PROTECTED
```

The runtime was intentionally stopped after the single approved Trade.

The broker later closed the protected Trade naturally.

A fresh GET-only open-Trade observation then returned:

```text
open_trade_count = 0
trades = []
last_transaction_id = 20
```

The existing explicit reconciliation endpoint returned:

```text
performed = false
reconciliationStatus = NOT_RUN
executionOutcome = FILLED_PROTECTED
```

The endpoint did not perform provider reconciliation.

Current-main inspection shows why:

```text
PaperRuntimeService.reconcile()
→ _attempt_is_outstanding()
→ is_unsafe_paper_attempt()
```

and `FILLED_PROTECTED + NOT_RUN` is deliberately safe under the existing
recovery/new-session safety predicate.

The underlying PAPER reconciliation coordinator already supports an exact attributable
Trade in state `CLOSED` and maps it to:

```text
TRADE_LIFECYCLE_ADVANCED
LIFECYCLE_ADVANCED
```

The missing seam is therefore the explicit lifecycle-reconciliation eligibility rule, not a
new broker execution mechanism.

## Architecture authority

`ARCHITECTURE.md` freezes the following decisions:

1. `is_unsafe_paper_attempt()` remains unchanged.
2. Explicit manual lifecycle reconciliation receives a separate narrow eligibility rule.
3. `FILLED_PROTECTED + NOT_RUN/CONSISTENT` with coherent durable Fill may reach the
   existing reconciliation coordinator.
4. `FILLED_PROTECTED + LIFECYCLE_ADVANCED` is already lifecycle-complete and may no-op.
5. Runtime-active states remain reconciliation-busy.
6. An exact CLOSED Trade still produces `LIFECYCLE_ADVANCED` without rewriting
   `FILLED_PROTECTED`.
7. OANDA Trade GET owns aggregate completed-Trade facts.
8. Exact closing OrderFill/TradeReduce evidence owns single-transaction exit attribution
   and exact close price.
9. Multiple closing transaction IDs are preserved as `MULTIPLE`; Atlas does not invent one
   exit.
10. A failed optional exit-cause enrichment does not erase an already-proven CLOSED
    lifecycle.
11. Closure evidence is durably stored in the existing append-only broker-observation
    ledger.
12. No database migration is expected.
13. No realized-R or net-P/L contract is introduced.
14. No broker mutation is authorized.

If implementation cannot satisfy those decisions using the current evidence ledger, stop
for architecture re-approval.

## Scope

### In scope

#### A. Manual lifecycle reconciliation eligibility

Replace the current use of “unsafe/outstanding” as the only reason to perform explicit
terminal-runtime reconciliation with a narrowly separate reconciliation eligibility rule.

Preserve current unsafe recovery behavior.

Additionally permit:

```text
FILLED_PROTECTED + NOT_RUN
FILLED_PROTECTED + CONSISTENT
```

when the durable Fill identity is coherent.

Do not repeatedly perform normal lifecycle reconciliation after:

```text
FILLED_PROTECTED + LIFECYCLE_ADVANCED
```

unless future architecture explicitly requires it.

#### B. Provider-neutral closure contract

Add the immutable closure/exit contract defined by `ARCHITECTURE.md`.

Keep:

- exact Decimal values;
- timezone-aware times;
- bounded IDs;
- deterministic serialization;
- explicit unresolved/multiple semantics.

#### C. OANDA CLOSED Trade normalization

Extend the existing exact Trade reconciliation reader to normalize documented closure
facts for a CLOSED Trade.

Required aggregate fields:

```text
closeTime
averageClosePrice
realizedPL
financing
dividendAdjustment
closingTransactionIDs
```

Continue using:

```text
initialUnits
```

for CLOSED Trade identity.

Do not weaken the existing account-scoped Trade identity rules.

#### D. OANDA closing transaction normalization

Add a narrow GET-only read for one exact closing transaction.

For a single `closingTransactionID`, normalize the exact OrderFill/TradeReduce information
needed to determine:

- exact affected Trade;
- exact close price;
- realized P/L for that reduction;
- financing for that reduction;
- provider fill reason.

Use the matching `TradeReduce.price`.

Do not use the deprecated top-level OrderFill `price` as close-price authority.

#### E. Exit-cause mapping

Implement the architecture's provider-neutral mapping:

```text
TAKE_PROFIT
STOP_LOSS
MARKET_CLOSE
MARGIN_CLOSEOUT
OTHER
MULTIPLE
UNRESOLVED
```

Preserve the exact provider reason where a single transaction is attributable.

Do not infer cause from target/stop price proximity.

#### F. Reconciliation composition

When the exact Trade is CLOSED:

1. preserve current exact Trade attribution;
2. set lifecycle result to `LIFECYCLE_ADVANCED`;
3. preserve aggregate closure;
4. if one closing transaction ID exists, attempt one bounded exact closing-transaction GET;
5. enrich exit cause/exact price when provable;
6. keep lifecycle advanced if optional cause enrichment is unavailable;
7. link all successful normalized reads to the same reconciliation run;
8. apply the reconciliation through the existing append/apply transaction.

Multiple closing IDs do not trigger transaction fan-out in this workstream.

#### G. Durable normalized evidence

Extend the bounded normalized-fact vocabulary and introduce the closure-capable broker fact
schema version.

Existing V1 evidence remains unchanged.

Persist:

- CLOSED Trade aggregate evidence;
- single closing-transaction evidence when successfully read;
- exit-attribution uncertainty/conflict evidence as applicable.

Do not persist raw OANDA JSON.

#### H. Bounded reconciliation response

Extend the reconciliation result/HTTP response with optional:

```text
tradeClosure
```

using exact decimal strings.

No closure proven:

```text
tradeClosure = null
```

Closure proven:

```text
tradeClosure = {
  tradeId,
  closedAt,
  averageClosePrice,
  realizedPl,
  financing,
  dividendAdjustment,
  closingTransactionIds,
  exitCause,
  providerReason,
  closingTransactionId,
  exactClosePrice
}
```

The response must not contain:

- account ID;
- token;
- raw broker payload;
- derived realized R;
- unsupported net P/L.

#### I. Generated OpenAPI client

If the HTTP schema changes, regenerate the generated frontend API types through the
repository's existing workflow.

No frontend component/UI change is authorized.

## Out of scope

- new PAPER activation;
- new Dogfood Trade;
- runtime restart;
- automatic reconciliation polling;
- scheduler/background reconciliation;
- broker Trade close/reduce;
- Stop/TP modification;
- broker repair;
- mutation retry;
- Risk changes;
- Strategy changes;
- methodology changes;
- new account/instrument/timeframe;
- LIVE;
- completed-Trade UI;
- PAPER history UI;
- realized-R calculation;
- performance analytics;
- new `completed_trades` table;
- new closure database projection;
- broad OANDA refactor;
- generic multi-provider exit-reason framework beyond the narrow provider-neutral contract
  required here.

## Expected files

### Primary production files

```text
backend/paper/persistence_contracts.py
backend/paper/reconciliation.py
backend/integrations/oanda/reconciliation.py
backend/runtime/activation.py
backend/api/schemas.py
```

`backend/api/paper.py` may change only if required to project the new bounded result. Its
route authority must remain unchanged.

### Generated contract

If required:

```text
frontend/lib/api.generated.ts
```

generated only.

### Primary tests

```text
backend/tests/paper/test_persistence_contracts.py
backend/tests/paper/test_reconciliation.py
backend/tests/integrations/test_oanda_reconciliation.py
backend/tests/runtime/test_runtime_activation.py
```

Use existing PAPER API tests for response coverage rather than creating a redundant new
suite if they already own this route.

### Files expected to remain untouched

```text
backend/paper/execution.py
backend/paper/risk_evaluation.py
backend/risk/**
backend/integrations/oanda/execution.py
backend/integrations/oanda/mutation_request.py
backend/runtime/orchestration.py
backend/persistence/models.py
backend/persistence/migrations/**
frontend/components/**
```

If implementation requires a material semantic change in one of these areas, stop for
architecture re-approval.

## Suggested task boundaries

Create tasks only after explicit approval.

### T001 — Closure evidence contracts and OANDA normalization

Primary ownership:

```text
backend/paper/persistence_contracts.py
backend/integrations/oanda/reconciliation.py
backend/tests/paper/test_persistence_contracts.py
backend/tests/integrations/test_oanda_reconciliation.py
```

Outcome:

- provider-neutral closure contract;
- exit-cause enum;
- closure-capable normalized broker-facts schema;
- exact CLOSED Trade aggregate normalization;
- exact one-transaction close normalization;
- OANDA reason mapping;
- multiple/unresolved semantics;
- no deprecated OrderFill price authority;
- no mutation.

T001 must not alter runtime reconciliation eligibility.

### T002 — Lifecycle reconciliation composition and public result

Depends on T001.

Primary ownership:

```text
backend/paper/reconciliation.py
backend/runtime/activation.py
backend/api/schemas.py
backend/api/paper.py          # only if projection requires it
frontend/lib/api.generated.ts # generated only, if schema changed
backend/tests/paper/test_reconciliation.py
backend/tests/runtime/test_runtime_activation.py
existing PAPER API tests
```

Outcome:

- separate explicit manual-reconciliation eligibility;
- healthy FILLED_PROTECTED lifecycle checks;
- OPEN → CONSISTENT;
- CLOSED → LIFECYCLE_ADVANCED;
- optional closing-transaction enrichment;
- durable linked observations;
- bounded `tradeClosure` result;
- active-runtime busy fence unchanged;
- recovery/new-session safety predicates unchanged.

T001 and T002 should run sequentially because T002 consumes the contracts introduced by
T001.

Avoid parallel workers editing shared reconciliation contracts.

## Acceptance criteria

1. `is_unsafe_paper_attempt()` behavior is unchanged.
2. Existing new-session history classification from the Dogfood 01 remediation is
   unchanged.
3. `FILLED_PROTECTED + NOT_RUN` with a coherent durable Fill may perform explicit
   reconciliation.
4. `FILLED_PROTECTED + CONSISTENT` with a coherent durable Fill may perform explicit
   reconciliation again to observe later lifecycle advancement.
5. `FILLED_PROTECTED + LIFECYCLE_ADVANCED` does not require another normal lifecycle run.
6. Active/busy runtime states still reject explicit reconciliation.
7. Existing unsafe UNKNOWN/incomplete recovery behavior does not regress.
8. Exact attributable OPEN protected Trade returns `CONSISTENT`.
9. OPEN Trade does not produce closure evidence.
10. Exact attributable CLOSED Trade returns `LIFECYCLE_ADVANCED`.
11. `execution_outcome` remains `FILLED_PROTECTED` after natural closure.
12. CLOSED identity continues to use the existing documented `initialUnits` rule rather
    than current zero units.
13. CLOSED Trade aggregate preserves exact close time.
14. CLOSED Trade aggregate preserves exact average close price.
15. CLOSED Trade aggregate preserves exact realized P/L.
16. Financing and dividend adjustment remain separate facts.
17. All closing transaction IDs are preserved deterministically.
18. One closing transaction may be read exactly once for cause enrichment.
19. Exact closing price comes from the matching TradeReduce, not deprecated top-level
    OrderFill price.
20. `TAKE_PROFIT_ORDER` maps to `TAKE_PROFIT`.
21. stop-loss family reasons map to `STOP_LOSS`.
22. explicit market Trade close maps to `MARKET_CLOSE`.
23. margin closeout maps to `MARGIN_CLOSEOUT`.
24. unsupported provider reason maps to `OTHER`.
25. multiple closing transaction IDs map to `MULTIPLE` without transaction fan-out.
26. failed optional cause enrichment maps to `UNRESOLVED` without erasing proven
    `LIFECYCLE_ADVANCED`.
27. unrelated closing transaction/Trade evidence is never attributed to the attempt.
28. Closure evidence is stored only as normalized bounded facts; raw provider payload is not
    persisted.
29. Existing V1 broker observations remain valid.
30. New closure observations are append-only and exact replay remains idempotent.
31. Conflicting closure evidence is not silently overwritten.
32. Reconciliation HTTP response exposes bounded optional `tradeClosure`.
33. Financial values remain decimal strings on the HTTP wire.
34. No account ID, credential, token, or raw payload is exposed by `tradeClosure`.
35. No realized-R or net-P/L claim is introduced.
36. No database migration is introduced.
37. No runtime start or activation behavior changes.
38. No Risk behavior changes.
39. No Strategy methodology changes.
40. No broker mutation path is invoked during reconciliation.
41. No automatic polling/reconciliation is introduced.
42. No real Dogfood identifiers are hardcoded in production logic or automated fixtures.

## Required safety matrix

Tests must explicitly cover:

| Execution outcome            | Reconciliation     | Fill              | Explicit reconcile                  |
| ---------------------------- | ------------------ | ----------------- | ----------------------------------- |
| FILLED_PROTECTED             | NOT_RUN            | coherent          | PERFORM                             |
| FILLED_PROTECTED             | CONSISTENT         | coherent          | PERFORM                             |
| FILLED_PROTECTED             | LIFECYCLE_ADVANCED | coherent          | NO-OP                               |
| FILLED_PROTECTED             | UNRESOLVED         | coherent          | existing unsafe behavior            |
| FILLED_PROTECTED             | CONFLICT           | coherent          | existing unsafe behavior            |
| FILLED_PROTECTED             | NOT_RUN            | malformed/missing | FAIL CLOSED                         |
| FILLED_PROTECTION_INCOMPLETE | NOT_RUN            | any               | existing recovery behavior          |
| FILLED_PROTECTION_INCOMPLETE | UNRESOLVED         | any               | existing recovery behavior          |
| FILLED_PROTECTION_INCOMPLETE | LIFECYCLE_ADVANCED | coherent          | existing strict/recovery behavior   |
| UNKNOWN                      | any                | any               | existing recovery behavior          |
| REJECTED                     | safe status        | none              | NO-OP                               |
| CANCELLED                    | safe status        | none              | NO-OP                               |
| null/malformed               | any                | any               | FAIL CLOSED/current strict behavior |

The implementation must not reuse this table as new-session or entry authority.

## Validation plan

### Focused contract/provider tests

```bash
uv run pytest \
  backend/tests/paper/test_persistence_contracts.py \
  backend/tests/integrations/test_oanda_reconciliation.py
```

Prove:

- new immutable closure contract;
- normalized-facts bounds;
- V1 compatibility;
- CLOSED Trade normalization;
- exact Decimal handling;
- one/multiple closing IDs;
- exact close transaction;
- provider reason mapping;
- exact TradeReduce price;
- malformed/mismatched provider evidence.

### Focused reconciliation/runtime tests

```bash
uv run pytest \
  backend/tests/paper/test_reconciliation.py \
  backend/tests/runtime/test_runtime_activation.py \
  backend/tests/runtime/test_runtime_completion_cross_seam.py
```

Prove:

- eligibility matrix;
- OPEN `CONSISTENT`;
- CLOSED `LIFECYCLE_ADVANCED`;
- outcome non-rewrite;
- optional exit attribution;
- cause-read failure behavior;
- durable observation linkage;
- active-runtime busy fence;
- strict recovery/new-session behavior unchanged.

### PAPER API tests

Run the existing PAPER API test surface that owns:

```text
POST /api/v1/paper/activations/{activation_id}/reconcile
```

Prove:

- `tradeClosure = null` when absent;
- exact closure projection when present;
- Decimal strings;
- error redaction;
- no account/credential leakage.

Solo intake should identify the exact current test file(s) before task creation rather than
inventing a duplicate test path.

### Formatting/static checks

At minimum for changed backend files:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
git diff --check
```

If repository-wide Pyright remains known baseline debt, validation must distinguish existing
baseline findings from changed-surface regressions using the repository's established
Critical-workstream method.

### Broad safe backend suite

Because this touches PAPER reconciliation/runtime authority, run the repository's broad safe
backend test suite excluding external/credentialed tests.

At minimum preserve evidence across:

```text
PAPER execution
PAPER persistence
PAPER reconciliation
runtime activation
runtime orchestration
runtime completion cross-seam
OANDA reconciliation normalization
```

No real broker mutation test is authorized.

### Generated frontend contract

If `frontend/lib/api.generated.ts` changes:

- regenerate from the actual current FastAPI OpenAPI contract;
- do not hand-edit generated types;
- run the repository's generated-client freshness check if one exists;
- run the minimum frontend type/build gate necessary to prove the generated contract remains
  valid.

Do not broaden into UI testing.

### PostgreSQL/migration validation

No migration is expected.

Validate current migration head remains unchanged.

If implementation produces a migration:

```text
STOP
return for architecture re-approval
```

rather than silently accepting it.

## Post-merge Dogfood 02 operational acceptance

This is separate from BUILD validation.

Do not use the real Dogfood account during worker implementation tests.

After:

```text
BUILD PASS
VALIDATE PASS
REVIEW PASS
merge approval
GIT END
```

the developer may explicitly run the normal reconciliation endpoint once against the
existing closed Dogfood 02 activation.

The operation may:

- perform existing/new GET-only OANDA reconciliation reads;
- append normalized Atlas observations;
- append one reconciliation run;
- update the existing reconciliation projection.

It may not:

- start runtime;
- create an activation;
- submit/modify/cancel/close a broker order or Trade;
- evaluate Risk for a new entry.

Expected shape is not hardcoded, but for the already observed naturally closed Trade a
successful result should be structurally:

```json
{
  "performed": true,
  "executionOutcome": "FILLED_PROTECTED",
  "reconciliationStatus": "LIFECYCLE_ADVANCED",
  "tradeClosure": {
    "...": "facts determined from OANDA"
  }
}
```

Afterward, verify the activation/status and durable database evidence.

The actual provider result determines:

```text
TAKE_PROFIT
STOP_LOSS
MARKET_CLOSE
MARGIN_CLOSEOUT
OTHER
MULTIPLE
UNRESOLVED
```

Do not assume which one occurred before reading the evidence.

## Explicit non-authorizations

Before developer approval, do not:

```text
GIT START
create tasks
modify application code
modify tests
start atlas-runtime
create PAPER activation
use real OANDA credentials for validation
run another real reconciliation
perform broker mutation
```

During approved BUILD/VALIDATE/REVIEW, use deterministic fake/MockTransport provider
evidence only.

No production code or fixture may encode the real Dogfood:

```text
activation ID
attempt ID
Trade ID
account ID
transaction ID
units
entry price
stop
target
realized result
```

## Approval gate

This is a Critical workstream.

The next action is:

```text
Solo PLAN + ARCHITECTURE intake
```

Solo must validate:

- current base;
- every referenced file/path;
- every referenced class/function/contract;
- test paths;
- generated OpenAPI workflow;
- no expected migration requirement;
- task ownership feasibility;
- PLAN ↔ ARCHITECTURE semantic consistency;
- no material current-main drift.

Solo must not re-plan the workstream.

If intake passes:

```text
developer approval
→ GIT START
→ create T001/T002
→ sequential BUILD
→ VALIDATE
→ REVIEW
```

Any material conflict between current repository reality and the frozen architecture must
return for developer review before implementation.
