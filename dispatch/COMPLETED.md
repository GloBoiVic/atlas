# Completed

<!-- completion-id: dogfood-02-account-details-position-projection -->
## Dogfood 02 — Account Details Position Projection — completion record

- **Date/status:** 2026-09-04 — terminal closure; T001 BUILD, independent VALIDATE, and
  independent REVIEW **PASS** with no unresolved Critical or Important findings.
- **Commit:** `bd3ea7b` Repair OANDA Account Details Position projection; the feature branch
  was pushed to GitHub and fast-forward merged into `main`.
- **Scope:** Added a pure Account Details-specific projection of OANDA lifetime Position
  representations, excluding validated zero/zero historical records while retaining genuine
  exposure and existing fail-closed invariants. Preserved strict `/openPositions` semantics,
  derived count authority, one Account Details frontier, Trade/Order meaning, exposure,
  runtime, P05, reconciliation, Strategy/Risk/execution, and persistence/schema boundaries.
- **Validation:** Focused and affected suites passed; safe backend suite **1221 passed, 4
  skipped, 115 deselected**; changed-slice Ruff/Pyright and `git diff --check` passed. No
  credentials, OANDA calls, provider mutation, activation, runtime start, or manual repair
  occurred.
- **Review:** Independent review **PASS**; no unresolved Critical or Important findings.
- **Git/state:** `solo/dogfood-02-account-details-position-projection` was pushed and
  fast-forward merged into `main`; `dispatch/ACTIVE.md` was cleared; all workstream and
  validation/review evidence is preserved.

<!-- completion-id: dogfood-01-lifecycle-advanced-activation-fence -->
## Dogfood 01 — Lifecycle-Advanced Activation Fence — completion record

- **Date/status:** 2026-09-04 — terminal closure; T001 BUILD, independent VALIDATE and
  REVIEW, and R001/R002 remediation BUILD/VALIDATE/REVIEW chains **PASS** with no unresolved
  Critical or Important product findings.
- **Commit:** `4d21682` Implement lifecycle advanced activation fence; the feature branch was
  fast-forward merged into `main` and pushed to GitHub.
- **Scope:** Added the semantic new-session history classifier for lifecycle-ended incomplete
  Fills only when complete coherent durable Fill and applied `LIFECYCLE_ADVANCED` evidence is
  present. Preserved strict same-attempt recovery, provider-free activation POST, fresh startup
  capability/account/flatness gates, P05/Risk/claim/mutation barriers, and historical truth.
  No schema/migration or provider-neutral reconciliation semantics changed; no Dogfood 02 or
  broker-capable operation occurred.
- **Validation:** Focused suite **185 passed**; safe backend suite **1182 passed, 4 skipped,
  115 deselected**; changed-slice Ruff/Pyright, Alembic, and diff checks passed. R001 and R002
  independently closed the contradictory durable-evidence findings. PostgreSQL integration was
  unavailable because no dedicated test URL was configured; unrelated repository-wide tooling
  baseline findings remain documented as LOW limitations.
- **Review:** Final R002 independent review **PASS**; earlier failed review artifacts remain
  immutable evidence, with no unresolved Critical or Important findings.
- **Git/state:** `solo/dogfood-01-lifecycle-advanced-activation-fence` was pushed and
  fast-forward merged into `main`; `dispatch/ACTIVE.md` was cleared; all workstream and
  remediation evidence is preserved. No credentials, runtime start, activation, historical
  repair, or provider/broker mutation occurred.

<!-- completion-id: dogfood-01-paper-activation-response-projection -->
## Dogfood 01 — PAPER Activation Response Projection — completion record

- **Date/status:** 2026-09-03 — T001 BUILD, independent VALIDATE, and independent
  REVIEW **PASS**; no unresolved Critical or Important findings.
- **Commit:** `8227f37` Repair PAPER activation response projection; feature branch
  was pushed to GitHub and merged into `main` as `bc62431`.
- **Scope:** Restored the existing durable `requested_at` value in the
  `PaperRuntimeActivation.to_json()` projection and added deterministic real-domain
  coverage for create, active, detail/status, and stop response paths. Existing
  Decimal-string `riskPerTrade`, identity, lifecycle, transaction, Risk, execution,
  reconciliation, runtime, broker, schema, and migration semantics were unchanged.
- **Validation:** Focused projection checks **2 passed**; reconciled API/runtime
  suite **60 passed** with one pre-existing Starlette/httpx deprecation warning;
  changed-slice Ruff, Pyright, and `git diff --check` passed. No runtime start,
  durable activation mutation, OANDA request, broker mutation, or capital-capable
  operation occurred.
- **Review:** Independent review **PASS** with no unresolved Critical or Important
  findings. Non-blocking tooling notes are preserved in the immutable validation and
  review artifacts.
- **Git/state:** Feature branch and `main` were pushed to GitHub; the feature branch
  was merged into `main`; `dispatch/ACTIVE.md` was cleared; all workstream evidence
  is preserved.

<!-- completion-id: paper-06-runtime-activation -->
## PAPER 06 — Runtime Activation — completion record

- **Date/status:** 2026-09-03 — terminal closure approved; T001–T008 and the
  post-cap R004–R006 BUILD, independent VALIDATE, and independent REVIEW chains
  **PASS** with no unresolved Critical, Important, or Minor product findings.
- **Commit:** `5927b1c` Implement PAPER runtime activation; the feature branch was
  pushed to GitHub and fast-forward merged into `main`.
- **Scope:** Added the bounded durable PAPER runtime activation/orchestration,
  ownership and STOP controls, deterministic Strategy progression, and the
  provider-specific startup capability proof. R004 corrected terminal P05 safety
  classification so `NOT_RUN` alone is not unsafe for definite terminal outcomes;
  R005 proves the configured OANDA Practice USD account is non-MT4 before
  `RUNNING`; R006 preserves exact Decimal `risk_per_trade` identity through
  PostgreSQL with unconstrained `NUMERIC`. Fresh account truth remains distinct
  from historical `FILLED_PROTECTED` truth, and runtime has no direct broker
  mutation authority.
- **Validation:** Full deterministic non-integration/non-external backend suite
  **1108 passed, 4 skipped, 115 deselected**; dedicated PAPER 06 PostgreSQL
  suite **17 passed**; focused PAPER 05/OANDA and cross-remediation regressions
  passed; exact Decimal round-trip/replay/conflict and migration
  upgrade/downgrade/upgrade passed; Alembic current/check, changed-slice Ruff,
  focused Pyright, and `git diff --check` passed. The documented repository-wide
  Pyright baseline remains non-blocking tooling debt. No real OANDA request,
  credentials, broker mutation, PAPER activation, or LIVE operation occurred.
- **Review:** R004, R005, and R006 independent review artifacts — **PASS**;
  no unresolved Critical, Important, or Minor product findings and no R007
  required or authorized.
- **Git/state:** `solo/paper-06-runtime-activation` was pushed and fast-forward
  merged into `main`; `main` was pushed to GitHub; `dispatch/ACTIVE.md` was
  cleared; all workstream and remediation evidence is preserved. No GIT END
  capital-capable operation or real broker mutation occurred.

<!-- completion-id: paper-05-persistence-reconciliation -->
## PAPER 05 — Persistence + Reconciliation — completion record

- **Date/status:** 2026-09-02 — terminal closure approved; T001–T003 and R001–R004
  evidence preserved. The final R004 BUILD, independent VALIDATE, and fresh REVIEW
  chains **PASS** with no unresolved Critical or Important findings. Earlier failed
  T003/R003 evidence remains immutable and is superseded by the approved R004
  correction chain.
- **Commit:** `73c19d8` Correct PAPER reconciliation terminal history conflict; the
  feature branch was pushed to GitHub and fast-forward merged into `main`.
- **Scope:** Corrected the provider-neutral reconciliation history rule so an
  attributable later Fill after durable `REJECTED` or `CANCELLED` history advances
  execution truth while retaining `ReconciliationStatus.CONFLICT` and the
  `CONFLICT` finding across exact Order → Transaction and bounded Transaction-range
  paths. Added deterministic exact/range, Trade/protection, NULL/UNKNOWN, same
  terminal, and contradictory terminal regressions. No migration/schema, Strategy,
  Risk, PAPER 04 mutation, runtime, activation, OANDA write, repair, or LIVE behavior
  changed.
- **Validation:** R004 matrix **12 passed**; focused PAPER/OANDA suite **107 passed**;
  broad safe backend **975 passed, 4 skipped, 97 deselected**; changed-slice Ruff,
  Pyright, and `git diff --check` passed. Dedicated PostgreSQL tests were skipped
  without `ATLAS_TEST_DATABASE_URL`; stale configured Alembic state and unrelated
  repository-wide Ruff/Pyright baseline findings remain documented non-blocking
  environment concerns. No real OANDA request, credential, broker mutation, PAPER
  activation, runtime operation, or capital-capable action occurred.
- **Review:** `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R004-paper-05-terminal-history-conflict/REVIEW.md`
  — fresh independent **PASS**; no unresolved Critical or Important findings and no
  R005 warranted or authorized.
