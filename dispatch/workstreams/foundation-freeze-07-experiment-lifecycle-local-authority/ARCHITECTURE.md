# Foundation Freeze 07 — Experiment Lifecycle & Local Authority Architecture

Status: `FROZEN — implementation authorized`

Role: `ARCHITECT`
Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
Inspected source: `/Users/vike/Desktop/atlas`, branch `main`, base
`e2c186c619b961d296d84da01696920f4349e7f2`

This artifact is the ARCHITECT-owned contract for the Critical freeze. The
architecture is frozen, and implementation authorization has been granted.

## 1. Decision summary

1. Experiment deletion is an explicit application service operation, not an ORM
   relationship cascade and not a database `ON DELETE CASCADE` migration.
2. The service deletes the complete Experiment-owned graph child-first in one
   caller-owned PostgreSQL transaction. Existing `RESTRICT` foreign keys remain
   the final safety net.
3. The transaction retains exactly one minimal append-only
   `experiment_deletion_receipts` row. It is an audit fact, not an Experiment
   tombstone, and receipt insertion failure rolls back the deletion. The receipt
   has no foreign key to a deleted Experiment or DatasetSnapshot.
4. The DatasetSnapshot is deleted in that same transaction only when, after the
   Experiment root is removed, neither an Experiment nor any historical load
   request references it and no historical load request is `PENDING` or
   `RUNNING`. Experiment orphan deletion and historical-load activation are
   serialized by one dedicated PostgreSQL transaction-scoped lifecycle lock so
   a new load cannot become active between the active-load check and deletion
   commit. An active load always preserves the snapshot. Snapshot membership/gap
   rows are owned by the snapshot; canonical market bars and acquisition windows
   are not.
5. One `DELETE` API operation, reached from one human-confirmed detail-page
   workflow, is the only destructive surface. It has stable success, not-found,
   running-conflict, confirmation, authority, and rollback-error semantics.
6. A global ASGI peer guard admits only the actual socket peer when it is an IP
   loopback address; peer authority never comes from Host or forwarding headers.
   A separate local-only Host/`:authority` allowlist is used solely for browser
   DNS-rebinding defense. Its peer resolver is injectable only through the
   application factory/test seam. The supported Atlas Uvicorn entrypoint binds
   loopback and disables proxy-header rewriting.
7. The OANDA capability creates the validated `MarketSpecification` at the
   application composition boundary. `StrategyContext` receives that fact and
   performs only generic shape/instrument/frontier validation; it never imports,
   resolves, or names OANDA.

The initial product remains EUR/USD, OANDA, native M15 MID analysis, sparse
native M1 BID/ASK execution, and USD simulation. No lifecycle decision changes
StrategyVersion immutability, completed Experiment read semantics, or the
current no-lookahead and native-product behavior.

## 2. Experiment ownership graph

The following is the exact current graph. An arrow means the child table holds
the foreign key. A table named in the right-hand column is an owned child only
through the indicated Experiment lineage; references to StrategyVersion,
VenueInstrument, Instrument, or MarketBar are external provenance and are never
deleted by this operation.

| Table                             | FK / lineage                                                                                                                                                                                                | Ownership decision                                                                                 |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `experiments`                     | root                                                                                                                                                                                                        | delete only after every owned child below is gone                                                  |
| `experiment_accounts`             | `experiment_id -> experiments.id`                                                                                                                                                                           | Experiment-owned projection                                                                        |
| `trade_intents`                   | `experiment_id -> experiments.id`                                                                                                                                                                           | Experiment-owned immutable decision facts; also points to external StrategyVersion/VenueInstrument |
| `experiment_proposal_diagnostics` | `experiment_id -> experiments.id`; `trade_intent_id -> trade_intents.id`                                                                                                                                    | owned diagnostic facts; delete before intents                                                      |
| `risk_decisions`                  | `trade_intent_id -> trade_intents.id`                                                                                                                                                                       | owned through its intent; delete before intents                                                    |
| `orders`                          | `experiment_id -> experiments.id`; `trade_intent_id -> trade_intents.id`; `risk_decision_id -> risk_decisions.id`; `parent_entry_order_id -> orders.id`                                                     | owned order graph; self-reference requires descendant-first deletion                               |
| `order_events`                    | `order_id -> orders.id`; optional `source_market_bar_id -> market_bars.id`                                                                                                                                  | owned order history; MarketBar is external                                                         |
| `fills`                           | `order_id -> orders.id`; optional `source_market_bar_id -> market_bars.id`                                                                                                                                  | owned execution facts; MarketBar is external                                                       |
| `positions`                       | `experiment_id -> experiments.id`; `venue_instrument_id -> venue_instruments.id`                                                                                                                            | owned simulated projection; VenueInstrument is external                                            |
| `trades`                          | `experiment_id -> experiments.id`; `trade_intent_id -> trade_intents.id`; `entry_order_id -> orders.id`; optional `exit_order_id -> orders.id`; optional `ambiguity_source_market_bar_id -> market_bars.id` | owned exposure episodes; both order edges must be removed before their orders                      |
| `experiment_equity_points`        | `experiment_id -> experiments.id`; optional source BID/ASK MarketBar edges                                                                                                                                  | owned equity history; MarketBars are external                                                      |
| `experiment_results`              | `experiment_id -> experiments.id`                                                                                                                                                                           | owned terminal result                                                                              |
| `experiment_gap_decisions`        | `experiment_id -> experiments.id`                                                                                                                                                                           | owned gap decisions                                                                                |

