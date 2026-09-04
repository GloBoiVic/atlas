# ARCHITECTURE — Dogfood 02 Account Details Position Projection

## Status and authority

This document freezes the Critical workstream's implementation contract for BUILD.
It is based on `PLAN.md`, current `main` at
`b75930f2276f93938e250ea8498ad8affb4f97c5`, the implementation and tests named
below, and the official OANDA REST v20 documentation retrieved on 2026-09-04.
It authorizes no implementation, provider credential use, runtime start, account
change, or broker mutation.

The repair is only the interpretation of the `account.positions` member of one
full OANDA Account Details response. It is not a change to Strategy, Risk,
execution, reconciliation policy, persistence, or the meaning of the separate
`/openPositions` observation.

## Current-main behavior and directly affected seams

- `backend/integrations/oanda/execution_account.py:301-315` performs one
  `GET /v3/accounts/{accountID}`. `_normalize_execution_account` at
  `326-380` normalizes the account summary, `account.trades`, raw
  `account.positions`, and `account.orders`, assigning the summary's
  `last_transaction_id` to every child inventory. It currently calls the strict
  `/openPositions` normalizer for `account.positions` (`345-347`).
- `backend/integrations/oanda/positions.py:229-262` currently treats every
  input record as open. `_normalize_position` and `_normalize_side` at
  `265-308` validate signed units, `unrealizedPL`, and conditional
  `averagePrice`. `OandaPracticeOpenPosition.__post_init__` at `94-124`
  rejects negative long units, positive short units, missing prices on exposed
  sides, and zero/zero positions. `OandaPracticeOpenPositionInventory` at
  `127-161` rejects duplicate instruments, sorts deterministically, and retains
  one transaction ID.
- `backend/integrations/oanda/exposure_projection.py:37-82` accepts only a
  matching EUR/USD Trade/Position view. It returns `FLAT` only when both
  normalized inventories are empty; it rejects absent counterparts, more than
  one Position, opposing Trades, direction/unit disagreement, unsupported
  instruments, and dual-sided/non-nettable Position geometry.
- `backend/integrations/oanda/execution_account.py:89-154` requires one common
  identity and frontier, exact summary-to-inventory counts, a supported GSLO
  mode, and a boolean `hedgingEnabled`. `require_flat_entry_state` at
  `160-181` rejects any nonzero account counts before projection and then
  requires `FLAT`.
- `backend/runtime/orchestration.py:797-940` performs capability proof and a
  full account observation before a fresh activation becomes `RUNNING`.
  Non-flat fresh-bootstrap observations return `BOOTSTRAP_REQUIRES_FLAT`;
  normalization/projection failures are caught as `STARTUP_SAFETY_CHECK_FAILED`.
  `backend/runtime/cycles.py:163-192` projects the snapshot into the bounded
  runtime observation and retains only counts/state/frontier evidence.
- `backend/paper/execution_application.py:188-230` performs a fresh full
  Account Details read and calls `require_flat_entry_state` before P05 Risk or
  any entry mutation. `backend/paper/risk_evaluation.py:293-331` checks
  identity, derived-inventory counts, pending Orders, and the existing exposure
  projection before Risk. `backend/integrations/oanda/reconciliation.py:234-300`
  uses the normalized full snapshot and serializes only its normalized open
  Trades, Positions, and pending Orders.
- Existing tests demonstrate the current boundaries: strict Position behavior
  is in `backend/tests/integrations/test_oanda_positions.py:337-475`, full-read
  and frontier/count behavior is in
  `backend/tests/integrations/test_oanda_execution_capability.py:155-218`,
  projection safety is in
  `backend/tests/integrations/test_oanda_exposure_projection.py:98-305`, and
  the runtime/P05 sequencing is covered by
  `backend/tests/runtime/test_runtime_orchestration.py` and
  `backend/tests/paper/test_execution_composition.py`.

## Provider evidence

These are the governing provider references; provider fields not retained by
Atlas remain outside the typed Atlas contract.