- **Git/state:** `solo/paper-05-persistence-reconciliation` and `main` were pushed to
  GitHub; the feature branch was fast-forward merged into `main`; `dispatch/ACTIVE.md`
  was cleared; all workstream evidence is preserved. No real broker mutation or
  PAPER activation occurred.

<!-- completion-id: paper-04-broker-execution -->
## PAPER 04 — Broker Execution — completion record

- **Date/status:** 2026-09-02 — terminal closure approved; T001–T005 BUILD,
  independent validation, Critical review, and R001 remediation validation/review
  **PASS** with no unresolved Critical or Important findings.
- **Commit:** `ef032d1` Implement PAPER broker execution; the feature branch was
  fast-forward merged into `main`.
- **Scope:** Added the read-only OANDA Practice account/instrument capability
  gates, coherent account snapshot, provider-neutral PAPER execution contracts,
  exact MARKET/FOK/OPEN_ONLY entry translation, non-retrying entry mutation and
  bounded uncertainty readback, actual-Fill protection completion, and one-shot
  actual-Fill-derived Take Profit composition. No PAPER activation, LIVE behavior,
  persistence, reconciliation, runtime, API/UI, migration, or historical
  Experiment semantic changes were introduced.
- **Validation:** Focused execution/capability and regression suites passed;
  final broad non-integration/non-external suite **922 passed, 4 skipped**;
  changed-file Ruff format/lint, Pyright, and `git diff --check` passed. All
  mutation evidence used deterministic fakes/`httpx.MockTransport`; no
  credentialed or external OANDA mutation was performed.
- **Review:** Original Critical review found C-001; bounded R001 remediation
  preserved confirmed Fill facts/provenance for invariant violations and the
  targeted independent rereview **PASS**. Final remediation chain has no
  unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; `main` and
  `solo/paper-04-broker-execution` pushed to GitHub; active dispatch state
  cleared; workstream evidence preserved. No real broker mutation or PAPER
  activation occurred.

<!-- completion-id: paper-03-risk-executable-pricing -->
## PAPER 03 — Risk + Executable Pricing — completion record

- **Date/status:** 2026-09-02 — terminal closure approved; T001/T002/T003 BUILD, focused
  validation, and independent review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `ac5c00e` Implement PAPER executable pricing risk; the feature branch was
  fast-forward merged into `main`.
- **Scope:** Added the provider-neutral quantity-aware Risk seam, pure OANDA Practice EUR/USD
  required-side executable-pricing projection, and pure/read-only PAPER IMMEDIATE opening Risk
  composition with identity/count/pending-order gates, existing account/exposure projections,
  deterministic single-bucket capacity selection, and immutable provenance/evidence. No broker
  mutation, Order/Fill, persistence, accounting, runtime activation, API/UI, trigger execution,
  reconciliation, or LIVE behavior was added.
- **Validation:** Focused suite **173 passed**; non-integration/non-external suite **860 passed,
  4 skipped**; changed-file Ruff format/lint, Pyright, and `git diff --check` passed. The optional
  PostgreSQL candidate vertical-flow integration was not run because `ATLAS_TEST_DATABASE_URL`
  was unset. No credentialed OANDA or broker-mutation checks were run.
- **Review:** `dispatch/workstreams/paper-03-risk-executable-pricing/REVIEW.md` — **PASS**;
  no unresolved Critical or Important findings.
- **Git/state:** Required PLAN, ARCHITECTURE, T001/T002/T003, validation, and review evidence
  preserved; the feature branch was fast-forward merged into `main`; active dispatch state
  cleared; GitHub push follows after closure commit. No PAPER activation or capital-capable
  behavior was performed.

<!-- completion-id: paper-02-strategy-evaluation -->
## PAPER 02 — Strategy Evaluation — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; T001/T002 BUILD, focused validation,
  and independent review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `3798d61` Implement PAPER Strategy evaluation; the feature branch was pushed to
  GitHub and fast-forward merged into `main`.
- **Scope:** Added the read-only PAPER current analytical frontier seam for explicit UTC-cutoff,
  completed native OANDA EUR/USD M15/MID data and eligible warm-up context, plus exact persisted
  StrategyVersion composition through registry provenance, complete explicit parameters, caller-held
  Strategy state, explicit FinancialPositionState-to-Strategy-PositionState translation, and the
  existing `evaluate_strategy(...)`/`StrategyEvaluation` contract. No Risk, execution, pricing,
  sizing, persistence, reconciliation, runtime, API/UI, broker mutation, activation, or LIVE
  behavior was added.
- **Validation:** Combined focused validation **115 passed**; targeted Ruff format/lint, Pyright,
  and `git diff --check` passed. No full backend, database, frontend, browser, migration, or
  credentialed external OANDA checks were run.
- **Review:** `dispatch/workstreams/paper-02-strategy-evaluation/REVIEW.md` — **PASS**; no
  unresolved Critical or Important findings.
- **Git/state:** Required PLAN, T001/T002, validation, and review evidence preserved; the feature
  branch was fast-forward merged into `main`; `dispatch/ACTIVE.md` cleared and `main` pushed to
  GitHub. The capability remains one-shot and caller-state-held; no durable PAPER resume authority
  or capital-capable behavior was introduced.

<!-- completion-id: paper-01h-oanda-practice-eur-usd-exposure-state-projection -->
## PAPER 01H — OANDA Practice EUR/USD Exposure-State Projection — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; T001 BUILD, focused validation,
  and independent review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `7e4db27` Implement PAPER 01H OANDA exposure-state projection; the feature
  branch was fast-forward merged into `main`.
- **Scope:** Added the pure normalized OANDA open-Trade/open-Position cross-view projection
  to `FinancialPositionState`, with exact signed EUR/USD unit agreement, fail-closed
  unsupported/directional/counterpart/identity handling, and package exports. No Atlas
  `Position`, Risk evaluation, I/O, persistence, execution, runtime, pending-Order
  consumption, reconciliation, activation, or broker mutation behavior was added.
- **Validation:** Focused suite **140 passed**; targeted Ruff format/lint, Pyright, and
  `git diff --check` passed. No full backend, database, frontend, browser, migration, or
  credentialed external OANDA checks were run.
- **Review:** `dispatch/workstreams/paper-01h-oanda-practice-eur-usd-exposure-state-projection/REVIEW.md`
  — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Required PLAN, T001, VALIDATION, and REVIEW evidence preserved; the feature
  branch was fast-forward merged into `main`; `dispatch/ACTIVE.md` cleared and GitHub push
  completed. No PAPER activation, LIVE behavior, or broker mutation was performed.

<!-- completion-id: paper-01g-oanda-practice-risk-account-state-projection -->
## PAPER 01G — OANDA Practice Risk Account-State Projection — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; T001 BUILD, focused validation, and independent review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `ec03d46` Implement PAPER 01G OANDA risk account-state projection; the feature branch was fast-forward merged into `main`.
- **Scope:** Added the pure OANDA integration projection from the existing normalized `OandaPracticeAccountSummarySnapshot` to provider-neutral Risk `AccountState`, mapping only `identity.base_currency` to `base_currency` and `nav` to `equity`. Positive, zero, and negative finite NAV values are preserved exactly. No OANDA request, Risk evaluation, persistence, execution, runtime, activation, reconciliation, or broker mutation behavior was added.
- **Validation:** Focused OANDA projection/account/Risk suite **60 passed**; targeted Ruff format/lint, Pyright, and `git diff --check` passed. No full backend, database, frontend, browser, migration, or credentialed external OANDA checks were run.
- **Review:** `dispatch/workstreams/paper-01g-oanda-practice-risk-account-state-projection/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Required PLAN, T001, VALIDATION, and REVIEW evidence preserved; the feature branch was fast-forward merged into `main`; `dispatch/ACTIVE.md` cleared. No PAPER activation, LIVE behavior, or broker mutation was performed.

<!-- completion-id: paper-readiness-01-risk-lifecycle-boundary-cleanup -->
## PAPER Readiness 01 — Risk Lifecycle Boundary Cleanup — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; T001 BUILD, focused validation, and independent review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `5386d4b` Implement PAPER Readiness 01 Risk boundary cleanup; the feature branch was pushed and fast-forward merged into `main`. The approved architecture audit remains preserved in `d8219d5`.
- **Scope:** Within PAPER Readiness 01, removed Experiment lifecycle coupling from reusable `RiskService`, preserved the ExperimentRunner PENDING/RUNNING gate, retained `EXPERIMENT_NOT_RUNNING` as readable historical vocabulary without reusable Risk emission, and preserved historical financial Risk behavior.
- **Validation:** Focused Risk/runner suite **26 passed**; targeted Ruff lint, Risk Pyright, and `git diff --check` passed. Existing formatter and strict-Pyright baseline findings in touched historical files remain documented as non-blocking concerns. No full backend, database, OANDA, frontend, browser, or migration checks were run.
- **Review:** `dispatch/workstreams/paper-readiness-01-internal-trading-boundary-audit/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** T001 task, validation, and review evidence preserved; the branch was fast-forward merged into `main`; `dispatch/ACTIVE.md` cleared; `main` pushed to GitHub. No separate `paper-readiness-02` workstream was created, and no persistence, schema, OANDA, execution, runtime, frontend, PAPER activation, or broker mutation behavior changed.