The following are deliberately **not** Experiment-owned:

- `strategies`, `strategy_versions`, `instruments`, and `venue_instruments`;
- `market_bars`, including bars referenced by fills, order events, trades, and
  equity points;
- `historical_acquisition_windows`, which record canonical acquisition history;
- `historical_data_load_requests`, including their strategy-version and
  nullable snapshot references;
- `dataset_snapshots` themselves, until the separate orphan check below proves
  that a candidate snapshot has no remaining repository reference.

The snapshot graph is:

```text
experiments.dataset_snapshot_id  ─┐
historical_data_load_requests.snapshot_id ─┤ references dataset_snapshots
                                           │
dataset_snapshots ──< dataset_snapshot_bars ──> market_bars
                  ├─< dataset_snapshot_analytical_bars
                  ├─< dataset_snapshot_execution_observations ──> market_bars
                  └─< dataset_snapshot_gaps
```

Only the four rows on the left side of the snapshot's membership graph and the
snapshot row itself are removable. The two `market_bars` arrows and every
`historical_acquisition_windows` row survive.

## 3. Exact transactional deletion boundary and order

The delete service owns one short transaction. The API performs no network call
and commits only after all deletion stages and the orphan decision succeed.
The service is flush-oriented and does not use a session-wide ORM cascade.

### 3.0 Historical-load lifecycle serialization

Snapshot-row locking protects a known DatasetSnapshot, but it does not prevent a
new historical load request from becoming active after deletion has evaluated
the global active-load predicate.

Freeze 07 therefore uses one dedicated PostgreSQL transaction-scoped lifecycle
serialization lock for this narrow race.

The lock is acquired by:

1. **Experiment deletion**
   - acquire before evaluating whether any historical load request is
     `PENDING` or `RUNNING`;
   - hold through snapshot orphan decision/deletion and transaction commit.

2. **New historical-load activation**
   - acquire before inserting/committing a new `PENDING` historical load request;
   - hold through that activation transaction commit.

3. **Historical-load resume**
   - acquire before changing a FAILED request to `RUNNING`;
   - hold through that activation transaction commit.

Required ordering behavior:

- If load activation acquires the lifecycle lock first, deletion waits. After
  activation commits, deletion observes the PENDING/RUNNING request and preserves
  the snapshot.
- If deletion acquires the lifecycle lock first, new load activation waits until
  deletion commits and then proceeds against the new durable repository state.
- Loads already PENDING/RUNNING remain protected by the existing global
  active-load predicate.

This lifecycle lock does not replace the snapshot-row lock. Existing-snapshot
reference attachment still follows the separately frozen
`snapshot row -> referencing row` order.

The lifecycle primitive is PostgreSQL transaction-scoped and releases
automatically on commit or rollback. No distributed lock, lease, reservation,
candidate snapshot reference, worker coordination, or new persistence lifecycle
is introduced.

### 3.1 Lock and preflight sequence

To make snapshot reference races deterministic, all operations that attach a
snapshot reference must use the same lock order: **snapshot row, then the
referencing row**.

The complete current attachment inventory is deliberately explicit:

- **Experiment creation:** when the configured DatasetSnapshot already exists,
  lock its row `FOR UPDATE` first, then create the new Experiment row that
  references it in the same transaction. A newly created snapshot has no
  existing snapshot row to lock, but the Experiment insert still occurs before
  commit under this boundary.
- **Successful historical-load completion:** lock the existing DatasetSnapshot
  row `FOR UPDATE` first, then lock/re-read the historical load request row and
  attach its `snapshot_id`.
- **FAILED-load snapshot preservation/attachment:** use the same snapshot-first
  order, including the insufficient-warmup path: lock the existing
  DatasetSnapshot row `FOR UPDATE` first, then lock/re-read the load request row
  and attach/preserve its `snapshot_id`.

These are the only attachment paths. A shared helper/repository boundary owns
the ordering; no secondary `session.get`, direct assignment, or completion/failure
shortcut may attach an existing snapshot reference without first taking the
snapshot-row lock. The referencing-row lock is taken after that lock (or the new
referencing row is inserted after it), and the snapshot and referencing-row
changes commit together.

1. In the transaction, read the target Experiment's `dataset_snapshot_id`
   without changing anything. If the Experiment is absent, return `NOT_FOUND`.
2. Lock that `dataset_snapshots` row `FOR UPDATE`. A missing row is an internal
   integrity failure; do not attempt repair.
