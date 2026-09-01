# PLAN — PAPER Readiness 01 Internal Trading Boundary Audit

## Workstream state

- **Workstream:** `paper-readiness-01-internal-trading-boundary-audit`
- **Outcome:** Establish the code-grounded internal boundary decisions required before Atlas begins depending on OANDA Practice facts inside reusable Risk, execution, persistence, or runtime paths.
- **Classification:** `Critical`. The audit defines dependency direction among Strategy, Risk, Experiment, PAPER, broker integration, persistence, and eventual LIVE. Incorrect boundaries could couple capital-capable trading to historical simulation mechanics or move lifecycle/broker authority into the wrong layer.
- **Base:** `main` at `d8219d5` (`Close PAPER Readiness 01 architecture audit`).
- **Base SHA:** `d8219d52da774e9f84b39f4346f74bd87e59a291`.
- **Branch:** `solo/paper-readiness-01-internal-trading-boundary-audit`.
- **Phase:** `GIT_END`.
- **Approval:** implementation and merge approved by developer on 2026-09-01; GIT END is in progress. No broader PAPER/LIVE activation, broker mutation, or unrelated implementation is authorized.
- **Architecture:** `FROZEN_APPROVED_CANONICAL`; the approved `PLAN.md` and `ARCHITECTURE.md` are preserved as the canonical architecture decision.
- **Task state:** `T001` — `DONE`; BUILD receipt complete.
- **Next action:** commit this branch, merge it into `main`, push GitHub, then record completion and clear active state. Do not begin another PAPER slice.
- **Gate evidence:** focused VALIDATE `PASS_WITH_CONCERNS` with non-blocking baseline tooling concerns; independent REVIEW `PASS` with no Critical or Important findings.
- **Concerns:** several generic-looking trading seams were built specifically for historical Experiments. Reuse must follow semantic compatibility, not naming or code-reuse preference.

## Objective

Answer:

> Which Atlas internals already express environment-independent trading semantics that may carry unchanged through Experiment → PAPER → LIVE, which mechanics must remain explicitly Experiment-specific, and which exact boundary must be cleaned before bounded PAPER integration continues?

This is an architecture/readiness audit.

It is not authorization for a broad internal rewrite.

The intended result is:

```text
shared methodology and financial semantics
            ↓
environment-specific orchestration/mechanics
       ↙                     ↘
 Experiment                  PAPER
 historical                 broker-backed
 simulation                    path
```

rather than:

```text
PAPER
  ↓
adapters
  ↓
Experiment-shaped internals
```

## Current evidence inspected

The audit covers only internal surfaces PAPER is likely to cross:

- `backend/domain/`
- `backend/strategies/`
- `backend/risk/`
- `backend/execution/`
- `backend/experiments/`
- `backend/persistence/trading_repository.py`
- relevant trading persistence models and migrations
- `backend/execution/fill_application.py`
- `backend/runtime/`
- relevant tests that establish those contracts
- completed PAPER 01A–01F OANDA modules only to understand incoming provider facts

The current source establishes these important facts:

1. Strategy methodology identity and evaluation are already substantially provider-independent.
2. Atlas financial `Position` is distinct from Strategy `PositionState` and from OANDA provider Position aggregates.
3. `RiskService` is pure with respect to persistence and broker access, but its public call currently embeds historical lifecycle semantics through `experiment_status`.
4. Historical execution contracts contain explicit M1/OHLC, intrabar, slippage, sequence-one Fill, MarketBar provenance, and terminal Experiment assumptions.
5. Current trading persistence is intentionally Experiment-owned.
6. `apply_fill()` is the authoritative historical Experiment financial transition boundary, not a demonstrated universal broker accounting boundary.
7. `runtime/main.py` is currently inert with respect to trading activation.
8. OANDA PAPER observations remain read-only provider facts and have not yet been cast into Atlas financial records.

## Frozen architecture decisions

### 1. Strategy meaning is the reusable center

The immutable Strategy methodology must preserve the same meaning through:

```text
Experiment → PAPER → LIVE
```

This does not require reusing the same orchestration, execution adapter, persistence graph, or runtime.

Prefer:

```text
shared semantic contracts
+
environment-specific mechanics
```

over one generalized trading framework.

### 2. PAPER must not pretend to be an Experiment

PAPER must never supply synthetic facts such as:

```text
experiment_id
experiment_status="RUNNING"
DatasetSnapshot
historical MarketBar ID
```

merely to satisfy an existing historical API.

When a current API requires an Experiment-specific fact that does not belong to PAPER, that is evidence of a boundary decision—not permission to fabricate compatibility data.

