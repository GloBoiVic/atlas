# PLAN — Dogfood 01 Protection Trade Identity Remediation

- **Workstream:** `dogfood-01-protection-trade-identity`
- **Classification:** `Critical`
- **Status:** `READY_FOR_USER`
- **Phase:** `READY_FOR_USER`
- **Branch:** `solo/dogfood-01-protection-trade-identity`
- **GIT START:** completed from `main` at `ebb2ed98d52aa28f30870f94fdc77f516cea7742`
- **Base SHA:** `ebb2ed9` (`Close PAPER activation response projection`)
- **Architecture:** required; `ARCHITECTURE.md` is frozen for developer approval
- **Task state:** `T001` — `DONE`; root VALIDATION `PASS`; root REVIEW `FAIL` resolved by
  `R001` BUILD/VALIDATION/REVIEW `DONE`/`PASS`/`PASS`; no unresolved Critical or Important findings
- **Next action:** stop for explicit developer merge approval; do not merge or perform credentialed broker/runtime activity

## Outcome

Repair the demonstrated Dogfood 01 OANDA Practice account-scoped Trade identity defect
so Atlas can recognize a legitimate provider Trade without inventing a top-level
`accountID`, prove the exact Stop Loss, and advance to the existing dependent Take
Profit barrier. Apply the same provider-shape correction to the read-only reconciliation
Trade attribution seam before another dogfood, while preserving the existing one-shot,
non-retrying, fail-closed execution and runtime behavior.

This is remediation of the first controlled OANDA Practice dogfood. It is not PAPER 07,
does not expand PAPER scope, does not authorize a new activation, and does not authorize
any broker mutation or capital-capable operation.

## Dogfood 01 evidence

- **Activation:** `372d645f-4760-4c57-9a8b-7470dcf735a6`
- **Execution attempt:** `9530bab6-fea0-4f86-aa65-bbc9e1f1759a`
- **Strategy/instrument:** Candle Confirmation Break v1, EUR/USD M15
- **Risk:** `riskPerTrade = 0.001`
- Genuine LONG triggered; Risk sized 42,735 units; the ENTRY claim committed.
- OANDA MARKET/FOK entry filled at `1.16273` and created the expected Stop Loss at
  `1.16049`.
- Atlas persisted `FILLED_PROTECTION_INCOMPLETE`, blocked the activation with
  `EXECUTION_UNCERTAIN`, submitted no Take Profit, and created no Take Profit claim.
- Manual reconciliation returned `UNRESOLVED` with
  `RECONCILIATION_READ_FAILED`; no second trade occurred.
- Persisted facts included Fill Trade ID `5`, Fill price `1.16273`, target `null`,
  Stop `UNKNOWN`, and Take Profit `NOT_ATTEMPTED`.
- A later direct read-only GET of account-scoped OANDA Trade `5` returned an OPEN
  EUR/USD Trade with exact initial/current units, Fill price, Atlas Trade client ID,
  and a pending GTC Stop Loss at `1.16049` with the exact Atlas Stop client ID. The
  Trade had no Take Profit.
- The real Trade object contained no top-level `accountID`, matching OANDA's documented
  Trade schema.

## Investigation findings before architecture

### Primary protection identity defect — confirmed

Current `backend/integrations/oanda/execution.py` has
`_matches_protection_trade()` require:

```python
trade.get("accountID") == instruction.account.account_id
```

before Stop verification at `_observe_protection_order()`.

`OandaPracticeEntryReadbackReader.read_trade()` already performs the read against the
configured account-scoped path:

```text
/v3/accounts/{account_id}/trades/{trade_id}
```

and returns the provider Trade object. Current protection tests synthetically insert
top-level `accountID` into Trade fixtures.

The official OANDA v20 Trade definition lists Trade fields such as `id`, `instrument`,
`price`, `state`, units, `clientExtensions`, and dependent Orders, but does not define
top-level `accountID`. The specific Trade endpoint requires `accountID` in the request
path and returns the Trade within that Account.

Sources:

- <https://developer.oanda.com/rest-live-v20/trade-df/>
- <https://developer.oanda.com/rest-live-v20/trade-ep/>

The current implementation, real Dogfood response, and official contract therefore
prove the protection defect. Account identity must remain strict, but its proof belongs
to the configured account-scoped reader/request boundary. The provider Trade mapping
must remain unmodified.

### Reconciliation Trade attribution defect — separately confirmed

Current `backend/integrations/oanda/reconciliation.py` validates that the
`PaperReconciliationContext.provider_account_id` matches the reconciliation reader's
configured account before performing the account-scoped Trade GET. However,
`_trade_read()` separately requires raw:

```python
trade.get("accountID") == context.provider_account_id
```

for `attributable=True`.

A documented real-shape OANDA Trade without top-level `accountID` therefore becomes an
OPEN but unattributable reconciliation read and is consumed as `CONFLICT`, even though
the account identity was already established by the configured account-scoped request.

This is a separate **proven provider-shape defect that must be remediated before another
dogfood**. It does not prove the exact cause of the already persisted
`RECONCILIATION_READ_FAILED`.

### Observed `RECONCILIATION_READ_FAILED` — exact cause remains unproven

`PaperReconciliationCoordinator.reconcile()` assigns
`RECONCILIATION_READ_FAILED` when a bounded provider read/validation raises or the read
budget is exhausted, provided no conflict has already been established. Missing raw
Trade `accountID` alone does not raise in the current reconciliation adapter; on a
successful real-shape Trade read it instead produces unattributable/`CONFLICT`.

Therefore:

- the reconciliation account-scoped Trade attribution defect is proven and in scope;
- the exact transport/status/JSON/normalization/budget event that produced the historical
  Dogfood `RECONCILIATION_READ_FAILED` remains unproven;
- this workstream must not claim that repairing Trade attribution explains or rewrites
  that historical outcome;
- coordinator status mapping and generic read-failure semantics remain unchanged.

## Intended scope for approval

The frozen `ARCHITECTURE.md` defines the smallest implementation contract.

### Execution/protection

- Keep `OandaPracticeEntryReadbackReader` account-scoped and expose its configured
  account identity through the narrow readback contract rather than wrapping or
  fabricating provider payload fields.
- Validate the reader's configured OANDA Practice account using the existing account-ID
  validation semantics.
- Require the readback boundary's configured account to equal the immutable instruction
  account before an uncertain-entry Trade read or protection Trade read can establish
  authority.
- Do not require top-level Trade `accountID`; if OANDA unexpectedly supplies one, an
  explicitly mismatched value remains contradictory.
- Preserve exact Trade identity checks: Trade ID, `EUR_USD`, `OPEN`, exact initial and
  current units, exact Fill price, and exact Atlas Trade client ID.
- Preserve strict Stop checks: `STOP_LOSS`, exact Trade ID, exact Atlas Stop client ID,
  approved Stop price, `GTC`, and `PENDING`; existing optional dependent-order
  `accountID` behavior remains unchanged.
- Preserve Stop-before-Target ordering and the existing dependent Take Profit barrier.

### Reconciliation

- Keep `OandaPracticeReconciliationReader` bound to its validated configured account
  and preserve `_validate_context()` as the account authority gate.
- For an account-scoped Trade response, treat missing raw Trade `accountID` as valid
  provider shape; if a top-level `accountID` is supplied, require it to match the
  configured/context account.
- Preserve all remaining Trade attribution checks: expected Trade ID, persisted Trade
  identity where present, EUR/USD, exact Atlas Trade client ID, Fill units, and Fill
  price.
- Preserve reconciliation protection normalization, coordinator state mapping, read
  budget, persistence, cursor behavior, and all read-only semantics.
- Add no reconciliation mutation, repair, retry, or broader recovery authority.

### Frozen cross-cutting invariants

- Preserve immutable Strategy methodology and Risk authority.
- Preserve durable ENTRY and TAKE_PROFIT mutation barriers.
- Preserve non-retrying broker mutation semantics.
- Preserve ownership fences and fail-closed uncertainty.
- Preserve runtime blocking for `UNKNOWN` or `FILLED_PROTECTION_INCOMPLETE`.
- Preserve historical Dogfood evidence unchanged.