3. Lock the target `experiments` row `FOR UPDATE`, re-read its status and
   snapshot id, and abort if the row disappeared or its snapshot changed.
4. Accept only `PENDING`, `FAILED`, or `COMPLETED`. If the locked status is
   `RUNNING`, abort with no delete. An unknown status is also a conflict.
5. Collect and lock the root's direct rows and derive the complete owned ID sets:
   target TradeIntents; RiskDecisions whose intent is targeted; target Orders;
   OrderEvents/Fills whose order is targeted; and every directly
   `experiment_id`-owned projection/fact. Capture the receipt fields from the
   locked Experiment, StrategyVersion/Strategy, VenueInstrument/Instrument, and
   snapshot facts before deleting anything.
6. Validate the order-parent graph before the first mutation. Every target
   Order's `parent_entry_order_id` must be null or another target Order, and
   repeatedly following parent links must reach a null root in finite steps.
   Compute descendant depth with a visiting/visited traversal. Reject a
   self-cycle, a multi-node cycle, an external parent, a dangling parent, or any
   graph for which every node cannot receive one finite depth. There is no
   arbitrary depth cap; deepest finite depth is deleted first.
7. Validate all current inbound edges to target TradeIntent, RiskDecision, and
   Order IDs. The only allowable inbound rows are members of the collected graph.
   The complete current edge inventory is:

   - target TradeIntent: `experiment_proposal_diagnostics.trade_intent_id`,
     `risk_decisions.trade_intent_id`, `orders.trade_intent_id`, and
     `trades.trade_intent_id`;
   - target RiskDecision: `orders.risk_decision_id`;
   - target Order: `orders.parent_entry_order_id`, `order_events.order_id`,
     `fills.order_id`, `trades.entry_order_id`, and `trades.exit_order_id`.

   A diagnostic, Order, or Trade with another `experiment_id`, an outside child
   Order, or any other surviving row that points into a target set is an
   ownership conflict. Likewise, each direct diagnostic/Order/Trade must point
   only to the appropriate target intent/risk/order sets. Abort before the first
   mutation with `DELETE_OWNERSHIP_CONFLICT`; never enlarge the deletion set to
   follow a malformed cross-owner edge. A schema-contract test must inventory
   PostgreSQL foreign keys to these three target tables and fail if a later
   migration adds an unclassified inbound edge.

8. Require that no deletion receipt already exists for the still-present target
   Experiment. Such a state is an integrity conflict, not a second receipt or
   permission to overwrite audit history.
9. The snapshot lock blocks compliant Experiment creation and historical-load
   completion from adding a reference while this transaction evaluates the
   orphan predicate. Existing reads may race normally and receive either the
   old complete response or the subsequent `NOT_FOUND` response.

The initial non-locking lookup in step 1 is safe because step 3 is the
authoritative locked read. If a concurrent deletion wins between those steps,
the locked read returns absent and this request is the stable `NOT_FOUND` case.

### 3.2 Child-first delete order

After preflight, execute and flush these stages in this order. Each stage is
explicitly scoped to the collected IDs; row-count assertions may be used to
detect an unexpected concurrent/schema condition.

1. `experiment_gap_decisions`.
2. `experiment_equity_points`.
3. `experiment_results`.
4. `experiment_proposal_diagnostics` (before its `trade_intent_id` parents).
5. `trades` (before both `trade_intent_id` and entry/exit `orders`).
6. `order_events` (before `orders`; source MarketBars are not deletion targets).
7. `fills` (before `orders`; source MarketBars are not deletion targets).
8. `orders` in descending self-reference depth: delete every protected child
   order before its `parent_entry_order_id` parent, then delete root orders.
   The current graph normally has entry orders with STOP_LOSS/TAKE_PROFIT
   children. The algorithm must still handle a deeper valid chain by computing
   descendant depth and issuing deepest-first deletes. If a surviving order
   outside the Experiment points at a target order, preflight aborts rather than
   deleting through that reference.
9. `risk_decisions` (after orders no longer point at them).
10. `trade_intents` (after diagnostics, trades, orders, and risk decisions).
11. `positions`.
12. `experiment_accounts`.
13. `experiments` root.

The order of stages 1–3, 6–7, and 11–12 is not FK-sensitive, but is fixed here
for deterministic implementation and test assertions. No stage may
delete `market_bars`, acquisition windows, Strategies, StrategyVersions,
VenueInstruments, or load requests.

### 3.3 Snapshot orphan cleanup

Before evaluating orphanhood, the deletion transaction must already hold the
historical-load lifecycle serialization lock defined in §3.0.

Still holding the snapshot row lock, after the Experiment root delete:

1. Query `EXISTS (SELECT 1 FROM experiments WHERE dataset_snapshot_id = :id)`.
2. Query `EXISTS (SELECT 1 FROM historical_data_load_requests WHERE snapshot_id = :id)`.
3. Query `EXISTS (SELECT 1 FROM historical_data_load_requests WHERE status IN
('PENDING', 'RUNNING'))`. This is intentionally global and conservative: an
   active load may have created or reused this snapshot while its `snapshot_id`
   attachment is not durable yet.
