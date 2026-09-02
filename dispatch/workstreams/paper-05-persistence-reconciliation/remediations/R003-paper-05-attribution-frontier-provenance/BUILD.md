# R003 — PAPER 05 Attribution, Frontier + Provenance Remediation

- **Remediation ID:** `R003`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Origin finding:** `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T003-paper-05-reconciliation-VALIDATION.md`, findings 1–9
- **Finding severity:** eight `IMPORTANT` / `PRODUCT` blockers and one `MINOR` / `PRODUCT` RequestID finding, classified after the workstream-wide two-remediation-return cap
- **Related original tasks:** `T001-paper-05-persistence-foundation`, `T002-paper-05-durable-execution`, `T003-paper-05-reconciliation`; related prior remediation receipts `R001` and `R002`
- **Approved requirement/invariant violated:** frozen PLAN + ARCHITECTURE require strict immutable attempt/result identity, exact protection and provider-fact attribution, bounded reject/cancel recovery, known-Fill and closed-Trade attribution, Fill-over-contradiction precedence, monotonic numeric transaction frontiers, retained bounded range provenance, and preservation of supplied 404 RequestID metadata

## Authorization and worker evidence requirements

This is the one explicitly developer-authorized post-cap remediation path. It is
not new scope and does not reopen PLAN or ARCHITECTURE. Preserve every existing
task, validation, and remediation artifact unchanged; do not overwrite prior FAIL
evidence. The BUILD worker must inspect, before changing code:

- current frozen `PLAN.md` and `ARCHITECTURE.md`;
- root workstream `VALIDATION.md`;
- all prior remediation BUILD/VALIDATION/REVIEW receipts (`R001`, `R002`);
- all prior task BUILD/VALIDATION/REVIEW receipts, especially T003's failed validation;
- the current implementation and test diff;
- every deterministic failing probe/reproduction recorded by T003 validation.

Use only deterministic fakes/`httpx.MockTransport` and a dedicated test database
where available. No real OANDA mutation, credentialed action, PAPER activation,
or capital-capable operation is authorized.

## Exact remediation outcome

Address every currently unresolved approved-scope PRODUCT blocker from T003 and
make each reproduced failure permanent regression coverage, while preserving the
frozen architecture and all existing PAPER 04 semantics:

1. **Same-attempt immutable identity:** before `PaperExecutionRepository.apply_result()`
   or equivalent result application can change durable projection state, prove
   `result.instruction` is the exact immutable durable attempt. Compare every
   execution-relevant frozen fact, not only `attempt_id`, including instruction,
   canonical Strategy/receipt evidence, Risk authority, account, instrument,
   direction, quantity, entry price, Stop, correlation IDs, precision, and
   applicable timing/provenance. A same-ID changed quantity, price, Stop,
   direction, account, instrument, Strategy evidence, Risk authority,
   correlation, or precision must raise the bounded durable identity conflict
   and make no projection change. Add the validator's changed-quantity probe as
   permanent regression coverage.

2. **Protection attribution:** never treat a structurally valid
   `ProtectionConfirmation` as attempt truth without strict attribution. Stop
   facts must match the durable attempt's expected deterministic client Stop ID,
   Trade, exact Strategy Stop price, type, provider state, and all applicable
   persisted Fill/account/instrument/units facts. Take Profit facts must match
   the expected deterministic client Take Profit ID, Trade, exact persisted
   actual-fill-derived target, type, provider state, and applicable durable
   facts. `FILLED_PROTECTED` is impossible unless both exact legs belong to the
   attempt. Add the unrelated-client/price-9.98 negative probe permanently.

3. **MARKET_ORDER_REJECT recovery:** the bounded numeric OANDA Transaction-ID
   range path must recognize and strictly attribute supported
   `MARKET_ORDER_REJECT` evidence even when no Order resource exists. Resolve to
   `REJECTED` only when the reject is attributable to the original attempt under
   frozen identity/lineage rules; otherwise remain unresolved/conflicted.

4. **Cancellation attribution:** an UNKNOWN entry may become `CANCELLED` only
   from supported attributable broker cancellation proof. Support exact
   Order/exact Transaction and bounded range create/cancel lineage as applicable.
   Do not classify from transaction type or Order state alone; unknown-entry
   range cancellation must be attributable to the discovered original Order
   identity and required lineage.

5. **Provider fact attribution:** tighten normalized OANDA response, Order, and
   Transaction facts so every applicable provider-supplied frozen identity fact
   is checked before conclusions: account, `EUR_USD`, client Order identity,
   client Trade identity, signed requested units, `MARKET`, `FOK`, `OPEN_ONLY`,
   exact `priceBound`, expected Stop-on-Fill identity/price, Order/Transaction/
   batch relationships, and returned IDs/frontiers. Never invent unavailable
   facts. Malformed, absent, contradictory, or mismatched facts remain
   unresolved/conflicted. Add regressions for transaction-ID mismatch, request
   field mismatch, and terminal order-lineage mismatch.