### 3. Risk does not own lifecycle activation

The reusable Risk boundary must not know whether:

```text
an Experiment is RUNNING
PAPER is activated
LIVE is activated
reconciliation has completed
the runtime has permission to mutate a broker
```

Those are orchestration/activation prerequisites.

The immediate demonstrated pre-PAPER refactor is therefore:

> remove Experiment lifecycle knowledge from the reusable Risk call boundary without replacing it with a generic `authorized`, `eligible`, `paper_active`, or reconciliation-proof flag.

Risk remains authoritative for the individual financial RiskDecision under trader-approved Risk policy.

### 4. Provider facts remain provider facts

OANDA:

```text
Account
Trade
Position
Order
Price
```

observations remain provider-native until an explicit projection contract translates the minimum required facts.

Similarity of fields does not justify direct casting.

### 5. Historical execution remains historical

Current:

```text
ExecutionObservation
execution.contract.Order
execution.contract.Fill
SimulatedExecutionAdapter
apply_fill()
```

contain demonstrated historical Experiment semantics.

Do not reshape them into PAPER contracts merely to maximize reuse.

Preserve completed Experiment reproducibility.

Separate PAPER instruction, broker-confirmation, and accounting contracts are designed only when mutation is actually approached.

### 6. Historical persistence remains Experiment-owned

Current trading persistence uses an Experiment ownership graph.

Do not generalize those tables or repositories preemptively.

Do not introduce:

```text
experiment_id | paper_id | live_id
```

or synthetic Experiment ownership.

A PAPER ownership model is earned later when durable broker-backed trading facts actually require one.

### 7. Current ExecutableQuote remains historical for now

The existing two-field:

```text
ExecutableQuote(
    bid,
    ask,
)
```

works for historical deterministic execution.

Do not expand it now with:

```text
timestamp
provider
tradeable
reconciliation
authority
```

Provider validity belongs at the OANDA-to-Atlas projection boundary.

The unresolved PAPER pricing issue is quantity semantics:

```text
OANDA pricing
→ multiple price/liquidity buckets

current Risk
→ computes quantity from one bid/ask pair
```

Atlas has not yet proven that a single provider bucket can safely price the Risk-sized quantity.

That problem receives its own later Critical slice before actual PAPER pre-submission sizing.

### 8. Runtime remains inert until mutation is earned

Starting Atlas must not imply PAPER activation.

`runtime/main.py` may remain unchanged until the first mutation-capable PAPER lifecycle is close enough to require:

- explicit trader activation;
- current broker identity;
- successful reconciliation;
- safe resume;
- fail-closed shutdown/recovery.

No daemon/event-bus/scheduler architecture is authorized now.

## In scope

1. Current dependency-direction map.
2. Classification of important seams as:

   - `REUSE AS-IS`
   - `REFACTOR BEFORE PAPER`
   - `KEEP EXPERIMENT-SPECIFIC`
   - `DEFER UNTIL BROKER MUTATION`

3. Strategy methodology boundary.
4. Atlas financial Position boundary.
5. Risk financial responsibility versus lifecycle responsibility.
6. Historical execution isolation.
7. Historical persistence ownership.
8. Historical fill/accounting ownership.
9. Runtime activation responsibility.
10. Provider-to-Atlas translation responsibility.
11. Smallest immediate prerequisite before resuming bounded PAPER slices.
12. Just-in-time gates required later before Strategy PAPER evaluation, pricing/sizing, broker mutation, durable reconciliation, and activation.

## Out of scope

- application-code changes;
- test changes;
- migrations;
- schema changes;
- GIT START;
- task creation;
- BUILD;
- OANDA mutation;
- PAPER activation;
- LIVE activation;
- credential changes;
- Risk-policy changes;
- provider Order submission;
- generic broker architecture;
- generic portfolio/account architecture;
- generalized execution framework;
- generalized persistence ownership;
- final PAPER runtime design;
- final PAPER reconciliation design;
- final LIVE design;
- refactoring merely for module cleanliness or code deduplication.

## Architecture deliverable

`ARCHITECTURE.md` is the canonical code-grounded audit.

It must:

1. describe the current historical execution graph;
2. identify reusable methodology and financial semantics;
3. identify historical Experiment-specific mechanics;
4. define PAPER boundary requirements;
5. separate Risk financial authority from lifecycle/activation authority;
6. distinguish Atlas Position from Strategy state and provider Position;
7. distinguish historical execution contracts from future broker contracts;
8. preserve Experiment-owned persistence and accounting;
9. keep runtime non-trading until mutation is earned;
10. state dependency direction explicitly;
11. classify each required seam into exactly one primary category;
12. identify only the demonstrated immediate refactor blocker;
13. define later just-in-time capability gates without implementing them;
14. preserve capital-control boundaries.