4. If any of the three predicates exists, leave the snapshot and **all** its
   membership/gap rows unchanged and report `snapshot.deleted = false`.
5. If none exists, explicitly delete, in order,
   `dataset_snapshot_bars`, `dataset_snapshot_analytical_bars`,
   `dataset_snapshot_execution_observations`, `dataset_snapshot_gaps`, then
   `dataset_snapshots`. Report `snapshot.deleted = true`.

The first two existence queries are the complete current repository-reference
set; the implementation must not use a count of only Experiment rows. The third
predicate is an additional active-load safety guard, not a new reference. A
request's `strategy_version_id` does not make it Experiment-owned and is not
changed. This freeze introduces no `candidate_snapshot_id`, lease, reservation,
or change to the meaning or timing of historical-load `snapshot_id`.

The active-load predicate and orphan decision are evaluated while holding both
the candidate snapshot row lock and the lifecycle serialization lock.

The lifecycle lock prevents a new historical load from becoming PENDING or
RUNNING until the deletion transaction commits. The snapshot-row lock separately
serializes existing-snapshot reference attachment.

Consequently:

- an already-active load forces snapshot preservation;
- a new activation that wins the lifecycle lock first becomes visible before
  deletion evaluates orphanhood and therefore forces preservation;
- deletion that wins the lifecycle lock first commits its orphan decision before
  any new load can become active.

Successful completion and FAILED-load snapshot attachment continue to obey the
snapshot-first lock order in §3.1.

### 3.4 Durable deletion audit receipt

After the Experiment root delete and snapshot orphan decision, insert exactly
one row in `experiment_deletion_receipts`, flush it, and only then commit the
transaction. The smallest receipt schema retains scalar operation/audit facts
only:

| Field                                         | Required meaning                                             |
| --------------------------------------------- | ------------------------------------------------------------ |
| `receipt_id`                                  | durable audit/operation identity                             |
| `deleted_experiment_id`                       | ID of the permanently deleted Experiment; unique per receipt |
| `pre_delete_status`                           | locked status immediately before deletion                    |
| `strategy_id`                                 | Strategy identity                                            |
| `strategy_version_id`                         | StrategyVersion identity                                     |
| `strategy_source_fingerprint`                 | source/configuration fingerprint used by the Experiment      |
| `instrument` / `provider`                     | canonical instrument and provider identity                   |
| `trading_period_start` / `trading_period_end` | canonical UTC trading period                                 |
| `deleted_at`                                  | deletion timestamp                                           |
| `dataset_snapshot_id`                         | ID of the snapshot considered by orphan cleanup              |
| `snapshot_deleted`                            | whether this transaction deleted that snapshot               |
| `confirmation_schema_version`                 | version of the exact confirmation contract                   |

The receipt is append-only: the lifecycle service has no update, delete, or
restore operation for it, and its storage contract must prevent mutation after
commit. It has no FK that would prevent deletion of the Experiment or snapshot,
and it stores no label, result, Trade, Order, Fill, account, position, equity,
graph payload, or other deleted-domain data beyond the listed identity facts.
It is not returned as a tombstone: normal reads of the deleted Experiment stay
`NOT_FOUND`, and no restore behavior is introduced.

Receipt insertion failure, including a uniqueness or durability failure, is a
transaction failure. The root delete, snapshot cleanup, and receipt insert all
roll back together; no receipt may describe an uncommitted deletion and no
successful response may be emitted without the receipt.

### 3.5 Rollback and failure semantics

The root delete, every child stage, the orphan check, snapshot-member deletes,
and snapshot delete are one atomic transaction. An injected failure after any
stage, a foreign-key violation, a deadlock/serialization failure, or a database
failure rolls back the entire transaction. The pre-delete Experiment graph,
snapshot graph, and all unrelated data are then observable unchanged. The API
returns `EXPERIMENT_DELETE_FAILED` (500) without database diagnostics and does
not claim success. A retry is a new explicit user action.

The service must not catch a failure, commit completed stages, or silently turn
an unknown transaction outcome into a successful delete. If the client times
out, it refetches; the next durable read is authoritative.

### 3.6 Why explicit deletion, not schema cascades

Schema cascades are rejected for this boundary. A cascade cannot express the
conditional snapshot lifetime (Experiment references **and** historical-load
references), makes it too easy to erase shared immutable provenance, and would
hide the important order self-reference and both Trade order edges. It also
does not provide an application seam for status checks, cross-owner integrity
checks, injected rollback proof, or a useful audit of what the operation chose
not to delete. Keeping `RESTRICT` FKs makes accidental direct deletes fail;
the focused lifecycle service provides the deliberate, reviewed boundary and
the transaction provides atomicity.

## 4. Valid, invalid, and boundary cases

