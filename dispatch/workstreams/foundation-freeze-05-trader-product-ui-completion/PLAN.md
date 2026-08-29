# Foundation Freeze 05 — Trader Product UI Completion

## Outcome

Make the current Atlas historical-research workflow read and behave as one
coherent trader workstation:

`StrategyVersion → period/data readiness → configuration → run → result → Trade evidence → comparison`

The workstation will make the current historical-only capability explicit, keep
PAPER/LIVE visibly future-only, lead with trader decisions and evidence, and
keep technical provenance available without making it the normal workflow.

## Classification

`Feature`

Exploration found a bounded product/UI completion workstream, not a Critical
architecture decision. Freeze 04 has already established the authoritative V2
historical execution path, and this plan does not change domain ownership,
financial semantics, Strategy methodology, or lifecycle safety. If implementation
reveals a need to alter those authorities, stop and reclassify before coding.

## Status and approval gate

- **Status:** `READY_FOR_USER`
- **Implementation:** T002 regenerated the stale OpenAPI client; targeted freshness/typecheck validation passed. Approved final exception reopened T001 and its fail-closed list-result remediation is complete and targeted-reviewed.
- **Developer approval:** explicit approval received for this patched PLAN
- **Approval gate:** satisfied; BUILD dispatch follows artifact pre-creation
- **Architecture artifact:** not planned; no cross-domain contract or Critical
  architecture change is authorized by this plan

## Current repository state

- **Inspected/base branch:** `main`
- **Base SHA:** `e91362ccad7f47be4b9d40d5c9531fba6f5c42a2`
- **Execution branch:** `solo/foundation-freeze-05-trader-product-ui-completion`
- **GIT START:** completed on the actual checkout; verified branch is the execution source of truth
- **Pre-existing untracked files:** `.codegraph/`, `frontend/.env.local`; preserve
  and exclude from all workstream changes
- **Current dispatch state:** no prior active workstream; this plan is the only
  proposed Freeze 05 workstream

## Exploration findings

1. Freeze 04 is closed and merged on `main`; `CURRENT.md` records the current
   product as historical Experiments and keeps PAPER/LIVE future-only. The
   existing frontend already uses Geist, Tailwind v4, dark tokens, and a
   horizontal shell, so this is adoption/refinement rather than a new design
   system.
2. The shell (`frontend/components/app-shell.tsx`) has Strategies and
   Experiments routes, but Dashboard, Deployments, Journal, and Data are disabled
   placeholders. Normal users need an explicit historical-research mode/capability
   boundary rather than an implication that PAPER/LIVE workflows are available.
3. Strategy browsing (`frontend/components/strategy-history.tsx`) exposes catalog
   and immutable version history, but version context is spread across dense
   metadata, technical implementation details, and settings. There is no clear
   version-to-Experiment handoff or focused distinction between “usable for a new
   Experiment” and “retained for provenance.”
4. Experiment setup (`frontend/components/experiments/experiment-setup.tsx`) owns
   the correct durable load, coverage validation, and creation gates, but the
   screen is a very large mixed form with repeated “Strategy settings” sections,
   several technical-detail disclosures, and competing calls to action. The
   common path is not visually ordered as StrategyVersion → readiness →
   configuration → run.
5. The Experiment list (`frontend/components/experiments/experiment-list.tsx`)
   preserves canonical metric states and completed-only comparison eligibility,
   but uses generic “Experiment 1” labels, does not consume the existing
   `nextCursor`, and offers limited navigation context. The API already returns
   the immutable strategy/identity/metrics facts needed for a better list; no fake
   labels or client-recomputed metrics are permitted.
6. Result rendering currently nests the completed result beneath a generic Run
   status panel (`experiment-status.tsx`), then places price evidence under
   “Technical details” and assumptions/provenance at the end
   (`experiment-results.tsx`). The required trader hierarchy is instead outcome →
   key metrics → equity/trades → Strategy evidence/diagnostics → technical
   provenance, while preserving failed and zero-Trade fail-closed states.
7. Trade detail already receives authoritative rationale, setup facts, Risk
   decisions, Orders/events, Fills, protection levels, outcome, and bounded chart
   context from `backend/experiments/results.py`. The frontend currently adds
   hardcoded explanatory copy, presents rationale/lineage under “Technical
   details,” and uses a generic recursive renderer that exposes implementation
   field names. The UI should translate existing facts into a trader-readable
   progressive hierarchy without re-detecting Strategy patterns.
