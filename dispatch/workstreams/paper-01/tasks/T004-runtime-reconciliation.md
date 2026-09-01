# T004 — PAPER runtime, local control, and reconciliation

**State:** `DONE` (developer-approved narrow remediation complete; PostgreSQL
evidence concern recorded below)
**Dependency:** T003 `DONE`
**Owner:** BUILD

## Objective

Wire the narrow atlas-runtime PAPER coordinator and loopback control boundary so
explicit START remains distinct from actual RUNNING and every startup/reconnect /
uncertain-submission path reconciles broker truth before exposure.

## Required behavior

- Discover only eligible explicit PAPER Deployments; acquire the Deployment
  session advisory lock and persist heartbeat/health. A second owner is blocked.
- API START durably records desired RUNNING only. Runtime actual RUNNING requires
  account/capability/session provenance, broker connectivity, reconciliation,
  valid restored state/frontier, warm-up, fresh data, and protection gates.
- Implement desired/actual DRAFT, STARTING, RUNNING, PAUSED, STOPPED, FAILED, and
  RECONCILIATION_REQUIRED behavior, including idempotent START, safe PAUSE/STOP,
  and no browser-owned trading loop.
- Poll/compose completed native M15 and post-frontier sparse BID/ASK observations
  in chronological order. Catch-up reconstructs state but never executes stale
  entries. Stale/disconnected/malformed/out-of-order data blocks new exposure.
- Reconcile at startup, START, RESUME, reconnect, uncertain submission, mismatch,
  and explicit local command. Broker truth wins; cursor advances only after
  normalized evidence is durably applied; replay is idempotent.
- Handle found/absent/ambiguous unknown Order, pending Orders, open Trades and
  side-specific Positions, manual drift, missing protection, and broker
  unavailable as frozen fail-closed outcomes.
- Preserve broker-hosted protection across PAUSE, shutdown, restart, and runtime
  loss. Do not invoke mutating OANDA requests in this task's tests or startup.
- Keep the API loopback/local authority boundary and expose no remote control or
  credentials.

## Owned implementation surface

`backend/runtime/`, PAPER API routes/control schemas, reconciliation modules, app
wiring, and focused tests. Do not alter existing historical API behavior.

## Task-level checks

- Mocked coordinator lifecycle, lock conflict, startup ordering, restart,
  reconnect, stale data, and reconciliation matrix tests.
- Local API START/PAUSE/RESUME/STOP contract tests.
- Full non-capital backend test suite, ruff, and pyright on changed modules.

## Completion receipt

**Final state:** `DONE`

### Changed files

- `backend/runtime/coordinator.py` — injected single-owner PAPER lifecycle
  coordinator, explicit desired/actual command handling, startup/reconnect/
  shutdown reconciliation gates, lock/heartbeat seams, fail-closed safety
  transitions, session-policy provenance gate, and chronological M15/M1 cycle
  composition with catch-up entry suppression.
- `backend/runtime/reconciliation.py` — GET-only OANDA account/instrument/quote
  composition into provider-neutral broker facts; open exposure defaults to
  unverified protection and therefore remains blocked.
- `backend/runtime/store.py` — PostgreSQL lifecycle/heartbeat/reconciliation
  store and Deployment-keyed session advisory-lock lease.
- `backend/runtime/main.py` and `backend/runtime/__init__.py` — inert-by-default
  atlas-runtime wiring and public runtime exports; execution transports are not
  composed into startup.
- `backend/api/paper.py`, `backend/api/schemas.py`, and `backend/api/app.py` —
  loopback-protected PAPER control route that durably records desired state only;
  it never claims actual RUNNING or submits broker requests.
- `backend/config.py` — bounded runtime polling configuration.
- `backend/tests/runtime/test_coordinator.py` — lifecycle, lock conflict,
  readiness, reconciliation, STOP safety, policy provenance, and chronological
  catch-up tests.
- `backend/tests/runtime/test_paper_api.py` — local control contract tests for
  desired-state START and invalid commands.

### Checks and evidence

- Targeted runtime/control plus legacy runtime tests: **14 passed**.
- Full non-capital backend suite (`not integration and not external`): **440
  passed, 4 skipped, 88 deselected**; 4 pre-existing unknown-mark warnings.
- Ruff and format checks on changed runtime/API/config/test modules: **passed**.
- Pyright on changed runtime and PAPER API implementation modules: **0 errors,
  0 warnings**.
- `git diff --check`: **passed**.
- Runtime tests use injected fakes only. No credentials, activation, Risk-policy
  change, order submission, or mutating OANDA request was made; the concrete
  runtime broker seam is GET-only.

### Concerns

- PostgreSQL-backed `SqlAlchemyRuntimeStore` and advisory-lock exclusivity remain
  unverified because `ATLAS_TEST_DATABASE_URL` is not configured; migration/DB
  integration tests were not run against PostgreSQL.
- The default runtime intentionally remains fail-closed until a caller supplies
  Strategy state restoration, warm-up, and data-freshness readiness gates. The
  current task does not silently reset state or infer readiness.