| Case                                                                                                             | Required result                                                                                       |
| ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `PENDING` with only account/position                                                                             | delete root and those projections; orphan-clean snapshot if unreferenced                              |
| `FAILED` with partial intents, diagnostics, orders, or no result                                                 | delete every partial owned row using the same full order                                              |
| `COMPLETED` with result, trades, fills, and equity                                                               | delete explicitly; this is removal, not mutation or rewriting of completed facts                      |
| `RUNNING`, even with no children                                                                                 | `409 EXPERIMENT_RUNNING`; no row or snapshot mutation                                                 |
| two Experiments share one snapshot                                                                               | delete selected Experiment; preserve snapshot and all membership rows                                 |
| only a terminal historical load request still references snapshot                                                | delete selected Experiment; preserve snapshot and membership rows                                     |
| a `PENDING` or `RUNNING` historical load has produced/reused the snapshot but has not yet attached `snapshot_id` | delete selected Experiment; preserve snapshot and membership rows; report `snapshot.deleted = false`  |
| no Experiment and no load request references snapshot                                                            | delete snapshot memberships/gaps and snapshot, never bars/acquisition windows                         |
| canonical bar belongs to a snapshot and is also used by another snapshot                                         | bar and both provenance relationships survive                                                         |
| missing/invalid snapshot FK target                                                                               | integrity failure and rollback; never repair or partially delete                                      |
| descendant edge points to another Experiment                                                                     | ownership conflict and rollback; never delete the other graph                                         |
| request repeats after a successful delete                                                                        | stable `404 NOT_FOUND`, no destructive work                                                           |
| delete races with run transition                                                                                 | locked status decides: RUNNING conflicts; a delete that commits first makes the later run `NOT_FOUND` |
| confirmation says `PENDING`, but locked status is `FAILED` or `COMPLETED`                                        | `409 DELETE_CONFIRMATION_MISMATCH`; no deletion of newly-created result/trading facts                 |
| confirmation says any deletable status, but locked status is `RUNNING`                                           | `409 EXPERIMENT_RUNNING`; no mutation                                                                 |
| failure after deleting children but before root/snapshot                                                         | entire graph is restored by rollback                                                                  |

Completed Experiment reads remain persisted-fact reads. Deleting one Experiment
does not alter a surviving Experiment's result, comparison, metrics, equity,
trade, gap, or provenance response. Reads of the deleted ID return the existing
`NOT_FOUND` semantics; they do not return a tombstone or fabricated empty result.

## 5. API contract

### 5.1 One destructive endpoint

Proposed route:

```http
DELETE /api/v1/experiments/{experiment_id}
Content-Type: application/json
```

The path ID is a machine locator; the confirmation body does not require the
user to type or recognize a UUID. The body is strict and contains the facts the
user saw:

```json
{
  "confirmation": "DELETE",
  "expected": {
    "label": "Experiment · 2026-01-05 → 2026-01-31",
    "status": "PENDING",
    "strategy": "EMA Sweep Confirmation Break v2",
    "instrument": "EUR/USD",
    "provider": "OANDA",
    "analysis": "native M15 MID",
    "tradingPeriod": {
      "start": "2026-01-05T00:00:00Z",
      "end": "2026-01-31T00:00:00Z"
    }
  }
}
```

The server recomputes the expected projection from locked persisted facts and
requires an exact match, including the current status read from the locked
Experiment row, before the first mutation. UTC instants are canonical; display
timezone formatting is never submitted. The confirmation phrase is exact and
case-sensitive. A previously confirmed `PENDING`, `FAILED`, or `COMPLETED`
Experiment whose locked status changes to another deletable status returns
`409 DELETE_CONFIRMATION_MISMATCH`; it cannot use stale confirmation to delete
newly-created result or trading facts. A locked `RUNNING` status always returns
`409 EXPERIMENT_RUNNING`, including when the submitted status is stale.

Proposed successful response:

```http
200 OK
```

```json
{
  "deleted": true,
  "experimentId": "<uuid>",
  "snapshot": { "id": "<uuid>", "deleted": false }
}
```

`snapshot.deleted` tells the client whether the orphan-only cleanup ran; it does
not imply anything about canonical bars. A 200 response is chosen over 204 so
the UI can render the durable cleanup outcome without a second interpretive
request.

All errors use the existing envelope:

```json
{
  "error": { "code": "CODE", "message": "stable human message", "details": {} }
}
```

| HTTP | Code                              | Meaning / mutation guarantee                                             |
| ---: | --------------------------------- | ------------------------------------------------------------------------ |
|  404 | `NOT_FOUND`                       | Experiment is absent, including a repeated delete; no mutation           |
|  409 | `EXPERIMENT_RUNNING`              | locked status is RUNNING; no mutation                                    |
|  409 | `EXPERIMENT_DELETE_STATE_INVALID` | status is not an allowed deletable state; no mutation                    |
|  409 | `DELETE_CONFIRMATION_MISMATCH`    | persisted human facts changed/stale; no mutation                         |
|  409 | `DELETE_OWNERSHIP_CONFLICT`       | cross-owner graph or integrity conflict; rollback/no mutation            |
|  422 | `DELETE_CONFIRMATION_REQUIRED`    | missing or incorrect confirmation shape/phrase; no mutation              |
|  422 | `VALIDATION_ERROR`                | malformed path/body/schema, using the existing validation handler        |
|  403 | `LOCAL_PEER_REQUIRED`             | actual peer or Host/`:authority` is not admitted; request not dispatched |
|  500 | `EXPERIMENT_DELETE_FAILED`        | transaction failed and rolled back; no success claim                     |

