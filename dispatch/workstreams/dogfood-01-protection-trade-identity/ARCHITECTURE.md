# ARCHITECTURE — Dogfood 01 Protection Trade Identity Remediation

**Workstream:** `dogfood-01-protection-trade-identity`  
**Classification:** Critical  
**Architecture status:** FROZEN FOR RECONCILIATION / DEVELOPER APPROVAL  
**Implementation authorization:** None. No BUILD task is authorized or created.

## 1. Decision and root-cause proof

Two account-scoped OANDA Trade contract defects are proven. Only the first directly
caused the missing Take Profit in Dogfood 01.

| Evidence              | Current-main fact                                                                                                                                                                                                                                                                       | Consequence                                                                                                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Protection matcher    | `backend/integrations/oanda/execution.py::_matches_protection_trade` requires raw `trade["accountID"] == instruction.account.account_id` before the Stop is inspected.                                                                                                                  | A documented real OANDA Trade without that non-contract field cannot reach Stop verification.                                                                                                     |
| Execution reader      | `OandaPracticeEntryReadbackReader.read_trade()` requests `/v3/accounts/{account_id}/trades/{trade_id}` using its configured account and unwraps the provider Trade.                                                                                                                     | Account scope already exists at the request boundary, but it is not represented in the readback protocol and the matcher incorrectly demands it again from the payload.                           |
| Protection fixtures   | Current protection/composition/durable tests synthetically add top-level `accountID` to Trade fixtures.                                                                                                                                                                                 | Green tests do not represent the provider shape that failed in Dogfood 01.                                                                                                                        |
| Dogfood 01            | A later read-only account-scoped GET of Trade `5` returned the exact OPEN EUR/USD Trade, Fill identity, Atlas Trade client ID, and pending GTC Stop at `1.16049`, with no top-level Trade `accountID` and no Take Profit.                                                               | Under current protection code, Trade identity fails before the valid Stop is inspected, producing `STOP_CONFIRMATION_UNPROVEN`, no TAKE_PROFIT claim, no PUT, and `FILLED_PROTECTION_INCOMPLETE`. |
| Reconciliation reader | `backend/integrations/oanda/reconciliation.py::_trade_read` separately requires raw Trade `accountID` for `attributable=True`, even though `_validate_context()` binds the context account to the reader's configured account and `read_trade()` uses the same account-scoped endpoint. | A successful documented real-shape Trade becomes OPEN but unattributable and is consumed as reconciliation conflict. This is a separate proven provider-shape defect.                             |

