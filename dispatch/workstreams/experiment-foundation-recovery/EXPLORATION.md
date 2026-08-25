# Exploration — Experiment Foundation Recovery

## Governing contracts

- `AGENTS.md:9,17,19-21,47-57` defines EUR/USD/OANDA Practice, 15m Strategy, 1m base, canonical lifecycle, no-lookahead/completed-bar/idempotency invariants, and immutable StrategyVersion/Experiment/DatasetSnapshot rules.
- `context/features/experiments.md:15-26,32-70,88-102` specifies load → snapshot → M15 → validation, native M15 + sparse BID/ASK execution, post-decision execution, and sequencing tests.
- `context/features/experiment-results.md:11-17,43-57,67-73` requires completed-only results, immutable provenance, explicit assumptions/gaps, and canonical execution lineage.
- `context/architecture/strategy-contract.md:15-37,63-85,99-113`, `market-data-model.md:11-21,23-45,63-81,91-97`, `domain-model.md:7-18,27-33,63-101,143-157`, `runtime-model.md:29-41,71-85`, `accounting-model.md:15-29,39-57,59-89`, and `database.md:5-9,19-25,37-43,65-79,93-107` own the Strategy boundary, UTC/bar semantics, canonical lifecycle, historical runner separation, Fill-driven accounting, and PostgreSQL/Alembic invariants.

## Relevant files and traced flow

### StrategyVersion → requirement → acquisition

- `backend/domain/strategy.py:166-200` — `StrategyContext` hard-codes OANDA EUR/USD M15 MID; enforces UTC evaluation, strict bar ordering, and `bar.end_time <= evaluation_time`.
- `backend/domain/strategy.py:506-559` — `StrategyVersion` stores immutable fingerprint, implementation, primary timeframe, warm-up, and state schema; defaults are M15 and 100 warm-up bars.
- `backend/domain/strategy_requirements.py:13-73` — `requirement_for_version()` is the intended seam, but defaults and `resolution=primary_timeframe` still set MID independently; loader consumes warm-up rather than all persisted requirement metadata.
- `backend/persistence/models.py:52-97` — persistence stores `context_timeframes`, capabilities, primary timeframe, and warm-up, but downstream context/clock validation does not consume these fields generically.
- `backend/integrations/oanda/source.py:192-256` — adapter exposes M1 MBA (`fetch`), native M15 MID (`fetch_native_m15`), and sparse M1 BID/ASK (`fetch_execution_m1`); provider payloads stay private.
- `backend/market_data/ingestion.py:442-601` — `load_v2()` fetches native M15 and sparse execution, rejects incomplete provider candles, applies M1 execution bars, then creates V2 snapshot.

### Acquisition → Snapshot V2 → configuration

- `backend/market_data/ingestion.py:442-586` — V2 fingerprint covers ordered analytical members, execution members, and gaps. Missing native M15 starts are recorded as `NON_BLOCKING` gaps.
- `backend/persistence/market_data_repository.py:533-630` — `create_v2_validated()` persists immutable analytical M15 rows, execution memberships, and gaps; V2 is `base_resolution="M15"`, components MID.
- `backend/persistence/market_data_repository.py:640-702` — legacy membership reads omit `is_current` deliberately, preserving captured facts. V2 runner uses dedicated analytical/execution tables.
- `backend/experiments/configuration.py:180-317` — validates StrategyVersion/venue, dispatches V2 to native validation and V1 to current membership + M1→M15 aggregation.
- `backend/experiments/configuration.py:319-392` — V2 correctly avoids V1 wall-clock component coverage because execution is sparse; it checks native analytical bars and persisted blocking gaps, but not executable BID/ASK availability per decision frontier.
- `backend/experiments/configuration.py:394-461` — creation revalidates coverage and snapshots parameters/risk/simulation; `MODEL_VERSION` remains `PHASE4_HISTORICAL_EXECUTION_V1` even for V2 snapshots.

### Configuration → clock → runner → execution → persistence/API/frontend