## Immediate prerequisite decision

Only one internal refactor currently blocks the next PAPER projection slice:

### PAPER Readiness 02 — Risk Lifecycle Boundary Cleanup

Likely classification:

```text
Critical
```

Objective:

> Remove Experiment lifecycle knowledge from reusable Risk without changing Risk sizing mathematics, Risk policy, historical Experiment results, or introducing PAPER/LIVE activation semantics into Risk.

Expected direction:

```text
ExperimentRunner
  proves Experiment lifecycle eligibility
        ↓
RiskService
  evaluates financial Risk facts only
```

Future PAPER:

```text
PAPER coordinator
  proves activation/reconciliation prerequisites
        ↓
RiskService
  evaluates financial Risk facts only
```

The implementation workstream must inspect whether historical compatibility values such as `EXPERIMENT_NOT_RUNNING` need to remain readable even if they are no longer emitted by reusable Risk.

Do not decide that mechanically in this audit.

## PAPER progression after Risk cleanup

After PAPER Readiness 02 closes, return to bounded vertical PAPER slices.

The next previously planned slice remains:

```text
PAPER 01G
OandaPracticeAccountSummarySnapshot
        ↓
AccountState
```

with:

```text
identity.base_currency → AccountState.base_currency
nav                    → AccountState.equity
```

01G remains a pure projection.

Later capability gates are earned only when needed:

```text
Risk lifecycle cleanup
        ↓
resume bounded provider/domain projections
        ↓
completed analytical frontier/state continuity
  before first PAPER Strategy evaluation
        ↓
pricing/liquidity/quantity semantics
  before PAPER pre-submission sizing
        ↓
instruction + broker-confirmation semantics
  before first broker mutation
        ↓
PAPER ownership + reconciliation + accounting
  before durable mutation-capable state
        ↓
runtime activation/resume gate
  before PAPER may actually mutate OANDA
```

These are not one refactor program.

Each is separately planned, approved, implemented, validated, and reviewed only when its capability is actually needed.

## Acceptance criteria

1. `PLAN.md` and `ARCHITECTURE.md` are the only workstream-owned planning artifacts; no `tasks/` directory exists.
2. No application, test, migration, persistence, frontend, credential, or runtime implementation is changed.
3. Every important architectural conclusion is tied to observed current code or tests.
4. Strategy methodology identity/evaluation is classified independently from historical orchestration.
5. Atlas financial Position remains distinct from Strategy `PositionState` and OANDA provider Position.
6. Reusable Risk does not own Experiment/PAPER/LIVE lifecycle activation.
7. The architecture does not replace `experiment_status` with a generic lifecycle/reconciliation boolean or proof inside Risk.
8. Existing Risk financial decision authority remains explicit.
9. Current historical `ExecutableQuote` is not broadened merely to absorb OANDA provider metadata.
10. Quantity-aware PAPER pricing is identified as a later unresolved seam.
11. Current historical execution Order/Fill/Observation/simulator contracts are not generalized for PAPER.
12. Current `apply_fill()` remains classified according to its Experiment-specific financial ownership.
13. Existing trading persistence remains Experiment-owned.
14. No synthetic Experiment identity is recommended for PAPER.
15. Runtime startup remains non-trading.
16. Only Risk lifecycle cleanup is an immediate internal prerequisite before 01G.
17. Later broker execution, persistence, reconciliation, and activation work is explicitly just-in-time.
18. No architecture decision authorizes PAPER/LIVE activation or broker mutation.
19. Phase ends at `DEVELOPER_APPROVAL`.
20. No GIT START or task creation occurs until a separately authorized implementation workstream begins.

## Approval gate

This Critical audit is complete and reconciled.

Current lifecycle:

```text
PLAN
→ ARCHITECTURE
→ reconciliation
→ DEVELOPER_APPROVAL
```

This audit itself does not contain a BUILD phase.

If the developer approves these architecture decisions:

1. record/close PAPER Readiness 01 according to SoloFlow's architecture-only workstream convention;
2. do not turn the audit into a mass-refactor task;
3. start a separate workstream for `PAPER Readiness 02 — Risk Lifecycle Boundary Cleanup`;
4. follow that workstream's own classification, PLAN/ARCHITECTURE/approval lifecycle;
5. after it closes, resume PAPER 01G.
