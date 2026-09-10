# Development Baseline Consolidation

## Workstream state

- **Workstream:** `development-baseline-consolidation`
- **Classification:** `Feature`
- **Base:** `main` at `611fe10b9b596f9e48339f305b99023d402c4514`
- **Branch:** `solo/development-baseline-consolidation`
- **Phase:** `READY_FOR_USER`
- **Approval:** approved by developer on 2026-09-10 for the revised PLAN
- **Architecture:** not required; no durable contract change is approved
- **Task state:** T001 DONE; T002 DONE; T003 DONE; T004 DONE
- **Next action:** explicit developer merge approval; do not merge before approval
- **Remediation:** R001 BUILD DONE; R001 VALIDATE PASS; R001 REVIEW PASS; findings F-001 and F-002 closed
- **Concerns:** if implementation requires persistence, methodology, authority, trading, or another durable semantic change, stop and return for reclassification

## Outcome

Establish one clean development baseline before Atlas expands beyond its original EUR/USD slice.

This is not a general refactor. The purpose is to remove obvious development debris, establish truthful validation and engineering rules, decide how prototype compatibility should be treated while Atlas remains undeployed, and then stop cleanup work so Atlas can proceed to Market Capability 01.

The next product workstream after this should be GBP/JPY on OANDA Practice.

## Classification

Feature.

No ARCHITECTURE.md is required unless implementation discovers that a persistence contract, migration, trading semantic, broker-authority boundary, or other durable contract must change.

If that occurs, stop and return for reclassification. Do not absorb it into this Feature.

## Product state

Atlas is still in active development and is not deployed.

Development-era local database state does not automatically create a permanent compatibility obligation.

At the same time, undeployed status does not authorize silent destruction of immutable methodology, Experiment evidence, PAPER evidence, broker facts, or safety semantics.

Use this rule:

**Compatibility exists because Atlas deliberately needs the old meaning, not merely because an older implementation once existed.**

Any compatibility candidate must therefore be classified as one of:

**CURRENT** — required by current Atlas behavior.

**EVIDENCE** — required to inspect historical evidence we deliberately intend to retain.

**PROTOTYPE** — required only for disposable development-era state.

**DEFERRED** — likely removable, but belongs naturally to a later Strategy, market-capability, or persistence workstream.

Only mechanically safe PROTOTYPE/dead-code cleanup belongs in this Feature.

Anything requiring data migration, database reset, methodology reinterpretation, or evidence rewriting is not silently performed here.

## Preserve

The workstream must not weaken Strategy/Risk separation, immutable StrategyVersion methodology, deterministic Experiments, no-lookahead, explicit market-data provenance, Fill-derived exposure, broker authority, uncertain-order handling, restart/reconciliation safety, broker-side protection, durable runtime ownership, trader activation authority, or fail-closed financial uncertainty.

Large code protecting one of those responsibilities is not considered overengineering merely because it is large.

## Workstream scope

### Repository truth

Correct README.md and AGENTS.md so current main is described accurately.

They must state that Atlas currently contains historical Experiment capability and guarded OANDA Practice PAPER execution/runtime/activation/reconciliation capability.

They must not claim LIVE support.

They must not imply that starting Atlas, starting the runtime, inspecting broker state, or possessing configured credentials authorizes trading.

AGENTS.md should also state that Atlas is currently undeployed and that prototype compatibility is not automatically permanent.

### Provider-first engineering rule

Add the following engineering principle to the repository guidance:

**Provider-first:** Before Atlas derives, reconstructs, hard-codes, or maintains a market, account, execution, pricing, conversion, margin, instrument, or transaction fact, determine whether the provider already exposes the authoritative fact. Prefer normalized provider truth. Atlas should own Atlas decisions, not duplicate the broker's ledger or market metadata.

This is an engineering rule, not a reason to generalize provider infrastructure in this workstream.

Do not implement new OANDA behavior here.

### Pyright baseline investigation

Do not normalize 3,011 errors as permanent debt until the contradictory validation history is understood.

Establish:

- exact Pyright version used by the current locked environment;
- exact current diagnostic count using structured output;
- production versus test diagnostic counts;
- dominant diagnostic rules and highest-concentration files;
- the exact command recorded by the historical validation that claimed repository-wide success;
- whether relevant Pyright configuration, dependency lock state, command scope, or source tree changed between that validation and current main;
- whether the historical receipt was accurate, scoped differently, or incorrect.

Do not fix the entire repository in this Feature.

After diagnosis, define a temporary validation policy that makes new typing regressions visible.

At minimum:

- touched production files may not introduce new Pyright diagnostics;
- touched tests may not introduce new diagnostics relative to their baseline;
- focused typing checks must be clean where an isolated clean surface exists;
- repository-wide diagnostic count is recorded truthfully;
- no Pyright rule is disabled merely to make the baseline green.

Record the unresolved root causes so a later dedicated typing workstream can address them intentionally.

### Development compatibility classification

Inventory the known compatibility seams and classify each CURRENT, EVIDENCE, PROTOTYPE, or DEFERRED.

