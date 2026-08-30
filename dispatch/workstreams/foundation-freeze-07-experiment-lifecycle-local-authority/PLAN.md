# Foundation Freeze 07 — Experiment Lifecycle & Local Authority

## Outcome

Freeze the smallest trustworthy ownership and authority boundaries before the
pre-PAPER audit:

1. permanently hard-delete a non-running Experiment and its owned graph in one
   transaction, including partial FAILED graphs, while atomically retaining one
   minimal append-only destructive-action audit receipt;
2. remove a DatasetSnapshot and its membership/gap rows only when no Experiment
   or historical load request references it and no PENDING or RUNNING historical
   load request exists, while preserving canonical market bars and acquisition
   history;
3. expose one explicit, human-confirmed destructive Experiment workflow with
   stable not-found, repeated-delete, and RUNNING-conflict semantics;
4. enforce loopback-only API access from the actual socket peer, with a
   local-only Host / HTTP `:authority` check against DNS rebinding, and with
   proxy-header rewriting disabled in the supported Atlas server entrypoint;
   and
5. move provider capability resolution out of the generic StrategyContext seam,
   preserving the current EUR/USD, M15, and M1 behavior.

## Classification

`Critical`

## Status and approval gate

- Status: `READY_FOR_USER — merge approval required`
- Architecture status: `FROZEN`
- GIT START: complete on the dedicated Freeze 07 branch.
- BUILD: authorized; tasks are recorded below and dispatched sequentially.
- Validation is now authorized; review remains gated until `VALIDATION.md` is `PASS`.

## Repository state and base

- Inspected branch: `solo/foundation-freeze-07-experiment-lifecycle-local-authority`
- Requested base SHA: `e2c186c619b961d296d84da01696920f4349e7f2`
- `git log` confirms this SHA is the current `main` tip.
- Pre-existing untracked paths: `.codegraph/` and `frontend/.env.local`; preserve
  and exclude from any later workstream changes.
- `dispatch/ACTIVE.md` points to this workstream. GIT START created the dedicated
  branch; no commit, merge, or push has been performed.

## Exploration findings

### Experiment graph

- `experiments` owns rows in `experiment_accounts`, `trade_intents`,
  `experiment_proposal_diagnostics`, `positions`, `trades`,
  `experiment_equity_points`, `experiment_results`, and
  `experiment_gap_decisions` through `ON DELETE RESTRICT` foreign keys.
- `orders` also has a direct Experiment foreign key and is referenced by
  `order_events`, `fills`, and self-referential protection/order-parent links.
- `risk_decisions` belongs to an intent; `orders` reference both the intent and
  risk decision. `trades` reference an intent and entry/exit orders. Delete
  ordering therefore cannot be delegated to an undifferentiated parent delete.
- All current foreign keys use `RESTRICT`, making ownership visible but leaving
  no lifecycle deletion service today.

### Snapshot and historical-data graph

- `experiments.dataset_snapshot_id` references `dataset_snapshots` with
  `RESTRICT`.
- Snapshot-owned rows are `dataset_snapshot_bars`,
  `dataset_snapshot_analytical_bars`, `dataset_snapshot_execution_observations`,
  and `dataset_snapshot_gaps`.
- Snapshot membership references canonical `market_bars` with `RESTRICT`.
- `historical_data_load_requests.snapshot_id` is another real snapshot reference;
  its terminal rows remain durable acquisition/load history. The request's
  `strategy_version_id` is unrelated to Experiment ownership and must survive.
- `historical_acquisition_windows` are canonical acquisition history and have no
  snapshot ownership edge. No market-bar or acquisition-window eviction is in
  scope.
- All three current paths that attach an existing snapshot reference must share
  one snapshot-row-first lock contract: Experiment creation, successful
  historical-load completion, and FAILED-load snapshot preservation (including
  insufficient warm-up). The current load completion and failure paths do not
  consistently do so and must be reconciled rather than preserved as secondary
  direct-assignment/session-get paths.