Messages are stable and actionable but contain no SQL, credentials, raw
exception, or database diagnostic. An unexpected transaction outcome is not
mapped to 404 or 200.

## 6. UI interaction contract

There is one destructive workflow, on the Experiment detail/status surface. Do
not add a bulk-delete control, generic resource-delete framework, or a delete
button whose only identity is a UUID.

1. For `PENDING`, `FAILED`, and `COMPLETED`, show `Delete Experiment` beside
   the human-readable status, strategy/version, instrument/provider, native
   analysis product, and UTC trading period. For `RUNNING`, hide or disable it
   with the persistent explanation “Running Experiments cannot be deleted.”
2. Clicking it opens a real confirmation dialog. The dialog states that the
   operation is permanent, visibly names the current Experiment status and the
   other facts above, explains that Experiment-owned
   results/decisions/orders/fills/trades/equity are removed, and explains that
   shared DatasetSnapshot data, canonical bars, and acquisition history are
   retained.
3. The user types `DELETE` into a labelled field. The final button is disabled
   until the exact phrase is entered. No UUID is requested.
4. Submit exactly one API request. Disable the dialog controls while pending;
   do not retry automatically.
5. On 200, show a transient success acknowledgement if desired, then navigate to
   `/experiments` and refetch the list. The response's snapshot flag is not
   presented as bar deletion.
6. On 404, show “This Experiment no longer exists” and return to/refetch the
   list; do not claim that this click performed the deletion.
7. On `EXPERIMENT_RUNNING`, close/reload the detail state and show the persistent
   conflict. On confirmation mismatch, including a status transition, refetch
   the detail facts and require a fresh confirmation. On 500 or
   authority/unavailable errors, keep the dialog context and state that deletion
   was not confirmed; no toast is the sole safety record.

Existing completed-result rendering and polling remain unchanged for surviving
Experiments. The API client must preserve structured `ApiError` codes so the UI
does not infer lifecycle state from a status number alone.

## 7. Actual-socket-peer local authority

The application factory installs one global ASGI middleware before routing. It
guards HTTP API requests (and any future HTTP route) while allowing lifespan
startup/shutdown to function. The proposed denial response is the same for
missing, malformed, non-IP, and non-loopback peers, and for a disallowed
Host/`:authority`:

```http
403 Forbidden
Content-Type: application/json
```

```json
{
  "error": {
    "code": "LOCAL_PEER_REQUIRED",
    "message": "Atlas API is available only from the local machine.",
    "details": {}
  }
}
```

The supported Atlas API server entrypoint is Uvicorn with proxy-header
rewriting disabled: use `--no-proxy-headers`, or the programmatic equivalent
`uvicorn.Config(..., proxy_headers=False)`. This is part of the supported server
configuration, not an optional deployment setting. Consequently the
`scope["client"]` value is authoritative for this application only under the
supported entrypoint, where Uvicorn has not rewritten it from proxy headers.
Atlas does not support a proxy deployment or remote access in this freeze.

The scope client remains the primary peer-authority boundary. As a separate
browser DNS-rebinding defense, the middleware also requires the HTTP `Host` (or
HTTP/2 `:authority`) authority to be `localhost` or a numeric loopback IPv4 or
IPv6 literal, ignoring its port. This host check never identifies the peer and
can never make a non-loopback scope client authoritative. A loopback peer with
an arbitrary external hostname is denied. This is neither authentication nor
proxy support.

### 7.1 Peer validation algorithm

1. Read `scope["client"]` for peer authority. Require a tuple/list with a
   non-empty string host in position zero. Do not use Host, `:authority`, or any
   forwarding header to identify the peer.
2. Parse the host with Python's `ipaddress.ip_address`. Reject missing, invalid,
   hostname, Unix-socket, and ambiguous values.
3. Admit IPv4 when `address.is_loopback` is true (`127.0.0.0/8`) and IPv6 when
   `address.is_loopback` is true (`::1`). If an IPv6 address has an
   `ipv4_mapped` address, admit it only when that mapped IPv4 is loopback. Reject
   all other addresses, including private/link-local addresses.
4. Separately parse the effective HTTP `Host` / HTTP/2 `:authority`, ignoring
   only the port. Require `localhost` (case-insensitive) or a numeric IP
   literal whose address is loopback under the same IPv4/IPv6 rules. Reject a
   missing, malformed, external, or DNS-resolvable-but-non-local hostname. If
   both authorities are present, each must pass this allowlist and their
   normalized host portions must agree.
