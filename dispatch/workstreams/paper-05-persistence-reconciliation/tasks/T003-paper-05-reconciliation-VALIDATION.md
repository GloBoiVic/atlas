# T003 Validation — PAPER 05 Bounded Reconciliation

- **Task:** `T003`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `VALIDATE`
- **Status:** `FAIL`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`

## Validation mandate

Independently validate T003 against the frozen PLAN and ARCHITECTURE, T003's
BUILD receipt, prior task/remediation evidence, actual diff, and current source.
Verify the coordinator is strictly read-only and bounded; UNKNOWN/claimed-entry
and known-Fill/protection-incomplete sequences use exact attribution; not-found,
stale, malformed, contradictory, unexpected-exposure, and read-failure cases
remain fail-closed; observations/findings precede projections; and numeric
transaction frontiers retain bounded provenance without global synchronization.

Verify repeated/restarted/concurrent reconciliation cannot create mutation claims
or POST/PUT calls, and existing Strategy/Risk/PAPER 04/Fill semantics remain
unchanged. Run focused reconciliation/OANDA/PAPER tests first, then the broad
safe non-integration/non-external backend suite if focused tests pass. Use a
dedicated `*_test` PostgreSQL database/schema for repository/migration evidence
when available; report environment limitations separately from defects.

Only deterministic fakes/`httpx.MockTransport` are permitted. VALIDATE writes
only this artifact and must not modify application, tests, fixtures, migrations,
or other evidence artifacts.

## Worker Evidence

Populate this artifact once with the independent validation receipt, findings,
commands, and evidence.

## Independent judgment

T003 does not pass the frozen reconciliation contract. The provider boundary is
GET-only and the bounded coordinator has no mutation-capable collaborator, but
several required attribution, contradiction, frontier, and provenance rules are
not enforced by the current implementation.

## Checks / evidence

- Repository root/CWD and branch were verified as `/Users/vike/Desktop/atlas` and
  `solo/paper-05-persistence-reconciliation`; no application, test, fixture,
  migration, or prior evidence file was changed.
- Reviewed frozen `PLAN.md`/`ARCHITECTURE.md`, T001/T002 receipts and validation,
  R001/R002 BUILD/VALIDATION/REVIEW evidence, the T003 BUILD receipt, the complete
  T003 source/test diff, and current reconciliation/provider/repository source.
- Focused first:
  `uv run pytest -q backend/tests/paper/test_reconciliation.py
  backend/tests/integrations/test_oanda_reconciliation.py
  backend/tests/paper/test_durable_execution.py
  backend/tests/paper/test_persistence_contracts.py
  backend/tests/integrations/test_oanda_entry_mutation.py
  backend/tests/integrations/test_oanda_request.py` — **87 passed**.
- Broad safe suite after focused success:
  `uv run pytest -q -m "not integration and not external"` — **948 passed, 4
  skipped, 97 deselected**, four existing warnings. The first 120-second run
  timed out before completion; the bounded rerun completed successfully.
- Dedicated PostgreSQL database `atlas_test`, schema `paper05_validation`:
  `PGOPTIONS='-c search_path=paper05_validation' uv run pytest -q
  backend/tests/integration/test_paper_execution_repository.py` — **9 passed**.
  With `ATLAS_DATABASE_URL` directed to that dedicated URL,
  `alembic current` reported `0022_paper_persistence (head)` and `alembic check`
  reported **No new upgrade operations detected**.
- Dedicated migration fixture run: **1 passed, 2 failed at setup** because its
  hard-coded `DROP SCHEMA public CASCADE` requires ownership of `public`
  (`must be owner of schema public`). This is the previously documented
  environment/tooling limitation, not evidence of a T003 product pass.
- Changed-slice static checks passed: `ruff format --check` (10 files already
  formatted), `ruff check` (all checks passed), and `pyright` (**0 errors**).
  `git diff --check` passed. Deterministic `httpx.MockTransport` probes used a
  non-production token string and asserted GET-only requests; no credentials,
  real OANDA request, broker mutation, activation, or capital-capable action was
  used.

## Findings

### IMPORTANT — PRODUCT — bounded range cannot resolve required terminal reject

`OandaPracticeReconciliationReader._range_candidate()` recognizes
`ORDER_REJECT`, while the frozen range contract requires `MARKET_ORDER_REJECT`.
A MockTransport range containing a matching `MARKET_ORDER` and
`MARKET_ORDER_REJECT` returned no attributable terminal candidate and therefore
cannot resolve an uncertain entry to `REJECTED`. This violates the required
bounded lost-reject recovery and strict terminal attribution rules.

### IMPORTANT — PRODUCT — bounded range cannot attribute an unknown-entry cancel

For an unknown/claimed attempt, the reconciliation context starts with no
`provider_order_id`. The range reader does discover a matching create ID, but
the `ORDER_CANCEL` candidate still requires `context.provider_order_id` to be
non-null. A matching create/cancel chain in one bounded range was consequently
unattributed and unresolved, violating the frozen create/cancel recovery path.

### IMPORTANT — PRODUCT — exact provider response/request facts are not strictly attributed

The OANDA normalizer accepts provider objects without binding all applicable
facts to the original attempt:

- `read_transaction(context, "12")` accepted a response whose transaction body
  ID was `13`.
- `read_order()` marked an order with the right account/instrument/client ID but
  wrong type, units, time-in-force, position-fill, and price-bound as
  attributable.
- The fill/rejection paths do not require the terminal transaction's order ID
  to equal the exact order read's broker order ID.

These probes allow wrong or contradictory broker facts to reach terminal
execution conclusions despite the frozen all-applicable-facts attribution rule.

### IMPORTANT — PRODUCT — known-Fill Trade facts are insufficiently validated

Known-Fill reconciliation does not validate the provider Trade's signed units
or actual entry price against the durable Fill. A MockTransport Trade with the
correct ID/client/account/instrument but `currentUnits="1"` and `price="9.0"`
was accepted; the coordinator promoted the attempt to
`FILLED_PROTECTED` using otherwise matching protection. The normalizer also
accepted a response with a different returned Trade ID when the context had no
durable Trade ID. This violates the required known-Fill units, entry-price, and
requested-Trade identity checks.

### IMPORTANT — PRODUCT — unattributed closed Trade is classified as lifecycle advancement

`PaperReconciliationCoordinator._consume_trade()` handles `CLOSED` before it
checks `read.attributable`. A deterministic read with `state=CLOSED` and
`attributable=False` changed a protected attempt's reconciliation result to
`LIFECYCLE_ADVANCED` instead of failing closed. Wrong-account or wrong-Trade
closed objects must not support the lifecycle distinction.

### IMPORTANT — PRODUCT — contradictory range evidence is not preserved as conflict

The OANDA reader sets a range read to `CONFLICT` when it contains both an
attributable Fill and reject/cancel evidence, but `PaperReconciliationRead`
rejects transactions on a non-`RANGE` read. Thus contradictory provider facts
fail before their normalized observation can be appended. Independently, the
provider-neutral `_consume_range()` does not inspect `read.state` and, for a
range containing one attributable Fill plus one attributable reject, selected
the Fill and ignored the incompatible terminal evidence. The resulting run
was unresolved/incomplete rather than an explicit conflict, contrary to Fill
plus incompatible reject/cancel handling.

### IMPORTANT — PRODUCT — per-attempt transaction frontier can regress

`frontier_applied` is taken directly from the highest current read frontier and
written without comparing it with the durable `last_applied_transaction_id`.
A deterministic two-pass probe applied frontier `20`, then a later read with
frontier `15`, and stored `15`. The frozen contract requires an applied frontier
to advance only after validated observations; regressions weaken replay and
provenance safety.

### IMPORTANT — PRODUCT — range observations lose batch/related provenance

For transaction-range reads, the normalizer puts per-transaction `batchID` in a
limited facts map but does not retain `relatedTransactionIDs` or batch/related
IDs in the typed observation provenance. A MockTransport range carrying both
fields produced `observation.batch_id is None`, an empty
`related_transaction_ids`, and no related IDs in the normalized transaction
facts. This violates the frozen request/transaction/batch/related/frontier
provenance requirement needed to explain strict attribution.

### MINOR — PRODUCT — RequestID is discarded for not-found reads

`OandaObservationRequester` only returns metadata on successful responses and
`OandaRequestError` does not carry the response RequestID. A 404 with
`RequestID: not-found-request` normalized to an observation with
`request_id=None`, contrary to the requirement to retain a supplied RequestID.
This is metadata loss rather than a mutation-safety bypass, but remains an
acceptance gap.

## Regression and safety conclusion

The focused and broad suites provide useful deterministic regression evidence,
and the dedicated repository tests confirm existing row-lock/append-only/
immutable-claim behavior. The current source contains no POST/PUT/cancel/close/
reduce/repair operation in the reconciliation provider or coordinator. However,
the unresolved IMPORTANT PRODUCT findings above block validation: read-only
behavior alone is insufficient when the read facts can be misattributed,
contradictions can be hidden, or durable frontier/provenance can be lost.

## Worker Evidence Receipt

ROLE: VALIDATE
STATUS: FAIL
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T003-paper-05-reconciliation-VALIDATION.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Focused 87 passed; broad safe backend 948 passed, 4 skipped, 97 deselected; dedicated PostgreSQL repository 9 passed; Alembic current/check passed; migration fixture 1 passed and 2 setup-failed on documented public-schema ownership; scoped Ruff/Pyright and diff checks passed; deterministic MockTransport/source probes reproduced the findings.
FINDINGS / CONCERNS: FAIL — eight IMPORTANT PRODUCT findings and one MINOR PRODUCT provenance finding remain. No real OANDA call, credential, activation, runtime, or capital-capable action occurred.