<!-- completion-id: paper-readiness-01-internal-trading-boundary-audit -->
## PAPER Readiness 01 — Internal Trading Boundary Audit — completion record

- **Date/status:** 2026-09-01 — developer approved terminal closure of the reconciled architecture-only audit; no implementation approval was granted.
- **Canonical decision:** The approved `PLAN.md` and `ARCHITECTURE.md` are preserved as the canonical architecture decision. They establish the internal trading boundary and identify `paper-readiness-02-risk-lifecycle-boundary-cleanup` as the sole immediate implementation prerequisite.
- **Execution boundary:** No application, test, migration, persistence, frontend, credential, or runtime implementation changed. No `tasks/` directory, BUILD assignment, BUILD, VALIDATE, REVIEW, GIT START, PAPER/LIVE activation, or broker mutation was performed or authorized by this closure.
- **Git/state:** Documentation-only closure is committed directly on `main` because this architecture-only workstream has no feature branch. `dispatch/ACTIVE.md` is cleared; the separate Risk lifecycle cleanup workstream was not started.

<!-- completion-id: paper-01f-oanda-practice-eur-usd-pricing-observation -->
## PAPER 01F — OANDA Practice EUR/USD Pricing Observation — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; BUILD, validation, and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `37a2510` Implement PAPER 01F EUR/USD pricing observation; feature branch fast-forward merged into `main`.
- **Scope:** One explicitly configured and account-validated OANDA Practice account → one independent read-only `/pricing` observation → immutable normalized EUR/USD provider pricing facts. The slice retains the validated identity, provider instrument, UTC ClientPrice timestamp, exact tradeability, and ordered immutable bid/ask price-liquidity buckets. No persistence, polling, streaming, Risk/runtime, execution, reconciliation, API/UI, broker mutation, PAPER activation, or PAPER 01G/later behavior was added.
- **Validation:** Focused OANDA pricing/account/requester/primitive suite **199 passed**; targeted Ruff format/lint and Pyright passed; `git diff --check` passed. No full backend, database, Alembic, frontend, browser, or credentialed external OANDA checks were run.
- **Review:** `dispatch/workstreams/paper-01f-oanda-practice-eur-usd-pricing-observation/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch pushed to GitHub, fast-forward merged into `main`, and `main` pushed. Required workstream and immutable task/validation/review artifacts preserved; active dispatch state cleared. No credentialed external OANDA request was performed.

<!-- completion-id: oanda-observation-query-parameter-support -->
## OANDA Observation Query Parameter Support — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; BUILD, validation, and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `a8c627f` Implement OANDA observation query parameter support; feature branch fast-forward merged into `main`.
- **Scope:** Added the optional keyword-only `Mapping[str, str] | None` query seam to the existing read-only OANDA Practice requester. Supplied mappings are snapshotted once locally, reused across retries, and delegated through HTTPX `params=` without mutation or retention. Existing no-query PAPER 01A–01E behavior remains unchanged.
- **Validation:** Focused OANDA requester/account/Trade/Position/pending-Order suite **250 passed**; targeted Ruff format/lint and Pyright passed; `git diff --check` passed. No full backend, database, Alembic, frontend, browser, or credentialed external checks were run.
- **Review:** `dispatch/workstreams/oanda-observation-query-parameter-support/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; active dispatch state cleared. No new endpoint, pricing, PAPER 01F, Risk/runtime, execution, persistence, reconciliation, API/UI, broker mutation, or LIVE capability was added. No credentialed external OANDA request was performed.

<!-- completion-id: paper-01e-oanda-practice-pending-order-identity-inventory -->
## PAPER 01E — OANDA Practice Pending Order Identity Inventory — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; BUILD, validation, and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `f279042` Implement PAPER 01E pending Order inventory; feature branch fast-forward merged into `main`.
- **Scope:** One explicitly configured and account-validated OANDA Practice account → one independent read-only `/pendingOrders` observation → immutable normalized provider pending-Order identity inventory. The implementation preserves only provider Order identity, one of the seven documented pending-capable types, exact `PENDING` state, validated account identity, and response-local transaction provenance. No persistence, reconciliation, execution, Risk, runtime, API/UI, ownership, or broker mutation was added.
- **Validation:** Focused OANDA suite **309 passed**; non-integration/non-external suite **696 passed, 4 skipped, 88 deselected**; targeted Ruff format/lint and Pyright passed; `git diff --check` passed. Four pre-existing unrelated pytest warnings remain documented in the validation artifact.
- **Review:** `dispatch/workstreams/paper-01e-oanda-practice-pending-order-identity-inventory/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; active dispatch state cleared. No credentialed external OANDA request was performed. PAPER 01F and later work were not started.

<!-- completion-id: oanda-read-only-observation-infrastructure-refactor -->
## OANDA Read-only Observation Infrastructure Refactor — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; BUILD, validation, and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `75353e4` Refactor OANDA observation request infrastructure; feature branch fast-forward merged into `main`.
- **Scope:** Behavior-preserving extraction of the demonstrated authenticated GET, bounded retry, response, and provider-format primitive mechanics used by the OANDA Practice account, open-Trade, and open-Position read-only observations. Local endpoints, account binding, domain normalization, ordering, duplicate rules, and financial semantics remain unchanged. No new endpoint, Orders, persistence, reconciliation, Risk, runtime, execution, API/UI, PAPER 01E, or LIVE capability was added.
- **Validation:** Focused OANDA suite **253 passed**; non-integration/non-external suite **640 passed, 4 skipped, 88 deselected**; targeted Ruff format/lint and Pyright passed; `git diff --check` passed. Four pre-existing unrelated warnings remain documented in the validation artifact.
- **Review:** `dispatch/workstreams/oanda-read-only-observation-infrastructure-refactor/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; active dispatch state cleared. `source.py` and `backend/integrations/oanda/__init__.py` remain unchanged. No credentialed external OANDA request was performed.

<!-- completion-id: paper-01d-oanda-practice-open-position-inventory -->
## PAPER 01D — OANDA Practice Open Position Inventory — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; BUILD, validation, and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `45c9584` Implement PAPER 01D open Position inventory; feature branch fast-forward merged into `main`.
- **Scope:** One explicitly configured and account-validated OANDA Practice account → one read-only `/openPositions` observation → immutable normalized provider open-Position inventory. Provider Positions remain OANDA observations only, preserving long and short sides independently without netting. No Atlas Position/Trade/Order/Fill construction, ownership, accounting, persistence, reconciliation, Risk, runtime, API/UI, execution, mutation, activation, live data, Strategy execution, or PAPER 01E behavior was added.
- **Validation:** Focused OANDA suite **169 passed**; non-integration/non-external suite **556 passed, 4 skipped, 88 deselected**; targeted Ruff and Pyright passed; `git diff --check` passed. Repository-wide Ruff/Pyright findings remain documented unrelated baseline findings.
- **Review:** `dispatch/workstreams/paper-01d-oanda-practice-open-position-inventory/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; active dispatch state cleared. No credentialed external OANDA request was performed.

<!-- completion-id: paper-01c-oanda-practice-open-trade-inventory -->
## PAPER 01C — OANDA Practice Open Trade Inventory — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; final R001 validation and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `2e41f9a` Implement PAPER 01C open Trade inventory; feature branch pushed and fast-forward merged into `main`.
- **Scope:** One explicitly configured and account-validated OANDA Practice account → one read-only `/openTrades` observation → immutable normalized provider open-Trade inventory. Provider-native instruments, signed units, accepted provider states, deterministic ordering, duplicate rejection, empty inventories, and response transaction provenance remain broker observations only. No Atlas Trade/Position/Order/Fill construction, ownership inference, persistence, reconciliation, Risk, runtime, API/UI, execution, mutation, activation, live data, Strategy execution, or PAPER 01D behavior was added.
- **Validation:** Focused OANDA suite **117 passed**; targeted Ruff and Pyright passed; `git diff --check` passed. BUILD also recorded the non-integration/non-external suite **503 passed, 4 skipped, 88 deselected**; its repository-wide Ruff/Pyright findings were pre-existing and unrelated. Initial validation found IMPORTANT V-001 for leading-zero numeric ordering; R001 added the deterministic raw-ID tie-breaker and regression coverage.
- **Review:** `dispatch/workstreams/paper-01c-oanda-practice-open-trade-inventory/remediations/R001-leading-zero-trade-order/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch pushed to GitHub, fast-forward merged into `main`, and `main` pushed. Required workstream and immutable remediation artifacts preserved; active dispatch state cleared. No credentialed external OANDA request was performed.

