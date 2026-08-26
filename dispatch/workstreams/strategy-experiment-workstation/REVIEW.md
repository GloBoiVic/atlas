# R1 Review — Strategy Experiment Workstation

**Decision: BLOCKED**

Reviewed `PLAN.md`, `ARCHITECTURE.md`, `EXPLORATION.md`, `READY.md`,
`TASK-01.md` through `TASK-04.md`, `VALIDATION.md`, root `dispatch/ACTIVE.md`,
the Strategy/domain/runtime/market-data and Experiment/result/design context,
and the changed backend/frontend source. CodeGraph structural checks were run
first. No application code or Git state was changed by this review.

## Findings

### Important — generic Strategy boundary is not actually metadata-driven

- **Evidence:** `backend/domain/strategy.py:237-244` rejects every context that
  is not OANDA EUR/USD M15 MID, while `backend/strategies/contract.py:49-52`
  adds `StrategyDefinition.required_*` metadata. `contract.py:202-210` only
  partially uses that metadata. The blueprint requires analytical requirements
  to be declarative and generic (`ARCHITECTURE.md:112-129`), and explicitly
  disallows provider-specific Strategy requirements.
- **Remedy:** Move provider/timeframe/component validation out of the domain
  context (or validate against the active definition at the contract boundary),
  retaining the initial EUR/USD/OANDA/M15/MID restriction in Experiment
  configuration. Add a contract test proving a second definition can use its
  declared analytical metadata without changing `StrategyContext`.

### Important — configured slippage is applied twice and target is not from the actual fill

- **Evidence:** `backend/experiments/runner.py:917-923` adds
  `self.execution.slippage` to the quote before PRE_SUBMISSION Risk. Risk then
  resolves target from that quote (`backend/risk/service.py:122-144`). The same
  observation is passed to `SimulatedExecutionAdapter.execute` at
  `runner.py:929-931`, whose entry fill applies slippage again
  (`backend/execution/simulated.py:160-166`). Thus the persisted target is based
  on one slipped price but the Fill is two slips away. This violates the exact
  actual-fill target rule and the TASK-02 receipt claiming slippage is applied
  exactly once.
- **Remedy:** Establish one explicit boundary for adverse slippage: either pass
  the raw selected executable quote to Risk and use an execution observation
  that applies slippage once, or make the adapter consume an already-slipped
  quote without applying it again. Resolve/re-persist protection from the
  actual Fill price, and add non-zero-slippage assertions for LONG and SHORT
  target geometry and quantity.

### Important — persistence constraints do not enforce the stated proposal invariants

- **Evidence:** `backend/persistence/models.py:410-418` and migration
  `0007_proposal_watch.py:19-22` constrain policy shape and positive trigger,
  but do not constrain `trigger_price_basis` to ASK/BID, `expiry_bars` to a
  positive value, action/direction/policy matching, or `expiry_time` after
  `decision_frontier`. The blueprint explicitly requires database constraints
  for valid action/policy combinations and UTC/finite values
  (`ARCHITECTURE.md:174-190`).
- **Remedy:** Add clean-schema CHECK constraints (including direction/basis,
  positive expiry bars, and expiry frontier ordering) and persistence tests that
  attempt each malformed row. Keep domain validation as defense in depth.

### Important — implementation proceeded while the control artifact still forbids it

- **Evidence:** `dispatch/ACTIVE.md:6` says `EXPLORE — no implementation
  approval`; `PLAN.md:12` says no implementation approval was granted, while
  TASK-01 through TASK-04 report completed implementation. This is a direct
  plan/process alignment failure, independent of runtime behavior.
- **Remedy:** Have the orchestrator record explicit approval and advance the
  workstream status before accepting implementation receipts; do not silently
  treat stale control state as approval.

## Validation evidence and blockers

Reused the latest `VALIDATION.md` receipts:

- Strategy/domain/Experiment/execution/migration targeted suite: **183 passed**.
- Web tests: **9 files / 23 tests passed**; typecheck and lint passed.
- Fresh real OANDA Practice EUR/USD one-month flow completed with the current
  Confirmation Break v1: 10 Trades, `DETERMINED`, persisted provenance,
  `/price-analysis` HTTP 200, and two current Trade detail inspections with
  server-supplied landmarks (`VALIDATION.md:180-207`). This supports persistence,
  evidence, API/UI, immediate post-decision execution, and no-PAPER scope.
