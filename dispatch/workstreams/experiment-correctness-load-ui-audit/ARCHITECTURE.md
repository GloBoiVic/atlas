# Experiments Frontend Rebuild and Workstation Refresh Blueprint

## Outcome

Replace the rejected `experiment-workflow-legacy.tsx` catch-all with genuine
responsibility-owned client modules for the Experiment list, setup and historical
data readiness, run lifecycle, completed results, metrics, equity/drawdown,
Trades, Trade detail/lineage, price chart, and trader-facing formatters. Preserve
existing routes, API requests, polling guards, domain semantics, and failure
states. No backend, API contract, Strategy, or PAPER/LIVE changes.

Extend this into a modern proprietary trading workstation refresh: adopt local
Next.js Geist Sans/Geist Mono integration, update existing Atlas semantic tokens
toward a neutral near-black direction, reduce card nesting and repeated state,
and recompose the Experiments list, New Experiment, historical loading, completed
results, and Trade detail screens around trader-first hierarchy. This remains
frontend-only; no backend, API contracts, Strategy, Experiment semantics, routes,
or PAPER/LIVE behavior changes.

## Agreed language

- **Experiment:** deterministic historical run; never call it a backtest.
- **Technical details:** progressive disclosure for IDs, fingerprints, schemas,
  policy versions, provider internals, and diagnostics.
- **Atlas token:** an existing semantic CSS variable/class from `globals.css`;
  charts resolve colors from CSS variables, never literal chart hex values.

## Decisions

- **Ownership — confirmed:** each focused module contains its state, rendering,
  and orchestration for its responsibility; shared defensive helpers and
  formatting live in lower-level support modules. The route-facing
  `experiment-workflow.tsx` remains a thin export boundary only.
- **Behavior — confirmed:** extract/rewrite behavior-preservingly from the legacy
  source material. Keep request order, polling cadence, stale-request guards,
  route parameters, API payloads, and lifecycle semantics unchanged unless the
  current UI violates the explicit trader presentation requirements.
- **Presentation — confirmed:** use Atlas classes/CSS variables and existing
  shadcn `Button`, `Select`, `Popover`, and date controls where applicable;
  replace arbitrary `slate-*`, `blue-*`, `red-*`, `emerald-*`, and `amber-*`
  presentation with semantic Atlas roles. Keep technical/provenance information
  behind a `Technical details` disclosure.
- **Charts — confirmed:** retain Lightweight Charts lifecycle and timestamp
  guards; use the existing chart role map backed by `globals.css` variables.
- **Typography — confirmed:** use the current app’s local Next.js font integration
  for Geist Sans as the global family and Geist Mono only for technical details;
  do not add external runtime font requests. Apply tabular numerals to financial
  surfaces without making the general UI monospace.
- **Theme — confirmed:** revise existing semantic values in `globals.css` rather
  than adding page-specific workarounds. Keep one restrained primary accent,
  reserve positive/negative/amber for meaning, and remove legacy palette utilities
  from refreshed areas. Preserve compatibility aliases only for untouched screens.
- **Composition — confirmed:** recompose rather than recolor. New Experiment
  prioritizes Strategy, EUR/USD · 15m, period, historical data state, settings,
  account, costs, and one Run action. Results prioritize performance, equity /
  drawdown, Trades, and Trade analysis. Provenance appears once under Technical
  details.
- **Testing — assumed:** existing frontend tests are the behavioral baseline;
  add focused ownership/formatting assertions only where the rebuild requires
  them. Visual correctness is gated by Local Host, not tests alone.

## Constraints and risks

- Legacy code is 3,133 lines and currently contains all behavior; extraction must
  avoid accidentally changing API behavior or hidden error handling.
- `globals.css` contains compatibility aliases for old classes; new modules must
  not rely on those aliases or retain the old palette classes.
- Completed results must use immutable Experiment data and must not fabricate
  unavailable metrics or expose failed partial results as trustworthy.
- Local Host may expose API fixture/backend failures; distinguish those from UI
  defects, but still verify all reachable states and record blocked flows.
- Font loading and chart rendering can fail silently if local font integration or
  CSS-variable mapping is wrong; verify computed styles and chart readability in
  the browser, not only source text.

## Ordered implementation

1. Establish shared types/defensive helpers and `lib/experiment-formatters.ts`
   without legacy imports; keep raw IDs out of primary trader-facing labels.
2. Move list and setup state machines into `experiments/experiment-list.tsx`
   and `experiments/experiment-setup.tsx`; make `load-status.tsx` own durable
   historical status and technical disclosure.
3. Move run lifecycle into `experiment-status.tsx`, completed result composition
   into `experiment-results.tsx`, and metric/equity/trade sections into their
   named modules.
4. Move Trade detail, lineage, and price chart implementation into their named
   modules; keep chart CSS-variable role resolution in `chart-support.ts`.
5. Make `experiment-workflow.tsx` export only the real owners and shared
   compatibility symbols required by tests/routes, then delete the legacy file.
6. Validate source ownership (no legacy imports/arbitrary palette/chart hex), run
   the complete frontend checks, and perform Local Host visual flow validation.