1. [Account Details endpoint — `GET /v3/accounts/{accountID}`](https://developer.oanda.com/rest-live-v20/account-ep/)
   returns one full `Account` representation and a top-level
   `lastTransactionID`. The full representation includes pending Orders, open
   Trades, and open Position representations.
2. [Account definition](https://developer.oanda.com/rest-live-v20/account-df/)
   defines `openPositionCount` as the number of Positions currently open,
   separately from the full `positions` collection, and defines
   `hedgingEnabled` as the account hedging flag.
3. [Position endpoint — `GET /v3/accounts/{accountID}/positions`](https://developer.oanda.com/rest-live-v20/position-ep/)
   explicitly says that the returned Positions cover every instrument that has
   had a position during the lifetime of the Account. Its documented examples
   contain zero-unit long and short sides. This is the relevant meaning of the
   Position representations embedded in Account Details.
4. [Position definition](https://developer.oanda.com/rest-live-v20/position-df/)
   defines signed `PositionSide.units` (positive long-side units and negative
   short-side units), separate `long` and `short` sides, and the pricing/open-
   Trade facts associated with exposed sides.
5. The provider's strict [open Position operation](https://developer.oanda.com/rest-live-v20/position-ep/)
   is a different contract: it promises only currently open Positions. Atlas
   must not feed the lifetime Account Position collection through that
   operation's zero/zero rejection rule, and must not issue that operation as a
   second read to repair this boundary.
6. [OANDA account-state best practices](https://developer.oanda.com/rest-live-v20/best-practices/)
   direct an application to establish a complete, self-consistent Account
   snapshot with Account Details and retain the returned TransactionID for
   subsequent updates. This supports preserving one full-read frontier.
7. [Trade endpoints](https://developer.oanda.com/rest-live-v20/trade-ep/),
   [Trade definition](https://developer.oanda.com/rest-live-v20/trade-df/),
   [Order endpoints](https://developer.oanda.com/rest-live-v20/order-ep/), and
   [Order definition](https://developer.oanda.com/rest-live-v20/order-df/)
   continue to distinguish currently open Trades from pending Orders. Those
   meanings are not changed by this Position projection.

The documentation establishes the lifetime-vs-current distinction and the
signed side facts. It also exposes `hedgingEnabled` as an account-level flag,
but this remediation does not need to derive a new Position-classification rule
from that flag. The demonstrated defect is only that a lifetime Account Position
may be zero/zero while `openPositionCount` is zero.

If both long and short sides are nonzero, Atlas must preserve both sides and must
not net or discard either side. The existing Atlas exposure projection already
rejects dual-sided geometry as unsupported. Keeping that existing boundary is
smaller and safer than introducing a new `hedgingEnabled`-dependent provider
assumption that is unnecessary to repair the demonstrated zero/zero case.

## Frozen projection contract

### New Account Details-only seam

Add one pure provider-normalization seam in
`backend/integrations/oanda/positions.py` (and expose it through the OANDA
package only if needed by the existing import convention):

```text
normalize_oanda_practice_account_position_inventory(
    payload: Mapping[str, Any],
    identity: OandaPracticeAccountIdentity,
) -> OandaPracticeOpenPositionInventory
```

The internal `payload` is the already fetched Account Details collection in the
shape `{"positions": account["positions"], "lastTransactionID": frontier}`.
The helper performs no HTTP and receives the already validated account identity.
It returns the same immutable `OandaPracticeOpenPositionInventory` type consumed
today. A normalization error
is caught by `_normalize_execution_account` and remains an
`OandaPracticeExecutionAccountNormalizationError` at the full-snapshot
boundary.

`normalize_oanda_practice_open_position_inventory` remains the explicitly strict
normalizer for the separate `/openPositions` response. It is not an alias for,
and must not call, the new Account Details helper. The two functions must have
names/docstrings/tests that make the endpoint distinction obvious.

### Exact validation and classification order

The Account Details helper must process the complete raw collection without
returning a partial inventory:

1. Require the validated `OandaPracticeAccountIdentity`, require
   `payload["positions"]` to be a list, and require every element to be an
   object. Missing or non-list collection data is invalid even when
   `openPositionCount` is zero.
2. For each raw item, parse `instrument` with the existing provider instrument
   parser and reject it if invalid. Record the instrument in a raw-record
   duplicate set immediately; a duplicate fails even when both records would
   later be excluded as zero/zero. There is no merge, net, first-wins, or
   last-wins rule.
3. Require both `long` and `short` values to be objects. Parse
   `long["units"]` first and `short["units"]` second with the existing provider
   Decimal parser, and require each result to be finite. Both units must be
   parsed before classification; a malformed short unit cannot be hidden by a
   zero long unit, and a malformed long unit cannot be hidden by a zero short
   unit.
4. Validate the provider signs before classification: `long.units >= 0` and
   `short.units <= 0`. Negative long or positive short units fail closed. Decimal
   negative zero compares as zero and is classified as zero/zero.
5. If and only if both parsed units equal zero, classify the raw Position as
   **closed historical representation** and exclude it from the derived open
   inventory. Do not construct an `OandaPracticeOpenPosition` for it.
6. If at least one parsed unit is nonzero, classify it as **open**. Preserve
   both sides exactly, including the case where both sides are nonzero; do not
   net, select, or discard a side. This helper does not decide whether dual-sided
   geometry is an Atlas-supported financial state.
7. For every nonzero item, apply the existing open Position invariants and
   construct the retained provider facts. The helper may share a lower-level
   parser with the strict helper, but it must not duplicate or weaken those
   invariants. Validate all items before constructing the returned immutable
   inventory.

The supplied transaction ID is the already selected full Account Details
frontier. The resulting inventory constructor still validates that string; it
does not derive a transaction ID from an individual Position.

### Fields by classification

| Raw field                                                                                                                                             | Zero/zero historical item                                        | Nonzero derived open item                                                                                                              |
| ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `instrument`                                                                                                                                          | Required and valid; used for duplicate detection                 | Required and valid                                                                                                                     |
| `long`, `short` objects                                                                                                                               | Both required                                                    | Both required                                                                                                                          |
| `long.units`, `short.units`                                                                                                                           | Both required, finite, parsed before exclusion, and sign-checked | Same                                                                                                                                   |
| Position `unrealizedPL`                                                                                                                               | Not required and not inspected                                   | Required finite Decimal, as today                                                                                                      |
| side `unrealizedPL`                                                                                                                                   | Not required and not inspected                                   | Required finite Decimal for both sides, as today                                                                                       |
| side `averagePrice`                                                                                                                                   | Not required and not inspected, whether absent or present        | Required finite positive Decimal on each exposed side; a zero side may omit it; a supplied zero-side value is still validated as today |
| `tradeIDs`, `pl`, `resettablePL`, `marginUsed`, `financing`, `commission`, `dividendAdjustment`, `guaranteedExecutionFees`, and other provider extras | Irrelevant; not retained or validated                            | Still not retained by the current Atlas type and not required by this change                                                           |

Thus a valid zero/zero historical record needs only the collection/item shape,
valid instrument, both side objects, finite signed units, and the common
Account Details frontier. Ignoring non-exposure fields on an excluded record is
intentional, not a conversion of malformed units into flatness. Current open
Trade authority remains the same Account Details `account.trades` collection
plus `openTradeCount`; this helper does not infer or manufacture Trade exposure
from unretained PositionSide metadata. Any malformed
unit, invalid sign, invalid instrument, duplicate, or malformed required field
on a derived open item remains a hard failure. The strict `/openPositions`
helper continues its current behavior, including validating supplied fields and
rejecting zero/zero with “no exposed side”.

### Full Account Details normalization and count authority

`_normalize_execution_account` must:

1. Normalize identity and summary first. The summary validator remains the
   authority for the top-level/nested transaction-ID equality and for the
   nonnegative integer `openPositionCount`, `openTradeCount`, and
   `pendingOrderCount` fields.
2. Preserve the existing account-level validation of
   `guaranteedStopLossOrderMode` and boolean `hedgingEnabled`. The new Position
   helper does not consume `hedgingEnabled`; no new authority is derived from it.
3. Normalize `account.trades` with the existing open-Trade helper, normalize
   `account.positions` with the new Account Details helper, and normalize
   `account.orders` with the existing pending-Order helper. Each receives the
   same `frontier = summary.last_transaction_id`.
4. Construct the existing snapshot. Its exact coherence check remains the
   final count check: `summary.open_position_count ==
len(derived_open_positions)`, not `len(account.positions)`. The analogous
   Trade and pending Order checks remain unchanged.

Both count mismatch directions are contradictions and fail closed:

- provider count `0`, one or more derived nonzero Positions: fail;
- provider count `1` or greater, but all Account Positions are zero/zero (or
  otherwise derive fewer Positions): fail;
- equal derived count succeeds, subject to every other invariant.

The raw lifetime collection length is never exposed as an account-open count,
never used as an exposure signal, and never substituted for the provider's
`openPositionCount`.

### Dual-sided exposure and Atlas projection

A nonzero Account Position with both long and short sides exposed is retained
exactly. This is necessary to avoid silently deleting broker exposure. The
normalizer does **not** net the sides, add a HEDGED Atlas state, or derive a new
allow/deny rule from `hedgingEnabled`.

The existing Atlas behavior remains authoritative after normalization:

- `project_oanda_practice_eur_usd_exposure_state` still rejects dual-sided
  geometry, opposing Trade directions, missing Trade/Position counterparts,
  unsupported instruments, and unit/direction disagreement. It must receive
  only the derived open inventory.
- `require_flat_entry_state` still rejects nonzero summary counts before it
  attempts projection. Any dual-sided open Position therefore cannot pass a
  flat entry gate.
- `hedgingEnabled` remains a validated account fact on the snapshot, but this
  remediation does not use it to reinterpret or discard Position exposure.
- A single genuine long or short Position remains non-flat and cannot satisfy
  fresh-bootstrap flatness or P05 entry flatness. Unsupported or contradictory
  exposure remains an error, never `FLAT`.

### Trades, Orders, fills, and Order semantics

No Trade or Order contract changes are authorized. Account Details Trades remain
currently open (`OPEN` or `CLOSE_WHEN_TRADEABLE`) and retain their existing IDs,
signed `currentUnits`, prices, times, states, duplicate-ID checks, and
`openTradeCount` check. Account Details Orders remain currently pending and
retain their existing type/state validation, duplicate-ID checks, and
`pendingOrderCount` check. A Position never creates a Trade, and a Trade never
creates a Position.

The domain distinction that an Order request does not prove a Fill remains
unchanged. This read-only repair cannot submit, cancel, amend, protect, retry,
or otherwise mutate an Order or Fill. P05 continues to pass the same normalized
Trade/Position facts to Risk only after the fresh flatness gate.

### One Account Details read and one transaction frontier

There remains exactly one full Account Details GET per invocation of
`OandaPracticeExecutionAccountReader.read` (with only the request layer's
existing bounded retry of that same GET). The implementation must not add a
`/openPositions` GET, a `/positions` GET, or any other position read to avoid
interpreting `account.positions`.

The full response's validated top-level/nested `lastTransactionID` is the one
frontier. The summary, Trade inventory, derived Position inventory, pending
Order inventory, and `OandaPracticeExecutionAccountSnapshot.last_transaction_id`
all carry that exact string. Existing snapshot validation that all child
frontiers equal the snapshot frontier remains in force. No raw child Position
frontier is invented, and no second response is combined with the Account
Details response.

AccountProperties capability proof is still the existing separate read used by
startup/P05 wiring; it is not a replacement for, or an additional Position
observation in, the full Account Details transaction frontier.

### No mutation and no raw-provider leakage

The helper and full normalizer are pure over sanitized mappings. They must not
mutate the caller's payload, reuse it as an output object, retain raw provider
extras, log credentials/provider bodies, or return a partial inventory after a
failed item. Tests use local `httpx.MockTransport`/sanitized captured shapes,
assert GET-only behavior where a reader is exercised, and do not use a live
token or perform POST/PUT/PATCH/DELETE calls.

## Complete A–O decision matrix

The shorthand `P(i, L, S)` means one raw Account Position for instrument `i`
with parsed long and short units `L` and `S`; an open item additionally has the
required finite PL fields and prices. “Fail closed” means no snapshot is
returned and the caller's existing safety behavior applies.

| Case  | Frozen example                                                                                                                                       | Result/evidence required                                                                                                                                                                                                 |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **A** | `openPositionCount=0`, `positions=[]`, no Trades or pending Orders                                                                                   | Pass; derived inventory is empty and exposure projects `FLAT`.                                                                                                                                                           |
| **B** | Count `0`; one historical `P(EUR_USD, 0, 0)` with no PL/price fields                                                                                 | Pass; the record is excluded and derived positions are `[]`.                                                                                                                                                             |
| **C** | Count `0`; several zero/zero records, e.g. EUR/USD and USD/CAD                                                                                       | Pass; every record is validated for shape/instrument/units, all are excluded, derived positions are `[]`.                                                                                                                |
| **D** | Count `1`; one `P(EUR_USD, +100, 0)` with exposed long `averagePrice` and required finite PL fields                                                  | Pass; exactly one retained open Position with long units `100`; matching open Trade facts project `LONG`.                                                                                                                |
| **E** | Count `1`; one `P(EUR_USD, 0, -100)` with exposed short `averagePrice` and required finite PL fields                                                 | Pass; exactly one retained open Position with short units `-100`; matching open Trade facts project `SHORT`.                                                                                                             |
| **F** | Count `0`; one nonzero Position such as `P(EUR_USD, +1, 0)`                                                                                          | Fail closed at full-snapshot count coherence; never treat the count as permission to ignore exposure.                                                                                                                    |
| **G** | Count `1`; every raw Position is zero/zero                                                                                                           | Fail closed because the derived count is `0`, not `1`; never treat historical presence as open exposure.                                                                                                                 |
| **H** | `long.units="not-a-decimal"`, missing units, non-string provider unit, `short.units="NaN"`, or `"Infinity"`                                          | Fail closed; both units are parsed/finite-validated before classification, so malformed exposure facts cannot be excluded as closed.                                                                                     |
| **I** | `long.units="-1"` or `short.units="1"`                                                                                                               | Fail closed for provider sign contradiction, regardless of the other side.                                                                                                                                               |
| **J** | Two raw records with the same instrument, including two zero/zero records or one zero/one open record                                                | Fail closed; duplicate detection is on the raw collection before exclusion, with no merge/net/dedup.                                                                                                                     |
| **K** | Feed a zero/zero Position to `GET /v3/accounts/{accountID}/openPositions` normalization                                                              | Still fail closed with the existing strict `/openPositions` no-exposed-side rule. The strict endpoint helper is unchanged.                                                                                               |
| **L** | Full Account Details: count fields all `0`, no Trades/Orders, one or more historical zero/zero Positions, valid identity/frontier/GSLO/account facts | Pass; derived open Positions are empty, projection is `FLAT`, and `require_flat_entry_state()` succeeds.                                                                                                                 |
| **M** | Fresh-bootstrap Account Details with a genuine matching long/short exposure (or unsupported/dual contradictory geometry)                             | Genuine exposure remains non-flat and startup returns `BOOTSTRAP_REQUIRES_FLAT`; malformed/contradictory normalization or projection remains `STARTUP_SAFETY_CHECK_FAILED`. No Strategy cycle or mutation is authorized. |
| **N** | P05 `prepare` sees a fresh snapshot with a derived open Position, or a pending Order                                                                 | `require_flat_entry_state()` refuses before Risk/ENTRY; the result is the existing bounded refusal and entry mutation call count remains zero. A dual-sided observation is never converted to a flat approval.           |
| **O** | All focused/runtime/P05/reconciliation tests use sanitized fixtures and local MockTransport                                                          | No provider mutation; assert only expected GETs (one full Account Details GET for that reader), no credentialed external call, and no secret/raw body leakage.                                                           |

Boundary examples also required: `-0`/`0` classifies zero/zero after finite sign
validation; a zero side may omit `averagePrice` on an open item; a nonzero side
may not omit it; an invalid supplied `averagePrice` on a nonzero item (or on a
zero side under the strict `/openPositions` helper) fails; and a malformed
zero/zero-only PL/price field is irrelevant to the Account Details exclusion
but must never make malformed units irrelevant.

## Required implementation evidence and tests

BUILD must add focused tests without changing unrelated semantics:

1. **Position helper tests** in
   `backend/tests/integrations/test_oanda_positions.py` (or the smallest
   directly adjacent test module) cover the exact unit parse order/finite
   validation, zero/zero exclusion with minimal fields, multiple historical
   records, positive long, negative short, both-side preservation without
   netting, existing dual-side projection rejection, invalid signs, malformed
   units, duplicates including excluded records, open-only required fields, and
   no input mutation. Existing strict reader tests must remain green, including
   K.
2. **Full Account Details tests** in
   `backend/tests/integrations/test_oanda_execution_capability.py` use a
   sanitized full payload and prove B/C/D/E/F/G, both count mismatch directions,
   common identity/frontier propagation, one request to exactly
   `/v3/accounts/{ACCOUNT_ID}`, and unchanged Trade/Order count normalization.
   They must prove that Account Details no longer calls `/openPositions`.
3. **Projection tests** in
   `backend/tests/integrations/test_oanda_exposure_projection.py` retain the
   empty-inventory `FLAT` case, matching long/short cases, and the existing
   dual-sided rejection. Add/adjust only the fixture path needed to prove that
   only the derived open inventory reaches this pure projection.
4. **Runtime tests** in
   `backend/tests/runtime/test_runtime_orchestration.py` and/or
   `backend/tests/runtime/test_runtime_cycles.py` prove L and M with normalized
   `OandaPracticeExecutionAccountSnapshot` facts: historical zero/zero records
   permit a flat observation/startup, while genuine, unsupported, and
   contradictory exposure remain blocked and do not reserve/evaluate a cycle
   when startup safety fails.
5. **P05 tests** in
   `backend/tests/paper/test_execution_composition.py` (and the existing Risk
   tests where appropriate) pass a snapshot produced from Account Details
   semantics. Prove L reaches the existing read-only Risk path only when flat;
   prove genuine exposure, dual-side exposure, count contradiction, and
   pending Orders refuse before entry mutation. Assert no POST/PUT/PATCH/DELETE
   and zero entry/protection mutation calls.
6. **Reconciliation regression** in
   `backend/tests/integrations/test_oanda_reconciliation.py` proves a full
   Account Details response containing only historical zero/zero Positions
   produces no derived open Positions and `unexpected_exposure=False`, while a
   genuine derived Position remains visible as exposure. Reconciliation must
   serialize the derived inventory only.
7. Run changed-slice Ruff/Pyright and focused tests before the Critical safe
   backend suite. No external credentialed test is required or authorized.

## Explicit non-authorizations

This architecture does not authorize:

- implementation or test edits before developer approval and the later BUILD
  task gate;
- restarting, retrying, reviving, or reusing activation
  `2e3a1e17-38fb-4953-9231-e1d0caf75993`, or creating another activation;
- any credential change, credentialed OANDA call, live/PAPER runtime start,
  broker mutation, manual position repair, or capital exposure;
- weakening the strict `/openPositions` normalizer, treating raw Account
  Position length as open count/exposure, inventing `FLAT`, netting dual-sided
  exposure, discarding a nonzero side, or ignoring malformed exposure facts;
- changes to Strategy/StrategyVersion, Risk policy, Fill/Order semantics,
  runtime cadence/frontier rules, reconciliation design, UI, migrations, or
  schema; or
- a workaround that issues an additional `/openPositions` or `/positions` GET
  instead of interpreting the coherent Account Details snapshot.
