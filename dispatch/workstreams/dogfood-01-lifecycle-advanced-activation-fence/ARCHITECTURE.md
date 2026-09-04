# ARCHITECTURE — Dogfood 01 Lifecycle-Advanced Activation Fence

ROLE: `ARCHITECT`
WORKSTREAM: `dogfood-01-lifecycle-advanced-activation-fence`
BRANCH: `main` (pre-approval; no GIT START)
CWD: `/Users/vike/Desktop/atlas`
TASK: `NONE`
OWNED_ARTIFACT: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/ARCHITECTURE.md`
SPECIALIST_SKILLS: `none`

**Classification:** Critical  
**Status:** Approval-ready architecture; implementation is not authorized  
**Base inspected:** `main` at `bc53f70d0afdcbbc728d54d48df5370da0f2238e`

This document freezes the smallest trustworthy recovery seam for a new explicitly
approved `FRESH_BOOTSTRAP` PAPER session after a prior filled Trade has durably ended its
broker lifecycle while its original execution remains historically
`FILLED_PROTECTION_INCOMPLETE`.

It authorizes no implementation, task creation, branch creation, runtime start, PAPER
activation, credential use, OANDA mutation, historical repair, schema migration, or capital
authority before explicit developer approval of the reconciled `PLAN.md` and this document.

## 1. Decision in one paragraph

Dogfood 01 exposed a missing distinction between **same-attempt recovery safety** and
**whether a completed historical broker lifecycle must permanently fence every future
explicitly approved session**.

The existing strict `is_unsafe_paper_attempt()` remains unchanged and continues to classify
`FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` as unsafe for same-attempt recovery.
A separate new-session history rule may treat that pair as no longer permanently blocking
a new `FRESH_BOOTSTRAP` activation only when the durable Fill identity is complete and an
applied reconciliation proves `LIFECYCLE_ADVANCED`.

This rule is semantic and applies to any future attempt with the same authoritative durable
facts in the supported scope. The Dogfood attempt UUID is historical evidence only and must
not be hardcoded into production authority.

`LIFECYCLE_ADVANCED` is not flatness or protection proof. POST remains local and creates
only `REQUESTED`. A new activation reaches `RUNNING` only after existing provider
capability and fresh full-account reads prove the configured account is coherent and flat
with zero open Trades, zero open Positions, and zero pending Orders. Any opening still
requires the later independent P05 fresh account/instrument/pricing/Risk and permanent
claim gates.

The prior `BLOCKED` activation is never revived. Only a separately approved new activation
may use this new-session rule.

## 2. Repository-grounded current behavior

### 2.1 Strict durable-attempt predicate

`backend/persistence/runtime_repository.py` currently defines
`is_unsafe_paper_attempt()` so only:

```text
REJECTED
CANCELLED
FILLED_PROTECTED
```

combined with:

```text
NOT_RUN
CONSISTENT
LIFECYCLE_ADVANCED
```

are non-blocking. Incomplete, unknown, malformed, missing, unresolved, and conflicted
values remain unsafe.

This predicate is intentionally stronger than the new-session rule because interrupted
claim recovery relies on it.

### 2.2 Meaning of `LIFECYCLE_ADVANCED`

`backend/paper/reconciliation.py` returns `LIFECYCLE_ADVANCED` for a durable Fill only
after:

```text
provider read is valid
read is attributable
Trade identity matches the persisted Fill/context
Trade state == CLOSED
```

The original execution outcome is returned unchanged. Therefore:

```text
FILLED_PROTECTION_INCOMPLETE
+
LIFECYCLE_ADVANCED
```

means:

```text
Atlas still truthfully records incomplete original protection
AND
the exact attributable filled Trade is no longer OPEN
```

It does **not** mean the account is flat, which exit occurred, realized PnL is known, or
Atlas successfully protected the Trade.

### 2.3 Fresh startup authority

`backend/runtime/orchestration.py` performs startup as:

```text
owner acquisition
→ STARTING
→ strict interrupted-cycle/claim recovery
→ Strategy registry validation
→ provider capability read
→ current full account read
→ fresh-bootstrap FLAT / zero-pending gate
→ RUNNING
```

`PaperRuntimeAccountObservation` additionally enforces that `FLAT` is coherent with zero
open Trade and Position counts.

### 2.4 Fresh entry authority

A RUNNING session still requires a new cycle/account observation and then P05 independently
rereads account/instrument/pricing and evaluates Risk before the permanent ENTRY claim and
one-shot mutation.

These four meanings remain separate.

## 3. Immutable historical truth

The demonstrated attempt is:

```text
9530bab6-fea0-4f86-aa65-bbc9e1f1759a
```

Its permanent history is:

```text
entry filled at OANDA Practice
→ Stop existed
→ Atlas did not complete/prove protection
→ no Take Profit was submitted
→ execution_outcome = FILLED_PROTECTION_INCOMPLETE
→ runtime blocked with EXECUTION_UNCERTAIN
→ trader manually closed the Trade
→ later exact GET-only Trade reconciliation observed CLOSED
→ reconciliation_status = LIFECYCLE_ADVANCED
```

No implementation may:

- convert the outcome to `FILLED_PROTECTED`;
- remove or reinterpret the Fill;
- invent a Take Profit;
- claim Atlas performed the manual closure;
- erase observations, mutation claims, or reconciliation runs;
- infer current account flatness from the old Trade's closed lifecycle.

The Dogfood UUID may appear in incident documentation and regression data. It must not
appear as a production eligibility constant or branch condition.

## 4. Frozen semantic distinction

Atlas now recognizes two different questions.

### 4.1 Same-attempt recovery question

Question:

> Is this attempt safe enough to complete/recover the current claimed execution path?

Authority:

```text
is_unsafe_paper_attempt()
```

Rule:

```text
UNCHANGED
```

`FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` remains unsafe here.

Consequences:

- interrupted ENTRY/TAKE_PROFIT claim recovery remains strict and GET-only;
- no old claim becomes retryable;
- no blocked cycle is reopened;
- no blocked activation is revived;
- no reconciliation result creates mutation authority.

### 4.2 New-session history question

Question:

> Does this historical attempt still have to permanently prevent creation and operation
> of a separately approved, fresh session after its exact filled Trade lifecycle ended?

Authority:

a new narrowly named repository/application classifier, for example:

```text
has_new_session_blocker(session, account_id)
```

or equivalent.

This rule is not used by same-attempt recovery.

A historical row does **not** block a new session when it is either:

```text
existing safe terminal history:
  outcome ∈ {REJECTED, CANCELLED, FILLED_PROTECTED}
  reconciliation ∈ {NOT_RUN, CONSISTENT, LIFECYCLE_ADVANCED}
