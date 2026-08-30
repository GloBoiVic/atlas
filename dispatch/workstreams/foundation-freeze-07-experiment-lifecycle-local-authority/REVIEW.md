# Foundation Freeze 07 Review

## Status

`PASS` — targeted rereview of approved R-001–R-005 remediation; merge approval remains external.

## Targeted rereview decision

`PASS` — no unresolved `CRITICAL` or `IMPORTANT` findings remain. The initial
R-001–R-005 failures are remediated and freshly verified below; R-006 bookkeeping
is consistent. This review stops before merge and does not authorize pre-PAPER or
PAPER work.

### Targeted evidence

- **R-001 PASS:** the populated PostgreSQL deletion suite passed **37 tests**.
  PENDING, FAILED, and COMPLETED graphs delete through the legacy immutable
  triggers under the deletion context; the exact child-first stage sequence,
  both Trade order edges, fills/events/projections/results/gaps, receipt fields,
  receipt-insert rollback, and rollback after every explicit deletion stage are
  covered. Migration checks passed **10 tests** across the head → 0020 → head
  cycle; source inspection confirms the downgrade restores the pre-0021 guarded
  trigger bodies and removes the deletion helper. Direct immutable DML remains
  fail-closed without deletion context.
- **R-002 PASS:** scoped IPv6 peers and Host/`:authority` forms (raw,
  bracketed, encoded, and decoded) return `403 LOCAL_PEER_REQUIRED` before
  routing; valid IPv4/IPv6/mapped loopback and `localhost` behavior remains
  admitted. Fresh authority/API checks passed **42 + 16 tests** (with only the
  documented skipped health cases in the standalone authority run).
- **R-003 PASS:** focused frontend deletion/API tests passed **10 tests**.
  `EXPERIMENT_DELETE_FAILED`, `LOCAL_PEER_REQUIRED`, unavailable, and timeout
  failures are visible inside the active accessible dialog, preserve `DELETE`,
  issue one request, and expose no deletion retry. The recorded Local Host
  workflow independently observed the same persistent in-dialog 500 failure.
- **R-004 PASS:** deletion/lock/lifecycle proof passed **37 + 15 tests** and
  covers populated/partial graphs, inbound-FK inventory, receipt and stage
  rollback, shared/terminal/active snapshot retention, both activation race
  directions for new PENDING and FAILED → RUNNING, deletion-first ordering, and
  bounded snapshot-first/lifecycle no-deadlock completion.
- **R-005 PASS:** `ARCHITECTURE.md` is frozen and authorized with technical
  sections unchanged by remediation; its final gate, `PLAN.md`, `ACTIVE.md`, all
  five task headers/receipts, and targeted `VALIDATION.md` tell one coherent
  lifecycle story. R-006 is corrected: every task header and receipt is `DONE`.
- Fresh supporting checks passed: historical/strategy regression selection
  **47 passed, 1 skipped**; targeted Ruff, focused Pyright, frontend TypeScript,
  ESLint, Prettier, Python compilation, and `git diff --check`.

### Scope and residual concerns

- Prior broad PASS evidence remains applicable; the targeted checks did not
  alter its conclusions. The current worktree diff remains within the five task
  implementation/test areas plus expected dispatch bookkeeping; pre-existing
  `.codegraph/` and `frontend/.env.local` remain excluded.
- No pre-PAPER audit, PAPER/LIVE work, Deployment work, broker execution, or
  unrelated infrastructure was started. No residual gating concern remains.
- Non-gating repository concerns retained from prior receipts: the full frontend
  suite has pre-existing decomposed-component mock failures, strict repository-wide
  Pyright remains noisy in legacy/partially typed surfaces, and existing
  Starlette/httpx plus unregistered-mark warnings remain.

## Review basis

- **Role:** `REVIEW`
- **Workstream:** `foundation-freeze-07-experiment-lifecycle-local-authority`
- **Branch/CWD:**
  `solo/foundation-freeze-07-experiment-lifecycle-local-authority` /
  `/Users/vike/Desktop/atlas`
- Read the request, corrected `PLAN.md`, frozen-contract content in
  `ARCHITECTURE.md`, all five task receipts and remediation history,
  `VALIDATION.md`, relevant architecture context, and the implementation/test
  diff.