- Snapshot orphan cleanup must also preserve a candidate snapshot whenever any
  historical data load request is `PENDING` or `RUNNING`, covering the interval
  after a load creates or reuses the snapshot and before it attaches
  `snapshot_id`. This adds no candidate reference, lease, reservation, or timing
  change to historical-load behavior.
- The global active-load predicate alone does not serialize a new load becoming
  `PENDING` after orphanhood is checked but before deletion commits. Freeze 07
  therefore uses one dedicated PostgreSQL transaction-scoped lifecycle
  serialization lock shared by Experiment snapshot orphan deletion and
  historical-load activation. Experiment deletion acquires it before evaluating
  active-load state and holds it through commit. Historical-load creation and
  FAILED -> RUNNING resume acquire the same lock before making a load active and
  hold it through commit. Snapshot attachment/completion continues to use the
  separate snapshot-row-first lock order.

### Current API/UI seams

- `backend/api/experiments.py` has one Experiment router and existing human
  identity projection (`strategy`, instrument/provider, dates, status), but no
  delete endpoint or destructive UI action.
- `frontend/components/experiments/experiment-status.tsx` and
  `frontend/components/experiments/experiment-list.tsx` are the existing
  trader-facing identity/status surfaces. The new workflow should be local to
  these surfaces, not a generic destructive-resource framework.
- Existing read routes distinguish `NOT_FOUND`, incomplete results, and terminal
  statuses; completed result reads are persisted-fact reads and must remain
  unchanged for surviving Experiments.

### Local authority seam

- `backend/api/app.py` currently creates the FastAPI application and routes but
  has no application-level peer-address guard.
- Peer authority must use the ASGI request scope's actual client peer, never
  Host, `:authority`, X-Forwarded-For, or any other forwarding header. A
  separate local-only Host/`:authority` allowlist is permitted solely for
  browser DNS-rebinding defense. The scope value is authoritative only when the
  supported Uvicorn entrypoint disables proxy-header rewriting; proxy deployment
  and remote access remain out of scope.
- Test clients and local frontend/API operation need an injectable or explicit
  testable peer seam without weakening production behavior.

### Strategy capability seam

- `backend/domain/strategy.py:StrategyContext` currently imports
  `backend.integrations.oanda.capabilities` inside `__post_init__`, resolves a
  default `OANDA_CAPABILITY`, and calls `validate_market_specification`.
- `backend/api/experiments.py`, `backend/api/strategies.py`, and
  `backend/experiments/results.py` also resolve OANDA capability facts for their
  projections. This freeze changes only the generic StrategyContext ownership
  seam; fixed product composition remains OANDA-backed.
- The intended boundary is a composition/runtime-supplied, already validated
  `MarketSpecification`. StrategyContext validates shape/instrument consistency
  only and does not import or name OANDA. Existing callers must be updated at
  composition boundaries, not by adding a provider lookup to the domain.

## Scope

### In scope

- Explicit Experiment-owned deletion service/repository boundary and exact FK
  deletion order.
- Minimal append-only Experiment deletion audit receipt, inserted in the same
  transaction as deletion and containing operation/audit identity only.
- Transactional orphan snapshot cleanup that considers every current repository
  reference, including all Experiment rows and all historical load request rows.
- API response/error contract and one explicit confirmation-based UI workflow.
- Application-code loopback peer enforcement for IPv4 and IPv6, a secondary
  localhost/numeric-loopback Host / HTTP `:authority` restriction solely for
  browser DNS-rebinding defense, a supported Uvicorn startup with proxy headers
  disabled, and tests for loopback, non-loopback, missing/invalid peer,
  local/external host, and spoofed-header cases through that startup
  configuration.
- One snapshot-first lock helper/boundary used by Experiment creation,
  successful load completion, and FAILED-load snapshot preservation/attachment.