- T004 provides conservative read-only broker reconciliation, but transaction
  history-based unknown-Order repair, canonical missed-Fill repair, and detailed
  broker protection retrieval require a later injected OANDA read surface; open,
  pending, stale, ambiguous, or unverified conditions remain
  `RECONCILIATION_REQUIRED` rather than being guessed or retried.
- Existing strict pyright diagnostics in `backend/api/app.py` and legacy schema
  declarations remain outside this task's implementation scope.

## Third approved remediation packet — F-R1/F-R2

Developer approved reopening T004 strictly for the two CRITICAL findings in the
independent rereview. This packet is deliberately narrow. Do not revisit passed
findings, broaden PAPER 01, add PAPER 02 recovery, activate PAPER, change
credentials/Risk policy, or invoke any mutating/capital-capable OANDA request.

### F-R1 — conflicting external Fill identity

At the production Fill-application seam, a deduplication hit on
`external_execution_id` is idempotent only when the existing Fill belongs to the
same canonical Order and immutable provider execution facts agree. At minimum,
require the same Order, executed quantity, external execution/transaction
identity, external Trade identity where present, and no other conflicting
immutable execution facts. A collision must reject/roll back the current
application, never complete the current Order/TradeIntent/handoff, persist or
surface a CRITICAL reconciliation/safety outcome, and block new exposure. Never
repair an identity collision by reassigning an existing Fill.

Required regression: drive the production store seam with a Fill identity already
owned by another Order and prove no cross-attribution, no current-Order
completion, and fail-closed transaction behavior.

### F-R2 — missed entry repair requires current protected broker exposure

Before applying a missed PAPER 01 ENTRY Fill, broker truth must prove all of the
following: exactly one matching current OANDA open Trade; matching external Trade
identity; matching direction; matching full quantity; matching current Position
side/exposure; required broker-hosted stop exists and matches; and required
broker-hosted target exists and matches the expected actual-Fill-derived target
and protection lineage. Only then may the store apply/deduplicate the canonical
Fill, repair Order/Position/Trade projections, persist reconciliation evidence,
advance `lastTransactionID` after durable application, and return `REPAIRED`.

If no matching open Trade exists, the Trade is closed, Position/Trade identity or
quantity conflicts, protection is absent/wrong/ambiguous, or transaction history
is incomplete, return `RECONCILIATION_REQUIRED`, leave the cursor unchanged, and
do not apply the entry Fill. Keep this limited to the PAPER 01 missed-entry path;
do not add general closed-lifecycle reconstruction or PAPER 02 recovery.

Required regressions: entry transaction without an open Trade; missing stop;
missing/wrong target; matching Trade/Position/protection with exactly one repair;
repeated repair without duplicate Fill/projection changes; and cursor advancement
only after successful durable repair.

### Remediation receipt

To be completed by BUILD after implementation and task-level checks. The task may
return to `DONE` only with the changed-file list, focused test evidence, and the
explicit no-mutation/no-activation safety receipt.

## Validation remediation packet — F-01/F-02/F-03/F-05/F-06

- **Classification:** PRODUCT; **severity:** BLOCKER.
- **F-01 issue/fix:** Persisted `RUNNING` is trusted without reacquiring the
  Deployment session advisory lock and reconciling. On every fresh runtime,
  treat persisted `RUNNING` as untrusted: acquire lock, enter `STARTING`, run
  reconciliation/state/freshness gates, and only then set `RUNNING`; no data or
  execution processing without proven ownership. Revalidate persisted-RUNNING,
  second-owner, and restart-before-reconciliation cases.
- **F-02 issue/fix:** Production `_build_coordinator` wires no live data, state
  restore/warm-up, Strategy, Risk, execution, Fill, target/protection, or
  persistence gates. Compose the bounded PAPER vertical slice in the owning
  runtime while retaining fail-closed behavior for missing seams. Revalidate one
  fully mocked end-to-end cycle and startup/restart with no provider mutation.
- **F-03 issue/fix:** A non-zero open broker Trade can be treated as flat when
  position sides are empty. Any non-zero Trade is exposure; compare Trade and
  side facts and classify missing/contradictory facts as
  `RECONCILIATION_REQUIRED`. Revalidate absent/zero/opposing side cases and Risk
  exposure gates.
- **F-05 issue/fix:** Read-only reconciliation lacks transaction/order/trade/
  protection reads, local canonical comparison, cursor replay/gap handling, and
  missed-Fill repair. Add the bounded GET surface and durable comparison/repair;
  preserve UNKNOWN/RECONCILIATION_REQUIRED until normalized evidence is applied
  and protection verified. Revalidate found/absent/ambiguous unknown Order,
  missed Fill, cursor replay/gap, drift, and protection cases.
- **F-06 issue/fix:** Heartbeat/DB failure can leave processing marked RUNNING and
  continue the data processor. Make lease/heartbeat proof a hard precondition for
  every cycle/authorization; on failure stop processing and durably block when
  possible; reacquisition requires full reconciliation. Revalidate failing
  heartbeat, lost lock, cycle, and reacquisition cases.
- **Invalidated evidence:** T004 lifecycle/startup/reconciliation/readiness
  claims and the validation evidence named above.
- **Owner/files:** T004; `backend/runtime/{main,coordinator,reconciliation,store}.py`,
  `backend/domain/broker.py`, OANDA read-only adapter, and focused runtime tests;
  use T001/T002 contracts without broadening PAPER 01.

