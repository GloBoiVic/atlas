# PLAN - UI 02 Trader Shell and Overview Product Cleanup

## Workstream state

- **Workstream:** `ui-02-trader-shell-overview-product-cleanup`
- **Classification:** `Feature`
- **Base:** `main` at `9c31774f499c2e21a34b7f80fbfa190bf3be1fdb`
- **Branch:** `solo/ui-02-trader-shell-overview-product-cleanup`
- **Phase:** `READY_FOR_USER`
- **Approval:** approved by developer on 2026-09-09; current PLAN intake correction accepted
- **Architecture:** not required; this is a frontend-only information-hierarchy and presentation change over existing read contracts
- **Task state:** T001 DONE_WITH_CONCERNS (expected stale T002 assertions); T002 DONE_WITH_CONCERNS (existing lint warnings)
- **Next action:** explicit developer merge approval; do not merge before approval

`dispatch/ACTIVE.md` is the mutable operational record for this active workstream.

## Outcome

Turn the Atlas Overview from a diagnostic/read-contract surface into a trader-facing operating dashboard.

The Overview should answer, in order:

1. Do I currently have broker exposure?
2. How is that exposure doing?
3. Is an Atlas PAPER runtime currently active?
4. What Strategies are available?
5. What Experiments are visible?
6. Is Atlas healthy?

Technical evidence remains available in Atlas but must not dominate the primary dashboard.

This workstream does not change any backend or trading behavior.

## Product principle

Atlas stores technical truth richly but presents trader truth progressively.

Use three information levels:

```text
Level 1 — Decision
What matters right now?

Level 2 — Context
Which market, Strategy, state, period, or environment?

Level 3 — Evidence
IDs, fingerprints, schemas, raw codes, policy identifiers, durable evidence.
```

The Overview is primarily Level 1 and Level 2.

Level 3 evidence must not dominate the Overview.

## Copy principle

Prefer:

- short labels;
- values;
- status indicators;
- concise empty/error states;
- contextual actions.

Avoid explanatory sentences when layout and labels already communicate the distinction.

Examples:

```text
BAD
Readiness is a system check, not a PAPER connectivity claim.

GOOD
System
Ready
```

```text
BAD
Current OANDA Practice open Trades. Broker exposure, not runtime.

GOOD
Paper Trading
OANDA Practice
```

```text
BAD
Status summary for the visible first page only; no global total or performance metric is inferred.

GOOD
Experiments
```

Do not shorten copy by making a stronger claim than the underlying contract supports.

When Atlas cannot prove something, preserve the uncertainty rather than explaining it away.

## Current findings

### Shell

`frontend/components/app-shell.tsx` currently renders:

- primary navigation;
- API status;
- timezone selector;
- a permanent lifecycle/explainer strip;
- a separate `Times shown in <timezone>` body line.

The lifecycle strip and timezone body line add vertical noise without helping the trader make a decision.

The navigation, API status, timezone selector, responsive behavior, and disabled LIVE affordance are useful and should remain.

### Overview

`frontend/components/overview.tsx` currently renders:

1. broker-state section;
2. API/database readiness;
3. Strategy catalog count;
4. Experiment status-count summary;
5. PAPER capability;
6. PAPER runtime status;
7. historical-data capability;
8. full DatasetSnapshot metadata;
9. a separate Next Steps navigation section.

This over-represents backend capability and configuration facts.

Historical-data capability and DatasetSnapshot evidence already have a dedicated `/data` surface and do not belong on the primary trading dashboard.

### Broker state

`frontend/components/paper-broker-state.tsx` already has the authoritative frontend facts required for this slice:

- provider/environment;
- account currency;
- every open Trade;
- instrument;
- signed units;
- derived LONG/SHORT display;
- entry;
- unrealized P/L;
- opened time;
- provider Trade state.

Its current `compact` mode changes spacing but does not materially change information hierarchy.

The compact Overview mode still:

- uses the diagnostic heading `PAPER broker state`;
- includes explanatory copy;
- shows Trade ID;
- gives unrealized P/L similar visual weight to secondary facts.

### Runtime

`PaperActiveStatusSection` correctly treats runtime state separately from broker exposure.