<!-- completion-id: paper-01b-oanda-practice-account-summary-snapshot -->
## PAPER 01B — OANDA Practice Account Summary Snapshot — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; BUILD, validation, and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `9ff8e7a` Implement PAPER 01B account summary snapshot; fast-forward merged into `main`.
- **Scope:** One authenticated read-only OANDA Practice `/summary` read normalized into an immutable account-summary snapshot containing the existing 01A identity, selected broker-reported financial facts, counts, and top-level transaction provenance. Separate identity and summary normalization preserved PAPER 01A behavior. No persistence, Risk, runtime, Deployment, reconciliation, detailed broker retrieval, order submission, activation, live data, Strategy execution, or PAPER 01C behavior was added.
- **Validation:** Focused OANDA tests **72 passed**; non-integration/non-external backend suite **459 passed, 4 skipped, 88 deselected**; targeted Ruff and Pyright passed; `git diff --check` passed. No remediation was required.
- **Review:** `dispatch/workstreams/paper-01b-oanda-practice-account-summary-snapshot/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; required workstream artifacts preserved; inherited modified `.gitignore` remained untouched and excluded; active dispatch state cleared. No credentialed external OANDA request was performed.

<!-- completion-id: paper-01a-oanda-practice-account-binding -->
## PAPER 01A — OANDA Practice Account Binding — completion record

- **Date/status:** 2026-09-01 — terminal closure approved; validation and review **PASS** with no unresolved Critical or Important findings.
- **Commit:** `bc69499` Implement OANDA Practice account binding; fast-forward merged into `main`.
- **Scope:** Explicit OANDA Practice account-ID configuration, direct read-only account-summary validation, immutable five-field normalized account identity, bounded retries, fail-closed response handling, and sanitized deterministic MockTransport coverage. No persistence, runtime, Deployment, Risk, reconciliation, Orders, live market data, PAPER activation, API/UI, or PAPER 01B behavior was added.
- **Validation:** Targeted account/config/source tests **57 passed**; non-integration/non-external suite **432 passed, 4 skipped**; targeted Ruff and Pyright passed; `git diff --check` passed. Repository-wide pre-existing Ruff/Pyright findings remain documented in the workstream artifacts.
- **Review:** `dispatch/workstreams/paper-01a-oanda-practice-account-binding/REVIEW.md` — **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`; required workstream artifacts preserved; inherited untracked `.codegraph/` and `frontend/.env.local` remained untouched and excluded; active dispatch state cleared. PAPER 01B was not started.

<!-- completion-id: foundation-freeze-07-corrections -->
## Foundation Freeze 07 Corrections — completion record

- **Date/status:** 2026-08-30 — terminal closure approved; targeted validation
  and targeted rereview **PASS** with no unresolved Critical or Important findings.
- **Commit:** `e54e694` Correct Freeze 07 lock and downgrade contracts;
  fast-forward merged into `main`.
- **Scope:** Corrected DELETE lock ownership to the frozen non-lock Experiment
  read → DatasetSnapshot lock → Experiment lock sequence, and restored the exact
  revision-0020 `snapshot_v2_append_only_guard` downgrade function/trigger
  contract. No architecture semantics, pre-PAPER audit, PAPER, Strategy
  authoring, or unrelated code changed.
- **Validation:** Targeted PostgreSQL C1/C2 validation passed with 51 focused
  tests, migration-cycle and guarded-DML checks, targeted Ruff/Pyright/
  compile/diff checks, and preserved confirmation/deletion semantics.
- **Review:** `dispatch/workstreams/foundation-freeze-07-corrections/REVIEW.md`
  — targeted rereview **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Correction branch fast-forward merged into `main`. Known
  pre-existing `.codegraph/` and `frontend/.env.local` remain untracked and
  excluded. Active dispatch state cleared.

<!-- completion-id: foundation-freeze-07-experiment-lifecycle-local-authority -->
## Foundation Freeze 07 — Experiment Lifecycle & Local Authority — completion record

- **Date/status:** 2026-08-30 — terminal closure approved; validation and targeted
  rereview **PASS** with no unresolved Critical or Important findings.
- **Commit:** `469edd3` Implement Foundation Freeze 07 lifecycle authority;
  fast-forward merged into `main`.
- **Scope:** Explicit transactional Experiment deletion with populated-graph,
  rollback, receipt, snapshot-retention, and lifecycle-lock proof; loopback
  actual-peer/local-authority enforcement with proxy-header rewriting disabled;
  provider-neutral StrategyContext capability composition; strict delete API and
  human-confirmed modal workflow. No pre-PAPER audit, PAPER, LIVE, or unrelated
  infrastructure work started.
- **Validation:** Dedicated PostgreSQL migration/deletion/lifecycle/authority
  evidence passed, including the initial broad matrix and targeted remediation
  checks; frontend focused tests, TypeScript, lint, formatting, build, and Local
  Host failure/modal workflows passed. Known repository-wide typing/frontend
  baseline issues remain non-gating and documented in the workstream artifacts.
- **Review:** `dispatch/workstreams/foundation-freeze-07-experiment-lifecycle-local-authority/REVIEW.md`
  — targeted rereview **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch fast-forward merged into `main`. Known
  pre-existing `.codegraph/` and `frontend/.env.local` remain untracked and
  excluded. Active dispatch state cleared.

<!-- completion-id: foundation-freeze-06-strategy-extensibility-proof -->
## Foundation Freeze 06 — Strategy Extensibility Proof — completion record

- **Date/status:** 2026-08-29 — terminal closure approved; targeted validation
  and targeted review **PASS**; merged and pushed.
- **Commit:** `25497d7` Complete Foundation Freeze 06 strategy extensibility
  proof; merge commit `a23aa18`.
- **Scope:** constrained generic Strategy parameter/state/evidence/market
  contracts, Candle Confirmation Break v1 registration and behavior, immutable
  Experiment/V2 execution and inspection proof, schema-driven UI, and preserved
  EMA compatibility/provenance. No EMA source/fingerprint, migration,
  checkpoint persistence, or PAPER/LIVE behavior changed.
- **Validation:** targeted remediation validation **PASS**; R-001 through R-004
  resolved; candidate PostgreSQL vertical regression and directly affected
  Strategy/result evidence passed. No full matrix was rerun during final
  remediation, per approval.
- **Review:** `dispatch/workstreams/foundation-freeze-06-strategy-extensibility-proof/REVIEW.md`
  — targeted review **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch pushed, merged into `main`, and `main` pushed.
  `.codegraph/` and `frontend/.env.local` were preserved and excluded. Active
  dispatch state cleared. Freeze 07 was not started.

<!-- completion-id: foundation-freeze-05-trader-product-ui-completion -->
## Foundation Freeze 05 — Trader Product UI Completion — completion record

- **Date/status:** 2026-08-29 — terminal closure approved; targeted validation and review **PASS**; merged and pushed.
- **Commit:** `e55c805` Complete Freeze 05 trader product UI; merge commit `481928f`.
- **Scope:** Historical-research trader workstation UI completion, StrategyVersion handoff and setup readiness, bounded list projections, result/Trade/comparison hierarchy, acceptance hardening, and generated OpenAPI client freshness. PAPER/LIVE, financial semantics, and broader API meaning remained unchanged.
- **Validation:** Prior full evidence preserved; targeted OpenAPI freshness/typecheck passed; targeted Experiment-list regression, response-equivalence, and bounded 3-SELECT evidence passed. Full validation matrix was not rerun during remediation.
- **Review:** `dispatch/workstreams/foundation-freeze-05-trader-product-ui-completion/REVIEW.md` — broad and targeted review **PASS**; no unresolved Critical or Important findings.
- **Git/state:** Feature branch pushed, merged into `main`, and `main` pushed. `.codegraph/` and `frontend/.env.local` were preserved and excluded. Active dispatch state cleared. Freeze 06 was not started.

<!-- completion-id: foundation-freeze-04-experiment-engine-simplification -->
## Foundation Freeze 04 — Experiment Engine Simplification — completion record

- **Date/status:** 2026-08-29 — terminal closure approved; validation and fresh independent review **PASS**; merged and pushed.
- **Commit:** `6c41602` Simplify Experiment engine authority.
- **Scope:** One authoritative V2 Experiment runner path; removal of superseded Phase 4 execution and obsolete V1 acquisition/CLI paths; explicit immutable V1 read boundary; pending-trigger and W1–W6/no-lookahead regressions; legacy Strategy isolation; E2E harness and fixture remediation; RiskConfig fail-closed ordering.
- **Validation:** Full backend and integration suites, migration/head checks, golden replay and fact immutability, Freeze 01–03 regressions, exact Ruff/Pyright differential, web tests/typecheck/build, and Playwright E2E **5/5** passed. No current-only Freeze 04 lint/type findings; remaining quality findings are exact baseline debt.
- **Review:** `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/REVIEW.md` — **PASS**; no Critical or Important findings.
- **Git/state:** Branch pushed, fast-forward merged into `main`, and `main` pushed. `.codegraph/` and `frontend/.env.local` were preserved and excluded. Freeze 05 was not started.

<!-- completion-id: foundation-freeze-03-historical-data-foundation -->
## Foundation Freeze 03 — Historical Data Foundation — completion record