```

or:

```text
lifecycle-ended incomplete Fill:
  outcome = FILLED_PROTECTION_INCOMPLETE
  reconciliation = LIFECYCLE_ADVANCED
  durable Fill identity is complete
  applied lifecycle-advanced reconciliation evidence is present
```

Every other value blocks.

No attempt UUID is part of this semantic rule.

## 5. Required durable qualifier for lifecycle-ended incomplete Fill

`FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` is eligible for the new-session rule
only if existing durable evidence is coherent.

At minimum, the row must prove:

```text
provider = OANDA
environment = PRACTICE
provider_account_id = configured account
base_currency = USD
instrument = EUR_USD

execution_outcome = FILLED_PROTECTION_INCOMPLETE
reconciliation_status = LIFECYCLE_ADVANCED

fill_trade_id present
fill_signed_units present
fill_price present
fill_executed_at present

last_reconciliation_run_id present
last_reconciled_at present
reconciliation_block_code absent
```

The referenced/latest applied reconciliation evidence must be consistent with
`LIFECYCLE_ADVANCED`; implementation may use the existing applied projection plus its
linked run rather than invent a new persistence concept.

If current schema or repository constraints cannot prove this without ambiguity,
implementation must stop for architecture re-approval. Do not add a broad
`recovery_resolved`, allowlist UUID, environment toggle, or manual DB bypass.

This qualifier is defensive. Normal reconciliation already requires exact attributable
Trade identity before producing `LIFECYCLE_ADVANCED`; the new-session classifier must not
coerce malformed durable rows into that state.

## 6. Activation creation

Current path:

```text
PaperActivationHttpRequest
→ PaperActivationRequest
→ PaperRuntimeService.activate()
→ local configuration / StrategyVersion / registry / parameter validation
→ local account-history check
→ PaperRuntimeRepository.create_activation()
→ REQUESTED
```

The activation POST remains provider-free.

The only authority change is the local account-history check:

```text
strict current helper for same-attempt recovery:
  unchanged