Its compact mode currently renders the same diagnostic copy and raw `PAPER_ACTIVATION_NOT_ACTIVE` evidence as the full PAPER page.

The Overview needs a trader-facing compact runtime presentation while preserving full PAPER evidence elsewhere.

### Strategies

The existing Strategy list read already provides useful trader-facing facts including:

- Strategy name;
- description;
- latest version display name;
- version count;
- Experiment count;
- last Experiment time.

No new backend projection is needed.

### Experiments

The existing Experiment list read and existing frontend helpers already support trader-facing presentation of:

- Experiment identity;
- Strategy identity;
- status;
- period;
- headline metrics where present.

The Overview does not need raw status-count diagnostics.

### Tests

Current shell and Overview tests intentionally assert the old lifecycle prose, timezone body line, DatasetSnapshot data, raw status summaries, and Next Steps controls.

Those tests must be updated to assert the new product hierarchy rather than preserve the old diagnostic UI.

## Proposed shell

### Header

Preserve:

- Atlas wordmark;
- Overview;
- Strategies;
- Experiments;
- PAPER;
- Data;
- disabled LIVE;
- API status;
- timezone selector;
- responsive horizontal navigation behavior;
- keyboard/focus behavior.

### Remove lifecycle explainer strip

Remove the entire persistent strip containing copy similar to:

```text
Historical research
Strategies are authored and versioned
/
Experiments are deterministic historical research
/
PAPER status is observable, not controllable here
/
LIVE is a future capability
```

The application structure should communicate this through navigation and individual surfaces.

### Remove timezone body sentence

Remove:

```text
Times shown in America/Chicago
```

from the main body.

The header timezone selector remains the source of display-timezone context.

Do not remove timezone functionality.

### Do not redesign global navigation

This workstream does not:

- introduce a sidebar;
- introduce a new mobile-navigation architecture;
- add settings infrastructure;
- change lifecycle navigation;
- enable LIVE.

## Proposed Overview hierarchy

The Overview should become:

```text
Overview

[ PAPER / CURRENT BROKER EXPOSURE ]

[ STRATEGIES ] [ EXPERIMENTS ] [ SYSTEM ]
```

Do not add another global navigation section at the bottom.

### Page header

Use:

```text
Overview
```

Remove the recurring explanatory copy:

```text
Trader workspace
Atlas is where the trader creates methodologies...
```

A short secondary label is acceptable only if it communicates useful current state.

The page should not explain Atlas every time it opens.

## PAPER / current exposure

Current broker exposure is the primary Overview object.

Reuse the existing `paperBrokerState()` read unchanged.

### Open Trade presentation

For each open Trade, prioritize:

1. instrument;
2. OPEN / CLOSE_WHEN_TRADEABLE state;
3. direction;
4. absolute quantity;
5. unrealized P/L;
6. entry;
7. opened time;
8. provider/environment.

Conceptually:

```text
Paper Trading                                  OANDA Practice

EUR/USD                                           OPEN

SHORT 390,663

Unrealized P/L
-$410.20

Entry                     Opened
1.16188                   Sep 4, 2:04 AM
```

The exact responsive layout is an implementation/design choice.

### P/L hierarchy

Unrealized P/L must be visually stronger than:

- Trade ID;
- entry;
- opened time;
- provider metadata.

Preserve the existing positive/negative/neutral semantic treatment.

Do not alter exact API decimal strings.

### Trade ID

Do not display provider Trade ID in the compact Overview mode.

Trade ID may remain on the full PAPER surface as secondary evidence.

Do not remove it from the API contract.

### Multiple Trades

If multiple Trades are returned:

- render every Trade;
- preserve each independently;
- do not net;
- do not select one;
- do not hide unexpected exposure.

The compact layout must remain usable with multiple Trades.

### Empty state

Only a successful empty `openTrades` response may render a concise state such as:

```text
No open trades
```

Do not display `Flat`.

### Unavailable state

A failed broker read must remain distinct:

```text
Broker unavailable
Retry
```

Do not convert failure into:

- flat;
- no exposure;
- no open Trades.

### Refresh

Retain the explicit GET-only Refresh action.

Do not add automatic polling.

## Runtime summary

The Overview should preserve broker/runtime separation without giving runtime equal visual weight to current capital exposure.