- **Date/status:** 2026-08-28 — remediation, validation, and fresh independent review **PASS**; commit pushed and workstream closed.
- **Commit:** `1dd3614` Complete Freeze 03 historical data foundation.
- **Scope:** Authoritative native OANDA M15 MID plus M1 BID/ASK acquisition, independent bounded planning, durable progress/resume, atomic observation/window persistence, sparse/closure semantics, immutable deterministic V2 DatasetSnapshots, bounded Experiment validation, fail-closed completion, and complete terminal metrics.
- **Validation:** T036/T037 focused regressions **2 passed**; affected tests **46 passed**; isolated PostgreSQL **11 passed**; full backend **383 passed, 1 skipped, 4 warnings**; scoped Ruff, compileall, and diff checks passed. Existing genuine-year, covered-repeat, and stopped-run recovery evidence remains accepted; no new genuine-year benchmark was run.
- **Review:** `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/REVIEW.md` — PASS; no Critical or Important findings.
- **Non-blocking observations:** Accepted malformed-URL `atlas_test.public` validation-process incident and 45 unrelated pre-existing full-Ruff issues remain documented. `.codegraph/` and `frontend/.env.local` were excluded from the commit.

Completion log for items that passed their final gate. Each row references the authoritative
review artifact in `dispatch/`. Prior dispatch artifacts remain untouched in `dispatch/`.

| Date | Item | Scope | Validation | Approved review | Non-blocking observations |
|---|---|---|---|---|---|
| 2026-08-12 | Phase 0 — Project Foundation | Repository foundation: root manifests and lockfiles (pyproject.toml, uv.lock, package.json, package-lock.json); typed `ATLAS_` config and secret-safe logging; SQLAlchemy 2 + psycopg 3 + Alembic empty baseline (single head); FastAPI `/health/live` + `/health/ready`; `atlas-runtime` process (`--check` exit 0/1/2 + signal lifecycle); Next.js 16 frontend (single page, strict TS, Tailwind v4); pytest (unit + guarded PostgreSQL integration), Vitest, Playwright e2e; quality gates (Ruff, Pyright strict, ESLint, Prettier, tsc, build); root README. No trading functionality. | All 21 acceptance criteria PASS, empirically verified against the live environment: lockfiles reproducible (`uv sync --all-groups --locked`, `npm ci`); 15 unit + 2 integration tests pass; migration cycle/current/check green on real PostgreSQL 18; live API health contract exact incl. sanitized 503; runtime exit codes + signals; all frontend gates incl. Playwright Chromium e2e; no credential/exception leakage; `AGENTS.md` and `context/` unchanged. | **APPROVED** — `dispatch/PHASE-0-FINAL-REVIEW.md` (Tier 2 completion gate, 2026-08-12); reviewer made no application code or `context/` modifications. | O1: e2e `webServer` logs a Next.js dev HMR `allowedDevOrigins` warning (cosmetic; a future `allowedDevOrigins: ['127.0.0.1']` would silence it — no change required). O2: Node v24.18.0 used vs blueprint's Node 22 LTS — documented environment deviation; all gates pass. O3: one StarletteDeprecationWarning in pytest output — expected consequence of the blueprint's `httpx<1` requirement, not a defect. |
| 2026-08-12 | Flat Backend — corrective package layout | Target achieved: `backend/` is the sole Python import package (`backend.*`), directly containing application source (`__init__.py`, `config.py`, `logging.py`, `api/`, `persistence/`, `runtime/`) with `backend/tests/` retained in place; repository-root `atlas/` source package removed; `backend/atlas/` forbidden; Hatch `packages = ["backend"]`, console `atlas-runtime = backend.runtime.main:main`, Uvicorn `backend.api.app:create_app`, Alembic at `backend/persistence/migrations` with unchanged one-history baseline `0001_phase_0_baseline`; distribution `atlas-platform`, migration history, API/runtime/health contracts, frontend, and trading semantics unchanged; `context/architecture/repository-structure.md` corrected to match. | FB-05 full validation PASS (2026-08-12), recorded in `dispatch/FLAT-BACKEND-VALIDATION.md` against the live environment: every blueprint Section 9 gate verified — structural tree (no root `atlas/`, no `backend/atlas/`); locked reinstall, import probes, wheel inspection, outside-repository import; ruff/pyright/pytest (15 passed, 2 deselected); Alembic upgrade/current/heads/check with one head `0001_phase_0_baseline` and guarded `_test`-only integration (2 passed); process gates (exact liveness/readiness contracts, DB-down sanitized 503, runtime exit codes 0/1/2, clean signal shutdown); frontend npm ci/check:web/Chromium/e2e; stale-reference audit with no affirmative current stale use; historical checksum integrity (all 11 non-append pre-existing dispatch files checksum-identical to the FB-01 baseline; MODEL-LOG append-only). All 21 Section 10 acceptance criteria PASS; no blocking defects. | **APPROVED** — `dispatch/FLAT-BACKEND-REVIEW.md` (FB-06 independent architecture review, 2026-08-12); reviewer separate from the implementation engineer independently reran structural, packaging/import/wheel/outside-repo, ruff/pyright/pytest, Alembic/PostgreSQL, process, stale-reference, and historical-checksum checks; no Critical or Important findings; all 21 acceptance criteria PASS; reviewer made no application code, `context/`, or historical artifact modifications. | M1: built wheel includes the retained `backend/tests/` (6 files) — matches blueprint §9.2 record-only requirement, no exclusion added, no action. M2: pre-existing environment-only warnings during deterministic gates (StarletteDeprecationWarning re: httpx/starlette.testclient) unrelated to the correction. M3: `rg` unavailable in this environment — stale-path and checksum verification used `grep -rn`/`shasum` equivalents, consistent with FB-05. |
<!-- completion-id: phase-1-reference-strategy -->
## Phase 1 Reference Strategy — completion record

- **Date/status:** 2026-08-14 — approved final review: **Phase 1 final independent completion R1 APPROVED**.
- **Worktree:** `/Users/vike/Desktop/atlas-phase-1-reference-strategy`; branch `feature/phase-1-reference-strategy`; starting/full SHA `6403788710b8e3934bf3276d90b40d7121a1f17a`.
- **Implementation inventory:** pure `backend.domain`/public Strategy contract; Decimal EMA/ATR; explicit source fingerprint and one-entry registry; EMA Sweep Engulfing W1–W5 rules; immutable Strategy/StrategyVersion persistence with Alembic migration `0002`.
- **Verification:** 81 non-integration tests; 5 PostgreSQL integration tests; Ruff format/check; Pyright; Alembic check — all passed.
- **Non-blocking review observations:** (1) historical archived-version execution remains a later loader decision; (2) the source snapshot secret detector is intentionally narrow, not exhaustive; (3) Phase 1 remains deliberately fixed to EUR/USD MID 15m; (4) target resolution correctly remains caller-supplied entry geometry rather than fabricated execution data; (5) persistence downgrade is intentionally destructive and must remain an explicit operator action. None blocks this phase.
- **State/authorization:** Commit `eed18db Implement Phase 1 reference strategy` was fast-forward merged into `main`.
- **One-off dispatch inventory/material summary:** `dispatch/PHASE-1-BLUEPRINT.md` — approved scope, contract, EMA/ATR formulas, W1–W5 state machine, persistence shape, exclusions, and validation matrix; `dispatch/PHASE-1-READY.md` — verified READY receipt for the root, isolated path, branch, SHA, scope, and recovery/no-Git conditions; final independent completion review — R1 approval recorded above (no separate Phase 1 report artifact is present in root `dispatch/`). No secrets are recorded.
- **Memory-save receipt:** `memory.md` successfully updated on 2026-08-14 after user approval; no secrets.

<!-- completion-id: phase-2-historical-data-dataset-snapshot -->
## Phase 2 Historical Data to DatasetSnapshot — completion record

- **Date/status:** 2026-08-21 — terminal closure approved; final independent review **PASS**.
- **Scope:** EUR/USD OANDA Practice historical completed M1 BID/MID/ASK ingestion, coverage and
  gap validation, immutable corrected bar variants, deterministic M15 derivation, immutable
  DatasetSnapshot persistence, narrow `atlas-data` CLI, and operator documentation. Experiment,
  Risk, execution, live trading, streaming, scheduling, API, and UI remain out of scope.
- **Acceptance evidence:** `uv run pytest -m integration` PASS 14/14 including DB CLI; Ruff
  format/check, Pyright, and `uv run pytest -m "not integration and not external"` PASS with
  126 tests; `uv run alembic current` and standalone `uv run alembic check` PASS with both DB
  URLs pointed to the local `atlas_test` owner; one OANDA Practice EUR/USD historical smoke
  test PASS for `[2026-08-18T13:00:00Z,2026-08-18T14:00:00Z)`, HTTP 200, with no account,
  trading, live, or DB calls.
- **Review:** Final independent review PASS; no Critical or Important findings. P2-05 and P2-06
  are complete. Phase 3 is eligible after closure.
- **Deferred Minors:** wrong-provider coverage; explicit timeframe mapping; serialization/
  docstring cleanup; full integrity-summary shape; speculative aliases; hardcoded M1 header;
  idempotent snapshot lookup coverage; service error-path and byte-serialization coverage;
  summary-key casing; generic partial-fetch failure class. None blocks closure.
- **Git/state:** No commits, pushes, merges, branch deletion, or worktree cleanup performed.
- **Report inventory/material summary:** `dispatch/PHASE-2-BLUEPRINT.md` — authoritative scope,
  contracts, invariants, gates, and acceptance criteria; `dispatch/PHASE-2-EXPLORATION.md` —
  repository/context findings, risks, and narrow-slice recommendation; `dispatch/PHASE-2-READY.md`
  — current feature-branch authorization and recovery constraints; all are preserved. No unknown
  or user-authored reports were deleted.
