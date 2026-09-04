# PLAN — Dogfood 01 Lifecycle-Advanced Activation Fence

## Workstream state

- **Workstream:** `dogfood-01-lifecycle-advanced-activation-fence`
- **Classification:** `Critical`
- **Status:** `READY_FOR_USER`
- **Phase:** `READY_FOR_USER`
- **Base:** `main` at `bc53f70d0afdcbbc728d54d48df5370da0f2238e` (`Close Dogfood 01 Trade identity workstream`)
- **Base SHA:** `bc53f70d0afdcbbc728d54d48df5370da0f2238e`
- **Branch:** `solo/dogfood-01-lifecycle-advanced-activation-fence`
- **Architecture:** `FROZEN`; `ARCHITECTURE.md` is reconciled and approval-ready
- **Task state:** T001 `DONE_WITH_CONCERNS`; original validation `PASS`; original review `FAIL`; R001 `DONE_WITH_CONCERNS` with validation `PASS` and review `FAIL`; R002 `DONE_WITH_CONCERNS` with validation `PASS` and review `PASS`; remediation-return cap satisfied
- **Next action:** explicit developer merge approval; do not merge before approval
- **Approval:** implementation explicitly approved by the developer; GIT START completed from `main` at the recorded base SHA; R001 and R002 were approved-scope defect remediations; merge approval is pending; no activation, runtime start, credential use, or broker mutation authorized

## Outcome

Design the smallest trustworthy recovery seam that permits a new explicitly approved
`FRESH_BOOTSTRAP` PAPER session after a prior filled PAPER Trade has been durably recorded
as `FILLED_PROTECTION_INCOMPLETE` and later authoritatively reconciled to
`LIFECYCLE_ADVANCED`, without rewriting historical execution truth and without weakening
the existing fresh provider/account/flatness, Risk, ownership, claim, or no-retry gates.

This is a Critical Dogfood 01 remediation workstream. It is **not PAPER 07**.
Dogfood 02 has **not started**, no Dogfood 02 activation may be created or retried during
this workstream, and the prior Dogfood 02 approval is not automatic authority after this
capital-safety rule changes.

## Historical execution truth to preserve

The demonstrated Dogfood 01 execution attempt is:

```text
9530bab6-fea0-4f86-aa65-bbc9e1f1759a
```

Its permanent meaning is:

```text
entry filled at OANDA Practice
→ Stop existed at OANDA
→ Atlas failed to complete/prove protection under the then-current Trade identity contract
→ no Take Profit was submitted
→ runtime blocked with EXECUTION_UNCERTAIN
→ trader manually closed the Trade
→ later GET-only reconciliation observed the exact attributable Trade as CLOSED
→ reconciliation_status became LIFECYCLE_ADVANCED
```

The durable `execution_outcome` remains `FILLED_PROTECTION_INCOMPLETE`.

This workstream must not convert it to `FILLED_PROTECTED`, erase or alter its Fill,
invent a Take Profit, reinterpret manual closure as Atlas protection success, delete or
rewrite observations/claims/reconciliation evidence, or infer current account flatness
from `LIFECYCLE_ADVANCED`.

The current configured OANDA Practice account was independently observed after closure
with zero open Trades, zero open Positions, and zero pending Orders. That is historical
operator evidence only. A future activation must re-prove current account safety through
the existing runtime startup account gate.

## Current-main contract inspected

Current main is `bc53f70`.

The closed PAPER 05 and PAPER 06 contracts establish:

- `FILLED_PROTECTION_INCOMPLETE` is historical execution/protection truth and is not
  rewritten by later lifecycle observations.
- Provider-neutral reconciliation returns `LIFECYCLE_ADVANCED` for a durable Fill only
  after the provider Trade read is attributable, matches the persisted Trade/Fill context,
  and reports that exact Trade as `CLOSED`.
- `LIFECYCLE_ADVANCED` does **not** prove current account flatness, which exit occurred,
  realized PnL, or protection success.
- `is_unsafe_paper_attempt()` is intentionally strict. It currently treats only
  `REJECTED`, `CANCELLED`, and `FILLED_PROTECTED` with a safe reconciliation status as
  non-blocking. It is also used by interrupted-claim recovery and therefore must not be
  relaxed globally.
- `PaperRuntimeService.activate()` is local durable control. It validates configuration,
  StrategyVersion/registry/parameters, and local history before creating `REQUESTED`; it
  does not call OANDA.
- `PaperRuntimeOrchestrator` separately proves provider capability, configured account
  identity, and fresh full account state before a fresh activation reaches `RUNNING`.
- `PaperRuntimeAccountObservation` enforces that `FLAT` is coherent with zero open Trade
  and Position counts. Fresh bootstrap separately requires zero pending Orders.
- Every opening still passes through P05 fresh account/instrument/pricing reads and one
  fresh Risk evaluation before the permanent ENTRY claim and one-shot mutation.
