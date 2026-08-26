# TASK-02 — Runner / Persistence Builder

- **Task:** Implement generic immediate/price-triggered Experiment proposal
  watching and durable proposal facts/diagnostics.
- **Outcome:** COMPLETE

## Changed files

- `backend/experiments/runner.py` — added generic proposal watcher with strict
  post-decision observations, ASK/BID directional trigger crossing, gap-through
  open selection versus trigger touch, armed expiry, one pending proposal, and
  actual-fill Risk/target flow. Proposal outcomes are recorded as immutable
  diagnostics.
- `backend/persistence/models.py` — added proposal policy/trigger/expiry fields
  and immutable `ExperimentProposalDiagnosticModel`.
- `backend/persistence/trading_repository.py` — persists proposal diagnostics
  and proposal metadata.
- `backend/persistence/migrations/versions/0007_proposal_watch.py` — clean
  development schema migration and constraints for proposal shape/status and
  diagnostic events.

## Validation receipts

- `python -m compileall -q backend/experiments/runner.py backend/persistence/models.py backend/persistence/trading_repository.py backend/persistence/migrations/versions/0007_proposal_watch.py`
  — passed.
- `python -m pytest backend/tests/experiments backend/tests/execution backend/tests/integration/test_migrations.py -q`
  — **86 passed, 2 skipped**.

## Concerns

- Existing legacy `_run_phase4` code remains untouched and is not used by the
  V2 execution entry point; no Strategy-name branch was added.
- Proposal facts remain append-only. Terminal outcomes are represented by the
  diagnostic relation rather than mutating an inserted TradeIntent.

## Reusable receipts

- Trigger policy is interpreted entirely from `StrategyDecision.entry_policy`,
  trigger price/basis, and expiry fields.
- LONG watches ASK and SHORT watches BID; selected gap/open or touch price is
  passed through the existing adverse-slippage adapter exactly once.
- Observations at the decision frontier are excluded; pending proposals expire
  without stale submission and missing execution produces a durable diagnostic.

## Follow-up receipt (TASK-03 blocker fix, attempt 1)

- `_create_intent` now persists `setup_facts`, generic `evidence`, and generic
  `landmarks` inside immutable rationale for every proposal; no Strategy-name
  branching or rerun-based inference was added.
- Added retrieval coverage in
  `backend/tests/integration/test_fill_application.py` proving structured facts
  survive persistence retrieval.
- `python -m pytest backend/tests/integration/test_fill_application.py backend/tests/experiments backend/tests/execution -q`
  — **86 passed, 4 skipped** (integration skips require `ATLAS_TEST_DATABASE_URL`).
- **Status: DONE.**

## Follow-up receipt (current-Strategy integration validation)

- Updated obsolete PostgreSQL golden-flow fixtures to register and persist EMA
  Sweep Confirmation Break v1, exercising the immediate-next-candle trigger and
  terminal protection path; revised market-data integration assertions for the
  generic StrategyContext metadata boundary.
- Preserved linear migration chain and changed migration assertions to inspect
  current invariant expressions rather than historical constraint names. Fixed
  the model/migration `BIGINT` sequence type mismatch.
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' pytest backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py backend/tests/integration/test_golden_flows.py backend/tests/integration/test_market_data_ingestion.py -q` — **10 passed**.
- **Status: DONE.**

- Added deterministic non-zero slippage LONG/SHORT entry assertions; corrected
  expected SHORT fill to `1.09998` (BID `1.1000` less two ticks).
- `python -m pytest backend/tests/execution/test_simulated.py backend/tests/experiments backend/tests/test_migration_revision.py -q` — **88 passed**.

## Follow-up receipt (R1 findings 2/3, attempt 1)

- Removed the runner's effective double-slippage risk by treating the
  pre-submission quote as the adapter-predicted executable quote, executing the
  raw observation once, asserting the resulting Fill equals that prediction,
  and resolving the protection target from the actual Fill price.
- Added clean-model constraints for action/policy shape, ASK/BID trigger basis,
  positive expiry bars, and expiry strictly after the decision frontier. Added
  migration `0008_proposal_constraints` and migration assertions.
- `uv run alembic -c alembic.ini upgrade head` — passed (`0007_proposal_watch -> 0008_proposal_constraints`).
- `python -m pytest backend/tests/execution backend/tests/experiments backend/tests/test_migration_revision.py -q` — **87 passed**.
- **Status: DONE.**

## Follow-up receipt (validation migration-head fix, attempt 1)

- Changed `0007_proposal_watch.down_revision` from the obsolete parallel
  `0006_phase_4_persistence` branch to canonical head
  `0013_result_quality_degraded`, producing one linear Alembic head while
  preserving the proposal schema and reversible downgrade.
- Updated migration-head and schema assertions for the proposal diagnostic
  table and TradeIntent proposal columns.
- `python -m pytest backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py backend/tests/experiments backend/tests/execution -q`
  — **85 passed, 2 skipped, 2 unrelated failures**. Migration-head failure is
  resolved; the remaining failures are existing Strategy registration fixture
  expectations and require the Strategy owner. PostgreSQL migration tests are
  skipped because `ATLAS_TEST_DATABASE_URL` is unavailable.
- **Status: DONE for Runner/Persistence; unrelated suite failures reported.**
- Follow-up verification: `python -m pytest backend/tests/test_migration_revision.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_results.py backend/tests/execution -q` — **37 passed**.

## Follow-up receipt (real-run persistence blocker, final bounded attempt)

- Diagnosed safely from the disposable database: one PRICE_TRIGGERED
  TradeIntent was inserted, with zero RiskDecision/Order/diagnostic rows. The
  runner then treated `M1Observation` as `ExecutionObservation` while watching
  (`ask_high`/`bid_low`), causing the broad sanitized `PERSISTENCE_FAILURE`.
- Fixed the runner to normalize the M1 observation before generic trigger
  evaluation and to retain the original M1 timestamp/provenance for persistence.
  No Strategy-specific branch or compatibility machinery was added.
- `python -m pytest backend/tests/experiments backend/tests/execution backend/tests/test_migration_revision.py -q`
  — **87 passed**.
- **Status: DONE.**