Use the existing active PAPER runtime read.

### No active runtime

When the active-runtime read returns its existing normal no-active result, compact Overview copy may say:

```text
Runtime
Not running
```

or:

```text
Runtime
No active runtime
```

Do not say:

```text
Stopped
```

unless the returned current contract actually proves that lifecycle state.

Do not display:

```text
PAPER_ACTIVATION_NOT_ACTIVE
```

on Overview.

### Active runtime

If an active activation is returned, the compact view may show:

```text
Runtime
Active
```

with one concise authoritative lifecycle/phase fact if useful.

Do not reproduce the full diagnostic runtime fact grid on Overview.

### Full PAPER page

The full PAPER page remains the detailed evidence surface.

This workstream may add meaningful compact rendering behavior to shared PAPER components, but it must not broadly redesign `/paper`.

Do not weaken its existing broker/runtime truth boundary.

## Strategies summary

Replace `Strategy catalog` and `returned items` language with a trader-facing `Strategies` card.

Use only the existing Strategy list response.

Show a small number of useful rows, preferably up to three.

Each row should prioritize:

```text
Strategy name
Latest version display name
```

Secondary facts such as Experiment count may be included if they improve scanability.

Do not show internal StrategyVersion UUIDs.

Do not add a caveat paragraph about whether the count is global.

If a total cannot be stated cleanly, omit it.

Provide a contextual link:

```text
View Strategies
```

### Strategy empty/error

Use concise states:

```text
No Strategies
```

and the existing explicit error treatment.

A Strategy read failure must not affect broker, Experiment, or system sections.

## Experiments summary

Replace the current status-count diagnostic block with an `Experiments` card.

Use the existing list read.

Show a small number of returned Experiments, preferably up to three.

Reuse existing trader-facing formatting helpers where appropriate rather than inventing a second Experiment-display vocabulary.

Prioritize:

- Experiment identity;
- Strategy identity;
- status;
- one or two headline metrics for completed Experiments where already present;
- concise period/date when useful.

Conceptually:

```text
Experiments

Candle Confirmation Break
COMPLETED
+1.70% · 1 trade

Experiment
RUNNING
```

Do not label the list as a global total.

Do not invent performance metrics.

Do not expose Experiment UUIDs in primary Overview presentation.

Provide contextual actions:

```text
View Experiments
Run Experiment
```

These actions belong inside the Experiments card rather than a global Next Steps section.

### Experiment empty/error

Use concise states.

A failed Experiment read must remain independent of every other Overview read.

## System summary

Replace the large `API and database readiness` card with a compact `System` card using the existing readiness endpoint.

### Healthy

When:

```text
status = ready
database = ok
```

show a concise healthy state such as:

```text
System
Ready

API        Ready
Database   Ready
```

The exact layout may be smaller.

### Degraded

If the API responds but reports non-ready/degraded facts:

- keep the condition visible;
- use concise readable labels;
- do not hide the actual problem;
- do not add a paragraph explaining readiness semantics.

Example:

```text
System
Needs attention

API        Not ready
Database   Unavailable
```

### Error

If the readiness request itself fails, retain explicit unavailable/error treatment with retry.

## Remove from Overview

Remove the following Overview sections entirely:

- `PaperCapabilitySection`;
- `HistoricalCapabilitySection`;
- `SnapshotOptionsSection`;
- DatasetSnapshot fingerprints;
- DatasetSnapshot schemas;
- snapshot integrity metadata;
- historical product capability details.

Do not call these APIs from Overview after this change:

```text
paperCapability()
historicalCapability()
configurationOptions()
```

Their dedicated pages continue to own those facts.

No Data functionality is deleted.

## Remove Next Steps

Delete the existing Overview `Next steps` section and its duplicate navigation actions:

- Review Strategies;
- Configure an Experiment;
- Inspect Experiments;
- Inspect Data;
- View PAPER status.

Global navigation already provides destination navigation.

Only contextual actions inside the relevant card should remain.

## Progressive disclosure rules

Primary Overview must not prominently expose:

- UUIDs;
- provider Trade IDs;
- DatasetSnapshot fingerprints;
- schema identifiers;
- policy versions;
- raw provider transaction IDs;
- raw API error codes;
- raw internal implementation explanations.