6. **Known-Fill Trade verification:** before a known-Fill Trade read can produce
   `CONSISTENT`, `FILLED_PROTECTED`, or `LIFECYCLE_ADVANCED`, strictly attribute
   the Trade to the immutable Fill/attempt. Validate applicable provider facts:
   account, instrument, broker Trade ID, client Trade ID, signed units, and
   entry price. Mismatched identity, units, price, or returned Trade ID must not
   advance lifecycle truth. Add permanent mismatch regressions.

7. **Closed Trade attribution:** a provider Trade `CLOSED` state is not enough
   for `LIFECYCLE_ADVANCED`. Prove exact durable attempt/Fill Trade attribution
   first, then advance only reconciliation status. Preserve historical execution
   outcome and Fill unchanged. Unattributed/mismatched closed Trade is
   unresolved/conflicted. Add the validator's negative regression.

8. **Contradictory Fill versus reject/cancel:** when attributable Fill exists
   alongside contradictory attributable reject or cancel evidence, retain the
   durable Fill, retain old reject/cancel observations, append new observations,
   advance execution truth to a filled outcome when supported, and set
   reconciliation status `CONFLICT`. Never let a no-Fill conclusion hide broker
   exposure. Add permanent Fill+reject and Fill+cancel regressions.

9. **Transaction frontier monotonicity:** parse OANDA Transaction IDs
   numerically. Persist an applied attempt frontier only after validated
   observations and only when `new_applied_frontier >= current_applied_frontier`.
   Stale reads may be evidence but must not regress `last_applied_transaction_id`
   or newer projection truth. Add explicit two-pass regression coverage.

10. **Transaction-range provenance:** preserve bounded provider provenance that
    OANDA supplies, including applicable RequestID, transaction IDs, batchID,
    related transaction lineage, `lastTransactionID`, Atlas observation time,
    and provider transaction time. Do not collapse range results so batch/related
    attribution needed for later conclusions is lost. Keep normalized facts
    bounded/whitelisted; never store raw bodies or unbounded text. Add range
    batch/related provenance regression.

11. **404 RequestID:** when a read requester receives a provider RequestID on a
    404/error response, preserve it through the bounded read metadata/error seam.
    Do not fabricate a RequestID when none is supplied. Add supplied and absent
    RequestID coverage without architectural expansion.

## Affected implementation seams

- `backend/paper/reconciliation.py`
- `backend/paper/persistence_contracts.py` only where the narrow typed contract requires it
- `backend/persistence/paper_execution_repository.py` only where frontier/contradiction/application guards require it
- `backend/integrations/oanda/reconciliation.py`
- `backend/integrations/oanda/request.py`
- directly affected OANDA read metadata/account normalization modules only
- focused deterministic tests under `backend/tests/paper/`, `backend/tests/integrations/`, and repository integration tests where needed

## Explicit out-of-scope items

- No PLAN or ARCHITECTURE reopening or redesign.
- No PAPER activation, runtime loop, scheduler, background worker, automatic Strategy cadence, automatic mutation retry, entry resubmission, Stop/Take Profit repair/resubmission, cancel/close/reduce operations, LIVE, general broker abstraction, multi-account, multi-instrument, or PAPER accounting/PnL.
- No unbounded transaction scanning, global OANDA transaction cursor, or provider raw-body/secret persistence.
- No real OANDA mutation or capital-capable credential use.
- Do not alter historical Experiment semantics, Strategy/Risk policy, PAPER 04 mutation semantics, immutable Fill truth, permanent mutation claims, or R001/R002 evidence.
- Do not weaken frozen invariants merely to accept an incomplete or malformed fixture.

## Regression evidence required

First rerun every deterministic negative probe that caused the current block. All
must pass. Then add/verify permanent deterministic coverage for:

- same-ID immutable result conflict with unchanged projection;
- strict Stop and Take Profit attribution;
- attributable `MARKET_ORDER_REJECT` recovery without an Order resource;
- UNKNOWN cancellation attribution through approved lineage paths;
- provider Order/Transaction identity/request-field mismatches;
- known-Fill Trade identity/units/price mismatches;
- unattributed `CLOSED` Trade;
- Fill + reject and Fill + cancel conflicts with Fill non-erasure;
- numeric transaction frontier non-regression;
- range batch/related provenance retention;
- supplied and absent 404 RequestID behavior.

Run focused affected PostgreSQL repository/concurrency/constraint tests, then the
focused PAPER persistence/reconciliation and migration suites. Because execution
truth and persistence authority are affected, after focused checks pass run:

```text
pytest -m 'not integration and not external'
```

plus changed-slice Ruff, Pyright, Alembic checks, and `git diff --check`.

No external OANDA mutation test is permitted.

## Worker Evidence

### Implementation receipt

R003 is implemented within the frozen PAPER 05 persistence and read-only
reconciliation seams. The remediation does not add mutation capability,
resubmission, runtime activation, scheduling, repair, or provider raw-body
persistence.

- `PaperExecutionRepository.apply_result()` verifies the presented immutable
  instruction facts before projection changes, including quantity, prices,
  direction, account/instrument, timing/provenance, precision, Risk decisions,
  and deterministic correlations. Same-attempt changed facts raise
  `PaperIdentityConflict`.
- Provider-neutral reconciliation now strictly attributes Stop/Take Profit
  facts, known-Fill Trade facts, closed Trade lifecycle evidence, and
  Fill-versus-reject/cancel contradictions. Fill evidence is retained and
  contradictions resolve to explicit `CONFLICT` rather than hiding exposure.
- OANDA normalization now validates exact Order/Transaction/Trade identity,
  request fields, order/transaction lineage, supported
  `MARKET_ORDER_REJECT` recovery, and bounded create/cancel recovery. Malformed,
  missing, contradictory, or mismatched provider facts remain unresolved or
  conflicted.
- Transaction frontiers are parsed numerically and applied monotonically.
  Bounded range observations retain whitelisted batch, related-transaction,
  request, frontier, Atlas-observation-time, and provider-transaction-time
  provenance.
- OANDA observation errors preserve a supplied 404 `RequestID` without storing
  provider response bodies; absent IDs remain `None`.
- Durable result application passes the immutable durable attempt identity into
  the repository seam, and frontier persistence cannot regress a newer applied
  frontier.
- Added deterministic regression coverage for every T003 finding, using local
  fakes and `httpx.MockTransport` only.

### Checks and evidence

- Focused R003/PAPER/OANDA suite:
  `uv run pytest -q backend/tests/paper/test_reconciliation.py
  backend/tests/integrations/test_oanda_reconciliation.py
  backend/tests/paper/test_durable_execution.py
  backend/tests/paper/test_persistence_contracts.py
  backend/tests/integrations/test_oanda_entry_mutation.py
  backend/tests/integrations/test_oanda_request.py` — **102 passed**.
- Broad safe backend suite:
  `uv run pytest -q -m "not integration and not external"` — **963 passed,
  4 skipped, 97 deselected**, four existing warnings.
- Dedicated PostgreSQL repository suite using the configured
  `paper05_validation` schema — **9 passed**.
- With `ATLAS_DATABASE_URL` directed to the dedicated test URL,
  `uv run alembic current` reported `0022_paper_persistence (head)` and
  `uv run alembic check` reported **No new upgrade operations detected**.
- Changed-slice Ruff format/check — passed; changed-slice Pyright — **0
  errors, 0 warnings, 0 informations**.
- `git diff --check` — passed.
- No real OANDA call, credential use, broker mutation, PAPER activation, runtime
  operation, or capital-capable action occurred.

### Concerns

- Four broad-suite skips and four existing warnings remain documented test-suite
  conditions; no R003 PRODUCT or REGRESSION concern is known from BUILD checks.
- Fresh VALIDATE and REVIEW contexts are still required by the workstream plan.

## Completion Receipt

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R003-paper-05-attribution-frontier-provenance/BUILD.md`
FILES CHANGED: `backend/paper/reconciliation.py`, `backend/paper/persistence_contracts.py`, `backend/paper/durable_execution.py`, `backend/persistence/paper_execution_repository.py`, `backend/integrations/oanda/reconciliation.py`, `backend/integrations/oanda/request.py`, `backend/integrations/oanda/source.py`, `backend/tests/paper/test_reconciliation.py`, `backend/tests/integrations/test_oanda_reconciliation.py`, `backend/tests/integrations/test_oanda_request.py`, `backend/tests/paper/test_durable_execution.py`, and this BUILD artifact
CHECKS / EVIDENCE: Focused 102 passed; broad safe backend 963 passed, 4 skipped, 97 deselected; dedicated PostgreSQL repository 9 passed; Alembic current/check passed at 0022_paper_persistence head; Ruff/Pyright passed; git diff --check passed; deterministic MockTransport/fake-only evidence; no broker mutation or capital-capable action.
FINDINGS / CONCERNS: The approved T003 findings are addressed in the implementation and covered by deterministic regressions. Four existing warnings and four broad-suite skips remain; fresh VALIDATE and REVIEW are required. Prior T003, R001, and R002 evidence artifacts were not edited.