## Approved remediation authorization

Developer approved reopening T004 for this packet only. F-04 and F-08 remain
closed and must not be reopened unless this remediation directly proves regression.
The circuit-breaker bypass is limited to runtime ownership, production composition,
reconciliation, and heartbeat safety. F-07 session-policy provenance remains
outside this approved remediation. No architecture redesign, PAPER 02 work,
activation, credential/Risk-policy change, or mutating/capital-capable OANDA request
is authorized.

## Second approved remediation packet — F-02/F-05

Developer approved reopening T004 again, strictly for F-02 production PAPER
composition and F-05 durable reconciliation repair/cursor. Passed findings F-01,
F-03, and F-06 remain closed; F-04 and F-08 remain closed; F-07 and F-09 remain
outside this remediation.

### F-02 required outcome

Wire `ProductionPaperComposition` through eligible pending handoff → persisted
TradeIntent → PRE_FLIGHT → fresh executable facts → PRE_SUBMISSION → persisted
`PENDING_SUBMISSION` Order → execution adapter boundary → normalized authoritative
result → canonical Fill application → stop/target protection workflow. Preserve an
activation/capital-capable gate so startup and all non-capital validation cannot
submit to OANDA. Add one mocked end-to-end production-composition test proving the
complete lifecycle without provider mutation; object-presence or no-op callbacks
are insufficient.

### F-05 required outcome

Wire a persistence-backed repair callback into production reconciliation. For clear,
unambiguous broker truth only, deduplicate external transaction/execution identity,
apply a missed confirmed full Fill through canonical Fill application, repair the
Order/Position/Trade projection transactionally, persist reconciliation evidence,
advance `lastTransactionID` only after applicable facts are durably applied, and
verify required broker-hosted protection before resume. Repeated replay must be
idempotent. Cursor gaps, partial/reissued fills, conflicting identity, unattributed
drift, or ambiguous protection remain `RECONCILIATION_REQUIRED` with cursor
unchanged. Do not add generalized PAPER 02 repair machinery.

### Required targeted tests

Unknown Order + clear full Fill → `REPAIRED`; missed Fill replay → exactly one
canonical Fill; repeated reconciliation → no duplicate Fill/projection change;
cursor-after-application ordering; cursor gap/ambiguous evidence blocked with
unchanged cursor; absent/wrong protection blocked; and proof that the production
coordinator receives the repair seam. All provider interactions are mocks/recorded
GET shapes only; no credentials or mutating/capital-capable OANDA request.

## F-01/F-02/F-03/F-05/F-06 remediation completion receipt

**Final state:** `DONE`

### Remediation details

- **F-01 runtime ownership:** persisted `RUNNING` is now untrusted on every fresh
  runtime. The coordinator acquires the Deployment session lock, persists
  `STARTING`/heartbeat, reconciles, evaluates readiness gates, and only then
  persists `RUNNING`. Processing is refused until ownership is proven.
- **F-02 production composition:** `atlas-runtime` now composes the GET-only live
  native M15/M1 source, production Strategy registry/state restoration seam,
  chronological Strategy processor, pure PAPER Risk service, execution mapping
  seam, and post-frontier entry processor. No submit-capable transport is created
  or called during startup; missing authorization remains fail-closed.
- **F-03 broker authority:** normalized open Trade facts are exposure even when
  aggregate position sides are absent. Trade/side direction, quantity, and trade
  identity contradictions require reconciliation; Risk inherits the conservative
  exposure result.
- **F-05 reconciliation:** added GET-only pending-Order/open-Trade/trade-detail and
  transaction-history transport seams, normalized protection/transaction facts,
  local-vs-broker projection comparison, cursor-gap/unknown-order/missed-Fill
  blocking, and an explicit injected repair seam. No ambiguous evidence is
  promoted or blindly retried.
- **F-06 heartbeat/lock safety:** heartbeat and advisory-lock proof are hard cycle
  preconditions. Heartbeat, database, or lock failure clears in-memory ownership,
  durably blocks when possible, and prevents data/entry processing; reacquisition
  still requires reconciliation.
- F-04, F-07, and F-08 were not addressed by this remediation.

### Changed files

- `backend/runtime/coordinator.py`
- `backend/runtime/__init__.py`
- `backend/runtime/main.py`
- `backend/runtime/production.py`
- `backend/runtime/reconciliation.py`
- `backend/runtime/store.py`
- `backend/persistence/lifecycle_locks.py`
- `backend/domain/broker.py`
- `backend/domain/__init__.py`
- `backend/integrations/oanda/normalization.py`
- `backend/integrations/oanda/readonly.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/runtime/test_coordinator.py`
- `backend/tests/runtime/test_production_runtime.py`

### Checks and evidence

- Focused runtime, production-composition, GET-only OANDA, Risk, and runtime
  control tests: **34 passed, 1 warning**.
- Full non-capital backend suite: **456 passed, 4 skipped, 88 deselected, 4
  pre-existing unknown-mark warnings**.
- Ruff on remediation implementation/tests: **passed**.
- Pyright on changed runtime, lock, broker, and OANDA implementation modules:
  **0 errors, 0 warnings**.
