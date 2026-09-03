# PLAN — PAPER 05 Persistence + Reconciliation

## Workstream state

- **Workstream:** `paper-05-persistence-reconciliation`
- **Outcome:** Establish the smallest trustworthy OANDA Practice PAPER capability that durably records one PAPER execution attempt, the exact Strategy/Risk authority that produced it, and its broker-confirmed facts, then provides bounded read-only reconciliation that can re-inspect uncertain or protection-incomplete execution truth without resubmitting, repairing, or retroactively rewriting what PAPER 04 proved.
- **Classification:** `Critical`
- **Base:** `main` at `7a3204c41a394172752ab64b8aeab3f8fbcccf5e` (`Close PAPER 04 workstream`)
- **Base SHA:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Phase:** `COMPLETED`
- **Approval:** terminal closure, merge, and GitHub push explicitly authorized in the current request
- **Architecture:** `FROZEN` for approval review; `ARCHITECTURE.md` is canonical with this PLAN
- **Task state:** `T001` `DONE_WITH_CONCERNS`; `R001` `DONE_WITH_CONCERNS` with validation/review `PASS`; `T002` `DONE_WITH_CONCERNS` with validation/review `PASS`; `R002` `DONE` with validation/review `PASS`; `T003` `DONE_WITH_CONCERNS`; validation `FAIL`; `R003` `DONE`; validation `FAIL`; `R004` `DONE`; validation `PASS`; review `PASS`
- **Next action:** workstream closed; preserve all immutable task, validation, review, and remediation evidence; no R005 created.
- **Concerns:** This crosses durable financial truth, migration/constraint/concurrency behavior, broker authority, restart recovery, and the first durable boundary around capital-capable PAPER execution. Existing Experiment persistence is historical-only and must not be reused as PAPER broker truth. No broker mutation, automatic recovery mutation, runtime activation, PAPER scheduling, closing/reducing exposure, or protective-order repair is authorized by this workstream. The workstream-wide two-remediation-return cap remains exhausted. The developer has authorized exactly one narrow post-cap R004 chain for this approved-scope PRODUCT defect; if R004 VALIDATE or REVIEW finds any Critical or Important PRODUCT defect, stop and report that exact finding without creating R005.

## 1. Repository-grounded starting point

PAPER 04 is closed on the requested base. The current implementation has a one-shot, in-memory composition boundary:

```text
StrategyDecision
  → fresh OANDA Practice reads
  → fresh PAPER Risk evaluation
  → immutable PaperExecutionInstruction
  → one non-retrying entry mutation
  → broker-confirmed Fill/protection facts
  → PaperExecutionResult
```

The current `PaperExecutionInstruction` carries the allocated `attempt_id`, Strategy proposal, OANDA Practice/USD account identity, EUR/USD direction and quantity, Risk entry/stop facts, PRE_FLIGHT and PRE_SUBMISSION decisions, observation provenance, provider precision, and deterministic execution correlation.

`ExecutionCorrelation` derives stable client identities from `attempt_id`:

```text
client_order_id
client_trade_id
client_stop_loss_order_id
client_take_profit_order_id
```

The current `PaperExecutionResult` distinguishes:

```text
FILLED_PROTECTED
FILLED_PROTECTION_INCOMPLETE
REJECTED
CANCELLED
UNKNOWN
```

and retains broker Fill facts, independent Stop/Take Profit facts, rejection/uncertainty, transaction provenance, and bounded diagnostics in memory only.

`PaperExecutionApplication` explicitly has no persistence or durable retry state. It currently accepts a `StrategyDecision` and `RiskConfig`, performs fresh account/instrument/pricing reads and exactly one `evaluate_paper_risk(...)`, then immediately crosses the entry mutation boundary.

The current PAPER Strategy evaluation path is separately able to prove the exact persisted `StrategyVersion` and validate the exact parameter values before producing a `StrategyEvaluation`. However, the returned `StrategyEvaluation` contains only the decision and next Strategy state. `StrategyDecision` itself deliberately does not contain StrategyVersion identity or parameter provenance.

Therefore PAPER 05 must not accept an independently supplied Strategy provenance sidecar beside an arbitrary `StrategyDecision`. The durable capital-capable path must retain a Strategy evaluation receipt produced by the same validated PAPER Strategy evaluation boundary that produced the decision.

The current PAPER Risk composition has more explanatory evidence than `PaperExecutionInstruction` alone retains. In particular, Risk sizing depends on:

```text
RiskConfig.risk_per_trade
account equity
financial exposure state
Strategy entry/stop/target geometry
required-side executable prices and capacities
selected executable candidate
PRE_FLIGHT decision
PRE_SUBMISSION decision
observation provenance
```