- HEAD and the requested base are both `e2c186c619b961d296d84da01696920f4349e7f2`
  (`main`); the branch contains the uncommitted worktree changes. The changed
  paths are confined to the union of the five task receipts plus expected
  `dispatch/ACTIVE.md` bookkeeping. Pre-existing `.codegraph/` and
  `frontend/.env.local` remain untracked and excluded.
- No pre-PAPER audit or PAPER/LIVE work was performed.

## Initial acceptance review (historical R-001–R-006; superseded by targeted rereview)

| # | Judgment | Evidence |
|---:|---|---|
| 1 | PASS | `ARCHITECTURE.md` enumerates the Experiment graph and fixed child-first order. |
| 2 | **FAIL** | The populated graph cannot currently be deleted because legacy immutable triggers still reject deletes; see R-001. |
| 3 | PARTIAL | The code has cycle, dangling/external-parent, and inbound-edge preflight, but the required schema inventory and broad malformed-graph proof are absent; see R-004. |
| 4 | PASS (implementation) / PARTIAL (proof) | Snapshot orphan predicates and the shared lifecycle lock are present; the required concurrency matrix is not committed; see R-004. |
| 5 | PASS (implementation) | Receipt is same-transaction, identity-only, unique, FK-free, and append-only by trigger. |
| 6 | PASS | Snapshot memberships are conditionally removed while canonical bars, acquisition windows, and load rows are outside the delete set. |
| 7 | PARTIAL | Caller-owned rollback is implemented and a stage-failure test exists, but receipt-failure and every-stage rollback proof are absent; R-001 also prevents success for populated graphs. |
| 8 | **FAIL** | API confirmation/error semantics are mostly present, but unknown delete errors render inside inert page content behind the still-open dialog; see R-003. |
| 9 | **FAIL** | Loopback and local-authority checks exist, but scoped IPv6 loopback authorities are admitted although the contract requires numeric literals; see R-002. |
| 10 | PASS (implementation) / PARTIAL (proof) | The snapshot-first helper is used by creation/completion/failed attachment and the lifecycle lock is separate; both-direction activation/race proof is not a committed test matrix; see R-004. |
| 11 | PASS | `StrategyContext` has explicit provider-neutral `MarketSpecification` input and no OANDA capability import/resolution; targeted composition tests pass. |
| 12 | PASS (implementation) / PARTIAL (proof) | Normal reads remain persisted-fact based and deleted IDs are not tombstones; surviving completed-read equivalence after deletion is not fully exercised. |
| 13 | **FAIL** | Required architecture proof is incomplete and the architecture artifact still contains a pre-BUILD approval gate; see R-004 and R-005. |

## Initial findings (historical; remediation status is recorded above)

### R-001 — PERSISTENCE / CRITICAL — populated Experiment graphs are not deletable

- **Evidence:** `0004_phase_3_first_historical_trade.py:89-95` installs the
  legacy `trades_terminal_guard`, `orders_fact_guard`, and append-only fact
  triggers. The current `0021` migration replaces the Phase 4 guard functions
  but never removes or reconciles those legacy triggers. Independent inspection
  of the migrated validation database shows:
  `trade_intents_append_only`/`risk_decisions_append_only`/`fills_append_only`
  still call `prevent_fact_mutation()`, `orders_fact_guard` still calls
  `prevent_order_fact_mutation()`, and `trades_terminal_guard` still calls
  `prevent_completed_trade_mutation()`.
- **Impact:** Those functions reject `DELETE` unconditionally. Any Experiment
  containing an intent, risk decision, fill, order, or trade fails before the
  receipt. The current deletion integration test only deletes an empty child
  graph, so it does not expose the blocker. This violates hard deletion for
  normal PENDING/FAILED/COMPLETED graphs, exact graph deletion, and successful
  receipt semantics.
- **Remediation packet:** Owner `T001`/migration owner. Reconcile the legacy
  triggers in `0021` so every delete path is guarded by the reviewed deletion
  context while ordinary immutable DML remains fail-closed; alternatively
  retire only the redundant legacy triggers after proving the Phase 4 guards
  preserve their behavior. Restore the exact pre-0021 trigger/function set on
  downgrade. Add a PostgreSQL test with the complete graph (including
  completed Trade, both order edges, fills, events, protections, diagnostics,
  risk, projections, results, and gaps) and run it for PENDING, FAILED, and
  COMPLETED, plus migration upgrade/downgrade and rollback checks.