- `python -m compileall -q backend`: **passed**; `git diff --check`: **passed**.
- All provider tests used mocked/recorded shapes. No credentials, activation,
  order submission, POST/PUT/PATCH/DELETE, cancel, close, transfer, or other
  capital-capable OANDA request was invoked.

### Concerns

- PostgreSQL-backed migration, ownership, session advisory-lock exclusivity,
  cursor, numeric/UTC, and durable repair evidence remain unverified because
  `ATLAS_TEST_DATABASE_URL` is unset. The four skipped checks are environment
  skips, not observed application failures.
- This remediation does not authorize activation or make a capital-capable
  request. F-04/F-07/F-08 and the separate activation/review gates remain outside
  this receipt.

## Second F-02/F-05 remediation completion receipt

**Final state:** `DONE` for the approved F-02/F-05 reopening only.

### Remediation details

- **F-02 production composition:** the production processor now persists the
  Strategy state, canonical Deployment-owned TradeIntent, and lifecycle-only
  pending handoff together. An explicit `PaperEntryAuthorizer` performs
  PRE_FLIGHT, obtains a second fresh broker read, persists PRE_SUBMISSION with a
  null PAPER target, commits a stable-correlation `PENDING_SUBMISSION` Order,
  calls the injected OANDA execution adapter, applies only a normalized full
  Fill through canonical Fill application, derives the 1.7R target from that
  Fill, attaches it, confirms stop/target protection, and persists the
  stop/target protection projections/events. A terminal or unknown handoff is
  not resubmitted by the live owner; restart recovery remains reconciliation.
  Rejections, unknown/partial/reissued outcomes, and protection failures remain
  fail-closed.
- **Activation boundary:** authorization returns inertly unless an explicit
  capital-action gate and execution transport are both supplied. The production
  runtime builder supplies neither a mutation transport nor activation approval;
  startup, reconciliation, and non-capital validation therefore cannot submit
  to OANDA.
- **F-05 durable repair:** `SqlAlchemyRuntimeStore` now supplies the production
  reconciliation repair seam. It accepts only attributable, unambiguous full
  Fill transactions, rejects partial/reissued/conflicting/gapped evidence,
  deduplicates external execution/transaction identities, repairs Order,
  Position, Trade, intent, and handoff projections transactionally, records
  bounded evidence, verifies broker protection, and advances the account cursor
  only after application. Replays are idempotent; failed protection or cursor
  gaps roll back and remain `RECONCILIATION_REQUIRED`.
- **Read ordering/wiring:** transaction reads use the durable local cursor, the
  reconciler invokes the store repair callback for cursor and projection
  mismatches, and the production coordinator is wired to that callback.

### Changed files

- `backend/runtime/production.py`
- `backend/runtime/store.py`
- `backend/runtime/reconciliation.py`
- `backend/runtime/coordinator.py`
- `backend/runtime/__init__.py`
- `backend/runtime/main.py`
- `backend/tests/runtime/test_production_runtime.py`
- `backend/tests/runtime/test_coordinator.py`

### Checks and evidence

- Focused runtime, persistence, OANDA contract, and Risk tests: **48 passed, 1
  pre-existing Starlette/httpx deprecation warning**.
- Broad non-capital backend run: **460 passed, 75 skipped, 16 setup errors**;
  the setup errors are environment-gated integration tests requiring the
  missing `ATLAS_TEST_DATABASE_URL`.
- Ruff on changed implementation and runtime tests: **passed**.
- Pyright on changed runtime/coordinator/store/reconciliation/main modules: **0
  errors, 0 warnings**.
- `python -m compileall -q backend` and `git diff --check`: **passed**.
- Provider interactions in tests were mocked/recorded. No credentials,
  activation, order submission, or mutating/capital-capable OANDA request was
  made.

### Concerns

- PostgreSQL-backed repair/cursor transactionality, constraints, and advisory
  lock behavior remain environment-unverified because `ATLAS_TEST_DATABASE_URL`
  is unset; the existing PostgreSQL integration skips remain unchanged.
- F-01, F-03, and F-06 remain closed. F-04 and F-08 remain closed. F-07 and F-09
  remain outside this reopening. This receipt does not authorize activation or
  advance PAPER 01 to `READY_TO_ACTIVATE`.

## Third F-R1/F-R2 remediation completion receipt

**Final state:** `DONE` for the approved third remediation packet only.

### Remediation details

- **F-R1 Fill identity:** production execution deduplication now requires the
  existing Fill to belong to the same Order and to match all immutable normalized
  execution facts, including quantity, execution/transaction identity, Trade
  identity, execution facts, and provenance. A collision raises a dedicated
  safety error; the application transaction rolls back, a separate transaction
  persists a CRITICAL identity-conflict event, marks the Deployment
  `RECONCILIATION_REQUIRED`, and leaves the current Order/intent incomplete.
- **F-R2 protected missed-entry repair:** production store repair validates the
  complete candidate set before mutating any projection. It now requires one
  current matching open Trade, matching signed full quantity/direction and
  external Trade identity, one matching Position side, approved PAPER stop and
  actual-Fill-derived target lineage, and exactly one verified matching broker
  protection fact. Unsafe, absent, ambiguous, or incomplete evidence returns
  `RECONCILIATION_REQUIRED` with the cursor and projections unchanged. Cursor
  advancement remains after durable Fill/projection application; replay remains
  idempotent.