- The receipt separately records **13 integration-test errors solely because
  `ATLAS_TEST_DATABASE_URL` is absent** (`VALIDATION.md:184-188`). This is an
  environmental acceptance blocker, not a demonstrated code defect; provision
  the test database and rerun `python -m pytest -q`.
- E2E execution was previously blocked by the occupied Playwright port
  (`VALIDATION.md:74`); browser MCP evidence exists, but a clean supported E2E
  run remains desirable before release.
- The receipt reports 960 persisted gap decisions. They are disclosed and the
  run is marked `DETERMINED`; acceptance must retain that disclosure rather than
  treating the data as gap-free.

## Scope and safety assessment

The implementation does not add PAPER/LIVE lifecycle behavior, broker calls in
the Strategy, a Strategy-name branch in the watcher, or browser-side pattern
detection. The current receipts demonstrate sanitized failures, immutable
lineage, BID/ASK execution, trigger/open-vs-touch handling, and persistent
landmarks. Before production readiness, resolve the two execution/contract
correctness findings above, enforce persistence invariants, obtain the missing
integration environment, and rerun the required acceptance receipts.

**R1 outcome: BLOCKED.** There are Important code findings and an unresolved
required integration acceptance gate. No Critical finding was identified.

---

# R1 Re-review — Remediation Check

**Decision: BLOCKED (environmental acceptance gate only)**

Current `dispatch/ACTIVE.md` and `PLAN.md` were reread and are treated as
approved, as requested. Current blueprint, TASK-01 through TASK-04, and the
latest `VALIDATION.md` were reviewed. No source, dispatch artifact other than
this file, or Git state was changed. Unchanged tests were not rerun.

## Prior Important findings

1. **Generic Strategy boundary — RESOLVED.** `StrategyContext` now validates
   only instrument identity and temporal/bar invariants at
   `backend/domain/strategy.py:222-243`; provider, timeframe, and component
   checks are performed against the active definition at
   `backend/strategies/contract.py:192-210`. TASK-01 added a non-EMA declared
   metadata test (`backend/tests/strategies/test_contract.py:83-100`), and its
   receipt reports 100 passing Strategy/domain/configuration tests
   (`TASK-01.md:41-46`). This matches the blueprint's generic metadata boundary.

2. **Double slippage / actual-fill target — RESOLVED.** The runner predicts the
   adapter's slipped executable quote at `backend/experiments/runner.py:914-921`,
   executes the raw observation once at `:929-931`, asserts Fill equality at
   `:932-937`, and resolves protection from `fill.execution_price` at
   `:938-940`. TASK-02 added non-zero slippage coverage and reports 88 targeted
   execution/Experiment tests passing (`TASK-02.md:57-59`), followed by 87
   runner/persistence tests (`TASK-02.md:61-72`). The latest validation reports
   the targeted suite passing (`VALIDATION.md:219-220`). No Important finding
   remains here.

3. **Proposal persistence constraints — RESOLVED in source and migration.**
   `TradeIntentModel` now enforces action/policy shape, basis, positive expiry,
   and expiry ordering at `backend/persistence/models.py:410-422`; the clean
   migration is `0008_proposal_constraints.py:10-14`. The latest receipt confirms
   one Alembic head and migration assertions passing
   (`VALIDATION.md:221-222`), with PostgreSQL execution explicitly unverified
   only because the test database is unavailable. No Important code finding
   remains.

The former control-artifact finding is also closed: current `ACTIVE.md:6` is
`APPROVED` and `PLAN.md:13` records user approval. No PAPER/LIVE behavior was
introduced.

## Remaining acceptance blockers

- **Environmental required blocker — `ATLAS_TEST_DATABASE_URL` missing.** The
  latest full suite is `274 passed, 30 skipped, 13 errors`; all 13 errors are
  integration fixture setup failures due solely to the absent variable
  (`VALIDATION.md:217-224`). This is not a demonstrated application defect,
  but it prevents the required full-suite and PostgreSQL constraint gate.
  Provision the test database and rerun `python -m pytest -q`.