- New activations are `FRESH_BOOTSTRAP`; terminal prior sessions do not donate Strategy
  state or mutation authority.
- A protection-incomplete execution blocks its current activation. Later reconciliation
  must never revive that same blocked activation.

## Reconciled architecture decision

The smallest trustworthy product rule is **semantic, not incident-ID-specific**.

The Dogfood attempt UUID remains incident evidence and may be used in regression fixtures,
but production eligibility must not special-case that UUID.

Introduce a separate **new-session history** decision while keeping the existing strict
attempt/recovery predicate unchanged.

For a prior attempt in the configured supported account/scope, the local history may stop
fencing creation and operation of a **new explicitly approved FRESH_BOOTSTRAP session**
when either:

```text
A. existing safe terminal case:
   execution_outcome ∈ {REJECTED, CANCELLED, FILLED_PROTECTED}
   reconciliation_status ∈ {NOT_RUN, CONSISTENT, LIFECYCLE_ADVANCED}

or

B. lifecycle-ended incomplete Fill:
   execution_outcome = FILLED_PROTECTION_INCOMPLETE
   reconciliation_status = LIFECYCLE_ADVANCED
   durable Fill identity is complete and coherent
   an applied reconciliation run exists for the lifecycle advancement
```

Any other unknown, unresolved, conflicted, null, malformed, unsupported, or incomplete
state remains a blocker.

This rule means only that the prior attempt no longer permanently fences a **new session**.
It does not make the prior attempt safe under `is_unsafe_paper_attempt()`, does not make
the prior attempt protected, and does not authorize mutation.

The current activation must remain terminal if it previously blocked on the incomplete
execution. Only a separately approved new activation may use the new-session rule.

## Design decisions

`ARCHITECTURE.md` freezes:

1. **No hardcoded incident UUID in production authority.** The demonstrated UUID is
   historical evidence only. Future identical durable evidence must have identical
   semantics without requiring another code deployment.
2. **Strict recovery remains strict.** `is_unsafe_paper_attempt()` and interrupted
   ENTRY/TAKE_PROFIT claim recovery remain unchanged.
3. **Separate new-session history rule.** Add a narrowly named repository/application
   classifier such as `has_new_session_blocker(...)` or equivalent. It is not a general
   replacement for `is_unsafe_paper_attempt()`.
4. **Activation POST remains local.** It may create only `REQUESTED` intent and must not
   call OANDA.
5. **Fresh startup remains authoritative for current broker state.** The new activation
   cannot become `RUNNING` until the existing capability and full account reads establish
   exact configured identity, coherent `FLAT`, zero open Trades, zero open Positions, and
   zero pending Orders.
6. **Current blocked activation is never revived.** A later
   `FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` observation cannot transition the
   old `BLOCKED` activation back into `STARTING` or `RUNNING`.
7. **Entry authority remains independent.** The runtime account observation, P05 fresh
   account/instrument/pricing reads, one fresh Risk evaluation, owner/generation fences,
   permanent ENTRY/TAKE_PROFIT claims, and no-retry semantics remain unchanged.
8. **No schema change is expected.** Existing attempt Fill fields and reconciliation
   projection/run fields are sufficient. If implementation cannot prove the semantic
   qualifier from current durable evidence without weakening a constraint, stop for
   architecture re-approval rather than adding a bypass flag.

## Required safety matrix

The architecture must explicitly classify future-session eligibility for at least:

```text
FILLED_PROTECTED + NOT_RUN
FILLED_PROTECTED + CONSISTENT
FILLED_PROTECTED + LIFECYCLE_ADVANCED

FILLED_PROTECTION_INCOMPLETE + NOT_RUN
FILLED_PROTECTION_INCOMPLETE + CONSISTENT
FILLED_PROTECTION_INCOMPLETE + UNRESOLVED
FILLED_PROTECTION_INCOMPLETE + CONFLICT
FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED with coherent durable Fill/reconciliation evidence
FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED with missing/contradictory durable evidence

UNKNOWN + NOT_RUN
UNKNOWN + CONSISTENT
UNKNOWN + UNRESOLVED
UNKNOWN + CONFLICT
UNKNOWN + LIFECYCLE_ADVANCED

REJECTED / CANCELLED with safe and unsafe reconciliation combinations
malformed, null, missing, or unsupported outcome/status values
```

The matrix must distinguish:

```text
local creation eligibility
fresh-bootstrap startup/RUNNING eligibility
same-activation recovery eligibility
new-entry eligibility
```

No row by itself proves current flatness or authorizes broker mutation.

## Scope

### In scope after approval

- A narrow semantic new-session history classifier for the demonstrated lifecycle-ended
  incomplete-Fill state.