This is presentation hierarchy only.

Do not weaken, delete, or mutate authoritative backend evidence.

## Visual direction

Use the existing Atlas dark-first palette and design tokens.

Do not introduce a new visual design system.

Prefer:

- fewer cards;
- stronger spacing hierarchy;
- larger important values;
- restrained borders;
- existing positive/negative/warning colors;
- clear typography over explanatory prose.

Avoid:

- gradients added only for decoration;
- excessive badges;
- oversized icons;
- dashboard decoration without information value;
- dense nested cards.

The primary PAPER surface should have more visual weight than the secondary cards.

## Expected implementation files

Expected primary files:

```text
frontend/components/app-shell.tsx
frontend/components/overview.tsx
frontend/components/paper-broker-state.tsx
frontend/components/paper-status.tsx
frontend/tests/app_shell.test.tsx
frontend/tests/overview.test.tsx
frontend/tests/paper_broker_state.test.tsx
frontend/tests/paper_status.test.tsx
```

Existing helpers may be reused from:

```text
frontend/components/experiments/shared.ts
frontend/lib/instrument.ts
frontend/lib/time.ts
frontend/lib/experiment-formatters.ts
```

Do not modify those helpers unless a real reuse gap is demonstrated.

No change is expected in:

```text
frontend/components/data-overview.tsx
frontend/lib/api-client.ts
frontend/lib/api.generated.ts
```

No new design-token change in `frontend/app/globals.css` is expected. Prefer existing Tailwind utilities and Atlas tokens.

If an implementation need requires expanding beyond these files materially, stop and assess scope before proceeding.

## Hard boundary

This workstream is frontend-only.

No files under:

```text
backend/**
```

may change.

Specifically do not change:

- PAPER API contracts;
- broker-state endpoint;
- OANDA integrations;
- runtime;
- Risk;
- execution;
- persistence;
- migrations;
- Strategy contracts.

Do not regenerate OpenAPI.

Do not alter frontend API request semantics.

No:

- `atlas-runtime`;
- PAPER activation;
- stop;
- reconciliation;
- broker mutation;
- Trade management;
- automatic broker polling;
- websocket work.

Dogfood 02 and any existing broker Trade remain untouched.

## Suggested task boundaries

After approval, Solo should create implementation tasks from this PLAN rather than re-plan the workstream.

Recommended decomposition:

### T001 - Compact trader state presentation

Primary files:

```text
frontend/components/paper-broker-state.tsx
frontend/components/paper-status.tsx
frontend/tests/paper_broker_state.test.tsx
frontend/tests/paper_status.test.tsx
```

Outcome:

- real compact broker presentation;
- stronger Trade/P&L hierarchy;
- no Trade ID on Overview compact mode;
- concise broker empty/unavailable states;
- concise compact runtime state;
- no raw no-active API code in compact mode;
- full PAPER evidence behavior preserved.

### T002 - Shell and Overview hierarchy

Primary files:

```text
frontend/components/app-shell.tsx
frontend/components/overview.tsx
frontend/tests/app_shell.test.tsx
frontend/tests/overview.test.tsx
```

Outcome:

- remove lifecycle strip;
- remove standalone timezone sentence;
- simplify Overview header;
- primary PAPER area;
- trader-facing Strategies summary;
- trader-facing Experiments summary;
- compact System summary;
- remove PAPER capability from Overview;
- remove historical-data/DatasetSnapshot sections from Overview;
- remove Next Steps.

T002 may consume the compact components completed in T001.

Avoid parallel workers editing the same primary files.

## Acceptance criteria