8. Comparison (`frontend/components/experiment-comparison.tsx`) already uses the
   canonical read-only comparison endpoint, preserves selection order, surfaces
   warnings before metrics, and does not rank or recommend a winner. It needs
   clearer comparison identity, changed-fact emphasis, result/trade navigation,
   and less raw JSON/internal naming—not new comparison semantics.
9. The bounded list APIs have material query-shape inefficiencies. The
   `/api/v1/experiments` route reads up to 100 rows, then composes each row with
   `results.detail`, gap reads, identity reads, and related lookups in a loop.
   Strategy catalog listing likewise performs per-Strategy version and usage
   reads. These are suitable for narrow batch/projection improvements that return
   the same authoritative payload; broad persistence or caching work is not.
10. Single-Experiment result, comparison (maximum four), and Trade detail reads
    are already explicitly bounded. Optimize them only if a focused query-count
    or latency check proves a material regression for the screens in scope.

## Scope

### Included

- Shared historical-research workstation shell and page hierarchy using Geist,
  near-black/charcoal surfaces, subtle borders, compact density, existing Atlas
  tokens, and existing shadcn-style controls.
- Explicit current capability treatment: historical research/Experiment is
  available now; PAPER and LIVE are future-only and must not appear as executable
  workflows. Disabled future navigation may remain, but its meaning must be
  clear and non-misleading.
- Strategy catalog and Strategy detail improvements:
  - readable methodology identity and immutable StrategyVersion context;
  - usable/retained-for-provenance state;
  - market requirements, parameter schema, and Experiment usage in trader terms;
  - direct handoff to a new Experiment with the selected StrategyVersion;
  - implementation keys, fingerprints, Git refs, and raw IDs hidden or
    progressively disclosed outside the normal path.
- Experiment setup redesign around four visible stages:
  1. StrategyVersion;
  2. requested period and historical-data readiness;
  3. Strategy/risk/simulation configuration;
  4. review and Run Experiment.
     Preserve durable historical-load status, coverage validation, immutable input
     capture, timeout/unknown handling, and all current fail-closed gates.
- Experiment list/navigation improvements using the current API truth:
  human-readable identity, StrategyVersion, period, status, canonical headline
  metrics, completed-only selection, cursor-based continuation where useful, and
  clear links to results, setup, and comparison.
- Result hierarchy improvements:
  outcome/status and identity first; key metrics next; equity/drawdown and Trades
  next; Strategy evidence and diagnostics after that; assumptions/provenance as
  secondary detail. Preserve canonical metric states, unavailable values, zero
  Trades, failed Experiments, bounded chart disclosures, and immutable data use.
- Trade inspection improvements that make the existing facts easy to follow:
  why the Strategy acted; persisted setup/evidence; Risk decision; Order/Fill;
  protection; and outcome. Keep the chart bounded and authoritative, with
  explicit semantic labels and progressive disclosure for execution lineage.
- Comparison workspace refinement using the existing endpoint and rules:
  configuration differences/warnings before performance, compact canonical metric
  comparison, no winner/best/recommendation language, and direct navigation back
  to each Experiment and its Trades.
- Narrow backend read/query work only where it materially supports these screens:
  batch or projected list metadata for Experiments and Strategies, preserving
  response meaning and OpenAPI compatibility. Add focused query-shape regression
  evidence. Do not add a new read model, cache, persistence layer, or semantic
  API redesign.
- UI tests, API contract tests where read composition changes, and required Local
  Host browser acceptance using structured snapshots/interactions first. Capture
  screenshots only where text/accessibility evidence cannot diagnose visual
  hierarchy.

### Excluded

- Any PAPER or LIVE implementation, broker/account/deployment workflow, live
  status, order submission, reconciliation, or exposure management.
- New Strategy methodology, StrategyVersion mutation, new broker, Instrument,
  timeframe, market-data product, or simulation behavior.
- Changes to Risk ownership, Order/Fill/Position/Trade accounting, result
  methodology, no-lookahead, gap policy, immutability, or failure authority.