5. Call the downstream ASGI application only when both the scope peer and the
   host authority are admitted. Otherwise return the stable 403 envelope above.

`Forwarded`, `X-Forwarded-For`, `X-Real-IP`, and any similarly named forwarding
header are ignored. A request with a real loopback peer, a local Host, and
spoofed remote forwarding headers is admitted. A request with a real
non-loopback peer and a local or spoofed-loopback Host is denied. A request with
a loopback peer and an external/DNS-rebinding Host is denied.

### 7.2 Test seam

The application factory may accept a keyword-only `peer_address_resolver`
callable for tests; production entrypoint code supplies none, so the default
resolver reads the ASGI scope's actual client tuple. The seam returns the host
string (or `None`) and cannot read request headers. Tests should also exercise a
real local TestClient/ASGI peer where available. The seam is not an environment
variable, HTTP option, or client-provided override.

Required authority examples:

- pass: `127.0.0.1`, `127.42.1.9`, `::1`, and IPv4-mapped loopback;
- deny: `10.0.0.1`, `192.168.1.10`, public IPv4/IPv6, malformed host, missing
  client, Unix socket, and non-loopback mapped IPv4;
- pass: loopback peer with `localhost` or numeric loopback Host/`:authority`;
- pass: loopback peer with local Host and spoofed `Forwarded`,
  `X-Forwarded-For`, and `X-Real-IP` headers;
- deny: loopback peer with an external/DNS-rebinding Host/`:authority`;
- deny: non-loopback peer with local or spoofed-loopback Host/`:authority`.

## 8. Strategy capability composition contract

`MarketSpecification` remains a small immutable domain value containing the
canonical Instrument and calculation facts such as pip size. Its intrinsic
domain validation remains provider-neutral: correct type, positive finite
value, and instrument consistency.

The provider capability owns the stronger validation. For this slice,
`OANDA_CAPABILITY.market_specification(Instrument.EUR_USD)` is called once at
application/runtime composition and returns the validated specification with
pip size `0.0001`. The resulting object is explicitly supplied to every
`StrategyContext` construction, including the Experiment runner and deterministic
test fixtures. The proposed narrow injection shape is:

```python
market = OANDA_CAPABILITY.market_specification(Instrument.EUR_USD)
runner = ExperimentRunner(..., market_specification=market)
context = StrategyContext(
    evaluation_time=frontier,
    instrument=Instrument.EUR_USD,
    bars=completed_m15,
    market=market,
    position=position,
    exposure_allowed=allowed,
)
```

The exact object is composed outside `backend/domain/strategy.py`; no resolver,
provider singleton, import, or fallback lives in `StrategyContext`. A missing
market fact is an input error, not permission to resolve OANDA. A market fact
for another Instrument is rejected. A manually constructed positive but
provider-incompatible pip size is a composition error and must not be used in a
production context; the provider capability is the authority that prevents it.

`StrategyContext` continues to enforce Instrument matching, completed-bar
ordering, UTC evaluation time, no future bars, position type, and exposure
shape. `strategies/contract.py` continues to enforce the registered Strategy's
EUR/USD M15 MID requirements and warm-up. These checks remain generic and
unchanged in meaning.

API read projections may continue to use the fixed OANDA capability at their
application boundary for the current product's pip-size display. That is not a
domain fallback. The reference Strategy still sees only canonical completed
bars and facts; it never sees a broker object or provider lookup. With the
same validated `0.0001` fact, EMA Sweep Confirmation Break v2 decisions,
native M15 analysis, sparse M1 execution, BID/ASK pricing, and no-lookahead
frontiers remain equivalent.

## 9. Required proof and tests before BUILD completion

The later implementation must provide focused deterministic proof for every
contract in this artifact:

### Deletion and retention

- PENDING, FAILED (including every partial graph shape), and COMPLETED deletion;
- RUNNING conflict with an assertion that every row and snapshot member remains;
- explicit FK-order test covering diagnostics, both Trade order edges, fills,
  order events, risk decisions, intent, self-referential protected orders,
  projections, result, gap decisions, and root;
- snapshot orphan deletion when unreferenced;
- shared snapshot retention through a second Experiment;
- retention when only a terminal or active historical load request references
  the snapshot;
- retention when an active `PENDING`/`RUNNING` load has produced or reused the
  snapshot but has not yet durably attached `snapshot_id`;
- canonical `market_bars` and `historical_acquisition_windows` survive every
  deletion case, including membership and execution-source references;
- one receipt is committed for each successful deletion with every listed
  identity field, no deleted graph data, no tombstone/restore behavior, and no
  foreign key to deleted rows;
- receipt insert failure and any post-child/pre-commit failure leave the graph
  and receipt set unchanged;
- cross-owner edge is rejected without mutation;
- injected failure after each deletion stage proves complete transaction
  rollback, including Experiment and snapshot graphs;
- concurrent run/delete and concurrent same-snapshot delete/create/load
  scenarios prove lock order, no orphan race, and no false success;