- **Memory-save receipt:** `memory.md` successfully updated on 2026-08-21 after explicit user
  authorization; no secrets recorded. Terminal reset eligibility is satisfied.

<!-- completion-id: phase-3-first-historical-trade -->
## Phase 3 First Historical Trade — completion record

- **Date/status:** 2026-08-21 — implementation and final independent R1 review **PASS**; terminal closure complete after explicit `/remember save` user confirmation.
- **Scope:** deterministic persisted EUR/USD LONG and SHORT historical Experiments through Strategy → TradeIntent → RiskDecision → Order → Fill → Position → Trade, with immutable snapshot provenance, no-lookahead clocking, centralized Risk, pure simulated execution, Fill-authoritative exposure, sanitized fail-closed failures, and `PHASE3_OPEN_CHECKPOINT_V1`; Phase 4/API/UI/broker/runtime behavior excluded.
- **Evidence:** golden LONG/SHORT flows, migration cycle, failure persistence, Fill boundary, snapshot-only reads, supporting integration tests, non-integration suite, quality checks, and semantic reruns passed. Final isolation recheck: sequential full `pytest -q` runs from residue-present and base-schema states each **170 passed, 1 skipped**; integration-only **18 passed**.
- **Migration/model boundary:** `0004_phase_3_first_trade` adds exactly the eight approved Phase 3 tables; forward `0005_phase_3_failure_persistence` adds immutable terminal failure facts. No TradingAccount, Deployment, RiskProfile, OrderEvent, equity-history, SystemEvent, or generalized infrastructure.
- **Review/dispositions:** `dispatch/workstreams/first-historical-trade/REVIEW.md` R1 **PASS**; Important OBS-2 resolved by test-only isolation. Minor OBS-1 (NY-calendar/partial-break warmup coupling) and OBS-3 (runner Pyright hygiene) remain non-blocking follow-ups.
- **Material reports:** `PHASE-3-BLUEPRINT.md`; workstream `READY.md`, `TASK-01`…`TASK-10` (including `TASK-08A`), `VALIDATION.md`, `REVIEW.md`, and `RECORD.md`.
- **State/authorization:** branch and uncommitted task context preserved; no Git operation, cleanup, reset, or deletion performed. `memory.md` was updated only after explicit confirmation; no terminal reset or deletion was performed.
- **Memory-save receipt:** `Memory saved to memory.md.` on 2026-08-21 after explicit user confirmation; secret-safe update only, no secrets recorded. Terminal closure is complete; no reset or deletion was performed.

<!-- completion-id: phase-4-historical-execution -->
## Phase 4 Historical Execution — completion record

- **Date/status:** 2026-08-21 — terminal closure approved; final independent R1 review **PASS**.
- **Outcome/path:** deterministic persisted EUR/USD historical Experiment execution for the approved fixed slice, with chronological M1/M15 frontier semantics, BID/ASK execution, configured adverse slippage, protection, multi-Trade accounting, equity/results provenance, semantic fingerprints, and inspectable terminal failures. Workstream preserved at `dispatch/workstreams/phase-4-historical-execution/`.
- **Evidence:** `VALIDATION.md` PASS; full suite **180 passed, 1 skipped**; focused remediation checks PASS; Ruff, compileall, Alembic head `0006_phase_4_persistence`, and forbidden-import boundary checks PASS. `REVIEW.md` R1 PASS with 0 Important findings.
- **Non-blocking follow-ups:** Review findings C/D remain accepted: explicit DatasetSnapshot integrity/coverage validation and session-closed decision-frontier/mid-stream gap handling.
- **State:** No Git operations, cleanup, reset, branch deletion, or workstream deletion performed. Application, tests, context, and selected workstream artifacts are preserved.
- **Memory-save receipt:** `Memory saved to memory.md.` verified on 2026-08-21; secret-safe update only, no secrets recorded. Closure is complete.

<!-- completion-id: phase-5-experiment-workflow -->
## Phase 5 Experiment Workflow — completion record

- **Date/status:** 2026-08-23 — terminal closure approved; final independent R1 review **PASS** (no Critical/Important findings; four Minor non-blocking). Full independent validation **PASS**. Terminal memory-save confirmed by the user; closure completed.
- **Outcome/path:** configure, validate, create, run, observe status, and inspect completed/failed/zero-Trade Experiments from the UI — headline metrics, equity/drawdown, Trade list/detail, assumptions/provenance — through FastAPI contract + Next.js frontend, preserving Phase 4 reproducibility/no-lookahead invariants and the UTC session policy. Workstream preserved at `dispatch/workstreams/phase-5-experiment-workflow/` (branch `feature/phase-5-experiment-workflow`, HEAD `67c24b714f3c128cfefab0581118638194063de8`).
- **Evidence:** `VALIDATION.md` full-workstream receipt **PASS** — backend suite **219 passed / 1 skipped** (single skip = external OANDA credential), Alembic upgrade/downgrade/upgrade cycle to `0007_phase_5_metric_contract`, frontend lint/typecheck/unit/build, generated-OpenAPI contract freshness (byte-identical `frontend/lib/api.generated.ts`), Ruff clean, `git diff --check` clean, and canonical E2E **5/5** (`--workers=1`, isolated `atlas_test`, non-UTC host) independently re-confirmed against the `TASK-21.md` 5/5 receipt. UTC session policy enforced across production/CLI/runtime/online-Alembic/E2E/integration PG paths; diagnostics default-off and leak-free; chart/disclosure compositions corrected.
- **Review:** `REVIEW.md` R1 **PASS** — plan alignment (L1), system integrity (L2, incl. UTC/session safety and diagnostic-leakage), and production readiness (L3, incl. E2E 5/5) all PASS. Evidence reused as valid on unchanged HEAD; no gate rerun needed.
- **Non-blocking Minors (accepted):** (1) `autoflush=True` in `create_session_factory` (approved, evidence-proven Task 16 correction) deviates from the ARCHITECTURE.md UTC blueprint's documented `autoflush=False` — blueprint text not reconciled. (2) Chart setup-context window does not literally meet the blueprint's "EMA period + 20 preceding bars" requirement; EMA values canonical so presentation-only, unasserted by test. (3) `pyright backend` (strict) non-clean (1132 errors; 757 at Phase 4 baseline) — pre-existing project-wide gate, not a Phase 5 regression. (4) `format:check:web` flags `experiment-workflow.tsx` and generated `tests/e2e/.fixtures.json`. None blocks closure.
- **State/authorization:** No Git operations, cleanup, reset, branch deletion, or workstream deletion performed. Application, tests, context, and the selected workstream artifacts are preserved. Scope excluded Phase 6, PAPER/LIVE, comparison, optimization, cancellation, export, background workers, and WebSockets.
- **Report inventory/material summary:** `PLAN.md`, `ARCHITECTURE.md` (incl. append-only remediation/UTC/diagnostic blueprints), `EXPLORATION.md`, `RESEARCH.md`, `READY.md`, `VALIDATION.md`, `REVIEW.md`, and `TASK-01.md`…`TASK-21.md` all preserved. No unknown or user-authored reports were deleted.
- **Memory-save receipt:** `Memory saved to memory.md.` on 2026-08-23 after explicit user confirmation; secret-safe update only, no secrets recorded (the OANDA token in `.env` was not referenced). Terminal reset eligibility is satisfied.

<!-- completion-id: product-vision-alignment -->
## Product Vision Alignment — completion record

- **Date/status:** 2026-08-23 — terminal closure approved; final independent R1 review **PASS** (two Minor non-blocking findings); full independent validation **PASS**. Terminal memory-save confirmed by the user; closure completed.
- **Outcome/path:** surgically aligned authoritative product context with the approved proprietary, licensed, local-first Atlas Workstation vision. `context/product/vision.md` is now the single authoritative home for the canonical **Build → Experiment → PAPER → LIVE → Monitor → Improve** lifecycle, proprietary/licensed direction, and local-first/customer-controlled operating model; `context/product/product-principles.md` references the lifecycle via link and adds one concise Safety-Independent Licensing Boundary principle; `context/architecture/architecture.md` Purpose directly references `../product/vision.md` instead of restating the lifecycle, retaining the same-StrategyVersion Experiment → PAPER → LIVE consequence. Workstream preserved at `dispatch/workstreams/product-vision-alignment/` (branch `feature/product-vision-alignment`).
- **Evidence:** `VALIDATION.md` full-workstream receipt **PASS** — all PLAN acceptance criteria met (one authoritative home per decision; lifecycle/proprietary/licensed/customer-controlled/Strategy-principles/safety-independent-licensing-boundary clear; no scope expansion; no contradictory or duplicated long-form vision). `git diff` confirms exactly `3 files changed, 9 insertions(+), 5 deletions(-)` confined to the three prescribed context files; `context/roadmap/roadmap.md` and all `context/features/*` unchanged; no legacy `Build → Test → Deploy → Monitor → Improve` / `test → deploy` lifecycle text remains in `context/`; canonical terminology (`StrategyVersion`, `Experiment`, `PAPER`, `LIVE`, `Deployment`, `Risk`) preserved; relative links resolve; no Backtest/Bot terminology introduced. `REVIEW.md` R1 **PASS** — plan alignment (L1), system integrity (L2), production readiness (L3) all PASS.
- **Non-blocking Minors (accepted):** (1) `PLAN.md` ordered-tasks table has two duplicate "Documentation review" rows — dispatch bookkeeping only; collapse to a single row on a future PLAN edit. (2) "customer-controlled"/"customer's control" wording appears in both `vision.md:5` and `vision.md:13` — harmless, not a long-form duplication; optional consolidation on future edits. Neither blocks closure.
- **State/authorization:** No Git operations, cleanup, reset, branch deletion, or workstream deletion performed. Application, tests, context, and the selected workstream artifacts are preserved. Scope excluded application code, roadmap changes, commercial infrastructure (licensing/SaaS/multi-tenancy/billing/installers/cloud/SDK packaging/Phase 6), and an alignment audit.
- **Report inventory/material summary:** `PLAN.md`, `ARCHITECTURE.md`, `EXPLORATION.md`, `READY.md`, `TASK-1.md`, `VALIDATION.md`, and `REVIEW.md` all preserved. No unknown or user-authored reports were deleted.
- **Memory-save receipt:** `Memory saved to memory.md.` on 2026-08-23 after explicit user confirmation; secret-safe update only, no secrets recorded. Terminal reset eligibility is satisfied.