Include at least:

- StrategyState schema 1;
- window_bars / AWAITING_CONFIRMATION compatibility;
- warm_up_bars;
- snapshot V1;
- legacy result metric states and old result schema identifiers;
- indicators.py versus indicators_v2.py;
- EmaSweepConfirmationBreakCompatibilityAdaptor;
- historical-load compatibility fields;
- runtime service aliases.

Do not remove a seam merely because Atlas is undeployed.

Do not preserve a seam merely because it has old tests.

For each seam identify the current caller, persisted dependency, evidence dependency, and natural retirement point.

Expected natural retirement examples:

- EMA adaptor / old indicator behavior → Strategy SDK / EMA vNext;
- instrument/account assumptions → Market Capability work;
- true prototype persistence compatibility → future explicit development-data baseline/reset decision.

This Feature may delete only compatibility proven to have no current, evidence, API, persistence, test-contract, or planned transition responsibility.

### Phase terminology

Distinguish historical identifiers from current semantics.

Historical migration revision IDs, closed workstreams, persisted schema/version identifiers, old benchmark names, and existing database constraint names may retain Phase terminology when changing them provides no functional benefit.

Do not create migrations merely to rename historical constraint names.

Current application concepts, new contracts, new identifiers, comments describing current behavior, and future code must use domain/capability terminology rather than development milestones such as Phase 2, Phase 4, or Phase 5.

Remove or rewrite non-contract phase terminology only when the change is mechanical.

### Obvious code debris

Remove only mechanically proven dead or duplicate code.

Current candidates include duplicated experiment chart types/order helpers, unused imports/locals in files already being touched, genuinely unreferenced workflow helpers, and runtime aliases proven to have no consumer.

Do not launch a repository-wide frontend warning cleanup.

Do not redesign experiment components.

Do not remove an alias or helper without checking repository imports, tests, API exposure, generated surfaces where relevant, and persistence/evidence responsibility.

### Complexity ratchet

Add an engineering rule that prevents Atlas agents from extending large files by default.

Generated files are exempt.

For hand-maintained production code:

A new module should normally target approximately 400 lines or fewer.

A new module above approximately 600 lines requires explicit PLAN justification based on cohesion.

An existing file at or above 800 lines must not receive a new responsibility without extracting a cohesive boundary.

An existing file at or above 800 lines should not grow by more than approximately 50 net lines unless the PLAN explicitly explains why the behavior belongs there.

For files above 1,200 lines, separable new behavior should normally be implemented in a new cohesive module rather than extending the existing file.

These are ratchets, not automatic refactor triggers.

Do not split a cohesive state machine merely to satisfy a line count.

Every future Feature/Critical PLAN should identify expected files to modify/create and call out any large-file growth exception.

## Explicitly deferred

Do not implement GBP/JPY, multi-instrument support, additional timeframes, Strategy SDK, EMA methodology changes, Experiment redesign, broad UI redesign, LIVE trading, generalized provider/plugin architecture, or a full repository typing cleanup.

Do not change Risk sizing, broker reconciliation, broker mutation semantics, Fill application, protection, ownership, activation fencing, or financial-state authority.

Do not create an Alembic migration or reset the development database in this workstream.

If investigation shows that meaningful simplification requires either, record the candidate and defer the decision.

## Planned implementation slices

1. Correct repository capability truth and add the undeployed-development/provider-first/complexity-ratchet engineering guidance.
2. Reconcile the Pyright baseline contradiction and record a truthful changed-surface validation policy.
3. Classify development compatibility seams and phase terminology; make only mechanical safe removals.
4. Consolidate mechanically proven duplicate/dead frontend/runtime symbols without redesign.
5. Run focused validation plus the existing safe backend/frontend suites and record remaining repository-wide debt truthfully.
6. Independent REVIEW confirms that the workstream reduced development noise without weakening a trading, evidence, or safety boundary.

BUILD task files are created only after developer approval and GIT START. They are
sequential and remain limited to the approved implementation slices above.

## Acceptance

The workstream passes only if current repository documentation accurately describes Atlas; the Pyright contradiction has an evidence-backed explanation or clearly bounded unresolved cause; repository-wide Pyright debt is reported truthfully rather than treated as green; known compatibility seams have explicit CURRENT/EVIDENCE/PROTOTYPE/DEFERRED classifications; no historical evidence is silently rewritten; no migration or database reset occurs; no trading, Strategy, Risk, provider, PAPER, or Experiment semantics change; obvious duplicate/dead code removed has proven no contract responsibility; provider-first and complexity-ratchet guidance is present; touched surfaces introduce no new lint/type/test regressions; and Atlas is left ready to begin the GBP/JPY Critical workstream without another general cleanup phase.

## Stop condition

This is the only general development-baseline cleanup before Market Capability 01.

Do not turn newly discovered imperfections into additional cleanup workstreams unless they materially block correct GBP/JPY implementation or violate a safety invariant.

After this closes, proceed to the market-capability work.