PAPER 05 must durably retain a bounded canonical snapshot of the exact fresh Risk authority/evidence used for the mutation. This is evidence of the original Risk decision, not durable authority to mutate again.

Existing OANDA read-only seams relevant to reconciliation include:

```text
OandaPracticeEntryReadbackReader
  read_order_by_client_id()
  read_transaction()
  read_trade()

OandaProtectionReadbackReader
  read_trade()

OandaPracticeExecutionAccountReader
  one full Account Details snapshot with Trades, Positions, pending Orders,
  counts, account identity, and lastTransactionID
```

PAPER 05 also requires one narrowly bounded OANDA transaction-range read seam for recovery cases where the entry mutation may have reached OANDA but no exact Order resource is available. OANDA exposes numeric Transaction IDs and a bounded:

```text
GET /v3/accounts/{accountID}/transactions/idrange
```

read. PAPER 05 may use that endpoint only within an explicit finite range anchored to the pre-entry account transaction frontier. It must not introduce open-ended polling or an unbounded `sinceid` recovery loop.

The existing `OandaObservationRequester` remains GET-only and safely retrying. The existing mutation requester remains separate, non-retrying, and at-most-once.

The current database contains historical Strategy, Experiment, TradeIntent, RiskDecision, Order, Fill, Position, Trade, and event models. Those models and their append-only/terminal guards describe deterministic historical simulation and are not a PAPER broker ledger. No PAPER persistence tables, repositories, migrations, runtime loop, activation path, or reconciliation service exist on `main`.

## 2. Reconciled capability

The smallest trustworthy vertical slice is a PAPER-specific durable execution ledger around PAPER 04 plus explicit bounded read-only reconciliation:

```text
validated PAPER Strategy evaluation receipt
        ↓
fresh P04 account/instrument/pricing reads
        ↓
exactly one fresh PAPER Risk evaluation
        ↓
durable immutable Strategy + Risk + instruction evidence
+
permanent ENTRY mutation claim
        ↓ commit
one P04 entry POST at most once
        ↓
durable normalized broker observations
+
durable execution outcome
        ↓
if Fill proven:
durable Fill first
        ↓
Stop confirmation + actual-fill target derivation
        ↓
durable actual target + permanent TAKE_PROFIT claim
        ↓ commit
one dependent Take Profit PUT at most once
        ↓
durable normalized broker observations
+
durable execution outcome
        ↓
explicit bounded reconciliation when requested
        ↓
read-only OANDA observations
        ↓
append-only reconciliation run
+
guarded execution-resolution update when new proof exists
```

The durable identity of one logical execution attempt is the existing PAPER `attempt_id`.

Its deterministic PAPER 04 client correlations are durable aliases of that identity, not replacement identities.

A restart or reconciliation pass must load the same attempt and reuse only its original correlation. It must never allocate a replacement identity for the purpose of resubmitting an uncertain entry or Take Profit mutation.

### Strategy methodology binding

PAPER 05 adds a provider-neutral immutable Strategy evaluation receipt produced by the verified PAPER Strategy evaluation path.

The receipt contains at minimum:

```text
exact StrategyVersion identity
strategy source fingerprint
implementation key
canonical validated parameter snapshot
StrategyEvaluation
analytical frontier / decision time already represented by the evaluation
```

The durable PAPER execution coordinator accepts this receipt, not an arbitrary:

```text
StrategyDecision + unrelated provenance sidecar
```

The executed `StrategyDecision` is always:

```text
receipt.evaluation.decision
```

The referenced persisted StrategyVersion is reloaded and verified before the mutation claim.

This preserves the existing meaning of `StrategyDecision`; it does not add execution concerns to the Strategy contract.

The receipt is evidence only. Persisting `next_state` does not create PAPER runtime/resumption authority in PAPER 05.

### Risk authority binding

The same fresh `PaperRiskEvaluation` used to construct the PAPER 04 instruction must produce a bounded immutable `PaperRiskAuthoritySnapshot`.

It retains enough normalized evidence to explain and reproduce the original sizing decision, including:

```text
RiskConfig
normalized account equity/base-currency facts used by Risk
financial exposure state used by Risk
PRE_FLIGHT decision
PRE_SUBMISSION decision
required-side executable-pricing evidence
selected executable price/capacity
observation provenance
```

The snapshot must be built from the already-computed fresh Risk composition.

PAPER 05 must not call Risk a second time to create persistence evidence.

If the exact bounded Strategy/Risk/instruction evidence cannot be serialized before the mutation claim, execution refuses before any broker mutation becomes possible.