new activation history check:
  use new-session classifier
```

A valid POST may persist `REQUESTED` if every attempt in the configured account is
new-session-safe under section 4.2.

If any attempt is:

```text
UNKNOWN
UNRESOLVED
CONFLICT
null
malformed
unsupported
FILLED_PROTECTION_INCOMPLETE without authoritative LIFECYCLE_ADVANCED
```

creation fails closed with the existing bounded activation error contract or a narrowly
equivalent safe code.

Exact same activation-request replay and same-ID identity conflict behavior remain
unchanged.

POST must not call:

```text
OANDA capability/account readers
pricing
Risk
reconciliation
entry POST
Take Profit PUT
cancel
close
reduce
repair
```

## 7. Fresh-bootstrap startup

Creation eligibility is not broker authority.

A new activation begins:

```text
state_origin = FRESH_BOOTSTRAP
strategy_state = null
lifecycle_state = REQUESTED
```

Startup remains:

```text
owner.try_acquire()
→ attach activation
→ STARTING
→ strict _recover_interrupted()
→ Strategy registry validation
→ startup capability read
→ fresh full account observation
→ bootstrap flatness gate
→ RUNNING
```

The runtime account-history fence used for a new session must understand the new-session
history rule so a lifecycle-ended historical incomplete Fill does not prevent the fresh
broker read.

That change must **not** alter `_recover_interrupted()`, which remains on the strict
same-attempt predicate.

For a fresh bootstrap, `RUNNING` requires:

```text
valid current owner / generation
exact activation and Strategy identity
successful OANDA Practice capability proof
configured account identity exact
fresh full account snapshot valid
financial_position_state = FLAT
open_trade_count = 0
open_position_count = 0
pending_order_count = 0
no local new-session blocker
```

`PaperRuntimeAccountObservation` already makes `FLAT` inconsistent with nonzero Trade or
Position counts.

Any current exposure, pending order, identity mismatch, malformed provider state,
contradiction, or unsupported account fails closed before `RUNNING`.

Transient pre-proof provider failure may remain `STARTING` under existing bounded retry
semantics. It never becomes speculative success.

## 8. Current activation non-revival

This invariant is mandatory:

```text
current activation executes
→ FILLED_PROTECTION_INCOMPLETE
→ activation BLOCKED
→ later reconciliation becomes LIFECYCLE_ADVANCED
```

must remain:

```text
activation BLOCKED
```

The new-session rule cannot transition that activation back to `STARTING` or `RUNNING`.

A new session requires:

```text
new activationRequestId
new explicit trader approval
FRESH_BOOTSTRAP
fresh provider/account proof
```

This is the key boundary that allows semantic reuse without weakening same-session
recovery.

## 9. RUNNING cycle and new entry

Even `RUNNING` is not entry authority.

Current entry path remains:

```text
completed frontier
→ fresh runtime account observation
→ owner-guarded cycle reservation
→ exact Strategy evaluation
→ FLAT / zero Trade / zero Position / zero pending gate
→ P05 prepare_entry_claim()
    → fresh account properties/full account/instrument/pricing reads
    → one fresh Risk evaluation