- One PostgreSQL transaction-scoped historical-load lifecycle serialization
  boundary shared by Experiment snapshot orphan deletion, new `PENDING`
  historical-load creation, and FAILED -> RUNNING resume. It exists only to
  serialize load activation against snapshot orphan deletion; it does not replace
  snapshot-row locking or change historical-load snapshot semantics.
- Outward capability resolution and composition updates needed to remove OANDA
  dependency from `StrategyContext`.
- Regression proof for completed Experiment immutability/read semantics and all
  required rollback/failure paths.

### Out of scope

- Soft delete, trash, restore, archival replacement, deletion receipts exposed as
  Experiment tombstones, retention/eviction jobs, or automatic market-data
  cleanup.
- Deletion of Strategies, StrategyVersions, Instruments, VenueInstruments,
  canonical MarketBars, acquisition windows, or historical load requests.
- Deletion of RUNNING Experiments, cancellation, Experiment execution redesign,
  result methodology, Risk, accounting, market-data acquisition, or PAPER/LIVE.
- Remote access, authentication, authorization, proxy deployment semantics, or
  trusting forwarded headers.
- New brokers, instruments, timeframes, Strategy frameworks, plugin systems, or
  generic destructive-resource infrastructure.
- Git branch creation, commits, merges, tasks, BUILD dispatch, or application
  implementation during this planning freeze.

## Acceptance criteria

1. ARCHITECTURE.md names every Experiment-owned table and exact child-first
   delete order, including order self-references and both Trade order edges.
2. A PENDING, FAILED, or COMPLETED Experiment can be hard-deleted; RUNNING is
   rejected without deleting any row. Partial FAILED graphs are included.
3. Before its first mutation, deletion rejects order-parent self-cycles,
   multi-node cycles, any malformed order graph without well-defined descendant
   depth, and every surviving inbound reference from outside the Experiment
   graph to a target TradeIntent, RiskDecision, or Order with
   `DELETE_OWNERSHIP_CONFLICT`.
4. The deletion transaction removes the Experiment graph and deletes its
      snapshot plus all snapshot-owned membership/gap rows only if no remaining
      Experiment or historical load request references that snapshot and no
      historical data load request is `PENDING` or `RUNNING`.

   Before evaluating that active-load predicate, deletion holds the shared
   transaction-scoped historical-load lifecycle serialization lock through
   transaction commit. New PENDING load creation and FAILED -> RUNNING resume
   acquire the same lock before becoming active and hold it through their own
   transaction commit.

   Therefore:
   - if load activation commits first, deletion subsequently observes an active
     load and preserves the snapshot;
   - if deletion acquires the lifecycle lock first, no new load can become active
     until the deletion transaction commits.

   An active load always preserves the snapshot and returns
   `snapshot.deleted = false`, including the interval where it has produced or
   reused the snapshot but has not yet attached `snapshot_id`.

5. In that same transaction, deletion inserts exactly one minimal append-only
   audit receipt containing only the durable operation identity, deleted
   Experiment/pre-delete identity, Strategy identity/version/source fingerprint,
   instrument/provider/trading period, deletion time, DatasetSnapshot ID,
   `snapshot_deleted`, and confirmation schema/version. It has no FK to deleted
   rows, stores no deleted result/trading/account/equity graph, and provides no
   restore or Experiment tombstone behavior. Receipt failure rolls back every
   deletion.
6. Canonical `market_bars`, `historical_acquisition_windows`, and unrelated
   snapshot/load rows survive. Shared snapshots survive.
7. An injected delete or audit-receipt failure leaves the entire Experiment
   graph, snapshot graph, and receipt set unchanged after rollback.
8. Delete is one explicit API workflow: a successful first delete is permanent;
   repeat/not-found is stable and non-destructive; RUNNING conflict is explicit;
   confirmation identifies human-readable Experiment facts, including the
   locked current status, rather than requiring raw UUID text. A stale
   PENDING/FAILED/COMPLETED status returns `DELETE_CONFIRMATION_MISMATCH` and
   cannot delete newly-created facts.