The official OANDA v20 [Trade definition](https://developer.oanda.com/rest-live-v20/trade-df/)
defines Trade fields including `id`, `instrument`, `price`, `state`, `initialUnits`,
`currentUnits`, `clientExtensions`, and dependent Orders; it does not define top-level
`accountID`. The [specific Trade endpoint](https://developer.oanda.com/rest-live-v20/trade-ep/)
requires `accountID` in the request path and returns the Trade within that Account.

Therefore account identity must remain strict, but proof belongs to the configured
account-scoped request boundary. Atlas must not invent `accountID` in provider payloads
or fixtures merely to satisfy internal checks.

The historical manual reconciliation result
`UNRESOLVED / RECONCILIATION_READ_FAILED` is a different question. Missing raw Trade
`accountID` alone does not raise in the current reconciliation normalizer; on a
successful read it yields unattributable/CONFLICT. The exact historical read exception
or budget event was not persisted and remains unproven. This architecture repairs the
separately proven Trade attribution defect without claiming to explain or rewrite that
historical outcome.

## 2. Frozen execution account-scope contract

### 2.1 Account-bound readback boundary

Do not introduce a new wrapper around every provider Trade mapping. The smallest
trustworthy contract is the existing reader itself:

```text
OandaPracticeEntryReadbackReader
    configured_account_id
    └── GET /v3/accounts/{configured_account_id}/trades/{trade_id}
            └── raw OANDA Trade mapping
```

The execution readback protocols must expose the configured account identity through a
narrow read-only member/property such as:

```text
account_id: str
```

for both the entry and protection Trade readback contracts.

`OandaPracticeEntryReadbackReader` must:

1. validate/bind one OANDA Practice account using the existing OANDA Practice account-ID
   validation semantics;
2. expose that exact configured account as read-only account scope;
3. build only the existing account-scoped paths from that configured account;
4. return the provider Trade mapping unmodified after unwrapping the documented
   `{"trade": Trade}` envelope;
5. never add, merge, or fabricate `accountID` or any other provider field;
6. preserve existing bounded GET behavior: 404 remains `None`; other request/status/
   JSON/normalization failures remain failures to existing fail-closed callers.

A fake or alternate readback implementation used by public-seam tests must also declare
its account scope. A readback whose declared account differs from the immutable
instruction account cannot establish Trade authority.

This is stronger and smaller than relying on a non-contract provider field: production
account proof comes from the configured reader that actually constructs the account-
scoped request.

### 2.2 Exact Trade predicates

For protection and uncertain-entry Trade readback:

1. first require the readback's configured `account_id` to equal
   `instruction.account.account_id`;
2. then apply exact provider Trade checks to the raw Trade mapping.

The protection Trade predicate retains:

- positive Trade `id` equals the Fill's `broker_trade_id`;
- `instrument == "EUR_USD"`;
- `state == "OPEN"`;
- exact `initialUnits == fill.signed_units`;
- exact `currentUnits == fill.signed_units`;
- exact `price == fill.price`;
- mapping `clientExtensions` exists and its `id` exactly equals the immutable Atlas
  Trade client ID.

Top-level Trade `accountID` is not required. If a response unexpectedly supplies it,
its value must equal the already-proven configured account; an explicitly mismatched
value is contradictory and fails closed.

The uncertain-entry `_matches_readback_trade` path must use the same account-bound
reader authority and retain its existing exact Trade/Fill lineage checks. This shared
reader change must not allow an uncertain Fill readback to succeed without configured
account proof, and it must never create a second entry POST.

## 3. Frozen reconciliation account-scope contract

`OandaPracticeReconciliationReader` already has its own account authority boundary:

```text
validated reader _account_id
        +
_validate_context(context.provider_account_id == _account_id)
        +
GET /v3/accounts/{_account_id}/trades/{trade_id}
```

That boundary remains authoritative and unchanged.

For `_trade_read()`:

- missing raw top-level Trade `accountID` is valid provider shape and must not by itself
  make the Trade unattributable;
- if raw Trade `accountID` is unexpectedly supplied, it must equal
  `context.provider_account_id`; an explicit mismatch remains unattributable/conflict;
- preserve positive Trade ID and expected Trade ID matching;
- preserve persisted `context.provider_trade_id` matching when present;
- preserve exact instrument matching;
- preserve exact Atlas Trade client ID matching;
- preserve exact Fill units and Fill price matching when those durable facts are present;
- preserve existing OPEN/CLOSED/UNKNOWN state normalization;
- preserve existing dependent-protection normalization and drift detection.

The provider-neutral `PaperReconciliationCoordinator` is not changed. Its read budget,
status mapping, finding codes, cursor/frontier behavior, persistence, and read-only
authority remain exactly as current main.

This repair does **not** claim that the historical `RECONCILIATION_READ_FAILED` was
caused by missing Trade `accountID`. That historical code still means the bounded read
or provider-read validation raised, or the budget was exhausted without an established
conflict. The exact event remains unknown.

## 4. Strict dependent-order contract

Execution `_observe_protection_order` remains strict and bounded. For exactly one
selected Stop or Target candidate, retain:

- exact `type` (`STOP_LOSS` or `TAKE_PROFIT`);
- exact Trade ID linkage;
- exact Atlas dependent-order client-extension ID;
- exact approved Stop price, or Fill-derived immutable target price;
- `timeInForce == "GTC"`;
- `PENDING` is the only confirmed state; `CANCELLED`, `FILLED`, and `REJECTED` remain
  rejected, and other states remain unknown;
- existing candidate cardinality and malformed-shape checks.

Dependent-order `accountID` remains optional exactly as current execution semantics:
when OANDA supplies it, it must equal the configured account; when OANDA omits it,
absence is not a failure. The existing optional Target `clientTradeID` behavior is also
retained: if supplied, it must equal the Atlas Trade client ID.

The reconciliation adapter's existing dependent-order checks remain unchanged except
for any mechanical fixture adaptation required by the real-shape parent Trade. Do not
invent new reconciliation protection rules in this remediation.

## 5. Ordering, barriers, authority, and fail-closed invariants

The repair changes only provider account-scope proof for Trade detail. The following
current-main invariants are frozen:

1. **Fill authority:** exposure and protection evaluation use broker-confirmed Fill
   facts. Strategy intent, Order intent, or a presumed Trade cannot substitute for Fill.
2. **Immutable methodology and Risk authority:** the persisted StrategyVersion and
   Strategy evaluation remain immutable evidence; Risk remains the sole authority for
   whether and how exposure was sized. Target geometry still comes from the immutable
   Strategy proposal resolved against actual Fill price.
3. **Stop before Target:** the first Trade read proves account scope and exact Trade
   identity, then the exact Stop is confirmed, before target resolution,
   `before_take_profit`, the TAKE_PROFIT claim, or any PUT. A missing, mismatched,
   non-pending, or uncertain Stop authorizes none of those actions. No Stop repair or
   mutation is introduced.
4. **Durable ENTRY barrier:** the ENTRY claim and immutable attempt evidence commit
   before the single entry POST. The runtime owner guard remains immediately before
   broker dispatch. Claim/persistence failure does not permit POST.
5. **Durable TAKE_PROFIT barrier:** after Stop confirmation, the existing callback
   commits the TAKE_PROFIT claim and runtime cycle transition, then re-checks owner
   authority immediately before the one already-authorized PUT. PUT cannot occur
   without that durable claim.
6. **Observation and final proof:** the pre-PUT Trade observation remains unclaimed;
   the mutation response observation is linked to the TAKE_PROFIT claim; the final
   Trade-detail read must prove both exact protections before `FILLED_PROTECTED` is
   persisted. Observation/result persistence failures remain uncertain and fail closed.
7. **One-shot mutation semantics:** no retry, replacement Entry, Stop repair, or second
   Target PUT is added. Existing bounded GET retry behavior is not a mutation retry and
   is unchanged.
8. **Runtime blocking:** `UNKNOWN` or `FILLED_PROTECTION_INCOMPLETE` still blocks the
   cycle and activation with `EXECUTION_UNCERTAIN`, does not resolve the cycle, and
   cannot create a second Trade.
9. **Reconciliation remains observational:** the reconciliation repair changes only
   attribution of a successful account-scoped Trade read. It cannot create, change, or
   repair broker exposure.

## 6. Valid, invalid, and boundary examples

| Case                                                                                                                                                                         | Expected result                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Execution readback account matches instruction; raw Trade has no `accountID`, exact Trade/Fill identity, exact Atlas client ID; Stop has exact identity/price, GTC, PENDING. | Stop `CONFIRMED`; target resolution may proceed to existing TAKE_PROFIT barrier.                    |
| Same valid Trade but raw Trade unexpectedly includes matching `accountID`.                                                                                                   | Valid; supplied identity is consistent with already-proven account scope.                           |
| Execution readback account differs from instruction account.                                                                                                                 | Trade unproven; incomplete, no target claim and no PUT.                                             |
| Raw Trade includes a mismatching `accountID`.                                                                                                                                | Contradictory identity; fail closed.                                                                |
| Raw Trade has mismatched ID, instrument, state, initial/current units, price, missing/mismatched Atlas client ID, malformed client extensions, or non-object response.       | Trade unproven; incomplete, no target authorization.                                                |
| Stop is absent, duplicated/ambiguous, malformed, wrong type/Trade ID/client ID/price, wrong TIF, has mismatching supplied account, or is not PENDING.                        | Stop UNKNOWN or REJECTED as appropriate; no target claim or PUT.                                    |
| Initial exact Trade/Stop passes; Target PUT is rejected, uncertain, or final readback fails/mismatches.                                                                      | Existing `FILLED_PROTECTION_INCOMPLETE`; at most one PUT and no retry.                              |
| Execution Trade GET returns 404 or request/status/JSON failure.                                                                                                              | Existing bounded failure/unknown path; Stop is not proven and no PUT occurs.                        |
| Reconciliation context account matches configured reader and successful real-shape Trade omits `accountID` while exact Trade/Fill identity matches.                          | Trade is attributable; coordinator consumes existing OPEN/protection facts normally.                |
| Same reconciliation Trade includes an explicit mismatching `accountID`.                                                                                                      | Trade is unattributable/conflict; fail closed.                                                      |
| Reconciliation provider read raises or read budget is exhausted without established conflict.                                                                                | Existing `RECONCILIATION_READ_FAILED` semantics remain.                                             |
| ENTRY or TAKE_PROFIT claim/persistence barrier cannot commit, or runtime owner is lost at either fence.                                                                      | No corresponding broker mutation; runtime remains blocked/read-only recovery behavior is unchanged. |

## 7. Directly affected seams and implementation boundaries

Post-approval BUILD may touch only the following narrow seams and directly required
tests:

- `backend/integrations/oanda/execution.py`
  - validated/read-only configured account identity on the shared Trade readback reader;
  - readback protocols;
  - uncertain-entry and protection Trade-account proof;
  - initial/final protection Trade handling;
  - no mutation payload or retry redesign.
- `backend/integrations/oanda/reconciliation.py`
  - only the account-scoped Trade attribution rule for missing/supplied raw
    `accountID`;
  - no provider-neutral coordinator changes.
- `backend/tests/integrations/test_oanda_protection_completion.py`
  - real-shape Trade fixtures without synthetic top-level `accountID`;
  - complete path and account/Trade/Stop negatives.
- `backend/tests/integrations/test_oanda_entry_mutation.py`
  - shared account-bound readback behavior and uncertain-entry identity coverage.
- directly relevant OANDA reconciliation integration/unit tests
  - successful account-scoped real-shape Trade is attributable;
  - explicit contradictory Trade `accountID` fails closed;
  - generic read failure semantics remain.
- `backend/tests/paper/test_execution_composition.py`
  - adapt shared Trade readback fake/account scope and retain composition identity.
- `backend/tests/paper/test_durable_execution.py`
  - real-shape Trade through durable claim/persistence barriers.
- `backend/tests/runtime/test_runtime_completion_cross_seam.py`,
  `backend/tests/runtime/test_runtime_orchestration.py`, and directly relevant activation
  recovery coverage if required
  - retain incomplete-execution blocking, owner fences, and no duplicate mutation.

No persistence model, migration, Strategy, Risk policy, UI, scheduler, general broker
abstraction, activation authority, or credential behavior is in scope.

## 8. Required focused regression evidence

The focused suite must prove behavior at public seams, not private-helper-only tests:

1. A real-shape OANDA `{"trade": ...}` fixture omits top-level Trade `accountID`,
   includes valid `clientExtensions`, `initialUnits`, `currentUnits`, `price`, OPEN
   state, and a pending GTC Stop at the approved price.
2. Execution reader coverage asserts the GET path is
   `/v3/accounts/<configured>/trades/<id>`, exposes the configured account through the
   readback contract, and returns a provider Trade mapping without fabricated fields.
3. Protection completion with the real-shape fixture proves account scope and exact Stop
   before Target, advances to one existing Target PUT, performs the final Trade read,
   and returns `FILLED_PROTECTED` only when both protections are exact. Assert logical
   ordering `GET -> claim barrier -> PUT -> GET` and no Stop PUT.
4. Parameterized execution mismatches cover account-bound reader identity, supplied
   contradictory Trade `accountID`, Trade identity, and Stop identity. Every mismatch
   proves no Target mutation.
5. Uncertain-entry readback retains exact account and Trade attribution and cannot
   convert a wrong-account reader or contradictory Trade into a Fill.
6. Durable evidence asserts ENTRY claim commit precedes Entry POST; Stop observation
   precedes TAKE_PROFIT claim; TAKE_PROFIT claim commit and second owner fence precede
   PUT; mutation/final observations carry correct claim linkage; result persistence
   records Fill and exact protection facts; each claim and mutation occurs once.
7. Durable failure cases retain `FILLED_PROTECTION_INCOMPLETE` for Stop uncertainty,
   Target rejection/uncertainty, final-readback failure, and post-mutation persistence
   failure. Restart/replay proves no second Entry or Target mutation.
8. Runtime evidence retains `EXECUTION_UNCERTAIN`, blocked cycle/activation state, and
   no cycle resolution/new Trade for incomplete or unknown results.
9. Reconciliation reader coverage uses a real-shape accountless Trade with exact
   durable Fill identity and proves `attributable=True`; a supplied mismatching
   `accountID` proves conflict/unattributable.
10. Existing reconciliation tests prove provider exceptions/read-budget exhaustion
    still produce the same `RECONCILIATION_READ_FAILED` semantics. No test may claim the
    historical Dogfood read failure's exact cause has been recovered.

## 9. Historical reconciliation evidence boundary

The persisted Dogfood reconciliation outcome is:

```text
reconciliation_status = UNRESOLVED
reconciliation_block_code = RECONCILIATION_READ_FAILED
```

The exact first reconciliation HTTP response, OANDA `RequestID`, exception detail, and
read-attempt sequence were not retained in the evidence available to this workstream.
The later successful direct GET is not proof that the earlier bounded read was
successful.

Therefore the workstream must preserve this statement:

> The OANDA reconciliation Trade attribution contract was independently wrong for
> documented accountless Trade objects, and this workstream repairs that proven defect.
> The exact cause of Dogfood 01's historical `RECONCILIATION_READ_FAILED` remains
> unknown and is not rewritten as an attribution conflict.

No logging/persistence redesign is authorized solely to recover evidence that no longer
exists. If `RECONCILIATION_READ_FAILED` recurs after this contract repair, capture the
live provider/request diagnostics under a separately approved diagnostic scope before
changing coordinator semantics.

## 10. Safe validation boundary

After explicit developer implementation approval and GIT START:

1. run focused deterministic execution/protection tests;
2. run focused uncertain-entry/shared-readback tests;
3. run focused OANDA reconciliation attribution/read-failure tests;
4. run durable barrier/persistence and runtime-blocking tests;
5. run formatting, lint, and type checks for the changed backend slice;
6. run the appropriate safe backend suite.

Use MockTransport or recorded provider-shape fixtures only. Do not make credentialed
broker mutations, start runtime, create activation, retry Dogfood 01, or authorize the
missing Take Profit.

No persistence/schema change is intended. If BUILD changes persistence or
provider-neutral reconciliation coordinator semantics despite this boundary, stop and
return for architecture re-approval before continuing.