→ owner-guarded cycle/state/attempt/ENTRY claim commit
→ existing one-shot entry mutation
→ existing Fill/Stop/Take Profit barriers
```

The lifecycle-ended historical attempt only stops being a local **history blocker** for the
new session.

It is never:

```text
Risk authority
account authority
Strategy state
claim authority
broker receipt
flatness proof
```

A later P05 fresh read overrides earlier runtime observations for entry authority. If P05
sees changed exposure or otherwise refuses, no claim/mutation occurs.

## 10. Safety matrix

Marks:

| Mark              | Meaning                                                                          |
| ----------------- | -------------------------------------------------------------------------------- |
| `ALLOW→REQUESTED` | Local POST may persist new activation intent; no provider or mutation authority. |
| `CHECK`           | Startup must still prove current capability/account/flatness.                    |
| `STRICT BLOCK`    | Same-attempt recovery remains unsafe under `is_unsafe_paper_attempt()`.          |
| `ENTRY*`          | Entry may reach P05 only after all current runtime and P05 gates.                |
| `BLOCK`           | No new session / no RUNNING / no entry.                                          |

No row proves current flatness or authorizes mutation by itself.

### 10.1 Outcome/reconciliation matrix

| Outcome                                      | Reconciliation                                                      | New activation    | Same-attempt recovery        | Fresh startup | New entry |
| -------------------------------------------- | ------------------------------------------------------------------- | ----------------- | ---------------------------- | ------------- | --------- |
| `FILLED_PROTECTED`                           | `NOT_RUN`                                                           | `ALLOW→REQUESTED` | current strict safe behavior | `CHECK`       | `ENTRY*`  |
| `FILLED_PROTECTED`                           | `CONSISTENT`                                                        | `ALLOW→REQUESTED` | current strict safe behavior | `CHECK`       | `ENTRY*`  |
| `FILLED_PROTECTED`                           | `LIFECYCLE_ADVANCED`                                                | `ALLOW→REQUESTED` | current strict safe behavior | `CHECK`       | `ENTRY*`  |
| `FILLED_PROTECTED`                           | `UNRESOLVED` / `CONFLICT`                                           | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `FILLED_PROTECTION_INCOMPLETE`               | `NOT_RUN`                                                           | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `FILLED_PROTECTION_INCOMPLETE`               | `CONSISTENT`                                                        | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `FILLED_PROTECTION_INCOMPLETE`               | `UNRESOLVED`                                                        | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `FILLED_PROTECTION_INCOMPLETE`               | `CONFLICT`                                                          | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `FILLED_PROTECTION_INCOMPLETE`               | `LIFECYCLE_ADVANCED` + coherent durable Fill/applied reconciliation | `ALLOW→REQUESTED` | `STRICT BLOCK`               | `CHECK`       | `ENTRY*`  |
| `FILLED_PROTECTION_INCOMPLETE`               | `LIFECYCLE_ADVANCED` + missing/contradictory durable qualifier      | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `UNKNOWN`                                    | any status including `LIFECYCLE_ADVANCED`                           | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `REJECTED`                                   | `NOT_RUN` / `CONSISTENT` / `LIFECYCLE_ADVANCED`                     | `ALLOW→REQUESTED` | current strict safe behavior | `CHECK`       | `ENTRY*`  |
| `REJECTED`                                   | `UNRESOLVED` / `CONFLICT`                                           | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| `CANCELLED`                                  | `NOT_RUN` / `CONSISTENT` / `LIFECYCLE_ADVANCED`                     | `ALLOW→REQUESTED` | current strict safe behavior | `CHECK`       | `ENTRY*`  |
| `CANCELLED`                                  | `UNRESOLVED` / `CONFLICT`                                           | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |
| null/malformed/unsupported outcome or status | any                                                                 | `BLOCK`           | `STRICT BLOCK`               | `BLOCK`       | `BLOCK`   |

### 10.2 Multi-attempt account history

The configured account is eligible only if **every** historical attempt is
new-session-safe.

Examples:

```text
Dogfood incomplete + LIFECYCLE_ADVANCED
+ second UNKNOWN attempt
= BLOCK

