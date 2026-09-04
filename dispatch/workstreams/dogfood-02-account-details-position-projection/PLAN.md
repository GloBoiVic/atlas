# PLAN — Dogfood 02 Account Details Position Projection

## Workstream state

- **Workstream:** `dogfood-02-account-details-position-projection`
- **Classification:** `Critical`
- **Status:** `CLOSED`
- **Phase:** `GIT_END`
- **Base:** `main` at `b75930f2276f93938e250ea8498ad8affb4f97c5` (`Close lifecycle advanced activation fence`)
- **Base SHA:** `b75930f2276f93938e250ea8498ad8affb4f97c5`
- **Branch:** `solo/dogfood-02-account-details-position-projection`
- **Architecture:** `FROZEN`; `ARCHITECTURE.md` is reconciled and approval-ready
- **Task state:** `T001` `DONE`; original validation `PASS`; original review `PASS`
- **Next action:** none; GIT END completed
- **Approval:** developer explicitly approved implementation and merge of the frozen `PLAN.md` and `ARCHITECTURE.md` on 2026-09-04; GIT START and GIT END completed; no activation, runtime, credential, or broker mutation authorized

The ARCHITECT worker independently inspected the current seams, tests, domain/runtime
consumers, and official OANDA documentation. Solo verified the resulting artifact and
reconciled its material decisions into this plan. BUILD, independent VALIDATE, and
independent REVIEW passed before the approved GIT END.

## Outcome

Repair the provider-specific projection of OANDA full Account Details so a valid flat
Practice account with historical zero/zero Account Positions normalizes successfully,
while preserving fail-closed exposure, transaction-frontier, count, Strategy, Risk, PAPER
execution, and provider-read safety.

This is a Critical Dogfood 02 remediation workstream. It is **not PAPER 07**.

The affected semantic boundary is:

```text
OANDA Account Details account.positions
    → provider Account Position interpretation
    → derived currently-open Position subset
    → OandaPracticeOpenPositionInventory
    → EUR/USD financial exposure projection and PAPER gates
```

The repair must retain the existing one full Account Details GET and its single
`lastTransactionID` frontier. It must not replace that coherent snapshot with an additional
`/openPositions` GET merely to avoid interpreting `Account.positions`.

## Incident and immutable authority

Dogfood 02 activation:

```text
2e3a1e17-38fb-4953-9231-e1d0caf75993
```

The activation used the approved Candle Confirmation Break v1 StrategyVersion and exact
approved parameters, including `confirmation_bars = 2`, `stop_buffer_pips = "20"`,
`target_r = "1.5"`, and `risk_per_trade = 0.01`, with `FRESH_BOOTSTRAP` origin.

Its terminal result is permanent incident evidence:

```text
lifecycle_state = BLOCKED
reason = STARTUP_SAFETY_CHECK_FAILED
strategy_state = null
last_frontier_end = null
last_cycle_id = null
execution_outcome = null
reconciliation_status = NOT_RUN
```

No Strategy cycle, Risk decision, execution attempt, mutation claim, or broker mutation
occurred. The activation is not to be restarted or reused. This workstream creates no
activation and does not authorize any provider mutation.

The read-only diagnostics proved:

```text
AccountProperties: configured account matched; non-MT4
Account Details: GET succeeded; Atlas normalization failed
openTradeCount = 0; len(account.trades) = 0
openPositionCount = 0; len(account.positions) = 1
pendingOrderCount = 0; len(account.orders) = 0
account.positions[0] = EUR_USD, long.units = "0", short.units = "0"
```

The current failure is the mismatch between OANDA `Account.positions` lifetime/instrument
representations and the existing strict `/openPositions` normalizer. The current full
snapshot also compares `summary.open_position_count` to the raw normalized list length,
which is not a valid count authority for `Account.positions`.

## Provider contract verified

The official OANDA REST v20 documentation was independently checked on 2026-09-04:

- Account Details: [`GET /v3/accounts/{accountID}`](https://developer.oanda.com/rest-live-v20/account-ep/)
  returns the full Account representation and one `lastTransactionID`.
- Position list: [`GET /v3/accounts/{accountID}/positions`](https://developer.oanda.com/rest-live-v20/position-ep/)
  returns Positions for every instrument that has had a position during the lifetime of
  the Account; the documented response includes zero-unit sides.
- Position schema: [`Position`](https://developer.oanda.com/rest-live-v20/position-df/)
  defines signed `PositionSide.units`, with positive long-side units and negative
  short-side units, plus open-trade and pricing facts for exposed sides.
- Trade and Order endpoints: [`Trade`](https://developer.oanda.com/rest-live-v20/trade-ep/)
  uses open Trades as the default and exposes `/openTrades`; [`Order`](https://developer.oanda.com/rest-live-v20/order-ep/)
  distinguishes pending Orders. These meanings remain unchanged.

The architecture must preserve the explicit distinction between general Account Position
representations and the strict `/openPositions` endpoint, whose endpoint contract promises
only currently open Positions.

## Current-main seams inspected

- `backend/integrations/oanda/execution_account.py` reads one full Account Details payload,
  normalizes summary, Trades, raw `account.positions`, and Orders, then enforces frontier and
  inventory-count coherence. It currently reuses
  `normalize_oanda_practice_open_position_inventory()` for `account.positions`.
- `backend/integrations/oanda/positions.py` correctly rejects zero/zero records in the
  `/openPositions` contract, rejects malformed/non-finite units and invalid signs, requires
  `averagePrice` for exposed sides, and rejects duplicate instruments. Those strict semantics
  must remain intact for `/openPositions`.
- `backend/integrations/oanda/exposure_projection.py` derives only `FLAT`, `LONG`, or `SHORT`
  from matching normalized open Trades and Positions. It rejects unsupported instruments,
  missing counterparts, opposing directions, dual-sided/non-nettable exposure, and unit
  disagreement.
- `backend/runtime/orchestration.py` performs provider capability, full-account observation,
  and the FRESH_BOOTSTRAP flat/pending-Order gate before `RUNNING`; any normalization or
  projection failure remains a startup safety block.
- `backend/runtime/cycles.py` converts the normalized snapshot to a bounded runtime
  observation through the existing exposure projection and retains count/state coherence.
- `backend/paper/execution_application.py` reads the full account snapshot before P05 Risk,
  calls `require_flat_entry_state()`, then passes the same normalized Trades/Positions to
  P05 Risk evaluation. A genuine current exposure must continue to refuse entry.
- `backend/integrations/oanda/reconciliation.py` consumes the normalized full snapshot and
  must continue to report only the derived open Position inventory.

## In scope after approval

- A narrowly scoped Account Details Position-to-open-inventory projection seam, preferably
  in `backend/integrations/oanda/positions.py`, or the smallest safer equivalent discovered
  by ARCHITECT.
- Full Account Details normalization using the derived open subset, with
  `summary.open_position_count == len(derived_open_positions)` required exactly.
- Deterministic sanitized regression fixtures and focused OANDA normalization tests for
  the required validation matrix below.
- Runtime startup and P05 execution-account regression coverage proving that historical
  zero/zero Positions can pass flatness while genuine exposure remains blocked.
- Any narrowly required shared helper extraction that leaves `/openPositions` semantics
  strict and obvious.
- Changed-slice Ruff/Pyright and the appropriate Critical safe backend validation suite.

## Explicitly out of scope

- PAPER 07; Strategy methodology or StrategyVersion changes; Risk policy changes; runtime
  redesign; scheduler; UI; migrations/schema; reconciliation redesign; Dogfood 01 changes.
- Restarting, retrying, reviving, or reusing activation
  `2e3a1e17-38fb-4953-9231-e1d0caf75993`.
- Creating another PAPER activation, fresh or otherwise, during this workstream.
- Any credential change, credentialed OANDA call for BUILD/VALIDATE/REVIEW, broker mutation,
  manual position repair, live/PAPER runtime start, or account-state mutation.
- Treating raw `len(account.positions)` as open exposure, inventing `FLAT` from the mere
  presence of a Position object, ignoring malformed exposure facts, weakening count checks,
  adding a workaround `/openPositions` GET, or generic OANDA refactoring.

## Frozen acceptance direction

`ARCHITECTURE.md` freezes the following implementation shape and safety decisions:

- Add a separate pure Account Details helper for `account.positions`; do not alter or call
  the strict `/openPositions` normalizer for this collection.
- Parse and sign-check both `long.units` and `short.units` before classifying a record.
  Require only the collection/item shape, valid instrument, both side objects, and finite
  signed units for a zero/zero historical record; do not require irrelevant Position/side
  P&L or pricing fields once it is excluded.
- Exclude exactly zero/zero records. For nonzero records, preserve both sides and apply all
  existing open-position invariants. Do not add a new `hedgingEnabled`-dependent
  classification rule in this remediation: if both sides are nonzero, retain both sides
  without netting and let the existing Atlas exposure projection reject the unsupported
  dual-sided geometry. `hedgingEnabled` remains a validated account fact, not new Position
  authority for this slice.
- Keep duplicate detection over the raw collection, including records later excluded.
  Require `openPositionCount == len(derived_open_positions)` exactly; never use raw list
  length as open count or exposure.
- Preserve the single full Account Details GET and its validated frontier for every child
  inventory. Trades remain currently-open Trades, Orders remain currently-pending Orders,
  and exposure projection receives only the derived open Position inventory.
- Keep runtime startup, `require_flat_entry_state()`, P05, and reconciliation fail-closed
  behavior unchanged apart from allowing the valid historical zero/zero flat case to reach
  those existing gates.

The approved implementation must demonstrate all of the following:

1. `Account.positions` is interpreted according to OANDA's general Account Position
   semantics, not `/openPositions` semantics.
2. Every Account Position's `long.units` and `short.units` are parsed as finite provider
   decimals before open/closed classification; invalid units fail closed.
3. `long.units == 0` **and** `short.units == 0` excludes that historical Position from the
   open inventory. At least one nonzero side enters the open inventory and still satisfies
   the existing open-position invariants.
4. Negative long units and positive short units fail closed; no malformed or contradictory
   exposure-determining fact is silently ignored.
5. Duplicate instrument records fail closed unless ARCHITECTURE.md proves an official,
   repository-compatible alternative interpretation.
6. The derived open Position count, not raw Account Position list length, must equal
   `Account.openPositionCount` exactly. Count contradictions fail closed in both directions.
7. Trades remain currently-open Trades and Orders remain currently-pending Orders; their
   count checks and normalization behavior do not change.
8. Exposure projection receives only the derived open Position inventory. A flat snapshot
   with no open Trades, zero derived open Positions, no pending Orders, and valid frontier
   projects to `FLAT` and passes `require_flat_entry_state()`.
9. Genuine long/short exposure, including unsupported or contradictory exposure, remains
   non-flat or fails closed and blocks FRESH_BOOTSTRAP startup and P05 entry preflight.
10. The single full Account Details read and one transaction frontier are preserved.
11. `normalize_oanda_practice_open_position_inventory()` remains strict: a zero/zero record
    received from `/openPositions` still fails closed.
12. Tests perform no provider mutation and use only sanitized captured provider shape.

## Required validation matrix

The post-approval implementation and evidence must cover at least:

| Case                                                         | Expected result                                                                                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| A. `openPositionCount=0`, `Account.positions=[]`             | PASS / `FLAT`                                                                                                                   |
| B. Flat with one historical zero/zero EUR_USD Position       | PASS / derived open positions `[]`                                                                                              |
| C. Flat with multiple historical zero/zero Positions         | PASS / derived open positions `[]`                                                                                              |
| D. One genuine long (`long > 0`, `short = 0`) and count `1`  | PASS / one open Position                                                                                                        |
| E. One genuine short (`long = 0`, `short < 0`) and count `1` | PASS / one open Position                                                                                                        |
| F. Count `0` but one derived nonzero Position                | FAIL CLOSED                                                                                                                     |
| G. Count `1` but every Account Position is zero/zero         | FAIL CLOSED                                                                                                                     |
| H. Malformed long or short units                             | FAIL CLOSED                                                                                                                     |
| I. Invalid signs (`long < 0` or `short > 0`)                 | FAIL CLOSED                                                                                                                     |
| J. Duplicate instrument records                              | FAIL CLOSED unless architecture proves otherwise                                                                                |
| K. `/openPositions` receives zero/zero Position              | Still FAIL CLOSED                                                                                                               |
| L. Flat full snapshot with historical zero/zero Position     | `require_flat_entry_state()` succeeds only with zero open Trades, derived open Positions, pending Orders, and `FLAT` projection |
| M. Genuine exposure                                          | FRESH_BOOTSTRAP startup remains blocked                                                                                         |
| N. P05 preflight                                             | Corrected full Account Details semantics still refuse exposure/pending Orders before ENTRY                                      |
| O. Tests                                                     | No provider mutation                                                                                                            |

## Architecture questions for ARCHITECT

`ARCHITECTURE.md` must freeze, with repository and provider evidence:

- The exact Account Position projection/helper seam and its separation from `/openPositions`.
- Which fields are validated for zero/zero historical Positions before exclusion, and which
  open-position-only fields are intentionally not required for excluded records.
- How both-side nonzero exposure is preserved without netting and then rejected by the
  existing Atlas dual-sided exposure projection, without inventing a new
  `hedgingEnabled`-dependent provider rule in this slice.
- Count authority and contradiction behavior, including both count mismatch directions.
- How the one full Account Details frontier is retained and propagated.
- The direct runtime and P05 regression evidence required to prove no safety gate weakened.

## Dogfood authority after closure

After this remediation closes, the operational sequence is strictly:

1. Re-run the normalized full Account Details read.
2. Verify the current OANDA Practice account is flat through current read-only evidence.
3. Obtain a fresh explicit Dogfood 02 approval.
4. Create a brand-new `FRESH_BOOTSTRAP` activation.

Those actions are not authorized by this planning workstream and must not occur before a
separate explicit approval.