- `backend/experiments/clock.py:29-68,87-188` — `M1Observation` supports full ASK/BID/MID or sparse ASK/BID; `SimulationClock` indexes M1 by start and M15 by end, selects warm-up, and still validates OANDA EUR/USD M15 MID.
- `backend/experiments/clock.py:190-276` — observations enforce complete M1 and skip scheduled closures; frames use `frontier-1` as completed signal minute and `frontier` as executable opens. Sparse mode bypasses missing completed-minute validation.
- `backend/experiments/runner.py:346-450` — schema-first V2 dispatch, then PHASE4, then legacy V1; legacy re-aggregates M1 MID and uses full MBA assumptions.
- `backend/experiments/runner.py:451-527` — `_run_v2()` loads native analytical and sparse execution memberships, evaluates warm-up frames, evaluates decisions only when an execution observation shares the frontier, applies protection, closes at final observation, persists gaps, and completes via `_complete_phase4()`.
- `backend/experiments/runner.py:833-950` — canonical TradeIntent/RiskDecision/Order/Fill path; adverse-slipped quote for risk, protection after entry, LONG valuation at BID and SHORT at ASK.
- `backend/experiments/lifecycle.py:152-242,244-297` — durable RUNNING claim precedes facts; duplicate commands serialize; committed partial state fails closed; fallback failure is sanitized and separate.
- `backend/api/experiments.py:234-294,296-377,435-459` — options, coverage, create, and run endpoints. API assumptions are fixed to M1/MID/BID-ASK.
- `backend/api/historical_data.py:98-206` — durable load endpoint takes only StrategyVersion + UTC range, reports OANDA Practice, and schedules coordinator; no provider/credential selector.
- `frontend/components/experiment-workflow.tsx:1540-1647,1674-1744,1989-2171,2251-2319` — durable load attachment, StrategyVersion/Snapshot selection, proof/coverage, and creation gating. Copy still says “stored in market_bars → derived M15” and “Earliest/Latest M1” for V2 native snapshots.

## Duplicated assumptions and transitional paths

1. M15/MID/provider literals are repeated in `StrategyContext` (`strategy.py:187-194`), clock (`clock.py:133-184`), configuration (`configuration.py:226-256`), OANDA source (`source.py:218-256`), API options (`experiments.py:267-293`), and frontend copy. The requirement seam exists but is not authoritative end-to-end.
2. Warm-up is independently implemented by `StrategyVersion.warm_up_bars` (`strategy.py:514-516`), `requirement_for_version()` (`strategy_requirements.py:61-72`), coordinator planning (`historical_load.py:174-223,293-360`), V1 aggregation (`configuration.py:262-275`), V2 native counting (`configuration.py:334-353`), and clock selection (`clock.py:116-125`).
3. V1/transitional behavior remains in runner (`runner.py:373-450`), load coordinator (`historical_load.py:169-172,250-371`), and ingestion (`ingestion.py:366-440,603-628`). This compatibility surface gives multiple definitions of Experiment data semantics.
4. V2 snapshot schema dispatch is schema-first, but Experiment model/risk/simulation labels remain PHASE4/V1 (`configuration.py:36-38,444-458`; `runner.py:281-284`).
5. Frontend V1 assumptions remain in proof and coverage copy (`experiment-workflow.tsx:1647,1831-1869,1961-1984,2246-2249`), while `StateDisclosure` (`:423-435`) does not distinguish native analytical V2 from derived V1.

## Critical sparse-M1 sequencing bug