- The prior Playwright run was blocked before execution by an occupied port
  (`TASK-04.md:41-43`). Valid current browser MCP evidence exists and the latest
  validation reports clean console/network checks and current result/trade
  inspection (`VALIDATION.md:233-237`), so this is not a new code finding; a
  clean E2E run remains prudent if the acceptance process requires that command
  specifically.

## Reused acceptance evidence

The fresh real OANDA Practice one-month Experiment remains valid: current
Confirmation Break v1, immutable snapshot/provenance, 10 Trades,
`DETERMINED`, `/price-analysis` HTTP 200, persisted landmarks, and two current
Trade detail inspections (`VALIDATION.md:190-207`). The corrected runtime path
does not alter that run because configured slippage was zero
(`VALIDATION.md:233-235`). Web tests, typecheck, lint, targeted backend tests,
and migration-head checks are green per the latest receipts.

## Final R1 disposition

No Critical or Important application findings remain. R1 nevertheless remains
**BLOCKED** because the required full backend acceptance gate cannot execute
without `ATLAS_TEST_DATABASE_URL`. After provisioning it, rerun the full suite
and confirm no new failures; then R1 may PASS without another OANDA run unless
execution configuration changes.

---

# Final R1 Re-review

**Decision: PASS**

Current `dispatch/ACTIVE.md` (`APPROVED`) and `PLAN.md` (user-approved) were
reviewed with the current blueprint, TASK-01 through TASK-04, and latest
`VALIDATION.md`. No source, other artifact, or Git state was changed; unchanged
tests were not rerun.

## Prior findings and failure classification

- **Generic Strategy boundary: RESOLVED.** `StrategyContext` permits declared
  dimensions (`backend/domain/strategy.py:222-243`) and the contract validates
  against active `StrategyDefinition` metadata (`backend/strategies/contract.py:192-210`).
  The non-EMA test and 100-test receipt are recorded in `TASK-01.md:41-46`.
- **Slippage and actual-fill target: RESOLVED.** The runner predicts the
  adapter fill, executes raw observation once, asserts equality, and resolves
  protection from `fill.execution_price` (`backend/experiments/runner.py:914-940`).
  Non-zero LONG/SHORT coverage and targeted passing receipts are recorded in
  `TASK-02.md:69-83` and `VALIDATION.md:219-220`.
- **Proposal constraints: RESOLVED.** Constraints are present at
  `backend/persistence/models.py:410-422`, with migration `0008` and one
  Alembic head; clean-schema receipts are in `VALIDATION.md:247-253`.
- **Six former failures: correctly classified and resolved.** They were stale
  obsolete-Strategy/database expectations updated for the approved current
  catalog and clean schema, not regressions fixed by restoring obsolete
  behavior (`VALIDATION.md:243-259`). The clean recreated-database full run is
  **316 passed, 1 skipped, 4 warnings** (`VALIDATION.md:255-258`). The sole skip
  is the credentialed external OANDA test.

No Important or Critical finding remains, and no obsolete production behavior
was restored. No PAPER/LIVE lifecycle was added.

## Acceptance evidence

The real OANDA Practice one-month run remains valid: current Confirmation Break
v1, immutable Strategy/snapshot fingerprints, 10 Trades, `COMPLETED`,
`DETERMINED`, 960 disclosed gaps, and `/price-analysis` HTTP 200
(`VALIDATION.md:261-265`). The final changes were test expectation updates and
disposable database recreation/migration application, not runtime semantics.

Local Host MCP result and Trade pages remain valid, showing current Strategy
identity, formatted metrics, persisted M15/EMA chart, requested landmarks,
accessibility evidence, and clean console/network diagnostics
(`VALIDATION.md:263-265`). This satisfies the blueprint browser-evidence path.
The earlier Playwright occupied-port issue is documented as a non-gating
reproducibility follow-up because MCP browser acceptance is complete
(`VALIDATION.md:267-269`).

## Environment and final disposition

The missing `ATLAS_TEST_DATABASE_URL` blocker is closed by the clean
`atlas_test` recreation, successful migrations, and green full-suite receipt
(`VALIDATION.md:249-258`). The one external credentialed-test skip is expected.

**Final R1: PASS.** All prior Important findings are resolved, the six failures
were correctly classified without obsolete behavior, clean database/migration
and full-suite evidence is green, and the valid OANDA plus MCP browser evidence
satisfies the required acceptance gates.
