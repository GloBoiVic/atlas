# T027 — Phase telemetry and progress contract

Status: `DONE_WITH_CONCERNS`

Implement the developer-approved performance evidence contract for the authoritative
V2 path. Before the first provider call, derive and durably expose expected provider
request counts per product. Make progress explicit: completed/total provider requests
are per product, and `completed_units` is no longer a shared opaque counter or paired
with `total_units=None`.

Instrument, without changing trading/data semantics:

- acquisition planning;
- M15 and M1 provider request count plus elapsed OANDA request durations;
- M15 and M1 persistence duration per batch;
- final coverage/integrity validation;
- snapshot membership construction;
- fingerprinting;
- total elapsed time and baseline/peak RSS.

Report expected requests before acquisition, completed/total requests by product,
average and p95 provider request duration, average and p95 persistence duration per
batch, and rows inserted per second. Keep telemetry bounded and redacted. Inspect and
test that policy closures affect expected-observation validation only, not provider
range splitting; retain the configured OANDA bounds for safe larger calendar requests.

Run a short representative sample before any full-year run. Use its measured dominant
bottleneck to scope exactly one evidence-based remediation; do not optimize other
stages speculatively. Preserve durable stopped-run facts and verify Freeze 03 resume
semantics before reusing them.

## Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T027-phase-telemetry-and-progress.md`

FILES CHANGED:

- `backend/market_data/ingestion.py`
- `backend/market_data/historical_load.py`
- `backend/persistence/historical_data_load_repository.py`
- `backend/market_data/freeze03_benchmark.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- `backend/tests/test_historical_data_load.py`

IMPLEMENTATION:

- Authoritative V2 planning now counts deterministic bounded M15/M1 provider windows
  for both products before the first provider call, then replays the bounded planner
  without retaining a request-sized plan. Progress is `m15`/`m1` request counts with
  `completed_units` counting only validated canonical plus successful acquisition-window
  commits; durable planning assigns a monotonic `plan_generation`.
- Added strict `ATLAS_HISTORICAL_PROGRESS_V1` validation, redacted latest-window-only
  progress, and an 8 KiB serialized cap. Legacy range columns remain empty compatibility
  fields and are not used for resume.
- Added bounded fixed log2 duration histograms (`[1..2^16]` plus zero/overflow),
  nearest-rank p95, per-product provider and canonical-persistence timing, rows/sec,
  planning/validation/snapshot-membership/fingerprinting/total timing, and normalized
  baseline/peak RSS. Snapshot membership timing remains separate from canonical
  observation persistence. Coordinator persistence stores terminal telemetry in the
  durable coverage summary.
- Corrected provider range formation to coalesce across policy closures and split only
  at the configured OANDA bounds (M1 4,000 minutes; M15 60,000 minutes). Closure policy
  remains validation semantics.
- Extended the deterministic fixture benchmark result with terminal telemetry and
  bounded progress-payload measurement. No OANDA request or hours-long run was started.

CHECKS / EVIDENCE:

- `pytest -q backend/tests/test_historical_data_load.py` — 22 passed, 1 skipped.
- Focused telemetry/range tests — 4 passed.
- Prior complete V2 regression run — 35 passed, 1 skipped; deterministic fixture
  benchmark scenarios included fresh month/year, covered repeat, and interrupted/resumed.
- `ruff check` on all changed Python files — passed.
- `python -m compileall -q` on changed implementation modules — passed.
- `git diff --check` — passed.
- Short deterministic fixture benchmark (representative year window, not full-year
  acceptance): fresh year reported expected/completed `m15=1/1`, `m1=12/12`, planning
  311 ms, provider `m15=155 ms avg / 256 ms p95`, `m1=81 ms avg / 128 ms p95`,
  canonical persistence `m15=4 ms avg / 4 ms p95`, `m1=81 ms avg / 256 ms p95`,
  validation 2,002 ms, snapshot membership 733 ms, fingerprinting 4,652 ms,
  total 10,120 ms, 68,126 membership rows, and baseline/peak RSS
  132,763,648/132,763,648 bytes. Maximum progress payload was 474 bytes and
  maximum serialized terminal telemetry was 855 bytes; maximum canonical batch was
  7,976 rows (4,000 M1 minutes × BID/ASK).
- Covered repeat reported `0/0` for both products and zero provider calls. The
  interrupted/resumed fixture completed its remaining `m1=3/3` with repeat calls,
  without duplicating the final fingerprint.

FINDINGS / CONCERNS:

- The measured short fixture hotspot is fingerprinting (4,652 ms), ahead of validation
  and persistence. No speculative remediation was made; the one evidence-based
  bottleneck remediation remains a follow-up after this telemetry gate.
- Genuine credentialed OANDA Practice full-calendar-year and restart evidence remains
  validation work and was intentionally not started. Existing durable `atlas_test`
  facts were not reset or modified.

- Audit after the sample found that the stopped run's legacy 262 M1 windows leave
  closure-only holes between adjacent windows. The current resume planner would treat
  those holes as uncovered and could re-request them; T029 is opened to remove only
  those closure-only requests before acceptance.