- lifecycle serialization race where Experiment deletion acquires the lock before
  new PENDING load creation: deletion commits first and the later load proceeds
  only against post-delete durable state;
- lifecycle serialization race where new PENDING load creation acquires the lock
  first: deletion waits, then observes the active load and preserves the snapshot;
- lifecycle serialization race where FAILED -> RUNNING resume acquires the lock
  first: deletion waits, then preserves the snapshot;
- opposite resume/delete ordering where deletion commits first and resume proceeds
  only afterward;
- lock-order proof that lifecycle serialization and the existing
  snapshot-row-first attachment contract cannot deadlock.
- repeated delete is stable 404 and does not invoke a second destructive path;
- surviving completed Experiment detail, result, comparison, equity, trade, gap,
  and metric reads are byte/semantic-equivalent before and after another
  Experiment is deleted.

### API/UI

- strict confirmation body including locked current `status`, exact human facts,
  UTC serialization, and no UUID entry requirement;
- stale deletable-status confirmation returns `DELETE_CONFIRMATION_MISMATCH`,
  while locked `RUNNING` returns `EXPERIMENT_RUNNING`;
- 200 response and `snapshot.deleted` values for orphan/shared cases;
- 404 `NOT_FOUND`, 409 `EXPERIMENT_RUNNING`, stale-facts conflict, malformed
  confirmation, ownership conflict, and rolled-back 500 response envelopes;
- detail-page dialog behavior for all statuses, double-submit prevention,
  refetch/navigation, and structured error rendering;
- no new destructive bulk or generic-resource workflow.

### Authority

- actual scope peers for IPv4, IPv6, mapped IPv4, private/public/non-IP,
  missing/invalid peers;
- loopback peer with local Host/`:authority` passes, including with spoofed
  forwarding headers;
- loopback peer with external/DNS-rebinding Host/`:authority` is denied;
- actual non-loopback peer with local or spoofed-loopback Host/`:authority` is
  denied;
- supported Uvicorn `--no-proxy-headers` configuration proves forwarding-header
  rewriting cannot change the peer decision;
- injected resolver is testable, header-independent, and absent from production
  composition; lifespan/startup remains testable.

### Strategy composition and regression

- static/import guard that `StrategyContext` and generic domain modules do not
  import or resolve OANDA capabilities;
- context requires/safely rejects missing market facts and rejects instrument
  mismatch; capability composition rejects incompatible facts;
- fake/provider-neutral capability fixture can compose a context without the
  domain importing that provider;
- existing Strategy contract tests still prove deterministic EMA v2 behavior,
  completed-only native M15 MID input, no future data, same-bar frontier rules,
  sparse native M1 BID/ASK execution semantics, and identical persisted result
  facts for unchanged inputs.

## 10. Non-goals

- soft delete, trash, restore, archive replacement, tombstones, retention jobs,
  automatic cleanup, or generic destructive-resource infrastructure;
- deletion of Strategies, StrategyVersions, Instruments, VenueInstruments,
  canonical MarketBars, acquisition windows, or historical load requests;
- deletion/cancellation/redesign of RUNNING Experiments;
- changing result methodology, Risk, accounting, ingestion, reconciliation,
  PAPER/LIVE, broker authority, or execution behavior;
- remote access, authentication, authorization, proxy trust, forwarded-header
  semantics, or deployment/network hardening beyond the application peer guard;
- new providers, instruments, timeframes, Strategy frameworks, plugin systems,
  workers, queues, or distributed infrastructure;
- changing completed Experiment immutability/read semantics or native M15/M1
  product boundaries.

## 11. Approved developer decisions and final gate

The five boundary choices are approved as proposed and are now part of this
frozen contract:

1. **Success status/body:** `200` JSON with `snapshot.deleted`.
2. **Peer denial scope/policy:** global pre-routing peer middleware with
   `403 LOCAL_PEER_REQUIRED`; authority is the un-rewritten scope client peer
   under the supported Uvicorn `--no-proxy-headers` configuration.
3. **Composition injection shape:** an explicitly composed immutable
   `MarketSpecification` passed into `ExperimentRunner` and each
   `StrategyContext`; no provider resolver in the domain.
4. **Confirmation strictness:** exact `DELETE` plus exact human-fact projection
   matching, including locked current Experiment status.
5. **Integrity conflict exposure:** `409 DELETE_OWNERSHIP_CONFLICT`, fail-closed
   before mutation.

The final architecture reconciliations are also frozen: the same-transaction
append-only receipt; disabled proxy-header rewriting; the complete
snapshot-first attachment inventory plus conservative active-load orphan guard;
cycle/inbound cross-owner preflight; a dedicated transaction-scoped historical-load lifecycle serialization lock covering new PENDING creation, FAILED -> RUNNING resume, and Experiment snapshot orphan deletion; locked Experiment status in confirmation;
and the secondary local-host authority check. Overall final developer approval
has been granted; PLAN advancement, task creation, Git start, and BUILD
authorization are permitted under the frozen contract.