two separate incomplete + LIFECYCLE_ADVANCED attempts
both with coherent durable Fill/applied reconciliation
= history does not itself block
→ fresh startup still required

safe REJECTED
+ safe FILLED_PROTECTED
+ lifecycle-ended incomplete Fill
= history does not itself block
→ fresh startup still required
```

### 10.3 Fresh account matrix

| Capability                                              | Full account |  Trades | Positions | Pending | Fresh startup               |
| ------------------------------------------------------- | ------------ | ------: | --------: | ------: | --------------------------- |
| exact supported                                         | coherent     |       0 |         0 |       0 | may reach `RUNNING`         |
| exact supported                                         | coherent     |      >0 |       any |     any | `BLOCK` for fresh bootstrap |
| exact supported                                         | coherent     |     any |        >0 |     any | `BLOCK`                     |
| exact supported                                         | coherent     |     any |       any |      >0 | `BLOCK`                     |
| wrong identity/provider/currency/unsupported capability | any          |     any |       any |     any | `BLOCK`                     |
| malformed/contradictory account facts                   | invalid      | unknown |   unknown | unknown | `BLOCK`                     |
| transient read failure                                  | no proof     | unknown |   unknown | unknown | remain `STARTING`; no entry |

## 11. Minimal implementation shape

Expected affected seams:

```text
backend/persistence/runtime_repository.py
backend/runtime/activation.py
backend/runtime/orchestration.py
backend/tests/runtime/test_runtime_activation.py
backend/tests/runtime/test_runtime_orchestration.py
backend/tests/runtime/test_runtime_completion_cross_seam.py
backend/tests/paper/test_reconciliation.py   # regression only if directly useful
```

Expected design:

1. Keep `_DEFINITE_TERMINAL_EXECUTION_OUTCOMES`,
   `_SAFE_RECONCILIATION_STATUSES`, and `is_unsafe_paper_attempt()` unchanged.
2. Add a new narrowly named row/query classifier for **new-session history**.
3. Make the classifier semantic; do not accept an incident UUID parameter and do not
   hardcode one.
4. Require coherent Fill + applied lifecycle-advanced reconciliation for the new incomplete
   case.
5. Use the new-session classifier at activation creation.
6. Use the same new-session history meaning when a new/fresh session needs to read current
   account state.
7. Keep interrupted-claim recovery on the strict helper.
8. Do not add a generalized recovery framework, policy table, bypass flag, schema column,
   or new API parameter unless implementation proves the current schema insufficient and
   returns for architecture re-approval.

No migration is expected.

## 12. Validation matrix

All validation is deterministic and broker-mutation-free.

Required focused scenarios:

1. Strict `is_unsafe_paper_attempt()` still returns unsafe for
   `FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED`.
2. New-session classifier allows that pair only with coherent durable Fill and applied
   lifecycle-advanced reconciliation.
3. Dogfood attempt UUID and a different synthetic attempt UUID with identical semantic
   evidence produce identical new-session classification.
4. No production helper contains or depends on the Dogfood attempt UUID.
5. Missing Fill ID, units, price, executed time, linked reconciliation evidence, or a
   reconciliation block code fails closed.
6. Any second account-history blocker makes the entire account history block.
7. `UNKNOWN + LIFECYCLE_ADVANCED` remains blocked.
8. Activation POST with only lifecycle-ended historical incompletes performs no provider
   read and persists only `REQUESTED`.
9. The old blocked activation remains blocked after its reconciliation becomes
   `LIFECYCLE_ADVANCED`; it cannot restart/resume.
10. A separately created fresh activation performs capability and full account reads before
    `RUNNING`.
11. Current open Trade, Position, pending Order, identity mismatch, malformed account state,
    or unsupported capability blocks fresh startup.
12. Fresh P05 account/Risk remains independent before ENTRY claim.
13. Owner loss, claim commit failure, and restart after committed claims retain current
    no-retry semantics.
14. Mutation spies prove no POST, PUT, cancel, close, reduce, or repair is reached by
    activation/startup/recovery validation.

Suggested focused commands:

```bash
uv run pytest backend/tests/runtime/test_runtime_activation.py \
  backend/tests/runtime/test_runtime_orchestration.py \
  backend/tests/runtime/test_runtime_completion_cross_seam.py