- Minimal changes to activation creation and runtime account-history fencing needed for a
  new `FRESH_BOOTSTRAP` session to reach the existing startup/account gates.
- Preservation of strict same-attempt claim recovery.
- Deterministic tests for the complete outcome/reconciliation matrix, durable Fill
  qualifier, blocked-activation non-revival, startup/current-account safety, and affected
  runtime/P05 regressions.
- Broad safe backend validation appropriate to a Critical capital-safety gate.

### Explicitly out of scope

- PAPER 07.
- Dogfood 02 activation/retry or any automatic post-remediation capital authority.
- Hardcoding the demonstrated attempt UUID into production authority logic.
- Any OANDA mutation, manual broker repair, runtime start, PAPER activation, credential use,
  or real-account validation during planning, BUILD, validation, or review.
- Rewriting historical Dogfood rows, Fill facts, missing Take Profit facts, execution
  outcome, or reconciliation evidence.
- Treating `LIFECYCLE_ADVANCED` as current flatness, protection success, or generic recovery
  authority.
- Reviving the prior blocked activation.
- Bypassing provider capability, configured identity, fresh account, zero
  Trade/Position/pending-Order, fresh Risk, ENTRY, TAKE_PROFIT, owner/generation, or
  no-retry fences.
- Strategy changes, Risk policy redesign, provider abstraction, scheduler/daemon/
  distributed infrastructure, UI, LIVE, automatic repair/self-healing, reconciliation
  semantic weakening, general historical cleanup, or speculative schema work.

## Acceptance direction

The later implementation must prove, at minimum:

1. Dogfood 01 remains exactly `FILLED_PROTECTION_INCOMPLETE`; no later state manufactures
   `FILLED_PROTECTED`.
2. `LIFECYCLE_ADVANCED` is consumed only as evidence that the exact attributable filled
   Trade's lifecycle has ended; it is never current account flatness or protection proof.
3. Production logic contains no hardcoded Dogfood attempt UUID or account-specific bypass.
4. A synthetic future attempt with the same coherent durable semantics is classified the
   same way as the Dogfood attempt.
5. The strict shared `is_unsafe_paper_attempt()` behavior remains unchanged, including
   classifying `FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` as unsafe for
   same-attempt recovery.
6. A new-session history classifier permits the lifecycle-ended incomplete Fill only when
   durable Fill identity and applied reconciliation evidence are complete and coherent.
7. Any second unsafe attempt, `UNKNOWN`, `UNRESOLVED`, `CONFLICT`, null/malformed value, or
   incomplete state without authoritative lifecycle advancement still blocks.
8. Activation creation remains provider-free and persists only a new `REQUESTED`
   `FRESH_BOOTSTRAP` activation.
9. The original blocked activation cannot be revived by later reconciliation.
10. A new activation cannot reach `RUNNING` until existing startup capability and fresh
    full account facts prove exact identity, coherent FLAT state, zero open Trades, zero
    open Positions, and zero pending Orders.
11. A new entry cannot occur without the existing fresh current account/Risk/owner/claim
    gates; startup evidence and historical reconciliation are never mutation authority.
12. Existing `FILLED_PROTECTED`, `REJECTED`, `CANCELLED`, restart, STOP, frontier,
    ownership, claim, and no-retry behavior do not regress.
13. Validation is deterministic and provider-mutation-free.

## Validation direction

Focused tests first:

```bash
uv run pytest backend/tests/runtime/test_runtime_activation.py \
  backend/tests/runtime/test_runtime_orchestration.py \
  backend/tests/runtime/test_runtime_completion_cross_seam.py

uv run pytest backend/tests/paper/test_reconciliation.py
```

Focused coverage must include:

- complete new-session history truth table;
- strict generic predicate unchanged;
- no hardcoded UUID behavior;
- coherent Fill + applied `LIFECYCLE_ADVANCED` acceptance;
- malformed/missing Fill or reconciliation evidence rejection;
- multiple-attempt ledger where any blocker blocks;
- activation POST performs no provider read;
- old `BLOCKED` activation is not revived;
- fresh startup capability/account/flatness gate;
- P05 fresh account/Risk remains independent;
- owner/claim/restart no-retry regressions;
- mutation seams spied to prove zero POST/PUT/cancel/close/reduce/repair during this workstream.

Then run the appropriate Critical safe backend gates:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration and not external"
git diff --check
```

Run PostgreSQL integration/migration checks only as required by touched persistence seams and
the repo's normal Critical validation contract. No migration is expected; if a migration or
provider-neutral reconciliation semantic change becomes necessary, stop for architecture
re-approval before proceeding.

## Approval gate

This is a Critical workstream. Before explicit developer approval of the reconciled
`PLAN.md` and `ARCHITECTURE.md`, do not create `tasks/`, create or switch to a feature
branch, modify application or test code, start runtime, create an activation, use
credentials, or perform broker mutation.