### Mutation truth

PAPER 05 uses two permanent mutation claims:

```text
ENTRY
TAKE_PROFIT
```

A claim is committed before the corresponding broker mutation is allowed.

The claim means only:

> From this durable point onward, that broker mutation may have been dispatched and therefore must never be automatically submitted again.

It does **not** prove that the HTTP request reached OANDA, left the process, or was accepted.

A crash after the claim but before the HTTP call is therefore intentionally conservative: the mutation remains uncertain and only read-only reconciliation is permitted.

The claim is permanent, has no lease, does not expire, and is not reacquired.

### Execution outcome versus current broker lifecycle

The five PAPER 04 outcomes remain the resolution of the **original execution/protection attempt**:

```text
FILLED_PROTECTED
FILLED_PROTECTION_INCOMPLETE
REJECTED
CANCELLED
UNKNOWN
```

They are not a general current-Trade lifecycle state.

In particular:

```text
FILLED_PROTECTED
```

means Atlas proved at the relevant execution/protection readback that the Fill existed and both intended protections were pending and exact.

If that Trade later closes naturally or protection later changes, PAPER 05 must not rewrite history by downgrading the original execution outcome.

Current reconciliation status is therefore represented separately from the five execution outcomes.

A later broker read may establish:

```text
CONSISTENT
UNRESOLVED
CONFLICT
LIFECYCLE_ADVANCED
```

without changing what the original execution attempt previously proved.

An initially `UNKNOWN` or `FILLED_PROTECTION_INCOMPLETE` attempt may advance to a more definite execution outcome when later broker proof establishes what actually happened.

A proven Fill is never erased.

## 3. Required architectural decisions

`ARCHITECTURE.md` resolves, using current code and provider semantics rather than roadmap assumptions:

- the exact Strategy evaluation receipt that binds the executed `StrategyDecision` to the persisted StrategyVersion and canonical parameter values that produced it;
- the exact bounded Risk authority snapshot required to explain fresh Risk sizing without calling Risk twice;
- the minimum durable PAPER facts required before and immediately after each PAPER 04 mutation boundary;
- the exact durable identity and uniqueness rules for an execution attempt;
- the distinction between:

  - immutable Strategy/Risk/instruction evidence;
  - permanent possible-mutation claims;
  - immutable normalized broker observations;
  - durable execution outcome;
  - current reconciliation status;

- a PAPER-specific schema/model/repository boundary that does not reuse historical Experiment `Order`, `Fill`, `Trade`, accounting, or result contracts;
- valid execution-outcome advancements without converting the five PAPER 04 outcomes into a Trade lifecycle state;
- the bounded read-only OANDA reconciliation sequence for:

  - an uncertain entry;
  - a lost mutation response;
  - a known Fill;
  - a protection-incomplete attempt;
  - a previously protected attempt whose Trade has since advanced in its lifecycle;

- the narrowly bounded OANDA transaction-ID range recovery seam required when exact Order lookup cannot expose a lost reject/create/fill/cancel transaction;
- retained provider request IDs, transaction IDs, batch/related IDs, transaction frontiers, observation timestamps, and per-read provenance;
- how contradictory or un-attributable Atlas/broker facts fail closed without erasing previously proven Fill/execution truth;
- how durable state is committed around broker mutation boundaries without claiming database/broker atomicity;
- the explicit pre-Take-Profit seam needed to commit the actual-fill-derived target and TAKE_PROFIT claim before the dependent PUT;
- the exact validation matrix, including PostgreSQL migration, append-only guards, concurrency, stale reconciliation, restart, and commit-boundary evidence;
- the PAPER 06 boundary: no runtime loop, scheduler, activation, resumption policy, automatic recovery mutation, protective-order repair, LIVE, or autonomous account management.

## 4. Initial scope boundary

In scope:

```text
OANDA Practice
one configured USD account
EUR_USD
PAPER 04 IMMEDIATE OPEN_LONG/OPEN_SHORT execution
Strategy evaluation receipt for exact version/parameter/decision provenance
fresh Risk authority snapshot
durable attempt identity
permanent ENTRY and TAKE_PROFIT mutation claims
durable normalized broker Order/Transaction/Trade/account observations
durable proven Fill and independent Stop/Take Profit facts
the five existing PAPER 04 execution outcomes
separate reconciliation status
bounded exact-Order / exact-Transaction / exact-Trade / Account Details reads
bounded Transaction-ID-range recovery
restart-safe no-resubmit behavior
fail-closed conflict/uncertainty handling
PAPER-specific SQLAlchemy models, repository, migration, and tests
```

Out of scope unless the architecture proves a narrow prerequisite inseparable from the above:

```text
continuous runtime loop
scheduler
automatic Strategy evaluation cadence
PAPER activation or activation UI/API
trader start/stop controls
background workers
LIVE
credential-management changes
general broker abstraction
multi-account or multi-instrument support
automatic recovery mutation
automatic protective-order repair
closing or reducing exposure
partial-fill or multi-fill accounting
closed-Trade accounting
PAPER PnL/accounting
historical Experiment semantic changes
historical Order/Fill/Trade reuse
unbounded transaction synchronization
global broker reconciliation cursor
```

## 5. Reconciled acceptance criteria

The final acceptance matrix must prove at minimum that:

1. The durable capital-capable path cannot execute a `StrategyDecision` independently paired with unrelated StrategyVersion/parameter provenance. The persisted receipt binds the executed decision to the exact verified PAPER Strategy evaluation that produced it.
2. The exact fresh Risk assumptions and evidence needed to explain sizing—including current `RiskConfig.risk_per_trade`, account equity/exposure facts, executable pricing/capacity evidence, PRE_FLIGHT, PRE_SUBMISSION, and observation provenance—are durable without a second Risk evaluation.
3. A unique attempt and permanent `ENTRY` mutation claim are durably committed before a possible entry POST. Duplicate invocation, restart, concurrent callers, or uncertain transport cannot obtain a second entry mutation permission.
4. A mutation claim is represented truthfully as a possible-mutation barrier, not false proof that OANDA received or processed a request.
5. A confirmed Fill is committed before any dependent Take Profit mutation can occur. Fill price, quantity, initial risk, broker Order ID, Fill transaction ID, and Trade ID can never be erased by later `UNKNOWN`, rejection, cancellation, reconciliation failure, or lifecycle advancement.
6. Stop Loss and Take Profit facts remain independent. `FILLED_PROTECTION_INCOMPLETE` always retains known Fill/exposure truth and never means that entry exposure is unknown.
7. The actual-fill-derived target and permanent `TAKE_PROFIT` mutation claim are durably committed before the one dependent PUT. Restart or uncertain transport can never produce an automatic second PUT.
8. The five PAPER 04 outcomes remain execution-resolution facts. A later naturally closed Trade or changed broker lifecycle does not retroactively downgrade a previously proven `FILLED_PROTECTED` execution result.
9. Reconciliation status is separate and can represent `CONSISTENT`, `UNRESOLVED`, `CONFLICT`, or `LIFECYCLE_ADVANCED` without falsifying prior execution truth.
10. A bounded reconciliation pass can re-inspect `UNKNOWN` using the original client correlation and read-only OANDA seams. When exact Order lookup cannot expose a lost entry result, one finite transaction-ID range anchored to the original pre-entry frontier may be inspected. No absence alone proves rejection or cancellation.
11. A matching OANDA reject/cancel/fill transaction is accepted only with strict attempt attribution. Unrecognized, truncated, stale, contradictory, or unattributable reads remain unresolved or conflicted.
12. Known Fill/protection can be re-read without treating separate GETs as one atomic broker snapshot. Previously protected Trades that are now closed or otherwise outside the narrow open-Trade model are recorded as lifecycle advancement rather than rewritten as execution failure.
13. Existing historical Experiment, Strategy methodology, Risk authority, OANDA mutation semantics, runtime, API/UI, activation, and LIVE behavior remain semantically unchanged.
14. PostgreSQL upgrade/downgrade/upgrade, append-only guards, mutation-claim uniqueness, immutable attempt evidence, Fill non-erasure, outcome guards, reconciliation concurrency/staleness behavior, deterministic OANDA fixtures, focused tests, and broad safe regressions provide evidence appropriate to this Critical slice.
15. All validation uses deterministic fakes, normalized fixtures, and `httpx.MockTransport`; no real OANDA Practice mutation, PAPER activation, LIVE operation, or capital-capable credential use is permitted.

## 6. Approval and remediation state

Architecture reconciliation remains complete and `ARCHITECTURE.md` remains frozen.

The existing PAPER 05 branch is the execution source of truth. The workstream-wide
remediation-return cap is exhausted, but the developer has explicitly authorized
exactly one narrow post-cap R004 correction for the approved-scope PRODUCT finding
in the immutable R003 `VALIDATION.md` receipt. This authorization does not reopen
the PLAN or ARCHITECTURE and does not authorize R005.

R004 must preserve the existing persistence transition contract permitting
`REJECTED`/`CANCELLED` to advance to a filled outcome when later broker-authoritative
Fill proof exists. It adds only the missing historical contradiction status/finding
and its deterministic regression coverage.