- **Regression coverage:** added PostgreSQL production-store-seam tests for
  cross-Order Fill identity collision, absent open Trade, missing protection,
  wrong target, one successful repair, cursor ordering, and repeated repair.

### Changed files

- `backend/integrations/oanda/execution.py`
- `backend/integrations/oanda/__init__.py`
- `backend/runtime/store.py`
- `backend/tests/integration/test_runtime_store_reconciliation.py`

### Checks and evidence

- Focused runtime, OANDA execution, and production store-reconciliation tests:
  **28 passed, 5 skipped, 1 pre-existing warning**. The five new PostgreSQL
  tests were environment-skipped because `ATLAS_TEST_DATABASE_URL` is unset.
- Full non-capital backend suite: **459 passed, 4 skipped, 93 deselected, 4
  pre-existing unknown-mark warnings**.
- Ruff on changed implementation and regression-test modules: **passed**.
- Pyright on changed implementation, export, and regression-test modules: **0
  errors, 0 warnings**.
- `python -m compileall -q` on changed modules and `git diff --check`:
  **passed**.

### Safety receipt and concerns

- No credentials were read or changed; no PAPER activation occurred; no Risk
  policy or branch/history change was made.
- No OANDA provider request was made by the tests or implementation checks. No
  POST/PUT/PATCH/DELETE, cancel, close, transfer, or order-submission request
  was invoked.
- PostgreSQL-backed transaction rollback, constraints, and concurrent identity
  behavior remain environment-unverified until a dedicated `*_test` database is
  supplied. The skipped tests are environment skips, not observed failures.
- This receipt is limited to F-R1/F-R2. Partial/reissued fills, closed-lifecycle
  reconstruction, PAPER 02 recovery, F-07 provenance, F-09 database evidence,
  activation, and `READY_TO_ACTIVATE` remain outside this task.

## T004 design reconciliation — APPROVED FOR FRESH BUILD

This packet freezes the remaining F-R1/F-R2 safety contract after the repeated
implementation failures. The developer has now explicitly approved reopening
this existing task with a fresh BUILD worker/session. Implement only this
packet and the success-fixture correction below. F-07 and F-09 are deliberately
untouched.

### F-R1 — Fill identity and concurrency contract

#### Identity scope and keys

PAPER 01 uses OANDA account-scoped provider identities. Because this slice has one
selected OANDA Practice account and the existing `fills` table has no provider or
account columns, the database keys are global within that table for this slice;
they must not be weakened to deployment-scoped keys. If the schema later carries
provider/account columns, the equivalent keys are `(provider, external_account_id,
identity)`.

The two provider identity keys are:

1. `K_execution = (external_execution_id)`; it is required and non-null for an
   authoritative PAPER full Fill.
2. `K_transaction = (external_transaction_id)`; it is required and non-null for
   an authoritative PAPER full Fill.

Both keys have database uniqueness constraints over non-null values. The existing
`external_execution_id` and `external_transaction_id` unique constraints remain;
`external_trade_id` is not independently unique because several provider Fills
may belong to one Trade in the domain, even though PAPER 01 repairs only one full
entry Fill. `order_id + sequence_number` remains unique.

For every incoming full-fill result, the complete provider identity tuple is:

```text
P = (
  external_order_id,
  external_trade_ids in provider order,
  fill.external_execution_id,
  fill.external_transaction_id,
  fill.external_trade_id,              # nullness is significant
  fill.related_transaction_ids in provider order,
)
```

The complete immutable canonical Fill fact tuple is:

```text
F = (
  canonical_order_id,
  sequence_number,
  quantity,
  execution_price,
  executed_at normalized to UTC,
  fee,
  source_market_bar_id,                # nullness/value is significant
  price_basis,
  executable_reference_price,
  slippage_per_unit,
  slippage_cost,
  external_execution_id,
  external_transaction_id,
  external_trade_id,
  related_transaction_ids in provider order,
)
```

The existing Order provider identity facts are also immutable for this decision
and must agree before any replay is accepted:

```text
O = (
  order.external_order_id,
  tuple(order.external_trade_ids),
  tuple(order.related_transaction_ids),
)
```

`provider_request_id` is diagnostic request provenance, not an execution identity
fact; it must never be used to make two Fills equal or unequal. All other
persisted execution facts are compared exactly, including nullness, Decimal
values, UTC timestamp, source-bar provenance, and ordered related IDs.

#### Idempotent replay versus collision

An incoming authoritative full Fill is **idempotent** only if all of the
following hold:

1. both required keys `K_execution` and `K_transaction` are present;
2. every existing Fill found by either key is the same single database row;
3. that row belongs to the same canonical Order (`existing.order_id == incoming
order.id`) and has the same sequence number; and
4. the complete `P`, `F`, and `O` tuples agree exactly, including external Trade
   identity and every immutable execution/provenance fact.