9. API access is denied unless the actual peer is loopback IPv4/IPv6 and the
   Host / HTTP `:authority` is `localhost` or a numeric loopback IPv4/IPv6 form,
   ignoring its port. The supported Atlas Uvicorn startup uses
   `--no-proxy-headers` (or equivalent `proxy_headers=False`), so
   `scope["client"]` remains primary and authoritative. Tests through that
   configuration prove local Host passes, external/DNS-rebinding Host denies,
   non-loopback peers deny even with local/spoofed Host, and forwarding headers
   cannot alter the decision. Local test/frontend operation remains possible
   through a documented testable peer seam.
10. Experiment creation, successful historical-load completion, and FAILED-load
    snapshot preservation/attachment (including insufficient warm-up) all lock
    the existing DatasetSnapshot row before the referencing Experiment/load row;
    a single helper owns this order and no `session.get` or direct-assignment
     bypass remains. The lifecycle serialization lock does not replace this snapshot-first attachment order and the two locks must have a documented non-deadlocking acquisition
    contract.
11. `StrategyContext` and generic Strategy/domain modules have no OANDA capability
    import or resolution. Composition supplies validated MarketSpecification and
    current Strategy/Experiment behavior remains equivalent.
12. Completed Experiment result/read semantics remain persisted-fact based and
    immutable; deleting one Experiment does not alter surviving completed reads.
    Normal reads of the deleted ID remain `NOT_FOUND`, never a receipt/tombstone.
13. Required architecture proof and implementation-test plan are complete before
    any later BUILD authorization.

## Approved architecture decisions and implementation gate

The developer has approved the five proposed boundary choices:

- `200` JSON success with `snapshot.deleted`;
- global pre-routing peer middleware with `403 LOCAL_PEER_REQUIRED`;
- explicit immutable `MarketSpecification` object injection at OANDA
  composition/runtime boundaries, with no provider resolver in the Strategy
  domain;
- exact `DELETE` plus locked exact human-fact confirmation; and
- `409 DELETE_OWNERSHIP_CONFLICT`.

The architecture additionally freezes the required reconciliations: an atomic
append-only deletion audit receipt; Uvicorn proxy-header rewriting disabled for
the supported startup; snapshot-first locking across every current reference
attachment path plus the conservative active-load orphan guard; complete cycle
plus inbound cross-owner preflight before any mutation; locked Experiment status
in confirmation; a PostgreSQL transaction-scoped lifecycle serialization lock preventing new
 historical-load activation from racing snapshot orphan deletion; and the secondary local-host authority check. These are contract
requirements, not implementation authorization.

BUILD task decomposition is recorded in the canonical task artifacts:

- `tasks/T001-experiment-deletion-lifecycle.md`
- `tasks/T002-snapshot-attachment-and-load-locks.md`
- `tasks/T003-local-authority.md`
- `tasks/T004-strategy-capability-composition.md`
- `tasks/T005-delete-api-and-ui.md`

## BUILD task state

| Task | Status | Dependency |
| ---- | ------ | ---------- |
| T001 — Experiment deletion lifecycle | `DONE` | — |
| T002 — Snapshot attachment and historical-load locks | `DONE` | T001 |
| T003 — Loopback peer and local-host authority | `DONE` | — |
| T004 — Strategy capability composition | `DONE` | — |
| T005 — Experiment delete API and confirmation UI | `DONE` | T001, T002, T003 |

Tasks are dispatched sequentially on this branch. Each BUILD worker owns its task
receipt and implementation/test files; role artifacts remain Solo/role-owned.

## Next action

Approved remediation for REVIEW findings R-001 through R-005 is complete. All
BUILD tasks are `DONE`; validation and targeted rereview both `PASS`, with no
unresolved CRITICAL/IMPORTANT findings. R-006 remains corrected. Await explicit
merge approval. Do not start the pre-PAPER audit or PAPER work.