7. Refresh `frontend/app/layout.tsx`, `frontend/app/globals.css`, and the shared
   shell only as needed for local Geist fonts, neutral semantic tokens, tabular
   numerals, compact controls, and workstation hierarchy. Keep non-Experiment
   screens behaviorally intact.
8. Recompose the five Experiment surfaces (list, setup/load, run/results,
   completed result, Trade detail) by removing redundant copy/panels, relocating
   provenance into one disclosure, and improving timeout/running UX with
   elapsed/last-updated/indeterminate activity without inventing completion
   percentages or changing API semantics.
9. Iterate in Local Host per screen: inspect current state, screenshot, interact
   with real controls, inspect computed font/token styles, diagnose console and
   network, fix visual defects, and repeat after every browser-found fix.

## Validation

- `npm run test:web`
- `npm run typecheck:web`
- `npm run lint:web`
- `npm run build:web` and available format/check command
- Source audit for legacy file/imports, forbidden palette classes, and chart hex
  literals.
- Local Host: discover active tab, snapshot/read each reachable route, interact
  with setup/run/trade controls, verify resulting states, inspect computed Atlas
  token styles, then diagnose console and failed network requests. Repeat after
  every browser-found fix.
- Font acceptance: computed body/navigation/control styles resolve to Geist Sans;
  technical disclosure fields resolve to Geist Mono; financial surfaces use
  tabular numerals; no external font request is introduced.
- Visual acceptance: near-black neutral-dark canvas, restrained charcoal surfaces,
  sparse semantic color, shallow hierarchy, readable charts, trader-first copy,
  and no substantial redundant/nested panels across the five Experiment screens.

## Consistent Experiment and Trade presentation extension

### Outcome

Remove hardcoded EUR/USD, OANDA, and PAPER labels from refreshed Experiment and
Trade surfaces where API data already contains identity. Create one shared,
trader-facing identity/summary vocabulary used consistently by the Experiment
result page and individual Trade page. Keep only information that helps a trader
understand setup, risk, outcome, and execution; place genuinely diagnostic
provenance in a compact, formatted Technical details disclosure.

### Decisions

- **Dynamic identity — confirmed:** derive instrument, broker/venue, account
  label, timeframe, and strategy name from the returned Experiment/Trade payload;
  display fallbacks such as “Instrument unavailable” rather than inventing
  values. Do not alter API contracts.
- **Shared presentation — confirmed:** add a small shared trader-summary module
  for identity rows, price/money/percent/R formatting, and semantic outcome
  labels. Both pages use the same labels, spacing, table conventions, and
  disclosure affordance.
- **Information architecture — confirmed:** primary Trade view contains outcome,
  entry/stop/target/exit, setup explanation, chart, and a compact execution
  timeline. Remove proposal-state and financing/model jargon from the primary
  view when it does not aid a trader. Technical details contains only useful
  audit evidence: rationale facts, risk decision summary, order/fill provenance,
  and omitted chart range; remove duplicated nested panels and raw UUIDs.
- **Formatting — confirmed:** all numeric values pass shared formatters. Prices
  use five decimal places where applicable, money uses USD currency formatting,
  quantities use grouped decimals, and R values use `R` rather than `x` where
  the field is an R multiple. Technical raw values may use Geist Mono but remain
  human-formatted and bounded.
- **Table choice — confirmed:** use a compact definition/table treatment for
  stable key-value facts and a real table for multi-event execution records.
  Avoid turning every section into a bordered card or repeating the same fact in
  multiple places.

### Ordered implementation

1. Trace the exact identity fields present in Experiment and Trade API payloads;
   add shared extraction/formatting helpers without backend changes.
2. Apply the shared identity row and result summary treatment to Experiment
   results and the Trade header/summary; remove hardcoded venue/instrument labels.
3. Recompose Trade detail so primary content is trader-facing; make the chart
   and setup explanation prominent, simplify outcome facts, and replace generic
   recursive raw dumps with bounded technical disclosure/table sections.
4. Format every visible financial, price, quantity, and R value; ensure technical
   details do not expose raw Decimal strings or UUIDs as labels.
5. Update stale frontend assertions only where the deliberately rejected
   presentation changes; run tests/typecheck/lint/build.
6. Validate in Local Host by inspecting Experiment and Trade screens, expanding
   Technical details, interacting with trade links, checking responsive layout,
   computed fonts/tokens, chart readability, console, and network. Repeat after
   browser-found fixes.

### Acceptance

- No refreshed Experiment/Trade UI hardcodes EUR/USD, OANDA, PAPER, or a fixed
  timeframe when dynamic payload data is available.
- Shared identity and summary patterns are visually consistent across both pages.
- Primary views are trader-first; technical disclosure is concise, formatted,
  non-duplicative, and useful.
- No raw Decimal strings or raw UUIDs appear in trader-facing labels.
- Tests, typecheck, lint, build, and Local Host validation pass.

## Approval gate

## Authoritative identity contract extension

### Required information contract

The Strategy, Experiment, and Trade screens will answer their trader questions
from an explicit backend contract rather than the current UI field set. The
Experiment identity object is the source for Experiment and Trade context:

```json
{
  "strategyVersion": { "id": "…", "displayName": "…", "version": 1 },
  "instrument": { "code": "…", "baseCurrency": "…", "quoteCurrency": "…" },
  "analytical": { "resolution": "…", "priceComponent": "…" },
  "provider": { "name": "…", "symbol": "…" },
  "tradingPeriod": { "start": "…", "end": "…" }
}
```

The Strategy detail contract additionally exposes Strategy-owned market
requirements, trader-readable methodology, parameter definitions, and research
usage summary. The Trade detail response does not own duplicate identity; the
Next.js Trade page loads the owning Experiment identity.

### Payload comparison and gaps

| Required fact | Current authoritative source | Current read API | Action |
|---|---|---|---|
| StrategyVersion display identity | StrategyVersion + Strategy rows | Present in Strategy and Experiment responses, but not one normalized identity object | Normalize into identity object |
| Analytical timeframe/resolution | StrategyVersion `primary_timeframe`; DatasetSnapshot `base_resolution` | Strategy response has `timeframe`; Experiment has simulation config only | Expose persisted StrategyVersion requirement and snapshot analytical facts |
| Analytical price component | Strategy requirement (`MID`); V2 snapshot components | Only buried in simulation/provenance | Expose explicit `analytical.priceComponent` |
| Instrument | DatasetSnapshot → VenueInstrument → Instrument | Missing from Experiment/Trade responses; present in domain/persistence | Join and expose; no new persistence |
| Provider/venue | DatasetSnapshot → VenueInstrument | Missing from Experiment/Trade responses; capability endpoint is not immutable Experiment truth | Join and expose from owning snapshot |
| Trading period | Experiment `trading_start/end` | Present as top-level fields | Include in normalized identity |
| Required context | StrategyVersion `required_historical_context_bars` | Present on Strategy version options/detail | Expose under Strategy market requirements |
| Strategy description | Strategy row / registry definition | Present as description, but current text includes market facts | Keep description; add structured requirements rather than parsing text |
| Strategy methodology | Strategy implementation/domain definition | Not exposed as trader-facing API content | Add read-only methodology fields from the registered Strategy definition; do not expose source code |
| Research summary | persisted Experiment usage queries | Strategy detail has counts/latest timestamp, not tested periods | Add tested-period summary derived from Experiment rows if available |
| Trade execution facts | Trade/Intent/Risk/Order/Fill persistence | Trade response exposes them, but recursive/raw to UI | Keep API facts; frontend formats and bounds them under Technical details |

### Decisions

- **Backend source of truth — confirmed:** add only read-contract fields and
  joins over existing immutable rows. Do not add migrations or duplicate
  identity persistence unless a fact is proven absent.
- **Experiment identity assembly — confirmed:** `_detail` resolves the owning
  DatasetSnapshot → VenueInstrument → Instrument and StrategyVersion requirement
  and returns one normalized `identity` object. List, detail, and creation
  responses use the same shape where a database session is available.
- **Trade context — confirmed:** Trade detail fetches its owning Experiment and
  renders `identity`; Trade does not invent, duplicate, or infer market identity.
- **Strategy requirements — confirmed:** Strategy detail exposes structured
  requirements from the StrategyVersion/domain requirement boundary. Never parse
  the description string in React or infer from current EUR/USD scope.
- **Missing methodology — confirmed:** if the persisted/registered Strategy
  definition does not yet contain trader-readable methodology fields, add those
  to the read representation at the API boundary from existing definition data;
  do not expose Python source or create new persistence.
- **Contract typing — confirmed:** define Pydantic response models for the new
  identity/requirements envelopes and update generated frontend types only via
  the repository’s existing generation workflow if required; do not handwave
  fields through `Record<string, unknown>` as the final contract.

### Ordered implementation

1. Add/extend backend Pydantic read models for ExperimentIdentity,
   StrategyMarketRequirements, and normalized StrategyVersion identity; update
   Strategy/Experiment response construction with existing persisted/domain data.
2. Add focused backend tests for identity joins, immutable period/config facts,
   missing-related-row failure behavior, and list/detail consistency. No new
   persistence.
3. Update frontend API types/client and shared identity formatter to render only
   returned identity/requirements; remove all remaining hardcoded identity.
4. Recompose Strategy screen around methodology/requirements/research questions;
   recompose Experiment and Trade headers/config blocks around the shared identity
   and concise trader tables. Keep technical provenance secondary and formatted.
5. Run backend/frontend tests, typecheck, lint, build, and Local Host validation
   of Strategy → Experiment → Trade identity consistency and technical disclosure.

### Acceptance

- Every required identity fact shown in primary UI comes from the authoritative
  API object; no frontend hardcoding or inference remains.
- Experiment and Trade display the same owning Experiment identity.
- Strategy display uses structured API requirements and methodology, not raw JSON
  or source-code text.
- Missing facts are explicit/unavailable, never guessed; no new persistence is
  introduced without evidence.
- Contract, tests, typecheck, lint, build, and Local Host checks pass.

Implementation is not authorized until the developer explicitly approves this
blueprint and the ordered workflow. Git operations are out of scope.