<!-- completion-id: phase-6-strategy-iteration -->
## Phase 6 Strategy Iteration — completion record

- **Date/status:** 2026-08-23 — terminal closure approved; final independent premium R1 review **PASS** (0 Critical / 0 Important / 0 Minor). Workstream preserved at `dispatch/workstreams/phase-6-strategy-iteration/`.
- **Outcome/path:** immutable parameter-enabled StrategyVersion v2 (`ema_sweep_engulfing_v2`), registry/catalog synchronization, Strategy catalog/history API + UI, typed schema-derived parameter controls, and a stateless read-only Experiment comparison workflow with repeated `experimentId` query contract, generated-client freshness, and canonical metric envelopes. v1 source/fingerprint preserved byte-identical. Branch `feature/phase-6-strategy-iteration`, base SHA `f009be5fbe7cee7387ccda7cf3460833525ff303`.
- **Validation summary:** `VALIDATION.md` recorded B1–B3 (stale generated client, comparison query-key mismatch, Suspense build regression); remediated in `TASK-07` (B1–B3) and `TASK-08` (review I1/M1: restored exact repeated `experimentId` contract + migrated-database HTTP integration coverage). Final: backend `not external` **235 passed / 1 deselected**; integration `test_api_experiments.py` **5 passed**; `npm run test:web` **12 passed**; lint/typecheck/build **passed** (`/experiments/compare` generated); OpenAPI freshness byte-identical; Ruff/`git diff --check` clean. `REVIEW.md` R1 PASS — ready for dispatch closure.
- **Deferred environment notes (non-code):** (1) the R1 review shell did not export `ATLAS_TEST_DATABASE_URL`, so its `not external` run reported 12 integration setup errors solely from the missing dedicated test-URL (no application-test failure; Task 08's explicit-URL run `235 passed`). (2) `VALIDATION.md` env provisioning: local PostgreSQL was started and the `atlas_test` `public` schema/tables ownership was transferred to role `atlas` to run the documented test convention — environment provisioning, no production DB touched. (3) `npm run format:check:web` flags only pre-existing `tests/e2e/.fixtures.json` drift, not Phase 6 changes.
- **State/authorization:** No Git operations, cleanup, reset, branch deletion, or workstream deletion performed. Application, tests, context, and the selected workstream artifacts are preserved. Uncommitted remediation work remains on the feature branch, owned by the user.
- **Memory-save receipt:** `Memory saved to memory.md.` on 2026-08-23 after explicit user confirmation; secret-safe update only, no secrets recorded. Terminal reset eligibility is satisfied.

<!-- completion-id: ui-tokens-screenshot-references -->
## Atlas V2 UI Tokens and Screenshot References — completion record

- **Date/status:** 2026-08-23 — terminal closure approved; final independent R1 review **PASS** (no Critical/Important findings; two Minor non-blocking); full independent validation **PASS**. Terminal memory-save confirmed by the requester; closure completed.
- **Outcome/path:** design-context-only extraction from the ten approved individual V2 PNG mockups, providing the semantic Atlas UI design system for later Tailwind CSS v4 / shadcn/ui / TradingView Lightweight Charts work. Added `context/design/ui-tokens.md` (semantic roles, aliases, chart role-alias mappings, deferred exact values) and `context/design/visual-guide.md` (shell/hierarchy/patterns/chart treatment/anti-patterns and a ten-screen validation matrix); narrowly reoriented `context/design/design.md` to dark-first V2 appearance and removed the stale deleted composite-screenshot reference (`context/design/screenshot/atlas-screens.PNG`, absent, not recreated). Workstream preserved at `dispatch/workstreams/ui-tokens-screenshot-references/` (branch `feature/ui-tokens-screenshot-references`, base SHA `f009be5fbe7cee7387ccda7cf3460833525ff303`).
- **Validation PASS:** `VALIDATION.md` full-workstream receipt PASS — all ten acceptance criteria: only the three authorized design paths changed; dark-first reorientation explicit while calm/low-noise and scope guidance preserved; no stale composite reference / no recreation; bidirectional guide links; exactly ten canonical inventory paths + ten completed matrix rows; semantic token restraint with no hex/OKLCH literals and all exact values deferred; Tailwind/shadcn/Lightweight Charts guidance conceptual only (no CSS/config/dependency content); behavior/safety/navigation scope retained; all ten mockups match stated recurring evidence; cross-document consistency. `git diff --check`, scoped diffs, and deterministic path/row counts all clean. `REVIEW.md` R1 **PASS** — plan alignment (L1), system integrity (L2, scope/inherited-dirty-tree/branch-SHA), and production readiness (L3) all PASS; no Critical/Important findings.
- **Non-blocking findings (accepted):** (1) Direct human-grade pixel inspection of typography, radii, and the specific amber "Different Strategy Version" label / violet Sweep annotation was not possible for the validator or reviewer models (no image input) — visual proof is **programmatic** (pure-Python PNG decode + luminance/hue analysis corroborating dark-first character and sparse semantic color); numerical evidence strongly consistent, and direct visual-capable review or a later visual-regression check at application adoption is recommended. (2) `design.md` guide links use backtick-wrapped text inside link text (`` [`ui-tokens.md`](ui-tokens.md) ``) — valid Markdown, renders correctly, not a defect. Neither blocks closure.
- **Scope limits:** design-context migration only (`context/design/design.md`, `ui-tokens.md`, `visual-guide.md`). No screen rebuilds, behavior change, mockup modification, CSS/Tailwind/shadcn/chart configuration, dependency, framework config, or application-adoption implementation; adoption is a separate approved workstream.
- **State/authorization:** No Git operations, cleanup, reset, branch deletion, or workstream deletion performed. Application, tests, context, and the selected workstream artifacts are preserved; the inherited dirty working tree (incl. `D context/design/screenshot/atlas-screens.PNG` and other pre-existing dirty paths) is preserved.
- **Report inventory/material summary:** `PLAN.md`, `ARCHITECTURE.md`, `EXPLORATION.md`, `RESEARCH.md`, `READY.md`, `TASK-1.md`, `VALIDATION.md`, and `REVIEW.md` all preserved. No unknown or user-authored reports were deleted.
- **Memory-save receipt:** `Memory saved to memory.md.` on 2026-08-23 after explicit requester confirmation; secret-safe update only, no secrets recorded. Terminal reset eligibility is satisfied.

<!-- completion-id: recovery-historical-simulation-spine -->
## Recovery — Historical Simulation Spine — completion record

- **Date/status:** 2026-08-25 — recovery branch `recovery/historical-simulation-spine` @ `1a1474d` built sequentially 1-6 and manually validated; `COMPLETED` experiment `6734f48b-c9e5-4cbf-8c3f-1024b29e6a48` (EUR/USD M15 MID native + sparse M1 BID/ASK, 32.1d May27→Jul1, 2320 analytical + 69k execution) on V2 `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2`; direct `TestClient` rerun also `COMPLETED` with deterministic rerun.
- **Scope:** Clean recovery from known-good Phase 6 `1a1474d`; `StrategyMarketDataRequirement` (`AnalyticalRequirement M15 MID UTC_HALF_OPEN_V1` + `RequiredHistoricalContext 200` analytical bars) + `ProviderCapability` (`OANDA_M15_NATIVE_UTC_V1` + `OANDA_M1_NATIVE_UTC_V1` sparse) with 90d/40w bounds; `aggregate_m1_to_m15` V1-only; `America/Chicago` display-only UTC canonical; fixes: `gap.blocking→blocked` typo, `phase_4_append_only_guard` result_quality UPDATE blocked (kept default DETERMINED + gap_decisions), DB grants `GRANT ALL ON SCHEMA/TABLES/SEQUENCES TO atlas` for `atlas_test`.
- **Files:** `backend/domain/{market_data,strategy_requirements}.py`, `backend/market_data/{historical_load,session_policy,fingerprint,ingestion,aggregation,coverage,session_calendar}.py`, `backend/persistence/{models,historical_data_load_repository,market_data_repository,experiment_repository,result_repository}` + migrations `0008_historical_load` `0009_snapshot_v2` `0010_gap_decisions` `0011_fix_trigger`, `backend/integrations/oanda/{source,capabilities}.py`, `backend/experiments/{clock,configuration,runner,results}.py`, `backend/api/{historical_data,experiments,schemas,app}.py`, `frontend/lib/time.ts` + `utc-date-time-picker` + `experiment-workflow` durable polling, `api.generated.ts`.
- **Validation:** `ruff` PASS (1 remaining `F401 UTC` in test helper), `alembic 0011 head` PASS, `pytest -m "not external and not integration"` 258 passed, `test_migration_revision` + `snapshot_v2_contract` 43 passed, `integration/test_migrations` 2 passed, `typecheck:web`/`lint:web` PASS, `test:web` 8/9 files 22/23 (1 pre-existing `focused Trade detail` deferred), `TestClient` 201→200 COMPLETED + gapDecisions 960 + price-analysis M15 payload; manual browser `Jun1→Jul1` V2 load `COMPLETED` + `Run Experiment` `COMPLETED` verified 2026-08-25.
- **Deferred:** Strategy sweep/engulfing trade logic review deferred as requested; `result_quality` DETERMINED_WITH_GAPS via UPDATE remains blocked by trigger (acceptable for recovery — gaps in `experiment_gap_decisions`); frontend `focused Trade detail` chart spy failure is pre-existing non-blocking.
- **Branch/workstream:** `recovery/historical-simulation-spine` @ `1a1474d`; workstream `dispatch/workstreams/recovery-historical-simulation-spine/` preserved (`PLAN.md` `TASK-01…06` `VALIDATION.md`); stashes preserved (`stash@{0}` pre-recovery dirty, `stash@{1}` dark-first).
- **State:** Recovery fixes staged for merge to `main`; dark-mode `feature/dark-first-v2-frontend-adoption` deferred to next commit on same branch.

<!-- completion-id: strategy-experiment-workstation -->
## Strategy Experiment Workstation — completion record

- **Date/status:** 2026-08-25 — terminal closure approved; final independent R1 review **PASS** with no remaining Important or Critical findings.
- **Outcome:** EMA Sweep Confirmation Break v1, generic Strategy/Experiment proposal and analytical contracts, price-triggered runner/persistence, auditable result landmarks, and Experiment workstation delivered. PAPER/LIVE behavior remains deferred.
- **Validation:** Full suite **316 passed, 1 skipped, 4 warnings**; targeted backend/web tests, typecheck, lint, migrations, and clean disposable database gates passed. The six former failures were correctly classified as stale obsolete-Strategy registration expectations and stale database integration expectations after the approved catalog/clean-schema changes; no obsolete behavior was restored. The one skip is the credentialed external OANDA test.
- **Real OANDA/browser evidence:** Current OANDA Practice EUR/USD one-month flow completed as Experiment `2ff310d8-f462-4df8-a0e4-275a7d99a0a1`: Confirmation Break v1, immutable snapshot, M1 MID/BID/ASK with native M15, 10 Trades, `DETERMINED`, 960 disclosed gaps, `/price-analysis` HTTP 200. Local Host MCP result and Trade 1/2 pages showed current Strategy identity, persisted landmarks/charts, accessibility evidence, and empty console/failed-network diagnostics. No secrets recorded.
- **Deferred:** PAPER and LIVE lifecycle behavior; dedicated Playwright E2E remains a non-gating reproducibility follow-up because its hard-coded port was occupied.
- **Memory-save receipt:** `Memory saved to memory.md.` on 2026-08-25 after explicit user confirmation; secret-safe update only, no secrets recorded.

<!-- completion-id: experiment-identity-contract -->
## Experiments frontend, workstation refresh, and authoritative identity contract — completion record

- **Date/status:** 2026-08-26 — terminal R1 PASS.
- **Scope:** Responsibility-based Experiments frontend rebuild, neutral Atlas workstation refresh, local Geist typography, chart token resolution, trader-facing Strategy/Experiment/Trade presentation, and typed FastAPI identity assembled from immutable Experiment, DatasetSnapshot, VenueInstrument, Instrument, and StrategyVersion facts. No new persistence or PAPER/LIVE behavior.
- **Validation:** Canonical receipt `dispatch/workstreams/experiment-correctness-load-ui-audit/TASK-19-rebuild.md` records frontend 23-test suite, typecheck, lint, build, backend Experiment API integration 9 passed, Strategy integration 8 passed, and Local Host Strategy/Experiment/Trade identity checks.
- **Review:** `dispatch/workstreams/experiment-correctness-load-ui-audit/REVIEW.md` — R1 PASS; no Critical or Important findings.
- **Memory-save receipt:** `memory.md` successfully updated on 2026-08-26 after user approval; no secrets.

<!-- completion-id: foundation-freeze-01-reference-strategy -->
## Foundation Freeze 01 — Reference Strategy Correctness — completion record

- **Date/status:** 2026-08-26 — implementation, validation, and review PASS; merged to `main`.
- **Commit:** `58d932a Freeze reference strategy semantics` (fast-forward from `main`).
- **Scope:** Corrected authoritative EMA Sweep Confirmation Break v2 semantics, immediate strict confirmation, Strategy-owned W1–W5 pending window, ATR14 stop timing, schema/evidence versioning, nullable non-authoritative expiry, runner handoff, persistence constraints, and public regression coverage.
- **Validation:** PostgreSQL `atlas_test` migrated to head; full backend suite `322 passed, 1 skipped, 4 warnings`; targeted tests, compileall, Ruff, and diff checks passed.
- **Review:** `dispatch/workstreams/foundation-freeze-01-reference-strategy/REVIEW.md` — PASS; no blockers.

<!-- completion-id: foundation-freeze-02-experiment-correctness -->
## Foundation Freeze 02 — Experiment Correctness and Result Immutability — completion record

- **Date/status:** 2026-08-27 — final external-review remediation, validation, and independent review **PASS**; fast-forward merged to `main`.
- **Commits:** `efe4e62` Freeze Experiment correctness and immutable results; `a9c0436` Remediate Freeze 02 review blockers; `0f04b30` Narrow Freeze 02 failure ownership.
- **Scope:** Canonical equity/result correctness, independent drawdown amount and percentage maxima, immutable result state, and seam-owned historical Experiment failure classification. Strategy lookup, execution, Risk, accounting, persistence, and unexpected-engine failure ownership remain narrow and typed. Freeze 03 was not started.
- **Validation:** PostgreSQL migration cycle **2 passed**; PostgreSQL integration **37 passed**; non-integration **294 passed, 1 skipped, 39 deselected**; focused diagnostics/metrics **27 passed**; Experiments **84 passed**; migration revision, compileall, Alembic heads, and diff checks passed.
- **Review:** `dispatch/workstreams/foundation-freeze-02-experiment-correctness/REVIEW.md` — PASS; no unresolved Important or Critical findings.
- **Git state:** Merged from `solo/foundation-freeze-02-experiment-correctness` at `0f04b30`; workstream closed. Pre-existing untracked `.codegraph/` and `frontend/.env.local` were untouched.

<!-- completion-id: dogfood-01-protection-trade-identity -->
## Dogfood 01 — Protection Trade Identity — completion record

- **Date/status:** 2026-09-03 — T001 BUILD and root VALIDATION completed; the original
  review finding I-001 was resolved by the R001 BUILD/VALIDATION/REVIEW chain. Final review
  **PASS** with no unresolved Critical or Important findings.
- **Commit:** `03092e6` Repair OANDA Trade identity readback; the feature branch was pushed
  to GitHub and fast-forward merged into `main`.
- **Scope:** Repaired account-scoped OANDA execution/protection and uncertain-entry Trade
  readback proof without fabricating provider `accountID`, and corrected accountless Trade
  attribution in OANDA reconciliation. Explicitly supplied null or mismatching account
  identity remains fail-closed. Strategy, Risk, persistence/schema, provider-neutral
  reconciliation coordinator, runtime authority, mutation barriers, retry semantics, and
  historical Dogfood 01 evidence were unchanged.
- **Validation:** Final remediation evidence records targeted explicit-null regressions
  **3 passed**, focused execution/protection/uncertain-entry/reconciliation/durable/runtime
  checks **196 passed**, safe backend suite **1121 passed, 4 skipped**, and changed-slice
  Ruff format/lint, Pyright, and `git diff --check` passed. Four pre-existing warnings and
  inherited frozen-architecture metadata are documented as non-blocking.
- **Git/state:** `solo/dogfood-01-protection-trade-identity` and `main` were pushed to
  GitHub; the feature branch was fast-forward merged into `main`; `dispatch/ACTIVE.md` was
  cleared; all workstream and remediation evidence is preserved. No credentialed OANDA
  mutation, PAPER runtime start, activation, retry, or historical repair occurred.