1. Overview contains no recurring Atlas explanation paragraph.
2. Shell lifecycle explainer strip is removed.
3. Standalone `Times shown in <timezone>` body text is removed.
4. Timezone selector remains functional.
5. Primary navigation remains responsive and keyboard accessible.
6. API status remains available in the shell.
7. Current broker exposure is the first substantive Overview section.
8. Every returned open Trade remains individually visible.
9. LONG/SHORT quantity semantics remain unchanged.
10. Unrealized P/L is visually more prominent than entry, opened time, or Trade ID.
11. Compact Overview does not show provider Trade ID.
12. Successful empty broker inventory produces a concise no-open-Trades state.
13. Broker failure remains unavailable and is never represented as flat/no exposure.
14. Explicit broker Refresh remains GET-only.
15. Overview runtime state is visibly secondary to broker exposure.
16. No-active runtime is presented concisely without exposing `PAPER_ACTIVATION_NOT_ACTIVE`.
17. Runtime state is not used as proof of broker flatness.
18. Strategies card uses Strategy names/version display facts rather than catalog/read terminology.
19. Experiments card shows useful returned Experiment facts rather than a status-count diagnostic.
20. System health is compact when healthy and explicit when degraded.
21. Overview no longer renders PAPER capability.
22. Overview no longer renders historical-data capability.
23. Overview no longer renders DatasetSnapshot fingerprints, schemas, or integrity metadata.
24. Overview no longer invokes `paperCapability()`, `historicalCapability()`, or `configurationOptions()`.
25. Overview has no global Next Steps section.
26. Contextual Strategy/Experiment links remain usable.
27. Each independent Overview read preserves its own loading, empty, and error state.
28. Mobile layout remains readable without horizontal page overflow.
29. No trading or mutation controls are introduced.
30. No backend files change.

## Validation plan

### Focused tests

Run focused tests covering changed surfaces:

```bash
npm run test:web -- \
  tests/app_shell.test.tsx \
  tests/overview.test.tsx \
  tests/paper_broker_state.test.tsx \
  tests/paper_status.test.tsx

```

Focused evidence must cover:

- one LONG broker Trade;
- one SHORT broker Trade;
- multiple Trades;
- successful empty broker inventory;
- broker unavailable;
- positive/negative/neutral unrealized P/L;
- active runtime;
- no active runtime;
- Strategy populated/empty/error;
- Experiment populated/empty/error;
- system ready/degraded/error;
- shell navigation;
- timezone selector;
- removal of lifecycle explainer;
- removal of standalone timezone copy;
- absence of DatasetSnapshot metadata;
- absence of raw `PAPER_ACTIVATION_NOT_ACTIVE` on Overview;
- absence of Next Steps;
- absence of mutation controls.

### Full frontend gate

Run:

```bash
npm run check:web
```

Existing baseline warnings may remain documented, but this workstream must introduce no new lint/type/build/test failures.

### Browser validation

Use the repository's safe frontend/browser workflow where available.

Verify at desktop and mobile widths:

- PAPER is visually primary;
- P/L is immediately scannable;
- secondary cards do not compete with current exposure;
- no horizontal page overflow;
- multiple Trades remain readable;
- empty/unavailable states remain distinct;
- nav remains usable;
- timezone selector remains usable;
- focus states remain visible.

Browser validation must not:

- start `atlas-runtime`;
- activate PAPER;
- reconcile;
- mutate OANDA;
- close or modify any Trade.

If the configured local API is used during a visual check, only existing read-only GET surfaces are permitted.

## Explicit deferrals

This workstream does not redesign:

- `/data`;
- DatasetSnapshot cards on `/data`;
- DatasetSnapshot progressive disclosure;
- `/experiments` list;
- Experiment detail;
- Experiment comparison;
- `/strategies` list/detail;
- full `/paper` information architecture;
- PAPER history;
- completed PAPER Trades;
- stop-loss/target presentation;
- live Trade Strategy attribution;
- RiskDecision presentation;
- realized P/L;
- realized R;
- exit cause;
- broker reconciliation history;
- global navigation architecture;
- LIVE;
- trading controls.

Those should be handled as later focused slices.

## Approval gate

Before explicit developer approval, do not:

```text
GIT START
create a solo/* branch
create task files
modify application code
modify tests
run implementation validation
```

After approval, Solo should:

```text
verify base/current repo state
-> register this PLAN as workstream authority
-> GIT START
-> create tasks from Suggested task boundaries
-> BUILD
-> VALIDATE
-> REVIEW
-> remediation if required
-> explicit merge approval
```

Solo should not rewrite or expand the approved PLAN merely to restate it.

If current repository reality materially conflicts with the approved PLAN, Solo should stop and report the conflict rather than silently re-plan.