An existing row found by one key but not the other is not silently completed:
the missing key is a conflicting immutable identity fact. Two rows found by the
two keys, a different Order, a different Trade, a different quantity/price/time,
different related IDs, different source-bar provenance, or any other tuple
mismatch is a **CRITICAL identity collision**. The same applies when the incoming
result-level `P` conflicts with the Order metadata already stored. No existing
Fill may ever be reassigned to the current Order.

Before accepting a replay, compare all tuples before updating Order metadata.
An idempotent replay may return the existing Fill and make no Fill/projection
change; the caller may complete only the already matching current Order path. A
collision must not mark the current Order, TradeIntent, or handoff filled.

#### Database race, rollback, and re-read

Two concurrent applications of the same external execution or transaction
identity are serialized by the database uniqueness constraints. The loser of a
unique-key violation must:

1. roll back the entire application transaction, including Order metadata,
   Fill/projection changes, handoff/intent changes, and cursor advancement;
2. discard the failed SQLAlchemy Session/transaction; it must not continue using
   a session that observed an integrity error;
3. open a fresh transaction and re-read both unique-key owners (with row locks
   where supported), resolving the winner's committed row; and
4. apply the exact idempotent-replay test above. It must never blindly retry the
   insert or repair ownership.

If the fresh read cannot yet observe a committed owner, the application remains
`RECONCILIATION_REQUIRED`/blocked and records a CRITICAL unresolved identity
outcome rather than retrying. If the re-read finds a mismatching owner, it
records a durable CRITICAL identity-collision outcome in a separate clean
transaction, sets the Deployment to `RECONCILIATION_REQUIRED`, and re-raises or
returns the failure. The original transaction remains rolled back. The separate
safety transaction must contain the Deployment, attempted Order ID, both
identity keys, and a sanitized reason, but no secret/provider payload.

#### F-R1 required tests

- same Order plus byte-for-byte/equivalent complete `P`, `F`, and `O` replay is
  idempotent and changes no projection;
- same `external_execution_id` on another Order is a CRITICAL collision with
  rollback and no current Order/intent/handoff completion;
- same execution identity with changed Trade, transaction, quantity, price,
  timestamp, related IDs, or source-bar provenance is a collision;
- same transaction identity with a different execution identity or owner is a
  collision;
- two concurrent inserts of the same execution/transaction identity leave one
  Fill only, with the loser following rollback/re-read and never reassigning it;
- unique-key conflict with no committed owner after the bounded re-read remains
  blocked and does not retry blindly.

### F-R2 — currently open, fully protected Trade contract

The repair seam may consider a missed PAPER 01 ENTRY transaction only when one
coherent, fresh broker read proves the complete current exposure. Local rows and
`protection_verified` alone are never proof.

For PAPER 01, the authoritative current-state fence for one repair attempt is one
OANDA Account Details snapshot. Its `lastTransactionID`, open Trades, Positions,
and pending Orders are treated as the coherent account-state snapshot for that
attempt. Transaction-history reconciliation is evaluated only through that
snapshot's `lastTransactionID`; broker changes occurring after that fence belong
to the next reconciliation cycle rather than being mixed into the current repair.

Any additional provider reads used to obtain detailed protection or transaction
facts must be attributable to that same reconciliation attempt and may not be
used to advance beyond the Account Details snapshot's `lastTransactionID`.

#### Required coherent broker facts

The read must satisfy all of these before any Fill/projection/cursor mutation:

1. `AccountSnapshot.identity.account_id` matches the Deployment's explicit
   account; `fresh is True`; `orders_known`, `trades_known`, and `positions_known`
   are all true; and `observed_at` is timezone-aware UTC, not in the future, and
   no older than the bounded PAPER reconciliation freshness window (two minutes
   for this slice).
2. Transaction history is known and complete. `last_transaction_id` is present,
   ASCII decimal, and is the provider cursor for the same coherent read. If the
   local cursor is behind, every numeric transaction in the required inclusive
   range is present exactly once with no gap, duplicate conflict, or page
   truncation. The candidate transaction's `occurred_at` is UTC, is not after
   the account snapshot `observed_at`, and its numeric identity is at or before
   the broker cursor. Missing/invalid/stale history is immediately
   `RECONCILIATION_REQUIRED` with the local cursor unchanged.
3. There is exactly one open OANDA EUR/USD Trade relevant to the Deployment and
   it is the candidate's matching Trade. No additional, zero-unit, or unattributed
   EUR/USD Trade is tolerated. Its external Trade ID equals the entry transaction's
   `external_trade_id`; its signed `current_units` equals the Order's signed full
   quantity and direction; and `abs(initial_units) == abs(current_units) ==
order.quantity`. This proves full remaining broker exposure, not merely that a
   Trade once opened. Unrelated non-EUR/USD Trades in the selected Practice account
   do not by themselves invalidate this Deployment's reconciliation.
4. There is exactly one open Position side, with the same direction and units as
   that Trade, and its Trade identity set is exactly the one matching external
   Trade ID. An empty, opposing, extra, stale, unknown, or unlinked side is a
   contradiction. The side's units must equal `abs(trade.current_units)` and
   `order.quantity`; no aggregate position value may substitute for this side
   proof.