- Fake/sample product data, client-side metric recomputation, hidden fallback
  values, or raw UUIDs as normal labels.
- Optimization, ranking, winner labels, heatmaps, exports, dashboards, Journal,
  notifications, search, mass pagination, responsive redesign beyond what is
  needed to keep these screens usable, or speculative North Star features.
- Dependency additions unless an existing stack/component cannot satisfy a
  demonstrated in-scope need and approval is obtained.

## Product and authority rules

- Backend/API and persisted Experiment facts remain authoritative. Frontend work
  may change presentation, composition, navigation, and request efficiency, not
  financial meaning.
- Completed results use the Experiment’s immutable StrategyVersion, parameters,
  DatasetSnapshot, Risk, simulation, and result facts; never current defaults.
- Failed Experiments show failure and next action, not partial trustworthy
  output. Zero-Trade Experiments remain valid with unavailable Trade-dependent
  metrics shown as unavailable, not fabricated zeros.
- Only existing Strategy evidence/landmarks/setup facts are displayed; the UI
  must not re-implement EMA sweep/confirmation detection.
- Green/red are reserved for trading semantics such as positive/negative outcome,
  direction, stop, target, and critical state. Neutral charcoal surfaces/text,
  restrained action/selection treatment, and amber warnings handle everything
  else. Pair color with text/icon/position.
- Technical provenance remains inspectable for reproducibility, but normal trader
  workflows should lead with meaning rather than implementation keys, schema
  names, internal IDs, SQL-shaped field names, or raw payload dumps.

## Proposed BUILD task breakdown

Tasks are proposed only; task files and role artifacts will be pre-created after
approval and before dispatch.

1. `T001-read-projections-and-navigation`: add the smallest batch/projected
   metadata path for materially inefficient bounded list reads, prove equivalent
   response facts, consume existing experiment cursors, and establish shared
   human-readable identity/status/metric presentation helpers. No new API
   semantics.
2. `T002-shell-strategy-and-setup`: refine the workstation shell’s current/future
   boundary, Strategy catalog/version context, version-to-Experiment handoff, and
   four-stage Experiment setup while preserving all existing load/validation/run
   behavior and API calls.
3. `T003-results-trade-and-comparison`: implement the result hierarchy, evidence
   and diagnostics placement, trader-readable Trade inspection/progressive
   lineage, and comparison workspace/navigation using authoritative payloads only.
4. `T004-acceptance-hardening`: add/update focused frontend/API regressions for
   states, navigation, hidden technical details, immutable evidence, and query
   bounds; run quality gates and Local Host structured browser acceptance for the
   complete historical research flow.

Task order is intentional: data/read shape first, then shared shell/setup, then
dependent result/comparison presentation, then independent acceptance.

## Acceptance criteria

### Workflow and scope

- A trader can start from a StrategyVersion, understand its requirements and
  availability, enter setup with that version selected, see the period/data
  readiness gate, configure the Experiment, and run it without guessing the next
  action.
- The visible workstation consistently identifies the current scope as historical
  research/Experiments. PAPER/LIVE are clearly future-only and no control implies
  that either is implemented.
- Strategies, Experiments, results, Trades, and comparison use human-readable
  labels; raw UUIDs, implementation keys, fingerprints, schema names, and raw
  JSON are not normal trader-facing content.

### Authoritative behavior

- Existing backend authority and API meaning are preserved byte-for-byte where
  practical, or by explicit response-equivalence tests when read composition is
  optimized.
- No new Strategy methodology, broker/instrument/timeframe support, PAPER/LIVE
  behavior, or financial/domain semantic change enters the diff.
- Historical load, coverage validation, durable status, failed/unknown behavior,
  completed-result immutability, zero-Trade handling, canonical metrics, and
  bounded evidence disclosures remain correct.
- Trade detail presents persisted Strategy rationale/evidence, Risk decisions,
  Orders/Fills, protection, and outcome in that order of understanding; it does
  not infer or recompute Strategy facts in the browser.
- Comparison keeps 2–4 completed Experiment limits, warnings, selection order,
  canonical metric definitions, unavailable states, and the explicit no-winner
  boundary.

### Performance and quality