- **Revalidation:** Dedicated PostgreSQL migration cycle, full populated-graph
  deletion/receipt assertions, stage and receipt-failure rollback, and the
  affected integration/Ruff/diff checks.

### R-002 — AUTHORITY / IMPORTANT — scoped IPv6 literals bypass the numeric-host allowlist

- **Evidence:** `backend/api/local_authority.py:80-86` passes a host containing
  an IPv6 zone identifier to `ipaddress.ip_address`; Python reports
  `::1%lo0` as loopback, so `[::1%lo0]`, `::1%lo0`, and
  `[::1%25lo0]` are admitted. Independent middleware reproduction returned
  `200` and reached the downstream app for each value.
- **Impact:** The frozen contract admits only `localhost` or numeric loopback
  IPv4/IPv6 authorities and rejects ambiguous/malformed values. A scoped host
  is not a numeric literal and weakens the DNS-rebinding authority boundary.
  The peer path uses the same helper and has the same edge case.
- **Remediation packet:** Owner `T003`. Reject `%`/zone identifiers in peer
  and HTTP authority host strings before parsing (or require a strict numeric
  IPv6 grammar), while retaining mapped-loopback behavior. Add direct tests for
  raw and bracketed encoded/decoded scoped IPv6 peers and authorities, then
  rerun the complete authority suite and startup/lifespan checks.
- **Revalidation:** Assert all scoped forms return `403 LOCAL_PEER_REQUIRED`
  without routing; retain passes for `::1`, mapped loopback, and `localhost`.

### R-003 — UI / IMPORTANT — unknown deletion failures are hidden by modal inertness

- **Evidence:** `frontend/components/experiments/experiment-status.tsx:269-275`
  marks the page containing the `deleteError` panel at lines 322-330 as
  `inert` and `aria-hidden` while the dialog is open. The unknown-outcome path
  at lines 149-152 keeps the dialog open, but does not render the error inside
  the dialog. The focused test only finds the text in the DOM; it does not
  establish visibility or dialog containment.
- **Impact:** A 500, authority error, transport failure, or ownership error
  leaves the confirmation context open but does not visibly/semantically tell
  the user that deletion was not confirmed. This fails the frozen persistent
  error behavior and makes a destructive unknown outcome ambiguous.
- **Remediation packet:** Owner `T005`. Render the structured unknown-outcome
  `ErrorPanel` inside the active dialog (or otherwise outside inert content),
  preserve the typed phrase and no-retry behavior, and keep it live/accessible.
  Add a focused test asserting the error is visible and contained by the
  dialog for `EXPERIMENT_DELETE_FAILED`, `LOCAL_PEER_REQUIRED`, and transport
  failures.
- **Revalidation:** Focused Vitest deletion suite, frontend typecheck/lint,
  and the available Local Host modal workflow with an observable failure.

### R-004 — TESTING / IMPORTANT — required deletion and lock proof is incomplete

- **Evidence:** `backend/tests/integration/test_experiment_deletion.py` has
  nine tests and does not cover all required cases in `ARCHITECTURE.md:650-734`:
  all partial FAILED graph shapes, order self/multi-node cycles and malformed
  depths, shared/terminal/active load retention, receipt insertion failure,
  failure after each deletion stage, the complete PostgreSQL inbound-FK
  inventory guard, surviving completed-read equivalence, or the two-direction
  lifecycle activation races. T002's committed tests are mostly statement
  inspection; the two-connection advisory-lock probe is receipt evidence, not
  a repository test matrix.
- **Impact:** `VALIDATION.md` PASS evidence is targeted to F-001–F-005 and
  cannot establish the frozen architecture's explicit required proof. The
  current suite also missed R-001's populated-graph trigger failure.
- **Remediation packet:** Owners `T001`/`T002`/`T005`. Add the smallest
  deterministic PostgreSQL tests for each listed deletion graph, inbound edge,
  snapshot/load race and rollback boundary. Add a schema-contract test that
  inventories every PostgreSQL FK into `trade_intents`, `risk_decisions`, and
  `orders` and fails on an unclassified future edge. Add completed-survivor
  read equivalence and API/UI failure-path assertions without broadening the
  product scope.