5. Protection is a current authoritative fact for that exact Trade. The broker
   read must prove exactly one STOP_LOSS Order and exactly one TAKE_PROFIT Order
   linked by `tradeID` to the matching open OANDA Trade, with non-empty distinct
   provider Order IDs and the required prices. OANDA Stop Loss and Take Profit Orders are Trade-scoped and do not carry independent quantity fields; therefore Atlas must not invent or require protection-order quantity fields.

Full protected exposure is proven by the protection Orders' exact `tradeID`
linkage together with the matching Trade's authoritative `current_units` and the
matching Position side. Missing linkage, extra/foreign protection, duplicate
protection, or ambiguous provider Order identity is unknown and blocks repair.

6. The stop price equals the approved PAPER stop from the immutable
   PRE_SUBMISSION Risk/TradeIntent lineage. The target price equals the target
   calculated from the authoritative transaction Fill price, approved stop,
   direction, and immutable target multiple. Both prices, both provider protection Order IDs, their exact Trade linkage, and the Trade ID must match; local protection
   Orders or a local target calculation without provider attachment evidence do
   not satisfy this contract.

The broker read is one evidence bundle: account freshness/cursor, Trade,
Position side, transaction page, and protection details must be obtained from
the same reconciliation observation. A protection fact with no freshness or
attachment provenance is not independently current; it is valid only when the
provider read explicitly binds it to this bundle's `observed_at` and exact Trade
ID.

#### Repair and failure semantics

Only after all required facts pass may the store, in one database transaction,
deduplicate/apply the canonical Fill, repair Order/Position/Trade projections,
mark the linked intent/handoff, persist bounded reconciliation evidence, and
advance `lastTransactionID` after those changes are durably applied. A replay
must pass the same broker proof and exact Fill identity check; it creates no
second Fill, projection, event, or cursor change.

Any absent, stale, unknown, incomplete, extra, or contradictory fact—including
no open Trade, a closed Trade, wrong Trade identity, partial/current-unit
mismatch, missing Position linkage, missing stop/target, missing or wrong
protection-to-Trade linkage, wrong stop/target price or ID, foreign/duplicate
protection, stale observation, cursor absence, cursor gap, or incomplete
transaction page—must:

- return `RECONCILIATION_REQUIRED`;
- leave the transaction cursor unchanged;
- apply no entry Fill and change no Order/Position/Trade/intent/handoff
  projection; and
- leave new exposure blocked, with the safety/reconciliation outcome persisted
  through the normal durable safety path.

The repair seam itself enforces these preconditions; it may not rely on the outer
reconciler having checked freshness, collection-known flags, or protection. This
remains a narrow missed-entry repair rule. It does not reconstruct closed Trades,
infer exits, repair general lifecycle drift, or add PAPER 02 recovery.

#### F-R2 required tests

- entry transaction with no current open Trade: blocked, no Fill, cursor
  unchanged;
- closed Trade, wrong Trade ID, wrong signed/current/full quantity, extra Trade,
  or Position identity/direction/quantity mismatch: blocked;
- missing stop, missing target, missing or wrong Trade linkage,
  wrong price, wrong provider protection Order ID, foreign/duplicate protection,
  or stale/unverified protection: blocked;
- unknown/stale account Trade/Position collections or incomplete transaction
  history: blocked at the repair seam, cursor unchanged;
- matching Trade, Position side, transaction, and complete current protection:
  exactly one canonical repair, projection application, evidence record, and
  cursor advancement after durable application;
- repeated identical repair: no duplicate Fill/projection/event/cursor change.

#### Success fixture correction

The provider-realistic success fixture must use numeric OANDA transaction
identities consistently. Replace `tx-10` with `10` in the transaction's
`external_id`, the Fill's `external_execution_id` and
`external_transaction_id`, `related_transaction_ids`, and any expected cursor
range. Keep the local cursor at `9` and the broker `last_transaction_id` at
`10`; do not weaken production cursor validation to accommodate a synthetic
non-numeric ID.

## Fresh BUILD remediation receipt — F-R1/F-R2

**Final state:** `DONE_WITH_CONCERNS`

### Changed files

- `backend/domain/broker.py` — broker protection facts now retain the coherent
  reconciliation observation binding.
- `backend/integrations/oanda/normalization.py` and
  `backend/runtime/reconciliation.py` — normalized Trade protection is bound to
  the account snapshot observation.
- `backend/integrations/oanda/execution.py` — full-fill application now requires
  both provider identity keys, compares complete immutable Fill and Order provider
  facts before mutation, detects identity collisions across either key, and
  leaves the current Order untouched on collision.
- `backend/runtime/store.py` — production Fill application records CRITICAL
  identity conflicts after rollback, resolves uniqueness races only through a
  fresh locked re-read, and keeps unresolved races blocked. Reconciliation repair
  now validates explicit account/freshness/collection/cursor/history evidence,
  rejects zero/extra/unlinked Trade and Position-side facts, requires current
  bound protection and exact lineage, detects cross-Deployment identity owners,
  and persists confirmed protection projections transactionally. Cursor movement
  remains after durable application.
- `backend/tests/integration/test_runtime_store_reconciliation.py` — corrected
  the provider-realistic success and collision fixtures to numeric OANDA
  transaction identities and current protection observation binding.

### Checks and evidence

- Focused execution/runtime/production tests: **26 passed**.
- Production-store reconciliation suite: **5 skipped** because
  `ATLAS_TEST_DATABASE_URL` is not configured.