uv run pytest backend/tests/paper/test_reconciliation.py
```

Then the appropriate safe Critical backend gates:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend
uv run pytest -m "not integration and not external"
git diff --check
```

Run PostgreSQL integration/migration checks only as required by touched persistence seams
and the repository's normal Critical validation contract. No real OANDA credentialed
mutation is permitted.

## 13. Rejected alternatives

| Alternative                                                                                              | Rejection reason                                                                                                                                                                                                    |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hardcode Dogfood attempt UUID as a production exception                                                  | It is a data-specific bypass, gives identical durable states different semantics, and would require a code deployment for every future identical incident. The UUID belongs in evidence/tests, not authority logic. |
| Broaden `is_unsafe_paper_attempt()` globally                                                             | It is shared with same-attempt/claim recovery. Relaxing it would collapse two different safety questions.                                                                                                           |
| Accept `FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` without durable Fill/reconciliation qualifier | A malformed row could acquire future-session privilege without proving the lifecycle-ended filled Trade.                                                                                                            |
| Accept `UNKNOWN + LIFECYCLE_ADVANCED`                                                                    | `UNKNOWN` does not provide the same durable filled-Trade truth; do not generalize beyond the demonstrated semantic case.                                                                                            |
| Treat `LIFECYCLE_ADVANCED` as flatness or protection proof                                               | It proves only that the exact attributable Trade read as CLOSED. Fresh full-account state remains separately required.                                                                                              |
| Revive the old blocked activation                                                                        | This would donate post-failure authority to the same session and erase the explicit-new-approval boundary.                                                                                                          |
| Call OANDA during activation POST                                                                        | Provider/current-account proof belongs to runtime startup, not local durable activation intent.                                                                                                                     |
| Rewrite the old outcome to `FILLED_PROTECTED`                                                            | Falsifies historical execution truth.                                                                                                                                                                               |
| Add recovery/bypass schema state                                                                         | Existing durable Fill and reconciliation evidence are sufficient for this slice; adding new authority state is unnecessary unless implementation proves otherwise.                                                  |
| Retry, repair, cancel, close, reduce, or auto-heal                                                       | Outside PAPER 05/06 authority and this workstream.                                                                                                                                                                  |

## 14. Explicit exclusions and capital boundary

This workstream is not PAPER 07 and does not begin or authorize Dogfood 02.

It does not authorize:

```text
Dogfood 02 activation or retry
automatic activation
real OANDA mutation
PAPER/LIVE capital authority
credential changes
historical outcome/Fill/protection rewrite
current blocked-activation revival
entry or Take Profit retry
broker cancel/close/reduce/repair
Risk policy change
Strategy methodology/state change
provider abstraction
scheduler/queue/distributed ownership
UI work
general recovery framework
```

After this workstream closes, the trader must again:

```text
verify current Practice account state
review remediation behavior
provide fresh explicit Dogfood 02 approval
```

Only then may a new activation be created.

## 15. Approval gate

The next lifecycle state is `DEVELOPER_APPROVAL`.

Before explicit developer approval of the reconciled `PLAN.md` and
`ARCHITECTURE.md`, do not create `tasks/`, create or switch branches, modify application or
tests, start runtime, create an activation, use credentials, or perform broker mutation.