- **Revalidation:** Run the dedicated `_test` database migration cycle, full
  integration selection, affected unit suites, frontend focused suite, and
  record the complete matrix in the owning receipts and `VALIDATION.md`.

### R-005 — DISPATCH / IMPORTANT — frozen architecture artifact contradicts the canonical plan

- **Evidence:** `ARCHITECTURE.md:3` says `RECONCILED — awaiting final explicit
  developer approval`, and `ARCHITECTURE.md:769-775` still says final approval
  is required before task creation, Git start, or BUILD authorization. In
  contrast, `PLAN.md:30-35` says architecture is `FROZEN`, Git start/build are
  complete, and `PLAN.md:285-301` records all tasks DONE and validation PASS.
- **Impact:** The canonical artifacts disagree about the authorization gate and
  whether this implementation phase was permitted. Acceptance criterion 13 and
  the required artifact-completeness gate cannot be judged complete while the
  architecture still contains its pre-approval text.
- **Remediation packet:** Owner `ARCHITECT`/Solo. Reconcile only the canonical
  architecture status and final-gate text to record the actual explicit approval
  and frozen state, without changing the frozen technical contract. Recheck
  PLAN/ACTIVE/task references after the reconciliation.
- **Revalidation:** Artifact-only consistency check: architecture status,
  PLAN/ACTIVE phase, branch/base, and task authorization must tell one coherent
  lifecycle story.

### R-006 — DISPATCH / MINOR — three task headers retain stale `IN_PROGRESS`
  status

- **Evidence:** `tasks/T001-experiment-deletion-lifecycle.md:5`,
  `tasks/T002-snapshot-attachment-and-load-locks.md:5`, and
  `tasks/T005-delete-api-and-ui.md:5` say `IN_PROGRESS`, while each receipt
  later says `Status: DONE` and `PLAN.md:287-293` says DONE.
- **Impact:** Bookkeeping is internally inconsistent, but it does not change
  application behavior. It should be corrected before terminal closure.
- **Remediation packet:** Owner Solo/task owners. Change only those stale task
  header states to `DONE` (or `DONE_WITH_CONCERNS` if the remaining review
  findings are intentionally assigned there), preserving the remediation
  history and receipt evidence.
- **Revalidation:** Compare all five task headers, receipt sections, PLAN task
  table, ACTIVE phase, and final REVIEW status.

## Initial verified passes and constraints (retained history)

- Reviewer rerun: dedicated PostgreSQL targeted backend suites (deletion,
  lifecycle, authority, historical load, and capability composition) — **77
  passed, 1 existing Starlette/httpx deprecation warning**.
- Reviewer rerun: focused frontend deletion/API-client Vitest — **6 passed**;
  frontend TypeScript check passed.
- Targeted Ruff, `git diff --check`, dedicated-database Alembic `current` and
  `check`, and the static provider-neutral checks passed.
- The default local database was not at head for an unqualified Alembic check;
  the documented dedicated `*_test` database was at head and clean. The full
  frontend suite's pre-existing decomposed-component mock failures remain
  documented by T005/VALIDATION and were not treated as Freeze 07 regressions.
- README and implementation continue to state historical simulation only;
  no Deployment, broker execution, PAPER, LIVE, pre-PAPER audit, or unrelated
  infrastructure change was found.

## Initial review decision (historical; superseded)

`FAIL`. R-001 is a direct populated-graph deletion blocker; R-002 and R-003
are unresolved security/UI contract defects; R-004 and R-005 leave required
proof and canonical authorization incomplete. R-006 is a non-blocking
bookkeeping observation. No application, test, fixture, selector, harness,
workflow, migration, PLAN, ARCHITECTURE, VALIDATION, task artifact, or other
role artifact was edited by REVIEW.

## Final targeted rereview decision

`PASS` — R-001–R-005 are freshly remediated with no unresolved
`CRITICAL`/`IMPORTANT` finding; R-006 is corrected. Merge approval remains
external, and no pre-PAPER or PAPER work is authorized by this review.