- Full non-capital backend suite: **459 passed, 4 skipped, 93 deselected**;
  four pre-existing unknown-mark warnings remain.
- Ruff on changed implementation and regression-test modules: **passed**.
- Pyright on changed implementation modules: **0 errors, 0 warnings**.
- `python -m compileall -q backend`: **passed**; `git diff --check`: **passed**.
- Tests used mocks/recorded facts only. No credentials, activation, order
  submission, or mutating/capital-capable OANDA request was made.

### Concerns

- PostgreSQL-backed identity uniqueness races, transaction rollback, protection
  projection constraints, cursor ordering, and advisory-lock behavior remain
  environment-unverified until a dedicated database whose name ends in `_test`
  is supplied. The five skipped production-store cases are environment skips,
  not observed application failures.
- F-07/F-09, activation, credentials, Risk policy, and PAPER 02 remain outside
  this remediation. No `READY_TO_ACTIVATE` or activation claim is made.

## Approved three-finding remediation packet — fresh BUILD continuation

The developer approved one narrow reopening of the current T004 BUILD worker.
Implement only these three review findings; do not redesign the frozen F-R1/F-R2
contract, revisit passed findings, touch F-07/F-09, add PAPER 02 recovery, alter
Risk policy, use credentials, activate PAPER, or invoke a mutating/capital-capable
OANDA request.

### F-R1 — conflicting provider Order identities (CRITICAL)

- Before producing an authoritative `FULL_FILLED` result, collect every supplied
  provider Order identity from `orderCreateTransaction`,
  `orderFillTransaction.orderID`, payload/order identity copies, and every other
  authoritative response copy.
- All supplied non-null identities must agree. Missing attribution evidence or
  any conflict normalizes to `UNKNOWN`/fail closed; never choose one identity by
  precedence and discard another.
- Add a non-capital regression where create Order ID differs from fill Order ID
  and prove no authoritative Fill reaches canonical application.

### F-R2 — immediate protection confirmation (CRITICAL)

- Preserve/normalize the matching broker Trade's external ID, signed
  `currentUnits`, optional `initialUnits`, open/current state, and
  observation/freshness evidence.
- Before confirmation, require exact Trade identity, correct direction,
  `abs(currentUnits) ==` approved/full Fill quantity, no partial/closed/
  contradictory exposure, and the already-frozen exact Trade-linked stop/target
  IDs/prices. Do not invent protection-order quantity fields.
- Missing, stale, or contradictory Trade exposure must fail closed and never be
  reported as a protected full-fill result. Add the regression with broker
  `currentUnits=5` versus approved/full quantity `1000`.

### F-R1 — canonical Fill provenance (IMPORTANT)

- `fill_model_from_canonical` must persist `source_market_bar_id` exactly,
  including nullness/value.
- Audit that every field in frozen immutable tuple `F` is copied to the
  persistence model before replay/deduplication comparison.
- Add a non-null source-bar replay regression proving first application and
  identical replay agree.

### Completion requirements

Return a complete receipt with changed files, focused tests including all three
regressions, no-mutation/no-activation evidence, and any environment concerns.
The task may return to `DONE` only after implementation and task-level checks.

## Fresh BUILD continuation receipt — three approved findings

**Final state:** `DONE_WITH_CONCERNS`

### Changed files

- `backend/integrations/oanda/execution.py` — all authoritative provider Order ID
  copies are collected and conflicting create/fill identities normalize to
  `UNKNOWN`; protection confirmation now requires an observed OPEN Trade with
  matching signed current and optional initial units, freshness, and exact
  stop/target facts; canonical Fill mapping preserves source-bar provenance.
- `backend/runtime/production.py` — protection confirmation comparison ignores
  only observation timestamps while retaining all broker protection and Trade
  facts.
- `backend/tests/integrations/test_oanda_execution.py` — regressions for
  conflicting provider Order IDs, partial current Trade units, and non-null
  source-bar replay/provenance agreement.
- `backend/tests/runtime/test_production_runtime.py` — provider-realistic
  protection fixture now supplies authoritative Trade state and submitted full
  quantity.

### Checks and evidence

- Focused execution/runtime/production tests: **29 passed**.
- Full non-capital backend suite: **462 passed, 4 skipped, 93 deselected**;
  four pre-existing unknown-mark warnings remain.
- All three approved regressions are covered: conflicting Order identity produces
  no Fill, `currentUnits=5` is rejected for quantity `1000`, and source-bar
  provenance survives canonical mapping and replay comparison.
- Ruff on changed implementation/test modules: **passed**.
- Pyright on changed implementation modules: **0 errors, 0 warnings**.
- No credentials, activation, order submission, or mutating/capital-capable OANDA
  request was made; provider interactions remain mocks/recorded shapes only.

### Concerns

- PostgreSQL-backed uniqueness race/rollback and production-store evidence remain
  environment-unverified because `ATLAS_TEST_DATABASE_URL` is unset; the five
  production-store tests remain skipped.
- F-07/F-09, activation, credentials, Risk policy, and PAPER 02 remain outside
  this approved continuation. No `READY_TO_ACTIVATE` claim is made.