- V2 stores each BID/ASK row as an independent sequence ordered by `(start_time, component)` (`ingestion.py:465-520`). Clock groups them by minute and `observations()` correctly emits one sparse BID+ASK observation (`clock.py:128-163,205-222`).
- **Bug:** `frames()` emits a decision frame for every native M15 frontier in sparse mode without requiring completed M1 at `frontier-1` (`clock.py:239-249`). `_run_v2()` then evaluates only when `observations()` happens to contain an observation at the same frontier (`runner.py:493-512`). If the first post-decision sparse M1 is absent, a native M15 decision is silently skipped while V2 coverage can still be valid (`configuration.py:360-380`). This can yield an under-traded/zero-trade result instead of an explicit execution-data outcome.
- **Related hazard:** protection is only applied inside the sparse observation loop (`runner.py:502-517`). Missing sparse minutes receive no protection check. Current V2 gaps cover absent native M15 starts, not absent sparse execution minutes (`ingestion.py:522-543`), and V2 validation only checks persisted `blocked` gaps (`configuration.py:368-380`).
- Same-frontier entry/protection ordering itself is correct: `_run_v2()` enters before `_apply_protection()` (`runner.py:503-512`), and `_apply_protection()` returns while flat (`runner.py:890-900`). The missing-data outcome is the untested edge.

## Persistence, migrations, and tests

- `backend/persistence/models.py:142-215` constrains market bars to completed M1 and snapshot combinations: V1=M1+ASK/BID/MID; V2=M15+MID.
- `backend/persistence/models.py:230-305` defines append-only analytical, sparse execution, and gap membership tables. No DB constraint requires both BID and ASK for each minute.
- `backend/persistence/migrations/versions/0009_historical_snapshot_v2.py:19-49` adds V2 tables/constraints/triggers; `0011_fix_v2_snapshot_trigger.py:1-23` fixes table-specific `NEW` field dispatch and is required at head.
- `backend/persistence/models.py:308-352` plus migration `0008_historical_load.py` implement durable single-load state, bounded progress, and terminal consistency. `historical_load.py:162-249` uses short transactions and never resumes provider I/O after interruption.
- Clock tests `backend/tests/experiments/test_clock.py:42-70,72-86,88-103,127-145` cover signal-bar exclusion, sparse acceptance, warm-up, and full observations, but not missing post-decision sparse execution or protection through sparse gaps.
- V2/fingerprint tests `backend/tests/market_data/test_snapshot_v2_contract.py:21-93`; ingestion V2 structural test `backend/tests/integration/test_market_data_ingestion.py:207-278`; lifecycle claim/failure tests `backend/tests/integration/test_experiment_lifecycle.py:100-223`; Phase5/Phase4 compatibility test `backend/tests/integration/test_phase5_valid_run.py:102-260`. No end-to-end sparse V2 sequencing golden flow was found.

## Risks, blockers, and context gaps

- **High:** silent sparse decision skips can create false no-trade/under-traded results.
- **High:** V2 validation does not define whether absent post-decision BID/ASK means failure, explicit skipped decision, or conservative gap resolution.
- **High:** V1/V2 runner and loader paths can receive a fix inconsistently.
- **Medium:** persisted timeframe/context/capability metadata can drift from hard-coded StrategyContext/clock checks.
- **Medium:** V2 result quality remains default `DETERMINED` despite gap decisions (`runner.py:540-557`), contrary to explicit result disclosure requirements.
- Integration verification requires `ATLAS_TEST_DATABASE_URL` ending in `_test` (`backend/tests/integration/test_phase5_valid_run.py:47-54`). No credentials or environment files were read.
- Unknowns needing architecture confirmation: policy for missing sparse executable observations; retirement boundary for V1 paths; whether V2 should receive a distinct model/result version.

## Minimal likely change areas

1. Make `StrategyMarketDataRequirement` authoritative through loader, V2 validation, clock, and StrategyContext while retaining current slice constraints at boundaries.
2. Define/persist/validate per-minute sparse BID/ASK completeness and make `_run_v2()` fail or record the prescribed explicit outcome rather than silently skip.
3. Align V2 model/result labels with snapshot schema or document one explicit compatibility mapping.
4. Add deterministic tests for missing first post-decision minute, protected-position sparse gap, present BID/ASK decision, same-bar entry/protection, V2 coverage diagnostic, and immutable native membership.
5. Branch API/frontend proof and assumptions between V1 “M1 → derived M15” and V2 “native M15 + sparse M1 BID/ASK”.