- Focused query evidence demonstrates that the bounded Experiment/Strategy list
  screens no longer perform avoidable per-row metadata composition, or documents
  why a measured path is already within the accepted bound. No speculative cache
  or generalized query framework is introduced.
- Existing frontend unit tests plus new/changed tests pass; changed backend/API
  tests pass; generated OpenAPI client remains fresh if the public contract is
  touched; `npm run check:web` and the relevant backend quality gates pass with
  no new diagnostics attributable to this workstream.
  - Local Host acceptance uses discover → structured accessibility snapshot → one interaction at a time → bounded verification. It covers StrategyVersion handoff, setup readiness, Experiment list/detail, completed result hierarchy, Trade evidence/lineage, comparison, console errors, and failed requests. Failed and zero-Trade states must remain covered by automated tests, and should also be exercised in Local Host when suitable fixtures already exist. Screenshots are supplemental visual
    evidence only.

## Branch, artifacts, and lifecycle

- **Before approval:** no branch switch, implementation, BUILD dispatch, or role
  artifact creation.
- **After approval:** reconcile developer feedback into this PLAN, inspect Git
  state again, perform GIT START on
  `solo/foundation-freeze-05-trader-product-ui-completion`, record the verified
  branch/base SHA, then pre-create `tasks/T001-*.md` through `T004-*.md` and the
  required validation/review artifacts.
- **Roles:** fresh `solo-flow-worker` BUILD sessions for T001–T004 as needed;
  fresh VALIDATE only after all BUILD tasks are DONE; fresh REVIEW only after
  VALIDATION PASS. No ARCHITECT role is required unless the scope is reclassified
  Critical.
- **Closure:** do not claim READY_FOR_USER until task receipts, validation,
  review, branch/status/diff, Git state, and Local Host evidence all pass. Merge
  and GIT END require separate explicit developer approval.

## Phase and task state

- **Phase:** BUILD
- **Tasks:** T001 `DONE` final list-result gating remediation; T002/T003/T004 complete
- **Validation:** `PASS`; affected list regression, response-equivalence, and 3-SELECT query-bound evidence passed; unrelated evidence preserved
- **Review:** `PASS`; targeted review resolved the original IMPORTANT finding with no new blocker

## Current concerns

- Existing repository-wide format/Ruff/lint warnings and two minor accessibility
  cleanups remain documented as non-blocking by VALIDATE. Fresh validation found
  two changed test/fixture regressions requiring T002/T004 remediation.
- Review findings for StrategyVersion requirements, DatasetSnapshot identity,
  and Trade-detail ordering are remediated in T002/T003 receipts.
- T002 corrected the changed integration regression and preserved the full
  StrategyVersion requirements assertion; T004 corrected E2E fixture facts and
  completed-row setup while preserving explicit ambiguity blocking.
- Fresh VALIDATE found `frontend/lib/api.generated.ts` stale versus the current
  OpenAPI output. T002 regenerated the committed client with the repository
  generation path and recorded a byte-equivalent freshness check without changing
  API meaning. Fresh targeted validation is required before the initial broad
  REVIEW.

- Broad REVIEW found an IMPORTANT PRODUCT BLOCKER in the optimized Experiment
  list projection: `backend/api/experiments.py` can pass persisted result rows
  through for non-`COMPLETED` Experiments, bypassing the existing fail-closed
  result gating. Owning task is T001. The smallest remediation is to filter the
  batch result projection to `COMPLETED` rows (or preserve the existing service
  gate) and add one regression for a non-completed Experiment with a result row.
  The smallest revalidation is the affected list/API contract regression and
  targeted response-equivalence/query-bound check; prior unrelated evidence is
   preserved. Developer approved this as the second and final automatic-remediation
   exception. Reopen T001 only. Preserve the existing bounded-query improvement
   for completed rows; ensure only `COMPLETED` Experiments receive projected
   result/metric facts; add a regression for a non-completed Experiment with a
   persisted result row. After BUILD, run only targeted validation for the
   affected list regression, response-equivalence, and query-bound evidence, then
   targeted REVIEW of this original finding only. If targeted REVIEW finds another
   blocker, stop.

## Next action

Report `READY_FOR_USER` and await separate explicit approval before GIT END and
merge. Do not commit, merge, or clean up the understood worktree without that
approval.