## Out of scope

- PAPER 07, a new PAPER activation, or any expansion of supported provider/instrument
  scope.
- Retrying, repairing, or altering the existing Dogfood entry/Stop/Take Profit state.
- Any OANDA broker mutation, credentialed validation request, runtime start, activation,
  or retry.
- Scheduler/runtime redesign, general broker abstraction, UI work, Strategy changes,
  Risk policy changes, persistence schema/migration changes, or speculative cleanup.
- Changing provider-neutral reconciliation coordinator status mapping to make the
  historical `RECONCILIATION_READ_FAILED` disappear.
- Treating the later direct GET as authorization to submit the missing Take Profit.

## Acceptance criteria for the post-approval BUILD

1. A regression fixture mirrors the real OANDA Trade shape: no synthetic top-level
   Trade `accountID`, valid `clientExtensions`, valid OPEN Trade/Fill identity, and
   valid pending GTC Stop Loss at the approved price.
2. The execution readback contract proves the configured account outside the provider
   Trade mapping. A wrong configured readback account fails closed. The raw Trade
   remains free of fabricated fields.
3. The real-shape Trade passes all remaining exact Trade checks. A supplied mismatching
   top-level Trade `accountID` remains contradictory.
4. Stop is confirmed before target resolution, the TAKE_PROFIT claim, or any PUT. The
   flow may advance to the existing dependent Take Profit barrier and perform at most
   the already-authorized one target mutation. No Stop repair or mutation is introduced.
5. Mismatched Trade ID, instrument, state, units, Fill price, Atlas Trade ID, Stop
   identity, Stop price, time-in-force, state, or supplied contradictory account
   identity remain fail-closed and do not authorize Take Profit.
6. Durable claim/persistence tests prove ENTRY and TAKE_PROFIT barriers, exact Fill and
   protection facts, no duplicate mutation, and unchanged
   `FILLED_PROTECTION_INCOMPLETE` behavior for uncertainty/rejection/final-readback
   failure.
7. Runtime tests prove an uncertain or incomplete execution remains blocked and cannot
   create a second trade; safe recovery behavior is unchanged.
8. A real-shape accountless Trade through `OandaPracticeReconciliationReader` is
   attributable when all actual Trade/Fill identity fields match and the context matches
   the reader's configured account. A supplied mismatching Trade `accountID` remains
   conflict/unattributable.
9. Reconciliation coordinator behavior is unchanged: the provider-shape fix may allow a
   successful real Trade read to be consumed correctly, but generic read exceptions,
   exhausted budgets, conflicts, lifecycle advancement, and unresolved states retain
   their existing semantics.
10. The workstream does not claim to have identified the historical
    `RECONCILIATION_READ_FAILED` transport/normalization cause. That historical evidence
    remains intact.
11. The historical Dogfood remains explainable: entry filled, OANDA Stop existed, Atlas
    failed to prove it under the old execution Trade contract, Take Profit was never
    authorized or submitted, runtime blocked safely, and the later manual reconciliation
    also ended unresolved.

## Validation gates after approval

Run focused deterministic OANDA execution/protection tests first, then the directly
affected durable persistence/barrier, runtime-blocking, and OANDA reconciliation tests.
Use real-shape MockTransport/fixture responses with no synthetic Trade `accountID`.

Then run the appropriate safe backend suite plus formatting/lint/type checks for the
changed slice. No credentialed broker mutation, runtime start, or new activation is
allowed.

No persistence model or migration change is intended. If BUILD changes persistence or
provider-neutral reconciliation state semantics despite this boundary, dedicated
PostgreSQL integration validation and architecture re-approval become mandatory.

## Approval state

Explicit developer implementation approval was granted for the current frozen PLAN and
ARCHITECTURE. GIT START completed on the approved feature branch; implementation remains
bounded by those artifacts.

`T001` is the sole authorized implementation task for this narrow repair. No production or
test changes outside its approved seams are authorized.
